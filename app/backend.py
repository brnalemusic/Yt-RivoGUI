from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL


logger = logging.getLogger(__name__)


@dataclass
class DownloadJob:
    url: str
    output_dir: str = "."
    format: str | None = None
    status: str = "queued"
    progress: float = 0.0
    info: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


class YtDLBackend:
    """Thin wrapper around yt-dlp that exposes app-friendly methods."""

    def __init__(self, output_dir: str = ".", *, verbose: bool = False):
        self.output_dir = output_dir
        self.verbose = verbose

    def _base_options(self, *, skip_download: bool = False, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        opts = {
            'outtmpl': str(Path(self.output_dir) / '%(title)s.%(ext)s'),
            'quiet': not self.verbose,
            'no_warnings': not self.verbose,
            'noplaylist': True,
            'skip_download': skip_download,
            'extract_flat': False,
        }
        if progress_callback:
            opts['progress_hooks'] = [progress_callback]
        return opts

    def extract_info(self, url: str, *, download: bool = False, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        opts = self._base_options(skip_download=not download, progress_callback=progress_callback)
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)

    def download(self, url: str, *, output_dir: str | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        target = Path(output_dir or self.output_dir)
        target.mkdir(parents=True, exist_ok=True)
        opts = self._base_options(skip_download=False, progress_callback=progress_callback)
        opts['outtmpl'] = str(target / '%(title)s.%(ext)s')

        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)
