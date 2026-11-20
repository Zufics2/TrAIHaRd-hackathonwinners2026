"""Deterministic KPI calculation. Undefined metrics return None (shown as N/A), never 0.

Definitions (see docs/08_EXPERIMENT_PROTOCOL.md):
  mention_rate        = answers mentioning E / answers in scope
  recommendation_rate = answers where E is recommended (heuristic) / answers in scope
  top3_rate           = answers with explicit ranking where rank(E) <= 3 / answers with explicit ranking
  citation_rate       = answers citing >=1 URL owned by E / answers with >=1 citation
  share_of_voice      = answers mentioning E / sum over same-level entities of answers mentioning them
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pandas as pd

from .analysis import AnswerAnalysis, analyze_answer
from .registry import Registry


def rate(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def fmt(v: float | None, pct: bool = True) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


@dataclass
class AnalyzedResponse:
    record: dict
    analysis: AnswerAnalysis


def analyze_records(records: list[dict], registry: Registry) -> list[AnalyzedResponse]:
    return [AnalyzedResponse(r, analyze_answer(r["answer_text"], registry, r.get("cited_urls"))) for r in records]


def entity_metrics(items: list[AnalyzedResponse], entity_id: str) -> dict:
    n = len(items)
    mentioned = sum(1 for it in items if entity_id in it.analysis.mentions)
    recommended = sum(1 for it in items if entity_id in it.analysis.mentions and it.analysis.mentions[entity_id].recommended)
    ranked = [it for it in items if it.analysis.has_ranking]
    top3 = sum(1 for it in ranked if (m := it.analysis.mentions.get(entity_id)) and m.rank is not None and m.rank <= 3)
    with_cit = [it for it in items if it.analysis.citations]
    cited = sum(1 for it in with_cit if any(c.owner_entity == entity_id for c in it.analysis.citations))
    return {
        "answers": n,
        "mention_rate": rate(mentioned, n),
        "recommendation_rate": rate(recommended, n),
        "top3_rate": rate(top3, len(ranked)),
        "ranked_answers": len(ranked),
        "citation_rate": rate(cited, len(with_cit)),
        "answers_with_citations": len(with_cit),
    }


def share_of_voice(items: list[AnalyzedResponse], registry: Registry, level: str, category: str | None = None) -> pd.DataFrame:
    ids = [e.id for e in registry.by_level(level) if category is None or e.category in (category, "marketplace")]
    cnt = Counter()
    for it in items:
        for eid in ids:
            if eid in it.analysis.mentions:
                cnt[eid] += 1
    total = sum(cnt.values())
    rows = [{"entity_id": eid, "name": registry.entities[eid].name, "is_client": registry.entities[eid].is_client,
             "in_client_assortment": bool(registry.entities[eid].sold_by),
             "registry_status": registry.entities[eid].status,  # candidate_unverified = named by AI, not checked
             "answers_mentioning": c, "share_of_voice": rate(c, total)} for eid, c in cnt.most_common()]
    return pd.DataFrame(rows)


def source_table(items: list[AnalyzedResponse], registry: Registry) -> pd.DataFrame:
    """QUERY | AI SYSTEM | RECOMMENDED ENTITY | CITED URL | SOURCE TYPE | EVIDENCE STATUS"""
    rows = []
    for it in items:
        recs = [registry.entities[e].name for e, m in it.analysis.mentions.items() if m.recommended] or ["—"]
        for c in it.analysis.citations or [None]:
            rows.append({
                "prompt_id": it.record["prompt_id"],
                "query": it.record["query"],
                "ai_system": it.record["provider"],
                "recommended_entities": ", ".join(recs),
                "cited_url": c.url if c else "(no citation)",
                "domain": c.domain if c else "",
                "source_type": c.source_type if c else "no_citation",
                "source_owner": registry.entities[c.owner_entity].name if c and c.owner_entity else "",
                "evidence_status": "explicit_citation" if c else "unknown_origin",
                "data_type": it.record["data_type"], "verification": it.record["verification_status"],
            })
    return pd.DataFrame(rows)


def general_metrics(items: list[AnalyzedResponse]) -> dict:
    domains = {c.domain for it in items for c in it.analysis.citations}
    with_cit = sum(1 for it in items if it.analysis.citations)
    return {
        "answers": len(items),
        "providers": len({it.record["provider"] for it in items}),
        "unique_cited_domains": len(domains),
        "answers_with_citations": with_cit,
        "citation_coverage": rate(with_cit, len(items)),
    }


def consistency(items: list[AnalyzedResponse], entity_id: str) -> pd.DataFrame:
    """Per prompt+provider: fraction of repeated runs mentioning the entity (repeatability)."""
    groups: dict[tuple, list[bool]] = {}
    for it in items:
        key = (it.record["prompt_id"], it.record["provider"])
        groups.setdefault(key, []).append(entity_id in it.analysis.mentions)
    rows = [{"prompt_id": k[0], "provider": k[1], "runs": len(v), "mention_share": sum(v) / len(v)} for k, v in groups.items()]
    return pd.DataFrame(rows)
