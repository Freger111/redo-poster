"""Темы канала: NFT, GRAM, Telegram, Дуров."""
from __future__ import annotations

TOPICS = {
    "nft": {
        "title": "NFT",
        "keywords": ["nft", "нфт", "коллекц", "минт", "дроп", "opensea", "blur",
                     "magic eden", "токенизир", "цифровое искусство"],
        "queries": ["NFT коллекция", "NFT рынок", "NFT продажи"],
        "feeds": ["https://cointelegraph.com/rss/tag/nft"],
    },
    "gram": {
        "title": "GRAM",
        "keywords": ["gram", "toncoin", "ton ", "грам", "тонев", " ton"],
        "queries": ["GRAM Toncoin", "Toncoin курс"],
        "feeds": [],
    },
    "telegram": {
        "title": "Telegram",
        "keywords": ["telegram", "телеграм", "телеграмм", "мини-апп", "miniapp",
                     "tma", "звёзд", "stars", "папки", "премиум"],
        "queries": ["Telegram новости", "Telegram крипто", "Telegram мини-приложения"],
        "feeds": [],
    },
    "pepe": {
        "title": "PEPE",
        "keywords": ["pepe", "пепе", "лягушк", "frog", "жаба", "rare pepe", "pepe nft"],
        "queries": ["Pepe NFT", "Rare Pepe", "Пепе NFT", "NFT лягушка",
                    "самый дорогой NFT", "NFT редкость"],
        "feeds": [],
    },
    "durov": {
        "title": "Дуров",
        "keywords": ["дуров", "durov", "павел", "павла"],
        "queries": ["Дуров", "Павел Дуров Telegram"],
        "feeds": [],
    },
}

ORDER = ["nft", "pepe", "gram", "telegram", "durov"]


def detect(text: str) -> str | None:
    """Определяет тему по тексту (заголовок + лид)."""
    low = text.lower()
    best, best_score = None, 0
    for key, topic in TOPICS.items():
        score = sum(1 for word in topic["keywords"] if word in low)
        if score > best_score:
            best, best_score = key, score
    return best
