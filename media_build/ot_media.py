import json, sys, time, random
sys.path.insert(0,'.')
from platforms.browser import headless_chrome
vs=[v for v in json.load(open('venues.json')) if v['platform']=='opentable']
only=sys.argv[1:]
if only: vs=[v for v in vs if v['name'] in only]
JS=r"""() => {
 const og=(document.querySelector('meta[property="og:image"]')||{}).content||null;
 const imgs=[...document.querySelectorAll('img')].map(i=>i.currentSrc||i.src).filter(s=>/otstatic|resizer/.test(s)&&!/logo|avatar|profile|icon/i.test(s));
 let st=null; try{st=window.__INITIAL_STATE__||null}catch(e){}
 const found={website:[],menu:[],desc:[],cuisine:[],price:[],photos:[]};
 const seen=new Set();
 function walk(o,d){ if(!o||typeof o!=='object'||d>9||seen.has(o))return; seen.add(o);
  for(const [k,v] of Object.entries(o)){ const lk=k.toLowerCase();
   if(typeof v==='string'){
     if(lk==='website'||lk==='websiteurl') found.website.push(v);
     if(/menu/.test(lk)&&/^https?:/.test(v)) found.menu.push(v);
     if(lk==='description'&&v.length>60) found.desc.push(v);
     if(lk==='primarycuisine'||lk==='cuisine') found.cuisine.push(v);
     if(lk==='pricebanddescription'||lk==='pricerange') found.price.push(v);
     if(/^https:\/\/resizer|otstatic\.com\/prod/.test(v)&&/(\.jpe?g|\.webp|\.png|resizer)/i.test(v)) found.photos.push(v);
   } else if(v&&typeof v==='object'){ if(lk==='name'&&v.text) {} walk(v,d+1);} } }
 walk(st,0);
 const links=[...document.querySelectorAll('a')].filter(a=>/menu|website/i.test(a.textContent)&&/^https?:/.test(a.href)&&!/opentable\.com/.test(a.href)).map(a=>[a.textContent.trim(),a.href]);
 return {og, imgs:[...new Set(imgs)].slice(0,12), links, st:Object.fromEntries(Object.entries(found).map(([k,v])=>[k,[...new Set(v)].slice(0,8)]))};
}"""
out={}
try: out=json.load(open('media_build/ot.json'))
except Exception: pass
with headless_chrome() as b:
    pg=b.page()
    for v in vs:
        if v['name'] in out and out[v['name']].get('og'): continue
        url=v['url'] if '/r/' in v['url'] or 'nobu' in v['url'] or 'nick-and' in v['url'] else f"https://www.opentable.com/restaurant/profile/{v['id']}"
        try:
            r=pg.goto(url,wait_until='domcontentloaded',timeout=45000)
            pg.wait_for_timeout(2500)
            d=pg.evaluate(JS); d['status']=r.status if r else None; d['page']=pg.url
        except Exception as e:
            d={'error':str(e)[:200]}
        out[v['name']]=d
        print(v['name'],d.get('status'),bool(d.get('og')),len(d.get('imgs',[])),d.get('st',{}).get('website'),d.get('links'),flush=True)
        json.dump(out,open('media_build/ot.json','w'),indent=1)
        time.sleep(random.uniform(6,11))
