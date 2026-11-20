# AGENTS.md — правила для Codex и других coding agents (GEO Intelligence Lab)

Те же правила, что в `CLAUDE.md`. Технические права **не являются** разрешением. Капитан = P1 (MacBook #1).

## Ветка и рабочая папка

- Codex работает **только** в `~/Desktop/TrAIHaRd-codex` на ветке `codex/qa-experiments`.
- Не открывать и не править основную папку `~/Desktop/TrAIHaRd-hackathonwinners2026` (там работает Claude Code).
- `main` — стабильная интеграция, меняется только через Pull Request с разрешения капитана.

## Запрещено без явного разрешения капитана

- `git push` в `main` в любой форме (`main`, `HEAD:main`, `:main`, `--all`, `--mirror`); commit на `main`.
- Merge в `main`, создание/слияние Pull Request.
- `git merge main` в свою ветку при незакоммиченных изменениях.
- `git rebase` опубликованных веток; `git push --force`, `--force-with-lease`, `--no-verify`.
- `git reset --hard`, `git clean -fd`, `git checkout -- .`, `git stash drop`.
- `git merge --allow-unrelated-histories`; удаление удалённых веток; теги; branch protection; `git config`; hooks.
- Публикация секретов, `.env`, личных данных.

Разрешено: чтение, тесты, локальные коммиты в `codex/qa-experiments`, `git push origin codex/qa-experiments` после проверки ветки, `git diff --check`, тестов и отсутствия секретов.

## Файлы Codex

`src/geolab/experiment.py`, `data/experiments/**`, `tests/test_experiment*.py`, `tests/test_qa_*.py`, `qa/`, `docs/08_EXPERIMENT_PROTOCOL.md`, `docs/CODEX_*.md`.

**Не трогать:** `app.py`, `src/geolab/{registry,analysis,metrics,store,contract,corpus}.py`, `data/registry/`, `data/prompts/`, `data/templates/`, `data/raw/`, `assets/evidence/`, `docs/00,01,06,07,15,16`, `CLAUDE.md`, `AGENTS.md`, `.idea/`, `main.py`.
Нужна правка чужого файла — описать её в `docs/CODEX_*.md` для капитана.

## Интерфейс experiment engine

Совместимость с `docs/15_DATA_CONTRACT.md §6` обязательна: поля результата можно добавлять, но не удалять и не переименовывать (их читает `app.py`).
Результаты имеют статус `CONTROLLED_EXPERIMENT` и никогда не выдаются за ответы ChatGPT/Gemini/Perplexity.

## Перед каждым коммитом

```sh
git branch --show-current     # codex/qa-experiments
git diff --cached --check
python -m pytest -q
```
