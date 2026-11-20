# FINAL DEMO SCRIPT v2 · 6 слайдов · 3:00 + 2:00 Q&A

Структура — по Положению METU, п. 7.3: проблема → решение → демо → метрики → импакт → план пилота 30–90 дней. Версия v1 на 7 слайдов есть в истории Git (`4f6818c`) — **архив, не использовать**.
Числа — только из `docs/STATUS.md`.

Запуск: `.venv/bin/streamlit run app.py`. Интернет не нужен.

Закладки браузера, открыть заранее в отдельных вкладках:
1. `http://localhost:8501/?page=1&client=svet_kz` — Обзор
2. `http://localhost:8501/?page=3&client=svet_kz&city=astana` — ответ Gemini по Астане
3. `http://localhost:8501/?page=6&client=svet_kz` — GEO-01
4. `http://localhost:8501/?page=7&exp=EXP-001-COMPETITIVE-v1` — эксперимент
5. `http://localhost:8501/?page=7&exp=EXP-002-SVET-ASTANA` — отрицательный результат

| # | Слайд | Время | Экран |
|---|---|---|---|
| 1 | Проблема | 0:00–0:20 | слайд |
| 2 | Решение | 0:20–0:45 | слайд (схема: вопрос → ответ → источники → проблема → правка → проверка) |
| 3 | Демо | 0:45–1:45 | вкладки 1 → 2 → 3 |
| 4 | Метрики | 1:45–2:20 | вкладки 4 → 5 |
| 5 | Импакт | 2:20–2:40 | слайд |
| 6 | План пилота 30–90 дней | 2:40–3:00 | слайд |

---

## 1. Проблема (20 с)

> **EN:** When people ask ChatGPT or Gemini where to buy paint or a chandelier, they get a short list of store names instead of a page of links — in our ten answers, between one and seven stores. If your store isn't on that short list, the customer never sees you.

> **RU:** Когда люди спрашивают ChatGPT или Gemini, где купить краску или люстру, они получают не страницу ссылок, а короткий список магазинов — в наших десяти ответах от одного до семи. Если вашего магазина нет в этом списке, покупатель вас не увидит.

## 2. Решение (25 с)

**На слайде:** вопрос → полный ответ и ссылки → упоминания и конкуренты → бизнес-проблема → GEO-правка с доказательством → локальная проверка → следующий шаг.

> **EN:** GEO Intelligence Lab takes real AI answers, finds which stores and sources the AI uses, links each gap to a verified fact on the client's own website, and proposes a concrete fix — with a reproducible local test and a plan to measure the real effect.

> **RU:** GEO Intelligence Lab берёт реальные ответы AI, определяет, какие магазины и источники AI использует, связывает каждый пробел с проверенным фактом на сайте клиента и предлагает конкретную правку — с воспроизводимой локальной проверкой и планом измерить реальный эффект.

## 3. Демо (60 с)

**Вкладка 1 — Обзор (SVET.KZ):** матрица «клиент назван / не назван».
**Вкладка 2 — Наблюдения, Астана:** раскрыть «❌ SVET.KZ нет · gemini · Астана». Показать полный ответ: M light, Митрис, Светолюкс, TEKLED Astana — и ссылки: 5 Google Maps и 2 сайта конкурентов.
**Вкладка 3 — Рекомендации → GEO-01:** таблица ФАКТЫ (салон на Мангилик Ел, 29/2 размечен на сайте как Store), затем BEFORE/AFTER.

> **EN:** Ten real answers. Here SVET.KZ is first in Almaty — but in this Gemini answer about Astana it isn't mentioned at all. Yet SVET.KZ has a showroom in Astana, and its own website marks it up as a store. The problem: the page about Astana only talks about delivery from Almaty. Our fix puts the showroom on that page, using only facts the client already publishes.

> **RU:** Десять реальных ответов. Здесь SVET.KZ первый в Алматы, но в этом ответе Gemini про Астану его нет вообще. При этом у SVET.KZ есть салон в Астане, и сайт сам размечает его как магазин. Проблема: страница про Астану говорит только о доставке из Алматы. Наша правка добавляет салон на эту страницу — только из фактов, которые клиент уже публикует.

## 4. Метрики (35 с)

**На экране:** вкладка 4, затем вкладка 5.
**Числа:**
- Где купить: каждый клиент назван в 1 из 3 ответов, в Астане — 0 из 2.
- Бренд → магазин: 4 из 4.
- Ссылки: 35 появлений, 33 уникальных URL, 2ГИС — 0.
- EXP-001-COMPETITIVE-v1: MRR 0.479 → 0.667, Hit@3 75% → 100%, контроли без изменений.
- EXP-002: на уровне магазина 0.875 → 0.875 (T1 — место 2 → 2), на уровне страницы 0.1125 → 0.175. Это отдельная проверка механизма, а не доказательство того, что GEO-01 подействует на Gemini.

> **EN:** Across the sample, each client appears in one of three "where to buy" answers, and in none of the two Astana answers. With a brand in the question, they appear in four out of four. Separately, we test the retrieval mechanism on saved pages — a local BM25 simulation, not ChatGPT. For Centr Krasok's kids-paint page, MRR rose from 0.48 to 0.67 with controls unchanged. For SVET.KZ in Astana we fixed the test in advance and found no store-level effect: MRR stayed at 0.875. On the exact Gemini question the simulation puts SVET.KZ second, while real Gemini didn't name it at all — so the simulation does not predict the real assistant, and we say so.

> **RU:** В выборке каждый клиент назван в одном из трёх ответов «где купить» и ни в одном из двух ответов по Астане. Если в вопросе есть бренд — в четырёх из четырёх. Отдельно мы проверяем механизм поиска на сохранённых страницах — это локальная симуляция BM25, не ChatGPT. Для страницы «Для детской» Центра Красок MRR вырос с 0,48 до 0,67, контроли не сдвинулись. Для SVET.KZ в Астане тест зафиксирован заранее, эффекта на уровне магазина нет: MRR остался 0,875. По дословному вопросу из ответа Gemini симуляция ставит SVET.KZ вторым, а реальный Gemini его не назвал вовсе. Значит, симуляция не предсказывает реального ассистента — и мы это говорим.

## 5. Импакт (20 с)

> **EN:** Both clients already pay for an Astana showroom that AI didn't mention in our Astana answers. The first fixes are low-cost — a text block, structured data, a canonical tag — and each states only published facts. The client gets a ranked action list, not a promise.

> **RU:** Оба клиента уже платят за салон в Астане, которого AI не назвал в наших ответах по Астане. Первые правки дешёвые — текстовый блок, разметка, canonical — и в каждой только опубликованные факты. Клиент получает приоритизированный список действий, а не обещание.

## 6. План пилота 30–90 дней (20 с)

- **0–30 дней:** согласовать с клиентами и опубликовать GEO-01, GEO-03, GEO-05; сверить телефоны (GEO-07). Базовый замер: одинаковые вопросы, ChatGPT и Gemini, ≥3 прогона, скриншоты, перекрёстная проверка → первые verified KPI.
- **30–60 дней:** повторный замер теми же вопросами. Mention Rate по Астане до/после с N и знаменателями. Проверка карточек 2ГИС/Google/Яндекс.
- **60–90 дней:** этап A (выбор бренда), Караганда (доставка), новые клиенты через тот же контракт данных. Сбор через API, где это разрешено.

> **EN:** In the pilot we publish the three fixes with the clients' approval, measure the same questions three times in both assistants before and after, and report the change with sample sizes — that turns today's observations into verified KPIs.

> **RU:** В пилоте мы с согласия клиентов публикуем три правки, задаём одни и те же вопросы по три раза в обоих ассистентах до и после и показываем изменение с размером выборки. Так сегодняшние наблюдения становятся проверенными KPI.

---

## Резерв (без интернета или если упало приложение)

1. Приложение работает офлайн — проверено AppTest с отключённой сетью.
2. Если Streamlit не стартует: `docs/STATUS.md` (все числа), `docs/REAL_AI_FINDINGS.md` (таблицы ответов), `data/processed/recommendations.json` → GEO-01, `docs/EXPERIMENT_AUDIT_2026-11-20.md`.
3. Кнопку «Перезапустить baseline и treatment» на демо не нажимать — показываются сохранённые результаты.

## 10 сложных вопросов (ответы короткие)

1. **GEO vs SEO?** SEO — позиция в списке ссылок. GEO — попасть внутрь ответа AI. AI собирает ответ из немногих источников; в 9 из 10 ответов есть адрес, в 8 — телефон, поэтому важна однозначность фактов.
2. **Ответы настоящие?** Собраны вручную участником и подтверждены им. Скриншотов нет, поэтому все 10 — `self_attested`, а verified KPI показывает N/A.
3. **10 ответов — мало?** Да. Каждая метрика со знаменателем (1 из 3, 0 из 2). Это наблюдения, а не доля рынка. Парная серия с повторами — следующий шаг.
4. **Причинность?** Не утверждаем. Есть подтверждённый пробел на сайте и план замера до/после.
5. **BM25 ≠ ChatGPT?** Верно. Симуляция проверяет только находимость сохранённой страницы. EXP-002: по вопросу из OBS-005 симуляция ставит SVET.KZ вторым, а Gemini его не назвал — симуляция не предсказывает ассистента.
6. **Воспроизводимость?** Хеши снимков и документов. Конфиг EXP-002 закоммичен до прогона. `pytest`: 121 passed.
7. **Бизнес-ценность?** Салон в Астане оплачивается, но не называется AI в наших ответах. Правки дешёвые и основаны на фактах.
8. **Конкуренты?** TEKLED — во всех 3 ответах о люстрах; «Мастерская Цвета Dulux» выше Центра Красок. Это кандидаты, не проверенные нами.
9. **Масштабирование?** Новый город или клиент — это вопросы и записи реестра, а не код. Импорт через контракт данных.
10. **Ограничения?** `self_attested`, 1 прогон, нет этапа A, корпуса смещены к клиентам, правки не опубликованы. Всё это видно в приложении.
