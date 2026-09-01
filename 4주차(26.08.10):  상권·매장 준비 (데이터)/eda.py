"""
eda.py — 서울시 상권분석서비스 CSV에서 특정 상권의 유동인구 EDA를 수행합니다.

사용법
------
python eda.py --csv "서울시_상권분석서비스_길단위인구-상권_.csv" --district 코엑스 --quarter 20261

출력
----
- 콘솔에 연령대/성별/시간대 비율, 분기별 총 유동인구 추이를 출력합니다.
- results/actual_pct.json 에 실제 비율을 저장합니다. (simulation_baseline.py, 비교 단계에서 사용)
- results/quarterly_trend.csv 에 분기별 추이를 저장합니다.
"""

import argparse
import json
import os

import pandas as pd


AGE_COLS = {
    "10대": "연령대_10_유동인구_수", "20대": "연령대_20_유동인구_수",
    "30대": "연령대_30_유동인구_수", "40대": "연령대_40_유동인구_수",
    "50대": "연령대_50_유동인구_수", "60대+": "연령대_60_이상_유동인구_수",
}
GENDER_COLS = {"남": "남성_유동인구_수", "여": "여성_유동인구_수"}
TIME_COLS = {
    "00-06": "시간대_00_06_유동인구_수", "06-11": "시간대_06_11_유동인구_수",
    "11-14": "시간대_11_14_유동인구_수", "14-17": "시간대_14_17_유동인구_수",
    "17-21": "시간대_17_21_유동인구_수", "21-24": "시간대_21_24_유동인구_수",
}


def parse_args():
    p = argparse.ArgumentParser(description="상권 유동인구 EDA")
    p.add_argument("--csv", required=True, help="서울시 상권분석서비스 CSV 경로")
    p.add_argument("--encoding", default="cp949", help="CSV 인코딩 (기본 cp949, 필요시 euc-kr)")
    p.add_argument("--district", required=True, help="상권_코드_명 (예: 코엑스)")
    p.add_argument("--quarter", type=int, required=True, help="기준_년분기_코드 (예: 20261)")
    p.add_argument("--outdir", default="results", help="결과 저장 폴더 (기본: results/)")
    return p.parse_args()


def print_table(title, d):
    print(f"\n== {title} ==")
    for k, v in d.items():
        print(f"{k:<8}{v:>8.2f}%")


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    df = pd.read_csv(args.csv, encoding=args.encoding)

    # --- 1) 지정 분기의 실제 비율 계산 ---
    match = df[(df["상권_코드_명"] == args.district) & (df["기준_년분기_코드"] == args.quarter)]
    if match.empty:
        raise SystemExit(
            f"'{args.district}' / {args.quarter} 조합을 CSV에서 찾을 수 없습니다. "
            f"상권_코드_명 철자와 기준_년분기_코드 값을 확인하세요."
        )
    row = match.iloc[0]
    total = row["총_유동인구_수"]

    age_pct = {k: round(row[v] / total * 100, 2) for k, v in AGE_COLS.items()}
    gender_pct = {k: round(row[v] / total * 100, 2) for k, v in GENDER_COLS.items()}
    time_pct = {k: round(row[v] / total * 100, 2) for k, v in TIME_COLS.items()}

    print(f"대상 상권: {args.district} / 기준분기: {args.quarter}")
    print(f"총 유동인구: {int(total):,}명")
    print_table("연령대별 비율", age_pct)
    print_table("성별 비율", gender_pct)
    print_table("시간대별 비율", time_pct)

    actual = {
        "district": args.district,
        "quarter": args.quarter,
        "total": int(total),
        "age": age_pct,
        "gender": gender_pct,
        "time": time_pct,
    }
    out_path = os.path.join(args.outdir, "actual_pct.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(actual, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] {out_path}")

    # --- 2) 해당 상권의 전체 분기 추이 ---
    trend = df[df["상권_코드_명"] == args.district].sort_values("기준_년분기_코드")
    trend_out = trend[["기준_년분기_코드", "총_유동인구_수", "남성_유동인구_수", "여성_유동인구_수"]]
    trend_path = os.path.join(args.outdir, "quarterly_trend.csv")
    trend_out.to_csv(trend_path, index=False, encoding="utf-8-sig")
    print(f"[저장] {trend_path} ({len(trend_out)}개 분기)")


if __name__ == "__main__":
    main()
