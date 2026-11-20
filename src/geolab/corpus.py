"""Build the frozen baseline corpus from a manifest of public URLs.

Respects robots.txt, fetches each URL once, stores extracted visible text
with fetch timestamp. Usage:
    python -m geolab.corpus data/experiments/corpus_manifest.csv
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .experiment import EXP_DIR

UA = "GeoIntelligenceLab-Hackathon/0.1 (research prototype)"
MAX_CHARS = 20000


def allowed(url: str, cache: dict) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in cache:
        rp = robotparser.RobotFileParser(base + "/robots.txt")
        try:
            rp.read()
        except OSError:
            rp = None
        cache[base] = rp
    rp = cache[base]
    return True if rp is None else rp.can_fetch(UA, url)


def extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "form"]):
        t.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return title, text[:MAX_CHARS]


def build(manifest: Path, out_dir: Path | None = None, delay: float = 1.0) -> list[str]:
    out_dir = out_dir or EXP_DIR / "corpus" / "baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
    log = []
    with Path(manifest).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            url = row["url"].strip()
            if not allowed(url, cache):
                log.append(f"SKIP robots: {url}")
                continue
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
                r.raise_for_status()
            except requests.RequestException as exc:
                log.append(f"FAIL {url}: {exc}")
                continue
            title, text = extract_text(r.text)
            doc = {
                "doc_id": row["doc_id"], "entity_id": row["entity_id"], "url": url, "title": title,
                "text": text, "source_type": row.get("source_type", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "provenance": "fetched_public_page",
            }
            (out_dir / f"{row['doc_id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            log.append(f"OK {row['doc_id']} {len(text)} chars")
            time.sleep(delay)
    return log


if __name__ == "__main__":
    for line in build(Path(sys.argv[1])):
        print(line)


# CMS session/CSRF tokens embedded in public HTML (Bitrix: "bitrix_sessid", hidden <input name="sessid">).
# They identify the crawler's own anonymous session, but are session-like values: never store them.
SESSION_TOKEN_RE = re.compile(
    r"""((?:bitrix_)?sessid["']?\s*[:=]\s*["']|name=["']sessid["'][^>]*?value=["'])([A-Za-z0-9]{16,})""", re.I)


def redact_session_tokens(html: str) -> tuple[str, int]:
    """Replace session-token VALUES with 'REDACTED' (visible page text is unaffected). Returns (html, count)."""
    return SESSION_TOKEN_RE.subn(lambda m: m.group(1) + "REDACTED", html)
