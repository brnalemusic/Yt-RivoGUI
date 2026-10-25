from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app import updater
from app.updater import (
    UpdateAsset,
    UpdateCancelled,
    UpdateError,
    UpdateInfo,
    UpdateIntegrityError,
    UpdateSettings,
    check_for_updates,
    cleanup_update_cache,
    download_asset,
    is_newer_version,
    load_manifest_from_file,
    normalize_version,
    parse_version,
    sha256_file,
    verify_asset,
)

GITHUB_RELEASE_BASE = 'https://github.com/brnalemusic/Yt-RivoGUI/releases/download'
RELEASE_PAGE = 'https://github.com/brnalemusic/Yt-RivoGUI/releases/tag'


class _Handler(BaseHTTPRequestHandler):
    routes: dict[str, bytes] = {}

    def do_GET(self):  # noqa: N802 - http.server API
        body = self.routes.get(self.path)
        if body is None:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D401 - silence test server
        pass


@pytest.fixture
def http_server():
    handler = type('TestHandler', (_Handler,), {'routes': {}})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', handler.routes
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('YTRIVO_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.delenv('YTRIVO_UPDATE_MANIFEST_URL', raising=False)
    monkeypatch.delenv('YTRIVO_UPDATE_API_URL', raising=False)
    yield tmp_path / 'data'


def _manifest(base: str = GITHUB_RELEASE_BASE, version: str = '0.0.4.0', **overrides) -> dict:
    data = {
        'schema': 1,
        'version': version,
        'tag': version,
        'channel': 'stable',
        'release_url': f'{RELEASE_PAGE}/{version}',
        'notes_url': f'{RELEASE_PAGE}/{version}',
        'published_at': '2026-01-01T00:00:00Z',
        'assets': {
            'installer': {
                'name': f'Yt-RivoGUI-Setup-v{version}.exe',
                'url': f'{base}/{version}/setup.exe',
                'size': 7,
                'sha256': 'a' * 64,
            },
            'portable': {
                'name': 'Yt-RivoGUI.exe',
                'url': f'{base}/{version}/portable.exe',
                'size': 4,
                'sha256': 'b' * 64,
            },
        },
    }
    data.update(overrides)
    return data


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / 'latest.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


# ---------------------------------------------------------------------------
# version handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('0.0.4.0', (0, 0, 4, 0)),
        ('v0.0.4.0', (0, 0, 4, 0)),
        ('V1.2', (1, 2)),
        (' 2.3.4 ', (2, 3, 4)),
    ],
)
def test_parse_version_accepts_numeric_versions(raw, expected):
    assert parse_version(raw) == expected


@pytest.mark.parametrize('raw', ['', 'v', 'abc', '1.2.3.4.5', '1..2', '1.2-beta'])
def test_parse_version_rejects_invalid_versions(raw):
    with pytest.raises(ValueError):
        parse_version(raw)


def test_normalize_version_strips_prefix_and_whitespace():
    assert normalize_version(' v0.0.4.0 ') == '0.0.4.0'


@pytest.mark.parametrize(
    ('candidate', 'current', 'expected'),
    [
        ('0.0.4.0', '0.0.3.0', True),
        ('0.0.3.0', '0.0.4.0', False),
        ('0.0.4.0', '0.0.4.0', False),
        ('0.0.4', '0.0.4.0', False),
        ('1.0', '0.9.9.9', True),
        ('invalid', '0.0.3.0', False),
    ],
)
def test_is_newer_version(candidate, current, expected):
    assert is_newer_version(candidate, current) is expected


# ---------------------------------------------------------------------------
# manifest parsing and asset selection
# ---------------------------------------------------------------------------

def test_manifest_loads_and_selects_assets(tmp_path):
    info = load_manifest_from_file(_write_manifest(tmp_path, _manifest()), allow_insecure=False)
    assert info.version == '0.0.4.0'
    assert info.tag == '0.0.4.0'
    assert info.channel == 'stable'
    assert info.asset_for(installed=True).name == 'Yt-RivoGUI-Setup-v0.0.4.0.exe'
    assert info.asset_for(installed=False).name == 'Yt-RivoGUI.exe'


def test_manifest_prefers_portable_exe_over_zip(tmp_path):
    data = _manifest()
    data['assets'].pop('portable')
    data['assets']['portable_zip'] = {
        'name': 'Yt-RivoGUI-v0.0.4.0-windows.zip',
        'url': f'{GITHUB_RELEASE_BASE}/0.0.4.0/x.zip',
        'size': 10,
        'sha256': 'c' * 64,
    }
    info = load_manifest_from_file(_write_manifest(tmp_path, data))
    assert info.asset_for(installed=False).name.endswith('.zip')
    assert info.asset_for(installed=True).name.startswith('Yt-RivoGUI-Setup-')


@pytest.mark.parametrize(
    'mutation',
    [
        {'schema': 2},
        {'version': '0.0.4.0', 'tag': '0.0.3.0'},
        {'channel': 'beta'},
        {'assets': {}},
        {'assets': {'installer': {'name': '../evil.exe', 'url': 'https://github.com/x', 'size': 1}}},
        {'assets': {'installer': {'name': 'ok.exe', 'url': 'https://evil.example/ok.exe', 'size': 1}}},
        {
            'assets': {
                'installer': {
                    'name': 'ok.exe',
                    'url': 'https://github.com/brnalemusic/Yt-RivoGUI/releases/download/x/ok.exe',
                    'size': 1,
                    'sha256': 'not-a-checksum',
                }
            }
        },
    ],
)
def test_manifest_rejects_invalid_data(tmp_path, mutation):
    data = _manifest()
    data.update(mutation)
    with pytest.raises(UpdateError):
        load_manifest_from_file(_write_manifest(tmp_path, data))


# ---------------------------------------------------------------------------
# checksums and downloads
# ---------------------------------------------------------------------------

def test_sha256_and_verify_asset(tmp_path):
    payload = b'verified payload'
    path = tmp_path / 'asset.bin'
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    assert sha256_file(path) == digest

    verify_asset(path, UpdateAsset('asset.bin', 'https://github.com/x', size=len(payload), sha256=digest))
    with pytest.raises(UpdateIntegrityError):
        verify_asset(path, UpdateAsset('asset.bin', 'https://github.com/x', size=999, sha256=digest))
    with pytest.raises(UpdateIntegrityError):
        verify_asset(path, UpdateAsset('asset.bin', 'https://github.com/x', sha256='0' * 64))
    with pytest.raises(UpdateIntegrityError):
        verify_asset(path, UpdateAsset('asset.bin', 'https://github.com/x', size=len(payload)))
    with pytest.raises(UpdateIntegrityError):
        verify_asset(tmp_path / 'missing.bin', UpdateAsset('missing.bin', 'https://github.com/x', sha256='0' * 64))


def test_download_asset_verifies_and_reuses_file(http_server, tmp_path):
    base, routes = http_server
    payload = b'hello update payload'
    routes['/update.bin'] = payload
    asset = UpdateAsset(
        'update.bin',
        f'{base}/update.bin',
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )

    progress: list[tuple[int, int]] = []
    path = download_asset(asset, dest_dir=tmp_path, allow_insecure=True, progress=lambda done, total: progress.append((done, total)))
    assert path.read_bytes() == payload
    assert progress[-1] == (len(payload), len(payload))

    # A second call must reuse the verified file without hitting the server.
    routes.clear()
    again = download_asset(asset, dest_dir=tmp_path, allow_insecure=True)
    assert again == path
    assert again.read_bytes() == payload


def test_download_asset_rejects_bad_checksum(http_server, tmp_path):
    base, routes = http_server
    payload = b'corrupted update'
    routes['/bad.bin'] = payload
    asset = UpdateAsset(
        'bad.bin',
        f'{base}/bad.bin',
        size=len(payload),
        sha256='0' * 64,
    )
    with pytest.raises(UpdateIntegrityError):
        download_asset(asset, dest_dir=tmp_path, allow_insecure=True)


def test_download_asset_requires_checksum(http_server, tmp_path):
    base, routes = http_server
    routes['/x.bin'] = b'x'
    asset = UpdateAsset('x.bin', f'{base}/x.bin')
    with pytest.raises(UpdateIntegrityError):
        download_asset(asset, dest_dir=tmp_path, allow_insecure=True)


def test_download_asset_honours_cancellation(http_server, tmp_path):
    base, routes = http_server
    payload = b'cancel me'
    routes['/cancel.bin'] = payload
    asset = UpdateAsset(
        'cancel.bin',
        f'{base}/cancel.bin',
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    event = threading.Event()
    event.set()
    with pytest.raises(UpdateCancelled):
        download_asset(asset, dest_dir=tmp_path, allow_insecure=True, cancel=event)


# ---------------------------------------------------------------------------
# update checks
# ---------------------------------------------------------------------------

def test_check_for_updates_reads_primary_manifest(http_server, monkeypatch):
    base, routes = http_server
    routes['/latest.json'] = json.dumps(_manifest(base)).encode()
    monkeypatch.setenv('YTRIVO_UPDATE_MANIFEST_URL', f'{base}/latest.json')
    monkeypatch.setenv('YTRIVO_UPDATE_API_URL', f'{base}/api')

    result = check_for_updates('0.0.3.0', allow_insecure=True)
    assert result.status == 'update_available'
    assert result.latest_version == '0.0.4.0'
    assert result.info is not None
    assert result.info.asset_for(installed=True).name == 'Yt-RivoGUI-Setup-v0.0.4.0.exe'


def test_check_for_updates_reports_up_to_date(http_server, monkeypatch):
    base, routes = http_server
    routes['/latest.json'] = json.dumps(_manifest(base)).encode()
    monkeypatch.setenv('YTRIVO_UPDATE_MANIFEST_URL', f'{base}/latest.json')
    monkeypatch.setenv('YTRIVO_UPDATE_API_URL', f'{base}/api')

    result = check_for_updates('0.0.4.0', allow_insecure=True)
    assert result.status == 'up_to_date'
    assert result.latest_version == '0.0.4.0'


def test_check_for_updates_rejects_invalid_current_version():
    result = check_for_updates('not-a-version')
    assert result.is_error
    assert result.error_code == 'invalid_current_version'


def test_check_for_updates_rejects_invalid_manifest(http_server, monkeypatch):
    base, routes = http_server
    routes['/latest.json'] = b'{"schema": 99}'
    monkeypatch.setenv('YTRIVO_UPDATE_MANIFEST_URL', f'{base}/latest.json')
    monkeypatch.setenv('YTRIVO_UPDATE_API_URL', f'{base}/api')

    result = check_for_updates('0.0.3.0', allow_insecure=True)
    assert result.is_error
    assert result.error_code == 'invalid_manifest'


def test_check_for_updates_falls_back_to_github_api(http_server, monkeypatch):
    base, routes = http_server
    tag = '0.0.4.0'
    installer_name = f'Yt-RivoGUI-Setup-v{tag}.exe'
    installer_digest = 'd' * 64
    release = {
        'tag_name': tag,
        'draft': False,
        'prerelease': False,
        'html_url': f'{base}/releases/tag/{tag}',
        'assets': [
            {
                'name': installer_name,
                'browser_download_url': f'{base}/assets/{installer_name}',
                'size': 1234,
            },
            {
                'name': 'Yt-RivoGUI.exe',
                'browser_download_url': f'{base}/assets/Yt-RivoGUI.exe',
                'size': 4321,
            },
            {
                'name': 'SHA256SUMS.txt',
                'browser_download_url': f'{base}/assets/SHA256SUMS.txt',
                'size': 200,
            },
        ],
    }
    routes['/latest.json'] = b''  # not used: force a 404 below
    routes.pop('/latest.json', None)
    routes['/api'] = json.dumps(release).encode()
    routes['/assets/SHA256SUMS.txt'] = f'{installer_digest}  {installer_name}\n'.encode()
    monkeypatch.setenv('YTRIVO_UPDATE_MANIFEST_URL', f'{base}/latest.json')
    monkeypatch.setenv('YTRIVO_UPDATE_API_URL', f'{base}/api')

    result = check_for_updates('0.0.3.0', allow_insecure=True)
    assert result.status == 'update_available'
    assert result.info is not None
    installer = result.info.asset_for(installed=True)
    assert installer is not None
    assert installer.name == installer_name
    assert installer.sha256 == installer_digest


def test_check_for_updates_maps_rate_limit(http_server, monkeypatch):
    base, routes = http_server
    monkeypatch.setenv('YTRIVO_UPDATE_MANIFEST_URL', f'{base}/latest.json')
    monkeypatch.setenv('YTRIVO_UPDATE_API_URL', f'{base}/api')

    def handler_status(self):
        self.send_response(403)
        self.send_header('Content-Length', '0')
        self.end_headers()

    # Patch the shared handler for this request only.
    original = _Handler.do_GET
    _Handler.do_GET = handler_status
    try:
        result = check_for_updates('0.0.3.0', allow_insecure=True)
    finally:
        _Handler.do_GET = original
    assert result.is_error
    assert result.error_code == 'rate_limit'


# ---------------------------------------------------------------------------
# settings, cache and helper script
# ---------------------------------------------------------------------------

def test_update_settings_roundtrip_and_schedule(tmp_path):
    settings = UpdateSettings(auto_check_updates=True)
    settings.save()
    loaded = UpdateSettings.load()
    assert loaded.auto_check_updates is True
    assert loaded.channel == 'stable'

    loaded.mark_checked(when=datetime.now(timezone.utc) - timedelta(hours=13))
    loaded.save()
    assert UpdateSettings.load().should_check() is True

    loaded.mark_checked()
    loaded.save()
    assert UpdateSettings.load().should_check() is False

    loaded.auto_check_updates = False
    assert loaded.should_check(interval_hours=0) is False


def test_update_settings_skip_and_invalid_file(tmp_path):
    settings = UpdateSettings(skipped_version='0.0.5.0')
    assert settings.should_show_version('0.0.5.0') is False
    assert settings.should_show_version('0.0.6.0') is True
    assert UpdateSettings(skipped_version='garbage').should_show_version('0.0.6.0') is True

    (tmp_path / 'data').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'data' / 'settings.json').write_text('not-json', encoding='utf-8')
    assert UpdateSettings.load().auto_check_updates is True


def test_cleanup_update_cache_removes_old_files(tmp_path):
    update_dir = updater.get_update_dir()
    old = update_dir / 'old.bin'
    recent = update_dir / 'recent.bin'
    old.write_bytes(b'old')
    recent.write_bytes(b'new')
    old_time = time.time() - 10 * 86400
    os.utime(old, (old_time, old_time))

    cleanup_update_cache(max_age_days=7)
    assert not old.exists()
    assert recent.exists()


def test_helper_script_escapes_paths(isolated_data_dir):
    target = Path(r"C:\Program Files\Yt-RivoGUI\Yt-RivoGUI.exe")
    installer = Path(r"C:\Users\Breno\Downloads\Setup's file.exe")
    script = updater._write_helper_script(target_exe=target, installer=installer)
    try:
        text = script.read_text(encoding='utf-8')
        assert 'Start-Process -FilePath $installer' in text
        assert '/VERYSILENT' in text
        assert "Setup''s file.exe" in text
        assert '/LOG=' in text
    finally:
        shutil.rmtree(script.parent, ignore_errors=True)


def test_helper_script_portable_branch(isolated_data_dir):
    target = Path(r"C:\Apps\Yt-RivoGUI\Yt-RivoGUI.exe")
    new_exe = Path(r"C:\Apps\Yt-RivoGUI\Yt-RivoGUI.exe.new")
    script = updater._write_helper_script(target_exe=target, new_exe=new_exe)
    try:
        text = script.read_text(encoding='utf-8')
        assert 'Move-Item -LiteralPath $target' in text
        assert 'Copy-Item -LiteralPath $newExe' in text
        assert 'Yt-RivoGUI.exe.old' in text
        assert 'Start-Process -FilePath $target' in text
    finally:
        shutil.rmtree(script.parent, ignore_errors=True)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows named mutex')
def test_single_instance_guard():
    name = f'Yt-RivoGUI.Test.{os.getpid()}.{time.time_ns()}'
    first = updater.SingleInstanceGuard(name)
    second = updater.SingleInstanceGuard(name)
    try:
        assert first.acquired is True
        assert second.acquired is False
    finally:
        second.release()
        first.release()


# ---------------------------------------------------------------------------
# apply_update safety
# ---------------------------------------------------------------------------

def test_apply_update_requires_a_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    payload = tmp_path / 'Yt-RivoGUI-Setup-v0.0.5.0.exe'
    payload.write_bytes(b'installer bytes')
    info = UpdateInfo(
        version='0.0.5.0',
        tag='0.0.5.0',
        assets={
            'installer': UpdateAsset(
                name=payload.name,
                url=f'{GITHUB_RELEASE_BASE}/0.0.5.0/{payload.name}',
                size=payload.stat().st_size,
                sha256=None,
            )
        },
    )
    with pytest.raises(UpdateIntegrityError):
        updater.apply_update(info, payload, installed=True)


def test_apply_update_rejects_a_tampered_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    payload = tmp_path / 'Yt-RivoGUI.exe'
    payload.write_bytes(b'tampered')
    info = UpdateInfo(
        version='0.0.5.0',
        tag='0.0.5.0',
        assets={
            'portable': UpdateAsset(
                name=payload.name,
                url=f'{GITHUB_RELEASE_BASE}/0.0.5.0/{payload.name}',
                size=payload.stat().st_size,
                sha256='0' * 64,
            )
        },
    )
    with pytest.raises(UpdateIntegrityError):
        updater.apply_update(info, payload, installed=False)
