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
import gifs as gifs_mod  # noqa: E402
import gram as gram_mod  # noqa: E402
import gifts as gifts_mod  # noqa: E402
import topics as topics_mod  # noqa: E402
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
    tg = poster.Telegram(cfg.BOT_TOKEN)
    if post.tag == "NOTE":
        caption = f"<b>{post.title}</b>\n\n{post.text}" if post.text else f"<b>{post.title}</b>"
        result = tg.call("sendMessage", chat_id=cfg.CHANNEL, text=caption[:4000],
                         parse_mode="HTML")
    else:
        image = render.render(post.tag, post.title, post.text.split("\n")[0][:80],
                              index=f"{post.id:02d}")
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


def cmd_gif_market(publish: bool = True) -> int:
    coins = market_mod.fetch(24)
    if not coins:
        print("нет данных рынка")
        return 1
    data = gifs_mod.heatmap(coins)
    (cfg.OUT / "heatmap.gif").write_bytes(data)
    text = market_mod.caption(coins)
    if not publish:
        print("гифка:", cfg.OUT / "heatmap.gif", f"{len(data)//1024} КБ")
        print(text)
        return 0
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendAnimation", files={"animation": ("market.gif", data, "image/gif")},
                     chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    print("гифка рынка опубликована")
    return 0


def cmd_gif_news(publish: bool = True) -> int:
    item = news_mod.pick()
    if item is None:
        print("свежих новостей нет")
        return 1
    path = news_mod.download_image(item["image"]) if item["image"] else None
    if path is None:
        print("у новости нет картинки")
        return 1
    text = news_mod.caption(item)
    title = text.split("\n")[0]
    data = gifs_mod.news_zoom(path, title)
    (cfg.OUT / "news.gif").write_bytes(data)
    if not publish:
        print("гифка:", cfg.OUT / "news.gif", f"{len(data)//1024} КБ")
        print(text)
        return 0
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendAnimation", files={"animation": ("news.gif", data, "image/gif")},
                     chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    seen = news_mod.load_seen()
    seen.add(item["link"])
    news_mod.save_seen(seen)
    print("гифка-новость опубликована:", item["title"][:60])
    return 0


def cmd_gram(publish: bool = True) -> int:
    coin = gram_mod.fetch()
    if not coin:
        print("нет данных GRAM")
        return 1
    data = gram_mod.render(coin)
    path = cfg.OUT / "gram.jpg"
    path.write_bytes(data)
    text = gram_mod.caption(coin)
    if not publish:
        print("картинка:", path)
        print(text)
        return 0
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendPhoto", files={"photo": ("gram.jpg", data, "image/jpeg")},
                     chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    print("GRAM опубликован:", f"{coin['change_24h']:+.2f}%")
    return 0


def cmd_topic(topic_key: str, publish: bool = True) -> int:
    item = news_mod.pick_topic(topic_key)
    if item is None:
        print(f"нет новостей по теме {topic_key}")
        return 1
    text = news_mod.caption(item)
    image_path = news_mod.download_image(item["image"]) if item.get("image") else None
    if image_path is None:
        print(f"[{topic_key}] нет картинки — пропускаем (пустые карточки не публикуем)")
        return 1
    if not publish:
        print("картинка:", image_path)
        print(text)
        return 0
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendPhoto", files={"photo": (image_path.name, image_path.read_bytes(),
                                                  "image/jpeg")},
                     chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    seen = news_mod.load_seen()
    seen.add(item["link"])
    news_mod.save_seen(seen)
    print(f"[{topic_key}] опубликовано:", item["title"][:60])
    return 0


def cmd_gifts(publish: bool = True) -> int:
    coin = gram_mod.fetch()
    if not coin:
        print("нет данных GRAM")
        return 1
    collections = gifts_mod.fetch_collections(4)
    if not collections:
        print("не удалось получить коллекции подарков")
        return 1
    data = gifts_mod.render(coin, collections)
    (cfg.OUT / "gifts.jpg").write_bytes(data)
    text = gifts_mod.caption(coin, collections)
    if not publish:
        print("картинка:", cfg.OUT / "gifts.jpg")
        print(text)
        return 0
    tg = poster.Telegram(cfg.BOT_TOKEN)
    result = tg.call("sendPhoto", files={"photo": ("gifts.jpg", data, "image/jpeg")},
                     chat_id=cfg.CHANNEL, caption=text[:1024], parse_mode="HTML")
    if not result.get("ok"):
        print("ошибка публикации:", result)
        return 1
    print("подарки опубликованы:", ", ".join(c["name"] for c in collections))
    return 0


def cmd_loop() -> int:
    plan: list[tuple[str, str]] = []
    for raw in cfg.SLOTS:
        if "=" not in raw:
            continue
        time_part, kind = raw.split("=", 1)
        plan.append((time_part.strip(), kind.strip()))
    print(f"Автопостер запущен. Канал: {cfg.CHANNEL}")
    for slot_time, kind in plan:
        print(f"  {slot_time} — {kind}")
    import time

    while True:
        try:
            current = now_local()
            state = queue_mod.load_state()
            for slot_time, kind in plan:
                hour, minute = [int(x) for x in slot_time.split(":")]
                fire_at = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slot_key = f"{current:%Y-%m-%d} {slot_time}"
                if current < fire_at or state.get(f"slot_{kind}_{slot_time}") == slot_key:
                    continue

                code = 1
                if kind == "queue":
                    posts = queue_mod.load()
                    if queue_mod.next_post(posts) is None:
                        print("очередь пуста — добавьте посты")
                    else:
                        code = cmd_post_now()
                elif kind == "gram":
                    code = cmd_gram(True)
                elif kind == "gifts":
                    code = cmd_gifts(True)
                elif kind == "mix":
                    # вечерний слот чередует форматы: подарки → GRAM → NFT
                    options = [cmd_gifts, cmd_gram, lambda pub=True: cmd_topic("nft", pub)]
                    picker = current.timetuple().tm_yday % len(options)
                    code = options[picker](True)
                elif kind in topics_mod.TOPICS:
                    code = cmd_topic(kind, True)

                if code == 0:
                    state = queue_mod.load_state()
                    state[f"slot_{kind}_{slot_time}"] = slot_key
                    queue_mod.save_state(state)
                    print(f"{kind} · {slot_key} отработан")
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
    parser.add_argument("--market", action="store_true", help="опубликовать рыночный пост")
    parser.add_argument("--market-preview", action="store_true", help="только собрать картинку")
    parser.add_argument("--gram", action="store_true", help="пост про GRAM")
    parser.add_argument("--gifts", action="store_true", help="подарки Telegram")
    parser.add_argument("--topic", default="", help="тема: nft, gram, telegram, durov")
    parser.add_argument("--gif-news", action="store_true", help="гифка по новости")
    parser.add_argument("--gif-market", action="store_true", help="гифка рынка")
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
    if args.topic:
        return cmd_topic(args.topic, publish=True)
    if args.gram:
        return cmd_gram(publish=True)
    if args.gifts:
        return cmd_gifts(publish=True)
    if args.gif_market:
        return cmd_gif_market(True)
    if args.gif_news:
        return cmd_gif_news(True)
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


