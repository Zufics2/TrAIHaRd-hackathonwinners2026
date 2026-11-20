"""Live re-check of the facts behind each GEO card (read-only; robots.txt respected; 1 s between requests).

Writes data/research/geo_recheck_2026-11-20/{html/, checks.json}. Does NOT overwrite the 17:00 audit
snapshots (EXP-002 provenance points to them).  Run: .venv/bin/python scripts/geo_recheck.py [--offline]
Each check = (card, claim, url, predicate) -> PASS / FAIL with the matched snippet as evidence.
"""
from __future__ import annotations

import hashlib
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geolab.corpus import redact_session_tokens  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "geo_recheck_2026-11-20"
UA = "GeoIntelligenceLab-Hackathon/0.1 (research prototype)"
URLS = ["https://svet.kz/dostavka/astana/", "https://svet.kz/katalog/lyustry/", "https://svet.kz/contact/", "https://svet.kz/brands/maytoni/",
        "https://centr-krasok.kz/about/contacts/", "https://centr-krasok.kz/", "https://centr-krasok.kz/catalog/dulux/",
        "https://centr-krasok.kz/catalog/dlya_detskoy/", "https://centr-krasok.kz/robots.txt"]


def slug(url: str) -> str:
    p = urlsplit(url)
    return re.sub(r"[^A-Za-z0-9_.-]", "_", (p.netloc + p.path).strip("/").replace("/", "__"))[:120]


def page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ld = []
    for t in soup.find_all("script", type="application/ld+json"):
        try:
            ld.append(json.loads(t.string or ""))
        except (json.JSONDecodeError, TypeError):
            pass
    canon = soup.find("link", rel="canonical")
    h1 = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    return {"title": title, "h1": h1, "canonical": canon.get("href") if canon else None, "ld": json.dumps(ld, ensure_ascii=False),
            "text": " ".join(soup.get_text(" ").split())}


def snippet(text: str, pat: str) -> str | None:
    m = re.search(pat, text, re.I)
    return text[max(0, m.start() - 70):m.end() + 70] if m else None


def main(offline: bool) -> None:
    (OUT / "html").mkdir(parents=True, exist_ok=True)
    meta = {}
    if not offline:
        rp_cache: dict[str, robotparser.RobotFileParser] = {}
        for url in URLS:
            base = "{0.scheme}://{0.netloc}".format(urlsplit(url))
            if base not in rp_cache:
                rp = robotparser.RobotFileParser()
                rp.parse(requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20).text.splitlines())
                rp_cache[base] = rp
            if not url.endswith("robots.txt") and not rp_cache[base].can_fetch(UA, url):
                meta[url] = {"status": "robots_disallowed"}
                continue
            time.sleep(1)
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            red = redact_session_tokens(r.text)[0]  # never store CMS session tokens
            (OUT / "html" / f"{slug(url)}.html").write_bytes(red.encode("utf-8"))
            meta[url] = {"status": r.status_code, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "sha256": hashlib.sha256(r.text.encode()).hexdigest(), "sha256_redacted": hashlib.sha256(red.encode()).hexdigest()}
        (OUT / "fetch_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    meta = json.loads((OUT / "fetch_meta.json").read_text(encoding="utf-8"))
    P = {u: page((OUT / "html" / f"{slug(u)}.html").read_text(encoding="utf-8")) for u in URLS if not u.endswith("robots.txt")}
    robots = (OUT / "html" / f"{slug(URLS[-1])}.html").read_text(encoding="utf-8")
    checks = [
        ("GEO-01", "Страница доставки в Астану существует", "https://svet.kz/dostavka/astana/", lambda p: snippet(p["text"], r"DPD")),
        ("GEO-01", "На ней НЕТ блока о салоне в Астане (адрес только в футере)", "https://svet.kz/dostavka/astana/",
         lambda p: None if re.search(r"салон|шоурум|самовывоз", p["text"], re.I) else "слов «салон/шоурум/самовывоз» нет"),
        ("GEO-01", "Категория люстр описывает Астану через доставку", "https://svet.kz/katalog/lyustry/",
         lambda p: snippet(p["text"], r"заказы в Астану привозим доставкой")),
        ("GEO-01", "Салон в Астане опубликован как Store в JSON-LD", "https://svet.kz/contact/",
         lambda p: snippet(p["ld"], r"Мангилик Ел, 29/2")),
        ("GEO-03", "Адрес Центра Красок в Астане опубликован на странице контактов", "https://centr-krasok.kz/about/contacts/",
         lambda p: snippet(p["text"], r"Мангилик Ел, 29/2")),
        ("GEO-03", "На странице контактов нет JSON-LD Store / LocalBusiness / Organization", "https://centr-krasok.kz/about/contacts/",
         lambda p: None if re.search(r'"(Store|LocalBusiness|Organization|PaintStore|HomeGoodsStore)"', p["ld"]) else p["ld"][:160]),
        ("GEO-03", "WebSite.name на главной упоминает только Алматы", "https://centr-krasok.kz/",
         lambda p: snippet(p["ld"], r"в Алматы")),
        ("GEO-05", "robots.txt закрывает фильтр-URL (Disallow: /*/filter/)", "https://centr-krasok.kz/robots.txt",
         lambda _: snippet(robots, r"Disallow: /\*/filter/")),
        ("GEO-05", "У категории Dulux нет rel=canonical", "https://centr-krasok.kz/catalog/dulux/",
         lambda p: None if p["canonical"] else "canonical отсутствует"),
        ("GEO-05", "H1 «Dulux» повторяется", "https://centr-krasok.kz/catalog/dulux/",
         lambda p: f"h1={p['h1']}" if len(p["h1"]) > 1 else None),
        ("GEO-07", "Телефон +7 777 292-84-01 на контактах SVET.KZ", "https://svet.kz/contact/", lambda p: snippet(p["text"], r"292[\s-]?84[\s-]?01")),
        ("GEO-07", "Номер 245-88-88 (назван AI) на контактах SVET.KZ отсутствует", "https://svet.kz/contact/",
         lambda p: None if re.search(r"245[\s-]?88[\s-]?88", p["text"]) else "не найден"),
        ("XX-003", "Категория люстр SVET.KZ заявляет отправку в Караганду", "https://svet.kz/katalog/lyustry/",
         lambda p: snippet(p["text"], r"в Караганду")),
        ("XX-003", "На контактах SVET.KZ адрес в Караганде не опубликован", "https://svet.kz/contact/",
         lambda p: None if re.search(r"Караганда,|г\. Караганда|Караганды, ул", p["text"]) else "адреса в Караганде нет"),
        ("XX-003", "На контактах Центра Красок адрес в Караганде не опубликован (есть только в списке городов)", "https://centr-krasok.kz/about/contacts/",
         lambda p: None if re.search(r"Караганда,|г\. Караганда|Караганды, ул", p["text"]) else "адреса в Караганде нет"),
        ("CK-005", "Число товаров в категории «Для детской» (live)", "https://centr-krasok.kz/catalog/dlya_detskoy/",
         lambda p: snippet(p["text"], r"Найдено \d+ товар")),
    ]
    res = []
    for card, claim, url, pred in checks:
        p = P.get(url, {})
        ev = pred(p) if (p or url.endswith("robots.txt")) else None
        res.append({"card": card, "claim": claim, "url": url, "result": "PASS" if ev else "FAIL", "evidence": ev,
                    "fetched_at": meta.get(url, {}).get("fetched_at"), "sha256": meta.get(url, {}).get("sha256")})
        print(f"{res[-1]['result']:4} {card:6} {claim[:70]:70} | {str(ev)[:110]}")
    (OUT / "checks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main("--offline" in sys.argv)
