import asyncio
import io
import json
import logging
import os
import random
import re
import threading
import time
import urllib.request
from urllib.parse import quote
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
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
# URL мини-приложения (Pac-Man). Должен быть HTTPS. Пример: https://your-domain.com/mini_app/
MINI_APP_URL = (os.getenv("MINI_APP_URL") or "").strip()
WEATHER_APP_URL = (os.getenv("WEATHER_APP_URL") or "").strip()


@dataclass
class City:
    slug: str
    name_ru: str
    name_en: str
    lat: float
    lon: float
    # Доп. ключевые слова для поиска новостей (город + регион/республика/край)
    search_keywords: tuple = ()


# Все города РФ с населением 500 тыс.+ (по данным Росстата): название, координаты, ключевые слова для новостей
RUSSIAN_MILLION_PLUS_CITIES: Dict[str, City] = {
    "moscow": City("moscow", "Москва", "Moscow", 55.7558, 37.6173, ("Московская область", "Подмосковье")),
    "spb": City("spb", "Санкт-Петербург", "Saint Petersburg", 59.9343, 30.3351, ("Ленинградская область", "Петербург")),
    "novosibirsk": City("novosibirsk", "Новосибирск", "Novosibirsk", 55.0084, 82.9357, ("Новосибирская область",)),
    "yekaterinburg": City("yekaterinburg", "Екатеринбург", "Yekaterinburg", 56.8389, 60.6057, ("Свердловская область", "Урал")),
    "kazan": City("kazan", "Казань", "Kazan", 55.8304, 49.0661, ("Татарстан",)),
    "krasnoyarsk": City("krasnoyarsk", "Красноярск", "Krasnoyarsk", 56.0153, 92.8932, ("Красноярский край",)),
    "nizhny_novgorod": City("nizhny_novgorod", "Нижний Новгород", "Nizhny Novgorod", 56.2965, 43.9361, ("Нижегородская область",)),
    "chelyabinsk": City("chelyabinsk", "Челябинск", "Chelyabinsk", 55.1644, 61.4368, ("Челябинская область",)),
    "ufa": City("ufa", "Уфа", "Ufa", 54.7388, 55.9721, ("Башкортостан", "Башкирия")),
    "krasnodar": City("krasnodar", "Краснодар", "Krasnodar", 45.0353, 38.9753, ("Краснодарский край", "Кубань")),
    "samara": City("samara", "Самара", "Samara", 53.1959, 50.1002, ("Самарская область", "Куйбышев")),
    "rostov_on_don": City("rostov_on_don", "Ростов-на-Дону", "Rostov-on-Don", 47.2313, 39.7233, ("Ростовская область", "Дон")),
    "omsk": City("omsk", "Омск", "Omsk", 54.9885, 73.3242, ("Омская область",)),
    "voronezh": City("voronezh", "Воронеж", "Voronezh", 51.6720, 39.1843, ("Воронежская область",)),
    "perm": City("perm", "Пермь", "Perm", 58.0105, 56.2502, ("Пермский край",)),
    "volgograd": City("volgograd", "Волгоград", "Volgograd", 48.7080, 44.5133, ("Волгоградская область",)),
    "saratov": City("saratov", "Саратов", "Saratov", 51.5924, 46.0342, ("Саратовская область",)),
    "tyumen": City("tyumen", "Тюмень", "Tyumen", 57.1531, 65.5343, ("Тюменская область",)),
    "tolyatti": City("tolyatti", "Тольятти", "Tolyatti", 53.5303, 49.3461, ("Самарская область", "Жигулёвск")),
    "mahachkala": City("mahachkala", "Махачкала", "Makhachkala", 42.9849, 47.5047, ("Дагестан", "Дагестана")),
    "barnaul": City("barnaul", "Барнаул", "Barnaul", 53.3606, 83.7546, ("Алтайский край", "Алтай")),
    "izhevsk": City("izhevsk", "Ижевск", "Izhevsk", 56.8498, 53.2045, ("Удмуртия", "Удмуртская")),
    "khabarovsk": City("khabarovsk", "Хабаровск", "Khabarovsk", 48.4827, 135.0838, ("Хабаровский край",)),
    "ulyanovsk": City("ulyanovsk", "Ульяновск", "Ulyanovsk", 54.3282, 48.3866, ("Ульяновская область",)),
    "irkutsk": City("irkutsk", "Иркутск", "Irkutsk", 52.2978, 104.2964, ("Иркутская область", "Байкал")),
    "vladivostok": City("vladivostok", "Владивосток", "Vladivostok", 43.1198, 131.8869, ("Приморский край", "Приморье")),
    "yaroslavl": City("yaroslavl", "Ярославль", "Yaroslavl", 57.6299, 39.8737, ("Ярославская область",)),
    "stavropol": City("stavropol", "Ставрополь", "Stavropol", 45.0428, 41.9734, ("Ставропольский край",)),
    "sevastopol": City("sevastopol", "Севастополь", "Sevastopol", 44.6167, 33.5254, ("Крым", "Севастополь")),
    "naberezhnye_chelny": City("naberezhnye_chelny", "Набережные Челны", "Naberezhnye Chelny", 55.7306, 52.4112, ("Татарстан", "Челны")),
    "tomsk": City("tomsk", "Томск", "Tomsk", 56.4846, 84.9476, ("Томская область",)),
    "balashikha": City("balashikha", "Балашиха", "Balashikha", 55.8094, 37.9581, ("Московская область", "Подмосковье")),
    "kemerovo": City("kemerovo", "Кемерово", "Kemerovo", 55.3547, 86.0873, ("Кемеровская область", "Кузбасс")),
    "orenburg": City("orenburg", "Оренбург", "Orenburg", 51.7682, 55.0970, ("Оренбургская область",)),
    "novokuznetsk": City("novokuznetsk", "Новокузнецк", "Novokuznetsk", 53.7565, 87.1361, ("Кемеровская область", "Кузбасс")),
    "ryazan": City("ryazan", "Рязань", "Ryazan", 54.6294, 39.7357, ("Рязанская область",)),
    "donetsk": City("donetsk", "Донецк", "Donetsk", 48.0159, 37.8029, ("ДНР", "Донецкая область")),
    "luhansk": City("luhansk", "Луганск", "Luhansk", 48.5671, 39.3171, ("ЛНР", "Луганская область")),
    "tula": City("tula", "Тула", "Tula", 54.2044, 37.6175, ("Тульская область",)),
    "kirov": City("kirov", "Киров", "Kirov", 58.6036, 49.6680, ("Кировская область",)),
    "kaliningrad": City("kaliningrad", "Калининград", "Kaliningrad", 54.7104, 20.5106, ("Калининградская область",)),
    "bryansk": City("bryansk", "Брянск", "Bryansk", 53.2521, 34.3717, ("Брянская область",)),
    "kursk": City("kursk", "Курск", "Kursk", 51.7304, 36.1926, ("Курская область",)),
    "magnitogorsk": City("magnitogorsk", "Магнитогорск", "Magnitogorsk", 53.4186, 58.9794, ("Челябинская область",)),
    "sochi": City("sochi", "Сочи", "Sochi", 43.5992, 39.7257, ("Краснодарский край",)),
    "vladikavkaz": City("vladikavkaz", "Владикавказ", "Vladikavkaz", 43.0367, 44.6678, ("Северная Осетия",)),
    "grozny": City("grozny", "Грозный", "Grozny", 43.3178, 45.6982, ("Чечня",)),
    "tambov": City("tambov", "Тамбов", "Tambov", 52.7317, 41.4433, ("Тамбовская область",)),
    "ivanovo": City("ivanovo", "Иваново", "Ivanovo", 56.9972, 40.9714, ("Ивановская область",)),
    "tver": City("tver", "Тверь", "Tver", 56.8587, 35.9176, ("Тверская область",)),
    "simferopol": City("simferopol", "Симферополь", "Simferopol", 44.9572, 34.1108, ("Крым",)),
    "kostroma": City("kostroma", "Кострома", "Kostroma", 57.7665, 40.9269, ("Костромская область",)),
    "volzhsky": City("volzhsky", "Волжский", "Volzhsky", 48.7858, 44.7794, ("Волгоградская область",)),
    "taganrog": City("taganrog", "Таганрог", "Taganrog", 47.2362, 38.8969, ("Ростовская область",)),
    "sterlitamak": City("sterlitamak", "Стерлитамак", "Sterlitamak", 53.6247, 55.9502, ("Башкортостан",)),
    "komsomolsk_na_amure": City("komsomolsk_na_amure", "Комсомольск-на-Амуре", "Komsomolsk-on-Amur", 50.5500, 137.0000, ("Хабаровский край",)),
    "petrozavodsk": City("petrozavodsk", "Петрозаводск", "Petrozavodsk", 61.7849, 34.3469, ("Карелия",)),
    "lipetsk": City("lipetsk", "Липецк", "Lipetsk", 52.6031, 39.5708, ("Липецкая область",)),
    "arhangelsk": City("arhangelsk", "Архангельск", "Arkhangelsk", 64.5401, 40.5433, ("Архангельская область",)),
    "cheboksary": City("cheboksary", "Чебоксары", "Cheboksary", 56.1322, 47.2515, ("Чувашия",)),
    "kaluga": City("kaluga", "Калуга", "Kaluga", 54.5293, 36.2754, ("Калужская область",)),
    "smolensk": City("smolensk", "Смоленск", "Smolensk", 54.7826, 32.0453, ("Смоленская область",)),
}

# 10 самых крупных по населению — только они в выпадающем списке; остальные через поиск (лупа)
TOP_10_CITY_SLUGS: List[str] = [
    "moscow", "spb", "novosibirsk", "yekaterinburg", "kazan", "krasnoyarsk",
    "nizhny_novgorod", "chelyabinsk", "ufa", "krasnodar",
]

# Часовой пояс (IANA) для каждого города — для актуального местного времени в сообщении о погоде
CITY_TIMEZONES: Dict[str, str] = {
    "moscow": "Europe/Moscow", "spb": "Europe/Moscow", "nizhny_novgorod": "Europe/Moscow", "kazan": "Europe/Moscow",
    "voronezh": "Europe/Moscow", "volgograd": "Europe/Moscow", "krasnodar": "Europe/Moscow", "rostov_on_don": "Europe/Moscow",
    "saratov": "Europe/Moscow", "ulyanovsk": "Europe/Moscow", "mahachkala": "Europe/Moscow", "samara": "Europe/Samara",
    "tolyatti": "Europe/Samara", "izhevsk": "Europe/Samara", "yekaterinburg": "Asia/Yekaterinburg", "chelyabinsk": "Asia/Yekaterinburg",
    "perm": "Asia/Yekaterinburg", "tyumen": "Asia/Yekaterinburg", "ufa": "Asia/Yekaterinburg", "omsk": "Asia/Omsk",
    "novosibirsk": "Asia/Krasnoyarsk", "barnaul": "Asia/Barnaul", "krasnoyarsk": "Asia/Krasnoyarsk", "irkutsk": "Asia/Irkutsk",
    "khabarovsk": "Asia/Vladivostok", "vladivostok": "Asia/Vladivostok",
    "yaroslavl": "Europe/Moscow", "stavropol": "Europe/Moscow", "sevastopol": "Europe/Simferopol", "naberezhnye_chelny": "Europe/Moscow",
    "tomsk": "Asia/Tomsk", "balashikha": "Europe/Moscow", "kemerovo": "Asia/Krasnoyarsk", "orenburg": "Asia/Yekaterinburg",
    "novokuznetsk": "Asia/Krasnoyarsk", "ryazan": "Europe/Moscow",
    "donetsk": "Europe/Moscow", "luhansk": "Europe/Moscow", "tula": "Europe/Moscow", "kirov": "Europe/Moscow",
    "kaliningrad": "Europe/Kaliningrad", "bryansk": "Europe/Moscow", "kursk": "Europe/Moscow", "magnitogorsk": "Asia/Yekaterinburg",
    "sochi": "Europe/Moscow", "vladikavkaz": "Europe/Moscow", "grozny": "Europe/Moscow", "tambov": "Europe/Moscow",
    "ivanovo": "Europe/Moscow", "tver": "Europe/Moscow", "simferopol": "Europe/Simferopol", "kostroma": "Europe/Moscow",
    "volzhsky": "Europe/Moscow", "taganrog": "Europe/Moscow", "sterlitamak": "Asia/Yekaterinburg",
    "komsomolsk_na_amure": "Asia/Vladivostok", "petrozavodsk": "Europe/Moscow", "lipetsk": "Europe/Moscow",
    "arhangelsk": "Europe/Moscow", "cheboksary": "Europe/Moscow", "kaluga": "Europe/Moscow", "smolensk": "Europe/Moscow",
}

# Смещение от UTC (часы) для запасного расчёта местного времени
CITY_UTC_OFFSET_HOURS: Dict[str, int] = {
    "moscow": 3, "spb": 3, "nizhny_novgorod": 3, "kazan": 3, "voronezh": 3, "volgograd": 3, "krasnodar": 3,
    "rostov_on_don": 3, "saratov": 3, "ulyanovsk": 3, "mahachkala": 3, "samara": 4, "tolyatti": 4, "izhevsk": 4,
    "yekaterinburg": 5, "chelyabinsk": 5, "perm": 5, "tyumen": 5, "ufa": 5, "omsk": 6, "novosibirsk": 7,
    "barnaul": 7, "krasnoyarsk": 7, "irkutsk": 8, "khabarovsk": 10, "vladivostok": 10,
    "yaroslavl": 3, "stavropol": 3, "sevastopol": 3, "naberezhnye_chelny": 3, "tomsk": 7, "balashikha": 3,
    "kemerovo": 7, "orenburg": 5, "novokuznetsk": 7, "ryazan": 3,
    "donetsk": 3, "luhansk": 3, "tula": 3, "kirov": 3, "kaliningrad": 2, "bryansk": 3, "kursk": 3, "magnitogorsk": 5,
    "sochi": 3, "vladikavkaz": 3, "grozny": 3, "tambov": 3, "ivanovo": 3, "tver": 3, "simferopol": 3, "kostroma": 3,
    "volzhsky": 3, "taganrog": 3, "sterlitamak": 5, "komsomolsk_na_amure": 10, "petrozavodsk": 3, "lipetsk": 3,
    "arhangelsk": 3, "cheboksary": 3, "kaluga": 3, "smolensk": 3,
}

# Региональные RSS: у каждого города свои ленты. Сначала — надёжные федеральные (РИА, ТАСС, Интерфакс, Lenta), затем региональные.
CITY_RSS_FEEDS: Dict[str, List[str]] = {
    "moscow": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://www.mskagency.ru/rss/index.rss",
        "https://www.mos.ru/rss/news/",
        "https://riamo.ru/rss/",
        "https://vm.ru/rss/",
        "https://m24.ru/rss/",
    ],
    "spb": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://neva.versia.ru/rss/index.xml",
        "https://www.fontanka.ru/fontanka.rss",
        "https://spb.rbc.ru/rss/",
        "https://spb.aif.ru/rss/",
        "https://mr7.ru/rss/",
    ],
    "novosibirsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://ngs.ru/rss/",
        "https://tayga.info/rss",
        "https://nsk.rbc.ru/rss/",
        "https://nsk.aif.ru/rss/",
        "https://sibnovosti.ru/rss/",
    ],
    "yekaterinburg": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://66.ru/rss/",
        "https://uralpolit.ru/rss",
        "https://ekb.rbc.ru/rss/",
        "https://ekb.aif.ru/rss/",
        "https://ura.news/rss",
    ],
    "nizhny_novgorod": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://nn.versia.ru/rss/index.xml",
        "https://nn.rbc.ru/rss/",
        "https://pravda-nn.ru/rss/",
        "https://nn.aif.ru/rss/",
        "https://vremyan.ru/rss/",
    ],
    "kazan": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://tat.versia.ru/rss/index.xml",
        "https://kazan.rbc.ru/rss/",
        "https://rt.rbc.ru/rss/",
        "https://kazan.aif.ru/rss/",
        "https://business-gazeta.ru/rss",
    ],
    "chelyabinsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://74.ru/rss/",
        "https://up74.ru/rss/",
        "https://chelyabinsk.rbc.ru/rss/",
        "https://chel.aif.ru/rss/",
        "https://uralpress.ru/rss/",
        "https://www.kommersant.ru/rss/news.xml",
        "https://www.gazeta.ru/export/rss/lenta.xml",
    ],
    "omsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://om1.ru/rss/",
        "https://omsk.rbc.ru/rss/",
        "https://omsk55.ru/rss/",
        "https://omsk.aif.ru/rss/",
        "https://omskinform.ru/rss/",
    ],
    "samara": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://63.ru/rss/",
        "https://samara.ru/rss",
        "https://samara.rbc.ru/rss/",
        "https://samara.aif.ru/rss/",
        "https://sgpress.ru/rss/",
    ],
    "rostov_on_don": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://161.ru/rss/",
        "https://rostov.ru/rss/",
        "https://rostov.rbc.ru/rss/",
        "https://rostov.aif.ru/rss/",
        "https://don24.ru/rss/",
    ],
    "ufa": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://rb.versia.ru/rss/index.xml",
        "https://ufa.rbc.ru/rss/",
        "https://bash.news/rss/",
        "https://www.bashinform.ru/feed",
        "https://ufa.aif.ru/rss/",
    ],
    "krasnoyarsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://ngs24.ru/rss/",
        "https://krasnoyarsk.rbc.ru/rss/",
        "https://krsk.sibnovosti.ru/rss/",
        "https://krsk.aif.ru/rss/",
        "https://gornovosti.ru/rss/",
    ],
    "perm": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://59.ru/rss/",
        "https://perm.rbc.ru/rss/",
        "https://perm.aif.ru/rss/",
        "https://permnews.ru/rss/",
        "https://zvzda.ru/rss/",
    ],
    "voronezh": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://voronezh.versia.ru/rss/index.xml",
        "https://voronezh.rbc.ru/rss/",
        "https://vrntimes.ru/rss/",
        "https://voronezh.aif.ru/rss/",
        "https://communa.ru/rss/",
    ],
    "volgograd": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://v1.ru/rss/",
        "https://volgograd.rbc.ru/rss/",
        "https://volgograd-trv.ru/rss/",
        "https://volgograd.aif.ru/rss/",
        "https://vlg-media.ru/rss/",
    ],
    "krasnodar": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://kavkaz.versia.ru/rss/index.xml",
        "https://yugopolis.ru/rss/",
        "https://krasnodar.rbc.ru/rss/",
        "https://krasnodar.aif.ru/rss/",
        "https://kuban24.tv/rss/",
    ],
    "saratov": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://www.sarbc.ru/rss/",
        "https://saratov.versia.ru/rss/index.xml",
        "https://saratov.rbc.ru/rss/",
        "https://saratov.aif.ru/rss/",
        "https://sarnovosti.ru/rss/",
    ],
    "tyumen": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://72.ru/rss/",
        "https://tyumen.rbc.ru/rss/",
        "https://tumentoday.ru/rss/",
        "https://tyumen.aif.ru/rss/",
        "https://t-l.ru/rss/",
    ],
    "tolyatti": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://63.ru/rss/",
        "https://tlt.ru/rss/",
        "https://togliatti24.ru/rss/",
        "https://samara.aif.ru/rss/",
        "https://tltgorod.ru/rss/",
    ],
    "izhevsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://udm-info.ru/rss/",
        "https://izhlife.ru/rss/",
        "https://udm.rbc.ru/rss/",
        "https://izhevsk.aif.ru/rss/",
        "https://susanin.news/rss/",
    ],
    "barnaul": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://barnaul22.ru/rss/",
        "https://altapress.ru/rss/",
        "https://barnaul.rbc.ru/rss/",
        "https://altai.aif.ru/rss/",
        "https://barnaul.fm/rss/",
    ],
    "ulyanovsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://73online.ru/rss/",
        "https://ulpressa.ru/rss/",
        "https://uliyanovsk.rbc.ru/rss/",
        "https://ul.aif.ru/rss/",
        "https://ulgov.ru/rss/",
    ],
    "irkutsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://irk.ru/rss/",
        "https://irkutsk.rbc.ru/rss/",
        "https://baikal-info.ru/rss/",
        "https://irkutsk.aif.ru/rss/",
        "https://irk.kp.ru/rss/",
    ],
    "khabarovsk": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://dvhab.ru/rss/",
        "https://khabarovsk.rbc.ru/rss/",
        "https://dvnovosti.ru/rss/",
        "https://khabarovsk.aif.ru/rss/",
        "https://amurpress.ru/rss/",
    ],
    "vladivostok": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://vl.ru/rss/",
        "https://vladivostok.rbc.ru/rss/",
        "https://primamedia.ru/rss/",
        "https://vladivostok.aif.ru/rss/",
        "https://primorye24.ru/rss/",
    ],
    "mahachkala": [
        "https://ria.ru/export/rss2/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://lenta.ru/rss/news/russia",
        "https://kavkaz.versia.ru/rss/index.xml",
        "https://riadagestan.ru/rss/",
        "https://makhachkala.rbc.ru/rss/",
        "https://dag.aif.ru/rss/",
        "https://dagestan.news/rss/",
    ],
    "yaroslavl": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://yaroslavl.rbc.ru/rss/", "https://76.ru/rss/"],
    "stavropol": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://stavropol.rbc.ru/rss/"],
    "sevastopol": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia"],
    "naberezhnye_chelny": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://rt.rbc.ru/rss/"],
    "tomsk": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://tomsk.rbc.ru/rss/", "https://tayga.info/rss"],
    "balashikha": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://riamo.ru/rss/"],
    "kemerovo": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://kemerovo.rbc.ru/rss/"],
    "orenburg": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://56.ru/rss/"],
    "novokuznetsk": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://kemerovo.rbc.ru/rss/"],
    "ryazan": ["https://ria.ru/export/rss2/index.xml", "https://tass.ru/rss/v2.xml", "https://www.interfax.ru/rss.asp", "https://lenta.ru/rss/news/russia", "https://62info.ru/rss/", "https://ryazan.rbc.ru/rss/"],
}

# Локальная карта России при приветствии (шаблон из проекта)
MAP_RUSSIA_PATH = os.path.join(_script_dir, "assets", "map_russia.png")
# Эталонная тёмная карта России для погоды (форма страны + границы регионов)
RUSSIA_WEATHER_MAP_BASE = os.path.join(_script_dir, "assets", "russia_weather_base.png")
# Запасная карта по URL, если локального файла нет
MAP_RUSSIA_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Russia_orthographic_map.svg/600px-Russia_orthographic_map.svg.png"
# Контур России (долгота, широта) — замкнутый полигон по часовой стрелке с северо-запада
RUSSIA_OUTLINE_LONLAT = [
    (19.6, 54.4), (21.1, 55.3), (28.2, 59.9), (30.9, 69.1), (44.2, 76.0), (58.6, 76.5),
    (82.5, 77.6), (104.3, 77.0), (140.0, 75.2), (180.0, 71.5), (180.0, 66.0), (178.0, 62.0),
    (164.0, 55.0), (143.0, 50.0), (135.0, 43.0), (130.0, 42.5), (127.0, 40.0), (113.0, 41.0),
    (87.5, 41.0), (68.0, 45.0), (53.0, 41.2), (39.0, 47.0), (37.5, 46.0), (33.5, 45.2),
    (33.5, 44.4), (36.8, 44.0), (39.0, 43.5), (48.0, 42.0), (47.5, 41.0), (40.0, 41.0),
    (28.0, 41.2), (27.5, 45.0), (19.6, 54.4),
]
MAP_IMG_SIZE = (700, 450)
MAP_EXTENT = (19.0, 41.0, 180.0, 82.0)  # lon_min, lat_min, lon_max, lat_max

def _lonlat_to_xy(lon: float, lat: float) -> tuple:
    """Перевод (долгота, широта) в пиксели для карты России."""
    lon_min, lat_min, lon_max, lat_max = MAP_EXTENT
    w, h = MAP_IMG_SIZE
    x = (lon - lon_min) / (lon_max - lon_min) * w
    y = (lat_max - lat) / (lat_max - lat_min) * h
    return (round(x), round(y))


def _point_in_polygon(px: int, py: int, points: List[Tuple[int, int]]) -> bool:
    """Проверка, лежит ли точка (px, py) внутри многоугольника (points)."""
    n = len(points)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]
        xj, yj = points[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _weather_code_to_icon_type(code: Optional[int]) -> str:
    """Тип иконки погоды по коду WMO: sun, cloud, rain, snow, storm."""
    if code is None:
        return "cloud"
    if code == 0:
        return "sun"
    if code in (1, 2, 3, 45, 48):
        return "cloud"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"


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


def _temp_to_color(temp: Optional[float]) -> Tuple[int, int, int]:
    """Цвет точки по температуре: холодно — синий, тепло — зелёный/жёлтый, жарко — красный."""
    if temp is None:
        return (128, 128, 128)
    t = max(-40, min(40, temp))
    # -40 -> синий (0,80,200), 0 -> голубой (100,180,255), +20 -> зелёный (100,220,100), +40 -> красный (220,60,60)
    if t <= 0:
        k = (t + 40) / 40
        r = int(0 + (100 - 0) * k)
        g = int(80 + (180 - 80) * k)
        b = int(200 + (255 - 200) * k)
    else:
        k = t / 40
        r = int(100 + (220 - 100) * k)
        g = int(180 + (220 - 180) * k)
        b = int(255 + (60 - 255) * k)
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _draw_weather_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, icon_type: str, size: int = 20) -> None:
    """Рисует иконку погоды в центре (cx, cy): солнце, облако, дождь, снег, гроза. Белый цвет на цветном круге."""
    white = (255, 255, 255)
    dark = (55, 60, 80)
    r = size // 2
    L = r + 5
    if icon_type == "sun":
        rays = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
        for dx, dy in rays:
            x2 = cx + int(L * dx * 0.85)
            y2 = cy - int(L * dy * 0.85)
            draw.line([cx, cy, x2, y2], fill=white, width=2)
        draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=white, outline=dark)
    elif icon_type == "cloud":
        draw.ellipse([cx - r - 3, cy + 2, cx - 2, cy + r], fill=white, outline=dark)
        draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=white, outline=dark)
        draw.ellipse([cx + 2, cy - 2, cx + r + 3, cy + r], fill=white, outline=dark)
    elif icon_type == "rain":
        for i in (-1, 0, 1):
            draw.line([cx + i * 5, cy - r, cx + i * 5 + 1, cy + r], fill=white, width=2)
    elif icon_type == "snow":
        for (dx, dy) in [(0, r), (0, -r), (r, 0), (-r, 0), (int(r * 0.7), int(r * 0.7)), (int(-r * 0.7), int(-r * 0.7)), (int(r * 0.7), int(-r * 0.7)), (int(-r * 0.7), int(r * 0.7))]:
            draw.line([cx, cy, cx + dx, cy + dy], fill=white, width=2)
    else:
        draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=white, outline=dark)


def _generate_russia_weather_map_bytes(weather_by_slug: Dict[str, Dict[str, Any]]) -> bytes:
    """Карта России в тёмном стиле: фон по нормальной географической карте + погода по городам."""
    w, h = MAP_IMG_SIZE
    outline_pts = [_lonlat_to_xy(lon, lat) for lon, lat in RUSSIA_OUTLINE_LONLAT]

    # 1) Пытаемся использовать нормальную карту России как фон (аскетичная политическая/географическая карта).
    if os.path.isfile(RUSSIA_WEATHER_MAP_BASE):
        try:
            bg = Image.open(RUSSIA_WEATHER_MAP_BASE).convert("RGB")
            bg = bg.resize((w, h), Image.Resampling.LANCZOS)
        except Exception:
            bg = None
    else:
        bg = None

    # 2) Если файла нет или не загрузился — рисуем аккуратный контур по координатам.
    if bg is None:
        bg = Image.new("RGB", (w, h), (0, 0, 0))
        draw_bg = ImageDraw.Draw(bg)
        draw_bg.polygon(outline_pts, fill=(30, 45, 80), outline=(220, 220, 230), width=2)

    draw = ImageDraw.Draw(bg)
    font = _get_font(11)
    title_font = _get_font(20)

    # Чтобы подписи не наслаивались, будем помнить уже занятые прямоугольники
    label_boxes: List[Tuple[int, int, int, int]] = []

    for idx, city in enumerate(RUSSIAN_MILLION_PLUS_CITIES.values()):
        x, y = _lonlat_to_xy(city.lon, city.lat)
        if not _point_in_polygon(x, y, outline_pts):
            continue
        data = weather_by_slug.get(city.slug)
        temp = data.get("temp") if data else None
        code = data.get("code") if data else None
        color = _temp_to_color(temp)
        # Чуть меньше круги, чтобы не закрывали друг друга
        r_circle = 10
        draw.ellipse([x - r_circle, y - r_circle, x + r_circle, y + r_circle], fill=color, outline=(255, 255, 255), width=2)
        _draw_weather_icon(draw, x, y, _weather_code_to_icon_type(code), size=14)
        label = f"{city.name_ru}"
        if temp is not None:
            label += f" {temp:+.0f}°"
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # Небольшой горизонтальный сдвиг в зависимости от индекса, чтобы подписи в плотных регионах расходились
        jitter = ((idx % 3) - 1) * 10
        tx = max(2, min(w - tw - 2, x - tw // 2 + jitter))
        # Базовая позиция — под точкой
        ty = min(h - th - 2, y + r_circle + 3)

        # Попробуем несколько раз сдвинуть подпись, чтобы не пересекаться с уже размещёнными
        # Сдвигаем вниз, а если дошли до низа — ставим над точкой.
        def _intersects(a, b):
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)

        box = (tx, ty, tx + tw, ty + th)
        for _ in range(6):
            if any(_intersects(box, other) for other in label_boxes):
                new_ty = ty + th + 2
                if new_ty + th > h - 2:
                    # Места снизу нет — пробуем над точкой
                    new_ty = max(2, y - r_circle - th - 3)
                ty = new_ty
                box = (tx, ty, tx + tw, ty + th)
            else:
                break

        label_boxes.append(box)
        draw.text((tx, ty), label, fill=(240, 240, 245), font=font)

    title = "Погода по регионам России"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, 10), title, fill=(240, 240, 245), font=title_font)

    buf = io.BytesIO()
    bg.save(buf, format="PNG")
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
    """Список имён файлов картинок для города: 5 фото исторического центра (красота города, без промышленных) + до 3 достопримечательностей."""
    return [
        f"historic_{city.slug}.png",
        f"historic_{city.slug}_2.png",
        f"historic_{city.slug}_3.png",
        f"historic_{city.slug}_4.png",
        f"historic_{city.slug}_5.png",
        f"historic_{city.slug}_6.png",
        f"historic_{city.slug}_7.png",
        f"historic_{city.slug}_8.png",
        f"historic_{city.slug}_9.png",
        f"historic_{city.slug}_10.png",
        f"landmark_{city.slug}_1.png",
        f"landmark_{city.slug}_2.png",
        f"landmark_{city.slug}_3.png",
    ]


# Пошаговая ротация: каждый запрос — следующее фото по кругу, картинки не повторяются подряд
_city_image_rotation_index: Dict[str, int] = {}
_city_image_lock = threading.Lock()


def _get_random_city_image_bytes(
    city: City,
    user_data: Optional[Dict[str, Any]] = None,
    chat_id: Optional[int] = None,
) -> bytes:
    """Возвращает байты картинки города; строгая ротация — каждый запрос следующее фото, без повторов подряд."""
    assets_dir = os.path.join(_script_dir, "assets")
    names = _city_image_candidates(city)
    candidates = [
        (name, os.path.join(assets_dir, name))
        for name in names
        if os.path.isfile(os.path.join(assets_dir, name))
    ]
    if not candidates:
        return _generate_historic_center_image(city)
    with _city_image_lock:
        idx = _city_image_rotation_index.get(city.slug, 0)
        _city_image_rotation_index[city.slug] = (idx + 1) % len(candidates)
    chosen_name, path = candidates[idx]
    logger.info("Фото города %s: найдено %s, показано №%s (%s)", city.slug, len(candidates), idx + 1, chosen_name)
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

# Эмодзи для сообщения о погоде (по коду WMO) — сочный дизайн
WEATHER_EMOJI: Dict[int, str] = {
    0: "☀️",
    1: "🌤",
    2: "⛅",
    3: "☁️",
    45: "🌫",
    48: "🌫",
    51: "🌧",
    53: "🌧",
    55: "🌧",
    61: "🌧",
    63: "🌧",
    65: "⛈",
    71: "❄️",
    73: "❄️",
    75: "❄️",
    77: "❄️",
    80: "🌦",
    81: "🌦",
    82: "⛈",
    85: "❄️",
    86: "❄️",
    95: "⛈",
    96: "⛈",
    99: "⛈",
}


def _weather_emoji(code: Optional[int]) -> str:
    """Эмодзи погоды для текста сообщения."""
    if code is not None and code in WEATHER_EMOJI:
        return WEATHER_EMOJI[code]
    return "🌡️"


def _weather_mood(temp: Optional[float]) -> str:
    """Короткая «настроение» по температуре для сочного текста."""
    if temp is None:
        return ""
    if temp < -15:
        return "🥶 Довольно холодно — теплее одевайтесь!"
    if temp < 0:
        return "🧣 Прохладно — захватите шарф."
    if temp < 15:
        return "🍂 Комфортная погода для прогулки."
    if temp < 25:
        return "🌸 Тепло и уютно — отличный денёк!"
    return "🌞 Жарко — не забудьте воду и головной убор."


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


# Названия месяцев и дней недели для вывода местного времени
_MONTHS_RU = ("января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря")
_WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def _format_local_time_from_iso(iso_time_str: Optional[str]) -> Optional[str]:
    """Форматирует местное время из строки ISO в «ЧЧ:ММ, пн, 26 февраля 2026 г.»."""
    if not iso_time_str or "T" not in iso_time_str:
        return None
    try:
        part = iso_time_str.split("T")[0] + " " + iso_time_str.split("T")[1][:5]
        dt = datetime.strptime(part, "%Y-%m-%d %H:%M")
        wd = _WEEKDAYS_RU[dt.weekday()]
        month = _MONTHS_RU[dt.month - 1]
        return f"{dt.strftime('%H:%M')}, {wd}, {dt.day} {month} {dt.year} г."
    except (ValueError, IndexError):
        return None


# Внешний API местного времени (источник — не UTC, а время по поясу города)
WORLD_TIME_API_URL = "http://worldtimeapi.org/api/timezone/{tz}"


async def _fetch_local_time_from_api(tz_name: str) -> Optional[str]:
    """Запрашивает местное время по IANA timezone у WorldTimeAPI. Возвращает строку для подписи или None."""
    url = WORLD_TIME_API_URL.format(tz=tz_name)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        dt_str = data.get("datetime")
        if dt_str:
            return _format_local_time_from_iso(dt_str)
        return None
    except Exception:
        return None


def _city_local_time_str_fallback(city: City) -> str:
    """Местное время по смещению от UTC (без ZoneInfo, без слова UTC в выводе)."""
    offset_h = CITY_UTC_OFFSET_HOURS.get(city.slug, 3)
    utc_now = datetime.now(timezone.utc)
    local = utc_now + timedelta(hours=offset_h)
    wd = _WEEKDAYS_RU[local.weekday()]
    month = _MONTHS_RU[local.month - 1]
    return f"{local.strftime('%H:%M')}, {wd}, {local.day} {month} {local.year} г."


async def get_weather(city: City) -> str:
    url = "https://api.open-meteo.com/v1/forecast"
    tz_name = CITY_TIMEZONES.get(city.slug, "Europe/Moscow")
    params = {
        "latitude": str(city.lat),
        "longitude": str(city.lon),
        "current": "temperature_2m,relative_humidity_2m,weather_code,surface_pressure,wind_speed_10m",
        "timezone": tz_name,
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
    # Источник времени: 1) WorldTimeAPI (местное по поясу), 2) Open-Meteo current.time, 3) UTC+смещение (без слова UTC)
    tz_name = CITY_TIMEZONES.get(city.slug, "Europe/Moscow")
    local_time_str = await _fetch_local_time_from_api(tz_name)
    if not local_time_str and cur.get("time"):
        local_time_str = _format_local_time_from_iso(cur.get("time"))
    if not local_time_str:
        local_time_str = _city_local_time_str_fallback(city)

    # Пояс: смещение от UTC
    offset_h = CITY_UTC_OFFSET_HOURS.get(city.slug, 3)
    tz_hint = f" (GMT+{offset_h})"
    emoji = _weather_emoji(code)
    desc_cap = desc.capitalize()
    mood = _weather_mood(temp)

    # Красивый сочный дизайн: заголовок, время, блок показателей, настроение
    temp_str = f"{temp:+.0f}°C" if temp is not None else "—"
    lines: List[str] = [
        "✦━━━━━━━━━━━━━━━━━━━━✦",
        f"{emoji} *Погода · {city.name_ru}*",
        "✦━━━━━━━━━━━━━━━━━━━━✦",
        "",
        f"🕐 _Местное время{tz_hint}_",
        f"   {local_time_str}",
        "",
        "────────────────────",
        f"🌡 *Температура:* {temp_str}",
        f"{emoji} *{desc_cap}*",
        "────────────────────",
    ]
    extra: List[str] = []
    if humidity is not None:
        extra.append(f"💧 {humidity}%")
    if pressure is not None:
        extra.append(f"📊 {pressure} hPa")
    if wind_speed is not None:
        extra.append(f"💨 {wind_speed} км/ч")
    if extra:
        lines.append("  " + "  ·  ".join(extra))
    if mood:
        lines.append("")
        lines.append("────────────────────")
        lines.append(mood)
    return "\n".join(lines)


async def get_weather_data(city: City) -> Optional[Dict[str, Any]]:
    """Возвращает сырые данные погоды для города (temp, code, desc) или None при ошибке."""
    url = "https://api.open-meteo.com/v1/forecast"
    tz_name = CITY_TIMEZONES.get(city.slug, "Europe/Moscow")
    params = {
        "latitude": str(city.lat),
        "longitude": str(city.lon),
        "current": "temperature_2m,weather_code",
        "timezone": tz_name,
    }
    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, url, params)
    if not data or "current" not in data:
        return None
    cur = data["current"]
    temp = cur.get("temperature_2m")
    code = cur.get("weather_code")
    return {
        "temp": temp,
        "code": code,
        "desc": _weather_desc(code),
    }


async def get_all_cities_weather() -> Dict[str, Dict[str, Any]]:
    """Параллельно запрашивает погоду по всем городам. Ключ — slug города."""
    result: Dict[str, Dict[str, Any]] = {}
    tasks = [get_weather_data(c) for c in RUSSIAN_MILLION_PLUS_CITIES.values()]
    done = await asyncio.gather(*tasks, return_exceptions=True)
    for city, out in zip(RUSSIAN_MILLION_PLUS_CITIES.values(), done):
        if isinstance(out, dict):
            result[city.slug] = out
        elif isinstance(out, Exception):
            logger.debug("Weather for %s: %s", city.slug, out)
    return result


# ---- Ежедневная рассылка погоды (утро/день/вечер/ночь) ----
SUBSCRIPTIONS_FILE = os.path.join(_script_dir, "data", "weather_reminders.json")

# Часовые пояса для выбора пользователем (рассылка в его местном времени). Формат: (подпись, IANA).
REMINDER_TIMEZONES: List[Tuple[str, str]] = [
    ("Калининград (UTC+2)", "Europe/Kaliningrad"),
    ("Москва (UTC+3)", "Europe/Moscow"),
    ("Самара (UTC+4)", "Europe/Samara"),
    ("Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
    ("Омск (UTC+6)", "Asia/Omsk"),
    ("Новосибирск / Томск (UTC+7)", "Asia/Novosibirsk"),
    ("Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
    ("Иркутск (UTC+8)", "Asia/Irkutsk"),
    ("Якутск (UTC+9)", "Asia/Yakutsk"),
    ("Владивосток (UTC+10)", "Asia/Vladivostok"),
    ("Магадан (UTC+11)", "Asia/Magadan"),
    ("Камчатка (UTC+12)", "Asia/Kamchatka"),
]


def _load_subscriptions() -> List[Dict[str, Any]]:
    """Загружает список подписок. Ключи: user_id, chat_id, city_slug, time, tz (IANA)."""
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_FILE), exist_ok=True)
        if os.path.isfile(SUBSCRIPTIONS_FILE):
            with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("subscriptions", [])
    except Exception as e:
        logger.warning("Load subscriptions: %s", e)
    return []


def _save_subscriptions(subs: List[Dict[str, Any]]) -> None:
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_FILE), exist_ok=True)
        with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscriptions": subs}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Save subscriptions: %s", e)


def add_reminder(chat_id: int, user_id: int, city_slug: str, time_str: str, tz: str = "Europe/Moscow") -> None:
    """Добавляет или обновляет напоминание. time_str приводится к «HH:MM», tz = IANA (местное время пользователя)."""
    time_str = _normalize_time_str(time_str)
    subs = _load_subscriptions()
    subs = [s for s in subs if not (s["chat_id"] == chat_id and s["city_slug"] == city_slug)]
    subs.append({"user_id": user_id, "chat_id": chat_id, "city_slug": city_slug, "time": time_str, "tz": tz})
    _save_subscriptions(subs)


def remove_reminder(chat_id: int, city_slug: str) -> bool:
    """Удаляет напоминание. Возвращает True если была запись."""
    subs = _load_subscriptions()
    before = len(subs)
    subs = [s for s in subs if not (s["chat_id"] == chat_id and s["city_slug"] == city_slug)]
    if len(subs) < before:
        _save_subscriptions(subs)
        return True
    return False


def _normalize_time_str(raw: str) -> str:
    """Приводит время к формату HH:MM (например «9:0» -> «09:00») для надёжного сравнения."""
    if not raw or not raw.strip():
        return "08:00"
    raw = raw.strip()
    parts = raw.split(":")
    try:
        h = int(parts[0].strip()) if parts else 0
        m = int(parts[1].strip()) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return "08:00"
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return f"{h:02d}:{m:02d}"


def get_reminders_to_send_now() -> List[Tuple[int, str]]:
    """Список (chat_id, city_slug) подписок, у которых сейчас в их часовом поясе наступило время рассылки."""
    subs = _load_subscriptions()
    result: List[Tuple[int, str]] = []
    for s in subs:
        tz_name = s.get("tz") or "Europe/Moscow"
        try:
            now_local = datetime.now(ZoneInfo(tz_name))
        except Exception:
            continue
        current_time = f"{now_local.hour:02d}:{now_local.minute:02d}"
        sub_time = _normalize_time_str(s.get("time") or "08:00")
        if sub_time == current_time:
            result.append((s["chat_id"], s["city_slug"]))
    return result


def get_user_reminders(user_id: int) -> List[Dict[str, Any]]:
    """Подписки пользователя: список dict с city_slug, time, tz."""
    subs = _load_subscriptions()
    return [
        {"city_slug": s["city_slug"], "time": s.get("time", "?"), "tz": s.get("tz", "Europe/Moscow")}
        for s in subs if s.get("user_id") == user_id
    ]


async def get_daily_weather_forecast(city: City) -> str:
    """Прогноз на день: ночь, утро, день, вечер (температура и описание) в местном времени города."""
    url = "https://api.open-meteo.com/v1/forecast"
    tz_name = CITY_TIMEZONES.get(city.slug, "Europe/Moscow")
    params = {
        "latitude": str(city.lat),
        "longitude": str(city.lon),
        "hourly": "temperature_2m,weather_code",
        "timezone": tz_name,
        "forecast_days": 2,
    }
    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, url, params)
    if not data or "hourly" not in data:
        return "Не удалось загрузить прогноз. Попробуйте позже."

    hours = data["hourly"].get("time", [])
    temps = data["hourly"].get("temperature_2m", [])
    codes = data["hourly"].get("weather_code", [])
    if not hours or not temps:
        return "Нет данных прогноза."

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    today = now.date()
    if now.hour >= 22:
        target_date = today + timedelta(days=1)
    else:
        target_date = today

    def slot(hour_rep: int, label: str) -> str:
        """Представительный час для слота: 3=ночь, 9=утро, 15=день, 21=вечер."""
        for i, t in enumerate(hours):
            try:
                raw = t.replace("Z", "+00:00")
                if "+" not in raw and raw.count("-") >= 2:
                    dt = datetime.fromisoformat(raw).replace(tzinfo=tz)
                else:
                    dt = datetime.fromisoformat(raw).astimezone(tz)
                if dt.date() == target_date and dt.hour == hour_rep:
                    temp = temps[i] if i < len(temps) else None
                    code = codes[i] if i < len(codes) else None
                    desc = _weather_desc(code)
                    temp_str = f"{temp:+.0f}°C" if temp is not None else "—"
                    return f"  {label}: {temp_str}, {desc}"
            except (ValueError, IndexError, TypeError):
                continue
        return f"  {label}: —"

    night = slot(3, "Ночь")
    morning = slot(9, "Утро")
    day_s = slot(15, "День")
    evening = slot(21, "Вечер")

    date_label = "завтра" if target_date != today else "на сегодня"
    lines = [
        "✦━━━━━━━━━━━━━━━━━━━━✦",
        f"⏰ *Прогноз на день · {city.name_ru}*",
        "✦━━━━━━━━━━━━━━━━━━━━✦",
        "",
        night,
        morning,
        day_s,
        evening,
        "",
        f"_Местное время города ({date_label})._",
    ]
    return "\n".join(lines)


async def get_weekly_weather_forecast(city: City) -> str:
    """Прогноз на 7 дней вперёд по городу: ночь, утро, день, вечер для каждого дня."""
    url = "https://api.open-meteo.com/v1/forecast"
    tz_name = CITY_TIMEZONES.get(city.slug, "Europe/Moscow")
    params = {
        "latitude": str(city.lat),
        "longitude": str(city.lon),
        "hourly": "temperature_2m,weather_code",
        "timezone": tz_name,
        "forecast_days": 7,
    }
    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, url, params)
    if not data or "hourly" not in data:
        return "Не удалось загрузить прогноз на 7 дней. Попробуйте позже."

    hours = data["hourly"].get("time", [])
    temps = data["hourly"].get("temperature_2m", [])
    codes = data["hourly"].get("weather_code", [])
    if not hours or not temps:
        return "Нет данных прогноза на 7 дней."

    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    # Сгруппируем почасовые данные по дате и часу.
    by_date: Dict[Any, Dict[int, Tuple[Optional[float], Any]]] = {}
    for i, t in enumerate(hours):
        try:
            raw = t.replace("Z", "+00:00")
            if "+" not in raw and raw.count("-") >= 2:
                dt = datetime.fromisoformat(raw).replace(tzinfo=tz)
            else:
                dt = datetime.fromisoformat(raw).astimezone(tz)
        except Exception:
            continue
        d = dt.date()
        if d not in by_date:
            by_date[d] = {}
        temp = temps[i] if i < len(temps) else None
        code = codes[i] if i < len(codes) else None
        by_date[d][dt.hour] = (temp, code)

    # Выберем до 7 ближайших дней, для которых есть данные.
    target_dates = []
    for offset in range(7):
        d = today + timedelta(days=offset)
        if d in by_date:
            target_dates.append(d)
    if not target_dates:
        return "Нет данных прогноза на 7 дней."

    def slot_for_date(d, hour_rep: int, label: str) -> str:
        """Берёт температуру и код погоды для указанного часа (или ближайшего к нему)."""
        hours_map = by_date.get(d) or {}
        if hour_rep in hours_map:
            temp, code = hours_map[hour_rep]
        else:
            # Поиск ближайшего часа в пределах ±2 часов.
            best = None
            for delta in range(1, 3):
                for h_try in (hour_rep - delta, hour_rep + delta):
                    if h_try in hours_map:
                        best = hours_map[h_try]
                        break
                if best is not None:
                    break
            if best is None:
                return f"  {label}: —"
            temp, code = best
        desc = _weather_desc(code)
        temp_str = f"{temp:+.0f}°C" if temp is not None else "—"
        return f"  {label}: {temp_str}, {desc}"

    def format_date(d) -> str:
        wd = _WEEKDAYS_RU[d.weekday()]
        return f"*{wd} {d.day:02d}.{d.month:02d}*"

    lines: List[str] = [
        "📅━━━━━━━━━━━━━━━━━━━━📅",
        f"*Прогноз на 7 дней · {city.name_ru}*",
        "📅━━━━━━━━━━━━━━━━━━━━📅",
        "",
    ]
    for d in target_dates:
        lines.append(format_date(d))
        lines.append(slot_for_date(d, 3, "Ночь"))
        lines.append(slot_for_date(d, 9, "Утро"))
        lines.append(slot_for_date(d, 15, "День"))
        lines.append(slot_for_date(d, 21, "Вечер"))
        lines.append("")

    lines.append("_Местное время города._")
    return "\n".join(lines)


async def reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Раз в минуту проверяет местное время каждого подписчика и отправляет рассылку."""
    to_send = get_reminders_to_send_now()
    for chat_id, city_slug in to_send:
        city = RUSSIAN_MILLION_PLUS_CITIES.get(city_slug)
        if not city:
            continue
        try:
            text = await get_daily_weather_forecast(city)
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info("Reminder sent chat_id=%s city_slug=%s", chat_id, city_slug)
        except Exception as e:
            logger.warning("Reminder send to %s for %s: %s", chat_id, city_slug, e)


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


# Новости только за последние N дней (для региональных лент — до 14 дней, чтобы не терять редкие обновления)
NEWS_DAYS_BACK = 14

# Гарантированные федеральные RSS: если по городу ничего не нашли — тянем отсюда (всегда что-то будет)
GUARANTEED_RSS_FEEDS: List[str] = [
    "https://ria.ru/export/rss2/index.xml",
    "https://tass.ru/rss/v2.xml",
    "https://www.interfax.ru/rss.asp",
    "https://lenta.ru/rss/news",
    "https://lenta.ru/rss/news/russia",
]

# User-Agent для запросов к RSS-мостам (Telegram/VK в RSS), чтобы реже получать отказ
RSS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_rss_from_url(feed_url: str, max_fetch: int = 30) -> List[NewsItem]:
    """Загружает новости из одной RSS-ленты. Возвращает (title, link, description, pub_ts)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                feed_url,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": RSS_USER_AGENT},
            ) as resp:
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
        for feed_url in GUARANTEED_RSS_FEEDS + RSS_FEEDS:
            try:
                async with session.get(
                    feed_url,
                    timeout=aiohttp.ClientTimeout(total=20),
                    headers={"User-Agent": RSS_USER_AGENT},
                ) as resp:
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
        # Fallback: сначала GUARANTEED_RSS_FEEDS (РИА, ТАСС, Интерфакс, Lenta), потом RSS_FEEDS
        async with aiohttp.ClientSession() as session:
            for feed_url in GUARANTEED_RSS_FEEDS + RSS_FEEDS:
                try:
                    async with session.get(
                        feed_url,
                        timeout=aiohttp.ClientTimeout(total=20),
                        headers={"User-Agent": RSS_USER_AGENT},
                    ) as resp:
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


# Доп. ключевые слова для поиска (падежи, сокращения, регион) — чтобы находить больше новостей по городу
CITY_EXTRA_KEYWORDS: Dict[str, List[str]] = {
    "moscow": ["в Москве", "Москвы", "москвич", "столиц", "Московск"],
    "spb": ["СПб", "Питер", "Санкт-Петербург", "в Петербурге", "Петербурга", "Ленинград"],
    "novosibirsk": ["в Новосибирске", "Новосибирска", "Новосибирск", "Новосибирской"],
    "yekaterinburg": ["Екатеринбурге", "Екб", "Свердловск", "в Екатеринбурге", "Свердловской"],
    "nizhny_novgorod": ["Нижнем Новгороде", "Нижегородск", "Нижнего Новгорода", "Нижегородской"],
    "kazan": ["в Казани", "Казани", "Татарстан", "Татарстане"],
    "chelyabinsk": ["в Челябинске", "Челябинска", "Челябинск", "Челябинской", "Челябинская обл"],
    "omsk": ["в Омске", "Омска", "Омск", "Омской"],
    "samara": ["в Самаре", "Самары", "Самарск", "Самарской"],
    "rostov_on_don": ["Ростове-на-Дону", "Ростова-на-Дону", "в Ростове", "Ростовской", "Ростов-на-Дону"],
    "ufa": ["в Уфе", "Уфы", "Башкортостан", "Башкири"],
    "krasnoyarsk": ["в Красноярске", "Красноярска", "Красноярск", "Красноярского края"],
    "perm": ["в Перми", "Перми", "Пермск", "Пермского края"],
    "voronezh": ["в Воронеже", "Воронежа", "Воронежск", "Воронежской"],
    "volgograd": ["в Волгограде", "Волгограда", "Волгоградск", "Волгоградской"],
    "krasnodar": ["в Краснодаре", "Краснодара", "Кубан", "Краснодарского края"],
    "saratov": ["в Саратове", "Саратова", "Саратовск", "Саратовской"],
    "tyumen": ["в Тюмени", "Тюмени", "Тюменск", "Тюменской"],
    "tolyatti": ["в Тольятти", "Тольятти", "Самарской"],
    "izhevsk": ["в Ижевске", "Ижевска", "Удмурт", "Удмуртии"],
    "barnaul": ["в Барнауле", "Барнаула", "Алтайск", "Алтайского края"],
    "ulyanovsk": ["в Ульяновске", "Ульяновска", "Ульяновской"],
    "irkutsk": ["в Иркутске", "Иркутска", "Байкал", "Иркутской"],
    "khabarovsk": ["в Хабаровске", "Хабаровска", "Хабаровск", "Хабаровского края"],
    "vladivostok": ["во Владивостоке", "Владивостока", "Приморь", "Приморского края"],
    "mahachkala": ["в Махачкале", "Махачкалы", "Дагестан", "Дагестана"],
    "yaroslavl": ["в Ярославле", "Ярославля", "Ярославской"],
    "stavropol": ["в Ставрополе", "Ставрополя", "Ставропольский край"],
    "sevastopol": ["в Севастополе", "Севастополя", "Крым"],
    "naberezhnye_chelny": ["Набережные Челны", "Челны", "Татарстан"],
    "tomsk": ["в Томске", "Томска", "Томской"],
    "balashikha": ["Балашиха", "Подмосковье", "Московская область"],
    "kemerovo": ["в Кемерове", "Кемерово", "Кузбасс", "Кемеровской"],
    "orenburg": ["в Оренбурге", "Оренбурга", "Оренбургской"],
    "novokuznetsk": ["в Новокузнецке", "Новокузнецка", "Кузбасс"],
    "ryazan": ["в Рязани", "Рязани", "Рязанской"],
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


def _dzen_news_link(city: City) -> str:
    """Ссылка на новости в Дзене по названию города (поиск)."""
    q = quote(city.name_ru, safe="")
    return f"https://dzen.ru/news/search?query={q}"


def _is_junk_news_title(title: str) -> bool:
    """Заголовки-не новости (кнопки, служебный текст) — не показывать в списке."""
    if not title or not title.strip():
        return True
    t = title.strip().lower()
    if t == "показать все источники":
        return True
    if "показать все источники" in t:
        return True
    return False


# Дзен: реальная выгрузка статей через браузер (Playwright) + опционально 2Captcha. Скрипт dzen_scraper.py.
async def _fetch_dzen_news_for_city(city_name: str, limit: int = 5) -> List[Tuple[str, str]]:
    """Загружает новости из Дзена по городу через Playwright (и при капче — 2Captcha, если задан ключ)."""
    try:
        from dzen_scraper import fetch_dzen_news_for_city as fetch_dzen_playwright
        return await fetch_dzen_playwright(city_name, limit=limit)
    except ImportError:
        logger.debug("dzen_scraper/Playwright не установлены — новости Дзена через браузер недоступны")
        return []
    except Exception as exc:
        logger.debug("Dzen Playwright для %s: %s", city_name, exc)
        return []


async def get_city_news(city: City, limit: int = 5) -> str:
    dzen_line = ""  # Ссылка «Ещё в Дзене» убрана по запросу
    # Дзен — с таймаутом, чтобы не блокировать ответ (Playwright может зависать 10–20 сек).
    try:
        dzen_items = await asyncio.wait_for(
            _fetch_dzen_news_for_city(city.name_ru, limit=limit),
            timeout=14.0,
        )
    except asyncio.TimeoutError:
        logger.debug("Dzen timeout для %s", city.name_ru)
        dzen_items = []
    except Exception as exc:
        logger.debug("Dzen для %s: %s", city.name_ru, exc)
        dzen_items = []

    city_feeds = CITY_RSS_FEEDS.get(city.slug, [])
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS_BACK)).timestamp()
    city_items: List[NewsItem] = []
    seen_links: set = set()
    for feed_url in city_feeds:
        raw_city = await _fetch_rss_from_url(feed_url, max_fetch=30)
        if raw_city:
            _merge_news_items(city_items, raw_city, seen_links, cutoff_ts)
    if not city_items:
        fallback_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
        for feed_url in GUARANTEED_RSS_FEEDS:
            raw_guaranteed = await _fetch_rss_from_url(feed_url, max_fetch=40)
            if raw_guaranteed:
                _merge_news_items(city_items, raw_guaranteed, seen_links, fallback_cutoff)

    # В блок «Новости по городу X» — только то, что реально про город: Дзен (поиск по городу) + RSS с упоминанием города/региона
    city_filtered = _filter_news_by_city(city_items, city, limit=limit * 2) if city_items else []
    combined: List[Tuple[str, str]] = []
    seen = set()
    for title, link in dzen_items:
        if link and link not in seen and not _is_junk_news_title(title):
            combined.append((title, link))
            seen.add(link)
    for title, link in city_filtered:
        if link and link not in seen and len(combined) < limit * 2 and not _is_junk_news_title(title):
            combined.append((title, link))
            seen.add(link)

    if combined:
        show = [x for x in combined[: limit * 2] if not _is_junk_news_title(x[0])][:limit]
        lines: List[str] = [f"📰 Новости по городу {city.name_ru}:"]
        for idx, (title, link) in enumerate(show, start=1):
            lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
        return "\n".join(lines) + dzen_line

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
            articles = [a for a in data.get("articles", []) if not _is_junk_news_title(a.get("title") or "")][:limit]
            if articles:
                lines = [f"📰 Новости по городу {city.name_ru}:"]
                for idx, art in enumerate(articles, start=1):
                    title = art.get("title") or "Без заголовка"
                    url_art = art.get("url")
                    source = (art.get("source") or {}).get("name") or "Источник"
                    if url_art:
                        lines.append(f"{idx}. [{title}]({url_art}) — _{source}_")
                    else:
                        lines.append(f"{idx}. {title} — _{source}_")
                return "\n".join(lines) + dzen_line

    raw = await _fetch_rss_news_raw(max_fetch=600)
    if not raw:
        return "📰 Не удалось загрузить новости. Попробуйте позже." + dzen_line
    by_city = _filter_news_by_city(raw, city, limit=limit)
    by_city = [(t, l) for t, l in by_city if not _is_junk_news_title(t)]
    if by_city:
        lines = [f"📰 Новости по городу {city.name_ru} (за неделю):"]
        for idx, (title, link) in enumerate(by_city[:limit], start=1):
            lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
        return "\n".join(lines) + dzen_line
    # По городу не найдено — показываем общие новости (всегда что-то показываем)
    general_limit = max(limit, 8)
    general = [(t[0], t[1]) for t in raw[: general_limit * 2] if not _is_junk_news_title(t[0])][:general_limit]
    lines = [f"📰 Новости по городу {city.name_ru} (общая лента России):"]
    for idx, (title, link) in enumerate(general, start=1):
        lines.append(f"{idx}. [{title}]({link})" if link else f"{idx}. {title}")
    return "\n".join(lines) + dzen_line


async def get_city_news_safe(city: City, limit: int = 5) -> str:
    """Обёртка: при любой ошибке возвращает хотя бы сообщение."""
    try:
        return await get_city_news(city, limit=limit)
    except Exception as exc:
        logger.exception("get_city_news %s: %s", city.name_ru, exc)
        return f"📰 Не удалось загрузить новости по городу {city.name_ru}. Попробуйте позже."


# Тексты кнопок меню (одинаковые для inline и reply-клавиатуры)
MENU_BTN_HELP = "❓ Справка"
MENU_BTN_CITY = "🏙 Выбор города"
MENU_BTN_WEATHER = "🌤 Погода"
MENU_BTN_NEWS = "📰 Новости"
MENU_BTN_START = "🗺 Старт и карта"
MENU_BTN_MAP = "🌡 Карта погоды"
MENU_BTN_MENU = "📋 Меню"
MENU_BTN_GAME = "🎮 Pac-Man"
MENU_BTN_WEATHER_APP = "🌐 Погода (приложение)"
MENU_BTN_REMIND = "⏰ Напоминание о погоде"

MENU_BUTTON_TEXTS = frozenset(
    {MENU_BTN_HELP, MENU_BTN_CITY, MENU_BTN_WEATHER, MENU_BTN_NEWS, MENU_BTN_START, MENU_BTN_MAP, MENU_BTN_MENU, MENU_BTN_GAME, MENU_BTN_WEATHER_APP, MENU_BTN_REMIND}
)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Блок меню (inline): сетка кнопок + при необходимости кнопка мини-приложения погоды."""
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
            InlineKeyboardButton(MENU_BTN_MAP, callback_data="menu:map"),
        ],
        [
            InlineKeyboardButton(MENU_BTN_MENU, callback_data="menu:menu"),
            InlineKeyboardButton(MENU_BTN_GAME, callback_data="menu:game"),
        ],
        [
            InlineKeyboardButton(MENU_BTN_REMIND, callback_data="menu:remind"),
        ],
    ]
    if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
        buttons.append([
            InlineKeyboardButton(MENU_BTN_WEATHER_APP, web_app=WebAppInfo(url=WEATHER_APP_URL)),
        ])
    return InlineKeyboardMarkup(buttons)


def build_reply_menu_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура внизу экрана (блок меню под полем ввода)."""
    keyboard = [
        [KeyboardButton(MENU_BTN_HELP), KeyboardButton(MENU_BTN_CITY)],
        [KeyboardButton(MENU_BTN_WEATHER), KeyboardButton(MENU_BTN_NEWS)],
        [KeyboardButton(MENU_BTN_START), KeyboardButton(MENU_BTN_MAP)],
        [KeyboardButton(MENU_BTN_MENU), KeyboardButton(MENU_BTN_GAME)],
        [KeyboardButton(MENU_BTN_REMIND)],
    ]
    if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
        keyboard.append([KeyboardButton(MENU_BTN_WEATHER_APP)])
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def build_cities_keyboard(prefix: str = "city") -> InlineKeyboardMarkup:
    """Клавиатура: только 10 крупнейших городов + кнопка «Поиск города». Остальные — через лупу."""
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for slug in TOP_10_CITY_SLUGS:
        city = RUSSIAN_MILLION_PLUS_CITIES.get(slug)
        if not city:
            continue
        row.append(
            InlineKeyboardButton(text=city.name_ru, callback_data=f"{prefix}:{city.slug}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔍 Поиск города", callback_data=f"search:{prefix}")])
    return InlineKeyboardMarkup(buttons)


def search_cities_by_query(query: str, limit: int = 15) -> List[City]:
    """Ищет города по названию (погода и новости — по всему списку 500k+)."""
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip().lower()
    out: List[City] = []
    for city in RUSSIAN_MILLION_PLUS_CITIES.values():
        if q in city.name_ru.lower() or q in city.name_en.lower() or q in city.slug.replace("_", " "):
            out.append(city)
        if len(out) >= limit:
            break
    return out


def build_search_results_keyboard(cities: List[City], prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура с результатами поиска городов."""
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for city in cities:
        row.append(InlineKeyboardButton(text=city.name_ru, callback_data=f"{prefix}:{city.slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_remind_tz_keyboard(city_slug: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора часового пояса пользователя (рассылка в его местном времени)."""
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for label, tz_id in REMINDER_TIMEZONES:
        # callback_data до 64 байт. Используем | между частями (tz содержит : и /)
        row.append(InlineKeyboardButton(text=label, callback_data=f"remind_tz:{city_slug}|{tz_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_remind_time_keyboard(city_slug: str, tz_id: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора времени рассылки (в местном времени пользователя)."""
    times = ["06:00", "07:00", "08:00", "09:00", "12:00", "18:00", "20:00"]
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for t in times:
        row.append(InlineKeyboardButton(text=t, callback_data=f"remind_time:{city_slug}|{tz_id}|{t}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏ Другое время (ЧЧ:ММ)", callback_data=f"remind_custom:{city_slug}|{tz_id}")])
    return InlineKeyboardMarkup(buttons)


async def send_weather_only(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Только погода по городу (каждый запрос — другая картинка из папки города)."""
    try:
        img_bytes = _get_random_city_image_bytes(city, chat_id=chat_id)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(io.BytesIO(img_bytes), filename=f"{city.slug}.png"),
            caption=f"🏛 {city.name_ru}",
        )
    except Exception as exc:
        logger.warning("Historic center image for %s: %s", city.slug, exc)
    weather_text = await get_weather(city)
    # Кнопка для показа прогноза на 7 дней по запросу пользователя.
    weekly_btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📅 Показать погоду на 7 дней", callback_data=f"weekly:{city.slug}")]]
    )
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=weather_text,
            reply_markup=weekly_btn,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=weather_text,
            reply_markup=weekly_btn,
        )


async def send_news_only(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Только новости по городу."""
    news_text = await get_city_news_safe(city)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=news_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False,
        )
    except Exception as exc:
        logger.warning("send_news_only Markdown failed, sending plain: %s", exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text=news_text,
            disable_web_page_preview=False,
        )


async def send_weather_map(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Генерирует и отправляет карту России с погодой по регионам (городам-миллионникам)."""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Загружаю погоду по регионам России…",
        )
        weather_by_slug = await get_all_cities_weather()
        map_bytes = _generate_russia_weather_map_bytes(weather_by_slug)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(io.BytesIO(map_bytes), filename="map_weather.png"),
            caption="🌡 Погода по регионам России (города 500 тыс.+). Цвет круга — температура, иконка — погода (☀️ ясно, ☁️ облачно, 🌧 дождь, ❄️ снег).",
        )
    except Exception as exc:
        logger.exception("Карта погоды: %s", exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось построить карту погоды. Попробуйте позже.",
        )


async def send_city_info(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, city: City
) -> None:
    """Погода и новости вместе (для выбора города из /start или /city)."""
    await send_weather_only(context, chat_id, city)
    await send_news_only(context, chat_id, city)


# Метка версии: если пользователь видит это в чате — бот запущен из ЭТОГО кода (tg bot2 / russian-weather-tg-bot)
_START_VERSION_MARKER = "Версия 2.0 • tg bot2 • 27.02.2025"

async def _send_start_content(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Отправляет карту России и блок меню. Меню внизу экрана отправляется отдельным сообщением для надёжного отображения."""
    caption = (
        f"🗺 **Карта России** • {_START_VERSION_MARKER}\n\n"
        "Привет! Я бот погоды и новостей по городам России (500 тыс.+ жителей).\n\n"
        "**Команды:** /start — старт и карта, /menu — меню, /city — выбор города, "
        "/weather — погода, /news — новости, /help — справка.\n\n"
        "⬇️ **Под картой придёт сообщение с кнопками меню** (Справка, Выбор города, Погода, Новости и др.) — они закрепятся внизу экрана."
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
            await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN)
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
            await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN)

    # Блок меню внизу экрана — отдельным сообщением (так клавиатура гарантированно показывается во всех клиентах)
    await context.bot.send_message(
        chat_id=chat_id,
        text="📋 **Меню** — нажмите одну из кнопок внизу экрана:",
        reply_markup=build_reply_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    # Inline-кнопки под сообщением (дублируют меню)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Или выберите действие кнопками под этим сообщением:",
        reply_markup=build_main_menu_keyboard(),
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
        "Погода и новости по городам России (500 тыс.+). Выбор из топ‑10 или 🔍 поиск по названию.\n\n"
        "**Команды** (также в кнопке ☰ Меню слева от поля ввода):\n"
        "/start — приветствие и карта\n"
        "/menu — открыть меню кнопками\n"
        "/city — выбор города (погода и новости)\n"
        "/weather — погода по городу (сейчас + 7 дней вперёд)\n"
        "/news — новости по городу\n"
        "/map — карта России с погодой по регионам\n"
        "/game — мини-игра Pac-Man\n"
        "/app — погода (мини-приложение)\n"
        "/remind — напоминание о погоде на день (утро/день/вечер/ночь)"
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


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /map — карта России с погодой по регионам."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    await send_weather_map(context, chat_id)


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /game — открыть мини-игру Pac-Man (Web App)."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    if MINI_APP_URL and MINI_APP_URL.startswith("https://"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎮 **Pac-Man** — откройте мини-игру по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶ Играть Pac-Man", web_app=WebAppInfo(url=MINI_APP_URL))],
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Мини-игра Pac-Man будет доступна после настройки.\n\n"
                "1. Разместите папку `mini_app` на HTTPS (GitHub Pages, Vercel, ваш сервер).\n"
                "2. В `.env` укажите: `MINI_APP_URL=https://ваш-домен.com/mini_app/`"
            ),
            )
    if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🌤 **Погода по городам** — откройте сайт погоды по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌡 Сайт погоды", web_app=WebAppInfo(url=WEATHER_APP_URL))],
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )


async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /app — открыть мини-приложение погоды по городам (Web App)."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🌐 **Погода по городам** — откройте приложение по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(url=WEATHER_APP_URL))],
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Мини-приложение погоды будет доступно после настройки.\n\n"
                "1. Разместите папку `weather_app` на HTTPS (GitHub Pages, Vercel, ваш сервер).\n"
                "2. В `.env` укажите: `WEATHER_APP_URL=https://ваш-домен.com/weather_app/`"
            ),
        )


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /remind — подписка на ежедневную рассылку погоды (утро, день, вечер, ночь) в местном времени."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    msg = (
        "⏰ **Напоминание о погоде**\n\n"
        "Каждый день в выбранное время (в **вашем местном времени**) вам будет приходить прогноз на день: "
        "утро, день, вечер, ночь. Выберите часовой пояс, затем время.\n\nВыберите город:"
    )
    kb = build_cities_keyboard(prefix="remind_city")
    buttons = list(kb.inline_keyboard)
    buttons.append([InlineKeyboardButton("📋 Мои напоминания", callback_data="menu:reminders_list")])
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
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


async def handle_city_search_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает ввод названия города в режиме поиска (лупа). Возвращает True если сообщение обработано."""
    prefix = context.user_data.pop("awaiting_city_search", None)
    if not prefix:
        return False
    text = (update.message and update.message.text or "").strip()
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return True
    cities = search_cities_by_query(text, limit=15)
    if not cities:
        await context.bot.send_message(
            chat_id=chat_id,
            text="По запросу «%s» города не найдены. В списке — города России с населением 500 тыс.+ Попробуйте другое название." % text[:50],
        )
        return True
    if len(cities) == 1:
        city = cities[0]
        context.user_data["city_slug"] = city.slug
        if prefix == "weather":
            await context.bot.send_message(chat_id=chat_id, text=f"Город: {city.name_ru}. Загружаю погоду...")
            await send_weather_only(context, chat_id, city)
        elif prefix == "news":
            await context.bot.send_message(chat_id=chat_id, text=f"Город: {city.name_ru}. Загружаю новости...")
            await send_news_only(context, chat_id, city)
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"Город: {city.name_ru}. Получаю погоду и новости...")
            await send_city_info(context, chat_id, city)
        return True
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите город:",
        reply_markup=build_search_results_keyboard(cities, prefix),
    )
    return True


async def handle_remind_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает ввод времени для напоминания (ЧЧ:ММ). Возвращает True если обработано."""
    city_slug = context.user_data.pop("awaiting_remind_time", None)
    tz_id = context.user_data.pop("awaiting_remind_tz", "Europe/Moscow")
    if not city_slug:
        return False
    text = (update.message and update.message.text or "").strip()
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else 0
    if not chat_id:
        return True
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        context.user_data["awaiting_remind_time"] = city_slug
        context.user_data["awaiting_remind_tz"] = tz_id
        await context.bot.send_message(
            chat_id=chat_id,
            text="Введите время в формате ЧЧ:ММ (например 08:30 или 9:00).",
        )
        return True
    h, m_min = int(m.group(1)), int(m.group(2))
    if h < 0 or h > 23 or m_min < 0 or m_min > 59:
        context.user_data["awaiting_remind_time"] = city_slug
        context.user_data["awaiting_remind_tz"] = tz_id
        await context.bot.send_message(chat_id=chat_id, text="Часы: 0–23, минуты: 0–59. Попробуйте снова.")
        return True
    time_str = f"{h:02d}:{m_min:02d}"
    add_reminder(chat_id, user_id, city_slug, time_str, tz=tz_id)
    city = get_city_by_slug(city_slug)
    name = city.name_ru if city else city_slug
    tz_label = next((l for l, tid in REMINDER_TIMEZONES if tid == tz_id), tz_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Готово. Каждый день в **{time_str}** (ваше время — {tz_label}) будет приходить прогноз по {name}.",
        parse_mode=ParseMode.MARKDOWN,
    )
    # Прогноз будет приходить в заданное время через планировщик напоминаний.
    return True


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сначала проверяет режим поиска города (лупа), ввод времени напоминания, иначе — кнопки меню."""
    if await handle_city_search_message(update, context):
        return
    if await handle_remind_time_message(update, context):
        return
    await menu_reply_handler(update, context)


async def menu_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий кнопок постоянного меню (блок внизу экрана)."""
    text = (update.message and update.message.text or "").strip()
    # Кнопка «Напоминание о погоде» может приходить с разным эмодзи от клиентов — распознаём по тексту
    is_remind_btn = ("напоминание" in text.lower() and "погод" in text.lower()) or text == MENU_BTN_REMIND
    if text not in MENU_BUTTON_TEXTS and not is_remind_btn:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return
    if text == MENU_BTN_HELP:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                    "Я показываю погоду и новости по городам России (500 тыс.+). Топ‑10 в списке или 🔍 поиск по названию.\n\n"
                "**Команды:**\n"
                "/start — приветствие и карта России\n"
                "/menu — открыть блок меню\n"
                "/city — выбор города (погода и новости)\n"
                "/weather — погода по городу\n"
                "/news — новости по городу\n"
                    "/map — карта с погодой по регионам\n"
                    "/game — мини-игра Pac-Man\n"
                    "/app — погода (мини-приложение)\n"
                    "/remind — напоминание о погоде на день\n"
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
    elif text == MENU_BTN_MAP:
        await send_weather_map(context, chat_id)
    elif text == MENU_BTN_MENU:
        await context.bot.send_message(
            chat_id=chat_id,
            text="📋 **Меню** — выберите действие:",
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    elif text == MENU_BTN_GAME:
        if MINI_APP_URL and MINI_APP_URL.startswith("https://"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🎮 **Pac-Man** — откройте мини-игру по кнопке ниже:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶ Играть Pac-Man", web_app=WebAppInfo(url=MINI_APP_URL))],
                ]),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Мини-игра Pac-Man будет доступна после настройки.\n\n"
                    "1. Разместите папку `mini_app` на HTTPS (GitHub Pages, Vercel, ваш сервер).\n"
                    "2. В `.env` укажите: `MINI_APP_URL=https://ваш-домен.com/mini_app/`"
                ),
            )
        if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🌤 **Погода по городам** — откройте сайт погоды по кнопке ниже:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌡 Сайт погоды", web_app=WebAppInfo(url=WEATHER_APP_URL))],
                ]),
                parse_mode=ParseMode.MARKDOWN,
            )
    elif text == MENU_BTN_WEATHER_APP:
        if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🌐 **Погода по городам** — откройте приложение по кнопке ниже:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(url=WEATHER_APP_URL))],
                ]),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Мини-приложение погоды будет доступно после настройки.\n\n"
                    "1. Разместите папку `weather_app` на HTTPS (GitHub Pages, Vercel, ваш сервер).\n"
                    "2. В `.env` укажите: `WEATHER_APP_URL=https://ваш-домен.com/weather_app/`"
                ),
            )
    elif text == MENU_BTN_REMIND or is_remind_btn:
        msg = (
            "⏰ **Напоминание о погоде**\n\n"
            "Выберите **город**, затем **часовой пояс** и **время** — каждый день в это время будет приходить прогноз (утро, день, вечер, ночь).\n\n"
            "👇 Выберите город:"
        )
        kb = build_cities_keyboard(prefix="remind_city")
        buttons = list(kb.inline_keyboard)
        buttons.append([InlineKeyboardButton("📋 Мои напоминания", callback_data="menu:reminders_list")])
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning("Remind menu send_message: %s", e)
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Напоминание о погоде. Выберите город (кнопки ниже):",
                reply_markup=InlineKeyboardMarkup(buttons),
        )


def get_city_by_slug(slug: str) -> Optional[City]:
    return RUSSIAN_MILLION_PLUS_CITIES.get(slug)


async def city_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    try:
        await query.answer()
    except BadRequest:
        pass  # callback устарел (бот был выключен) — не логируем
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
                    "Я показываю погоду и новости по городам России с населением 500 тыс.+.\n\n"
                    "**Команды:**\n"
                    "/start — приветствие и карта России\n"
                    "/menu — открыть блок меню\n"
                    "/city — выбор города (погода и новости)\n"
                    "/weather — погода по городу\n"
                    "/news — новости по городу\n"
                    "/map — карта с погодой по регионам\n"
                    "/game — мини-игра Pac-Man\n"
                    "/app — погода (мини-приложение)\n"
                    "/remind — напоминание о погоде на день (утро/день/вечер/ночь)\n"
                    "/help — эта справка\n\n"
                    "В выборе города: топ‑10 крупнейших или 🔍 **Поиск города** — введите название (например Уфа, Рязань)."
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
        elif slug == "map":
            await send_weather_map(context, chat_id)
        elif slug == "menu":
            await context.bot.send_message(
                chat_id=chat_id,
                text="📋 **Меню** — выберите действие:",
                reply_markup=build_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif slug == "game":
            if MINI_APP_URL and MINI_APP_URL.startswith("https://"):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🎮 **Pac-Man** — откройте мини-игру по кнопке ниже:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶ Играть Pac-Man", web_app=WebAppInfo(url=MINI_APP_URL))],
                    ]),
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Мини-игра Pac-Man будет доступна после настройки.\n\n"
                        "1. Разместите папку `mini_app` на HTTPS (GitHub Pages, Vercel, ваш сервер).\n"
                        "2. В `.env` укажите: `MINI_APP_URL=https://ваш-домен.com/mini_app/`"
                    ),
                )
            if WEATHER_APP_URL and WEATHER_APP_URL.startswith("https://"):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🌤 **Погода по городам** — откройте сайт погоды по кнопке ниже:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌡 Сайт погоды", web_app=WebAppInfo(url=WEATHER_APP_URL))],
                    ]),
                    parse_mode=ParseMode.MARKDOWN,
                )
        elif slug == "remind":
            text = (
                "⏰ **Напоминание о погоде**\n\n"
                "Каждый день в выбранное время (в **вашем местном времени**) вам будет приходить прогноз на день: "
                "утро, день, вечер, ночь. Сначала выберите часовой пояс, затем время.\n\nВыберите город:"
            )
            kb = build_cities_keyboard(prefix="remind_city")
            buttons = list(kb.inline_keyboard)
            buttons.append([InlineKeyboardButton("📋 Мои напоминания", callback_data="menu:reminders_list")])
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif slug == "reminders_list":
            user_id = query.from_user.id if query.from_user else 0
            reminders = get_user_reminders(user_id)
            if not reminders:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="У вас пока нет напоминаний о погоде. Добавьте их через меню «⏰ Напоминание о погоде».",
                )
            else:
                buttons_unsub: List[List[InlineKeyboardButton]] = []
                for r in reminders:
                    city = get_city_by_slug(r["city_slug"])
                    name = city.name_ru if city else r["city_slug"]
                    buttons_unsub.append([InlineKeyboardButton(f"Отписаться: {name}", callback_data=f"unsub:{r['city_slug']}")])
                def _tz_label(tz_id: str) -> str:
                    return next((l for l, tid in REMINDER_TIMEZONES if tid == tz_id), tz_id)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="📋 **Ваши напоминания:**\n\n" + "\n".join(
                        f"• {get_city_by_slug(r['city_slug']).name_ru if get_city_by_slug(r['city_slug']) else r['city_slug']} — каждый день в {r['time']} ({_tz_label(r.get('tz', 'Europe/Moscow'))})"
                        for r in reminders
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons_unsub),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # Лупа: пользователь нажал «Поиск города» — просим ввести название
    if prefix == "search":
        context.user_data["awaiting_city_search"] = slug  # city / weather / news
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔍 Введите название города (например: Уфа, Ярославль, Рязань):",
        )
        return

    # Напоминание: выбор часового пояса (местное время пользователя)
    if prefix == "remind_city":
        city = get_city_by_slug(slug)
        if not city:
            await query.edit_message_text("Город не найден.")
            return
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏰ Выберите **ваш часовой пояс** — рассылка будет приходить в ваше местное время.\n\n"
                f"Город погоды: **{city.name_ru}**."
            ),
            reply_markup=build_remind_tz_keyboard(slug),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if prefix == "remind_tz":
        parts = slug.split("|", 1)
        city_slug = parts[0]
        tz_id = parts[1] if len(parts) > 1 else "Europe/Moscow"
        city = get_city_by_slug(city_slug)
        if not city:
            await query.edit_message_text("Город не найден.")
            return
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ На какое время присылать прогноз по **{city.name_ru}**? (в вашем местном времени)",
            reply_markup=build_remind_time_keyboard(city_slug, tz_id),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if prefix == "remind_time":
        parts = slug.split("|", 2)
        city_slug = parts[0]
        tz_id = parts[1] if len(parts) > 1 else "Europe/Moscow"
        time_str = parts[2] if len(parts) > 2 else "08:00"
        user_id = query.from_user.id if query.from_user else 0
        add_reminder(chat_id, user_id, city_slug, time_str, tz=tz_id)
        city = get_city_by_slug(city_slug)
        name = city.name_ru if city else city_slug
        tz_label = next((l for l, tid in REMINDER_TIMEZONES if tid == tz_id), tz_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Готово. Каждый день в **{time_str}** (ваше время — {tz_label}) будет приходить прогноз по {name} (утро, день, вечер, ночь).",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Первый прогноз придёт в заданное время через планировщик напоминаний.
        return

    if prefix == "remind_custom":
        parts = slug.split("|", 1)
        city_slug = parts[0]
        tz_id = parts[1] if len(parts) > 1 else "Europe/Moscow"
        context.user_data["awaiting_remind_time"] = city_slug
        context.user_data["awaiting_remind_tz"] = tz_id
        await context.bot.send_message(
            chat_id=chat_id,
            text="Введите время в формате **ЧЧ:ММ** (в вашем местном времени), например 08:30 или 9:00.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if prefix == "unsub":
        city_slug = slug
        removed = remove_reminder(chat_id, city_slug)
        city = get_city_by_slug(city_slug)
        name = city.name_ru if city else city_slug
        if removed:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Напоминание по {name} отменено.")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"Напоминание по {name} не найдено.")
        return

    if prefix == "weekly":
        city = get_city_by_slug(slug)
        if not city:
            await context.bot.send_message(chat_id=chat_id, text="Город не найден.")
            return
        try:
            weekly_text = await get_weekly_weather_forecast(city)
            await context.bot.send_message(
                chat_id=chat_id,
                text=weekly_text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            logger.warning("Weekly forecast callback failed for %s: %s", city.slug, exc)
            try:
                await context.bot.send_message(chat_id=chat_id, text=weekly_text)
            except Exception:
                pass
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


# Блок «Меню» как у @WantToPayBot: список команд по кнопке ☰ слева от поля ввода.
# Заполняется через set_my_commands и отображается при нажатии на кнопку меню (MenuButtonCommands).
BOT_COMMANDS_MENU: List[BotCommand] = [
    BotCommand("start", "Старт и карта России"),
    BotCommand("menu", "Открыть меню с кнопками"),
    BotCommand("city", "Выбор города (погода и новости)"),
    BotCommand("weather", "Погода по городу"),
    BotCommand("news", "Новости по городу"),
    BotCommand("map", "Карта России с погодой по регионам"),
    BotCommand("game", "Мини-игра Pac-Man"),
    BotCommand("app", "Погода — мини-приложение"),
    BotCommand("remind", "Напоминание о погоде на день"),
    BotCommand("help", "Справка по командам"),
]


async def post_init_set_commands(application) -> None:
    """Устанавливает блок меню: список команд (☰) и кнопку «Меню» при запуске бота."""
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

    logger.info("Запуск из папки: %s", _script_dir)
    logger.info("Версия бота (маркер в /start): %s", _START_VERSION_MARKER)
    logger.info("Токен загружен (первые 15 символов): %s...", TELEGRAM_TOKEN[:15] if len(TELEGRAM_TOKEN) >= 15 else "***")
    _log_bot_username()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init_set_commands)
        .build()
    )

    if app.job_queue:
        app.job_queue.run_repeating(reminder_job, interval=60, first=10)
        logger.info("Напоминания о погоде: рассылка раз в минуту по местному времени подписчиков.")
    else:
        logger.warning("Job queue недоступен — напоминания о погоде не будут отправляться.")

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
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("app", app_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CallbackQueryHandler(city_button_handler))
    app.add_handler(MessageHandler(filters.TEXT, text_message_handler))

    logger.info("Starting Telegram weather/news bot...")
    logger.info("Если в /start видишь «Версия 2.0 • tg bot2 • 27.02.2025» — это эта сборка.")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
