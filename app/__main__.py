from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

# Ensure root directory is on sys.path so embedded engine is always resolved
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

# Ensure stdout and stderr exist even in Windows noconsole / pythonw mode
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def _run_dev(*, allow_update_check: bool = True, allow_multiple: bool = False) -> int:
    logging.info('Starting Yt-RivoGUI in dev mode...')
    try:
        from app.gui import run_gui
        return run_gui(allow_update_check=allow_update_check, allow_multiple=allow_multiple)
    except RuntimeError as exc:
        logging.error(str(exc))
        return 1


def _run_release(*, allow_update_check: bool = True, allow_multiple: bool = False) -> int:
    logging.info('Starting Yt-RivoGUI in release mode...')
    try:
        from app.gui import run_gui
        return run_gui(allow_update_check=allow_update_check, allow_multiple=allow_multiple)
    except RuntimeError as exc:
        logging.error(str(exc))
        return 1


def _run_update_check() -> int:
    from app import __version__
    from app.updater import check_for_updates

    result = check_for_updates(__version__)
    print(f'current: {result.current_version}')
    if result.latest_version:
        print(f'latest: {result.latest_version}')
    print(f'status: {result.status}')
    if result.is_error:
        print(f'error: {result.error_code}: {result.error}', file=sys.stderr)
        return 1
    if result.update_available and result.info:
        print(f'release: {result.info.release_url}')
    return 0


def _run_update_now() -> int:
    from app import __version__
    from app.updater import RELEASES_URL, UpdateError, is_frozen, update_now

    if not is_frozen():
        print('automatic updates are only available in packaged builds.', file=sys.stderr)
        print(f'download the latest version from: {RELEASES_URL}', file=sys.stderr)
        return 1

    last_percent = -1

    def progress(downloaded: int, total: int) -> None:
        nonlocal last_percent
        percent = int(downloaded * 100 / total) if total else 0
        if percent != last_percent:
            last_percent = percent
            print(f'downloading update: {percent}%', flush=True)

    try:
        result = update_now(__version__, progress=progress)
    except UpdateError as exc:
        print(f'update failed: {exc}', file=sys.stderr)
        return 1

    if result.is_error:
        print(f'update check failed: {result.error or result.error_code}', file=sys.stderr)
        return 1
    if not result.update_available:
        print(f'already up to date: v{result.current_version}')
        return 0
    print('update helper launched; the app will restart on the new version.')
    return 0


def main(argv: list[str] | None = None) -> int:
    from app import __version__

    parser = argparse.ArgumentParser(prog='yt-rivogui', description='Yt-RivoGUI desktop app')
    parser.add_argument('--dev', action='store_true', help='Start in development mode')
    parser.add_argument('--release', action='store_true', help='Start in packaged release mode')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--test-startup', action='store_true', help='Test module imports, backend initialization and exit')
    parser.add_argument('--no-update-check', action='store_true', help='Disable automatic update checks')
    parser.add_argument('--allow-multiple', action='store_true', help='Allow more than one running GUI instance')
    update_group = parser.add_mutually_exclusive_group()
    update_group.add_argument('--check-updates', action='store_true', help='Check GitHub for a newer release and exit')
    update_group.add_argument('--update-now', action='store_true', help='Download and install the latest release and exit')
    args = parser.parse_args(argv)

    if args.test_startup:
        try:
            import app.backend
            import app.gui
            import app.i18n
            import app.updater
            import yt_dlp
            import yt_dlp_ejs
            print(f'yt-rivogui startup test passed: version {__version__}')
            return 0
        except Exception as exc:
            print(f'Startup test failed: {exc}', file=sys.stderr)
            return 1

    if args.check_updates:
        return _run_update_check()
    if args.update_now:
        return _run_update_now()

    allow_update_check = not args.no_update_check
    if args.release:
        return _run_release(
            allow_update_check=allow_update_check,
            allow_multiple=args.allow_multiple,
        )
    return _run_dev(
        allow_update_check=allow_update_check,
        allow_multiple=args.allow_multiple,
    )


if __name__ == '__main__':
    raise SystemExit(main())
