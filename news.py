"""Новости с сайтов: заголовок, лид, картинка и ссылка на источник.

Пост выглядит как обычный репост с сайта, а не как сгенерированный текст:
берём реальный заголовок, первый абзац и оригинальную картинку.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import config as cfg

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"}

FEEDS = [
    "https://incrypted.com/feed/",
    "https://forklog.com/feed",
    "https://cointelegraph.com/rss/tag/nft",
]

CACHE = cfg.DATA / "seen.json"


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_sentence(text: str, limit: int = 240) -> str:
    text = _clean(text)
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = parts[0]
    for part in parts[1:]:
        if len(out) + len(part) > limit:
            break
        out += " " + part
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0] + "…"
    return out


def _find_image(item: ET.Element) -> str:
    for tag in ("{http://search.yahoo.com/mrss/}content", "enclosure"):
        node = item.find(tag)
        if node is not None:
            url = node.get("url") or ""
            if url:
                return url
    return ""


def _og_image(url: str) -> str:
    try:
        page = _get(url).decode("utf-8", "replace")
    except Exception:
        return ""
    match = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)', page)
    if not match:
        match = re.search(r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', page)
    return match.group(1) if match else ""


def fetch(limit: int = 12) -> list[dict]:
    items: list[dict] = []
    for feed in FEEDS:
        try:
            root = ET.fromstring(_get(feed))
        except Exception:
            continue
        for node in root.iter("item"):
            title = _clean(node.findtext("title") or "")
            link = (node.findtext("link") or "").strip()
            if not title or not link:
                continue
            description = node.findtext("description") or ""
            items.append({
                "title": title,
                "link": link,
                "lead": _first_sentence(description),
                "image": _find_image(node),
                "source": urlparse(link).netloc.replace("www.", ""),
                "feed": feed,
            })
            if len(items) >= limit * 3:
                break
    return items


def load_seen() -> set[str]:
    if not CACHE.exists():
        return set()
    try:
        return set(json.loads(CACHE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen(links: set[str]) -> None:
    CACHE.write_text(json.dumps(sorted(links)[-300:], ensure_ascii=False), encoding="utf-8")


KEYWORDS = [
    ("nft", 5), ("нфт", 5), ("коллекц", 4), ("минт", 4), ("дроп", 3), ("mint", 4),
    ("opensea", 4), ("blur", 3), ("magic eden", 4), ("токенизир", 3),
    ("ethereum", 2), ("solana", 2), ("биткоин", 1), ("bitcoin", 1), ("блокчейн", 2),
]


RU_SOURCES = {"incrypted.com", "forklog.com"}


def score(item: dict) -> int:
    text = f"{item['title']} {item['lead']}".lower()
    points = sum(weight for word, weight in KEYWORDS if word in text)
    if item["source"] in RU_SOURCES:
        points += 3
    return points


def pick(limit_checked: int = 12) -> dict | None:
    """Самая тематичная свежая новость, которой ещё не было в канале."""
    seen = load_seen()
    candidates = [item for item in fetch(limit_checked) if item["link"] not in seen]
    if not candidates:
        return None
    candidates.sort(key=score, reverse=True)
    item = candidates[0]
    if not item["image"]:
        item["image"] = _og_image(item["link"])
    return item


def caption(item: dict) -> str:
    lines = [f"<b>{item['title']}</b>"]
    if item["lead"]:
        lines += ["", item["lead"]]
    lines += ["", f"Источник: {item['source']}", item["link"]]
    return "\n".join(lines)


def download_image(url: str, name: str = "news.jpg") -> Path | None:
    try:
        data = _get(url, timeout=25)
    except Exception:
        return None
    if len(data) < 4000:
        return None
    path = cfg.OUT / name
    path.write_bytes(data)
    return path
