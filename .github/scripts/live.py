# 실시간 항공 정보 → live.json (+ 바뀌면 휴대폰 알림)
# 출처: FlightStats(출발·도착 예정/실제 시각, 지연, 게이트, 수하물) + 인천공항 공식(인천 출발편 체크인·게이트)
# 실행: 한 번 돌 때 최대 LOOP_MIN분 동안 POLL_SEC초마다 반복 (깃허브 예약 실행이 몇 시간씩 밀려도 빈틈 없게)
import json, urllib.request, urllib.parse, datetime, os, re, time, subprocess

KST = datetime.timezone(datetime.timedelta(hours=9))
# 편명: (출발일 현지 연,월,일, 인천 출발편이면 True)
FLIGHTS = {"ET672": (2026, 11, 6, True), "ET673": (2026, 11, 8, False)}
WIN_BEFORE_H, WIN_AFTER_H = 8, 4          # 출발 8시간 전 ~ 도착 4시간 후만 확인
LOOP_MIN = int(os.environ.get("LOOP_MIN", "0"))  # 0이면 한 번만
POLL_SEC = 300
NTFY = os.environ.get("NTFY_TOPIC", "").strip()
PATH = "live.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
ST_KO = {"Scheduled": "예정", "Departed": "출발함", "En Route": "비행 중", "Arrived": "도착", "Landed": "도착",
         "Delayed": "지연", "Cancelled": "결항", "Diverted": "회항", "Unknown": "확인 중"}

def now(): return datetime.datetime.now(KST)

def flightstats(fno, y, m, d):
    url = f"https://www.flightstats.com/v2/flight-tracker/{fno[:2]}/{fno[2:]}?year={y}&month={m}&date={d}"
    h = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "ignore")
    j = json.loads(re.search(r'__NEXT_DATA__ = (\{.*?\});\s*__NEXT_LOADED', h, re.S).group(1))
    f = j["props"]["initialState"]["flightTracker"]["flight"]
    st, sc = f.get("status") or {}, f.get("schedule") or {}
    dep, arr = f.get("departureAirport") or {}, f.get("arrivalAirport") or {}
    dl = st.get("delay") or {}
    hm = lambda s: (s or "")[11:16]
    return {
        "st": st.get("status") or "", "desc": st.get("statusDescription") or "",
        "dDelay": ((dl.get("departure") or {}).get("minutes")) or 0,
        "aDelay": ((dl.get("arrival") or {}).get("minutes")) or 0,
        "depS": hm(sc.get("scheduledDeparture")), "depE": hm(sc.get("estimatedActualDeparture")),
        "depT": sc.get("estimatedActualDepartureTitle") or "",
        "arrS": hm(sc.get("scheduledArrival")), "arrE": hm(sc.get("estimatedActualArrival")),
        "arrT": sc.get("estimatedActualArrivalTitle") or "",
        "depGate": dep.get("gate") or "", "depTerm": dep.get("terminal") or "",
        "arrGate": arr.get("gate") or "", "arrTerm": arr.get("terminal") or "", "bag": arr.get("baggage") or "",
        "landed": bool(f.get("isLanded")), "upd": st.get("lastUpdatedText") or "",
        "utcDep": sc.get("scheduledDepartureUTC") or "", "utcArr": sc.get("scheduledArrivalUTC") or "",
    }

def icn_dep(fno, y, m, d):
    day = f"{y:04d}{m:02d}{d:02d}"
    data = urllib.parse.urlencode({"siteId": "ap_ko", "langSe": "ko", "daySel": day, "fromTime": "0000", "toTime": "2359",
        "airline": fno[:2], "row": "200", "page": "1", "layout": "61705f6b6f40403836394040666e637431"}).encode()
    req = urllib.request.Request("https://www.airport.kr/dep/ap_ko/getDepPasSchList.do", data=data, headers={
        "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.airport.kr/ap_ko/869/subview.do", "User-Agent": UA})
    rows = [r for r in json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))["scheduleList"] if r.get("fnumber") == fno]
    return rows[0] if rows else {}

def build(fno, y, m, d, icn):
    fs = flightstats(fno, y, m, d)
    r = {}
    if icn:
        try: r = icn_dep(fno, y, m, d)
        except Exception as e: print("인천공항 실패", fno, e)
    status = ST_KO.get(fs["st"], fs["st"])
    if fs["dDelay"] >= 5 and not fs["landed"] and fs["st"] in ("Scheduled", "Delayed", ""): status = f"{fs['dDelay']}분 지연"
    if r.get("stattxt"): status = r["stattxt"]
    gate = r.get("gatenumber") or fs["depGate"]
    new = {
        "status": status, "gate": gate, "term": fs["depTerm"],
        "depS": fs["depS"], "depE": fs["depE"], "depT": "실제" if fs["depT"] == "Actual" else "예상",
        "arrS": fs["arrS"], "arrE": fs["arrE"], "arrT": "실제" if fs["arrT"] == "Actual" else "예상",
        "dDelay": fs["dDelay"], "aDelay": fs["aDelay"],
        "arrGate": fs["arrGate"], "arrTerm": fs["arrTerm"], "bag": fs["bag"], "landed": fs["landed"],
        "chk": r.get("chkinrange") or "",
        "time": fs["depE"] or fs["depS"],
        "note": " · ".join(x for x in [("체크인 " + r["chkinrange"]) if r.get("chkinrange") else "", ("터미널 " + fs["depTerm"]) if fs["depTerm"] else ""] if x),
        "src": "인천공항+FlightStats" if r else "FlightStats",
    }
    return new

def msg(fno, old, new):
    """사람이 알아야 할 변화만 골라 한 줄로"""
    out = []
    if old.get("gate") != new["gate"] and new["gate"]: out.append(f"출발 게이트 {new['gate']}" + (f" (← {old['gate']})" if old.get("gate") else ""))
    if abs((old.get("dDelay") or 0) - new["dDelay"]) >= 10 and not new["landed"]: out.append(f"출발 {new['depE'] or new['depS']} ({new['dDelay']}분 지연)" if new["dDelay"] else f"정시 출발 {new['depS']}")
    if old.get("status") != new["status"] and new["status"] in ("출발함", "비행 중", "도착", "결항", "회항"): out.append(new["status"])
    if old.get("bag") != new["bag"] and new["bag"]: out.append(f"수하물 {new['bag']}번")
    if old.get("arrE") != new["arrE"] and new["arrE"] and new["landed"]: out.append(f"도착 {new['arrE']}")
    return f"✈️ {fno} · " + " · ".join(out) if out else ""

def push(text):
    if not NTFY or not text: return
    try:
        urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + NTFY, data=text.encode("utf-8"),
            headers={"Title": "여행 앱 항공 알림", "Tags": "airplane", "Priority": "high"}), timeout=20)
        print("알림 보냄", text)
    except Exception as e: print("알림 실패", e)

def commit():
    subprocess.run("git add live.json && (git commit -qm '실시간 항공 정보' || true) && for i in 1 2 3; do git pull --rebase -q && git push -q && break; sleep 5; done", shell=True)

def once():
    try: live = json.load(open(PATH, encoding="utf-8"))
    except Exception: live = {}
    changed, active = False, False
    for fno, (y, m, d, icn) in FLIGHTS.items():
        try: new = build(fno, y, m, d, icn)
        except Exception as e: print("실패", fno, e); continue
        old = live.get(fno, {})
        same = {k: v for k, v in new.items()} == {k: v for k, v in old.items() if k not in ("at", "chkAt")}
        new["at"] = now().strftime("%m/%d %H:%M")
        if not same:
            push(msg(fno, old, new)); live[fno] = new; changed = True
        else:
            live[fno]["chkAt"] = now().strftime("%m/%d %H:%M")   # 바뀐 건 없어도 '방금 확인함' 표시
            changed = True
        print(fno, new)
    if changed:
        json.dump(live, open(PATH, "w", encoding="utf-8"), ensure_ascii=False)
    return live

def active_now():
    t = now()
    for fno, (y, m, d, icn) in FLIGHTS.items():
        a = datetime.datetime(y, m, d, 0, 0, tzinfo=KST) - datetime.timedelta(hours=WIN_BEFORE_H)
        b = datetime.datetime(y, m, d, 23, 59, tzinfo=KST) + datetime.timedelta(hours=WIN_AFTER_H)
        if a <= t <= b: return True
    return False

if __name__ == "__main__":
    if os.environ.get("FORCE"):
        once(); commit(); raise SystemExit
    end = time.time() + LOOP_MIN * 60
    while True:
        if active_now():
            once()
            if LOOP_MIN: commit()
        if not LOOP_MIN or time.time() + POLL_SEC > end: break
        time.sleep(POLL_SEC)
