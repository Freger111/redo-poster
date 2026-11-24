"""Публикация в Telegram-канал."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
import uuid

import config as cfg


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----redo" + uuid.uuid4().hex
    parts: list[bytes] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f"\r\n\r\n{value}\r\n".encode("utf-8"))
    for key, (filename, data, mime) in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; '
                     f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8"))
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class Telegram:
    def __init__(self, token: str, transport=None):
        self.token = token
        self.transport = transport
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, files: dict | None = None, **params) -> dict:
        if self.transport is not None:
            return self.transport(method, params, files)
        url = f"{self.base}/{method}"
        params = {k: v for k, v in params.items() if v is not None}
        last: Exception | None = None
        for attempt in range(3):
            try:
                if files:
                    body, ctype = _multipart(params, files)
                    req = urllib.request.Request(url, data=body,
                                                 headers={"Content-Type": ctype})
                else:
                    req = urllib.request.Request(
                        url, data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, ssl.SSLError, TimeoutError, ConnectionError) as exc:
                last = exc
                time.sleep(1 + attempt)
        raise last if last else RuntimeError("telegram call failed")


def publish(tg: Telegram, post, image: bytes) -> dict:
    caption = f"<b>{post.title}</b>\n\n{post.text}\n\n#nft #редо" if post.text \
        else f"<b>{post.title}</b>\n\n#nft #редо"
    result = tg.call("sendPhoto", files={"photo": ("post.jpg", image, "image/jpeg")},
                     chat_id=cfg.CHANNEL, caption=caption[:1000], parse_mode="HTML")
    return result
