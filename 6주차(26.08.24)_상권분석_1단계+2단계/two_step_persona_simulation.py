"""
two_step_persona_simulation.py — 캡스톤 2차 과제: 2단계 LLM 프롬프트 파이프라인

Google Colab 또는 VS Code(로컬, 네트워크 필요)에서 실행하세요.

파이프라인
----------
[1단계] 상권 정보(장소·업종·운영시간)만으로 "지역 분석가" 관점의 정성적 프로필을 생성
        → 방문객 통계는 절대 언급하지 않음 (실험 오염 방지)
[2단계] Nemotron-Personas-Korea에서 10대를 제외하고 페르소나를 1명씩 추출 →
        1단계 프로필 + 페르소나 정보를 LLM에게 주고 "방문할까? 언제?"를 판단시킴
        → 목표 수락 인원(기본 100명)이 채워질 때까지 반복

과제 스펙과의 차이점 (반드시 확인하세요)
----------------------------------------
과제에 주어진 2단계 출력 스키마는 {"방문", "주요_시간대", "이유"} 3개 필드였습니다.
요일별 분포까지 비교하려면 요일 정보가 필요해서, 아래 STEP2_PROMPT_TEMPLATE에
"요일유형"(평일/주말) 필드를 추가했습니다. 과제 스펙을 엄격히 지켜야 한다면
STEP2_JSON_SCHEMA_NOTE와 파싱 로직에서 이 필드를 제거하고 사용하세요.

사전 준비
---------
pip install -r requirements.txt
Groq API 키: https://console.groq.com/keys
"""

import os
import re
import json
import time
import random
from datetime import datetime

import requests
import pandas as pd
from tqdm import tqdm

# =========================================================
# CONFIG
# =========================================================

API_PROVIDER = "groq"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "여기에_발급받은_키_입력")
GROQ_MODEL = "llama-3.1-8b-instant"

TARGET_ACCEPT = 100
MAX_ASK = 20000
REQUEST_SLEEP_SEC = 0.05
SAVE_PATH = "results/two_step_results.csv"

DISTRICT_NAME = "코엑스"
STEP1_PROFILE_PATH = "results/step1_district_profile_coex.json"  # 미리 생성해둔 1단계 결과 사용


# =========================================================
# 1단계: 상권 정성적 프로필 (이미 생성된 파일을 그대로 로드)
# =========================================================

def load_step1_profile():
    """1단계 프롬프트로 이미 생성해둔 코엑스 프로필을 불러옵니다.
    다른 상권으로 바꾸려면 STEP1_PROMPT_TEMPLATE로 LLM을 호출해 새로 생성하세요."""
    with open(STEP1_PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


STEP1_PROMPT_TEMPLATE = """당신은 한국 상권에 정통한 지역 분석가입니다.
아래 상권에 대해 '일반적으로 알려진 사실'만으로 그 장소의 성격을 정리하세요.

[상권]
- 상권명: {district_name}
- 위치: {location}
- (선택) 대표 업종/장소: {store_list}

[반드시 지킬 규칙]
1. '장소와 업종'만 서술한다: 상권 성격, 대표 업종·장소와 그 운영시간, 사람들이 이곳을 찾는 이유·활동, 요일/시즌 특성.
2. 시간대 특성은 반드시 '평일'과 '주말'을 나누어 서술한다. 업종·장소의 운영시간이 평일/주말에 다르면 그 차이도 함께 적는다.
3. '방문객의 연령·성별·시간대·요일별 분포'나 유동인구 수치는 절대 언급하지 않는다.
4. 구체적 통계·퍼센트를 지어내지 않는다. 정성적 사실만.
5. 잘 모르는 상권이면 모른다고 답하고 지어내지 않는다.

[출력 — JSON만]
{{"상권유형": "...", "대표업종_운영시간": [{{"업종": "...", "운영시간": "..."}}],
 "방문목적": ["..."], "시간특성_이유_평일": "...", "시간특성_이유_주말": "...",
 "요일특성": "...", "한줄요약": "..."}}
"""


# =========================================================
# 2단계: 페르소나 방문 판단
# =========================================================

STEP2_PROMPT_TEMPLATE = """[상권 정보]
{district_summary}
대표 업종/운영시간: {store_hours}
방문목적: {visit_purposes}

[가상 인물]
나이: {age} / 성별: {gender} / 직업: {job} / 취미·성향: {persona_text}

위 '상권 정보'와 '인물 특성'을 함께 고려해, 이 인물이 향후 30일 내 이 상권을 방문할지,
방문한다면 주로 몇 시경일지, 평일과 주말 중 언제일 가능성이 높은지 판단하세요.
※ 상권 정보는 '이곳이 어떤 장소인지'에 대한 설명일 뿐입니다. 인물의 성향에 비추어
  방문 여부와 시간대를 스스로 추론하세요.

다음 JSON 형식으로만 답하세요. 다른 텍스트는 절대 포함하지 마세요:
{{"방문": "예 또는 아니오",
  "주요_시간대": "방문한다면 00-06/06-11/11-14/14-17/17-21/21-24 중 하나, 아니면 null",
  "요일유형": "방문한다면 평일 또는 주말 중 하나, 아니면 null",
  "이유": "간단한 판단 근거"}}
"""
# ↑ "요일유형" 필드는 요일별 분포 비교를 위해 저희가 추가한 필드입니다 (과제 원본 스키마에는 없음).


AGE_BAND_ORDER = ["20대", "30대", "40대", "50대", "60대+"]  # 10대 제외


def age_to_band(age: int):
    if age < 20:
        return None  # 10대 제외
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


def stream_shuffled_personas(buffer_size=50_000, seed=None):
    from datasets import load_dataset
    seed = seed or random.randint(0, 10_000_000)
    ds = load_dataset("nvidia/Nemotron-Personas-Korea", split="train", streaming=True)
    ds = ds.shuffle(seed=seed, buffer_size=buffer_size)
    for row in ds:
        yield row


def call_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7, "max_tokens": 200}
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_llm(prompt: str) -> str:
    if API_PROVIDER == "groq":
        return call_groq(prompt)
    raise ValueError(f"지원하지 않는 API_PROVIDER: {API_PROVIDER}")


def parse_step2(raw_text: str):
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        visit = str(obj.get("방문", "")).strip()
        if visit not in ("예", "아니오"):
            return None
        time_slot = obj.get("주요_시간대") if visit == "예" else None
        day_type = obj.get("요일유형") if visit == "예" else None
        return visit, time_slot, day_type
    except json.JSONDecodeError:
        return None


def build_step2_prompt(profile, persona):
    store_hours = "; ".join(f"{s['업종']}({s['운영시간']})" for s in profile["대표업종_운영시간"])
    return STEP2_PROMPT_TEMPLATE.format(
        district_summary=profile["한줄요약"],
        store_hours=store_hours,
        visit_purposes=", ".join(profile["방문목적"]),
        age=persona["age"], gender=persona["sex"],
        job=persona["occupation"], persona_text=persona["persona"],
    )


# =========================================================
# 메인 루프
# =========================================================

def run():
    os.makedirs("results", exist_ok=True)
    profile = load_step1_profile()

    accepted_rows = []
    if os.path.exists(SAVE_PATH):
        accepted_rows = pd.read_csv(SAVE_PATH).to_dict("records")
        print(f"[재시작] 기존 결과 {len(accepted_rows)}건 불러옴")

    n_asked = 0
    pbar = tqdm(total=TARGET_ACCEPT, initial=len(accepted_rows), desc="수락자 수집")

    for persona in stream_shuffled_personas():
        if len(accepted_rows) >= TARGET_ACCEPT or n_asked >= MAX_ASK:
            break

        age_band = age_to_band(persona["age"])
        if age_band is None:  # 10대 제외 (사전 필터링)
            continue

        prompt = build_step2_prompt(profile, persona)
        n_asked += 1
        try:
            raw = call_llm(prompt)
            parsed = parse_step2(raw)
        except Exception as e:
            print(f"[경고] API 호출 실패, 스킵: {e}")
            time.sleep(1.0)
            continue

        if parsed is None:
            continue

        visit, time_slot, day_type = parsed
        if visit == "예":
            accepted_rows.append({
                "age": persona["age"], "age_band": age_band,
                "sex": sex_to_kr(persona["sex"]),
                "time_slot": time_slot, "day_type": day_type,
            })
            pbar.update(1)
            if len(accepted_rows) % 10 == 0:
                pd.DataFrame(accepted_rows).to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")

        time.sleep(REQUEST_SLEEP_SEC)

    pbar.close()
    pd.DataFrame(accepted_rows).to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")
    print(f"\n완료: 10대 제외 질의 {n_asked}회 중 수락 {len(accepted_rows)}명 "
          f"(수락률 {len(accepted_rows)/max(n_asked,1)*100:.2f}%)")
    return pd.DataFrame(accepted_rows)


if __name__ == "__main__":
    print(f"[{datetime.now()}] 2단계 파이프라인 시작 — 대상 상권: {DISTRICT_NAME}")
    df = run()
    if len(df):
        print("\n연령대 분포:\n", (df["age_band"].value_counts(normalize=True)*100).round(2))
        print("\n성별 분포:\n", (df["sex"].value_counts(normalize=True)*100).round(2))
        print("\n시간대 분포:\n", (df["time_slot"].value_counts(normalize=True)*100).round(2))
        print("\n평일/주말 분포:\n", (df["day_type"].value_counts(normalize=True)*100).round(2))
        print("\n비교표는 compare_results.py를 실행해 확인하세요.")
