"""Staged import finalization (geolab.staging). Uses temp copies only — never writes to the repo."""
import csv
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geolab import contract as C  # noqa: E402
from geolab import staging as SG  # noqa: E402
from geolab import store  # noqa: E402

BATCH = ROOT / "data" / "staging" / "forme_2026-11-20"


@pytest.fixture
def env(tmp_path, monkeypatch):
    batch = tmp_path / "forme_2026-11-20"
    batch.mkdir()
    shutil.copy(BATCH / "observations_contract_staging.jsonl", batch)
    prompts = tmp_path / "prompts.csv"  # team prompts only: without the rows this batch already imported
    lines = store.PROMPTS_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    prompts.write_text("".join(ln for ln in lines if not ln.startswith("P-")), encoding="utf-8")
    out = tmp_path / "raw"
    out.mkdir()
    monkeypatch.setattr(store, "UPLOAD_DIR", out)
    return batch, prompts, out


def _resolve(batch: Path, rows: dict[str, dict]):
    with open(batch / "resolution.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SG.RESOLUTION_COLS)
        w.writeheader()
        for rid, r in rows.items():
            w.writerow({"response_id": rid, **r})


CONFIRMED = {"query_source": "история чата, копия 2026-11-20", "collector": "P3", "collector_source": "капитан",
             "evidence_status": "awaiting"}
NEW_CLASS = {"category": "paint", "city": "almaty", "language": "ru", "funnel_stage": "retailer_discovery",
             "intent": "transactional", "brand_type": "unbranded", "test_group": "retail", "priority": "P0"}


def test_blank_resolution_blocks_every_row(env):
    batch, prompts, _ = env
    _resolve(batch, {})
    results, new = SG.plan(batch, prompts)
    assert [r.status for r in results] == ["blocked"] * 10 and not new


def test_repo_batch_resolution_is_self_attested_never_verified():
    results, new = SG.plan(BATCH)  # the real resolution.csv: exact questions from v2 docx, collector via captain
    assert [r.status for r in results] == ["ready"] * 10
    assert {r.prompt_id for r in results} == {r.record["prompt_id"] for r in results}
    assert all(r.prompt_id.startswith("P-") for r in results)  # participant IDs (new prompts or, after import, existing)
    assert len(new) == sum(r.prompt_match == "new" for r in results if r.response_id in {"OBS-001", "OBS-002", "OBS-003", "OBS-004", "OBS-005", "OBS-006", "BR-C-PA-001", "BR-C-CH-001"})
    assert {(r.record["data_type"], r.record["verification_status"], r.record["evidence_link"]) for r in results} == {("MANUAL_REPORTED", "self_attested", "")}
    assert not any(store.is_real_kpi_row(r.record) for r in results)
    br = {r.response_id: r.prompt_id for r in results if r.response_id.startswith("BR-")}
    assert br == {"BR-G-PA-001": "P-BRIDGE-PA-001", "BR-C-PA-001": "P-BRIDGE-PA-001", "BR-G-CH-001": "P-BRIDGE-CH-001", "BR-C-CH-001": "P-BRIDGE-CH-001"}


def test_existing_query_reuses_prompt_id_and_imports_pending(env):
    batch, prompts, out = env
    _resolve(batch, {"OBS-004": {**CONFIRMED, "exact_query": "  где купить ЛЮСТРУ в Алматы? "}})
    results, new = SG.plan(batch, prompts)
    r = next(x for x in results if x.response_id == "OBS-004")
    assert (r.status, r.prompt_id, r.prompt_match, new) == ("ready", "R-C-ALA-01", "existing", [])
    assert r.record["verification_status"] == "pending" and r.record["evidence_link"] == "assets/evidence/OBS-004.png"
    assert "запроса в исходных файлах отсутствует" not in r.record["notes"]
    before = prompts.read_text(encoding="utf-8")
    [path] = SG.apply(batch, results, new, prompts_path=prompts)
    assert path == out / "P3_observations_forme_2026-11-20.csv" and prompts.read_text(encoding="utf-8") == before
    recs, iss = store.load_observations(real_dirs=[out])
    assert [x["response_id"] for x in recs] == ["OBS-004"] and not [i for i in iss if i["severity"] == "error"]
    assert recs[0]["cited_urls"] and not store.is_real_kpi_row(recs[0])          # pending never in KPI
    with pytest.raises(FileExistsError):                                          # no silent overwrite
        SG.apply(batch, results, new, prompts_path=prompts)


def test_new_query_needs_full_classification(env):
    batch, prompts, _ = env
    q = "Где в Алматы купить качественную интерьерную краску с колеровкой?"
    _resolve(batch, {"OBS-001": {**CONFIRMED, "exact_query": q, "category": "paint", "city": "almaty"}})
    r = SG.plan(batch, prompts)[0][0]
    assert r.status == "blocked" and any(x.startswith("prompt.") for x in r.reasons)
    _resolve(batch, {"OBS-001": {**CONFIRMED, "exact_query": q, **NEW_CLASS}})
    results, new = SG.plan(batch, prompts)
    assert results[0].status == "ready" and results[0].prompt_match == "new" and new[0]["prompt_id"] == "P-PA-ALM-001"
    SG.apply(batch, results, new, prompts_path=prompts)
    assert store.load_prompts(prompts)["query"].iloc[-1] == q


def test_no_evidence_gets_self_attested_never_verified(env):
    batch, prompts, out = env
    _resolve(batch, {"OBS-004": {**CONFIRMED, "exact_query": "Где купить люстру в Алматы?", "evidence_status": "none",
                                 "verification_status": "verified", "verified_by": "P2", "verification_note": "x"}})
    assert SG.plan(batch, prompts)[0][3].status == "blocked"
    _resolve(batch, {"OBS-004": {**CONFIRMED, "exact_query": "Где купить люстру в Алматы?", "evidence_status": "none"}})
    results, new = SG.plan(batch, prompts)
    r = results[3]
    assert r.status == "ready" and r.record["verification_status"] == "self_attested" and r.record["evidence_link"] == ""
    assert r.record["data_type"] == "MANUAL_REPORTED"
    SG.apply(batch, results, new, prompts_path=prompts)
    recs, _ = store.load_observations(real_dirs=[out])
    assert recs[0]["verification_status"] == "self_attested" and not store.is_real_kpi_row(recs[0])


@pytest.mark.parametrize("extra,ok", [
    ({"evidence_status": "awaiting", "verified_by": "P2", "verification_note": "сверено"}, False),   # no evidence yet
    ({"evidence_status": "available", "evidence_link": "https://chatgpt.com/share/abc", "verified_by": "P3",
      "verification_note": "сверено"}, False),                                                       # self-verified
    ({"evidence_status": "available", "evidence_link": "https://chatgpt.com/share/abc", "verified_by": "P2"}, False),  # no note
    ({"evidence_status": "available", "evidence_link": "https://chatgpt.com/share/abc", "verified_by": "P2",
      "verification_note": "текст и 9 URL совпадают с диалогом"}, True),
])
def test_verified_only_with_evidence_and_independent_check(env, extra, ok):
    batch, prompts, _ = env
    _resolve(batch, {"OBS-004": {**CONFIRMED, "exact_query": "Где купить люстру в Алматы?", "verification_status": "verified", **extra}})
    r = SG.plan(batch, prompts)[0][3]
    assert (r.status == "ready") is ok
    if ok:
        assert r.record["verification_status"] == "verified" and store.is_real_kpi_row({**r.record, "data_type": "MANUAL_VERIFIED"})


def test_contract_self_attested_rules():
    base = {"response_id": "X-1", "prompt_id": "R-C-ALA-01", "query": "Где купить люстру в Алматы?", "provider": "gemini",
            "model": "", "search_mode": "search_on", "timestamp": "2026-11-20T14:05+05:00", "run_no": "1", "language": "ru",
            "region_setting": "", "answer_text": "Ответ достаточно длинный для проверки валидатора, SVET.KZ.", "cited_urls": "",
            "data_type": "MANUAL_REPORTED", "verification_status": "self_attested", "collector": "P3", "verified_by": "",
            "evidence_link": "", "notes": "текст сохранился в документе сборщика"}
    P = store.prompts_index()
    assert C.validate_rows("observations", [(2, base)], prompts=P)[0]
    for bad in ({"notes": ""}, {"evidence_link": "https://chatgpt.com/share/x"}, {"verified_by": "P2"},
                {"data_type": "MANUAL_VERIFIED"}, {"verification_status": "verified", "verified_by": "P2"}):
        assert not C.validate_rows("observations", [(2, {**base, **bad})], prompts=P)[0], bad


def test_dashboard_shows_self_attested_outside_kpi(env, monkeypatch):
    from streamlit.testing.v1 import AppTest
    batch, prompts, out = env
    _resolve(batch, {"OBS-004": {**CONFIRMED, "exact_query": "Где купить люстру в Алматы?", "evidence_status": "none"}})
    SG.apply(batch, *SG.plan(batch, prompts), prompts_path=prompts)
    monkeypatch.setattr(store, "REAL_DIRS", (out,))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.selectbox[0].set_value("svet_kz").run()
    at.sidebar.selectbox[1].set_value("retailer_discovery").run()
    at.sidebar.radio[0].set_value("Реальные KPI").run()
    assert not at.exception
    assert all("A предварительно" in m.label for m in at.metric)                # 0 verified -> no block-B numbers
    assert {m.label: m.value for m in at.metric}["Mention rate · A предварительно"] == "100%"  # A shows the real row
    assert any("self_attested" in i.value for i in at.info)
    at.sidebar.radio[0].set_value("Наблюдения AI (evidence)").run()
    assert not at.exception and any("Где купить люстру в Алматы?" in e.label for e in at.expander)


def test_paired_series_import_readiness(tmp_path, monkeypatch):
    """P2/P3 paired series: same question, 2 providers x 2 runs. TEST FIXTURE rows only (not data)."""
    import csv as _csv
    from streamlit.testing.v1 import AppTest
    q = store.prompts_index()["R-C-AST-01"]["query"]
    rows = []
    for prov, coll, letter in (("chatgpt_search", "P2", "C"), ("gemini", "P3", "G")):
        for run in (1, 2):
            rows.append({"response_id": f"TEST-PS-{letter}-R{run}", "prompt_id": "R-C-AST-01", "query": q, "provider": prov, "model": "",
                         "search_mode": "search_on", "timestamp": f"2026-11-20T18:0{run}+05:00", "run_no": str(run), "language": "ru",
                         "region_setting": "", "answer_text": ("В Астане: 1. SVET.KZ — Мангилик Ел 29/2. 2. TEKLED." if run == 1 else
                                                               f"Варианты в Астане ({prov}, прогон {run}): TEKLED, Митрис."),
                         "cited_urls": "https://svet.kz/contact/" if run == 1 else "", "data_type": "MANUAL_REPORTED",
                         "verification_status": "self_attested", "collector": coll, "verified_by": "", "evidence_link": "",
                         "notes": "TEST FIXTURE — not a real observation"})
    with open(tmp_path / "P2P3_paired_TEST.csv", "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    recs, iss = store.load_observations(real_dirs=[tmp_path])
    assert len(recs) == 4 and not [i for i in iss if i["severity"] == "error"]
    from geolab.metrics import analyze_records, consistency
    from geolab.registry import load_registry
    cons = consistency(analyze_records(recs, load_registry()), "svet_kz")
    assert sorted(cons.runs) == [2, 2] and set(cons.mention_share) == {0.5}
    # duplicate response_id across files is an error, not a silent overwrite
    (tmp_path / "dup.csv").write_text((tmp_path / "P2P3_paired_TEST.csv").read_text(encoding="utf-8"), encoding="utf-8")
    _, iss2 = store.load_observations(real_dirs=[tmp_path])
    assert any(i["severity"] == "error" and i["field"] == "response_id" for i in iss2)
    (tmp_path / "dup.csv").unlink()
    monkeypatch.setattr(store, "REAL_DIRS", (tmp_path,))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.selectbox[0].set_value("svet_kz").run()
    at.sidebar.selectbox[2].set_value("astana").run()
    at.sidebar.radio[0].set_value("Реальные KPI").run()
    assert not at.exception and any("Result Consistency" in h.value for h in at.subheader)


def test_real_search_cannot_enter_via_manual_dir_or_staging(tmp_path, env):
    """REAL_SEARCH in data/raw/manual (UI upload target) or via staging is rejected; data/raw/api is the only channel."""
    import csv as _csv
    batch, prompts, out = env
    q = store.prompts_index()["R-C-ALA-01"]["query"]
    row = {"response_id": "RS-T1", "prompt_id": "R-C-ALA-01", "query": q, "provider": "chatgpt_search", "model": "",
           "search_mode": "search_on", "timestamp": "2026-11-20T14:05+05:00", "run_no": "1", "language": "ru", "region_setting": "",
           "answer_text": "TEST FIXTURE: длинный ответ про SVET.KZ на Кабдолова.", "cited_urls": "", "data_type": "REAL_SEARCH",
           "verification_status": "verified", "collector": "P3", "verified_by": "P2", "evidence_link": "", "notes": "TEST FIXTURE"}
    manual = tmp_path / "raw" / "manual"
    api = tmp_path / "raw" / "api"
    for d in (manual, api):
        d.mkdir(parents=True)
        with open(d / "rs.csv", "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
            w.writeheader()
            w.writerow({**row, "response_id": f"RS-{d.name}"})
    recs, iss = store.load_observations(real_dirs=[manual])
    assert not recs and any(i["field"] == "data_type" for i in iss)                  # manual channel: rejected
    recs, iss = store.load_observations(real_dirs=[api])
    assert not recs and any(i["field"] == "evidence_link" for i in iss)              # api channel: still needs evidence
    st = json.loads((batch / "observations_contract_staging.jsonl").read_text(encoding="utf-8").splitlines()[3])
    st["data_type"] = "REAL_SEARCH"
    (batch / "observations_contract_staging.jsonl").write_text(json.dumps(st, ensure_ascii=False) + "\n", encoding="utf-8")
    _resolve(batch, {st["response_id"]: {**CONFIRMED, "exact_query": "Где купить люстру в Алматы?"}})
    r = SG.plan(batch, prompts)[0][0]
    assert r.status == "invalid" and any("REAL_SEARCH" in x for x in r.reasons)  # staging: rejected


def test_current_ten_answers_unchanged_and_never_verified():
    import hashlib
    p = ROOT / "data" / "raw" / "manual" / "P3_observations_forme_2026-11-20.csv"
    assert hashlib.sha256(p.read_bytes()).hexdigest().startswith("7b74a303127c024a")
    recs, iss = store.load_observations()
    assert len(recs) == 10 and not iss and not any(store.is_real_kpi_row(r) for r in recs)
    assert {(r["data_type"], r["verification_status"]) for r in recs} == {("MANUAL_REPORTED", "self_attested")}
