"""Приём постов с телефона: админ пишет боту в личку — бот предлагает опубликовать."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field

import config as cfg
import poster

FILE = cfg.DATA / "drafts.json"


@dataclass
class Draft:
    id: int
    kind: str                 # text | photo | link
    text: str = ""
    photo: str = ""           # telegram file_id
    link: str = ""
    author: int = 0
    created: float = field(default_factory=time.time)


def load() -> list[Draft]:
    if not FILE.exists():
        return []
    try:
        return [Draft(**item) for item in json.loads(FILE.read_text(encoding="utf-8"))]
    except Exception:
        return []


def save(items: list[Draft]) -> None:
    FILE.write_text(json.dumps([asdict(d) for d in items], ensure_ascii=False, indent=1),
                    encoding="utf-8")


def _next_id(items: list[Draft]) -> int:
    return max([d.id for d in items], default=0) + 1


def _preview_buttons(draft_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": f"dr:{draft_id}:pub"},
        {"text": "🕒 В очередь", "callback_data": f"dr:{draft_id}:queue"},
    ], [
        {"text": "❌ Удалить", "callback_data": f"dr:{draft_id}:del"},
    ]]}


def _fetch_title(url: str) -> tuple[str, str, str]:
    """Заголовок, картинка и описание со страницы по ссылке."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", "replace")
    except Exception:
        return "", "", ""
    title = ""
    match = re.search(r'property=["\']og:title["\']\s+content=["\']([^"\']+)', page)
    if match:
        title = html.unescape(match.group(1))
    else:
        match = re.search(r"<title>(.*?)</title>", page, re.S)
        if match:
            title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    image = ""
    match = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)', page)
    if match:
        image = match.group(1)
    desc = ""
    match = re.search(r'property=["\']og:description["\']\s+content=["\']([^"\']+)', page)
    if match:
        desc = html.unescape(match.group(1))
    return title, image, desc


def create_from_message(tg: poster.Telegram, msg: dict) -> Draft | None:
    user = (msg.get("from") or {}).get("id")
    if user not in cfg.ADMINS:
        return None

    items = load()
    draft = Draft(id=_next_id(items), author=user or 0, kind="text")

    if msg.get("photo"):
        draft.kind = "photo"
        draft.photo = msg["photo"][-1]["file_id"]
        draft.text = (msg.get("caption") or "").strip()
    elif msg.get("text"):
        text = msg["text"].strip()
        if text.startswith("/"):
            return None
        if text.startswith("http"):
            draft.kind = "link"
            draft.link = text
            title, image, desc = _fetch_title(text)
            draft.text = title or text
            if image:
                draft.photo = image
        else:
            draft.text = text
    else:
        return None

    items.append(draft)
    save(items)

    preview = draft.text[:600] or draft.link
    tg.call("sendMessage", chat_id=user, text=f"<b>Черновик #{draft.id}</b>\n\n{preview}",
            parse_mode="HTML", reply_markup=_preview_buttons(draft.id),
            disable_web_page_preview=True)
    return draft


def _send_photo_bytes(tg: poster.Telegram, draft: Draft, chat_id: int) -> dict:
    try:
        req = urllib.request.Request(draft.photo, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read()
        return tg.call("sendPhoto", files={"photo": ("photo.jpg", data, "image/jpeg")},
                       chat_id=chat_id, caption=draft.text[:1024], parse_mode="HTML")
    except Exception:
        return {}


def publish(tg: poster.Telegram, draft: Draft) -> bool:
    if draft.kind == "photo":
        if draft.photo and not draft.photo.startswith("http"):
            result = tg.call("sendPhoto", chat_id=cfg.CHANNEL, photo=draft.photo,
                             caption=draft.text[:1024] or None, parse_mode="HTML")
        else:
            result = _send_photo_bytes(tg, draft, cfg.CHANNEL) or {}
        if not result.get("ok"):
            result = tg.call("sendMessage", chat_id=cfg.CHANNEL,
                             text=draft.text or draft.link, parse_mode="HTML",
                             disable_web_page_preview=True)
        return bool(result.get("ok"))
    if draft.kind == "link":
        result = _send_photo_bytes(tg, draft, cfg.CHANNEL) or {}
        if not result.get("ok"):
            result = tg.call("sendMessage", chat_id=cfg.CHANNEL, text=draft.text or draft.link,
                             parse_mode="HTML", disable_web_page_preview=True)
        return bool(result.get("ok"))
    result = tg.call("sendMessage", chat_id=cfg.CHANNEL, text=draft.text,
                     parse_mode="HTML")
    return bool(result.get("ok"))


def to_queue(draft: Draft) -> None:
    import content

    title = draft.text.split("\n")[0][:80] or "Пост"
    body = "\n".join(draft.text.split("\n")[1:]).strip() or draft.link
    content.add_post("NOTE", title, body)


def handle_callback(tg: poster.Telegram, query: dict) -> bool:
    data = query.get("data") or ""
    if not data.startswith("dr:"):
        return False
    _, raw_id, action = data.split(":", 2)
    draft_id = int(raw_id)
    items = load()
    draft = next((d for d in items if d.id == draft_id), None)
    chat_id = (query.get("message") or {}).get("chat", {}).get("id")
    if draft is None:
        tg.call("answerCallbackQuery", callback_query_id=query["id"], text="Черновик не найден")
        return True

    if action == "pub":
        ok = publish(tg, draft)
        answer = "Опубликовано ✅" if ok else "Не удалось опубликовать"
        items = [d for d in items if d.id != draft_id]
        save(items)
    elif action == "queue":
        to_queue(draft)
        answer = "Добавлено в очередь 🕒"
        items = [d for d in items if d.id != draft_id]
        save(items)
    else:
        items = [d for d in items if d.id != draft_id]
        save(items)
        answer = "Удалено"

    tg.call("answerCallbackQuery", callback_query_id=query["id"], text=answer)
    if chat_id:
        tg.call("editMessageReplyMarkup", chat_id=chat_id,
                message_id=(query.get("message") or {}).get("message_id"),
                reply_markup={"inline_keyboard": []})
    return True
