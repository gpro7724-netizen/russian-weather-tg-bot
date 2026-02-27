# Скачивание нескольких фотографий (исторический центр / вид города) для каждого города.
# Источник: Wikimedia Commons. Сохраняет в assets/historic_{slug}.png, historic_{slug}_2.png, ...
# При выборе города бот показывает одну случайную из загруженных.
# Запуск: python download_city_photos.py

import io
import json
import os
import time
import urllib.request
import urllib.parse

from PIL import Image

# Города: slug -> (name_ru, name_en) — синхрон с bot.py
CITIES = {
    "moscow": ("Москва", "Moscow"),
    "spb": ("Санкт-Петербург", "Saint Petersburg"),
    "novosibirsk": ("Новосибирск", "Novosibirsk"),
    "yekaterinburg": ("Екатеринбург", "Yekaterinburg"),
    "nizhny_novgorod": ("Нижний Новгород", "Nizhny Novgorod"),
    "kazan": ("Казань", "Kazan"),
    "chelyabinsk": ("Челябинск", "Chelyabinsk"),
    "omsk": ("Омск", "Omsk"),
    "samara": ("Самара", "Samara"),
    "rostov_on_don": ("Ростов-на-Дону", "Rostov-on-Don"),
    "ufa": ("Уфа", "Ufa"),
    "krasnoyarsk": ("Красноярск", "Krasnoyarsk"),
    "perm": ("Пермь", "Perm"),
    "voronezh": ("Воронеж", "Voronezh"),
    "volgograd": ("Волгоград", "Volgograd"),
    "krasnodar": ("Краснодар", "Krasnodar"),
    "saratov": ("Саратов", "Saratov"),
    "tyumen": ("Тюмень", "Tyumen"),
    "tolyatti": ("Тольятти", "Tolyatti"),
    "izhevsk": ("Ижевск", "Izhevsk"),
    "barnaul": ("Барнаул", "Barnaul"),
    "ulyanovsk": ("Ульяновск", "Ulyanovsk"),
    "irkutsk": ("Иркутск", "Irkutsk"),
    "khabarovsk": ("Хабаровск", "Khabarovsk"),
    "vladivostok": ("Владивосток", "Vladivostok"),
    "mahachkala": ("Махачкала", "Makhachkala"),
    "yaroslavl": ("Ярославль", "Yaroslavl"),
    "stavropol": ("Ставрополь", "Stavropol"),
    "sevastopol": ("Севастополь", "Sevastopol"),
    "naberezhnye_chelny": ("Набережные Челны", "Naberezhnye Chelny"),
    "tomsk": ("Томск", "Tomsk"),
    "balashikha": ("Балашиха", "Balashikha"),
    "kemerovo": ("Кемерово", "Kemerovo"),
    "orenburg": ("Оренбург", "Orenburg"),
    "novokuznetsk": ("Новокузнецк", "Novokuznetsk"),
    "ryazan": ("Рязань", "Ryazan"),
}

_script_dir = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_script_dir, "..", "assets")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_SIZE = 800
USER_AGENT = "RussianWeatherBot/1.0 (city photos from Commons)"

# По 3–4 фото на город. Точные имена файлов с Wikimedia Commons (проверенные в city-landmark-images).
CITY_COMMONS_FILES: dict[str, list[str]] = {
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
    # Новые города: только исторический центр и достопримечательности, без промышленности
    "yaroslavl": ["Yaroslavl_Church_of_St._John_the_Baptist.jpg", "Yaroslavl_Spaso-Preobrazhensky_monastery.jpg", "Yaroslavl_Volga_embankment.jpg"],
    "stavropol": ["Stavropol_Kazan_Cathedral.jpg", "Stavropol_central_park.jpg", "Stavropol_downtown.jpg"],
    "sevastopol": ["Sevastopol_Panorama_Museum.jpg", "Sevastopol_Count_Jetty.jpg", "Sevastopol_Nakhimov_Square.jpg"],
    "naberezhnye_chelny": ["Naberezhnye_Chelny_Tatarstan.jpg", "Naberezhnye_Chelny_boulevard.jpg", "Naberezhnye_Chelny_central_mosque.jpg"],
    "tomsk": ["Tomsk_wooden_house_architecture.jpg", "Tomsk_State_University_main.jpg", "Tomsk_Tom_river.jpg"],
    "balashikha": ["Balashikha_Pechatniki.jpg", "Balashikha_Gorenki_estate.jpg", "Balashikha_church.jpg"],
    "kemerovo": ["Kemerovo_Tom_embankment.jpg", "Kemerovo_drama_theatre.jpg", "Kemerovo_Monument_to_Miners.jpg"],
    "orenburg": ["Orenburg_Caravan_Saray.jpg", "Orenburg_Ural_embankment.jpg", "Orenburg_historic_bridge.jpg"],
    "novokuznetsk": ["Novokuznetsk_Transfiguration_Cathedral.jpg", "Novokuznetsk_city_center.jpg", "Novokuznetsk_Kondoma.jpg"],
    "ryazan": ["Ryazan_Kremlin.jpg", "Ryazan_Assumption_Cathedral.jpg", "Ryazan_embankment.jpg"],
}


def _get_commons_image_url(file_name: str) -> str | None:
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


def _download_image(url: str, retries: int = 2) -> bytes | None:
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read()
        except Exception:
            if attempt < retries:
                time.sleep(2)
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


def main():
    os.makedirs(ASSETS, exist_ok=True)
    total_ok = 0
    for slug, (name_ru, _) in CITIES.items():
        files = CITY_COMMONS_FILES.get(slug, [])
        if not files:
            print(f"  [skip] {name_ru}: нет списка фото")
            continue
        saved = 0
        for i, file_name in enumerate(files):
            if i == 0:
                out_name = f"historic_{slug}.png"
            else:
                out_name = f"historic_{slug}_{i + 1}.png"
            path = os.path.join(ASSETS, out_name)
            time.sleep(0.4)
            url = _get_commons_image_url(file_name)
            if not url:
                continue
            raw = _download_image(url)
            if not raw:
                continue
            if _save_png(raw, path):
                saved += 1
                total_ok += 1
                print(f"  {name_ru} -> {out_name}")
        if saved == 0:
            print(f"  [fail] {name_ru}: не удалось скачать ни одного фото")
    print(f"Готово. Сохранено {total_ok} изображений в {ASSETS}")


if __name__ == "__main__":
    main()
