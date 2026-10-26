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
        # video mode: the audio section describes the audio embedded in the video
        assert window.section_audio.summary_label.text() == 'melhor · máximo'
        assert window.section_playlist.summary_label.text() == 'vídeo único'
        assert window.section_extras.summary_label.text() == 'capa · metadados'

        # defaults are the best possible configuration
        assert window.quality_combo.currentData() == 'best'
        assert window.format_combo.currentData() == 'mp4'
        assert window.video_codec_combo.currentData() == 'h264'
        assert window.video_bitrate_combo.currentData() == 'auto'
        assert window.video_fps_combo.currentData() == 'auto'
        assert window.embedded_audio_bitrate_combo.currentData() == 'auto'
        assert window.embedded_audio_rate_combo.currentData() == 'auto'
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


def test_drawer_starts_hidden_and_first_click_opens():
    window, _, _, _ = _make_window()
    try:
        # regression: a visible drawer at startup paints as a broken strip in
        # the top-left corner and eats the first hamburger click
        assert window.drawer.isHidden()
        assert window.drawer_overlay.isHidden()
        assert not window._drawer_open

        window._toggle_drawer()
        assert not window.drawer.isHidden()
        assert not window.drawer_overlay.isHidden()
        assert window._drawer_open

        window._toggle_drawer()
        assert not window._drawer_open

        # deterministic close: force the final animation state
        window._drawer_animation.stop()
        window.drawer.move(window._drawer_animation.endValue())
        window._on_drawer_animation_finished()
        assert window.drawer.isHidden()
        assert window.drawer_overlay.isHidden()
    finally:
        window.close()
        window.deleteLater()


def test_paste_icon_prefills_without_continuing(monkeypatch):
    window, home, _, _ = _make_window()
    try:
        target = 'https://example.com/watch?v=abc'

        class _FakeClipboard:
            def text(self):
                return target

        monkeypatch.setattr('app.gui.QApplication.clipboard', lambda: _FakeClipboard())

        window.btn_paste.click()
        assert window.url_input.text() == target
        assert window.stack.currentIndex() == home
        assert not window._preview_loading
        assert window.btn_continue.isEnabled()
        # paste never starts the metadata preview on its own
        assert window.last_fetched_url == ''
    finally:
        window.close()
        window.deleteLater()


def test_continue_waits_in_loading_state_for_the_preview(monkeypatch):
    window, home, configure, _ = _make_window()
    try:
        calls = []
        monkeypatch.setattr(window, '_fetch_metadata', lambda url=None: calls.append(url))

        window.url_input.setText('https://example.com/watch?v=abc')
        assert window.btn_continue.text() == 'continuar'
        assert window.btn_continue.isEnabled()

        window.btn_continue.click()
        assert calls == ['https://example.com/watch?v=abc']
        assert window.stack.currentIndex() == home
        assert window._preview_loading
        assert not window.btn_continue.isEnabled()
        assert window.btn_continue.text().startswith('carregando')
        assert window.hero_hint_label.text() == 'obtendo metadados...'

        # the loading state is cleared only when the preview arrives
        window._on_metadata_ready({'title': 'video teste'}, None)
        assert window.stack.currentIndex() == configure
        assert not window._preview_loading
        assert window.btn_continue.text() == 'continuar'
        assert window.hero_hint_label.text() == 'cole um link de vídeo ou playlist para começar'
    finally:
        window.close()
        window.deleteLater()


def test_continue_rejects_invalid_links():
    window, home, _, _ = _make_window()
    try:
        window.url_input.setText('não é uma url')
        assert not window.btn_continue.isEnabled()
        window._continue_to_preview()
        assert window.stack.currentIndex() == home
        assert window.hero_hint_label.text() == 'cole um link de vídeo ou playlist válido para continuar'
    finally:
        window.close()
        window.deleteLater()


def test_mode_switch_updates_sections_not_leaf_visibility():
    window, _, _, _ = _make_window()
    try:
        window._set_phase(1)
        # video mode: quality section shown, audio section shown too (it sets the
        # quality of the audio embedded into the video), but the separate audio
        # codec controls belong to the audio/split modes
        assert not window.section_quality.isHidden()
        assert not window.section_audio.isHidden()
        assert window.audio_format_combo.isHidden()
        assert window.audio_quality_combo.isHidden()
        assert not window.embedded_audio_bitrate_combo.isHidden()
        assert not window.embedded_audio_rate_combo.isHidden()
        assert window.chk_video_muted.isHidden()

        window.radio_split.setChecked(True)
        window._on_mode_changed()
        assert not window.quality_combo.isHidden()
        assert not window.audio_format_combo.isHidden()
        assert not window.chk_video_muted.isHidden()
        assert not window.section_quality.isHidden()
        assert not window.section_audio.isHidden()
        # the embedded-audio controls only apply to video mode
        assert window.embedded_audio_bitrate_combo.isHidden()
        assert window.embedded_audio_rate_combo.isHidden()

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
        assert window.section_audio.summary_label.text() == 'best · max'
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


def _format_info_1080p_30fps() -> dict:
    """Synthetic metadata: a 1080p/30 fps video with 44.1 kHz audio only."""
    return {
        'formats': [
            {'format_id': '137', 'height': 1080, 'vcodec': 'avc1.640028', 'acodec': 'none', 'vbr': 4340, 'fps': 30},
            {'format_id': '136', 'height': 720, 'vcodec': 'avc1.4d401f', 'acodec': 'none', 'vbr': 1536, 'fps': 30},
            {'format_id': '140', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 128, 'asr': 44100},
        ],
    }


def _combo_data(combo) -> list[str]:
    return [combo.itemData(i) for i in range(combo.count())]


def test_metadata_ready_limits_quality_choices_to_real_streams():
    window, _, _, _ = _make_window()
    try:
        window._on_metadata_ready({'title': 'video teste', 'raw': _format_info_1080p_30fps()}, None)

        # no resolution above what the video really has
        assert _combo_data(window.quality_combo) == ['best', '1080p', '720p']
        assert '2160p' not in _combo_data(window.quality_combo)
        assert '1440p' not in _combo_data(window.quality_combo)

        # frame rate stops at the native 30 fps
        assert _combo_data(window.video_fps_combo) == ['auto', '30', '24', '15']
        assert '60' not in _combo_data(window.video_fps_combo)

        # bitrates are the real ones of the resolution "melhor" would download
        assert _combo_data(window.video_bitrate_combo) == ['auto', '4400']
        assert _combo_data(window.embedded_audio_bitrate_combo) == ['auto', '128']
        assert _combo_data(window.embedded_audio_rate_combo) == ['auto', '44100']

        # choosing 720p narrows the bitrate list to that resolution's streams
        window.quality_combo.setCurrentIndex(window.quality_combo.findData('720p'))
        assert _combo_data(window.video_bitrate_combo) == ['auto', '1600']
    finally:
        window.close()
        window.deleteLater()


def test_audio_section_controls_the_embedded_audio_in_video_mode():
    window, _, _, _ = _make_window()
    try:
        window.radio_video.setChecked(True)
        window._on_mode_changed()
        window._on_metadata_ready({'title': 'video teste', 'raw': _format_info_1080p_30fps()}, None)

        assert not window.section_audio.isHidden()
        assert not window.embedded_audio_bitrate_combo.isHidden()
        assert not window.embedded_audio_rate_combo.isHidden()
        assert window.audio_format_combo.isHidden()
        assert window.audio_quality_combo.isHidden()

        window.embedded_audio_bitrate_combo.setCurrentIndex(
            window.embedded_audio_bitrate_combo.findData('128')
        )
        window.embedded_audio_rate_combo.setCurrentIndex(
            window.embedded_audio_rate_combo.findData('44100')
        )
        assert window.section_audio.summary_label.text() == '128 kbps · 44.1 khz'

        options = None
        from app.backend import DownloadOptions

        options = DownloadOptions()
        window._apply_video_options(options)
        assert options.video_codec == 'h264'
        assert options.video_bitrate == 'auto'
        assert options.video_fps == 'auto'
        assert options.embedded_audio_bitrate == '128'
        assert options.embedded_audio_rate == '44100'
    finally:
        window.close()
        window.deleteLater()


def test_continue_button_keeps_its_size_while_loading(monkeypatch):
    window, _, _, _ = _make_window()
    try:
        monkeypatch.setattr(window, '_fetch_metadata', lambda url=None: None)
        window.url_input.setText('https://example.com/watch?v=abc')

        idle_width = window.btn_continue.width()
        idle_height = window.btn_continue.height()
        assert idle_width > 0

        window.btn_continue.click()
        assert window._preview_loading
        assert window.btn_continue.text() == 'carregando...'
        assert window.btn_continue.width() == idle_width
        assert window.btn_continue.height() == idle_height

        # cycling the loading dots must not resize the button either
        window._tick_loading()
        assert window.btn_continue.width() == idle_width
        assert window.btn_continue.height() == idle_height

        # nor can a language switch change the size between the two states
        window.i18n.set_language('en_US')
        window.apply_translations()
        english_width = window.btn_continue.width()
        window._set_preview_loading(False)
        assert window.btn_continue.width() == english_width
        window._set_preview_loading(True)
        assert window.btn_continue.width() == english_width
    finally:
        window.close()
        window.deleteLater()
