from __future__ import annotations

import argparse
import io
import logging
import sys

# Ensure stdout and stderr exist even in Windows noconsole / pythonw mode
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def _run_dev() -> int:
    logging.info('Starting Yt-RivoGUI in dev mode...')
    try:
        from app.gui import run_gui
        return run_gui()
    except RuntimeError as exc:
        logging.error(str(exc))
        return 1


def _run_release() -> int:
    logging.info('Starting Yt-RivoGUI in release mode...')
    try:
        from app.gui import run_gui
        return run_gui()
    except RuntimeError as exc:
        logging.error(str(exc))
        return 1


def main(argv: list[str] | None = None) -> int:
    from app import __version__

    parser = argparse.ArgumentParser(prog='yt-rivogui', description='Yt-RivoGUI desktop app')
    parser.add_argument('--dev', action='store_true', help='Start in development mode')
    parser.add_argument('--release', action='store_true', help='Start in packaged release mode')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--test-startup', action='store_true', help='Test module imports, backend initialization and exit')
    args = parser.parse_args(argv)

    if args.test_startup:
        try:
            import app.backend
            import app.gui
            import app.i18n
            import yt_dlp
            import yt_dlp_ejs
            print(f'yt-rivogui startup test passed: version {__version__}')
            return 0
        except Exception as exc:
            print(f'Startup test failed: {exc}', file=sys.stderr)
            return 1

    if args.release:
        return _run_release()
    return _run_dev()


if __name__ == '__main__':
    raise SystemExit(main())
