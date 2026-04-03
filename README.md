# Контрольная работа №3 — FastAPI / ТРСП

Монолитное FastAPI-приложение, реализующее задания **6.1–6.5**, **7.1**, **8.1–8.2**: аутентификация (Basic + JWT), хеширование паролей через bcrypt, режимы `DEV`/`PROD`, rate limiting, RBAC, SQLite и полноценный CRUD для задач (`todos`).

---

## Быстрый старт

```bash
# 1. Клонировать и перейти в директорию проекта
git clone <repo-url> && cd <repo-dir>

# 2. Создать виртуальное окружение и активировать его
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env             # при необходимости отредактируйте .env

# 5. Запустить приложение
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> Таблицы в БД создаются автоматически при первом запуске. Если нужно создать их вручную заранее: `python scripts/init_db.py`

Приложение будет доступно по адресу: **http://127.0.0.1:8000**

---

## Переменные окружения

| Переменная | Описание | Пример |
|---|---|---|
| `MODE` | Режим запуска: `DEV` или `PROD` | `DEV` |
| `DOCS_USER` | Логин для доступа к `/docs` (только DEV) | `docs` |
| `DOCS_PASSWORD` | Пароль для доступа к `/docs` (только DEV) | `secret` |
| `JWT_SECRET` | Секретный ключ для подписи токенов | `supersecret` |
| `JWT_ALGORITHM` | Алгоритм JWT | `HS256` |
| `JWT_EXPIRE_MINUTES` | Время жизни токена в минутах | `60` |
| `DATABASE_PATH` | Путь к файлу SQLite | `app.db` |

**Поведение в зависимости от режима:**
- `DEV` — Swagger (`/docs`) и OpenAPI (`/openapi.json`) доступны под Basic Auth; `/redoc` отдаёт 404.
- `PROD` — `/docs`, `/openapi.json`, `/redoc` отдают **404**. Документация полностью скрыта.

---

## API — примеры запросов

### Регистрация и вход

```bash
# Регистрация (лимит: 1 запрос/мин)
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "s3cr3t", "role": "user"}'

# Вход по JSON и получение JWT (лимит: 5 запросов/мин)
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "s3cr3t"}'

# Вход через Basic Auth (задание 6.2)
curl -u alice:s3cr3t http://127.0.0.1:8000/login
```

### Защищённые ресурсы

```bash
# Сохраните токен из ответа /login
TOKEN="<вставьте access_token>"

# Обращение к защищённому эндпоинту
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/protected_resource
```

### CRUD для задач (`/todos`)

Требует JWT. Доступ по ролям: `admin` — полный CRUD, `user` — создание/чтение/обновление, `guest` — только чтение.

```bash
# Создать задачу
curl -X POST http://127.0.0.1:8000/todos \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Купить продукты", "description": "Молоко, яйца, хлеб"}'

# Получить задачу по ID
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/todos/1

# Обновить задачу
curl -X PUT http://127.0.0.1:8000/todos/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Купить продукты", "description": "Обновлённый список", "done": true}'

# Удалить задачу (только admin)
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/todos/1
```

### RBAC

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/rbac/admin/ping
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/rbac/user/readwrite
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/rbac/guest/read
```

### Документация (только DEV)

```bash
# Swagger UI
curl -u docs:secret http://127.0.0.1:8000/docs

# Убедиться, что в PROD документация закрыта
curl -i http://127.0.0.1:8000/docs    # ожидается: HTTP 404
```

---

## Структура проекта

```
.
├── main.py          — приложение, маршруты, режимы документации, rate limiting
├── auth.py          — bcrypt (PassLib), Basic Auth, JWT, RBAC-зависимости
├── config.py        — настройки через pydantic-settings
├── database.py      — подключение к SQLite, init_db()
├── models.py        — Pydantic-схемы запросов и ответов
├── rbac.py          — роли и разрешения
├── scripts/
│   └── init_db.py   — ручное создание таблиц
├── .env.example     — пример переменных окружения
└── requirements.txt
```

---

## Примечание о безопасности паролей

В таблице `users` поле `password` хранит **хеш bcrypt**, а не пароль в открытом виде. Это соответствует требованиям заданий 6.2 и 6.5. Сравнение паролей при входе выполняется через `passlib.verify`, без обратного декодирования хеша. 

## Выполнила

Гришутина А.В.  
ЭФБО-17-24
