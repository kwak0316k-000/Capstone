"""
generate_character_prompts.py — Nemotron-Personas-Korea 페르소나 CSV를 읽어,
각 인물에 대한 "2등신 애니메 캐릭터" 이미지 생성 프롬프트를 자동으로 만든다.

지금까지 시행착오(2주차 README §1.4)에서 확정한 규칙을 전부 반영했다:
- 스타일 고정 문구는 절대 바꾸지 않음
- 옆모습은 거울상이 아니라 독립적으로 묘사
- 좌우 비대칭은 항상 "오른쪽에 더 많이 덮인다"로 통일 (일관성을 위한 임의 규칙)
- 액세서리는 "왜 특정 각도에서 안 보이는지"까지 설명

v3 변경사항: 머리(앞머리 유무/색/길이/직모or곱슬)와 눈(모양/색)을 각각 독립 요소로
조합해서 다양성을 대폭 늘렸다. 앞머리가 없는 스타일은 "눈썹을 덮는" 비대칭 메커니즘을
쓸 수 없어서, 앞머리 유무에 따라 비대칭 서술 방식 자체를 분기했다:
  - 앞머리 있음: 오른쪽 눈썹은 앞머리에 덮여 거의 안 보임, 왼쪽은 뚜렷이 보임 (기존 방식)
  - 앞머리 없음: 오른쪽 귀는 머리에 더 많이 가려짐, 왼쪽 귀는 머리가 넘어가 더 잘 보임

사용법
------
python generate_character_prompts.py --csv sample_personas_500.csv --n 20 --out prompts_output.txt
"""

import argparse
import hashlib
import re

import pandas as pd


NAME_PATTERN = re.compile(r"^([가-힣]{2,4})\s*씨")


def extract_name(persona_text, fallback_uuid):
    if isinstance(persona_text, str):
        m = NAME_PATTERN.match(persona_text.strip())
        if m:
            return m.group(1)
    return fallback_uuid[:8] if fallback_uuid else "unknown"


def stable_pick(key, salt, options):
    """hashlib 기반 — 같은 key+salt는 몇 번을 실행해도 항상 같은 결과 (재현성 확보,
    파이썬 내장 hash()는 프로세스마다 값이 달라져서 쓰면 안 됨)."""
    h = hashlib.md5(f"{key}::{salt}".encode()).hexdigest()
    idx = int(h, 16) % len(options)
    return options[idx]


# ---------------------------------------------------------------
# 의상 / 소품 / 자세 규칙
# ---------------------------------------------------------------

OUTFIT_VARIANTS = {
    "military": [
        "an oversized {c} athletic hoodie, black leggings, white sneakers",
        "a fitted {c} tracksuit jacket, black joggers, running shoes",
        "a relaxed {c} zip-up windbreaker, cargo pants, combat-style boots",
    ],
    "office": [
        "a neat {c} cardigan over a simple shirt, straight-leg trousers, loafers",
        "a tailored {c} blazer over a white blouse, pencil skirt, low heels",
        "a {c} knit vest over a collared shirt, chinos, clean sneakers",
    ],
    "medical": [
        "a soft {c} casual top with a small clinic badge clipped on, comfortable trousers, white sneakers",
        "{c} scrub-style top and pants, comfortable clogs",
    ],
    "culinary": [
        "a {c} apron over a striped shirt, comfortable pants, clogs",
        "a {c} chef's bandana, apron over a plain tee, kitchen clogs",
    ],
    "creative": [
        "an artsy oversized {c} cardigan, wide-leg pants, canvas sneakers",
        "a {c} turtleneck sweater, corduroy overalls, ankle boots",
        "a paint-splattered {c} denim jacket over a plain tee, straight jeans",
    ],
    "education": [
        "a tidy {c} knit sweater vest over a collared shirt, slacks, loafers",
        "a {c} cardigan with a small brooch, pleated skirt, flat shoes",
    ],
    "student": [
        "an oversized {c} crewneck sweatshirt, joggers, white sneakers",
        "a {c} varsity-style jacket, straight jeans, canvas sneakers",
        "a baggy {c} hoodie, wide cargo pants, chunky sneakers",
    ],
    "driver": [
        "a practical {c} zip-up windbreaker, cargo pants, sturdy sneakers",
        "a {c} utility vest over a long-sleeve shirt, work pants, boots",
    ],
    "default": [
        "a simple {c} sweater, comfortable pants, sneakers",
        "a {c} zip-up cardigan, straight trousers, canvas shoes",
        "a relaxed {c} shirt, denim pants, loafers",
    ],
}

# 30대 — 캐주얼함은 줄이고 세미포멀 쪽으로 (트레이닝/후드류 배제)
THIRTIES_OUTFITS = {
    "f": [
        "a tailored {c} blazer over a simple top, straight trousers, low heels",
        "a midi skirt with a fitted {c} sweater, ankle boots",
        "a smart {c} cardigan over a blouse, wide-leg trousers, loafers",
    ],
    "m": [
        "a fitted {c} knit sweater, chinos, clean sneakers",
        "a casual blazer over a plain tee, straight trousers, loafers",
        "a {c} zip-up cardigan, tailored trousers, minimal sneakers",
    ],
}

# 40~70대 — 후드티/크루넥/조거팬츠 전면 배제. 여성은 롱스커트+블라우스, 남성은 포멀/니트 위주
MATURE_OUTFITS = {
    "f": [
        "a below-the-knee A-line skirt in a solid muted color, a simple {c} blouse (no bold prints), a light cardigan, low block heels",
        "a pleated long skirt, a tidy {c} blouse with subtle texture (no flashy patterns), flat loafers",
        "a straight long skirt, a soft {c} knit top, low heels",
    ],
    "m": [
        "a crisp collared shirt under a {c} cardigan, tailored trousers, polished loafers",
        "a {c} V-neck knit sweater over a collared shirt, straight trousers, dress shoes",
        "a neat {c} blazer, dress shirt, slacks, loafers",
    ],
}

# 이 두 직업군은 나이와 무관하게 업무 맥락상의 의상을 그대로 유지 (앞치마/스크럽 등)
AGE_EXEMPT_CATEGORIES = {"culinary", "medical"}


OCCUPATION_CATEGORY_KEYWORDS = [
    ("military", ["군인", "부사관", "장교", "경찰", "소방"]),
    ("office", ["사무", "행정", "회계", "비서", "관리", "은행", "보험"]),
    ("medical", ["의사", "간호", "약사", "치과"]),
    ("culinary", ["요리", "조리사", "주방", "제빵"]),
    ("creative", ["디자이너", "예술", "작가", "화가", "사진"]),
    ("education", ["교사", "교수", "강사"]),
    ("student", ["학생", "무직", "구직"]),
    ("driver", ["운전", "배송", "택배", "기사"]),
]

PROP_RULES = [
    (["카페", "커피", "디저트"], ["is holding a takeout coffee cup",
                                  "is holding a coffee cup with both hands, warming them"]),
    (["원예", "식물", "가드닝", "화분"], ["is holding a small potted plant",
                                      "is holding a small watering can"]),
    (["독서", "책", "소설", "도서관"], ["is holding a small paperback book against {p} chest",
                                     "is holding an open book, reading it"]),
    (["게임", "e스포츠", "esports"], ["is holding a smartphone, looking at the screen",
                                     "is holding a game controller"]),
    (["사진", "촬영", "카메라"], ["is holding a small vintage camera"]),
    (["운동", "헬스", "요가", "필라테스"], ["is holding a rolled-up yoga mat under one arm",
                                        "is holding a small water bottle"]),
    (["반려", "강아지", "고양이"], ["is holding a small pet leash"]),
    (["음악", "악기", "기타", "피아노"], ["is wearing wireless earbuds and holding a phone showing a music app"]),
]
DEFAULT_PROPS = [
    "is standing with hands relaxed at {p} sides",
    "is holding a small tote bag",
    "is holding a phone, casually checking it",
]

POSE_OPTIONS = [
    "standing straight with a relaxed, friendly posture",
    "standing with weight shifted onto one leg, casual stance",
    "leaning slightly forward with curious energy",
    "standing with a slight head tilt and an easygoing posture",
    "standing upright with confident, alert posture",
    "standing with shoulders relaxed and a laid-back stance",
]

COLOR_PALETTE = ["sage-green", "dusty-blue", "warm mustard", "terracotta",
                 "muted lavender", "charcoal-gray", "soft coral", "deep teal", "warm taupe"]

# ---------------------------------------------------------------
# 머리 — 길이/질감/색/앞머리 유무를 각각 독립 요소로 조합
# ---------------------------------------------------------------

LENGTH_OPTIONS = {
    "f_young": ["a chin-length bob (short)", "a shoulder-length", "a very long, waist-length (extending well past the shoulders down to the waist)"],
    "f_mature": ["a chin-length bob (short)", "a shoulder-length (just above the shoulder blades, not longer)"],
    "m": ["a very short", "a short", "a medium-length"],
}
# 강한 단일 표현 + "NOT X" 부정지시로, 이미지 모델이 straight를 무시하고
# 기본값(웨이브 펌)으로 그리는 걸 최대한 막는다
TEXTURE_DESC = {
    "straight": "poker-straight (NOT wavy, NOT curly, NOT permed)",
    "wavy": "loosely wavy",
    "curly": "tightly curled/permed",
}
TEXTURE_OPTIONS = ["straight", "wavy", "curly"]

# 젊은층은 자연스러운 컬러 범위, 장년층은 흰/회색 섞임 옵션도 포함 (전부 회색은 아님)
COLOR_YOUNG = ["jet black", "dark brown", "chestnut brown", "ash brown", "deep auburn"]
COLOR_OLDER = ["jet black", "dark brown", "salt-and-pepper gray", "silver-gray", "dark brown with gray streaks"]

# 앞머리 유형 3종 — 옆으로 넘긴 스타일/이마를 덮는 풀뱅/앞머리 없음 을 고르게 배치
BANGS_CHOICES = ["side_swept", "full_bangs", "full_bangs", "no_bangs"]

# 눈모양 — 설명을 강화(괄호 안 구체 묘사 + 대비되는 부정지시)해서 chibi 스타일 특유의
# "큰 동그란 눈" 기본값으로 뭉개지지 않게 함
EYE_SHAPE_DESC = {
    "round, wide": "round, wide-open eyes (large circular shape, NOT narrow, NOT slanted)",
    "gentle downturned": "gently downturned eyes (outer corners visibly drooping slightly downward, NOT upturned)",
    "sharp upturned": "sharp upturned eyes (outer corners angled distinctly upward, cat-eye-like, NOT round or drooping)",
    "almond-shaped": "elongated almond-shaped eyes (narrower and more angular than round eyes, NOT perfectly circular)",
    "soft monolid": "soft monolid eyes (single-eyelid, smooth eyelid with no visible crease/fold, NOT double-eyelid)",
}
EYE_SHAPES = list(EYE_SHAPE_DESC.keys())
# 나이대가 있는 남성(40대+)은 처진눈/무쌍/아몬드형이 더 어울린다는 피드백 반영
EYE_SHAPES_MATURE_MALE = ["gentle downturned", "soft monolid", "almond-shaped"]
# 동양인 눈 색 톤 범위 기본 + 밝은 톤(웜헤이즐)도 다양성 차원에서 하나 포함
EYE_COLORS = ["dark brown", "deep espresso-brown", "soft caramel-brown", "deep black", "warm chestnut-brown", "warm hazel"]


def match_category(occupation):
    for cat, keywords in OCCUPATION_CATEGORY_KEYWORDS:
        if any(k in occupation for k in keywords):
            return cat
    return "default"


def pick_prop(hobbies, possessive, uuid_key):
    for keywords, options in PROP_RULES:
        if any(k in hobbies for k in keywords):
            template = stable_pick(uuid_key, "prop", options)
            return template.format(p=possessive)
    template = stable_pick(uuid_key, "prop_default", DEFAULT_PROPS)
    return template.format(p=possessive)


def build_hair_and_asymmetry(uuid_key, sex, age, possessive, pronoun):
    """머리 스타일을 길이/질감/색/앞머리로 조합하고, 앞머리 유무에 따라
    비대칭(좌우가 다르게 보여야 하는 부분) 서술 방식을 분기한다."""
    gender_key = "f" if sex == "여자" else "m"
    length_pool_key = ("f_mature" if age >= 50 else "f_young") if gender_key == "f" else "m"
    length = stable_pick(uuid_key, "length", LENGTH_OPTIONS[length_pool_key])
    texture_key = stable_pick(uuid_key, "texture", TEXTURE_OPTIONS)
    texture = TEXTURE_DESC[texture_key]
    color_pool = COLOR_YOUNG if age < 50 else COLOR_OLDER
    color = stable_pick(uuid_key, "haircolor", color_pool)
    bangs_choice = stable_pick(uuid_key, "bangs", BANGS_CHOICES)

    if bangs_choice == "side_swept":
        hair_desc = f"{length} {texture} {color} hair with side-swept bangs"
        asymmetry_block = (
            f"{possessive.capitalize()} hairstyle has a side part with side-swept bangs: more hair "
            f"covers {possessive} RIGHT side of the forehead, and more of {possessive} LEFT forehead "
            "is visible. This asymmetry must stay physically consistent across all four panels — it "
            "is not something to flip or mirror between panels."
        )
        front_extra = f"The side-swept bangs are visible covering more of {possessive} right forehead."
        right_extra = (
            f"Since more hair covers this side, {possessive} bangs fall low enough to almost completely "
            f"cover {possessive} right eyebrow — barely visible or fully hidden under the hair, clearly "
            "different from the front view."
        )
        left_extra = (
            f"Since more of {possessive} left forehead is exposed, this profile shows a cleaner hairline "
            f"with {possessive} left eyebrow fully visible — clearly different from panel 2, not a "
            "mirrored copy of it."
        )
    elif bangs_choice == "full_bangs":
        hair_desc = f"{length} {texture} {color} hair with full, blunt bangs covering most of the forehead"
        asymmetry_block = (
            f"{possessive.capitalize()} hairstyle has full, straight-across bangs that evenly cover most "
            f"of the forehead — NOT side-swept, NOT parted to one side. There is only a very subtle "
            f"asymmetry: the fringe sits marginally heavier/lower over {possessive} RIGHT eyebrow than "
            f"{possessive} LEFT. This small asymmetry must stay physically consistent across all four "
            "panels — it is not something to flip or mirror between panels."
        )
        front_extra = f"The full bangs are visible evenly covering most of {possessive} forehead, nearly reaching the eyebrows."
        right_extra = (
            f"Since the fringe sits marginally heavier on this side, {possessive} right eyebrow is almost "
            "entirely hidden beneath the bangs, clearly different from the front view."
        )
        left_extra = (
            f"Since the fringe is marginally shorter on this side, a sliver of {possessive} left eyebrow "
            "peeks through beneath the bangs — clearly different from panel 2, not a mirrored copy of it."
        )
    else:
        hair_desc = f"{length} {texture} {color} hair with no bangs, swept back off the forehead"
        asymmetry_block = (
            f"{possessive.capitalize()} hair is swept back with a side part: more hair volume falls "
            f"over {possessive} RIGHT ear (partially covering it), while {possessive} LEFT ear is more "
            "exposed. This asymmetry must stay physically consistent across all four panels — it is "
            "not something to flip or mirror between panels."
        )
        front_extra = f"Her hair is fully swept back, showing her full forehead, with slightly more volume on the right side."
        right_extra = (
            f"Since more hair falls over this side, {possessive} right ear is partially covered by hair "
            "strands, clearly different from the front view."
        )
        left_extra = (
            f"Since {possessive} left ear is more exposed, this profile shows the ear clearly, mostly "
            "uncovered by hair — clearly different from panel 2, not a mirrored copy of it."
        )

    back_extra = (
        f"{possessive.capitalize()} hair covers most of the back of {possessive} head; if any part of "
        "the ears is naturally visible due to hairstyle length, show the anatomically correct back-of-"
        "ear shape, not the front-of-ear shape reused from panel 1."
    )

    return hair_desc, asymmetry_block, front_extra, right_extra, left_extra, back_extra


def build_prompt(row, idx):
    age = int(row["age"])
    sex = row["sex"]
    occupation = str(row.get("occupation", ""))
    hobbies = str(row.get("hobbies_and_interests", "")) + " " + str(row.get("hobbies_and_interests_list", ""))
    uuid_key = str(row.get("uuid", str(idx)))

    pronoun = "she" if sex == "여자" else "he"
    possessive = "her" if sex == "여자" else "his"

    hair_desc, asymmetry_block, front_extra, right_extra, left_extra, back_extra = build_hair_and_asymmetry(
        uuid_key, sex, age, possessive, pronoun
    )

    eye_shape_pool = EYE_SHAPES_MATURE_MALE if (sex == "남자" and age >= 40) else EYE_SHAPES
    eye_shape_key = stable_pick(uuid_key, "eye_shape", eye_shape_pool)
    eye_color = stable_pick(uuid_key, "eye_color", EYE_COLORS)
    eyes_desc = f"{EYE_SHAPE_DESC[eye_shape_key]}, {eye_color} in color"

    gender_key = "f" if sex == "여자" else "m"
    category = match_category(occupation)
    # 나이대별 의상 풀 선택: 요리/의료는 나이 무관 업무 복장 유지, 그 외는 연령대로 분기
    if category in AGE_EXEMPT_CATEGORIES:
        outfit_pool = OUTFIT_VARIANTS[category]
    elif age >= 40:
        outfit_pool = MATURE_OUTFITS[gender_key]
    elif age >= 30:
        outfit_pool = THIRTIES_OUTFITS[gender_key]
    else:
        outfit_pool = OUTFIT_VARIANTS[category]
    outfit_template = stable_pick(uuid_key, "outfit", outfit_pool)
    color = stable_pick(uuid_key, "color", COLOR_PALETTE)
    outfit = outfit_template.format(c=color)

    pose = stable_pick(uuid_key, "pose", POSE_OPTIONS)
    prop_action = pick_prop(hobbies, possessive, uuid_key)
    expression = "bright, cheerful" if age < 40 else "calm, warm"

    # 60대 이상은 얼굴에 나이가 드러나도록 명시 (그렇지 않으면 2등신 chibi 특유의
    # 동안 기본값으로 그려져 60대 캐릭터가 20대처럼 나오는 문제가 있었음)
    if age >= 60:
        aging_detail = (
            f" {pronoun.capitalize()} face clearly shows {possessive} age: visible fine wrinkles "
            f"around the eyes (crow's feet) and mouth (smile lines/nasolabial folds), and a softer, "
            "slightly looser jawline than a young adult — this must be visible in all four panels, "
            "not just implied. Keep it gentle and consistent with the chibi illustration style, not "
            "photorealistic, but the character must NOT look like a young adult in older clothes."
        )
    else:
        aging_detail = ""

    front_detail = f"{front_extra} {pronoun.capitalize()} has {eyes_desc}. {pronoun.capitalize()} is {pose}.{aging_detail}"

    name = extract_name(row.get("persona", ""), uuid_key)

    prompt = f"""[{idx}] {name} ({uuid_key[:8]}) — {age}세 {sex}, {occupation}

A chibi-style anime character reference sheet with four panels arranged in a single
horizontal row, showing the exact same character. Cute super-deformed proportions:
2 heads tall, large round head, big expressive eyes, small simplified body. Clean bold
outlines, soft cel-shading, Korean webtoon/anime illustration style — NOT realistic, NOT
photographic, NOT normal human proportions.

{asymmetry_block}

Panel 1 (Front view): {pronoun} faces directly toward the camera, both eyes visible,
{expression} expression. {front_detail}
Panel 2 (Right side view): {possessive} body is turned so we see {possessive} RIGHT
profile — face pointing toward the right edge of the frame, nose pointing right, only
{possessive} right eye visible. {right_extra}
Panel 3 (Left side view): {possessive} body is turned so we see {possessive} LEFT
profile — face pointing toward the left edge of the frame, nose pointing left, only
{possessive} left eye visible. {left_extra}
Panel 4 (Back view): {pronoun} faces directly away from the camera, back of head and body
only, no face. {back_extra}

Character design: {age}-year-old Korean {"woman" if sex=="여자" else "man"}, average build,
{hair_desc}. Wearing {outfit}. In panel 1 only, {pronoun} {prop_action}.

All four panels: identical chibi proportions, identical height, identical outfit, hairstyle,
and eye color/shape (respecting the described asymmetry), plain light gray background, full
body visible head to toe. No text, labels, or watermarks.
"""
    return prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="페르소나 CSV 경로 (예: sample_personas_500.csv)")
    ap.add_argument("--n", type=int, default=20, help="생성할 프롬프트 개수")
    ap.add_argument("--min-age", type=int, default=20, help="10대 제외 등 최소 연령 필터")
    ap.add_argument("--out", default="prompts_output.txt", help="출력 파일")
    ap.add_argument("--seed", type=int, default=42, help="샘플링 시드")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = df[df["age"] >= args.min_age].sample(n=min(args.n, len(df)), random_state=args.seed).reset_index(drop=True)

    blocks = []
    for i, row in df.iterrows():
        blocks.append(build_prompt(row, i + 1))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n".join(blocks))

    print(f"{len(blocks)}명의 프롬프트를 생성했습니다 → {args.out}")
    print("각 블록을 ChatGPT(이미지 생성)에 하나씩 붙여넣으세요.")


if __name__ == "__main__":
    main()
