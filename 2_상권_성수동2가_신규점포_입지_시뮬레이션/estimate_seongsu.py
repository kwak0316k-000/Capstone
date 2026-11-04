"""
성수동2가 신규 점포 평가 — 길 위 동선 + 허프 모델 + 실제 매출 보정 + 민감도 분석 판정.
팀원의 7_store_entry_simulation/estimate_entry.py와 같은 보정 방법·판정 기준을 쓴다(상권·업종·에이전트 구성은 이 프로젝트 것).
API 호출 없음.

1) 에이전트(1,000명): 16명 페르소나를 성수 연령 비율로 뽑고(길단위인구), 방문 시각은 영업시간(11~21시) 안에서 시간별 유입 밀도로 뽑는다.
   '소포장 간식·소용량 화장품이 필요한가(need)'는 연령·성별·외국인에 따른 가정 확률로 정한다(수준은 보정에서 상쇄되고 구성 차이만 남는다).
2) 동선: 입구(길 끝 2곳 + 성수역 출구 4곳) → 목적지 → 출구. 입구는 가중치 × exp(−장소까지 거리/L)로 고른다.
3) 점포 선택(허프 모델): 필요한 사람은 오가는 길에 슈퍼마켓 하나를 들른다.
   점포 s를 고를 확률 ∝ 매력도_s × exp(−돌아가는 거리_s / λ),  돌아가는 거리 = (목적지→점포→출구) − (목적지→출구)  (들어오는 길도 같은 방식, 짧은 쪽)
4) 경쟁점: 서울시 점포 수(성수역 슈퍼마켓 23곳)만큼 도시 모델 길 위에 무작위로 놓는다(실제 위치 자료 없음).
5) 보정(실제 매출): 시간대 t마다 BASE(신규점 없음)에서 상권 안 점포로 가는 기대 이용을 2025년 실제 슈퍼마켓 결제 건수에 맞춘다.
   k_t = 실제 결제 건수_t ÷ Σ(need 에이전트의 점포 선택 확률 합)
   신규점 연 결제 = Σ_t k_t × Σ(신규점 선택 확률),  연매출 = × 실제 시간대별 객단가
   → 상권 전체 수요는 시나리오마다 같고, 신규점은 기존 점포 몫을 가져오는 만큼만 매출이 된다.
6) 민감도 분석(500회): 에이전트 복원추출 + λ·신규점 매력도·입구 감쇠·입구/장소 가중치·경쟁점 배치를 무작위로 바꾼다.

진출 판정 기준 (팀원과 동일, 실행 전에 정함):
  후보지별로 500회 중 '신규점 연매출 ≥ 기준 점포 연매출'인 비율이  70% 이상 Go / 40-70% 조건부 / 40% 미만 No-Go.
  상권 진출 판정 = 가장 좋은 후보지의 판정.
  기준 점포 연매출 = 성수역 슈퍼마켓 점포당 평균 연매출. 우리 점포는 11~21시만 열므로,
  같은 시간대(11~21시)만 비교한 값을 기본 기준으로, 24시간 전체 평균은 참고용으로 함께 낸다.

실행:  python3 prepare_market_seongsu.py ; python3 estimate_seongsu.py
결과:  data/evaluation_seongsu.json, data/assignments.json(화면용)
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
SEED = 42
N_AGENTS = 1000
N_RUNS = 500
BASE_PARAMS = {"lambda_m": 200.0, "alpha_new": 1.0, "entrance_decay_m": 500.0, "layout": "uniform"}
RANGES = {"lambda_m": (120.0, 350.0), "alpha_new": (1 / 1.5, 1.5), "entrance_decay_m": (300.0, 800.0), "weight_jitter": (0.5, 1.5)}
GO_SHARE, COND_SHARE = 0.7, 0.4
INF = 1e9
TB = ["11-14", "14-17", "17-21"]           # 영업시간 안의 시간대
TB_REAL = [2, 3, 4]                         # market_seongsu.json의 TIMES 인덱스
NEED_BASE = 0.30                            # 가정: 기준 필요 확률(수준은 보정에서 상쇄)
AFF_AGE = {"10": 1.0, "20": 1.3, "30": 1.1, "40": 0.7, "50": 0.5, "60": 0.3}
AFF_SEX = {"F": 1.2, "M": 0.9}
AFF_TOUR, TOUR_SHARE = 1.5, 0.10
# 길단위인구(성수 6곳 합산) 연령 비율과 11~21시 시간별 유입 밀도 (analysis_seongsu.json)
AGE_SHARE = {"10": 9.76, "20": 24.09, "30": 24.98, "40": 17.73, "50": 11.86, "60": 11.59}
HOUR_DENSITY = [18.87 / 3] * 3 + [20.37 / 3] * 3 + [20.92 / 4] * 4
SPRITES = [("19_F김서윤", 19, "F"), ("19_M이민우", 19, "M"), ("21_M김보민", 21, "M"), ("27_F김예림", 27, "F"),
           ("30_F채다연", 30, "F"), ("39_M방순호", 39, "M"), ("43_M전성일", 43, "M"), ("47_F김지선", 47, "F"),
           ("58_M고세종", 58, "M"), ("59_F이미경", 59, "F"), ("60_M박상윤", 60, "M"), ("69_F이정희", 69, "F"),
           ("73_F이순영", 73, "F"), ("78_M김춘식", 78, "M"), ("83_F홍신수", 83, "F"), ("89_M조상기", 89, "M")]


def bucket(a):
    return "10" if a < 20 else "20" if a < 30 else "30" if a < 40 else "40" if a < 50 else "50" if a < 60 else "60"


SPR_B = [bucket(a) for _, a, _ in SPRITES]
SPR_SEX = [s for _, _, s in SPRITES]
SPR_W = np.array([AGE_SHARE[b] / SPR_B.count(b) for b in SPR_B])


# ---------------------------------------------------------------- 공간
class Space:
    def __init__(self, market):
        g = json.load(open(DATA / "iso_graph.json", encoding="utf-8"))
        scene = json.load(open(DATA / "scene.json", encoding="utf-8"))
        ids = list(g["nodes"])
        self.ids, self.idx = ids, {k: i for i, k in enumerate(ids)}
        self.xy = np.array([g["nodes"][k] for k in ids], dtype=float)
        rows, cols, w = [], [], []
        for a, b in g["edges"]:
            d = float(np.hypot(*(self.xy[self.idx[a]] - self.xy[self.idx[b]])))
            rows += [self.idx[a], self.idx[b]]; cols += [self.idx[b], self.idx[a]]; w += [d, d]
        self.graph = csr_matrix((w, (rows, cols)), shape=(len(ids), len(ids)))
        self.places = list(g["anchors"]); self.place_w = np.array([g["anchors"][k] for k in self.places])
        self.ents = list(g["gates"]); self.ent_w = np.array([g["gates"][k] for k in self.ents])
        self.pn = [self.idx[k] for k in self.places]; self.en = [self.idx[k] for k in self.ents]
        self.sites = []
        for s in scene["stores"]:
            d = np.hypot(*(self.xy - np.array(s["doorpt"])).T)
            self.sites.append({"id": s["id"], "node": int(d.argmin()), "door": s["doorpt"]})
        self.sites.sort(key=lambda s: s["id"])
        src = sorted(set(self.pn + self.en))
        dist = dijkstra(self.graph, directed=False, indices=src)
        self.dist = {n: dist[i] for i, n in enumerate(src)}
        self.d_pe = np.array([[self.dist[p][e] for e in self.en] for p in self.pn])
        self.n_comp = int(round(market["stores"]))
        # 경쟁점이 놓일 수 있는 길: 모델 경계에서 5m 이상 안쪽
        MW, MH = scene["model"]
        self.inside = np.where((self.xy[:, 0] > 5) & (self.xy[:, 0] < MW - 5) & (self.xy[:, 1] > 5) & (self.xy[:, 1] < MH - 5))[0]
        self._lay = {}
        near = np.zeros(len(ids), bool)
        for n in self.pn + self.en:        # 사람이 모이는 곳(목적지·입구) 120m 안
            near |= self.dist[n] <= 120
        self.cluster_pool = np.array([n for n in self.inside if near[n]])

    def comp_nodes(self, layout, key):
        k = (layout, key)
        if k not in self._lay:
            r = np.random.default_rng(10_000 + key)
            pool = self.inside if layout == "uniform" else self.cluster_pool
            self._lay[k] = r.choice(pool, size=self.n_comp, replace=True)
        return self._lay[k]

    def store_nodes(self, layout, key):
        return np.array(list(self.comp_nodes(layout, key)) + [s["node"] for s in self.sites])

    def detour(self, snodes):
        d_ps = np.array([[self.dist[p][int(s)] for s in snodes] for p in self.pn])
        d_es = np.array([[self.dist[e][int(s)] for s in snodes] for e in self.en])
        leg = np.clip(d_ps[:, None, :] + d_es[None, :, :] - self.d_pe[:, :, None], 0, None)  # P×E×S
        return np.minimum(leg[:, :, None, :], leg[:, None, :, :])                           # P×E×E×S


# ---------------------------------------------------------------- 에이전트
def make_agents(rng, n=N_AGENTS):
    spr = rng.choice(len(SPRITES), size=n, p=SPR_W / SPR_W.sum())
    hw = np.array(HOUR_DENSITY); h = rng.choice(len(hw), size=n, p=hw / hw.sum())
    spawn = 660 + h * 60 + rng.random(n) * 60
    band = np.where(h < 3, 0, np.where(h < 6, 1, 2))
    tour = rng.random(n) < TOUR_SHARE
    p_need = np.minimum(0.95, NEED_BASE * np.array([AFF_AGE[SPR_B[i]] * AFF_SEX[SPR_SEX[i]] for i in spr]) * np.where(tour, AFF_TOUR, 1.0))
    need = rng.random(n) < p_need
    order = np.argsort(spawn)
    return {k: v[order] for k, v in dict(spr=spr, spawn=spawn, band=band, tour=tour, need=need.astype(float), u=rng.random(n)).items()}


# ---------------------------------------------------------------- 계산 단계
def entrance_probs(sp, ent_w, decay):
    W = ent_w[None, :] * np.exp(-sp.d_pe / decay)
    return W / W.sum(axis=1, keepdims=True)


def store_probs(sp, D, ent_p, attract, lam):
    U = attract[None, None, None, :] * np.exp(-D / lam)
    Pr = U / np.maximum(U.sum(axis=3, keepdims=True), 1e-300)
    w = ent_p[:, :, None] * ent_p[:, None, :]
    return (Pr * w[:, :, :, None]).sum(axis=(1, 2))      # P×S


def evaluate(sp, ag, A, w_agent, params, key, mk):
    snodes = sp.store_nodes(params["layout"], key)
    n_comp, n_cand = sp.n_comp, len(sp.sites)
    D = sp.detour(snodes)
    ent_p = entrance_probs(sp, params["ent_w"], params["entrance_decay_m"])
    w = ag["need"] * w_agent
    real_tx = np.array([mk["time"][list(mk["time"])[i]]["transactions"] for i in TB_REAL], float)
    ticket = np.array([mk["time"][list(mk["time"])[i]]["avg_ticket"] for i in TB_REAL], float)

    def probs(c):
        att = np.r_[np.ones(n_comp), np.zeros(n_cand)]
        if c >= 0:
            att[n_comp + c] = params["alpha_new"]
        return A @ store_probs(sp, D, ent_p, att, params["lambda_m"])      # N×S

    base = probs(-1)
    base_in = np.bincount(ag["band"], weights=w * base.sum(axis=1), minlength=3)
    k = np.divide(real_tx, base_in, out=np.zeros(3), where=base_in > 0)
    out = {"k": k, "base": base, "snodes": snodes, "ticket": ticket, "real_tx": real_tx, "scn": []}
    for c in range(n_cand):
        P = probs(c); p_new = P[:, n_comp + c]
        tx_t = k * np.bincount(ag["band"], weights=w * p_new, minlength=3)
        out["scn"].append({"P": P, "p_new": p_new, "tx_t": tx_t, "tx": float(tx_t.sum()), "sales": float((tx_t * ticket).sum())})
    return out


def verdict(p):
    return "Go" if p >= GO_SHARE else ("조건부" if p >= COND_SHARE else "No-Go")


def share(keys, weights, order):
    s = {k: 0.0 for k in order}
    for k, x in zip(keys, weights):
        s[k] += x
    t = sum(s.values())
    return {k: round(v / t * 100, 1) for k, v in s.items()} if t > 0 else {}


def sensitivity(sp, ag, mk, runs, rng, ent_w, place_w_base, need_override=None, layouts=("uniform", "clustered")):
    sales = np.zeros((runs, len(sp.sites)))
    ag2 = dict(ag)
    if need_override is not None:
        ag2["need"] = need_override
    N = len(ag["spr"]); P, E = len(sp.pn), len(sp.en); lo, hi = RANGES["weight_jitter"]
    for r in range(runs):
        prm = {"lambda_m": rng.uniform(*RANGES["lambda_m"]), "alpha_new": float(np.exp(rng.uniform(*np.log(RANGES["alpha_new"])))),
               "entrance_decay_m": rng.uniform(*RANGES["entrance_decay_m"]),
               "layout": layouts[int(rng.integers(len(layouts)))], "ent_w": ent_w * rng.uniform(lo, hi, size=E)}
        pw = place_w_base * rng.uniform(lo, hi, size=P)
        A = np.tile(pw / pw.sum(), (N, 1))
        wb = rng.multinomial(N, np.full(N, 1 / N)).astype(float)
        res = evaluate(sp, ag2, A, wb, prm, r % 20, mk)
        sales[r] = [s["sales"] for s in res["scn"]]
    return sales


def main():
    mk = json.load(open(DATA / "market_seongsu.json", encoding="utf-8"))
    sp = Space(mk)
    rng = np.random.default_rng(SEED)
    ag = make_agents(rng)
    N, P, E = N_AGENTS, len(sp.pn), len(sp.en)
    times = list(mk["time"])
    # 기준 점포 매출: 같은 영업시간(11~21시) 평균 / 24시간 전체 평균
    open_amt = sum(mk["time"][times[i]]["amount"] for i in TB_REAL)
    bench_open = open_amt / mk["stores"]; bench_all = mk["sales_per_store_2025"]

    # ---- 기본값 1회
    A0 = np.tile(sp.place_w / sp.place_w.sum(), (N, 1))
    prm0 = {**BASE_PARAMS, "ent_w": sp.ent_w}
    base = evaluate(sp, ag, A0, np.ones(N), prm0, 0, mk)
    print("보정계수 k_t:", {t: round(float(v), 1) for t, v in zip(TB, base["k"])})

    # ---- 민감도 분석 500회
    sales_runs = sensitivity(sp, ag, mk, N_RUNS, rng, sp.ent_w, sp.place_w)
    rank1 = np.bincount(sales_runs.argmax(axis=1), minlength=len(sp.sites)) / N_RUNS

    # ---- 대조실험 (200회): 입구 가중치 / 경쟁점 배치 / 경쟁점 수를 바꿔 결론이 유지되는지 본다
    # (장소 확률이 모든 에이전트에게 같으므로 '필요 확률'은 보정에서 상쇄되어 결과에 영향이 없다 → 대조에서 제외)
    ab = {}
    n_real = sp.n_comp
    cases = {"기본(민감도 분석과 같은 조건)": {}, "입구 6곳 가중치 균등": {"ent_w": np.ones(E)},
             "경쟁점 균등 배치만": {"layouts": ("uniform",)}, "경쟁점 사람 많은 곳 집중만": {"layouts": ("clustered",)},
             "경쟁점 16곳(−30%)": {"n_comp": 16}, "경쟁점 30곳(+30%)": {"n_comp": 30}}
    for name, kw in cases.items():
        kw = dict(kw); sp.n_comp = kw.pop("n_comp", n_real); sp._lay = {}
        a = dict(ent_w=sp.ent_w, place_w_base=sp.place_w); a.update(kw)
        s = sensitivity(sp, ag, mk, 200, np.random.default_rng(SEED + 1), **a)
        ab[name] = [{"id": st["id"], "p50": round(float(np.median(s[:, i]))),
                     "share_above": round(float((s[:, i] >= bench_open).mean()), 3)} for i, st in enumerate(sp.sites)]
    sp.n_comp = n_real; sp._lay = {}

    # ---- 후보지별 정리
    n_comp = sp.n_comp; need = ag["need"]; results = []
    kb = base["k"][ag["band"]]
    for c, site in enumerate(sp.sites):
        s = base["scn"][c]
        w_new = need * s["p_new"] * kb
        loss = (need[:, None] * (base["base"][:, :n_comp] - s["P"][:, :n_comp]) * kb[:, None]).sum(axis=0)
        sr = sales_runs[:, c]
        tx_open = float(base["real_tx"].sum())
        results.append({
            "id": site["id"], "node": site["node"],
            "base": {"annual_transactions": round(s["tx"]), "annual_sales": round(s["sales"]),
                     "ratio_to_bench_open": round(s["sales"] / bench_open, 3), "ratio_to_bench_all": round(s["sales"] / bench_all, 3),
                     "share_of_open_hours_tx_pct": round(s["tx"] / tx_open * 100, 2)},
            "robust": {"p5": round(float(np.percentile(sr, 5))), "p50": round(float(np.percentile(sr, 50))), "p95": round(float(np.percentile(sr, 95))),
                       "share_above_bench": round(float((sr >= bench_open).mean()), 3),
                       "share_above_bench_all_hours": round(float((sr >= bench_all).mean()), 3),
                       "rank1_share": round(float(rank1[c]), 3)},
            "verdict": verdict(float((sr >= bench_open).mean())),
            "verdict_all_hours_benchmark": verdict(float((sr >= bench_all).mean())),
            "avg_loss_per_competitor_tx": round(s["tx"] / n_comp), "avg_loss_per_competitor_pct": round(s["tx"] / n_comp / (mk["transactions_per_store_2025"] * tx_open / mk["transactions_2025"]) * 100, 2)
        })
    best = max(results, key=lambda x: (x["robust"]["share_above_bench"], x["robust"]["p50"]))

    # ---- BASE 검증: 시뮬레이션 필요 고객 구성 vs 실제 슈퍼마켓 결제 구성 (영업시간대 안에서)
    wb = need * base["base"].sum(axis=1)
    sim_age = share([SPR_B[i] for i in ag["spr"]], wb, ["10", "20", "30", "40", "50", "60"])
    real_age = dict(zip(["10", "20", "30", "40", "50", "60"], mk["age_tx_pct"].values()))
    sim_sex = share([SPR_SEX[i] for i in ag["spr"]], wb, ["M", "F"]); real_sex = {"M": mk["gender_tx_pct"]["남"], "F": mk["gender_tx_pct"]["여"]}
    sim_t = share([TB[b] for b in ag["band"]], wb, TB)
    rt = np.array([base["real_tx"]]); real_t = {t: round(float(v / rt.sum() * 100), 1) for t, v in zip(TB, base["real_tx"])}
    mae = lambda a, b: round(float(np.mean([abs(a[k] - b[k]) for k in b])), 1)
    validation = {"age": {"sim": sim_age, "real": real_age, "mae": mae(sim_age, real_age)},
                  "gender": {"sim": sim_sex, "real": real_sex, "mae": mae(sim_sex, real_sex)},
                  "time": {"sim": sim_t, "real": real_t, "mae": mae(sim_t, real_t)}}

    wn = need * 1.0
    profile = {"age_pct": share([SPR_B[i] for i in ag["spr"]], wn, ["10", "20", "30", "40", "50", "60"]),
               "gender_pct": share([SPR_SEX[i] for i in ag["spr"]], wn, ["M", "F"]),
               "time_pct": share([TB[b] for b in ag["band"]], wn, TB),
               "foreign_pct": round(float((wn * ag["tour"]).sum() / wn.sum() * 100), 1)}
    ev = {"n_agents": N, "n_need": int(need.sum()), "n_runs": N_RUNS,
          "market": {k: mk[k] for k in ["district_name", "industry", "stores", "sales_amount_2025", "transactions_2025", "avg_ticket", "sales_per_store_2025"]},
          "benchmark": {"same_hours_11_21": round(bench_open), "all_hours": round(bench_all)},
          "competitors": n_comp, "base_params": BASE_PARAMS, "ranges": RANGES,
          "criteria": {"go_share": GO_SHARE, "conditional_share": COND_SHARE, "benchmark": "성수역 슈퍼마켓 점포당 평균 연매출(2025, 같은 영업시간 11~21시)"},
          "calibration_k": {t: round(float(v), 1) for t, v in zip(TB, base["k"])},
          "real_tx_open": {t: int(v) for t, v in zip(TB, base["real_tx"])}, "ticket_open": {t: int(v) for t, v in zip(TB, base["ticket"])},
          "candidates": results, "best_candidate": best["id"], "district_verdict": best["verdict"],
          "ablation": ab, "validation": validation, "need_profile": profile}
    (DATA / "evaluation_seongsu.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 화면용: 에이전트마다 목적지·입구·출구·시나리오별 점포를 하나씩 뽑아 둔다(같은 난수 → 시나리오 간 비교 가능)
    vr = np.random.default_rng(SEED + 7)
    ent_p = entrance_probs(sp, sp.ent_w, BASE_PARAMS["entrance_decay_m"])
    pl = vr.choice(P, size=N, p=sp.place_w / sp.place_w.sum())
    rows = []
    for i in range(N):
        p = int(pl[i])
        row = {"spr": int(ag["spr"][i]), "spawn": round(float(ag["spawn"][i]), 1), "tour": bool(ag["tour"][i]), "need": bool(ag["need"][i]),
               "u": round(float(ag["u"][i]), 4), "place": sp.places[p], "in": sp.ents[int(vr.choice(E, p=ent_p[p]))], "out": sp.ents[int(vr.choice(E, p=ent_p[p]))]}
        if ag["need"][i]:
            # 목적지가 그 에이전트의 것이므로 장소 p의 점포 선택 확률로 뽑는다
            pass
        rows.append(row)
    # 점포 선택 확률은 장소별로 다르므로 장소 p 기준 Q를 다시 계산
    snodes = sp.store_nodes("uniform", 0); D = sp.detour(snodes)
    Qs = []
    for c in [-1] + list(range(len(sp.sites))):
        att = np.r_[np.ones(n_comp), np.zeros(len(sp.sites))]
        if c >= 0:
            att[n_comp + c] = BASE_PARAMS["alpha_new"]
        Qs.append(store_probs(sp, D, ent_p, att, BASE_PARAMS["lambda_m"]))
    for i, row in enumerate(rows):
        if not row["need"]:
            continue
        p = pl[i]; ch = []
        for q in Qs:
            pr = q[p] / q[p].sum()
            j = int(min(np.searchsorted(np.cumsum(pr), row["u"]), len(pr) - 1))
            ch.append(j)
        row["store"] = ch      # [BASE, A, F, B, C, D, E 순서(sites 정렬)] — 점포 인덱스(경쟁점 0..n-1, 후보 n..)
    comp = [{"id": f"V{k}", "node": sp.ids[int(n)], "xy": [round(float(x), 1) for x in sp.xy[int(n)]]} for k, n in enumerate(sp.comp_nodes("uniform", 0))]
    out = {"sites": [s["id"] for s in sp.sites], "site_nodes": {s["id"]: sp.ids[s["node"]] for s in sp.sites}, "n_comp": n_comp, "competitors": comp, "agents": rows}
    (DATA / "assignments.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- 출력
    print(f"기준 점포 연매출: 11~21시 {bench_open / 1e8:.2f}억 / 24시간 {bench_all / 1e8:.2f}억 | 경쟁점 {n_comp}곳 | 필요 에이전트 {int(need.sum())}/{N}")
    for c in results:
        b, r = c["base"], c["robust"]
        print(f"{c['id']}: 결제 {b['annual_transactions']:,}건 매출 {b['annual_sales'] / 1e8:.2f}억 (같은시간 평균 대비 {b['ratio_to_bench_open'] * 100:.0f}%) "
              f"| 구간 {r['p5'] / 1e8:.2f}-{r['p95'] / 1e8:.2f}억 | 평균이상 {r['share_above_bench'] * 100:.0f}% (24h기준 {r['share_above_bench_all_hours'] * 100:.0f}%) | 1위 {r['rank1_share'] * 100:.0f}% | {c['verdict']}")
    print("상권 진출 판정:", ev["district_verdict"], "(최적", ev["best_candidate"] + ")")
    print("검증 MAE:", {k: v["mae"] for k, v in validation.items()})


if __name__ == "__main__":
    main()
