"""Bounded, read-only collection; run explicitly, never during an experiment."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests

from geolab.corpus import extract_text

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("megastroy_kids", "megastroy", "https://megastroy.kz/catalog/lakokrasochnaya_produktsiya/vodnodispersionnye_kraski/258604/"),
    ("neostrim_paint", "neostrim", "https://neostrim.kz/catalog/interer-i-otdelka/lakokrasochnye-materialy/kraski-vodoemulsionnye/kraska-dlya-sten-i-potolkov/"),
    ("kraska_paint", "kraska", "https://kraska.kz/almaty/catalog/lakokrasochnye_materialy/kraski_emali/"),
]
UA = "GeoIntelligenceLab-Hackathon/0.1 (research prototype)"


def main():
    folder = ROOT / "data/experiments/competitive_v1/baseline"
    if any((folder / f"{doc_id}.json").exists() for doc_id, _, _ in SOURCES):
        raise ValueError("snapshot already exists; create a new version for a new collection")
    folder.mkdir(parents=True, exist_ok=True)
    logs = []
    for doc_id, entity, url in SOURCES:
        domain = url.split("/", 3)[:3]
        robots_url = "/".join(domain) + "/robots.txt"
        log = {"url": url, "robots_url": robots_url}
        try:
            rules = requests.get(robots_url, headers={"User-Agent": UA}, timeout=20, allow_redirects=False)
            if rules.status_code != 200 or "user-agent:" not in rules.text.lower():
                raise ValueError("robots unavailable or not a rules file; skip")
            rp = RobotFileParser(); rp.parse(rules.text.splitlines())
            if not rp.can_fetch(UA, url):
                raise ValueError("robots disallow; skip")
            log.update(robots=rules.text, robots_sha256=hashlib.sha256(rules.content).hexdigest())
            time.sleep(max(rp.crawl_delay(UA) or rp.crawl_delay("*") or 1, 1))
            response = requests.get(url, headers={"User-Agent": UA}, timeout=30, allow_redirects=False)
            log["http_status"] = response.status_code
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("redirect requires manual review; skip")
            title, text = extract_text(response.text)
            log.update(title=title, chars=len(text), preview=text[:300])
            if len(text) < 200 or "js-challenge-loader" in response.text.lower() or "captcha" in title.lower():
                raise ValueError("insufficient text or challenge; skip")
            document = dict(doc_id=doc_id, entity_id=entity, url=url, title=title, text=text,
                            source_type="retailer_site", fetched_at=datetime.now(timezone.utc).isoformat(),
                            provenance="fetched_public_page; bounded research snapshot; not independent product verification")
            (folder / f"{doc_id}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2))
            log.update(status="saved", chars=len(text), response_sha256=hashlib.sha256(response.content).hexdigest())
        except (requests.RequestException, ValueError) as exc:
            log.update(status="excluded", reason=str(exc))
        logs.append(log)
        print(doc_id, log["status"], log.get("reason", ""), flush=True)
    (ROOT / "qa/evidence/collection.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
