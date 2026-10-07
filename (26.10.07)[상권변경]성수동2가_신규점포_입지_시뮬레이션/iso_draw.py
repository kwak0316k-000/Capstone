"""아이소메트릭 오브젝트(건물·나무·가로등·고가선로) 타일 그리기."""
import math, random
from PIL import Image, ImageDraw
from iso_common import CX, ZS
SS = 2
FH = 3.0                                  # 한 층 높이(m)
def sh(c, f): return tuple(int(max(0, min(255, v*f))) for v in c[:3])
def mixc(a, b, t): return tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3))
def jit(c, r, a=10): return tuple(int(max(0, min(255, v + r.uniform(-a, a)))) for v in c)

class Tile:
    """모델 좌표 (mx,my,z) 로 그리는 로컬 캔버스. 원점은 (ox,oy) 월드 픽셀."""
    def __init__(self, bounds, pad=14):
        # bounds: (mx0,mx1,my0,my1,ztop)
        mx0, mx1, my0, my1, zt = bounds
        xs = []; ys = []
        for mx in (mx0, mx1):
            for my in (my0, my1):
                for z in (0, zt):
                    x, y = self.raw(mx, my, z); xs.append(x); ys.append(y)
        self.ox = math.floor(min(xs)) - pad; self.oy = math.floor(min(ys)) - pad
        self.w = math.ceil(max(xs)) + pad - self.ox; self.h = math.ceil(max(ys)) + pad - self.oy
        self.im = Image.new("RGBA", (self.w*SS, self.h*SS), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.im, "RGBA")
    @staticmethod
    def raw(mx, my, z=0.0):
        return ((mx-my)*CX, (mx+my)*CX/2 - z*ZS)
    def p(self, mx, my, z=0.0):
        x, y = self.raw(mx, my, z); return ((x-self.ox)*SS, (y-self.oy)*SS)
    def poly(self, pts, fill, outline=None, width=1):
        self.d.polygon(pts, fill=fill)
        if outline: self.d.line(pts+[pts[0]], fill=outline, width=width*SS)
    def finish(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)

WALLS = [(240,222,178),(238,208,126),(236,190,150),(228,178,162),(212,210,204),(248,246,240),(180,106,86),(156,104,76),(182,202,176),(172,190,206),(224,200,150),(244,214,196)]
ROOFS = {"terra":[(196,104,66),(184,92,56),(206,118,78)], "teal":[(84,154,170),(72,138,156),(98,168,182)], "brown":[(126,82,62),(110,70,54)], "slate":[(96,104,120),(84,92,108)]}
AWN = [((54,98,176),(250,250,248)), ((196,50,56),(250,250,248)), ((46,128,84),(250,250,248)), ((226,170,40),(250,250,248)), ((126,70,150),(250,250,248))]

def face_pt(face, b, s, z):
    """face 'L'(gy=gy1, 왼쪽 아래 면) / 'R'(gx=gx1, 오른쪽 아래 면)"""
    if face == "L": return (b["mx0"]+s, b["my1"], z)
    return (b["mx1"], b["my0"]+s, z)

def draw_face(t, b, face, r, wall, shade):
    L = (b["mx1"]-b["mx0"]) if face == "L" else (b["my1"]-b["my0"])
    H = b["H"]; base = sh(wall, shade); line = sh(wall, shade*0.62)
    p = [t.p(*face_pt(face, b, 0, 0)), t.p(*face_pt(face, b, L, 0)), t.p(*face_pt(face, b, L, H)), t.p(*face_pt(face, b, 0, H))]
    t.poly(p, base, line)
    # 층 띠
    for f in range(1, b["fl"]):
        z = f*FH
        t.d.line([t.p(*face_pt(face, b, 0, z)), t.p(*face_pt(face, b, L, z))], fill=sh(wall, shade*1.1)+(255,), width=SS)
        t.d.line([t.p(*face_pt(face, b, 0, z-0.35)), t.p(*face_pt(face, b, L, z-0.35))], fill=sh(wall, shade*0.8)+(150,), width=SS)
    if L < 4.2: return
    frame = (252, 250, 244); glass = (70, 100, 124); glass2 = (110, 142, 164)
    n = max(1, int((L-1.6)//3.0)); gap = (L-1.6)/n
    shop = b["fl"] >= 1
    awn = b["awn"] if b.get("awn_face") == face else None
    for i in range(n):
        cs = 0.8 + gap*i + gap/2
        for f in range(b["fl"]):
            z0 = f*FH
            if f == 0 and shop:
                if b.get("door_face") == face and i == b["door_i"]:                   # 문
                    ww, z1, z2 = 1.5, 0.0, 2.5
                    q = [(cs-ww/2, z1), (cs+ww/2, z1), (cs+ww/2, z2), (cs-ww/2, z2)]
                    t.poly([t.p(*face_pt(face, b, s, z)) for s, z in q], sh((120, 78, 52), shade), sh((60, 40, 30), 1))
                    continue
                ww, z1, z2 = min(2.2, gap-0.5), 0.5, 2.5
            else:
                ww, z1, z2 = 1.25, z0+0.95, z0+2.55
            q = [(cs-ww/2, z1), (cs+ww/2, z1), (cs+ww/2, z2), (cs-ww/2, z2)]
            fr = [t.p(*face_pt(face, b, s, z)) for s, z in [(cs-ww/2-0.12, z1-0.12), (cs+ww/2+0.12, z1-0.12), (cs+ww/2+0.12, z2+0.12), (cs-ww/2-0.12, z2+0.12)]]
            t.poly(fr, sh(frame, shade))
            t.poly([t.p(*face_pt(face, b, s, z)) for s, z in q], sh(glass, 1.0), None)
            hi = [(cs-ww/2, z1+(z2-z1)*0.55), (cs+ww/2, z1+(z2-z1)*0.55), (cs+ww/2, z2), (cs-ww/2, z2)]
            t.poly([t.p(*face_pt(face, b, s, z)) for s, z in hi], glass2+(160,), None)
            t.d.line([t.p(*face_pt(face, b, cs, z1)), t.p(*face_pt(face, b, cs, z2))], fill=sh(frame, shade)+(255,), width=SS)
            if f >= 1 and b.get("balc") and f == 1:
                bq = [(cs-ww/2-0.3, z1-0.05), (cs+ww/2+0.3, z1-0.05), (cs+ww/2+0.3, z1+0.75), (cs-ww/2-0.3, z1+0.75)]
                t.d.line([t.p(*face_pt(face, b, s, z)) for s, z in bq[:2]], fill=(52, 56, 66, 255), width=SS)
                t.d.line([t.p(*face_pt(face, b, s, z)) for s, z in bq[3:1:-1]], fill=(52, 56, 66, 255), width=SS)
                for k in range(5):
                    ss = cs-ww/2-0.3 + (ww+0.6)*k/4
                    t.d.line([t.p(*face_pt(face, b, ss, z1-0.05)), t.p(*face_pt(face, b, ss, z1+0.75))], fill=(52, 56, 66, 230), width=SS)
            elif f >= 1 and b.get("shut"):
                for sd in (-1, 1):
                    xs = cs + sd*(ww/2+0.38)
                    sq = [(xs-0.26, z1), (xs+0.26, z1), (xs+0.26, z2), (xs-0.26, z2)]
                    t.poly([t.p(*face_pt(face, b, s, z)) for s, z in sq], sh((70, 126, 92), shade), None)
        if awn is not None and i % 1 == 0:
            pass
    if awn is not None:
        c1, c2 = awn
        out = 1.5
        nst = int(L//0.9)
        for k in range(nst):
            s0, s1 = L*k/nst, L*(k+1)/nst
            def aw(s, o, z):
                x, y, zz = face_pt(face, b, s, z)
                if face == "L": y += o
                else: x += o
                return t.p(x, y, zz)
            q = [aw(s0, 0, 2.95), aw(s1, 0, 2.95), aw(s1, out, 2.35), aw(s0, out, 2.35)]
            t.poly(q, sh(c1 if k % 2 == 0 else c2, 1.0 if face == "L" else 0.82), sh(c1, 0.6))
        # 처마 아래 가장자리 물결
def draw_roof(t, b, r):
    mx0, mx1, my0, my1, H = b["mx0"], b["mx1"], b["my0"], b["my1"], b["H"]
    w, d = mx1-mx0, my1-my0
    if b["roof"] in ("terra", "teal", "brown", "slate"):
        col = b["roofcol"]; rh = min(min(w, d)*0.34, 4.6); ov = 0.55
        ridge_x = w >= d
        if ridge_x:
            gym = (my0+my1)/2
            R0 = (mx0-ov, gym, H+rh); R1 = (mx1+ov, gym, H+rh)
            slopes = [("back", [(mx0-ov, my0-ov, H-0.1), (mx1+ov, my0-ov, H-0.1), R1, R0], (0, -1)),
                      ("front", [(mx0-ov, my1+ov, H-0.1), (mx1+ov, my1+ov, H-0.1), R1, R0], (0, 1))]
            # 박공 벽(오른쪽 면)
            tri = [(mx1, my0, H), (mx1, my1, H), (mx1, gym, H+rh)]
            t.poly([t.p(*q) for q in tri], sh(b["wall"], 0.78), sh(b["wall"], 0.48))
        else:
            gxm = (mx0+mx1)/2
            R0 = (gxm, my0-ov, H+rh); R1 = (gxm, my1+ov, H+rh)
            slopes = [("back", [(mx0-ov, my0-ov, H-0.1), (mx0-ov, my1+ov, H-0.1), R1, R0], (-1, 0)),
                      ("front", [(mx1+ov, my0-ov, H-0.1), (mx1+ov, my1+ov, H-0.1), R1, R0], (1, 0))]
            tri = [(mx0, my1, H), (mx1, my1, H), (gxm, my1, H+rh)]
            t.poly([t.p(*q) for q in tri], sh(b["wall"], 1.0), sh(b["wall"], 0.6))
        mask = Image.new("L", t.im.size, 0); md = ImageDraw.Draw(mask)
        for nm, pts, nrm in slopes:
            br = max(0.66, min(1.0, 0.86 + 0.14*(nrm[1]-nrm[0])))
            pp = [t.p(*q) for q in pts]
            t.poly(pp, sh(col, br), sh(col, br*0.58))
            md.polygon(pp, fill=255)
            # 기와 줄
            a0, a1 = pts[0], pts[1]; r0, r1 = pts[3], pts[2]
            nl = 7
            for k in range(1, nl):
                f = k/nl
                e0 = tuple(a0[i]+(r0[i]-a0[i])*f for i in range(3)); e1 = tuple(a1[i]+(r1[i]-a1[i])*f for i in range(3))
                t.d.line([t.p(*e0), t.p(*e1)], fill=sh(col, br*0.8)+(170,), width=SS)
            t.d.line([t.p(*pts[3]), t.p(*pts[2])], fill=sh(col, br*1.18)+(255,), width=2*SS)
        if b.get("ivy"):
            iv = Image.new("RGBA", t.im.size, (0, 0, 0, 0)); idr = ImageDraw.Draw(iv)
            for _ in range(b["ivy"]):
                f1, f2 = r.random(), r.random(); sl = slopes[r.randint(0, 1)][1]
                x = sl[0][0]+(sl[1][0]-sl[0][0])*f1; y = sl[0][1]+(sl[1][1]-sl[0][1])*f1; zz = sl[0][2]+(sl[3][2]-sl[0][2])*f2
                x += (sl[3][0]-sl[0][0])*f2; y += (sl[3][1]-sl[0][1])*f2
                cx_, cy_ = t.p(x, y, zz); rr = r.uniform(5, 12)*SS
                idr.ellipse([cx_-rr, cy_-rr*.6, cx_+rr, cy_+rr*.6], fill=jit((92, 152, 76), r, 14)+(235,))
                idr.ellipse([cx_-rr*.6, cy_-rr*.6, cx_+rr*.2, cy_-rr*.05], fill=(138, 192, 104, 220))
            t.im.paste(iv, (0, 0), Image.composite(iv.split()[3], Image.new("L", t.im.size, 0), mask))
    else:   # 평지붕
        top = [t.p(mx0, my0, H), t.p(mx1, my0, H), t.p(mx1, my1, H), t.p(mx0, my1, H)]
        rc = b["roofcol"]
        t.poly(top, rc, sh(rc, 0.6))
        par = 0.55
        # 난간: 앞쪽 두 면 안쪽
        for face in ("L", "R"):
            pts = [face_pt(face, b, 0, H), face_pt(face, b, (w if face == "L" else d), H), face_pt(face, b, (w if face == "L" else d), H+par), face_pt(face, b, 0, H+par)]
            t.poly([t.p(*q) for q in pts], sh(b["wall"], 1.0 if face == "L" else 0.78), sh(b["wall"], 0.55))
        if b.get("garden"):
            ins = 1.1
            g = [t.p(mx0+ins, my0+ins, H+0.05), t.p(mx1-ins, my0+ins, H+0.05), t.p(mx1-ins, my1-ins, H+0.05), t.p(mx0+ins, my1-ins, H+0.05)]
            t.poly(g, (112, 168, 92), (84, 134, 72))
            for _ in range(int(w*d/14)+2):
                x = r.uniform(mx0+1.4, mx1-1.4); y = r.uniform(my0+1.4, my1-1.4); cx_, cy_ = t.p(x, y, H+0.5); rr = r.uniform(4, 8)*SS
                t.d.ellipse([cx_-rr, cy_-rr, cx_+rr, cy_+rr*.8], fill=jit((84, 150, 78), r, 16)+(255,))
                if r.random() < .4: t.d.ellipse([cx_-rr*.3, cy_-rr*.7, cx_+rr*.3, cy_-rr*.1], fill=r.choice([(240,120,150),(250,210,90),(250,250,250)])+(255,))
        elif w*d > 60 and r.random() < .7:
            for _ in range(r.randint(1, 3)):
                x = r.uniform(mx0+1.2, mx1-2.2); y = r.uniform(my0+1.2, my1-2.2); a = t.p(x, y, H+0.1); bx = t.p(x+1.6, y+1.2, H+0.1)
                bt = [t.p(x, y, H+0.1), t.p(x+1.6, y, H+0.1), t.p(x+1.6, y+1.2, H+0.1), t.p(x, y+1.2, H+0.1)]
                t.poly(bt, (178, 180, 186), (110, 112, 120))
                tt = [t.p(x, y, H+1.0), t.p(x+1.6, y, H+1.0), t.p(x+1.6, y+1.2, H+1.0), t.p(x, y+1.2, H+1.0)]
                t.poly([t.p(x+1.6, y, H+0.1), t.p(x+1.6, y+1.2, H+0.1), t.p(x+1.6, y+1.2, H+1.0), t.p(x+1.6, y, H+1.0)], (140, 142, 150), None)
                t.poly([t.p(x, y+1.2, H+0.1), t.p(x+1.6, y+1.2, H+0.1), t.p(x+1.6, y+1.2, H+1.0), t.p(x, y+1.2, H+1.0)], (196, 198, 204), None)
                t.poly(tt, (214, 216, 222), (120, 122, 130))
def draw_building(b, seed):
    r = random.Random(seed)
    zt = b["H"] + 6
    t = Tile((b["mx0"]-1.6, b["mx1"]+1.6, b["my0"]-1.6, b["my1"]+1.6, zt), pad=10)
    draw_face(t, b, "L", r, b["wall"], 1.0); draw_face(t, b, "R", r, b["wall"], 0.76)
    draw_roof(t, b, r)
    return t
def draw_tree(kind, r):
    t = Tile((-4, 4, -4, 4, 9), pad=6)
    t.d.ellipse([*t.p(-2.2, -0.4, 0), *t.p(2.0, 2.2, 0)], fill=(60, 60, 50, 70)) if False else None
    cx_, cy_ = t.p(0, 0, 0)
    t.d.ellipse([cx_-14*SS, cy_-5*SS, cx_+14*SS, cy_+6*SS], fill=(40, 50, 40, 70))
    t.d.rectangle([cx_-2*SS, cy_-22*SS, cx_+2*SS, cy_], fill=(104, 76, 54, 255))
    pal = {"g": [(82, 148, 82), (108, 172, 96), (66, 124, 72)], "p": [(236, 150, 176), (250, 190, 206), (214, 120, 150)], "y": [(150, 190, 84), (186, 214, 104), (122, 164, 70)]}[kind]
    blobs = [(0, -34, 17), (-11, -26, 13), (11, -26, 13), (0, -44, 12), (-7, -38, 11), (8, -38, 11)]
    for i, (bx, by, br) in enumerate(blobs):
        c = pal[0] if i < 3 else pal[2] if i == 4 else pal[0]
        t.d.ellipse([cx_+(bx-br)*SS, cy_+(by-br*.9)*SS, cx_+(bx+br)*SS, cy_+(by+br*.9)*SS], fill=jit(c, r, 6)+(255,), outline=sh(c, .7)+(255,))
    for bx, by, br in [(-4, -40, 7), (5, -33, 6), (-9, -30, 5)]:
        t.d.ellipse([cx_+(bx-br)*SS, cy_+(by-br*.8)*SS, cx_+(bx+br)*SS, cy_+(by+br*.8)*SS], fill=pal[1]+(235,))
    return t
def draw_lamp(r):
    t = Tile((-1, 1, -1, 1, 6), pad=8); cx_, cy_ = t.p(0, 0, 0)
    t.d.ellipse([cx_-6*SS, cy_-2*SS, cx_+6*SS, cy_+3*SS], fill=(40, 40, 40, 60))
    t.d.rectangle([cx_-1.2*SS, cy_-34*SS, cx_+1.2*SS, cy_], fill=(52, 58, 70, 255))
    t.d.ellipse([cx_-5*SS, cy_-40*SS, cx_+5*SS, cy_-30*SS], fill=(255, 226, 150, 255), outline=(52, 58, 70, 255))
    return t
def draw_bench(r):
    t = Tile((-1.2, 1.2, -0.5, 0.5, 1.2), pad=6)
    for z, col in ((0.5, (150, 100, 66)), (1.0, (130, 86, 58))):
        t.poly([t.p(-1.1, -0.4, z), t.p(1.1, -0.4, z), t.p(1.1, 0.4, z), t.p(-1.1, 0.4, z)], col+(255,), (80, 52, 36, 255))
    return t
def draw_planter(r):
    t = Tile((-1, 1, -1, 1, 3), pad=6); cx_, cy_ = t.p(0, 0, 0)
    t.poly([t.p(-.7, -.7, .7), t.p(.7, -.7, .7), t.p(.7, .7, .7), t.p(-.7, .7, .7)], (112, 168, 92), (80, 60, 44))
    t.poly([t.p(-.7, .7, 0), t.p(.7, .7, 0), t.p(.7, .7, .7), t.p(-.7, .7, .7)], (176, 118, 84), (110, 72, 50))
    t.poly([t.p(.7, -.7, 0), t.p(.7, .7, 0), t.p(.7, .7, .7), t.p(.7, -.7, .7)], (146, 96, 68), (110, 72, 50))
    for _ in range(7):
        x, y = r.uniform(-.5, .5), r.uniform(-.5, .5); px, py = t.p(x, y, 1.0)
        t.d.ellipse([px-4*SS, py-4*SS, px+4*SS, py+4*SS], fill=r.choice([(240,110,140),(250,210,90),(250,250,250),(180,130,230)])+(255,), outline=(70,110,60,255))
    return t
