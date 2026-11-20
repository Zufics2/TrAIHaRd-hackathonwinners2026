"""Read-only GEO audit of the clients' public pages (robots.txt respected, 1 request per URL, 1 s apart).

Saves raw HTML snapshots (evidence + offline demo) and extracted signals:
    data/research/geo_audit_2026-11-20/html/<slug>.html
    data/research/geo_audit_2026-11-20/audit.json
Run:  .venv/bin/python scripts/geo_audit.py            (network)
      .venv/bin/python scripts/geo_audit.py --offline  (re-parse saved snapshots only)
Production sites are never modified.
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
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geolab.corpus import redact_session_tokens  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "geo_audit_2026-11-20"
UA = "GeoIntelligenceLab-Hackathon/0.1 (research prototype)"
PAGES = {
    "centr_krasok": ["https://centr-krasok.kz/", "https://centr-krasok.kz/about/contacts/", "https://centr-krasok.kz/about/delivery/",
                     "https://centr-krasok.kz/about/", "https://centr-krasok.kz/brands/", "https://centr-krasok.kz/catalog/dulux/",
                     "https://centr-krasok.kz/catalog/bindo_7_1/kraska_dulux_professional_bindo_7_matovaya_bc_0_9l/"],
    "svet_kz": ["https://svet.kz/", "https://svet.kz/contact/", "https://svet.kz/pay-delivery/", "https://svet.kz/about/",
                "https://svet.kz/brands/maytoni/", "https://svet.kz/katalog/lyustry/",
                "https://svet.kz/products/podvesnoy_svetilnik_maytoni_mod272pl_l12bs3k/", "https://svet.kz/dostavka/astana/"],
}
CITY_PAT = {"astana": r"астан|нур-султан|mangilik|мангилик|мәңгілік", "almaty": r"алмат|кабдолов|жибек жол", "karaganda": r"караганд|қарағанд"}
PHONE = re.compile(r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")


def slug(url: str) -> str:
    p = urlsplit(url)
    s = (p.netloc + p.path).strip("/").replace("/", "__") or p.netloc
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:120]


def jsonld(soup: BeautifulSoup) -> list:
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            out.append(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            out.append({"_invalid_json": (tag.string or "")[:200]})
    return out


def ld_types(obj) -> list[str]:
    if isinstance(obj, list):
        return [t for o in obj for t in ld_types(o)]
    if isinstance(obj, dict):
        t = obj.get("@type")
        here = t if isinstance(t, list) else ([t] if t else [])
        return here + [x for k, v in obj.items() if k != "@type" for x in ld_types(v)]
    return []


def extract(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ld = jsonld(soup)
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    text = " ".join(soup.get_text(" ").split())
    low = text.lower()
    meta = lambda n: (soup.find("meta", attrs={"name": n}) or {}).get("content")  # noqa: E731
    canon = soup.find("link", rel="canonical")
    host = urlsplit(url).netloc
    links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]
    return {
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "meta_description": meta("description"),
        "meta_robots": meta("robots"),
        "canonical": canon.get("href") if canon else None,
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")],
        "h2": [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:15],
        "h3_count": len(soup.find_all("h3")),
        "jsonld_types": sorted(set(ld_types(ld))),
        "jsonld": ld,
        "visible_chars": len(text),
        "city_mentions": {c: len(re.findall(p, low)) for c, p in CITY_PAT.items()},
        "phones": sorted(set(PHONE.findall(text)))[:10],
        "internal_links": sum(1 for l in links if urlsplit(l).netloc == host),
        "has_hreflang": bool(soup.find("link", rel="alternate", hreflang=True)),
        "astana_snippets": [low[max(0, m.start() - 90):m.start() + 110] for m in re.finditer(CITY_PAT["astana"], low)][:4],
    }


def main(offline: bool) -> None:
    (OUT / "html").mkdir(parents=True, exist_ok=True)
    prev = json.loads((OUT / "audit.json").read_text(encoding="utf-8")) if (OUT / "audit.json").exists() else {}
    robots: dict[str, robotparser.RobotFileParser] = {}
    result = {"_meta": {"user_agent": UA, "note": "read-only; robots.txt respected; production unchanged",
                        "redaction": "CMS session-token values (sessid / bitrix_sessid) replaced by REDACTED; "
                                     "'sha256' = raw fetched bytes (raw copy in git-ignored data/private/geo_snapshots_raw/), "
                                     "'sha256_redacted' = tracked file; visible text identical"}}
    for client, urls in PAGES.items():
        result[client] = {}
        for url in urls:
            f = OUT / "html" / f"{slug(url)}.html"
            rec = {"url": url, "snapshot": str(f.relative_to(ROOT))}
            if not offline:
                base = "{0.scheme}://{0.netloc}".format(urlsplit(url))
                if base not in robots:
                    rp = robotparser.RobotFileParser()
                    rp.parse(requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20).text.splitlines())
                    robots[base] = rp
                if not robots[base].can_fetch(UA, url):
                    rec["status"] = "robots_disallowed"
                    result[client][url] = rec
                    continue
                time.sleep(1)
                r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
                rec.update(status=r.status_code, final_url=r.url, fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           x_robots_tag=r.headers.get("X-Robots-Tag"))
                if r.ok:
                    rec["sha256"] = hashlib.sha256(r.text.encode()).hexdigest()       # raw fetched bytes
                    f.write_bytes(redact_session_tokens(r.text)[0].encode("utf-8"))  # never store CMS session tokens
            else:
                rec.update({k: v for k, v in prev.get(client, {}).get(url, {}).items()
                            if k in ("status", "final_url", "fetched_at", "x_robots_tag", "sha256")})
            if f.exists():
                html = f.read_bytes().decode("utf-8")
                rec["sha256_redacted"] = hashlib.sha256(html.encode()).hexdigest()
                rec.update(extract(url, html))
            result[client][url] = rec
            print(client, rec.get("status"), url, "| title:", (rec.get("title") or "")[:70], "| h1:", rec.get("h1"), "| ld:", rec.get("jsonld_types"),
                  "| cities:", rec.get("city_mentions"), "| chars:", rec.get("visible_chars"))
    (OUT / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main("--offline" in sys.argv)
