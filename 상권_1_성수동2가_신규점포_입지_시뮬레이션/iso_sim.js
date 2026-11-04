/* ===================== 화면: 아이소메트릭 도시 모델 ===================== */
const cv=document.getElementById("stage"), ctx=cv.getContext("2d");
const $=id=>document.getElementById(id);
const VW=cv.width, VH=cv.height;
const CX=SCENE.cx, ZS=SCENE.zs, XOFF=SCENE.xoff, YOFF=SCENE.yoff, MW=SCENE.model[0], MH=SCENE.model[1];
const proj=(mx,my,z)=>[(mx-my)*CX+XOFF,(mx+my)*CX/2+YOFF-(z||0)*ZS];
const FONT="-apple-system,'Apple SD Gothic Neo','Noto Sans KR','Malgun Gothic',sans-serif";
const groundImg=new Image(), atlasImg=new Image(); let imgReady=0;
groundImg.onload=atlasImg.onload=()=>{ imgReady++; draw(); };
groundImg.src="assets/ground.jpg"; atlasImg.src="assets/atlas.webp";
const STORE_BY_ID={}; SCENE.stores.forEach(s=>STORE_BY_ID[s.id]=s);
const siteStore=i=>STORE_BY_ID[CONFIG.sites[i].id];
/* ---- 오브젝트(건물·나무·가로등·점포) 정렬 ---- */
const OBJ=SCENE.objects.map(o=>({...o,key:(o.fp[0]+o.fp[1]+o.fp[2]+o.fp[3])/2}));
SCENE.stores.forEach(st=>{
  const pts=[]; for(const mx of [st.mx0-3,st.mx1+3]) for(const my of [st.my0-3,st.my1+3]) for(const z of [0,9]) pts.push(proj(mx,my,z));
  const x0=Math.floor(Math.min(...pts.map(p=>p[0]))), x1=Math.ceil(Math.max(...pts.map(p=>p[0]))), y0=Math.floor(Math.min(...pts.map(p=>p[1]))), y1=Math.ceil(Math.max(...pts.map(p=>p[1])));
  OBJ.push({kind:"shop",st,fp:[st.mx0,st.mx1,st.my0,st.my1],ox:x0,oy:y0,w:x1-x0,h:y1-y0,key:(st.mx0+st.mx1+st.my0+st.my1)/2});
});
const ORD=OBJ.sort((a,b)=>a.key-b.key);
const CELL=160, GRID={};
ORD.forEach((o,i)=>{ if(o.kind==="lamp"||o.kind==="bench"||o.kind==="planter") return;
  for(let cx=Math.floor(o.ox/CELL); cx<=Math.floor((o.ox+o.w)/CELL); cx++) for(let cy=Math.floor(o.oy/CELL); cy<=Math.floor((o.oy+o.h)/CELL); cy++){ const k=cx+","+cy; (GRID[k]=GRID[k]||[]).push(i); } });
const LMH={}; ORD.forEach(o=>{ if(o.lm) LMH[o.lm]={fp:o.fp,H:o.H}; });
function occluder(mx,my){            // 이 위치의 캐릭터를 가리는 가장 먼저 그려지는 오브젝트의 순번
  const [X,Y]=proj(mx,my,0), bx0=X-18, bx1=X+18, by0=Y-40, by1=Y+4; let best=1e9;
  for(let cx=Math.floor(bx0/CELL); cx<=Math.floor(bx1/CELL); cx++) for(let cy=Math.floor(by0/CELL); cy<=Math.floor(by1/CELL); cy++){
    const arr=GRID[cx+","+cy]; if(!arr) continue;
    for(const i of arr){ if(i>=best) continue; const o=ORD[i];
      if(!(mx<o.fp[1]&&my<o.fp[3])) continue;
      if(bx1<o.ox||bx0>o.ox+o.w||by1<o.oy||by0>o.oy+o.h) continue; best=i; } }
  return best;
}
/* ---- 점포 모델(캔버스에 한 번 그려 둠) ---- */
const SNACK=["#d7263d","#f4a300","#2b6fd6","#2e9e5b","#f06292","#8e44ad","#ffb703","#e76f51"], COSM=["#f8bbd0","#e1bee7","#b2dfdb","#fff3c4","#ffffff","#ffccbc","#c5cae9"];
const shopCache={};
function Qg(g,pts,fill,stroke,lw){ g.beginPath(); pts.forEach((q,i)=>{ const p=proj(q[0],q[1],q[2]); i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1]); }); g.closePath(); if(fill){ g.fillStyle=fill; g.fill(); } if(stroke){ g.strokeStyle=stroke; g.lineWidth=lw||1; g.stroke(); } }
function boxg(g,x0,x1,y0,y1,z0,z1,cT,cL,cR){ Qg(g,[[x0,y1,z0],[x1,y1,z0],[x1,y1,z1],[x0,y1,z1]],cL,"rgba(60,40,30,.5)"); Qg(g,[[x1,y0,z0],[x1,y1,z0],[x1,y1,z1],[x1,y0,z1]],cR,"rgba(60,40,30,.5)"); Qg(g,[[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],cT,"rgba(60,40,30,.5)"); }
function skewText(g,text,mx,my,z,face,size,color,weight){ const p=proj(mx,my,z); g.save(); g.translate(p[0],p[1]); g.transform(1,face==="L"?0.5:-0.5,0,1,0,0); g.font=(weight||"800")+" "+size+"px "+FONT; g.textAlign="center"; g.textBaseline="middle"; g.fillStyle=color; g.fillText(text,0,0); g.restore(); }
function mkCanvas(o,drawFn){ const c=document.createElement("canvas"); c.width=o.w*2; c.height=o.h*2; const g=c.getContext("2d"); g.scale(2,2); g.translate(-o.ox,-o.oy); drawFn(g); return c; }
function shopParts(i,open){
  const k=i+(open?"o":"c"); if(shopCache[k]) return shopCache[k];
  const o=ORD.find(q=>q.kind==="shop"&&q.st.id===SCENE.stores[i].id), st=o.st, W=st.mx1-st.mx0, D=st.my1-st.my0, H=4.6, T=0.3, door=st.door;
  const rnd=rng32(100+i), cxm=(st.mx0+st.mx1)/2, cym=(st.my0+st.my1)/2;
  const back=mkCanvas(o,g=>{
    if(!open){
      boxg(g,st.mx0,st.mx1,st.my0,st.my1,0,4.0,"#9aa1ab","#d3d9e0","#a9b1bd");
      Qg(g,[[st.mx0-.3,st.my0-.3,4.0],[st.mx1+.3,st.my0-.3,4.0],[st.mx1+.3,st.my1+.3,4.0],[st.mx0-.3,st.my1+.3,4.0]],"#8a919b","#5c626c");
      const dc=door==="L"?[cxm,st.my1,1.2]:[st.mx1,cym,1.2];
      if(door==="L") Qg(g,[[cxm-1,st.my1,0],[cxm+1,st.my1,0],[cxm+1,st.my1,2.5],[cxm-1,st.my1,2.5]],"#6b4a34","#3a2a1e"); else Qg(g,[[st.mx1,cym-1,0],[st.mx1,cym+1,0],[st.mx1,cym+1,2.5],[st.mx1,cym-1,2.5]],"#5a3f2c","#3a2a1e");
      if(door==="L") skewText(g,"후보 "+st.id,cxm,st.my1,3.2,"L",9,"#c8102e"); else skewText(g,"후보 "+st.id,st.mx1,cym,3.2,"R",9,"#c8102e");
      return; }
    for(let a=0;a<Math.ceil(W);a++) for(let b=0;b<Math.ceil(D);b++){ const x0=st.mx0+a,x1=Math.min(st.mx1,x0+1),y0=st.my0+b,y1=Math.min(st.my1,y0+1); Qg(g,[[x0,y0,.02],[x1,y0,.02],[x1,y1,.02],[x0,y1,.02]],(a+b)%2?"#f6c6d2":"#fff4f6"); }
    Qg(g,[[st.mx0,st.my0,0],[st.mx0,st.my1,0],[st.mx0,st.my1,H],[st.mx0,st.my0,H]],"#f6ecdb","#b9a98c");
    Qg(g,[[st.mx0,st.my0,0],[st.mx1,st.my0,0],[st.mx1,st.my0,H],[st.mx0,st.my0,H]],"#ecdfc8","#b9a98c");
    Qg(g,[[st.mx0-T,st.my0-T,H],[st.mx1,st.my0-T,H],[st.mx1,st.my0,H],[st.mx0-T,st.my0,H]],"#fffaf0","#b9a98c");
    Qg(g,[[st.mx0-T,st.my0-T,H],[st.mx0,st.my0-T,H],[st.mx0,st.my1,H],[st.mx0-T,st.my1,H]],"#fffaf0","#b9a98c");
    // 뒷벽 창문
    for(const f of [.28,.72]){ const x=st.mx0+W*f; Qg(g,[[x-1,st.my0,2.9],[x+1,st.my0,2.9],[x+1,st.my0,4.1],[x-1,st.my0,4.1]],"#9fc6dc","#fffdf6",2); }
    for(const f of [.3,.75]){ const y=st.my0+D*f; Qg(g,[[st.mx0,y-1,2.9],[st.mx0,y+1,2.9],[st.mx0,y+1,4.1],[st.mx0,y-1,4.1]],"#9fc6dc","#fffdf6",2); }
    // 과자 월 (뒷벽 gy0 쪽)
    const sx0=st.mx0+1.2, sx1=st.mx1-1.0, sy0=st.my0+.15, sy1=st.my0+.9;
    boxg(g,sx0,sx1,sy0,sy1,0,2.5,"#e8d6b0","#f3e7cf","#d7c4a0");
    for(let r=0;r<4;r++){ const z0=.2+r*.58; Qg(g,[[sx0,sy1,z0+.42],[sx1,sy1,z0+.42],[sx1,sy1,z0+.46],[sx0,sy1,z0+.46]],"#a67c52");
      const n=Math.floor((sx1-sx0-.2)/.46); for(let c=0;c<n;c++){ const x=sx0+.12+c*.46; Qg(g,[[x,sy1,z0+.06],[x+.34,sy1,z0+.06],[x+.34,sy1,z0+.4],[x,sy1,z0+.4]],SNACK[Math.floor(rnd()*SNACK.length)],"rgba(70,40,30,.6)",.6); } }
    Qg(g,[[sx0,sy1,2.5],[sx1,sy1,2.5],[sx1,sy1,2.95],[sx0,sy1,2.95]],"#c8102e","#7a0a1c");
    skewText(g,"낱개 과자",(sx0+sx1)/2,sy1,2.72,"L",7.5,"#ffffff");
    // 화장품 월 (gx0 쪽)
    const cx0=st.mx0+.15, cx1=st.mx0+.85, cy0=st.my0+1.6, cy1=st.my1-2.8;
    boxg(g,cx0,cx1,cy0,cy1,0,2.2,"#f8e1ea","#fff4f8","#f1d3de");
    for(let r=0;r<4;r++){ const z0=.18+r*.5; Qg(g,[[cx1,cy0,z0+.38],[cx1,cy1,z0+.38],[cx1,cy1,z0+.42],[cx1,cy0,z0+.42]],"#e3aabf");
      const n=Math.floor((cy1-cy0-.2)/.4); for(let c=0;c<n;c++){ const y=cy0+.1+c*.4; Qg(g,[[cx1,y,z0+.04],[cx1,y+.28,z0+.04],[cx1,y+.28,z0+.36],[cx1,y,z0+.36]],COSM[Math.floor(rnd()*COSM.length)],"rgba(120,70,90,.6)",.6); } }
    Qg(g,[[cx1,cy0,2.2],[cx1,cy1,2.2],[cx1,cy1,2.65],[cx1,cy0,2.65]],"#f06292","#a63a62");
    skewText(g,"소용량 뷰티",cx1,(cy0+cy1)/2,2.42,"R",7.5,"#ffffff");
    // 골라담기 바구니(가운데)
    for(const [bx,by] of [[cxm-.6,cym-.4],[cxm+2.2,cym+.8]]){ boxg(g,bx,bx+2.0,by,by+1.1,0,.85,"#f2d9a8","#c99a5a","#a97d44"); for(let q=0;q<16;q++){ const p=proj(bx+.12+rnd()*1.76,by+.12+rnd()*.86,.88); g.fillStyle=SNACK[Math.floor(rnd()*SNACK.length)]; g.beginPath(); g.ellipse(p[0],p[1],2.1,1.4,0,0,6.283); g.fill(); } skewText(g,"골라담기",bx+1,by+1.1,.45,"L",5.5,"#fff"); }
    // 계산대
    const cnt=door==="L"?[st.mx1-3.6,st.mx1-1.0,st.my1-2.6,st.my1-1.6]:[st.mx1-2.6,st.mx1-1.6,st.my1-3.6,st.my1-1.0];
    boxg(g,cnt[0],cnt[1],cnt[2],cnt[3],0,1.1,"#e7c9a0","#b9824f","#8f6238"); boxg(g,(cnt[0]+cnt[1])/2-.3,(cnt[0]+cnt[1])/2+.3,(cnt[2]+cnt[3])/2-.3,(cnt[2]+cnt[3])/2+.3,1.1,1.55,"#4a5568","#6b7686","#3a4352");
    // 화분
    const pp=proj(st.mx0+1.2,st.my1-1.0,0); g.fillStyle="#b0764d"; g.fillRect(pp[0]-4,pp[1]-5,8,6); for(const [dx,dy,r] of [[0,-14,8],[-6,-9,6],[6,-9,6],[0,-21,5]]){ g.fillStyle="#5aa05a"; g.beginPath(); g.arc(pp[0]+dx,pp[1]+dy,r,0,6.283); g.fill(); }
  });
  const front=mkCanvas(o,g=>{
    if(!open) return;
    const lowH=.95, gapW=1.9;
    function lowL(x0,x1){ if(x1-x0<.05) return; Qg(g,[[x0,st.my1,0],[x1,st.my1,0],[x1,st.my1,lowH],[x0,st.my1,lowH]],"#e4d3b3","#9a8664"); Qg(g,[[x0,st.my1-T,lowH],[x1,st.my1-T,lowH],[x1,st.my1,lowH],[x0,st.my1,lowH]],"#fff7ea","#9a8664"); }
    function lowR(y0,y1){ if(y1-y0<.05) return; Qg(g,[[st.mx1,y0,0],[st.mx1,y1,0],[st.mx1,y1,lowH],[st.mx1,y0,lowH]],"#c8b693","#8a7654"); Qg(g,[[st.mx1-T,y0,lowH],[st.mx1,y0,lowH],[st.mx1,y1,lowH],[st.mx1-T,y1,lowH]],"#fff1db","#8a7654"); }
    if(door==="L"){ lowL(st.mx0,cxm-gapW/2); lowL(cxm+gapW/2,st.mx1); lowR(st.my0,st.my1); } else { lowR(st.my0,cym-gapW/2); lowR(cym+gapW/2,st.my1); lowL(st.mx0,st.mx1); }
    // 기둥
    for(const [x,y] of [[st.mx0,st.my1],[st.mx1,st.my1],[st.mx1,st.my0]]) Qg(g,[[x-.25,y+.25,0],[x+.25,y+.25,0],[x+.25,y+.25,H],[x-.25,y+.25,H]],"#fffaf0","#9a8664");
    // 차양과 간판
    const nst=10, aw=door==="L"?[cxm-2.2,cxm+2.2]:[cym-2.2,cym+2.2], out=1.8;
    for(let s=0;s<nst;s++){ const a0=aw[0]+(aw[1]-aw[0])*s/nst, a1=aw[0]+(aw[1]-aw[0])*(s+1)/nst, col=s%2?"#ffffff":"#d7263d";
      if(door==="L") Qg(g,[[a0,st.my1,3.3],[a1,st.my1,3.3],[a1,st.my1+out,2.65],[a0,st.my1+out,2.65]],col,"#8d1a28",.7);
      else Qg(g,[[st.mx1,a0,3.3],[st.mx1,a1,3.3],[st.mx1+out,a1,2.65],[st.mx1+out,a0,2.65]],col,"#8d1a28",.7); }
    if(door==="L"){ Qg(g,[[cxm-2.6,st.my1,3.5],[cxm+2.6,st.my1,3.5],[cxm+2.6,st.my1,4.5],[cxm-2.6,st.my1,4.5]],"#c8102e","#7a0a1c",1.2); skewText(g,"낱개 스낵 & 뷰티",cxm,st.my1,4.0,"L",7.5,"#fff"); }
    else { Qg(g,[[st.mx1,cym-2.6,3.5],[st.mx1,cym+2.6,3.5],[st.mx1,cym+2.6,4.5],[st.mx1,cym-2.6,4.5]],"#c8102e","#7a0a1c",1.2); skewText(g,"낱개 스낵 & 뷰티",st.mx1,cym,4.0,"R",7.5,"#fff"); }
  });
  return shopCache[k]={back,front,o,W,D,door};
}
/* 점포 안 손님의 동선 (모델 좌표) */
function shopPath(st,buy){
  const W=st.mx1-st.mx0, D=st.my1-st.my0, door=st.door==="L"?[st.mx0+W/2,st.my1-.4]:[st.mx1-.4,st.my0+D/2];
  const snack=[st.mx0+W*.5,st.my0+2.3], cosm=[st.mx0+1.8,st.my0+D*.5], isl=[st.mx0+W*.5+.5,st.my0+D*.55];
  const cnt=st.door==="L"?[st.mx1-2.3,st.my1-.9]:[st.mx1-.9,st.my1-2.3];
  const pts=[door,snack,isl,cosm]; if(buy) pts.push(cnt); pts.push(door); return pts;
}
function along(pts,f){ let L=0; const seg=[]; for(let i=0;i<pts.length-1;i++){ const d=Math.hypot(pts[i+1][0]-pts[i][0],pts[i+1][1]-pts[i][1]); seg.push(d); L+=d; }
  let t=f*L; for(let i=0;i<seg.length;i++){ if(t<=seg[i]||i===seg.length-1){ const u=seg[i]?Math.min(1,t/seg[i]):0; return [pts[i][0]+(pts[i+1][0]-pts[i][0])*u, pts[i][1]+(pts[i+1][1]-pts[i][1])*u]; } t-=seg[i]; } return pts[pts.length-1]; }
/* ---- 상태 ---- */
let P=readParams(), agents=[], live=[], simT=CONFIG.openMin, playing=false, last=0, stats, siteIdx=0, floats=[];
const cam={x:0,y:0,z:1,tx:0,ty:0,tz:1,follow:true};
function readParams(){ return { tour:+$("rTour").value, base:+$("rBase").value, conv:+$("rConv").value, ticket:+$("rTicket").value, n:+$("rN").value }; }
function fmt(n){ return Math.round(n).toLocaleString("ko-KR"); }
function clock(t){ const h=Math.floor(t/60), m=Math.floor(t%60); return String(h).padStart(2,"0")+":"+String(m).padStart(2,"0"); }
function focusStore(snap){ const st=siteStore(siteIdx), c=proj((st.mx0+st.mx1)/2,(st.my0+st.my1)/2,1.5); cam.tx=c[0]; cam.ty=c[1]-10; cam.tz=2.8; cam.follow=true; if(snap){ cam.x=cam.tx; cam.y=cam.ty; cam.z=cam.tz; } }
function resetSim(){
  P=readParams(); agents=makeAgents(20260707, P.n, P); live=[]; simT=CONFIG.openMin; floats=[];
  stats={seen:0,enter:0,buy:0,rev:0,tourBuy:0}; renderStats(); draw();
}
function renderStats(){ $("kSeen").textContent=fmt(stats.seen); $("kEnter").textContent=fmt(stats.enter); $("kBuy").textContent=fmt(stats.buy); $("kRev").textContent=fmt(stats.rev);
  $("kSub").textContent=`구매자 중 외국인 ${fmt(stats.tourBuy)}명 · 지금 점포 안 ${live.filter(L=>L.mode==="inside").length}명`; $("clock").textContent=clock(simT); }
/* ---- 이동 ---- */
function step(dtMin){
  const sp=CONFIG.speedPxPerMin, st=siteStore(siteIdx), door=st.doorpt;
  while(agents.length && agents[0].spawn<=simT){ const a=agents.shift(); live.push({a, seg:0, x:a.pts[0][0], y:a.pts[0][1], wait:0, fired:false, walk:Math.random()*6.28, mode:"walk", t:0}); }
  for(const L of live){
    let budget=dtMin;
    if(L.mode==="inside"){ L.t+=dtMin; if(L.t>=L.dwell){ L.mode="back"; } continue; }
    if(L.mode==="toDoor"||L.mode==="back"){
      const T=L.mode==="toDoor"?door:L.ret, d=Math.hypot(T[0]-L.x,T[1]-L.y), mv=sp*1.15*dtMin;
      if(d<=mv){ L.x=T[0]; L.y=T[1]; if(L.mode==="toDoor"){ L.mode="inside"; L.t=0; } else L.mode="walk"; } else { L.x+=(T[0]-L.x)/d*mv; L.y+=(T[1]-L.y)/d*mv; }
      continue; }
    if(L.wait>0){ const w=Math.min(L.wait,budget); L.wait-=w; budget-=w; }
    let move=sp*budget;
    while(move>0 && L.seg<L.a.pts.length-1 && L.wait<=0){
      const B=L.a.pts[L.seg+1], d=Math.hypot(B[0]-L.x,B[1]-L.y);
      if(d<=move){ L.x=B[0]; L.y=B[1]; move-=d; L.seg++; if(L.a.pts[L.seg][2]>0 && L.seg<L.a.pts.length-1){ L.wait=L.a.pts[L.seg][2]; break; } }
      else { L.x+=(B[0]-L.x)/d*move; L.y+=(B[1]-L.y)/d*move; move=0; }
    }
    if(!L.fired){ const nr=L.a.near[siteIdx]; if(nr.d<CONFIG.noticeR && L.seg>=nr.i){ L.fired=true;
        const res=decide(L.a, siteIdx, P); L.res=res;
        if(res.seen){ stats.seen++; if(res.enter){ stats.enter++; L.mode="toDoor"; L.ret=[L.x,L.y]; L.dwell=1.5+L.a.uP*3.5; L.shopPath=shopPath(st,res.buy);
              floats.push({mx:L.x,my:L.y,t:1,txt:res.buy?"+"+fmt(res.ticket)+"원":"입장",c:res.buy?"#2e7d32":"#1f6f8b"}); }
          if(res.buy){ stats.buy++; stats.rev+=res.ticket; if(res.tourist) stats.tourBuy++; } } } }
  }
  live=live.filter(L=>L.mode!=="walk"||L.seg<L.a.pts.length-1);
}
/* ---- 그리기 ---- */
const trains=[{dir:1,off:0,yo:-1.7},{dir:-1,off:260,yo:1.7}];
function trainCars(tms){
  const cars=[], span=MW+240;
  trains.forEach(tr=>{ const base=(((tms/1000)*16+tr.off)%span); const head=tr.dir>0?base-110:MW+110-base;
    for(let k=0;k<4;k++){ const cxm=head-tr.dir*k*11.6; if(cxm<-8||cxm>MW+8) continue; const yc=SCENE.viaduct.a*cxm+SCENE.viaduct.b+tr.yo; cars.push({cx:cxm,yc,key:cxm+yc+.2,first:k===0}); } });
  return cars.sort((a,b)=>a.key-b.key);
}
function drawCar(c){ const z0=SCENE.viaduct.z+.2, x0=c.cx-5.5, x1=c.cx+5.5, y0=c.yc-1.45, y1=c.yc+1.45;
  boxg(ctx,x0,x1,y0,y1,z0,z0+3.1,"#d7dde3","#eef1f4","#c0c8d0");
  Qg(ctx,[[x0,y1,z0+.55],[x1,y1,z0+.55],[x1,y1,z0+1.05],[x0,y1,z0+1.05]],"#00a84d"); Qg(ctx,[[x1,y0,z0+.55],[x1,y1,z0+.55],[x1,y1,z0+1.05],[x1,y0,z0+1.05]],"#008a3f");
  for(let k=0;k<5;k++){ const a=x0+.7+k*2.0; Qg(ctx,[[a,y1,z0+1.5],[a+1.35,y1,z0+1.5],[a+1.35,y1,z0+2.55],[a,y1,z0+2.55]],"#35566e","rgba(255,255,255,.8)",.8); } }
function drawAgent(L){
  const sp=SPRITES[L.a.spr]; if(!sp.img||!sp.img.complete) return;
  const [X,Y]=proj(L.x,L.y,0), h=32, w=sp.img.width/sp.img.height*h, bob=(L.wait>0||L.mode==="inside"?0:Math.sin(L.walk+simT*2.4)*1.6);
  ctx.fillStyle="rgba(20,30,40,.28)"; ctx.beginPath(); ctx.ellipse(X,Y+1,w*.34,4,0,0,6.283); ctx.fill();
  ctx.drawImage(sp.img,X-w/2,Y-h+bob,w,h);
  if(L.a.uT < P.tour/100){ ctx.fillStyle="#ff9800"; ctx.beginPath(); ctx.arc(X+w/2-3,Y-h+5+bob,3.6,0,6.283); ctx.fill(); ctx.lineWidth=1.2; ctx.strokeStyle="#fff"; ctx.stroke(); }
  if(L.res&&L.res.enter){ ctx.fillStyle=L.res.buy?"#2e7d32":"#1f6f8b"; ctx.beginPath(); ctx.arc(X,Y-h-6+bob,3.8,0,6.283); ctx.fill(); }
}
function drawInside(L){
  const sp=SPRITES[L.a.spr]; if(!sp.img||!sp.img.complete) return;
  const f=Math.min(1,L.t/L.dwell), p=along(L.shopPath,f), [X,Y]=proj(p[0],p[1],0), h=25, w=sp.img.width/sp.img.height*h;
  ctx.fillStyle="rgba(20,30,40,.25)"; ctx.beginPath(); ctx.ellipse(X,Y+1,w*.34,3,0,0,6.283); ctx.fill(); ctx.drawImage(sp.img,X-w/2,Y-h,w,h);
  if(L.res&&L.res.buy&&f>.6){ ctx.fillStyle="#ffb703"; ctx.fillRect(X+w/2-4,Y-h*.5,7,9); ctx.strokeStyle="#7a5a00"; ctx.strokeRect(X+w/2-4,Y-h*.5,7,9); }
}
function drawShop(o){
  const i=SCENE.stores.findIndex(s=>s.id===o.st.id), sel=CONFIG.sites[siteIdx].id===o.st.id, parts=shopParts(i,sel);
  ctx.drawImage(parts.back,o.ox,o.oy,o.w,o.h);
  if(sel){ const ins=live.filter(L=>L.mode==="inside").sort((a,b)=>{ const pa=along(a.shopPath,a.t/a.dwell),pb=along(b.shopPath,b.t/b.dwell); return (pa[0]+pa[1])-(pb[0]+pb[1]); }); ins.forEach(drawInside); }
  ctx.drawImage(parts.front,o.ox,o.oy,o.w,o.h);
}
function drawRing(){
  const st=siteStore(siteIdx), d=st.doorpt, r=CONFIG.noticeR; ctx.beginPath();
  for(let k=0;k<=48;k++){ const a=k/48*6.283, p=proj(d[0]+Math.cos(a)*r,d[1]+Math.sin(a)*r,0); k?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]); }
  ctx.fillStyle="rgba(200,16,46,.10)"; ctx.fill(); ctx.setLineDash([10,8]); ctx.strokeStyle="rgba(200,16,46,.85)"; ctx.lineWidth=2.4; ctx.stroke(); ctx.setLineDash([]);
}
function pill(text,x,y,bg,fg,size){ ctx.font="700 "+size+"px "+FONT; const w=ctx.measureText(text).width+12, h=size+8; ctx.beginPath(); ctx.roundRect(x-w/2,y-h/2,w,h,h/2); ctx.fillStyle=bg; ctx.fill(); ctx.lineWidth=1; ctx.strokeStyle="rgba(0,0,0,.25)"; ctx.stroke(); ctx.fillStyle=fg; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(text,x,y+.5); }
const CATC={food:"#f39c3d",retail:"#4a88e8",gallery:"#a56fd1"};
function drawLabels(vx0,vx1,vy0,vy1){
  const z=cam.z, inv=1/z;
  if(z>=.5) SCENE.landmarks.forEach(l=>{ const b=LMH[l.name]; if(!b) return; const p=proj((b.fp[0]+b.fp[1])/2,(b.fp[2]+b.fp[3])/2,b.H+4.2); if(p[0]<vx0||p[0]>vx1||p[1]<vy0||p[1]>vy1) return;
    ctx.save(); ctx.translate(p[0],p[1]); ctx.scale(inv,inv); pill(l.name,0,0,"rgba(255,255,255,.92)","#2b2f36",11); ctx.fillStyle=CATC[l.cat]; ctx.beginPath(); ctx.arc(-ctx.measureText(l.name).width/2-1,0,0,0,0); ctx.restore(); });
  // 성수역·출구
  const ex=SCENE.exits, sx=(ex["1"][0]+ex["2"][0])/2, sy=SCENE.viaduct.a*sx+SCENE.viaduct.b, sp=proj(sx,sy,SCENE.viaduct.z+7.5);
  ctx.save(); ctx.translate(sp[0],sp[1]); ctx.scale(inv,inv); ctx.fillStyle="#00a84d"; ctx.beginPath(); ctx.arc(-44,0,11,0,6.283); ctx.fill(); ctx.fillStyle="#fff"; ctx.font="800 13px "+FONT; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText("2",-44,1); pill("성수역",-8,0,"rgba(255,255,255,.95)","#1b1f24",13); ctx.restore();
  SCENE.kiosks.forEach(k=>{ const p=proj((k.mx0+k.mx1)/2,(k.my0+k.my1)/2,6); ctx.save(); ctx.translate(p[0],p[1]); ctx.scale(inv,inv); ctx.fillStyle="#1f8a45"; ctx.beginPath(); ctx.roundRect(-9,-9,18,18,4); ctx.fill(); ctx.strokeStyle="#fff"; ctx.lineWidth=1.5; ctx.stroke(); ctx.fillStyle="#fff"; ctx.font="800 12px "+FONT; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(k.id,0,1); ctx.restore(); });
  // 후보 점포 표지
  CONFIG.sites.forEach((s,i)=>{ const st=STORE_BY_ID[s.id], on=i===siteIdx, bob=on?Math.sin(performance.now()/260)*3:0, p=proj((st.mx0+st.mx1)/2,(st.my0+st.my1)/2,on?9.5:6.5);
    ctx.save(); ctx.translate(p[0],p[1]+bob*inv); ctx.scale(inv,inv); const R=on?15:11; ctx.beginPath(); ctx.moveTo(0,R+9); ctx.lineTo(-6,R-1); ctx.lineTo(6,R-1); ctx.closePath(); ctx.fillStyle=on?"#c8102e":"#7d838c"; ctx.fill();
    ctx.beginPath(); ctx.arc(0,0,R,0,6.283); ctx.fillStyle=on?"#c8102e":"#7d838c"; ctx.fill(); ctx.lineWidth=2.5; ctx.strokeStyle="#fff"; ctx.stroke(); ctx.fillStyle="#fff"; ctx.font="800 "+(on?16:13)+"px "+FONT; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(s.id,0,1); ctx.restore(); });
  for(const f of floats){ const p=proj(f.mx,f.my,5); ctx.save(); ctx.translate(p[0],p[1]-(1-f.t)*40*inv-30*inv); ctx.scale(inv,inv); ctx.globalAlpha=Math.max(0,f.t); ctx.font="800 14px "+FONT; ctx.textAlign="center"; ctx.lineWidth=3; ctx.strokeStyle="rgba(255,255,255,.95)"; ctx.strokeText(f.txt,0,0); ctx.fillStyle=f.c; ctx.fillText(f.txt,0,0); ctx.restore(); }
}
function drawHUD(){
  ctx.setTransform(1,0,0,1,0,0);
  // 방위(북쪽)
  const n=proj(-.352*10,-.936*10,0), o=proj(0,0,0), dx=n[0]-o[0], dy=n[1]-o[1], L=Math.hypot(dx,dy), ux=dx/L, uy=dy/L, cx=VW-52, cy=VH-52;
  ctx.fillStyle="rgba(10,24,36,.55)"; ctx.beginPath(); ctx.arc(cx,cy,32,0,6.283); ctx.fill(); ctx.strokeStyle="rgba(255,255,255,.5)"; ctx.lineWidth=1.5; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx+ux*24,cy+uy*24); ctx.lineTo(cx-uy*6-ux*8,cy+ux*6-uy*8); ctx.lineTo(cx+uy*6-ux*8,cy-ux*6-uy*8); ctx.closePath(); ctx.fillStyle="#ff6b6b"; ctx.fill();
  ctx.fillStyle="#fff"; ctx.font="800 12px "+FONT; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText("N",cx+ux*40*.78+0,cy+uy*40*.78);
  // 시계
  ctx.fillStyle="rgba(10,24,36,.62)"; ctx.beginPath(); ctx.roundRect(14,14,150,44,10); ctx.fill(); ctx.fillStyle="#fff"; ctx.font="800 24px "+FONT; ctx.textAlign="left"; ctx.fillText(clock(simT),26,37);
  ctx.font="600 12px "+FONT; ctx.fillStyle="rgba(255,255,255,.75)"; ctx.fillText("영업 11:00–21:00",88,37);
  if(imgReady<2){ ctx.fillStyle="#fff"; ctx.font="700 16px "+FONT; ctx.textAlign="center"; ctx.fillText("도시 모델을 불러오는 중…",VW/2,VH/2); }
}
function draw(){
  ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle="#0d2030"; ctx.fillRect(0,0,VW,VH);
  if(imgReady<2){ drawHUD(); return; }
  const z=cam.z; ctx.setTransform(z,0,0,z,VW/2-cam.x*z,VH/2-cam.y*z);
  const vx0=cam.x-VW/2/z, vx1=cam.x+VW/2/z, vy0=cam.y-VH/2/z, vy1=cam.y+VH/2/z;
  const gw=groundImg.width, gh=groundImg.height, sx=Math.max(0,Math.floor(vx0)), sy=Math.max(0,Math.floor(vy0)), ex=Math.min(gw,Math.ceil(vx1)), ey=Math.min(gh,Math.ceil(vy1));
  ctx.imageSmoothingEnabled=true; ctx.imageSmoothingQuality="high";
  if(ex>sx&&ey>sy) ctx.drawImage(groundImg,sx,sy,ex-sx,ey-sy,sx,sy,ex-sx,ey-sy);
  drawRing();
  // 캐릭터를 가리는 순번별로 묶기
  const buckets={}, tail=[];
  for(const L of live){ if(L.mode==="inside") continue; const k=occluder(L.x,L.y); if(k===1e9) tail.push(L); else (buckets[k]=buckets[k]||[]).push(L); }
  const cars=trainCars(performance.now()); let ci=0;
  for(let i=0;i<ORD.length;i++){ const o=ORD[i];
    while(ci<cars.length && cars[ci].key<=o.key){ drawCar(cars[ci]); ci++; }
    const b=buckets[i]; if(b) b.sort((p,q)=>(p.x+p.y)-(q.x+q.y)).forEach(drawAgent);
    if(o.ox>vx1||o.ox+o.w<vx0||o.oy>vy1||o.oy+o.h<vy0) continue;
    if(o.kind==="shop") drawShop(o); else ctx.drawImage(atlasImg,o.ax,o.ay,o.w,o.h,o.ox,o.oy,o.w,o.h);
  }
  while(ci<cars.length){ drawCar(cars[ci]); ci++; }
  tail.sort((p,q)=>(p.x+p.y)-(q.x+q.y)).forEach(drawAgent);
  drawLabels(vx0,vx1,vy0,vy1);
  drawHUD();
}
function frame(ts){
  if(!last) last=ts; const dt=Math.min(0.05,(ts-last)/1000); last=ts;
  if(playing){ const dm=dt*(+$("selSpeed").value);
    simT+=dm; step(dm); floats.forEach(f=>f.t-=dt*0.8); floats=floats.filter(f=>f.t>0);
    renderStats();
    if(simT>=CONFIG.closeMin+90 && live.length===0){ playing=false; $("btnPlay").textContent="▶ 다시 보기"; } }
  const k=1-Math.pow(0.001,dt); cam.x+=(cam.tx-cam.x)*k; cam.y+=(cam.ty-cam.y)*k; cam.z+=(cam.tz-cam.z)*k;
  draw(); requestAnimationFrame(frame);
}
/* ---- 카메라 조작 ---- */
function clampCam(){ cam.tz=Math.max(.3,Math.min(2.2,cam.tz)); cam.tx=Math.max(0,Math.min(SCENE.world[0],cam.tx)); cam.ty=Math.max(0,Math.min(SCENE.world[1],cam.ty)); }
let drag=null;
cv.addEventListener("pointerdown",e=>{ drag={x:e.clientX,y:e.clientY}; cv.setPointerCapture(e.pointerId); cam.follow=false; });
cv.addEventListener("pointermove",e=>{ if(!drag) return; const r=cv.getBoundingClientRect(), s=VW/r.width; cam.tx-=(e.clientX-drag.x)*s/cam.z; cam.ty-=(e.clientY-drag.y)*s/cam.z; cam.x=cam.tx; cam.y=cam.ty; drag={x:e.clientX,y:e.clientY}; clampCam(); });
cv.addEventListener("pointerup",()=>{ drag=null; }); cv.addEventListener("pointercancel",()=>{ drag=null; });
cv.addEventListener("wheel",e=>{ e.preventDefault(); cam.tz*=e.deltaY<0?1.12:1/1.12; clampCam(); },{passive:false});
$("btnZin").addEventListener("click",()=>{ cam.tz*=1.25; clampCam(); }); $("btnZout").addEventListener("click",()=>{ cam.tz/=1.25; clampCam(); });
$("btnFit").addEventListener("click",()=>{ cam.tx=SCENE.world[0]/2; cam.ty=SCENE.world[1]*.5; cam.tz=.3; cam.follow=false; });
$("btnFocus").addEventListener("click",()=>focusStore(false));
