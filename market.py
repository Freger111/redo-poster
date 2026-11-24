"""Рыночный пост: heatmap топ-монет, график BTC, крупный заголовок."""
from __future__ import annotations

import io
import json
import urllib.request

from PIL import Image, ImageDraw, ImageFont

import config as cfg

SIZE = 1080
API = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
       "&order=market_cap_desc&per_page=30&page=1&sparkline=true"
       "&price_change_percentage=24h")
STABLE = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "BUSD"}

RED = (255, 64, 64)
GREEN = (46, 214, 118)
DARK = (11, 11, 15)


def fetch(limit: int = 24) -> list[dict]:
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode())
    result = []
    for coin in data:
        symbol = (coin.get("symbol") or "").upper()
        if symbol in STABLE:
            continue
        result.append({
            "symbol": symbol,
            "name": coin.get("name", symbol),
            "price": coin.get("current_price") or 0,
            "change": coin.get("price_change_percentage_24h") or 0,
            "spark": (coin.get("sparkline_in_7d") or {}).get("price") or [],
        })
        if len(result) >= limit:
            break
    return result


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


def _fmt_price(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}".replace(",", " ")
    if value >= 1:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:.4f}"


def headline(btc_change: float) -> tuple[str, str]:
    if btc_change <= -5:
        return "РЫНОК ГОРИТ", "красная волна по всему топу"
    if btc_change <= -2:
        return "КРАСНОЕ УТРО", "биток тянет всех вниз"
    if btc_change >= 4:
        return "ЗЕЛЁНАЯ НЕДЕЛЯ", "топ уходит в плюс"
    if btc_change >= 1:
        return "ОТСКОК", "покупатели вернулись"
    return "БОКОВИК", "рынок выбирает направление"


def render(coins: list[dict], index: str = "") -> bytes:
    img = Image.new("RGB", (SIZE, SIZE), DARK)
    d = ImageDraw.Draw(img)

    btc = next((c for c in coins if c["symbol"] == "BTC"), coins[0])
    change = btc["change"]
    accent = GREEN if change >= 0 else RED

    # верхняя полоса
    d.rectangle([0, 0, SIZE, 16], fill=accent)
    d.text((60, 54), "РЕДО · РЫНОК", font=_font(cfg.FONT_MONO, 26), fill=cfg.GRAY)

    # цена BTC
    d.text((60, 92), f"BTC ${_fmt_price(btc['price'])}", font=_font(cfg.FONT_HEAD, 74),
           fill=cfg.WHITE)
    badge = f"{change:+.2f}%"
    bw = d.textlength(badge, font=_font(cfg.FONT_HEAD, 34))
    d.rounded_rectangle([60, 186, 60 + bw + 36, 236], radius=14, fill=accent)
    d.text((78, 194), badge, font=_font(cfg.FONT_HEAD, 34), fill=DARK)

    # спарклайн BTC
    spark = btc["spark"][-168:]
    if spark:
        left, top, width, height = 60, 260, SIZE - 120, 130
        lo, hi = min(spark), max(spark)
        span = (hi - lo) or 1
        points = [(left + i * width / (len(spark) - 1),
                   top + height - (v - lo) / span * height) for i, v in enumerate(spark)]
        d.line(points, fill=accent, width=4, joint="curve")
        d.line([(left, top + height), (left + width, top + height)], fill=(30, 30, 38), width=2)

    # heatmap
    cols, rows = 6, 4
    grid_top = 420
    gap = 8
    tile_w = (SIZE - 120 - gap * (cols - 1)) // cols
    tile_h = 92
    for i, coin in enumerate(coins[: cols * rows]):
        r, c = divmod(i, cols)
        x = 60 + c * (tile_w + gap)
        y = grid_top + r * (tile_h + gap)
        d.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=12,
                            fill=_tile_color(coin["change"]))
        d.text((x + 14, y + 12), coin["symbol"][:6], font=_font(cfg.FONT_HEAD, 24),
               fill=(255, 255, 255))
        sign = "+" if coin["change"] >= 0 else ""
        d.text((x + 14, y + 48), f"{sign}{coin['change']:.1f}%",
               font=_font(cfg.FONT_MONO, 22), fill=(255, 255, 255))

    # заголовок
    title, subtitle = headline(change)
    d.text((60, 830), title, font=_font(cfg.FONT_HEAD, 96), fill=cfg.WHITE)
    d.text((64, 946), subtitle, font=_font(cfg.FONT_MONO, 28), fill=accent)

    # футер
    if index:
        d.text((60, 1006), index, font=_font(cfg.FONT_MONO, 22), fill=cfg.GRAY)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def caption(coins: list[dict]) -> str:
    btc = next((c for c in coins if c["symbol"] == "BTC"), coins[0])
    change = btc["change"]
    title, _ = headline(change)
    losers = sorted(coins, key=lambda c: c["change"])[:3]
    winners = sorted(coins, key=lambda c: c["change"], reverse=True)[:3]
    emoji = "🩸" if change < -2 else ("🔥" if change > 2 else "😐")
    lines = [f"{emoji} <b>{title}</b>", "",
             f"BTC ${_fmt_price(btc['price'])} ({change:+.2f}% за сутки)", ""]
    if change < 0:
        lines.append("Сильнее всех льют:")
    else:
        lines.append("Лучше всех растут:")
    for coin in (losers if change < 0 else winners):
        lines.append(f"· {coin['symbol']} {coin['change']:+.1f}%")
    lines += ["", "#nft #рынок #crypto"]
    return "\n".join(lines)
