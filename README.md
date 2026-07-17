# kaiten-mcp

**MCP-сервер для [Kaiten](https://kaiten.ru/)** — интеграция канбан-досок и задач Kaiten с AI-ассистентами ([Cursor](https://cursor.com/), [Claude Code](https://docs.anthropic.com/en/docs/claude-code) и любым MCP-клиентом).

Управляйте карточками прямо из чата: создавайте задачи, перемещайте по колонкам, обновляйте описания, оставляйте комментарии и теги — без ручного копирования из веб-интерфейса и без огромных JSON-ответов API в контексте модели.

## Зачем это нужно

- Подключить **Kaiten к Cursor / Claude Code** через [Model Context Protocol](https://modelcontextprotocol.io/)
- Работать с пространствами, досками, колонками и карточками голосом агента
- Экономить токены: ответы компактные по умолчанию (описания — только по запросу)
- Развернуть локально (stdio) или для команды (Streamable HTTP / Docker / Kubernetes)

## Возможности

- Локальный транспорт **stdio** для Cursor и Claude Code
- Удалённый **Streamable HTTP** (`POST /mcp`) для командного хостинга
- Токен Kaiten на каждый запрос (credentials не сохраняются на диске)
- Компактные списки: страница по умолчанию 20 (макс. 100), без вложений и «шумных» вложенных полей
- Бенчмарки размера payload (`kaiten-mcp-benchmark`), чтобы ответы не раздувались со временем
- Структурированные логи в stderr (безопасно для stdio MCP)

## Быстрый старт

### Требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- API-токен Kaiten (Профиль → API-ключ в вашем инстансе, например `https://<компания>.kaiten.ru/profile/api-key`)

### 1. Установка и запуск

```bash
git clone https://github.com/evvfebruary/kaiten-mcp.git
cd kaiten-mcp
uv sync --all-groups

export KAITEN_API_TOKEN='ваш-токен'
export KAITEN_WORKSPACE_SLUG='ваша-компания'   # → https://ваша-компания.kaiten.ru/api/v1

uv run kaiten-mcp --transport stdio
```

Для on-prem / кастомного домена вместо slug задайте полный корень API:

```bash
export KAITEN_BASE_URL='https://kaiten.example.com/api/v1'
```

Остальные переменные — в [`.env.example`](.env.example).

### 2. Cursor

Конфиг проекта уже есть: [`.cursor/mcp.json`](.cursor/mcp.json).

1. Экспортируйте токен и workspace в окружение, которое наследует Cursor:

```bash
export KAITEN_API_TOKEN='ваш-токен'
export KAITEN_WORKSPACE_SLUG='ваша-компания'
```

2. Перезапустите Cursor после смены переменных окружения.
3. Откройте **Output → MCP Logs** и убедитесь, что сервер `kaiten` подключился.
4. Попросите агента: «покажи пространства» или «найди задачи на доске …».

`${env:KAITEN_API_TOKEN}` и `${env:KAITEN_WORKSPACE_SLUG}` подставляет Cursor. Не коммитьте реальные токены.

### 3. Claude Code

Конфиг проекта: [`.mcp.json`](.mcp.json).

```bash
export KAITEN_API_TOKEN='ваш-токен'
export KAITEN_WORKSPACE_SLUG='ваша-компания'
claude mcp list
```

Или вручную:

```bash
claude mcp add --transport stdio kaiten -- uv run kaiten-mcp --transport stdio
```

## Примеры запросов к агенту

- «Покажи все пространства в Kaiten»
- «Найди доски в пространстве X и создай карточку „Исправить баг логина“»
- «Перенеси задачу #1234 в колонку In Progress»
- «Добавь комментарий к карточке #1234: готово к ревью»
- «Повесь тег „hotfix“ на задачу #1234»

Типовой порядок инструментов:

1. `list_spaces` → `list_boards` → `list_columns` / `list_lanes`
2. `create_task` / `list_tasks` / `get_task` / `update_task` / `move_task`
3. `add_comment` / `add_tag_to_task` при необходимости

## Инструменты MCP

| Инструмент | Назначение |
|------------|------------|
| `list_spaces` | Список пространств (id, title) |
| `list_boards` | Доски пространства |
| `list_columns` | Колонки доски |
| `list_lanes` | Дорожки доски |
| `create_task` | Создать карточку (`title` + `board_id`) |
| `get_task` | Детали задачи (`include_description` — по запросу) |
| `list_tasks` | Фильтрованный компактный список (query, board, column, tag, …) |
| `update_task` | Обновление полей (title, description, owner, condition, …) |
| `move_task` | Перемещение (board / column / lane / sort) |
| `add_comment` / `list_comments` | Комментарии |
| `list_tags` / `get_task_tags` | Теги |
| `add_tag_to_task` | Добавить тег **по имени** |
| `remove_tag_from_task` | Снять тег **по id** |

## Удалённый сервер / Docker / Kubernetes

Streamable HTTP:

```bash
uv run kaiten-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

- Health: `GET /healthz`
- MCP: `POST /mcp`

Docker:

```bash
docker build -t kaiten-mcp .
docker run --rm -p 8000:8000 \
  -e KAITEN_WORKSPACE_SLUG=ваша-компания \
  kaiten-mcp
```

Каждый клиент передаёт свой токен:

```http
Authorization: Bearer <kaiten-api-token>
```

Примеры конфигов:

- [`examples/remote-mcp/cursor.mcp.json`](examples/remote-mcp/cursor.mcp.json)
- [`examples/remote-mcp/claude.mcp.json`](examples/remote-mcp/claude.mcp.json)

Заметки для Kubernetes:

- Stateless-реплики допустимы (`stateless_http=True`)
- TLS — на Ingress
- Увеличьте proxy/read timeouts для streaming
- Не логируйте заголовок `Authorization`
- У Kaiten лимит порядка ~50 req/s — делите бюджет между репликами

Модель с Bearer-токеном на запрос — осознанный выбор v1 (не browser OAuth).

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `KAITEN_API_TOKEN` | Да (stdio) | API-токен; для HTTP — также в `Authorization: Bearer` |
| `KAITEN_WORKSPACE_SLUG` | Да\* | Slug: `acme` → `https://acme.kaiten.ru/api/v1` |
| `KAITEN_BASE_URL` | Да\* | Полный корень API (on-prem); имеет приоритет над slug |
| `KAITEN_HOST` / `KAITEN_PORT` | Нет | Bind для HTTP (по умолчанию `127.0.0.1:8000`) |
| `KAITEN_LOG_LEVEL` | Нет | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `KAITEN_LOG_FORMAT` | Нет | `text` \| `json` |
| `KAITEN_LOG_BODIES` | Нет | Компактные redacted-превью в логах |
| `KAITEN_ENABLE_METRICS` | Нет | Метрики размера payload без секретов |

\* Нужен **либо** `KAITEN_WORKSPACE_SLUG`, **либо** `KAITEN_BASE_URL`.

## Экономия токенов

- Размер страницы списка по умолчанию: **20** (макс. **100**)
- В списках нет описаний, вложений и глубоких дублей
- Мутации возвращают id/url и изменённые поля
- Обрезка явная: `truncated`, `next_offset`, `has_more`
- Коротко описанные схемы инструментов

Проверка бюджетов размера ответа:

```bash
uv run kaiten-mcp-benchmark
uv run kaiten-mcp-benchmark --check
```

## Логирование

Логи всегда идут в **stderr** (совместимо со stdio MCP).

```bash
export KAITEN_LOG_LEVEL=INFO
export KAITEN_LOG_FORMAT=json
uv run kaiten-mcp --transport stdio --log-format json
```

Полезные события: `server_starting`, `tool_start` / `tool_success` / `tool_error`, `kaiten_request`, `kaiten_rate_limited`.

Секреты редактируются; токены видны только как fingerprint вида `token_fp=len=40:…ab12`.

## Разработка

```bash
uv sync --all-groups
uv run ruff format .
uv run ruff check .
uv run ty check
uv run pytest
uv run kaiten-mcp-benchmark --check
```

Live smoke (опционально, не в CI по умолчанию):

```bash
KAITEN_API_TOKEN=... KAITEN_WORKSPACE_SLUG=... uv run pytest -m live
```

## Структура

```text
src/kaiten_mcp/
  api/           # HTTP-клиент и адаптеры эндпоинтов
  tools/         # MCP-инструменты
  auth.py        # Токен на запрос
  config.py      # Настройки
  presentation.py
  metrics.py
  server.py
  __main__.py
tests/
benchmarks/
examples/remote-mcp/
```

## Безопасность

- Токен берётся из HTTP Bearer или `KAITEN_API_TOKEN` на каждый запрос
- Сервер не пишет токены на диск
- Предпочитайте переменные окружения, а не хардкод в MCP JSON
- Права на стороне Kaiten определяются токеном вызывающего

## FAQ

**Как подключить Kaiten к Cursor?**  
Установите зависимости через `uv`, задайте `KAITEN_API_TOKEN` и `KAITEN_WORKSPACE_SLUG`, перезапустите Cursor — конфиг уже в [`.cursor/mcp.json`](.cursor/mcp.json).

**Где взять API-токен Kaiten?**  
В вашем инстансе: Профиль → API-ключ (`https://<компания>.kaiten.ru/profile/api-key`). OAuth у публичного API Kaiten для этого сценария не используется.

**Чем этот сервер отличается от других kaiten-mcp?**  
Фокус на **компактных ответах** и экономии контекста модели, плюс готовый remote Streamable HTTP для команды без хранения токенов на сервере.

**Можно ли развернуть для всей команды?**  
Да: Docker / Kubernetes с `streamable-http`; каждый сотрудник передаёт свой Bearer-токен в заголовке.

**Работает ли с on-prem Kaiten?**  
Да — задайте `KAITEN_BASE_URL` на ваш `/api/v1`.

## Лицензия

[MIT](LICENSE)
