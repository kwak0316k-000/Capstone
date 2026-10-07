"""index.html 조립: 기존 화면/데이터 코드 + 아이소메트릭 장면 + 새 시뮬레이션 화면 코드."""
import json, re
old = open("index_old.html", encoding="utf8").read()
head, rest = old.split("<script>", 1)
body_script = rest.split("</script>")[0]
shared = body_script[body_script.index("const DATA = {"):body_script.index("/* ===================== 화면")]
tail = body_script[body_script.index("/* ---- 비교(헤드리스)"):]
tail = tail[:tail.index("let loaded=0;")]
tail = tail.replace("setSiteDesc(); resetSim(); });","setSiteDesc(); resetSim(); focusStore(false); });")
tail = tail.replace('buildIdx("ageIdx",DATA.ageIndex); buildIdx("timeIdx",DATA.timeIndex); setSiteDesc();',"")
scene = json.load(open("data/scene.json")); g = json.load(open("data/iso_graph.json"))
sites = [("A","A. 성수역 2·3번 출구 앞(동측)","2호선 성수역 2·3번 출구로 나오자마자 만나는 자리. 카페거리·대림창고 방향으로 걷는 사람들이 먼저 지납니다."),
         ("B","B. 성수동 카페거리 입구","아차산로에서 카페거리로 꺾이는 길목. 카페·팝업 목적 방문객이 모이는 곳."),
         ("C","C. 연무장5가길 서쪽 · 올리브영N 인근","연무장5가길 서쪽 구간. 올리브영N·탬버린즈 쪽으로 걷는 방문객이 지나갑니다."),
         ("D","D. 연무장길 · 대림창고 일대","대형 팝업·갤러리 카페 주변. 체류형 방문객이 많고 길이 넓습니다."),
         ("E","E. 연무장길 동쪽 이면 · 안목 성수 인근","큰길에서 한 블록 안쪽. 임대료는 낮지만 우연히 지나가는 사람이 적습니다."),
         ("F","F. 성수역 1·4번 출구 앞(서측)","2호선 성수역 1·4번 출구. 올리브영 성수역점·연무장5가길 방향으로 나가는 사람들이 지납니다.")]
st = {s["id"]: s for s in scene["stores"]}
cfg = "const CONFIG = " + json.dumps(dict(
    nodes=g["nodes"], edges=g["edges"], gates=g["gates"], anchors=g["anchors"],
    sites=[dict(id=i, name=n, pos=st[i]["doorpt"], desc=d) for i, n, d in sites],
    noticeR=50, speedPxPerMin=90, openMin=660, closeMin=1260), ensure_ascii=False, separators=(",", ":")) + ";\n"
for s in scene["stores"]: s["doorpt"] = s["doorpt"]
html_head = head
html_head = html_head.replace("</style>", """
#stage{height:auto;aspect-ratio:1200/720;cursor:grab;touch-action:none;background:#0d2030}
#stage:active{cursor:grabbing}
.cam{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center}
.cam button{padding:5px 10px;font-size:13px}
</style>""")
html_head = html_head.replace('width="1200" height="612"', 'width="1200" height="720"')
html_head = re.sub(r'<canvas id="stage"[^>]*>', '<canvas id="stage" width="1200" height="720" role="img" aria-label="성수동2가 아이소메트릭 도시 모델 위에서 캐릭터들이 이동하고 후보 점포에 들어가는 시뮬레이션 화면"></canvas>', html_head)
html_head = html_head.replace("16명의 페르소나 캐릭터가 성수동2가 구글맵 위를 돌아다니며, 후보 위치 6곳 중 어디에서 가게를 가장 많이 마주치는지 비교합니다.",
  "구글맵 윤곽을 바탕으로 성수동2가를 아이소메트릭 도시 모델로 세우고, 16명의 페르소나 캐릭터가 그 길을 걸으며 후보 점포 6곳 중 어디에서 가게를 가장 많이 마주치고 들어가는지 비교합니다.")
html_head = re.sub(r'<div class="notice">.*?</div>', '<div class="notice"><b>읽기 전에:</b> 도로·블록·공원의 윤곽은 구글맵 캡처에서 가져왔지만 <b>건물의 모양·높이·색은 가상으로 만든 모델</b>이며 실제 건물과 다릅니다. 이동 경로·입장 확률·객단가도 <b>가정</b>입니다. 그래서 숫자의 크기보다 후보지 사이의 <b>상대 비교</b>로 읽어주세요. 화면을 끌어 이동하고 휠로 확대할 수 있습니다.</div>', html_head, count=1, flags=re.S)
html_head = re.sub(r'<div class="legend">.*?</div>\s*<div class="row">', '''<div class="cam"><button id="btnZin" aria-label="확대">＋</button><button id="btnZout" aria-label="축소">－</button><button id="btnFit">전체 보기</button><button id="btnFocus">선택한 점포로 이동</button>
        <span class="small">끌어서 이동 · 휠로 확대</span></div>
      <div class="legend">
        <span><span class="dot" style="background:#c8102e"></span>선택한 후보 점포(지붕을 걷어낸 단면)</span>
        <span><span class="dot" style="background:#7d838c"></span>다른 후보지</span>
        <span><span class="dot" style="background:#ff9800"></span>외국인 관광객 표시</span>
        <span>점선 원 = 가게를 &lsquo;알아보는&rsquo; 반경(약 50m)</span>
      </div>
      <div class="row">''', html_head, count=1, flags=re.S)
html_head = re.sub(r'<select id="selSpeed">.*?</select>', '<select id="selSpeed"><option value="0.3">느리게</option><option value="0.6" selected>보통</option><option value="1.5">빠르게</option><option value="6">아주 빠르게</option></select>', html_head, flags=re.S)
html_head = html_head.replace("지도에서 추출한 길 구조(입구 3곳의 위치는 가정이며 동쪽 건대입구 방향은 반영하지 않음)와 거리","지도에서 추출한 길 구조(입구 가중치와 출구별 배분은 가정이며 동쪽 건대입구 방향은 반영하지 않음)와 거리")
html_head = re.sub(r"<li>지도를 바꾸려면.*?</li>", "<li><b>건물은 가상입니다.</b> 도로·블록·공원 윤곽은 구글맵에서 뽑았지만 건물 배치·층수·색은 규칙으로 만든 것이며, 점포 내부(진열대·계산대)도 이 가게 콘셉트를 보여주기 위한 가정 도면입니다.</li>", html_head, flags=re.S)
js = open("iso_sim.js", encoding="utf8").read()
script = "<script>\n\"use strict\";\n/* 설정: 길 그래프·입구·목적지·후보지(모델 좌표, 단위 m) */\n" + cfg + "const SCENE = " + json.dumps(scene, ensure_ascii=False, separators=(",", ":")) + ";\n" + shared + js + "\n" + tail + """
buildIdx("ageIdx",DATA.ageIndex); buildIdx("timeIdx",DATA.timeIndex); setSiteDesc();
let loaded=0; SPRITES.forEach(s=>{ const im=new Image(); im.onload=()=>{ if(++loaded===SPRITES.length) draw(); }; im.src="assets/sprites/"+s.file+".png"; s.img=im; });
resetSim(); focusStore(true); compare(); requestAnimationFrame(frame);
</script>
</body>
</html>
"""
open("index.html", "w", encoding="utf8").write(html_head + script)
print("ok", len(html_head+script))
