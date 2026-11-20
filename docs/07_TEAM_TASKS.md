# 07 · Команда, задачи, дедлайны

## Роли (зафиксировано 2026-11-20 13:55)

| Роль | Кто |
|---|---|
| Основной разработчик (код, интеграция, импорт данных) — работает только в `feat/core-app` | **Claude Code** на MacBook #1 (P1) |
| Эксперимент и QA | **Codex** (`codex/qa-experiments`) |
| Research: источники, 2ГИС/Яндекс/соцсети, конкуренты, бренды, правки | **P2** (MacBook #2) |
| Реальные наблюдения AI + питч | **P3** (Windows) |

Пошаговые инструкции для P2/P3 — **`docs/16_TEAM_HANDOFF.md`**. Baseline v1 = 12 запросов из `data/prompts/baseline_v1.csv`.
Подписки на чаты API не дают. Пока ключей нет, MODE 1 = ручной сбор (`MANUAL_VERIFIED`).

## Ветки и рабочие папки

| Ветка | Кто | Рабочая папка |
|---|---|---|
| `main` | стабильная интеграция: только Pull Request с разрешения капитана | `~/Desktop/TrAIHaRd-hackathonwinners2026` (сейчас на `feat/core-app`) |
| `feat/core-app` | P1 + Claude Code | та же |
| `codex/qa-experiments` | Codex | **`~/Desktop/TrAIHaRd-codex`** — отдельный git worktree, уже создан |
| `research/brand-sources` | P2 | свой клон на MacBook #2 |
| `data/ai-baseline` | P3 | свой клон на Windows (или загрузка CSV через дашборд у P1) |

Владельцы файлов — `docs/15_DATA_CONTRACT.md §5`. Никто не правит чужие файлы. Force push запрещён.

## WHAT PARTICIPANT 2 MUST DELIVER (MacBook #2, Gemini · research)

| # | Файл | Минимум | Срок |
|---|---|---|---|
| 1 | `P2_observations_chatgpt_search.csv` (из `data/templates/prefilled_P2_chatgpt_search_baseline_v1.csv`) | 12 запросов baseline v1 × ChatGPT Search; первые 3 строки — к 14:30 | 16:00 |
| 2 | `assets/evidence/OBS-P2-*.png` | скриншот на каждый ответ | 16:00 |
| 3 | `data/research/P2_sources.csv` | 2ГИС + Яндекс Карты + Instagram для обоих клиентов во всех трёх городах (есть / нет / расхождения NAP) | 18:30 |
| 4 | `data/research/P2_sources.csv` (те же строки) | 3–5 конкурентов-магазинов на категорию×город: только те, кто назван AI **или** найден ≥2 независимыми источниками | 18:30 |
| 5 | `data/research/P2_brand_catalog.csv` | ≥10 строк «производитель → магазин клиента» с URL карточки | 19:30 |
| 6 | `data/research/P2_proposals.csv` | ≥6 правок с evidence (сайт, 2ГИС/Яндекс, соцсети) | 21:00 |

## WHAT PARTICIPANT 3 MUST DELIVER (Windows, Gemini Pro · validation)

| # | Файл | Минимум | Срок |
|---|---|---|---|
| 1 | `P3_observations_gemini.csv` (из `data/templates/prefilled_P3_gemini_baseline_v1.csv`) | 12 запросов baseline v1 × Gemini; первые 3 строки — к 14:30 | 16:00 |
| 2 | `P3_observations_perplexity.csv` | те же 12 запросов baseline v1 × Perplexity | 17:30 |
| 3 | повторы `run_no=2` | 12 P0-запросов у того же провайдера (для consistency) | 19:00 |
| 4 | Верификация | проставить `verified` / `rejected` + `verified_by=P3` в файлах **P2** (и наоборот, P2 — в файлах P3): текст совпадает со скриншотом, URL открываются | непрерывно, итог 20:00 |
| 5 | QA | 10 случайных ответов: сравнить распознанные бренды/магазины в дашборде с ручной разметкой → `data/research/P3_qa_matching.md` | 20:00 |
| 6 | Питч | черновик слайдов + вопросы жюри | 23:00 |

## WHAT CODEX MUST DELIVER (`codex/qa-experiments`, папка `~/Desktop/TrAIHaRd-codex`)

1. Тесты `tests/test_experiment*.py`: детерминизм (два прогона = один результат), изоляция treatment (меняются только `changed_doc_ids`), MRR / Top-3 / N/A на граничных случаях.
2. Усиление engine **с сохранением интерфейса** из `docs/15 §6`: повторные прогоны / доверительный интервал по запросам, проверка, что treatment не добавляет фактов без `provenance`.
3. Когда P2 добавит конкурентов в `corpus_manifest.csv`: пересобрать корпус, перезапустить EXP-001, обновить `docs/08 §6`.
4. EXP-002 для SVET.KZ (по рекомендации, согласованной с P1).
5. Не трогать: `app.py`, `src/geolab/{analysis,metrics,store,contract,registry}.py`, `data/registry/`, `data/prompts/`, `data/raw/`.

## Порядок передачи данных (для капитана)

1. P2/P3 заполняют свой CSV в Google Sheets → «Файл → Скачать → CSV».
2. Проверка: дашборд у P1 → «Импорт наблюдений» → загрузить файл. Есть ошибки — таблица «строка · поле · причина» → исправить в Sheets → загрузить снова. **Ничего не правим руками в CSV на MacBook #1.**
3. Без ошибок → кнопка «Сохранить» (файл кладётся в `data/raw/manual/` без изменений; одноимённый файл не перезаписывается).
4. Скриншоты → `assets/evidence/` (AirDrop/Telegram «Избранное» → P1).
5. Claude: `python -m pytest -q` → commit `data: P3 gemini baseline (N rows)` в `feat/core-app` → push `feat/core-app`. В `main` — только через PR после разрешения капитана.
6. Участники с Git вместо шагов 2–4 делают commit в свою ветку и push. Капитан сливает ветку через PR после валидатора: `cd src && ../.venv/bin/python -m geolab.contract observations ../data/raw/manual/<file>`.

## Приоритеты

**P0** — оба клиента · два слоя · реальные ответы AI с цитатами · таблица источников · конкурентное сравнение · ≥1 конкретная правка · контролируемый до/после · KPI · рабочее демо.
**P1** — все 6 сегментов · 2+ провайдера · повторы · несколько экспериментов · отчёт клиенту.
**P2** — автоматический мониторинг, API-коллекторы, граф знаний, деплой.

## План (Asia/Almaty, пересчитан в 13:45)

| Время | P1 + Claude Code | P2 | P3 | Codex | PASS |
|---|---|---|---|---|---|
| 14:00–16:00 | приём файлов, правка распознавания по реальным ответам | наблюдения слой B (ChatGPT) | наблюдения P0 (Gemini) | тесты engine | ≥40 строк импортировано без ошибок |
| 16:00–18:30 | реальные KPI, источники, интеграция веток | 2ГИС/Яндекс/соцсети, конкуренты | Perplexity + перекрёстная верификация | EXP-001 на корпусе с конкурентами | ≥50% строк `verified` |
| 18:30–21:00 | Track C (мост) при готовых A/B, экспорт отчёта | brand catalog, правки | повторы, QA распознавания | EXP-002 | ошибка распознавания < 10% |
| 21:00–00:00 | финальная интеграция | evidence register | слайды, вопросы жюри | финальные метрики | все P0 = PASS |
| 04:00–07:30 | фиксы, прогон демо | — | репетиция ×2 | — | демо ≤ 180 с |
| 08:15 | **feature freeze**, тег `v1.0` | | | | |

Если не успеваем: режем Perplexity, Track C, EXP-002 — **не** качество доказательств.
