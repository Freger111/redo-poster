"""Автопостер канала РЕДО.

Команды:
    python main.py --preview             собрать превью следующего поста
    python main.py --post-now            опубликовать следующий пост
    python main.py --digest              собрать и опубликовать дайджест из RSS
    python main.py --add "ДРОП|Заголовок|Текст"
    python main.py --loop                работать по расписанию
    python main.py --selftest            проверка без сети и токена
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfg  # noqa: E402
import digest as digest_mod  # noqa: E402
import poster  # noqa: E402
import content as queue_mod  # noqa: E402
import render  # noqa: E402


def now_local() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=cfg.TIMEZONE_OFFSET)


def cmd_preview() -> int:
    posts = queue_mod.load()
    post = queue_mod.next_post(posts)
    if post is None:
        print("Очередь пуста — добавьте посты через --add")
        return 1
    image = render.render(post.tag, post.title, post.text.split("\n")[0][:80],
                          index=f"{post.id:02d}")
    path = cfg.OUT / f"preview_{post.id}.jpg"
    path.write_bytes(image)
    print("превью:", path)
    print("заголовок:", post.title)
    return 0


def cmd_post_now() -> int:
    posts = queue_mod.load()
    post = queue_mod.next_post(posts)
    if post is None:
        print("Очередь пуста")
        return 1
    image = render.render(post.tag, post.title, post.text.split("\n")[0][:80],
                          index=f"{post.id:02d}")
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = poster.publish(tg, post, image)
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    queue_mod.mark_posted(posts, post.id)
    state = queue_mod.load_state()
    state["last_post_date"] = now_local().strftime("%Y-%m-%d")
    state["posted_total"] = state.get("posted_total", 0) + 1
    queue_mod.save_state(state)
    print("опубликовано:", post.title)
    return 0


def cmd_digest() -> int:
    items = digest_mod.fetch_items(5)
    if not items:
        print("не удалось получить новости")
        return 1
    text = digest_mod.build_text(items)
    image = render.render("ДАЙДЖЕСТ", "Главное за сутки", "5 ссылок без воды")
    post = queue_mod.Post(0, "ДАЙДЖЕСТ", "Главное за сутки", text)
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = poster.publish(tg, post, image)
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    print("дайджест опубликован, новостей:", len(items))
    return 0


def cmd_add(raw: str) -> int:
    parts = [p.strip() for p in raw.split("|")]
    tag = parts[0] if parts else "ПОСТ"
    title = parts[1] if len(parts) > 1 else "Без заголовка"
    text = parts[2] if len(parts) > 2 else ""
    post = queue_mod.add_post(tag, title, text)
    print(f"добавлен пост #{post.id}: {post.title}")
    return 0


def cmd_loop() -> int:
    print(f"Автопостер запущен. Канал: {cfg.CHANNEL}. Время: {', '.join(cfg.POST_TIMES)}")
    import time

    while True:
        try:
            current = now_local()
            state = queue_mod.load_state()
            today = current.strftime("%Y-%m-%d")
            for slot in cfg.POST_TIMES:
                hour, minute = [int(x) for x in slot.split(":")]
                slot_dt = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slot_key = f"{today} {slot}"
                if current >= slot_dt and state.get("last_slot") != slot_key:
                    posts = queue_mod.load()
                    if queue_mod.next_post(posts) is None:
                        print("очередь пуста — жду новых постов")
                        break
                    if cmd_post_now() == 0:
                        state = queue_mod.load_state()
                        state["last_slot"] = slot_key
                        queue_mod.save_state(state)
                        print(f"слот {slot_key} отработан")
                    break
        except Exception as exc:
            print("ошибка цикла:", exc)
        time.sleep(60)


def selftest() -> int:
    ok = True

    def check(name: str, condition: bool) -> None:
        nonlocal ok
        print(("  ✓ " if condition else "  ✗ ") + name)
        ok = ok and condition

    tmp = Path(tempfile.mkdtemp())
    cfg.QUEUE = tmp / "queue.json"
    cfg.STATE = tmp / "state.json"
    cfg.OUT = tmp

    print("1. Очередь")
    posts = queue_mod.load()
    check("очередь создана", len(posts) >= 5)
    post = queue_mod.next_post(posts)
    check("есть следующий пост", post is not None)

    print("2. Отрисовка")
    image = render.render(post.tag, post.title, "подзаголовок", "01")
    check("картинка собрана", len(image) > 5000)
    check("это JPEG", image[:2] == b"\xff\xd8")

    print("3. Публикация")
    calls = []

    def fake(method, params, files):
        calls.append((method, params, files))
        return {"ok": True, "result": {"message_id": 1}}

    tg = poster.Telegram("test", transport=fake)
    result = poster.publish(tg, post, image)
    check("sendPhoto вызван", calls and calls[0][0] == "sendPhoto")
    check("есть файл", calls[0][2] is not None)
    check("канал верный", calls[0][1]["chat_id"] == cfg.CHANNEL)
    check("ответ ok", result.get("ok") is True)

    print("4. Отметка и состояние")
    queue_mod.mark_posted(posts, post.id)
    check("пост помечен", queue_mod.load()[0].posted)
    state = queue_mod.load_state()
    state["posted_total"] = 1
    queue_mod.save_state(state)
    check("состояние сохранено", queue_mod.load_state()["posted_total"] == 1)

    print("5. Дайджест")
    sample = [{"title": "Тестовая новость", "link": "https://example.com", "source": "rss"}]
    text = digest_mod.build_text(sample)
    check("текст дайджеста собран", "Тестовая новость" in text and "example.com" in text)

    print("\nИтог:", "всё работает" if ok else "есть ошибки")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Автопостер РЕДО")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--post-now", action="store_true")
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--add", default="")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.add:
        return cmd_add(args.add)
    if args.preview:
        return cmd_preview()
    if args.digest:
        return cmd_digest()
    if args.post_now:
        return cmd_post_now()
    if args.loop:
        return cmd_loop()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


