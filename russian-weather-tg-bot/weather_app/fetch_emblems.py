# -*- coding: utf-8 -*-
"""Fetch 48px thumbnail URLs for Russian city coats of arms from Wikimedia Commons API."""
import urllib.request
import urllib.parse
import json
import sys

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

def main():
    out = {}
    for slug, fname_list in CITY_FILES:
        url = fetch_thumb(slug, fname_list)
        if url:
            out[slug] = url
            print(slug, "OK")
        else:
            print(slug, "MISSING")
    with open("emblems_new.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Written emblems_new.json with", len(out), "cities")

if __name__ == "__main__":
    main()
