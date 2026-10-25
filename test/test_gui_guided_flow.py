from __future__ import annotations

import os

import pytest


def _make_window():
    """Instanciates the main window offscreen with a fixed language."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from app.gui import PHASE_CONFIGURE, PHASE_HOME, PHASE_PROGRESS, MainWindow

    window = MainWindow(allow_update_check=False)
    window.i18n.set_language('pt_BR')
    window.apply_translations()
    return window, PHASE_HOME, PHASE_CONFIGURE, PHASE_PROGRESS


def test_flow_starts_at_home_with_stepper_hidden():
    window, home, _, _ = _make_window()
    try:
        assert window.stack.currentIndex() == home
        assert window.stepper_row.isHidden()
        assert not window.url_input.isHidden()
        # home is minimal: only the url input, paste and save-to controls
        assert not window.btn_paste.isHidden()
        assert not window.btn_save_to.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_section_summaries_show_smart_defaults():
    window, _, _, _ = _make_window()
    try:
        assert window.section_quality.summary_label.text() == 'melhor · mp4'
        assert window.section_audio.summary_label.text() == 'mp3 · melhor bitrate'
        assert window.section_playlist.summary_label.text() == 'vídeo único'
        assert window.section_extras.summary_label.text() == 'capa · metadados'

        # defaults are the best possible configuration
        assert window.quality_combo.currentData() == 'best'
        assert window.format_combo.currentData() == 'mp4'
        assert window.audio_format_combo.currentData() == 'mp3'
        assert window.chk_embed_thumb.isChecked()
        assert window.chk_embed_meta.isChecked()
        assert not window.chk_subtitles.isChecked()
    finally:
        window.close()
        window.deleteLater()


def test_metadata_ready_advances_to_configure_phase():
    window, _, configure, progress = _make_window()
    try:
        info = {
            'title': 'video teste',
            'uploader': 'canal',
            'duration_str': '12:34',
            'is_playlist': True,
            'playlist_count': 42,
        }
        window._on_metadata_ready(info, None)

        assert window.stack.currentIndex() == configure
        assert not window.stepper_row.isHidden()
        assert window.preview_title.text() == 'video teste'
        assert window.preview_playlist_badge.text() == 'playlist: 42 itens'
        assert window.chk_playlist.isChecked()
        assert window.section_playlist.summary_label.text() == '42 itens · baixar tudo'

        # stepper renders the active step
        assert window.step_texts[0].text() == 'link'
        assert window.step_texts[1].text() == 'ajustes'
        assert window.step_texts[1].objectName() == 'StepTextActive'

        # navigation back and forth
        window._go_home()
        assert window.stack.currentIndex() == 0
        window._set_phase(configure)
        window._back_to_settings()
        assert window.stack.currentIndex() == configure
        window._set_phase(progress)
        assert not window.btn_back_settings.isHidden()
        assert window.btn_cancel.isHidden()
        assert window.btn_new_download.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_download_finished_offers_open_and_new_download():
    window, _, _, _ = _make_window()
    try:
        window._on_download_failed('erro simulado')
        assert not window.btn_new_download.isHidden()
        assert not window.btn_back_settings.isHidden()
        assert window.btn_cancel.isHidden()

        window._start_new_download_flow()
        assert window.stack.currentIndex() == 0
        assert not window.url_input.text()
        assert window.btn_new_download.isHidden()
        assert not window.btn_back_settings.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_drawer_opens_and_closes_deterministically():
    window, _, _, _ = _make_window()
    try:
        window._open_drawer()
        assert not window.drawer.isHidden()
        assert not window.drawer_overlay.isHidden()

        # deterministic close: force the final animation state
        window._close_drawer()
        window._drawer_animation.stop()
        window.drawer.move(window._drawer_animation.endValue())
        window._on_drawer_animation_finished()
        assert window.drawer.isHidden()
        assert window.drawer_overlay.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_mode_switch_updates_sections_not_leaf_visibility():
    window, _, _, _ = _make_window()
    try:
        window._set_phase(1)
        # video mode: quality section shown, audio hidden
        assert not window.section_quality.isHidden()
        assert window.section_audio.isHidden()
        assert window.chk_video_muted.isHidden()

        window.radio_split.setChecked(True)
        window._on_mode_changed()
        assert not window.quality_combo.isHidden()
        assert not window.audio_format_combo.isHidden()
        assert not window.chk_video_muted.isHidden()
        assert not window.section_quality.isHidden()
        assert not window.section_audio.isHidden()

        window.radio_thumbnail.setChecked(True)
        window._on_mode_changed()
        assert window.section_quality.isHidden()
        assert window.section_audio.isHidden()
        assert window.section_playlist.isHidden()
        assert window.section_extras.isHidden()
        assert not window.thumb_mode_notice.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_english_summaries_follow_translation():
    window, _, _, _ = _make_window()
    try:
        window.i18n.set_language('en_US')
        window.apply_translations()
        assert window.section_quality.summary_label.text() == 'best · mp4'
        assert window.section_audio.summary_label.text() == 'mp3 · best bitrate'
        assert window.section_playlist.summary_label.text() == 'single video'
        assert window.section_extras.summary_label.text() == 'cover art · metadata'
        assert window.btn_download.text() == 'download now'
        assert window.hero_title_label.text() == 'download any media'
    finally:
        window.close()
        window.deleteLater()


def test_clipboard_prefill_gates_on_visibility(monkeypatch):
    window, _, _, _ = _make_window()
    try:
        target = 'https://example.com/watch?v=abc'

        class _FakeClipboard:
            def text(self):
                return target

        monkeypatch.setattr('app.gui.QApplication.clipboard', lambda: _FakeClipboard())

        # hidden window: prefill must not run
        assert not window.isVisible()
        window._prefill_from_clipboard()
        assert window.url_input.text() == ''

        # visible window: prefill fills the url field
        window.show()
        window._prefill_from_clipboard()
        assert window.url_input.text() == target
        window.hide()
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize(
    ('url', 'accepted'),
    [
        ('https://youtu.be/x', True),
        ('http://site.com/v', True),
        ('not a url', False),
        ('', False),
    ],
)
def test_drop_event_only_accepts_urls(url, accepted):
    window, _, _, _ = _make_window()
    try:
        class _FakeMime:
            def __init__(self, text):
                self._text = text

            def hasUrls(self):
                return False

            def hasText(self):
                return True

            def text(self):
                return self._text

        class _FakeEvent:
            def __init__(self, mime):
                self._mime = mime
                self._accepted = False

            def mimeData(self):
                return self._mime

            def acceptProposedAction(self):
                self._accepted = True

        event = _FakeEvent(_FakeMime(url))
        window.dropEvent(event)
        assert event._accepted is accepted
        if accepted:
            assert window.url_input.text() == url
    finally:
        window.close()
        window.deleteLater()
