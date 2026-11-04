"""성수동 상권 데이터 분석 — 신규 점포 진출 검토용 근거 수치 산출.
입력: 서울시 상권분석서비스 길단위인구-상권 CSV (cp949)
출력: data/analysis_seongsu.json
분석 대상 6곳은 이름으로 직접 골랐다(CSV에 좌표가 없어 지리적 근접성은 확인하지 못함).
"""
import json, sys
import pandas as pd

csv = sys.argv[1] if len(sys.argv) > 1 else "서울시_상권분석서비스_길단위인구-상권_.csv"
d = pd.read_csv(csv, encoding="cp949")
d.columns = [c.replace("_유동인구_수", "").replace("_", "") for c in d.columns]
tc = [c for c in d.columns if c.startswith("총")][0]
Q = 20261
AREAS = ["성수역", "성수동카페거리", "성수대교남단", "서울숲카페거리", "서울숲역", "뚝섬역"]
cur = d[d["기준년분기코드"] == Q].copy()
cur["rank"] = cur[tc].rank(ascending=False).astype(int)
dev = cur[cur["상권구분코드명"] == "발달상권"]
ages = [c for c in d.columns if c.startswith("연령대")]
times = [c for c in d.columns if c.startswith("시간대")]
days = [c for c in d.columns if c.endswith("요일")]

def shares(frame, cols):
    s = frame[cols].sum(); return {c: round(float(s[c]) / float(s.sum()) * 100, 2) for c in cols}
def index(a, b): return {k: round(a[k] / b[k] * 100) for k in a}

sel = cur[cur["상권코드명"].isin(AREAS)]
rows = {}
for a in AREAS:
    r = cur[cur["상권코드명"] == a].iloc[0]
    hist = d[d["상권코드명"] == a].sort_values("기준년분기코드")
    first = float(hist.iloc[0][tc]); last = float(hist.iloc[-1][tc])
    prev = hist[hist["기준년분기코드"] == Q - 10]
    rows[a] = {"구분": r["상권구분코드명"], "유동인구": int(r[tc]), "전체순위": int(r["rank"]),
               "2021Q1대비%": round((last / first - 1) * 100, 1),
               "전년동기대비%": round((last / float(prev.iloc[0][tc]) - 1) * 100, 1) if len(prev) else None,
               "20대+30대비중%": round((r["연령대20"] + r["연령대30"]) / sum(r[c] for c in ages) * 100, 1)}

# 성수 6곳 합산 프로필(비율)과 발달상권 평균 대비 지수
age_s, time_s, day_s = shares(sel, ages), shares(sel, times), shares(sel, days)
age_d, time_d, day_d = shares(dev, ages), shares(dev, times), shares(dev, days)

# 코엑스 비교용
cx = cur[cur["상권코드명"] == "코엑스"].iloc[0]
out = {
    "quarter": Q, "areas": rows, "sum_total": int(sel[tc].sum()),
    "n_all": int(len(cur)), "dev_mean": int(dev[tc].mean()),
    "age": age_s, "age_index": index(age_s, age_d),
    "time": time_s, "time_index": index(time_s, time_d),
    "day": day_s, "day_index": index(day_s, day_d),
    "weekend_share": round(day_s["토요일"] + day_s["일요일"], 2),
    "weekend_share_dev": round(day_d["토요일"] + day_d["일요일"], 2),
    "coex": {"유동인구": int(cx[tc]), "전체순위": int(cur[cur["상권코드명"] == "코엑스"]["rank"].iloc[0])},
}
json.dump(out, open("data/analysis_seongsu.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=1))
