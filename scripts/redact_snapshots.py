"""Redact CMS session tokens (sessid / bitrix_sessid VALUES) from tracked HTML snapshots.

Raw originals -> data/private/geo_snapshots_raw/<dir>/ (git-ignored) so the original sha256 stays verifiable.
Proves for every file that the VISIBLE text (what BM25 / audits use) is byte-identical before and after.
Run once: .venv/bin/python scripts/redact_snapshots.py
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bs4 import BeautifulSoup  # noqa: E402
from geolab.corpus import redact_session_tokens  # noqa: E402

DIRS = ["data/research/geo_audit_2026-11-20/html", "data/research/geo_recheck_2026-11-20/html"]


def visible(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    return " ".join(soup.get_text(" ").split())


report = []
for d in DIRS:
    raw_dir = ROOT / "data" / "private" / "geo_snapshots_raw" / Path(d).parent.name
    raw_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted((ROOT / d).glob("*.html")):
        raw = f.read_bytes().decode("utf-8")  # bytes-exact: keep CRLF as fetched
        red, n = redact_session_tokens(raw)
        if not n:
            continue
        if not (raw_dir / f.name).exists():
            shutil.copy2(f, raw_dir / f.name)
        same_visible = visible(raw) == visible(red)
        f.write_bytes(red.encode("utf-8"))
        report.append({"file": f"{d}/{f.name}", "tokens_redacted": n, "visible_text_identical": same_visible,
                       "sha256_raw": hashlib.sha256(raw.encode()).hexdigest(), "sha256_redacted": hashlib.sha256(red.encode()).hexdigest()})
out = ROOT / "data" / "research" / "SNAPSHOT_REDACTION.json"
json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(report), "files,", sum(r["tokens_redacted"] for r in report), "tokens; visible text identical in all:", all(r["visible_text_identical"] for r in report))
