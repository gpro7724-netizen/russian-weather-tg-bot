# Дозаполнение картинок для мини-приложения: для городов без ни одного фото
# в weather_app/assets/ генерируется historic_{slug}.png (как в боте).
# Запуск из папки с bot.py: python ensure_weather_app_assets.py

import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from bot import (
    RUSSIAN_MILLION_PLUS_CITIES,
    _generate_historic_center_image,
    _script_dir,
)

WEATHER_APP_ASSETS = os.path.join(_script_dir, "weather_app", "assets")

def _city_image_candidates(slug: str):
    return [
        f"historic_{slug}.png",
        f"historic_{slug}_2.png",
        f"historic_{slug}_3.png",
        f"historic_{slug}_4.png",
        f"historic_{slug}_5.png",
        f"historic_{slug}_6.png",
        f"landmark_{slug}_1.png",
        f"landmark_{slug}_2.png",
        f"landmark_{slug}_3.png",
        f"city_{slug}_1.png",
    ]

def _city_has_primary_image(slug: str) -> bool:
    """Есть ли основной файл historic_{slug}.png (первый кандидат в мини-аппе)."""
    return os.path.isfile(os.path.join(WEATHER_APP_ASSETS, f"historic_{slug}.png"))

def main():
    os.makedirs(WEATHER_APP_ASSETS, exist_ok=True)
    added = 0
    for city in RUSSIAN_MILLION_PLUS_CITIES.values():
        if _city_has_primary_image(city.slug):
            continue
        path = os.path.join(WEATHER_APP_ASSETS, f"historic_{city.slug}.png")
        try:
            with open(path, "wb") as f:
                f.write(_generate_historic_center_image(city))
            print(f"  + {city.name_ru} -> weather_app/assets/historic_{city.slug}.png")
            added += 1
        except Exception as e:
            print(f"  ! {city.name_ru}: {e}", file=sys.stderr)
    print(f"Done. Added: {added}")

if __name__ == "__main__":
    main()
