"""把 latest.json 渲染成单文件响应式网页 docs/index.html（电脑/手机通用，无外部依赖）。

页面结构（固定暗色，电脑/手机一致，所有周期同时展示，无需切换）：
  1 各周期资金流入/流出最多的行业TOP3：一张堆叠条形图，横轴＝周期（20/60/120/250日），同一纵轴比例尺，柱向上＝流入前3、柱向下＝流出前3，文字全部在悬停/点按浮窗
  2 四象限散点图（横轴长期、纵轴短期，一个点=一个行业，点击圆点选中行业）
  3 选中行业详情：6个周期的主力净流入条形图 + 各周期行业内个股TOP3
"""
import json

import config

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>行业资金流向</title>
<style>
:root{color-scheme:dark;--bg:#12151c;--card:#1b1f29;--ink:#e8ebf2;--mute:#98a0b3;--line:#2a3040;
--in:#ff6b63;--out:#2ec4b6;--warn:#f0b04a;--warn-bg:#3a2e16;--accent:#7aa2ff;--ok-bg:#17332a;--ok:#3ccf8e;
--in1:#ffa09a;--in2:#ff6b63;--in3:#c9433d;--out1:#7ee6da;--out2:#2ec4b6;--out3:#23958b;
--pt:#3987e5;--grid:#2c2c2a;--axis:#4a4a46;--axtxt:#898781}
html{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0}
.meta{color:var(--mute);font-size:13px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;background:var(--warn-bg);color:var(--warn)}
.badge.final{background:var(--ok-bg);color:var(--ok)}
.note{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:12px 0;color:var(--mute);font-size:13px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin:12px 0}
.panel h2{font-size:16px;margin:0}
.sub{color:var(--mute);font-size:13px;margin:2px 0 8px}
#chart{position:relative}
#chart svg{display:block;width:100%;height:auto;touch-action:manipulation}
.pt{cursor:pointer;outline:none}
.pt:focus-visible .dot{stroke:var(--ink)}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);white-space:nowrap;display:none;z-index:4}
.tip .n{color:var(--mute);margin-bottom:2px}
.tip .v{font-size:14px;font-weight:600}
.gw{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:13px;color:var(--mute)}
.gbar{display:flex;gap:6px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 12px;border-radius:18px;font-size:13px;cursor:pointer}
.tab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}
section{margin:18px 0}
section h3{font-size:15px;margin:0 0 2px}
section .tag{color:var(--mute);font-size:13px;margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.panel .card{border:0;padding:0}
.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:4px 8px}
.name{font-weight:600;font-size:16px;white-space:nowrap;flex-shrink:0}
.today{font-size:12px;color:var(--mute);white-space:normal}
.tr{display:flex;flex-direction:column;align-items:flex-end;gap:2px;flex:1 1 280px;min-width:0;text-align:right}
@media (max-width:520px){.tr{align-items:flex-start;text-align:left;flex-basis:100%}}
.in{color:var(--in)}.out{color:var(--out)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{font-size:12px;padding:2px 8px;border-radius:8px;background:var(--bg)}
.chip.in{background:var(--in-bg)}.chip.out{background:var(--out-bg)}
.etf{font-size:12px;margin-top:8px;color:var(--mute)}
.etf.diverge{color:var(--warn)}
.stitle{font-size:12px;color:var(--mute);margin-bottom:6px}
.cov{font-size:11px;color:var(--warn);margin-top:4px}
.stocks{margin-top:8px;border-top:1px dashed var(--line);padding-top:8px;font-size:13px}
.srow{display:flex;justify-content:space-between;gap:8px}
.stocks small{color:var(--mute)}
.empty{color:var(--mute);font-size:13px}
.r1{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:flex-start;margin-top:8px}
.r1 .cbox{flex:1 1 420px;min-width:0}
.lg{flex:0 1 300px;font-size:13px;color:var(--mute)}
.lg .lt{color:var(--ink);font-weight:600;margin-bottom:4px}
.lg .lp{margin:6px 0}
.lg .lrow{display:flex;flex-wrap:wrap;gap:4px 12px;margin:6px 0}
.lg .lsw{color:var(--ink);font-size:12px}
.tsw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.colg{outline:none;cursor:pointer}
.colg:focus-visible rect{stroke:var(--accent);stroke-width:2}
.cbox{width:100%}
.cbox svg{display:block;touch-action:manipulation}
.key{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:center;font-size:13px;color:var(--mute);margin:4px 0 2px}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.sw.in{background:var(--in)}.sw.out{background:var(--out)}
.rowg{cursor:pointer;outline:none}
.rhit{fill:transparent}
.rowg:hover .rhit{fill:rgba(255,255,255,.07)}
.rowg:focus-visible .rhit{stroke:var(--accent);stroke-width:2}
.dhead{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:2px 12px}
.dhead .dr{margin-left:auto;text-align:right;margin-bottom:6px}
.dtag{color:var(--mute);font-size:13px}
.dline{font-size:13px;color:var(--mute);margin-top:2px}
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin-top:6px}
.sb{background:var(--bg);border-radius:10px;padding:8px 10px}
.sb h4{font-size:13px;margin:0 0 4px}
.sr{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:2px 0}
.sr .r{text-align:right;white-space:nowrap}
.sr small{color:var(--mute)}
.gtip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.4);display:none;z-index:9;max-width:min(330px,calc(100vw - 16px))}
.gtip .n{color:var(--mute);margin-bottom:2px}
.gtip .v{font-size:13px;font-weight:600}
.gtip .tg{margin-top:6px;font-size:12px;color:var(--mute)}
.gtip .trow{padding:3px 4px;border-radius:6px}
.gtip .trow.hl{background:rgba(255,255,255,.09)}
.gtip .t1{display:flex;justify-content:space-between;gap:12px;align-items:baseline;font-size:13px}
.gtip .t2{color:var(--mute);font-size:11px}
.gtip .hint{margin-top:6px;color:var(--accent);font-size:12px}
details{margin-top:8px;font-size:13px;color:var(--mute)}
summary{cursor:pointer;padding:4px 0}
table{border-collapse:collapse;width:100%;font-size:12px;margin-top:4px}
th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;font-weight:400}
th{color:var(--mute)}
td.num,th.num{text-align:right}
footer{color:var(--mute);font-size:12px;margin:24px 0 8px}
</style>
</head>
<body>
<div class="wrap">
<h1>行业资金流向</h1>
<div class="meta" id="meta"></div>
<div class="note">
口径：行业按__SCHEME__分类（取自东方财富F10公司资料；个别公司分类滞后时，可在 industry_override.json 手动修正）；行业主力净流入＝行业内个股主力净流入（新浪大单口径，估算值）逐日汇总，占比＝主力净流入合计 ÷ 同期成交额合计。因新浪大单口径的全市场合计偏正，行业的净流入和占比均已扣除全市场同期水平，只反映相对强弱（红色=强于全市场，绿色=弱于全市场）。红色=流入（条向右），绿色=流出（条向左）。
短期=近20日，长期=近250日（历史不足时用120日，详情里会标注）。
盘中数据为"今日暂计"，盘后定稿；ETF验证为T+1。本页是资金流向观察工具，不构成买卖建议。
</div>

<div class="panel">
  <h2>资金流入 / 流出最多的行业 TOP3</h2>
  <div class="key"><span><i class="sw in"></i>净流入（向右）</span><span><i class="sw out"></i>净流出（向左）</span></div>
  <div id="rankChart" class="cbox" style="margin-top:8px"></div>
</div>

<div class="panel">
  <h2>行业四象限</h2>
  <div id="chart"></div>
</div>

<div class="panel" id="detailPanel">
  <h2>个股热榜</h2>
  <div id="detail" style="margin-top:6px"></div>
</div>

<footer id="foot"></footer>
</div>
<script>
const DATA = __DATA__;
const QMETA = __QMETA__;
const $ = id => document.getElementById(id);
function h(tag, cls, text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
const fmt = (v,d=2) => v==null ? "—" : (v>0?"+":"")+v.toFixed(d)+"%";
const cls = v => v==null ? "" : (v>0 ? "in" : v<0 ? "out" : "");
const order = ["q1","q2","q3","q4"];
const WINS = DATA.windows || [20,60,120,250];
const signed = (v,d=2) => v==null ? "—" : (v>0?"+":"")+v.toFixed(d);

/* ---------- 通用：全局提示框、条形路径、表格 ---------- */
const gt = h("div","gtip"); document.body.append(gt);
function gtPlace(x,y){
  gt.style.display="block";
  const w=gt.offsetWidth, hh=gt.offsetHeight;
  gt.style.left=Math.max(4,Math.min(x+12,innerWidth-w-4))+"px";
  gt.style.top=(y-hh-10<4 ? y+16 : y-hh-10)+"px";
}
function gtShow(title, rows, x, y){
  gt.replaceChildren(); gt.append(h("div","n",title));
  rows.forEach(([k,v])=>{const d=h("div","v"); d.append(k+" "); d.append(v); gt.append(d)});
  gtPlace(x,y); gtArm();
}
function gtShowNode(node, x, y){gt.replaceChildren(node); gtPlace(x,y); gtArm()}
let gtTouch = false, gtTimer = null;
let tapKey = null, tapTimer = null;
const gtHide = () => {clearTimeout(gtTimer); gt.style.display="none"};
const setTap = k => {tapKey=k; clearTimeout(tapTimer); tapTimer=setTimeout(()=>{tapKey=null},3000)};
// 手机：浮窗2.2秒后自动消失；点按别处或滚动页面也立即消失
function gtArm(){clearTimeout(gtTimer); if(gtTouch) gtTimer=setTimeout(gtHide,2200)}
document.addEventListener("pointerdown",e=>{gtTouch = e.pointerType!=="mouse"; if(gtTouch) gtHide()},true);
window.addEventListener("scroll",gtHide,{passive:true});
function bindTip(el, title, rows){
  el.addEventListener("pointermove",e=>gtShow(title,rows,e.clientX,e.clientY));
  el.addEventListener("pointerleave",gtHide);
  el.addEventListener("focus",()=>{const r=el.getBoundingClientRect();gtShow(title,rows,r.left+r.width/2,r.top)});
  el.addEventListener("blur",gtHide);
}
// 条形：基线一侧方角、数据端4px圆角
function barPath(x0,len,dir,y,th){
  const r=Math.min(4,len/2), x1=x0+dir*len;
  return "M"+x0+" "+y+" H"+(x1-dir*r)+" Q"+x1+" "+y+" "+x1+" "+(y+r)+" V"+(y+th-r)+" Q"+x1+" "+(y+th)+" "+(x1-dir*r)+" "+(y+th)+" H"+x0+" Z";
}
function table(heads, rows){
  const t=h("table",""); const tr=h("tr","");
  heads.forEach((x,i)=>tr.append(h("th",i>=heads.numFrom?"num":"",x))); t.append(tr);
  rows.forEach(r=>{const q=h("tr",""); r.forEach((c,i)=>q.append(h("td",i>=heads.numFrom?"num":"",c))); t.append(q)});
  return t;
}
const qTitle = q => q ? QMETA[q].title : "历史不足，未分类";

/* ---------- 模块1：堆叠条形图（横轴=周期；柱向上=净流入最多的3个行业，柱向下=净流出最多的3个行业；同一纵轴比例尺；文字全部在浮窗） ---------- */
const RWINS = DATA.rank_windows || [20,60,120,250];
/* ---------- 模块1：一张完整的正负轴条形图（纵轴=周期，同一比例尺，标签交错在条形对侧） ---------- */
function rankChartAll(W){
  const gl=46, rowH=24, th=14, gpad=7;
  const groups=RWINS.map(w=>{const r=(DATA.rank||{})[String(w)]||{in:[],out:[]}; return {w, rows:[...r.in,...r.out]}});
  const maxName=Math.max(4,...groups.flatMap(g=>g.rows.map(r=>r.industry.length)));
  const labelPad=Math.max(76, Math.round(maxName*13*(W<520?0.95:1))+14);
  let H=4;
  groups.forEach(g=>{g.y=H; g.h=Math.max(g.rows.length,1)*rowH+2*gpad; H+=g.h});
  H+=4;
  const all=groups.flatMap(g=>g.rows);
  const P=Math.max(0,...all.filter(r=>r.net>0).map(r=>r.net)), N=Math.max(0,...all.filter(r=>r.net<0).map(r=>-r.net));
  const areaW=W-gl-4;
  const k=(P+N)>0 ? Math.max(1e-6,(areaW-2*labelPad)/(P+N)) : 0;
  const x0=gl+N*k+labelPad;
  const svg=s("svg",{width:W,height:H,viewBox:"0 0 "+W+" "+H,role:"img","aria-label":"各周期主力净流入最多与最少的行业，纵轴为周期"});
  groups.forEach((g,gi)=>{
    if(gi%2===0) svg.append(s("rect",{x:0,y:g.y,width:W,height:g.h,fill:"rgba(255,255,255,.035)",rx:6}));
    svg.append(s("text",{x:4,y:g.y+g.h/2+5,"font-size":14,"font-weight":700,fill:"var(--ink)"},g.w+"日"));
  });
  svg.append(s("line",{x1:x0,x2:x0,y1:4,y2:H-4,stroke:"var(--axis)","stroke-width":1}));
  groups.forEach(g=>{
    if(!g.rows.length){svg.append(s("text",{x:gl+8,y:g.y+g.h/2+4,"font-size":12,fill:"var(--mute)"},"暂无数据（历史不足）"));return}
    g.rows.forEach((r,i)=>{
      const y=g.y+gpad+i*rowH, cy=y+rowH/2, pos=r.net>0, len=Math.max(2,Math.abs(r.net)*k);
      if(i>0 && g.rows[i-1].net>0 && !pos) svg.append(s("line",{x1:gl,x2:W-4,y1:y,y2:y,stroke:"var(--grid)","stroke-width":1}));
      const a=ALL.find(x=>x.it.industry===r.industry);
      const gr=s("g",{class:"rowg"});
      gr.append(s("rect",{class:"rhit",x:gl,y,width:W-gl,height:rowH}));
      gr.append(s("path",{d:barPath(x0,len,pos?1:-1,cy-th/2,th),fill:pos?"var(--in)":"var(--out)"}));
      gr.append(s("text",{x:pos?x0+len+6:x0-len-6,y:cy+4,"text-anchor":pos?"start":"end","font-size":12,"font-weight":600,fill:"var(--ink)"},signed(r.net)+"亿"));
      gr.append(s("text",{x:pos?x0-8:x0+8,y:cy+4,"text-anchor":pos?"end":"start","font-size":13,fill:"var(--ink)"},r.industry));
      bindTip(gr, r.industry+" · "+g.w+"日", [["主力净流入（扣除全市场）",signed(r.net)+"亿"],["主力净流入占同期成交额比例（扣除全市场）",fmt(r.ratio)],["所属象限",qTitle(r.q)]]);
      if(a){gr.setAttribute("tabindex","0");gr.setAttribute("role","button");
        gr.setAttribute("aria-label",g.w+"日 "+r.industry+"，主力净流入"+signed(r.net)+"亿，点击查看详情");
        gr.addEventListener("click",e=>{
          if(gtTouch && tapKey!==g.w+r.industry){   // 手机：第一次点按先显示浮窗，再点一次才进入行业详情
            gtShow(r.industry+" · "+g.w+"日（再点一次查看行业详情）",[["主力净流入（扣除全市场）",signed(r.net)+"亿"],["主力净流入占同期成交额比例（扣除全市场）",fmt(r.ratio)],["所属象限",qTitle(r.q)]],e.clientX,e.clientY);
            setTap(g.w+r.industry); gtArm(); return}
          choose(a)});
        gr.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(a)}});}
      svg.append(gr);
    });
  });
  return svg;
}
function renderRank(){
  const box=$("rankChart"); box.replaceChildren();
  const cb=box;
  const any=RWINS.some(w=>{const r=(DATA.rank||{})[String(w)];return r&&(r.in.length||r.out.length)});
  if(any) cb.append(rankChartAll(Math.max(280,cb.clientWidth)));
  else cb.append(h("div","empty","暂无数据（历史不足）"));
}

/* ---------- 模块3：选中行业详情（各周期条形图 + 各周期个股TOP3，全部同时展示） ---------- */
function detailChart(it, W){
  const rowH=34, th=16, padT=4, padB=4, H=padT+RWINS.length*rowH+padB;
  const gl=48, gr=74, labelPad=70;
  const svg=s("svg",{width:W,height:H,viewBox:"0 0 "+W+" "+H,role:"img","aria-label":it.industry+"各周期主力净流入"});
  const nets=RWINS.map(w=>it.nets[String(w)]);
  const pos=Math.max(0,...nets.filter(v=>v!=null)), neg=Math.max(0,...nets.filter(v=>v!=null).map(v=>-v));
  const span=Math.max(pos+neg,1e-9), areaL=gl+labelPad*(neg>0?1:0.3), areaR=W-gr-labelPad*(pos>0?1:0.3);
  const k=Math.max(10,areaR-areaL)/span, x0=areaL+neg*k;
  svg.append(s("line",{x1:x0,x2:x0,y1:padT,y2:H-padB,stroke:"var(--axis)","stroke-width":1}));
  RWINS.forEach((w,i)=>{
    const y=padT+i*rowH, cy=y+rowH/2, v=it.nets[String(w)], ratio=it.ratios[String(w)];
    const g=s("g",{class:"rowg",tabindex:0,role:"img","aria-label":w+"日主力净流入"+signed(v)+"亿，占同期成交额比例"+fmt(ratio)});
    if(i%2===0) g.append(s("rect",{x:0,y,width:W,height:rowH,fill:"rgba(255,255,255,.035)",rx:6}));
    g.append(s("rect",{class:"rhit",x:0,y,width:W,height:rowH}));
    g.append(s("text",{x:4,y:cy+5,"font-size":14,"font-weight":700,fill:"var(--ink)"},w+"日"));
    if(v==null){
      g.append(s("text",{x:areaL,y:cy+4,"font-size":12,fill:"var(--mute)"},"历史不足"));
    }else{
      const len=Math.max(2,Math.abs(v)*k), p=v>0;
      g.append(s("path",{d:barPath(x0,len,p?1:-1,cy-th/2,th),fill:p?"var(--in)":"var(--out)"}));
      g.append(s("text",{x:p?x0+len+6:x0-len-6,y:cy+4,"text-anchor":p?"start":"end","font-size":12,"font-weight":600,fill:"var(--ink)"},signed(v)+"亿"));
    }
    g.append(s("text",{x:W-2,y:cy+4,"text-anchor":"end","font-size":12,fill:"var(--ink)"},fmt(ratio)));
    bindTip(g, it.industry+" · "+w+"日", [["主力净流入（扣除全市场）",signed(v)+"亿"],["主力净流入占同期成交额比例（扣除全市场）",fmt(ratio)]]);
    svg.append(g);
  });
  return svg;
}
function stockBlocks(it){
  const grid=h("div","sg");
  RWINS.forEach(w=>{
    const b=h("div","sb"); b.append(h("h4","",w+"日主力净流入 TOP3"));
    const rows=(it.stocks&&it.stocks[String(w)])||[];
    if(!rows.length) b.append(h("div","empty","暂无数据"));
    rows.forEach(x=>{
      const r=h("div","sr");
      const l=h("span",""); l.append(x.name); l.title=x.code; r.append(l);
      const rt=h("span","r"); rt.append(h("span",cls(x.net),signed(x.net)+"亿")); rt.append(" ");
      rt.append(h("small",cls(x.pct_chg),"今日 "+fmt(x.pct_chg))); r.append(rt); b.append(r);
    });
    const have=it.stocks&&it.stocks.cov?it.stocks.cov[String(w)]:null;
    if(have!=null && have<w*0.9) b.append(h("div","cov","个股数据仅累积 "+have+" 日，未满 "+w+" 日，仅供参考"));
    grid.append(b);
  });
  return grid;
}
function renderDetail(sel){
  const d=$("detail"); d.replaceChildren();
  if(!sel){d.append(h("div","empty","暂无已分类的行业"));return}
  const it=sel.it;
  const head=h("div","dhead"); head.append(h("span","name",it.industry)); head.append(h("span","dtag",QMETA[sel.q].title+"（"+QMETA[sel.q].tag+"）"));
  const rt=h("div","dr");
  if(it.today_net!=null){const l=h("div","dline",""); l.append("今日主力净流入（扣除全市场） "); l.append(h("span",cls(it.today_net),signed(it.today_net)+"亿")); rt.append(l);}
  if(it.etf) rt.append(h("div","dline"+(it.etf.status==="diverge"?" diverge":""),"ETF验证："+it.etf.text));
  head.append(rt); d.append(head);
  d.append(h("div","sub","条形＝各周期主力净流入金额（扣除全市场，亿元）；右列＝主力净流入占同期成交额比例（扣除全市场）。"));
  const cb=h("div","cbox"); d.append(cb);
  cb.append(detailChart(it, Math.max(260,cb.clientWidth)));
  d.append(h("div","sub","行业内个股 · 各周期主力净流入 TOP3"));
  if(it.stocks) d.append(stockBlocks(it)); else d.append(h("div","empty","该象限为持续撤离，不展示个股。"));
}

/* ---------- 顶部信息 ---------- */
const meta = $("meta");
meta.append(h("span","","交易日 "+DATA.trade_date));
meta.append(h("span","","更新于 "+DATA.updated_at+"（北京时间）"));
const badge=h("span","badge","");
meta.append(badge);
function bjNow(){return new Date(Date.now()+(new Date().getTimezoneOffset()+480)*60000);}
function isOpen(){
  const t=bjNow(),wd=t.getDay(),m=t.getHours()*60+t.getMinutes();
  if(wd===0||wd===6)return false;
  if(m<570||m>=900)return false;
  const today=t.getFullYear()+String(t.getMonth()+1).padStart(2,"0")+String(t.getDate()).padStart(2,"0");
  const td=String(DATA.trade_date||"").replace(/\D/g,"");
  return !td||td===today;
}
function setBadge(){const o=isOpen();badge.className="badge"+(o?"":" final");badge.textContent=o?"盘中暂计":"盘后定稿";}
setBadge();setInterval(setBadge,60000);
meta.append(h("span","","已累积历史 "+DATA.history_days+" 个交易日"));
$("foot").textContent = DATA.insufficient.length
  ? "历史数据不足、暂未分类的行业："+DATA.insufficient.join("、")
  : "";

/* ---------- 四象限图 ---------- */
const NS = "http://www.w3.org/2000/svg";
function s(tag, attrs, text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!==undefined)e.textContent=text;return e}
const ALL = [];
order.forEach(q=>DATA.quadrants[q].forEach(it=>ALL.push({q,it})));
let selected = ALL.length ? ALL[0] : null;
let hover = null;

function ticksFor(lo, hi, target){
  const raw=(hi-lo)/target, p=Math.pow(10,Math.floor(Math.log10(raw))), f=raw/p;
  const st=(f<1.5?1:f<3?2:f<7?5:10)*p, out=[];
  for(let v=Math.ceil(lo/st-1e-9)*st; v<=hi+1e-9; v+=st) out.push(Math.round(v/st)*st);
  return {st, out};
}
const tickText = (v,st) => (v>0?"+":"")+v.toFixed(st>=1?0:(st>=0.1?1:2))+"%";

function showDetail(sel, scroll){
  renderDetail(sel);
  if(scroll) $("detailPanel").scrollIntoView({behavior:"smooth",block:"nearest"});
}

function draw(){
  const wrap = $("chart"); wrap.replaceChildren();
  if(!ALL.length){wrap.append(h("div","empty","暂无已分类的行业"));return}
  const W = Math.max(300, wrap.clientWidth || 360);
  const H = W < 520 ? Math.max(380, Math.round(W*1.05)) : Math.max(440, Math.min(560, Math.round(W*0.55)));
  const m = {l: W<520?58:60, r:14, t:14, b:46};
  const pw = W-m.l-m.r, ph = H-m.t-m.b;

  const amt=a=>Math.abs((a.it.nets||{})[String(a.it.long_basis)]||0), amax=Math.max(1e-9,...ALL.map(amt));
  const R=a=>3.5+(W<520?5:8)*Math.sqrt(amt(a)/amax);
  const xs = ALL.map(a=>a.it.long), ys = ALL.map(a=>a.it.short);
  const padOf = (lo,hi)=>{const sp=(hi-lo)||1; return sp*(W<520?0.2:0.1)};
  let x0=Math.min(0,...xs), x1=Math.max(0,...xs), y0=Math.min(0,...ys), y1=Math.max(0,...ys);
  const px=padOf(x0,x1), py=padOf(y0,y1); x0-=px; x1+=px; y0-=py; y1+=py;
  const X = v => m.l + (v-x0)/(x1-x0)*pw;
  const Y = v => m.t + (1-(v-y0)/(y1-y0))*ph;

  const svg = s("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":"行业资金四象限散点图：横轴长期，纵轴短期"});
  const xt = ticksFor(x0,x1,W<520?4:6), yt = ticksFor(y0,y1,W<520?5:6);

  // 网格与刻度（细实线、低对比）
  xt.out.forEach(v=>{
    svg.append(s("line",{x1:X(v),x2:X(v),y1:m.t,y2:m.t+ph,stroke:"var(--grid)","stroke-width":1}));
    svg.append(s("text",{x:X(v),y:m.t+ph+16,"text-anchor":"middle","font-size":11,fill:"var(--axtxt)"},tickText(v,xt.st)));
  });
  yt.out.forEach(v=>{
    svg.append(s("line",{x1:m.l,x2:m.l+pw,y1:Y(v),y2:Y(v),stroke:"var(--grid)","stroke-width":1}));
    svg.append(s("text",{x:m.l-6,y:Y(v)+4,"text-anchor":"end","font-size":11,fill:"var(--axtxt)"},tickText(v,yt.st)));
  });
  // 零轴（分隔四个象限）
  svg.append(s("line",{x1:X(0),x2:X(0),y1:m.t,y2:m.t+ph,stroke:"var(--axis)","stroke-width":1.5}));
  svg.append(s("line",{x1:m.l,x2:m.l+pw,y1:Y(0),y2:Y(0),stroke:"var(--axis)","stroke-width":1.5}));
  // 轴标题
  svg.append(s("text",{x:m.l+pw/2,y:H-6,"text-anchor":"middle","font-size":W<520?10.5:12,fill:"var(--mute)"},(W<520?"长期250日 主力净流入占同期成交额比例（扣除全市场）→":"长期：主力净流入占同期成交额比例（扣除全市场）（250日，不足用120日）→ 流入")));
  svg.append(s("text",{x:11,y:m.t+ph/2,"text-anchor":"middle","font-size":W<520?10.5:12,fill:"var(--mute)",transform:"rotate(-90 11 "+(m.t+ph/2)+")"},(W<520?"短期20日 主力净流入占同期成交额比例（扣除全市场）→":"短期：主力净流入占同期成交额比例（扣除全市场）（20日）→ 流入")));

  // 象限角标：q1右上 q2左上 q3右下 q4左下
  const cnt = q => DATA.quadrants[q].length;
  const top = m.t, bot = m.t+ph;
  const corners = [   // [象限, x, 第一行y, 第二行y, 对齐]；第一行=象限名称，第二行=注释
    ["q1", m.l+pw-6, top+14, top+27, "end"], ["q2", m.l+6, top+14, top+27, "start"],
    ["q3", m.l+pw-6, bot-21, bot-8, "end"], ["q4", m.l+6, bot-21, bot-8, "start"]];
  const reserved = [];
  corners.forEach(([q,x,y1,y2,a])=>{
    const t1 = QMETA[q].title+"("+cnt(q)+")", t2 = "（"+QMETA[q].tag+"）";
    svg.append(s("text",{x,y:y1,"text-anchor":a,"font-size":11,fill:"var(--mute)","font-weight":600},t1));
    svg.append(s("text",{x,y:y2,"text-anchor":a,"font-size":11,fill:"var(--mute)"},t2));
    const w = Math.max(t1.length,t2.length)*11;
    reserved.push({x0:a==="end"?x-w:x, x1:a==="end"?x:x+w, y0:y1-13, y1:y2+3});
  });

  // 选择性标注：每个象限里离原点最远的前3个 + 当前选中
  const nx = v=>v/((x1-x0)||1), ny = v=>v/((y1-y0)||1);
  const cand = [];
  order.forEach(q=>{
    ALL.filter(a=>a.q===q).sort((a,b)=>Math.hypot(nx(b.it.long),ny(b.it.short))-Math.hypot(nx(a.it.long),ny(a.it.short))).slice(0,3).forEach(a=>cand.push(a));
  });
  if(selected && !cand.includes(selected)) cand.unshift(selected);
  const placed = reserved.slice(), labels = new Map();
  const pointRects = ALL.map(a=>({a,x0:X(a.it.long)-R(a)-2,x1:X(a.it.long)+R(a)+2,y0:Y(a.it.short)-R(a)-2,y1:Y(a.it.short)+R(a)+2}));
  const overlap = (r,p)=>!(r.x1<p.x0||r.x0>p.x1||r.y1<p.y0||r.y0>p.y1);
  cand.sort((a,b)=>(b===selected)-(a===selected));
  cand.forEach(a=>{
    const cx=X(a.it.long), cy=Y(a.it.short), w=a.it.industry.length*11+2, rr=R(a)+3;
    const opts = [
      {r:{x0:cx+rr,x1:cx+rr+w,y0:cy-7,y1:cy+7}, t:{x:cx+rr,y:cy+4,anchor:"start"}},
      {r:{x0:cx-rr-w,x1:cx-rr,y0:cy-7,y1:cy+7}, t:{x:cx-rr,y:cy+4,anchor:"end"}},
      {r:{x0:cx-w/2,x1:cx+w/2,y0:cy-rr-14,y1:cy-rr}, t:{x:cx,y:cy-rr-4,anchor:"middle"}},
      {r:{x0:cx-w/2,x1:cx+w/2,y0:cy+rr,y1:cy+rr+14}, t:{x:cx,y:cy+rr+11,anchor:"middle"}}];
    for(const o of opts){
      const inside = o.r.x0>=m.l && o.r.x1<=m.l+pw && o.r.y0>=m.t && o.r.y1<=m.t+ph;
      const hit = placed.some(p=>overlap(o.r,p)) || pointRects.some(p=>p.a!==a && overlap(o.r,p));
      if(inside && !hit){placed.push(o.r); labels.set(a,o.t); break}
    }
  });

  // 点（2px 表面色环；选中=墨色描边；悬停略放大）
  const g = s("g",{});
  ALL.forEach(a=>{
    const cx=X(a.it.long), cy=Y(a.it.short);
    const on = a===selected, hv = a===hover;
    const grp = s("g",{class:"pt",tabindex:0,role:"button","aria-label":a.it.industry+"，短期"+fmt(a.it.short)+"，长期"+fmt(a.it.long)});
    const rb=R(a);
    grp.append(s("circle",{cx,cy,r:Math.max(14,rb+4),fill:"transparent"}));           // 24px+ 的点击/悬停范围
    grp.append(s("circle",{class:"dot",cx,cy,r:rb,fill:"var(--pt)","fill-opacity":.8,stroke:on?"var(--ink)":"var(--card)","stroke-width":2}));
    const dot = grp.querySelector(".dot");
    grp.addEventListener("pointerenter",()=>{hover=a;dot.setAttribute("r",rb+1.5);tip(a,cx,cy)});
    grp.addEventListener("pointerleave",()=>{hover=null;dot.setAttribute("r",rb);hideTip()});
    grp.addEventListener("focus",()=>tip(a,cx,cy));
    grp.addEventListener("blur",hideTip);
    grp.addEventListener("click",()=>{
      if(gtTouch && tapKey!=="sc"+a.it.industry){   // 手机：第一次点按显示数值，再点一次进入详情
        tip(a,cx,cy); setTap("sc"+a.it.industry); clearTimeout(gtTimer); gtTimer=setTimeout(hideTip,2600); return}
      choose(a)});
    grp.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(a)}});
    g.append(grp);
  });
  svg.append(g);
  labels.forEach((p,a)=>{
    svg.append(s("text",{x:p.x,y:p.y,"text-anchor":p.anchor,"font-size":11,fill:"var(--ink)","pointer-events":"none","paint-order":"stroke",stroke:"var(--card)","stroke-width":3,"stroke-linejoin":"round"},a.it.industry));
  });
  wrap.append(svg);

  const tipEl = h("div","tip"); wrap.append(tipEl);
  function tip(a,cx,cy){
    tipEl.replaceChildren();
    tipEl.append(h("div","n",a.it.industry+" · "+QMETA[a.q].title));
    const v1=h("div","v",""); v1.append("20日主力净流入占同期成交额比例（扣除全市场） "); v1.append(h("span",cls(a.it.short),fmt(a.it.short))); tipEl.append(v1);
    const v2=h("div","v",""); v2.append(a.it.long_basis+"日主力净流入占同期成交额比例（扣除全市场） "); v2.append(h("span",cls(a.it.long),fmt(a.it.long))); tipEl.append(v2);
    const nv=(a.it.nets||{})[String(a.it.long_basis)];
    if(nv!=null){const v3=h("div","v",""); v3.append(a.it.long_basis+"日主力净流入（扣除全市场） "); v3.append(h("span",cls(nv),signed(nv)+"亿")); tipEl.append(v3); tipEl.append(h("div","tg","圆圈大小＝该金额的绝对值"));}
    tipEl.style.display="block";
    const sx = cx/W*wrap.clientWidth, sy = cy/H*wrap.clientHeight;
    const tw = tipEl.offsetWidth, th = tipEl.offsetHeight;
    let left = sx+12; if(left+tw>wrap.clientWidth) left = sx-12-tw; if(left<0) left=0;
    let topv = sy-th-10; if(topv<0) topv = sy+12;
    tipEl.style.left = left+"px"; tipEl.style.top = topv+"px";
  }
  function hideTip(){tipEl.style.display="none"}
}

function choose(a){selected=a; draw(); showDetail(a,true)}

draw(); showDetail(selected,false); renderRank();
let rt; window.addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(()=>{draw();renderRank();renderDetail(selected)},120)});
</script>
</body>
</html>
"""


def render(result, out=None):
    out = out or (config.DOCS / "index.html")
    data = json.dumps(result, ensure_ascii=False).replace("</", "<\\/")
    qmeta = json.dumps({k: {"title": v["title"], "tag": v["tag"]} for k, v in config.QUADRANTS.items()},
                       ensure_ascii=False)
    scheme = {"em": f"东方财富行业（{config.EM_LEVEL}级）", "csrc": "证监会行业（" + ("门类" if config.CSRC_LEVEL <= 1 else "大类") + "）",
              "sw": "申万一级行业"}.get(config.INDUSTRY_SCHEME, "东方财富行业")
    html = TEMPLATE.replace("__DATA__", data).replace("__QMETA__", qmeta).replace("__SCHEME__", scheme)
    config.DOCS.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
