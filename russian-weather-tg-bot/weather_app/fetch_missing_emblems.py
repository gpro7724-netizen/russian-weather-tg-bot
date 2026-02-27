# -*- coding: utf-8 -*-
"""For each missing city, search Commons and get first coat of arms thumb URL."""
import urllib.request
import urllib.parse
import json

MISSING = [
    "krasnoyarsk", "voronezh", "volgograd", "tolyatti", "izhevsk", "ulyanovsk",
    "yaroslavl", "stavropol", "sevastopol", "naberezhnye_chelny", "tomsk",
    "balashikha", "kemerovo", "novokuznetsk", "ryazan", "donetsk", "tula",
    "kirov", "kaliningrad", "bryansk", "magnitogorsk", "sochi", "vladikavkaz",
    "tambov", "ivanovo", "tver", "simferopol", "volzhsky", "taganrog",
    "sterlitamak", "komsomolsk_na_amure", "petrozavodsk", "lipetsk",
    "cheboksary", "smolensk"
]

# Russian names for search
NAMES = {
    "krasnoyarsk": "Krasnoyarsk", "voronezh": "Voronezh", "volgograd": "Volgograd",
    "tolyatti": "Tolyatti", "izhevsk": "Izhevsk", "ulyanovsk": "Ulyanovsk",
    "yaroslavl": "Yaroslavl", "stavropol": "Stavropol", "sevastopol": "Sevastopol",
    "naberezhnye_chelny": "Naberezhnye Chelny", "tomsk": "Tomsk",
    "balashikha": "Balashikha", "kemerovo": "Kemerovo", "novokuznetsk": "Novokuznetsk",
    "ryazan": "Ryazan", "donetsk": "Donetsk", "tula": "Tula", "kirov": "Kirov",
    "kaliningrad": "Kaliningrad", "bryansk": "Bryansk", "magnitogorsk": "Magnitogorsk",
    "sochi": "Sochi", "vladikavkaz": "Vladikavkaz", "tambov": "Tambov",
    "ivanovo": "Ivanovo", "tver": "Tver", "simferopol": "Simferopol",
    "volzhsky": "Volzhsky", "taganrog": "Taganrog", "sterlitamak": "Sterlitamak",
    "komsomolsk_na_amure": "Komsomolsk-on-Amur", "petrozavodsk": "Petrozavodsk",
    "lipetsk": "Lipetsk", "cheboksary": "Cheboksary", "smolensk": "Smolensk"
}

def search_and_thumb(city_name):
    search_url = "https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=Coat+of+arms+" + urllib.parse.quote(city_name) + "&srnamespace=6&format=json&srlimit=3"
    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": "WeatherBot/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read().decode())
            for hit in d.get("query", {}).get("search", []):
                title = hit.get("title", "")
                if "Coat" in title and "arms" in title.lower() and city_name.split()[0].lower() in title.lower():
                    # get imageinfo for this file
                    file_url = "https://commons.wikimedia.org/w/api.php?action=query&titles=" + urllib.parse.quote(title) + "&prop=imageinfo&iiprop=url&iiurlwidth=48&format=json"
                    with urllib.request.urlopen(urllib.request.Request(file_url, headers={"User-Agent": "WeatherBot/1.0"}), timeout=12) as r2:
                        d2 = json.loads(r2.read().decode())
                        for pid, p in d2.get("query", {}).get("pages", {}).items():
                            if pid != "-1" and "imageinfo" in p:
                                thumb = p["imageinfo"][0].get("thumburl") or p["imageinfo"][0].get("url", "")
                                if thumb and "upload.wikimedia.org" in thumb:
                                    if "/48px-" not in thumb and "thumb/" in thumb:
                                        for w in ["60px-", "80px-", "330px-", "250px-"]:
                                            if w in thumb:
                                                thumb = thumb.replace(w, "48px-")
                                                break
                                    return thumb
                    break
    except Exception:
        pass
    return None

def main():
    with open("emblems_new.json", "r", encoding="utf-8") as f:
        out = json.load(f)
    for slug in MISSING:
        if slug in out:
            continue
        name = NAMES.get(slug, slug.replace("_", " "))
        url = search_and_thumb(name)
        if url:
            out[slug] = url
            print(slug, "OK")
        else:
            print(slug, "MISS")
    with open("emblems_new.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Total:", len(out))

if __name__ == "__main__":
    main()
