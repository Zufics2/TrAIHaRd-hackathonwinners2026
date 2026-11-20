import json, sys, collections
sys.path.insert(0, 'src')
from geolab.registry import load_registry
from geolab.analysis import url_key
from geolab.metrics import analyze_records, entity_metrics, source_table, fmt
reg = load_registry()
CAT = {'PA': 'paint', 'CH': 'chandelier'}; CITY = {'ALM': 'almaty', 'AST': 'astana', 'KAR': 'karaganda'}
recs = []
for l in open(sys.argv[1], encoding='utf-8'):
    r = json.loads(l); _, c, t, _ = r['prompt_id'].split('-')
    r.update(category=CAT[c], city=CITY[t]); recs.append(r)
items = analyze_records(recs, reg)
print('| OBS | AI | категория | город | клиент упомянут | клиент рекомендован | рейтинг | позиция клиента | ссылок (уник.) | клиент процитирован |')
print('|---|---|---|---|---|---|---|---|---|---|')
for it in items:
    r, a = it.record, it.analysis
    cl = 'centr_krasok' if r['category'] == 'paint' else 'svet_kz'
    m = a.mentions.get(cl)
    uniq = len({url_key(c.url) for c in a.citations})
    print(f"| {r['response_id']} | {r['provider']} | {r['category']} | {r['city']} | {'да' if m else 'нет'} | {'да' if m and m.recommended else 'нет'} | "
          f"{'да ('+str(len(a.ranked_entities))+')' if a.has_ranking else 'нет'} | {m.rank if m and m.rank else '—'} | {uniq} | "
          f"{'да' if any(c.owner_entity == cl for c in a.citations) else 'нет'} |")
print()
for key in ('provider', 'city'):
    for val in sorted({it.record[key] for it in items}):
        sub = [it for it in items if it.record[key] == val]
        for cl in ('centr_krasok', 'svet_kz'):
            cat = reg.entities[cl].category
            s2 = [it for it in sub if it.record['category'] == cat]
            if not s2: continue
            em = entity_metrics(s2, cl)
            print(f"{key}={val} {cl}: N={em['answers']} mention={fmt(em['mention_rate'])} rec={fmt(em['recommendation_rate'])} "
                  f"top3={fmt(em['top3_rate'])} (ranked N={em['ranked_answers']}) citation={fmt(em['citation_rate'])} (N={em['answers_with_citations']})")
print()
st = source_table(items, reg)
print(st.groupby(['ai_system', 'source_type']).size().to_string())
print(st[['prompt_id', 'domain', 'source_type', 'source_owner']].drop_duplicates().to_string())
print()
cnt = collections.Counter()
for it in items:
    for e, m in it.analysis.mentions.items():
        if reg.entities[e].level == 'retailer': cnt[(e, m.recommended)] += 1
print(sorted(cnt.items()))
