# GEO Intelligence Lab

AIHack 2026 · кейс ProNovation «Как быть первым в ИИ-поиске».

Платформа измеряет, как AI-поиск рекомендует **товарные бренды** (слой A) и **магазины** (слой B)
для Центр Красок №1 (краски) и SVET.KZ (люстры) в Алматы, Астане и Караганде, показывает
процитированные источники, предлагает правки и проверяет их в контролируемом эксперименте.

## Запуск (macOS)

```zsh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

Подробно: [docs/00_START_HERE.md](docs/00_START_HERE.md). Состояние: [docs/01_PROGRESS_LOG.md](docs/01_PROGRESS_LOG.md).

## Принципы

- Все KPI считает детерминированный Python; неопределённое значение = N/A, не 0.
- Статусы данных `REAL` / `MANUAL_VERIFIED` / `CONTROLLED_EXPERIMENT` / `SYNTHETIC_DEMO` не смешиваются.
- Контролируемый эксперимент — BM25-симуляция извлечения, а не замер ChatGPT. Это подписано везде, где он показан.
- Production-сайты клиентов не изменяются; правки — предложения в `data/processed/recommendations.json`.
