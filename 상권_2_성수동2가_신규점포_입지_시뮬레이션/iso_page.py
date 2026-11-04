"""index.html 조립: 화면 틀(index_old.html의 CSS·공용 코드) + 도시 모델 장면 + 평가 결과 + 새 화면 코드(iso_sim2.js).
선행: iso_build.py, iso_graph.py, estimate_seongsu.py (data/scene.json, iso_graph.json, evaluation_seongsu.json, assignments.json)."""
import json
import re

old = open("index_old.html", encoding="utf8").read()
css = old[old.index("<style>"):old.index("</style>")]          # <style> ... (닫는 태그 제외)
body_script = old.split("<script>", 1)[1].split("</script>")[0]
shared = body_script[body_script.index("const DATA = {"):body_script.index("/* ===================== 방문자 생성")]
shared += body_script[body_script.index("/* ===================== 방문자 생성") - 0:body_script.index("function makeAgents")] if False else ""
scene = json.load(open("data/scene.json"))
g = json.load(open("data/iso_graph.json"))
ev = json.load(open("data/evaluation_seongsu.json"))
assign = json.load(open("data/assignments.json"))

sites = [("A", "A. 성수역 2·3번 출구 앞(동측)", "2호선 성수역 2·3번 출구로 나오자마자 만나는 자리. 카페거리·대림창고 방향으로 걷는 사람들이 먼저 지납니다."),
         ("B", "B. 성수동 카페거리 입구", "아차산로에서 카페거리로 꺾이는 길목. 카페·팝업 목적 방문객이 모이는 곳."),
         ("C", "C. 연무장5가길 서쪽 · 올리브영N 인근", "연무장5가길 서쪽 구간. 올리브영N·탬버린즈 쪽으로 걷는 방문객이 지나갑니다."),
         ("D", "D. 연무장길 · 대림창고 일대", "대형 팝업·갤러리 카페 주변. 체류형 방문객이 많고 길이 넓습니다."),
         ("E", "E. 연무장길 동쪽 이면 · 안목 성수 인근", "큰길에서 한 블록 안쪽. 임대료는 낮지만 우연히 지나가는 사람이 적습니다."),
         ("F", "F. 성수역 1·4번 출구 앞(서측)", "2호선 성수역 1·4번 출구. 올리브영 성수역점·연무장5가길 방향으로 나가는 사람들이 지납니다.")]
st = {s["id"]: s for s in scene["stores"]}
assert assign["sites"] == [s[0] for s in sites]
cfg = "const CONFIG = " + json.dumps(dict(
    nodes=g["nodes"], edges=g["edges"], gates=g["gates"], anchors=g["anchors"],
    sites=[dict(id=i, name=n, pos=st[i]["doorpt"], desc=d) for i, n, d in sites],
    noticeR=50, speedPxPerMin=90, openMin=660, closeMin=1260), ensure_ascii=False, separators=(",", ":")) + ";\n"

m = ev["market"]
head = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>성수동2가 신규 점포 시뮬레이션</title>
{css}
#stage{{height:auto;aspect-ratio:1200/720;cursor:grab;touch-action:none;background:#0d2030}}
#stage:active{{cursor:grabbing}}
.cam{{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center}}
.cam button{{padding:5px 10px;font-size:13px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;font-size:13px;color:#fff}}
.badge.Go{{background:#2e7d32}} .badge.cond{{background:#b26a00}} .badge.No{{background:#b3261e}}
.vbox{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:8px}}
.vbox div{{border:1px solid var(--line);border-radius:10px;padding:8px 10px}}
.vbox b{{display:block;font-size:18px;font-variant-numeric:tabular-nums}}
.vbox span{{font-size:12px;color:var(--sub)}}
td.l,th.l{{text-align:left}}
</style>
</head>
<body>
<div class="wrap">
  <h1>성수동2가 신규 점포 시뮬레이션</h1>
  <p class="lead">구글맵 윤곽을 바탕으로 성수동2가를 등각(아이소메트릭) 도시 모델로 세우고, 16명의 페르소나 캐릭터 1,000명이 그 길을 걸으며 경쟁 슈퍼마켓과 우리 점포 중 어디를 고르는지 봅니다. 결과는 서울시 실제 슈퍼마켓 매출로 보정해 <b>Go / 조건부 / No-Go</b>로 판정합니다.</p>
  <div class="notice"><b>읽기 전에:</b> 도로·블록·공원의 윤곽은 구글맵 캡처에서 가져왔지만 <b>건물의 모양·높이·색은 가상으로 만든 모델</b>이며 실제 건물과 다릅니다. <b>경쟁 슈퍼마켓의 위치는 실제가 아닙니다.</b> 서울시 점포 수({m['stores']:.0f}곳)만큼 길 위에 무작위로 놓았습니다. 입구·목적지 가중치도 가정이라 숫자의 크기보다 <b>후보지 사이의 상대 비교와 판정이 유지되는 정도</b>로 읽어주세요.</div>

  <div class="layout">
    <div class="card">
      <canvas id="stage" width="1200" height="720" role="img" aria-label="성수동2가 아이소메트릭 도시 모델 위에서 캐릭터들이 걸으며 경쟁 슈퍼마켓과 우리 점포 중 하나를 고르는 시뮬레이션 화면"></canvas>
      <div class="cam"><button id="btnZin" aria-label="확대">＋</button><button id="btnZout" aria-label="축소">－</button><button id="btnFit">전체 보기</button><button id="btnFocus">선택한 점포로 이동</button>
        <span class="small">끌어서 이동 · 휠로 확대</span></div>
      <div class="legend">
        <span><span class="dot" style="background:#c8102e"></span>선택한 후보 점포(지붕을 걷어낸 단면)</span>
        <span><span class="dot" style="background:#7d838c"></span>다른 후보지</span>
        <span><span class="dot" style="background:#5a6b7b;border-radius:3px"></span>경쟁 슈퍼마켓(위치는 가정)</span>
        <span><span class="dot" style="background:#ff9800"></span>외국인 관광객 표시</span>
      </div>
      <div class="row">
        <button id="btnPlay" class="primary">▶ 시작</button>
        <button id="btnReset">↺ 처음부터</button>
        <label>속도 <select id="selSpeed"><option value="0.3">느리게</option><option value="0.6" selected>보통</option><option value="1.5">빠르게</option><option value="6">아주 빠르게</option></select></label>
        <span id="clock" class="small" style="margin-left:auto">11:00</span>
      </div>
    </div>

    <div>
      <div class="card">
        <b>후보 위치</b>
        <div class="row"><select id="selSite" aria-label="후보 위치 선택"></select></div>
        <div id="siteDesc" class="small"></div>
        <div class="kpis">
          <div class="kpi"><b id="kSeen">0</b><span>지나간 방문자(표본)</span></div>
          <div class="kpi"><b id="kEnter">0</b><span>간식·화장품이 필요한 사람</span></div>
          <div class="kpi"><b id="kBuy">0</b><span>우리 점포를 고른 사람</span></div>
          <div class="kpi"><b id="kRev">0</b><span>다른 슈퍼를 고른 사람</span></div>
        </div>
        <div id="kSub" class="small" style="margin-top:6px"></div>
      </div>
      <div class="card" style="margin-top:12px">
        <b>이 자리의 판정</b> <span id="vBadge"></span>
        <div class="vbox">
          <div><b id="vSales">-</b><span>연 매출(보정, 기본 가정)</span></div>
          <div><b id="vTx">-</b><span>연 결제건수</span></div>
          <div><b id="vRatio">-</b><span>같은 시간대 점포 평균 대비</span></div>
          <div><b id="vShare">-</b><span>민감도 분석 500회 중 평균 이상</span></div>
        </div>
        <p class="small" id="vNote" style="margin:8px 0 0"></p>
      </div>
    </div>
  </div>

  <h2>후보지 비교와 판정 <span class="small">(서울시 {m['district_name']} 상권 {m['industry']} 2025년 실제 결제로 보정, 민감도 분석 {ev['n_runs']}회)</span></h2>
  <div class="card">
    <div id="distVerdict" style="margin-bottom:8px"></div>
    <div style="overflow-x:auto"><table id="cmp"><thead><tr><th class="l">후보 위치</th><th>연 결제건수</th><th>연 매출(억)</th><th>평균 대비</th><th>매출 90% 구간(억)</th><th>평균 이상 비율</th><th>1위 비율</th><th>판정</th><th>참고: 24시간 평균 기준</th></tr></thead><tbody></tbody></table></div>
    <p class="small" id="cmpNote"></p>
  </div>

  <h2>보정과 판정 방법 <span class="small">(팀원의 7_store_entry_simulation과 같은 방식)</span></h2>
  <div class="grid3">
    <div class="card"><b>1. 보정</b>
      <p class="small" style="color:var(--ink)">신규 점포가 없는 상태(BASE)에서 필요한 사람들이 상권 안 슈퍼마켓으로 가는 기대 이용량을 구하고, 시간대마다 2025년 실제 결제 건수에 맞춥니다. 신규 점포의 연 결제는 <b>보정계수 × 신규점을 고를 확률</b>이고, 매출은 여기에 시간대별 실제 객단가를 곱합니다. 상권 전체 수요는 그대로이므로 신규점은 기존 점포의 몫을 가져오는 만큼만 매출이 됩니다.</p>
      <table style="font-size:12.5px"><thead><tr><th class="l">시간대</th><th>실제 결제(건)</th><th>객단가(원)</th><th>보정계수</th></tr></thead><tbody id="kTable"></tbody></table>
    </div>
    <div class="card"><b>2. 판정 기준</b>
      <p class="small" style="color:var(--ink)">민감도 분석 {ev['n_runs']}회 중 <b>신규점 연매출이 점포 평균 연매출 이상</b>인 비율이<br><b>70% 이상 Go</b>, <b>40~70% 조건부</b>, <b>40% 미만 No-Go</b>. 상권 진출 판정은 가장 좋은 후보지의 판정입니다.</p>
      <p class="small" style="color:var(--ink)">기준 점포 매출: 성수역 슈퍼마켓 {m['stores']:.0f}곳, 연 {m['sales_amount_2025']/1e8:.1f}억원, 결제 {m['transactions_2025']:,}건, 객단가 {m['avg_ticket']:,}원. 우리 점포는 11~21시만 열기 때문에 <b>같은 시간대(11~21시) 평균 {ev['benchmark']['same_hours_11_21']/1e8:.2f}억원</b>과 비교하고, 24시간 전체 평균({ev['benchmark']['all_hours']/1e8:.2f}억원)은 참고로 오른쪽 열에 둡니다.</p>
    </div>
    <div class="card"><b>3. 민감도 분석에서 흔드는 것</b>
      <ul class="tight small" style="color:var(--ink)">
        <li>점포 선택의 거리 감쇠 λ 120~350m(기본 200m)</li>
        <li>우리 점포 매력도 0.67~1.5배(기본 1.0)</li>
        <li>입구 선택 거리 감쇠 300~800m(기본 500m)</li>
        <li>입구·목적지 가중치 0.5~1.5배</li>
        <li>경쟁점 배치: 길 전체 균등 / 사람이 모이는 곳 집중</li>
        <li>방문자 표본 복원추출</li>
      </ul>
    </div>
  </div>

  <h2>결론이 무엇에 기대고 있나 <span class="small">(조건을 바꿔 다시 계산, 각 200회, 평균 이상 비율)</span></h2>
  <div class="card"><div style="overflow-x:auto"><table id="abl"><thead></thead><tbody></tbody></table></div>
    <p class="small" id="ablNote"></p></div>

  <h2>상권 데이터에서 읽은 것 <span class="small">(성수 6개 상권 합산, 서울시 상권분석서비스 2026년 1분기)</span></h2>
  <div class="grid3">
    <div class="card"><b>연령대 지수</b> <span class="small">발달상권 평균=100</span><div id="ageIdx"></div></div>
    <div class="card"><b>시간대 지수</b> <span class="small">발달상권 평균=100</span><div id="timeIdx"></div></div>
    <div class="card"><b>성수 6개 상권의 규모와 추세</b> <span class="small">2021Q1 대비</span>
      <table style="margin-top:6px;font-size:12.5px"><thead><tr><th class="l">상권</th><th>유동인구</th><th>순위</th><th>추세</th></tr></thead><tbody>
        <tr><td>뚝섬역</td><td>2,393,932</td><td>74</td><td>+23.3%</td></tr>
        <tr><td>성수역</td><td>1,410,766</td><td>278</td><td>+12.8%</td></tr>
        <tr><td>성수동카페거리</td><td>1,077,930</td><td>427</td><td>+20.0%</td></tr>
        <tr><td>성수대교남단</td><td>731,626</td><td>642</td><td>−11.4%</td></tr>
        <tr><td>서울숲카페거리</td><td>313,129</td><td>1,083</td><td>−50.2%</td></tr>
        <tr><td>서울숲역</td><td>233,345</td><td>1,204</td><td>+2.4%</td></tr>
      </tbody></table>
      <p class="small" style="margin-top:8px">순위는 전체 1,649곳 중입니다. 코엑스는 48,674명(1,536위)이었습니다.</p>
    </div>
  </div>

  <h2>가정과 한계</h2>
  <div class="card small" style="color:var(--ink)">
    <ul class="tight">
      <li><b>데이터에서 온 값:</b> 연령대 구성(캐릭터 16명을 이 비율대로 뽑음), 시간별 방문 비중, 입구별 유입 비율(해당 상권 유동인구에 비례), 성수역 슈퍼마켓의 점포 수·시간대별 결제 건수·객단가(서울시 2025년).</li>
      <li><b>가정한 값:</b> 도시 모델의 길 구조와 건물, 입구·목적지 가중치, 경쟁점 23곳의 위치(길 위 무작위), 점포 선택의 거리 감쇠(λ=200m)와 우리 점포 매력도(기존 점포와 같음), 연령·성별·외국인에 따른 &lsquo;필요&rsquo; 확률(수준은 보정에서 상쇄되고 구성 차이만 남음).</li>
      <li><b>판정은 경쟁점 수와 위치에 민감합니다.</b> 경쟁점을 30곳으로 늘리면 A·D·B의 평균 이상 비율이 50~60%대로 내려가 조건부가 됩니다(위 표 참고). 실제 슈퍼마켓 위치를 확인하는 것이 가장 중요한 보완입니다.</li>
      <li><b>구성 검증:</b> 시뮬레이션의 필요 고객 구성을 실제 슈퍼마켓 결제 구성과 비교하면 연령 오차 {ev['validation']['age']['mae']}%p, 시간대 {ev['validation']['time']['mae']}%p이지만 성별은 {ev['validation']['gender']['mae']}%p로 큽니다(실제는 남성 {ev['validation']['gender']['real']['M']}%인데 가정상 여성이 더 많음).</li>
      <li><b>데이터에 없는 값:</b> 점포 앞 실제 통행량, 임대료·인건비, 우리 콘셉트(소포장 간식+소용량 화장품) 고유의 구매 행태. 비교 기준은 슈퍼마켓 업종 평균이라 우리 점포의 실제 손익분기와 다릅니다.</li>
      <li><b>건물은 가상입니다.</b> 점포 내부(진열대·계산대)도 콘셉트를 보여주기 위한 가정 도면입니다.</li>
    </ul>
  </div>
</div>
"""
js = open("iso_sim2.js", encoding="utf8").read()
panel = """
/* ---- 패널 ---- */
const EV = __EV__;
function buildIdx(id, obj){ const el=$(id); el.innerHTML="";
  for(const k in obj){ const v=obj[k], pct=Math.min(100,v/200*100);
    el.insertAdjacentHTML("beforeend",`<div class="idxrow"><span>${k}</span><div class="idxtrack"><div class="idxfill" style="width:${pct}%;background:${v>=100?'var(--accent2)':'var(--sub)'}"></div><div class="idxmid"></div></div><b>${v}</b></div>`); } }
const CAND={}; EV.candidates.forEach(c=>CAND[c.id]=c);
const bd=v=>`<span class="badge ${v==="Go"?"Go":v==="조건부"?"cond":"No"}">${v}</span>`;
const eok=x=>(x/1e8).toFixed(2), pc=x=>Math.round(x*100)+"%";
function setSiteInfo(){ const s=CONFIG.sites[siteIdx], c=CAND[s.id]; $("siteDesc").textContent=s.desc;
  $("vBadge").innerHTML=bd(c.verdict); $("vSales").textContent=eok(c.base.annual_sales)+"억원"; $("vTx").textContent=fmt(c.base.annual_transactions)+"건";
  $("vRatio").textContent=Math.round(c.base.ratio_to_bench_open*100)+"%"; $("vShare").textContent=pc(c.robust.share_above_bench);
  $("vNote").textContent=`90% 구간 ${eok(c.robust.p5)}~${eok(c.robust.p95)}억원, 11~21시 상권 슈퍼마켓 결제 중 우리 점포 몫 ${(c.base.share_of_open_hours_tx_pct).toFixed(1)}%(점포 평균 몫 ${(100/EV.market.stores).toFixed(1)}%). 24시간 평균 기준으로 보면 평균 이상 ${pc(c.robust.share_above_bench_all_hours)}(${c.verdict_all_hours_benchmark}).`; }
function buildTables(){
  const tb=document.querySelector("#cmp tbody"); tb.innerHTML="";
  CONFIG.sites.forEach(s=>{ const c=CAND[s.id], best=s.id===EV.best_candidate;
    tb.insertAdjacentHTML("beforeend",`<tr${best?' class="best"':''}><td class="l">${s.name}</td><td>${fmt(c.base.annual_transactions)}</td><td>${eok(c.base.annual_sales)}</td><td>${Math.round(c.base.ratio_to_bench_open*100)}%</td><td>${eok(c.robust.p5)}~${eok(c.robust.p95)}</td><td>${pc(c.robust.share_above_bench)}</td><td>${pc(c.robust.rank1_share)}</td><td>${bd(c.verdict)}</td><td>${pc(c.robust.share_above_bench_all_hours)} ${c.verdict_all_hours_benchmark}</td></tr>`); });
  const b=CAND[EV.best_candidate];
  $("distVerdict").innerHTML=`<b>상권 진출 판정:</b> ${bd(EV.district_verdict)} <span class="small">(가장 좋은 후보지 ${b.id}, 평균 이상 ${pc(b.robust.share_above_bench)}). 24시간 평균을 기준으로 바꾸면 최고 후보의 평균 이상 비율은 ${pc(Math.max(...EV.candidates.map(c=>c.robust.share_above_bench_all_hours)))}로 <b>조건부</b> 수준입니다.</span>`;
  $("cmpNote").textContent=`연 매출은 기본 가정 1회, 90% 구간은 민감도 분석 ${EV.n_runs}회의 5~95% 값입니다. 평균 대비는 같은 시간대(11~21시) 점포 평균 ${eok(EV.benchmark.same_hours_11_21)}억원 기준입니다.`;
  const kt=$("kTable"); kt.innerHTML=""; Object.keys(EV.calibration_k).forEach(t=>kt.insertAdjacentHTML("beforeend",`<tr><td class="l">${t}</td><td>${fmt(EV.real_tx_open[t])}</td><td>${fmt(EV.ticket_open[t])}</td><td>${fmt(EV.calibration_k[t])}</td></tr>`));
  const names=Object.keys(EV.ablation), ids=CONFIG.sites.map(s=>s.id);
  document.querySelector("#abl thead").innerHTML="<tr><th class='l'>조건</th>"+ids.map(i=>`<th>${i}</th>`).join("")+"</tr>";
  const ab=document.querySelector("#abl tbody"); ab.innerHTML="";
  names.forEach(n=>{ const m={}; EV.ablation[n].forEach(x=>m[x.id]=x); ab.insertAdjacentHTML("beforeend",`<tr><td class="l">${n}</td>${ids.map(i=>`<td>${pc(m[i].share_above)}</td>`).join("")}</tr>`); });
  $("ablNote").textContent="평균 이상 비율(70% 이상 Go, 40~70% 조건부). 조건을 바꿔도 A·B·D가 상위이고 E가 최하위인 점은 같습니다. 그러나 경쟁점을 30곳으로 늘리면 어느 후보지도 Go 기준(70%)을 넘지 못하고, 입구를 균등하게 하면 F가 내려가고 C가 올라갑니다.";
}
CONFIG.sites.forEach((s,i)=>{ const o=document.createElement("option"); o.value=i; o.textContent=s.name; $("selSite").appendChild(o); });
$("selSite").addEventListener("change",e=>{ siteIdx=+e.target.value; setSiteInfo(); resetSim(); focusStore(false); });
$("btnPlay").addEventListener("click",()=>{ if(!playing && simT>=CONFIG.closeMin && live.length===0 && agents.length===0) resetSim(); playing=!playing; $("btnPlay").textContent=playing?"❚❚ 일시정지":"▶ 계속"; });
$("btnReset").addEventListener("click",()=>{ playing=false; $("btnPlay").textContent="▶ 시작"; resetSim(); });
buildIdx("ageIdx",DATA.ageIndex); buildIdx("timeIdx",DATA.timeIndex); buildTables(); setSiteInfo();
let loaded=0; SPRITES.forEach(s=>{ const im=new Image(); im.onload=()=>{ if(++loaded===SPRITES.length) draw(); }; im.src="assets/sprites/"+s.file+".png"; s.img=im; });
resetSim(); focusStore(true); requestAnimationFrame(frame);
</script>
</body>
</html>
""".replace("__EV__", json.dumps(ev, ensure_ascii=False, separators=(",", ":")))
script = ("<script>\n\"use strict\";\n/* 설정: 길 그래프·입구·목적지·후보지(모델 좌표, 단위 m) */\n" + cfg + "const SCENE = " + json.dumps(scene, ensure_ascii=False, separators=(",", ":")) + ";\nconst ASSIGN = " + json.dumps(assign, ensure_ascii=False, separators=(",", ":")) + ";\n" + shared + js + panel)
open("index.html", "w", encoding="utf8").write(head + script)
print("ok", len(head + script))
