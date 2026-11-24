"""Розыгрыши NFT-подарков: пост с кнопкой, сбор участников, итоги."""
from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import asdict, dataclass, field

import config as cfg
import poster

FILE = cfg.DATA / "giveaways.json"


@dataclass
class Giveaway:
    id: int
    prize: str
    hours: int
    started: float
    message_id: int = 0
    finished: bool = False
    participants: list = field(default_factory=list)   # [{"id":..,"name":..}]


def load() -> list[Giveaway]:
    if not FILE.exists():
        return []
    try:
        return [Giveaway(**item) for item in json.loads(FILE.read_text(encoding="utf-8"))]
    except Exception:
        return []


def save(items: list[Giveaway]) -> None:
    FILE.write_text(json.dumps([asdict(g) for g in items], ensure_ascii=False, indent=1),
                    encoding="utf-8")


def start(tg: poster.Telegram, prize: str, hours: int = 24) -> Giveaway:
    items = load()
    gw = Giveaway(id=max([g.id for g in items], default=0) + 1, prize=prize, hours=hours,
                  started=time.time())
    text = (f"🎁 <b>Розыгрыш: {prize}</b>\n\n"
            f"Условие одно — нажать кнопку ниже.\n"
            f"Итоги через {hours} ч. Победителя выберем случайно.\n\n"
            f"#розыгрыш #nft")
    result = tg.call("sendMessage", chat_id=cfg.CHANNEL, text=text, parse_mode="HTML",
                     reply_markup={"inline_keyboard": [[
                         {"text": "🎉 Участвую", "callback_data": f"gw:{gw.id}"}]]})
    if not result.get("ok"):
        raise RuntimeError(result)
    gw.message_id = result["result"]["message_id"]
    items.append(gw)
    save(items)
    return gw


def join(gw_id: int, user: dict) -> str:
    items = load()
    for gw in items:
        if gw.id != gw_id or gw.finished:
            continue
        uid = user.get("id")
        if any(p["id"] == uid for p in gw.participants):
            save(items)
            return "already"
        gw.participants.append({"id": uid,
                                "name": user.get("username") or user.get("first_name") or "аноним"})
        save(items)
        return "ok"
    return "closed"


def finish(tg: poster.Telegram, gw_id: int) -> str:
    items = load()
    for gw in items:
        if gw.id != gw_id:
            continue
        if gw.finished:
            return "уже завершён"
        gw.finished = True
        if not gw.participants:
            save(items)
            tg.call("sendMessage", chat_id=cfg.CHANNEL,
                    text=f"🎁 <b>{gw.prize}</b>\n\nЖелающих не нашлось — розыгрыш отменён.",
                    parse_mode="HTML")
            return "участников не было"
        winner = random.choice(gw.participants)
        save(items)
        tg.call("sendMessage", chat_id=cfg.CHANNEL,
                text=(f"🏁 <b>Розыгрыш {gw.prize} завершён</b>\n\n"
                      f"🏆 Победитель: @{winner['name']}\n"
                      f"👥 Участников: {len(gw.participants)}"),
                parse_mode="HTML")
        return f"победитель @{winner['name']}, участников {len(gw.participants)}"
    return "не найден"


def poll_forever(tg: poster.Telegram) -> None:
    """Слушает нажатия кнопки «Участвую» и отвечает на них."""
    offset = 0
    while True:
        try:
            result = tg.call("getUpdates", offset=offset, timeout=25,
                             allowed_updates=["callback_query"])
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                query = update.get("callback_query")
                if not query:
                    continue
                data = query.get("data") or ""
                if not data.startswith("gw:"):
                    continue
                gw_id = int(data.split(":")[1])
                status = join(gw_id, query.get("from") or {})
                answer = {"ok": "Вы в списке ✅", "already": "Вы уже участвуете",
                          "closed": "Розыгрыш уже завершён"}.get(status, "Ошибка")
                tg.call("answerCallbackQuery", callback_query_id=query["id"], text=answer)
        except Exception as exc:
            print("розыгрыш: ошибка опроса —", exc)
            time.sleep(5)
        time.sleep(1)


def start_polling(tg: poster.Telegram) -> threading.Thread:
    thread = threading.Thread(target=poll_forever, args=(tg,), daemon=True)
    thread.start()
    return thread


def auto_finish(tg: poster.Telegram) -> list[str]:
    """Завершает розыгрыши, у которых вышло время."""
    done = []
    for gw in load():
        if gw.finished:
            continue
        if time.time() - gw.started >= gw.hours * 3600:
            done.append(f"#{gw.id} {gw.prize}: " + finish(tg, gw.id))
    return done
