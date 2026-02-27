# -*- coding: utf-8 -*-
"""Fetch 48px thumbnail URLs for Russian city coats of arms from Wikimedia Commons API."""
import urllib.request
import urllib.parse
import json
import os

# slug -> list of possible Commons filenames (try in order)
CITY_FILES = [
    ("moscow", ["Coat_of_arms_of_Moscow.svg"]),
    ("spb", ["Coat_of_Arms_of_Saint_Petersburg.svg", "Coat_of_arms_of_Saint_Petersburg.svg"]),
    ("novosibirsk", ["Coat_of_Arms_of_Novosibirsk.svg"]),
    ("yekaterinburg", ["Coat_of_Arms_of_Yekaterinburg_(Sverdlovsk_oblast).svg", "Coat_of_Arms_of_Yekaterinburg.svg"]),
    ("kazan", ["Coat_of_Arms_of_Kazan.svg", "Coat_of_arms_of_Kazan_1859.svg"]),
    ("krasnoyarsk", ["Coat_of_Arms_of_Krasnoyarsk.svg"]),
    ("nizhny_novgorod", ["Coat_of_Arms_of_Nizhny_Novgorod.svg"]),
    ("chelyabinsk", ["Coat_of_Arms_of_Chelyabinsk.svg"]),
    ("ufa", ["Coat_of_Arms_of_Ufa.svg", "Coat_of_arms_of_Ufa.svg"]),
    ("krasnodar", ["Coat_of_arms_of_Krasnodar.png", "Coat_of_Arms_of_Krasnodar.svg"]),
    ("samara", ["Coat_of_Arms_of_Samara.svg", "Coat_of_Arms_of_Samara_Oblast.svg", "Coat_of_Arms_of_Samara_1859.svg"]),
    ("rostov_on_don", ["Coat_of_Arms_of_Rostov-on-Don.svg"]),
    ("omsk", ["Coat_of_arms_of_Omsk.svg"]),
    ("voronezh", ["Coat_of_Arms_of_Voronezh.svg"]),
    ("perm", ["Coat_of_Arms_of_Perm.svg"]),
    ("volgograd", ["Coat_of_Arms_of_Volgograd.svg"]),
    ("saratov", ["Coat_of_Arms_of_Saratov.svg"]),
    ("tyumen", ["Coat_of_Arms_of_Tyumen.svg"]),
    ("tolyatti", ["Coat_of_arms_of_Tolyatti.svg", "Coat_of_Arms_of_Tolyatti.svg"]),
    ("mahachkala", ["Coat_of_Arms_of_Makhachkala.svg"]),
    ("barnaul", ["Coat_of_Arms_of_Barnaul.svg"]),
    ("izhevsk", ["Coat_of_Arms_of_Izhevsk.svg"]),
    ("khabarovsk", ["Coat_of_Arms_of_Khabarovsk.svg", "Coat_of_Arms_of_Khabarovsk_1991-2014.svg"]),
    ("ulyanovsk", ["Coat_of_Arms_of_Ulyanovsk.svg"]),
    ("irkutsk", ["Coat_of_Arms_of_Irkutsk.svg"]),
    ("vladivostok", ["Coat_of_Arms_of_Vladivostok.svg"]),
    ("yaroslavl", ["Coat_of_Arms_of_Yaroslavl.svg"]),
    ("stavropol", ["Coat_of_Arms_of_Stavropol.svg"]),
    ("sevastopol", ["Coat_of_Arms_of_Sevastopol.svg"]),
    ("naberezhnye_chelny", ["Coat_of_Arms_of_Naberezhnye_Chelny.svg"]),
    ("tomsk", ["Coat_of_Arms_of_Tomsk.svg"]),
    ("balashikha", ["Coat_of_Arms_of_Balashikha.svg"]),
    ("kemerovo", ["Coat_of_Arms_of_Kemerovo.svg"]),
    ("orenburg", ["Coat_of_Arms_of_Orenburg.svg"]),
    ("novokuznetsk", ["Coat_of_Arms_of_Novokuznetsk.svg"]),
    ("ryazan", ["Coat_of_Arms_of_Ryazan.svg"]),
    ("donetsk", ["Coat_of_arms_of_Donetsk.svg"]),
    ("luhansk", ["Coat_of_arms_of_Luhansk.svg"]),
    ("tula", ["Coat_of_Arms_of_Tula.svg"]),
    ("kirov", ["Coat_of_Arms_of_Kirov_(city).svg", "Coat_of_Arms_of_Kirov_oblast.svg"]),
    ("kaliningrad", ["Coat_of_Arms_of_Kaliningrad.svg"]),
    ("bryansk", ["Coat_of_Arms_of_Bryansk.svg"]),
    ("kursk", ["Kursk_city_COA.svg"]),
    ("magnitogorsk", ["Coat_of_Arms_of_Magnitogorsk.svg"]),
    ("sochi", ["Coat_of_Arms_of_Sochi.svg"]),
    ("vladikavkaz", ["Coat_of_Arms_of_Vladikavkaz.svg"]),
    ("grozny", ["Coat_of_Arms_of_Grozny_(Chechnya).svg"]),
    ("tambov", ["Coat_of_Arms_of_Tambov.svg"]),
    ("ivanovo", ["Coat_of_Arms_of_Ivanovo.svg"]),
    ("tver", ["Coat_of_Arms_of_Tver.svg"]),
    ("simferopol", ["Coat_of_Arms_of_Simferopol.svg"]),
    ("kostroma", ["Coat_of_Arms_of_Kostroma.svg"]),
    ("volzhsky", ["Coat_of_Arms_of_Volzhsky.svg"]),
    ("taganrog", ["Coat_of_Arms_of_Taganrog.svg"]),
    ("sterlitamak", ["Coat_of_Arms_of_Sterlitamak.svg"]),
    ("komsomolsk_na_amure", ["Coat_of_Arms_of_Komsomolsk-on-Amur.svg"]),
    ("petrozavodsk", ["Coat_of_Arms_of_Petrozavodsk.svg"]),
    ("lipetsk", ["Coat_of_Arms_of_Lipetsk.svg"]),
    ("arhangelsk", ["Coat_of_Arms_of_Arkhangelsk.svg"]),
    ("cheboksary", ["Coat_of_Arms_of_Cheboksary.svg"]),
    ("kaluga", ["Coat_of_Arms_of_Kaluga.svg"]),
    ("smolensk", ["Coat_of_Arms_of_Smolensk.svg"]),
    # 200k+ города
    ("penza", ["Coat_of_Arms_of_Penza.svg", "Coat_of_arms_of_Penza.svg", "Coat_of_arms_of_Penza_Oblast_(large).svg"]),
    ("astrakhan", ["Coat_of_Arms_of_Astrakhan.svg", "Coat_of_arms_of_Astrakhan.svg"]),
    ("ulan_ude", ["Coat_of_Arms_of_Ulan-Ude.svg", "Coat_of_arms_of_Ulan-Ude.svg", "Coat_of_arms_of_Ulan-Ude.svg"]),
    ("surgut", ["Coat_of_Arms_of_Surgut.svg"]),
    ("yakutsk", ["Coat_of_Arms_of_Yakutsk.svg", "Coat_of_arms_of_Yakutsk.svg"]),
    ("vladimir", ["Coat_of_Arms_of_Vladimir.svg", "Coat_of_arms_of_Vladimir.svg", "Coat_of_Arms_of_Vladimir_(Vladimir_oblast).svg"]),
    ("belgorod", ["Coat_of_Arms_of_Belgorod.svg"]),
    ("nizhny_tagil", ["Coat_of_Arms_of_Nizhny_Tagil.svg", "Coat_of_arms_of_Nizhny_Tagil.svg"]),
    ("chita", ["Coat_of_Arms_of_Chita.svg", "Coat_of_arms_of_Chita.svg", "Coat_of_Arms_of_Chita_(Zabaykalsky_Krai).svg"]),
    ("podolsk", ["Coat_of_Arms_of_Podolsk.svg", "Coat_of_arms_of_Podolsk.svg"]),
    ("saransk", ["Coat_of_Arms_of_Saransk.svg"]),
    ("vologda", ["Coat_of_arms_of_Vologda_1859.svg", "Coat_of_Arms_of_Vologda.svg", "Coat_of_Arms_of_Vologda_(Vologda_oblast)_(1967).png"]),
    ("kurgan", ["Coat_of_Arms_of_Kurgan.svg"]),
    ("cherepovets", ["Coat_of_Arms_of_Cherepovets.svg", "Coat_of_arms_of_Cherepovets.svg", "Coat_of_Arms_of_Cherepovets_(Vologda_oblast).svg"]),
    ("oryol", ["Coat_of_Arms_of_Oryol.svg", "Coat_of_arms_of_Oryol.svg"]),
    ("nizhnevartovsk", ["Coat_of_Arms_of_Nizhnevartovsk.svg"]),
    ("yoshkar_ola", ["Coat_of_Arms_of_Yoshkar-Ola.svg", "Coat_of_arms_of_Yoshkar-Ola.svg", "Coat_of_Arms_of_Yoshkar-Ola_(Mari_El).svg"]),
    ("murmansk", ["Coat_of_Arms_of_Murmansk_(1968-2004).svg", "RUS_Murmansk_COA.svg", "Coat_of_Arms_of_Murmansk.svg"]),
    ("novorossiysk", ["Coat_of_Arms_of_Novorossiysk.svg"]),
    ("khimki", ["Coat_of_Arms_of_Khimki.svg", "Coat_of_arms_of_Khimki.svg"]),
    ("mytishchi", ["Coat_of_Arms_of_Mytishchi.svg", "Coat_of_arms_of_Mytishchi.svg"]),
    ("nalchik", ["Coat_of_Arms_of_Nalchik.svg"]),
    ("nizhnekamsk", ["Coat_of_Arms_of_Nizhnekamsk.svg", "Coat_of_arms_of_Nizhnekamsk.svg"]),
    ("blagoveshchensk", ["Coat_of_Arms_of_Blagoveshchensk.svg"]),
    ("korolyov", ["Coat_of_Arms_of_Korolyov.svg", "Coat_of_Arms_of_Korolev.svg", "Coat_of_arms_of_Korolyov.svg"]),
    ("shakhty", ["Coat_of_Arms_of_Shakhty.svg", "Coat_of_arms_of_Shakhty.svg"]),
    ("engels", ["Coat_of_Arms_of_Engels_(Saratov_oblast).svg", "Coat_of_Arms_of_Engels.svg"]),
    ("veliky_novgorod", ["Coat_of_Arms_of_Veliky_Novgorod.svg"]),
    ("lyubertsy", ["Coat_of_Arms_of_Lyubertsy.svg", "Coat_of_arms_of_Lyubertsy.svg"]),
    ("bratsk", ["Coat_of_Arms_of_Bratsk.svg", "Coat_of_arms_of_Bratsk.svg"]),
    ("stary_oskol", ["Coat_of_Arms_of_Stary_Oskol.svg"]),
    ("angarsk", ["Coat_of_Arms_of_Angarsk.svg"]),
    ("syktyvkar", ["Coat_of_Arms_of_Syktyvkar.svg", "Coat_of_arms_of_Syktyvkar.svg", "Coat_of_Arms_of_Syktyvkar_(Komi).svg"]),
    ("dzerzhinsk", ["Coat_of_Arms_of_Dzerzhinsk_(Nizhny_Novgorod_Oblast).svg", "Coat_of_Arms_of_Dzerzhinsk.svg"]),
]

def fetch_thumb(slug, filenames):
    if isinstance(filenames, str):
        filenames = [filenames]
    for filename in filenames:
        url = "https://commons.wikimedia.org/w/api.php?action=query&titles=File:" + urllib.parse.quote(filename) + "&prop=imageinfo&iiprop=url&iiurlwidth=48&format=json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WeatherBot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
                pages = d.get("query", {}).get("pages", {})
                for pid, p in pages.items():
                    if pid != "-1" and "imageinfo" in p:
                        thumb = p["imageinfo"][0].get("thumburl") or p["imageinfo"][0].get("url", "")
                        if thumb and "upload.wikimedia.org" in thumb:
                            if "/48px-" not in thumb and "thumb/" in thumb:
                                for w in ["60px-", "80px-", "330px-", "250px-"]:
                                    if w in thumb:
                                        thumb = thumb.replace(w, "48px-")
                                        break
                            return thumb
        except Exception:
            pass
    return None


# Поиск герба по названию города на Commons (если по имени файла не нашли)
SEARCH_NAMES = {
    "penza": "Penza", "ulan_ude": "Ulan-Ude", "yakutsk": "Yakutsk", "nizhny_tagil": "Nizhny Tagil",
    "chita": "Chita", "podolsk": "Podolsk", "vologda": "Vologda", "cherepovets": "Cherepovets",
    "yoshkar_ola": "Yoshkar-Ola", "murmansk": "Murmansk", "khimki": "Khimki", "mytishchi": "Mytishchi",
    "nizhnekamsk": "Nizhnekamsk", "korolyov": "Korolyov", "shakhty": "Shakhty", "engels": "Engels Saratov",
    "lyubertsy": "Lyubertsy", "bratsk": "Bratsk", "syktyvkar": "Syktyvkar", "dzerzhinsk": "Dzerzhinsk Russia",
}


def search_commons_coat(slug, name_en):
    """Ищет на Commons по запросу 'Coat of arms CityName' и возвращает URL 48px или None."""
    q = "Coat of arms " + name_en
    url = "https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=" + urllib.parse.quote(q) + "&srnamespace=6&format=json&srlimit=5"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WeatherBot/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read().decode())
        for hit in d.get("query", {}).get("search", []):
            title = hit.get("title", "")
            if "Coat" not in title or "arms" not in title.lower():
                continue
            # Исключаем гербы областей и других городов (первое слово названия города должно быть в title)
            first_word = name_en.split()[0].lower()
            if first_word not in title.lower():
                continue
            file_url = "https://commons.wikimedia.org/w/api.php?action=query&titles=" + urllib.parse.quote(title) + "&prop=imageinfo&iiprop=url&iiurlwidth=48&format=json"
            req2 = urllib.request.Request(file_url, headers={"User-Agent": "WeatherBot/1.0"})
            with urllib.request.urlopen(req2, timeout=12) as r2:
                d2 = json.loads(r2.read().decode())
            for pid, p in d2.get("query", {}).get("pages", {}).items():
                if pid != "-1" and "imageinfo" in p and p["imageinfo"]:
                    thumb = p["imageinfo"][0].get("thumburl") or p["imageinfo"][0].get("url", "")
                    if thumb and "upload.wikimedia.org" in thumb:
                        return thumb
            break
    except Exception:
        pass
    return None

def main():
    out = {}
    existing_path = "emblems.json"
    if os.path.isfile(existing_path):
        with open(existing_path, "r", encoding="utf-8") as f:
            out = json.load(f)
    for slug, fname_list in CITY_FILES:
        if slug in out:
            continue
        url = fetch_thumb(slug, fname_list)
        if not url and slug in SEARCH_NAMES:
            url = search_commons_coat(slug, SEARCH_NAMES[slug])
        if url:
            out[slug] = url
            print(slug, "OK")
        else:
            print(slug, "MISSING")
    with open("emblems.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Written emblems.json with", len(out), "cities")

if __name__ == "__main__":
    main()
