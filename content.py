"""Очередь постов и состояние автопостера."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import config as cfg


@dataclass
class Post:
    id: int
    tag: str
    title: str
    text: str
    posted: bool = False


DEFAULT_QUEUE = [
    Post(1, "ДРОП", "Что минтить на этой неделе",
         "Разбираем 5 дропов: цена минта, размер коллекции, риски.\n\n"
         "Главное правило — смотреть на утилити и команду, а не на картинку."),
    Post(2, "РАЗБОР", "Утилити против хайпа",
         "Как отличить проект с реальной пользой от красивой обёртки:\n"
         "1. Есть ли продукт до минта\n2. Кто инвесторы\n3. Что с ликвидностью\n"
         "4. Планы на год, а не на неделю"),
    Post(3, "АНТИСКАМ", "7 красных флагов",
         "Анонимная команда без истории · обещания «х10» · закрытый Discord "
         "только для «своих» · минт за час до дедлайна · нет контракта на проверку."),
    Post(4, "ГАЙД", "Как проверить контракт",
         "1. Откройте контракт в explorer\n2. Проверьте, есть ли функция mint-паузы\n"
         "3. Посмотрите, может ли владелец менять метаданные\n"
         "4. Проверьте, не заблокированы ли переводы"),
    Post(5, "ЦИФРЫ", "Рынок за неделю",
         "Смотрим объёмы, миграции и средний чек. Без прогнозов и «луны»."),
]


def load() -> list[Post]:
    if not cfg.QUEUE.exists():
        save(DEFAULT_QUEUE)
        return list(DEFAULT_QUEUE)
    try:
        data = json.loads(cfg.QUEUE.read_text(encoding="utf-8"))
        return [Post(**item) for item in data]
    except Exception:
        return list(DEFAULT_QUEUE)


def save(posts: list[Post]) -> None:
    cfg.QUEUE.write_text(json.dumps([asdict(p) for p in posts], ensure_ascii=False, indent=1),
                         encoding="utf-8")


def next_post(posts: list[Post]) -> Post | None:
    for post in posts:
        if not post.posted:
            return post
    return None


def mark_posted(posts: list[Post], post_id: int) -> None:
    for post in posts:
        if post.id == post_id:
            post.posted = True
    save(posts)


def load_state() -> dict:
    if not cfg.STATE.exists():
        return {"last_post_date": "", "posted_total": 0}
    try:
        return json.loads(cfg.STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_post_date": "", "posted_total": 0}


def save_state(state: dict) -> None:
    cfg.STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def add_post(tag: str, title: str, text: str = "") -> Post:
    posts = load()
    new_id = max([p.id for p in posts], default=0) + 1
    post = Post(new_id, tag, title, text)
    posts.append(post)
    save(posts)
    return post
