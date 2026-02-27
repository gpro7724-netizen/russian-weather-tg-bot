# Включить GitHub Pages для Pac-Man (убрать 404)

Сайт мини-игры лежит в репозитории **gpro7724-netizen/tg-pacman**, но **GitHub Pages для него не включён** — поэтому открывается «There isn't a GitHub Pages site here».

## Вариант 1: Включить вручную (1 минута)

1. Откройте в браузере:
   **https://github.com/gpro7724-netizen/tg-pacman/settings/pages**

2. В блоке **Build and deployment** → **Source** выберите:
   - **Deploy from a branch**

3. В **Branch** выберите:
   - ветку **main**
   - папку **/ (root)**

4. Нажмите **Save**.

5. Подождите 1–2 минуты. После этого сайт откроется по адресу:
   **https://gpro7724-netizen.github.io/tg-pacman/**

В боте уже указан этот адрес в `.env` как `MINI_APP_URL` — после включения Pages кнопка «🎮 Pac-Man» будет открывать игру.

---

## Вариант 2: Включить через API (если есть токен GitHub)

Если у вас есть Personal Access Token с правом `repo`:

```powershell
$token = "ваш_токен_github"
$body = '{"source":{"branch":"main","path":"/"}}'
Invoke-RestMethod -Uri "https://api.github.com/repos/gpro7724-netizen/tg-pacman/pages" -Method Post -Headers @{
  Authorization = "token $token"
  "Content-Type" = "application/json"
} -Body $body
```

После выполнения подождите 1–2 минуты и проверьте: https://gpro7724-netizen.github.io/tg-pacman/
