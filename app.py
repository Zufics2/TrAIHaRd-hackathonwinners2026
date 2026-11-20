"""GEO Intelligence Lab — Streamlit dashboard.  Run:  streamlit run app.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from geolab import experiment as X  # noqa: E402
from geolab.metrics import analyze_records, entity_metrics, fmt, general_metrics, share_of_voice, source_table  # noqa: E402
from geolab.registry import ROOT, load_registry  # noqa: E402
from geolab.store import STATUSES, load_prompts, load_responses  # noqa: E402

st.set_page_config(page_title="GEO Intelligence Lab", layout="wide")
st.markdown("<style>.block-container{padding-top:1.5rem;max-width:1300px}</style>", unsafe_allow_html=True)

REG = load_registry()
PROMPTS = load_prompts()
RECORDS, LOAD_ERRORS = load_responses()

STAGE_LABEL = {"brand_discovery": "A · Выбор бренда товара", "retailer_discovery": "B · Выбор магазина", "bridge": "C · Бренд → магазин"}
STATUS_HELP = {
    "REAL": "ответ получен через API AI-поиска",
    "MANUAL_VERIFIED": "ответ собран вручную из интерфейса AI-поиска и проверен",
    "CONTROLLED_EXPERIMENT": "результат локальной симуляции, не внешний AI",
    "SYNTHETIC_DEMO": "демо-данные, не измерение",
}

# ---------- sidebar ----------
st.sidebar.title("GEO Intelligence Lab")
page = st.sidebar.radio("Раздел", ["Обзор", "Ответы AI и KPI", "Источники", "Рекомендации", "Эксперимент до/после", "Данные и статусы"])
client = st.sidebar.selectbox("Клиент", [e.id for e in REG.clients()], format_func=lambda i: REG.entities[i].name)
stage = st.sidebar.selectbox("Этап пути", list(STAGE_LABEL), format_func=STAGE_LABEL.get)
city = st.sidebar.selectbox("Город", ["all", "almaty", "astana", "karaganda", "national"],
                            format_func=lambda c: "Все" if c == "all" else REG.cities[c]["name"])
statuses = st.sidebar.multiselect("Статус данных", STATUSES, default=["REAL", "MANUAL_VERIFIED"],
                                  help="Статусы никогда не смешиваются по умолчанию.")
category = REG.entities[client].category

if LOAD_ERRORS:
    st.sidebar.error(f"Ошибки импорта: {len(LOAD_ERRORS)} (см. «Данные и статусы»)")


def scoped_records() -> list[dict]:
    pids = PROMPTS[(PROMPTS.category == category) & (PROMPTS.funnel_stage == stage)]
    if city != "all":
        pids = pids[pids.city == city]
    ids = set(pids.prompt_id)
    return [r for r in RECORDS if r["prompt_id"] in ids and r["status"] in statuses]


def no_data_box():
    st.info("Нет ответов AI для выбранного среза и статусов. Соберите ответы по протоколу docs/08 и положите файл в data/raw/manual/. "
            "Пустой срез отображается как N/A, а не как 0%.")


# ---------- pages ----------
if page == "Обзор":
    st.header("Как AI-поиск рекомендует бренды товаров и магазины")
    c1, c2, c3 = st.columns(3)
    c1.metric("Запросов в датасете", len(PROMPTS))
    c2.metric("Ответов AI (все статусы)", len(RECORDS))
    c3.metric("Провайдеров", len({r["provider"] for r in RECORDS}) or "N/A")
    st.subheader("Два слоя покупательского пути")
    st.markdown(
        "- **Слой A — выбор бренда товара** («какая краска лучше для детской?»): AI рекомендует производителей. "
        "Клиент выигрывает, если рекомендуют марки из его ассортимента.\n"
        "- **Слой B — выбор магазина** («где купить люстру в Астане?»): AI рекомендует продавцов. Клиент выигрывает, если назван он.\n"
        "- **Мост C**: если AI посоветовал марку, связан ли следующий шаг с нашим магазином?"
    )
    cov = PROMPTS.groupby(["category", "city", "funnel_stage"]).size().reset_index(name="prompts")
    st.dataframe(cov, hide_index=True, width="stretch")
    st.subheader("Подтверждённое присутствие клиентов по городам")
    rows = [{"магазин": e.name, "город": REG.cities[c]["name"], "статус": v["status"], "доказательство": v["evidence"]}
            for e in REG.clients() for c, v in e.cities.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

elif page == "Ответы AI и KPI":
    st.header(f"{STAGE_LABEL[stage]} — {REG.entities[client].name}")
    recs = scoped_records()
    if not recs:
        no_data_box()
    else:
        items = analyze_records(recs, REG)
        g = general_metrics(items)
        if stage == "brand_discovery":
            assort = REG.assortment(client)
            st.caption("Объект рекомендации — производитель. Метрика клиента: доля ответов, где названа хотя бы одна марка из ассортимента.")
            hit = sum(1 for it in items if any(a.id in it.analysis.mentions for a in assort))
            c1, c2, c3 = st.columns(3)
            c1.metric("Assortment Brand Coverage", fmt(hit / len(items)))
            c2.metric("Ответов", g["answers"])
            c3.metric("Ответов с цитатами", g["answers_with_citations"])
            sov = share_of_voice(items, REG, "manufacturer", category)
        else:
            m = entity_metrics(items, client)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Mention rate", fmt(m["mention_rate"]))
            c2.metric("Recommendation rate", fmt(m["recommendation_rate"]), help="эвристика: список или слова-рекомендации, без отрицаний")
            c3.metric("Top-3 rate", fmt(m["top3_rate"]), help=f"только явно нумерованные списки: {m['ranked_answers']} отв.")
            c4.metric("Citation rate", fmt(m["citation_rate"]), help=f"знаменатель: {m['answers_with_citations']} отв. с цитатами")
            c5.metric("Ответов", m["answers"])
            sov = share_of_voice(items, REG, "retailer", category)
        if not sov.empty:
            fig = px.bar(sov, x="share_of_voice", y="name", orientation="h", color="is_client" if stage != "brand_discovery" else "in_client_assortment",
                         color_discrete_map={True: "#2f6f4f", False: "#b8bcc2"}, labels={"share_of_voice": "AI Share of Voice", "name": ""})
            fig.update_layout(height=60 + 28 * len(sov), showlegend=False, margin=dict(l=0, r=0, t=10, b=0), xaxis_tickformat=".0%")
            st.plotly_chart(fig, width="stretch")
        st.subheader("Ответы")
        for it in items:
            r = it.record
            with st.expander(f"[{r['status']}] {r['provider']} · {r['query']} · {r['timestamp']}"):
                st.write(r["answer_text"])
                ments = [{"entity": REG.entities[k].name, "level": v.level, "recommended": v.recommended, "rank": v.rank} for k, v in it.analysis.mentions.items()]
                st.dataframe(pd.DataFrame(ments) if ments else pd.DataFrame([{"entity": "нет упоминаний"}]), hide_index=True)

elif page == "Источники":
    st.header("Откуда AI берёт ответы")
    st.caption("Показываются только явные цитаты из ответов. Наличие источника ≠ цитирование ≠ доказанное влияние.")
    recs = scoped_records()
    if not recs:
        no_data_box()
    else:
        items = analyze_records(recs, REG)
        tbl = source_table(items, REG)
        by_type = tbl[tbl.source_type != "no_citation"].groupby("source_type").size().reset_index(name="citations")
        if not by_type.empty:
            st.plotly_chart(px.bar(by_type.sort_values("citations"), x="citations", y="source_type", orientation="h", labels={"source_type": ""}), width="stretch")
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={"cited_url": st.column_config.LinkColumn("cited_url")})

elif page == "Рекомендации":
    st.header("GEO-правки (предложения, production не изменён)")
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

elif page == "Эксперимент до/после":
    st.header("Контролируемый эксперимент")
    st.warning("CONTROLLED_EXPERIMENT: локальная BM25-симуляция стадии извлечения. Это не ответ ChatGPT/Gemini и не доказательство изменения внешней модели.")
    exps = sorted(p.stem for p in X.EXP_DIR.glob("EXP-*.json"))
    if not exps:
        st.info("Эксперименты ещё не описаны (data/experiments/EXP-*.json).")
    else:
        exp_id = st.selectbox("Эксперимент", exps)
        exp = X.load_experiment(exp_id)
        st.markdown(f"**Гипотеза:** {exp.get('hypothesis', '')}\n\n**Изменённые документы:** {', '.join(exp['changed_doc_ids'])}")
        if st.button("Запустить baseline и treatment", type="primary"):
            try:
                with st.spinner("Индексация корпуса и прогон запросов…"):
                    res = X.run_experiment(exp)
                    X.save_result(res)
                st.session_state["res"] = res
            except (FileNotFoundError, ValueError) as exc:
                st.error(f"Эксперимент не готов: {exc}")
        res = st.session_state.get("res")
        if res and res["experiment_id"] == exp_id:
            s = res["summary"]
            c1, c2, c3, c4 = st.columns(4)
            bm, tm = s["target"]["baseline"]["mrr"], s["target"]["treatment"]["mrr"]
            c4.metric("MRR (целевые)", fmt(tm, pct=False), None if bm is None or tm is None else f"{tm - bm:+.2f} vs {fmt(bm, pct=False)}")
            bt, tt = s["target"]["baseline"]["top3_rate"], s["target"]["treatment"]["top3_rate"]
            c1.metric("Top-3 (целевые запросы)", fmt(tt), None if bt is None or tt is None else f"{(tt - bt) * 100:+.0f} п.п. vs baseline {fmt(bt)}")
            bc, tc = s["target"]["baseline"]["citation_rate"], s["target"]["treatment"]["citation_rate"]
            c2.metric("Цитирование страницы клиента", fmt(tc), None if bc is None or tc is None else f"{(tc - bc) * 100:+.0f} п.п.")
            nb, nt = s["negative_control"]["baseline"]["top3_rate"], s["negative_control"]["treatment"]["top3_rate"]
            c3.metric("Negative control Top-3", fmt(nt), None if nb is None or nt is None else f"{(nt - nb) * 100:+.0f} п.п. (должно быть ≈0)", delta_color="inverse")
            df = pd.DataFrame(res["per_query"])
            df["baseline_entities"] = df.baseline_entities.map(lambda v: ", ".join(v))
            df["treatment_entities"] = df.treatment_entities.map(lambda v: ", ".join(v))
            st.dataframe(df, hide_index=True, width="stretch")

elif page == "Данные и статусы":
    st.header("Происхождение данных")
    for s, h in STATUS_HELP.items():
        st.markdown(f"- **{s}** — {h}: {sum(1 for r in RECORDS if r['status'] == s)} ответов")
    if LOAD_ERRORS:
        st.error("\n".join(LOAD_ERRORS))
    st.subheader("Датасет запросов")
    st.dataframe(PROMPTS, hide_index=True, width="stretch")
