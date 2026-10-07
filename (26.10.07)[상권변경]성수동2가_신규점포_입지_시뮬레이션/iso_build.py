"""2단계: 건물·나무·가로등·고가선로를 만들고 월드 이미지(ground.jpg)와 오브젝트 아틀라스(atlas.webp, scene.json)를 출력."""
import json, math, pickle, random, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
import geo
from geo import disp_to_g
from iso_common import *
from iso_draw import *
TD = 8
rng = random.Random(21)
mk = pickle.load(open("data/_tmasks.pkl", "rb"))
road, park, valid, wide, glT = mk["road"], mk["park"], mk["valid"], mk["wide"], mk["gl"]
HT, WT = road.shape
K = geo.K
def sat(m): return np.pad(np.cumsum(np.cumsum(m.astype(np.int32), 0), 1), ((1, 0), (1, 0)))
def rect_sum(S, x0, y0, x1, y1):
    x0, y0, x1, y1 = [int(round(v*TD)) for v in (x0, y0, x1, y1)]
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, WT), min(y1, HT)
    if x1 <= x0 or y1 <= y0: return 0, 0
    return S[y1, x1]-S[y0, x1]-S[y1, x0]+S[y0, x0], (x1-x0)*(y1-y0)
def M(xy): return (xy[0]-GX0, xy[1]-GY0)
# --- 주요 지점 (모델 좌표) ---
disp = {"A":(885,293),"F":(670,212),"B":(1003,255),"C":(600,345),"D":(840,640),"E":(1100,760)}
site_g = {k: M(disp_to_g(*v)) for k, v in disp.items()}
EX = {"1":(673,193),"4":(668,230),"2":(892,274),"3":(878,313)}
ex_g = {k: M(disp_to_g(*v)) for k, v in EX.items()}
LM = json.load(open("data/landmarks_disp.json"))
lm_g = [dict(name=n, cat=c, g=M(disp_to_g(x, y))) for n, c, x, y in LM]
# --- 고가선로 중심선 ---
from skimage.morphology import skeletonize
sk = skeletonize(cv2.resize(glT.astype(np.uint8), (WT//4, HT//4), interpolation=cv2.INTER_AREA) > 0)
ys, xs = np.nonzero(sk); xm = xs*4/TD; ym = ys*4/TD
ok = (xm > 5) & (xm < MW-5)
a_, b_ = np.polyfit(xm[ok], ym[ok], 1)
def my_line(mx): return a_*mx + b_
print("viaduct slope", a_, "my at mid", my_line(MW/2))
# --- 점유(예약) 마스크 ---
free = valid & ~road & ~park
free = cv2.erode(free.astype(np.uint8), K(int(2.2*TD))).astype(bool)
reserved = np.zeros_like(free)
def reserve(x0, y0, x1, y1, pad=0.8):
    reserved[max(0,int((y0-pad)*TD)):int((y1+pad)*TD), max(0,int((x0-pad)*TD)):int((x1+pad)*TD)] = True
# --- 후보지 점포 부지 선택 (앞면이 길을 향하는 자리) ---
SW, SD = 11.0, 10.0
road_s = sat(road)
SF = sat(free)
def clear_rect(x0, y0, x1, y1, S):
    f, a = rect_sum(S, x0, y0, x1, y1); return a > 0 and f >= a*0.995
stores = []
for sid, (sx, sy) in site_g.items():
    S2 = sat(free & ~reserved); best = None
    for cx in np.arange(max(6, sx-50), min(MW-6, sx+50), 1.0):
        for cy in np.arange(max(6, sy-50), min(MH-6, sy+50), 1.0):
            x0, x1, y0, y1 = cx-SW/2, cx+SW/2, cy-SD/2, cy+SD/2
            if not clear_rect(x0, y0, x1, y1, S2): continue
            # 앞면 후보: +gy 면(L) 앞 2m, +gx 면(R) 앞 2m 의 도로 비율
            fl_, al = rect_sum(road_s, x0, y1, x1, y1+3.6); fr_, ar = rect_sum(road_s, x1, y0, x1+3.6, y1)
            pl = fl_/al if al else 0; pr = fr_/ar if ar else 0
            if max(pl, pr) < 0.3: continue
            door = "L" if pl >= pr else "R"
            doorpt = (cx, y1+1.0) if door == "L" else (x1+1.0, cy)
            dd = math.hypot(doorpt[0]-sx, doorpt[1]-sy)
            if best is None or dd < best[0]: best = (dd, x0, x1, y0, y1, door, doorpt)
    if best is None: raise SystemExit("store lot not found for "+sid)
    dd, x0, x1, y0, y1, door, doorpt = best
    reserve(x0, y0, x1, y1, 1.2); stores.append(dict(id=sid, mx0=x0, mx1=x1, my0=y0, my1=y1, door=door, doorpt=doorpt, dist=dd))
    print("store", sid, round(dd, 1), door, (round(x0), round(y0)))
# 출구 키오스크
kiosks = []
for k, (ex, ey) in ex_g.items():
    best = None; S2 = sat(free & ~reserved)
    for dx in np.arange(-6, 6.1, 0.5):
        for dy in np.arange(-6, 6.1, 0.5):
            x0, y0 = ex+dx-2, ey+dy-2
            if clear_rect(x0, y0, x0+4, y0+4, S2):
                d = math.hypot(dx, dy)
                if best is None or d < best[0]: best = (d, x0, y0)
    if best is None:                       # 보도 위에 놓기: 길 가장자리 허용
        best = (0, ex-2, ey-2)
    _, x0, y0 = best; reserve(x0, y0, x0+4, y0+4, 0.8); kiosks.append(dict(id=k, mx0=x0, mx1=x0+4, my0=y0, my1=y0+4))
# --- 건물 생성 ---
S2 = sat(free & ~reserved)
n, lab, st, _ = cv2.connectedComponentsWithStats((free & ~reserved).astype(np.uint8), 4)
lots = []
for i in range(1, n):
    x, y, w, h, a = st[i]
    if a < 40*TD*TD: continue
    bx0, by0, bx1, by1 = x/TD, y/TD, (x+w)/TD, (y+h)/TD
    v0 = by0 + rng.uniform(0, 1.2)
    while v0 < by1-5:
        dep = rng.choice([9, 10, 11, 12, 14])
        u0 = bx0 + rng.uniform(0, 1.2)
        while u0 < bx1-4:
            placed = False
            for dfac in (1, .78, .58):
                dd = dep*dfac
                if dd < 6: continue
                wmax = rng.choice([6, 7, 8, 9, 10, 12, 14, 18, 24])
                for wf in (1, .8, .62):
                    ww = wmax*wf
                    if ww < 5: continue
                    if u0+ww <= bx1 and v0+dd <= by1 and clear_rect(u0, v0, u0+ww, v0+dd, S2) and (lab[int((v0+dd/2)*TD), int((u0+ww/2)*TD)] == i):
                        lots.append(dict(mx0=u0, mx1=u0+ww, my0=v0, my1=v0+dd)); u0 += ww+0.7; placed = True; break
                if placed: break
            if not placed: u0 += 3
        v0 += dep+0.7
print("lots", len(lots))
road_s = sat(road)
bld = []
lmpts = [(l["g"], l) for l in lm_g]
for L in lots:
    cx, cy = (L["mx0"]+L["mx1"])/2, (L["my0"]+L["my1"])/2; w, d = L["mx1"]-L["mx0"], L["my1"]-L["my0"]; area = w*d
    dl = abs(cy-my_line(cx))
    fl = rng.choices([1,2,3,4,5], [.16,.36,.28,.16,.04])[0] + (1 if dl < 20 else 0)
    if area > 260 and fl > 2: fl = 2
    b = dict(L); b["fl"] = fl; b["H"] = fl*FH
    wall = rng.choice(WALLS); b["wall"] = jit(wall, rng, 8)
    if area > 240: b["roof"] = "flat"; b["roofcol"] = rng.choice([(104,108,118),(128,96,80),(96,100,108)]); b["garden"] = rng.random() < .15
    elif area <= 190 and fl <= 4 and rng.random() < .72:
        kind = rng.choices(["terra", "teal", "brown", "slate"], [.46, .2, .14, .2])[0]; b["roof"] = kind; b["roofcol"] = rng.choice(ROOFS[kind]); b["ivy"] = rng.randint(1, 5) if kind in ("terra", "teal") and rng.random() < .55 else 0
    else: b["roof"] = "flat"; b["roofcol"] = rng.choice([(150,152,158),(120,100,88),(98,104,112),(176,150,128)]); b["garden"] = rng.random() < .2
    # 길에 닿은 면에 문/차양
    fl_, al = rect_sum(road_s, L["mx0"], L["my1"], L["mx1"], L["my1"]+4.6); fr_, ar = rect_sum(road_s, L["mx1"], L["my0"], L["mx1"]+4.6, L["my1"])
    pl, pr = (fl_/al if al else 0), (fr_/ar if ar else 0)
    if max(pl, pr) > .22:
        face = "L" if (pl >= pr and w >= 5) or d < 5 else "R"
        b["door_face"] = face; Lf = w if face == "L" else d
        nn = max(1, int((Lf-1.6)//3.0)); b["door_i"] = rng.randrange(nn)
        if rng.random() < .55: b["awn_face"] = face; b["awn"] = rng.choice(AWN)
    b["balc"] = rng.random() < .3; b["shut"] = rng.random() < .35
    # 랜드마크
    for (g, l) in lmpts:
        if L["mx0"]-3 <= g[0] <= L["mx1"]+3 and L["my0"]-3 <= g[1] <= L["my1"]+3 and not b.get("lm"):
            b["lm"] = l["name"]; b["cat"] = l["cat"]
            if "door_face" in b and "awn" not in b: b["awn_face"] = b["door_face"]; b["awn"] = rng.choice(AWN)
    bld.append(b)
print("buildings", len(bld), "landmarks tagged", sum(1 for b in bld if b.get("lm")))
# --- 소품 (나무·가로등·벤치·화분) ---
props = []
occ = np.zeros_like(free)
for L in lots + stores + kiosks:
    occ[max(0,int((L["my0"]-1.2)*TD)):int((L["my1"]+1.2)*TD), max(0,int((L["mx0"]-1.2)*TD)):int((L["mx1"]+1.2)*TD)] = True
curb = cv2.dilate(road.astype(np.uint8), K(int(2.6*TD))).astype(bool) & ~cv2.dilate(road.astype(np.uint8), K(int(1.0*TD))).astype(bool) & valid & ~park & ~occ
def poisson(mask, mind, edge=3, prob=1.0):
    ys, xs = np.nonzero(mask[::2, ::2]); pts = list(zip((xs*2/TD).tolist(), (ys*2/TD).tolist())); rng.shuffle(pts)
    cell = mind; grid = {}; out = []
    for (x, y) in pts:
        if x < edge or y < edge or x > MW-edge or y > MH-edge: continue
        gx_, gy_ = int(x//cell), int(y//cell)
        if any(((x-q[0])**2 + (y-q[1])**2) < mind*mind for i in (-1, 0, 1) for j in (-1, 0, 1) for q in grid.get((gx_+i, gy_+j), [])): continue
        grid.setdefault((gx_, gy_), []).append((x, y)); out.append((x, y))
    return out
sample = lambda mask, step, jitter, edge=3: poisson(mask, step, edge)
for (x, y) in poisson(curb, 10):
    r_ = rng.random()
    if r_ < .46: props.append(dict(kind="tree", sub=rng.choices(["g", "p", "y"], [.7, .12, .18])[0], mx=x, my=y))
    elif r_ < .64: props.append(dict(kind="lamp", mx=x, my=y))
    elif r_ < .70: props.append(dict(kind="bench", mx=x, my=y))
    elif r_ < .82: props.append(dict(kind="planter", mx=x, my=y))
for (x, y) in poisson(park, 6):
    if rng.random() < .6: props.append(dict(kind="tree", sub=rng.choices(["g", "y", "p"], [.7, .2, .1])[0], mx=x, my=y))
# 건물 뒷마당 소형 나무
backs = free & ~occ
for (x, y) in poisson(backs, 16):
    if rng.random() < .3: props.append(dict(kind="tree", sub="g", mx=x, my=y))
print("props", len(props))
# --- 타일 그리기 ---
objs = []; tiles = []
def add(kind, t, fp, extra=None):
    img = t.finish(); o = dict(kind=kind, fp=[round(v, 2) for v in fp], ox=int(t.ox+XOFF), oy=int(t.oy+YOFF), w=img.width, h=img.height); o.update(extra or {})
    objs.append(o); tiles.append(img)
for k, b in enumerate(bld):
    t = draw_building(b, 1000+k)
    add("building", t, (b["mx0"], b["mx1"], b["my0"], b["my1"]), dict(lm=b.get("lm"), cat=b.get("cat"), H=round(b["H"], 1)))
for k, p in enumerate(props):
    r = random.Random(5000+k)
    if p["kind"] == "tree": t = draw_tree(p["sub"], r)
    elif p["kind"] == "lamp": t = draw_lamp(r)
    elif p["kind"] == "bench": t = draw_bench(r)
    else: t = draw_planter(r)
    # 타일의 원점은 (0,0) 모델 좌표 기준 → 월드로 평행이동
    wx, wy = P(p["mx"], p["my"], 0)
    ox0 = t.ox+wx; oy0 = t.oy+wy
    img = t.finish(); objs.append(dict(kind=p["kind"], fp=[round(p["mx"]-.4, 2), round(p["mx"]+.4, 2), round(p["my"]-.4, 2), round(p["my"]+.4, 2)], ox=int(round(ox0)), oy=int(round(oy0)), w=img.width, h=img.height)); tiles.append(img)
# --- 출구 키오스크 ---
def draw_kiosk(kk):
    t = Tile((kk["mx0"]-1, kk["mx1"]+1, kk["my0"]-1, kk["my1"]+1, 7), pad=10)
    b = dict(kk); b.update(H=3.2, fl=1, wall=(196,200,206), roof="flat", roofcol=(236,240,244), door_face="L", door_i=0, awn=None, balc=False, shut=False)
    draw_face(t, b, "L", rng, b["wall"], 1.0); draw_face(t, b, "R", rng, b["wall"], 0.76)
    ov = 0.5
    top = [t.p(kk["mx0"]-ov, kk["my0"]-ov, 3.2), t.p(kk["mx1"]+ov, kk["my0"]-ov, 3.2), t.p(kk["mx1"]+ov, kk["my1"]+ov, 3.2), t.p(kk["mx0"]-ov, kk["my1"]+ov, 3.2)]
    t.poly(top, (60, 168, 84), (36, 110, 56))
    return t
for kk in kiosks:
    t = draw_kiosk(kk); add("kiosk", t, (kk["mx0"], kk["mx1"], kk["my0"], kk["my1"]), dict(id=kk["id"]))
# --- 2호선 고가선로 ---
DECK_Z0, DECK_Z1, HW = 7.6, 8.9, 4.2
def draw_viaduct(x0, x1, yc, station):
    t = Tile((x0, x1, yc-HW-1, yc+HW+1, DECK_Z1+6), pad=10)
    yl, yr = yc-HW, yc+HW
    # 기둥
    for px in (x0+(x1-x0)/2,):
        for z in (0,):
            t.poly([t.p(px-0.9, yc-0.9, 0), t.p(px+0.9, yc-0.9, 0), t.p(px+0.9, yc+0.9, 0), t.p(px-0.9, yc+0.9, 0)], (170,172,178), None)
        t.poly([t.p(px-0.9, yc+0.9, 0), t.p(px+0.9, yc+0.9, 0), t.p(px+0.9, yc+0.9, DECK_Z0), t.p(px-0.9, yc+0.9, DECK_Z0)], (168,170,176), (110,112,120))
        t.poly([t.p(px+0.9, yc-0.9, 0), t.p(px+0.9, yc+0.9, 0), t.p(px+0.9, yc+0.9, DECK_Z0), t.p(px+0.9, yc-0.9, DECK_Z0)], (132,134,142), (96,98,106))
    # 상판 측면
    t.poly([t.p(x0, yr, DECK_Z0), t.p(x1, yr, DECK_Z0), t.p(x1, yr, DECK_Z1), t.p(x0, yr, DECK_Z1)], (186,190,198), (120,124,134))
    t.poly([t.p(x1, yl, DECK_Z0), t.p(x1, yr, DECK_Z0), t.p(x1, yr, DECK_Z1), t.p(x1, yl, DECK_Z1)], (150,154,164), (110,114,124))
    # 상판 윗면
    t.poly([t.p(x0, yl, DECK_Z1), t.p(x1, yl, DECK_Z1), t.p(x1, yr, DECK_Z1), t.p(x0, yr, DECK_Z1)], (206,210,216), (140,144,154))
    for off in (-1.6, 1.6):               # 레일
        t.d.line([t.p(x0, yc+off, DECK_Z1+0.05), t.p(x1, yc+off, DECK_Z1+0.05)], fill=(96,100,110,255), width=2*SS)
    t.poly([t.p(x0, yc-0.5, DECK_Z1+0.04), t.p(x1, yc-0.5, DECK_Z1+0.04), t.p(x1, yc+0.5, DECK_Z1+0.04), t.p(x0, yc+0.5, DECK_Z1+0.04)], (60,181,74), None)
    # 난간
    t.d.line([t.p(x0, yr, DECK_Z1+0.9), t.p(x1, yr, DECK_Z1+0.9)], fill=(120,126,138,255), width=SS)
    t.d.line([t.p(x0, yr, DECK_Z1), t.p(x0, yr, DECK_Z1+0.9)], fill=(120,126,138,255), width=SS)
    t.d.line([t.p(x1, yr, DECK_Z1), t.p(x1, yr, DECK_Z1+0.9)], fill=(120,126,138,255), width=SS)
    if station:       # 승강장 지붕
        zt = DECK_Z1+3.6
        for (px, py) in ((x0, yl), (x0, yr), (x1, yr)):
            t.d.line([t.p(px, py, DECK_Z1), t.p(px, py, zt)], fill=(120,126,138,255), width=2*SS)
        t.poly([t.p(x0, yr, DECK_Z1+0.9), t.p(x1, yr, DECK_Z1+0.9), t.p(x1, yr, zt), t.p(x0, yr, zt)], (188,214,234,120), (150,160,172))
        t.poly([t.p(x1, yl, DECK_Z1+0.9), t.p(x1, yr, DECK_Z1+0.9), t.p(x1, yr, zt), t.p(x1, yl, zt)], (150,180,206,140), (150,160,172))
        t.poly([t.p(x0, yl, zt), t.p(x1, yl, zt), t.p(x1, yr, zt), t.p(x0, yr, zt)], (238,242,246), (150,160,172))
        t.poly([t.p(x0, yr, zt), t.p(x1, yr, zt), t.p(x1, yr, zt+0.35), t.p(x0, yr, zt+0.35)], (214,220,228), (150,160,172))
    return t
sx0 = min(ex_g[k][0] for k in ex_g)-10; sx1 = max(ex_g[k][0] for k in ex_g)+10
xx = 0.0
while xx < MW-1:
    x1 = min(xx+10, MW); xc = (xx+x1)/2
    t = draw_viaduct(xx, x1, my_line(xc), sx0 <= xc <= sx1)
    add("viaduct", t, (xx, x1, my_line(xc)-HW, my_line(xc)+HW), dict(station=bool(sx0 <= xc <= sx1)))
    xx = x1
print("objects", len(objs))
# --- 아틀라스 패킹 ---
order = sorted(range(len(tiles)), key=lambda i: -tiles[i].height)
AW = 4096; x = y = rowh = 0; pos = {}
for i in order:
    w, h = tiles[i].size
    if x + w + 2 > AW: x = 0; y += rowh + 2; rowh = 0
    pos[i] = (x, y); x += w + 2; rowh = max(rowh, h)
AH = y + rowh + 2
atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
for i, (px, py) in pos.items(): atlas.paste(tiles[i], (px, py))
for i, o in enumerate(objs): o["ax"], o["ay"] = pos[i]
atlas.save("assets/atlas.webp", quality=88, method=5)
print("atlas", atlas.size)
# --- 지면(월드) ---
gnd = np.load("_ground_T.npy")
W, H = WORLD_W, WORLD_H
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
s = (yy-YOFF)*2/CX; dd = (xx-XOFF)/CX
mxm = (s+dd)/2; mym = (s-dd)/2
inside = (mxm >= 0) & (mxm <= MW) & (mym >= 0) & (mym <= MH)
world = np.zeros((H, W, 3), np.float32)
# 배경(물): 어두운 청록 그라데이션 + 잔물결
yv = (np.arange(H)/H)[:, None, None]
world[:] = (np.array([18, 40, 58])*(1-yv) + np.array([30, 62, 80])*yv)
rip = (np.sin(xx/38 + np.sin(yy/23)*2.2) + np.sin(yy/9 + xx/80)) * 5
world += rip[..., None]*np.array([0.5, 0.9, 1.0])
g = cv2.remap(gnd, (mxm*TD).astype(np.float32), (mym*TD).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
world[inside] = g[inside]
world = np.clip(world, 0, 255).astype(np.uint8)
img = Image.fromarray(world); dr = ImageDraw.Draw(img, "RGBA")
TH = 6.5                              # 지반 두께(m)
def band(x0, y0, x1, y1, c, c2):
    p0 = P(x0, y0, 0); p1 = P(x1, y1, 0)
    pts = [p0, p1, (p1[0], p1[1]+TH*ZS), (p0[0], p0[1]+TH*ZS)]
    dr.polygon(pts, fill=c)
    n = 9
    for k in range(1, n):
        f = k/n; a_ = (p0[0], p0[1]+TH*ZS*f); b_ = (p1[0], p1[1]+TH*ZS*f)
        dr.line([a_, b_], fill=c2, width=2)
    dr.line([p0, p1], fill=(236, 230, 214, 255), width=3)
    dr.line([(p0[0], p0[1]+TH*ZS), (p1[0], p1[1]+TH*ZS)], fill=(30, 36, 44, 255), width=3)
band(0, MH, MW, MH, (132, 100, 76, 255), (110, 82, 62, 200))        # 왼쪽 아래 면
band(MW, 0, MW, MH, (104, 78, 60, 255), (86, 64, 50, 200))           # 오른쪽 아래 면
# 물 위 그림자
sh_ = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(sh_)
sd.polygon([P(0, MH, -TH), P(MW, MH, -TH), P(MW, 0, -TH), (P(MW, 0, -TH)[0]+60, P(MW, 0, -TH)[1]+40), (P(MW, MH, -TH)[0]+60, P(MW, MH, -TH)[1]+60), (P(0, MH, -TH)[0]+60, P(0, MH, -TH)[1]+60)], fill=140)
sh_ = sh_.filter(ImageFilter.GaussianBlur(26))
img = Image.composite(Image.new("RGB", (W, H), (6, 14, 22)), img, sh_.point(lambda v: int(v*.55)))
# 판 다시 그려 그림자가 판 위로 덮이지 않게
w2 = np.array(img); w2[inside] = world[inside]; img = Image.fromarray(w2); dr = ImageDraw.Draw(img, "RGBA")
band(0, MH, MW, MH, (132, 100, 76, 255), (110, 82, 62, 200)); band(MW, 0, MW, MH, (104, 78, 60, 255), (86, 64, 50, 200))
img.save("assets/ground.jpg", quality=86, optimize=True)
# --- 장면 정보 ---
scene = dict(world=[W, H], model=[MW, MH], cx=CX, zs=ZS, xoff=XOFF, yoff=YOFF,
             objects=objs, stores=[dict(id=s_["id"], mx0=s_["mx0"], mx1=s_["mx1"], my0=s_["my0"], my1=s_["my1"], door=s_["door"], doorpt=[round(v, 2) for v in s_["doorpt"]]) for s_ in stores],
             exits={k: [round(v, 2) for v in ex_g[k]] for k in ex_g}, kiosks=[{**k_, "id": k_["id"]} for k_ in kiosks],
             landmarks=[dict(name=l["name"], cat=l["cat"], g=[round(l["g"][0], 1), round(l["g"][1], 1)]) for l in lm_g],
             viaduct=dict(a=a_, b=b_, z=DECK_Z1), sites={k: [round(v[0], 1), round(v[1], 1)] for k, v in site_g.items()})
json.dump(scene, open("data/scene.json", "w"), ensure_ascii=False)
print("done")
