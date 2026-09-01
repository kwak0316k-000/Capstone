"""
코엑스 상권 유동인구 LLM-persona 시뮬레이션
=========================================
Google Colab 또는 VS Code(로컬)에서 실행하세요. (Claude.ai 코드 샌드박스는 네트워크가
막혀 있어 huggingface.co / 무료 LLM API에 접근할 수 없기 때문에, 실제 실행은 이 스크립트를
사용자 환경에서 돌려야 합니다.)

파이프라인
----------
1. nvidia/Nemotron-Personas-Korea (HuggingFace, 1,000,000명) 페르소나를 스트리밍으로 불러옴
2. 무작위 순서로 한 명씩 꺼내, 무료 LLM API(Groq, 기본값)에게
   "이 사람이 코엑스 상권에 갈지 안 갈지"를 페르소나 설명 + 상권 정보를 주고 물어봄
3. "간다"(YES) 응답이 TARGET_ACCEPT(기본 100)명이 될 때까지 반복
4. 수락자들의 연령대/성별/시간대 비율을 서울시 상권분석서비스 실제 데이터와 비교, MAE 계산

사전 준비
---------
pip install datasets requests pandas tqdm

무료 LLM API 키 발급 (아무거나 하나 선택):
  - Groq (추천, 매우 빠르고 무료 티어 넉넉함): https://console.groq.com/keys
  - Google AI Studio(Gemini 무료 티어): https://aistudio.google.com/apikey

Colab이라면 왼쪽 열쇠 아이콘(Secrets)에 GROQ_API_KEY를 등록하거나,
아래 CONFIG 섹션에 직접 문자열로 붙여넣으세요.
"""

import os
import re
import json
import time
import random
import unicodedata
from datetime import datetime

import requests
import pandas as pd
from tqdm import tqdm

# =========================================================
# 0. CONFIG — 여기만 채우면 됩니다
# =========================================================

# --- 서울시 상권분석서비스 CSV 경로 (실제 비교용 ground-truth) ---
# data.seoul.go.kr/dataList/OA-15568 에서 내려받은 파일 경로를 지정하세요.
SEOUL_CSV_PATH = "서울시_상권분석서비스_길단위인구-상권_.csv"
SEOUL_CSV_ENCODING = "cp949"  # 원본 CSV 인코딩 (한글 깨질 경우 "euc-kr"로 변경)
TARGET_DISTRICT_NAME = "코엑스"
TARGET_QUARTER = 20261  # 기준_년분기_코드 (예: 2026년 1분기)

# --- LLM API 설정 ---
API_PROVIDER = "groq"  # "groq" 또는 "gemini"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "여기에_발급받은_키_입력")
GROQ_MODEL = "llama-3.1-8b-instant"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "여기에_발급받은_키_입력")
GEMINI_MODEL = "gemini-2.0-flash"

# --- 시뮬레이션 파라미터 ---
TARGET_ACCEPT = 100          # 수락(간다)이 몇 명 채워질 때까지 반복할지
MAX_ASK = 20000              # 안전장치: 최대 질의 횟수 (무한루프 방지)
REQUEST_SLEEP_SEC = 0.05     # API 호출 사이 최소 대기 시간 (rate limit 보호)
SAVE_PATH = "coex_llm_persona_results.csv"  # 중간 저장 파일 (재실행 시 이어서 진행 가능)

# 코엑스 상권 설명 (2번 항목: 매장 유형별 지도 데이터를 반영해 프롬프트에 포함)
DISTRICT_DESCRIPTION = """
[상권명] 코엑스 (서울 강남구 삼성동, 발달상권)
[특징] 대형 컨벤션센터 + 복합쇼핑몰(스타필드 코엑스몰), 테헤란로 오피스 밀집지 인근
[대표 매장]
- 마트/식품관: 현대백화점 트레이드점 지하 식품관
- 편의점: emart24 코엑스몰점, 세븐일레븐 아셈타워점
- 카페: %Arabica, Terarosa Coffee, Gabaedo Coex(티라미수 유명)
- 영화관: 메가박스 코엑스 (한국 최초 멀티플렉스)
- 호텔: 오크우드 프리미어 코엑스센터, GLAD 강남 코엑스센터
- 면세점: 롯데면세점 코엑스, 현대면세점 무역센터점
- 체험시설: SEA LIFE 코엑스 아쿠아리움 (별도 테마파크는 없음)
- 백화점: 현대백화점 무역센터점
[영업시간 특징] 대부분 10:30~22:00, 일부 편의점/식당 24시간
""".strip()


# =========================================================
# 1. 서울시 상권분석서비스 CSV → 실제 비율(ground truth) 계산
# =========================================================

def load_actual_percentages():
    df = pd.read_csv(SEOUL_CSV_PATH, encoding=SEOUL_CSV_ENCODING)
    row = df[
        (df["상권_코드_명"] == TARGET_DISTRICT_NAME)
        & (df["기준_년분기_코드"] == TARGET_QUARTER)
    ].iloc[0]

    total = row["총_유동인구_수"]
    age_cols = {
        "10대": "연령대_10_유동인구_수", "20대": "연령대_20_유동인구_수",
        "30대": "연령대_30_유동인구_수", "40대": "연령대_40_유동인구_수",
        "50대": "연령대_50_유동인구_수", "60대+": "연령대_60_이상_유동인구_수",
    }
    gender_cols = {"남": "남성_유동인구_수", "여": "여성_유동인구_수"}
    time_cols = {
        "00-06": "시간대_00_06_유동인구_수", "06-11": "시간대_06_11_유동인구_수",
        "11-14": "시간대_11_14_유동인구_수", "14-17": "시간대_14_17_유동인구_수",
        "17-21": "시간대_17_21_유동인구_수", "21-24": "시간대_21_24_유동인구_수",
    }
    return {
        "total": int(total),
        "age": {k: round(row[v] / total * 100, 2) for k, v in age_cols.items()},
        "gender": {k: round(row[v] / total * 100, 2) for k, v in gender_cols.items()},
        "time": {k: round(row[v] / total * 100, 2) for k, v in time_cols.items()},
    }


# =========================================================
# 2. Nemotron-Personas-Korea 로드 (스트리밍 — 전체를 다운로드하지 않음)
# =========================================================

def stream_shuffled_personas(buffer_size=50_000, seed=None):
    """1,000,000행 데이터셋을 스트리밍 + 셔플하여 순서대로 한 명씩 반환."""
    from datasets import load_dataset

    seed = seed or random.randint(0, 10_000_000)
    ds = load_dataset("nvidia/Nemotron-Personas-Korea", split="train", streaming=True)
    ds = ds.shuffle(seed=seed, buffer_size=buffer_size)
    for row in ds:
        yield row


AGE_BAND_ORDER = ["10대", "20대", "30대", "40대", "50대", "60대+"]


def age_to_band(age: int) -> str:
    if age < 20:
        return "10대"
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    if age < 60:
        return "50대"
    return "60대+"


def sex_to_kr(sex: str) -> str:
    return "남" if sex == "남자" else "여"


# =========================================================
# 3. LLM 호출 — "코엑스에 갈래말래?" + 방문 시간대
# =========================================================

PROMPT_TEMPLATE = """당신은 아래 페르소나 그 자체가 되어 1인칭이 아닌 3인칭 관점에서 행동을 판단합니다.

[페르소나]
{persona_bio}
- 성별: {sex}, 나이: {age}세, 거주지: {district}, 직업: {occupation}

[상권 정보]
{district_desc}

[질문]
오늘 이 사람이 특별한 목적 없이 여가 시간에 위 상권(코엑스)에 방문할 가능성이 있습니까?
페르소나의 나이, 직업, 거주지, 취미, 소비 성향을 종합적으로 고려해 현실적으로 판단하세요.

다음 JSON 형식으로만 답하세요. 다른 텍스트는 절대 포함하지 마세요:
{{"decision": "YES 또는 NO", "time_slot": "간다면 방문할 가능성이 가장 높은 시간대 하나 (00-06/06-11/11-14/14-17/17-21/21-24 중 선택, 안 간다면 null)"}}
"""


def call_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 100,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def call_llm(prompt: str) -> str:
    if API_PROVIDER == "groq":
        return call_groq(prompt)
    elif API_PROVIDER == "gemini":
        return call_gemini(prompt)
    raise ValueError(f"알 수 없는 API_PROVIDER: {API_PROVIDER}")


def parse_decision(raw_text: str):
    """LLM 응답에서 JSON만 뽑아 파싱. 실패 시 None 반환."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        decision = str(obj.get("decision", "")).strip().upper()
        time_slot = obj.get("time_slot")
        if decision not in ("YES", "NO"):
            return None
        return decision, (time_slot if decision == "YES" else None)
    except json.JSONDecodeError:
        return None


# =========================================================
# 4. 메인 시뮬레이션 루프
# =========================================================

def run_simulation():
    accepted_rows = []
    n_asked = 0

    # 이어서 실행 지원: 기존 저장 파일 있으면 로드
    if os.path.exists(SAVE_PATH):
        prev = pd.read_csv(SAVE_PATH)
        accepted_rows = prev.to_dict("records")
        print(f"[재시작] 기존 결과 {len(accepted_rows)}건 불러옴")

    pbar = tqdm(total=TARGET_ACCEPT, initial=len(accepted_rows), desc="수락자 수집")

    for persona in stream_shuffled_personas():
        if len(accepted_rows) >= TARGET_ACCEPT or n_asked >= MAX_ASK:
            break

        age = persona["age"]
        sex = persona["sex"]
        district = f"{persona['province']}-{persona['district']}"
        occupation = persona["occupation"]
        persona_bio = persona["persona"]  # 42~174자 짧은 요약 페르소나 필드

        prompt = PROMPT_TEMPLATE.format(
            persona_bio=persona_bio,
            sex=sex, age=age, district=district, occupation=occupation,
            district_desc=DISTRICT_DESCRIPTION,
        )

        n_asked += 1
        try:
            raw = call_llm(prompt)
            parsed = parse_decision(raw)
        except Exception as e:
            print(f"[경고] API 호출 실패, 스킵: {e}")
            time.sleep(1.0)
            continue

        if parsed is None:
            continue  # 파싱 실패한 응답은 버리고 다음 사람으로

        decision, time_slot = parsed
        if decision == "YES":
            accepted_rows.append({
                "age": age,
                "age_band": age_to_band(age),
                "sex": sex_to_kr(sex),
                "district": district,
                "occupation": occupation,
                "time_slot": time_slot,
            })
            pbar.update(1)
            # 중간 저장 (10명마다)
            if len(accepted_rows) % 10 == 0:
                pd.DataFrame(accepted_rows).to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")

        time.sleep(REQUEST_SLEEP_SEC)

    pbar.close()
    pd.DataFrame(accepted_rows).to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")
    print(f"\n완료: 질의 {n_asked}회 중 수락 {len(accepted_rows)}명 "
          f"(수락률 {len(accepted_rows)/max(n_asked,1)*100:.2f}%)")
    return pd.DataFrame(accepted_rows), n_asked


# =========================================================
# 5. 실제 데이터 vs 시뮬레이션 비교 (요청하신 표 형식)
# =========================================================

def compare_and_print(sim_df: pd.DataFrame, actual: dict):
    def pct_table(sim_counts: pd.Series, actual_dict: dict, order):
        sim_pct = (sim_counts / sim_counts.sum() * 100).reindex(order).fillna(0).round(2)
        rows, errs = [], []
        for k in order:
            a, s = actual_dict[k], sim_pct[k]
            e = round(abs(a - s), 2)
            rows.append((k, a, s, e))
            errs.append(e)
        return rows, round(sum(errs) / len(errs), 2)

    age_rows, age_mae = pct_table(sim_df["age_band"].value_counts(), actual["age"], AGE_BAND_ORDER)
    gender_rows, gender_mae = pct_table(sim_df["sex"].value_counts(), actual["gender"], ["남", "여"])
    time_rows, time_mae = pct_table(
        sim_df["time_slot"].value_counts(), actual["time"],
        ["00-06", "06-11", "11-14", "14-17", "17-21", "21-24"]
    )

    def show(name, rows, mae):
        print(f"\n== {name} ==")
        print(f"{'구분':<8}{'실제(%)':<10}{'시뮬(%)':<10}{'오차(%p)':<10}")
        for k, a, s, e in rows:
            print(f"{k:<8}{a:<10}{s:<10}{e:<10}")
        print(f"MAE: {mae}")

    show("연령대", age_rows, age_mae)
    show("성별", gender_rows, gender_mae)
    show("시간대", time_rows, time_mae)


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":
    print(f"[{datetime.now()}] 실제 데이터 로드 중...")
    actual = load_actual_percentages()
    print(f"대상 상권: {TARGET_DISTRICT_NAME}, 실제 총 유동인구: {actual['total']:,}명")

    print(f"[{datetime.now()}] 시뮬레이션 시작 (목표 수락 {TARGET_ACCEPT}명)...")
    sim_df, n_asked = run_simulation()

    if len(sim_df) > 0:
        compare_and_print(sim_df, actual)
    else:
        print("수락된 페르소나가 없습니다. API 키/네트워크 상태를 확인하세요.")
