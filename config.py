"""Настройки автопостера РЕДО."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
QUEUE = DATA / "queue.json"
STATE = DATA / "state.json"
OUT = DATA / "out"
OUT.mkdir(exist_ok=True)


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    text = env.read_text(encoding="utf-8-sig")   # utf-8-sig снимает BOM
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().strip('"').strip("'")
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_env()

VERSION = "1.0"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@redo_nft")
POST_TIMES = [t.strip() for t in os.environ.get("POST_TIMES", "10:00").split(",") if t.strip()]
MARKET_TIMES = [t.strip() for t in os.environ.get("MARKET_TIMES", "21:00").split(",") if t.strip()]
NEWS_TIMES = [t.strip() for t in os.environ.get("NEWS_TIMES", "13:00,19:00").split(",") if t.strip()]

# расписание вида "10:00=queue,11:00=gifts,13:00=nft,16:00=telegram,19:00=durov,21:00=gram"
SLOTS = [s.strip() for s in os.environ.get(
    "SLOTS", "10:00=queue,11:00=gifts,13:00=nft,16:00=telegram,19:00=durov,21:00=gram"
).split(",") if s.strip()]
TIMEZONE_OFFSET = int(os.environ.get("TZ_OFFSET", "3"))   # Москва = UTC+3
LINK = os.environ.get("CHANNEL_LINK", "t.me/redo_nft")

# бренд
BLACK = (11, 11, 15)
LIME = (200, 255, 61)
WHITE = (242, 242, 242)
GRAY = (107, 107, 122)


def _pick_font(*candidates: str) -> str:
    """Первый существующий шрифт: работает и на Windows, и на Linux-хосте."""
    for path in candidates:
        if path and Path(path).exists():
            return path
    return ""


def _matplotlib_font(name: str) -> str:
    """Шрифты из пакета matplotlib — страховка, если в системе нет DejaVu."""
    try:
        import matplotlib

        path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name
        return str(path) if path.exists() else ""
    except Exception:
        return ""


_LOCAL_FONTS = ROOT / "fonts"

FONT_HEAD = _pick_font(
    str(_LOCAL_FONTS / "DejaVuSans-Bold.ttf"),
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    _matplotlib_font("DejaVuSans-Bold.ttf"),
)
FONT_BODY = _pick_font(
    str(_LOCAL_FONTS / "DejaVuSans.ttf"),
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    _matplotlib_font("DejaVuSans.ttf"),
)
FONT_MONO = _pick_font(
    str(_LOCAL_FONTS / "DejaVuSansMono.ttf"),
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    _matplotlib_font("DejaVuSansMono.ttf"),
)

FEEDS = [
    "https://forklog.com/feed",
]
