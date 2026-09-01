"""
eda_v2.py — JSON 원본에서 실제 비율(연령대 10대 제외 정규화, 성별, 시간대, 요일)을 계산합니다.
2차 과제(2단계 프롬프트 파이프라인) 비교용 ground truth를 생성합니다.

사용법
------
python eda_v2.py --json "서울시_상권분석서비스_길단위인구-상권_.json" --district 코엑스 --quarter 20261
"""

import argparse
import json
import os


AGE_MAP = {"20대": "agrde_20_flpop_co", "30대": "agrde_30_flpop_co", "40대": "agrde_40_flpop_co",
           "50대": "agrde_50_flpop_co", "60대+": "agrde_60_above_flpop_co"}
TIME_MAP = {"00-06": "tmzon_00_06_flpop_co", "06-11": "tmzon_06_11_flpop_co", "11-14": "tmzon_11_14_flpop_co",
            "14-17": "tmzon_14_17_flpop_co", "17-21": "tmzon_17_21_flpop_co", "21-24": "tmzon_21_24_flpop_co"}
DAY_MAP = {"월": "mon_flpop_co", "화": "tues_flpop_co", "수": "wed_flpop_co", "목": "thur_flpop_co",
           "금": "fri_flpop_co", "토": "sat_flpop_co", "일": "sun_flpop_co"}
WEEKDAYS = ["월", "화", "수", "목", "금"]
WEEKEND = ["토", "일"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True, help="서울시 상권분석서비스 JSON 경로")
    p.add_argument("--district", required=True, help="상권명 (trdar_cd_nm)")
    p.add_argument("--quarter", required=True, help="기준_년분기_코드 (예: 20261)")
    p.add_argument("--outdir", default="results")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    with open(args.json, encoding="utf-8") as f:
        raw = json.load(f)
    matches = [d for d in raw["DATA"] if d["trdar_cd_nm"] == args.district and str(d["stdr_yyqu_cd"]) == str(args.quarter)]
    if not matches:
        raise SystemExit(f"'{args.district}' / {args.quarter} 를 찾을 수 없습니다.")
    row = matches[0]

    age_sum_excl10 = sum(row[v] for v in AGE_MAP.values())
    age_pct = {k: round(row[v] / age_sum_excl10 * 100, 2) for k, v in AGE_MAP.items()}

    gender_pct = {"남": round(row["ml_flpop_co"] / row["tot_flpop_co"] * 100, 2),
                  "여": round(row["fml_flpop_co"] / row["tot_flpop_co"] * 100, 2)}

    time_pct = {k: round(row[v] / row["tot_flpop_co"] * 100, 2) for k, v in TIME_MAP.items()}

    day_sum = sum(row[v] for v in DAY_MAP.values())
    day_pct = {k: round(row[v] / day_sum * 100, 2) for k, v in DAY_MAP.items()}
    weekday_sum = sum(row[DAY_MAP[d]] for d in WEEKDAYS)
    weekend_sum = sum(row[DAY_MAP[d]] for d in WEEKEND)
    wd_we_pct = {"평일(5일 합)": round(weekday_sum / day_sum * 100, 2),
                 "주말(2일 합)": round(weekend_sum / day_sum * 100, 2)}

    result = {
        "district": args.district, "quarter": args.quarter,
        "age_excl10": age_pct, "gender": gender_pct, "time": time_pct,
        "day": day_pct, "weekday_weekend": wd_we_pct,
    }
    out_path = os.path.join(args.outdir, "actual_pct_v2.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[저장] {out_path}")


if __name__ == "__main__":
    main()
