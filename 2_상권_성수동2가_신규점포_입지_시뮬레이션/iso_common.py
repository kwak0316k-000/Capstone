import math
CX = 5.0            # 1m(축 방향) = 가로 5px, 세로 2.5px
ZS = 6.0            # 높이 1m = 6px
GX0, GX1, GY0, GY1 = 370, 815, -140, 215
MW, MH = GX1-GX0, GY1-GY0        # 모델 폭(gx), 깊이(gy) [m]
MARGIN_X = 160; MARGIN_TOP = 330; MARGIN_BOT = 150
XOFF = MH*CX + MARGIN_X
YOFF = MARGIN_TOP
WORLD_W = int((MW+MH)*CX + 2*MARGIN_X)
WORLD_H = int((MW+MH)*CX/2 + MARGIN_TOP + MARGIN_BOT)
def P(mx, my, z=0.0):
    """모델 좌표(m, 영역 원점 기준) → 월드 픽셀"""
    return ((mx-my)*CX + XOFF, (mx+my)*CX/2 + YOFF - z*ZS)
def Pinv(X, Y):
    s = (Y-YOFF)*2/CX; d = (X-XOFF)/CX
    return ((s+d)/2, (s-d)/2)
