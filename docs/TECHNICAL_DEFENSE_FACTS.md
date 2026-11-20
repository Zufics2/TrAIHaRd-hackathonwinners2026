# TECHNICAL DEFENSE FACTS — проверенные факты из исходного кода

Состояние: commit `daf2f6e` (`feat/core-app`). Пути и номера строк указаны по этому commit. Всё ниже проверено по коду и результатам; планы помечены отдельно.

## 1. Стек

- Python 3.14.6.
- Зависимости: Streamlit 1.67.0, pandas 3.1.1, NumPy 2.5.5, Plotly 7.1.0, rank-bm25 0.2.2, requests 2.34.2, beautifulsoup4 4.15.0, pytest 9.2.0. Полный список: `requirements.lock.txt`.
- **LLM внутри продукта не используется.** ChatGPT Search и Gemini — объект измерения; ответы получены вручную.
- Код: `app.py` и `src/geolab/*.py` — 2 106 строк.

## 2. Архитектура

```
data/raw/manual/*.csv|jsonl ──► contract.read_rows / validate_rows ──► store.load_observations
        ▲ (UI upload, staging)                                            │  join prompts.csv
data/staging/<batch> + resolution.csv ──► staging.plan/apply ──┘          ▼
data/registry/entities.json ──► registry.load_registry ──► analysis.analyze_answer ──► metrics.* ──► app.py (Streamlit)
public pages ──► scripts/geo_audit.py, geo_recheck.py (read-only, robots.txt, token redaction) ──► data/research/ ──► recommendations.json
experiment config + corpus (JSON pages) ──► experiment.run_experiment (BM25) ──► results/*.json ──► app.py
```

Два потока не смешиваются:
- **наблюдения** — реальные ответы AI;
- **эксперименты** — `CONTROLLED_EXPERIMENT`, показываются только на своей странице.

## 3. Основные функции (путь:строка)

| Функция | Что делает |
|---|---|
| `src/geolab/contract.py:309` `read_rows` | CSV (`,`/`;`, BOM, многострочные ячейки) и JSONL; нестроковые `cited_urls` → ошибка строки (G07) |
| `src/geolab/contract.py:196` `validate_rows(…, channel)` | схема, словари, ISO-время с поясом (не в будущем), уникальность ID, правила наблюдений |
| `src/geolab/contract.py:248` `_observation_rules` | `REAL_SEARCH` только через `channel="api"`; `MANUAL_REPORTED ⇔ self_attested`; verified = другой проверяющий + существующее https/файл-доказательство + notes; query совпадает с `prompts.csv` |
| `src/geolab/store.py:40` `load_observations` | загрузка `data/raw/manual` (канал manual) и `data/raw/api` (канал api), дубли ID — ошибка, дубли текста — предупреждение |
| `src/geolab/store.py:73` `is_real_kpi_row` | verified KPI: реальный тип, не `MANUAL_REPORTED`, verified, `verified_by ≠ collector`, есть `evidence_link` |
| `src/geolab/staging.py:65` `plan`, `:168` `apply` | завершение импорта по `resolution.csv`: точное совпадение запроса → существующий `prompt_id`, иначе новый промпт с классификацией; без `--replace` не перезаписывает |
| `src/geolab/registry.py:52` `load_registry` | реестр: 38 магазинов (2 клиента + 36 непроверенных кандидатов, включая 4 маркетплейса) и 29 производителей; `case_sensitive`, `case_sensitive_aliases`, `exclude_preceding` |
| `src/geolab/analysis.py:144` `find_entity_spans` | поиск алиасов по границам слов, русские окончания, пересечения считаются 1 раз |
| `src/geolab/analysis.py:260` `mask_sources` | убирает URL, «метки» ChatGPT (`svet.kz+1`), строки «Источники:» перед поиском упоминаний (G10) |
| `src/geolab/analysis.py:294` `_list_items` | пункты списков с номером и вводной фразой; вводная сохраняется для пунктов 2, 3… |
| `src/geolab/analysis.py:237` `_head_entity` | магазин, о котором пункт; повелительные глаголы («Проверьте») — не заголовок (G09) |
| `src/geolab/analysis.py:335` `analyze_answer` | упоминания, рекомендация (эвристика), рейтинг (место = номер пункта, G08), источники |
| `src/geolab/analysis.py:179` `url_key`, `:191` `classify_source` | нормализация URL (без utm/gclid/www/«/»), тип источника по хосту и пути |
| `src/geolab/metrics.py:41` `entity_metrics` | Mention / Recommendation / Top-3 / Citation Rate с N |
| `src/geolab/metrics.py:108` `consistency` | доля прогонов с упоминанием по вопросу × AI |
| `src/geolab/experiment.py:175` `run_experiment` | baseline/treatment, метрики, блок evidence с хешами |
| `src/geolab/corpus.py:94` `redact_session_tokens` | удаляет значения `sessid` / `bitrix_sessid` из HTML |

## 4. Формулы KPI (`metrics.py:41`)

`rate(num, den)` возвращает **None (N/A) при den = 0**, а не 0 (`metrics.py:21`).

| KPI | Числитель / знаменатель |
|---|---|
| Mention Rate | ответов с упоминанием / все ответы среза |
| Recommendation Rate | ответов с `recommended = True` / все ответы среза |
| Top-3 Rate | ответов с `rank ≤ 3` / ответов с явным рейтингом (≥ 2 пункта нумерованного списка вариантов, во главе которых известный магазин) |
| Citation Rate | ответов, где процитирован домен клиента / ответов с ≥ 1 ссылкой |
| Citation Coverage | ответов с ≥ 1 ссылкой / все ответы |
| SoV | упоминаний магазина / сумма упоминаний магазинов категории (по числу ответов) |

Recommendation — детерминированная эвристика:
- магазин стоит во главе пункта списка с вводной-предложением («можно купить в следующих…», «я бы рекомендовал») или пункта явного рейтинга;
- либо в его предложении есть слово-рекомендация, которое не входит в отрицание, и в его части предложения нет отрицания.

Предварительные показатели (блок A) — по всем реальным строкам, кроме `rejected`. Verified (блок B) — только `is_real_kpi_row`.

## 5. BM25 и эксперименты (`src/geolab/experiment.py`, владелец кода — Codex)

- **Алгоритм:** `BM25Okapi(k1=1.5, b=0.75, epsilon=0.25)` по `title + text` документа.
- **Токены:** `\w+` в нижнем регистре, `ё → е`, усечение до 5 символов (`STEM_LEN`), выброс односимвольных.
- **Ответ:** top-5 документов со score > 0, затем уникальные владельцы по порядку (`answer`, `:131`).
- **Метрики целевых запросов:**
  - MRR = среднее 1/место владельца (0, если его нет);
  - Hit@3 = доля запросов с местом ≤ 3;
  - Citation Rate = доля запросов, где документ владельца в top-5;
  - changed-page MRR — то же для изменённой страницы.
- **Evidence:** sha256 каждого документа, sha256 конфига, флаг `negative_control_entity_ranks_unchanged`.

| | Корпус (клиентских) | Целевые / контроли | MRR магазина | Hit@3 | MRR страницы | Результат |
|---|---|---|---|---|---|---|
| EXP-001 | 12 (10) | 4 / 3 | 0.750 → 1.000 | 100% → 100% (насыщен) | 0.5625 → 1.000 | `data/experiments/results/EXP-001_result.json` |
| EXP-001-COMPETITIVE-v1 | 15 (10) | 4 / 5 | 0.479167 → 0.666667 | 75% → 100% | 0.3958 → 0.6667 | `data/experiments/results/EXP-001-COMPETITIVE-v1_result.json` |
| EXP-002-SVET-ASTANA | 12 (8) | 4 / 5 | 0.875 → 0.875 | 100% → 100% | 0.1125 → 0.175 | `data/research/exp002_svet_astana/EXP-002_result.json` |

- Citation Rate — 100% → 100% везде.
- Контроли: ранги магазинов не изменились во всех трёх экспериментах. В EXP-001 изменённая страница вошла в top-5 контроля N2 (место 4).
- В EXP-002 по T1 (вопрос из OBS-005) SVET.KZ на месте 2 → 2.
- Конфиг EXP-002 закоммичен до прогона (`2c8371a` → результат в `6825fa7`). Движок запускается без изменений, через `corpus_dir`.

## 6. Provenance

- **Ответы:** оригиналы (`Запросы.docx`, `Bridge.docx`, версии v1 и v2) хранятся только для чтения в `data/private/` (в `.gitignore`); sha256 — в `data/staging/forme_2026-11-20/ORIGINALS_SHA256.txt`. Конвертация — `scripts/forme_2026-11-20/*.py`. Матрица происхождения каждого поля — `EVIDENCE_MATRIX.md`.
- **Страницы:**
  - `audit.json` и `fetch_meta.json`: время, статус, `sha256` сырого ответа и `sha256_redacted` отслеживаемого файла;
  - сырые копии — в `data/private/geo_snapshots_raw/`.
- **Факты карточек:** `geo_recheck_2026-11-20/checks.json`, 16 утверждений с фрагментом-доказательством, все PASS.

## 7. Безопасность и приватность

- Сайты клиентов только читались, с соблюдением robots.txt, 1 запрос в секунду. Production не изменялся.
- Значения CMS-токенов (`sessid` / `bitrix_sessid`, 43 шт. в 23 снимках) заменены на `REDACTED`. Видимый текст при этом побайтно тот же. Скрипты сбора теперь редактируют токены сразу при загрузке.
- **В неотправленных локальных коммитах `2c8371a…a3d95a4` значения остаются в истории.** На GitHub их нет ни в одной ветке — проверено по всем коммитам, достижимым из `origin/*`.
- Имена из метаданных docx и личные пути в репозиторий не попадают. `data/private/` в `.gitignore`. Скан секретов (`sk-`, `AIza`, `ghp_`, `github_pat_`) — 0.

## 8. Тесты (129)

| Файл | Тестов |
|---|---|
| `tests/test_contract.py` | 28 |
| `tests/test_core.py` | 29 |
| `tests/test_qa_adversarial.py` | 31 |
| `tests/test_experiment_qa.py` | 15 |
| `tests/test_staging.py` | 14 |
| `tests/test_real_path.py` | 12 |

Покрыто:
- контракт и правила verified (включая `REAL_SEARCH`), G06–G13;
- распознавание на реальных текстах (результаты клиентов по 10 ответам зафиксированы тестом);
- staging и парная серия;
- AppTest всех ключевых экранов, deep links;
- воспроизводимость EXP-002;
- отсутствие токенов в снимках;
- соответствие документов результатам (запрещённые формулировки).

## 9. Воспроизводимость

```zsh
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
.venv/bin/python -m pytest -q                                   # 129 passed
.venv/bin/python scripts/real_findings.py                       # KPI и источники из data/raw/manual
.venv/bin/python scripts/geo_recheck.py --offline               # 16/16 PASS по сохранённым страницам
.venv/bin/streamlit run app.py                                  # офлайн
```

Эксперименты детерминированы: сортировка `(-score, doc_id)`, фиксированные параметры, без случайности.

## 10. Ограничения

- 10 ответов `self_attested`, один сборщик, по одному прогону. Этапа A нет. Verified — 0.
- Распознавание работает по ручному реестру, а не по обнаружению. Рекомендация — эвристика. Конкуренты — непроверенные кандидаты.
- BM25 ≠ ChatGPT/Gemini. Корпуса малы и смещены к клиентам (67–83%). Нет qrels и holdout.
- API-коллектора нет, поэтому канал `REAL_SEARCH` пуст.
- Не исправлены G21 (неатомарная запись staging) и G23 (ограничения манифеста `corpus.build`).
