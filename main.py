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
import market as market_mod  # noqa: E402
import news as news_mod  # noqa: E402
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


def cmd_market(publish: bool = True) -> int:
    coins = market_mod.fetch(24)
    if not coins:
        print("не удалось получить данные рынка")
        return 1
    image = market_mod.render(coins, index="РЫНОК 24Ч")
    path = cfg.OUT / "market.jpg"
    path.write_bytes(image)
    if not publish:
        print("картинка:", path)
        print(market_mod.caption(coins)[:300])
        return 0
    post = queue_mod.Post(0, "РЫНОК", market_mod.headline(coins[1]['change'])[0],
                          market_mod.caption(coins))
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendPhoto", files={"photo": ("market.jpg", image, "image/jpeg")},
                     chat_id=cfg.CHANNEL, caption=post.text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    print("рыночный пост опубликован")
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


def cmd_news(publish: bool = True) -> int:
    item = news_mod.pick()
    if item is None:
        print("свежих новостей нет")
        return 1
    text = news_mod.caption(item)
    path = news_mod.download_image(item["image"]) if item["image"] else None
    if not publish:
        print("источник:", item["source"])
        print("картинка:", path if path else "нет")
        print(text)
        return 0

    tg = poster.Telegram(cfg.BOT_TOKEN)
    if path:
        result = tg.call("sendPhoto", files={"photo": ("news.jpg", path.read_bytes(), "image/jpeg")},
                         chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    else:
        result = tg.call("sendMessage", chat_id=cfg.CHANNEL, text=text[:4000], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    seen = news_mod.load_seen()
    seen.add(item["link"])
    news_mod.save_seen(seen)
    print("новость опубликована:", item["title"][:60])
    return 0


def cmd_loop() -> int:
    print(f"Автопостер запущен. Канал: {cfg.CHANNEL}")
    print(f"  новости: {', '.join(cfg.NEWS_TIMES) or '—'}")
    print(f"  очередь: {', '.join(cfg.POST_TIMES) or '—'}")
    print(f"  рынок:   {', '.join(cfg.MARKET_TIMES) or '—'}")
    import time

    def slot_due(slots: list[str], key: str, state: dict, current) -> str | None:
        for slot in slots:
            hour, minute = [int(x) for x in slot.split(":")]
            fire_at = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
            slot_key = f"{current:%Y-%m-%d} {slot}"
            if current >= fire_at and state.get(key) != slot_key:
                return slot_key
        return None

    while True:
        try:
            current = now_local()
            state = queue_mod.load_state()

            news_slot = slot_due(cfg.NEWS_TIMES, "last_news_slot", state, current)
            if news_slot and cmd_news(True) == 0:
                state = queue_mod.load_state()
                state["last_news_slot"] = news_slot
                queue_mod.save_state(state)
                print(f"новостной слот {news_slot} отработан")
                time.sleep(60)
                continue

            market_slot = slot_due(cfg.MARKET_TIMES, "last_market_slot", state, current)
            if market_slot and cmd_market(True) == 0:
                state = queue_mod.load_state()
                state["last_market_slot"] = market_slot
                queue_mod.save_state(state)
                print(f"рыночный слот {market_slot} отработан")
                time.sleep(60)
                continue

            post_slot = slot_due(cfg.POST_TIMES, "last_slot", state, current)
            if post_slot:
                posts = queue_mod.load()
                if queue_mod.next_post(posts) is None:
                    print("очередь пуста — жду новых постов")
                elif cmd_post_now() == 0:
                    state = queue_mod.load_state()
                    state["last_slot"] = post_slot
                    queue_mod.save_state(state)
                    print(f"слот {post_slot} отработан")
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
    parser.add_argument("--market", action="store_true", help="опубликовать рыночный пост")
    parser.add_argument("--market-preview", action="store_true", help="только собрать картинку")
    parser.add_argument("--news", action="store_true", help="опубликовать новость с сайта")
    parser.add_argument("--news-preview", action="store_true", help="показать новость без публикации")
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
    if args.market_preview:
        return cmd_market(publish=False)
    if args.market:
        return cmd_market(publish=True)
    if args.news_preview:
        return cmd_news(publish=False)
    if args.news:
        return cmd_news(publish=True)
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


