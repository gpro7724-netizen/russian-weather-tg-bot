# Скачивание по 3 фото для городов, у которых ещё нет изображений в assets.
# Использует поиск Wikimedia Commons по названию города, затем скачивает найденные изображения.
# Запуск: python fetch_missing_city_photos.py

import io
import json
import os
import time
import urllib.request
import urllib.parse

from PIL import Image

_script_dir = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_script_dir, "..", "assets")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "RussianWeatherBot/1.0 (city photos)"
MAX_IMAGES_PER_CITY = 3

# Только города без ни одного фото в assets (проверяется в main)
MISSING_CITIES = {
    "ufa": "Ufa Belaya River Russia",
    "volgograd": "Volgograd Motherland Calls Russia",
    "saratov": "Saratov Volga Russia",
    "tyumen": "Tyumen Russia",
    "tolyatti": "Tolyatti Volga Russia",
    "barnaul": "Barnaul Ob Russia",
    "khabarovsk": "Khabarovsk Amur Russia",
}

# Точные заголовки файлов Commons (как в API)
FALLBACK_COMMONS_TITLES: dict[str, list[str]] = {
    "saratov": [
        "File:Saratov_City_Centre.jpg",
        "File:Volga in Saratov Oblast P5161212 2200.jpg",
        "File:2018-10-08 Bank of the Volga (Saratov) (Volga Sky cropped).JPG",
    ],
    "tyumen": [
        "File:Tyumen Urban Okrug Tyumen 2023-06 1687974106.JPG",
        "File:Tyumen Urban Okrug Tyumen 2023-06 1687976737.JPG",
        "File:Tyumen Urban Okrug Tyumen 2023-06 1687976745.JPG",
    ],
    "tolyatti": [
        "File:Duma of city Togliatty, Russia.JPG",
        "File:Komsomolsky district, Tolyatti, Russia.JPG",
        "File:Administration of city, Tolyatti, Russia.JPG",
    ],
    "barnaul": [
        "File:Barnaul Schild.jpg",
        "File:Barnaul Hafen.jpg",
        "File:Barnaul (2021)-1.jpeg",
    ],
    "khabarovsk": [
        "File:Khabarovsk 2024-08 001.jpg",
        "File:Khabarovsk 2024-08 110.jpg",
        "File:Khabarovsk 2024-08 111.jpg",
    ],
}


def _commons_search(search_term: str, limit: int = 5) -> list[str]:
    """Возвращает список имён файлов (File:...) из поиска Commons."""
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    titles = []
    for item in data.get("query", {}).get("search", []):
        t = item.get("title", "")
        if t.startswith("File:") and t.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            titles.append(t)
    return titles[:MAX_IMAGES_PER_CITY]


def _get_image_url_from_title(file_title: str) -> str | None:
    """По полному заголовку File:... возвращает URL изображения."""
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
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid != "-1" and "imageinfo" in page and page["imageinfo"]:
            info = page["imageinfo"][0]
            return info.get("thumburl") or info.get("url")
    return None


def _download(url: str, retries: int = 3) -> bytes | None:
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


def _city_has_no_photos(slug: str) -> bool:
    for name in [f"historic_{slug}.png", f"historic_{slug}_2.png", f"historic_{slug}_3.png",
                 f"landmark_{slug}_1.png", f"landmark_{slug}_2.png", f"landmark_{slug}_3.png"]:
        if os.path.isfile(os.path.join(ASSETS, name)):
            return False
    return True


def main():
    os.makedirs(ASSETS, exist_ok=True)
    total = 0
    for slug, search_query in list(MISSING_CITIES.items()):
        if not _city_has_no_photos(slug):
            continue
        time.sleep(0.5)
        if slug in FALLBACK_COMMONS_TITLES:
            titles = FALLBACK_COMMONS_TITLES[slug]
        else:
            titles = _commons_search(search_query, limit=8)
        if not titles:
            print(f"  [skip] {slug}: нет файлов")
            continue
        saved = 0
        for i, file_title in enumerate(titles[:MAX_IMAGES_PER_CITY]):
            if i == 0:
                out_name = f"historic_{slug}.png"
            else:
                out_name = f"historic_{slug}_{i + 1}.png"
            path = os.path.join(ASSETS, out_name)
            if os.path.isfile(path):
                saved += 1
                total += 1
                continue
            time.sleep(0.45)
            img_url = _get_image_url_from_title(file_title)
            if not img_url:
                continue
            raw = _download(img_url)
            if not raw:
                continue
            if _save_png(raw, path):
                saved += 1
                total += 1
                print(f"  {slug} -> {out_name}")
        if saved == 0 and slug in FALLBACK_COMMONS_TITLES:
            for i, file_title in enumerate(FALLBACK_COMMONS_TITLES[slug][:MAX_IMAGES_PER_CITY]):
                if i == 0:
                    out_name = f"historic_{slug}.png"
                else:
                    out_name = f"historic_{slug}_{i + 1}.png"
                path = os.path.join(ASSETS, out_name)
                if os.path.isfile(path):
                    saved += 1
                    total += 1
                    continue
                time.sleep(0.45)
                img_url = _get_image_url_from_title(file_title)
                if not img_url:
                    continue
                raw = _download(img_url)
                if not raw:
                    continue
                if _save_png(raw, path):
                    saved += 1
                    total += 1
                    print(f"  {slug} (fallback) -> {out_name}")
        if saved == 0:
            print(f"  [fail] {slug}")
    print(f"Готово. Всего: {total}")


if __name__ == "__main__":
    main()
