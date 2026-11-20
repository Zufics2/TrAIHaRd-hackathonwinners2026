import re, html, json, sys, difflib
d = sys.argv[1]
x = open(d + '/word/document.xml', encoding='utf-8').read()
rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', open(d + '/word/_rels/document.xml.rels').read()))
nx = open(d + '/word/numbering.xml', encoding='utf-8').read()
absfmt = {a: re.search(r'<w:lvl w:ilvl="0".*?<w:numFmt w:val="(\w+)"', blk, flags=re.S).group(1)
          for a, blk in re.findall(r'<w:abstractNum [^>]*w:abstractNumId="(\d+)".*?>(.*?)</w:abstractNum>', nx, flags=re.S)}
numfmt = {n: absfmt[a] for n, a in re.findall(r'<w:num w:numId="(\d+)"[^>]*>.*?<w:abstractNumId w:val="(\d+)"', nx, flags=re.S)}
counters = {}
recs = []; cur = None
for p in re.findall(r'<w:p[ >].*?</w:p>', x, flags=re.S):
    t = html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, flags=re.S)))
    nid = re.search(r'<w:numPr>.*?<w:numId w:val="(\d+)"', p, flags=re.S)
    if nid and t.strip():
        if numfmt[nid.group(1)] == 'bullet':
            t = '- ' + t
        else:
            counters[nid.group(1)] = counters.get(nid.group(1), 0) + 1
            t = f"{counters[nid.group(1)]}. " + t
    links = [html.unescape(rels[r]) for r in re.findall(r'r:id="(rId\d+)"', p)]
    if t.startswith('ID: '):
        cur = {'id': t[4:].strip(), 'paras': [], 'links': []}; recs.append(cur); continue
    cur['paras'].append(t); cur['links'] += links
out = []
for r in recs:
    svc = r['paras'][0]
    body = r['paras'][1:]
    body[0] = body[0].removeprefix('Ответ: ')
    i = next(k for k, s in enumerate(body) if s.startswith('Ссылки:'))
    ans = '\n'.join(body[:i]).strip()
    refs = '\n'.join(body[i:]).strip()
    out.append({'id': r['id'], 'svc': svc, 'answer': ans, 'refs_section': refs, 'links': r['links']})
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
jl = [json.loads(l) for l in open(sys.argv[3], encoding='utf-8')]
for o, j in zip(out, jl):
    a, b = o['answer'], j['response_text']
    print(j['observation_id'], o['id'] == j['prompt_id'], o['svc'], 'docx', len(a), 'jsonl', len(b), 'equal', a == b)
    if a != b:
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != 'equal': print('   ', op, repr(a[i1:i2][:120]), '->', repr(b[j1:j2][:120]))
    print('   links:', [l for l in o['links'] if 'images.openai' not in l], ' n_img:', sum('images.openai' in l for l in o['links']))
