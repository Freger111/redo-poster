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


def render(tag: str, title: str, subtitle: str = "", index: str = "",
           invert: bool = False) -> bytes:
    """Обложка поста 1080×1080. invert=True — лаймовый фон (для PEPE)."""
    bg = cfg.LIME if invert else cfg.BLACK
    fg = cfg.BLACK if invert else cfg.WHITE
    dim = (186, 238, 52) if invert else (16, 16, 21)
    accent = cfg.BLACK if invert else cfg.LIME

    img = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(img)

    # сетка
    for x in range(0, SIZE, 40):
        d.line([(x, 0), (x, SIZE)], fill=dim)
    for y in range(0, SIZE, 40):
        d.line([(0, y), (SIZE, y)], fill=dim)

    # верхняя полоса и бренд
    d.rectangle([0, 0, SIZE, 14], fill=accent)
    d.text((70, 74), "РЕДО", font=_font(cfg.FONT_HEAD, 30), fill=accent)

    # тег
    if tag:
        tw = d.textlength(tag.upper(), font=_font(cfg.FONT_MONO, 26))
        d.rounded_rectangle([70, 132, 70 + tw + 40, 186], radius=28, fill=accent)
        d.text((90, 144), tag.upper(), font=_font(cfg.FONT_MONO, 26), fill=bg)

    # заголовок: размер подбирается под длину, чтобы не обрезать
    length = len(title)
    head_size = 92 if length <= 45 else (76 if length <= 70 else (60 if length <= 100 else 48))
    line_step = int(head_size * 1.13)
    head = _font(cfg.FONT_HEAD, head_size)
    lines = _wrap(title, head, SIZE - 140, d)[:6]
    y = 240
    for line in lines:
        d.text((70, y), line, font=head, fill=fg)
        y += line_step

    # подзаголовок
    if subtitle:
        d.rectangle([70, y + 26, 170, y + 38], fill=accent)
        body = _font(cfg.FONT_BODY, 40)
        sub_color = (40, 44, 24) if invert else (190, 195, 220)
        for line in _wrap(subtitle, body, SIZE - 140, d)[:3]:
            d.text((70, y + 66), line, font=body, fill=sub_color)
            y += 56

    # номер выпуска
    if index:
        idx_color = (170, 205, 40) if invert else (26, 26, 33)
        d.text((70, SIZE - 330), index, font=_font(cfg.FONT_HEAD, 120), fill=idx_color)

    # футер
    line_color = (150, 180, 40) if invert else (30, 30, 38)
    foot_color = (70, 78, 30) if invert else cfg.GRAY
    d.line([(70, SIZE - 120), (SIZE - 70, SIZE - 120)], fill=line_color, width=2)
    d.text((70, SIZE - 96), "nft · gram · telegram", font=_font(cfg.FONT_MONO, 24),
           fill=foot_color)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=93)
    return out.getvalue()


def save_preview(tag: str, title: str, subtitle: str, index: str, name: str) -> Path:
    path = cfg.OUT / name
    path.write_bytes(render(tag, title, subtitle, index))
    return path

