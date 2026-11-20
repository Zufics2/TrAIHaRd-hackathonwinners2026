import json, sys
recs = json.load(open(sys.argv[1], encoding='utf-8'))
orig = [json.loads(l) for l in open(sys.argv[2], encoding='utf-8')]
PROV = {'gemini_search': 'gemini', 'chatgpt_search': 'chatgpt_search'}
out = []
for r, o in zip(recs, orig):
    assert r['id'] == o['prompt_id']
    links = [u for u in r['links'] if 'images.openai.com' not in u]
    n_img = len(r['links']) - len(links)
    notes = [f"Источник: Запросы.docx ({r['svc'].removeprefix('Сервис и время: ')}); prompt_id участника; текст запроса в исходных файлах отсутствует"]
    if not links:
        notes.append("в docx нет URL источников (только подпись «Google Maps»)")
    if n_img:
        notes.append(f"исключено {n_img} ссылок images.openai.com (миниатюры изображений, не источники)")
    out.append({
        'response_id': o['observation_id'], 'prompt_id': o['prompt_id'], 'query': '',
        'provider': PROV[o['provider']], 'model': '', 'search_mode': 'search_on' if o['search_mode'] is True else 'unknown',
        'timestamp': o['timestamp'], 'run_no': '1', 'language': 'ru', 'region_setting': '',
        'answer_text': r['answer'], 'cited_urls': links,
        'data_type': 'MANUAL_VERIFIED', 'verification_status': 'pending',
        'collector': '', 'verified_by': '', 'evidence_link': f"assets/evidence/{o['observation_id']}.png",
        'notes': '; '.join(notes),
        'refs_section_docx': r['refs_section'],
    })
with open(sys.argv[3], 'w', encoding='utf-8') as f:
    for x in out: f.write(json.dumps(x, ensure_ascii=False) + '\n')
