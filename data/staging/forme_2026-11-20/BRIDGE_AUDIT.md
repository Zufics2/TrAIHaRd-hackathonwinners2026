# Read-only аудит `~/Downloads/Bridge.docx` (НЕ импортировано)

Оригинал не изменялся. Копия сохранена в `data/private/forme_2026-11-20/Bridge.docx` (в `.gitignore`), sha256 — в `ORIGINALS_SHA256.txt`.
Файл создан 2026-11-20 16:01 и изменён 16:07 (+05:00). Автор в метаданных тот же, что у `Запросы.docx` (имя не переносится).
Структура docx: 12 частей; таблиц, комментариев, правок, скрытого текста и изображений нет.

| # | ID участника | Сервис, время | Точный запрос | Collector | Citation URLs (уник.) | Миниатюры | Ссылки на диалог / скриншоты | Клиент назван |
|---|---|---|---|---|---|---|---|---|
| 1 | P-BRIDGE-PA-001 | Gemini Search, 16:05 | NOT_FOUND | NOT_FOUND | 1: paintcenter.kz | 0 | NOT_FOUND | Центр красок #1 — да |
| 2 | P-BRIDGE-PA-001 | GPT Search, 16:05 | NOT_FOUND | NOT_FOUND | 2: centr-krasok.kz/catalog/dulux, alma-ata.jsprav.ru (стр. Центра красок) | 3 | NOT_FOUND | Центр красок — да, сайт процитирован |
| 3 | P-BRIDGE-CH-001 | Gemini Search, 16:05 | NOT_FOUND | NOT_FOUND | 8: svet.kz, svetilniki.kz, novasvet.kz, vmasterskoy.kz, artvance.kz, zions.kz, maytoni-shop.kz, kaspi.kz | 0 | NOT_FOUND | SVET.KZ — да |
| 4 | P-BRIDGE-CH-001 | GPT Search, 16:05 | NOT_FOUND | NOT_FOUND | 3: svet.kz/brands/maytoni, svet.kz, maytoni.am | 2 | NOT_FOUND | SVET.KZ — да («официальный дилер») |

Итого: **4 ответа, 14 уникальных citation URL**, 5 миниатюр images.openai.com, 0 ссылок на диалоги, 0 упоминаний скриншотов.

## Отличия от `Запросы.docx`

- Нет JSONL-сопровождения: дату и `+05:00` можно взять только из метаданных файла (это не прямое указание сборщика). Нужно подтверждение.
- **Один ID на два ответа** (Gemini и GPT). Для импорта нужны разные `response_id`, например `BR-G-PA-001` и `BR-C-PA-001`. Сам ID участника станет `prompt_id`.
- Часть URL записана простым текстом или в markdown (`[https://artvance.kz](https://artvance.kz)`) в строке «Ссылки:». При подсчёте нормализовано.
- По смыслу это bridge-запросы (Dulux / Maytoni в Алматы). В `prompts.csv` есть `R-P-ALA-05` «Где в Алматы купить краску Dulux?» и `R-C-ALA-04` «Где купить люстру Maytoni в Алматы?», **но точный текст не подтверждён**. Сопоставление не выполнялось.

## Для импорта нужно (те же блокеры, что у OBS-001…006)

Точный текст 2 запросов, collector, подтверждение даты, скриншоты или share-ссылки (иначе `evidence_lost`). Затем — отдельный staging-batch и `python -m geolab.staging`.
