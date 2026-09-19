from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import functools
import itertools
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile


def read_file(fname):
    with open(fname, encoding='utf-8') as f:
        return f.read()


def write_file(fname, content, mode='w'):
    with open(fname, mode, encoding='utf-8') as f:
        return f.write(content)


def read_version(fname='yt_dlp/version.py', varname='__version__'):
    """Get the version without importing the package"""
    items = {}
    exec(compile(read_file(fname), fname, 'exec'), items)
    return items[varname]


def is_valid_version(version: str) -> bool:
    if not version:
        return False
    clean = str(version).strip().lstrip('vV')
    return bool(re.fullmatch(r'\d+(?:\.\d+){0,3}', clean))


def calculate_version(version=None, fname='yt_dlp/version.py'):
    if version:
        clean = str(version).strip().lstrip('vV')
        if clean:
            assert is_valid_version(clean), 'Version must be numeric and use 1-4 dot-separated segments'
            return clean

    # For Yt-RivoGUI, never generate a date as version.
    # Preserve the real project version from app/__init__.py or fname.
    try:
        from pathlib import Path
        app_init = Path(__file__).resolve().parent.parent / 'app' / '__init__.py'
        if app_init.exists():
            content = app_init.read_text(encoding='utf-8')
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1).strip().lstrip('vV')
    except Exception:
        pass

    try:
        return read_version(fname=fname)
    except Exception:
        return '0.0.3.0'


def get_filename_args(has_infile=False, default_outfile=None):
    parser = argparse.ArgumentParser()
    if has_infile:
        parser.add_argument('infile', help='Input file')
    kwargs = {'nargs': '?', 'default': default_outfile} if default_outfile else {}
    parser.add_argument('outfile', **kwargs, help='Output file')

    opts = parser.parse_args()
    if has_infile:
        return opts.infile, opts.outfile
    return opts.outfile


def compose_functions(*functions):
    return lambda x: functools.reduce(lambda y, f: f(y), functions, x)


def run_process(*args, **kwargs):
    kwargs.setdefault('text', True)
    kwargs.setdefault('check', True)
    kwargs.setdefault('capture_output', True)
    if kwargs['text']:
        kwargs.setdefault('encoding', 'utf-8')
        kwargs.setdefault('errors', 'replace')
    return subprocess.run(args, **kwargs)


def request(url: str, *, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    return contextlib.closing(urllib.request.urlopen(req))


def call_github_api(path: str, *, query: dict | None = None) -> dict | list:
    API_BASE_URL = 'https://api.github.com/'
    assert not path.startswith(('https://', 'http://')) or path.startswith(API_BASE_URL)

    url = urllib.parse.urlparse(urllib.parse.urljoin(API_BASE_URL, path))
    qs = urllib.parse.urlencode({
        **urllib.parse.parse_qs(url.query),
        **(query or {}),
    }, True)

    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'yt-dlp',
        'X-GitHub-Api-Version': '2026-03-10',
    }
    if gh_token := os.getenv('GH_TOKEN'):
        headers['Authorization'] = f'Bearer {gh_token}'

    with request(urllib.parse.urlunparse(url._replace(query=qs)), headers=headers) as resp:
        return json.load(resp)


def zipf_files_and_folders(zipf: zipfile.ZipFile, glob: str = '*') -> tuple[list[str], list[str]]:
    files = []
    folders = []

    path = zipfile.Path(zipf)
    for f in itertools.chain(path.glob(glob), path.rglob(glob)):
        if not f.is_file():
            continue
        files.append(f.at)  # type: ignore[attr-defined]
        folder = f.parent.at.rstrip('/')  # type: ignore[attr-defined]
        if folder and folder not in folders:
            folders.append(folder)

    return files, folders
