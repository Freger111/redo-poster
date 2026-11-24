"""Новости с сайтов: заголовок, лид, картинка и ссылка на источник.

Пост выглядит как обычный репост с сайта, а не как сгенерированный текст:
берём реальный заголовок, первый абзац и оригинальную картинку.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
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


def translate(text: str, target: str = "ru") -> str:
    """Перевод через бесплатный endpoint Google; при ошибке возвращает оригинал."""
    if not text:
        return ""
    try:
        params = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": target,
                                         "dt": "t", "q": text[:1800]})
        url = "https://translate.googleapis.com/translate_a/single?" + params
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        result = "".join(part[0] for part in data[0] if part[0])
        return result.strip() or text
    except Exception:
        return text


def _needs_translation(item: dict) -> bool:
    if item["source"] in RU_SOURCES:
        return False
    text = item["title"]
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    return latin > len(text) * 0.5


GOOGLE = "https://news.google.com/rss/search?"


def fetch_google(query: str, limit: int = 15) -> list[dict]:
    """Новости по запросу через Google News RSS (заголовок, ссылка, издание)."""
    url = GOOGLE + urllib.parse.urlencode({"q": query, "hl": "ru", "gl": "RU",
                                           "ceid": "RU:ru"})
    try:
        root = ET.fromstring(_get(url, timeout=25))
    except Exception:
        return []
    result: list[dict] = []
    for node in root.iter("item"):
        raw_title = _clean(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        source_node = node.find("source")
        source = _clean(source_node.text if source_node is not None else "")
        if not raw_title or not link:
            continue
        title = raw_title
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        result.append({"title": title, "link": link, "lead": "", "image": "",
                       "source": source or "google news", "feed": "google"})
        if len(result) >= limit:
            break
    return result


def pick_topic(topic_key: str) -> dict | None:
    """Свежая новость по конкретной теме (nft, gram, telegram, durov)."""
    import topics as topics_mod

    topic = topics_mod.TOPICS.get(topic_key)
    if not topic:
        return None
    seen = load_seen()
    pool: list[dict] = []
    for feed in topic.get("feeds", []):
        try:
            pool.extend(_fetch_feed(feed, limit=20))
        except Exception:
            continue
    if not pool:
        for query in topic.get("queries", []):
            pool.extend(fetch_google(query, limit=10))

    keywords = topic["keywords"]
    scored: list[tuple[int, dict]] = []
    for item in pool:
        if item["link"] in seen:
            continue
        text = f"{item['title']} {item.get('lead', '')}".lower()
        hits = sum(1 for word in keywords if word in text)
        if hits == 0:
            continue
        image = item.get("image") or ""
        if not image:
            image = _og_image(item["link"])
        if not image:
            continue                      # без картинки не публикуем
        item["image"] = image
        scored.append((hits, item))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    item = scored[0][1]
    if not item.get("lead"):
        item["lead"] = ""
    return item


def _fetch_feed(feed: str, limit: int = 10) -> list[dict]:
    root = ET.fromstring(_get(feed))
    result: list[dict] = []
    for node in root.iter("item"):
        title = _clean(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        if not title or not link:
            continue
        result.append({"title": title, "link": link,
                       "lead": _first_sentence(node.findtext("description") or ""),
                       "image": _find_image(node),
                       "source": urlparse(link).netloc.replace("www.", ""),
                       "feed": feed})
        if len(result) >= limit:
            break
    return result


def caption(item: dict) -> str:
    title = item["title"]
    lead = item["lead"]
    if _needs_translation(item):
        title = translate(title)
        lead = translate(lead) if lead else ""
    lines = [f"<b>{title}</b>"]
    if lead:
        lines += ["", lead]
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
