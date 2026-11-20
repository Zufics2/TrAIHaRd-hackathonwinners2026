"""Controlled GEO experiment (MODE 2).

A frozen corpus of real pages (client + competitors) is indexed with BM25.
A deterministic "answer engine" retrieves top-k documents per query and
recommends the entities those documents belong to, citing their URLs.

Baseline and treatment differ ONLY in the documents listed in
experiment["changed_doc_ids"] (treatment text replaces baseline text).
Same queries, same k, same tokenizer, same corpus otherwise.

This simulates the retrieval stage of AI search. It is NOT a measurement of
ChatGPT/Gemini/Perplexity and must be labelled CONTROLLED_EXPERIMENT.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from .registry import ROOT

EXP_DIR = ROOT / "data" / "experiments"
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
STEM_LEN = 5  # crude, deterministic prefix stemming for Russian morphology


def tokenize(text: str) -> list[str]:
    toks = TOKEN_RE.findall(text.lower().replace("ё", "е"))
    return [t[:STEM_LEN] if len(t) > STEM_LEN else t for t in toks if len(t) > 1]


@dataclass
class Doc:
    doc_id: str
    entity_id: str
    url: str
    title: str
    text: str
    source_type: str
    fetched_at: str = ""
    provenance: str = ""


def load_corpus(variant: str, changed_doc_ids: list[str], corpus_dir: Path | None = None) -> list[Doc]:
    corpus_dir = corpus_dir or EXP_DIR / "corpus"
    docs: dict[str, Doc] = {}
    for p in sorted((corpus_dir / "baseline").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        docs[d["doc_id"]] = Doc(**{k: d.get(k, "") for k in Doc.__dataclass_fields__})
    if variant == "treatment":
        for doc_id in changed_doc_ids:
            p = corpus_dir / "treatment" / f"{doc_id}.json"
            if not p.exists():
                raise FileNotFoundError(f"treatment document missing: {p}")
            d = json.loads(p.read_text(encoding="utf-8"))
            if d["doc_id"] not in docs:
                raise ValueError(f"treatment doc {doc_id} has no baseline counterpart")
            docs[doc_id] = Doc(**{k: d.get(k, "") for k in Doc.__dataclass_fields__})
    return [docs[k] for k in sorted(docs)]


def answer(query: str, docs: list[Doc], bm25: BM25Okapi, top_k: int) -> dict:
    scores = bm25.get_scores(tokenize(query))
    order = sorted(range(len(docs)), key=lambda i: (-scores[i], docs[i].doc_id))[:top_k]
    order = [i for i in order if scores[i] > 0]
    ranked: list[str] = []
    for i in order:
        if docs[i].entity_id not in ranked:
            ranked.append(docs[i].entity_id)
    return {
        "query": query,
        "ranked_entities": ranked,
        "citations": [{"doc_id": docs[i].doc_id, "url": docs[i].url, "score": round(float(scores[i]), 4)} for i in order],
    }


def run_variant(exp: dict, variant: str, corpus_dir: Path | None = None) -> list[dict]:
    docs = load_corpus(variant, exp["changed_doc_ids"], corpus_dir)
    if not docs:
        raise ValueError("empty corpus")
    bm25 = BM25Okapi([tokenize(d.title + " " + d.text) for d in docs])
    out = []
    for q in exp["queries"]:
        a = answer(q["query"], docs, bm25, exp.get("top_k", 5))
        a.update({"query_id": q["query_id"], "role": q["role"]})
        out.append(a)
    return out


def _target_stats(results: list[dict], target: str) -> dict:
    rows = []
    for r in results:
        rank = r["ranked_entities"].index(target) + 1 if target in r["ranked_entities"] else None
        cited = any(c["doc_id"] in r.get("_target_docs", ()) for c in r["citations"])
        rows.append({"query_id": r["query_id"], "role": r["role"], "rank": rank, "top3": rank is not None and rank <= 3, "cited": cited})
    return rows


def run_experiment(exp: dict, corpus_dir: Path | None = None) -> dict:
    target = exp["target_entity"]
    base = run_variant(exp, "baseline", corpus_dir)
    treat = run_variant(exp, "treatment", corpus_dir)
    target_docs = {d.doc_id for d in load_corpus("baseline", [], corpus_dir) if d.entity_id == target}
    for r in base + treat:
        r["_target_docs"] = target_docs
    b_rows, t_rows = _target_stats(base, target), _target_stats(treat, target)
    per_query = []
    for b, t, br, tr in zip(b_rows, t_rows, base, treat):
        per_query.append({
            "query_id": b["query_id"], "query": br["query"], "role": b["role"],
            "baseline_rank": b["rank"], "treatment_rank": t["rank"],
            "baseline_top3": b["top3"], "treatment_top3": t["top3"],
            "baseline_cited": b["cited"], "treatment_cited": t["cited"],
            "baseline_entities": br["ranked_entities"], "treatment_entities": tr["ranked_entities"],
        })

    def summary(rows: list[dict], prefix: str, role: str) -> dict:
        sel = [r for r in rows if r["role"] == role]
        n = len(sel)
        return {
            "queries": n,
            "top3_rate": None if n == 0 else sum(r[f"{prefix}_top3"] for r in sel) / n,
            "citation_rate": None if n == 0 else sum(r[f"{prefix}_cited"] for r in sel) / n,
            # MRR: mean of 1/rank (0 if absent) — sensitive to moves inside the top-3
            "mrr": None if n == 0 else sum(1 / r[f"{prefix}_rank"] if r[f"{prefix}_rank"] else 0 for r in sel) / n,
        }

    for r in base + treat:
        r.pop("_target_docs", None)
    return {
        "experiment_id": exp["experiment_id"],
        "target_entity": target,
        "changed_doc_ids": exp["changed_doc_ids"],
        "status": "CONTROLLED_EXPERIMENT",
        "per_query": per_query,
        "summary": {
            role: {"baseline": summary(per_query, "baseline", role), "treatment": summary(per_query, "treatment", role)}
            for role in ("target", "negative_control")
        },
        "raw": {"baseline": base, "treatment": treat},
    }


def load_experiment(exp_id: str) -> dict:
    return json.loads((EXP_DIR / f"{exp_id}.json").read_text(encoding="utf-8"))


def save_result(result: dict) -> Path:
    out = EXP_DIR / "results" / f"{result['experiment_id']}_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
