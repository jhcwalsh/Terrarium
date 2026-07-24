"""Assemble the data-vintage HTML artifact with the real series embedded."""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path("scratch_data.json").read_text(encoding="utf-8")
META = json.loads(DATA)["meta"]

CSS = """
:root{
  --bg:#f6f8fa; --surface:#ffffff; --ink:#141a20; --muted:#5c6874; --line:#e6eaef;
  --accent:#0e7490; --neg:#b45309; --rec:rgba(92,104,120,.10); --edge:#dde3ea;
  --serif:ui-serif,Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0b0e12; --surface:#12171d; --ink:#e7ecf1; --muted:#94a2b2; --line:#232b34;
  --accent:#38bdf8; --neg:#f59e0b; --rec:rgba(148,162,178,.10); --edge:#222a33;
}}
:root[data-theme="dark"]{
  --bg:#0b0e12; --surface:#12171d; --ink:#e7ecf1; --muted:#94a2b2; --line:#232b34;
  --accent:#38bdf8; --neg:#f59e0b; --rec:rgba(148,162,178,.10); --edge:#222a33;
}
:root[data-theme="light"]{
  --bg:#f6f8fa; --surface:#ffffff; --ink:#141a20; --muted:#5c6874; --line:#e6eaef;
  --accent:#0e7490; --neg:#b45309; --rec:rgba(92,104,120,.10); --edge:#dde3ea;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:clamp(20px,4vw,56px) clamp(16px,4vw,40px)}
.mono{font-family:var(--mono)}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.06em;color:var(--muted);
  text-transform:uppercase}
.eyebrow b{color:var(--accent);font-weight:600}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(30px,5vw,50px);line-height:1.05;
  letter-spacing:-.015em;margin:.35em 0 .3em;text-wrap:balance}
.dek{max-width:64ch;color:var(--muted);font-size:16px;margin:0}
.dek .mono{color:var(--ink)}
.stats{display:flex;flex-wrap:wrap;gap:28px;margin-top:28px;padding-top:22px;border-top:1px solid var(--edge)}
.stat .num{font-family:var(--mono);font-size:clamp(20px,3vw,27px);font-weight:600;
  font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.stat .lab{font-family:var(--mono);font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:18px;margin-top:34px}
@media (max-width:520px){.grid{grid-template-columns:1fr}}
.card{margin:0;background:var(--surface);border:1px solid var(--edge);border-radius:12px;
  padding:16px 16px 8px;overflow:hidden}
figcaption{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.ct h2{font-family:var(--serif);font-weight:600;font-size:18px;margin:0;letter-spacing:-.01em}
.csrc{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:3px;letter-spacing:.02em}
.cval{font-family:var(--mono);font-size:20px;font-weight:600;text-align:right;white-space:nowrap;
  font-variant-numeric:tabular-nums;color:var(--accent)}
.cvl{display:block;font-size:10px;font-weight:400;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.plot{position:relative;margin-top:8px}
.chart{width:100%;height:auto;display:block;touch-action:none}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 3;opacity:.6}
.chart .rec{fill:var(--rec)}
.chart .line{fill:none;stroke:var(--accent);stroke-width:1.6;stroke-linejoin:round;
  vector-effect:non-scaling-stroke}
.chart .line-div{stroke:var(--muted);stroke-width:1.2}
.chart .area{fill:var(--accent);opacity:.12}
.chart .dot{fill:var(--accent);stroke:var(--surface);stroke-width:1.5}
.chart .ylab{fill:var(--muted);font-family:var(--mono);font-size:10px;text-anchor:end;font-variant-numeric:tabular-nums}
.chart .xlab{fill:var(--muted);font-family:var(--mono);font-size:10px;text-anchor:middle}
.chart .cross{stroke:var(--ink);stroke-width:1;opacity:.35;pointer-events:none}
.chart .hdot{fill:var(--ink);stroke:var(--surface);stroke-width:1.5;pointer-events:none}
.tip{position:absolute;top:-2px;transform:translateX(-50%);background:var(--ink);color:var(--bg);
  font-family:var(--mono);font-size:11px;padding:3px 7px;border-radius:6px;pointer-events:none;
  opacity:0;transition:opacity .1s;white-space:nowrap;font-variant-numeric:tabular-nums;z-index:2}
.tip b{font-weight:600;margin-right:6px}.tip span{opacity:.7}
.foot{margin-top:34px;padding-top:20px;border-top:1px solid var(--edge);color:var(--muted);
  font-size:13.5px;max-width:80ch}
.foot b{color:var(--ink);font-weight:600}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

BODY = r"""
<div class="wrap">
<header>
  <div class="eyebrow">Alternate Histories &middot; Data Layer &middot; Point-in-time vintage <b>__VINTAGE__</b></div>
  <h1>A century and a half of the tape</h1>
  <p class="dek">The first real data vintage &mdash; public macro-financial series pulled live from FRED, Ken&nbsp;French, Shiller, the BIS and the Jord&agrave;&ndash;Schularick&ndash;Taylor Macrohistory database, QC-validated and stored immutably. NBER recessions are shaded from the recorded <span class="mono">USREC</span> series.</p>
  <div class="stats">
    <div class="stat"><div class="num">__NSERIES__</div><div class="lab">series</div></div>
    <div class="stat"><div class="num">__NOBS__</div><div class="lab">observations</div></div>
    <div class="stat"><div class="num">1854&ndash;2026</div><div class="lab">span</div></div>
    <div class="stat"><div class="num">5</div><div class="lab">public sources</div></div>
  </div>
</header>
<main id="grid" class="grid"></main>
<footer class="foot">
  <p><b>Real, not synthetic.</b> Every point was downloaded and validated through the platform's QC gate (bounds, monotonic dates, frequency, staleness, cross-series identities) and written to the immutable vintage <span class="mono">__VINTAGE__</span>. French factors are net total-market returns compounded from 1926; CAPE is Shiller's cyclically-adjusted P/E; the credit-to-GDP gap is the BIS one-sided HP-filter gap for US private non-financial credit.</p>
</footer>
</div>
<script id="payload" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('payload').textContent);
const CHARTS=[
 {k:'gs10',t:'10-Year Treasury Yield',src:'FRED · GS10 · 1953–2026',unit:'%',dec:2,rec:true},
 {k:'spread',t:'Baa–Aaa Credit Spread',src:"FRED · Moody's · 1919–2026",unit:'%',dec:2,rec:true},
 {k:'cpi_yoy',t:'CPI Inflation · year-over-year',src:'FRED · CPIAUCNS · 1914–2026',unit:'%',dec:1,rec:true,zero:true},
 {k:'cape',t:'Shiller CAPE',src:'Shiller · 1881–2024',unit:'×',dec:1,rec:false},
 {k:'credit_gap',t:'US Credit-to-GDP Gap',src:'BIS · 1957–2025',unit:' ppt',dec:1,rec:false,diverging:true,zero:true},
 {k:'equity_cum',t:'US Equity · Growth of $1',src:'Fama–French total market · 1926–2026',unit:'',dec:0,log:true,rec:true,prefix:'$'},
];
const fmt=(v,c)=>(c.prefix||'')+(c.log?Math.round(v).toLocaleString():v.toFixed(c.dec))+(c.unit||'');
function ticks(min,max,n){const span=(max-min)||1,s0=span/n,mag=Math.pow(10,Math.floor(Math.log10(s0))),nm=s0/mag;
 const step=(nm<1.5?1:nm<3?2:nm<7?5:10)*mag;const t=[];for(let x=Math.ceil(min/step)*step;x<=max+1e-9;x+=step)t.push(x);return t;}
function draw(card,c){
 const S=D[c.k],xs=S.t,ys=S.v,W=560,H=300,pl=52,pr=14,pt=14,pb=26;
 const xmin=xs[0],xmax=xs[xs.length-1];const lg=v=>c.log?Math.log10(Math.max(v,1e-9)):v;
 let ymin=Math.min(...ys),ymax=Math.max(...ys);
 if(c.log){ymin=0;ymax=Math.ceil(Math.log10(ymax));}else{const p=(ymax-ymin)*0.08||1;ymin-=p;ymax+=p;if(c.zero){ymin=Math.min(ymin,0);ymax=Math.max(ymax,0);}}
 const X=x=>pl+(x-xmin)/(xmax-xmin)*(W-pl-pr);
 const Y=v=>pt+(1-(lg(v)-ymin)/(ymax-ymin))*(H-pt-pb);
 const NS='http://www.w3.org/2000/svg';
 const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;};
 const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,class:'chart',preserveAspectRatio:'none'});
 if(c.rec)D.recessions.forEach(([s,e])=>{if(e<xmin||s>xmax)return;const x0=X(Math.max(s,xmin)),x1=X(Math.min(e,xmax));
   svg.appendChild(el('rect',{x:x0,y:pt,width:Math.max(1,x1-x0),height:H-pt-pb,class:'rec'}));});
 const yt=c.log?[0,1,2,3,4].filter(t=>t>=ymin&&t<=ymax):ticks(ymin,ymax,4);
 yt.forEach(t=>{const rv=c.log?Math.pow(10,t):t,y=Y(rv);
   svg.appendChild(el('line',{x1:pl,y1:y,x2:W-pr,y2:y,class:(c.zero&&Math.abs(rv)<1e-9)?'zero':'grid'}));
   const lab=el('text',{x:pl-7,y:y+3,class:'ylab'});
   lab.textContent=c.log?('$'+Math.pow(10,t).toLocaleString()):(Math.abs(t)<10?t.toFixed(1):Math.round(t));svg.appendChild(lab);});
 ticks(Math.ceil(xmin),Math.floor(xmax),5).forEach(yr=>{const lab=el('text',{x:X(yr),y:H-8,class:'xlab'});lab.textContent=Math.round(yr);svg.appendChild(lab);});
 if(c.diverging){const y0=Y(0);let dp=`M ${X(xs[0])} ${y0}`;xs.forEach((x,i)=>dp+=` L ${X(x)} ${Y(ys[i])}`);dp+=` L ${X(xs[xs.length-1])} ${y0} Z`;
   svg.appendChild(el('path',{d:dp,class:'area'}));}
 let d='';xs.forEach((x,i)=>{d+=(i?' L ':'M ')+X(x).toFixed(1)+' '+Y(ys[i]).toFixed(1);});
 svg.appendChild(el('path',{d,class:'line'+(c.diverging?' line-div':'')}));
 svg.appendChild(el('circle',{cx:X(xs[xs.length-1]),cy:Y(ys[ys.length-1]),r:3.5,class:'dot'}));
 const cross=el('line',{class:'cross',x1:0,y1:pt,x2:0,y2:H-pb,style:'opacity:0'});svg.appendChild(cross);
 const hdot=el('circle',{r:4,class:'hdot',style:'opacity:0'});svg.appendChild(hdot);
 const tip=card.querySelector('.tip');
 svg.addEventListener('pointermove',ev=>{const r=svg.getBoundingClientRect();const px=(ev.clientX-r.left)/r.width*W;
   const yr=xmin+(px-pl)/(W-pl-pr)*(xmax-xmin);let lo=0,hi=xs.length-1;
   while(hi-lo>1){const m=(lo+hi)>>1;if(xs[m]<yr)lo=m;else hi=m;}
   const i=(yr-xs[lo]<xs[hi]-yr)?lo:hi,gx=X(xs[i]),gy=Y(ys[i]);
   cross.setAttribute('x1',gx);cross.setAttribute('x2',gx);cross.style.opacity=1;
   hdot.setAttribute('cx',gx);hdot.setAttribute('cy',gy);hdot.style.opacity=1;
   const y2=Math.floor(xs[i]),mo=Math.round((xs[i]-y2)*12)+1;
   tip.innerHTML=`<b>${fmt(ys[i],c)}</b><span>${y2}·${String(mo).padStart(2,'0')}</span>`;
   tip.style.opacity=1;tip.style.left=Math.min(Math.max(gx/W*r.width,44),r.width-44)+'px';});
 svg.addEventListener('pointerleave',()=>{cross.style.opacity=0;hdot.style.opacity=0;tip.style.opacity=0;});
 card.querySelector('.plot').appendChild(svg);
}
const grid=document.getElementById('grid');
CHARTS.forEach(c=>{const S=D[c.k],last=S.v[S.v.length-1];const card=document.createElement('figure');card.className='card';
 card.innerHTML=`<figcaption><div class="ct"><h2>${c.t}</h2><div class="csrc">${c.src}</div></div>`+
   `<div class="cval">${fmt(last,c)}<span class="cvl">latest</span></div></figcaption>`+
   `<div class="plot"><div class="tip"></div></div>`;
 grid.appendChild(card);draw(card,c);});
</script>
"""

page = f"<style>{CSS}</style>\n<title>Data vintage {META['vintage']}</title>\n" + (
    BODY.replace("__DATA__", DATA)
    .replace("__VINTAGE__", META["vintage"])
    .replace("__NSERIES__", str(META["n_series"]))
    .replace("__NOBS__", f"{META['n_obs']:,}")
)
Path(sys.argv[1]).write_text(page, encoding="utf-8")
print("wrote", sys.argv[1], len(page), "bytes")
