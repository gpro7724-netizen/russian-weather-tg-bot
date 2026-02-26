import io
import json
import logging
import os
import random
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple, Any

# Тип элемента новости: (title, link, description, pub_timestamp или None)
NewsItem = Tuple[str, str, str, Optional[float]]

import aiohttp
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from telegram import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# .env ищем рядом с bot.py
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
VK_ACCESS_TOKEN = (os.getenv("VK_ACCESS_TOKEN") or "").strip()


@dataclass
class City:
    slug: str
    name_ru: str
    name_en: str
    lat: float
    lon: float
    # Доп. ключевые слова для поиска новостей (город + регион/республика/край)
    search_keywords: tuple = ()


# Города-миллионники РФ: название, координаты и ключевые слова для новостей
RUSSIAN_MILLION_PLUS_CITIES: Dict[str, City] = {
    "moscow": City("moscow", "Москва", "Moscow", 55.7558, 37.6173, ("Московская область", "Подмосковье")),
    "spb": City("spb", "Санкт-Петербург", "Saint Petersburg", 59.9343, 30.3351, ("Ленинградская область", "Петербург")),
    "novosibirsk": City("novosibirsk", "Новосибирск", "Novosibirsk", 55.0084, 82.9357, ("Новосибирская область",)),
    "yekaterinburg": City("yekaterinburg", "Екатеринбург", "Yekaterinburg", 56.8389, 60.6057, ("Свердловская область", "Урал")),
    "nizhny_novgorod": City("nizhny_novgorod", "Нижний Новгород", "Nizhny Novgorod", 56.2965, 43.9361, ("Нижегородская область",)),
    "kazan": City("kazan", "Казань", "Kazan", 55.8304, 49.0661, ("Татарстан",)),
    "chelyabinsk": City("chelyabinsk", "Челябинск", "Chelyabinsk", 55.1644, 61.4368, ("Челябинская область",)),
    "omsk": City("omsk", "Омск", "Omsk", 54.9885, 73.3242, ("Омская область",)),
    "samara": City("samara", "Самара", "Samara", 53.1959, 50.1002, ("Самарская область", "Куйбышев")),
    "rostov_on_don": City("rostov_on_don", "Ростов-на-Дону", "Rostov-on-Don", 47.2313, 39.7233, ("Ростовская область", "Дон")),
    "ufa": City("ufa", "Уфа", "Ufa", 54.7388, 55.9721, ("Башкортостан", "Башкирия")),
    "krasnoyarsk": City("krasnoyarsk", "Красноярск", "Krasnoyarsk", 56.0153, 92.8932, ("Красноярский край",)),
    "perm": City("perm", "Пермь", "Perm", 58.0105, 56.2502, ("Пермский край",)),
    "voronezh": City("voronezh", "Воронеж", "Voronezh", 51.6720, 39.1843, ("Воронежская область",)),
    "volgograd": City("volgograd", "Волгоград", "Volgograd", 48.7080, 44.5133, ("Волгоградская область",)),
    "krasnodar": City("krasnodar", "Краснодар", "Krasnodar", 45.0353, 38.9753, ("Краснодарский край", "Кубань")),
    "saratov": City("saratov", "Саратов", "Saratov", 51.5924, 46.0342, ("Саратовская область",)),
    "tyumen": City("tyumen", "Тюмень", "Tyumen", 57.1531, 65.5343, ("Тюменская область",)),
    "tolyatti": City("tolyatti", "Тольятти", "Tolyatti", 53.5303, 49.3461, ("Самарская область", "Жигулёвск")),
    "izhevsk": City("izhevsk", "Ижевск", "Izhevsk", 56.8498, 53.2045, ("Удмуртия", "Удмуртская")),
    "barnaul": City("barnaul", "Барнаул", "Barnaul", 53.3606, 83.7546, ("Алтайский край", "Алтай")),
    "ulyanovsk": City("ulyanovsk", "Ульяновск", "Ulyanovsk", 54.3282, 48.3866, ("Ульяновская область",)),
    "irkutsk": City("irkutsk", "Иркутск", "Irkutsk", 52.2978, 104.2964, ("Иркутская область", "Байкал")),
    "khabarovsk": City("khabarovsk", "Хабаровск", "Khabarovsk", 48.4827, 135.0838, ("Хабаровский край",)),
    "vladivostok": City("vladivostok", "Владивосток", "Vladivostok", 43.1198, 131.8869, ("Приморский край", "Приморье")),
    "mahachkala": City("mahachkala", "Махачкала", "Makhachkala", 42.9849, 47.5047, ("Дагестан", "Дагестана")),
}

# Региональные RSS: у каждого города — своя лента (городские/областные новости)
CITY_RSS_FEEDS: Dict[str, List[str]] = {
    "moscow": ["https://www.mskagency.ru/rss/index.rss"],
    "spb": ["https://neva.versia.ru/rss/index.xml"],
    "novosibirsk": ["https://ngs.ru/rss/", "https://tayga.info/rss"],
    "yekaterinburg": ["https://66.ru/rss/", "https://uralpolit.ru/rss"],
    "nizhny_novgorod": ["https://nn.versia.ru/rss/index.xml"],
    "kazan": ["https://tat.versia.ru/rss/index.xml"],
    "chelyabinsk": ["https://74.ru/rss/", "https://up74.ru/rss/"],
    "omsk": ["https://om1.ru/rss/", "https://omsk.rbc.ru/rss/"],
    "samara": ["https://63.ru/rss/", "https://samara.ru/rss"],
    "rostov_on_don": ["https://161.ru/rss/", "https://rostov.ru/rss/"],
    "ufa": ["https://rb.versia.ru/rss/index.xml"],
    "krasnoyarsk": ["https://ngs24.ru/rss/"],
    "perm": ["https://59.ru/rss/"],
    "voronezh": ["https://voronezh.versia.ru/rss/index.xml"],
    "volgograd": ["https://v1.ru/rss/"],
    "krasnodar": ["https://kavkaz.versia.ru/rss/index.xml", "https://yugopolis.ru/rss/"],
    "saratov": ["https://www.sarbc.ru/rss/", "https://saratov.versia.ru/rss/index.xml"],
    "tyumen": ["https://72.ru/rss/"],
    "tolyatti": ["https://63.ru/rss/"],
    "izhevsk": ["https://udm-info.ru/rss/"],
    "barnaul": ["https://barnaul22.ru/rss/"],
    "ulyanovsk": ["https://73online.ru/rss/"],
    "irkutsk": ["https://irk.ru/rss/"],
    "khabarovsk": ["https://dvhab.ru/rss/"],
    "vladivostok": ["https://vl.ru/rss/"],
    "mahachkala": ["https://kavkaz.versia.ru/rss/index.xml", "https://riadagestan.ru/rss/"],
}

# Локальная карта России при приветствии (шаблон из проекта)
MAP_RUSSIA_PATH = os.path.join(_script_dir, "assets", "map_russia.png")
# Запасная карта по URL, если локального файла нет
MAP_RUSSIA_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Russia_orthographic_map.svg/600px-Russia_orthographic_map.svg.png"
# Упрощённый контур России (долгота, широта) для генерации карты
RUSSIA_OUTLINE_LONLAT = [
    (19.6, 54.4), (21.1, 55.3), (28.2, 59.9), (30.9, 69.1), (44.2, 76.0), (58.6, 76.5),
    (82.5, 77.6), (104.3, 77.0), (140.0, 75.2), (180.0, 71.5), (180.0, 66.0),
    (178.0, 62.0), (164.0, 55.0), (143.0, 50.0), (135.0, 43.0), (130.0, 42.5),
    (127.0, 40.0), (113.0, 41.0), (87.5, 41.0), (68.0, 45.0), (53.0, 41.2),
    (39.0, 47.0), (37.5, 46.0), (33.5, 45.2), (33.5, 44.4), (36.8, 44.0),
    (39.0, 43.5), (48.0, 42.0), (47.5, 41.0), (40.0, 41.0), (28.0, 41.2),
    (27.5, 45.0), (19.6, 54.4),
]
MAP_IMG_SIZE = (600, 400)
MAP_EXTENT = (19.0, 41.0, 180.0, 82.0)  # lon_min, lat_min, lon_max, lat_max

def _lonlat_to_xy(lon: float, lat: float) -> tuple:
    """Перевод (долгота, широта) в пиксели для карты России."""
    lon_min, lat_min, lon_max, lat_max = MAP_EXTENT
    w, h = MAP_IMG_SIZE
    x = (lon - lon_min) / (lon_max - lon_min) * w
    y = (lat_max - lat) / (lat_max - lat_min) * h
    return (round(x), round(y))


def _generate_russia_map_bytes() -> bytes:
    """Генерирует карту России (контур) и возвращает PNG в байтах."""
    w, h = MAP_IMG_SIZE
    img = Image.new("RGB", (w, h), (224, 238, 255))  # светло-голубой фон
    draw = ImageDraw.Draw(img)
    points = [_lonlat_to_xy(lon, lat) for lon, lat in RUSSIA_OUTLINE_LONLAT]
    draw.polygon(points, fill=(255, 250, 240), outline=(70, 100, 140), width=2)
    font = ImageFont.load_default()
    for path in ("arial.ttf", "Arial.ttf", os.path.join(os.environ.get("WINDIR", ""), "Fonts", "arial.ttf")):
        if path and os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, 36)
                break
            except OSError:
                pass
    text = "Россия"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) // 2, (h - th) // 2), text, fill=(60, 80, 120), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _fetch_map_url_bytes() -> Optional[bytes]:
    """Загружает карту по URL. Возвращает None при ошибке."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MAP_RUSSIA_URL, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as exc:
        logger.debug("Fetch map URL: %s", exc)
    return None


async def _get_russia_map_bytes() -> bytes:
    """Возвращает байты PNG карты России (из URL или сгенерированной)."""
    data = await _fetch_map_url_bytes()
    if data:
        return data
    return _generate_russia_map_bytes()


def _get_font(size: int = 24):
    """Загружает шрифт для подписей на картинках."""
    font = ImageFont.load_default()
    for path in (
        "arial.ttf",
        "Arial.ttf",
        os.path.join(os.environ.get("WINDIR", ""), "Fonts", "arial.ttf"),
    ):
        if path and os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                pass
    return font


# Палитра фонов и акцентов для карточек «Исторический центр» (у каждого города свой тон)
_HISTORIC_PALETTE = [
    ((232, 228, 218), (100, 70, 50)),   # бежевый, коричневый
    ((220, 232, 240), (50, 80, 120)),   # голубой, синий
    ((240, 235, 228), (120, 90, 60)),   # крем, сепия
    ((228, 238, 232), (60, 100, 80)),   # мятный, зелёный
    ((238, 228, 235), (100, 70, 90)),   # лавандовый, сливовый
    ((248, 242, 230), (140, 100, 60)),  # песочный, золотистый
    ((230, 238, 248), (70, 100, 130)),  # небесный, синий
    ((235, 228, 218), (90, 60, 50)),    # пенька, тёмно-коричневый
    ((242, 238, 228), (80, 70, 90)),   # серый фон, графит
    ((228, 235, 242), (50, 70, 100)),   # светло-синий, синий
]

def _generate_historic_center_image(city: City) -> bytes:
    """Генерирует картинку «Исторический центр» для города с уникальным оформлением."""
    w, h = 600, 400
    # Цвета по индексу города (у каждого города свой стиль)
    cities_list = list(RUSSIAN_MILLION_PLUS_CITIES.values())
    idx = next((i for i, c in enumerate(cities_list) if c.slug == city.slug), 0)
    bg_rgb, accent_rgb = _HISTORIC_PALETTE[idx % len(_HISTORIC_PALETTE)]

    img = Image.new("RGB", (w, h), bg_rgb)
    draw = ImageDraw.Draw(img)

    # Полукруг «купол» сверху по центру
    draw.ellipse([w // 2 - 90, -20, w // 2 + 90, 160], fill=tuple(max(0, c - 25) for c in accent_rgb), outline=accent_rgb, width=2)
    # Горизонтальная полоска под куполом (базовый силуэт)
    draw.rectangle([w // 2 - 120, 120, w // 2 + 120, 145], fill=accent_rgb)

    margin = 14
    draw.rectangle(
        [(margin, margin), (w - margin, h - margin)],
        outline=accent_rgb,
        width=2,
    )
    font_small = _get_font(20)
    font_large = _get_font(44)
    line1 = "Исторический центр"
    line2 = city.name_ru
    for font, text, y_frac in [
        (font_small, line1, 0.42),
        (font_large, line2, 0.62),
    ]:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, int(h * y_frac) - (bbox[3] - bbox[1]) // 2), text, fill=accent_rgb, font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _city_image_candidates(city: City) -> List[str]:
    """Список имён файлов картинок для города: 1 исторический центр + 3 достопримечательности."""
    return [
        f"historic_{city.slug}.png",
        f"landmark_{city.slug}_1.png",
        f"landmark_{city.slug}_2.png",
        f"landmark_{city.slug}_3.png",
    ]


def _get_random_city_image_bytes(city: City, user_data: Optional[Dict[str, Any]] = None) -> bytes:
    """Возвращает байты одной случайной картинки города; при повторном выборе того же города — по возможности другую (не повторяем последнюю)."""
    assets_dir = os.path.join(_script_dir, "assets")
    names = _city_image_candidates(city)
    candidates = [
        (name, os.path.join(assets_dir, name))
        for name in names
        if os.path.isfile(os.path.join(assets_dir, name))
    ]
    if not candidates:
        return _generate_historic_center_image(city)
    # Исключаем последнюю показанную картинку для этого города, чтобы показывать другую
    last_key = f"last_city_image_{city.slug}"
    if user_data and last_key in user_data:
        last_shown = user_data[last_key]
        choices = [c for c in candidates if c[0] != last_shown]
        if not choices:
            choices = candidates
    else:
        choices = candidates
    chosen_name, path = random.choice(choices)
    if user_data is not None:
        user_data[last_key] = chosen_name
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        pass
    return _generate_historic_center_image(city)


def _get_historic_center_image_bytes(city: City) -> bytes:
    """Возвращает байты картинки исторического центра: из файла assets или сгенерированные."""
    path = os.path.join(_script_dir, "assets", f"historic_{city.slug}.png")
    if os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            pass
    return _generate_historic_center_image(city)


# Коды погоды WMO (Open-Meteo) -> краткое описание на русском
WEATHER_CODE_RU: Dict[int, str] = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "морось",
    53: "морось",
    55: "морось",
    61: "дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "снег",
    73: "снег",
    75: "сильный снег",
    77: "снежные зёрна",
    80: "ливень",
    81: "ливень",
    82: "сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "гроза с сильным градом",
}


def _require_token_or_exit() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "Не задан TELEGRAM_TOKEN. Установите его в .env или переменных окружения."
        )


async def fetch_json(
    session: aiohttp.ClientSession, url: str, params: Dict[str, str]
) -> Optional[dict]:
    try:
        async with session.get(url, params=params, timeout=15) as resp:
            if resp.status != 200:
                logger.warning("Bad response %s from %s", resp.status, url)
                return None
            return await resp.json()
    except Exception as exc:
        logger.exception("Error fetching %s: %s", url, exc)
        return None


def _weather_desc(code: Optional[int]) -> str:
    if code is not None and code in WEATHER_CODE_RU:
        return WEATHER_CODE_RU[code]
    return "без осадков" if code is not None and code < 51 else "осадки"


async def get_weather(city: City) -> str:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": str(city.lat),
        "longitude": str(city.lon),
        "current": "temperature_2m,relative_humidity_2m,weather_code,surface_pressure,wind_speed_10m",
        "timezone": "Europe/Moscow",
    }

    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, url, params)

    if not data or "current" not in data:
        return "Не удалось получить погоду для этого города. Попробуйте позже."

    cur = data["current"]
    temp = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m")
    pressure = cur.get("surface_pressure")
    wind_speed = cur.get("wind_speed_10m")
    code = cur.get("weather_code")
    desc = _weather_desc(code)

    lines: List[str] = [
        f"🌤 Погода в городе {city.name_ru}:",
        f"• Температура: {temp}°C" if temp is not None else "",
        f"• {desc.capitalize()}",
        f"• Влажность: {humidity}%" if humidity is not None else "",
        f"• Давление: {pressure} hPa" if pressure is not None else "",
        f"• Ветер: {wind_speed} км/ч" if wind_speed is not None else "",
    ]
    return "\n".join(line for line in lines if line)


# RSS-ленты: много источников — больше новостей и выше шанс найти по каждому городу.
RSS_FEEDS: List[str] = [
    "https://lenta.ru/rss/news",
    "https://lenta.ru/rss/news/russia",
    "https://lenta.ru/rss/last24",
    "https://www.vedomosti.ru/rss/news",
    "https://ria.ru/export/rss2/index.xml",
    "https://ria.ru/export/rss2/archive/index.xml",
    "https://tass.ru/rss/v2.xml",
    "https://www.interfax.ru/rss.asp",
    "https://www.kommersant.ru/rss/news.xml",
    "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "https://www.mk.ru/rss/news.xml",
    "https://www.ng.ru/rss/",
    "https://www.gazeta.ru/export/rss/lenta.xml",
    "https://iz.ru/xml/rss/all.xml",
    "https://www.pravda.ru/rss/news.xml",
    "https://ura.news/rss",
]

# Соцсети: Telegram и VK. Telegram — через RSS-мосты (RSSHub и др.), VK — по API при наличии токена.
# Каналы СМИ и новостные паблики в Telegram (RSSHub и альтернативные мосты).
TELEGRAM_RSS_BRIDGES: List[str] = [
    "https://rsshub.app/telegram/channel/rian_ru",
    "https://rsshub.app/telegram/channel/rbc_news",
    "https://rsshub.app/telegram/channel/lentach",
    "https://rsshub.app/telegram/channel/tass_agency",
    "https://rsshub.app/telegram/channel/meduzalive",
    "https://rsshub.app/telegram/channel/moslenta",
    "https://rsshub.app/telegram/channel/msk1_news",
]
# Альтернативный мост (если rsshub недоступен): можно добавить свой rss-bridge
TELEGRAM_RSS_ALT: List[str] = [
    "https://tg.i-c-a.su/rss/rian_ru",
    "https://tg.i-c-a.su/rss/rbc_news",
]

# VK: ID новостных групп (owner_id = -id). Посты забираются только при заданном VK_ACCESS_TOKEN в .env
VK_NEWS_GROUP_IDS: List[int] = [
    15755094,   # РИА Новости
    27910242,   # Lenta.ru
    252324,     # РБК
    28588025,   # ТАСС
    30666417,   # Интерфакс
    224494,     # Коммерсантъ
]


def _parse_pubdate(date_str: str) -> Optional[float]:
    """Парсит pubDate из RSS (RFC 2822 или ISO 8601) в Unix timestamp (UTC)."""
    if not date_str or not date_str.strip():
        return None
    s = date_str.strip()
    try:
        # ISO 8601 (TASS и др.)
        if "T" in s and ("+" in s or "Z" in s or s.count("-") >= 2):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        # RFC 2822 (Lenta, RIA и др.)
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _parse_rss_items_full(xml_text: str, max_items: int = 80) -> List[NewsItem]:
    """Парсит RSS: возвращает список (title, link, description, pub_timestamp)."""
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            if elem.tag.endswith("item"):
                title, link, desc, pub_ts = "", "", "", None
                for child in elem:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    text = (child.text or "").strip() if child.text else ""
                    if not text and len(child) == 0 and child.tail:
                        text = (child.tail or "").strip()
                    if tag == "title" and text:
                        title = text
                    elif tag == "link" and text:
                        link = text
                    elif tag in ("description", "summary") and text:
                        desc = text
                    elif tag in ("pubDate", "published", "updated"):
                        pub_ts = _parse_pubdate(text) if text else None
                if title:
                    items.append((title, link, desc, pub_ts))
                    if len(items) >= max_items:
                        return items
        return items
    except ET.ParseError:
        pass
    return items


# Новости только за последние N дней
NEWS_DAYS_BACK = 7

# User-Agent для запросов к RSS-мостам (Telegram/VK в RSS), чтобы реже получать отказ
RSS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_rss_from_url(feed_url: str, max_fetch: int = 30) -> List[NewsItem]:
    """Загружает новости из одной RSS-ленты. Возвращает (title, link, description, pub_ts)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url, timeout=12) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                return _parse_rss_items_full(text, max_fetch)
    except Exception as exc:
        logger.debug("RSS fetch %s: %s", feed_url, exc)
    return []


async def _fetch_telegram_rss(session: aiohttp.ClientSession, feed_url: str) -> List[NewsItem]:
    """Пробует забрать RSS ленту Telegram-канала (через мост)."""
    try:
        async with session.get(
            feed_url,
            timeout=15,
            headers={"User-Agent": RSS_USER_AGENT},
        ) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()
            if "<rss" not in text.lower() and "<feed" not in text.lower():
                return []
            return _parse_rss_items_full(text, max_fetch=50)
    except Exception as exc:
        logger.debug("Telegram RSS %s: %s", feed_url[:50], exc)
    return []


async def _fetch_vk_wall(group_id: int, access_token: str, count: int = 40) -> List[NewsItem]:
    """Загружает посты со стены группы VK. owner_id = -group_id."""
    url = "https://api.vk.com/method/wall.get"
    params = {
        "owner_id": -group_id,
        "count": min(count, 100),
        "access_token": access_token,
        "v": "5.131",
        "filter": "owner",
    }
    out: List[NewsItem] = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception as exc:
        logger.debug("VK wall.get %s: %s", group_id, exc)
        return []
    if "error" in data:
        logger.debug("VK API error: %s", data.get("error", {}).get("error_msg"))
        return []
    items = data.get("response", {}).get("items", [])
    for post in items:
        text = (post.get("text") or "").strip()
        if not text:
            continue
        post_id = post.get("id")
        ts = post.get("date")
        pub_ts = float(ts) if ts else None
        link = f"https://vk.com/wall-{group_id}_{post_id}"
        title = text[:100] + "…" if len(text) > 100 else text
        title = title.replace("\n", " ").strip()
        out.append((title, link, text, pub_ts))
    return out


def _merge_news_items(
    merged: List[NewsItem],
    items: List[NewsItem],
    seen_links: set,
    cutoff_ts: float,
) -> None:
    for item in items:
        title, link, desc, pub_ts = item
        if link and link in seen_links:
            continue
        if pub_ts is not None and pub_ts < cutoff_ts:
            continue
        if link:
            seen_links.add(link)
        merged.append(item)


async def _fetch_rss_news_raw(max_fetch: int = 600) -> List[NewsItem]:
    """Загружает новости из СМИ (RSS), соцсетей (Telegram через RSS-мосты, VK по API) и объединяет."""
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS_BACK)).timestamp()
    seen_links: set = set()
    merged: List[NewsItem] = []

    # 1) Классические RSS (СМИ)
    async with aiohttp.ClientSession() as session:
        for feed_url in RSS_FEEDS:
            try:
                async with session.get(feed_url, timeout=12) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    items = _parse_rss_items_full(text, max_fetch=120)
                    _merge_news_items(merged, items, seen_links, cutoff_ts)
            except Exception as exc:
                logger.debug("RSS fetch %s: %s", feed_url, exc)

        # 2) Telegram: каналы СМИ через RSS-мосты (RSSHub, tg.i-c-a.su и т.д.)
        for feed_url in TELEGRAM_RSS_BRIDGES + TELEGRAM_RSS_ALT:
            items = await _fetch_telegram_rss(session, feed_url)
            _merge_news_items(merged, items, seen_links, cutoff_ts)

    # 3) VK: посты со стен новостных групп (если задан VK_ACCESS_TOKEN в .env)
    if VK_ACCESS_TOKEN:
        for group_id in VK_NEWS_GROUP_IDS:
            try:
                items = await _fetch_vk_wall(group_id, VK_ACCESS_TOKEN, count=30)
                _merge_news_items(merged, items, seen_links, cutoff_ts)
            except Exception as exc:
                logger.debug("VK wall %s: %s", group_id, exc)

    if not merged:
        # Fallback: одна лента без фильтра по дате
        async with aiohttp.ClientSession() as session:
            for feed_url in RSS_FEEDS:
                try:
                    async with session.get(feed_url, timeout=12) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        merged = _parse_rss_items_full(text, max_fetch)
                        if merged:
                            break
                except Exception:
                    continue
    merged.sort(key=lambda x: (x[3] or 0.0), reverse=True)
    return merged[:max_fetch]


# Доп. ключевые слова для поиска (падежи, сокращения) — чтобы находить больше новостей по городу
CITY_EXTRA_KEYWORDS: Dict[str, List[str]] = {
    "moscow": ["в Москве", "Москвы", "москвич", "столиц"],
    "spb": ["СПб", "Питер", "Санкт-Петербург", "в Петербурге", "Петербурга"],
    "novosibirsk": ["в Новосибирске", "Новосибирска"],
    "yekaterinburg": ["Екатеринбурге", "Екб", "Свердловск", "в Екатеринбурге"],
    "nizhny_novgorod": ["Нижнем Новгороде", "Нижегородск", "Нижнего Новгорода"],
    "kazan": ["в Казани", "Казани"],
    "chelyabinsk": ["в Челябинске", "Челябинска"],
    "omsk": ["в Омске", "Омска"],
    "samara": ["в Самаре", "Самары", "Самарск"],
    "rostov_on_don": ["Ростове-на-Дону", "Ростова-на-Дону", "в Ростове", "Ростовской"],
    "ufa": ["в Уфе", "Уфы"],
    "krasnoyarsk": ["в Красноярске", "Красноярска", "Красноярск"],
    "perm": ["в Перми", "Перми", "Пермск"],
    "voronezh": ["в Воронеже", "Воронежа", "Воронежск"],
    "volgograd": ["в Волгограде", "Волгограда", "Волгоградск"],
    "krasnodar": ["в Краснодаре", "Краснодара", "Кубан"],
    "saratov": ["в Саратове", "Саратова", "Саратовск"],
    "tyumen": ["в Тюмени", "Тюмени", "Тюменск"],
    "tolyatti": ["в Тольятти", "Тольятти"],
    "izhevsk": ["в Ижевске", "Ижевска", "Удмурт"],
    "barnaul": ["в Барнауле", "Барнаула", "Алтайск"],
    "ulyanovsk": ["в Ульяновске", "Ульяновска"],
    "irkutsk": ["в Иркутске", "Иркутска", "Байкал"],
    "khabarovsk": ["в Хабаровске", "Хабаровска", "Хабаровск"],
    "vladivostok": ["во Владивостоке", "Владивостока", "Приморь"],
    "mahachkala": ["в Махачкале", "Махачкалы", "Дагестан"],
}


def _keywords_for_city(city: City) -> List[str]:
    """Ключевые слова для поиска новостей по городу (название + регион + короткие формы)."""
    base = [city.name_ru] + list(city.search_keywords)
    extra = CITY_EXTRA_KEYWORDS.get(city.slug, [])
    return base + extra


def _strip_html(text: str) -> str:
    """Убирает HTML-теги для поиска по тексту."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ").strip()


def _filter_news_by_city(items: List[NewsItem], city: City, limit: int) -> List[Tuple[str, str]]:
    """Оставляет новости, где в заголовке или описании есть город или регион."""
    out: List[Tuple[str, str]] = []
    keywords = [k.lower() for k in _keywords_for_city(city) if k]
    for t in items:
        title = (t[0] or "").lower()
        desc_raw = t[2] if len(t) > 2 else ""
        desc = _strip_html(desc_raw).lower()
        if any(kw in title or kw in desc for kw in keywords):
            out.append((t[0], t[1]))
            if len(out) >= limit:
                return out
    return out


async def get_city_news(city: City, limit: int = 5) -> str:
    if NEWS_API_KEY:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": city.name_ru,
            "language": "ru",
            "pageSize": str(limit),
            "sortBy": "publishedAt",
            "apiKey": NEWS_API_KEY,
        }
        async with aiohttp.ClientSession() as session:
            data = await fetch_json(session, url, params)
        if data and data.get("status") == "ok":
            articles = data.get("articles", [])[:limit]
            if articles:
                lines: List[str] = [f"📰 Новости по городу {city.name_ru}:"]
                for idx, art in enumerate(articles, start=1):
                    title = art.get("title") or "Без заголовка"
                    url_art = art.get("url")
                    source = (art.get("source") or {}).get("name") or "Источник"
                    if url_art:
                        lines.append(f"{idx}. [{title}]({url_art}) — _{source}_")
                    else:
                        lines.append(f"{idx}. {title} — _{source}_")
                return "\n".join(lines)

    # Сначала пробуем региональную RSS для этого города (если есть)
    city_feeds = CITY_RSS_FEEDS.get(city.slug, [])
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS_BACK)).timestamp()
    for feed_url in city_feeds:
        raw_city = await _fetch_rss_from_url(feed_url, max_fetch=30)
        if raw_city:
            recent = [t for t in raw_city if t[3] is None or t[3] >= cutoff_ts][:limit]
            if not recent:
                recent = raw_city[:limit]
            items = [(t[0], t[1]) for t in recent]
            lines = [f"📰 Новости по городу {city.name_ru} (за неделю):"]
            for idx, (title, link) in enumerate(items, start=1):
                lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
            return "\n".join(lines)

    raw = await _fetch_rss_news_raw(max_fetch=600)
    if not raw:
        return "📰 Не удалось загрузить новости. Попробуйте позже."
    by_city = _filter_news_by_city(raw, city, limit=limit)
    if by_city:
        lines = [f"📰 Новости по городу {city.name_ru} (за неделю):"]
        for idx, (title, link) in enumerate(by_city, start=1):
            lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
        return "\n".join(lines)
    # По городу не найдено — показываем общие новости (всегда что-то показываем)
    general_limit = max(limit, 8)
    general = [(t[0], t[1]) for t in raw[:general_limit]]
    lines = [f"📰 Новости по городу {city.name_ru} (общая лента России):"]
    for idx, (title, link) in enumerate(general, start=1):
        lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
    return "\n".join(lines)


# Тексты кнопок меню (одинаковые для inline и reply-клавиатуры)
MENU_BTN_HELP = "❓ Справка"
MENU_BTN_CITY = "🏙 Выбор города"
MENU_BTN_WEATHER = "🌤 Погода"
MENU_BTN_NEWS = "📰 Новости"
MENU_BTN_START = "🗺 Старт и карта"
MENU_BTN_MENU = "📋 Меню"

MENU_BUTTON_TEXTS = frozenset(
    {MENU_BTN_HELP, MENU_BTN_CITY, MENU_BTN_WEATHER, MENU_BTN_NEWS, MENU_BTN_START, MENU_BTN_MENU}
)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Блок меню (inline): сетка 2×3, все команды подписаны."""
    buttons: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(MENU_BTN_HELP, callback_data="menu:help"),
            InlineKeyboardButton(MENU_BTN_CITY, callback_data="menu:city"),
        ],
        [
            InlineKeyboardButton(MENU_BTN_WEATHER, callback_data="menu:weather"),
            InlineKeyboardButton(MENU_BTN_NEWS, callback_data="menu:news"),
        ],
        [
            InlineKeyboardButton(MENU_BTN_START, callback_data="menu:start"),
            InlineKeyboardButton(MENU_BTN_MENU, callback_data="menu:menu"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def build_reply_menu_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура внизу экрана (блок меню под полем ввода)."""
    keyboard = [
        [KeyboardButton(MENU_BTN_HELP), KeyboardButton(MENU_BTN_CITY)],
        [KeyboardButton(MENU_BTN_WEATHER), KeyboardButton(MENU_BTN_NEWS)],
        [KeyboardButton(MENU_BTN_START), KeyboardButton(MENU_BTN_MENU)],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def build_cities_keyboard(prefix: str = "city") -> InlineKeyboardMarkup:
    """Клавиатура выбора города. prefix: city, weather или news — от него зависит callback_data."""
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for city in RUSSIAN_MILLION_PLUS_CITIES.values():
        row.append(
            InlineKeyboardButton(
                text=city.name_ru,
                callback_data=f"{prefix}:{city.slug}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


async def send_weather_only(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Только погода по городу (одна случайная картинка: при повторном выборе города — по возможности другая)."""
    try:
        user_data = context.user_data if context else None
        img_bytes = _get_random_city_image_bytes(city, user_data)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(io.BytesIO(img_bytes), filename=f"{city.slug}.png"),
            caption=f"🏛 {city.name_ru}",
        )
    except Exception as exc:
        logger.warning("Historic center image for %s: %s", city.slug, exc)
    weather_text = await get_weather(city)
    await context.bot.send_message(
        chat_id=chat_id,
        text=weather_text,
    )


async def send_news_only(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Только новости по городу."""
    news_text = await get_city_news(city)
    await context.bot.send_message(
        chat_id=chat_id,
        text=news_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False,
    )


async def send_city_info(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Погода и новости вместе (для выбора города из /start или /city)."""
    await send_weather_only(context, chat_id, city)
    await send_news_only(context, chat_id, city)


async def _send_start_content(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Отправляет карту России и блок меню (6 подписанных кнопок). Используется в /start и по кнопке «Старт и карта»."""
    caption = (
        "🗺 **Карта России**\n\n"
        "Привет! Я бот погоды и новостей по городам‑миллионникам.\n\n"
        "**Команды:** /start — старт и карта, /menu — меню, /city — выбор города, "
        "/weather — погода, /news — новости, /help — справка.\n\n"
        "Кнопка **☰ Меню** слева от поля ввода или блок кнопок ниже."
    )
    if os.path.isfile(MAP_RUSSIA_PATH):
        try:
            with open(MAP_RUSSIA_PATH, "rb") as f:
                photo_bytes = f.read()
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(io.BytesIO(photo_bytes), filename="map_russia.png"),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Отправка карты из файла не удалась: %s", e)
            await context.bot.send_message(
                chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN
            )
    else:
        try:
            map_bytes = await _get_russia_map_bytes()
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(io.BytesIO(map_bytes), filename="map_russia.png"),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Карта не отправлена: %s", e)
            await context.bot.send_message(
                chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN
            )
    await context.bot.send_message(
        chat_id=chat_id,
        text="📋 **Меню** — выберите действие (кнопки под сообщением и внизу экрана):",
        reply_markup=build_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    # Постоянный блок меню внизу экрана (как на образце)
    await context.bot.send_message(
        chat_id=chat_id,
        text="⬇️ Кнопки меню закреплены внизу.",
        reply_markup=build_reply_menu_keyboard(),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = getattr(update.effective_chat, "id", None) if update.effective_chat else None
    if chat_id is None:
        logger.error("/start: chat_id is None")
        return

    try:
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonCommands(),
        )
    except Exception:
        pass

    await _send_start_content(context, chat_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Погода и новости по городам‑миллионникам России.\n\n"
        "**Команды** (также в кнопке ☰ Меню слева от поля ввода):\n"
        "/start — приветствие и карта\n"
        "/menu — открыть меню кнопками\n"
        "/city — выбор города (погода и новости)\n"
        "/weather — погода по городу\n"
        "/news — новости по городу"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = build_cities_keyboard(prefix="weather")
    await update.message.reply_text(
        "Выберите город для погоды:",
        reply_markup=keyboard,
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = build_cities_keyboard(prefix="news")
    await update.message.reply_text(
        "Выберите город для новостей:",
        reply_markup=keyboard,
    )


async def city_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = build_cities_keyboard(prefix="city")
    await update.message.reply_text(
        "Выберите город (погода и новости):",
        reply_markup=keyboard,
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню и включает блок кнопок внизу экрана."""
    await update.message.reply_text(
        "📋 **Меню** — выберите действие:",
        reply_markup=build_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await update.message.reply_text(
        "⬇️ Кнопки меню внизу экрана.",
        reply_markup=build_reply_menu_keyboard(),
    )


async def menu_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий кнопок постоянного меню (блок внизу экрана)."""
    text = (update.message and update.message.text or "").strip()
    if text not in MENU_BUTTON_TEXTS:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return
    if text == MENU_BTN_HELP:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Я показываю погоду и новости по городам‑миллионникам России.\n\n"
                "**Команды:**\n"
                "/start — приветствие и карта России\n"
                "/menu — открыть блок меню\n"
                "/city — выбор города (погода и новости)\n"
                "/weather — погода по городу\n"
                "/news — новости по городу\n"
                "/help — эта справка"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    elif text == MENU_BTN_CITY:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Выберите город (погода и новости):",
            reply_markup=build_cities_keyboard(prefix="city"),
        )
    elif text == MENU_BTN_WEATHER:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Выберите город для погоды:",
            reply_markup=build_cities_keyboard(prefix="weather"),
        )
    elif text == MENU_BTN_NEWS:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Выберите город для новостей:",
            reply_markup=build_cities_keyboard(prefix="news"),
        )
    elif text == MENU_BTN_START:
        await _send_start_content(context, chat_id)
    elif text == MENU_BTN_MENU:
        await context.bot.send_message(
            chat_id=chat_id,
            text="📋 **Меню** — выберите действие:",
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


def get_city_by_slug(slug: str) -> Optional[City]:
    return RUSSIAN_MILLION_PLUS_CITIES.get(slug)


async def city_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    if ":" not in data:
        return
    prefix, slug = data.split(":", 1)
    chat_id = query.message.chat.id if query.message else update.effective_chat.id

    # Блок меню: все команды подписаны (Справка, Выбор города, Погода, Новости, Старт и карта, Меню)
    if prefix == "menu":
        if slug == "help":
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Я показываю погоду и новости по городам‑миллионникам России.\n\n"
                    "**Команды:**\n"
                    "/start — приветствие и карта России\n"
                    "/menu — открыть блок меню\n"
                    "/city — выбор города (погода и новости)\n"
                    "/weather — погода по городу\n"
                    "/news — новости по городу\n"
                    "/help — эта справка"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif slug == "city":
            await context.bot.send_message(
                chat_id=chat_id,
                text="Выберите город (погода и новости):",
                reply_markup=build_cities_keyboard(prefix="city"),
            )
        elif slug == "weather":
            await context.bot.send_message(
                chat_id=chat_id,
                text="Выберите город для погоды:",
                reply_markup=build_cities_keyboard(prefix="weather"),
            )
        elif slug == "news":
            await context.bot.send_message(
                chat_id=chat_id,
                text="Выберите город для новостей:",
                reply_markup=build_cities_keyboard(prefix="news"),
            )
        elif slug == "start":
            await _send_start_content(context, chat_id)
        elif slug == "menu":
            await context.bot.send_message(
                chat_id=chat_id,
                text="📋 **Меню** — выберите действие:",
                reply_markup=build_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    city = get_city_by_slug(slug)
    if not city:
        await query.edit_message_text("Неизвестный город, попробуйте ещё раз.")
        return

    context.user_data["city_slug"] = slug

    if prefix == "weather":
        await query.edit_message_text(f"Город: {city.name_ru}. Загружаю погоду...")
        await send_weather_only(context, chat_id, city)
    elif prefix == "news":
        await query.edit_message_text(f"Город: {city.name_ru}. Загружаю новости...")
        await send_news_only(context, chat_id, city)
    else:
        await query.edit_message_text(f"Город: {city.name_ru}. Получаю погоду и новости...")
        await send_city_info(context, chat_id, city)


def _log_bot_username() -> None:
    """Печатает @username бота, чтобы проверить, что пишете именно ему."""
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("ok") and data.get("result"):
            username = data["result"].get("username", "?")
            logger.info("Бот запущен. Пишите ему в Telegram: @%s", username)
    except Exception as e:
        logger.warning("Не удалось получить имя бота: %s", e)


# Список команд бота (при вводе / в чате)
BOT_COMMANDS_MENU: List[BotCommand] = [
    BotCommand("start", "Старт и карта России"),
    BotCommand("menu", "Открыть меню с кнопками"),
    BotCommand("city", "Выбор города (погода и новости)"),
    BotCommand("weather", "Погода по городу"),
    BotCommand("news", "Новости по городу"),
    BotCommand("help", "Справка по командам"),
]


async def post_init_set_commands(application) -> None:
    """Устанавливает список команд и кнопку «Меню» при запуске бота (паттерн из telegram-bot-builder)."""
    bot = application.bot
    scope_default = BotCommandScopeDefault()
    scope_private = BotCommandScopeAllPrivateChats()
    try:
        await bot.set_my_commands(BOT_COMMANDS_MENU, scope=scope_default)
        await bot.set_my_commands(BOT_COMMANDS_MENU, scope=scope_default, language_code="ru")
        await bot.set_my_commands(BOT_COMMANDS_MENU, scope=scope_private)
        await bot.set_my_commands(BOT_COMMANDS_MENU, scope=scope_private, language_code="ru")
        logger.info("Команды бота установлены (default + all_private_chats).")
    except Exception as e:
        logger.warning("set_my_commands: %s", e, exc_info=True)
    try:
        await bot.set_chat_menu_button(chat_id=None, menu_button=MenuButtonCommands())
        logger.info("Кнопка меню установлена (MenuButtonCommands).")
    except Exception as e:
        logger.warning("set_chat_menu_button: %s", e, exc_info=True)


def main() -> None:
    _require_token_or_exit()
    if len(TELEGRAM_TOKEN) < 20:
        raise RuntimeError("TELEGRAM_TOKEN похож на пустой или неверный. Проверьте .env")

    _log_bot_username()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init_set_commands)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    # Если /start пришёл как текст (не команда)
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"^(/start|start)$"), start_command)
    )
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("city", city_command))
    app.add_handler(CallbackQueryHandler(city_button_handler))
    app.add_handler(MessageHandler(filters.TEXT, menu_reply_handler))

    logger.info("Starting Telegram weather/news bot...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
