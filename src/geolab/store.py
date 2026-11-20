"""Loading prompts and AI responses. Provenance statuses are never mixed silently."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from .registry import ROOT

STATUSES = ("REAL", "MANUAL_VERIFIED", "CONTROLLED_EXPERIMENT", "SYNTHETIC_DEMO")
PROMPTS_PATH = ROOT / "data" / "prompts" / "prompts.csv"
RESPONSES_DIRS = (ROOT / "data" / "raw" / "manual", ROOT / "data" / "raw" / "api")

RESPONSE_FIELDS = (
    "response_id", "prompt_id", "query", "provider", "model", "search_mode", "timestamp",
    "city", "language", "answer_text", "cited_urls", "status", "collector", "evidence_link", "notes",
)
REQUIRED = ("response_id", "prompt_id", "query", "provider", "timestamp", "answer_text", "status")


class ValidationError(ValueError):
    pass


def load_prompts(path: Path = PROMPTS_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _split_urls(v) -> list[str]:
    if isinstance(v, list):
        return [u.strip() for u in v if u and u.strip()]
    if not v:
        return []
    return [u.strip() for u in str(v).replace("|", " ").replace(",", " ").split() if u.strip().startswith("http")]


def validate_record(rec: dict) -> dict:
    missing = [f for f in REQUIRED if not str(rec.get(f, "")).strip()]
    if missing:
        raise ValidationError(f"{rec.get('response_id', '?')}: missing {missing}")
    if rec["status"] not in STATUSES:
        raise ValidationError(f"{rec['response_id']}: bad status {rec['status']!r}; allowed {STATUSES}")
    out = {f: rec.get(f, "") for f in RESPONSE_FIELDS}
    out["cited_urls"] = _split_urls(rec.get("cited_urls"))
    return out


def read_response_file(path: Path) -> list[dict]:
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    else:
        return []
    return [validate_record(r) for r in rows]


def load_responses(dirs=RESPONSES_DIRS) -> tuple[list[dict], list[str]]:
    """Returns (records, errors). Bad rows are reported, not dropped silently."""
    recs: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    for d in dirs:
        d = Path(d)
        if not d.exists():
            continue
        for p in sorted(d.glob("*")):
            if p.name.startswith("_") or p.suffix not in (".jsonl", ".csv"):
                continue
            try:
                for r in read_response_file(p):
                    if r["response_id"] in seen:
                        errors.append(f"{p.name}: duplicate response_id {r['response_id']}")
                        continue
                    seen.add(r["response_id"])
                    r["_file"] = p.name
                    recs.append(r)
            except (ValidationError, json.JSONDecodeError) as exc:
                errors.append(f"{p.name}: {exc}")
    return recs, errors
