# Скрипты и данные из city-historic-photos

Эта папка — копия репозитория [gpro7724-netizen/city-historic-photos](https://github.com/gpro7724-netizen/city-historic-photos). Скрипты сохраняют файлы в `../assets` (папка `assets` бота).

## Содержимое

- **cities_data.py** — список городов (slug, name_ru, name_en) для скриптов
- **download_historic_photos.py** — главное фото с Wikipedia/Commons → `historic_{город}.png`
- **fetch_historic_center_photos.py** — несколько фото исторического центра → `historic_{город}_2.png` и т.д.
- **download_city_photos.py** — 3–4 фото на город из Commons → `historic_*.png` / `city_*.png`
- **fetch_missing_city_photos.py** — дозагрузка только для городов без ни одного изображения
- **download_landmarks.py** — 3 достопримечательности → `landmark_{город}_1.png`, `_2.png`, `_3.png`

## Запуск (из этой папки)

```bash
pip install -r ../requirements.txt
# или из корня city-historic-photos: pip install -r requirements.txt
python download_historic_photos.py
python fetch_historic_center_photos.py
python download_city_photos.py
python fetch_missing_city_photos.py
python download_landmarks.py
```

Файлы появятся в `../assets`. Бот использует их при выборе города и отправке фото.
