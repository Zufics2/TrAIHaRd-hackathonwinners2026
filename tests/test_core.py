import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geolab.analysis import analyze_answer, classify_source, find_entity_spans, normalize_domain  # noqa: E402
from geolab.experiment import run_experiment, tokenize  # noqa: E402
from geolab.metrics import entity_metrics, fmt, rate, share_of_voice, AnalyzedResponse  # noqa: E402
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


def test_numbered_list_with_detail_lines_keeps_intro_and_ranking():
    """Real ChatGPT layout (forme, 2026-11-20): intro sentence, heading, image caption, then items
    with address lines and captions between them. Text below is invented, the layout is real."""
    text = ("По отзывам я выделил несколько вариантов.\nМагазины люстр\nФото салона\n"
            "1. SVET.KZ\nМой первый выбор\n- Адрес: ул. Примерная, 1.\nКартинка - подпись\n"
            "2. HAYDI\n- Адрес: ул. Другая, 2.\n"
            "3. TEKLED\nТелефон: +7 700 000 0000.")
    a = analyze_answer(text, REG)
    assert a.has_ranking and a.ranked_entities == ["svet_kz", "haydi", "tekled"]
    assert all(a.mentions[e].recommended for e in ("svet_kz", "haydi", "tekled"))


def test_neutral_colon_intro_wins_over_earlier_recommendation():
    text = "Я бы рекомендовал начать с салонов.\nУпомянутые в отзывах названия:\n- HAYDI\n- TEKLED"
    a = analyze_answer(text, REG)
    assert not a.mentions["haydi"].recommended and not a.mentions["tekled"].recommended


def test_case_sensitive_competitor_common_words():
    for eid, common in (("raduga", "над городом радуга"), ("kokos", "кокос и бананы"), ("m_light", "m light bulb")):
        assert find_entity_spans(common, REG.entities[eid]) == [], eid
    assert len(find_entity_spans("Радуга — фирменные магазины", REG.entities["raduga"])) == 1


def test_competitor_domain_classified_as_retailer_site():
    a = analyze_answer("См. сайт", REG, ["https://haydi.kz/?utm_source=chatgpt.com"])
    assert a.citations[0].owner_entity == "haydi"


def test_numeric_store_name_not_matched_in_duration_phrases():
    e = REG.entities["dvenadtsat_mesyatsev"]
    for t in ("Гарантия 12 месяцев на все люстры.", "Срок хранения 12 месяцев.", "в течение 12 месяцев"):
        assert find_entity_spans(t, e) == [], t
    assert len(find_entity_spans("2. 12 месяцев\nГипермаркет «12 Месяцев» — пр-т Райымбека", e)) == 2


def test_sov_exposes_candidate_status():
    a = analyze_answer("Варианты:\n1. HAYDI\n2. SVET.KZ", REG)
    df = share_of_voice([AnalyzedResponse({"provider": "x"}, a)], REG, "retailer", "chandelier")
    st = dict(zip(df.entity_id, df.registry_status))
    assert st["haydi"] == "candidate_unverified" and st["svet_kz"] != "candidate_unverified"


def test_client_name_vs_generic_phrase():
    """BR-C-PA-001: «специализированные центры красок» / heading «Центр красок» are generic, not the client."""
    e = REG.entities["centr_krasok"]
    for generic in ("рекомендовал специализированные центры красок.", "Где купить Dulux\nЦентр красок\n1. Мастерская"):
        assert find_entity_spans(generic, e) == [], generic
    for real in ("2. Центр красок №1", "- Центр красок #1 — ул. Кабдолова", "купить в Центре Красок", "О магазине - Центр Красок #1"):
        assert len(find_entity_spans(real, e)) == 1, real


# ---- Sprint FINAL: Codex audit G08 / G09 / G10 ----
def test_g08_unknown_store_does_not_compress_ranks():
    a = analyze_answer("Варианты:\n1. НЕИЗВЕСТНЫЙ_МАГАЗИН\n2. SVET.KZ\n3. TEKLED", REG)
    assert a.has_ranking and a.mentions["svet_kz"].rank == 2 and a.mentions["tekled"].rank == 3


def test_g09_instructions_are_not_heads_or_recommendations():
    a = analyze_answer("1. Проверьте Dulux\n2. Проверьте Maytoni", REG)
    assert not a.has_ranking and not a.mentions["dulux"].recommended and not a.mentions["maytoni"].recommended


def test_g09_neutral_catalogue_is_not_a_ranking():
    a = analyze_answer("Каталог производителей:\n1. Dulux\n2. Maytoni", REG)
    assert not a.has_ranking and a.mentions["dulux"].rank is None


@pytest.mark.parametrize("text,expected", [
    ("Не рекомендую Dulux, лучше Maytoni.", {"dulux": False, "maytoni": True}),
    ("Не рекомендую Dulux, есть Maytoni.", {"dulux": False, "maytoni": False}),   # the only cue is negated
    ("Я бы рекомендовал Maytoni, но не Eglo.", {"maytoni": True, "eglo": False}),
])
def test_g09_negation_is_clause_scoped(text, expected):
    a = analyze_answer(text, REG)
    assert {e: a.mentions[e].recommended for e in expected} == expected


def test_g10_link_only_is_citation_not_mention():
    a = analyze_answer("Источники: https://svet.kz/", REG)
    assert "svet_kz" not in a.mentions and a.citations and a.citations[0].owner_entity == "svet_kz"
    a = analyze_answer("Хороший выбор — SVET.KZ.\nsvet.kz+1", REG)          # chip does not add a mention
    assert a.mentions["svet_kz"].count == 1


def test_real_answers_client_results_stable_after_g08_g10():
    """Client-level results on the 10 imported answers did not change with the G08–G10 fixes."""
    from geolab import store
    recs, _ = store.load_observations()
    got = {}
    for r in recs:
        a = analyze_answer(r["answer_text"], REG, r["cited_urls"])
        cl = "centr_krasok" if r["category"] == "paint" else "svet_kz"
        m = a.mentions.get(cl)
        got[r["response_id"]] = (bool(m), bool(m and m.recommended), m.rank if m else None)
    assert got == {"OBS-001": (True, True, None), "OBS-002": (False, False, None), "OBS-003": (False, False, None),
                   "OBS-004": (True, True, 1), "OBS-005": (False, False, None), "OBS-006": (False, False, None),
                   "BR-G-PA-001": (True, True, 2), "BR-C-PA-001": (True, True, 2), "BR-G-CH-001": (True, True, 1),
                   "BR-C-CH-001": (True, True, 1)}


# ---- Security: CMS session tokens must not be stored in tracked snapshots ----
def test_redact_session_tokens_only_values():
    from geolab.corpus import redact_session_tokens
    html = ('<input type="hidden" name="sessid" id="sessid" value="0123456789abcdef0123456789abcdef" />'
            '{"bitrix_sessid":"0123456789abcdef0123456789abcdef"}'
            "{'sessid':'abcdef0123456789abcdef0123456789'}  &sessid=' + encodeURIComponent(BX.bitrix_sessid())")
    out, n = redact_session_tokens(html)
    assert n == 3 and "0123456789abcdef" not in out and "encodeURIComponent(BX.bitrix_sessid())" in out


def test_no_session_token_values_in_tracked_snapshots():
    import re
    root = Path(__file__).resolve().parents[1] / "data"
    rx = re.compile(r"""(?:bitrix_)?sessid["']?\s*[:=]\s*["'][A-Za-z0-9]{16,}|name=["']sessid["'][^>]*?value=["'][A-Za-z0-9]{16,}""", re.I)
    leaks = [str(p) for p in root.rglob("*.htm*") if "private" not in p.parts and rx.search(p.read_bytes().decode("utf-8", "replace"))]
    assert not leaks, leaks
