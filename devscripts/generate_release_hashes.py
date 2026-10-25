#!/usr/bin/env python3
"""Writes SHA256SUMS.txt for the top-level files of a release folder.

Only direct children are hashed: release folders may contain subdirectories
(build caches, extracted archives) that are not published as assets.  The
manifest and the checksum file itself are excluded so the file never hashes
its own output.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

EXCLUDED_NAMES = {'SHA256SUMS.txt', 'latest.json'}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.').resolve()
    hashes = []
    for file_path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not file_path.is_file() or file_path.name in EXCLUDED_NAMES:
            continue
        if file_path.suffix.lower() in {'.log', '.tmp'}:
            continue
        hashes.append(f'{sha256_file(file_path)}  {file_path.name}')
    manifest = root / 'SHA256SUMS.txt'
    manifest.write_text('\n'.join(hashes) + ('\n' if hashes else ''), encoding='utf-8')
    print(f'Wrote {manifest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
