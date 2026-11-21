import json, urllib.request, urllib.parse, re, time, html
vs=json.load(open('venues.json')); resy=json.load(open('media_build/resy.json'))
BAD=re.compile(r'yelp|tripadvisor|opentable|resy|sevenrooms|exploretock|facebook|instagram|google|eater|dmagazine|guidedallas|culturemap|wikipedia|doordash|ubereats|grubhub|toasttab|mapquest|foursquare|thrillist|timeout|infatuation|michelin|dallasnews|youtube|tiktok|linkedin|beliapp|postmates|seamless|zomato|restaurantji|menupix|allmenus|sirved|order|giftly|apple\.com|bing',re.I)
out={}
for v in vs:
    if resy.get(v['name'],{}).get('website'): out[v['name']]=resy[v['name']]['website']; continue
    q=f"{v['name']} {v.get('hood') or ''} Dallas TX official site"
    req=urllib.request.Request('https://html.duckduckgo.com/html/?q='+urllib.parse.quote(q),headers={'User-Agent':'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/142 Safari/537.36'})
    try: h=urllib.request.urlopen(req,timeout=20).read().decode('utf8','ignore')
    except Exception as e: print('ERR',v['name'],e); continue
    links=[urllib.parse.unquote(m) for m in re.findall(r'uddg=([^&"]+)',h)]
    links=[l for l in dict.fromkeys(links) if not BAD.search(l)]
    out[v['name']]=links[0] if links else None
    print(v['name'],'->',links[:2],flush=True); time.sleep(1.5)
json.dump(out,open('media_build/sites.json','w'),indent=1)
