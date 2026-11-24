"""Пост про подарки: только настоящие картинки коллекций, без нашей графики."""
from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

import config as cfg
import gram as gram_mod

COLLECTIONS = [
    "Durov's Caps",
    "Plush Pepe",
    "Resistance Dog",
    "Heart Locket",
    "Diamond Rings",
    "Swiss Watch",
    "Mood Pack",
]
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode())


def _download(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read()
        return data if len(data) > 3000 else None
    except Exception:
        return None


def fetch_collections(limit: int = 4) -> list[dict]:
    import time

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
        time.sleep(0.3)
        if len(found) >= limit:
            break
    return found


def build(limit: int = 4) -> dict | None:
    """Возвращает настоящую картинку коллекции и текст поста."""
    coin = gram_mod.fetch()
    if not coin:
        return None
    collections = fetch_collections(limit)
    if not collections:
        return None
    main = collections[0]
    image = _download(main["image"])
    if image is None:
        for candidate in collections[1:]:
            image = _download(candidate["image"])
            if image is not None:
                main = candidate
                break
    if image is None:
        return None

    names = ", ".join(item["name"] for item in collections)
    change = coin["change_24h"]
    emoji = "🔥" if change >= 2 else ("🩸" if change <= -2 else "🐸")
    text = (f"{emoji} <b>GRAM ${coin['price']:.2f} ({change:+.2f}%)</b>\n\n"
            f"Подарки в Телеграме: {names}.\n"
            f"За неделю GRAM {coin['change_7d']:+.1f}%.\n\n"
            f"#подарки #gram #nft")
    return {"image": image, "text": text, "collections": collections, "coin": coin}
