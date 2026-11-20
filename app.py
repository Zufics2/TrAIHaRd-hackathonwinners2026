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
from geolab.metrics import analyze_records, entity_metrics, fmt, general_metrics, share_of_voice, source_table  # noqa: E402
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
    "CONTROLLED_EXPERIMENT": "результат локальной симуляции извлечения — не внешний AI",
    "SYNTHETIC_DEMO": "придуманные данные для проверки интерфейса — не измерение",
}
PAGES = ["Обзор", "Импорт наблюдений", "Наблюдения AI (evidence)", "Реальные KPI", "Источники",
         "Рекомендации", "Контролируемый эксперимент", "Данные и ошибки"]

# ---------- sidebar ----------
st.sidebar.title("GEO Intelligence Lab")
page = st.sidebar.radio("Раздел", PAGES)
client = st.sidebar.selectbox("Клиент", [e.id for e in REG.clients()], format_func=lambda i: REG.entities[i].name)
stage = st.sidebar.selectbox("Этап пути", list(STAGE_LABEL), format_func=STAGE_LABEL.get)
city = st.sidebar.selectbox("Город", ["all", "almaty", "astana", "karaganda", "national"],
                            format_func=lambda c: "Все" if c == "all" else REG.cities[c]["name"])
demo = st.sidebar.toggle("Режим SYNTHETIC_DEMO", value=False,
                         help="Показывает только синтетические образцы из data/samples. Реальные данные в этом режиме скрыты.")
category = REG.entities[client].category

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
    return r["category"] == category and r["funnel_stage"] == stage and (city == "all" or r["city"] == city)


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
if page == "Обзор":
    st.header("Как AI-поиск рекомендует бренды товаров и магазины")
    real = [r for r in ALL_RECORDS if r["data_type"] in C.REAL_DATA_TYPES]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Запросов в датасете", len(PROMPTS))
    c2.metric("Реальных наблюдений", len(real))
    c3.metric("из них verified", sum(1 for r in real if r["verification_status"] == "verified"))
    c4.metric("AI-провайдеров", len({r["provider"] for r in real}) or "N/A")
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
               + ("SYNTHETIC_DEMO" if demo else "реальные данные (pending и verified; rejected скрыты)"))
    recs = evidence_rows()
    if not recs:
        no_data_box()
    for it in analyze_records(recs, REG):
        r = it.record
        badge = f"`{r['data_type']}` · `{r['verification_status']}`"
        with st.expander(f"{r['provider']} · {r['query']} · {r['timestamp']} · run {r['run_no']}"):
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
    st.caption("Только verified-наблюдения REAL_SEARCH / MANUAL_VERIFIED. Результаты эксперимента сюда не входят.")
    recs = kpi_rows()
    pending = len([r for r in evidence_rows() if r["verification_status"] == "pending"]) if not demo else 0
    if pending:
        st.warning(f"{pending} наблюдений в статусе pending не учтены. Их должен проверить второй участник.")
    if not recs:
        no_data_box()
    else:
        items = analyze_records(recs, REG)
        if len(items) < 10:
            st.warning(f"Малая выборка: N = {len(items)}. Это описание наблюдений, а не статистический вывод.")
        g = general_metrics(items)
        if stage == "brand_discovery":
            assort = REG.assortment(client)
            hit = sum(1 for it in items if any(a.id in it.analysis.mentions for a in assort))
            c1, c2, c3 = st.columns(3)
            metric_n(c1, "Assortment Brand Coverage", fmt(hit / len(items)), len(items),
                     "доля ответов, где названа ≥1 марка из подтверждённого ассортимента клиента")
            metric_n(c2, "Citation coverage", fmt(g["citation_coverage"]), len(items))
            metric_n(c3, "Уникальных доменов", g["unique_cited_domains"], g["answers_with_citations"])
            sov = share_of_voice(items, REG, "manufacturer", category)
            color = "in_client_assortment"
        else:
            m = entity_metrics(items, client)
            c1, c2, c3, c4 = st.columns(4)
            metric_n(c1, "Mention rate", fmt(m["mention_rate"]), m["answers"])
            metric_n(c2, "Recommendation rate", fmt(m["recommendation_rate"]), m["answers"], "эвристика")
            metric_n(c3, "Top-3 rate", fmt(m["top3_rate"]), m["ranked_answers"], "только ответы с явным нумерованным списком")
            metric_n(c4, "Citation rate", fmt(m["citation_rate"]), m["answers_with_citations"], "среди ответов с цитатами")
            sov = share_of_voice(items, REG, "retailer", category)
            color = "is_client"
        if not sov.empty:
            st.subheader("AI Share of Voice (по числу ответов с упоминанием)")
            fig = px.bar(sov, x="answers_mentioning", y="name", orientation="h", color=color,
                         color_discrete_map={True: "#2f6f4f", False: "#b8bcc2"}, labels={"answers_mentioning": "ответов с упоминанием", "name": ""})
            fig.update_layout(height=80 + 28 * len(sov), showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
        export = pd.DataFrame([{**{k: v for k, v in it.record.items() if not k.startswith("_")},
                                "cited_urls": " | ".join(it.record["cited_urls"]),
                                "manufacturers": ", ".join(named(it.analysis, "manufacturer")),
                                "retailers": ", ".join(named(it.analysis, "retailer")),
                                "ranked": " > ".join(it.analysis.ranked_entities)} for it in items])
        st.download_button("Экспорт наблюдений + распознавания (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"observations_{client}_{stage}_{city}.csv", mime="text/csv")

elif page == "Источники":
    st.header("Откуда AI берёт ответы")
    st.caption("Только явные цитаты в ответах. Наличие источника ≠ цитирование ≠ доказанное влияние.")
    recs = evidence_rows()
    if not recs:
        no_data_box()
    else:
        tbl = source_table(analyze_records(recs, REG), REG)
        cited = tbl[tbl.source_type != "no_citation"]
        st.caption(f"N ответов = {len(recs)} · цитат = {len(cited)} · ответов без цитат = {int((tbl.source_type == 'no_citation').sum())}")
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
    st.header("GEO-правки (предложения; production не изменён)")
    recs = json.loads((ROOT / "data" / "processed" / "recommendations.json").read_text(encoding="utf-8"))
    for r in recs:
        if client not in r["affected_entity"]:
            continue
        with st.expander(f"{r['priority']} · {r['issue_id']} · {r['finding'][:90]}"):
            st.markdown(f"**Тип:** {r['implementation_type']} · **уверенность:** {r['confidence']} · **статус:** {r['status']}")
            st.markdown(f"**Находка:** {r['finding']}\n\n**Доказательство:** {r['evidence']}\n\n**Механизм:** {r['expected_mechanism']}")
            a, b = st.columns(2)
            a.markdown("**BEFORE**")
            a.code(r["before"], language="html")
            b.markdown("**AFTER**")
            b.code(r["after"], language="html")
            st.markdown(f"**Почему:** {r['why']}\n\n**Тест:** {r['experiment_plan']}")

elif page == "Контролируемый эксперимент":
    st.header("CONTROLLED EXPERIMENT RESULTS")
    st.warning("Локальная BM25-симуляция стадии извлечения на фиксированном корпусе. Это не ответ ChatGPT/Gemini/Perplexity "
               "и не доказательство изменения их ранжирования. С реальными KPI не смешивается.")
    exps = sorted(p.stem for p in X.EXP_DIR.glob("EXP-*.json"))
    if not exps:
        st.info("Эксперименты не описаны (data/experiments/EXP-*.json).")
    else:
        exp_id = st.selectbox("Эксперимент", exps, index=len(exps) - 1)
        exp = X.load_experiment(exp_id)
        try:
            corpus_dir = X.resolve_corpus(exp, None)
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
        saved = X.EXP_DIR / "results" / f"{exp_id}_result.json"
        if st.button("Перезапустить baseline и treatment", type="primary"):
            try:
                with st.spinner("Индексация корпуса и прогон запросов…"):
                    st.session_state["res"] = X.run_experiment(exp)
            except (FileNotFoundError, ValueError) as exc:
                st.error(f"Эксперимент не готов: {exc}")
        res = st.session_state.get("res")
        if (res is None or res["experiment_id"] != exp_id) and saved.exists():
            res = json.loads(saved.read_text(encoding="utf-8"))
            st.caption(f"Показан сохранённый результат: {saved.relative_to(ROOT)}")
        if res and res["experiment_id"] == exp_id:
            s = res["summary"]
            st.subheader("Целевые запросы: baseline → treatment")
            c1, c2, c3 = st.columns(3)
            bm, tm = s["target"]["baseline"].get("mrr"), s["target"]["treatment"].get("mrr")
            metric_n(c1, "MRR владельца", f"{fmt(bm, False)} → {fmt(tm, False)}", s["target"]["baseline"]["queries"],
                     "Mean Reciprocal Rank: среднее 1/позиция первого документа клиента в top-k (0, если нет). Это НЕ средняя позиция.")
            bt, tt = s["target"]["baseline"]["top3_rate"], s["target"]["treatment"]["top3_rate"]
            metric_n(c2, "Hit@3", f"{fmt(bt)} → {fmt(tt)}", s["target"]["baseline"]["queries"],
                     "доля целевых запросов, где клиент в первых 3 владельцах (поле top3_rate)")
            bc, tc = s["target"]["baseline"]["citation_rate"], s["target"]["treatment"]["citation_rate"]
            metric_n(c3, "Citation Rate", f"{fmt(bc)} → {fmt(tc)}", s["target"]["baseline"]["queries"],
                     "доля целевых запросов, где документ клиента попал в top-k цитат. Не путать с Hit@3.")
            if "changed_page_mrr" in s["target"]["baseline"]:
                st.caption(f"MRR изменённой страницы: {fmt(s['target']['baseline']['changed_page_mrr'], False)} → "
                           f"{fmt(s['target']['treatment']['changed_page_mrr'], False)}")
            st.subheader("Negative controls (рост = ухудшение релевантности)")
            n = s["negative_control"]
            c1, c2, c3 = st.columns(3)
            metric_n(c1, "MRR · controls", f"{fmt(n['baseline'].get('mrr'), False)} → {fmt(n['treatment'].get('mrr'), False)}", n["baseline"]["queries"])
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
