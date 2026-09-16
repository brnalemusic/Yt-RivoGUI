from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def clean_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub('', str(text))


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
    video_quality: str = 'best'  # 'best', '2160p', '1440p', '1080p', '720p', '480p', '360p'
    video_format: str = 'mp4'  # 'mp4', 'mkv'
    audio_format: str = 'mp3'  # 'mp3', 'm4a', 'flac', 'wav', 'opus'
    audio_quality: str = '320'  # '320', '256', '192', '128', 'best'
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    download_subs: bool = False
    sub_lang: str = 'pt'  # 'pt', 'en', 'all'
    is_playlist: bool = False
    video_muted: bool = False  # If True in split mode, strip audio stream from video container
    output_dir: str = ''


class DownloadCancelledException(Exception):
    pass


class YtDLBackend:
    """Enhanced wrapper around yt-dlp providing video/audio/thumbnail downloads."""

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

            res_limit = {
                '2160p': '[height<=2160]',
                '1440p': '[height<=1440]',
                '1080p': '[height<=1080]',
                '720p': '[height<=720]',
                '480p': '[height<=480]',
                '360p': '[height<=360]',
            }.get(options.video_quality, '')

            if res_limit:
                opts['format'] = f'bestvideo{res_limit}+bestaudio/best{res_limit}/best'
            else:
                opts['format'] = 'bestvideo+bestaudio/best'

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
            # Video mode
            # Quality resolution string
            res_limit = {
                '2160p': '[height<=2160]',
                '1440p': '[height<=1440]',
                '1080p': '[height<=1080]',
                '720p': '[height<=720]',
                '480p': '[height<=480]',
                '360p': '[height<=360]',
            }.get(options.video_quality, '')

            if res_limit:
                opts['format'] = f'bestvideo{res_limit}+bestaudio/best{res_limit}/best'
            else:
                opts['format'] = 'bestvideo+bestaudio/best'

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
        cmd = ['ffmpeg', '-y', '-i', str(video_path), '-c:v', 'copy', '-an', str(temp_path)]
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
