# Как включить GitHub Pages (убрать 404)

Если при открытии ссылки на приложение погоды вы видите **«404 There isn't a GitHub Pages site here»**, сделайте следующее.

## Шаг 1. Включите GitHub Pages в настройках репозитория

1. Откройте репозиторий на GitHub:  
   **https://github.com/gpro7724-netizen/russian-weather-tg-bot**
2. Перейдите в **Settings** (Настройки).
3. В левом меню выберите **Pages** (в разделе "Code and automation").
4. В блоке **Build and deployment**:
   - **Source** выберите **GitHub Actions** (не "Deploy from a branch").
5. Сохраните — ничего больше нажимать не нужно.

После этого сайт будет публиковаться workflow'ом при каждом push в `main`/`master`.

## Шаг 2. Запустите деплой (если ещё не было push после включения Pages)

- Сделайте любой **push в ветку `main`** (например, пустой коммит или изменение в этом репозитории).  
- Либо откройте вкладку **Actions**, найдите workflow **"Deploy Weather App to GitHub Pages"** и при необходимости нажмите **Run workflow** для ветки `main`.

## Шаг 3. Дождитесь окончания workflow

1. Вкладка **Actions** → выберите последний запуск workflow.
2. Убедитесь, что job **deploy** завершился зелёной галочкой (успех).
3. Обычно через 1–2 минуты после успешного деплоя сайт станет доступен.

## Шаг 4. Правильные ссылки

После включения Pages используйте именно эти адреса:

| Приложение   | Ссылка |
|-------------|--------|
| Погода      | **https://gpro7724-netizen.github.io/russian-weather-tg-bot/weather_app/** |
| Pac-Man     | **https://gpro7724-netizen.github.io/russian-weather-tg-bot/mini_app/** |
| Корень сайта | **https://gpro7724-netizen.github.io/russian-weather-tg-bot/** (редирект в погоду) |

Важно: в конце ссылки на приложение погоды должен быть слэш — **`/weather_app/`**, не просто `weather_app`.

## Если всё ещё 404

- Проверьте, что в **Settings → Pages** выбран источник **GitHub Actions**.
- Убедитесь, что в **Actions** последний workflow **Deploy Weather App to GitHub Pages** выполнен без ошибок.
- Подождите 2–5 минут после первого деплоя — GitHub иногда обновляет с задержкой.
- Откройте именно ссылку с `/weather_app/` в конце (см. таблицу выше).
