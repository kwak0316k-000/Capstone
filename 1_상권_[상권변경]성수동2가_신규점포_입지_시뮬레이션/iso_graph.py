"""도로 그래프를 모델 영역(미터)으로 옮기고 경계에서 잘라 시뮬레이션용 그래프(data/iso_graph.json)를 만든다."""
import json, math, numpy as np, networkx as nx
import geo
from geo import orig_to_g, disp_to_g
from iso_common import *
gj = json.load(open("data/roadgraph.json")); pts = np.array(gj["nodes"], float)
gx, gy = orig_to_g(pts[:, 0], pts[:, 1]-48); P_ = np.stack([gx-GX0, gy-GY0], 1)
LO = np.array([1.0, 1.0]); HI = np.array([MW-1.0, MH-1.0])
def clip(p, q):
    d = q-p; t0, t1 = 0.0, 1.0
    for i in range(2):
        for s, bnd in ((-1, p[i]-LO[i]), (1, HI[i]-p[i])):
            den = s*d[i]*(-1 if s == -1 else 1)
    # Liang-Barsky
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-d[0], p[0]-LO[0]), (d[0], HI[0]-p[0]), (-d[1], p[1]-LO[1]), (d[1], HI[1]-p[1])):
        if abs(pp) < 1e-12:
            if qq < 0: return None
        else:
            r = qq/pp
            if pp < 0: t0 = max(t0, r)
            else: t1 = min(t1, r)
    return (t0, t1) if t0 < t1 else None
nodes = {}; edges = set(); bnd = set()
def nid(pt, b=False):
    k = (round(float(pt[0]), 1), round(float(pt[1]), 1))
    if k not in nodes: nodes[k] = len(nodes)
    if b: bnd.add(nodes[k])
    return nodes[k]
for a, b in gj["edges"]:
    p, q = P_[a], P_[b]; c = clip(p, q)
    if c is None: continue
    t0, t1 = c; p2 = p+(q-p)*t0; q2 = p+(q-p)*t1
    ia = nid(p2, t0 > 1e-9); ib = nid(q2, t1 < 1-1e-9)
    if ia != ib: edges.add((min(ia, ib), max(ia, ib)))
g = nx.Graph(); g.add_edges_from(edges)
from scipy.spatial import cKDTree
inv0 = {v: k for k, v in nodes.items()}
ids_ = sorted(g.nodes); coords = np.array([inv0[n] for n in ids_]); tree = cKDTree(coords)
for R in (14, 30):
    while True:
        comps = list(nx.connected_components(g)); cid = {n: i for i, c in enumerate(comps) for n in c}
        done = True
        for ii, n in enumerate(ids_):
            for jj in tree.query_ball_point(coords[ii], R):
                m = ids_[jj]
                if cid[n] != cid[m]: g.add_edge(n, m); done = False; break
            if not done: break
        if done: break
print("components", len(list(nx.connected_components(g))))
comp = max(nx.connected_components(g), key=len); g = g.subgraph(comp).copy()
inv = {v: k for k, v in nodes.items()}
ids = {n: f"n{i}" for i, n in enumerate(sorted(g.nodes))}
N = {ids[n]: [inv[n][0], inv[n][1]] for n in g.nodes}
E = [[ids[a], ids[b]] for a, b in g.edges]
B = [ids[n] for n in bnd if n in ids]
def nearest(x, y, among=None):
    keys = among or list(N)
    return min(keys, key=lambda k: (N[k][0]-x)**2 + (N[k][1]-y)**2)
scene = json.load(open("data/scene.json"))
nw = disp_to_g(215, 40); so = disp_to_g(690, 1045)
gates = {}
def addg(k, w): gates[k] = gates.get(k, 0)+w
addg(nearest(nw[0]-GX0, nw[1]-GY0, B), 2.394); addg(nearest(so[0]-GX0, so[1]-GY0, B), 1.278)
for k in scene["kiosks"]:
    cx, cy = (k["mx0"]+k["mx1"])/2, (k["my0"]+k["my1"])/2; addg(nearest(cx, cy), 1.411/4)
AN = {"대림창고 갤러리": .28, "꼽당 성수점": .17, "올리브영N 성수": .10, "성수동 카페거리": .15, "미피스토어 서울": .08, "안목 성수": .08}
anchors = {}
for l in scene["landmarks"]:
    if l["name"] in AN:
        k = nearest(*l["g"]); anchors[k] = anchors.get(k, 0)+AN[l["name"]]
for k in scene["kiosks"]:
    cx, cy = (k["mx0"]+k["mx1"])/2, (k["my0"]+k["my1"])/2; kk = nearest(cx, cy); anchors[kk] = anchors.get(kk, 0)+0.0175
json.dump(dict(nodes=N, edges=E, gates=gates, anchors=anchors), open("data/iso_graph.json", "w"))
print("nodes", len(N), "edges", len(E), "boundary", len(B), "gates", gates)
print("anchors", anchors)
