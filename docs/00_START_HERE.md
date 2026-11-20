# 00 · START HERE — от открытия Terminal до сдачи проекта

Руководство для основного разработчика (MacBook #1, macOS, Apple Silicon).
Все команды — для `zsh` в приложении **Terminal**. Windows-команд здесь нет.

Состояние проекта на момент написания: см. `docs/01_PROGRESS_LOG.md`.

---

## 0. Что это за проект за 30 секунд

GEO Intelligence Lab измеряет, как AI-поисковики (ChatGPT Search, Gemini, Perplexity)
рекомендуют **товарные бренды** (слой A: «какая краска лучше для детской?») и **магазины**
(слой B: «где купить люстру в Астане?») для двух клиентов: Центр Красок №1 и SVET.KZ.

Три части:
1. **Сбор и анализ ответов AI** — какие бренды/магазины названы, какие URL процитированы.
2. **Рекомендации** — конкретные правки сайтов и карточек 2ГИС/Яндекс (production не трогаем).
3. **Контролируемый эксперимент** — локальная BM25-симуляция: страница ДО и ПОСЛЕ правки на одинаковых запросах.

Все KPI считает детерминированный Python. LLM чисел не придумывает.

---

## 1. Открыть Terminal

`Cmd + Пробел` → набрать `Terminal` → `Enter`.

Видите строку вида `<имя>@MacBook ~ %` — это приглашение `zsh`. Знак `%`
вводить не нужно.

---

## 2. Перейти в папку проекта и проверить, где вы

```zsh
cd ~/Desktop/TrAIHaRd-hackathonwinners2026
```
- **`cd`** (change directory) — сменить текущую папку.
- **`~`** — ваша домашняя папка (`/Users/<имя>`).
- Ожидаемый вывод: ничего. Ошибка `no such file or directory` — путь набран неверно; проверьте `ls ~/Desktop`.

```zsh
pwd
```
- **`pwd`** (print working directory) — показывает текущую папку.
- Ожидается: `/Users/<ваше_имя>/Desktop/TrAIHaRd-hackathonwinners2026`.

```zsh
ls -la
```
- **`ls`** — список файлов. **`-l`** — подробный формат, **`-a`** — показывать скрытые (`.git`, `.gitignore`, `.venv`).
- Ожидается: `README.md`, `app.py`, `src`, `data`, `docs`, `tests`, `.git`, `.venv`.

> Новую папку для другого проекта создают так: `mkdir -p ~/Desktop/new-project` —
> **`mkdir`** создаёт каталог, **`-p`** не выдаёт ошибку, если он уже есть, и создаёт промежуточные папки.
> Для этого проекта папка уже создана — **не создавайте новую поверх**.

---

## 3. Проверить инструменты

```zsh
git --version        # ожидается: git version 2.39.x (Apple Git)
python3 --version    # ожидается: Python 3.14.x
which claude         # ожидается: /Users/<имя>/.local/bin/claude
which gh             # сейчас: "gh not found" — GitHub CLI НЕ установлен
```
- **`which`** показывает путь к программе. Пустой ответ / `not found` = программы нет.
- Если `git` не найден, macOS предложит установить Command Line Tools — согласитесь.
- `gh` не обязателен: push работает через обычный `git` (см. §9).

---

## 4. Открыть Claude Code

```zsh
cd ~/Desktop/TrAIHaRd-hackathonwinners2026
claude
```
- Claude Code запускается **в текущей папке** и видит только её. Поэтому сначала `cd`.
- Выход: `/exit` или `Ctrl + C` дважды.
- Команду оболочки прямо из Claude Code можно выполнить с префиксом `!`, например `! git status`.

---

## 5. Python-окружение (уже создано, но вот как это делается)

```zsh
python3 -m venv .venv
```
- **`-m venv`** — запустить встроенный модуль создания виртуального окружения.
- **`.venv`** — имя папки окружения. Она в `.gitignore`, в Git не попадает.
- Нужно один раз. Повторный запуск безопасен.

```zsh
source .venv/bin/activate
```
- **`source`** выполняет скрипт в текущей оболочке; после него `python` и `pip` берутся из `.venv`.
- Признак успеха: в начале строки появится `(.venv)`.
- Выйти: `deactivate`.
- **Делать в каждом новом окне Terminal.**

```zsh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
- **`python -m pip`** — pip именно этого Python (защищает от путаницы версий).
- **`--upgrade`** — обновить. **`-r requirements.txt`** — установить всё из файла.
- Ожидается: `Successfully installed ...` или `Requirement already satisfied`.
- Ошибка сборки (`Failed building wheel`) на Python 3.14 — сообщите в Claude Code; запасной путь — `brew install python@3.12` и окружение на 3.12 (требует Homebrew, не `sudo`).

Проверка импортов:
```zsh
python -c "import streamlit, pandas, plotly, bs4, rank_bm25; print('ok')"
```
Ожидается: `ok`.

---

## 6. Тесты

```zsh
python -m pytest -q
```
- **`pytest`** находит файлы `tests/test_*.py` и запускает функции `test_*`.
- **`-q`** — краткий вывод.
- Ожидается: `25 passed` (число растёт по мере работы). Любое `failed` — **не коммитить в main**, сначала исправить.

---

## 7. Запуск приложения

```zsh
streamlit run app.py
```
- Откроется браузер на `http://localhost:8501`. Если нет — откройте адрес вручную.
- `Ctrl + C` в Terminal — остановить.
- `Port 8501 is already in use` → `streamlit run app.py --server.port 8502`.
- `ModuleNotFoundError` → вы забыли `source .venv/bin/activate`.

Что проверить в браузере:
1. **Обзор** — покрытие сегментов (сколько реальных наблюдений в каждом), присутствие магазинов по городам.
2. **Импорт наблюдений** — загрузить `data/samples/INVALID_example.csv` → таблица ошибок «строка · поле · причина», кнопки сохранения нет.
3. **Наблюдения AI / Реальные KPI / Источники** — N/A, пока нет verified-данных. Под каждой метрикой указано `N`.
4. Переключатель **Режим SYNTHETIC_DEMO** в sidebar — придуманные образцы для проверки UI. Реальные данные в этом режиме скрыты.
5. **Контролируемый эксперимент** — сохранённый результат EXP-001 и кнопка перезапуска.

---

## 8. Ежедневные рабочие команды

### 8.1 Пересобрать корпус для эксперимента (скачать публичные страницы)
```zsh
cd src && python -m geolab.corpus ../data/experiments/corpus_manifest.csv && cd ..
```
- Скачивает URL из манифеста, **соблюдая robots.txt**, сохраняет текст в `data/experiments/corpus/baseline/`.
- `FAIL ... 403` — сайт запрещает автоматический доступ. **Не обходим.** Собираем вручную или исключаем.
- После пересборки результаты эксперимента меняются — перезапустите его и обновите журнал.

### 8.2 Импорт ответов AI (основной поток данных)
Формат и словари: `docs/15_DATA_CONTRACT.md`. Шаблоны: `data/templates/*.csv`.

Через интерфейс: раздел **«Импорт наблюдений»** → выбрать CSV/JSONL → посмотреть ошибки и предпросмотр распознавания → «Сохранить». Файл сохраняется без изменений, одноимённый не перезаписывается.

Через терминал (проверка без сохранения):
```zsh
cd src
../.venv/bin/python -m geolab.contract observations ../data/raw/manual/P3_observations_gemini.csv
cd ..
```
- **`-m geolab.contract`** — запустить валидатор как модуль. Первый аргумент — вид данных (`observations`, `prompts`, `brand_catalog`, `sources`, `proposals`), второй — путь к файлу.
- Ожидается последней строкой: `observations: валидных строк N, ошибок 0, ...`. Код выхода `0` = файл годен.
- Ошибка `ModuleNotFoundError: geolab` → вы не в папке `src`.

Ошибки в уже сохранённых файлах видны в разделе **«Данные и ошибки»**.

---

## 9. Git: commit, ветки, push

### 9.1 Состояние
```zsh
git status
```
Показывает изменённые / новые файлы. Делайте **перед каждым commit**.

```zsh
git diff --check
```
Ищет ошибки пробелов и конфликтные маркеры. Пустой вывод = хорошо.

### 9.2 Проверка, что нет секретов
```zsh
git status --ignored | grep .env
grep -rnE "sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}" --exclude-dir=.venv --exclude-dir=.git . || echo "секретов не найдено"
```
- `.env` должен быть только в разделе Ignored.
- **`grep -r`** — рекурсивный поиск, **`-n`** — номера строк, **`-E`** — регулярное выражение (типовые форматы ключей OpenAI и Google).

### 9.3 Commit
```zsh
git add README.md app.py src tests data docs requirements.txt .gitignore .env.example
git commit -m "feat: deterministic GEO core, controlled experiment EXP-001"
```
- **`git add <пути>`** — добавить в «индекс» то, что войдёт в commit. Перечисляйте пути явно, а не `git add .` — так меньше риск закоммитить лишнее.
- **`-m "..."`** — сообщение commit. Префиксы: `feat:` функция, `fix:` исправление, `docs:` документация, `data:` данные.

### 9.4 Ветки
- `main` — всегда рабочая версия, которую можно показать жюри.
- Задачи — в ветках:
```zsh
git switch -c feature/source-intel   # -c = создать и переключиться
git switch main                      # вернуться на main
git merge feature/source-intel       # влить ветку в текущую (main)
```
- Конфликт при merge: Git отметит файлы `<<<<<<<`. Откройте файл, оставьте нужное, затем `git add <файл>` и `git commit`.

### 9.5 GitHub
Ветки проекта: `main` (стабильная интеграция), `feat/core-app` (P1), `codex/qa-experiments`, `research/brand-sources` (P2), `data/ai-baseline` (P3). Подробно — `docs/07_TEAM_TASKS.md`.

Удалённый репозиторий уже настроен:
```zsh
git remote -v
# origin  https://github.com/Zufics2/TrAIHaRd-hackathonwinners2026.git
```
Первый push:
```zsh
git push -u origin main
```
- **`origin`** — имя удалённого репозитория, **`main`** — ветка.
- **`-u`** — запомнить связь, дальше достаточно `git push`.
- Вход: на этом Mac Git хранит данные входа в Связке ключей (`credential.helper = osxkeychain`). Если пароль спрашивают — подходят Personal Access Token, Git Credential Manager (`brew install --cask git-credential-manager`, открывает браузер) или SSH-ключ (`git remote set-url origin git@github.com:Zufics2/TrAIHaRd-hackathonwinners2026.git`). Пароль от аккаунта GitHub **не** подходит.
- `Permission denied` / `403` — у вашего аккаунта нет прав на запись в `Zufics2/...`. Обходить нельзя: попросите владельца репозитория добавить вас в Collaborators.

Отправить свою ветку:
```zsh
git push -u origin feat/core-app
```
- **Никогда** не используйте `git push --force` в `main`.

Получить изменения коллег:
```zsh
git pull --rebase origin main
```
- **`--rebase`** — поставить ваши локальные коммиты поверх свежих, без лишних merge-коммитов.

---

### 9.6 Отдельная папка для Codex (git worktree)
Codex работает **не** в основной папке, чтобы не мешать вашим изменениям. Worktree уже создан:
```zsh
git worktree list
# .../TrAIHaRd-hackathonwinners2026  [feat/core-app]
# .../TrAIHaRd-codex                 [codex/qa-experiments]
```
Если его нужно создать заново:
```zsh
git worktree add ../TrAIHaRd-codex codex/qa-experiments
```
- **`worktree add <папка> <ветка>`** — вторая рабочая папка того же репозитория на другой ветке. Одна ветка может быть открыта только в одной папке.

Обновить ветку Codex до свежего `main`, а затем запустить Codex:
```zsh
cd ~/Desktop/TrAIHaRd-codex
git merge main
python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt
codex
```
- `git merge main` в папке Codex забирает стабильные изменения. В основной папке результат Codex забирают так: `git merge codex/qa-experiments`.
- Codex правит только свои файлы (`docs/15_DATA_CONTRACT.md §5`).

## 10. Типовые ошибки

| Симптом | Причина | Что делать |
|---|---|---|
| `command not found: streamlit` | не активирован `.venv` | `source .venv/bin/activate` |
| `ModuleNotFoundError: geolab` | запуск модуля не из `src` | `cd src && python -m geolab...` |
| Метрики `N/A` | нет verified-данных в срезе | импортируйте ответы, проставьте `verified`, проверьте фильтры этап/город |
| `Ошибок в файлах данных` в sidebar | невалидная строка CSV | раздел «Данные и ошибки» покажет файл, строку и поле |
| `treatment document missing` | нет файла в `corpus/treatment/` | создайте treatment с тем же `doc_id` |
| `fatal: not a git repository` | вы не в папке проекта | `cd ~/Desktop/TrAIHaRd-hackathonwinners2026` |

---

## 11. Подготовка демо (утро 21 ноября)

```zsh
cd ~/Desktop/TrAIHaRd-hackathonwinners2026
source .venv/bin/activate
git pull --rebase origin main
python -m pytest -q
streamlit run app.py
```
- Пройдите сценарий `docs/11_DEMO_SCRIPT.md` дважды.
- Держите сохранённые результаты (`data/experiments/results/*.json`, ответы в `data/raw/`) — демо не зависит от живого API.
- Feature freeze в 08:15: после этого только исправления, без новых функций.
