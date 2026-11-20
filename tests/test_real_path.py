"""End-to-end: file -> contract -> storage -> entities -> citations -> verified KPI -> dashboard.
Uses tests/fixtures/real_path (TEST FIXTURE, never under data/raw)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geolab import contract as C  # noqa: E402
from geolab import store  # noqa: E402
from geolab.metrics import analyze_records, entity_metrics  # noqa: E402
from geolab.registry import load_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/real_path/P3_observations_fixture.csv"
REG = load_registry()


def test_fixture_is_not_in_real_dirs():
    assert all(FIX.resolve().parent != d.resolve() for d in store.REAL_DIRS)


def test_end_to_end(tmp_path, monkeypatch):
    # 1. contract validation of a ';'-separated Excel CSV, with lowercase query and Z timezone
    valid, issues = C.validate_file("observations", FIX, prompts=store.prompts_index())
    assert [i for i in issues if i.severity == "error"] == []
    assert len(valid) == 2
    # 2. storage: verbatim save, no overwrite
    monkeypatch.setattr(store, "UPLOAD_DIR", tmp_path)
    p1 = store.save_upload(FIX.name, FIX.read_bytes())
    p2 = store.save_upload(FIX.name, FIX.read_bytes())
    assert p1 != p2 and p1.read_bytes() == FIX.read_bytes()
    p2.unlink()
    # 3. loader joins prompt metadata
    recs, iss = store.load_observations(real_dirs=[tmp_path])
    assert [i for i in iss if i["severity"] == "error"] == []
    r1 = next(r for r in recs if r["response_id"] == "FIX-001")
    assert r1["city"] == "astana" and r1["funnel_stage"] == "retailer_discovery"
    assert "\n1. **SVET.KZ**" in r1["answer_text"]  # original text preserved incl. newlines/markdown
    # 4. citations: comma/semicolon separated, utm duplicate with in-text link collapsed, none lost
    items = analyze_records(recs, REG)
    a1 = next(it.analysis for it in items if it.record["response_id"] == "FIX-001")
    assert sorted(c.domain for c in a1.citations) == ["2gis.kz", "kaspi.kz", "svet.kz"]
    assert {c.source_type for c in a1.citations} == {"client_site", "map_directory", "marketplace"}
    # 5. entities: retailers vs manufacturers, inflected Russian form, explicit ranking
    assert a1.mentions["svet_kz"].level == "retailer" and a1.mentions["svet_kz"].rank == 1
    assert a1.mentions["maytoni"].level == "manufacturer"
    assert "centr_krasok" in a1.mentions  # "Центре Красок"
    a2 = next(it.analysis for it in items if it.record["response_id"] == "FIX-002")
    assert {"maytoni", "odeon_light", "eglo"} <= set(a2.mentions)  # Kazakh/Russian mixed text
    # 6. KPI uses only verified rows
    kpi = [it for it in items if store.is_real_kpi_row(it.record)]
    assert [it.record["response_id"] for it in kpi] == ["FIX-001"]
    m = entity_metrics(kpi, "svet_kz")
    assert m["answers"] == 1 and m["top3_rate"] == 1.0 and m["citation_rate"] == 1.0


def test_duplicate_text_warning(tmp_path):
    shutil.copy(FIX, tmp_path / "a.csv")
    txt = FIX.read_text(encoding="utf-8").replace("FIX-001", "FIX-901").replace("FIX-002", "FIX-902")
    (tmp_path / "b.csv").write_text(txt, encoding="utf-8")
    recs, iss = store.load_observations(real_dirs=[tmp_path])
    assert len(recs) == 4
    assert sum("совпадает" in i["reason"] for i in iss) == 2


def test_duplicate_id_across_files_is_error(tmp_path):
    shutil.copy(FIX, tmp_path / "a.csv")
    shutil.copy(FIX, tmp_path / "b.csv")
    recs, iss = store.load_observations(real_dirs=[tmp_path])
    assert len(recs) == 2
    assert sum(i["severity"] == "error" and i["field"] == "response_id" for i in iss) == 2


def verified_metrics(at):
    """Metrics of block B (independently verified). Block A labels end with 'A предварительно'."""
    return [m for m in at.metric if "A предварительно" not in m.label]


def test_dashboard_shows_verified_fixture(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    shutil.copy(FIX, tmp_path / FIX.name)
    monkeypatch.setattr(store, "REAL_DIRS", (tmp_path,))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.selectbox[0].set_value("svet_kz").run()
    at.sidebar.selectbox[1].set_value("retailer_discovery").run()
    at.sidebar.radio[0].set_value("Реальные KPI").run()
    assert not at.exception
    vals = {m.label: m.value for m in at.metric}
    assert vals["Mention rate"] == "100%" and vals["Top-3 rate"] == "100%"
    assert any("Малая выборка: N = 1" in w.value for w in at.warning)          # small-sample flag
    assert not any("MRR" in k or "Hit@3" in k for k in vals)                     # no experiment metrics in real KPIs
    at.sidebar.selectbox[3].set_value("gemini").run()                           # provider filter: FIX-001 is chatgpt_search
    assert not at.exception and not at.metric                                   # gemini: no rows at all
    at.sidebar.selectbox[3].set_value("chatgpt_search").run()
    assert {m.label: m.value for m in at.metric}["Mention rate"] == "100%"
    at.sidebar.selectbox[3].set_value("all").run()
    at.sidebar.selectbox[1].set_value("brand_discovery").run()
    assert not at.exception and not verified_metrics(at)  # FIX-002 is pending -> no verified KPI
    assert any(m.label.endswith("A предварительно") for m in at.metric)       # but shown as preliminary (A)
    assert any("pending" in w.value for w in at.warning)


def test_replace_same_file_version(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "UPLOAD_DIR", tmp_path)
    p1 = store.save_upload("P3_observations_gemini.csv", b"v1")
    p2 = store.save_upload("P3_observations_gemini.csv", b"v2", replace=True)
    assert p1 == p2 and p2.read_bytes() == b"v2" and len(list(tmp_path.iterdir())) == 1
    import pytest
    with pytest.raises(ValueError):
        store.save_upload("_hidden.csv", b"x")


def test_dashboard_experiment_page_uses_selected_corpus():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.radio[0].set_value("Контролируемый эксперимент").run()
    for exp_id, docs, owners, neg, hit3 in [("EXP-001-COMPETITIVE-v1", 15, 6, 5, "75% → 100%"), ("EXP-001", 12, 3, 3, "100% → 100%")]:
        sel = next(s for s in at.selectbox if s.label == "Эксперимент")
        sel.set_value(exp_id).run()
        assert not at.exception
        m = {x.label: x.value for x in at.metric}
        assert m["Документов в корпусе"] == str(docs) and m["Владельцев документов"] == str(owners)
        assert m["Negative controls"] == str(neg) and m["Целевых запросов"] == "4"
        assert m["Hit@3"] == hit3 and m["Citation Rate"] == "100% → 100%"
        assert m["Hit@3 · controls"] == ("20% → 20%" if neg == 5 else "33% → 33%")


def test_exp002_svet_astana_reproducible_and_shown():
    """EXP-002: Claude-built corpus, Codex engine unchanged. Saved result == fresh run; controls unchanged."""
    import json
    from geolab import experiment as X
    d = ROOT / "data" / "research" / "exp002_svet_astana"
    exp = json.loads((d / "EXP-002.json").read_text(encoding="utf-8"))
    fresh = X.run_experiment(exp, corpus_dir=d)
    saved = json.loads((d / "EXP-002_result.json").read_text(encoding="utf-8"))
    assert fresh["per_query"] == saved["per_query"] and fresh["summary"] == saved["summary"]
    t, n = fresh["summary"]["target"], fresh["summary"]["negative_control"]
    assert (t["baseline"]["mrr"], t["treatment"]["mrr"]) == (0.875, 0.875)                 # honest null at owner level
    assert t["treatment"]["changed_page_mrr"] > t["baseline"]["changed_page_mrr"]          # page-level move (T4)
    assert n["baseline"] == n["treatment"] and fresh["evidence"]["negative_control_entity_ranks_unchanged"]
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.radio[0].set_value("Контролируемый эксперимент").run()
    next(s for s in at.selectbox if s.label == "Эксперимент").set_value("EXP-002-SVET-ASTANA").run()
    assert not at.exception
    m = {x.label: x.value for x in at.metric}
    assert m["Документов в корпусе"] == "12" and m["Negative controls"] == "5" and m["MRR владельца"] == "0.875 → 0.875"


def test_g11_link_appearances_vs_unique_urls():
    """35 link appearances (dedup within an answer) != 33 globally unique URLs (Codex audit G11)."""
    from geolab import store
    from geolab.analysis import analyze_answer, url_key
    from geolab.registry import load_registry
    reg = load_registry()
    recs, _ = store.load_observations()
    per_answer = [{url_key(c.url) for c in analyze_answer(r["answer_text"], reg, r["cited_urls"]).citations} for r in recs]
    assert sum(len(s) for s in per_answer) == 35 and len(set().union(*per_answer)) == 33
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.selectbox[0].set_value("svet_kz").run()
    at.sidebar.radio[0].set_value("Источники").run()
    assert not at.exception and any("уникальных URL" in c.value for c in at.caption)


def test_g12_g13_geo_cards_traceable_and_current():
    import json
    import re
    cards = json.loads((ROOT / "data" / "processed" / "recommendations.json").read_text(encoding="utf-8"))
    core = [c for c in cards if c.get("tier") == "core"]
    assert 3 <= len(core) <= 4
    for c in core:
        assert c["facts"] and all(f["fact"] and f["source_url"] and f["evidence"] for f in c["facts"]), c["issue_id"]
        for k in ("geo_issue", "proposal", "hypothesis", "test", "limitations", "before", "after", "priority", "status"):
            assert c.get(k), (c["issue_id"], k)
        # no promise of a guaranteed AI effect
        assert not re.search(r"(?<!не )гарантир", c["hypothesis"], re.I), c["issue_id"]
    checks = json.loads((ROOT / "data" / "research" / "geo_recheck_2026-11-20" / "checks.json").read_text(encoding="utf-8"))
    assert checks and all(x["result"] == "PASS" for x in checks)            # every card fact re-checked on the live page
    xx3 = next(c for c in cards if c["issue_id"] == "XX-003")                  # G12: branch vs delivery not mixed
    assert "доставк" in xx3["finding"] and "не доказывает" in xx3["finding"]   # absence of a published address != no store
    for c in cards:                                                            # every card has the full structure
        for k in ("facts", "geo_issue", "observation", "hypothesis", "proposal", "test", "limitations"):
            assert c.get(k), (c["issue_id"], k)
        blob = json.dumps(c, ensure_ascii=False)
        assert "Физического магазина" not in blob and "та же группа" not in blob, c["issue_id"]
    assert not any(c.get("linked_experiment") for c in cards)                  # no causal link card -> EXP-002
    assert not any(c["issue_id"] == "CK-002" for c in cards)                   # outdated card removed


def test_demo_deep_links_and_demo_path():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.query_params["page"] = "6"
    at.query_params["client"] = "svet_kz"
    at.query_params["city"] = "astana"
    at.run()
    assert not at.exception and at.sidebar.radio[0].value == "Рекомендации"
    assert at.sidebar.selectbox[0].value == "svet_kz" and at.sidebar.selectbox[2].value == "astana"
    assert any("GEO-01" in e.label for e in at.expander)
    at2 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at2.query_params["page"] = "99"                       # bad values fall back to defaults
    at2.query_params["client"] = "nope"
    at2.run()
    assert not at2.exception and at2.sidebar.radio[0].value == "Обзор"


def test_pitch_docs_match_results_no_overclaims():
    """Demo script / README / experiment docs must match result files (Codex QA: wrong rank, unconfirmed Google Maps role)."""
    import json
    r = json.loads((ROOT / "data/research/exp002_svet_astana/EXP-002_result.json").read_text(encoding="utf-8"))
    t1 = next(q for q in r["per_query"] if q["query_id"] == "T1")
    assert (t1["baseline_rank"], t1["treatment_rank"]) == (2, 2)
    banned = ["ставит SVET.KZ первым", "ranks SVET.KZ first", "three to five", "три–пять", "3–5 магазинов",
              "outside the page", "рычаг — вне", "карточки и каталоги, которые AI цитирует"]
    for p in ["README.md", "docs/FINAL_DEMO_SCRIPT.md", "docs/STATUS.md", "docs/EXPERIMENT_AUDIT_2026-11-20.md",
              "docs/PITCH_EVIDENCE_PACKAGE.md", "docs/TECHNICAL_DEFENSE_FACTS.md", "data/research/exp002_svet_astana/INTERPRETATION.md"]:
        f = ROOT / p
        if f.exists():
            txt = f.read_text(encoding="utf-8")
            assert not [b for b in banned if b in txt], (p, [b for b in banned if b in txt])
