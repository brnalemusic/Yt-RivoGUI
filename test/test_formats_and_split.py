from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from app import backend as backend_module
from app.backend import (
    DownloadOptions,
    YtDLBackend,
    available_audio_bitrates,
    available_audio_sample_rates,
    available_video_bitrates,
    available_video_fps,
    available_video_heights,
    build_video_format_expression,
    ensure_local_ffmpeg_on_path,
    format_options_from_info,
    get_ffmpeg_executable,
)
from app.i18n import TRANSLATIONS, I18nManager


def _create_fake_media_tools(bin_dir: Path) -> tuple[Path, Path]:
    suffix = '.exe' if os.name == 'nt' else ''
    bin_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = bin_dir / f'ffmpeg{suffix}'
    ffprobe = bin_dir / f'ffprobe{suffix}'
    ffmpeg.write_bytes(b'fake-ffmpeg')
    ffprobe.write_bytes(b'fake-ffprobe')
    return ffmpeg, ffprobe


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
        'video_codec_label',
        'video_codec_h264',
        'video_codec_h265',
        'video_bitrate_label',
        'video_bitrate_auto',
        'video_fps_label',
        'video_fps_auto',
        'section_audio',
        'audio_bitrate_label',
        'audio_bitrate_auto',
        'audio_rate_label',
        'audio_rate_auto',
        'summary_auto_max',
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


def test_local_ffmpeg_detection_prepends_bin_to_path(tmp_path, monkeypatch):
    """The installer-provided bin folder must win over whatever is already on PATH."""
    bin_dir = tmp_path / 'bin'
    ffmpeg, _ = _create_fake_media_tools(bin_dir)
    monkeypatch.setenv('PATH', 'C:\\Windows\\System32' if os.name == 'nt' else '/usr/bin')

    assert ensure_local_ffmpeg_on_path(bin_dir) == str(bin_dir)
    assert os.environ['PATH'].split(os.pathsep)[0] == str(bin_dir)
    assert get_ffmpeg_executable(bin_dir) == str(ffmpeg)

    # Re-running the helper must not duplicate the PATH entry.
    ensure_local_ffmpeg_on_path(bin_dir)
    entries = [entry for entry in os.environ['PATH'].split(os.pathsep)
               if os.path.normcase(entry) == os.path.normcase(str(bin_dir))]
    assert entries == [str(bin_dir)]


def test_app_bin_dir_uses_executable_location_when_frozen(tmp_path, monkeypatch):
    exe = tmp_path / ('Yt-RivoGUI.exe' if os.name == 'nt' else 'Yt-RivoGUI')
    exe.write_bytes(b'')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe))

    assert backend_module.get_app_bin_dir() == tmp_path / 'bin'


def test_local_ffmpeg_detection_requires_both_binaries(tmp_path):
    """A lone ffmpeg.exe is not enough to advertise the local tools directory."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    ffmpeg = bin_dir / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    ffmpeg.write_bytes(b'fake')

    assert ensure_local_ffmpeg_on_path(bin_dir) is None
    assert get_ffmpeg_executable(bin_dir) == str(ffmpeg)


def test_backend_passes_local_ffmpeg_location(tmp_path, monkeypatch):
    bin_dir = tmp_path / 'bin'
    _create_fake_media_tools(bin_dir)
    monkeypatch.setattr(backend_module, '_LOCAL_FFMPEG_DIR', str(bin_dir))

    opts = YtDLBackend().build_ydl_options(DownloadOptions())

    assert opts['ffmpeg_location'] == str(bin_dir)


def test_backend_omits_ffmpeg_location_without_local_tools(monkeypatch):
    monkeypatch.setattr(backend_module, '_LOCAL_FFMPEG_DIR', None)

    opts = YtDLBackend().build_ydl_options(DownloadOptions())

    assert 'ffmpeg_location' not in opts


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



# ---------------------------------------------------------------------------
# real-stream quality choices (resolution / fps / bitrate / sample rate)
# ---------------------------------------------------------------------------
def _format_info() -> dict:
    return {
        'formats': [
            {'format_id': '137', 'height': 1080, 'vcodec': 'avc1.640028', 'acodec': 'none', 'vbr': 4340, 'fps': 30},
            {'format_id': '248', 'height': 1080, 'vcodec': 'vp9', 'acodec': 'none', 'vbr': 2500, 'fps': 30},
            {'format_id': '136', 'height': 720, 'vcodec': 'avc1.4d401f', 'acodec': 'none', 'vbr': 1536, 'fps': 30},
            {'format_id': '18', 'height': 360, 'vcodec': 'avc1.42001E', 'acodec': 'mp4a.40.2', 'tbr': 700},
            {'format_id': '140', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 128, 'asr': 44100},
        ],
    }


def test_available_video_heights_only_lists_real_resolutions():
    """A 1080p upload must never advertise 4k or 2k."""
    assert available_video_heights(_format_info()) == [1080, 720, 360]
    assert available_video_heights({}) == []
    assert available_video_heights(None) == []


def test_available_video_fps_stops_at_the_native_maximum():
    thirty = {'formats': [{'vcodec': 'avc1', 'fps': 30}]}
    sixty = {'formats': [{'vcodec': 'avc1', 'fps': 60}]}
    fifty = {'formats': [{'vcodec': 'avc1', 'fps': 50}]}

    assert available_video_fps(thirty) == [30, 24, 15]
    assert available_video_fps(sixty) == [60, 45, 30, 24, 15]
    # a native frame rate outside the ladder keeps its own value
    assert available_video_fps(fifty) == [50, 45, 30, 24, 15]
    assert available_video_fps({'formats': [{'vcodec': 'avc1'}]}) == []


def test_available_video_bitrates_follow_the_chosen_height():
    info = _format_info()
    assert available_video_bitrates(info) == [4400, 2500, 1600, 700]
    assert available_video_bitrates(info, '1080p') == [4400, 2500]
    assert available_video_bitrates(info, '720p') == [1600]
    assert available_video_bitrates({}) == []


def test_available_audio_options_respect_the_media_limits():
    """Only the audio the media really carries is offered (44.1 kHz, no 48 kHz)."""
    info = _format_info()
    assert available_audio_bitrates(info) == [128]
    assert available_audio_sample_rates(info) == [44100]

    wide = {'formats': [
        {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 128, 'asr': 44100},
        {'vcodec': 'none', 'acodec': 'opus', 'abr': 160, 'asr': 48000},
    ]}
    assert available_audio_bitrates(wide) == [160, 128]
    assert available_audio_sample_rates(wide) == [48000, 44100]


def test_format_options_from_info_collects_every_choice():
    options = format_options_from_info(_format_info())
    assert options['heights'] == [1080, 720, 360]
    assert options['fps'] == [30, 24, 15]
    assert options['video_bitrates'] == [4400, 2500, 1600, 700]
    assert options['audio_bitrates'] == [128]
    assert options['sample_rates'] == [44100]


def test_video_format_expression_prefers_the_chosen_resolution():
    expression = build_video_format_expression(DownloadOptions(
        video_quality='1080p',
        video_fps='45',
        video_bitrate='4400',
        embedded_audio_bitrate='128',
        embedded_audio_rate='44100',
    ))
    candidates = expression.split('/')

    assert candidates[0] == (
        'bestvideo[height=1080][fps<=45][vbr<=4400]'
        '+bestaudio[asr<=44100][abr<=128]'
    )
    # the caps are relaxed before the requested resolution ever is
    assert 'bestvideo[height=1080]+bestaudio' in candidates
    assert candidates[-2] == 'best[height<=1080]'
    assert candidates[-1] == 'best'


def test_codec_is_a_preference_that_never_downgrades_resolution():
    """h.264 is preferred among equally sized streams, not as a hard filter."""
    h264_opts: dict = {}
    backend_module._apply_codec_preference(h264_opts, DownloadOptions(video_codec='h264'))
    assert h264_opts['format_sort'] == ['res', 'vcodec:h264']

    h265_opts: dict = {}
    backend_module._apply_codec_preference(h265_opts, DownloadOptions(video_codec='h265'))
    assert h265_opts['format_sort'] == ['res', 'vcodec:h265']


def test_frame_rate_cap_without_a_resolution_choice():
    expression = build_video_format_expression(DownloadOptions(video_fps='30'))
    assert expression.split('/')[0] == 'bestvideo[fps<=30]+bestaudio'


def test_split_format_expression_skips_embedded_audio_filters():
    """Split mode re-encodes a separate audio file, so audio filters do not apply."""
    expression = build_video_format_expression(
        DownloadOptions(video_quality='1080p', embedded_audio_rate='44100'),
        embedded_audio=False,
    )
    assert 'asr' not in expression
    assert '[height<=1080]' in expression


def test_video_mode_options_apply_the_real_quality_choices():
    ydl_opts = YtDLBackend().build_ydl_options(DownloadOptions(
        mode='video',
        video_quality='1080p',
        video_codec='h265',
        video_bitrate='4400',
        video_fps='30',
        embedded_audio_bitrate='128',
        embedded_audio_rate='44100',
    ))

    chosen = ydl_opts['format']
    assert chosen.startswith('bestvideo[height=1080][fps<=30][vbr<=4400]+bestaudio[asr<=44100][abr<=128]')
    assert ydl_opts['format_sort'] == ['res', 'vcodec:h265']
    assert ydl_opts['merge_output_format'] == 'mp4'


def test_generated_format_expression_is_accepted_by_ytdlp():
    """Every quality combination must produce a parseable yt-dlp format spec."""
    from yt_dlp import YoutubeDL

    ydl = YoutubeDL({'quiet': True})
    combos = [
        DownloadOptions(),
        DownloadOptions(video_quality='1080p'),
        DownloadOptions(video_codec='h265', video_fps='60', video_bitrate='8000'),
        DownloadOptions(
            video_quality='720p',
            video_codec='h264',
            video_fps='24',
            video_bitrate='1500',
            embedded_audio_bitrate='96',
            embedded_audio_rate='44100',
        ),
    ]
    for options in combos:
        ydl.build_format_selector(build_video_format_expression(options))
        ydl.build_format_selector(build_video_format_expression(options, embedded_audio=False))
