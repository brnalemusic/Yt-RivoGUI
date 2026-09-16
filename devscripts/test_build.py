#!/usr/bin/env python3
"""Build verification and test script for Yt-RivoGUI desktop executable."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def compute_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha.update(chunk)
    return sha.hexdigest()


def test_build(dist_dir: Path | None = None, auto_build: bool = False) -> int:
    os.chdir(ROOT_DIR)
    dist_path = dist_dir or (ROOT_DIR / 'dist' / 'gui')

    exe_name = 'Yt-RivoGUI.exe' if sys.platform == 'win32' else 'Yt-RivoGUI'
    exe_path = dist_path / exe_name
    checksum_path = dist_path / 'SHA256SUMS.txt'

    print(f'[test_build] Verifying Yt-RivoGUI build in: {dist_path}')

    if not exe_path.exists():
        if auto_build:
            print(f'[test_build] Executable not found. Running build_gui.py first...')
            from devscripts.build_gui import build
            build_code = build(dist_dir=dist_path)
            if build_code != 0:
                print(f'[test_build] Build failed with code {build_code}', file=sys.stderr)
                return build_code
        else:
            print(f'[test_build] ERROR: Executable not found at {exe_path}. Run devscripts/build_gui.py first or pass --build.', file=sys.stderr)
            return 1

    # 1. Check file size
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f'[test_build] Executable found: {exe_path.name} ({size_mb:.2f} MB)')
    if size_mb < 20:
        print(f'[test_build] WARNING: Executable is suspiciously small ({size_mb:.2f} MB)', file=sys.stderr)

    # 2. Check checksums file
    if checksum_path.exists():
        expected_hash = None
        for line in checksum_path.read_text(encoding='utf-8', errors='replace').splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and (parts[1] == exe_name or parts[1].endswith(exe_name)):
                expected_hash = parts[0]
                break

        if expected_hash:
            actual_hash = compute_sha256(exe_path)
            if actual_hash.lower() == expected_hash.lower():
                print(f'[test_build] Checksum verified: {actual_hash[:16]}... (matches SHA256SUMS.txt)')
            else:
                print(f'[test_build] ERROR: Checksum mismatch! Expected {expected_hash}, got {actual_hash}', file=sys.stderr)
                return 1
        else:
            print(f'[test_build] Notice: Executable not listed in {checksum_path}')

        # Check zip archive if present
        zip_files = list(dist_path.glob('*.zip'))
        for zf in zip_files:
            import zipfile
            with zipfile.ZipFile(zf, 'r') as z:
                if exe_name in z.namelist():
                    print(f'[test_build] Zip archive verified: {zf.name} contains {exe_name}')
                else:
                    print(f'[test_build] ERROR: {zf.name} does not contain {exe_name}', file=sys.stderr)
                    return 1
    else:
        print(f'[test_build] Notice: {checksum_path.name} not found')

    # 3. Test execution --version
    print(f'[test_build] Testing executable with --version...')
    try:
        proc = subprocess.run([str(exe_path), '--version'], capture_output=True, text=True, timeout=30)
        output = (proc.stdout + proc.stderr).strip()
        print(f'[test_build] --version output: {output} (exit code: {proc.returncode})')
        if proc.returncode != 0:
            print(f'[test_build] ERROR: --version exited with code {proc.returncode}', file=sys.stderr)
            return proc.returncode
    except Exception as exc:
        print(f'[test_build] ERROR running --version: {exc}', file=sys.stderr)
        return 1

    # 4. Test execution --test-startup
    print(f'[test_build] Testing executable with --test-startup...')
    try:
        proc = subprocess.run([str(exe_path), '--test-startup'], capture_output=True, text=True, timeout=30)
        output = (proc.stdout + proc.stderr).strip()
        print(f'[test_build] --test-startup output: {output} (exit code: {proc.returncode})')
        if proc.returncode != 0:
            print(f'[test_build] ERROR: --test-startup exited with code {proc.returncode}', file=sys.stderr)
            return proc.returncode
    except Exception as exc:
        print(f'[test_build] ERROR running --test-startup: {exc}', file=sys.stderr)
        return 1

    print('\n[test_build] ALL BUILD TESTS PASSED! Executable is verified and production-ready.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Test and verify Yt-RivoGUI executable')
    parser.add_argument('--distpath', type=Path, default=None, help='Custom output directory where executable resides')
    parser.add_argument('--build', action='store_true', help='Automatically run build if executable does not exist or needs rebuild')
    args = parser.parse_args()

    return test_build(dist_dir=args.distpath, auto_build=args.build)


if __name__ == '__main__':
    raise SystemExit(main())
