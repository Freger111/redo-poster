"""GRAM (бывший TON): цена, изменение, график."""
from __future__ import annotations

import io
import json
import urllib.request

from PIL import Image, ImageDraw

import config as cfg

SIZE = 1080
RED = (255, 64, 64)
GREEN = (46, 214, 118)

API = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
       "&ids=the-open-network&sparkline=true&price_change_percentage=24h,7d")


def _font(path: str, size: int):
    for candidate in (path, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "C:/Windows/Fonts/arialbd.ttf"):
        if not candidate:
            continue
        try:
            from PIL import ImageFont

            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    from PIL import ImageFont

    return ImageFont.load_default()


def fetch() -> dict | None:
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode())
    if not data:
        return None
    coin = data[0]
    return {
        "symbol": (coin.get("symbol") or "GRAM").upper(),
        "name": coin.get("name", "Gram"),
        "price": coin.get("current_price") or 0,
        "change_24h": coin.get("price_change_percentage_24h") or 0,
        "change_7d": coin.get("price_change_percentage_7d_in_currency") or 0,
        "spark": (coin.get("sparkline_in_7d") or {}).get("price") or [],
        "high": coin.get("high_24h") or 0,
        "low": coin.get("low_24h") or 0,
    }


def _fmt(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}".replace(",", " ")
    if value >= 1:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:.4f}"


def headline(change: float) -> str:
    if change <= -7:
        return "ГРАМ В КРАСНОМ"
    if change <= -2:
        return "ГРАМ ПАДАЕТ"
    if change >= 7:
        return "ГРАМ РАСТЁТ"
    if change >= 2:
        return "ГРАМ В ПЛЮСЕ"
    return "ГРАМ БЕЗ ИЗМЕНЕНИЙ"


def render(coin: dict) -> bytes:
    img = Image.new("RGB", (SIZE, SIZE), (11, 11, 15))
    d = ImageDraw.Draw(img)
    change = coin["change_24h"]
    accent = GREEN if change >= 0 else RED

    for x in range(0, SIZE, 40):
        d.line([(x, 0), (x, SIZE)], fill=(16, 16, 21))
    for y in range(0, SIZE, 40):
        d.line([(0, y), (SIZE, y)], fill=(16, 16, 21))

    d.rectangle([0, 0, SIZE, 16], fill=accent)
    d.text((60, 70), "РЕДО · GRAM", font=_font(cfg.FONT_MONO, 26), fill=cfg.GRAY)
    d.text((60, 112), f"${_fmt(coin['price'])}", font=_font(cfg.FONT_HEAD, 120), fill=cfg.WHITE)

    badge = f"{change:+.2f}% за 24ч"
    bw = d.textlength(badge, font=_font(cfg.FONT_HEAD, 34))
    d.rounded_rectangle([60, 258, 60 + bw + 40, 316], radius=16, fill=accent)
    d.text((80, 268), badge, font=_font(cfg.FONT_HEAD, 34), fill=(11, 11, 15))

    week = f"7 дней: {coin['change_7d']:+.1f}%"
    d.text((60, 344), week, font=_font(cfg.FONT_MONO, 30), fill=cfg.GRAY)

    spark = coin["spark"][-168:]
    if spark:
        left, top, width, height = 60, 420, SIZE - 120, 320
        lo, hi = min(spark), max(spark)
        span = (hi - lo) or 1
        points = [(left + i * width / (len(spark) - 1),
                   top + height - (v - lo) / span * height) for i, v in enumerate(spark)]
        d.line(points, fill=accent, width=5, joint="curve")
        d.line([(left, top + height), (left + width, top + height)], fill=(30, 30, 38), width=2)
        d.text((left, top - 30), f"макс ${_fmt(hi)}", font=_font(cfg.FONT_MONO, 22), fill=cfg.GRAY)
        d.text((left, top + height + 12), f"мин ${_fmt(lo)}", font=_font(cfg.FONT_MONO, 22),
               fill=cfg.GRAY)

    d.text((60, 830), headline(change), font=_font(cfg.FONT_HEAD, 86), fill=cfg.WHITE)
    d.text((64, 944), "GRAM — бывший TON, экосистема Telegram", font=_font(cfg.FONT_MONO, 26),
           fill=accent)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def caption(coin: dict) -> str:
    change = coin["change_24h"]
    emoji = "🔥" if change >= 2 else ("🩸" if change <= -2 else "😐")
    return (f"{emoji} <b>{headline(change)}</b>\n\n"
            f"GRAM ${_fmt(coin['price'])} ({change:+.2f}% за сутки, "
            f"{coin['change_7d']:+.1f}% за неделю)\n\n"
            f"#gram #ton #редо")
