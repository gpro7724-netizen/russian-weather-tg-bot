# Скачивание по 3 фото достопримечательностей для каждого города.
# Источник: Wikimedia Commons. Сохраняет в assets/landmark_{slug}_1.png, _2.png, _3.png.
# Запуск: python download_landmarks.py
# Используется в боте: https://github.com/gpro7724-netizen/russian-weather-tg-bot

import io
import json
import os
import time
import urllib.request
import urllib.parse

from PIL import Image

from cities import CITIES

_script_dir = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_script_dir, "assets")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "CityLandmarkImages/1.0 (landmark images)"

LANDMARK_FILES: dict[str, list[str]] = {
    "moscow": ["St._Basil's_Cathedral,_Red_Square.jpg", "Kremlin_Moscow.jpg", "Moscow-Kremlin.jpg"],
    "spb": ["Winter_Palace_Panorama_3.jpg", "Peter_and_Paul_Fortress,_Saint_Petersburg,_Russia.jpg", "Church_of_the_Savior_on_Blood,_St._Petersburg.jpg"],
    "novosibirsk": ["Novosibirsk_Opera_and_Ballet_Theatre.jpg", "Novosibirsk_railway_station_2.jpg", "Ob_Sea_dam_Novosibirsk.jpg"],
    "yekaterinburg": ["Church_on_the_Blood_in_Yekaterinburg.jpg", "Yekaterinburg_Circus_2.jpg", "Vysotsky_Business_Center_Yekaterinburg.jpg"],
    "nizhny_novgorod": ["Nizhny_Novgorod_Kremlin.jpg", "Chkalov_Stairs.jpg", "Nizhny_Novgorod_Fair_Building.jpg"],
    "kazan": ["Kazan_Kremlin.jpg", "Kul_Sharif_Mosque,_Kazan.jpg", "1_May_square_Kazan.JPG"],
    "chelyabinsk": ["Chelyabinsk_Revolution_Square.jpg", "Chelyabinsk_State_Academic_Opera_and_Ballet_Theatre.jpg", "Chelyabinsk_Pedestrian_Street.jpg"],
    "omsk": ["Omsk_Drama_Theatre.jpg", "Assumption_Cathedral_Omsk.jpg", "Omsk_Fortress_Gate.jpg"],
    "samara": ["Samara_Volga_embankment_2012-2.jpg", "Samara._Volga_river_P6190173_2350.jpg", "Samara.jpg"],
    "rostov_on_don": ["Rostov-on-Don_center.jpg", "Rostov_Cathedral.jpg", "Rostov_Don_Embankment.jpg"],
    "ufa": ["Ufa_View_from_Belaya_River.jpg", "Salavat_Yulayev_Monument_Ufa.jpg", "Ufa_Convention_Hall.jpg"],
    "krasnoyarsk": ["Krasnoyarsk_Bridge-2.jpg", "Krasnoyarsk_Stolby.jpg", "Krasnoyarsk_Dam.jpg"],
    "perm": ["Perm_Russia.jpg", "Perm_Opera_Theatre.jpg", "Perm_Art_Gallery.jpg"],
    "voronezh": ["Admiralteyskaya_Square,_Voronezh.jpg", "Voronezh_Annunciation_Cathedral.jpg", "Voronezh_Sea.jpg"],
    "volgograd": ["Mamayev_Kurgan_01.jpg", "The_Motherland_Calls.jpg", "Volgograd_Panorama_Museum.jpg"],
    "krasnodar": ["Krasnodar_centre_01.jpg", "Krasnodar_Alexander_Arch.jpg", "Krasnodar_Stadium.jpg"],
    "saratov": ["Saratov_Conservatory_1.jpg", "Saratov_Bridge.jpg", "Saratov_Circus.jpg"],
    "tyumen": ["Tyumen_center.jpg", "Tyumen_Drama_Theatre.jpg", "Tyumen_Bridge.jpg"],
    "tolyatti": ["Tolyatti_City_Hall.jpg", "Tolyatti_AvtoVAZ.jpg", "Volga_embankment_Tolyatti.jpg"],
    "izhevsk": ["Izhevsk_center.jpg", "Izhevsk_Arms_Plant_Museum.jpg", "Izhevsk_Pond.jpg"],
    "barnaul": ["Barnaul_Pedestrian_zone.jpg", "Barnaul_Drama_Theatre.jpg", "Ob_River_Barnaul.jpg"],
    "ulyanovsk": ["Lenin_Memorial_Complex_in_Ulyanovsk.jpg", "Ulyanovsk_Volga_Bridge.jpg", "Ulyanovsk_center.jpg"],
    "irkutsk": ["Irkutsk_130_quarter.jpg", "Irkutsk_Church_of_the_Savior.jpg", "Angara_River_Irkutsk.jpg"],
    "khabarovsk": ["Khabarovsk_Amur_embankment.jpg", "Khabarovsk_Bridge.jpg", "Khabarovsk_Cathedral.jpg"],
    "vladivostok": ["Russky_Bridge_Vladivostok.jpg", "Vladivostok_Railway_Station.jpg", "Vladivostok_Golden_Bridge.jpg"],
    "mahachkala": ["Makhachkala_Caspian.jpg", "Juma_Mosque_Makhachkala.jpg", "Makhachkala_center.jpg"],
}


def _get_commons_image_url(file_name: str) -> str | None:
    title = "File:" + file_name
    params = {"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url", "iiurlwidth": THUMB_SIZE, "format": "json"}
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


def _download_image(url: str, retries: int = 2) -> bytes | None:
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
    total_ok = 0
    for slug, (name_ru, _) in CITIES.items():
        files = LANDMARK_FILES.get(slug)
        if not files:
            continue
        for i, file_name in enumerate(files[:3], start=1):
            time.sleep(0.35)
            path = os.path.join(ASSETS, f"landmark_{slug}_{i}.png")
            url = _get_commons_image_url(file_name)
            if not url:
                print(f"  [skip] {slug} landmark_{i}: нет URL")
                continue
            raw = _download_image(url)
            if not raw:
                print(f"  [fail] {slug} landmark_{i}: не удалось скачать")
                continue
            try:
                img = Image.open(io.BytesIO(raw))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(path, "PNG")
            except Exception as e:
                print(f"  [fail] {slug} landmark_{i}: {e}")
                continue
            total_ok += 1
            print(f"  {name_ru} landmark_{i} -> {path}")
    print(f"Готово. Сохранено {total_ok} изображений.")


if __name__ == "__main__":
    main()
