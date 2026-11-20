import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geolab.experiment import EXP_DIR, digest, load_corpus, load_experiment, run_experiment, validate_experiment


def test_original_reproduces_saved_metrics_and_raw():
    result = run_experiment(load_experiment("EXP-001"))
    saved = json.loads((EXP_DIR / "results/EXP-001_result.json").read_text())
    for role in saved["summary"]:
        for variant in ("baseline", "treatment"):
            for metric, value in saved["summary"][role][variant].items():
                assert result["summary"][role][variant][metric] == value
    assert result["raw"] == saved["raw"]
    assert result == run_experiment(load_experiment("EXP-001"))
    assert result["evidence"]["negative_control_entity_ranks_unchanged"]


@pytest.mark.parametrize("mutation", [
    {"top_k": 0}, {"top_k": True}, {"queries": []}, {"changed_doc_ids": ["../bad"]},
    {"changed_doc_ids": ["ck_kids", "ck_kids"]}, {"experiment_id": "../../bad"},
])
def test_invalid_configuration(mutation):
    exp = {**load_experiment("EXP-001"), **mutation}
    with pytest.raises(ValueError):
        validate_experiment(exp)


def test_duplicate_query_and_unknown_role():
    exp = load_experiment("EXP-001")
    exp["queries"].append(copy.deepcopy(exp["queries"][0]))
    with pytest.raises(ValueError): validate_experiment(exp)
    exp["queries"].pop(); exp["queries"][0]["role"] = "REAL"
    with pytest.raises(ValueError): validate_experiment(exp)
    with pytest.raises(ValueError): validate_experiment([])


def test_identity_and_corruption(tmp_path):
    (tmp_path / "baseline").mkdir(); (tmp_path / "treatment").mkdir()
    doc = dict(doc_id="a", entity_id="target", url="https://example.org/a", title="Paint", text="краска детская", source_type="client_site")
    (tmp_path / "baseline/a.json").write_text(json.dumps(doc))
    (tmp_path / "treatment/a.json").write_text(json.dumps({**doc, "entity_id": "rival"}))
    with pytest.raises(ValueError, match="identity"): load_corpus("treatment", ["a"], tmp_path)
    (tmp_path / "baseline/b.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="doc_id"): load_corpus("baseline", [], tmp_path)
    (tmp_path / "baseline/b.json").write_text('[]')
    with pytest.raises(ValueError, match="object"): load_corpus("baseline", [], tmp_path)


def test_invalid_variant_and_path():
    with pytest.raises(ValueError): load_corpus("typo", [])
    with pytest.raises(ValueError): run_experiment({**load_experiment("EXP-001"), "corpus_subdir": "../../"})


def test_snapshot_hashes_and_unchanged_competitors():
    result = run_experiment(load_experiment("EXP-001"))
    ev = result["evidence"]
    assert ev["config_sha256"] == digest(ev["config"])
    b, t = ev["documents"]["baseline"], ev["documents"]["treatment"]
    for doc in b + t:
        assert doc["sha256"] == digest({k: v for k, v in doc.items() if k != "sha256"})
    assert [x["doc_id"] for x, y in zip(b, t) if x != y] == ["ck_kids"]


def test_no_controls_returns_na():
    exp = load_experiment("EXP-001")
    exp["queries"] = [q for q in exp["queries"] if q["role"] == "target"]
    assert run_experiment(exp)["summary"]["negative_control"]["baseline"]["mrr"] is None


def test_competitive_replication_and_metric_arithmetic():
    exp = load_experiment("EXP-001-COMPETITIVE-v1")
    result = run_experiment(exp)
    saved = json.loads((EXP_DIR / "results/EXP-001-COMPETITIVE-v1_result.json").read_text())
    assert result == saved
    assert result["summary"]["target"]["baseline"]["mrr"] == pytest.approx((1/3 + 1 + 1/4 + 1/3)/4)
    assert result["summary"]["target"]["treatment"]["mrr"] == pytest.approx((1 + 1 + 1/3 + 1/3)/4)
    assert result["summary"]["target"]["baseline"]["top3_rate"] == 3/4
    assert result["evidence"]["negative_control_entity_ranks_unchanged"]
    b, t = result["evidence"]["documents"].values()
    assert len(b) == 15 and len({d["entity_id"] for d in b}) == 6
    assert [x["doc_id"] for x, y in zip(b, t) if x != y] == ["ck_kids"]


@pytest.mark.parametrize("degrade", [False, True])
def test_zero_and_negative_effect_are_preserved(tmp_path, degrade):
    for variant in ("baseline", "treatment"): (tmp_path / variant).mkdir()
    for i, text in enumerate(["детская краска", "краска магазин", "погода солнце", "спорт футбол", "музыка театр"]):
        doc = dict(doc_id=f"d{i}", entity_id=f"e{i}", url=f"https://example.org/{i}", title=text, text=text, source_type="retailer_site")
        (tmp_path / "baseline" / f"d{i}.json").write_text(json.dumps(doc))
        if i == 0:
            if degrade: doc.update(title="астрономия", text="астрономия космос")
            (tmp_path / "treatment/d0.json").write_text(json.dumps(doc))
    exp = dict(experiment_id="QA", target_entity="e0", changed_doc_ids=["d0"], top_k=3,
               queries=[dict(query_id="q", query="детская", role="target")])
    r = run_experiment(exp, tmp_path)["summary"]["target"]
    delta = r["treatment"]["mrr"] - r["baseline"]["mrr"]
    assert delta == (-1 if degrade else 0)
