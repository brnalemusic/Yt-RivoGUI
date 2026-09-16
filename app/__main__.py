from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def _run_dev() -> int:
    print('Starting Yt-RivoGUI in dev mode...')
    try:
        from app.gui import run_gui
        return run_gui()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1


def _run_release() -> int:
    print('Starting Yt-RivoGUI in release mode...')
    try:
        from app.gui import run_gui
        return run_gui()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Yt-RivoGUI desktop app')
    parser.add_argument('--dev', action='store_true', help='Start in development mode')
    parser.add_argument('--release', action='store_true', help='Start in packaged release mode')
    args = parser.parse_args(argv)

    if args.release:
        return _run_release()
    return _run_dev()


if __name__ == '__main__':
    raise SystemExit(main())
