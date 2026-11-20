# 15 · Data Contract (LOCKED 2026-11-20 13:45 Asia/Almaty)

Единственный источник правды по формату данных. Допустимые значения в коде: `src/geolab/contract.py`.
Изменения контракта — только через капитана (Workstream A), с обновлением этого файла и тестов.

> Номер 15 выбран, чтобы не ломать нумерацию документов 00–14 из исходного плана. Раздел «Контракт данных» в `06_ARCHITECTURE.md` ссылается сюда.

## 1. Проверка любого файла перед передачей

```zsh
cd ~/Desktop/TrAIHaRd-hackathonwinners2026/src
../.venv/bin/python -m geolab.contract observations ../data/raw/manual/P3_observations_chatgpt.csv
```
Виды: `observations`, `prompts`, `brand_catalog`, `sources`, `proposals`.
Вывод: `ERROR строка 5 · provider: значение 'chatgpt' не из списка [...]`. Код выхода 0 = можно сдавать.
Номер строки — физическая строка файла (заголовок = 1). Для JSONL — номер строки JSON.
Участники без Python загружают CSV в разделе **«Импорт наблюдений»** дашборда — проверка та же.

Общие правила: CSV в **UTF-8** (Excel/Google Sheets: «CSV UTF-8»), разделитель — запятая, текст с переносами и запятыми — в кавычках (Sheets делает это сам). Ничего не исправляется автоматически: строка с ошибкой не импортируется.

## 2. Словари допустимых значений

| Поле | Значения |
|---|---|
| category | `paint`, `chandelier` |
| city | `almaty`, `astana`, `karaganda`, `national` |
| funnel_stage | `brand_discovery` (слой A), `retailer_discovery` (слой B), `bridge` (C) |
| intent | `informational`, `problem-aware`, `category-aware`, `brand-aware`, `comparison`, `transactional`, `local`, `post-purchase` |
| brand_type | `unbranded`, `branded`, `competitor-branded` |
| provider | `chatgpt_search`, `gemini`, `perplexity`, `google_ai_mode`, `google_ai_overview`, `copilot`, `yandex_alice`, `other` |
| search_mode | `search_on`, `unknown`. Ответы без поиска (`search_off`) **не являются** наблюдениями AI-поиска — не импортируются |
| data_type | `REAL_SEARCH` (API), `MANUAL_VERIFIED` (ручной сбор из интерфейса + доказательство), `CONTROLLED_EXPERIMENT` (только experiment engine), `SYNTHETIC_DEMO` (только `data/samples/`) |
| verification_status | `pending`, `verified`, `rejected` |
| entity_level | `manufacturer`, `retailer` |
| source_type | `client_site`, `retailer_site`, `manufacturer_site`, `map_directory`, `marketplace`, `social`, `review_q&a`, `media`, `encyclopedia`, `other_web` |
| implementation_type | `SITE_CONTENT`, `PRODUCT_CARD`, `BRAND_PAGE`, `RETAILER_PAGE`, `CATEGORY_PAGE`, `STRUCTURED_DATA`, `INTERNAL_LINK`, `LOCAL_BUSINESS_PROFILE`, `PRODUCT_CATALOG`, `VERIFIED_THIRD_PARTY_MENTION`, `SOCIAL_CONTENT`, `VERIFIED_REVIEW_RESPONSE` |
| priority | `P0`, `P1`, `P2` · cost / confidence: `low`, `medium`, `high` |
| collector / verified_by | `P1` (капитан, MacBook #1), `P2` (MacBook #2), `P3` (Windows), `CODEX` |
| дата/время | ISO 8601 **с часовым поясом**: `2026-11-20T15:04+05:00`. Не в будущем, не раньше 2026-01-01 |
| ID | латиница, цифры, `_`, `-`; 2–64 символа. Сущности (`entity_id`, `retailer_id`, `manufacturer_id`) — slug `a-z0-9_` из `data/registry/entities.json` |

## 3. Правило KPI

**Реальные KPI** = строки с `data_type ∈ {REAL_SEARCH, MANUAL_VERIFIED}` **и** `verification_status = verified`.
`pending` видны в разделах «Наблюдения» и «Источники» с пометкой, но не входят в KPI. `rejected` скрыты.
`verified` требует `verified_by`, по возможности — **другого** участника (если тот же человек, будет предупреждение).
`SYNTHETIC_DEMO` показывается только при включённом переключателе «Режим SYNTHETIC_DEMO», и тогда реальные данные скрыты.
Результаты эксперимента показываются только в разделе «Контролируемый эксперимент».

## 4. Шаблоны (`data/templates/`)

### 4.1 `observations_template.csv` — ответы AI-поиска
| Поле | Обяз. | Правило |
|---|---|---|
| response_id | да | уникален во всех файлах. Формат: `OBS-<collector>-<NNN>`, например `OBS-P3-001` |
| prompt_id | да | существует в `data/prompts/prompts.csv` |
| query | да | **дословно** как в prompts.csv (сравнение без учёта регистра/пробелов) |
| provider, search_mode | да | словарь |
| model | нет | если видна в интерфейсе |
| timestamp | да | время получения ответа |
| run_no | да | 1, 2, 3… — номер повтора того же запроса у того же провайдера |
| language | да | язык запроса |
| region_setting | нет | город устройства, VPN, вход в аккаунт |
| answer_text | да | **полный** ответ без правок |
| cited_urls | нет | все ссылки-цитаты через ` | `. Пусто = цитат не было (тоже данные) |
| data_type | да | для ручного сбора — `MANUAL_VERIFIED` |
| verification_status | да | `pending` при сборе, `verified`/`rejected` после проверки |
| collector, verified_by | да / нет | см. словарь |
| evidence_link | да для MANUAL_VERIFIED | `assets/evidence/OBS-P3-001.png` или share-ссылка на диалог |
| notes | нет | всё, что влияет на ответ |

### 4.2 `prompts_template.csv` — запросы
Поля как в `data/prompts/prompts.csv` (43 запроса — **сохранены, не перегенерированы**, проходят валидатор). Новые запросы — только через капитана, ID по схеме `R-<P|C>-<ALA|AST|KAR|KZ>-NN` / `B-<P|C>-NN`.

### 4.3 `brand_catalog_template.csv` — связь производитель → магазин
`catalog_id` (`BC-P2-001`), `manufacturer_id`, `manufacturer_name`, `category`, `retailer_id` (должен быть в реестре), `product_name`, `sku`, `evidence_url` (страница, где видно товар), `observed_at`, `availability_note` («Остаток Астана: 1 шт» — дословно), `verification_status`, `collector`, `notes`.
Наличие в каталоге ≠ наличие на складе: пишите в `availability_note` только то, что видно.

### 4.4 `sources_template.csv` — проверенные источники (2ГИС, Яндекс, соцсети, каталоги…)
`source_id` (`SRC-P2-001`), `entity_id`, `entity_level`, `url`, `source_type`, `platform` (`2gis`, `yandex_maps`, `instagram`…), `city`, `ownership` (`owned` / `third_party` / `unknown`), `content_summary` (что реально на странице), `issues_found` (несовпадения телефона, адреса, категории), `cited_in_response_ids` (через ` | `, только если URL реально был в ответе AI), `observed_at`, `verification_status`, `collector`.
SOURCE PRESENCE ≠ AI CITATION: `cited_in_response_ids` пусто, если цитирования не наблюдали.

### 4.5 `proposals_template.csv` — предложения GEO-правок
`issue_id` (`PR-P2-001`), `affected_entity`, `source_url`, `finding`, `evidence` (URL + дата), `implementation_type`, `before`, `after`, `why`, `priority`, `cost`, `expected_mechanism`, `confidence`, `experiment_plan`, `collector`.
Нельзя придумывать свойства товаров: каждый факт в `after` должен быть в `evidence`.

## 5. Куда класть файлы (каждый пишет только свои)

| Кто | Ветка | Файлы |
|---|---|---|
| P1 / Claude Code | `feat/core-app` | `app.py`, `src/geolab/{registry,analysis,metrics,store,contract,corpus}.py`, `data/registry/`, `data/prompts/`, `data/templates/`, docs 00/01/06/07/15 |
| P2 | `research/brand-sources` | `data/research/P2_brand_catalog.csv`, `data/research/P2_sources.csv`, `data/research/P2_proposals.csv`, `data/raw/manual/P2_observations_<provider>.csv`, `assets/evidence/OBS-P2-*.png` |
| P3 | `data/ai-baseline` | `data/raw/manual/P3_observations_<provider>.csv`, `assets/evidence/OBS-P3-*.png` |
| Codex | `codex/qa-experiments` | `src/geolab/experiment.py`, `data/experiments/**`, `tests/test_experiment*.py`, `docs/08_EXPERIMENT_PROTOCOL.md` |

`data/registry/entities.json` правит только P1: P2 присылает новых конкурентов строками в `P2_sources.csv` / `P2_brand_catalog.csv`, P1 переносит их в реестр.

## 6. Интерфейс experiment engine (для Codex)

Текущий API (`src/geolab/experiment.py`) — dashboard зависит от него, менять **с сохранением совместимости**:

| Элемент | Формат |
|---|---|
| Входные документы | `data/experiments/corpus/baseline/<doc_id>.json`: `doc_id, entity_id, url, title, text, source_type, fetched_at, provenance` |
| Treatment | `data/experiments/corpus/treatment/<doc_id>.json`, тот же `doc_id`; `provenance` указывает источники фактов |
| Манифест корпуса | `data/experiments/corpus_manifest.csv`: `doc_id, entity_id, url, source_type, added_by, notes` |
| Конфигурация | `data/experiments/EXP-NNN.json`: `experiment_id, target_entity, changed_doc_ids[], top_k, hypothesis, linked_issue, queries[{query_id, query, role: target|negative_control, prompt_id}]` |
| Функции | `load_experiment(id) → dict`, `run_experiment(exp, corpus_dir=None) → result`, `save_result(result) → Path`, `EXP_DIR` |
| Результат | `data/experiments/results/<id>_result.json`: `experiment_id, target_entity, changed_doc_ids, status="CONTROLLED_EXPERIMENT", per_query[{query_id, query, role, baseline_rank, treatment_rank, baseline_top3, treatment_top3, baseline_cited, treatment_cited, baseline_entities[], treatment_entities[]}], summary{target|negative_control: {baseline|treatment: {queries, top3_rate, citation_rate, mrr}}}, raw{baseline[], treatment[]}` |

Новые поля можно **добавлять**. Удалять или переименовывать — только после согласования с P1, потому что их читает `app.py` (раздел «Контролируемый эксперимент»).
