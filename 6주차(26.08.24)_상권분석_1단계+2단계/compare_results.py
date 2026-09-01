"""
compare_results.py — 두 시나리오의 오차(MAE)를 비교합니다.

시나리오 A: 확률모델 베이스라인(simulation_baseline.py) 결과에서 10대만 제외하고 재정규화
시나리오 B: 1단계+2단계 LLM-persona 파이프라인(two_step_persona_simulation.py) 결과

둘 다 실제 데이터(10대 제외 정규화된 연령대, 성별, 시간대, 평일/주말)와 비교해
"2단계 프롬프트를 실제로 돌리는 것이 정규화만 하는 것보다 오차를 얼마나 줄이는지" 확인합니다.

사용법
------
python eda_v2.py                                  # actual_pct_v2.json 생성 (JSON 원본 사용)
python simulation_baseline.py --target-accept 100 # 시나리오 A 재료 생성 (이미 있으면 생략 가능)
python two_step_persona_simulation.py              # 시나리오 B 데이터 생성 (네트워크 필요)
python compare_results.py
"""

import json
import os

import pandas as pd

AGE_ORDER = ["20대", "30대", "40대", "50대", "60대+"]
GENDERS = ["남", "여"]
TIMES = ["00-06", "06-11", "11-14", "14-17", "17-21", "21-24"]


def mae(sim_pct: dict, actual_pct: dict, order):
    errs = [abs(actual_pct[k] - sim_pct.get(k, 0.0)) for k in order]
    return round(sum(errs) / len(errs), 2)


def scenario_a(baseline_csv="results/simulated_visitors.csv"):
    """시나리오 A: 확률모델 베이스라인 + 10대만 제외 재정규화 (요일 정보 없음)."""
    if not os.path.exists(baseline_csv):
        return None
    sim = pd.read_csv(baseline_csv)
    sim_excl10 = sim[sim["age"] != "10대"]
    age_pct = (sim_excl10["age"].value_counts(normalize=True) * 100).reindex(AGE_ORDER).fillna(0).round(2).to_dict()
    gender_pct = (sim["gender"].value_counts(normalize=True) * 100).reindex(GENDERS).fillna(0).round(2).to_dict()
    time_pct = (sim["time"].value_counts(normalize=True) * 100).reindex(TIMES).fillna(0).round(2).to_dict()
    return {"age": age_pct, "gender": gender_pct, "time": time_pct, "day": None}


def scenario_b(two_step_csv="results/two_step_results.csv"):
    """시나리오 B: 1단계+2단계 LLM-persona 파이프라인 결과 (요일 포함)."""
    if not os.path.exists(two_step_csv):
        return None
    sim = pd.read_csv(two_step_csv)
    age_pct = (sim["age_band"].value_counts(normalize=True) * 100).reindex(AGE_ORDER).fillna(0).round(2).to_dict()
    gender_pct = (sim["sex"].value_counts(normalize=True) * 100).reindex(GENDERS).fillna(0).round(2).to_dict()
    time_pct = (sim["time_slot"].value_counts(normalize=True) * 100).reindex(TIMES).fillna(0).round(2).to_dict()
    day_pct = (sim["day_type"].value_counts(normalize=True) * 100).reindex(["평일", "주말"]).fillna(0).round(2).to_dict()
    return {"age": age_pct, "gender": gender_pct, "time": time_pct, "day": day_pct}


def print_table(name, sim_pct, actual_pct, order):
    print(f"\n== {name} ==")
    print(f"{'구분':<8}{'실제(%)':<10}{'시뮬(%)':<10}{'오차(%p)':<10}")
    for k in order:
        a = actual_pct[k]
        s = sim_pct.get(k, 0.0)
        print(f"{k:<8}{a:<10}{s:<10}{round(abs(a-s),2):<10}")
    print(f"MAE: {mae(sim_pct, actual_pct, order)}%p")


def main():
    with open("results/actual_pct_v2.json", encoding="utf-8") as f:
        actual = json.load(f)

    a = scenario_a()
    b = scenario_b()

    print("=" * 60)
    print("시나리오 A: 확률모델 베이스라인 + 10대만 제외 정규화 (2단계 프롬프트 미적용)")
    print("=" * 60)
    if a is None:
        print("results/simulated_visitors.csv 가 없습니다. simulation_baseline.py를 먼저 실행하세요.")
    else:
        print_table("연령대(10대 제외)", a["age"], actual["age_excl10"], AGE_ORDER)
        print_table("성별", a["gender"], actual["gender"], GENDERS)
        print_table("시간대", a["time"], actual["time"], TIMES)
        print("\n요일: 확률모델 베이스라인은 요일 차원을 모델링하지 않아 비교 불가")

    print("\n" + "=" * 60)
    print("시나리오 B: 1단계(상권 정성 프로필) + 2단계(LLM 페르소나 판단) 전체 파이프라인")
    print("=" * 60)
    if b is None:
        print("results/two_step_results.csv 가 없습니다. two_step_persona_simulation.py를 먼저 실행하세요 (네트워크 필요).")
    else:
        print_table("연령대(10대 제외)", b["age"], actual["age_excl10"], AGE_ORDER)
        print_table("성별", b["gender"], actual["gender"], GENDERS)
        print_table("시간대", b["time"], actual["time"], TIMES)
        actual_wd_we = {"평일": actual["weekday_weekend"]["평일(5일 합)"], "주말": actual["weekday_weekend"]["주말(2일 합)"]}
        print_table("평일/주말", b["day"], actual_wd_we, ["평일", "주말"])

    if a is not None and b is not None:
        age_mae_a = mae(a["age"], actual["age_excl10"], AGE_ORDER)
        age_mae_b = mae(b["age"], actual["age_excl10"], AGE_ORDER)
        time_mae_a = mae(a["time"], actual["time"], TIMES)
        time_mae_b = mae(b["time"], actual["time"], TIMES)
        print("\n" + "=" * 60)
        print("요약: 2단계 프롬프트 실행이 정규화만 한 것보다 오차를 얼마나 줄였는가")
        print("=" * 60)
        print(f"연령대 MAE:  A(정규화만) {age_mae_a}%p  →  B(2단계 실행) {age_mae_b}%p  "
              f"({'개선' if age_mae_b < age_mae_a else '악화'} {abs(age_mae_a-age_mae_b):.2f}%p)")
        print(f"시간대 MAE:  A(정규화만) {time_mae_a}%p  →  B(2단계 실행) {time_mae_b}%p  "
              f"({'개선' if time_mae_b < time_mae_a else '악화'} {abs(time_mae_a-time_mae_b):.2f}%p)")
        print("요일 MAE:    A는 요일 미모델링(비교 불가) → B만 산출됨")

        summary = {
            "age_mae": {"A_정규화만": age_mae_a, "B_2단계파이프라인": age_mae_b},
            "time_mae": {"A_정규화만": time_mae_a, "B_2단계파이프라인": time_mae_b},
        }
        with open("results/final_comparison_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("\n[저장] results/final_comparison_summary.json")


if __name__ == "__main__":
    main()
