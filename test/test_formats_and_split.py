from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.backend import DownloadOptions, YtDLBackend
from app.i18n import TRANSLATIONS, I18nManager


def test_i18n_translation_keys_parity():
    """Ensures pt_BR and en_US have identical translation keys."""
    pt_keys = set(TRANSLATIONS['pt_BR'].keys())
    en_keys = set(TRANSLATIONS['en_US'].keys())

    missing_in_en = pt_keys - en_keys
    missing_in_pt = en_keys - pt_keys

    assert not missing_in_en, f"Keys in pt_BR missing from en_US: {missing_in_en}"
    assert not missing_in_pt, f"Keys in en_US missing from pt_BR: {missing_in_pt}"

    # Verify our new keys exist
    expected_new_keys = {
        'mode_split',
        'opt_video_muted',
        'audio_quality_wav',
        'notice_wav_thumbnail',
        'status_downloading_split',
        'status_finished_split',
    }
    for key in expected_new_keys:
        assert key in pt_keys, f"Missing key in pt_BR: {key}"
        assert key in en_keys, f"Missing key in en_US: {key}"
        assert TRANSLATIONS['pt_BR'][key]
        assert TRANSLATIONS['en_US'][key]


def test_i18n_manager_switching():
    i18n = I18nManager('pt_BR')
    assert i18n('mode_split') == 'vídeo + áudio (separados)'
    i18n.set_language('en_US')
    assert i18n('mode_split') == 'video + audio (separated)'


def test_backend_wav_audio_options():
    """Tests that WAV downloads in audio mode avoid EmbedThumbnailPP crash and set PCM quality."""
    backend = YtDLBackend()
    logs: list[str] = []

    opts = DownloadOptions(
        mode='audio',
        audio_format='wav',
        audio_quality='320',  # User selected 320, but WAV should override to lossless '0'
        embed_thumbnail=True,
    )
    ydl_opts = backend.build_ydl_options(opts, log_callback=logs.append)

    postprocessors = ydl_opts.get('postprocessors', [])
    pp_keys = [pp['key'] for pp in postprocessors]

    # Must contain FFmpegExtractAudio with preferredcodec='wav' and preferredquality='0'
    extract_pp = next(pp for pp in postprocessors if pp['key'] == 'FFmpegExtractAudio')
    assert extract_pp['preferredcodec'] == 'wav'
    assert extract_pp['preferredquality'] == '0'

    # Must NOT contain EmbedThumbnail (which raises EmbedThumbnailPPError for WAV)
    assert 'EmbedThumbnail' not in pp_keys

    # Must have logged notice about WAV thumbnail incompatibility
    assert any('wav' in log and 'capa' in log for log in logs)


def test_backend_mp3_audio_options_keeps_thumbnail():
    """Tests that non-WAV formats like MP3 keep EmbedThumbnail when enabled."""
    backend = YtDLBackend()
    opts = DownloadOptions(
        mode='audio',
        audio_format='mp3',
        audio_quality='320',
        embed_thumbnail=True,
    )
    ydl_opts = backend.build_ydl_options(opts)
    postprocessors = ydl_opts.get('postprocessors', [])
    pp_keys = [pp['key'] for pp in postprocessors]

    assert 'FFmpegExtractAudio' in pp_keys
    assert 'EmbedThumbnail' in pp_keys


def test_backend_split_mode_options():
    """Tests build_ydl_options for split mode with video and audio separated."""
    backend = YtDLBackend()
    opts = DownloadOptions(
        mode='split',
        video_quality='1080p',
        video_format='mp4',
        audio_format='wav',
        audio_quality='best',
        embed_thumbnail=True,
        embed_metadata=True,
        video_muted=True,
    )
    ydl_opts = backend.build_ydl_options(opts)

    assert ydl_opts.get('keepvideo') is True
    assert ydl_opts.get('merge_output_format') == 'mp4'
    assert '[height<=1080]' in ydl_opts.get('format', '')

    postprocessors = ydl_opts.get('postprocessors', [])
    pp_keys = [pp['key'] for pp in postprocessors]

    assert 'FFmpegMetadata' in pp_keys
    assert 'FFmpegExtractAudio' in pp_keys

    extract_pp = next(pp for pp in postprocessors if pp['key'] == 'FFmpegExtractAudio')
    assert extract_pp['preferredcodec'] == 'wav'
    assert extract_pp['preferredquality'] == '0'

    # EmbedThumbnail should be present for video (before extraction), but not duplicated after extraction for WAV
    thumb_pps = [pp for pp in postprocessors if pp['key'] == 'EmbedThumbnail']
    assert len(thumb_pps) == 1
    assert thumb_pps[0].get('already_have_thumbnail') is True


def test_strip_audio_removes_audio_stream():
    """Creates a temporary MP4 with audio, calls _strip_audio, and verifies audio stream is removed."""
    backend = YtDLBackend()
    with tempfile.TemporaryDirectory() as td:
        src_mp4 = Path(td) / 'test_video.mp4'
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=1',
            '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=1',
            '-c:v', 'libx264', '-c:a', 'aac',
            str(src_mp4)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Before stripping: should have video and audio streams
        probe_before = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', str(src_mp4)],
            capture_output=True, text=True, check=True
        )
        assert 'video' in probe_before.stdout
        assert 'audio' in probe_before.stdout

        # Call _strip_audio
        backend._strip_audio(src_mp4)

        # After stripping: should only have video stream
        probe_after = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', str(src_mp4)],
            capture_output=True, text=True, check=True
        )
        assert 'video' in probe_after.stdout
        assert 'audio' not in probe_after.stdout


def test_handle_split_entry_populates_paths():
    backend = YtDLBackend()
    with tempfile.TemporaryDirectory() as td:
        video_file = Path(td) / 'test.mp4'
        audio_file = Path(td) / 'test.wav'
        video_file.touch()
        audio_file.touch()

        entry = {'filepath': str(audio_file)}
        opts = DownloadOptions(mode='split', video_format='mp4', audio_format='wav', video_muted=False)
        backend._handle_split_entry(entry, opts)

        assert entry['video_path'] == str(video_file)
        assert entry['audio_path'] == str(audio_file)
        assert entry['_filename'] == str(video_file)


def test_gui_split_mode_and_wav_interactions():
    """Tests GUI component reactions when toggling split mode and wav audio format."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from app.gui import MainWindow
    window = MainWindow()

    # Initial state: video mode
    assert window.radio_video.isChecked()
    assert window.chk_video_muted.isHidden()

    # Switch to split mode
    window.radio_split.setChecked(True)
    window._on_mode_changed()
    assert not window.quality_combo.isHidden()
    assert not window.audio_format_combo.isHidden()
    assert not window.chk_video_muted.isHidden()

    # Switch audio format to wav
    idx = window.audio_format_combo.findData('wav')
    assert idx >= 0
    window.audio_format_combo.setCurrentIndex(idx)
    assert not window.audio_quality_combo.isEnabled()
    assert window.audio_quality_combo.currentText() == 'sem perdas (pcm)'

    # Switch language to en_US
    window.lang_combo.setCurrentIndex(1)
    assert window.radio_split.text() == 'video + audio (separated)'
    assert window.chk_video_muted.text() == 'video without audio (video only)'
    assert window.audio_quality_combo.currentText() == 'lossless (pcm)'

    # Switch back to pt_BR
    window.lang_combo.setCurrentIndex(0)
    assert window.radio_split.text() == 'vídeo + áudio (separados)'
    assert window.chk_video_muted.text() == 'vídeo sem áudio (apenas vídeo)'
    assert window.audio_quality_combo.currentText() == 'sem perdas (pcm)'

    # Switch audio format to mp3
    idx_mp3 = window.audio_format_combo.findData('mp3')
    window.audio_format_combo.setCurrentIndex(idx_mp3)
    assert window.audio_quality_combo.isEnabled()

