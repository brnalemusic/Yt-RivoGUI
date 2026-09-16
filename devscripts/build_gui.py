#!/usr/bin/env python3
"""Build script for Yt-RivoGUI desktop application using PyInstaller."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def build(onefile: bool = True, clean: bool = True, dist_dir: Path | None = None) -> int:
    os.chdir(ROOT_DIR)
    dist_path = dist_dir or (ROOT_DIR / 'dist' / 'gui')
    work_path = ROOT_DIR / 'build' / 'gui'

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
        except Exception as e:
            print(f'Notice: Could not generate ICO from PNG: {e}')

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

    # Generate hashes
    try:
        from devscripts.generate_release_hashes import main as gen_hashes
        orig_argv = sys.argv
        sys.argv = ['generate_release_hashes.py', str(dist_path)]
        gen_hashes()
        sys.argv = orig_argv
    except Exception as exc:
        print(f'Notice: Hash generation skipped: {exc}')

    print(f'\nBuild finished successfully! Artifacts located in: {dist_path}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Build Yt-RivoGUI executable')
    parser.add_argument('--onedir', action='store_true', help='Build directory instead of single standalone executable')
    parser.add_argument('--no-clean', action='store_true', help='Skip cleaning PyInstaller cache before building')
    parser.add_argument('--distpath', type=Path, default=None, help='Custom output directory')
    args = parser.parse_args()

    return build(
        onefile=not args.onedir,
        clean=not args.no_clean,
        dist_dir=args.distpath,
    )


if __name__ == '__main__':
    raise SystemExit(main())
