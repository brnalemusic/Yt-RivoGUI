#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.').resolve()
    hashes = []
    for file_path in sorted(root.rglob('*')):
        if file_path.is_file() and file_path.name != 'SHA256SUMS.txt':
            hashes.append(f'{sha256_file(file_path)}  {file_path.name}')
    manifest = Path(root / 'SHA256SUMS.txt')
    manifest.write_text('\n'.join(hashes) + ('\n' if hashes else ''), encoding='utf-8')
    print(f'Wrote {manifest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
