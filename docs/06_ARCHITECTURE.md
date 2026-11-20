# 06 · Архитектура

## Выбор стека (зафиксирован, Scope Lock 2026-11-20 13:20)

| Критерий | Streamlit (выбран) | React + FastAPI |
|---|---|---|
| Скорость разработки | часы | день+ |
| Технический риск | низкий, один язык | два стека, CORS, сборка |
| Live demo | `streamlit run app.py` | два процесса |
| UX | достаточный для B2B-дашборда | выше, но не окупается за 20 ч |

Python 3.14 · Streamlit 1.67 · pandas 3.1 · Plotly · rank-bm25 · BeautifulSoup · pytest. Хранение — JSON/CSV в `data/` (Git-версионирование вместо БД).

## Поток данных

```
USER (маркетолог)
  ↓
app.py  (Streamlit: фильтры клиент / этап / город / статус данных)
  ↓
src/geolab
  ├─ registry.py   Brand/Manufacturer/Retailer/City registry  ← data/registry/entities.json
  ├─ contract.py   Data contract: словари + построчный валидатор (CLI и UI)
  ├─ store.py      Prompt Dataset + Observation loader/upload ← data/prompts, data/raw/{manual,api}, data/samples
  ├─ analysis.py   Citation Extractor, Source Classifier, Entity Matcher, ranking parser
  ├─ metrics.py    Metrics Calculator, Source table, Share of Voice
  ├─ corpus.py     сбор публичных страниц (robots.txt) → corpus/baseline
  └─ experiment.py Experiment Runner (BM25 retrieval + детерминированный answer engine)
  ↓
data/processed/recommendations.json (GEO Recommendation Engine, ручной + проверяемый)
data/experiments/results/*.json     (Report)
```

Объединены модули ТЗ: Brand/Manufacturer/Retailer/City Registry → `registry.py`; Citation Extractor + Source Classifier + Entity Matchers → `analysis.py`.

## Модель сущностей

```
MANUFACTURER (level=manufacturer, sold_by={retailer_id: evidence})
   ↓ sold by
RETAILER (level=retailer, is_client, cities={city: {status, evidence}})
   ↓ operates in
CITY (almaty | astana | karaganda | national)
```
Статусы связи: `observed` (видели на сайте), `verified` (подтверждено вторым источником), `candidate_unverified`, `watchlist` (бренд для отслеживания, не продаётся клиентом по нашим данным), `delivery_only_claimed`.

## Контракт данных между участниками

Вынесен в [15_DATA_CONTRACT.md](15_DATA_CONTRACT.md): словари, шаблоны, валидатор (`python -m geolab.contract`), правило KPI, владельцы файлов, интерфейс experiment engine.

## Детерминированность

- Сопоставление сущностей — алиасы с Unicode-границами слов; длинный алиас имеет приоритет («Центр Красок №1» считается один раз).
- `Top-3` считается только при нумерованном списке (≥2 пунктов).
- «Рекомендация» — эвристика: сущность в пункте списка или в предложении с маркером рекомендации, без отрицания. Ограничение задокументировано в `docs/08`.
- Неопределённая метрика = `None` → `N/A`.

## Безопасность

- Ключи только в `.env` (в `.gitignore`); `.env.example` без значений.
- Сбор страниц соблюдает robots.txt, 1 запрос/сек, без обхода 403.
- Текст ответов AI и страниц обрабатывается как данные: никогда не передаётся в LLM как инструкция (prompt injection не влияет на метрики, т. к. LLM в ядре нет).
- Production-сайты не изменяются.
