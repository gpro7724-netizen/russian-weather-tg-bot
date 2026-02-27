# -*- coding: utf-8 -*-
"""Экспорт списка городов в JSON для Web App погоды. Запуск: python export_cities_json.py"""
import json
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))

# Импортируем данные из бота
import sys
sys.path.insert(0, _script_dir)
from bot import RUSSIAN_MILLION_PLUS_CITIES, CITY_TIMEZONES

def main():
    cities = []
    for slug, city in RUSSIAN_MILLION_PLUS_CITIES.items():
        tz = CITY_TIMEZONES.get(slug, "Europe/Moscow")
        cities.append({
            "slug": slug,
            "name_ru": city.name_ru,
            "lat": city.lat,
            "lon": city.lon,
            "timezone": tz,
        })
    out_path = os.path.join(_script_dir, "weather_app", "cities.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cities, f, ensure_ascii=False, indent=2)
    print("Exported", len(cities), "cities to", out_path)

if __name__ == "__main__":
    main()
