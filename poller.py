"""Единый опрос обновлений: розыгрыши + приём постов от админа."""
from __future__ import annotations

import time

import config as cfg
import giveaway as gw_mod
import intake
import poster

HELP = (
    "📥 <b>Приём постов</b>\n\n"
    "Просто пришлите мне:\n"
    "· текст — станет постом;\n"
    "· фото с подписью — пост с картинкой;\n"
    "· ссылку — заберу заголовок и картинку со страницы.\n\n"
    "Дальше кнопки: <b>Опубликовать</b>, <b>В очередь</b> или <b>Удалить</b>.\n\n"
    "Команды: /help — эта справка, /gw — список розыгрышей."
)


def _reply(tg: poster.Telegram, chat_id: int, text: str) -> None:
    try:
        tg.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception:
        pass


def run(tg: poster.Telegram) -> None:
    offset = 0
    while True:
        try:
            result = tg.call("getUpdates", offset=offset, timeout=25,
                             allowed_updates=["message", "callback_query"])
            for update in result.get("result", []):
                offset = update["update_id"] + 1

                query = update.get("callback_query")
                if query:
                    data = query.get("data") or ""
                    if intake.handle_callback(tg, query):
                        continue
                    if data.startswith("gw:"):
                        status = gw_mod.join(int(data.split(":")[1]), query.get("from") or {})
                        answer = {"ok": "Вы в списке ✅", "already": "Вы уже участвуете",
                                  "closed": "Розыгрыш завершён"}.get(status, "Ошибка")
                        tg.call("answerCallbackQuery", callback_query_id=query["id"],
                                text=answer)
                    continue

                message = update.get("message")
                if not message:
                    continue
                user_id = (message.get("from") or {}).get("id")
                text = (message.get("text") or "").strip()
                if user_id in cfg.ADMINS and text in ("/help", "/start"):
                    _reply(tg, user_id, HELP)
                    continue
                if user_id in cfg.ADMINS and text == "/gw":
                    lines = [f"#{g.id} {g.prize} — "
                             f"{'завершён' if g.finished else f'идёт, {len(g.participants)} участн.'}"
                             for g in gw_mod.load()]
                    _reply(tg, user_id, "\n".join(lines) or "Розыгрышей нет")
                    continue
                if text.startswith("/"):
                    continue
                intake.create_from_message(tg, message)
        except Exception as exc:
            print("опрос: ошибка —", exc)
            time.sleep(5)
        time.sleep(1)


def start(tg: poster.Telegram):
    import threading

    thread = threading.Thread(target=run, args=(tg,), daemon=True)
    thread.start()
    return thread
