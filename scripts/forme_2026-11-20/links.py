import re, html, json, sys
sys.path.insert(0, 'src')
from geolab.analysis import url_key
d = sys.argv[1]
x = open(d + '/word/document.xml', encoding='utf-8').read()
rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', open(d + '/word/_rels/document.xml.rels').read()))
SHARE = re.compile(r'chatgpt\.com/(share|c)/|chat\.openai\.com/(share|c)/|gemini\.google\.com/(share|app)|g\.co/gemini|bard\.google\.com')
cur = None; out = []
for p in re.findall(r'<w:p[ >].*?</w:p>', x, flags=re.S):
    t = html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, flags=re.S)))
    if t.startswith('ID: '): cur = t[4:]; sect = 'answer'; continue
    if t.startswith('Ссылки:'): sect = 'refs'
    for rid, inner in re.findall(r'<w:hyperlink [^>]*r:id="(rId\d+)"[^>]*>(.*?)</w:hyperlink>', p, flags=re.S):
        u = html.unescape(rels[rid]); anchor = html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', inner, flags=re.S)))
        cls = 'B_conversation' if SHARE.search(u) else ('C_image_thumbnail' if 'images.openai.com' in u else 'A_citation')
        out.append(dict(block=cur, section=sect, cls=cls, anchor=anchor.strip(), url=u, key=url_key(u)))
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print('total hyperlinks', len(out), 'rels hyperlinks', sum('hyperlink' in l for l in open(d + '/word/_rels/document.xml.rels').read().split('<Relationship')))
from collections import Counter
print(Counter(o['cls'] for o in out))
for b in dict.fromkeys(o['block'] for o in out):
    a = [o for o in out if o['block'] == b and o['cls'] == 'A_citation']
    print(b, 'A raw', len(a), 'A unique', len({o['key'] for o in a}), 'C', sum(o['block'] == b and o['cls'] != 'A_citation' for o in out))
    for o in out:
        if o['block'] == b: print('   ', o['cls'][:1], o['section'][:3], repr(o['anchor'][:45]), o['url'][:85])
