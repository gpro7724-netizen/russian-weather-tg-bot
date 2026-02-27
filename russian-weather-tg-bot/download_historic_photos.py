# Скачивание реальных фотографий исторических центров городов.
# Источники: Wikipedia (главное фото статьи), при отсутствии — запасные URL Wikimedia Commons.
# Запуск: python download_historic_photos.py
# Сохраняет в assets/historic_{город}.png

import io
import json
import os
import sys
import time
import urllib.request
import urllib.parse

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot import RUSSIAN_MILLION_PLUS_CITIES, _script_dir

ASSETS = os.path.join(_script_dir, "assets")
WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "RussianWeatherBot/1.0 (historic center images)"

# Запасные файлы Commons (имя файла), если у статьи Wikipedia нет главного изображения.
# URL получаем через Commons API. Имена проверены на commons.wikimedia.org
FALLBACK_FILES = {
    "nizhny_novgorod": "Nizhny_Novgorod_Kremlin.jpg",
    "kazan": "Kazan_Kremlin.jpg",
    "chelyabinsk": "Chelyabinsk_Revolution_Square.jpg",
    "ufa": "Ufa_View_from_Belaya_River.jpg",
    "krasnoyarsk": "Krasnoyarsk_Bridge-2.jpg",
    "perm": "Perm_Russia.jpg",
    "voronezh": "Admiralteyskaya_Square,_Voronezh.jpg",
    "volgograd": "Mamayev_Kurgan_01.jpg",
    "krasnodar": "Krasnodar_centre_01.jpg",
    "saratov": "Saratov_Conservatory_1.jpg",
    "tolyatti": "Tolyatti_City_Hall.jpg",
    "izhevsk": "Izhevsk_center.jpg",
    "barnaul": "Barnaul_Pedestrian_zone.jpg",
    "ulyanovsk": "Lenin_Memorial_Complex_in_Ulyanovsk.jpg",
    "irkutsk": "Irkutsk_130_quarter.jpg",
    "khabarovsk": "Khabarovsk_Amur_embankment.jpg",
    "samara": "Samara_Volga_embankment_2012-2.jpg",
    "rostov_on_don": "Rostov-on-Don_center.jpg",
    "tyumen": "Tyumen_center.jpg",
    "vladivostok": "Russky_Bridge_Vladivostok.jpg",
    "mahachkala": "Makhachkala_Caspian.jpg",
    # Новые города (500 тыс.+): только исторический центр и достопримечательности, без промышленности
    "yaroslavl": "Yaroslavl_Church_of_St._John_the_Baptist.jpg",
    "stavropol": "Stavropol_cathedral.jpg",
    "sevastopol": "Sevastopol_Panorama_Museum.jpg",
    "naberezhnye_chelny": "Naberezhnye_Chelny_central_mosque.jpg",
    "tomsk": "Tomsk_wooden_house.jpg",
    "balashikha": "Balashikha_Pechatniki_park.jpg",
    "kemerovo": "Kemerovo_Tom_embankment.jpg",
    "orenburg": "Orenburg_caravan_saray.jpg",
    "novokuznetsk": "Novokuznetsk_Transfiguration_Cathedral.jpg",
    "ryazan": "Ryazan_Kremlin.jpg",
}


def _get_commons_image_url(file_name: str) -> str | None:
    """Возвращает URL превью изображения с Commons по имени файла."""
    title = "File:" + file_name
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": THUMB_SIZE,
        "format": "json",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid != "-1" and "imageinfo" in page and page["imageinfo"]:
            info = page["imageinfo"][0]
            return info.get("thumburl") or info.get("url")
    return None


def _get_wiki_image_url(title: str) -> str | None:
    """Возвращает URL главного изображения статьи Wikipedia или None."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": THUMB_SIZE,
    }
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid != "-1" and "thumbnail" in page:
            return page["thumbnail"].get("source")
    return None


def _download_image(url: str, retries: int = 2) -> bytes | None:
    """Скачивает изображение по URL и возвращает байты или None."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except Exception:
            if attempt < retries:
                time.sleep(2)
    return None


def main():
    os.makedirs(ASSETS, exist_ok=True)
    ok = 0
    for slug, city in RUSSIAN_MILLION_PLUS_CITIES.items():
        time.sleep(0.3)
        path = os.path.join(ASSETS, f"historic_{slug}.png")
        url = _get_wiki_image_url(city.name_en)
        if not url and slug in FALLBACK_FILES:
            url = _get_commons_image_url(FALLBACK_FILES[slug])
        if not url:
            print(f"  [skip] {city.name_ru}: нет URL")
            continue
        raw = _download_image(url)
        if not raw and slug in FALLBACK_FILES:
            url = _get_commons_image_url(FALLBACK_FILES[slug])
            if url:
                raw = _download_image(url)
        if not raw:
            print(f"  [fail] {city.name_ru}: не удалось скачать")
            continue
        time.sleep(0.4)
        # Конвертируем в PNG (бот ожидает historic_{slug}.png)
        try:
            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            path = os.path.join(ASSETS, f"historic_{slug}.png")
            img.save(path, "PNG")
        except Exception as e:
            print(f"  [fail] {city.name_ru}: {e}")
            continue
        ok += 1
        print(f"  {city.name_ru} -> {path}")
    print(f"Готово. Сохранено {ok} из {len(RUSSIAN_MILLION_PLUS_CITIES)}.")


if __name__ == "__main__":
    main()
