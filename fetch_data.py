#!/usr/bin/env python3
"""Reanimal Speedrun Data Fetcher v11"""

import requests, csv, time, json, os
from collections import defaultdict
from datetime import datetime, timezone

BASE_URL="https://www.speedrun.com/api/v1"
OUTPUT_DIR="."
DELAY=0.7

# ── Main Game ────────────────────────────────────────────────────
GAME_ID        ="m1meylxd"
ANYPCT_CAT     ="02q1p87d"; ANYPCT_SUBCAT="ql6m49k8"
ANYPCT_RESTRICTED="q5vy67rl"; ANYPCT_UNRESTRICTED="lx5rzdj1"
ANYPCT_PLAYER  ="kn03zeon"; ANYPCT_SOLO="qvvg7z5q"
GLOBAL_PLAYER  ="j841er28"; GLOBAL_SOLO="10vgd5ol"
IL_CAT="9d8m44qk"
IL_LEVELS=[("Chapter 1","9203nz7d"),("Chapter 2","9vmj53q9"),("Chapter 3","d40nrjq9"),
           ("Chapter 4","d0kl3gm9"),("Chapter 5","w6qre4pd"),("Chapter 6","93q8y42w"),
           ("Chapter 7","98reg7rd"),("Chapter 8","dnor2z5w"),("Chapter 9","dy1j8gpd")]

# ── Demo ─────────────────────────────────────────────────────────
DEMO_CAT        ="jdzm466k"; DEMO_SUBCAT="p85wvy58"
DEMO_RESTRICTED ="1gnd07ol"; DEMO_UNRESTRICTED="q75d3wr1"

# ── Очки Main Game ───────────────────────────────────────────────
PTS_UNREST={1:100,2:70,3:50,4:35,5:25,6:18,7:12,8:8,9:5,10:3}
PTS_REST  ={1:150,2:105,3:75,4:52.5,5:37.5,6:27,7:18,8:12,9:7.5,10:4.5}
PTS_IL    ={1:20,2:14,3:10,4:7,5:5,6:3.6,7:2.4,8:1.6,9:1.0,10:0.6}

def pts_main(place, restr):
    t = PTS_REST if restr else PTS_UNREST
    if place in t: return t[place]
    if 11<=place<=15: return 1.5 if restr else 1.0
    if 16<=place<=25: return 0.75 if restr else 0.5
    return 0.0

def pts_il(place):
    if place in PTS_IL: return PTS_IL[place]
    if 11<=place<=15: return 0.2
    if 16<=place<=25: return 0.1
    return 0.0

# ── Очки Demo ────────────────────────────────────────────────────
DEMO_PTS_UNREST={1:100,2:70,3:50,4:35,5:26,6:18,7:12,8:8,9:6,10:4,11:3,12:2,13:1.5}
DEMO_PTS_REST  ={1:120,2:84,3:60,4:31.5,5:23.4,6:16.2,7:10.8,8:7.2,9:5.4,10:3.6,11:2.7,12:1.8,13:1.35}

def pts_demo(place, restr):
    t = DEMO_PTS_REST if restr else DEMO_PTS_UNREST
    if place in t: return t[place]
    return 0.9 if restr else 1.0  # 14+

# ── API ──────────────────────────────────────────────────────────
sess=requests.Session(); sess.headers["User-Agent"]="Reanimal-TopList/11.0"; _uc={}

def api_get(ep, params=None):
    time.sleep(DELAY)
    r=sess.get(f"{BASE_URL}/{ep}", params=params, timeout=20)
    if r.status_code==404: return{"data":[]}
    r.raise_for_status(); return r.json()

def get_user(uid):
    if uid in _uc: return _uc[uid]
    try:
        u=api_get(f"users/{uid}")["data"]
        name=u.get("names",{}).get("international",uid)
        av=((u.get("assets") or{}).get("image") or{}).get("uri","")
    except: name,av=uid,""
    _uc[uid]={"name":name,"avatar":av}; return _uc[uid]

def fetch_runs(cat_id, level_id=None):
    params={"category":cat_id,"status":"verified","orderby":"date",
            "direction":"asc","max":200,"embed":"players"}
    if level_id: params["level"]=level_id
    all_runs, offset=[], 0
    while True:
        params["offset"]=offset
        data=api_get("runs", params); page=data.get("data",[])
        if not page: break
        for run in page:
            emb=run.get("players",{})
            if isinstance(emb, dict):
                for p in emb.get("data",[]):
                    pid=p.get("id",""); name=p.get("names",{}).get("international",pid)
                    av=((p.get("assets") or{}).get("image") or{}).get("uri","")
                    _uc[pid]={"name":name,"avatar":av}
        all_runs.extend(page)
        pag=data.get("pagination",{}); offset+=200
        if len(page)<200 or offset>=pag.get("size",len(page)): break
    return all_runs

def get_infos(run):
    emb=run.get("players",{}); result=[]
    if isinstance(emb,dict):
        for p in emb.get("data",[]):
            pid=p.get("id",""); name=p.get("names",{}).get("international",pid)
            av=((p.get("assets") or{}).get("image") or{}).get("uri","")
            result.append({"name":name,"avatar":av})
    else:
        for p in(emb if isinstance(emb,list) else[]):
            pid=p.get("id","")
            result.append(_uc.get(pid) or (get_user(pid) if pid else{"name":p.get("name","?"),"avatar":""}))
    return result

def is_solo(rv, player_var=None):
    pv = player_var or ANYPCT_PLAYER
    if pv in rv: return rv[pv]==ANYPCT_SOLO
    if GLOBAL_PLAYER in rv: return rv[GLOBAL_PLAYER]==GLOBAL_SOLO
    return True

def competition_rank(sorted_times):
    result, pos, prev_t, rank = [], 0, None, 0
    for name, t, av in sorted_times:
        pos += 1
        if t != prev_t: rank = pos; prev_t = t
        result.append({"place":rank,"player_name":name,"avatar":av})
    return result

def make_lb(runs, subcat_var, subval):
    best={}
    for run in runs:
        rv=run.get("values",{})
        if rv.get(subcat_var)!=subval or not is_solo(rv): continue
        t=run["times"]["primary_t"]
        for inf in get_infos(run):
            nm=inf["name"]
            if nm not in best or t<best[nm][0]: best[nm]=(t,inf["avatar"])
    sorted_t=sorted([(nm,t,av) for nm,(t,av) in best.items()], key=lambda x:x[1])
    return competition_rank(sorted_t)

# ── Collect Main Game ────────────────────────────────────────────
def collect_main():
    sc=defaultdict(lambda:{"points":0.0,"avatar":""})
    pl=defaultdict(dict)

    def add(nm,av,pts,cat,place):
        if not nm: return
        if pts>0:
            sc[nm]["points"]+=pts
            if not sc[nm]["avatar"] and av: sc[nm]["avatar"]=av
        pl[nm][cat]=place

    print("\n[Main] Any% — загрузка...")
    any_runs=fetch_runs(ANYPCT_CAT)
    print(f"  Итого: {len(any_runs)} ранов")

    for label,subval,restr in[("Any% Restricted",ANYPCT_RESTRICTED,True),
                               ("Any% Unrestricted",ANYPCT_UNRESTRICTED,False)]:
        print(f"\n  [{label}]")
        for e in make_lb(any_runs, ANYPCT_SUBCAT, subval):
            pts=pts_main(e["place"],restr)
            add(e["player_name"],e["avatar"],pts,label,e["place"])
            if pts>0: print(f"    #{e['place']:>2}  {e['player_name']}  +{pts}")

    for lvl_name,lvl_id in IL_LEVELS:
        print(f"\n[IL] {lvl_name}")
        best={}
        for run in fetch_runs(IL_CAT, level_id=lvl_id):
            t=run["times"]["primary_t"]
            for inf in get_infos(run):
                nm=inf["name"]
                if nm not in best or t<best[nm][0]: best[nm]=(t,inf["avatar"])
        sorted_t=sorted([(nm,t,av) for nm,(t,av) in best.items()], key=lambda x:x[1])
        for e in competition_rank(sorted_t):
            pts=pts_il(e["place"])
            add(e["player_name"],e["avatar"],pts,lvl_name,e["place"])
            if pts>0: print(f"    #{e['place']:>2}  {e['player_name']}  +{pts}")

    return dict(sc), dict(pl)

# ── Collect Demo ─────────────────────────────────────────────────
def collect_demo():
    sc=defaultdict(lambda:{"points":0.0,"avatar":""})
    pl=defaultdict(dict)

    def add(nm,av,pts,cat,place):
        if not nm: return
        if pts>0:
            sc[nm]["points"]+=pts
            if not sc[nm]["avatar"] and av: sc[nm]["avatar"]=av
        pl[nm][cat]=place

    print("\n[Demo] Any% — загрузка...")
    demo_runs=fetch_runs(DEMO_CAT)
    print(f"  Итого: {len(demo_runs)} ранов")

    for label,subval,restr in[("Demo Any% Restricted",DEMO_RESTRICTED,True),
                               ("Demo Any% Unrestricted",DEMO_UNRESTRICTED,False)]:
        print(f"\n  [{label}]")
        for e in make_lb(demo_runs, DEMO_SUBCAT, subval):
            pts=pts_demo(e["place"],restr)
            add(e["player_name"],e["avatar"],pts,label,e["place"])
            if pts>0: print(f"    #{e['place']:>2}  {e['player_name']}  +{pts}")

    return dict(sc), dict(pl)

# ── Save ─────────────────────────────────────────────────────────
def save_csv(data, filename):
    fn=os.path.join(OUTPUT_DIR, filename)
    sp=sorted(data.items(), key=lambda x:x[1]["points"], reverse=True)
    with open(fn,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["rank","player","points","avatar"])
        w.writeheader()
        for rank,(nm,inf) in enumerate(sp,1):
            w.writerow({"rank":rank,"player":nm,"points":round(inf["points"],2),"avatar":inf.get("avatar","")})
    print(f"  ✓ {fn}  ({len(sp)} игроков)")

def save_json(data, filename):
    with open(os.path.join(OUTPUT_DIR, filename),"w",encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ {filename}")

def save_metadata():
    now=datetime.now(timezone.utc)
    save_json({"last_updated":now.strftime("%d.%m.%Y"),
               "last_updated_iso":now.isoformat(),
               "game_id":GAME_ID}, "metadata.json")

# ── Main ─────────────────────────────────────────────────────────
def main():
    print("\n"+"="*60+"\n  REANIMAL Speedrun Points Fetcher  v11\n"+"="*60)
    try:
        print("\n--- MAIN GAME ---")
        main_data, main_pl = collect_main()
        print("\n--- DEMO ---")
        demo_data, demo_pl = collect_demo()

        print("\n"+"="*60+"\n  Сохранение...\n"+"="*60)
        save_csv(main_data, "main_game.csv")
        save_csv(demo_data, "demo.csv")
        save_json(main_pl, "achievements.json")
        save_json(demo_pl, "demo_achievements.json")
        save_metadata()

        print("\n"+"="*60+"\n  ИТОГИ Main Game\n"+"="*60)
        for i,(nm,inf) in enumerate(sorted(main_data.items(),key=lambda x:x[1]["points"],reverse=True),1):
            print(f"  {i:>2}. {nm}: {round(inf['points'],2)} pts")

        print("\n"+"="*60+"\n  ИТОГИ Demo\n"+"="*60)
        for i,(nm,inf) in enumerate(sorted(demo_data.items(),key=lambda x:x[1]["points"],reverse=True),1):
            print(f"  {i:>2}. {nm}: {round(inf['points'],2)} pts")

    except requests.exceptions.ConnectionError: print("[ERROR] Нет соединения")
    except Exception:
        import traceback; traceback.print_exc()

if __name__=="__main__": main()
