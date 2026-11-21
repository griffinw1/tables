import json, urllib.request, time
K='VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5'
vs=json.load(open('venues.json'))
out={}
for v in vs:
    if v['platform']!='resy' and 'resy.com' not in (v.get('url') or ''): continue
    vid=v.get('id')
    url = f"https://api.resy.com/3/venue?id={vid}" if vid else f"https://api.resy.com/3/venue?url_slug={v['url'].rstrip('/').split('/')[-1]}&location=dallas-fort-worth-tx"
    req=urllib.request.Request(url,headers={'Authorization':f'ResyAPI api_key="{K}"','Accept':'application/json','Origin':'https://resy.com','User-Agent':'Mozilla/5.0'})
    try: d=json.load(urllib.request.urlopen(req,timeout=20))
    except Exception as e: print('ERR',v['name'],e); continue
    imgs=[i.replace('640x360','1600x900') for i in d.get('images',[])]
    c=d.get('contact',{})
    blurb=next((x.get('body') for x in d.get('content',[]) if x.get('name')=='about' or x.get('body')),None)
    out[v['name']]={'images':imgs[:4],'website':c.get('url'),'menu':c.get('menu_url'),'blurb':(blurb or '')[:400],'price':d.get('price_range_id'),'cuisine':(d.get('type') or '')}
    print(v['name'],len(imgs),c.get('url'),c.get('menu_url'),d.get('type'))
    time.sleep(1)
json.dump(out,open('media_build/resy.json','w'),indent=1)
