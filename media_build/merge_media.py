"""media_build/{resy,ot,chrome}.json -> media.json  (photos hot-linked, menus/website links)."""
import json, re
def L(p):
    try: return json.load(open(p))
    except Exception: return {}
resy, ot, ch = L('media_build/resy.json'), L('media_build/ot.json'), L('media_build/chrome.json')
out = {}
for n, d in resy.items():
    out[n] = {'images': d.get('images') or [], 'website': d.get('website') or None, 'menu': d.get('menu') or None,
              'cuisine': d.get('cuisine') or None, 'blurb': d.get('blurb') or None, 'img_src': 'Resy'}
for n, d in ot.items():
    if d.get('error'): continue
    st = d.get('st', {})
    imgs = [i for i in ([d.get('og')] + d.get('imgs', []) + st.get('photos', [])) if i]
    imgs = [i for i in dict.fromkeys(imgs) if not re.search(r'logo|default|placeholder', i, re.I)]
    links = dict((t.lower(), h) for t, h in d.get('links', []))
    menu = next((h for t, h in links.items() if 'menu' in t), None) or next(iter(st.get('menu', [])), None)
    site = next((h for t, h in links.items() if 'website' in t), None) or next(iter(st.get('website', [])), None)
    out[n] = {'images': imgs[:4], 'website': site, 'menu': menu, 'cuisine': next(iter(st.get('cuisine', [])), None),
              'blurb': next(iter(st.get('desc', [])), None), 'img_src': 'OpenTable'}
for n, d in ch.items():  # Chrome pass wins for anything it set
    o = out.setdefault(n, {'images': []})
    for k in ('website', 'menu', 'cuisine', 'blurb'):
        if d.get(k): o[k] = d[k]
    if d.get('images'): o['images'] = d['images'] + [i for i in o.get('images', []) if i not in d['images']]; o['img_src'] = d.get('img_src', 'site')
json.dump(out, open('media.json', 'w'), indent=1, ensure_ascii=False)
print(len(out), 'venues with media;', sum(1 for v in out.values() if v.get('images')), 'with photos;', sum(1 for v in out.values() if v.get('menu')), 'with menus')
