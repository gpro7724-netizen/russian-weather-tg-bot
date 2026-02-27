"""
Скрипт для догрузки красивых фото по ВСЕМ городам из weather_app/cities.json.

Цели:
- минимум 6 картинок на город (historic_*.png / landmark_*.png / city_*.png);
- приоритет — исторический центр и красивые виды, без промышленности.

Как работает:
- читает список городов из ../weather_app/cities.json;
- для каждого города считает, сколько картинок уже есть в ../assets;
- если меньше 6 — ищет фото на Wikimedia Commons и докачивает недостающие
  в файлы historic_{slug}.png, historic_{slug}_2.png, ...;
- промышленные кадры частично отсекает по ключевым словам в названии файла.

Запуск из корня проекта (рядом с bot.py):

  cd russian-weather-tg-bot
  python russian-weather-tg-bot/scripts_city_photos/fetch_photos_for_all_cities.py
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List

from PIL import Image


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_SCRIPT_DIR, "..", "assets")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "RussianWeatherBot/1.0 (all cities photos from Commons)"

# Сколько изображений в сумме хотим на город
TARGET_IMAGES_PER_CITY = 6

# Ключевые слова, по которым выкидываем "промку"
_INDUSTRIAL_KEYWORDS = [
    "завод",
    "фабрик",
    "комбинат",
    "шахт",
    "карьер",
    "тэц",
    "гэс",
    "эсс",
    "factory",
    "plant",
    "industrial",
    "mine",
    "smelter",
    "steel",
]


def _load_cities_from_weather_app() -> List[Dict]:
    cities_path = os.path.join(_SCRIPT_DIR, "..", "weather_app", "cities.json")
    with open(cities_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _existing_city_images(slug: str) -> int:
    """Считает, сколько файлов с картинками уже есть для города (historic/landmark/city)."""
    if not os.path.isdir(ASSETS_DIR):
        return 0
    count = 0
    prefix_variants = [
        f"historic_{slug}",
        f"landmark_{slug}_",
        f"city_{slug}_",
    ]
    for name in os.listdir(ASSETS_DIR):
        if not name.lower().endswith(".png"):
            continue
        for pref in prefix_variants:
            if name.startswith(pref):
                count += 1
                break
    return count


def _target_filenames(slug: str) -> List[str]:
    """Имена файлов, которые будем использовать для докачки (historic_*)."""
    names: List[str] = []
    for i in range(TARGET_IMAGES_PER_CITY):
        if i == 0:
            fname = f"historic_{slug}.png"
        else:
            fname = f"historic_{slug}_{i + 1}.png"
        names.append(fname)
    return names


def _commons_search_files(city_name_ru: str, limit: int = 20) -> List[str]:
    """Ищем красивые виды города на Commons по русскому названию."""
    # Стараться выбирать панорамы / исторический центр / набережные
    search_term = f'"{city_name_ru}" (панорама OR набережная OR площадь OR кремль OR собор OR исторический центр)'
    params = {
        "action": "query",
        "list": "search",
        "srsearch": search_term,
        "srnamespace": 6,
        "srlimit": limit,
        "format": "json",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    titles: List[str] = []
    for item in data.get("query", {}).get("search", []):
        t = item.get("title", "")
        if not t.startswith("File:"):
            continue
        low = t.lower()
        if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if any(bad in low for bad in _INDUSTRIAL_KEYWORDS):
            continue
        titles.append(t)
    return titles


def _get_image_url_from_title(file_title: str) -> str | None:
    params = {
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": THUMB_SIZE,
        "format": "json",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid != "-1" and "imageinfo" in page and page["imageinfo"]:
            info = page["imageinfo"][0]
            return info.get("thumburl") or info.get("url")
    return None


def _download(url: str, retries: int = 2) -> bytes | None:
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read()
        except Exception:
            if attempt < retries:
                time.sleep(3)
    return None


def _save_png(raw: bytes, path: str) -> bool:
    try:
        img = Image.open(io.BytesIO(raw))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(path, "PNG")
        return True
    except Exception:
        return False


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    cities = _load_cities_from_weather_app()

    total_saved = 0
    per_city_saved: Dict[str, int] = {}

    for city in cities:
        slug = city.get("slug")
        name_ru = city.get("name_ru") or slug
        if not slug:
            continue

        existing = _existing_city_images(slug)
        if existing >= TARGET_IMAGES_PER_CITY:
            continue

        need = TARGET_IMAGES_PER_CITY - existing
        target_files = _target_filenames(slug)
        # Оставляем только те, которых ещё нет
        target_files = [
            fname for fname in target_files if not os.path.isfile(os.path.join(ASSETS_DIR, fname))
        ]
        if not target_files:
            continue

        print(f"{name_ru}: уже {existing}, докачиваем {min(need, len(target_files))} фото...")
        time.sleep(0.7)
        titles = _commons_search_files(name_ru, limit=25)
        if not titles:
            print(f"  [skip] {name_ru}: не нашли подходящих файлов")
            continue

        saved_here = 0
        title_idx = 0
        for out_name in target_files:
            if title_idx >= len(titles):
                break
            file_title = titles[title_idx]
            title_idx += 1

            path = os.path.join(ASSETS_DIR, out_name)
            if os.path.isfile(path):
                continue

            time.sleep(0.6)
            img_url = _get_image_url_from_title(file_title)
            if not img_url:
                continue
            raw = _download(img_url)
            if not raw:
                continue
            if _save_png(raw, path):
                saved_here += 1
                total_saved += 1
                print(f"  -> {out_name}")

        if saved_here:
            per_city_saved[slug] = saved_here
        else:
            print(f"  [fail] {name_ru}: не удалось сохранить ни одного фото")

    print(f"\nГотово. Новых изображений: {total_saved}")
    if per_city_saved:
        print("По городам:")
        for slug, n in sorted(per_city_saved.items()):
            print(f"  {slug}: {n}")


if __name__ == "__main__":
    main()

