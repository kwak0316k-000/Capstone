"""
nemotron_eda_full.py — nvidia/Nemotron-Personas-Korea 전체 100만 명에 대한 EDA를 수행하고
차트를 assets/ 폴더에 저장합니다.

사용법
------
python nemotron_eda_full.py --csv nemotron_full_1M_demographics.csv

입력 CSV는 다음 컬럼만 있으면 됩니다 (Colab에서 전체 데이터셋을 받아 인구통계 필드만
추출한 결과물 — README §13.1 참고):
sex, age, marital_status, military_status, family_type, housing_type,
education_level, bachelors_field, occupation, district, province
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd

CAPITAL_PROVINCES = ["서울", "경기", "인천"]
AGE_BINS = [18, 19, 29, 39, 49, 59, 69, 79, 99]
AGE_LABELS = ["10대", "20대", "30대", "40대", "50대", "60대", "70대", "80대+"]


def parse_args():
    p = argparse.ArgumentParser(description="Nemotron-Personas-Korea 전체 EDA")
    p.add_argument("--csv", required=True, help="nemotron_full_1M_demographics.csv 경로")
    p.add_argument("--outdir", default="assets", help="차트 저장 폴더")
    p.add_argument("--font", default="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                    help="한글 폰트 경로 (환경에 맞게 조정하세요)")
    return p.parse_args()


def fmt_n(v):
    return f"{v/10000:.1f}만" if v >= 10000 else f"{v}"


def bar_chart(fp, fp_bold, counts, title, path, horizontal=False, color="#2563eb", figsize=(8, 4.5), pct=False):
    fig, ax = plt.subplots(figsize=figsize, dpi=160)
    labels = counts.index.astype(str)
    if horizontal:
        ax.barh(labels[::-1], counts.values[::-1], color=color)
        for i, v in enumerate(counts.values[::-1]):
            label = f'{v:.2f}%' if pct else fmt_n(v)
            ax.text(v, i, f' {label}', va='center', fontsize=9, fontproperties=fp)
        ax.set_yticklabels(labels[::-1], fontproperties=fp, fontsize=10)
    else:
        ax.bar(labels, counts.values, color=color)
        for i, v in enumerate(counts.values):
            label = f'{v:.2f}%' if pct else fmt_n(v)
            ax.text(i, v, label, ha='center', va='bottom', fontsize=9, fontproperties=fp)
        ax.set_xticklabels(labels, fontproperties=fp, fontsize=10)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(fp)
    ax.set_title(title, fontproperties=fp_bold, fontsize=13, pad=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    fp = fm.FontProperties(fname=args.font)
    fp_bold = fp

    df = pd.read_csv(args.csv)
    df['age_band'] = pd.cut(df['age'], bins=AGE_BINS, labels=AGE_LABELS, right=True, include_lowest=True)
    df['region'] = df['province'].apply(lambda p: '수도권' if p in CAPITAL_PROVINCES else '지방')

    n = len(df)
    print(f"총 {n:,}명 / 연령 {df['age'].min()}~{df['age'].max()}세 (평균 {df['age'].mean():.2f})")

    bar_chart(fp, fp_bold, df['age_band'].value_counts().sort_index(),
              f'Nemotron-Personas-Korea 전체({n:,}명) 연령대 분포', f"{args.outdir}/age_distribution.png")
    bar_chart(fp, fp_bold, df['sex'].value_counts(), f'성별 분포 ({n:,}명)',
              f"{args.outdir}/gender_distribution.png", figsize=(5, 4.5))
    bar_chart(fp, fp_bold, df['marital_status'].value_counts(), f'혼인 상태 분포 ({n:,}명)',
              f"{args.outdir}/marital_status.png", figsize=(6, 4.5))
    bar_chart(fp, fp_bold, df['housing_type'].value_counts(), f'주거 형태 분포 ({n:,}명)',
              f"{args.outdir}/housing_type.png", horizontal=True, color="#f97316", figsize=(8, 4))

    edu_order = ['무학', '초등학교', '중학교', '고등학교', '2~3년제 전문대학', '4년제 대학교', '대학원']
    bar_chart(fp, fp_bold, df['education_level'].value_counts().reindex(edu_order),
              f'교육 수준 분포 ({n:,}명)', f"{args.outdir}/education_level.png", horizontal=True, figsize=(8, 4.5))

    bar_chart(fp, fp_bold, df['province'].value_counts(), f'광역시도별 거주 분포 ({n:,}명)',
              f"{args.outdir}/province_distribution.png", horizontal=True, figsize=(8, 7))

    occ = df[df['occupation'] != '무직']['occupation'].value_counts().head(15)
    bar_chart(fp, fp_bold, occ, f'직업 분포 상위 15 (무직 제외, {n:,}명)',
              f"{args.outdir}/occupation_top15.png", horizontal=True, figsize=(9, 6))

    unemploy = df.groupby('age_band', observed=True)['occupation'].apply(lambda x: (x == '무직').mean() * 100).round(2)
    bar_chart(fp, fp_bold, unemploy, f'연령대별 무직 비율(%) ({n:,}명)',
              f"{args.outdir}/unemployment_by_age.png", color="#dc2626", pct=True)

    bar_chart(fp, fp_bold, df['region'].value_counts(), f'수도권 vs 지방 거주 분포 ({n:,}명)',
              f"{args.outdir}/region_distribution.png", figsize=(5, 4.5), color="#059669")

    print(f"차트 9종 저장 완료 → {args.outdir}/")


if __name__ == "__main__":
    main()
