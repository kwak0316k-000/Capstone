"""지도 캡처(원본 픽셀) ↔ 격자 좌표(미터) ↔ 아이소메트릭 화면 좌표 변환과 마스크 추출."""
import math, numpy as np, cv2
from PIL import Image
from skimage.morphology import skeletonize
MORIG = 2.365            # 원본 캡처 1m = 2.365px (축척 막대 100m = 약 236px)
FD = 2848/1999           # 화면에서 읽은 좌표 → 원본 픽셀 배율
src = np.array(Image.open("data/map_src.png").convert("RGB"))[48:1500]
H0, W0 = src.shape[:2]
R_, G_, B_ = [src[..., i].astype(int) for i in range(3)]
def K(r): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
def clean(m, close, minarea, holearea):
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, K(close))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= minarea: keep[lab == i] = 1
    inv = (1-keep).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < holearea and x > 0 and y > 0 and x+w < W0 and y+h < H0: keep[lab == i] = 1
    return keep.astype(bool)
road_raw = (R_>192)&(R_<236)&(G_>198)&(G_<240)&(B_>205)&(B_<244)&(B_-R_>=4)&(B_-R_<=26)&(G_<=B_+1)
gline_raw = (G_-R_>=35)&(G_-B_>=45)&(G_>120)&(G_<200)
park_raw = (G_-R_>=14)&(G_-B_>=10)&(G_>=222)
gline = clean(gline_raw, 2, 200, 100)
n, lab, st, _ = cv2.connectedComponentsWithStats(gline.astype(np.uint8), 8)
gline = lab == (1+np.argmax(st[1:, cv2.CC_STAT_AREA]))                 # 가장 큰 초록 선만
road = clean(road_raw | cv2.dilate(gline_raw.astype(np.uint8), K(3)).astype(bool), 7, 1500, 900)
park = clean(park_raw, 5, 2500, 3000) & ~road
# 아차산로(2호선) 방향 각도: 초록 선 골격에 직선을 맞춘다
sk = skeletonize(gline); ys, xs = np.nonzero(sk)
slope = np.polyfit(xs, ys, 1)[0]; THETA = math.atan(slope)
C, S = math.cos(THETA), math.sin(THETA)
def orig_to_g(xo, yo):                  # 원본 픽셀(크롭 기준) → 격자 미터 (원점 임의)
    return ((xo*C + yo*S)/MORIG, (-xo*S + yo*C)/MORIG)
def disp_to_orig(xd, yd): return xd*FD, yd*FD - 48
def disp_to_g(xd, yd): return orig_to_g(*disp_to_orig(xd, yd))
if __name__ == "__main__":
    print("theta deg", math.degrees(THETA))
    pts = {"A":(885,293),"F":(670,212),"B":(1003,255),"C":(600,345),"D":(840,640),"E":(1100,760),
           "ex1":(673,193),"ex4":(668,230),"ex2":(892,274),"ex3":(878,313),"dae":(832,628),"kkop":(950,435),"oy":(620,312),"cafe":(1003,240),"mifi":(1003,585),"anmok":(1001,716),"tam":(407,358),"nw":(215,40),"s":(690,1045)}
    g = {k: disp_to_g(*v) for k, v in pts.items()}
    for k, v in g.items(): print(k, [round(t,1) for t in v])
