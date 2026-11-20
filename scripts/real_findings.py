"""Deterministic analysis of the REAL AI answers -> docs/REAL_AI_FINDINGS.md + data/processed/real_findings.json.

Run:  .venv/bin/python scripts/real_findings.py
Every number in the pitch / scorecard about real answers comes from this script (N and denominators shown).
Evidence level of every row is printed: self_attested = participant-provided, NOT independently verified.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geolab import store  # noqa: E402
from geolab.analysis import url_key  # noqa: E402
from geolab.metrics import analyze_records, entity_metrics, fmt  # noqa: E402
from geolab.registry import load_registry  # noqa: E402

REG = load_registry()
CLIENT_OF = {"paint": "centr_krasok", "chandelier": "svet_kz"}
STAGES = {"retailer_discovery": "B · Retailer discovery", "bridge": "C · Brand → retailer bridge", "brand_discovery": "A · Brand discovery"}
CITY = {"almaty": "Алматы", "astana": "Астана", "karaganda": "Караганда", "national": "Казахстан"}
PROV = {"chatgpt_search": "ChatGPT Search", "gemini": "Gemini"}
FACTS = {  # what the answers use to justify a store (regex on answer text, case-insensitive)
    "адрес": r"адрес", "телефон": r"телефон|\+7", "часы работы": r"график|часы работы|ежедневно|пн[–-]",
    "рейтинг / отзывы": r"рейтинг|отзыв|оцен|\d,\d/5|\d\.\d \(", "ассортимент / бренды": r"ассортимент|выбор|бренд|дилер",
    "колеровка / услуги": r"колеровк|подбор|доставк", "ТЦ / ориентир": r"ТЦ|ТК|торгов",
}


def name(eid: str) -> str:
    e = REG.entities[eid]
    return e.name + (" *(кандидат)*" if e.status == "candidate_unverified" else "")


def m3(m: dict) -> dict:
    return {"mention": f"{fmt(m['mention_rate'])} (N={m['answers']})", "recommendation": f"{fmt(m['recommendation_rate'])} (N={m['answers']})",
            "top3": f"{fmt(m['top3_rate'])} (N={m['ranked_answers']} с рейтингом)", "citation": f"{fmt(m['citation_rate'])} (N={m['answers_with_citations']} с цитатами)"}


def main() -> None:
    recs, issues = store.load_observations()
    real = [r for r in recs if r["data_type"] in ("REAL_SEARCH", "MANUAL_VERIFIED", "MANUAL_REPORTED") and r["verification_status"] != "rejected"]
    items = analyze_records(real, REG)
    ev = Counter(r["verification_status"] for r in real)
    out: list[str] = []
    w = out.append
    w("# Реальные ответы AI — анализ (генерируется `scripts/real_findings.py`)\n")
    w(f"**N = {len(items)} ответов** · провайдеры: " + ", ".join(f"{PROV.get(p, p)} {c}" for p, c in Counter(r['provider'] for r in real).items())
      + " · статус доказательств: " + ", ".join(f"`{k}` {v}" for k, v in ev.items()) + ".")
    w("\n> **Уровень доказательности.** `self_attested` = ответ скопирован участником P3 в документ, участник подтвердил, что это настоящие ответы "
      "ChatGPT Search / Gemini; скриншотов и ссылок на диалоги нет (решение капитана). Это **не независимо проверенные** ответы. "
      "Ниже — описание конкретных ответов (N=1–3 на срез), а не статистически устойчивые выводы. Каждый запрос задан **один раз** "
      "(run_no=1) → Result Consistency **не измерима** (N/A).\n")

    # 1. per answer
    w("## 1. Каждый ответ\n")
    w("| ID | AI | Этап | Город | Вопрос (дословно) | Клиент назван | Клиент рекомендован | Явный рейтинг: 1 / 2 / 3 | URL (уник.) | Сайт клиента процитирован |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    per = []
    for it in items:
        r, a = it.record, it.analysis
        cl = CLIENT_OF[r["category"]]
        m = a.mentions.get(cl)
        top = " / ".join(name(e) for e in a.ranked_entities[:3]) if a.has_ranking else "нет рейтинга"
        cited = any(c.owner_entity == cl for c in a.citations)
        nurl = len({url_key(c.url) for c in a.citations})
        w(f"| {r['response_id']} | {PROV.get(r['provider'], r['provider'])} | {STAGES[r['funnel_stage']][:1]} | {CITY[r['city']]} | {r['query']} | "
          f"{'**да**' if m else 'нет'} | {'**да**' if m and m.recommended else 'нет'}{f' (место {m.rank})' if m and m.rank else ''} | {top} | {nurl} | {'**да**' if cited else 'нет'} |")
        per.append({"response_id": r["response_id"], "provider": r["provider"], "stage": r["funnel_stage"], "city": r["city"], "query": r["query"],
                    "client": cl, "client_mentioned": bool(m), "client_recommended": bool(m and m.recommended), "client_rank": m.rank if m else None,
                    "ranked": a.ranked_entities, "unique_urls": nurl, "client_site_cited": cited, "evidence": r["verification_status"]})

    # 2. client metrics
    w("\n## 2. Метрики клиентов (числитель/знаменатель — в скобках)\n")
    w("| Срез | Клиент | Mention Rate | Recommendation Rate | Top-3 Rate | Citation Rate |")
    w("|---|---|---|---|---|---|")
    metrics = {}
    def row(label, sub, cl):
        if not sub:
            return
        m = entity_metrics(sub, cl)
        metrics[f"{label}|{cl}"] = m
        x = m3(m)
        w(f"| {label} | {REG.entities[cl].name} | {x['mention']} | {x['recommendation']} | {x['top3']} | {x['citation']} |")
    for cat, cl in CLIENT_OF.items():
        for st in ("retailer_discovery", "bridge"):
            row(STAGES[st], [it for it in items if it.record["category"] == cat and it.record["funnel_stage"] == st], cl)
        for p in PROV:
            row(f"B · {PROV[p]}", [it for it in items if it.record["category"] == cat and it.record["funnel_stage"] == "retailer_discovery" and it.record["provider"] == p], cl)
        for c in ("almaty", "astana", "karaganda"):
            row(f"B · {CITY[c]}", [it for it in items if it.record["category"] == cat and it.record["funnel_stage"] == "retailer_discovery" and it.record["city"] == c], cl)
    w("\nRecommendation Rate — детерминированная эвристика (`analysis.py`): упоминание в списке после фразы-введения «можно купить в следующих…», "
      "в явном рейтинге или рядом со словом-рекомендацией. Top-3 считается только по ответам с явным нумерованным списком.")

    # 3. SoV
    w("\n## 3. AI Share of Voice среди магазинов (этап B, по числу ответов с упоминанием)\n")
    sov = {}
    for cat, cl in CLIENT_OF.items():
        sub = [it for it in items if it.record["category"] == cat and it.record["funnel_stage"] == "retailer_discovery"]
        cnt = Counter(e for it in sub for e, m in it.analysis.mentions.items()
                      if m.level == "retailer" and REG.entities[e].category in (cat, "marketplace"))
        total = sum(cnt.values())
        sov[cat] = {e: c for e, c in cnt.items()}
        w(f"**{ {'paint': 'Краска', 'chandelier': 'Люстры'}[cat] }** — {len(sub)} ответов, {total} упоминаний магазинов:\n")
        w("| Магазин | Ответов с упоминанием | SoV | Города |")
        w("|---|---|---|---|")
        for e, c in cnt.most_common():
            cities = sorted({CITY[it.record['city']] for it in sub if e in it.analysis.mentions})
            w(f"| {'**' + name(e) + '**' if REG.entities[e].is_client else name(e)} | {c} из {len(sub)} | {c / total:.0%} | {', '.join(cities)} |")
        w("")

    # 4. brands and bridge
    w("## 4. Бренды и связь бренд → магазин\n")
    brand_cnt = Counter(e for it in items for e, m in it.analysis.mentions.items() if m.level == "manufacturer")
    w("| Бренд | Ответов с упоминанием (из 10) | В ассортименте клиента (реестр) |")
    w("|---|---|---|")
    for e, c in brand_cnt.most_common():
        sold = ", ".join(REG.entities[s].name for s in REG.entities[e].sold_by) or "—"
        w(f"| {REG.entities[e].name} | {c} | {sold} |")
    w("\n**Bridge (этап C)** — к какому магазину AI ведёт запрос о бренде:\n")
    w("| Вопрос | AI | Магазины в порядке ответа | Клиент | Сайт клиента процитирован |")
    w("|---|---|---|---|---|")
    for it in items:
        if it.record["funnel_stage"] != "bridge":
            continue
        a, cl = it.analysis, CLIENT_OF[it.record["category"]]
        order = sorted(((m.first_pos, e) for e, m in a.mentions.items() if m.level == "retailer"))
        m = a.mentions.get(cl)
        w(f"| {it.record['query']} | {PROV[it.record['provider']]} | {', '.join(name(e) for _, e in order)} | "
          f"{'назван' + (f', место {m.rank} в рейтинге' if m and m.rank else '') if m else 'не назван'} | {'да' if any(c.owner_entity == cl for c in a.citations) else 'нет'} |")

    # 5. sources
    w("\n## 5. Источники, которые AI явно процитировал (observed citations)\n")
    types, doms, by_prov = Counter(), Counter(), defaultdict(Counter)
    for it in items:
        seen = set()
        for c in it.analysis.citations:
            k = url_key(c.url)
            if k in seen:
                continue
            seen.add(k)
            types[c.source_type] += 1
            doms[c.domain] += 1
            by_prov[it.record["provider"]][c.source_type] += 1
    tot = sum(types.values())
    with_cit = sum(1 for it in items if it.analysis.citations)
    global_urls = {url_key(c.url) for it in items for c in it.analysis.citations}
    w(f"Citation Coverage: **{with_cit} из {len(items)}** ответов содержат ≥1 URL. "
      f"Появлений ссылок (без повторов внутри одного ответа): **{tot}**; глобально уникальных URL по всем ответам: **{len(global_urls)}**; "
      f"доменов: **{len(doms)}**.\n")
    w("| Тип источника | Появлений ссылок | Доля | ChatGPT Search | Gemini |")
    w("|---|---|---|---|---|")
    for t, c in types.most_common():
        w(f"| {t} | {c} | {c / tot:.0%} | {by_prov['chatgpt_search'][t]} | {by_prov['gemini'][t]} |")
    w("\nЧаще всего цитируемые домены: " + ", ".join(f"`{d}` ×{c}" for d, c in doms.most_common(8)) + ".")
    w("\n**Не процитированы ни разу:** 2ГИС (2gis.kz), соцсети (Instagram и др.), отзовики. "
      "Это наблюдение по 10 ответам; **присутствие страницы ≠ цитирование AI** — мы не утверждаем, какие страницы модель читала, но не цитировала.")

    # 6. facts used
    w("\n## 6. Какую информацию AI использует, когда рекомендует магазин\n")
    w("| Факт в ответе | Ответов (из 10) |")
    w("|---|---|")
    for k, pat in FACTS.items():
        w(f"| {k} | {sum(1 for it in items if re.search(pat, it.record['answer_text'], re.I))} |")

    # 7. gaps
    w("\n## 7. Чего нет в данных и почему выводы ограничены\n")
    w("- Нет ни одного ответа этапа **A (brand discovery)** — воронка покрыта только B и C.")
    w("- ChatGPT по Астане и Gemini по Караганде не спрашивали: сравнение AI-систем внутри города невозможно.")
    w("- Каждый вопрос — 1 прогон: нет Result Consistency; повторный запрос может дать другой список.")
    w("- Все 10 ответов — `self_attested` (один сборщик, без скриншотов): **independently verified KPI = N/A**.")
    w("- Распознавание магазинов работает по реестру; магазины-конкуренты — *кандидаты* (названы AI, не проверены).")
    if issues:
        w(f"- Предупреждения загрузчика: {len(issues)}.")

    (ROOT / "docs" / "REAL_AI_FINDINGS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (ROOT / "data" / "processed" / "real_findings.json").write_text(json.dumps(
        {"n": len(items), "evidence": ev, "per_answer": per, "metrics": metrics, "sov": sov,
         "source_types": types, "domains": doms, "citation_coverage": [with_cit, len(items)],
         "link_appearances": tot, "unique_urls_global": len(global_urls), "unique_domains": len(doms)},
        ensure_ascii=False, indent=1, default=lambda o: dict(o)) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
