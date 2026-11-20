"""Bridge.docx -> 4 staged rows (append to the forme batch). Format only, facts unchanged.
Usage: python -I build_bridge_staging.py <unzipped Bridge.docx dir> <batch dir>"""
import html, json, re, sys
d, batch = sys.argv[1], sys.argv[2]
x = open(d + '/word/document.xml', encoding='utf-8').read()
rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', open(d + '/word/_rels/document.xml.rels').read()))
nx = open(d + '/word/numbering.xml', encoding='utf-8').read()
# level-aware Word list rendering: level 0 decimal -> "N. ", level 0 bullet -> "- ", deeper levels -> "  - "
lvlfmt = {}
for a, b in re.findall(r'<w:abstractNum [^>]*w:abstractNumId="(\d+)".*?>(.*?)</w:abstractNum>', nx, flags=re.S):
    for lv, fmt in re.findall(r'<w:lvl w:ilvl="(\d+)".*?<w:numFmt w:val="(\w+)"', b, flags=re.S):
        lvlfmt[(a, lv)] = fmt
num2abs = dict(re.findall(r'<w:num w:numId="(\d+)"[^>]*>.*?<w:abstractNumId w:val="(\d+)"', nx, flags=re.S))
counters, recs, cur = {}, [], None
for p in re.findall(r'<w:p[ >].*?</w:p>', x, flags=re.S):
    t = html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, flags=re.S)))
    m = re.search(r'<w:numPr>.*?<w:ilvl w:val="(\d+)".*?<w:numId w:val="(\d+)"', p, flags=re.S)
    if m and t.strip():
        lv, nid = m.group(1), m.group(2)
        if lv != '0':
            t = '  - ' + t
        elif lvlfmt.get((num2abs[nid], '0')) == 'decimal':
            counters[nid] = counters.get(nid, 0) + 1
            t = f"{counters[nid]}. " + t
        else:
            t = '- ' + t
    if t.startswith('ID: ') and 'Вопрос:' in t:
        t = t.split('Вопрос:')[0]
    if t.startswith('ID: '):
        cur = {'pid': t[4:].strip(), 'paras': [], 'links': []}; recs.append(cur); continue
    if t.startswith('Вопрос: '):
        continue
    cur['paras'].append(t)
    cur['links'] += [html.unescape(rels[r]) for r in re.findall(r'<w:hyperlink [^>]*r:id="(rId\d+)"', p)]
PROV = {'Gemini Search': ('gemini', 'G'), 'GPT Search': ('chatgpt_search', 'C')}
out = []
for r in recs:
    svc, hhmm = r['paras'][0].removeprefix('Сервис и время: ').rsplit(', ', 1)
    prov, letter = PROV[svc]
    body = r['paras'][1:]; body[0] = body[0].removeprefix('Ответ: ')
    i = next(k for k, s in enumerate(body) if s.startswith('Ссылки:'))
    refs = '\n'.join(body[i:])
    text_urls = [u.split('](')[0].rstrip(').,') for u in re.findall(r'https?://[^\s<>"\]]+', '\n'.join(body))]
    links = [u for u in dict.fromkeys(r['links'] + text_urls) if 'images.openai.com' not in u]
    n_img = sum('images.openai.com' in u for u in r['links'])
    cat = r['pid'].split('-')[2]
    rid = f"BR-{letter}-{cat}-001"
    out.append({
        'response_id': rid, 'prompt_id': r['pid'], 'query': '', 'provider': prov, 'model': '', 'search_mode': 'search_on',
        'timestamp': f'2026-11-20T{hhmm}:00+05:00', 'run_no': '1', 'language': 'ru', 'region_setting': '',
        'answer_text': '\n'.join(body[:i]).strip(), 'cited_urls': links,
        'data_type': 'MANUAL_VERIFIED', 'verification_status': 'pending', 'collector': '', 'verified_by': '',
        'evidence_link': f'assets/evidence/{rid}.png',
        'notes': '; '.join(filter(None, [f"Источник: Bridge.docx ({svc}, {hhmm}); исходный ID участника {r['pid']} (общий для Gemini и GPT)",
                                       'дата 2026-11-20 и +05:00 — из метаданных docx (created 16:01, modified 16:07 +05:00), в тексте только время',
                                       'текст запроса в исходных файлах отсутствует',
                                       f'исключено {n_img} ссылок images.openai.com (миниатюры)' if n_img else ''])),
    })
with open(batch + '/observations_contract_staging.jsonl', 'a', encoding='utf-8') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')
for o in out: print(o['response_id'], o['prompt_id'], o['provider'], o['timestamp'], len(o['answer_text']), len(o['cited_urls']))
