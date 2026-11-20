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
    assert len(valid) == 43 and not [i for i in issues if i.severity == "error"]


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
    assert is_real_kpi_row({"data_type": "MANUAL_VERIFIED", "verification_status": "verified"})
    assert not is_real_kpi_row({"data_type": "MANUAL_VERIFIED", "verification_status": "pending"})
    assert not is_real_kpi_row({"data_type": "SYNTHETIC_DEMO", "verification_status": "verified"})


def test_sample_files_behave():
    v, iss = C.validate_file("observations", ROOT / "data/samples/SYNTHETIC_observations_sample.csv", prompts=PROMPTS, allow_synthetic=True, now=NOW)
    assert len(v) == 2 and not errors(iss)
    v, iss = C.validate_file("observations", ROOT / "data/samples/INVALID_example.csv", prompts=PROMPTS, now=NOW)
    assert not v and len(errors(iss)) >= 8
