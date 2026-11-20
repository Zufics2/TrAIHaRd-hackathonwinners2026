"""Loading prompts and AI observations. Provenance types are never mixed silently.

Real-world KPIs use ONLY rows with data_type in REAL_DATA_TYPES and verification_status == "verified".
SYNTHETIC_DEMO rows live in data/samples/ and are loaded only on explicit request.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from . import contract as C
from .registry import ROOT

STATUSES = C.DATA_TYPE
PROMPTS_PATH = ROOT / "data" / "prompts" / "prompts.csv"
REAL_DIRS = (ROOT / "data" / "raw" / "manual", ROOT / "data" / "raw" / "api")
SAMPLES_DIR = ROOT / "data" / "samples"
UPLOAD_DIR = ROOT / "data" / "raw" / "manual"


def load_prompts(path: Path = PROMPTS_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def prompts_index() -> dict[str, dict]:
    return {r["prompt_id"]: r for r in load_prompts().to_dict("records")}


def _files(dirs) -> list[Path]:
    out = []
    for d in dirs:
        d = Path(d)
        if d.exists():
            out += [p for p in sorted(d.glob("*")) if p.suffix in (".csv", ".jsonl") and not p.name.startswith("_")]
    return out


def load_observations(include_samples: bool = False, real_dirs=None) -> tuple[list[dict], list[dict]]:
    """Returns (records, issues). Issues carry file, row, field, severity, reason."""
    prompts = prompts_index()
    recs: list[dict] = []
    issues: list[dict] = []
    seen: set[str] = set()
    seen_text: dict[tuple, str] = {}
    sources = [(p, False) for p in _files(real_dirs or REAL_DIRS)]
    if include_samples:
        sources += [(p, True) for p in _files([SAMPLES_DIR]) if "observations" in p.name]
    for path, synthetic_ok in sources:
        channel = "api" if (path.parent.name == "api" and path.parent.parent.name == "raw") else "manual"
        valid, iss = C.validate_file("observations", path, prompts=prompts, allow_synthetic=synthetic_ok, existing_keys=seen,
                                     channel=channel)
        issues += [{"file": path.name, **i.as_dict()} for i in iss]
        for r in valid:
            if synthetic_ok and r["data_type"] != "SYNTHETIC_DEMO":
                issues.append({"file": path.name, "row": "-", "field": "data_type", "severity": "error",
                               "reason": "в data/samples допускается только SYNTHETIC_DEMO"})
                continue
            seen.add(r["response_id"])
            fp = (r["prompt_id"], r["provider"], " ".join(r["answer_text"].split()))
            if fp in seen_text:
                issues.append({"file": path.name, "row": "-", "field": "answer_text", "severity": "warning",
                               "reason": f"{r['response_id']}: текст ответа совпадает с {seen_text[fp]} — повторная вставка?"})
            seen_text.setdefault(fp, r["response_id"])
            p = prompts[r["prompt_id"]]
            r.update({"category": p["category"], "city": p["city"], "funnel_stage": p["funnel_stage"],
                      "intent": p["intent"], "_file": path.name})
            recs.append(r)
    return recs, issues


def is_real_kpi_row(r: dict) -> bool:
    # MANUAL_REPORTED (no evidence) can never be a verified KPI row, even if a file claims so
    return (r["data_type"] in C.REAL_DATA_TYPES and r["data_type"] != "MANUAL_REPORTED" and r["verification_status"] == "verified"
            and bool(r.get("verified_by")) and r.get("verified_by") != r.get("collector")
            and bool(r.get("evidence_link")))  # defence in depth (G06): evidence for every data_type, incl. REAL_SEARCH


def safe_name(name: str) -> str:
    safe = "".join(ch for ch in Path(name).name if ch.isalnum() or ch in "._-") or "upload.csv"
    if not safe.endswith((".csv", ".jsonl")) or safe.startswith((".", "_")):
        raise ValueError("имя файла должно оканчиваться на .csv или .jsonl и не начинаться с '.' или '_'")
    return safe


def save_upload(name: str, content: bytes, replace: bool = False) -> Path:
    """Store an uploaded file verbatim. Overwrites only with replace=True (new version of the same file;
    previous version stays in Git history)."""
    target = UPLOAD_DIR / safe_name(name)
    if target.exists() and not replace:
        stem, suf = target.stem, target.suffix
        target = UPLOAD_DIR / f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suf}"
    target.write_bytes(content)
    return target
