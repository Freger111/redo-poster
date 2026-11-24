"""Отрисовка постов в стиле РЕДО: чёрный фон, лаймовый акцент."""
from __future__ import annotations

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config as cfg

SIZE = 1080


FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(path: str, size: int):
    for candidate in (path, *FALLBACK_FONTS):
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


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


def render(tag: str, title: str, subtitle: str = "", index: str = "") -> bytes:
    """Обложка поста 1080×1080."""
    img = Image.new("RGB", (SIZE, SIZE), cfg.BLACK)
    d = ImageDraw.Draw(img)

    # сетка
    for x in range(0, SIZE, 40):
        d.line([(x, 0), (x, SIZE)], fill=(16, 16, 21))
    for y in range(0, SIZE, 40):
        d.line([(0, y), (SIZE, y)], fill=(16, 16, 21))

    # верхняя полоса и бренд
    d.rectangle([0, 0, SIZE, 14], fill=cfg.LIME)
    d.text((70, 74), "РЕДО", font=_font(cfg.FONT_HEAD, 30), fill=cfg.LIME)

    # тег
    if tag:
        tw = d.textlength(tag.upper(), font=_font(cfg.FONT_MONO, 26))
        d.rounded_rectangle([70, 132, 70 + tw + 40, 186], radius=28,
                            fill=cfg.LIME)
        d.text((90, 144), tag.upper(), font=_font(cfg.FONT_MONO, 26), fill=cfg.BLACK)

    # заголовок
    head = _font(cfg.FONT_HEAD, 92)
    lines = _wrap(title, head, SIZE - 140, d)[:4]
    y = 240
    for line in lines:
        d.text((70, y), line, font=head, fill=cfg.WHITE)
        y += 104

    # подзаголовок
    if subtitle:
        d.rectangle([70, y + 26, 170, y + 38], fill=cfg.LIME)
        body = _font(cfg.FONT_BODY, 40)
        for line in _wrap(subtitle, body, SIZE - 140, d)[:3]:
            d.text((70, y + 66), line, font=body, fill=(190, 195, 220))
            y += 56

    # номер выпуска
    if index:
        d.text((70, SIZE - 330), index, font=_font(cfg.FONT_HEAD, 120), fill=(26, 26, 33))

    # футер
    d.line([(70, SIZE - 120), (SIZE - 70, SIZE - 120)], fill=(30, 30, 38), width=2)
    d.text((70, SIZE - 96), "nft без хайпа", font=_font(cfg.FONT_MONO, 24), fill=cfg.GRAY)
    link_w = d.textlength(cfg.LINK, font=_font(cfg.FONT_MONO, 24))
    d.text((SIZE - 70 - link_w, SIZE - 96), cfg.LINK, font=_font(cfg.FONT_MONO, 24),
           fill=cfg.GRAY)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=93)
    return out.getvalue()


def save_preview(tag: str, title: str, subtitle: str, index: str, name: str) -> Path:
    path = cfg.OUT / name
    path.write_bytes(render(tag, title, subtitle, index))
    return path

