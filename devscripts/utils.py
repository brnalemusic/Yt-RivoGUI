import argparse
import functools
import re
import subprocess


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
        from app import __version__

        return __version__


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
