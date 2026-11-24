"""NFT-подарки Telegram: коллекции с картинками + цена GRAM."""
from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

import config as cfg
import gram as gram_mod

COLLECTIONS = [
    "Durov's Caps",
    "Plush Pepe",
    "Resistance Dog",
    "Heart Locket",
    "Diamond Rings",
    "Swiss Watch",
]
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode())


def _download(url: str) -> Image.Image | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def fetch_collections(limit: int = 4) -> list[dict]:
    found: list[dict] = []
    for name in COLLECTIONS:
        try:
            search = _get_json("https://tonapi.io/v2/accounts/search?name="
                               + urllib.parse.quote(name))
        except Exception:
            continue
        for item in search.get("addresses", []):
            if item.get("is_scam"):
                continue
            address = item.get("address")
            if not address:
                continue
            try:
                info = _get_json("https://tonapi.io/v2/nfts/collections/"
                                 + urllib.parse.quote(address))
            except Exception:
                continue
            meta = info.get("metadata") or {}
            title = meta.get("name") or item.get("name") or name
            image = meta.get("image") or ""
            if not image:
                continue
            found.append({"name": title, "image": image, "address": address})
            break
        if len(found) >= limit:
            break
    return found


def _font(path: str, size: int):
    from PIL import ImageFont

    for candidate in (path, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "C:/Windows/Fonts/arialbd.ttf"):
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _round(img: Image.Image, radius: int = 24) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def render(coin: dict, collections: list[dict]) -> bytes:
    size = 1080
    img = Image.new("RGB", (size, size), (11, 11, 15))
    d = ImageDraw.Draw(img)
    change = coin["change_24h"]
    accent = (46, 214, 118) if change >= 0 else (255, 64, 64)

    for x in range(0, size, 40):
        d.line([(x, 0), (x, size)], fill=(16, 16, 21))
    for y in range(0, size, 40):
        d.line([(0, y), (size, y)], fill=(16, 16, 21))

    d.rectangle([0, 0, size, 14], fill=accent)
    d.text((60, 60), "РЕДО · ПОДАРКИ TELEGRAM", font=_font(cfg.FONT_MONO, 24), fill=cfg.GRAY)
    d.text((60, 96), f"GRAM ${coin['price']:.2f}", font=_font(cfg.FONT_HEAD, 76), fill=cfg.WHITE)
    badge = f"{change:+.2f}%"
    bw = d.textlength(badge, font=_font(cfg.FONT_HEAD, 30))
    d.rounded_rectangle([60, 192, 60 + bw + 34, 240], radius=14, fill=accent)
    d.text((76, 200), badge, font=_font(cfg.FONT_HEAD, 30), fill=(11, 11, 15))

    # список коллекций — строками, как в приложении
    row_h = 106
    top = 300
    for i, item in enumerate(collections[:5]):
        y = top + i * (row_h + 10)
        d.rounded_rectangle([60, y, size - 60, y + row_h], radius=18,
                            fill=(20, 20, 28), outline=(38, 38, 50), width=2)
        art = _download(item["image"])
        if art is not None:
            art.thumbnail((row_h - 22, row_h - 22), Image.LANCZOS)
            art = _round(art, 12)
            img.paste(art, (78, y + (row_h - art.height) // 2), art)
        name = item["name"]
        if len(name) > 26:
            name = name[:25] + "…"
        d.text((78 + row_h - 14, y + 24), name, font=_font(cfg.FONT_HEAD, 34), fill=cfg.WHITE)
        d.text((78 + row_h - 14, y + 66), "подарок Telegram", font=_font(cfg.FONT_MONO, 20),
               fill=cfg.GRAY)

    d.text((60, 800), "ПОДАРКИ TELEGRAM", font=_font(cfg.FONT_HEAD, 62), fill=cfg.WHITE)
    d.text((64, 878), "коллекции, редкость и полы — в приложении", font=_font(cfg.FONT_MONO, 22),
           fill=accent)

    d.text((60, size - 96), "nft · gram · telegram", font=_font(cfg.FONT_MONO, 22),
           fill=cfg.GRAY)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def caption(coin: dict, collections: list[dict]) -> str:
    change = coin["change_24h"]
    emoji = "🔥" if change >= 2 else ("🩸" if change <= -2 else "🐸")
    names = ", ".join(item["name"] for item in collections)
    return (f"{emoji} <b>GRAM ${coin['price']:.2f} ({change:+.2f}%)</b>\n\n"
            f"Подарки Telegram: {names}.\n"
            f"За неделю GRAM {coin['change_7d']:+.1f}%.\n\n"
            f"#подарки #gram #nft")
