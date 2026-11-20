import json
import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geolab import contract as C  # noqa: E402
from geolab.store import is_real_kpi_row, load_prompts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
PROMPTS = {r["prompt_id"]: r for r in load_prompts().to_dict("records")}
HEADER = (ROOT / "data/templates/observations_template.csv").read_text().strip()


def obs(**kw):
    base = dict(response_id="OBS-P3-001", prompt_id="R-C-ALA-01", query="Где купить люстру в Алматы?", provider="chatgpt_search",
                model="", search_mode="search_on", timestamp="2026-11-20T15:04+05:00", run_no="1", language="ru",
                region_setting="Almaty, no VPN", answer_text="Можно посмотреть SVET.KZ и маркетплейс Kaspi, там большой выбор люстр.",
                cited_urls="https://svet.kz/ | https://kaspi.kz/", data_type="MANUAL_VERIFIED", verification_status="pending",
                collector="P3", verified_by="", evidence_link="assets/evidence/OBS-P3-001.png", notes="")
    base.update(kw)
    return base


def run(rows, **kw):
    return C.validate_rows("observations", list(enumerate(rows, start=2)), prompts=PROMPTS, now=NOW, **kw)


def errors(issues):
    return {(i.row, i.field) for i in issues if i.severity == "error"}


def test_existing_prompts_pass_contract():
    rows, _ = C.read_rows("prompts.csv", (ROOT / "data/prompts/prompts.csv").read_bytes())
    valid, issues = C.validate_rows("prompts", rows)
    assert len(valid) == len(rows) == 51 and not [i for i in issues if i.severity == "error"]
    assert sum(r["prompt_id"].startswith("P-") for r in valid) == 8   # real participant questions (forme 2026-11-20)


def test_template_header_matches_schema():
    assert HEADER.split(",") == [c.name for c in C.SCHEMAS["observations"]["cols"]]


def test_valid_observation_parsed():
    valid, issues = run([obs()])
    assert not errors(issues)
    assert valid[0]["cited_urls"] == ["https://svet.kz/", "https://kaspi.kz/"] and valid[0]["run_no"] == 1


def test_errors_report_row_and_field():
    _, issues = run([obs(), obs(response_id="OBS-P3-001", provider="chatgpt", timestamp="20.11.2026", cited_urls="svet.kz")])
    e = errors(issues)
    assert {(3, "response_id"), (3, "provider"), (3, "timestamp"), (3, "cited_urls")} <= e
    assert not any(r == 2 for r, _ in e)


def test_query_must_match_prompt_and_prompt_must_exist():
    _, issues = run([obs(query="Где купить люстру?"), obs(response_id="X2", prompt_id="NOPE-1")])
    assert {(2, "query"), (3, "prompt_id")} <= errors(issues)


def test_synthetic_and_experiment_rejected_from_real_import():
    _, issues = run([obs(data_type="SYNTHETIC_DEMO"), obs(response_id="X2", data_type="CONTROLLED_EXPERIMENT")])
    assert {(2, "data_type"), (3, "data_type")} <= errors(issues)
    valid, issues = run([obs(data_type="SYNTHETIC_DEMO")], allow_synthetic=True)
    assert len(valid) == 1


def test_future_and_naive_dates_rejected():
    _, issues = run([obs(timestamp="2026-11-21T09:00+05:00"), obs(response_id="X2", timestamp="2026-11-20T10:00")])
    assert {(2, "timestamp"), (3, "timestamp")} <= errors(issues)


def test_verified_requires_verifier_and_manual_requires_evidence():
    _, issues = run([obs(verification_status="verified"), obs(response_id="X2", evidence_link="")])
    assert {(2, "verified_by"), (3, "evidence_link")} <= errors(issues)


def test_search_off_not_allowed():
    _, issues = run([obs(search_mode="search_off")])
    assert (2, "search_mode") in errors(issues)


def test_missing_column_is_header_error():
    rows = [(2, {k: v for k, v in obs().items() if k != "answer_text"})]
    valid, issues = C.validate_rows("observations", rows, prompts=PROMPTS, now=NOW)
    assert not valid and issues[0].row == 1 and "answer_text" in issues[0].field


def test_csv_multiline_answer_row_numbers():
    text = HEADER + "\n" + ",".join(f'"{v}"' for v in obs(answer_text="строка1\nстрока2\nстрока3 SVET.KZ рекомендую").values()) + "\n" \
        + ",".join(f'"{v}"' for v in obs(response_id="X2", provider="bad").values()) + "\n"
    rows, _ = C.read_rows("f.csv", text.encode())
    assert [r for r, _ in rows] == [2, 5]
    _, issues = C.validate_rows("observations", rows, prompts=PROMPTS, now=NOW)
    assert (5, "provider") in errors(issues)


def test_non_utf8_rejected():
    _, issues = C.read_rows("f.csv", "привет".encode("cp1251"))
    assert issues and issues[0].severity == "error"


def test_kpi_filter_only_verified_real():
    ok = {"data_type": "MANUAL_VERIFIED", "verification_status": "verified", "collector": "P3", "verified_by": "P2",
          "evidence_link": "https://chatgpt.com/share/x"}
    assert is_real_kpi_row(ok)
    assert not is_real_kpi_row({**ok, "verified_by": "P3"})            # self-verification (G06)
    assert not is_real_kpi_row({**ok, "evidence_link": ""})            # no evidence (G06)
    assert not is_real_kpi_row({**ok, "data_type": "MANUAL_REPORTED"})
    assert not is_real_kpi_row({"data_type": "MANUAL_VERIFIED", "verification_status": "pending"})
    assert not is_real_kpi_row({"data_type": "SYNTHETIC_DEMO", "verification_status": "verified"})


def test_sample_files_behave():
    v, iss = C.validate_file("observations", ROOT / "data/samples/SYNTHETIC_observations_sample.csv", prompts=PROMPTS, allow_synthetic=True, now=NOW)
    assert len(v) == 2 and not errors(iss)
    v, iss = C.validate_file("observations", ROOT / "data/samples/INVALID_example.csv", prompts=PROMPTS, now=NOW)
    assert not v and len(errors(iss)) >= 8


# ---- Sprint FINAL: Codex audit G06 / G07 ----
VERIFIED_OK = {"response_id": "V-1", "prompt_id": "R-C-ALA-01", "query": "Где купить люстру в Алматы?", "provider": "gemini",
               "model": "", "search_mode": "search_on", "timestamp": "2026-11-20T14:05+05:00", "run_no": "1", "language": "ru",
               "region_setting": "", "answer_text": "Ответ достаточно длинный для валидатора: SVET.KZ на Кабдолова 1/8.",
               "cited_urls": "", "data_type": "MANUAL_VERIFIED", "verification_status": "verified", "collector": "P3",
               "verified_by": "P2", "evidence_link": "https://chatgpt.com/share/abc", "notes": "текст и 2 URL сверены со ссылкой"}


@pytest.mark.parametrize("change,field", [
    ({"verified_by": "P3"}, "verified_by"),                                   # self-verification
    ({"verified_by": ""}, "verified_by"),
    ({"evidence_link": ""}, "evidence_link"),                                 # no evidence
    ({"evidence_link": "assets/evidence/V-1.png"}, "evidence_link"),          # file does not exist
    ({"evidence_link": "http://chatgpt.com/share/abc"}, "evidence_link"),     # not https
    ({"notes": ""}, "notes"),                                                 # what was checked is unknown
])
def test_g06_verified_requires_independent_check_with_evidence(change, field):
    v, iss = C.validate_rows("observations", [(2, {**VERIFIED_OK, **change})], prompts=PROMPTS, now=NOW)
    assert not v and any(i.field == field and i.severity == "error" for i in iss), (change, [i.as_dict() for i in iss])


def test_g06_valid_independent_verification_passes():
    v, iss = C.validate_rows("observations", [(2, VERIFIED_OK)], prompts=PROMPTS, now=NOW)
    assert len(v) == 1 and not errors(iss)


@pytest.mark.parametrize("value", [[1], ["https://svet.kz/", None], 5, {"u": "x"}])
def test_g07_cited_urls_wrong_types_are_row_errors_not_exceptions(value):
    rows, iss = C.read_rows("x.jsonl", json.dumps({"response_id": "R1", "cited_urls": value}).encode())
    assert not rows and len(iss) == 1 and iss[0].field == "cited_urls" and iss[0].severity == "error" and iss[0].row == 1


# ---- REAL_SEARCH bypass (Codex QA, final) ----
RS = {**VERIFIED_OK, "response_id": "RS-1", "data_type": "REAL_SEARCH"}


def test_real_search_rejected_on_manual_channel():
    for status in ("verified", "pending"):
        row = {**RS, "verification_status": status, "verified_by": "P2" if status == "verified" else ""}
        v, iss = C.validate_rows("observations", [(2, row)], prompts=PROMPTS, now=NOW)            # default channel = manual
        assert not v and any(i.field == "data_type" and i.severity == "error" for i in iss), status


def test_real_search_verified_on_api_channel_still_needs_evidence():
    v, iss = C.validate_rows("observations", [(2, {**RS, "evidence_link": ""})], prompts=PROMPTS, now=NOW, channel="api")
    assert not v and any(i.field == "evidence_link" and i.severity == "error" for i in iss)
    v, iss = C.validate_rows("observations", [(2, RS)], prompts=PROMPTS, now=NOW, channel="api")  # evidence + other verifier
    assert len(v) == 1


def test_real_search_kpi_filter_requires_evidence():
    row = {"data_type": "REAL_SEARCH", "verification_status": "verified", "collector": "P3", "verified_by": "P2", "evidence_link": ""}
    assert not is_real_kpi_row(row) and is_real_kpi_row({**row, "evidence_link": "https://chatgpt.com/share/x"})
