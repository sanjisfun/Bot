# Деплой: веб-панель и бот отдельно

Структура репозитория:

- **`web/`** — React-панель (Vite), деплой как статика.
- **`bot/`** — Telegram-бот (Python + aiogram).

Веб-приложение и бот — **независимые** части. Сначала опубликуйте сайт и получите стабильный **HTTPS** URL, затем укажите его в переменной **`WEBAPP_URL`** у бота.

---

## 1. Веб-приложение (Vite + React)

Код в каталоге **`web/`**. Сборка выдаёт статику в **`web/dist/`** (один самодостаточный `index.html` благодаря `vite-plugin-singlefile`).

### Локальная сборка

```bash
cd web
npm ci
npm run build
```

Каталог для загрузки на хостинг: **`web/dist/`**.

### Cloudflare Pages

1. Подключите репозиторий или загрузите проект.
2. **Root directory / Base directory:** `web`
3. **Build command:** `npm run build`
4. **Build output directory:** `dist`
5. **Environment:** Node 20+ (или версия из `web/package.json`).
6. После деплоя скопируйте URL вида `https://xxxx.pages.dev` (или свой домен).

### Netlify

1. New site from Git (или drag-and-drop содержимое `web/dist` после локальной сборки).
2. **Base directory:** `web` (если доступно), иначе в корне репозитория задайте publish: `web/dist`.
3. Build: `cd web && npm ci && npm run build`, publish: `web/dist`.

### Vercel

1. Import репозитория, **Root Directory** — **`web`** (где лежит `package.json` панели).
2. Framework Preset: **Other**, Build: `npm run build`, Output: **`dist`**.

### Домен для Telegram Mini App

В [@BotFather](https://t.me/BotFather): **Bot Settings → Configure Mini App / Domain** — добавьте домен, с которого открывается панель (без `https://`, например `myapp.pages.dev`). Для теста на `*.pages.dev` следуйте подсказкам BotFather.

---

## 2. Telegram-бот (Python, long polling)

Нужны переменные окружения:

| Переменная       | Обязательно | Описание |
|-----------------|------------|----------|
| `BOT_TOKEN`     | Да         | Токен от @BotFather |
| `WEBAPP_URL`    | Нет*       | Полный HTTPS URL панели из шага 1; если не задан — кнопки Mini App скрыты |
| `BOT_DATA_FILE` | Нет        | Путь к `bot_data.json` (по умолчанию `bot_data.json` в текущей папке) |

\* Рекомендуется после деплоя фронта.

### Локальный запуск

Из папки `bot`:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
set BOT_TOKEN=ваш_токен
set WEBAPP_URL=https://ваш-сайт.example.com
python bot.py
```

### Docker

Из папки **`bot`**:

```bash
docker build -t admin-guard-bot .
docker run -d --name admin-guard-bot ^
  -e BOT_TOKEN=ваш_токен ^
  -e WEBAPP_URL=https://ваш-сайт.example.com ^
  -v admin_guard_data:/data ^
  admin-guard-bot
```

На Linux/macOS замените строку с `^` на `\` для переноса строк. Образ по умолчанию пишет данные в `/data/bot_data.json` внутри контейнера; том `-v admin_guard_data:/data` сохраняет файл между перезапусками.

### VPS (systemd, пример)

1. Скопируйте папку `bot` на сервер, установите зависимости в venv.
2. Юнит `/etc/systemd/system/admin-guard-bot.service`:

```ini
[Unit]
Description=Admin Guard Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/admin-guard-bot
Environment=BOT_TOKEN=ваш_токен
Environment=WEBAPP_URL=https://ваш-сайт.example.com
Environment=BOT_DATA_FILE=/opt/admin-guard-bot/data/bot_data.json
ExecStart=/opt/admin-guard-bot/.venv/bin/python /opt/admin-guard-bot/bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Создайте каталог для данных, затем `sudo systemctl enable --now admin-guard-bot`.

### Railway / Render / Fly.io

- Тип процесса: **long-running worker** (не «только HTTP»).
- **Start command:** `python bot.py` (working directory — папка с `bot.py` и `requirements.txt`).
- Задайте переменные `BOT_TOKEN` и `WEBAPP_URL` в панели сервиса.
- Уточните в документации платформы, сохраняется ли диск; при эфемерной ФС данные в `bot_data.json` могут пропадать при redeploy — тогда используйте привязанный volume или вынесите хранилище в БД.

---

## Порядок действий

1. Деплой **веб-панели** → получить HTTPS URL.
2. При необходимости настроить домен в BotFather для Mini App.
3. Деплой **бота** с `BOT_TOKEN` и тем же URL в `WEBAPP_URL`.
