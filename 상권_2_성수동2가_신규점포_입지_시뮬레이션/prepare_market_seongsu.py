"""
성수역 상권의 '슈퍼마켓' 실제 매출·점포 데이터(2025년 1~4분기)를 정리해 data/market_seongsu.json 으로 저장한다.
API 호출 없음. 판정·보정 방식은 팀원의 7_store_entry_simulation(estimate_entry.py)과 같게 맞췄다.

입력 (data/raw/, 서울시 원본에서 성수역·성수동카페거리 슈퍼마켓 행만 추출해 둔 것):
- seongsu_sales_supermarket_2025_raw.csv       서울시 상권분석서비스(추정매출-상권) OA-15572, 2025년
- seongsu_store_counts_supermarket_2025_raw.csv 서울시 상권분석서비스(점포-상권) OA-15577, 2025년

기준 상권은 '성수역'(상권코드 3120052)이다. 성수동카페거리(3110131)는 같은 해 슈퍼마켓 매출이 1.2억원, 결제 4,992건,
객단가 23,432원으로 점포 13곳 규모와 맞지 않아(점포당 약 900만원) 보정 기준으로 쓰지 않았다.
점포 수는 팀원과 같이 similr_induty_stor_co(분기 평균)를 쓴다.
"""
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "market_seongsu.json"
CODE, NAME, INDUSTRY = 3120052, "성수역", "슈퍼마켓"
QUARTERS = [20251, 20252, 20253, 20254]
TIMES = ["00-06", "06-11", "11-14", "14-17", "17-21", "21-24"]
AGES = ["10대", "20대", "30대", "40대", "50대", "60대+"]
T_AMT = ["시간대_00~06_매출_금액", "시간대_06~11_매출_금액", "시간대_11~14_매출_금액",
         "시간대_14~17_매출_금액", "시간대_17~21_매출_금액", "시간대_21~24_매출_금액"]
T_CNT = ["시간대_건수~06_매출_건수", "시간대_건수~11_매출_건수", "시간대_건수~14_매출_건수",
         "시간대_건수~17_매출_건수", "시간대_건수~21_매출_건수", "시간대_건수~24_매출_건수"]  # 원본 컬럼명 그대로
A_CNT = ["연령대_10_매출_건수", "연령대_20_매출_건수", "연령대_30_매출_건수", "연령대_40_매출_건수",
         "연령대_50_매출_건수", "연령대_60_이상_매출_건수"]


def pct(v):
    t = sum(v)
    return [round(x / t * 100, 2) for x in v]


def main():
    sales = pd.read_csv(RAW / "seongsu_sales_supermarket_2025_raw.csv", encoding="utf-8-sig")
    stores = pd.read_csv(RAW / "seongsu_store_counts_supermarket_2025_raw.csv", encoding="utf-8-sig")
    d = sales[(sales["상권_코드"] == CODE) & sales["기준_년분기_코드"].isin(QUARTERS)]
    st = stores[(stores["trdar_cd"] == CODE) & stores["stdr_yyqu_cd"].isin(QUARTERS)]
    assert len(d) == 4 and len(st) == 4, "2025년 4개 분기가 모두 있어야 함"
    s = d.sum(numeric_only=True)
    n_stores = round(st["similr_induty_stor_co"].mean(), 2)
    amount, count = int(s["당월_매출_금액"]), int(s["당월_매출_건수"])
    tc, ta = [s[c] for c in T_CNT], [s[c] for c in T_AMT]
    facts = {
        "district_code": CODE, "district_name": NAME, "industry": INDUSTRY, "period": "2025년 1~4분기 합계",
        "source": {"sales": "서울시 상권분석서비스(추정매출-상권) OA-15572", "stores": "서울시 상권분석서비스(점포-상권) OA-15577"},
        "stores": n_stores,
        "stores_by_quarter": {str(r.stdr_yyqu_cd): int(r.similr_induty_stor_co) for r in st.itertuples()},
        "sales_amount_2025": amount, "transactions_2025": count, "avg_ticket": round(amount / count),
        "sales_per_store_2025": round(amount / n_stores), "transactions_per_store_2025": round(count / n_stores),
        "time": {t: {"transactions": int(c), "amount": int(a), "tx_pct": p, "avg_ticket": round(a / c)}
                 for t, c, a, p in zip(TIMES, tc, ta, pct(tc))},
        "age_tx_pct": dict(zip(AGES, pct([s[c] for c in A_CNT]))),
        "gender_tx_pct": dict(zip(["남", "여"], pct([s["남성_매출_건수"], s["여성_매출_건수"]]))),
    }
    OUT.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{NAME} {INDUSTRY}: 점포 {n_stores} | 매출 {amount:,}원 | 결제 {count:,}건 | 객단가 {facts['avg_ticket']:,}원 | 점포당 연매출 {facts['sales_per_store_2025']:,}원")
    for t in TIMES:
        x = facts["time"][t]
        print(f"  {t}: {x['transactions']:,}건 ({x['tx_pct']}%) 객단가 {x['avg_ticket']:,}")
    print("  연령:", facts["age_tx_pct"], "성별:", facts["gender_tx_pct"])


if __name__ == "__main__":
    main()
