# 인천공항 출발편 실시간 정보(게이트·지연) → live.json
import json, urllib.request, urllib.parse, datetime, os
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
FLIGHTS = {"ET672": "20261106"}   # 인천 출발 (인천공항 공식)
FS = {"ET672": (2026, 11, 6), "ET673": (2026, 11, 8)}  # FlightStats (보조·나리타)
path = "live.json"
try:
    live = json.load(open(path, encoding="utf-8"))
except Exception:
    live = {}
def fetch(day, airline):
    data = urllib.parse.urlencode({"siteId": "ap_ko", "langSe": "ko", "daySel": day, "fromTime": "0000", "toTime": "2359",
        "airline": airline, "row": "200", "page": "1", "layout": "61705f6b6f40403836394040666e637431"}).encode()
    req = urllib.request.Request("https://www.airport.kr/dep/ap_ko/getDepPasSchList.do", data=data, headers={
        "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.airport.kr/ap_ko/869/subview.do",
        "User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Safari/605.1.15"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))["scheduleList"]
changed = False
import re
def flightstats(fno, y, m, d):
    url = f"https://www.flightstats.com/v2/flight-tracker/{fno[:2]}/{fno[2:]}?year={y}&month={m}&date={d}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"})
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    j = json.loads(re.search(r'__NEXT_DATA__ = (\{.*?\});\s*__NEXT_LOADED', h, re.S).group(1))
    f = j["props"]["initialState"]["flightTracker"]["flight"]
    st = f.get("status") or {}
    dep = f.get("departureAirport") or {}
    return {"gate": dep.get("gate") or "", "term": dep.get("terminal") or "", "status": st.get("status") or "", "desc": st.get("statusDescription") or ""}
FSR = {}
for fno, (y, m, d) in FS.items():
    try: FSR[fno] = flightstats(fno, y, m, d); print("FS", fno, FSR[fno])
    except Exception as e: print("FS fail", fno, e)
for fno, day in FLIGHTS.items():
    try:
        rows = [r for r in fetch(day, fno[:2]) if r.get("fnumber") == fno]
    except Exception as e:
        print("fetch fail", fno, e); continue
    r = rows[0] if rows else {}
    st, et = r.get("stime", ""), r.get("etime", "")
    status = r.get("stattxt") or ""
    note = []
    if r.get("chkinrange"): note.append("체크인 " + r["chkinrange"])
    if et and st and et != st: status = status or "지연"; note.append(f"예정 {st} → 변경 {et}")
    fs = FSR.get(fno, {})
    gate = r.get("gatenumber", "") or fs.get("gate", "")
    if not r.get("gatenumber") and fs.get("gate"): note.append("게이트는 FlightStats 기준 (공항 발표 전 예정)")
    if fs.get("desc") and fs["desc"] != "On time": status = status or fs["desc"]
    new = {"gate": gate, "status": status, "time": et or st, "note": " · ".join(note),
           "at": now.strftime("%m/%d %H:%M"), "src": "인천공항" if r.get("gatenumber") else ("FlightStats" if gate else "")}
    old = live.get(fno, {})
    if {k: v for k, v in new.items() if k != "at"} != {k: v for k, v in old.items() if k != "at"}:
        live[fno] = new; changed = True
    print(fno, new)
for fno in FS:
    if fno in FLIGHTS or fno not in FSR: continue
    fs = FSR[fno]; old = live.get(fno, {})
    new = {"gate": fs["gate"], "status": "" if fs["desc"] in ("On time", "") else fs["desc"], "time": "", "note": ("터미널 " + fs["term"]) if fs["term"] else "", "at": now.strftime("%m/%d %H:%M"), "src": "FlightStats" if fs["gate"] else ""}
    if {k: v for k, v in new.items() if k != "at"} != {k: v for k, v in old.items() if k != "at"}:
        live[fno] = new; changed = True
    print(fno, new)
if changed:
    json.dump(live, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print("changed")
