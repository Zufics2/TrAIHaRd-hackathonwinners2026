> **АРХИВ (2026-11-20 вечер).** Документ устарел; актуальные числа и статусы — в `docs/STATUS.md`. Оригинал сохранён без изменений ниже.

# Evidence matrix · 6 ответов из `forme` (повторная проверка, Sprint 005)

Машиночитаемая версия: `evidence_matrix.csv`. Все 37 гиперссылок docx с текстом ссылки: `docx_hyperlinks.json`.
Состояния: **CONFIRMED** / **NOT_FOUND** / **AMBIGUOUS**.

| response_id | ID участника | provider | время | query | collector | answer_text | citation URLs (docx / уник.) | conversation evidence |
|---|---|---|---|---|---|---|---|---|
| OBS-001 | P-PA-ALM-001 | CONFIRMED gemini | CONFIRMED 14:05 | NOT_FOUND | AMBIGUOUS | CONFIRMED | NOT_FOUND 0 | NOT_FOUND |
| OBS-002 | P-PA-AST-001 | CONFIRMED gemini | CONFIRMED 14:06 | NOT_FOUND | AMBIGUOUS | CONFIRMED | NOT_FOUND 0 | NOT_FOUND |
| OBS-003 | P-PA-KAR-001 | CONFIRMED chatgpt_search | CONFIRMED 14:07 | NOT_FOUND | AMBIGUOUS | CONFIRMED | CONFIRMED 4 / 3 | NOT_FOUND |
| OBS-004 | P-CH-ALM-001 | CONFIRMED chatgpt_search | CONFIRMED 14:05 | NOT_FOUND | AMBIGUOUS | CONFIRMED | CONFIRMED 11 / 9 | NOT_FOUND |
| OBS-005 | P-CH-AST-001 | CONFIRMED gemini | CONFIRMED 14:10 | NOT_FOUND | AMBIGUOUS | CONFIRMED | CONFIRMED 7 / 7 | NOT_FOUND |
| OBS-006 | P-CH-KAR-001 | CONFIRMED chatgpt_search | CONFIRMED 14:23 | NOT_FOUND | AMBIGUOUS | CONFIRMED | CONFIRMED 3 / 2 | NOT_FOUND |

Дата и часовой пояс (`2026-11-20`, `+05:00`) берутся из JSONL. Время совпадает с docx и попадает в окно создания и изменения файла (13:57–14:25 +05:00).

## Где искали (результаты поиска)

| Что | Где проверено | Результат |
|---|---|---|
| collector | все 12 частей docx: `document.xml` (текст, 1 таблица, 16 заголовков, 1 `<w:br>`), `rels`, `numbering`, `styles`, `settings`, `webSettings`, `docProps`. Скрытого текста, комментариев, правок, текстовых полей, колонтитулов, сносок нет | В каждом блоке есть только строки `ID:` и `Сервис и время:`. Совпадения «P2»/«P3» в `rels` — случайные символы внутри URL images.openai.com |
| collector | JSONL: 13 ключей, поля collector нет; совпадений P2/P3 — 0 | NOT_FOUND |
| collector | `docProps/core.xml`: creator = lastModifiedBy, одно лицо (имя не переносится в репозиторий) | AMBIGUOUS: метаданные Word не доказывают, кто отправлял запрос. В репозитории, во всех ветках и в worktree Codex нет соответствия этого имени P2/P3. Один и тот же файл содержит и Gemini, и ChatGPT, поэтому правило «ChatGPT = P2, Gemini = P3» неприменимо |
| query | docx (все абзацы, таблица, заголовки) | Текста запроса нет. Заголовки вроде «Где купить краску в Караганде» — это заголовки ответа ChatGPT, а не запрос |
| query | JSONL | Поля query или prompt_text нет |
| query | `prompts.csv`, `baseline_v1.csv`, все ветки (`git grep` по каждой ref), Spotlight по `P-PA-ALM-001` / `P-CH-KAR-001` | ID участника нигде не определены (только в `Запросы.docx` и в этом staging) |
| query | `~/Downloads/ПРОМПТ для победы.rtf` (директива) | Есть примеры вопросов, но без ID P-PA/P-CH. Сопоставление было бы догадкой, поэтому не используется |
| conversation links | 37 гиперссылок docx по шаблонам `chatgpt.com/share`, `/c/`, `chat.openai.com`, `gemini.google.com/share`, `g.co/gemini` | 0 |
| скриншоты | Spotlight `OBS-00*`; `~/Desktop`, `~/Downloads`, `~/Documents`, `~/Pictures`; скриншоты за сегодня | Ничего не найдено (`screenshots/OBS-00N.png` есть только как ссылка в JSONL) |

## Классификация 37 гиперссылок docx

- **A. Citation URLs — 25 в docx, 21 уникальная** (после `url_key`). Все сохранены в `cited_urls` staging (проверено поблочно: совпадают 6/6). 19 из 25 находятся в разделе «Ссылки:» блока, 6 — в тексте ответа. Все ссылки ChatGPT содержат `utm_source=chatgpt.com`, то есть скопированы из интерфейса ChatGPT.
- **B. Ссылки на диалоги — 0.**
- **C. Прочие — 12 ссылок images.openai.com** (миниатюры изображений в ответах ChatGPT: OBS-003 ×4, OBS-004 ×5, OBS-006 ×3). Это не цитирование и не доказательство диалога, в `cited_urls` не включены.
- OBS-001 и OBS-002 (Gemini): гиперссылок нет, в блоке только текст «Ссылки: Google maps».

## Также найдено: `~/Downloads/Bridge.docx` (вне объёма этого этапа)

В `~/Downloads/Bridge.docx` (сегодня, 16:05) лежат ещё bridge-ответы `P-BRIDGE-*` в том же формате. В них тоже нет запроса и collector. Этот файл не обрабатывался.

---

## Обновление v2 · 2026-11-20 16:52 — документы обновил участник №3

| Файл | sha256 | Что изменилось |
|---|---|---|
| `~/Desktop/forme/Запросы.docx` (v2, 35 529 Б) | `3cd5c71b…60a1c23c` | добавлены 6 строк «Вопрос: …»; тексты ответов и все 37 гиперссылок побайтно те же (`diff` извлечённого текста и `rels`) |
| `~/Desktop/forme/Bridge (1).docx` (v2, 25 692 Б) | `05ad8ee1…6a1a5e` | добавлены 4 строки «Вопрос: …»; ответы и ссылки те же |

Копии только для чтения — в `data/private/forme_2026-11-20/*_v2_1652.docx` (в `.gitignore`).

| Поле | Статус после v2 | Источник |
|---|---|---|
| original_query (10/10) | **CONFIRMED** | строка «Вопрос:» каждого блока v2 |
| collector = P3 (10/10) | **CONFIRMED капитаном**; в документах не указан | сообщение капитана 2026-11-20: «Участник №3 обновил документы… подтвердил, что данные являются реальными ответами» |
| conversation evidence (10/10) | **NOT_FOUND — по решению капитана** (скриншотов и share-ссылок нет) | → `data_type = MANUAL_REPORTED`, `verification_status = self_attested` |
| prompt_id | 8 новых промптов с ID участника (`P-PA-*`, `P-CH-*`, `P-BRIDGE-*`); точных совпадений с прежними 43 промптами нет | `data/prompts/prompts.csv` |
| timestamp Bridge | время — из docx (16:05), дата и `+05:00` — из метаданных docx | notes каждой строки |

Импорт: `python -m geolab.staging … --apply` → `data/raw/manual/P3_observations_forme_2026-11-20.csv` (10 строк, 0 ошибок, 0 предупреждений).
