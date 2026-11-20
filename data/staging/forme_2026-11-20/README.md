# Staging: первые 6 реальных ответов AI (папка `forme`, 2026-11-20)

**Статус (обновлено 2026-11-20 17:20): ИМПОРТИРОВАНО 10 ответов** как `MANUAL_REPORTED / self_attested` → `data/raw/manual/P3_observations_forme_2026-11-20.csv` (см. `EVIDENCE_MATRIX.md`, раздел v2). Ниже — история этапов.

~~Статус: НЕ ИМПОРТИРОВАНО.~~ Эта папка не читается дашбордом (`store.REAL_DIRS` = `data/raw/manual`, `data/raw/api`).
Строки не входят ни в реальные KPI, ни в «Наблюдения AI», пока не будут исправлены блокеры ниже.

## Исходные файлы (не изменялись)

| Файл | sha256 | Что внутри |
|---|---|---|
| `forme/Запросы.docx` | `6de08fed…c8a8337` | 6 блоков «ID · Сервис и время · Ответ · Ссылки», гиперссылки источников. **Текстов запросов нет.** В копию не перенесён (метаданные содержат имя автора). |
| `forme/observations.jsonl` → `original_observations.jsonl` | `237c259e…4599dfa` | 6 записей в собственной схеме участника (`observation_id`, `response_text`, `mentioned_entities`, …). Не соответствует контракту. |

Сверка: для 2 Gemini-ответов (OBS-002, OBS-005) текст JSONL совпадает с docx; в OBS-001 отличается одним переводом строки.
Для 3 ChatGPT-ответов (OBS-003/004/006) JSONL — **сокращённая и переформатированная** версия (удалены строки, переносы заменены на « — », «; »),
а `citations` содержит 1–2 URL вместо 3–11 гиперссылок из docx. Поэтому источником истины взят **docx**.

## Производная копия `observations_contract_staging.jsonl`

Сформирована `scripts/forme_2026-11-20/{parse_docx,build_staging}.py`. Только формат, факты не менялись:

| Поле | Откуда |
|---|---|
| response_id | `observation_id` участника (OBS-001…006) |
| prompt_id | ID участника (`P-PA-ALM-001`…) — **нет в `prompts.csv`** |
| query | **пусто — в исходниках нет текста запроса** |
| provider | `gemini_search`→`gemini`, `chatgpt_search` (docx: «Gemini Search» / «GPT Search») |
| search_mode | `true` → `search_on` |
| timestamp | из JSONL (дата 2026-11-20, `+05:00`); время совпадает с docx |
| run_no | `1` (в исходниках не указано; один ответ на запрос) |
| language | `ru` (ответы на русском) |
| answer_text | docx, текст между «Ответ:» и «Ссылки:» дословно, включая подписи картинок и карты; пункты списков Word размечены `- ` |
| cited_urls | все гиперссылки блока, кроме `images.openai.com` (миниатюры картинок); `utm_*` сохранены |
| data_type / verification_status | `MANUAL_VERIFIED` / `pending` |
| collector, verified_by | **пусто — неизвестно, P2 или P3** |
| evidence_link | `assets/evidence/OBS-00N.png` — имя из `evidence_reference` участника; **файлов скриншотов нет** |

Раздел «Ссылки:» каждого блока (подписи источников) сохранён отдельно в `docx_refs_sections.json`.

## Валидация (`python -m geolab.contract observations …`)

- `original_observations.jsonl`: 0 валидных, 1 ошибка (нет обязательных столбцов).
- `observations_contract_staging.jsonl`: **0 валидных, 18 ошибок, 6 предупреждений**: по каждой строке `query` пусто, `collector` пусто,
  `prompt_id` нет в `prompts.csv`; предупреждение — скриншот не найден.

## Что нужно для импорта

Повторная проверка (Sprint 005) — `EVIDENCE_MATRIX.md`. Текст ответов, провайдер, время и все 25 citation URL уже есть, повторно их не запрашивать.

1. **Капитан:** кто автор `Запросы.docx` — P2 или P3, и он ли отправлял все 6 запросов. Это одно подтверждение на OBS-001…006.
2. **Сборщик, по каждому OBS-001…006:** точный текст запроса (копией из истории чата). Затем Claude добавит 6 промптов в `prompts.csv`.
3. **Сборщик, по каждому OBS-001…006:** скриншот или share-ссылка на диалог. Без этого допустим импорт как `pending` с предупреждением, но `verified` невозможен.
4. Для `verified` нужна перекрёстная проверка другим участником (`verified_by`).

## Как завершить импорт (Sprint 005)

1. Заполнить `resolution.csv` (по строке на OBS). Поля:
   - `exact_query` + `query_source` — дословный текст запроса и откуда он скопирован;
   - `collector` + `collector_source` — P2 или P3 и кто это подтвердил;
   - `evidence_status`: `available` — есть файл в `assets/evidence/` или share-ссылка; `awaiting` — скриншот обещан; `none` — скриншотов/share-ссылок нет (решение капитана);
   - классификация (`language`, `intent`, `brand_type`, `test_group`, `priority`) — только если запроса ещё нет в `prompts.csv`. Предзаполненные `category`, `city` и `funnel_stage` проверить.
2. Пробный прогон: `cd src && ../.venv/bin/python -m geolab.staging ../data/staging/forme_2026-11-20`. Ничего не записывает, по каждой строке показывает READY / BLOCKED и причину.
3. Запись: тот же вызов с `--apply`. Пишет `data/raw/manual/<collector>_observations_forme_2026-11-20.csv` и при необходимости новые промпты в `prompts.csv`. Существующий файл не перезаписывается без `--replace`.
4. Перевод в `verified`: в `resolution.csv` указать `verification_status=verified`, `verified_by` (не сборщик) и `verification_note` (что сверено), затем запустить с `--apply --replace`. Механизм откажет, если доказательства нет (`awaiting` / `lost`) или файл не найден.
5. `none` → статус `self_attested`: строка видна в «Наблюдениях» и в предварительных показателях, но никогда не становится verified и не входит в verified KPI.

Оригиналы (`Запросы.docx`, `observations.jsonl`, `Bridge.docx`) — копии только для чтения в `data/private/forme_2026-11-20/` (в Git не попадают); sha256 — в `ORIGINALS_SHA256.txt`.
