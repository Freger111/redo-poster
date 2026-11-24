"""Дайджест из RSS: заголовки + ссылки на источники."""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET

import config as cfg


def fetch_items(limit: int = 5) -> list[dict]:
    items: list[dict] = []
    for feed in cfg.FEEDS:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                root = ET.fromstring(resp.read())
        except Exception:
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            title = re.sub(r"<[^>]+>", "", title)
            items.append({"title": title, "link": link, "source": feed})
            if len(items) >= limit:
                return items
    return items


def build_text(items: list[dict]) -> str:
    lines = ["Главное за сутки — коротко:", ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(item["link"])
        lines.append("")
    lines.append("Полные тексты — по ссылкам, без пересказа и без советов «покупать».")
    return "\n".join(lines)
