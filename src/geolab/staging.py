"""Finish a staged import once PEOPLE have confirmed the missing facts.

A staged batch (data/staging/<batch>/observations_contract_staging.jsonl) holds real answers whose
exact query / collector / evidence were not in the source files. The captain fills
`resolution.csv` (one row per response_id, with the SOURCE of every confirmed fact). This module:

1. matches the confirmed query to prompts.csv (exact, normalized) -> existing prompt_id;
   otherwise proposes a new prompt with the participant's ID and the classification from the
   resolution row (validated by the prompts schema);
2. builds contract rows and validates them with the unchanged validator;
3. with --apply, appends new prompts and writes data/raw/manual/<collector>_<batch>.csv
   (never overwrites without --replace).

Nothing is inferred: a blank required fact blocks that row. CLI:
    python -m geolab.staging data/staging/forme_2026-11-20            # dry run
    python -m geolab.staging data/staging/forme_2026-11-20 --apply
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from geolab import contract as C
from geolab import store

RESOLUTION_COLS = (
    "response_id", "participant_prompt_id",
    "exact_query", "query_source",                      # verbatim text + where it was copied from
    "collector", "collector_source",                    # P2/P3 + who confirmed it
    "evidence_status", "evidence_link",                 # available | awaiting | none (no screenshot/share link by decision)
    "verification_status", "verified_by", "verification_note",
    # classification, needed only when the query is NOT already in prompts.csv
    "category", "city", "language", "funnel_stage", "intent", "brand_type", "test_group", "priority",
)
EVIDENCE_STATUS = ("available", "awaiting", "none")
PROMPT_COLS = [c.name for c in C.SCHEMAS["prompts"]["cols"]]
OBS_COLS = [c.name for c in C.SCHEMAS["observations"]["cols"]]


@dataclass
class RowResult:
    response_id: str
    status: str = "blocked"            # blocked | ready | invalid
    prompt_id: str = ""
    prompt_match: str = ""             # existing | new | ""
    reasons: list[str] = field(default_factory=list)
    record: dict | None = None


def _read_csv(path: Path) -> list[dict]:
    rows, _ = C.read_rows(path.name, path.read_bytes())
    return [r for _, r in rows]


def read_staging(batch: Path) -> list[dict]:
    return [json.loads(line) for line in (batch / "observations_contract_staging.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def plan(batch: Path, prompts_path: Path = store.PROMPTS_PATH, existing_ids: set[str] | None = None) -> tuple[list[RowResult], list[dict]]:
    """Returns (per-row results, new prompt rows). Pure: writes nothing."""
    staged = {r["response_id"]: r for r in read_staging(batch)}
    res_path = batch / "resolution.csv"
    resolution = {r["response_id"]: r for r in _read_csv(res_path)} if res_path.exists() else {}
    prompts = {r["prompt_id"]: r for r in store.load_prompts(prompts_path).to_dict("records")}
    by_query: dict[str, list[str]] = {}
    for pid, p in prompts.items():
        by_query.setdefault(C._norm_q(p["query"]), []).append(pid)

    results, new_prompts = [], {}
    for rid, st in staged.items():
        rr = RowResult(rid)
        res = {k: (resolution.get(rid, {}).get(k) or "").strip() for k in RESOLUTION_COLS}
        results.append(rr)
        if rid not in resolution:
            rr.reasons.append("нет строки в resolution.csv")
            continue
        q = res["exact_query"]
        if not q or not res["query_source"]:
            rr.reasons.append("точный текст запроса не подтверждён (exact_query + query_source)")
        if not res["collector"] or not res["collector_source"]:
            rr.reasons.append("сборщик не подтверждён (collector + collector_source)")
        if res["evidence_status"] not in EVIDENCE_STATUS:
            rr.reasons.append(f"evidence_status должен быть одним из {EVIDENCE_STATUS}")
        if rr.reasons:
            continue

        hits = by_query.get(C._norm_q(q), [])
        if len(hits) > 1:
            rr.reasons.append(f"запрос совпадает с несколькими prompt_id: {hits}")
            continue
        if hits:
            rr.prompt_id, rr.prompt_match = hits[0], "existing"
        else:
            pid = res["participant_prompt_id"] or st["prompt_id"]
            if pid in prompts:
                rr.reasons.append(f"{pid} уже есть в prompts.csv с другим текстом: {prompts[pid]['query']!r}")
                continue
            prow = {"prompt_id": pid, "query": q, **{k: res[k] for k in PROMPT_COLS if k not in ("prompt_id", "query", "notes")},
                    "notes": f"из staging {batch.name}, {rid}; источник текста: {res['query_source']}"}
            if pid in new_prompts and C._norm_q(new_prompts[pid]["query"]) != C._norm_q(q):
                rr.reasons.append(f"{pid}: разные тексты запроса у ответов одного ID")
                continue
            _, piss = C.validate_rows("prompts", [(1, prow)])
            perr = [f"prompt.{i.field}: {i.reason}" for i in piss if i.severity == "error"]
            if perr:
                rr.reasons += perr
                continue
            new_prompts[pid] = prow
            rr.prompt_id, rr.prompt_match = pid, "new"

        ev_status, vs, dt = res["evidence_status"], res["verification_status"] or "pending", st["data_type"]
        kept = [n for n in st.get("notes", "").split("; ") if "запроса в исходных файлах отсутствует" not in n]
        notes = ["; ".join(kept), f"query: {res['query_source']}", f"collector: {res['collector_source']}"]
        ev = res["evidence_link"]
        if ev_status == "none":
            if vs not in ("pending", "self_attested"):
                rr.reasons.append("доказательства нет: verified/rejected невозможны, только self_attested")
                continue
            vs, ev = "self_attested", ""
            dt = "MANUAL_REPORTED"
        elif ev_status == "awaiting":
            ev = ev or st.get("evidence_link", "")
            if vs == "verified":
                rr.reasons.append("verified невозможен: доказательство ещё не передано (evidence_status=awaiting)")
                continue
        else:  # available
            if not ev:
                rr.reasons.append("evidence_status=available, но evidence_link пуст")
                continue
            if vs == "verified" and not ev.startswith(("http://", "https://")) and not (C.ROOT / ev).exists():
                rr.reasons.append(f"verified невозможен: файл {ev} не найден")
                continue
        if vs == "verified":
            if not res["verified_by"] or res["verified_by"] == res["collector"] or not res["verification_note"]:
                rr.reasons.append("verified требует verified_by ≠ collector и verification_note (что сверено)")
                continue
            notes.append(f"verified: {res['verification_note']}")
        rec = {**{k: st.get(k, "") for k in OBS_COLS},
               "prompt_id": rr.prompt_id, "query": q, "collector": res["collector"],
               "evidence_link": ev, "verification_status": vs, "data_type": dt,
               "verified_by": res["verified_by"] if vs == "verified" else "",
               "notes": "; ".join(n for n in notes if n)}
        rec["cited_urls"] = " | ".join(st.get("cited_urls") or [])
        rr.record = rec

    # validate all candidate rows together with the real validator (no relaxation)
    all_prompts = {**prompts, **new_prompts}
    cand = [(i + 1, rr.record) for i, rr in enumerate(results) if rr.record]
    valid, issues = C.validate_rows("observations", cand, prompts=all_prompts, existing_keys=existing_ids or set())
    valid_ids = {v["response_id"] for v in valid}
    rn_to_rr = {rn: rr for rn, rr in zip([rn for rn, _ in cand], [rr for rr in results if rr.record])}
    for i in issues:
        if i.severity == "error" and i.row in rn_to_rr:
            rn_to_rr[i.row].reasons.append(f"{i.field}: {i.reason}")
    for rr in results:
        if rr.record:
            rr.status = "ready" if rr.response_id in valid_ids else "invalid"
    used = {rr.prompt_id for rr in results if rr.status == "ready" and rr.prompt_match == "new"}
    return results, [p for pid, p in new_prompts.items() if pid in used]


def apply(batch: Path, results: list[RowResult], new_prompts: list[dict], replace: bool = False,
          prompts_path: Path = store.PROMPTS_PATH) -> list[Path]:
    ready = [rr for rr in results if rr.status == "ready"]
    if not ready:
        return []
    by_collector: dict[str, list[dict]] = {}
    for rr in ready:
        by_collector.setdefault(rr.record["collector"], []).append(rr.record)
    targets = {c: store.UPLOAD_DIR / store.safe_name(f"{c}_observations_{batch.name}.csv") for c in by_collector}
    for t in targets.values():
        if t.exists() and not replace:
            raise FileExistsError(f"{t} уже существует; новая версия — только с --replace")
    if new_prompts:
        with open(prompts_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=PROMPT_COLS, lineterminator="\n").writerows(new_prompts)
    written = []
    for c, recs in by_collector.items():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=OBS_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(recs)
        targets[c].write_text(buf.getvalue(), encoding="utf-8")
        written.append(targets[c])
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("batch", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--replace", action="store_true")
    a = ap.parse_args(argv)
    recs, _ = store.load_observations()
    existing = {r["response_id"] for r in recs if not r["_file"].endswith(f"_{a.batch.name}.csv")}
    results, new_prompts = plan(a.batch, existing_ids=existing)
    for rr in results:
        tag = {"ready": "READY  ", "invalid": "INVALID", "blocked": "BLOCKED"}[rr.status]
        extra = f" → {rr.prompt_id} ({rr.prompt_match}) · {rr.record['verification_status']}" if rr.record else ""
        print(f"{tag} {rr.response_id}{extra}")
        for reason in rr.reasons:
            print(f"        - {reason}")
    n = {s: sum(r.status == s for r in results) for s in ("ready", "invalid", "blocked")}
    print(f"\nготово {n['ready']}, невалидно {n['invalid']}, заблокировано {n['blocked']}; новых промптов {len(new_prompts)}")
    if a.apply:
        try:
            written = apply(a.batch, results, new_prompts, replace=a.replace)
        except FileExistsError as exc:
            print(f"ОТКАЗ: {exc}")
            return 1
        for p in written:
            print(f"записано: {p.relative_to(C.ROOT)}")
    elif n["ready"]:
        print("dry run — для записи добавьте --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
