# Добавляет по 3 новых фото исторического центра для каждого города из Wikimedia Commons.
# Для каждого города — 3 разных поисковых запроса (разные локации: центр, площадь, набережная и т.д.).
# Запуск: python fetch_historic_center_photos.py

import io
import json
import os
import time
import urllib.request
import urllib.parse

from PIL import Image

_script_dir = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_script_dir, "assets")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "RussianWeatherBot/1.0 (historic center photos)"
ADD_PER_CITY = 5  # до 5 дополнительных фото на город (для новых городов — побольше)
MAX_HISTORIC_SLOTS = 10

# Города и по 3 поисковых запроса на город (разные локации исторического центра — чтобы фото отличались)
CITY_HISTORIC_SEARCHES: dict[str, list[str]] = {
    "moscow": [
        "Moscow Red Square Russia",
        "Zaryadye Park Moscow Russia",
        "Kitay-gorod Moscow Russia",
    ],
    "spb": [
        "Saint Petersburg Palace Square",
        "Saint Petersburg Nevsky Prospect",
        "Saint Petersburg Peter Paul Fortress",
    ],
    "novosibirsk": [
        "Novosibirsk Lenin Square",
        "Novosibirsk Ob River embankment",
        "Novosibirsk historic center",
    ],
    "yekaterinburg": [
        "Yekaterinburg city center",
        "Yekaterinburg Iset River embankment",
        "Yekaterinburg historic square",
    ],
    "nizhny_novgorod": [
        "Nizhny Novgorod Kremlin",
        "Nizhny Novgorod Chkalov stairs Volga",
        "Nizhny Novgorod Bolshaya Pokrovskaya",
    ],
    "kazan": [
        "Kazan Kremlin",
        "Kazan Bauman Street",
        "Kazan Kremlin view from river",
    ],
    "chelyabinsk": [
        "Chelyabinsk Kirovka street",
        "Chelyabinsk city center",
        "Chelyabinsk Miass river embankment",
    ],
    "omsk": [
        "Omsk Irtysh embankment",
        "Omsk Lyubinsky prospect",
        "Omsk historic center",
    ],
    "samara": [
        "Samara Volga embankment",
        "Samara Kuibyshev Square",
        "Samara Leningradskaya street",
    ],
    "rostov_on_don": [
        "Rostov-on-Don Don embankment",
        "Rostov-on-Don Pushkin Street",
        "Rostov-on-Don city center",
    ],
    "ufa": [
        "Ufa Belaya River embankment",
        "Ufa Salavat Yulayev square",
        "Ufa historic center",
    ],
    "krasnoyarsk": [
        "Krasnoyarsk Yenisei embankment",
        "Krasnoyarsk Peace Square",
        "Krasnoyarsk historic center",
    ],
    "perm": [
        "Perm Kama embankment",
        "Perm city center",
        "Perm Esplanade",
    ],
    "voronezh": [
        "Voronezh Admiralty",
        "Voronezh city center",
        "Voronezh embankment",
    ],
    "volgograd": [
        "Volgograd Mamayev Kurgan",
        "Volgograd Volga embankment",
        "Volgograd central square",
    ],
    "krasnodar": [
        "Krasnodar Krasnaya street",
        "Krasnodar Kuban embankment",
        "Krasnodar city center",
    ],
    "saratov": [
        "Saratov Volga embankment",
        "Saratov city center",
        "Saratov Prospekt Kirova",
    ],
    "tyumen": [
        "Tyumen Tura embankment",
        "Tyumen historic center",
        "Tyumen Tsvetnoy boulevard",
    ],
    "tolyatti": [
        "Tolyatti Volga",
        "Tolyatti central square",
        "Tolyatti city center",
    ],
    "izhevsk": [
        "Izhevsk pond embankment",
        "Izhevsk central square",
        "Izhevsk historic center",
    ],
    "barnaul": [
        "Barnaul Ob River",
        "Barnaul Demidov square",
        "Barnaul historic center",
    ],
    "ulyanovsk": [
        "Ulyanovsk Volga embankment",
        "Ulyanovsk Lenin memorial",
        "Ulyanovsk historic center",
    ],
    "irkutsk": [
        "Irkutsk Angara embankment",
        "Irkutsk 130 Quarter",
        "Irkutsk historic wooden houses",
    ],
    "khabarovsk": [
        "Khabarovsk Amur embankment",
        "Khabarovsk Muravyov-Amursky street",
        "Khabarovsk city center",
    ],
    "vladivostok": [
        "Vladivostok central square",
        "Vladivostok embankment",
        "Vladivostok Svetlanskaya street",
    ],
    "mahachkala": [
        "Makhachkala central mosque",
        "Makhachkala Caspian embankment",
        "Makhachkala city center",
    ],
    # Новые города 500 тыс.+: только исторический центр и достопримечательности, без промышленности
    "yaroslavl": [
        "Yaroslavl historic center church",
        "Yaroslavl Volga embankment",
        "Yaroslavl Church of St John the Baptist",
    ],
    "stavropol": [
        "Stavropol cathedral square",
        "Stavropol historic center",
        "Stavropol central park",
    ],
    "sevastopol": [
        "Sevastopol Panorama Museum",
        "Sevastopol embankment",
        "Sevastopol historic center",
    ],
    "naberezhnye_chelny": [
        "Naberezhnye Chelny mosque center",
        "Naberezhnye Chelny boulevard",
        "Naberezhnye Chelny city center",
    ],
    "tomsk": [
        "Tomsk wooden architecture",
        "Tomsk University historic",
        "Tomsk river embankment",
    ],
    "balashikha": [
        "Balashikha park",
        "Balashikha church",
        "Balashikha city center",
    ],
    "kemerovo": [
        "Kemerovo Tom River embankment",
        "Kemerovo drama theatre",
        "Kemerovo city center square",
    ],
    "orenburg": [
        "Orenburg caravan saray",
        "Orenburg Ural embankment",
        "Orenburg historic center",
    ],
    "novokuznetsk": [
        "Novokuznetsk Transfiguration Cathedral",
        "Novokuznetsk city center",
        "Novokuznetsk Kondoma river",
    ],
    "ryazan": [
        "Ryazan Kremlin",
        "Ryazan cathedral",
        "Ryazan historic center",
    ],
}

# Точные имена файлов Commons (разные локации) — если поиск не дал новых фото
FALLBACK_COMMONS_TITLES: dict[str, list[str]] = {
    "moscow": [
        "File:Red Square, Moscow, Russia.jpg",
        "File:Glass Crust in Zaryadye park, Moscow, Russia.jpg",
        "File:Glass roof in Zaryadye Park, Moscow (25076506227).jpg",
    ],
    "nizhny_novgorod": [
        "File:Dmitrovskaya Tower of Nizhny Novgorod Kremlin.jpg",
        "File:NN Kremlin 08-2016 img2.jpg",
        "File:Nizhny Novgorod Eternal Flame 03.jpg",
    ],
    "chelyabinsk": [
        "File:Chelyabinsk Kirovka 2.jpg",
        "File:Chelyabinsk city view.jpg",
        "File:Челябинск Кировка 2012.jpg",
    ],
    "omsk": [
        "File:Omsk Irtysh embankment.jpg",
        "File:Omsk - Lyubinsky Avenue.jpg",
        "File:Омск - вид на Иртыш.jpg",
    ],
    # Новые города 500k+: точные имена с Commons (исторический центр, достопримечательности)
    "yaroslavl": [
        "File:Yaroslavl Church of St. John the Baptist (view from the south).jpg",
        "File:Yaroslavl Spaso-Preobrazhensky Monastery 2013.jpg",
        "File:Yaroslavl Volga embankment.jpg",
        "File:Yaroslavl view from Volga.jpg",
        "File:Church of Elijah the Prophet, Yaroslavl.jpg",
    ],
    "stavropol": [
        "File:Stavropol Kazan Cathedral 2.jpg",
        "File:Stavropol city view.jpg",
        "File:Ставрополь проспект Карла Маркса.jpg",
        "File:Stavropol Victory Park.jpg",
    ],
    "sevastopol": [
        "File:Sevastopol Panorama Museum.jpg",
        "File:Sevastopol Count's Jetty.jpg",
        "File:Sevastopol Nakhimov Square.jpg",
        "File:Sevastopol Primorsky Boulevard.jpg",
    ],
    "naberezhnye_chelny": [
        "File:Naberezhnye Chelny Central Mosque.jpg",
        "File:Naberezhnye Chelny city.jpg",
        "File:Набережные Челны проспект.jpg",
    ],
    "tomsk": [
        "File:Tomsk wooden house 01.jpg",
        "File:Tomsk State University main building.jpg",
        "File:Tomsk Tom river embankment.jpg",
        "File:Tomsk Resurrection Church.jpg",
    ],
    "balashikha": [
        "File:Balashikha Pechatniki park.jpg",
        "File:Balashikha Trinity Church.jpg",
        "File:Gorenki Estate Balashikha.jpg",
    ],
    "kemerovo": [
        "File:Kemerovo Tom River embankment.jpg",
        "File:Kemerovo Drama Theatre.jpg",
        "File:Kemerovo Monument to Miners.jpg",
        "File:Кемерово площадь.jpg",
    ],
    "orenburg": [
        "File:Orenburg Caravan-Saray.jpg",
        "File:Orenburg Ural embankment.jpg",
        "File:Orenburg pedestrian bridge.jpg",
        "File:Оренбург центр.jpg",
    ],
    "novokuznetsk": [
        "File:Novokuznetsk Transfiguration Cathedral.jpg",
        "File:Novokuznetsk city center.jpg",
        "File:Новокузнецк Кузнецкая крепость.jpg",
    ],
    "ryazan": [
        "File:Ryazan Kremlin Cathedral.jpg",
        "File:Ryazan Assumption Cathedral.jpg",
        "File:Ryazan embankment.jpg",
        "File:Рязань кремль.jpg",
        "File:Ryazan Kremlin view.jpg",
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
    return titles


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


def _existing_historic_indices(slug: str) -> list[int]:
    """Возвращает список индексов (1..8) уже существующих historic файлов."""
    indices = []
    for i in range(1, MAX_HISTORIC_SLOTS + 1):
        if i == 1:
            path = os.path.join(ASSETS, f"historic_{slug}.png")
        else:
            path = os.path.join(ASSETS, f"historic_{slug}_{i}.png")
        if os.path.isfile(path):
            indices.append(i)
    return indices


def main():
    os.makedirs(ASSETS, exist_ok=True)
    total_added = 0
    used_titles: dict[str, set[str]] = {}  # slug -> set of File: titles already saved for this city

    for slug, queries in CITY_HISTORIC_SEARCHES.items():
        existing = _existing_historic_indices(slug)
        next_indices = []
        for k in range(1, MAX_HISTORIC_SLOTS + 1):
            if k not in existing and len(next_indices) < ADD_PER_CITY:
                next_indices.append(k)
        if not next_indices:
            print(f"  [skip] {slug}: уже достаточно фото")
            continue

        used = used_titles.setdefault(slug, set())
        added = 0
        # По одному изображению с каждого из 3 запросов — разные локации
        for q_idx, query in enumerate(queries):
            if added >= len(next_indices):
                break
            time.sleep(0.6)
            titles = _commons_search(query, limit=10)
            chosen = None
            for t in titles:
                if t not in used:
                    chosen = t
                    break
            if not chosen:
                print(f"  [no new] {slug} query {q_idx + 1}: {query[:40]}...")
                continue
            time.sleep(0.55)
            img_url = _get_image_url_from_title(chosen)
            if not img_url:
                continue
            raw = _download(img_url)
            if not raw:
                continue
            idx = next_indices[added]
            out_name = f"historic_{slug}.png" if idx == 1 else f"historic_{slug}_{idx}.png"
            path = os.path.join(ASSETS, out_name)
            if _save_png(raw, path):
                used.add(chosen)
                added += 1
                total_added += 1
                print(f"  {slug} -> {out_name} (query: {query[:35]}...)")
        # Если поиск дал мало — пробуем точные имена из FALLBACK
        while added < len(next_indices) and slug in FALLBACK_COMMONS_TITLES:
            fallback_list = FALLBACK_COMMONS_TITLES[slug]
            chosen = None
            for t in fallback_list:
                if t not in used:
                    chosen = t
                    break
            if not chosen:
                break
            time.sleep(0.6)
            img_url = _get_image_url_from_title(chosen)
            if not img_url:
                used.add(chosen)
                continue
            raw = _download(img_url)
            if not raw:
                used.add(chosen)
                continue
            idx = next_indices[added]
            out_name = f"historic_{slug}.png" if idx == 1 else f"historic_{slug}_{idx}.png"
            path = os.path.join(ASSETS, out_name)
            if _save_png(raw, path):
                used.add(chosen)
                added += 1
                total_added += 1
                print(f"  {slug} -> {out_name} (fallback)")
        if added == 0:
            print(f"  [fail] {slug}")
    print(f"Готово. Добавлено фото: {total_added}")


if __name__ == "__main__":
    main()
