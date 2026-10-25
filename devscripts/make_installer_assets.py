#!/usr/bin/env python3
"""Generates the branded artwork used by the Inno Setup installer.

The installer ships three images:

* ``wizard-large.png`` - the tall panel shown on the welcome and finished pages.
* ``wizard-back.png``  - a very subtle page background used by every wizard page.
* ``wizard-small.png`` - the square mark shown in the upper-right corner.

All artwork is rendered from the official logo with the same dark/emerald
palette as the desktop app so the installer never looks like a stock Windows
wizard.  Images are rendered at 2x the logical size Inno Setup expects, which
keeps them crisp on high-DPI displays.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ModuleNotFoundError as exc:  # pragma: no cover - build-time tool
    raise SystemExit('Pillow is required: pip install pillow') from exc

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOGO = ROOT_DIR / 'app' / 'assets' / 'Yt-RivoGUI-Logo.png'
DEFAULT_OUTPUT = ROOT_DIR / 'installer' / 'assets'

# Brand palette shared with app/gui.py
BG_TOP = (13, 17, 23)
BG_BOTTOM = (5, 8, 12)
SURFACE = (11, 20, 28)
EMERALD = (52, 211, 153)
EMERALD_DEEP = (16, 185, 129)
EMERALD_SHADOW = (6, 95, 70)
TEXT = (240, 246, 252)
MUTED = (139, 148, 158)
FAINT = (64, 72, 82)

FONT_CANDIDATES = {
    'regular': ('consola.ttf', 'DejaVuSansMono.ttf', 'cour.ttf'),
    'bold': ('consolab.ttf', 'DejaVuSansMono-Bold.ttf', 'courbd.ttf'),
}


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Loads a monospaced font, falling back gracefully on non-Windows hosts."""
    for name in FONT_CANDIDATES['bold' if bold else 'regular']:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new('RGB', size)
    pixels = image.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        for x in range(width):
            pixels[x, y] = color
    return image


def _radial_glow(
    size: tuple[int, int],
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    alpha: int,
) -> Image.Image:
    """Builds a soft radial glow as a separate RGBA layer."""
    width, height = size
    glow = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(glow)
    steps = 26
    for step in range(steps, 0, -1):
        ratio = step / steps
        r = max(1, int(radius * ratio))
        value = int(alpha * (1 - ratio) ** 2)
        draw.ellipse(
            (center[0] - r, center[1] - r, center[0] + r, center[1] + r),
            fill=value,
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius / 6))
    layer = Image.new('RGBA', (width, height), color + (0,))
    layer.putalpha(glow)
    return layer


def _dot_grid(size: tuple[int, int], spacing: int = 28, alpha: int = 12) -> Image.Image:
    width, height = size
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for y in range(spacing // 2, height, spacing):
        for x in range(spacing // 2, width, spacing):
            draw.point((x, y), fill=(52, 211, 153, alpha))
    return layer


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _text_width(font, text: str, tracking: int = 0) -> float:
    return sum(font.getlength(char) for char in text) + tracking * max(0, len(text) - 1)


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    position: tuple[float, float],
    text: str,
    font,
    fill,
    tracking: int = 0,
) -> None:
    x, y = position
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += font.getlength(char) + tracking


def _draw_centered_tracked(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    y: int,
    text: str,
    font,
    fill,
    tracking: int = 0,
) -> None:
    width = _text_width(font, text, tracking)
    _draw_tracked(draw, ((size[0] - width) / 2, y), text, font, fill, tracking)


def _logo_tile(logo: Image.Image, size: int) -> Image.Image:
    """Returns the square logo scaled to ``size`` with a transparent margin removed."""
    source = logo.convert('RGBA')
    bbox = source.getbbox()
    if bbox:
        source = source.crop(bbox)
    return source.resize((size, size), Image.LANCZOS)


def _divider(size: tuple[int, int], y: int, width: int, height: int = 2) -> Image.Image:
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0 = (size[0] - width) // 2
    for offset in range(width):
        ratio = abs(offset - width / 2) / (width / 2)
        alpha = int(220 * (1 - ratio) + 15)
        draw.line((x0 + offset, y, x0 + offset, y + height), fill=EMERALD + (alpha,))
    return layer


def make_wizard_large(logo: Image.Image, destination: Path, version: str) -> Path:
    """Builds the tall welcome/finished panel (logical 164x314)."""
    width, height = 328, 628
    base = _vertical_gradient((width, height), (18, 28, 38), (4, 7, 10)).convert('RGBA')
    base.alpha_composite(_radial_glow((width, height), (width // 2, 120), 240, EMERALD_SHADOW, 70))
    base.alpha_composite(_radial_glow((width, height), (width, 520), 260, EMERALD_DEEP, 34))
    base.alpha_composite(_dot_grid((width, height), spacing=26, alpha=10))

    tile = _logo_tile(logo, 136)
    logo_x = (width - tile.width) // 2
    logo_y = 104

    halo = _radial_glow((width, height), (width // 2, logo_y + tile.height // 2), 150, EMERALD, 46)
    base.alpha_composite(halo)
    base.alpha_composite(tile, (logo_x, logo_y))

    draw = ImageDraw.Draw(base)
    wordmark_font = _load_font(33, bold=True)
    _draw_centered_tracked(draw, (width, height), 288, 'yt-rivogui', wordmark_font, TEXT, tracking=2)

    tagline_font = _load_font(12)
    _draw_centered_tracked(draw, (width, height), 344, 'minimalist media', tagline_font, MUTED, tracking=1)
    _draw_centered_tracked(draw, (width, height), 362, 'downloader', tagline_font, MUTED, tracking=1)

    base.alpha_composite(_divider((width, height), 412, 88))

    version_font = _load_font(12, bold=True)
    _draw_centered_tracked(draw, (width, height), 430, f'v{version}', version_font, EMERALD, tracking=1)

    meta_font = _load_font(10)
    _draw_centered_tracked(draw, (width, height), 556, 'windows 10 / 11 · x64', meta_font, FAINT, tracking=0)
    _draw_centered_tracked(draw, (width, height), 574, 'github.com/brnalemusic', meta_font, FAINT, tracking=0)

    # Thin emerald seam on the content-facing edge.
    seam = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    seam_draw = ImageDraw.Draw(seam)
    for y in range(height):
        ratio = y / (height - 1)
        alpha = int(180 * (1 - abs(ratio - 0.5) * 2) + 20)
        seam_draw.line((width - 1, y, width - 1, y), fill=EMERALD + (alpha,))
    base.alpha_composite(seam)

    destination.parent.mkdir(parents=True, exist_ok=True)
    base.convert('RGB').save(destination, format='PNG', optimize=True)
    return destination


def make_wizard_back(logo: Image.Image, destination: Path) -> Path:
    """Builds the subtle full-page background (logical 497x360)."""
    width, height = 994, 720
    base = _vertical_gradient((width, height), (10, 15, 21), (4, 6, 9)).convert('RGBA')
    base.alpha_composite(_radial_glow((width, height), (width - 40, -80), 520, EMERALD_SHADOW, 46))
    base.alpha_composite(_radial_glow((width, height), (width + 120, height + 60), 620, EMERALD_DEEP, 34))
    base.alpha_composite(_dot_grid((width, height), spacing=34, alpha=9))

    # Oversized watermark mark, kept faint so page text stays readable.
    watermark = _logo_tile(logo, 420)
    alpha = watermark.getchannel('A').point(lambda value: int(value * 0.055))
    watermark.putalpha(alpha)
    base.alpha_composite(watermark, (width - 286, height - 268))

    # A very quiet corner accent line, also low contrast.
    accent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent)
    accent_draw.line((0, 3, width, 3), fill=EMERALD + (36,), width=2)
    base.alpha_composite(accent)

    destination.parent.mkdir(parents=True, exist_ok=True)
    base.convert('RGB').save(destination, format='PNG', optimize=True)
    return destination


def make_wizard_small(logo: Image.Image, destination: Path) -> Path:
    """Builds the square corner mark (logical 58x58)."""
    size = 116
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    tile = Image.new('RGBA', (size, size), SURFACE + (255,))
    tile.putalpha(_rounded_mask((size, size), 22))
    canvas.alpha_composite(tile)

    border = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        (1, 1, size - 2, size - 2), radius=21, outline=EMERALD_SHADOW + (255,), width=2
    )
    canvas.alpha_composite(border)

    mark = _logo_tile(logo, 84)
    canvas.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format='PNG', optimize=True)
    return destination


def generate(logo_path: Path, output_dir: Path, version: str) -> list[Path]:
    if not logo_path.is_file():
        raise FileNotFoundError(f'logo not found: {logo_path}')
    logo = Image.open(logo_path)
    outputs = [
        make_wizard_large(logo, output_dir / 'wizard-large.png', version),
        make_wizard_back(logo, output_dir / 'wizard-back.png'),
        make_wizard_small(logo, output_dir / 'wizard-small.png'),
    ]
    for path in outputs:
        with Image.open(path) as image:
            print(f'[assets] {path.relative_to(ROOT_DIR) if path.is_relative_to(ROOT_DIR) else path} '
                  f'{image.width}x{image.height} ({path.stat().st_size / 1024:.1f} KB)')
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Generate branded Inno Setup artwork')
    parser.add_argument('--logo', type=Path, default=DEFAULT_LOGO, help='Source logo PNG')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Destination asset directory')
    parser.add_argument('--version', default=None, help='Version shown on the welcome panel')
    args = parser.parse_args(argv)

    version = args.version
    if not version:
        try:
            sys.path.insert(0, str(ROOT_DIR))
            from app import __version__
            version = __version__
        except Exception:
            version = '0.0.0.0'
    version = str(version).strip().lstrip('vV')

    try:
        generate(args.logo, args.output, version)
    except Exception as exc:
        print(f'[assets] ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
