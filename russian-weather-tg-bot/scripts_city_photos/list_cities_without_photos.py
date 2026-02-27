# -*- coding: utf-8 -*-
"""Показывает, у каких городов нет ни одного фото в assets. Запуск: python list_cities_without_photos.py"""
import json
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_script_dir, "..", "assets")
CITIES_JSON = os.path.join(_script_dir, "..", "weather_app", "cities.json")

def _candidates(slug: str):
    out = []
    for i in range(1, 11):
        out.append(f"historic_{slug}.png" if i == 1 else f"historic_{slug}_{i}.png")
    for i in range(1, 4):
        out.append(f"landmark_{slug}_{i}.png")
    for i in range(1, 7):
        out.append(f"city_{slug}_{i}.png")
    return out

def main():
    with open(CITIES_JSON, "r", encoding="utf-8") as f:
        cities = json.load(f)
    missing = []
    for c in cities:
        slug = c["slug"]
        name = c["name_ru"]
        found = any(os.path.isfile(os.path.join(ASSETS, n)) for n in _candidates(slug))
        if not found:
            missing.append((slug, name))
    if not missing:
        print("У всех городов есть хотя бы одно фото.")
        return
    print(f"Города без фото ({len(missing)}):")
    for slug, name in missing:
        print(f"  {slug}: {name}")

if __name__ == "__main__":
    main()
