#!/usr/bin/env python3
"""Verifies the packaged app, Inno Setup installer and update manifest."""

from __future__ import annotations

import argparse
import ctypes
import functools
import hashlib
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

EXE_NAME = 'Yt-RivoGUI.exe' if sys.platform == 'win32' else 'Yt-RivoGUI'
UNINSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Yt-RivoGUI_is1'
SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _file_version(path: Path) -> str:
    """Reads the numeric file version from a Windows PE resource."""
    if sys.platform != 'win32':
        return ''
    from ctypes import wintypes

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [
            ('dwSignature', wintypes.DWORD),
            ('dwStrucVersion', wintypes.DWORD),
            ('dwFileVersionMS', wintypes.DWORD),
            ('dwFileVersionLS', wintypes.DWORD),
            ('dwProductVersionMS', wintypes.DWORD),
            ('dwProductVersionLS', wintypes.DWORD),
            ('dwFileFlagsMask', wintypes.DWORD),
            ('dwFileFlags', wintypes.DWORD),
            ('dwFileOS', wintypes.DWORD),
            ('dwFileType', wintypes.DWORD),
            ('dwFileSubtype', wintypes.DWORD),
            ('dwFileDateMS', wintypes.DWORD),
            ('dwFileDateLS', wintypes.DWORD),
        ]

    version = ctypes.WinDLL('version', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [
        wintypes.LPVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.UINT),
    ]
    version.VerQueryValueW.restype = wintypes.BOOL

    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return ''
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        return ''
    pointer = wintypes.LPVOID()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buffer, '\\', ctypes.byref(pointer), ctypes.byref(length)):
        return ''
    info = ctypes.cast(pointer, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    return '{}.{}.{}.{}'.format(
        info.dwFileVersionMS >> 16,
        info.dwFileVersionMS & 0xFFFF,
        info.dwFileVersionLS >> 16,
        info.dwFileVersionLS & 0xFFFF,
    )


def _parse_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not SHA256_RE.fullmatch(parts[0]):
            continue
        name = Path(parts[1].strip().lstrip('*').strip()).name
        if name:
            result[name] = parts[0].lower()
    return result


def _verify_checksums(dist_path: Path) -> bool:
    checksum_path = dist_path / 'SHA256SUMS.txt'
    if not checksum_path.exists():
        print('[test_build] Notice: SHA256SUMS.txt not found')
        return True
    entries = _parse_checksums(checksum_path)
    if not entries:
        print('[test_build] ERROR: SHA256SUMS.txt contains no valid entries', file=sys.stderr)
        return False
    if 'SHA256SUMS.txt' in entries or 'latest.json' in entries:
        print('[test_build] ERROR: SHA256SUMS.txt must not hash itself or latest.json', file=sys.stderr)
        return False
    for name, expected in entries.items():
        path = dist_path / name
        if not path.is_file():
            print(f'[test_build] ERROR: checksum lists missing file {name}', file=sys.stderr)
            return False
        actual = compute_sha256(path)
        if actual != expected:
            print(f'[test_build] ERROR: checksum mismatch for {name}', file=sys.stderr)
            return False
    print(f'[test_build] Checksums verified: {len(entries)} file(s)')
    return True


def _verify_zip(dist_path: Path, version: str) -> bool:
    zip_path = dist_path / f'Yt-RivoGUI-v{version}-windows.zip'
    if not zip_path.exists():
        print(f'[test_build] ERROR: release archive not found: {zip_path.name}', file=sys.stderr)
        return False
    with zipfile.ZipFile(zip_path, 'r') as archive:
        names = set(archive.namelist())
        for required in (EXE_NAME, 'README.md', 'LICENSE'):
            if required not in names:
                print(f'[test_build] ERROR: {zip_path.name} does not contain {required}', file=sys.stderr)
                return False
        lowered = {name.lower() for name in names}
        for media_tool in ('ffmpeg.exe', 'ffprobe.exe'):
            if media_tool in lowered:
                print(
                    f'[test_build] ERROR: {zip_path.name} must not bundle {media_tool}',
                    file=sys.stderr,
                )
                return False
        bad = archive.testzip()
        if bad:
            print(f'[test_build] ERROR: corrupt member in {zip_path.name}: {bad}', file=sys.stderr)
            return False
    print(f'[test_build] Archive verified: {zip_path.name}')
    return True


def _verify_manifest(dist_path: Path, version: str) -> bool:
    manifest_path = dist_path / 'latest.json'
    if not manifest_path.exists():
        print('[test_build] ERROR: latest.json not found', file=sys.stderr)
        return False
    try:
        from app.updater import load_manifest_from_file, sha256_file

        info = load_manifest_from_file(manifest_path, allow_insecure=False)
    except Exception as exc:
        print(f'[test_build] ERROR: invalid latest.json: {exc}', file=sys.stderr)
        return False
    if info.version != version:
        print(f'[test_build] ERROR: manifest version {info.version} != {version}', file=sys.stderr)
        return False
    if info.channel != 'stable':
        print(f'[test_build] ERROR: manifest channel is {info.channel}', file=sys.stderr)
        return False
    if 'installer' not in info.assets:
        print('[test_build] ERROR: manifest has no installer asset', file=sys.stderr)
        return False
    if 'portable' not in info.assets and 'portable_zip' not in info.assets:
        print('[test_build] ERROR: manifest has no portable asset', file=sys.stderr)
        return False
    for key, asset in info.assets.items():
        path = dist_path / asset.name
        if not path.is_file():
            print(f'[test_build] ERROR: manifest asset {key} is missing locally: {asset.name}', file=sys.stderr)
            return False
        if asset.size and asset.size != path.stat().st_size:
            print(f'[test_build] ERROR: manifest size mismatch for {asset.name}', file=sys.stderr)
            return False
        if not asset.sha256 or sha256_file(path) != asset.sha256:
            print(f'[test_build] ERROR: manifest hash mismatch for {asset.name}', file=sys.stderr)
            return False
        if not asset.url.startswith('https://github.com/brnalemusic/Yt-RivoGUI/releases/download/'):
            print(f'[test_build] ERROR: unexpected asset URL: {asset.url}', file=sys.stderr)
            return False
    installed_asset = info.asset_for(installed=True)
    portable_asset = info.asset_for(installed=False)
    if not installed_asset or installed_asset.name != f'Yt-RivoGUI-Setup-v{version}.exe':
        print('[test_build] ERROR: manifest does not select the installer for installed mode', file=sys.stderr)
        return False
    if not portable_asset:
        print('[test_build] ERROR: manifest does not select a portable asset', file=sys.stderr)
        return False
    print(f'[test_build] Manifest verified: v{info.version} '
          f'({", ".join(sorted(info.assets))})')
    return True


def _installed_version() -> str | None:
    if sys.platform != 'win32':
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            value, _ = winreg.QueryValueEx(key, 'DisplayVersion')
            return str(value)
    except OSError:
        return None


def _create_synthetic_ffmpeg_archive(workspace: Path) -> Path | None:
    """Builds a tiny 7z with fake media tools for an offline installer smoke test.

    Windows ships bsdtar, which can write 7zip archives.  Using it keeps the
    smoke test independent from gyan.dev while still exercising the installer's
    download, SHA-256 verification, extraction and copy pipeline.
    """
    tar = shutil.which('tar')
    if sys.platform != 'win32' or not tar:
        return None

    source = workspace / 'ffmpeg-archive' / 'ffmpeg-test-essentials_build' / 'bin'
    source.mkdir(parents=True)
    (source / 'ffmpeg.exe').write_bytes(b'fake-ffmpeg')
    (source / 'ffprobe.exe').write_bytes(b'fake-ffprobe')

    archive = workspace / 'ffmpeg-test-essentials.7z'
    proc = subprocess.run(
        [tar, '-cf', str(archive), '--format', '7zip', 'ffmpeg-test-essentials_build'],
        cwd=source.parent.parent,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not archive.is_file():
        print(f'[test_build] Notice: could not create synthetic ffmpeg archive: {proc.stderr.strip()}')
        return None
    return archive


def _serve_ffmpeg_archive(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    """Serves the synthetic archive and its checksum over loopback HTTP."""
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_address[1]}'


def _smoke_install(installer: Path, version: str, expected_exe: Path) -> bool:
    if sys.platform != 'win32':
        print('[test_build] Notice: install smoke test is Windows-only')
        return True

    existing = _installed_version()
    if existing is not None:
        print(f'[test_build] Notice: skipping install smoke test; Yt-RivoGUI {existing} is already installed')
        return True

    workspace = Path(tempfile.mkdtemp(prefix='yt-rivo-install-smoke-'))
    install_dir = workspace / 'app'
    install_log = workspace / 'install.log'
    uninstall_log = workspace / 'uninstall.log'
    app_path = install_dir / EXE_NAME
    uninstaller = install_dir / 'unins000.exe'
    server = None
    try:
        installer_env = os.environ.copy()
        for key in ('YTRIVO_FFMPEG_URL', 'YTRIVO_FFMPEG_CHECKSUM_URL',
                    'YTRIVO_FFMPEG_SHA256', 'YTRIVO_FFMPEG_FORCE', 'YTRIVO_SKIP_FFMPEG'):
            installer_env.pop(key, None)

        archive = _create_synthetic_ffmpeg_archive(workspace)
        verify_media_tools = archive is not None
        if archive is not None:
            checksum = compute_sha256(archive)
            sidecar = archive.with_name(f'{archive.name}.sha256')
            sidecar.write_text(checksum + '\n', encoding='ascii')
            server, base_url = _serve_ffmpeg_archive(archive.parent)
            installer_env['YTRIVO_FFMPEG_URL'] = f'{base_url}/{archive.name}'
            installer_env['YTRIVO_FFMPEG_CHECKSUM_URL'] = f'{base_url}/{sidecar.name}'
            installer_env['YTRIVO_FFMPEG_FORCE'] = '1'
            print('[test_build] Installer media tools will be verified with a local test archive')
        else:
            installer_env['YTRIVO_SKIP_FFMPEG'] = '1'
            print('[test_build] Notice: ffmpeg installer smoke test skipped (no 7z archive support)')

        print(f'[test_build] Silent install smoke test -> {install_dir}')
        proc = subprocess.run(
            [
                str(installer),
                '/VERYSILENT',
                '/SUPPRESSMSGBOXES',
                '/NORESTART',
                '/NOCANCEL',
                '/CLOSEAPPLICATIONS',
                '/NOICONS',
                f'/DIR={install_dir}',
                f'/LOG={install_log}',
            ],
            env=installer_env,
            timeout=240,
        )
        if proc.returncode != 0:
            print(f'[test_build] ERROR: installer exited with {proc.returncode}', file=sys.stderr)
            return False
        if not app_path.is_file():
            print(f'[test_build] ERROR: installed executable missing: {app_path}', file=sys.stderr)
            return False

        if verify_media_tools:
            for name, expected_bytes in (('ffmpeg.exe', b'fake-ffmpeg'), ('ffprobe.exe', b'fake-ffprobe')):
                media_path = install_dir / 'bin' / name
                if not media_path.is_file():
                    print(f'[test_build] ERROR: installed media tool missing: {media_path}', file=sys.stderr)
                    return False
                if media_path.read_bytes() != expected_bytes:
                    print(f'[test_build] ERROR: unexpected contents for {name}', file=sys.stderr)
                    return False
            print('[test_build] Installer media tools verified: ffmpeg.exe, ffprobe.exe')

        # The installer must deploy the exact executable that was verified above.
        # Running the installed copy here would make the test depend on antivirus
        # scan timing, so compare bytes and the PE version instead.
        if compute_sha256(app_path) != compute_sha256(expected_exe):
            print('[test_build] ERROR: installed executable differs from the built executable', file=sys.stderr)
            return False
        installed_version = _file_version(app_path)
        if installed_version and installed_version != version:
            print(
                f'[test_build] ERROR: installed file version {installed_version} != {version}',
                file=sys.stderr,
            )
            return False
        if _installed_version() != version:
            print('[test_build] ERROR: uninstall registry entry was not created correctly', file=sys.stderr)
            return False
        if not uninstaller.is_file():
            print('[test_build] ERROR: uninstaller missing', file=sys.stderr)
            return False

        if verify_media_tools:
            skip_log = workspace / 'install-skip.log'
            skip_env = installer_env.copy()
            skip_env.pop('YTRIVO_FFMPEG_FORCE', None)
            skip_env.pop('YTRIVO_SKIP_FFMPEG', None)
            skip_env['YTRIVO_FFMPEG_URL'] = 'http://127.0.0.1:1/ffmpeg-must-not-be-downloaded.7z'
            skip_env['YTRIVO_FFMPEG_CHECKSUM_URL'] = 'http://127.0.0.1:1/ffmpeg-must-not-be-downloaded.7z.sha256'
            print('[test_build] Re-running the installer to verify existing media tools are reused')
            proc = subprocess.run(
                [
                    str(installer),
                    '/VERYSILENT',
                    '/SUPPRESSMSGBOXES',
                    '/NORESTART',
                    '/NOCANCEL',
                    '/CLOSEAPPLICATIONS',
                    '/NOICONS',
                    f'/DIR={install_dir}',
                    f'/LOG={skip_log}',
                ],
                env=skip_env,
                timeout=240,
            )
            if proc.returncode != 0:
                print(f'[test_build] ERROR: skip-path installer exited with {proc.returncode}', file=sys.stderr)
                return False
            log_text = skip_log.read_text(encoding='utf-8-sig', errors='replace') if skip_log.is_file() else ''
            if 'ffmpeg: found in' not in log_text:
                print('[test_build] ERROR: installer did not reuse the existing media tools', file=sys.stderr)
                return False
            for name, expected_bytes in (('ffmpeg.exe', b'fake-ffmpeg'), ('ffprobe.exe', b'fake-ffprobe')):
                if (install_dir / 'bin' / name).read_bytes() != expected_bytes:
                    print(f'[test_build] ERROR: media tool changed during the skip install: {name}', file=sys.stderr)
                    return False
            print('[test_build] Installer reused the existing media tools without downloading')

        print('[test_build] Silent uninstall smoke test')
        proc = subprocess.run(
            [
                str(uninstaller),
                '/VERYSILENT',
                '/SUPPRESSMSGBOXES',
                '/NORESTART',
                f'/LOG={uninstall_log}',
            ],
            env=installer_env,
            timeout=240,
        )
        if proc.returncode != 0:
            print(f'[test_build] ERROR: uninstaller exited with {proc.returncode}', file=sys.stderr)
            return False
        # Inno may finish directory cleanup a moment after the uninstaller exits.
        for _ in range(20):
            if not app_path.exists() and not install_dir.exists():
                break
            time.sleep(0.5)
        if app_path.exists() or install_dir.exists():
            print('[test_build] ERROR: install directory still exists after uninstall', file=sys.stderr)
            return False
        if _installed_version() is not None:
            print('[test_build] ERROR: uninstall registry entry still exists', file=sys.stderr)
            return False
        print('[test_build] Install/uninstall smoke test passed')
        return True
    except Exception as exc:
        print(f'[test_build] ERROR during install smoke test: {exc}', file=sys.stderr)
        return False
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        shutil.rmtree(workspace, ignore_errors=True)


def _verify_installer(dist_path: Path, version: str, *, install_smoke: bool) -> bool:
    installer = dist_path / f'Yt-RivoGUI-Setup-v{version}.exe'
    if not installer.exists():
        print(f'[test_build] ERROR: installer not found: {installer.name}', file=sys.stderr)
        return False
    size_mb = installer.stat().st_size / (1024 * 1024)
    if size_mb < 20:
        print(f'[test_build] ERROR: installer is suspiciously small ({size_mb:.2f} MB)', file=sys.stderr)
        return False
    file_version = _file_version(installer)
    if file_version and file_version != version:
        print(f'[test_build] ERROR: installer file version {file_version} != {version}', file=sys.stderr)
        return False
    print(f'[test_build] Installer verified: {installer.name} ({size_mb:.2f} MB, version {file_version or "unknown"})')
    if install_smoke:
        return _smoke_install(installer, version, dist_path / EXE_NAME)
    return True


def test_build(
    dist_dir: Path | None = None,
    auto_build: bool = False,
    *,
    install_smoke: bool = False,
    require_installer: bool = True,
) -> int:
    os.chdir(ROOT_DIR)
    dist_path = (dist_dir or (ROOT_DIR / 'dist' / 'gui')).resolve()
    exe_path = dist_path / EXE_NAME

    print(f'[test_build] Verifying Yt-RivoGUI build in: {dist_path}')

    if not exe_path.exists():
        if auto_build:
            print('[test_build] Executable not found. Running build_gui.py first...')
            from devscripts.build_gui import build

            build_code = build(dist_dir=dist_path)
            if build_code != 0:
                print(f'[test_build] Build failed with code {build_code}', file=sys.stderr)
                return build_code
        else:
            print(
                f'[test_build] ERROR: Executable not found at {exe_path}. '
                'Run devscripts/build_gui.py first or pass --build.',
                file=sys.stderr,
            )
            return 1

    # 1. Executable sanity
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f'[test_build] Executable found: {exe_path.name} ({size_mb:.2f} MB)')
    if size_mb < 20:
        print(f'[test_build] WARNING: Executable is suspiciously small ({size_mb:.2f} MB)', file=sys.stderr)
    exe_file_version = _file_version(exe_path)

    # 2. Run --version and capture the real version
    print('[test_build] Testing executable with --version...')
    try:
        proc = subprocess.run([str(exe_path), '--version'], capture_output=True, text=True, timeout=30)
    except Exception as exc:
        print(f'[test_build] ERROR running --version: {exc}', file=sys.stderr)
        return 1
    output = (proc.stdout + proc.stderr).strip()
    print(f'[test_build] --version output: {output} (exit code: {proc.returncode})')
    if proc.returncode != 0:
        return proc.returncode
    version = output.split()[-1].lstrip('vV') if output else ''
    if not re.fullmatch(r'\d+(?:\.\d+){0,3}', version):
        print(f'[test_build] ERROR: could not parse version from {output!r}', file=sys.stderr)
        return 1
    if exe_file_version and exe_file_version != version:
        print(
            f'[test_build] ERROR: exe file version {exe_file_version} != reported {version}',
            file=sys.stderr,
        )
        return 1

    # 3. Startup check
    print('[test_build] Testing executable with --test-startup...')
    try:
        proc = subprocess.run([str(exe_path), '--test-startup'], capture_output=True, text=True, timeout=30)
    except Exception as exc:
        print(f'[test_build] ERROR running --test-startup: {exc}', file=sys.stderr)
        return 1
    output = (proc.stdout + proc.stderr).strip()
    print(f'[test_build] --test-startup output: {output} (exit code: {proc.returncode})')
    if proc.returncode != 0:
        return proc.returncode

    # 4. Checksums, archive, installer and manifest
    if not _verify_checksums(dist_path):
        return 1
    if not _verify_zip(dist_path, version):
        return 1

    installer = dist_path / f'Yt-RivoGUI-Setup-v{version}.exe'
    if installer.exists():
        if not _verify_installer(dist_path, version, install_smoke=install_smoke):
            return 1
    elif require_installer:
        print(f'[test_build] ERROR: installer not found: {installer.name}', file=sys.stderr)
        return 1
    else:
        print('[test_build] Notice: installer not found (skipped)')

    if not _verify_manifest(dist_path, version):
        return 1

    print('\n[test_build] ALL BUILD TESTS PASSED! Executable is verified and production-ready.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Test and verify the Yt-RivoGUI release artifacts')
    parser.add_argument('--distpath', type=Path, default=None, help='Directory containing the built artifacts')
    parser.add_argument('--build', action='store_true', help='Build automatically when artifacts are missing')
    parser.add_argument('--install-smoke', action='store_true', help='Run a silent install/uninstall smoke test')
    parser.add_argument(
        '--no-installer',
        action='store_true',
        help='Do not fail when the installer is missing',
    )
    args = parser.parse_args()

    return test_build(
        dist_dir=args.distpath,
        auto_build=args.build,
        install_smoke=args.install_smoke,
        require_installer=not args.no_installer,
    )


if __name__ == '__main__':
    raise SystemExit(main())
