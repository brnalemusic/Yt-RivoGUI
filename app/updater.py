"""Self-update engine for Yt-RivoGUI.

This module deliberately has no Qt dependency so that update checks and
downloads can also be driven from the command line (``--check-updates`` and
``--update-now``) and from unit tests.

The updater follows the stable GitHub release channel only.  A release is
considered installable when it publishes a ``latest.json`` manifest (or, for
older releases, a ``SHA256SUMS.txt`` file).  Downloads are always verified
against the SHA-256 digest from the manifest before they are executed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)

APP_NAME = 'Yt-RivoGUI'
APP_REPO = 'brnalemusic/Yt-RivoGUI'
APP_URL = f'https://github.com/{APP_REPO}'
RELEASES_URL = f'{APP_URL}/releases'
LATEST_MANIFEST_URL = f'{APP_URL}/releases/latest/download/latest.json'
GITHUB_API_LATEST = f'https://api.github.com/repos/{APP_REPO}/releases/latest'

MANIFEST_SCHEMA = 1
MANIFEST_MAX_BYTES = 512 * 1024
CHECKSUM_MAX_BYTES = 1024 * 1024
DOWNLOAD_MAX_BYTES = 1024 * 1024 * 1024  # 1 GiB safety limit
CHUNK_SIZE = 64 * 1024
TRUSTED_HOSTS = frozenset({'github.com', 'api.github.com', 'objects.githubusercontent.com'})
DEFAULT_CHECK_INTERVAL_HOURS = 12
USER_AGENT = f'{APP_NAME}-updater'
SINGLE_INSTANCE_MUTEX = 'Yt-RivoGUI.SingleInstance'
INSTALL_REGISTRY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Yt-RivoGUI_is1'

_VERSION_RE = re.compile(r'^[vV]?(\d+(?:\.\d+){0,3})$')
_SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')
_progress_callback = Callable[[int, int], None]

__all__ = [
    'APP_NAME',
    'APP_REPO',
    'APP_URL',
    'RELEASES_URL',
    'LATEST_MANIFEST_URL',
    'GITHUB_API_LATEST',
    'SINGLE_INSTANCE_MUTEX',
    'UpdateAsset',
    'UpdateInfo',
    'CheckResult',
    'UpdateSettings',
    'InstallInfo',
    'SingleInstanceGuard',
    'UpdateError',
    'UpdateCancelled',
    'UpdateIntegrityError',
    'UpdateHTTPError',
    'parse_version',
    'normalize_version',
    'is_newer_version',
    'check_for_updates',
    'download_asset',
    'apply_update',
    'update_now',
    'get_app_data_dir',
    'get_update_dir',
    'get_update_log_path',
    'get_install_info',
    'is_frozen',
    'is_running_installed',
    'cleanup_update_cache',
    'load_manifest_from_file',
]


class UpdateError(Exception):
    """Base error raised by the update engine."""


class UpdateCancelled(UpdateError):
    """Raised when the user cancels a download."""


class UpdateIntegrityError(UpdateError):
    """Raised when a downloaded file does not match its checksum."""


class UpdateHTTPError(UpdateError):
    """Raised for non-success HTTP responses."""

    def __init__(self, url: str, code: int, message: str = ''):
        self.url = url
        self.code = code
        self.message = message
        super().__init__(f'HTTP {code} for {url}' + (f': {message}' if message else ''))


@dataclass(frozen=True)
class UpdateAsset:
    """A downloadable file attached to a GitHub release."""

    name: str
    url: str
    size: int = 0
    sha256: str | None = None

    @property
    def has_checksum(self) -> bool:
        return bool(self.sha256 and _SHA256_RE.fullmatch(self.sha256))

    @property
    def is_zip(self) -> bool:
        return self.name.lower().endswith('.zip')


@dataclass
class UpdateInfo:
    """Metadata for one installable release."""

    version: str
    tag: str
    channel: str = 'stable'
    release_url: str = RELEASES_URL
    notes_url: str = RELEASES_URL
    published_at: str = ''
    assets: dict[str, UpdateAsset] = field(default_factory=dict)

    def asset_for(self, *, installed: bool) -> UpdateAsset | None:
        """Returns the most appropriate asset for the current installation mode."""
        if installed:
            return self.assets.get('installer')
        return self.assets.get('portable') or self.assets.get('portable_zip')


@dataclass
class CheckResult:
    """Outcome of an update check, suitable for both GUI and CLI presentation."""

    status: str  # 'update_available', 'up_to_date' or 'error'
    current_version: str
    latest_version: str | None = None
    info: UpdateInfo | None = None
    error_code: str | None = None
    error: str | None = None
    detail: str | None = None

    @property
    def update_available(self) -> bool:
        return self.status == 'update_available'

    @property
    def is_error(self) -> bool:
        return self.status == 'error'


@dataclass
class InstallInfo:
    """Information about a per-user Inno Setup installation."""

    installed: bool = False
    location: Path | None = None
    version: str | None = None
    uninstall_string: str | None = None


class SingleInstanceGuard:
    """Keeps a named Windows mutex alive while the GUI is running.

    ``acquired`` is False when another instance already owns the mutex.  On
    non-Windows platforms the guard is a no-op so the source app keeps working.
    """

    def __init__(self, name: str = SINGLE_INSTANCE_MUTEX):
        self.name = name
        self.acquired = True
        self._handle = None
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            handle = kernel32.CreateMutexW(None, False, self.name)
            if not handle:
                # Let the app start if the guard itself cannot be created.
                return
            if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                self.acquired = False
                return
            self._handle = handle
        except Exception:
            logger.debug('single-instance mutex unavailable', exc_info=True)

    def release(self) -> None:
        if self._handle is not None:
            try:
                import ctypes
                from ctypes import wintypes

                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    def __del__(self):  # pragma: no cover - best-effort cleanup
        self.release()


@dataclass
class UpdateSettings:
    """Small, user-scoped updater preferences persisted as JSON."""

    auto_check_updates: bool = True
    last_check_utc: str | None = None
    skipped_version: str | None = None
    channel: str = 'stable'

    @classmethod
    def load(cls, path: Path | None = None) -> UpdateSettings:
        config_path = path or (get_app_data_dir() / 'settings.json')
        try:
            raw = json.loads(config_path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                return cls()
            return cls(
                auto_check_updates=bool(raw.get('auto_check_updates', True)),
                last_check_utc=_as_optional_str(raw.get('last_check_utc')),
                skipped_version=_as_optional_str(raw.get('skipped_version')),
                channel=_as_optional_str(raw.get('channel')) or 'stable',
            )
        except Exception:
            return cls()

    def save(self, path: Path | None = None) -> None:
        config_path = path or (get_app_data_dir() / 'settings.json')
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = config_path.with_name(f'{config_path.name}.tmp')
            temp_path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temp_path, config_path)
        except Exception as exc:
            logger.warning('Could not save updater settings: %s', exc)

    def mark_checked(self, *, when: datetime | None = None) -> None:
        self.last_check_utc = (when or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

    def should_check(self, *, interval_hours: int = DEFAULT_CHECK_INTERVAL_HOURS) -> bool:
        if not self.auto_check_updates:
            return False
        if not self.last_check_utc:
            return True
        try:
            last = datetime.fromisoformat(self.last_check_utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last.astimezone(timezone.utc)
            return age.total_seconds() >= max(0, interval_hours) * 3600
        except Exception:
            return True

    def should_show_version(self, version: str) -> bool:
        if not self.skipped_version:
            return True
        try:
            return normalize_version(self.skipped_version) != normalize_version(version)
        except ValueError:
            return True


def _as_optional_str(value: Any) -> str | None:
    return str(value) if value not in (None, '') else None


def get_app_data_dir() -> Path:
    """Returns the writable, user-scoped data directory for the application."""
    override = os.environ.get('YTRIVO_DATA_DIR')
    if override:
        path = Path(override).expanduser()
    elif sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        path = Path(base) / APP_NAME
    else:
        base = os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local' / 'share')
        path = Path(base) / 'yt-rivogui'
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_update_dir() -> Path:
    path = get_app_data_dir() / 'updates'
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_update_log_path() -> Path:
    return get_app_data_dir() / 'updater.log'


def append_update_log(message: str) -> None:
    """Appends a timestamped line to the updater log without raising."""
    try:
        log_path = get_update_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with log_path.open('a', encoding='utf-8') as handle:
            handle.write(f'[{timestamp}] {message}\n')
    except Exception:
        pass


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def parse_version(value: str | None) -> tuple[int, ...]:
    """Parses a 1-4 part numeric version, accepting an optional ``v`` prefix."""
    if value is None:
        raise ValueError('version is empty')
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f'invalid version: {value!r}')
    return tuple(int(part) for part in match.group(1).split('.'))


def normalize_version(value: str | None) -> str:
    parts = parse_version(value)
    return '.'.join(str(part) for part in parts)


def _comparison_tuple(value: str | None, length: int = 4) -> tuple[int, ...]:
    parts = parse_version(value)
    return tuple(parts) + (0,) * (length - len(parts))


def is_newer_version(candidate: str | None, current: str | None) -> bool:
    """Returns True when ``candidate`` is strictly newer than ``current``."""
    try:
        candidate_parts = _comparison_tuple(candidate)
        current_parts = _comparison_tuple(current)
    except ValueError:
        return False
    return candidate_parts > current_parts


def _is_checksum(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _is_allowed_url(url: str, *, allow_insecure: bool = False) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme == 'https' and parsed.hostname in TRUSTED_HOSTS:
        return True
    return bool(
        allow_insecure
        and parsed.scheme == 'http'
        and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
    )


def _is_trusted_release_asset(url: str, *, allow_insecure: bool = False) -> bool:
    if not _is_allowed_url(url, allow_insecure=allow_insecure):
        return False
    if allow_insecure and urllib.parse.urlparse(url).scheme == 'http':
        return True
    parsed = urllib.parse.urlparse(url)
    return parsed.path.startswith(f'/{APP_REPO}/releases/download/')


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open_url(
    url: str,
    *,
    timeout: float,
    headers: Mapping[str, str] | None = None,
    allow_insecure: bool = False,
) -> Any:
    if not _is_allowed_url(url, allow_insecure=allow_insecure):
        raise UpdateError(f'untrusted update URL: {url}')
    request_headers = {
        'User-Agent': f'{USER_AGENT}/{_local_version()}',
        'Accept': 'application/json, application/octet-stream, text/plain, */*',
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


def _local_version() -> str:
    try:
        from app import __version__

        return __version__
    except Exception:
        return '0.0.0.0'


def _read_limited(response: Any, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UpdateError('response is too large')
        chunks.append(chunk)
    return b''.join(chunks)


def _fetch_json(url: str, *, timeout: float, allow_insecure: bool = False, limit: int = MANIFEST_MAX_BYTES) -> Any:
    try:
        with _open_url(url, timeout=timeout, allow_insecure=allow_insecure) as response:
            data = _read_limited(response, limit)
    except urllib.error.HTTPError as exc:
        raise UpdateHTTPError(url, exc.code, str(exc.reason or '')) from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f'could not reach GitHub: {exc.reason}') from exc
    except ssl.SSLError as exc:
        raise UpdateError(f'TLS error: {exc}') from exc
    try:
        return json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError('invalid JSON response') from exc


def _asset_from_dict(key: str, value: Any, *, allow_insecure: bool = False) -> UpdateAsset:
    if not isinstance(value, dict):
        raise UpdateError(f'asset {key!r} is invalid')
    name = value.get('name')
    url = value.get('url')
    if not isinstance(name, str) or not name or Path(name).name != name or '/' in name or '\\' in name:
        raise UpdateError(f'asset {key!r} has an invalid name')
    if not isinstance(url, str) or not _is_trusted_release_asset(url, allow_insecure=allow_insecure):
        raise UpdateError(f'asset {key!r} has an untrusted URL')
    raw_size = value.get('size', 0)
    try:
        size = int(raw_size or 0)
    except (TypeError, ValueError) as exc:
        raise UpdateError(f'asset {key!r} has an invalid size') from exc
    if size < 0 or size > DOWNLOAD_MAX_BYTES:
        raise UpdateError(f'asset {key!r} has an invalid size')
    sha256 = value.get('sha256')
    if sha256 is not None and not _is_checksum(sha256):
        raise UpdateError(f'asset {key!r} has an invalid sha256')
    return UpdateAsset(name=name, url=url, size=size, sha256=sha256.lower() if sha256 else None)


def _info_from_manifest(data: Any, *, allow_insecure: bool = False) -> UpdateInfo:
    if not isinstance(data, dict):
        raise UpdateError('manifest must be a JSON object')
    if data.get('schema') != MANIFEST_SCHEMA:
        raise UpdateError('unsupported manifest schema')
    version = data.get('version')
    tag = data.get('tag') or version
    if not isinstance(version, str) or not isinstance(tag, str):
        raise UpdateError('manifest version is missing')
    normalized_version = normalize_version(version)
    normalized_tag = normalize_version(tag)
    if normalized_version != normalized_tag:
        raise UpdateError('manifest version and tag do not match')
    channel = str(data.get('channel') or 'stable').lower()
    if channel != 'stable':
        raise UpdateError(f'unsupported update channel: {channel}')
    release_url = str(data.get('release_url') or RELEASES_URL)
    notes_url = str(data.get('notes_url') or release_url)
    if not _is_allowed_url(release_url, allow_insecure=allow_insecure):
        release_url = RELEASES_URL
    if not _is_allowed_url(notes_url, allow_insecure=allow_insecure):
        notes_url = release_url
    raw_assets = data.get('assets')
    if not isinstance(raw_assets, dict):
        raise UpdateError('manifest assets are missing')
    assets = {
        key: _asset_from_dict(key, value, allow_insecure=allow_insecure)
        for key, value in raw_assets.items()
        if key in {'installer', 'portable', 'portable_zip', 'sha256sums'}
    }
    if not any(key in assets for key in ('installer', 'portable', 'portable_zip')):
        raise UpdateError('manifest contains no installable assets')
    return UpdateInfo(
        version=normalized_version,
        tag=normalized_tag,
        channel=channel,
        release_url=release_url,
        notes_url=notes_url,
        published_at=str(data.get('published_at') or ''),
        assets=assets,
    )


def load_manifest_from_file(path: str | Path, *, allow_insecure: bool = True) -> UpdateInfo:
    """Loads a local manifest.  Intended for tests and staging verification."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return _info_from_manifest(data, allow_insecure=allow_insecure)


def _parse_checksums(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not _is_checksum(parts[0]):
            continue
        name = parts[1].strip().lstrip('*').strip()
        if name:
            result[Path(name).name] = parts[0].lower()
    return result


def _fetch_checksums(asset: UpdateAsset | None, *, timeout: float, allow_insecure: bool) -> dict[str, str]:
    if not asset:
        return {}
    try:
        with _open_url(asset.url, timeout=timeout, allow_insecure=allow_insecure) as response:
            text = _read_limited(response, CHECKSUM_MAX_BYTES).decode('utf-8', 'replace')
        return _parse_checksums(text)
    except Exception as exc:
        logger.warning('Could not fetch release checksums: %s', exc)
        return {}


def _asset_from_release(key: str, raw: Any, *, checksums: dict[str, str], allow_insecure: bool) -> UpdateAsset | None:
    if not isinstance(raw, dict):
        return None
    name = raw.get('name')
    url = raw.get('browser_download_url')
    if not isinstance(name, str) or not isinstance(url, str):
        return None
    if not _is_trusted_release_asset(url, allow_insecure=allow_insecure):
        return None
    try:
        size = int(raw.get('size') or 0)
    except (TypeError, ValueError):
        size = 0
    return UpdateAsset(
        name=name,
        url=url,
        size=max(0, min(size, DOWNLOAD_MAX_BYTES)),
        sha256=checksums.get(name),
    )


def _info_from_release(release: Any, *, timeout: float, allow_insecure: bool) -> UpdateInfo:
    if not isinstance(release, dict):
        raise UpdateError('invalid GitHub release response')
    if release.get('draft') or release.get('prerelease'):
        raise UpdateError('latest release is a draft or pre-release')
    tag = release.get('tag_name')
    if not isinstance(tag, str):
        raise UpdateError('release tag is missing')
    version = normalize_version(tag)
    raw_assets = release.get('assets')
    if not isinstance(raw_assets, list):
        raise UpdateError('release assets are missing')

    assets_by_name = {
        asset.get('name'): asset
        for asset in raw_assets
        if isinstance(asset, dict) and isinstance(asset.get('name'), str)
    }
    checksum_raw = next(
        (asset for name, asset in assets_by_name.items() if name.lower() == 'sha256sums.txt'),
        None,
    )
    checksums: dict[str, str] = {}
    if checksum_raw:
        checksum_asset = _asset_from_release('sha256sums', checksum_raw, checksums={}, allow_insecure=allow_insecure)
        checksums = _fetch_checksums(checksum_asset, timeout=timeout, allow_insecure=allow_insecure)

    assets: dict[str, UpdateAsset] = {}
    installer_raw = next(
        (asset for name, asset in assets_by_name.items() if name.lower().startswith('yt-rivogui-setup-') and name.lower().endswith('.exe')),
        None,
    )
    portable_raw = assets_by_name.get('Yt-RivoGUI.exe')
    zip_raw = next(
        (asset for name, asset in assets_by_name.items() if name.lower().startswith('yt-rivogui-v') and name.lower().endswith('-windows.zip')),
        None,
    )
    if installer_raw:
        installer = _asset_from_release('installer', installer_raw, checksums=checksums, allow_insecure=allow_insecure)
        if installer:
            assets['installer'] = installer
    if portable_raw:
        portable = _asset_from_release('portable', portable_raw, checksums=checksums, allow_insecure=allow_insecure)
        if portable:
            assets['portable'] = portable
    if zip_raw:
        portable_zip = _asset_from_release('portable_zip', zip_raw, checksums=checksums, allow_insecure=allow_insecure)
        if portable_zip:
            assets['portable_zip'] = portable_zip
    if checksum_raw:
        checksum_asset = _asset_from_release('sha256sums', checksum_raw, checksums={}, allow_insecure=allow_insecure)
        if checksum_asset:
            assets['sha256sums'] = checksum_asset

    release_url = str(release.get('html_url') or f'{APP_URL}/releases/tag/{urllib.parse.quote(tag)}')
    if not _is_allowed_url(release_url, allow_insecure=allow_insecure):
        release_url = RELEASES_URL
    return UpdateInfo(
        version=version,
        tag=tag,
        channel='stable',
        release_url=release_url,
        notes_url=release_url,
        published_at=str(release.get('published_at') or ''),
        assets=assets,
    )


def _error_result(current_version: str, code: str, message: str, detail: str | None = None) -> CheckResult:
    return CheckResult(
        status='error',
        current_version=current_version,
        error_code=code,
        error=message,
        detail=detail,
    )


def check_for_updates(
    current_version: str,
    *,
    manifest_url: str | None = None,
    api_url: str | None = None,
    timeout: float = 15.0,
    allow_insecure: bool = False,
) -> CheckResult:
    """Checks the stable GitHub release channel for a newer version.

    The primary source is the ``latest.json`` release asset.  If that asset
    does not exist (older releases), the GitHub API is used and the release
    assets are reconstructed from the API plus ``SHA256SUMS.txt``.
    """
    try:
        current = normalize_version(current_version)
    except ValueError as exc:
        return _error_result(str(current_version), 'invalid_current_version', str(exc))

    manifest_url = (
        os.environ.get('YTRIVO_UPDATE_MANIFEST_URL')
        or manifest_url
        or LATEST_MANIFEST_URL
    )
    api_url = os.environ.get('YTRIVO_UPDATE_API_URL') or api_url or GITHUB_API_LATEST

    info: UpdateInfo | None = None
    try:
        manifest = _fetch_json(manifest_url, timeout=timeout, allow_insecure=allow_insecure)
        info = _info_from_manifest(manifest, allow_insecure=allow_insecure)
    except UpdateHTTPError as exc:
        if exc.code != 404:
            return _error_result(current, _http_error_code(exc), str(exc))
    except UpdateError as exc:
        return _error_result(current, _error_code_for_exception(exc), str(exc))
    except Exception as exc:
        logger.debug('Manifest check failed: %s', exc)
        return _error_result(current, 'unknown', str(exc))

    if info is None:
        try:
            release = _fetch_json(api_url, timeout=timeout, allow_insecure=allow_insecure)
            if not isinstance(release, dict):
                raise UpdateError('invalid GitHub API response')
            manifest_asset = next(
                (asset for asset in release.get('assets', []) if isinstance(asset, dict) and asset.get('name') == 'latest.json'),
                None,
            )
            if manifest_asset:
                manifest_asset_url = manifest_asset.get('browser_download_url')
                if not isinstance(manifest_asset_url, str):
                    raise UpdateError('manifest asset has no URL')
                manifest = _fetch_json(manifest_asset_url, timeout=timeout, allow_insecure=allow_insecure)
                info = _info_from_manifest(manifest, allow_insecure=allow_insecure)
                if info.version != normalize_version(str(release.get('tag_name') or info.version)):
                    raise UpdateError('manifest does not match the latest release tag')
            else:
                info = _info_from_release(release, timeout=timeout, allow_insecure=allow_insecure)
        except UpdateHTTPError as exc:
            return _error_result(current, _http_error_code(exc), str(exc))
        except UpdateError as exc:
            return _error_result(current, _error_code_for_exception(exc), str(exc))
        except Exception as exc:
            logger.debug('GitHub API check failed: %s', exc)
            return _error_result(current, 'unknown', str(exc))

    if info is None:
        return _error_result(current, 'not_found', 'no release information was returned')

    if is_newer_version(info.version, current):
        return CheckResult(
            status='update_available',
            current_version=current,
            latest_version=info.version,
            info=info,
        )
    return CheckResult(
        status='up_to_date',
        current_version=current,
        latest_version=info.version,
        info=info,
    )


def _http_error_code(exc: UpdateHTTPError) -> str:
    if exc.code == 403:
        return 'rate_limit'
    if exc.code == 404:
        return 'not_found'
    if 500 <= exc.code < 600:
        return 'server'
    return 'http'


def _error_code_for_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if 'tls' in text or 'ssl' in text or 'certificate' in text:
        return 'tls'
    if 'could not reach' in text or 'timed out' in text or 'urlopen' in text:
        return 'network'
    if 'manifest' in text or 'asset' in text or 'version' in text or 'json' in text:
        return 'invalid_manifest'
    return 'unknown'


def _retryable_http_error(exc: urllib.error.HTTPError) -> bool:
    return exc.code in {408, 429, 500, 502, 503, 504}


def _download_url(
    asset: UpdateAsset,
    *,
    timeout: float,
    allow_insecure: bool,
    range_start: int,
) -> Any:
    headers = {}
    if range_start > 0:
        headers['Range'] = f'bytes={range_start}-'
    return _open_url(asset.url, timeout=timeout, headers=headers, allow_insecure=allow_insecure)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_asset(path: str | Path, asset: UpdateAsset) -> None:
    """Verifies a downloaded file against the asset metadata."""
    file_path = Path(path)
    if not file_path.is_file():
        raise UpdateIntegrityError(f'downloaded file is missing: {file_path}')
    if asset.size and file_path.stat().st_size != asset.size:
        raise UpdateIntegrityError(
            f'size mismatch for {asset.name}: expected {asset.size}, got {file_path.stat().st_size}'
        )
    if not asset.sha256:
        raise UpdateIntegrityError(f'no checksum available for {asset.name}')
    actual = sha256_file(file_path)
    if not hmac.compare_digest(actual.lower(), asset.sha256.lower()):
        raise UpdateIntegrityError(f'sha256 mismatch for {asset.name}')


def _is_writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.ytrivo-write-', dir=path, delete=True):
            pass
        return True
    except Exception:
        return False


def download_asset(
    asset: UpdateAsset,
    *,
    dest_dir: str | Path | None = None,
    progress: _progress_callback | None = None,
    cancel: threading.Event | None = None,
    timeout: float = 30.0,
    allow_insecure: bool = False,
    require_checksum: bool = True,
) -> Path:
    """Downloads and verifies an update asset.

    Existing complete files are reused.  Partial downloads are resumed with an
    HTTP ``Range`` request when the server supports it.
    """
    if require_checksum and not asset.has_checksum:
        raise UpdateIntegrityError(f'no valid checksum available for {asset.name}')
    if asset.size and asset.size > DOWNLOAD_MAX_BYTES:
        raise UpdateError(f'asset is too large: {asset.size} bytes')

    target_dir = Path(dest_dir) if dest_dir else get_update_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / Path(asset.name).name
    partial = destination.with_name(f'{destination.name}.part')

    if destination.exists():
        try:
            verify_asset(destination, asset)
            if progress:
                size = destination.stat().st_size
                progress(size, size)
            return destination
        except UpdateIntegrityError:
            destination.unlink(missing_ok=True)

    start = partial.stat().st_size if partial.exists() else 0
    if asset.size and start >= asset.size:
        partial.unlink(missing_ok=True)
        start = 0

    attempts = 2
    for attempt in range(attempts):
        try:
            response = _download_url(
                asset,
                timeout=timeout,
                allow_insecure=allow_insecure,
                range_start=start,
            )
            with response:
                status = getattr(response, 'status', 200)
                if start and status != 206:
                    # The server ignored Range; restart from zero.
                    start = 0
                    partial.unlink(missing_ok=True)
                mode = 'ab' if start else 'wb'
                total = asset.size or 0
                if not total:
                    content_length = response.headers.get('Content-Length')
                    if content_length and content_length.isdigit():
                        total = start + int(content_length)
                downloaded = start
                with partial.open(mode) as handle:
                    while True:
                        if cancel and cancel.is_set():
                            raise UpdateCancelled('download cancelled')
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > DOWNLOAD_MAX_BYTES:
                            raise UpdateError('download exceeds the safety limit')
                        if progress:
                            progress(downloaded, total)
            if asset.size and partial.stat().st_size != asset.size:
                raise UpdateIntegrityError(
                    f'incomplete download for {asset.name}: expected {asset.size}, got {partial.stat().st_size}'
                )
            verify_asset(partial, asset)
            os.replace(partial, destination)
            remove_mark_of_the_web(destination)
            append_update_log(f'downloaded {asset.name} ({destination.stat().st_size} bytes)')
            return destination
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and start:
                partial.unlink(missing_ok=True)
                start = 0
                continue
            if attempt + 1 < attempts and _retryable_http_error(exc):
                time.sleep(2)
                start = partial.stat().st_size if partial.exists() else 0
                continue
            raise UpdateError(f'HTTP {exc.code} while downloading {asset.name}') from exc
        except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
            if attempt + 1 < attempts:
                time.sleep(2)
                start = partial.stat().st_size if partial.exists() else 0
                continue
            raise UpdateError(f'network error while downloading {asset.name}: {exc}') from exc
        except (UpdateCancelled, UpdateIntegrityError):
            raise
        except Exception as exc:
            if attempt + 1 < attempts:
                time.sleep(1)
                start = partial.stat().st_size if partial.exists() else 0
                continue
            raise UpdateError(f'could not download {asset.name}: {exc}') from exc

    raise UpdateError(f'could not download {asset.name}')


def remove_mark_of_the_web(path: str | Path) -> None:
    """Removes the Windows Zone.Identifier stream when present."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes

        ctypes.windll.kernel32.DeleteFileW(f'{Path(path)}:Zone.Identifier')
    except Exception:
        pass


def _extract_portable_executable(zip_path: Path, target_dir: Path) -> Path:
    output = target_dir / 'Yt-RivoGUI.exe'
    with zipfile.ZipFile(zip_path) as archive:
        member = next(
            (
                name for name in archive.namelist()
                if Path(name).name.lower() == 'yt-rivogui.exe' and not name.endswith('/')
            ),
            None,
        )
        if not member:
            raise UpdateError('portable zip does not contain Yt-RivoGUI.exe')
        with archive.open(member) as source, output.open('wb') as destination:
            shutil.copyfileobj(source, destination)
    return output


def get_install_info() -> InstallInfo:
    """Reads the Inno Setup uninstall registry entry for this application."""
    if sys.platform != 'win32':
        return InstallInfo()
    try:
        import winreg
    except ImportError:
        return InstallInfo()

    location: Path | None = None
    version: str | None = None
    uninstall_string: str | None = None
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in views:
            try:
                with winreg.OpenKey(root, INSTALL_REGISTRY_KEY, 0, winreg.KEY_READ | view) as key:
                    try:
                        raw_location, _ = winreg.QueryValueEx(key, 'InstallLocation')
                        if raw_location:
                            location = Path(str(raw_location).strip().strip('"'))
                    except OSError:
                        pass
                    try:
                        raw_version, _ = winreg.QueryValueEx(key, 'DisplayVersion')
                        version = str(raw_version).strip() if raw_version else None
                    except OSError:
                        pass
                    try:
                        raw_uninstall, _ = winreg.QueryValueEx(key, 'UninstallString')
                        uninstall_string = str(raw_uninstall).strip() if raw_uninstall else None
                    except OSError:
                        pass
            except OSError:
                continue
            if location:
                break
        if location:
            break

    if location is None and uninstall_string:
        try:
            uninstall_path = Path(uninstall_string.strip('"').split('"')[0])
            location = uninstall_path.parent
        except Exception:
            location = None

    if location is None:
        return InstallInfo(version=version, uninstall_string=uninstall_string)

    try:
        location = location.resolve()
    except Exception:
        pass
    return InstallInfo(
        installed=True,
        location=location,
        version=version,
        uninstall_string=uninstall_string,
    )


def is_running_installed() -> bool:
    """Returns True when the current executable lives in the installer's folder."""
    if not is_frozen():
        return False
    info = get_install_info()
    if not info.installed or not info.location:
        return False
    try:
        return Path(sys.executable).resolve().parent.samefile(info.location)
    except Exception:
        return str(Path(sys.executable).resolve().parent).casefold() == str(info.location).casefold()


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _write_helper_script(
    *,
    target_exe: Path,
    new_exe: Path | None = None,
    installer: Path | None = None,
) -> Path:
    script_dir = Path(tempfile.mkdtemp(prefix='yt-rivogui-update-'))
    script_path = script_dir / 'apply-update.ps1'
    log_path = get_update_log_path()
    target = _ps_quote(target_exe)
    log = _ps_quote(log_path)
    pid = os.getpid()
    lines = [
        '$ErrorActionPreference = "Stop"',
        f'$log = {log}',
        'function Write-UpdateLog([string]$message) {',
        '  try { Add-Content -LiteralPath $log -Value ("[{0}] {1}" -f (Get-Date -Format o), $message) -Encoding UTF8 } catch {}',
        '}',
        f'Write-UpdateLog "helper started for pid {pid}"',
        f'$pidToWait = {pid}',
        f'$target = {target}',
        'try { Wait-Process -Id $pidToWait -Timeout 180 -ErrorAction SilentlyContinue } catch {}',
        'Start-Sleep -Milliseconds 800',
    ]
    if installer is not None:
        lines.extend([
            f'$installer = {_ps_quote(installer)}',
            'try {',
            '  Write-UpdateLog "running installer"',
            '  $arguments = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/NOCANCEL", (\'/LOG="{0}"\' -f $log))',
            '  $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru',
            '  Write-UpdateLog ("installer exit code: {0}" -f $process.ExitCode)',
            '} catch {',
            '  Write-UpdateLog ("installer failed: {0}" -f $_.Exception.Message)',
            '}',
        ])
    else:
        if new_exe is None:
            raise UpdateError('no update payload supplied')
        backup = target_exe.with_name(f'{target_exe.name}.old')
        lines.extend([
            f'$newExe = {_ps_quote(new_exe)}',
            f'$backup = {_ps_quote(backup)}',
            'try {',
            '  Write-UpdateLog "replacing portable executable"',
            '  if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }',
            '  Move-Item -LiteralPath $target -Destination $backup -Force',
            '  try {',
            '    Copy-Item -LiteralPath $newExe -Destination $target -Force',
            '  } catch {',
            '    Write-UpdateLog ("copy failed, restoring backup: {0}" -f $_.Exception.Message)',
            '    if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $target -Force }',
            '    throw',
            '  }',
            '  Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue',
            '  Remove-Item -LiteralPath $newExe -Force -ErrorAction SilentlyContinue',
            '  Write-UpdateLog "portable executable replaced"',
            '} catch {',
            '  Write-UpdateLog ("portable update failed: {0}" -f $_.Exception.Message)',
            '}',
        ])
    lines.extend([
        'try {',
        '  Write-UpdateLog "restarting application"',
        '  Start-Process -FilePath $target -WorkingDirectory (Split-Path -LiteralPath $target)',
        '} catch {',
        '  Write-UpdateLog ("restart failed: {0}" -f $_.Exception.Message)',
        '}',
        'Start-Sleep -Seconds 1',
        'try { Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue } catch {}',
        'try { Remove-Item -LiteralPath (Split-Path -LiteralPath $MyInvocation.MyCommand.Path) -Force -ErrorAction SilentlyContinue } catch {}',
    ])
    script_path.write_text('\r\n'.join(lines) + '\r\n', encoding='utf-8')
    append_update_log(f'helper script written: {script_path}')
    return script_path


def _launch_helper(script_path: Path) -> None:
    if sys.platform != 'win32':
        raise UpdateError('automatic updates are only supported on Windows')
    powershell = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
    if not powershell:
        raise UpdateError('PowerShell was not found')
    flags = 0
    flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    flags |= getattr(subprocess, 'DETACHED_PROCESS', 0)
    try:
        subprocess.Popen(
            [
                powershell,
                '-NoProfile',
                '-NonInteractive',
                '-ExecutionPolicy',
                'Bypass',
                '-WindowStyle',
                'Hidden',
                '-File',
                str(script_path),
            ],
            cwd=str(script_path.parent),
            creationflags=flags,
            close_fds=True,
        )
    except Exception as exc:
        raise UpdateError(f'could not start the update helper: {exc}') from exc
    append_update_log(f'helper launched: {script_path}')


def apply_update(
    info: UpdateInfo,
    asset_path: str | Path,
    *,
    installed: bool | None = None,
    relaunch: bool = True,
) -> Path:
    """Prepares and launches the update helper, returning the helper path.

    The caller is responsible for closing the application after this returns.
    """
    if not is_frozen():
        raise UpdateError('automatic updates are only available in packaged builds')
    if not relaunch:
        # The helper always relaunches; this parameter is kept for future use.
        pass
    payload = Path(asset_path)
    if not payload.is_file():
        raise UpdateError(f'update payload does not exist: {payload}')
    if payload.stat().st_size <= 0:
        raise UpdateError('update payload is empty')

    target_exe = Path(sys.executable).resolve()
    installed = is_running_installed() if installed is None else installed
    asset = info.asset_for(installed=installed)
    if asset is None:
        raise UpdateError('no compatible update asset is available')

    if not asset.has_checksum:
        raise UpdateIntegrityError(f'no valid checksum available for {asset.name}')
    verify_asset(payload, asset)

    if installed:
        if payload.suffix.lower() == '.zip':
            raise UpdateError('the installer asset must not be a zip archive')
        script = _write_helper_script(target_exe=target_exe, installer=payload)
    else:
        if not _is_writable_directory(target_exe.parent):
            raise UpdateError(f'the application folder is not writable: {target_exe.parent}')
        new_exe = payload
        if payload.suffix.lower() == '.zip':
            new_exe = _extract_portable_executable(payload, get_update_dir())
        script = _write_helper_script(target_exe=target_exe, new_exe=new_exe)

    _launch_helper(script)
    return script


def update_now(
    current_version: str,
    *,
    progress: _progress_callback | None = None,
    cancel: threading.Event | None = None,
    timeout: float = 30.0,
    allow_insecure: bool = False,
) -> CheckResult:
    """Checks, downloads and launches an update.  Used by ``--update-now``."""
    result = check_for_updates(current_version, timeout=min(timeout, 20.0), allow_insecure=allow_insecure)
    if not result.update_available or not result.info:
        return result
    installed = is_running_installed()
    asset = result.info.asset_for(installed=installed)
    if asset is None:
        raise UpdateError('no compatible update asset is available')
    path = download_asset(
        asset,
        progress=progress,
        cancel=cancel,
        timeout=timeout,
        allow_insecure=allow_insecure,
    )
    apply_update(result.info, path, installed=installed)
    return result


def cleanup_update_cache(*, max_age_days: int = 7) -> None:
    """Deletes old update files while preserving recent downloads and partials."""
    try:
        cutoff = time.time() - max(1, max_age_days) * 86400
        for path in get_update_dir().iterdir():
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass
