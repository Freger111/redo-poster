"""Гифки для канала: оживший heatmap и зум по картинке новости."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config as cfg

RED = (255, 64, 64)
GREEN = (46, 214, 118)
DARK = (11, 11, 15)


def _font(path: str, size: int):
    for candidate in (path, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "C:/Windows/Fonts/arialbd.ttf"):
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _tile_color(change: float) -> tuple[int, int, int]:
    strength = min(abs(change) / 8.0, 1.0)
    if change >= 0:
        return (int(30 + 16 * strength), int(90 + 130 * strength), int(60 + 50 * strength))
    return (int(90 + 150 * strength), int(30 + 10 * strength), int(36 + 10 * strength))


def _save_gif(frames: list[Image.Image], path: Path, duration: int = 110) -> Path:
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration,
                   loop=0, optimize=True, disposal=2)
    return path


def heatmap(coins: list[dict], size: int = 800) -> bytes:
    """Плитки появляются ряд за рядом, в конце — заголовок."""
    cols, rows = 6, 4
    gap = 8
    margin = 36
    tile_w = (size - margin * 2 - gap * (cols - 1)) // cols
    grid_top = 132
    tile_h = 104

    def frame(reveal: int, title: str = "") -> Image.Image:
        img = Image.new("RGB", (size, size), DARK)
        d = ImageDraw.Draw(img)
        btc = coins[0]
        accent = GREEN if btc["change"] >= 0 else RED
        d.rectangle([0, 0, size, 10], fill=accent)
        d.text((margin, 22), "РЕДО · РЫНОК", font=_font(cfg.FONT_MONO, 17), fill=cfg.GRAY)
        d.text((margin, 44), f"BTC {btc['change']:+.1f}%", font=_font(cfg.FONT_HEAD, 46),
               fill=cfg.WHITE)
        for i, coin in enumerate(coins[: cols * rows]):
            if i >= reveal:
                break
            r, c = divmod(i, cols)
            x = margin + c * (tile_w + gap)
            y = grid_top + r * (tile_h + gap)
            d.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=9,
                                fill=_tile_color(coin["change"]))
            d.text((x + 9, y + 14), coin["symbol"][:5], font=_font(cfg.FONT_HEAD, 17),
                   fill=(255, 255, 255))
            d.text((x + 9, y + 44), f"{coin['change']:+.1f}%", font=_font(cfg.FONT_MONO, 16),
                   fill=(255, 255, 255))
        if title:
            d.text((margin, size - 150), title, font=_font(cfg.FONT_HEAD, 62), fill=cfg.WHITE)
            d.text((margin, size - 42), "nft без хайпа",
                   font=_font(cfg.FONT_MONO, 18), fill=cfg.GRAY)
        return img

    total = min(len(coins), cols * rows)
    title, _ = _headline(coins[0]["change"])
    frames = [frame(n) for n in range(6, total + 1, 3)]
    frames.append(frame(total, title))
    frames.append(frame(total, title))
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=120, loop=0, optimize=True)
    return buf.getvalue()


def _headline(change: float) -> tuple[str, str]:
    if change <= -5:
        return "РЫНОК ГОРИТ", "красная волна"
    if change <= -2:
        return "КРАСНОЕ УТРО", "биток тянет всех"
    if change >= 4:
        return "ЗЕЛЁНАЯ НЕДЕЛЯ", "топ в плюсе"
    if change >= 1:
        return "ОТСКОК", "покупатели вернулись"
    return "БОКОВИК", "рынок выбирает"


def news_zoom(image_path: Path, title: str, size: int = 720) -> bytes:
    """Картинка новости медленно приближается, снизу выезжает заголовок."""
    import re

    title = re.sub(r"<[^>]+>", "", title).strip()
    base = Image.open(image_path).convert("RGB")
    ratio = max(size / base.width, size / base.height)
    base = base.resize((int(base.width * ratio), int(base.height * ratio)), Image.LANCZOS)

    frames: list[Image.Image] = []
    steps = 6
    for i in range(steps):
        zoom = 1.0 + i * 0.018
        crop_w, crop_h = int(base.width / zoom), int(base.height / zoom)
        left = (base.width - crop_w) // 2
        top = (base.height - crop_h) // 2
        frame = base.crop((left, top, left + crop_w, top + crop_h)).resize((size, size),
                                                                          Image.LANCZOS)

        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        start = int(size * 0.45)
        for y in range(start, size):
            alpha = int(235 * (y - start) / (size - start))
            d.line([(0, y), (size, y)], fill=(0, 0, 0, alpha))
        d.rectangle([0, 0, size - 1, size - 1], outline=cfg.LIME, width=5)
        d.text((22, 18), "РЕДО", font=_font(cfg.FONT_HEAD, 20), fill=cfg.LIME)

        font = _font(cfg.FONT_HEAD, 28)
        shown = title[: max(1, int(len(title) * (i + 1) / steps))]
        lines = _wrap(shown, font, size - 50, d)[-3:]
        y = size - 34 - len(lines) * 34
        for line in lines:
            d.text((26, y), line, font=font, fill=(255, 255, 255))
            y += 34
        merged = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")
        frames.append(merged.quantize(colors=48, method=Image.MEDIANCUT))

    frames.append(frames[-1])
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=150, loop=0, optimize=True)
    return buf.getvalue()


def _wrap(text: str, font, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def save_preview(data: bytes, name: str) -> Path:
    path = cfg.OUT / name
    path.write_bytes(data)
    return path
