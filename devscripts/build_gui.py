#!/usr/bin/env python3
"""Builds the Yt-RivoGUI Windows executable, installer and update manifest."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

EXE_NAME = 'Yt-RivoGUI.exe' if sys.platform == 'win32' else 'Yt-RivoGUI'
COMPANY = 'brnalemusic'
PRODUCT = 'yt-rivogui'
COPYRIGHT = 'unlicense'


def _read_version() -> str:
    version = os.getenv('VERSION') or os.getenv('TARGET_TAG')
    if not version:
        try:
            from app import __version__

            version = __version__
        except Exception:
            version = '0.0.0.0'
    return str(version).strip().lstrip('vV')


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for chunk in version.split('.')[:4]:
        try:
            parts.append(max(0, int(chunk)))
        except ValueError:
            parts.append(0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)  # type: ignore[return-value]


def _write_version_file(path: Path, version: str) -> Path:
    """Writes a PyInstaller VSVersionInfo literal for the executable resources."""
    file_version = _version_tuple(version)
    path.write_text(
        'VSVersionInfo(\n'
        '  ffi=FixedFileInfo(\n'
        f'    filevers={file_version!r},\n'
        f'    prodvers={file_version!r},\n'
        '    mask=0x3f,\n'
        '    flags=0x0,\n'
        '    OS=0x40004,\n'
        '    fileType=0x1,\n'
        '    subtype=0x0,\n'
        '    date=(0, 0)\n'
        '  ),\n'
        '  kids=[\n'
        '    StringFileInfo([\n'
        "      StringTable('040904B0', [\n"
        f"        StringStruct('CompanyName', {COMPANY!r}),\n"
        f"        StringStruct('FileDescription', {PRODUCT!r}),\n"
        f"        StringStruct('FileVersion', {version!r}),\n"
        f"        StringStruct('InternalName', {EXE_NAME!r}),\n"
        f"        StringStruct('LegalCopyright', {COPYRIGHT!r}),\n"
        f"        StringStruct('OriginalFilename', {EXE_NAME!r}),\n"
        f"        StringStruct('ProductName', {PRODUCT!r}),\n"
        f"        StringStruct('ProductVersion', {version!r})\n"
        '      ])\n'
        '    ]),\n'
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        '  ]\n'
        ')\n',
        encoding='utf-8',
    )
    return path


def find_iscc() -> Path | None:
    """Locates the Inno Setup 6.7+ compiler (6.x is preferred over newer majors)."""
    override = os.environ.get('INNO_SETUP_COMPILER') or os.environ.get('ISCC')
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    found = shutil.which('ISCC.exe') or shutil.which('ISCC')
    if found:
        return Path(found)
    bases = [
        os.environ.get('ProgramFiles'),
        os.environ.get('ProgramFiles(x86)'),
        os.environ.get('LOCALAPPDATA'),
    ]
    for base in bases:
        if not base:
            continue
        # Inno Setup installs into "Inno Setup 6", "Inno Setup 7", ...; sorting by name
        # keeps the validated 6.x line first and still accepts newer majors.
        for root in (Path(base), Path(base) / 'Programs'):
            if not root.is_dir():
                continue
            for setup_dir in sorted(root.glob('Inno Setup *')):
                candidate = setup_dir / 'ISCC.exe'
                if candidate.is_file():
                    return candidate
    return None


def _generate_installer_assets(version: str) -> None:
    try:
        from devscripts.make_installer_assets import generate

        generate(ROOT_DIR / 'app' / 'assets' / 'Yt-RivoGUI-Logo.png', ROOT_DIR / 'installer' / 'assets', version)
    except Exception as exc:
        print(f'[build] ERROR: could not generate installer artwork: {exc}', file=sys.stderr)
        raise


def _compile_installer(iscc: Path, dist_path: Path, version: str) -> Path:
    script = ROOT_DIR / 'installer' / 'Yt-RivoGUI.iss'
    if not script.is_file():
        raise FileNotFoundError(f'installer script not found: {script}')
    for stale in dist_path.glob('Yt-RivoGUI-Setup-*.exe'):
        try:
            stale.unlink()
        except OSError:
            pass
    command = [
        str(iscc),
        f'/DMyAppVersion={version}',
        f'/O{dist_path}',
        str(script),
    ]
    print(f'\n[build] Compiling installer: {" ".join(command)}')
    result = subprocess.run(command)
    if result.returncode != 0:
        raise RuntimeError(f'Inno Setup failed with exit code {result.returncode}')
    expected = dist_path / f'Yt-RivoGUI-Setup-v{version}.exe'
    if not expected.is_file():
        raise FileNotFoundError(f'installer was not produced: {expected}')
    return expected


def build(
    onefile: bool = True,
    clean: bool = True,
    dist_dir: Path | None = None,
    *,
    installer: bool = True,
    require_installer: bool = False,
    version: str | None = None,
) -> int:
    os.chdir(ROOT_DIR)
    dist_path = (dist_dir or (ROOT_DIR / 'dist' / 'gui')).resolve()
    work_path = ROOT_DIR / 'build' / 'gui'
    version_str = (version or _read_version()).strip().lstrip('vV') or '0.0.0.0'

    dist_path.mkdir(parents=True, exist_ok=True)
    work_path.mkdir(parents=True, exist_ok=True)

    assets_dir = ROOT_DIR / 'app' / 'assets'
    icon_ico = assets_dir / 'Yt-RivoGUI-Logo.ico'
    icon_png = assets_dir / 'Yt-RivoGUI-Logo.png'

    # Ensure .ico exists for Windows builds
    if sys.platform == 'win32' and not icon_ico.exists() and icon_png.exists():
        try:
            from PIL import Image

            img = Image.open(icon_png)
            sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(icon_ico, format='ICO', sizes=sizes)
            print(f'Generated {icon_ico}')
        except Exception as exc:
            print(f'Notice: Could not generate ICO from PNG: {exc}')

    # Ensure lazy_extractors.py is generated for fast startup and bundled extraction
    lazy_extractors_script = ROOT_DIR / 'devscripts' / 'make_lazy_extractors.py'
    if lazy_extractors_script.exists():
        try:
            subprocess.run([sys.executable, str(lazy_extractors_script)], check=True)
            print('Generated lazy_extractors.py successfully')
        except Exception as exc:
            print(f'Notice: Could not generate lazy_extractors: {exc}')

    # Path separator for --add-data: ; on Windows, : on Unix
    sep = ';' if sys.platform == 'win32' else ':'
    add_data = f'app/assets{sep}app/assets'

    cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconsole',
        '--name=Yt-RivoGUI',
        f'--distpath={dist_path}',
        f'--workpath={work_path}',
        f'--add-data={add_data}',
        '--collect-all=app',
        '--collect-all=yt_dlp',
        '--collect-all=yt_dlp_ejs',
        '--noconfirm',
    ]

    for extra_pkg in ('mutagen', 'pycryptodomex', 'websockets', 'certifi'):
        try:
            __import__(extra_pkg)
            cmd.append(f'--collect-all={extra_pkg}')
        except ImportError:
            pass

    if sys.platform == 'win32':
        version_file = _write_version_file(ROOT_DIR / 'build' / 'gui-version_info.txt', version_str)
        cmd.append(f'--version-file={version_file}')

    if onefile:
        cmd.append('--onefile')
    else:
        cmd.append('--onedir')

    if clean:
        cmd.append('--clean')

    if sys.platform == 'win32' and icon_ico.exists():
        cmd.append(f'--icon={icon_ico}')
    elif icon_png.exists():
        cmd.append(f'--icon={icon_png}')

    cmd.append('app/__main__.py')

    print(f'Starting build with command:\n{" ".join(str(c) for c in cmd)}\n')
    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        print(f'Build failed with return code {ret.returncode}', file=sys.stderr)
        return ret.returncode

    exe_file = dist_path / EXE_NAME
    if not exe_file.is_file():
        print(f'Build did not produce {exe_file}', file=sys.stderr)
        return 1

    # Remove stale release artifacts before generating this version.
    for old_zip in dist_path.glob('Yt-RivoGUI-*-windows.zip'):
        try:
            old_zip.unlink()
        except OSError:
            pass
    for stale in (dist_path / 'latest.json', dist_path / 'SHA256SUMS.txt'):
        try:
            stale.unlink()
        except OSError:
            pass

    # Zip archive for releases (avoids browser heuristics for the bare exe).
    zip_name = f'Yt-RivoGUI-v{version_str}-windows.zip'
    zip_path = dist_path / zip_name
    print(f'\nPacking standalone zip archive: {zip_path.name}...')
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_file, arcname=EXE_NAME)
        for extra in (ROOT_DIR / 'README.md', ROOT_DIR / 'LICENSE'):
            if extra.exists():
                zf.write(extra, arcname=extra.name)
    print(f'Zip archive created successfully: {zip_path.name} ({zip_path.stat().st_size / (1024 * 1024):.2f} MB)\n')

    # Branded installer
    if installer:
        iscc = find_iscc()
        if iscc is None:
            message = 'Inno Setup 6.7+ compiler not found; skipping installer'
            if require_installer:
                print(f'[build] ERROR: {message}', file=sys.stderr)
                return 1
            print(f'[build] Notice: {message}')
        else:
            try:
                _generate_installer_assets(version_str)
                setup_path = _compile_installer(iscc, dist_path, version_str)
            except Exception as exc:
                if require_installer:
                    print(f'[build] ERROR: {exc}', file=sys.stderr)
                    return 1
                print(f'[build] Notice: installer skipped: {exc}', file=sys.stderr)
            else:
                print(f'[build] Installer ready: {setup_path.name} '
                      f'({setup_path.stat().st_size / (1024 * 1024):.2f} MB)')

    # Checksums and release manifest
    try:
        from devscripts.make_update_manifest import build_manifest

        tag = os.getenv('YTRIVO_RELEASE_TAG') or os.getenv('TARGET_TAG') or version_str
        manifest_path = build_manifest(dist_path, version_str, tag=tag)
        print(f'[build] Update manifest written: {manifest_path.name}')
    except Exception as exc:
        print(f'[build] ERROR: could not create update manifest: {exc}', file=sys.stderr)
        return 1

    print(f'\nBuild finished successfully! Artifacts located in: {dist_path}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Build Yt-RivoGUI executable')
    parser.add_argument('--onedir', action='store_true', help='Build directory instead of single standalone executable')
    parser.add_argument('--no-clean', action='store_true', help='Skip cleaning PyInstaller cache before building')
    parser.add_argument('--distpath', type=Path, default=None, help='Custom output directory')
    parser.add_argument('--no-installer', action='store_true', help='Skip the Inno Setup installer')
    parser.add_argument('--require-installer', action='store_true', help='Fail when Inno Setup is unavailable or fails')
    parser.add_argument('--version', default=None, help='Override the version baked into the build')
    args = parser.parse_args()

    return build(
        onefile=not args.onedir,
        clean=not args.no_clean,
        dist_dir=args.distpath,
        installer=not args.no_installer,
        require_installer=args.require_installer,
        version=args.version,
    )


if __name__ == '__main__':
    raise SystemExit(main())
