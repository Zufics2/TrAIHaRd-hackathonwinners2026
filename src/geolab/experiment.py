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

import hashlib
import json
import platform
import re
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

from rank_bm25 import BM25Okapi

from .registry import ROOT

EXP_DIR = ROOT / "data" / "experiments"
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
STEM_LEN = 5  # crude, deterministic prefix stemming for Russian morphology
RETRIEVAL = {"algorithm": "BM25Okapi", "k1": 1.5, "b": 0.75, "epsilon": 0.25,
             "tokenizer": "unicode-word-lower-yo-e-prefix5-min2-v1", "score_threshold": 0,
             "tie_break": "doc_id_ascending"}
ID_RE = re.compile(r"[A-Za-z0-9_-]+\Z")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_experiment(exp: dict) -> None:
    if not isinstance(exp, dict):
        raise ValueError("experiment must be an object")
    for key in ("experiment_id", "target_entity"):
        if not isinstance(exp.get(key), str) or not ID_RE.fullmatch(exp[key]):
            raise ValueError(f"invalid {key}")
    changed = exp.get("changed_doc_ids")
    if not isinstance(changed, list) or not changed or any(not isinstance(x, str) or not ID_RE.fullmatch(x) for x in changed) or len(set(changed)) != len(changed):
        raise ValueError("changed_doc_ids must contain unique safe IDs")
    if type(exp.get("top_k", 5)) is not int or exp.get("top_k", 5) < 1:
        raise ValueError("top_k must be a positive integer")
    queries = exp.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be nonempty")
    seen = set()
    for q in queries:
        if not isinstance(q, dict) or not isinstance(q.get("query_id"), str) or not q["query_id"] or q["query_id"] in seen:
            raise ValueError("query IDs must be unique and nonempty")
        seen.add(q["query_id"])
        if q.get("role") not in ("target", "negative_control") or not isinstance(q.get("query"), str) or not tokenize(q["query"]):
            raise ValueError("invalid query role or text")


def resolve_corpus(exp: dict, corpus_dir: Path | None) -> Path:
    if corpus_dir is not None:
        return Path(corpus_dir)
    subdir = exp.get("corpus_subdir", "corpus")
    if not isinstance(subdir, str) or not subdir:
        raise ValueError("corpus_subdir must be a nonempty relative path")
    relative = Path(subdir)
    if relative.is_absolute():
        raise ValueError("corpus_subdir must be relative")
    resolved = (EXP_DIR / relative).resolve()
    if not resolved.is_relative_to(EXP_DIR.resolve()):
        raise ValueError("corpus_subdir escapes experiment directory")
    return resolved


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
    if variant not in ("baseline", "treatment"):
        raise ValueError("unknown variant")
    corpus_dir = corpus_dir or EXP_DIR / "corpus"
    docs: dict[str, Doc] = {}
    for p in sorted((corpus_dir / "baseline").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError(f"document must be an object: {p}")
        if d.get("doc_id") != p.stem or d["doc_id"] in docs:
            raise ValueError(f"duplicate or mismatched doc_id: {p}")
        if any(not isinstance(d.get(k), str) or not d[k].strip() for k in ("entity_id", "url", "title", "text", "source_type")) or not tokenize(d["title"] + " " + d["text"]):
            raise ValueError(f"incomplete document: {p}")
        docs[d["doc_id"]] = Doc(**{k: d.get(k, "") for k in Doc.__dataclass_fields__})
    if variant == "treatment":
        for doc_id in changed_doc_ids:
            if not isinstance(doc_id, str) or not ID_RE.fullmatch(doc_id):
                raise ValueError("invalid changed document ID")
            p = corpus_dir / "treatment" / f"{doc_id}.json"
            if not p.exists():
                raise FileNotFoundError(f"treatment document missing: {p}")
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                raise ValueError(f"document must be an object: {p}")
            if d.get("doc_id") != doc_id or doc_id not in docs:
                raise ValueError(f"treatment doc {doc_id} has no baseline counterpart")
            if any(d.get(k) != getattr(docs[doc_id], k) for k in ("entity_id", "url", "source_type")):
                raise ValueError(f"treatment changes document identity: {doc_id}")
            if any(not isinstance(d.get(k), str) or not d[k].strip() for k in ("title", "text")) or not tokenize(d["title"] + " " + d["text"]):
                raise ValueError(f"empty treatment text: {doc_id}")
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
    validate_experiment(exp)
    corpus_dir = resolve_corpus(exp, corpus_dir)
    docs = load_corpus(variant, exp["changed_doc_ids"], corpus_dir)
    return _run_docs(exp, docs)


def _run_docs(exp: dict, docs: list[Doc]) -> list[dict]:
    if not docs:
        raise ValueError("empty corpus")
    bm25 = BM25Okapi([tokenize(d.title + " " + d.text) for d in docs],
                     k1=RETRIEVAL["k1"], b=RETRIEVAL["b"], epsilon=RETRIEVAL["epsilon"])
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
    validate_experiment(exp)
    corpus_dir = resolve_corpus(exp, corpus_dir)
    baseline_docs = load_corpus("baseline", [], corpus_dir)
    treatment_docs = load_corpus("treatment", exp["changed_doc_ids"], corpus_dir)
    if not any(d.entity_id == exp["target_entity"] for d in baseline_docs):
        raise ValueError("target entity has no documents")
    if any(d.entity_id != exp["target_entity"] for d in baseline_docs if d.doc_id in exp["changed_doc_ids"]):
        raise ValueError("only target documents may change")
    target = exp["target_entity"]
    base = _run_docs(exp, baseline_docs)
    treat = _run_docs(exp, treatment_docs)
    target_docs = {d.doc_id for d in baseline_docs if d.entity_id == target}
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
            # Page rank is separate from deduplicated owner rank.
            **{f"{prefix}_page_rank": next((i + 1 for i, c in enumerate(raw["citations"])
                if c["doc_id"] in exp["changed_doc_ids"]), None)
               for prefix, raw in (("baseline", br), ("treatment", tr))},
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
            "changed_page_mrr": None if n == 0 else sum(1 / r[f"{prefix}_page_rank"] if r[f"{prefix}_page_rank"] else 0 for r in sel) / n,
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
        "evidence": {
            "software": {"python": platform.python_version(), "numpy": version("numpy"), "rank-bm25": version("rank-bm25")},
            "config": exp, "config_sha256": digest(exp),
            "retrieval": {**RETRIEVAL, "top_k": exp.get("top_k", 5), "rank_bm25_version": version("rank-bm25")},
            "documents": {v: [{"doc_id": d.doc_id, "sha256": digest(asdict(d)), **asdict(d)} for d in ds]
                          for v, ds in (("baseline", baseline_docs), ("treatment", treatment_docs))},
            "negative_controls_unchanged": all(b == t for b, t in zip(base, treat) if b["role"] == "negative_control"),
            "negative_control_entity_ranks_unchanged": all(b["ranked_entities"] == t["ranked_entities"] for b, t in zip(base, treat) if b["role"] == "negative_control"),
            "scope": "local lexical retrieval; entity rank is not a relevant recommendation judgement",
        },
    }


def load_experiment(exp_id: str) -> dict:
    if not ID_RE.fullmatch(exp_id):
        raise ValueError("invalid experiment ID")
    return json.loads((EXP_DIR / f"{exp_id}.json").read_text(encoding="utf-8"))


def save_result(result: dict) -> Path:
    if not ID_RE.fullmatch(result["experiment_id"]):
        raise ValueError("invalid experiment ID")
    out = EXP_DIR / "results" / f"{result['experiment_id']}_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Offline controlled retrieval experiment")
    parser.add_argument("experiment_id")
    args = parser.parse_args()
    print(save_result(run_experiment(load_experiment(args.experiment_id))))
