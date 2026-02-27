# Фото городов (из city-historic-photos)

Изображения скопированы из репозитория [gpro7724-netizen/city-historic-photos](https://github.com/gpro7724-netizen/city-historic-photos).

- **historic_{город}.png**, **historic_{город}_2.png**, … — исторический центр (Wikimedia Commons / Wikipedia)
- **landmark_{город}_1.png**, **_2.png**, **_3.png** — достопримечательности
- **city_{город}_*.png** — дополнительные виды города

Чтобы обновить или дозагрузить фото, используйте скрипты в папке `scripts_city_photos/`.

**Если у города нет ни одного фото** (в мини-приложении и в боте показывается заглушка):
1. Запустите из папки `scripts_city_photos/`: `python fetch_historic_center_photos.py`
2. Скрипт для городов без фото скачает по 5 изображений исторического центра с Wikimedia Commons (без промышленных зон).
3. Список городов без фото: `python list_cities_without_photos.py`
