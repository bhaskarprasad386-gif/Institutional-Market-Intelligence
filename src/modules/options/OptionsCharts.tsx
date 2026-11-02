import { useMemo, useState } from "react";
import type { OptionMetric } from "./types";

type Props = { rows: OptionMetric[] };
type Point = { strike:number; ce:number; pe:number };

function BarChart({title,subtitle,points,format}:{title:string;subtitle:string;points:Point[];format:(v:number)=>string}) {
 const width=760,height=300,left=64,right=18,top=22,bottom=52,plotW=width-left-right,plotH=height-top-bottom;
 const max=Math.max(1,...points.flatMap(p=>[p.ce,p.pe]));
 const step=plotW/Math.max(1,points.length),barW=Math.min(18,step*0.32);
 const ticks=4;
 return <div className="option-chart-card">
  <h3>{title}</h3><p className="muted">{subtitle}</p>
  {points.length===0?<p className="muted">इस chart के लिए पर्याप्त imported data नहीं है।</p>:<div className="option-chart-scroll"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
   {Array.from({length:ticks+1},(_,i)=>{const y=top+plotH*i/ticks,value=max*(1-i/ticks);return <g key={i}><line x1={left} x2={width-right} y1={y} y2={y} stroke="#40516a" strokeDasharray="4 4"/><text x={left-9} y={y+4} fill="#c2cfdf" fontSize="10" textAnchor="end">{format(value)}</text></g>;})}
   <line x1={left} x2={left} y1={top} y2={top+plotH} stroke="#8fa3ba"/><line x1={left} x2={width-right} y1={top+plotH} y2={top+plotH} stroke="#8fa3ba"/>
   {points.map((p,i)=>{const center=left+step*(i+0.5),ceH=p.ce/max*plotH,peH=p.pe/max*plotH;return <g key={p.strike}>
    <rect x={center-barW-1} y={top+plotH-ceH} width={barW} height={ceH} rx="2" fill="#36a3a5"><title>{`CE ${p.strike}: ${format(p.ce)}`}</title></rect>
    <rect x={center+1} y={top+plotH-peH} width={barW} height={peH} rx="2" fill="#df9a43"><title>{`PE ${p.strike}: ${format(p.pe)}`}</title></rect>
    {(points.length<=18||i%Math.ceil(points.length/18)===0)&&<text x={center} y={top+plotH+19} fill="#d2deec" fontSize="10" textAnchor="middle">{p.strike}</text>}
   </g>;})}
   <g transform={`translate(${width/2-64},${height-9})`}><rect width="10" height="10" fill="#36a3a5"/><text x="15" y="9" fill="#e7edf6" fontSize="11">CE</text><rect x="55" width="10" height="10" fill="#df9a43"/><text x="70" y="9" fill="#e7edf6" fontSize="11">PE</text></g>
  </svg></div>}
 </div>;
}

export default function OptionsCharts({rows}:Props) {
 const keys=useMemo(()=>[...new Set(rows.map(r=>r.underlying+"|"+r.expiryDate))].sort(),[rows]);
 const [selected,setSelected]=useState("");
 const active=keys.includes(selected)?selected:(keys[0]??"");
 const scoped=useMemo(()=>rows.filter(r=>r.underlying+"|"+r.expiryDate===active),[rows,active]);
 const points=useMemo(()=>{
  const map=new Map<number,Point>();
  for(const r of scoped){const p=map.get(r.strike)??{strike:r.strike,ce:0,pe:0};if(r.optionType==="CE")p.ce+=r.openInterest;else p.pe+=r.openInterest;map.set(r.strike,p);}
  return [...map.values()].sort((a,b)=>a.strike-b.strike);
 },[scoped]);
 const ivPoints=useMemo(()=>{
  const map=new Map<number,Point>();
  for(const r of scoped){const p=map.get(r.strike)??{strike:r.strike,ce:0,pe:0};if(r.ivPct!==undefined){if(r.optionType==="CE")p.ce=r.ivPct;else p.pe=r.ivPct;}map.set(r.strike,p);}
  return [...map.values()].sort((a,b)=>a.strike-b.strike).filter(p=>p.ce>0||p.pe>0);
 },[scoped]);
 if(!rows.length)return null;
 return <div className="option-charts">
  <div className="option-chart-toolbar"><div><h3>Option Chain Charts</h3><p className="muted">Selected imported underlying and expiry · CE vs PE distribution</p></div><label>Underlying / expiry<select value={active} onChange={e=>setSelected(e.target.value)}>{keys.map(k=><option key={k} value={k}>{k.replace("|"," · ")}</option>)}</select></label></div>
  <div className="option-chart-grid">
   <BarChart title="Open Interest by Strike" subtitle="Contract OI distribution · CE vs PE" points={points} format={v=>v>=1000000?(v/1000000).toFixed(1)+"M":v>=1000?(v/1000).toFixed(0)+"k":Math.round(v).toString()}/>
   <BarChart title="Implied Volatility by Strike" subtitle="IV percentage · missing values omitted" points={ivPoints} format={v=>v.toFixed(1)+"%"}/>
  </div>
 </div>;
}
