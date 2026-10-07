"""구글맵 캡처에서 도로를 뽑아 도로 그래프(JSON)를 만든다.
도로 색(청회색)만 골라 마스크 → 골격화 → 교차점/끝점으로 끊어 단순화.
"""
import json, numpy as np, networkx as nx
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize, disk, binary_closing, remove_small_objects
from skimage.measure import approximate_polygon

im = np.array(Image.open("data/map_src.png").convert("RGB")).astype(int)
R, G, B = im[..., 0], im[..., 1], im[..., 2]
mask = (R > 192) & (R < 236) & (G > 198) & (G < 240) & (B > 205) & (B < 244) & (B - R >= 4) & (B - R <= 26) & (G <= B + 1)
mask[:50, :] = False                       # 상단 검색 UI 영역 제외
mask[1500:, :] = False; mask[:, :2]=False                      # 하단 저작권 문구 제외
mask = binary_closing(mask, disk(4))
mask = remove_small_objects(mask, 900)
sk = skeletonize(mask)
H, W = sk.shape
ys, xs = np.nonzero(sk)
g = nx.Graph()
S = set(zip(xs.tolist(), ys.tolist()))
for x, y in S:
    for dx, dy in ((1,0),(0,1),(1,1),(-1,1)):
        if (x+dx, y+dy) in S: g.add_edge((x,y),(x+dx,y+dy), w=(dx*dx+dy*dy)**.5)
# 작은 덩어리 제거
for comp in list(nx.connected_components(g)):
    if len(comp) < 120: g.remove_nodes_from(comp)
# 짧은 가지(스퍼) 반복 제거
def prune(g, minlen=22):
    changed = True
    while changed:
        changed = False
        ends = [n for n in g if g.degree(n) == 1]
        for e in ends:
            if e not in g: continue
            path=[e]; cur=e; prev=None
            while True:
                nb=[n for n in g[cur] if n!=prev]
                if len(nb)!=1: break
                prev,cur=cur,nb[0]; path.append(cur)
                if len(path)>minlen: break
            if len(path)<=minlen and g.degree(cur)>=3:
                g.remove_nodes_from(path[:-1]); changed=True
    return g
g = prune(g)
# 교차점/끝점 기준으로 경로 추적
keys = {n for n in g if g.degree(n) != 2}
if not keys: keys = {next(iter(g))}
nodes = {}; edges = []
def nid(p):
    if p not in nodes: nodes[p]=len(nodes)
    return nodes[p]
seen=set()
for k in keys:
    for nb in g[k]:
        if (k,nb) in seen: continue
        path=[k,nb]; prev,cur=k,nb
        while cur not in keys:
            nxts=[n for n in g[cur] if n!=prev]
            if not nxts: break
            prev,cur=cur,nxts[0]; path.append(cur)
        seen.add((path[-1],path[-2])); seen.add((k,nb))
        arr=np.array(path,float)
        simp=approximate_polygon(arr, tolerance=3.0)
        ids=[nid(tuple(map(int,p))) for p in simp]
        for a,b in zip(ids,ids[1:]):
            if a!=b: edges.append((a,b))
pts=[None]*len(nodes)
for p,i in nodes.items(): pts[i]=p
edges=sorted({tuple(sorted(e)) for e in edges})
print("nodes",len(pts),"edges",len(edges))
json.dump({"W":W,"H":H,"nodes":pts,"edges":edges}, open("roadgraph.json","w"))
# 확인용 겹쳐 그리기
from PIL import ImageDraw
ov=Image.open("data/map_src.png").convert("RGB"); d=ImageDraw.Draw(ov)
for a,b in edges: d.line([pts[a],pts[b]],fill=(230,0,80),width=3)
for p in pts: d.ellipse([p[0]-3,p[1]-3,p[0]+3,p[1]+3],fill=(0,90,255))
ov.save("overlay.png")
