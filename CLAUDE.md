# CLAUDE.md — постоянные правила для Claude Code (GEO Intelligence Lab)

Эти правила действуют на всех этапах хакатона. Технические права на репозиторий **не считаются разрешением**.
Капитан = владелец MacBook #1 (P1). «Разрешение» = явное сообщение капитана в текущем разговоре для конкретной операции.

## Ветки

| Ветка | Владелец |
|---|---|
| `feat/core-app` | **Claude Code** — единственная рабочая ветка Claude |
| `codex/qa-experiments` | Codex (worktree `~/Desktop/TrAIHaRd-codex`) |
| `research/brand-sources` | P2 |
| `data/ai-baseline` | P3 |
| `main` | стабильная интеграция; меняется **только через Pull Request с разрешения капитана** |

## Запрещено без явного разрешения капитана

1. `git push` в `main` (в любой форме: `main`, `HEAD:main`, `:main`, `--all`, `--mirror`).
2. `git commit` на `main`; `git switch main` с целью изменить её.
3. Merge любых веток в `main`; создание/слияние Pull Request.
4. `git merge main` в feature-ветку при незакоммиченных изменениях.
5. `git rebase` опубликованных веток.
6. `git push --force` / `--force-with-lease`, `git push --no-verify`.
7. `git reset --hard`, `git clean -fd`, `git checkout -- .`, `git restore` чужих файлов, `git stash drop`.
8. `git merge --allow-unrelated-histories`.
9. Удаление удалённых веток, перемещение тегов, смена default branch, настройки branch protection.
10. Установка/изменение git hooks и `git config` (кроме чтения).
11. Слияние ветки Codex без ревью капитана.
12. Публикация секретов, `.env`, личных данных, путей с именами пользователей.

## Разрешено без отдельного подтверждения

Чтение файлов, `git status/diff/log/branch -vv/ls-remote/fetch`, правка собственных модулей, локальные тесты, локальные коммиты в `feat/core-app`.
`git push origin feat/core-app` — только после чек-листа:

```zsh
git branch --show-current            # должно быть: feat/core-app
git status --short                   # только ожидаемые файлы
git diff --cached --check            # пусто
.venv/bin/python -m pytest -q        # все тесты зелёные
git grep -nE "sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_|github_pat_" || echo ok
git push origin feat/core-app        # явная ветка, без флагов
```

## Каталоги (кто что правит)

| Владелец | Пути |
|---|---|
| Claude Code | `app.py`, `src/geolab/{registry,analysis,metrics,store,contract,corpus}.py`, `tests/test_core.py`, `tests/test_contract.py`, `tests/test_real_path.py`, `tests/fixtures/`, `data/registry/`, `data/prompts/`, `data/templates/`, `data/samples/`, `data/processed/`, `docs/00,01,06,07,15,16`, `CLAUDE.md`, `AGENTS.md`, `scripts/` |
| Codex | `src/geolab/experiment.py`, `data/experiments/**`, `tests/test_experiment*.py`, `tests/test_qa_*.py` (в `feat/core-app` `test_qa_adversarial.py` адаптирован Claude в Sprint 004 — Codex должен взять эту версию), `qa/`, `docs/08_EXPERIMENT_PROTOCOL.md`, `docs/CODEX_*.md` |
| P2 | `data/research/P2_*`, `data/raw/manual/P2_*`, `assets/evidence/OBS-P2-*` |
| P3 | `data/raw/manual/P3_*`, `assets/evidence/OBS-P3-*` |
| Участник (автор коммита 4c87ae6) | `.idea/`, `main.py` — не удалять и не править |

Файлы Codex не редактируются из этой папки, даже если тест требует изменения: опишите нужное изменение капитану.

## Данные

- Никогда не удалять и не перезаписывать `data/raw/**`, `assets/evidence/**`, данные участников. Исправления — только у источника (участник правит свой файл).
- `SYNTHETIC_DEMO` не попадает в реальные KPI; результаты эксперимента не смешиваются с наблюдениями (`docs/15_DATA_CONTRACT.md`).
- Production-сайты клиентов не изменяются. Платные API — только с согласия капитана.

## Отчётность

Не заявлять PASS без выполненной проверки. Сообщать о любых операциях с удалёнными ветками точными командами. Инцидент 2026-11-20: `docs/GIT_INCIDENT_2026-11-20.md`.
