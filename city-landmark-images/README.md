# City Landmark Images

Загрузка и подготовка картинок для бота погоды и новостей по городам-миллионникам России.

**Связанный репозиторий:** [russian-weather-tg-bot](https://github.com/gpro7724-netizen/russian-weather-tg-bot) — Telegram-бот использует эти картинки (historic + landmarks) при выводе погоды по городу.

## Что здесь

- **download_historic_photos.py** — скачивает по одному фото «исторический центр» для каждого города (Wikipedia + Wikimedia Commons). Результат: `assets/historic_{slug}.png`.
- **download_landmarks.py** — скачивает по 3 фото достопримечательностей на город из Wikimedia Commons. Результат: `assets/landmark_{slug}_1.png`, `_2.png`, `_3.png`.
- **cities.py** — список городов (slug, name_ru, name_en) для обоих скриптов.

## Запуск

```bash
pip install -r requirements.txt
python download_historic_photos.py
python download_landmarks.py
```

Картинки появятся в папке `assets/`. Её можно скопировать в проект бота в каталог `assets/` рядом с `bot.py`.

## Требования

- Python 3.10+
- Pillow
