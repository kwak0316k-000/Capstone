"""
multi_agent_simulation.py — 3인 페르소나가 각자 독립된 LLM 호출로 대화하는
멀티 에이전트 시뮬레이션 (2주차 과제 원 설계 그대로: "colab, LLM(상용 API, 3B 로컬)")

WEEK2_SIMULATION.md의 대화는 Claude 하나가 3명을 전부 연기해서 작성한 것이라,
"조율된 그럴듯함"이 있을 수 있습니다. 이 스크립트는 각 페르소나를 정말로 독립된
API 호출(각자 자기 프로필만 아는 상태)로 분리해, 진짜 에이전트 간 상호작용이
얼마나 자연스러운지/일관되는지 확인합니다.

사용법
------
pip install requests
export GROQ_API_KEY="발급받은_키"
python multi_agent_simulation.py
"""

import os
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "여기에_키_입력")
GROQ_MODEL = "llama-3.1-8b-instant"  # 3B 로컬 모델(예: Ollama llama3.2:3b)로 교체 가능

SITUATION = "이번 주, 세 사람이 각자 사는 동네 근처에 대형 복합 쇼핑몰이 새로 생겼다."

PERSONAS = {
    "김소희": {
        "profile": (
            "33세 여성, 육군 부사관(현역), 대전 유성구 거주, 친구들과 아파트 비친족 동거. "
            "평일엔 격무, 주말엔 침대에서 웹툰 정주행·낮잠·베란다 몬스테라 원예로 완전히 이완. "
            "주 5회 이상 외식, 특히 둔산동 이탈리안 레스토랑의 크림파스타를 가장 좋아함. "
            "주 2~3회 배달 야식. 유성구 인근 소규모 갤러리 탐방도 즐김."
        ),
    },
    "김재성": {
        "profile": (
            "22세 남성, 4년제 대학교 언론학 전공, 무직(취업준비생), 서울 송파구 거주, 부모님과 아파트 거주. "
            "LCK e스포츠 시청에 깊이 몰입(주말마다). 송파구 일대 돈카츠·라멘 맛집을 꿰고 있고, "
            "배달 음식 시킬 때 리뷰를 집요하게 분석함. 엑셀/메모 앱으로 낭비 없는 이동 경로를 설계하는 습관."
        ),
    },
    "최수민": {
        "profile": (
            "21세 여성, 2~3년제 전문대졸, 구직 중(전직 비서), 서울 동대문구 거주, 독립해 아파트 1인 가구. "
            "주말엔 대학로 소극장 연극 관람 후 근처에서 트러플 뇨끼를 즐김. 넷플릭스 독립영화 감상. "
            "빽빽한 일정표보다 그날 기분에 따라 발길 닿는 대로 움직이는 여행/외출 스타일. 소품샵 구경을 좋아함."
        ),
    },
}

SYSTEM_TEMPLATE = """당신은 아래 페르소나 그 자체입니다. 1인칭으로, 이 사람의 말투와 성향을 살려 카카오톡 단톡방에 메시지를 보내세요.

[내 페르소나]
{profile}

[상황]
{situation}

[규칙]
- 반드시 이 페르소나의 실제 취향·직업·생활 패턴에 근거해서만 반응하세요. 페르소나에 없는 취향을 지어내지 마세요.
- 실제로 취할 행동이 있다면 메시지 끝에 [행동: 방문계획/구매/검색/찜 등] 형식으로 태그를 붙이세요.
- 메시지는 1~3문장, 실제 20~30대 카톡 말투로 짧게 쓰세요.
- 지금까지의 대화 흐름을 보고, 다른 사람의 말에 자연스럽게 반응하거나 질문하세요 (혼잣말처럼 쓰지 마세요).
"""


def call_groq(system_prompt, chat_log):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    user_content = "지금까지의 대화:\n" + "\n".join(chat_log) + "\n\n네 차례야. 메시지를 보내."
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.8,
        "max_tokens": 150,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def run_simulation(rounds=3):
    chat_log = []
    names = list(PERSONAS.keys())

    for round_i in range(rounds):
        for name in names:
            profile = PERSONAS[name]["profile"]
            system_prompt = SYSTEM_TEMPLATE.format(profile=profile, situation=SITUATION)
            try:
                reply = call_groq(system_prompt, chat_log)
            except Exception as e:
                print(f"[경고] {name} 호출 실패: {e}")
                continue
            line = f"{name}: {reply}"
            chat_log.append(line)
            print(line)

    with open("results_multi_agent_chat.json", "w", encoding="utf-8") as f:
        json.dump({"situation": SITUATION, "chat_log": chat_log}, f, ensure_ascii=False, indent=2)
    print("\n[저장] results_multi_agent_chat.json")


if __name__ == "__main__":
    run_simulation(rounds=3)
