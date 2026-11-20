import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geolab.analysis import analyze_answer, classify_source, find_entity_spans, normalize_domain  # noqa: E402
from geolab.experiment import run_experiment, tokenize  # noqa: E402
from geolab.metrics import entity_metrics, fmt, rate, AnalyzedResponse  # noqa: E402
from geolab.registry import load_registry  # noqa: E402

REG = load_registry()


def test_registry_separates_retailer_and_manufacturer():
    assert REG.entities["svet_kz"].level == "retailer"
    assert REG.entities["maytoni"].level == "manufacturer"
    assert {e.id for e in REG.assortment("svet_kz")} >= {"maytoni", "arte_lamp"}
    assert "tikkurila" not in {e.id for e in REG.assortment("centr_krasok")}


def test_alias_match_no_false_positive_on_common_word():
    e = REG.entities["svet_kz"]
    assert find_entity_spans("Хороший свет в комнате важен", e) == []
    assert len(find_entity_spans("Загляните в SVET.KZ на Кабдолова", e)) == 1


def test_overlapping_aliases_count_once():
    e = REG.entities["centr_krasok"]
    assert len(find_entity_spans("Центр Красок №1 — магазин", e)) == 1


def test_ranking_only_from_numbered_list():
    text = "Варианты:\n1. Tikkurila — финская\n2. Dulux — тоже хорошо\n3. Caparol\nТакже есть Jotun."
    a = analyze_answer(text, REG)
    assert a.has_ranking
    assert a.mentions["tikkurila"].rank == 1
    assert a.mentions["caparol"].rank == 3
    assert a.mentions["jotun"].rank is None


def test_no_ranking_in_free_text():
    a = analyze_answer("Можно рассмотреть Dulux, Tikkurila или Caparol.", REG)
    assert not a.has_ranking
    assert all(m.rank is None for m in a.mentions.values())


def test_negative_mention_not_recommended():
    a = analyze_answer("Не рекомендую Dulux для фасада.", REG)
    assert "dulux" in a.mentions and not a.mentions["dulux"].recommended


def test_citations_dedup_and_classify():
    text = "См. https://svet.kz/brands/maytoni/ и https://2gis.kz/almaty/firm/1, а также https://svet.kz/brands/maytoni"
    a = analyze_answer(text, REG, ["https://www.instagram.com/svet.kz_abis/"])
    types = {c.source_type for c in a.citations}
    assert len(a.citations) == 3
    assert {"client_site", "map_directory", "social"} <= types
    assert normalize_domain("https://WWW.Svet.kz/x") == "svet.kz"
    assert classify_source("https://example.org/a", REG) == ("other_web", None)


def test_rate_na_not_zero():
    assert rate(0, 0) is None
    assert fmt(None) == "N/A"
    assert rate(1, 4) == 0.25


def test_entity_metrics_denominators():
    recs = [
        {"prompt_id": "x", "provider": "p", "answer_text": "1. Maytoni\n2. Eglo\n3. Lussole", "cited_urls": []},
        {"prompt_id": "x", "provider": "p", "answer_text": "Можно купить в SVET.KZ https://svet.kz/", "cited_urls": []},
    ]
    items = [AnalyzedResponse(r, analyze_answer(r["answer_text"], REG)) for r in recs]
    m = entity_metrics(items, "maytoni")
    assert m["mention_rate"] == 0.5 and m["top3_rate"] == 1.0 and m["ranked_answers"] == 1
    assert m["citation_rate"] == 0.0  # 1 answer with citations, none Maytoni-owned
    s = entity_metrics(items, "svet_kz")
    assert s["top3_rate"] == 0.0 and s["citation_rate"] == 1.0


def test_tokenize_stems_russian_forms():
    assert tokenize("Караганде")[0] == tokenize("Караганда")[0]


def _write(p: Path, d: dict):
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_experiment_only_changed_doc_differs(tmp_path):
    (tmp_path / "baseline").mkdir()
    (tmp_path / "treatment").mkdir()
    _write(tmp_path / "baseline" / "a.json", dict(doc_id="a", entity_id="client", url="u/a", title="Магазин", text="люстры бра споты", source_type="x"))
    _write(tmp_path / "baseline" / "b.json", dict(doc_id="b", entity_id="rival", url="u/b", title="Свет", text="люстры Караганда доставка магазин", source_type="x"))
    _write(tmp_path / "baseline" / "c.json", dict(doc_id="c", entity_id="paint", url="u/c", title="Краски", text="краска фасадная металл", source_type="x"))
    for i in range(4):  # filler docs so BM25 idf is well-defined
        _write(tmp_path / "baseline" / f"f{i}.json", dict(doc_id=f"f{i}", entity_id=f"f{i}", url=f"u/f{i}", title="Новости", text=f"погода спорт кино {i}", source_type="x"))
    _write(tmp_path / "treatment" / "a.json", dict(doc_id="a", entity_id="client", url="u/a", title="Магазин люстр", text="люстры с доставкой в Караганду. Доставка люстр по Караганде за 3 дня", source_type="x"))
    exp = {"experiment_id": "t", "target_entity": "client", "changed_doc_ids": ["a"], "top_k": 1,
           "queries": [{"query_id": "q1", "query": "люстры Караганда доставка", "role": "target"},
                       {"query_id": "q2", "query": "краска фасадная металл", "role": "negative_control"}]}
    res = run_experiment(exp, tmp_path)
    q1, q2 = res["per_query"]
    assert q1["baseline_rank"] is None and q1["treatment_rank"] == 1
    assert q2["baseline_rank"] is None and q2["treatment_rank"] is None
    assert res["summary"]["negative_control"]["treatment"]["top3_rate"] == 0.0


def test_list_item_with_negation_not_recommended():
    a = analyze_answer("1. SVET.KZ — люстры\n2. Центр Красок не продает люстры, это магазин краски", REG)
    assert a.mentions["svet_kz"].recommended and not a.mentions["centr_krasok"].recommended
