"""GEO Intelligence Lab — Streamlit dashboard.  Run:  streamlit run app.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from geolab import contract as C  # noqa: E402
from geolab import experiment as X  # noqa: E402
from geolab.analysis import url_key  # noqa: E402
from geolab.metrics import analyze_records, consistency, entity_metrics, fmt, general_metrics, share_of_voice, source_table  # noqa: E402
from geolab.registry import ROOT, load_registry  # noqa: E402
from geolab.store import UPLOAD_DIR, is_real_kpi_row, load_observations, load_prompts, prompts_index, safe_name, save_upload  # noqa: E402

st.set_page_config(page_title="GEO Intelligence Lab", layout="wide")
st.markdown("<style>.block-container{padding-top:1.5rem;max-width:1300px}</style>", unsafe_allow_html=True)

REG = load_registry()
PROMPTS = load_prompts()

STAGE_LABEL = {"brand_discovery": "A · Выбор бренда товара", "retailer_discovery": "B · Выбор магазина", "bridge": "C · Бренд → магазин"}
TYPE_HELP = {
    "REAL_SEARCH": "ответ AI-поиска, полученный через API",
    "MANUAL_VERIFIED": "ответ AI-поиска, собранный вручную из интерфейса, со скриншотом/ссылкой",
    "MANUAL_REPORTED": "ответ AI-поиска, скопированный участником без скриншота/ссылки (self_attested) — только предварительно",
    "CONTROLLED_EXPERIMENT": "результат локальной симуляции извлечения — не внешний AI",
    "SYNTHETIC_DEMO": "придуманные данные для проверки интерфейса — не измерение",
}
PAGES = ["Обзор", "Импорт наблюдений", "Наблюдения AI (evidence)", "Реальные KPI", "Источники",
         "Рекомендации", "Контролируемый эксперимент", "Данные и ошибки"]

# ---------- sidebar ----------
st.sidebar.title("GEO Intelligence Lab")
QP = st.query_params  # optional deep links for demo bookmarks / offline screenshots: ?page=4&client=svet_kz&city=astana


def _qp_index(key: str, options: list, default: int) -> int:
    v = QP.get(key)
    if v is None:
        return default
    if key == "page" and v.isdigit() and 1 <= int(v) <= len(options):
        return int(v) - 1
    return options.index(v) if v in options else default


page = st.sidebar.radio("Раздел", PAGES, index=_qp_index("page", PAGES, 0))
_clients = [e.id for e in REG.clients()]
client = st.sidebar.selectbox("Клиент", _clients, index=_qp_index("client", _clients, 0), format_func=lambda i: REG.entities[i].name)
stage = st.sidebar.selectbox("Этап пути", list(STAGE_LABEL), index=1, format_func=STAGE_LABEL.get)  # B: where real answers are
_cities = ["all", "almaty", "astana", "karaganda", "national"]
city = st.sidebar.selectbox("Город", _cities, index=_qp_index("city", _cities, 0),
                            format_func=lambda c: "Все" if c == "all" else REG.cities[c]["name"])
PROVIDER_LABEL = {"all": "Все", "chatgpt_search": "ChatGPT Search", "gemini": "Gemini", "perplexity": "Perplexity",
                  "google_ai_mode": "Google AI Mode", "google_ai_overview": "Google AI Overview"}
provider = st.sidebar.selectbox("AI-провайдер", ["all", *C.PROVIDER], format_func=lambda p: PROVIDER_LABEL.get(p, p))
demo = st.sidebar.toggle("Режим SYNTHETIC_DEMO", value=False,
                         help="Показывает только синтетические образцы из data/samples. Реальные данные в этом режиме скрыты.")
category = REG.entities[client].category
with st.sidebar.expander("Demo path · 3 минуты"):
    st.markdown("1. **Обзор** — где клиент назван / не назван (город Астана)\n"
                "2. **Наблюдения AI** — полный ответ ❌ и его ссылки\n"
                "3. **Рекомендации** — ФАКТ → ИСТОЧНИК → BEFORE/AFTER\n"
                "4. **Контролируемый эксперимент** — отдельная проверка механизма (BM25), не ответ AI\n"
                "5. **Реальные KPI** — A предварительно (N) и B verified (N/A)")

ALL_RECORDS, LOAD_ISSUES = load_observations(include_samples=demo)
if demo:
    st.sidebar.warning("SYNTHETIC_DEMO: показаны придуманные данные. Это не измерение.")
    RECORDS = [r for r in ALL_RECORDS if r["data_type"] == "SYNTHETIC_DEMO"]
else:
    RECORDS = [r for r in ALL_RECORDS if r["data_type"] in C.REAL_DATA_TYPES]
n_err = sum(1 for i in LOAD_ISSUES if i["severity"] == "error")
if n_err:
    st.sidebar.error(f"Ошибок в файлах данных: {n_err} → «Данные и ошибки»")


def in_scope(r: dict) -> bool:
    return (r["category"] == category and r["funnel_stage"] == stage and (city == "all" or r["city"] == city)
            and (provider == "all" or r["provider"] == provider))


def evidence_rows() -> list[dict]:
    """Observations to display: everything except rejected."""
    return [r for r in RECORDS if in_scope(r) and r["verification_status"] != "rejected"]


def kpi_rows() -> list[dict]:
    """Rows allowed into KPIs: verified real observations (or synthetic in demo mode)."""
    if demo:
        return [r for r in RECORDS if in_scope(r)]
    return [r for r in RECORDS if in_scope(r) and is_real_kpi_row(r)]


def no_data_box(extra: str = ""):
    st.info("Нет наблюдений для выбранного среза. Метрики показываются как N/A, не 0%. "
            "Загрузите ответы в разделе «Импорт наблюдений». " + extra)


def named(an, level: str) -> list[str]:
    return [REG.entities[k].name + (" ★" if v.recommended else "") for k, v in an.mentions.items() if v.level == level]


def metric_n(col, label, value, n, help_=None):
    col.metric(label, value, help=help_)
    col.caption(f"N = {n}")


# ---------- pages ----------
def render_kpis(items: list, sfx: str = "") -> None:
    """KPI block. sfx marks the PRELIMINARY block (labels differ so the two are never confused)."""
    if len(items) < 10:
        st.warning(f"Малая выборка: N = {len(items)}. Это описание наблюдений, а не статистический вывод.")
    g = general_metrics(items)
    if stage == "brand_discovery":
        assort = REG.assortment(client)
        hit = sum(1 for it in items if any(a.id in it.analysis.mentions for a in assort))
        c1, c2, c3 = st.columns(3)
        metric_n(c1, "Assortment Brand Coverage" + sfx, fmt(hit / len(items)), len(items),
                 "доля ответов, где названа ≥1 марка из подтверждённого ассортимента клиента")
        metric_n(c2, "Citation coverage" + sfx, fmt(g["citation_coverage"]), len(items))
        metric_n(c3, "Уникальных доменов" + sfx, g["unique_cited_domains"], g["answers_with_citations"])
        sov = share_of_voice(items, REG, "manufacturer", category)
        color = "in_client_assortment"
    else:
        m = entity_metrics(items, client)
        c1, c2, c3, c4 = st.columns(4)
        metric_n(c1, "Mention rate" + sfx, fmt(m["mention_rate"]), m["answers"])
        metric_n(c2, "Recommendation rate" + sfx, fmt(m["recommendation_rate"]), m["answers"], "эвристика")
        metric_n(c3, "Top-3 rate" + sfx, fmt(m["top3_rate"]), m["ranked_answers"], "только ответы с явным нумерованным списком")
        metric_n(c4, "Citation rate" + sfx, fmt(m["citation_rate"]), m["answers_with_citations"], "среди ответов с цитатами")
        sov = share_of_voice(items, REG, "retailer", category)
        color = "is_client"
    if not sov.empty:
        sov["name"] = [n + (" · кандидат" if stt == "candidate_unverified" else "") for n, stt in zip(sov.name, sov.registry_status)]
        st.subheader("AI Share of Voice (по числу ответов с упоминанием)")
        st.caption("«кандидат» — магазин назван AI, но в реестре не проверен независимо.")
        fig = px.bar(sov, x="answers_mentioning", y="name", orientation="h", color=color,
                     color_discrete_map={True: "#2f6f4f", False: "#b8bcc2"}, labels={"answers_mentioning": "ответов с упоминанием", "name": ""})
        fig.update_layout(height=80 + 28 * len(sov), showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch", key=f"sov{sfx}")
    if stage != "brand_discovery":
        cons = consistency(items, client)
        if not cons.empty and (cons.runs >= 2).any():
            st.subheader("Result Consistency (повторные прогоны одного вопроса)")
            st.caption("Доля прогонов, где клиент назван, по вопросу и AI. Строки с 1 прогоном не показаны.")
            st.dataframe(cons[cons.runs >= 2], hide_index=True, width="stretch", key=f"cons{sfx}")
    export = pd.DataFrame([{**{k: v for k, v in it.record.items() if not k.startswith("_")},
                            "cited_urls": " | ".join(it.record["cited_urls"]),
                            "manufacturers": ", ".join(named(it.analysis, "manufacturer")),
                            "retailers": ", ".join(named(it.analysis, "retailer")),
                            "ranked": " > ".join(it.analysis.ranked_entities)} for it in items])
    st.download_button("Экспорт наблюдений + распознавания (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"observations_{client}_{stage}_{city}{'_preliminary' if sfx else ''}.csv", mime="text/csv", key=f"exp{sfx}")


if page == "Обзор":
    st.header("Как AI-поиск рекомендует бренды товаров и магазины")
    real = [r for r in ALL_RECORDS if r["data_type"] in C.REAL_DATA_TYPES]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Запросов в датасете", len(PROMPTS))
    c2.metric("Реальных наблюдений", len(real))
    c3.metric("из них verified", sum(1 for r in real if r["verification_status"] == "verified"))
    c4.metric("AI-провайдеров", len({r["provider"] for r in real}) or "N/A")
    if real and not demo:
        st.subheader(f"Реальные ответы AI: где {REG.entities[client].name}?")
        items_all = analyze_records([r for r in real if r["category"] == category and r["verification_status"] != "rejected"], REG)
        mx = []
        for it in items_all:
            r, a = it.record, it.analysis
            m = a.mentions.get(client)
            mx.append({"этап": STAGE_LABEL[r["funnel_stage"]][:1], "город": REG.cities[r["city"]]["name"], "AI": r["provider"],
                       "вопрос": r["query"], "клиент назван": "✅ да" if m else "❌ нет",
                       "место в рейтинге": str(m.rank) if m and m.rank else "—",
                       "сайт клиента процитирован": "✅" if any(c.owner_entity == client for c in a.citations) else "—",
                       "первые в ответе": ", ".join(REG.entities[e].name for e in (a.ranked_entities or [e for _, e in sorted(
                           (mm.first_pos, e) for e, mm in a.mentions.items() if mm.level == "retailer")])[:3]),
                       "доказательство": r["verification_status"]})
        if mx:
            st.dataframe(pd.DataFrame(mx), hide_index=True, width="stretch")
            st.caption(f"N = {len(mx)} · self_attested = ответ предоставил участник P3 без скриншота (предварительно, не независимо проверено). "
                       "Каждый вопрос задан 1 раз — это описание конкретных ответов, а не доля рынка.")
    st.markdown(
        "- **Слой A — выбор бренда товара** («какая краска лучше для детской?»): AI рекомендует производителей.\n"
        "- **Слой B — выбор магазина** («где купить люстру в Астане?»): AI рекомендует продавцов.\n"
        "- **Мост C**: AI назвал марку — ведёт ли следующий шаг к нашему магазину?"
    )
    cov = PROMPTS.groupby(["category", "city", "funnel_stage"]).size().reset_index(name="prompts")
    got = pd.DataFrame([{"category": r["category"], "city": r["city"], "funnel_stage": r["funnel_stage"]} for r in real])
    cov["real_observations"] = cov.apply(lambda x: 0 if got.empty else int(((got.category == x.category) & (got.city == x.city) & (got.funnel_stage == x.funnel_stage)).sum()), axis=1)
    st.subheader("Покрытие сегментов")
    st.dataframe(cov, hide_index=True, width="stretch")
    st.subheader("Подтверждённое присутствие клиентов по городам")
    rows = [{"магазин": e.name, "город": REG.cities[c]["name"], "статус": v["status"], "доказательство": v["evidence"]}
            for e in REG.clients() for c, v in e.cities.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

elif page == "Импорт наблюдений":
    st.header("Импорт ответов AI-поиска")
    st.markdown("Формат: `data/templates/observations_template.csv` (описание — `docs/15_DATA_CONTRACT.md`). "
                "Принимаются CSV (UTF-8) и JSONL. Файл сохраняется **без изменений** в `data/raw/manual/`; "
                "строки с ошибками не попадают в данные, ничего не исправляется автоматически.")
    up = st.file_uploader("Файл наблюдений", type=["csv", "jsonl"])
    if up is not None:
        content = up.getvalue()
        try:
            target_name = safe_name(up.name)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        replacing = (UPLOAD_DIR / target_name).exists()
        rows, issues = C.read_rows(up.name, content)
        # IDs from the file being replaced do not count as duplicates
        existing = {r["response_id"] for r in ALL_RECORDS if r["_file"] != target_name}
        valid, more = C.validate_rows("observations", rows, prompts=prompts_index(), existing_keys=existing)
        issues += more
        errs = [i for i in issues if i.severity == "error"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Строк в файле", len(rows))
        c2.metric("Валидных", len(valid))
        c3.metric("Ошибок", len(errs))
        if issues:
            st.dataframe(pd.DataFrame([i.as_dict() for i in issues]), hide_index=True, width="stretch")
        if valid:
            st.subheader("Предпросмотр распознавания")
            prev = []
            for it in analyze_records(valid, REG):
                prev.append({"response_id": it.record["response_id"], "query": it.record["query"], "provider": it.record["provider"],
                             "бренды (производители)": ", ".join(named(it.analysis, "manufacturer")) or "—",
                             "магазины": ", ".join(named(it.analysis, "retailer")) or "—",
                             "цитат": len(it.analysis.citations), "data_type": it.record["data_type"]})
            st.dataframe(pd.DataFrame(prev), hide_index=True, width="stretch")
            st.caption("★ — эвристически распознано как рекомендация (пункт списка или слова-рекомендации, без отрицания).")
        if errs:
            st.error("Файл не сохранён: исправьте ошибки в исходной таблице и загрузите снова.")
        elif valid and replacing:
            st.warning(f"Файл {target_name} уже есть. Новая версия заменит его целиком (старая останется в истории Git).")
            if st.button("Заменить предыдущую версию", type="primary"):
                path = save_upload(up.name, content, replace=True)
                st.success(f"Заменено: {path.relative_to(ROOT)}. Обновите страницу.")
        elif valid and st.button("Сохранить в data/raw/manual/", type="primary"):
            path = save_upload(up.name, content)
            st.success(f"Сохранено: {path.relative_to(ROOT)}. Обновите страницу.")

elif page == "Наблюдения AI (evidence)":
    st.header("Наблюдения AI-поиска")
    st.caption(f"{STAGE_LABEL[stage]} · {REG.entities[client].name} · "
               + ("SYNTHETIC_DEMO" if demo else "реальные данные (pending, self_attested, verified; rejected скрыты)"))
    recs = evidence_rows()
    if not recs:
        no_data_box()
    for it in analyze_records(recs, REG):
        r = it.record
        badge = f"`{r['data_type']}` · `{r['verification_status']}`"
        cm = it.analysis.mentions.get(client)
        mark = (f"✅ {REG.entities[client].name}" + (f" #{cm.rank}" if cm and cm.rank else "")) if cm else f"❌ {REG.entities[client].name} нет"
        with st.expander(f"{mark} · {r['provider']} · {REG.cities[r['city']]['name']} · {r['query']} · {r['timestamp'][:16]}"):
            st.markdown(f"{badge} · prompt `{r['prompt_id']}` · собрал `{r['collector']}`"
                        + (f" · проверил `{r['verified_by']}`" if r["verified_by"] else "")
                        + (f" · модель `{r['model']}`" if r["model"] else ""))
            if r["evidence_link"]:
                st.markdown(f"Доказательство: `{r['evidence_link']}`")
            a, b = st.columns(2)
            a.markdown("**Бренды товаров (LEVEL 1):** " + (", ".join(named(it.analysis, "manufacturer")) or "не названы"))
            b.markdown("**Магазины (LEVEL 2):** " + (", ".join(named(it.analysis, "retailer")) or "не названы"))
            if it.analysis.has_ranking:
                st.markdown("**Явный рейтинг:** " + " → ".join(REG.entities[e].name for e in it.analysis.ranked_entities))
            st.markdown("**Полный ответ:**")
            st.text(r["answer_text"])
            if it.analysis.citations:
                st.dataframe(pd.DataFrame([{"url": c.url, "домен": c.domain, "тип": c.source_type,
                                            "владелец": REG.entities[c.owner_entity].name if c.owner_entity else ""}
                                           for c in it.analysis.citations]),
                             hide_index=True, column_config={"url": st.column_config.LinkColumn("url")})
            else:
                st.markdown("_Цитат нет — источник ответа неизвестен (unknown origin)._")

elif page == "Реальные KPI":
    st.header(("SYNTHETIC DEMO KPI — не измерение" if demo else "REAL-WORLD METRICS") + f" · {STAGE_LABEL[stage]}")
    st.caption("Результаты эксперимента сюда не входят. A — предварительно (все реальные ответы, кроме rejected); "
               "B — только независимо проверенные (verified).")
    recs = kpi_rows()
    if not demo:
        prelim = evidence_rows()
        by = {s: sum(1 for r in prelim if r["verification_status"] == s) for s in ("self_attested", "pending", "verified")}
        st.subheader("A. Предварительные показатели — ручные ответы, НЕ проверены независимо")
        if prelim:
            st.warning(f"N = {len(prelim)}: self_attested {by['self_attested']}, pending {by['pending']}, verified {by['verified']}. "
                       "self_attested — ответ предоставил и подтвердил участник, скриншота / ссылки на диалог нет. "
                       "Это описание конкретных ответов, не статистический вывод.")
            render_kpis(analyze_records(prelim, REG), sfx=" · A предварительно")
        else:
            st.info("Нет реальных ответов в этом срезе (клиент · этап · город · провайдер).")
        st.subheader("B. Independently verified KPI")
    pending = len([r for r in evidence_rows() if r["verification_status"] == "pending"]) if not demo else 0
    if pending:
        st.warning(f"{pending} наблюдений в статусе pending не учтены. Их должен проверить второй участник.")
    att = len([r for r in evidence_rows() if r["verification_status"] == "self_attested"]) if not demo else 0
    if att:
        st.info(f"{att} наблюдений self_attested (ручной ответ участника без скриншота) — в verified KPI не входят.")
    if not recs:
        no_data_box()
    else:
        render_kpis(analyze_records(recs, REG))

elif page == "Источники":
    st.header("Откуда AI берёт ответы")
    st.caption("Только явные цитаты в ответах. Наличие источника ≠ цитирование ≠ доказанное влияние.")
    recs = evidence_rows()
    if not recs:
        no_data_box()
    else:
        tbl = source_table(analyze_records(recs, REG), REG)
        cited = tbl[tbl.source_type != "no_citation"]
        n_unique = len({url_key(u) for u in cited.cited_url})
        st.caption(f"N ответов = {len(recs)} · появлений ссылок (без повторов внутри ответа) = {len(cited)} · "
                   f"уникальных URL = {n_unique} · ответов без ссылок = {int((tbl.source_type == 'no_citation').sum())}")
        if not cited.empty:
            by_type = cited.groupby("source_type").size().reset_index(name="citations").sort_values("citations")
            st.plotly_chart(px.bar(by_type, x="citations", y="source_type", orientation="h", labels={"source_type": ""}), width="stretch")
            top = cited.groupby(["domain", "source_type"]).size().reset_index(name="citations").sort_values("citations", ascending=False)
            st.subheader("Домены")
            st.dataframe(top, hide_index=True, width="stretch")
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={"cited_url": st.column_config.LinkColumn("cited_url")})
        st.download_button("Экспорт таблицы источников (CSV)", tbl.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"sources_{client}_{stage}_{city}.csv", mime="text/csv")

elif page == "Рекомендации":
    st.header("GEO-правки — предложения (production сайтов не изменён)")
    st.caption("ФАКТ — проверено на живой странице клиента (data/research/geo_recheck_2026-11-20/checks.json). "
               "Наблюдение AI — отдельный уровень доказательности (self_attested). ГИПОТЕЗА — не обещание результата.")
    recs = json.loads((ROOT / "data" / "processed" / "recommendations.json").read_text(encoding="utf-8"))
    recs = [r for r in recs if client in r["affected_entity"]]
    core = sorted((r for r in recs if r.get("tier") == "core"), key=lambda r: (r["priority"], r["issue_id"]))
    secondary = sorted((r for r in recs if r.get("tier") != "core"), key=lambda r: (r["priority"], r["issue_id"]))
    if not recs:
        st.info("Для этого клиента предложений нет.")
    for i, r in enumerate(core + secondary):
        tag = "основная" if r.get("tier") == "core" else "дополнительная"
        with st.expander(f"{r['priority']} · {r['issue_id']} · {tag} · {r.get('status', '')} — {r.get('geo_issue', r['finding'])[:80]}…",
                         expanded=(i == 0)):
            st.markdown(f"**Страница:** {r.get('source_url', '—')}  \n**Тип:** {r['implementation_type']} · **стоимость:** {r.get('cost', '—')} · "
                        f"**уверенность:** {r['confidence']}")
            if r.get("facts"):
                st.markdown("**ФАКТЫ и ИСТОЧНИКИ**")
                st.dataframe(pd.DataFrame(r["facts"]).rename(columns={"fact": "факт", "source_url": "источник", "evidence": "доказательство"}),
                             hide_index=True, width="stretch")
            st.markdown(f"**GEO-ПРОБЛЕМА:** {r.get('geo_issue', r['finding'])}")
            a, b = st.columns(2)
            a.markdown("**BEFORE** (как сейчас)")
            a.code(r["before"], language="html")
            b.markdown("**AFTER** (предложение)")
            b.code(r["after"], language="html")
            st.markdown(f"**ПРЕДЛОЖЕНИЕ:** {r.get('proposal', r.get('proposed_change', ''))}\n\n"
                        f"**ГИПОТЕЗА:** {r.get('hypothesis', r.get('expected_mechanism', ''))}\n\n"
                        f"**ТЕСТ после публикации:** {r.get('test', r.get('experiment_plan', ''))}\n\n"
                        f"**ОГРАНИЧЕНИЯ:** {r.get('limitations', '—')}")
            st.markdown(f"**НАБЛЮДЕНИЕ в ответах AI** (не доказательство причины): {r.get('observation') or r.get('ai_observation', '—')}")

elif page == "Контролируемый эксперимент":
    st.header("CONTROLLED EXPERIMENT RESULTS")

    def m3(v):  # MRR shown with 3 decimals (0.875 must not read as 0.88)
        return "N/A" if v is None else f"{v:.3f}"
    st.warning("Локальная BM25-симуляция стадии извлечения на фиксированном корпусе. Это не ответ ChatGPT/Gemini/Perplexity "
               "и не доказательство изменения их ранжирования. С реальными KPI не смешивается.")
    # Codex experiments (data/experiments) + Claude-built experiments run with the same unchanged engine
    # (data/research/exp*/EXP-*.json, corpus next to the config, result saved as <id>_result.json).
    EXPS = {p.stem: (None, X.EXP_DIR / "results" / f"{p.stem}_result.json") for p in sorted(X.EXP_DIR.glob("EXP-*.json"))
            if not p.stem.endswith("_result")}
    for cfgp in sorted(p for p in (ROOT / "data" / "research").glob("exp*/EXP-*.json") if not p.stem.endswith("_result")):
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        EXPS[cfg["experiment_id"]] = (cfgp, cfgp.parent / f"{cfgp.stem}_result.json")
    exps = list(EXPS)
    if not exps:
        st.info("Эксперименты не описаны (data/experiments/EXP-*.json).")
    else:
        exp_id = st.selectbox("Эксперимент", exps, index=_qp_index("exp", exps, len(exps) - 1))
        cfg_path, saved = EXPS[exp_id]
        exp = X.load_experiment(exp_id) if cfg_path is None else json.loads(cfg_path.read_text(encoding="utf-8"))
        own_dir = None if cfg_path is None else cfg_path.parent
        try:
            corpus_dir = X.resolve_corpus(exp, own_dir)
            corpus = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((corpus_dir / "baseline").glob("*.json"))]
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            st.error(f"Корпус эксперимента недоступен: {exc}")
            st.stop()
        owners = sorted({d["entity_id"] for d in corpus})
        roles = [q["role"] for q in exp["queries"]]
        n_target, n_neg = roles.count("target"), roles.count("negative_control")
        st.markdown(f"**Гипотеза:** {exp.get('hypothesis', '')}\n\n"
                    f"**Изменённые документы (treatment):** {', '.join(exp['changed_doc_ids'])} · "
                    f"**корпус:** `{corpus_dir.relative_to(ROOT)}`")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Документов в корпусе", len(corpus))
        c2.metric("Владельцев документов", len(owners), help=", ".join(owners))
        c3.metric("Целевых запросов", n_target)
        c4.metric("Negative controls", n_neg)
        n_client = sum(1 for d in corpus if d["entity_id"] in {e.id for e in REG.clients()})
        st.caption(f"Документов клиентов: {n_client} из {len(corpus)} — корпус смещён к клиентам, это не модель рынка. "
                   "Эксперимент проверяет механизм извлечения на сохранённых страницах; он не является результатом конкретного ответа Gemini/ChatGPT.")
        if st.button("Перезапустить baseline и treatment", type="primary"):
            try:
                with st.spinner("Индексация корпуса и прогон запросов…"):
                    st.session_state["res"] = X.run_experiment(exp, corpus_dir=own_dir)
            except (FileNotFoundError, ValueError) as exc:
                st.error(f"Эксперимент не готов: {exc}")
        res = st.session_state.get("res")
        if (res is None or res["experiment_id"] != exp_id) and saved.exists():
            res = json.loads(saved.read_text(encoding="utf-8"))
            st.caption(f"Показан сохранённый результат: {saved.relative_to(ROOT)}")
        if res and res["experiment_id"] == exp_id:
            s = res["summary"]
            st.subheader("Целевые запросы: baseline → treatment · уровень МАГАЗИНА (entity-level)")
            c1, c2, c3 = st.columns(3)
            bm, tm = s["target"]["baseline"].get("mrr"), s["target"]["treatment"].get("mrr")
            metric_n(c1, "MRR владельца", f"{m3(bm)} → {m3(tm)}", s["target"]["baseline"]["queries"],
                     "Mean Reciprocal Rank: среднее 1/позиция первого документа клиента в top-k (0, если нет). Это НЕ средняя позиция.")
            bt, tt = s["target"]["baseline"]["top3_rate"], s["target"]["treatment"]["top3_rate"]
            metric_n(c2, "Hit@3", f"{fmt(bt)} → {fmt(tt)}", s["target"]["baseline"]["queries"],
                     "доля целевых запросов, где клиент в первых 3 владельцах (поле top3_rate)")
            bc, tc = s["target"]["baseline"]["citation_rate"], s["target"]["treatment"]["citation_rate"]
            metric_n(c3, "Citation Rate", f"{fmt(bc)} → {fmt(tc)}", s["target"]["baseline"]["queries"],
                     "доля целевых запросов, где документ клиента попал в top-k цитат. Не путать с Hit@3.")
            if "changed_page_mrr" in s["target"]["baseline"]:
                st.markdown(f"**Уровень ДОКУМЕНТА (document-level):** MRR изменённой страницы "
                            f"{m3(s['target']['baseline']['changed_page_mrr'])} → {m3(s['target']['treatment']['changed_page_mrr'])}")
            st.subheader("Negative controls (рост = ухудшение релевантности)")
            n = s["negative_control"]
            c1, c2, c3 = st.columns(3)
            metric_n(c1, "MRR · controls", f"{m3(n['baseline'].get('mrr'))} → {m3(n['treatment'].get('mrr'))}", n["baseline"]["queries"])
            metric_n(c2, "Hit@3 · controls", f"{fmt(n['baseline']['top3_rate'])} → {fmt(n['treatment']['top3_rate'])}", n["baseline"]["queries"])
            metric_n(c3, "Citation Rate · controls", f"{fmt(n['baseline']['citation_rate'])} → {fmt(n['treatment']['citation_rate'])}", n["baseline"]["queries"])
            df = pd.DataFrame(res["per_query"])
            for col in ("baseline_entities", "treatment_entities"):
                df[col] = df[col].map(lambda v: ", ".join(v))
            st.dataframe(df, hide_index=True, width="stretch")
            ev = res.get("evidence", {})
            lim = [f"Корпус: {len(corpus)} документов, {len(owners)} владельцев — малая exploratory-выборка без qrels и holdout; статистического обобщения нет.",
                   f"Целевых запросов {n_target}, negative controls {n_neg}: одна смена позиции меняет MRR/Hit@3 на десятки п.п.",
                   "Лексический BM25 ≠ семантический поиск, query fan-out и знания модели о брендах в реальных AI-поисковиках.",
                   "Treatment — неопубликованное предложение (production не изменён); эффект на внешние AI не измерен."]
            if ev:
                lim.append(f"Entity ranks negative controls неизменны: {ev.get('negative_control_entity_ranks_unchanged')}. Scope: {ev.get('scope', '')}.")
            else:
                lim.append("Сохранённый результат создан до добавления evidence-блока (hash/provenance) — перезапустите для полной трассировки.")
            st.markdown("**Ограничения доказательств**\n\n" + "\n".join(f"- {x}" for x in lim))
            note = (own_dir / "INTERPRETATION.md") if own_dir else None
            if note and note.exists():
                st.info(note.read_text(encoding="utf-8"))

elif page == "Данные и ошибки":
    st.header("Происхождение данных и ошибки импорта")
    for s, h in TYPE_HELP.items():
        st.markdown(f"- **{s}** — {h}: {sum(1 for r in ALL_RECORDS if r['data_type'] == s)} строк")
    if LOAD_ISSUES:
        st.dataframe(pd.DataFrame(LOAD_ISSUES), hide_index=True, width="stretch")
    else:
        st.success("Ошибок в файлах данных нет.")
    st.subheader("Датасет запросов")
    st.dataframe(PROMPTS, hide_index=True, width="stretch")
