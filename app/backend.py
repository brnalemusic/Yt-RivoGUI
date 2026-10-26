from __future__ import annotations

import logging
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Ensure repository root is on sys.path so the embedded yt_dlp technology is always loaded directly
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def clean_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub('', str(text))


def get_app_bin_dir() -> Path:
    """Returns the optional ``bin`` directory shipped next to the application.

    The Windows installer places ``ffmpeg.exe`` and ``ffprobe.exe`` in
    ``<install dir>\\bin``.  Portable builds use the same layout next to the
    executable, while source checkouts look in the repository root.
    """
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = _ROOT_DIR
    return base_dir / 'bin'


def ensure_local_ffmpeg_on_path(bin_dir: Path | None = None) -> str | None:
    """Prepends the local media tools directory to ``PATH`` when both exist.

    Returns the directory when ``ffmpeg`` and ``ffprobe`` are available so the
    caller can also pass it to yt-dlp as ``ffmpeg_location``.
    """
    directory = Path(bin_dir) if bin_dir is not None else get_app_bin_dir()
    ffmpeg = directory / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    ffprobe = directory / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
    if not (ffmpeg.is_file() and ffprobe.is_file()):
        return None

    current_path = os.environ.get('PATH', '')
    entries = current_path.split(os.pathsep) if current_path else []
    normalized = os.path.normcase(str(directory))
    if not entries or os.path.normcase(entries[0]) != normalized:
        os.environ['PATH'] = str(directory) + (os.pathsep + current_path if current_path else '')
    return str(directory)


def get_ffmpeg_executable(bin_dir: Path | None = None) -> str:
    """Returns the local ffmpeg binary when present, otherwise ``ffmpeg``."""
    directory = Path(bin_dir) if bin_dir is not None else get_app_bin_dir()
    names = ('ffmpeg.exe', 'ffmpeg') if os.name == 'nt' else ('ffmpeg',)
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    return 'ffmpeg'


# Resolve the installer-provided media tools once at import time.  The GUI and
# every download worker inherit this PATH, and yt-dlp receives ffmpeg_location.
_LOCAL_FFMPEG_DIR = ensure_local_ffmpeg_on_path()


def get_default_download_dir() -> Path:
    """Returns Videos/Yt-RivoGUI directory in user's home directory."""
    videos_dir = Path.home() / 'Videos'
    if not videos_dir.exists():
        # Fallback for systems without standard Videos folder
        videos_dir = Path.home() / 'Downloads'
    target = videos_dir / 'Yt-RivoGUI'
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


def format_bytes(size: float | int | None) -> str:
    if not size or size <= 0:
        return '0 MB'
    size_mb = size / (1024 * 1024)
    if size_mb >= 1024:
        return f'{size_mb / 1024:.2f} GB'
    return f'{size_mb:.1f} MB'


def format_speed(speed: float | int | None) -> str:
    if not speed or speed <= 0:
        return '0 KB/s'
    speed_kb = speed / 1024
    if speed_kb >= 1024:
        return f'{speed_kb / 1024:.2f} MB/s'
    return f'{speed_kb:.0f} KB/s'


# ---------------------------------------------------------------------------
# Real-stream inspection helpers
#
# The GUI only offers choices the media actually supports: resolution, frame
# rate, video bitrate, embedded-audio bitrate and sample rate are all derived
# from ``info['formats']``.  Nothing here re-encodes media: every choice is a
# yt-dlp format-selection filter over the streams the site already serves.
# ---------------------------------------------------------------------------

# Fallback ladders used when the real stream list is unavailable, e.g. for
# playlists, where ``extract_flat`` returns entries without their formats.
VIDEO_HEIGHT_LADDER = (2160, 1440, 1080, 720, 480, 360, 240, 144)
VIDEO_FPS_LADDER = (60, 45, 30, 24, 15)
GENERIC_VIDEO_BITRATE_LADDER = (8000, 6000, 4000, 2500, 1500, 800)
GENERIC_AUDIO_BITRATE_LADDER = (320, 256, 192, 128, 96)
GENERIC_SAMPLE_RATE_LADDER = (48000, 44100)

# Real sites expose many near-duplicate streams (including low-quality HLS
# renditions); the selectors stay short and useful by keeping the best ones.
MAX_VIDEO_BITRATE_CHOICES = 6
MAX_AUDIO_BITRATE_CHOICES = 4
MAX_SAMPLE_RATE_CHOICES = 3

# Codec preferences expressed as yt-dlp format sorting (no transcoding).  The
# resolution stays the primary criterion, so preferring h.264 never downgrades
# a 4k upload (which often only ships av1/vp9) to the best 1080p h.264 stream.
VIDEO_CODEC_SORT = {
    'h264': 'vcodec:h264',
    'h265': 'vcodec:h265',
}


def _positive_int(value: Any) -> int | None:
    """Best-effort conversion of a numeric format field into a positive int."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_height(value: Any) -> int | None:
    """Parses ``'1080p'``/``'1080'``/``1080`` into ``1080`` (``None`` for best/auto)."""
    if isinstance(value, (int, float)):
        return _positive_int(value)
    if not value or str(value).strip().lower() in ('best', 'auto', 'none'):
        return None
    digits = re.sub(r'[^0-9]', '', str(value))
    return _positive_int(digits) if digits else None


def _iter_info_formats(info: dict[str, Any] | None):
    for fmt in (info or {}).get('formats') or ():
        if isinstance(fmt, dict):
            yield fmt


def _has_stream(fmt: dict[str, Any], key: str) -> bool:
    return str(fmt.get(key) or 'none').lower() != 'none'


def _video_streams(info: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [fmt for fmt in _iter_info_formats(info) if _has_stream(fmt, 'vcodec')]


def _audio_streams(info: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Audio streams, preferring audio-only ones over combined video/audio formats."""
    streams = [fmt for fmt in _iter_info_formats(info) if _has_stream(fmt, 'acodec')]
    audio_only = [fmt for fmt in streams if not _has_stream(fmt, 'vcodec')]
    return audio_only or streams


def available_video_heights(info: dict[str, Any] | None) -> list[int]:
    """Returns every resolution height the video really offers, highest first."""
    heights = {_positive_int(fmt.get('height')) for fmt in _video_streams(info)}
    return sorted({height for height in heights if height}, reverse=True)


def available_video_fps(info: dict[str, Any] | None) -> list[int]:
    """Returns the frame-rate choices supported by the video, highest first.

    Only values at or below the highest natively available frame rate are
    offered, plus that native maximum when it is not part of the ladder
    (e.g. a 50 fps upload keeps ``50 fps``).
    """
    values = {_positive_int(fmt.get('fps')) for fmt in _video_streams(info)}
    values.discard(None)
    if not values:
        return []
    max_fps = max(values)
    options = {fps for fps in VIDEO_FPS_LADDER if fps <= max_fps}
    options.add(max_fps)
    return sorted(options, reverse=True)


def available_video_bitrates(info: dict[str, Any] | None, height: Any = None) -> list[int]:
    """Returns the video bitrates (kbps) really available for the chosen height."""
    streams = _video_streams(info)
    target = parse_height(height)
    if target:
        exact = [fmt for fmt in streams if _positive_int(fmt.get('height')) == target]
        if exact:
            streams = exact

    bitrates: set[int] = set()
    for fmt in streams:
        value = _positive_int(fmt.get('vbr')) or _positive_int(fmt.get('tbr'))
        if value:
            # Round up to the next 100 kbps so the cap always includes the stream
            # it was derived from.
            bitrates.add(int(math.ceil(value / 100.0) * 100))
    return sorted(bitrates, reverse=True)[:MAX_VIDEO_BITRATE_CHOICES]


def available_audio_bitrates(info: dict[str, Any] | None) -> list[int]:
    """Returns the audio bitrates (kbps) really available in the media."""
    bitrates: set[int] = set()
    for fmt in _audio_streams(info):
        value = _positive_int(fmt.get('abr')) or _positive_int(fmt.get('tbr'))
        if value:
            bitrates.add(value)
    return sorted(bitrates, reverse=True)[:MAX_AUDIO_BITRATE_CHOICES]


def available_audio_sample_rates(info: dict[str, Any] | None) -> list[int]:
    """Returns the audio sample rates (Hz) really available in the media."""
    rates = {_positive_int(fmt.get('asr')) for fmt in _audio_streams(info)}
    return sorted({rate for rate in rates if rate}, reverse=True)[:MAX_SAMPLE_RATE_CHOICES]


def format_options_from_info(info: dict[str, Any] | None) -> dict[str, list[int]]:
    """Collects every real-stream choice for the GUI in a single call."""
    return {
        'heights': available_video_heights(info),
        'fps': available_video_fps(info),
        'video_bitrates': available_video_bitrates(info),
        'audio_bitrates': available_audio_bitrates(info),
        'sample_rates': available_audio_sample_rates(info),
    }


def format_seconds(seconds: float | int | None) -> str:
    if not seconds or seconds < 0:
        return '--:--'
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


@dataclass
class ProgressInfo:
    status: str = 'ready'
    percent: float = 0.0
    speed_str: str = '--'
    eta_str: str = '--:--'
    downloaded_str: str = '0 MB'
    total_str: str = '0 MB'
    current_file: str = ''
    raw_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadOptions:
    mode: str = 'video'  # 'video', 'audio', 'split', 'thumbnail_only'
    video_quality: str = 'best'  # 'best' or a real height such as '1080p'
    video_format: str = 'mp4'  # 'mp4', 'mkv'
    video_codec: str = 'h264'  # 'h264', 'h265'
    video_bitrate: str = 'auto'  # 'auto' or a kbps cap derived from real streams
    video_fps: str = 'auto'  # 'auto' or a frame-rate cap derived from real streams
    audio_format: str = 'mp3'  # 'mp3', 'm4a', 'flac', 'wav', 'opus'
    audio_quality: str = '320'  # '320', '256', '192', '128', 'best'
    embedded_audio_bitrate: str = 'auto'  # 'auto' or a kbps cap for the audio inside the video
    embedded_audio_rate: str = 'auto'  # 'auto' or an Hz cap for the audio inside the video
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    download_subs: bool = False
    sub_lang: str = 'pt'  # 'pt', 'en', 'all'
    is_playlist: bool = False
    video_muted: bool = False  # If True in split mode, strip audio stream from video container
    output_dir: str = ''


def _video_cap_filters(options: DownloadOptions) -> list[str]:
    """Builds the optional video caps (frame rate, bitrate), strictest first."""
    parts: list[str] = []
    fps = parse_height(options.video_fps)
    if fps:
        parts.append(f'[fps<={fps}]')
    bitrate = _positive_int(options.video_bitrate)
    if bitrate:
        parts.append(f'[vbr<={bitrate}]')
    return parts


def _apply_codec_preference(opts: dict[str, Any], options: DownloadOptions) -> None:
    """Prefers the chosen codec among equally sized streams only.

    Resolution stays the first sorting criterion, so h.264 never downgrades a
    4k upload to the best 1080p h.264 rendition.
    """
    preference = VIDEO_CODEC_SORT.get(str(options.video_codec or '').lower())
    if preference:
        opts['format_sort'] = ['res', preference]


def _embedded_audio_filter_parts(options: DownloadOptions) -> list[str]:
    """Builds the format filters for the audio embedded in the video stream."""
    parts: list[str] = []
    rate = _positive_int(options.embedded_audio_rate)
    if rate:
        parts.append(f'[asr<={rate}]')
    bitrate = _positive_int(options.embedded_audio_bitrate)
    if bitrate:
        parts.append(f'[abr<={bitrate}]')
    return parts


def build_video_format_expression(options: DownloadOptions, *, embedded_audio: bool = True) -> str:
    """Builds a fallback ladder honouring every quality choice without re-encoding.

    The chosen resolution is the primary decision, so it is tried exactly first
    and only relaxed at the very end.  The frame rate and bitrate are caps: when
    the site ships no stream matching them at that resolution they are dropped
    before the resolution is, which avoids collapsing a 720p request into a 144p
    rendition just because it is the only 15 fps one.  Finally the plain ``best``
    stream keeps the download working on sites with a single combined format.
    ``embedded_audio`` is False for split mode, where the audio is downloaded
    and re-encoded separately.
    """
    height = parse_height(options.video_quality)
    caps = _video_cap_filters(options)
    relaxed = [''.join(caps[:count]) for count in range(len(caps), -1, -1)]

    video_chains = []
    if height:
        # exact resolution first (caps honoured only when they exist there)…
        video_chains += [f'[height={height}]{caps_suffix}' for caps_suffix in relaxed]
        # …then anything up to it, before finally giving the cap priority
        video_chains += [f'[height<={height}]{caps_suffix}' for caps_suffix in relaxed]
    else:
        video_chains = list(relaxed)
    video_chains = [f'bestvideo{filters}' for filters in video_chains]
    video_chains.append('bestvideo')

    audio_chains = ['']
    if embedded_audio:
        audio_parts = _embedded_audio_filter_parts(options)
        audio_chains = [
            ''.join(audio_parts[:count])
            for count in range(len(audio_parts), -1, -1)
        ]

    candidates = [
        f'{video_chain}+bestaudio{audio_chain}'
        for video_chain in video_chains
        for audio_chain in audio_chains
    ]
    if height:
        candidates.append(f'best[height<={height}]')
    candidates.append('best')

    return '/'.join(dict.fromkeys(candidates))


class DownloadCancelledException(Exception):
    pass


class YtDLBackend:
    """Core embedded downloader backend running the media downloading technology directly inside Yt-RivoGUI."""

    def __init__(self, output_dir: str | None = None, *, verbose: bool = False):
        self.output_dir = str(output_dir) if output_dir else str(get_default_download_dir())
        self.verbose = verbose
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _create_progress_hook(self, callback: Callable[[ProgressInfo], None] | None):
        def hook(data: dict[str, Any]):
            if self._is_cancelled:
                raise DownloadCancelledException('Download cancelled by user')

            if not callback:
                return

            status = data.get('status', '')
            info = ProgressInfo(raw_info=data)

            if status == 'downloading':
                info.status = 'downloading'
                total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
                downloaded = data.get('downloaded_bytes', 0)
                if total > 0:
                    info.percent = min((downloaded / total) * 100.0, 100.0)
                else:
                    info.percent = 0.0

                info.downloaded_str = format_bytes(downloaded)
                info.total_str = format_bytes(total)
                info.speed_str = format_speed(data.get('speed'))
                info.eta_str = format_seconds(data.get('eta'))
                info.current_file = Path(data.get('filename', '')).name

            elif status == 'finished':
                info.status = 'processing'
                info.percent = 100.0
                info.downloaded_str = format_bytes(data.get('total_bytes', 0))
                info.total_str = info.downloaded_str
                info.speed_str = '--'
                info.eta_str = '00:00'
                info.current_file = Path(data.get('filename', '')).name

            callback(info)

        return hook

    def extract_metadata(self, url: str) -> dict[str, Any]:
        """Extracts video/playlist information without downloading media."""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {}

            # Handle playlist vs single video
            is_playlist = 'entries' in info or info.get('_type') == 'playlist'
            title = info.get('title') or 'Unknown Title'
            uploader = info.get('uploader') or info.get('channel') or info.get('creator') or 'Unknown'
            duration_sec = info.get('duration') or 0
            view_count = info.get('view_count') or 0
            thumbnails = info.get('thumbnails') or []
            thumb_url = ''
            if thumbnails:
                # pick thumbnail with highest resolution or last entry
                thumb_url = thumbnails[-1].get('url', '')
            elif info.get('thumbnail'):
                thumb_url = info.get('thumbnail', '')

            playlist_count = len(list(info.get('entries', []))) if is_playlist else 0

            return {
                'title': title,
                'uploader': uploader,
                'duration_sec': duration_sec,
                'duration_str': format_seconds(duration_sec),
                'view_count': view_count,
                'thumbnail_url': thumb_url,
                'is_playlist': is_playlist,
                'playlist_count': playlist_count,
                'raw': info,
            }

    def build_ydl_options(
        self,
        options: DownloadOptions,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        target_dir = Path(options.output_dir or self.output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Output template:
        # If playlist, create subfolder with playlist name: Videos/Yt-RivoGUI/<Playlist Title>/<title>.<ext>
        # Otherwise: Videos/Yt-RivoGUI/<title>.<ext>
        if options.is_playlist:
            outtmpl = str(target_dir / '%(playlist_title,playlist)s' / '%(title)s.%(ext)s')
        else:
            outtmpl = str(target_dir / '%(title)s.%(ext)s')

        opts: dict[str, Any] = {
            'outtmpl': outtmpl,
            'noplaylist': not options.is_playlist,
            'quiet': not self.verbose,
            'no_warnings': False,
            'ignoreerrors': False,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'remote_components': ['ejs:github'],
        }
        if _LOCAL_FFMPEG_DIR:
            opts['ffmpeg_location'] = _LOCAL_FFMPEG_DIR

        postprocessors: list[dict[str, Any]] = []

        if progress_callback:
            opts['progress_hooks'] = [self._create_progress_hook(progress_callback)]

        if log_callback:
            class CustomLogger:
                def debug(self, msg: str):
                    clean = clean_ansi(msg)
                    if clean.startswith('[debug]'):
                        return
                    log_callback(clean)

                def info(self, msg: str):
                    log_callback(clean_ansi(msg))

                def warning(self, msg: str):
                    log_callback(f'[aviso] {clean_ansi(msg)}')

                def error(self, msg: str):
                    log_callback(f'[erro] {clean_ansi(msg)}')

            opts['logger'] = CustomLogger()

        # Mode configuration
        if options.mode == 'thumbnail_only':
            opts['skip_download'] = True
            opts['writethumbnail'] = True
            postprocessors.append({
                'key': 'FFmpegThumbnailsConvertor',
                'format': 'png',
                'when': 'before_dl',
            })

        elif options.mode == 'audio':
            # Audio-only extraction
            opts['format'] = 'bestaudio/best'
            audio_codec = options.audio_format.lower()
            quality = options.audio_quality if (options.audio_quality != 'best' and audio_codec != 'wav') else '0'

            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_codec,
                'preferredquality': quality,
            })

            # Note: yt-dlp EmbedThumbnailPP does not support WAV. Skip to prevent EmbedThumbnailPPError.
            if options.embed_thumbnail and audio_codec != 'wav':
                opts['writethumbnail'] = True
                postprocessors.append({'key': 'EmbedThumbnail'})
            elif options.embed_thumbnail and audio_codec == 'wav' and log_callback:
                log_callback('[aviso] arquivos .wav não suportam incorporação de capa; download continuará sem capa.')

            if options.embed_metadata:
                postprocessors.append({
                    'key': 'FFmpegMetadata',
                    'add_chapters': True,
                    'add_metadata': True,
                })

        elif options.mode in ('split', 'video_audio'):
            # Download video and audio separately
            opts['keepvideo'] = True
            opts['format'] = build_video_format_expression(options, embedded_audio=False)
            _apply_codec_preference(opts, options)

            container = options.video_format.lower()
            opts['merge_output_format'] = container

            if options.download_subs:
                opts['writesubtitles'] = True
                opts['writeautomaticsub'] = True
                if options.sub_lang == 'pt':
                    opts['subtitleslangs'] = ['pt', 'pt-BR', 'pt-PT']
                elif options.sub_lang == 'en':
                    opts['subtitleslangs'] = ['en', 'en-US']
                else:
                    opts['subtitleslangs'] = ['pt', 'pt-BR', 'en', 'en-US']
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

            if options.embed_metadata:
                postprocessors.append({
                    'key': 'FFmpegMetadata',
                    'add_chapters': True,
                    'add_metadata': True,
                })

            if options.embed_thumbnail:
                opts['writethumbnail'] = True
                postprocessors.append({
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': True,
                })

            audio_codec = options.audio_format.lower()
            quality = options.audio_quality if (options.audio_quality != 'best' and audio_codec != 'wav') else '0'

            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_codec,
                'preferredquality': quality,
            })

            if options.embed_thumbnail and audio_codec != 'wav':
                postprocessors.append({'key': 'EmbedThumbnail'})
            elif options.embed_thumbnail and audio_codec == 'wav' and log_callback:
                log_callback('[aviso] arquivos .wav não suportam incorporação de capa no áudio.')

        else:
            # Video mode: the audio stream is merged as-is, so the audio
            # preferences are applied as stream filters (never re-encoded).
            opts['format'] = build_video_format_expression(options)
            _apply_codec_preference(opts, options)

            container = options.video_format.lower()
            opts['merge_output_format'] = container

            if options.embed_thumbnail:
                opts['writethumbnail'] = True
                postprocessors.append({'key': 'EmbedThumbnail'})

            if options.embed_metadata:
                postprocessors.append({
                    'key': 'FFmpegMetadata',
                    'add_chapters': True,
                    'add_metadata': True,
                })

            if options.download_subs:
                opts['writesubtitles'] = True
                opts['writeautomaticsub'] = True
                if options.sub_lang == 'pt':
                    opts['subtitleslangs'] = ['pt', 'pt-BR', 'pt-PT']
                elif options.sub_lang == 'en':
                    opts['subtitleslangs'] = ['en', 'en-US']
                else:
                    opts['subtitleslangs'] = ['pt', 'pt-BR', 'en', 'en-US']
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

        if postprocessors:
            opts['postprocessors'] = postprocessors

        return opts

    def _strip_audio(self, video_path: Path, log_callback: Callable[[str], None] | None = None) -> None:
        """Removes audio stream from the video file using ffmpeg stream copy."""
        if not video_path.exists():
            return
        temp_path = video_path.with_name(f'{video_path.stem}.tmp_muted{video_path.suffix}')
        cmd = [get_ffmpeg_executable(), '-y', '-i', str(video_path), '-c:v', 'copy', '-an', str(temp_path)]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if res.returncode == 0 and temp_path.exists():
                temp_path.replace(video_path)
                if log_callback:
                    log_callback(f'✔ faixa de áudio removida do vídeo: {video_path.name}')
            elif temp_path.exists():
                temp_path.unlink(missing_ok=True)
        except Exception as err:
            logger.warning('Failed to strip audio from %s: %s', video_path, err)
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _handle_split_entry(
        self,
        entry: dict[str, Any],
        options: DownloadOptions,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Finds both video and audio files in split mode and strips audio if requested."""
        audio_path_str = entry.get('filepath')
        video_path: Path | None = None
        audio_path: Path | None = Path(audio_path_str) if audio_path_str else None

        if audio_path and audio_path.exists():
            candidate = audio_path.with_suffix(f'.{options.video_format.lower()}')
            if candidate.exists():
                video_path = candidate

        if not video_path:
            for f in entry.get('__files_to_move', {}).keys():
                candidate = Path(f)
                if candidate.suffix.lower() in ('.mp4', '.mkv') and candidate.exists():
                    video_path = candidate
                    break

        if video_path and video_path.exists():
            entry['video_path'] = str(video_path)
            entry['_filename'] = str(video_path)
            if options.video_muted:
                self._strip_audio(video_path, log_callback)
            if log_callback:
                log_callback(f'✔ vídeo salvo: {video_path.name}')

        if audio_path and audio_path.exists():
            entry['audio_path'] = str(audio_path)
            if log_callback:
                log_callback(f'✔ áudio salvo: {audio_path.name}')

    def download(
        self,
        url: str,
        options: DownloadOptions,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        self._is_cancelled = False
        opts = self.build_ydl_options(options, progress_callback, log_callback)

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError('nenhum dado retornado ou falha no download.')

            if options.mode in ('split', 'video_audio'):
                entries = info.get('entries')
                if entries:
                    for entry in entries:
                        if entry:
                            self._handle_split_entry(entry, options, log_callback)
                else:
                    self._handle_split_entry(info, options, log_callback)

            return info
