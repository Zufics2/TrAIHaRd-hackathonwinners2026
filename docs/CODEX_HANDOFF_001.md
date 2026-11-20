# Mission 001 handoff

20 ноября 2026. Итог **PARTIAL**. Рабочая ветка `codex/qa-experiments`, worktree `~/Desktop/TrAIHaRd-codex`, проверенная база `0740ac1`. Изменения ограничены experiment runner, экспериментальными данными, QA-тестами и отчётами. Claude-owned analysis.py, metrics.py, app.py, store.py и registry не менялись. Список путей: `qa/evidence/changed_files.txt`.

## Девять подтверждённых дефектов базы 0740ac1

Все тесты ниже находятся в `tests/test_qa_adversarial.py` и сохраняют `xfail(strict=True)`. **XFAIL означает открытый дефект проверенной версии, а не исправление.** Серьёзность HIGH относится к искажению результатов/потере доступности MVP, а не к доказанной возможности удалённой атаки. QA-010 из исходного аудита — отдельная группа исправленных проверок experiment runner; она не входит в эти девять.

| ID / серьёзность | Точное имя теста | Файл и функция с дефектом | Вход | Ожидается | Фактически на 0740ac1 | Влияние на реальные KPI |
|---|---|---|---|---|---|---|
| QA-001 HIGH | test_numbered_instructions_not_ranking | src/geolab/analysis.py: analyze_answer, parse_ranking | `1. Откройте сайт Dulux.\n2. Проверьте время работы SVET.KZ.` | Инструкции: has_ranking=False, rank=None | has_ranking=True, Dulux rank=1, SVET rank=2; обе сущности recommended=True | Ложные Top-3 и recommendation rate; лишний ranked answer меняет знаменатель для всех сущностей |
| QA-002 HIGH | test_neutral_list_not_recommendation | src/geolab/analysis.py: analyze_answer | `Упомянутые названия:\n- Dulux\n- Maytoni` | recommended=False для обоих | recommended=True | Завышает recommendation rate, хотя ответ не рекомендует товар |
| QA-003 HIGH | test_source_host_not_query | src/geolab/analysis.py: classify_source | `https://evil.example/?next=https://2gis.kz/` | other_web, owner=None | map_directory, owner=None | Ложная атрибуция происхождения; искажает долю карт/каталогов. В этом примере owner citation rate клиента не меняется |
| QA-004 HIGH | test_extra_citations_require_absolute_http | src/geolab/analysis.py: extract_citations | extra_urls=`['javascript:alert(1)', '/catalog/x']` | Отклонить/исключить оба; relative только с подтверждённым base | Две citations, domain пустой | Завышает citation coverage, меняет знаменатель citation_rate; пустой домен попадает в unique domains |
| QA-005 HIGH | test_bad_timestamp_rejected | src/geolab/store.py: validate_record | response_id=r, prompt_id=NONEXISTENT, query=x, provider=unknown, timestamp=yesterday, answer_text=x, status=REAL | ValidationError как минимум для timestamp; prompt association проверяется отдельно | Запись принимается | Невалидные observations способны попасть в реальные метрики/неверные временные срезы. Сам unknown provider/model не является ошибкой |
| QA-006 MEDIUM | test_alias_cache_tracks_registry_changes | src/geolab/analysis.py: find_entity_spans, _PATTERN_CACHE | Entity(id=qa_cache, name=OldAlias), затем Entity с тем же id и name=NewAlias | Оба имени находятся в соответствующей версии registry | NewAlias не находится после прогрева cache | После обновления aliases занижает mention rate, recommendation rate, share of voice до перезапуска процесса |
| QA-007 MEDIUM | test_url_case_sensitive_paths | src/geolab/analysis.py: extract_citations | `https://example.org/A https://example.org/a` | Две разные ссылки | Одна ссылка | Теряется источник/page evidence; в этом примере бинарные citation coverage и owner citation rate не меняются, но анализ страниц неполон |
| QA-008 HIGH | test_jsonl_non_object_reported | src/geolab/store.py: validate_record, load_responses | Файл bad.jsonl содержит `[]` | records=[], диагностическая ошибка загрузки | Необработанный AttributeError | Может прервать загрузку всех KPI/дашборда, а не только отклонить одну строку |
| QA-009 MEDIUM | test_brand_as_common_word_requires_context | src/geolab/analysis.py: find_entity_spans | `This is my favourite colour.` | manufacturer favourite отсутствует | Ложное упоминание Favourite | Завышает mention rate/share of voice производителя; этот пример не является рекомендацией |

### Изменения Claude после базы аудита

Read-only comparison с `feat/core-app` на `72942e9416f8f7c7d2155f113ca5a5e38dcf2410` сохранён в `qa/evidence/claude_branch_review.json`.

- QA-007: изолированная проверка нового analysis.py возвращает **две** ссылки. Исходный дефект подтверждён на базе, а в новой ветке минимальный сценарий уже проходит. После интеграции Claude должен снять соответствующий xfail и выполнить полный suite.
- Старые `ValidationError`, `validate_record`, `read_response_file`, `load_responses` удалены из нового store.py. Поэтому **нельзя переносить legacy QA-тесты на новую ветку без адаптации импортов**: возможна ошибка collection, а не только XPASS. QA-005/008 должны быть перенесены на contract.validate_file/load_observations и заново проверены; их текущий статус на новом API не заявляется.
- Прочие восемь дефектов не объявляются автоматически исправленными из-за наличия новых коммитов. Число 43 passed / 9 xfailed относится только к Codex snapshot, не ко всему текущему feat/core-app.

## Эксперимент и provenance

Сохранённый результат `data/experiments/results/EXP-001-COMPETITIVE-v1_result.json` точно совпадает с двумя новыми offline-прогонами. Доступные tests проверяют формулы вручную, нулевой и отрицательный эффект, отсутствие ранга, N/A, malformed inputs и неизменность конкурентов.

| Метрика целевого клиента, n=4 | Baseline | Treatment |
|---|---:|---:|
| MRR владельца | 0,479167 | 0,666667 |
| Hit@3 / top3_rate | 75% | 100% |
| Citation Rate | **100%** | **100%** |
| MRR изменённой страницы | 0,395833 | 0,666667 |

Уточнение handoff: **75% → 100% относится к Hit@3, не к Citation Rate**. Основание — поля summary.target.{baseline,treatment} в сохранённом JSON. Скриншот сам по себе не заменяет проверку этих полей.

MRR = `(Σ reciprocal_rank)/n`, rank — позиция первого появления владельца в top-5 документов, отсутствие = 0. Для baseline ранги 3,1,4,3: `(1/3+1+1/4+1/3)/4`. Treatment 1,1,3,3: `(1+1+1/3+1/3)/4`. Это не средняя позиция и не relevance MRR без qrels.

15 baseline документов, 6 владельцев: 12 точных копий исходных snapshots и три новых реальных retailer pages. Для каждого документа проверены URL, timezone timestamp, непустой provenance и SHA256; все URL/timestamps/provenance перечислены в `qa/evidence/finalization.json:corpus_documents`. Treatment ck_kids совпадает с исходным proposal Claude, конкуренты не менялись. Полный текст и hashes обеих веток содержатся в evidence результата.

Происхождение исходных 12 страниц унаследовано от Claude (`fetched_public_page`): файл, timestamp и URL сохранены, но исходные HTTP responses независимо не пересобирались. Новые Megastroy/Neostrim/KRASKA pages имеют журнал HTTP/robots/response hash в collection.json. Доступность robots не является отдельной лицензией на переиздание. Исходный treatment — неопубликованный proposal, а не реальный ответ сайта по указанному URL; это явно обозначено provenance.

Пять negative controls: три про люстры, один про промышленную эмаль, один про Finncolor. Entity rankings неизменны, MRR 0,10 → 0,10, Hit@3 20% → 20%. N5 всё ещё ошибочно возвращает Центр Красок на позиции 2 в обеих ветках. BM25 scores меняются из-за avgdl; raw equality=False при entity rank equality=True. Нельзя называть controls идеально релевантными или требовать равенства scores.

## Совместимость и порядок интеграции для Claude

1. Ревьюировать Codex commit отдельно от main. До интеграции проверить чистоту своей ветки; не делать автоматический merge. Только капитан разрешает PR/изменения main.
2. Сначала взять `src/geolab/experiment.py`, competitive config/data/result и `tests/test_experiment_qa.py`. Старые функции `load_experiment`, `run_experiment(exp, corpus_dir=None)`, `save_result`, `EXP_DIR` и обязательные result keys сохранены; это соответствует docs/15_DATA_CONTRACT.md §6. Новые evidence/page-rank поля только аддитивны.
3. Проверить app.py отдельно: в новой версии на 72942e9 список corpus для подписи жёстко берётся из `X.EXP_DIR / 'corpus' / 'baseline'`. Claude должен использовать `X.resolve_corpus(exp, None) / 'baseline'` или evidence выбранного result. Иначе competitive-v1 выполняется на 15 документах, а подпись UI показывает исходные 12/3. Это ограничение отображения, не пересчёт результата. app.py Codex не менял.
4. Затем переносить adversarial tests. Сначала согласовать новые импорты и fixtures с contract/store; нельзя удалять сценарии из-за смены API. Порядок исправлений: QA-008/005 (целостность загрузки), QA-004/003 (валидность/происхождение citations), QA-001/002 (рейтинги/рекомендации), QA-006/009 (matching/cache). QA-007 уже имеет положительную минимальную проверку в новой ветке.
5. Для каждого исправленного дефекта удалить **только соответствующий** strict xfail после воспроизведения успеха на актуальной ветке. Остальные xfail оставить и перечислить в PR. Не скрывать XPASS, collection errors или менять expected на фактически ошибочное поведение.
6. Перед PR: `git diff --check`, весь pytest актуальной ветки, импорты, два offline-прогона EXP-001-COMPETITIVE-v1 с сравнением JSON/metrics/hashes; проверить старый EXP-001. Проверить Streamlit вручную: правильный corpus count, MRR, Hit@3 и Citation Rate, n=4/5, статусы CONTROLLED_EXPERIMENT и отсутствие смешения с real KPI. Повторить secret scan. Не запускать collector для воспроизводимости.

## Git hook и границы проверок

Обнаружен уже установленный executable hook:

`~/Desktop/TrAIHaRd-hackathonwinners2026/.git/hooks/pre-push`

Он не перезаписывался. core.hooksPath не установлен в обоих worktrees, common git directory общий. Локальные проверки через stdin (без git push): main update, HEAD→main, deletion main и смешанный refspec с main заблокированы (exit 1); feat/core-app и codex/qa-experiments разрешены (exit 0). Пустой input разрешён. Hook проверяет remote ref, а не имя локальной ветки. Результаты в finalization.json.

Ограничение существующего hook: его можно обойти `--no-verify` или установленным в нём GEOLAB_ALLOW_PROTECTED_PUSH; это локальная защита от ошибки, не server-side branch protection. Эти обходы не применялись. Настоящих тестовых push main/feat/core-app не делалось; remote ветки main не менялись.

## Проверки и известные ограничения

Повторяемая команда из Codex worktree: `PYTHONDONTWRITEBYTECODE=1 python qa/finalize_checks.py` с установленными requirements. Она проверяет frozen data, обе ветки corpus, provenance/hash, повтор результата, существующий hook через stdin, импорты, синтаксис app, типовые сигнатуры secrets и запускает pytest. Результат — finalization.json. Перечень открытых дефектов привязан к baseline; этот скрипт намеренно проверяет handoff этой стадии, а не заменяет тесты последующей версии продукта.

- PASS: Git-изоляция, принадлежность файлов, воспроизводимость, формула MRR, imports/AST, diff check, типовые secret signatures без совпадений.
- PARTIAL: полный suite 43 passed / 9 strict xfailed; relevance controls; provenance исходных страниц унаследован; app API сохранён, но новая подпись corpus требует правки Claude. Интерактивный UI не тестировался.
- FAIL для заявления о настоящем AI-search before/after: реальных observations 0. Это lexical retrieval simulation, маленькая exploratory выборка без qrels/holdout и статистического обобщения. EXP-002 остаётся планом в основном аудите; новый функционал не начинался.

Локальный commit и push в origin/codex/qa-experiments фиксируются в финальном сообщении после выполнения. Main, чужие исходники, remote branches кроме разрешённой Codex branch, hooks и Git config не изменяются.
