"""Yt-RivoGUI desktop application package."""

from __future__ import annotations

__title__ = "Yt-RivoGUI"
__author__ = "Breno Alexandrē"
__email__ = "brenoalexandre.music@gmail.com"
__url__ = "https://github.com/brnalemusic/Yt-RivoGUI"
__funding__ = "https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L"
__platform__ = "Windows (Windows 10 / 11 64-bit)"
__description__ = (
    "A feature-rich tool for downloading video and audio from any platform, "
    "featuring a graphical interface and powered by yt-dlp technology."
)

__all__ = [
    "__title__",
    "__author__",
    "__email__",
    "__url__",
    "__funding__",
    "__platform__",
    "__description__",
    "__version__",
]

try:
    from yt_dlp.version import __version__
except Exception:
    __version__ = "0.0.1.0"
