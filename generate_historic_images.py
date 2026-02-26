# Генерация картинок «Исторический центр» для всех городов.
# Запуск: python generate_historic_images.py
# Сохраняет файлы в assets/historic_{город}.png

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot import (
    RUSSIAN_MILLION_PLUS_CITIES,
    _generate_historic_center_image,
    _script_dir,
)

def main():
    assets = os.path.join(_script_dir, "assets")
    os.makedirs(assets, exist_ok=True)
    for city in RUSSIAN_MILLION_PLUS_CITIES.values():
        path = os.path.join(assets, f"historic_{city.slug}.png")
        with open(path, "wb") as f:
            f.write(_generate_historic_center_image(city))
        print(f"  {city.name_ru} -> {path}")
    print("Готово. Картинки в папке assets/")

if __name__ == "__main__":
    main()
