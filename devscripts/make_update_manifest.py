#!/usr/bin/env python3
"""Builds ``latest.json`` and ``SHA256SUMS.txt`` for a GitHub release.

The updater consumes ``latest.json`` from the ``latest`` release download URL.
Older clients fall back to the GitHub API plus ``SHA256SUMS.txt``, so both
files are always produced together and always describe the exact bytes that
will be uploaded.

``SHA256SUMS.txt`` intentionally excludes ``latest.json`` and itself to avoid
a circular dependency; ``latest.json`` carries the checksum of
``SHA256SUMS.txt`` instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPO = 'brnalemusic/Yt-RivoGUI'
SCHEMA = 1
CHECKSUM_NAME = 'SHA256SUMS.txt'
MANIFEST_NAME = 'latest.json'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_version(value: str) -> str:
    return str(value).strip().lstrip('vV')


def release_files(dist_dir: Path, version: str) -> dict[str, Path]:
    """Locates the exact assets that belong to the requested release."""
    version = normalize_version(version)
    files: dict[str, Path] = {}
    installer = dist_dir / f'Yt-RivoGUI-Setup-v{version}.exe'
    if installer.is_file():
        files['installer'] = installer
    portable = dist_dir / 'Yt-RivoGUI.exe'
    if portable.is_file():
        files['portable'] = portable
    archive = dist_dir / f'Yt-RivoGUI-v{version}-windows.zip'
    if archive.is_file():
        files['portable_zip'] = archive
    return files


def write_checksums(dist_dir: Path, *, exclude: set[str] | None = None) -> dict[str, dict[str, object]]:
    """Writes top-level checksums and returns ``{name: {size, sha256}}``."""
    excluded = {MANIFEST_NAME, CHECKSUM_NAME}
    if exclude:
        excluded.update(exclude)
    entries: dict[str, dict[str, object]] = {}
    lines: list[str] = []
    for path in sorted(dist_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.name in excluded:
            continue
        if path.suffix.lower() in {'.log', '.tmp'}:
            continue
        digest = sha256_file(path)
        entries[path.name] = {'size': path.stat().st_size, 'sha256': digest}
        lines.append(f'{digest}  {path.name}')
    checksum_path = dist_dir / CHECKSUM_NAME
    checksum_path.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
    if lines:
        entries[CHECKSUM_NAME] = {
            'size': checksum_path.stat().st_size,
            'sha256': sha256_file(checksum_path),
        }
    return entries


def _asset(name: str, dist_dir: Path, tag: str, repo: str) -> dict[str, object]:
    path = dist_dir / name
    return {
        'name': name,
        'url': f'https://github.com/{repo}/releases/download/{quote(tag, safe="")}/{quote(name)}',
        'size': path.stat().st_size,
        'sha256': sha256_file(path),
    }


def build_manifest(
    dist_dir: Path,
    version: str,
    *,
    tag: str | None = None,
    repo: str = DEFAULT_REPO,
    published_at: str | None = None,
    output: Path | None = None,
) -> Path:
    dist_dir = dist_dir.resolve()
    version = normalize_version(version)
    tag = (tag or version).strip()
    if not tag:
        raise ValueError('release tag is empty')

    files = release_files(dist_dir, version)
    if not any(key in files for key in ('installer', 'portable', 'portable_zip')):
        raise FileNotFoundError(f'no release assets found in {dist_dir}')

    entries = write_checksums(dist_dir)
    release_url = f'https://github.com/{repo}/releases/tag/{quote(tag, safe="")}'
    manifest: dict[str, object] = {
        'schema': SCHEMA,
        'version': version,
        'tag': tag,
        'channel': 'stable',
        'release_url': release_url,
        'notes_url': release_url,
        'published_at': published_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'assets': {},
    }
    assets: dict[str, object] = {}
    for key, path in files.items():
        info = entries.get(path.name)
        if info is None:
            continue
        assets[key] = _asset(path.name, dist_dir, tag, repo)
    checksum_info = entries.get(CHECKSUM_NAME)
    if checksum_info is not None:
        assets['sha256sums'] = _asset(CHECKSUM_NAME, dist_dir, tag, repo)
    manifest['assets'] = assets

    destination = output or (dist_dir / MANIFEST_NAME)
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    # Validate through the same parser the app uses.
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from app.updater import load_manifest_from_file

        load_manifest_from_file(destination, allow_insecure=False)
    except Exception as exc:
        raise ValueError(f'generated manifest failed validation: {exc}') from exc
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Generate latest.json and SHA256SUMS.txt')
    parser.add_argument('--dist', type=Path, default=ROOT_DIR / 'dist' / 'gui', help='Folder with release artifacts')
    parser.add_argument('--version', default=None, help='Release version (defaults to app.__version__)')
    parser.add_argument('--tag', default=None, help='Git tag used in asset URLs (defaults to the version)')
    parser.add_argument('--repo', default=DEFAULT_REPO, help='GitHub repository (owner/name)')
    parser.add_argument('--published-at', default=None, help='ISO-8601 release timestamp')
    parser.add_argument('--output', type=Path, default=None, help='Manifest output path')
    args = parser.parse_args(argv)

    version = args.version
    if not version:
        try:
            sys.path.insert(0, str(ROOT_DIR))
            from app import __version__

            version = __version__
        except Exception as exc:
            print(f'[manifest] ERROR: could not read app version: {exc}', file=sys.stderr)
            return 1

    try:
        output = build_manifest(
            args.dist,
            version,
            tag=args.tag,
            repo=args.repo,
            published_at=args.published_at,
            output=args.output,
        )
    except Exception as exc:
        print(f'[manifest] ERROR: {exc}', file=sys.stderr)
        return 1

    print(f'[manifest] wrote {output}')
    print(f'[manifest] checksums {args.dist / CHECKSUM_NAME}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
