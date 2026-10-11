"""把 latest.json 渲染成单文件响应式网页 docs/index.html（电脑/手机通用，无外部依赖）。

页面结构：四象限散点图（横轴长期、纵轴短期，一个点=一个行业）→ 选中行业详情（含个股TOP3窗口切换）
→ 全部行业明细（按象限分组，兼作表格视图）。
"""
import json

import config

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>行业资金四象限</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2230;--mute:#6b7385;--line:#e4e7ec;
--in:#d6362f;--out:#1a9a5b;--in-bg:#fdecea;--out-bg:#e7f6ee;--warn:#b26a00;--warn-bg:#fff4e0;--accent:#2f5fd0;
--pt:#2a78d6;--grid:#e1e0d9;--axis:#c3c2b7;--axtxt:#898781}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1b1f29;--ink:#e8ebf2;--mute:#98a0b3;--line:#2a3040;
--in:#ff6b63;--out:#3ccf8e;--in-bg:#3a1f1f;--out-bg:#17332a;--warn:#f0b04a;--warn-bg:#3a2e16;--accent:#7aa2ff;
--pt:#3987e5;--grid:#2c2c2a;--axis:#383835;--axtxt:#898781}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0}
.meta{color:var(--mute);font-size:13px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;background:var(--warn-bg);color:var(--warn)}
.badge.final{background:var(--out-bg);color:var(--out)}
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
footer{color:var(--mute);font-size:12px;margin:24px 0 8px}
</style>
</head>
<body>
<div class="wrap">
<h1>行业资金四象限</h1>
<div class="meta" id="meta"></div>
<div class="note">
口径：行业主力净流入（东方财富大单口径，估算值）÷ 同期成交额。红色=流入，绿色=流出。
短期=近20日，长期=近250日（历史不足时用120日，详情里会标注）。个股TOP3=行业内个股在所选窗口（5/20/60/120/250日）的主力净流入合计前三，可点击切换。
盘中数据为"今日暂计"，盘后定稿；ETF验证为T+1。本页是资金流向观察工具，不构成买卖建议。
</div>

<div class="panel">
  <h2>四象限图</h2>
  <div class="sub">横轴＝长期（250日；不足用120日）主力净流入占同期成交额比例，纵轴＝短期（20日）主力净流入占同期成交额比例，每个点是一个行业。点击圆点查看详情。</div>
  <div id="chart"></div>
</div>

<div class="panel" id="detailPanel">
  <div class="gw"><span>周期（行业金额/涨幅与个股TOP3同步切换）</span><span class="gbar" id="gwin"></span></div>
  <div id="detail" style="margin-top:10px"></div>
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
const WINS = [5,20,60,120,250];
let curWin = DATA.stock_default_window || 20;
let detailReg = [];      // 当前详情卡的周期切换函数

/* ---------- 卡片（选中行业详情） ---------- */
const signed = (v,d=2) => v==null ? "—" : (v>0?"+":"")+v.toFixed(d);
const amt = v => v==null ? "" : " · "+signed(v)+"亿";
function card(it, reg){
  const c = h("div","card");
  const top = h("div","top");
  top.append(h("span","name",it.industry));
  const right = h("div","tr");
  const td = h("span","today");
  td.append("今日行业指数涨幅 "); td.append(h("span",cls(it.pct_chg),fmt(it.pct_chg)));
  if(it.today_net!=null){td.append(" · 今日主力净流入 "); td.append(h("span",cls(it.today_net),signed(it.today_net)+"亿"));}
  const tw = h("div","tw");                   // 跟随周期变化：所选周期的三项指标，每项写全名
  right.append(td); right.append(tw); top.append(right); c.append(top);


  if(it.etf){c.append(h("div","etf "+(it.etf.status==="diverge"?"diverge":""),"ETF验证："+it.etf.text));}

  let stitle, lst, note;
  if(it.stocks){
    const s = h("div","stocks");
    stitle = h("div","stitle",""); lst = h("div",""); note = h("div","cov");
    s.append(stitle); s.append(lst); s.append(note);
    c.append(s);
  }
  function setWin(w){
    tw.replaceChildren();
    const n = it.nets[w];
    [[w+"日行业指数涨幅", it.pcts[w], fmt(it.pcts[w])],
     [w+"日主力净流入", n, signed(n)+"亿"],
     [w+"日主力净流入占同期成交额比例", it.ratios[w], fmt(it.ratios[w])]].forEach(([lab,v,txt])=>{
      const line = h("div","today"); line.append(lab+" "); line.append(h("span",cls(v),txt)); tw.append(line);
    });
    if(!it.stocks) return;
    stitle.textContent = "行业内个股 · "+w+"日主力净流入TOP3";
    lst.replaceChildren();
    const rows = it.stocks[w] || [];
    if(!rows.length) lst.append(h("div","empty","暂无数据"));
    rows.forEach(x=>{
      const row = h("div","srow");
      const l = h("span",""); l.append(x.name+" "); l.append(h("small","",x.code)); row.append(l);
      const r = h("span","");
      r.append(h("span",cls(x.net),signed(x.net)+"亿"));
      r.append(" "); r.append(h("small",cls(x.pct_chg),"个股今日涨幅 "+fmt(x.pct_chg)));
      row.append(r); lst.append(row);
    });
    const have = it.stocks.cov[w];
    note.textContent = have < w*0.9 ? "个股数据仅累积 "+have+" 日，未满 "+w+" 日窗口，排名仅供参考" : "";
  }
  reg.push(setWin);
  setWin(curWin);
  return c;
}

/* ---------- 周期切换（唯一入口） ---------- */
const gbtns = {};
WINS.forEach(w=>{
  const b = h("button","tab"+(w===curWin?" on":""),w+"日");
  b.onclick = () => {
    curWin = w;
    WINS.forEach(k=>gbtns[k].classList.toggle("on",k===w));
    detailReg.forEach(f=>f(w));
  };
  gbtns[w]=b; $("gwin").append(b);
});

/* ---------- 顶部信息 ---------- */
const meta = $("meta");
meta.append(h("span","","交易日 "+DATA.trade_date));
meta.append(h("span","","更新于 "+DATA.updated_at+"（北京时间）"));
meta.append(h("span","badge "+(DATA.mode==="final"?"final":""), DATA.mode==="final"?"盘后定稿":"盘中暂计"));
meta.append(h("span","","已累积历史 "+DATA.history_days+" 个交易日"));
$("foot").textContent = DATA.insufficient.length
  ? "历史数据不足、暂未分类的行业："+DATA.insufficient.join("、")
  : "全部行业均已分类。";

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
  const d = $("detail"); d.replaceChildren(); detailReg = [];
  if(!sel){d.append(h("div","empty","暂无已分类的行业"));return}
  const head = h("div","sub", QMETA[sel.q].title+"（"+QMETA[sel.q].tag+"）");
  d.append(head);
  d.append(card(sel.it, detailReg));
  if(scroll) $("detailPanel").scrollIntoView({behavior:"smooth",block:"nearest"});
}

function draw(){
  const wrap = $("chart"); wrap.replaceChildren();
  if(!ALL.length){wrap.append(h("div","empty","暂无已分类的行业"));return}
  const W = Math.max(300, wrap.clientWidth || 360);
  const H = W < 520 ? Math.max(380, Math.round(W*1.05)) : Math.max(440, Math.min(560, Math.round(W*0.55)));
  const m = {l: W<520?58:60, r:14, t:14, b:46};
  const pw = W-m.l-m.r, ph = H-m.t-m.b;

  const xs = ALL.map(a=>a.it.long), ys = ALL.map(a=>a.it.short);
  const padOf = (lo,hi)=>{const sp=(hi-lo)||1; return sp*0.1};
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
  svg.append(s("text",{x:m.l+pw/2,y:H-6,"text-anchor":"middle","font-size":12,fill:"var(--mute)"},(W<520?"长期：主力净流入占同期成交额比例（250日）→":"长期：主力净流入占同期成交额比例（250日，不足用120日）→ 流入")));
  svg.append(s("text",{x:11,y:m.t+ph/2,"text-anchor":"middle","font-size":12,fill:"var(--mute)",transform:"rotate(-90 11 "+(m.t+ph/2)+")"},(W<520?"短期：主力净流入占同期成交额比例（20日）→":"短期：主力净流入占同期成交额比例（20日）→ 流入")));

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
  const pointRects = ALL.map(a=>({a,x0:X(a.it.long)-7,x1:X(a.it.long)+7,y0:Y(a.it.short)-7,y1:Y(a.it.short)+7}));
  const overlap = (r,p)=>!(r.x1<p.x0||r.x0>p.x1||r.y1<p.y0||r.y0>p.y1);
  cand.sort((a,b)=>(b===selected)-(a===selected));
  cand.forEach(a=>{
    const cx=X(a.it.long), cy=Y(a.it.short), w=a.it.industry.length*11+2;
    const opts = [
      {r:{x0:cx+8,x1:cx+8+w,y0:cy-7,y1:cy+7}, t:{x:cx+8,y:cy+4,anchor:"start"}},
      {r:{x0:cx-8-w,x1:cx-8,y0:cy-7,y1:cy+7}, t:{x:cx-8,y:cy+4,anchor:"end"}},
      {r:{x0:cx-w/2,x1:cx+w/2,y0:cy-22,y1:cy-8}, t:{x:cx,y:cy-12,anchor:"middle"}},
      {r:{x0:cx-w/2,x1:cx+w/2,y0:cy+8,y1:cy+22}, t:{x:cx,y:cy+19,anchor:"middle"}}];
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
    grp.append(s("circle",{cx,cy,r:14,fill:"transparent"}));           // 24px+ 的点击/悬停范围
    grp.append(s("circle",{class:"dot",cx,cy,r:on||hv?6.5:4.5,fill:"var(--pt)",stroke:on?"var(--ink)":"var(--card)","stroke-width":2}));
    const dot = grp.querySelector(".dot");
    grp.addEventListener("pointerenter",()=>{hover=a;dot.setAttribute("r",6.5);tip(a,cx,cy)});
    grp.addEventListener("pointerleave",()=>{hover=null;if(a!==selected)dot.setAttribute("r",4.5);hideTip()});
    grp.addEventListener("focus",()=>tip(a,cx,cy));
    grp.addEventListener("blur",hideTip);
    grp.addEventListener("click",()=>choose(a));
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
    const v1=h("div","v",""); v1.append("20日主力净流入占同期成交额比例 "); v1.append(h("span",cls(a.it.short),fmt(a.it.short))); tipEl.append(v1);
    const v2=h("div","v",""); v2.append(a.it.long_basis+"日主力净流入占同期成交额比例 "); v2.append(h("span",cls(a.it.long),fmt(a.it.long))); tipEl.append(v2);
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

draw(); showDetail(selected,false);
let rt; window.addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(draw,120)});
</script>
</body>
</html>
"""


def render(result, out=None):
    out = out or (config.DOCS / "index.html")
    data = json.dumps(result, ensure_ascii=False).replace("</", "<\\/")
    qmeta = json.dumps({k: {"title": v["title"], "tag": v["tag"]} for k, v in config.QUADRANTS.items()},
                       ensure_ascii=False)
    html = TEMPLATE.replace("__DATA__", data).replace("__QMETA__", qmeta)
    config.DOCS.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
