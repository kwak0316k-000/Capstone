"""1단계: 격자 정렬 마스크(T 공간)와 지면 텍스처를 만든다. 결과는 pickle로 저장."""
import math, pickle, numpy as np, cv2
from scipy.spatial import cKDTree
import geo
from geo import *
TD = 8                                   # T 공간: 1m = 8px
GX0, GX1, GY0, GY1 = 370, 815, -140, 215 # 모델 영역(미터)
WT, HT = int((GX1-GX0)*TD), int((GY1-GY0)*TD)
A = TD/MORIG
M = np.array([[A*C, A*S, -TD*GX0], [-A*S, A*C, -TD*GY0]], np.float64)
# 위 아핀: orig(x,y) → T = TD*(R@p/MORIG - g0), g0=(GX0,GY0) (원점 0 기준 격자 좌표)
def warp(mask, interp=cv2.INTER_NEAREST):
    return cv2.warpAffine(mask.astype(np.uint8)*255, M, (WT, HT), flags=interp, borderValue=0) > 127
road_t = warp(road, cv2.INTER_LINEAR); park_t = warp(park, cv2.INTER_LINEAR) & ~road_t; gl_t = warp(gline, cv2.INTER_LINEAR)
# 지도 밖(캡처 범위 밖) 영역: 모두 0 → 블록으로 취급되지 않게 유효 영역 마스크
valid = warp(np.ones_like(road, bool), cv2.INTER_NEAREST)
print("T size", WT, HT, "valid frac", valid.mean(), "road frac", road_t.mean())
rng = np.random.RandomState(7)
# 폭이 넓은 길(아스팔트) / 좁은 길(자갈)
small = cv2.resize(road_t.astype(np.uint8), (WT//4, HT//4), interpolation=cv2.INTER_AREA)
wide_s = cv2.morphologyEx(small, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23)))  # 약 11m
wide_t = cv2.resize(cv2.dilate(wide_s, geo.K(3)), (WT, HT), interpolation=cv2.INTER_NEAREST).astype(bool) & road_t
cob_t = road_t & ~wide_t
# 자갈 패턴: 보로노이 셀
def cobble(shape, cell_m, base, var, seed):
    h, w = shape; r = np.random.RandomState(seed)
    n = int(h*w/ (cell_m*TD)**2 * 1.2)
    pts = np.stack([r.rand(n)*w, r.rand(n)*h], 1)
    tree = cKDTree(pts)
    yy, xx = np.mgrid[0:h:2, 0:w:2]; q = np.stack([xx.ravel(), yy.ravel()], 1)
    d, idx = tree.query(q, k=2)
    cid = idx[:, 0]; edge = (d[:, 1]-d[:, 0]) < 1.3
    col = np.array(base, np.float32)[None, :] + (r.rand(n, 1)*2-1)*var
    img = col[cid].reshape(yy.shape[0], yy.shape[1], 3)
    mort = np.array([168, 162, 152], np.float32)
    img[edge.reshape(yy.shape)] = mort
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
    return img
print("cobble...")
cob = cobble((HT, WT), 1.25, (208, 202, 190), 14, 1)
print("ground...")
gnd = np.zeros((HT, WT, 3), np.float32)
gnd[:] = (214, 208, 196)                                   # 보도·대지
nz = cv2.resize((rng.rand(HT//16+1, WT//16+1)*14).astype(np.float32), (WT, HT), interpolation=cv2.INTER_CUBIC)
gnd += (nz[..., None]-7)
# 보도 블록 줄눈
gx_line = (np.arange(WT) % (TD*1) < 1)[None, :]; gy_line = (np.arange(HT) % (TD*1) < 1)[:, None]
gnd[(gx_line | gy_line)] -= 6
curb_t = cv2.dilate(road_t.astype(np.uint8), geo.K(int(TD*1.0))).astype(bool) & ~road_t
gnd[curb_t] = (232, 228, 218)
asph = np.zeros_like(gnd); asph[:] = (118, 124, 134)
asph += (nz[..., None]-7)*0.6
gnd[cob_t] = cob[cob_t]
gnd[wide_t] = asph[wide_t]
# 길 가장자리 어두운 선
edge = cv2.morphologyEx(road_t.astype(np.uint8), cv2.MORPH_GRADIENT, geo.K(2)).astype(bool)
gnd[edge] = (150, 144, 134)
# 잔디(공원)
grass = np.zeros_like(gnd); grass[:] = (150, 198, 112)
blade = cv2.resize((rng.rand(HT//3, WT//3)*40).astype(np.float32), (WT, HT), interpolation=cv2.INTER_NEAREST)
grass += (blade[..., None]-20)*np.array([0.5, 0.8, 0.3])
gnd[park_t] = grass[park_t]
pe = cv2.morphologyEx(park_t.astype(np.uint8), cv2.MORPH_GRADIENT, geo.K(3)).astype(bool)
gnd[pe] = (110, 160, 90)
# 도로 표시선(아스팔트): 중앙 점선 — 넓은 길의 골격 위에
if True:
    from skimage.morphology import skeletonize
    sk = skeletonize(cv2.resize(wide_t.astype(np.uint8), (WT//2, HT//2), interpolation=cv2.INTER_NEAREST) > 0)
    sk = cv2.resize(sk.astype(np.uint8), (WT, HT), interpolation=cv2.INTER_NEAREST) > 0
ysk, xsk = np.nonzero(sk)
dash = ((xsk//(TD*3) + ysk//(TD*3)) % 2 == 0)
for x, y in zip(xsk[dash][::1], ysk[dash][::1]): gnd[max(0,y-1):y+2, max(0,x-1):x+2] = (238, 236, 226)
gnd = np.clip(gnd, 0, 255).astype(np.uint8)
gnd[~valid] = (200, 196, 186)
pickle.dump(dict(road=road_t, park=park_t, wide=wide_t, valid=valid, gl=gl_t), open("data/_tmasks.pkl", "wb"))
cv2.imwrite("_ground_T.jpg", cv2.cvtColor(cv2.resize(gnd, (WT//3, HT//3), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
np.save("_ground_T.npy", gnd)
print("done")
