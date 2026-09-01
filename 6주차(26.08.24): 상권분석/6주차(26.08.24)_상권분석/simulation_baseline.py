"""
simulation_baseline.py — 구현체 A: 확률모델(ABM) 기반 유동인구 시뮬레이션

LLM API 없이, 인구통계 가중치 기반 로지스틱 수락확률 모델로 "갈래말래"를
흉내냅니다. 1,000,000명 풀에서 무작위로 한 명씩 꺼내 수락확률을 계산하고,
목표 인원(기본 100명)이 수락할 때까지 반복합니다.

실제 LLM 판단을 반영하려면 coex_persona_simulation.py(구현체 B)를 사용하세요.

사용법
------
python eda.py --csv "서울시_상권분석서비스_길단위인구-상권_.csv" --district 코엑스 --quarter 20261
python simulation_baseline.py --target-accept 100

(eda.py를 먼저 실행해 results/actual_pct.json이 있어야 비교표가 출력됩니다.
 없으면 시뮬레이션 결과만 출력합니다.)
"""

import argparse
import json
import os

import numpy as np
import pandas as pd


AGE_GROUPS = ["10대", "20대", "30대", "40대", "50대", "60대+"]
GENDERS = ["남", "여"]
TIME_SLOTS = ["00-06", "06-11", "11-14", "14-17", "17-21", "21-24"]

# 일반 인구 구조에서의 표본 추출 비율 (통계청 인구구조 근사치 — 상권 방문 성향과 무관하게 독립 설정)
AGE_POOL_P = [0.08, 0.11, 0.13, 0.16, 0.18, 0.34]
GENDER_POOL_P = [0.495, 0.505]

# 코엑스 상권 "매력도" 가중치 — 정성적 가정으로 사전에 독립 설정 (실제 비율에 맞춰 역산하지 않음)
AGE_LOGIT = {"10대": 0.6, "20대": 2.6, "30대": 2.8, "40대": 1.6, "50대": 0.3, "60대+": -0.9}
GENDER_LOGIT = {"남": 0.0, "여": 0.18}
BASE_LOGIT = -4.6

BASE_TIME_P = np.array([0.05, 0.18, 0.24, 0.25, 0.22, 0.06])
YOUNG_SHIFT = np.array([-0.01, -0.03, -0.02, 0.00, 0.05, 0.01])   # 20~30대: 저녁 선호 ↑
OLDER_SHIFT = np.array([0.00, 0.02, 0.03, 0.02, -0.05, -0.02])    # 40대+: 낮 시간 선호 ↑


def parse_args():
    p = argparse.ArgumentParser(description="확률모델 기반 유동인구 시뮬레이션")
    p.add_argument("--pool-size", type=int, default=1_000_000, help="가상인간 풀 크기 (기본 100만)")
    p.add_argument("--target-accept", type=int, default=100, help="목표 수락 인원 (기본 100)")
    p.add_argument("--max-ask", type=int, default=200_000, help="최대 질의 횟수 (무한루프 방지)")
    p.add_argument("--seed", type=int, default=42, help="난수 시드 (재현성)")
    p.add_argument("--actual-pct", default="results/actual_pct.json",
                    help="eda.py가 생성한 실제 비율 JSON 경로")
    p.add_argument("--outdir", default="results", help="결과 저장 폴더")
    return p.parse_args()


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def run_simulation(rng, pool_size, target_accept, max_ask):
    pool_age = rng.choice(AGE_GROUPS, size=pool_size, p=AGE_POOL_P)
    pool_gender = rng.choice(GENDERS, size=pool_size, p=GENDER_POOL_P)

    accepted_age, accepted_gender = [], []
    idx_pool = rng.permutation(pool_size)
    asked = 0

    for i in idx_pool:
        if len(accepted_age) >= target_accept or asked >= max_ask:
            break
        a, g = pool_age[i], pool_gender[i]
        logit = BASE_LOGIT + AGE_LOGIT[a] + GENDER_LOGIT[g]
        p_accept = sigmoid(logit)
        asked += 1
        if rng.random() < p_accept:
            accepted_age.append(a)
            accepted_gender.append(g)

    # 시간대 배정
    accepted_time = []
    for a in accepted_age:
        p = BASE_TIME_P.copy()
        if a in ("20대", "30대"):
            p = p + YOUNG_SHIFT
        elif a in ("40대", "50대", "60대+"):
            p = p + OLDER_SHIFT
        p = np.clip(p, 0.001, None)
        p = p / p.sum()
        accepted_time.append(rng.choice(TIME_SLOTS, p=p))

    sim_df = pd.DataFrame({"age": accepted_age, "gender": accepted_gender, "time": accepted_time})
    return sim_df, asked


def compare(sim_df, actual):
    def table(sim_series, actual_dict, order):
        pct = (sim_series.value_counts(normalize=True) * 100).reindex(order).fillna(0).round(2)
        rows, errs = [], []
        for k in order:
            a, s = actual_dict[k], pct[k]
            e = round(abs(a - s), 2)
            rows.append({"구분": k, "실제(%)": a, "시뮬(%)": float(s), "오차(%p)": e})
            errs.append(e)
        return rows, round(sum(errs) / len(errs), 2)

    age_rows, age_mae = table(sim_df["age"], actual["age"], AGE_GROUPS)
    gender_rows, gender_mae = table(sim_df["gender"], actual["gender"], GENDERS)
    time_rows, time_mae = table(sim_df["time"], actual["time"], TIME_SLOTS)
    return {
        "age": {"rows": age_rows, "mae": age_mae},
        "gender": {"rows": gender_rows, "mae": gender_mae},
        "time": {"rows": time_rows, "mae": time_mae},
    }


def print_comparison(name, block):
    print(f"\n== {name} (MAE {block['mae']}%p) ==")
    print(f"{'구분':<8}{'실제(%)':<10}{'시뮬(%)':<10}{'오차(%p)':<10}")
    for r in block["rows"]:
        print(f"{r['구분']:<8}{r['실제(%)']:<10}{r['시뮬(%)']:<10}{r['오차(%p)']:<10}")


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    sim_df, asked = run_simulation(rng, args.pool_size, args.target_accept, args.max_ask)
    accept_rate = len(sim_df) / max(asked, 1) * 100

    sim_path = os.path.join(args.outdir, "simulated_visitors.csv")
    sim_df.to_csv(sim_path, index=False, encoding="utf-8-sig")

    print(f"가상인간 풀: {args.pool_size:,}명 / 질의 {asked:,}회 / 수락 {len(sim_df)}명 "
          f"(수락률 {accept_rate:.3f}%)")
    print(f"[저장] {sim_path}")

    if not os.path.exists(args.actual_pct):
        print(f"\n[안내] {args.actual_pct} 가 없어 실제 데이터와의 비교는 건너뜁니다. "
              f"먼저 eda.py를 실행하세요.")
        return

    with open(args.actual_pct, encoding="utf-8") as f:
        actual = json.load(f)

    comparison = compare(sim_df, actual)
    for name_kr, key in [("연령대", "age"), ("성별", "gender"), ("시간대", "time")]:
        print_comparison(name_kr, comparison[key])

    comp_path = os.path.join(args.outdir, "comparison_tables.json")
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump({
            "district": actual.get("district"),
            "quarter": actual.get("quarter"),
            "pool_size": args.pool_size,
            "n_asked": asked,
            "n_accepted": len(sim_df),
            "accept_rate_pct": round(accept_rate, 3),
            **comparison,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] {comp_path}")


if __name__ == "__main__":
    main()
