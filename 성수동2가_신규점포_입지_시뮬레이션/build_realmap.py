"""구글맵 캡처 + 추출한 도로 그래프로 index.html의 CONFIG를 만든다."""
import json, re, networkx as nx
from PIL import Image
gj=json.load(open("data/roadgraph.json"))
F=2848/1999; Y0=48; S=1200/2848
im=Image.open("data/map_src.png").convert("RGB").crop((0,Y0,2848,1500)); im.save("assets/seongsu_map.png")
Wc,Hc=1200,round(im.height*S)
pts=gj["nodes"]; g=nx.Graph(); g.add_edges_from(map(tuple,gj["edges"]))
ids={n:i for i,n in enumerate(sorted(g.nodes))}
P={f"n{ids[n]}":[round(pts[n][0]*S),round((pts[n][1]-Y0)*S)] for n in g.nodes}
E=[[f"n{ids[a]}",f"n{ids[b]}"] for a,b in g.edges]
def snap(x,y):
    x,y=x*F,y*F
    X,Yy=x*S,(y-Y0)*S
    return min(P,key=lambda k:(P[k][0]-X)**2+(P[k][1]-Yy)**2)
gates={}
def addg(k,w): gates[k]=gates.get(k,0)+w
addg(snap(215,40),2.394); addg(snap(690,1045),1.278)
# 성수역 2호선 출구(사용자 제공 확대 지도로 위치 확인): 1·4번=서측, 2·3번=동측. 유입 배분은 4곳 균등(가정)
EXITS={"1":(673,193),"4":(668,230),"2":(892,274),"3":(878,313)}
for k,(x,y) in EXITS.items(): addg(snap(x,y),1.411/4)
anch_px={(830,630):.28,(950,435):.17,(620,312):.10,(1003,240):.15,(1003,585):.08,(1003,716):.08,(407,358):.07,(673,193):.0175,(668,230):.0175,(892,274):.0175,(878,313):.0175}
anchors={}
for (x,y),w in anch_px.items(): k=snap(x,y); anchors[k]=anchors.get(k,0)+w
def sp(x,y): x,y=x*F,y*F; return [round(x*S),round((y-Y0)*S)]
sites=[
 ("A","A. 성수역 2·3번 출구 앞(동측)",(885,293),"2호선 성수역 동측 출구. 성수동 카페거리·성수이로 방향으로 걷는 사람들이 먼저 지나는 자리."),
 ("B","B. 성수동 카페거리 입구",(1003,255),"아차산로에서 카페거리로 꺾이는 길목. 카페·팝업 목적 방문객이 모이는 곳."),
 ("C","C. 연무장5가길 · 올리브영N 인근",(600,345),"연무장5가길 서쪽 구간. 올리브영N·탬버린즈 쪽으로 걷는 방문객이 지나감."),
 ("D","D. 연무장길 · 대림창고 일대",(840,640),"대형 팝업·갤러리 카페 주변. 체류형 방문객이 많고 길이 넓음."),
 ("E","E. 연무장길 동쪽 이면 · 안목 성수 인근",(1100,760),"큰길에서 한 블록 안쪽. 임대료는 낮지만 우연히 지나가는 사람이 적음."),
 ("F","F. 성수역 1·4번 출구 앞(서측)",(670,212),"2호선 성수역 서측 출구. 올리브영 성수역점·연무장5가길 방향으로 나가는 사람들이 지나는 자리."),
]
cfg=f'''const CONFIG = {{
  W: {Wc}, H: {Hc},
  floorplan: "assets/seongsu_map.png",              // 구글맵 캡처(상단 검색창 제거)
  // 도로망: 지도 이미지의 도로 색을 추출해 골격화한 그래프(roadgraph.py). 방문자는 이 길 위로만 걷습니다.
  nodes: {json.dumps(P,separators=(",",":"))},
  edges: {json.dumps(E,separators=(",",":"))},
  // 입구 가중치 = 해당 상권 길단위 유동인구 비율 (뚝섬역 239만 / 성수역 141만 / 성수대교남단 73만 + 서울숲역·서울숲카페거리 54만)
  gates: {json.dumps(gates)},
  // 목적지 가중치(가정): 대림창고, 꼽당 일대, 올리브영N, 성수역 출구(4곳), 카페거리, 미피스토어, 안목 성수, 탬버린즈
  anchors: {json.dumps(anchors)},
  sites: [
''' + ",\n".join(f'    {{ id:"{i}", name:"{n}", pos:{json.dumps(sp(*p))}, desc:"{d}" }}' for i,n,p,d in sites) + '''
  ],
  noticeR: 50,
  speedPxPerMin: 90,
  openMin: 660, closeMin: 1260   // 11:00 ~ 21:00 (시뮬 시각, 분)
};'''
h=open("index.html",encoding="utf8").read()
h=re.sub(r"const CONFIG = \{.*?\n\};",lambda m:cfg,h,count=1,flags=re.S)
h=h.replace('width="1200" height="660"',f'width="{Wc}" height="{Hc}"')
h=h.replace('코엑스몰 개념도 위에서','성수동2가 구글맵 위에서').replace("성수동2가 개념도 위를","성수동2가 구글맵 위를")
h=h.replace("function drawMap(){ if(!bgCanvas) buildBg(); ctx.drawImage(bgCanvas,0,0); }",
 "function drawMap(){ if(bgImg){ ctx.drawImage(bgImg,0,0,CONFIG.W,CONFIG.H); ctx.fillStyle='rgba(255,255,255,.25)'; ctx.fillRect(0,0,CONFIG.W,CONFIG.H);} else { ctx.fillStyle='#f4f4f2'; ctx.fillRect(0,0,CONFIG.W,CONFIG.H);} }")
h=h.replace('<b>읽기 전에:</b> 배경은 실측 도면이 아닌 <b>개념도</b>이고,','<b>읽기 전에:</b> 배경은 구글맵 캡처이고 걷는 길은 이 지도에서 도로를 추출한 것이지만(건물 출입·골목 폭·횡단 등은 반영되지 않음),')
h=h.replace("개념도의 길 구조와 거리","지도에서 추출한 길 구조(성수역 출구·동쪽 방향은 캡처에 없어 입구 위치는 가정)와 거리")
h=re.sub(r"<li><b>C\(연무장길 중심\).*?</li>","<li><b>결과는 길 구조와 가중치 가정에 좌우됩니다.</b> 입구 3곳의 위치와 목적지 가중치는 가정이므로, 아래 비교는 순위의 방향성으로만 읽어주세요. 캡처 밖(성수역 출구, 건대입구 방향)에서 오는 사람은 반영되지 않았습니다.</li>",h,flags=re.S)
h=re.sub(r"<li>배경을 실제 지도로 바꾸려면.*?</li>","<li>지도를 바꾸려면 새 캡처로 <code>roadgraph.py</code>를 다시 돌려 도로 그래프를 만들고 <code>build_realmap.py</code>에서 후보지 좌표를 고치면 됩니다.</li>",h,flags=re.S)
open("index.html","w",encoding="utf8").write(h)
print(Wc,Hc,len(P),len(E),gates,anchors)
