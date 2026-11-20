"""Build EXP-002 (SVET.KZ · Astana · GEO-01) corpus in data/research/exp002_svet_astana/ — Claude's area.

The experiment ENGINE is Codex's unchanged src/geolab/experiment.py, run with corpus_dir=...
Baseline = real public pages: client pages from today's GEO-audit snapshots + competitor pages that
Gemini actually cited for Astana in OBS-005 (mitris.kz, svetolux.kz, tekled.kz) + one Almaty competitor.
Treatment = ONE document changed: svet.kz/dostavka/astana/ with the GEO-01 AFTER block (facts already
published by the client: address, hours, phone, 2GIS link of the Astana showroom in its own JSON-LD).
Queries and controls are fixed in EXP-002.json BEFORE the first run (git commit precedes the result).
Run:  .venv/bin/python scripts/exp002_build.py [--offline]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "exp002_svet_astana"
SNAP = ROOT / "data" / "research" / "geo_audit_2026-11-20" / "html"
UA = "GeoIntelligenceLab-Hackathon/0.1 (research prototype)"
MAX_CHARS = 20000  # same cap as geolab.corpus

FROM_AUDIT = [  # doc_id, entity, url, snapshot
    ("svet_home", "svet_kz", "https://svet.kz/", "svet.kz.html"),
    ("svet_contact", "svet_kz", "https://svet.kz/contact/", "svet.kz__contact.html"),
    ("svet_lyustry", "svet_kz", "https://svet.kz/katalog/lyustry/", "svet.kz__katalog__lyustry.html"),
    ("svet_maytoni", "svet_kz", "https://svet.kz/brands/maytoni/", "svet.kz__brands__maytoni.html"),
    ("svet_dostavka_astana", "svet_kz", "https://svet.kz/dostavka/astana/", "svet.kz__dostavka__astana.html"),
    ("ck_home", "centr_krasok", "https://centr-krasok.kz/", "centr-krasok.kz.html"),
    ("ck_contacts", "centr_krasok", "https://centr-krasok.kz/about/contacts/", "centr-krasok.kz__about__contacts.html"),
    ("ck_dulux", "centr_krasok", "https://centr-krasok.kz/catalog/dulux/", "centr-krasok.kz__catalog__dulux.html"),
]
FETCH = [  # competitors cited by AI (OBS-005: Astana; OBS-004: Almaty)
    ("mitris_home", "mitris", "http://mitris.kz/", "OBS-005 cited_urls"),
    ("svetolux_home", "svetolux", "http://svetolux.kz/", "OBS-005 cited_urls"),
    ("tekled_home", "tekled", "https://tekled.kz/", "OBS-004 cited_urls; TEKLED named in OBS-004/005/006"),
    ("artlamp_home", "artlamp", "https://artlamp.kz/", "OBS-004 cited_urls"),
]
GEO01_BLOCK = ("Люстры и светильники в Астане: салон и доставка. Салон SVET.KZ в Астане: ул. Мангилик Ел, 29/2, "
               "ежедневно 10:00–20:00, телефон +7 777 292-84-01, карточка в 2ГИС. Доставка в Астану: DPD из Алматы, 7 000 ₸, 1–3 рабочих дня. ")


def visible(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    return title, " ".join(soup.get_text(" ").split())[:MAX_CHARS]


def doc(doc_id, entity, url, title, text, stype, fetched, prov) -> dict:
    return {"doc_id": doc_id, "entity_id": entity, "url": url, "title": title, "text": text,
            "source_type": stype, "fetched_at": fetched, "provenance": prov}


def main(offline: bool) -> None:
    (OUT / "baseline").mkdir(parents=True, exist_ok=True)
    (OUT / "treatment").mkdir(parents=True, exist_ok=True)
    audit = json.loads((ROOT / "data" / "research" / "geo_audit_2026-11-20" / "audit.json").read_text(encoding="utf-8"))
    for doc_id, ent, url, snap in FROM_AUDIT:
        title, text = visible((SNAP / snap).read_text(encoding="utf-8"))
        meta = audit[ent][url]
        d = doc(doc_id, ent, url, title, text, "client_site", meta["fetched_at"], f"geo_audit snapshot {snap} sha256 {meta['sha256'][:12]}")
        (OUT / "baseline" / f"{doc_id}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not offline:
        robots: dict[str, robotparser.RobotFileParser] = {}
        for doc_id, ent, url, why in FETCH:
            base = "{0.scheme}://{0.netloc}".format(urlsplit(url))
            if base not in robots:
                rp = robotparser.RobotFileParser()
                try:
                    rp.parse(requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20).text.splitlines())
                except requests.RequestException:
                    rp.parse([])
                robots[base] = rp
            if not robots[base].can_fetch(UA, url):
                print("robots disallow", url)
                continue
            time.sleep(1)
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            except requests.RequestException as exc:
                print("FETCH FAILED", url, exc)
                continue
            if not r.ok:
                print("HTTP", r.status_code, url)
                continue
            title, text = visible(r.text)
            d = doc(doc_id, ent, url, title or doc_id, text, "retailer_site", datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    f"fetched_public_page; why in corpus: {why}")
            (OUT / "baseline" / f"{doc_id}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print("ok", doc_id, len(text), "chars", title[:70])
    base = json.loads((OUT / "baseline" / "svet_dostavka_astana.json").read_text(encoding="utf-8"))
    treat = {**base, "title": "Люстры и светильники в Астане: салон и доставка | SVET.KZ",
             "text": GEO01_BLOCK + base["text"], "provenance": base["provenance"] + "; TREATMENT = GEO-01 AFTER block prepended (facts from svet.kz JSON-LD Store)"}
    (OUT / "treatment" / "svet_dostavka_astana.json").write_text(json.dumps(treat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("docs:", sorted(p.stem for p in (OUT / "baseline").glob("*.json")))


if __name__ == "__main__":
    main("--offline" in sys.argv)
