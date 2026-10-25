"""GUI-level tests for the update banner, version badge and language parity.

The tests run Qt with the offscreen platform plugin so they work on CI without
a desktop session.  They never touch the network: worker threads are replaced
by state transitions and plain fake objects.
"""

from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from PySide6.QtWidgets import QApplication

from app import __version__
from app.updater import UpdateAsset, UpdateInfo


GITHUB_BASE = 'https://github.com/brnalemusic/Yt-RivoGUI/releases/download'


@pytest.fixture(scope='module')
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('YTRIVO_DATA_DIR', str(tmp_path / 'data'))
    yield tmp_path / 'data'


@pytest.fixture
def window(qt_app, isolated_data_dir):
    from app.gui import MainWindow

    win = MainWindow(allow_update_check=False)
    win.i18n.set_language('pt_BR')
    win.apply_translations()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()
        qt_app.processEvents()


def _asset(name: str, version: str = '0.0.5.0', *, checksum: bool = True) -> UpdateAsset:
    return UpdateAsset(
        name=name,
        url=f'{GITHUB_BASE}/{version}/{name}',
        size=1024,
        sha256='a' * 64 if checksum else None,
    )


def _info(version: str = '0.0.5.0', *, installer: bool = True, portable: bool = True) -> UpdateInfo:
    assets: dict[str, UpdateAsset] = {}
    if installer:
        assets['installer'] = _asset(f'Yt-RivoGUI-Setup-v{version}.exe', version)
    if portable:
        assets['portable'] = _asset('Yt-RivoGUI.exe', version)
    return UpdateInfo(
        version=version,
        tag=version,
        release_url=f'https://github.com/brnalemusic/Yt-RivoGUI/releases/tag/{version}',
        notes_url=f'https://github.com/brnalemusic/Yt-RivoGUI/releases/tag/{version}',
        assets=assets,
    )


def _visible_texts(*widgets) -> list[str]:
    return [widget.text() for widget in widgets if not widget.isHidden()]


def _assert_lowercase(*widgets) -> None:
    for text in _visible_texts(*widgets):
        assert text == text.lower(), f'not lowercase: {text!r}'


class _RunningThread:
    """Minimal stand-in for a QThread that reports activity."""

    def isRunning(self) -> bool:  # noqa: N802 - mirrors the Qt API
        return True


# ---------------------------------------------------------------------------
# badge and static states
# ---------------------------------------------------------------------------

def test_version_badge_is_clickable_and_lowercase(window):
    assert window.version_badge.text() == f'v{__version__}'
    assert window.version_badge.text() == window.version_badge.text().lower()
    assert window.version_badge.toolTip() == window.i18n('update_check_tooltip').lower()
    assert window.update_banner.isHidden()
    assert window._update_state == 'hidden'


def test_checking_state_renders_lowercase(window):
    window._set_update_state('checking')
    assert not window.update_banner.isHidden()
    assert window.update_title.text() == 'verificando atualizações...'
    assert window.update_detail.text() == 'consultando o canal estável do github...'
    assert window.update_install_btn.isHidden()
    assert window.update_progress.isHidden()
    _assert_lowercase(window.update_title, window.update_detail)


def test_language_switch_keeps_banner_lowercase(window):
    window._set_update_state('checking')
    before = window.update_title.text()

    window.i18n.set_language('en_US')
    window.apply_translations()
    assert window.update_title.text() == 'checking for updates...'
    assert window.update_title.text() != before
    _assert_lowercase(window.update_title, window.update_detail)

    window.i18n.set_language('pt_BR')
    window.apply_translations()
    assert window.update_title.text() == before


def test_up_to_date_state_offers_only_close(window):
    window._set_update_state('up_to_date', info=_info())
    assert not window.update_banner.isHidden()
    assert window.update_title.text() == 'você está na versão mais recente'
    assert 'v0.0.5.0' in window.update_detail.text()
    assert not window.update_later_btn.isHidden()
    assert window.update_install_btn.isHidden()
    assert window.update_skip_btn.isHidden()
    _assert_lowercase(window.update_title, window.update_detail, window.update_later_btn)


# ---------------------------------------------------------------------------
# available / source / installed modes
# ---------------------------------------------------------------------------

def test_available_in_source_mode_points_to_releases(window):
    window._set_update_state('available', info=_info())
    assert not window.update_banner.isHidden()
    assert window.update_title.text() == 'nova versão disponível: v0.0.5.0'
    assert window.update_detail.text() == window.i18n('update_source_mode').lower()
    assert window.update_install_btn.isHidden()
    assert window.update_notes_btn.text() == 'abrir releases'
    assert not window.update_skip_btn.isHidden()
    assert not window.update_later_btn.isHidden()
    _assert_lowercase(
        window.update_title,
        window.update_detail,
        window.update_notes_btn,
        window.update_skip_btn,
        window.update_later_btn,
    )


def test_download_update_in_source_mode_switches_to_source_state(window):
    window._set_update_state('available', info=_info())
    window._download_update()
    assert window._update_state == 'source'
    assert window.update_install_btn.isHidden()
    assert window.update_notes_btn.text() == 'abrir releases'


def test_installed_mode_offers_installer_asset(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: True)

    window._set_update_state('available', info=_info())
    assert window._update_install_available() is True
    assert not window.update_install_btn.isHidden()
    assert window.update_install_btn.text() == 'baixar e instalar'
    assert 'v0.0.5.0' in window.update_detail.text()
    _assert_lowercase(window.update_title, window.update_detail, window.update_install_btn)


def test_portable_mode_offers_portable_asset(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: False)

    info = _info()
    window._set_update_state('available', info=info)
    assert info.asset_for(installed=False).name == 'Yt-RivoGUI.exe'
    assert not window.update_install_btn.isHidden()


def test_missing_checksum_blocks_install_button(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: True)

    info = UpdateInfo(version='0.0.5.0', tag='0.0.5.0', assets={
        'installer': _asset('Yt-RivoGUI-Setup-v0.0.5.0.exe', checksum=False),
    })
    window._set_update_state('available', info=info)
    assert window._update_install_available() is False
    assert window.update_install_btn.isHidden()
    assert window.update_detail.text() == window.i18n('update_no_asset').lower()
    assert window.update_notes_btn.text() == 'abrir releases'


def test_missing_asset_blocks_install_and_reports_error(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: False)

    window._update_info = _info(portable=False)
    window._download_update()
    assert window._update_state == 'error'
    assert window._update_error_code == 'no_asset'
    assert window.update_detail.text() == window.i18n('update_error_no_asset').lower()
    assert window.update_install_btn.isHidden()


# ---------------------------------------------------------------------------
# download progress, readiness, retries
# ---------------------------------------------------------------------------

def test_downloading_state_renders_progress_and_cancel(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: True)
    window._set_update_state('downloading', info=_info())

    assert not window.update_progress.isHidden()
    assert not window.update_cancel_btn.isHidden()
    assert window.update_install_btn.isHidden()
    assert window.update_title.text() == 'baixando atualização v0.0.5.0...'
    assert window.update_detail.text() == 'baixando... 0% · 0 b / 0 b'

    window._on_update_download_progress(512, 1024)
    assert window.update_progress.value() == 50
    assert '50%' in window.update_detail.text()
    _assert_lowercase(
        window.update_title,
        window.update_detail,
        window.update_cancel_btn,
    )


def test_download_progress_without_total_is_supported(window):
    window._set_update_state('downloading', info=_info())
    window._on_update_download_progress(2048, 0)
    assert window.update_progress.value() == 0
    assert window.update_detail.text().startswith('baixando...')
    assert '2.0 kb' in window.update_detail.text()


def test_ready_state_offers_restart_and_install(window):
    window._set_update_state('ready', info=_info())
    assert not window.update_progress.isHidden()
    assert window.update_progress.value() == 100
    assert window.update_install_btn.text() == 'reiniciar e instalar'
    assert not window.update_install_btn.isHidden()
    assert window.update_detail.text() == 'o aplicativo será fechado e reaberto na versão v0.0.5.0.'
    _assert_lowercase(window.update_title, window.update_detail, window.update_install_btn)


@pytest.mark.parametrize(
    ('code', 'key'),
    [
        ('network', 'update_error_network'),
        ('tls', 'update_error_tls'),
        ('rate_limit', 'update_error_rate_limit'),
        ('not_found', 'update_error_not_found'),
        ('server', 'update_error_server'),
        ('http', 'update_error_http'),
        ('invalid_manifest', 'update_error_invalid_manifest'),
        ('download', 'update_error_download'),
        ('checksum', 'update_error_checksum'),
        ('checksum_missing', 'update_error_checksum_missing'),
        ('install', 'update_error_install'),
        ('something-new', 'update_error_unknown'),
    ],
)
def test_error_states_map_to_translated_messages(window, code, key):
    window._set_update_state('error', info=_info(), error_code=code)
    assert window.update_title.text() == 'não foi possível verificar atualizações'
    assert window.update_detail.text() == window.i18n(key).lower()
    assert window.update_notes_btn.text() == 'abrir releases'
    _assert_lowercase(window.update_title, window.update_detail)


def test_retry_button_only_for_recoverable_errors(window, monkeypatch):
    monkeypatch.setattr('app.gui.is_frozen', lambda: True)
    monkeypatch.setattr('app.gui.is_running_installed', lambda: True)

    window._set_update_state('error', info=_info(), error_code='checksum')
    assert not window.update_install_btn.isHidden()
    assert window.update_install_btn.text() == 'tentar novamente'

    window._set_update_state('error', info=_info(), error_code='network')
    assert window.update_install_btn.isHidden()


# ---------------------------------------------------------------------------
# skip, busy guard and auto-check preference
# ---------------------------------------------------------------------------

def test_skip_remembers_version_and_hides_banner(window):
    info = _info()
    window._set_update_state('available', info=info)
    window._skip_update_version()

    assert window._update_state == 'hidden'
    assert window.update_banner.isHidden()
    assert window.update_settings.skipped_version == info.version

    from app.updater import UpdateSettings

    assert UpdateSettings.load().skipped_version == info.version


def test_skip_is_ignored_when_no_update_is_known(window):
    window._update_info = None
    window._skip_update_version()
    assert window.update_settings.skipped_version is None


def test_download_is_blocked_while_media_download_runs(window):
    window._update_info = _info()
    window.download_thread = _RunningThread()
    try:
        window._download_update()
    finally:
        window.download_thread = None

    assert window._update_state == 'hidden'
    assert window.status_label.text() == window.i18n('update_busy').lower()
    assert window.update_banner.isHidden()


def test_install_is_blocked_while_media_download_runs(window, tmp_path):
    setup_file = tmp_path / 'Yt-RivoGUI-Setup-v0.0.5.0.exe'
    setup_file.write_bytes(b'setup')
    window._update_info = _info()
    window._update_path = setup_file
    window.download_thread = _RunningThread()
    try:
        window._install_update()
    finally:
        window.download_thread = None

    assert window.status_label.text() == window.i18n('update_busy').lower()
    assert window._update_state == 'hidden'


def test_auto_check_toggle_persists_preference(window):
    from app.updater import UpdateSettings

    window.chk_auto_update.setChecked(False)
    assert window.update_settings.auto_check_updates is False
    assert UpdateSettings.load().auto_check_updates is False

    window.chk_auto_update.setChecked(True)
    assert window.update_settings.auto_check_updates is True
    assert UpdateSettings.load().auto_check_updates is True


# ---------------------------------------------------------------------------
# update check results
# ---------------------------------------------------------------------------

def test_check_result_available_respects_skipped_version(window):
    from app.updater import CheckResult

    info = _info()
    window.update_settings.skipped_version = info.version
    window._update_manual_check = False
    window._on_update_check_finished(
        CheckResult(
            status='update_available',
            current_version=__version__,
            latest_version=info.version,
            info=info,
        )
    )
    assert window._update_state == 'hidden'

    window._update_manual_check = True
    window._on_update_check_finished(
        CheckResult(
            status='update_available',
            current_version=__version__,
            latest_version=info.version,
            info=info,
        )
    )
    assert window._update_state == 'available'
    assert not window.update_banner.isHidden()


def test_check_result_up_to_date_and_errors(window):
    from app.updater import CheckResult

    window._update_manual_check = True
    window._on_update_check_finished(
        CheckResult(status='up_to_date', current_version=__version__, latest_version=__version__)
    )
    assert window._update_state == 'up_to_date'

    window._update_manual_check = True
    window._on_update_check_finished(
        CheckResult(
            status='error',
            current_version=__version__,
            error_code='network',
            error='offline',
        )
    )
    assert window._update_state == 'error'
    assert window.update_detail.text() == window.i18n('update_error_network').lower()


def test_automatic_check_error_keeps_banner_hidden(window):
    from app.updater import CheckResult

    window._update_manual_check = False
    window._on_update_check_finished(
        CheckResult(
            status='error',
            current_version=__version__,
            error_code='network',
            error='offline',
        )
    )
    assert window._update_state == 'hidden'
    assert window.update_banner.isHidden()
