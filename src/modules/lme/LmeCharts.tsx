import {useMemo,useState} from "react";
import type {LmeMetric} from "./types";
type Point={date:string;inventory:number;live?:number;cancelled?:number;livePct?:number;cancelledPct?:number};
function LineChart({title,points,series}:{title:string;points:Point[];series:{key:"inventory"|"live"|"cancelled"|"livePct"|"cancelledPct";label:string;color:string}[]}){
 const width=760,height=260,left=66,right=20,top=20,bottom=42,plotW=width-left-right,plotH=height-top-bottom;
 const values=points.flatMap(p=>series.map(s=>p[s.key])).filter((v):v is number=>v!==undefined&&Number.isFinite(v));
 const max=Math.max(1,...values)*1.08;
 const x=(i:number)=>left+(points.length<=1?plotW/2:i*plotW/(points.length-1));
 const y=(v:number)=>top+plotH-(v/max)*plotH;
 return <div className="option-chart-card"><h3>{title}</h3>{!points.length?<p className="muted">इस metal के लिए पर्याप्त history उपलब्ध नहीं है।</p>:<div className="option-chart-scroll"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
 {Array.from({length:5},(_,i)=>{const val=max*(1-i/4),yy=y(val);return <g key={i}><line x1={left} x2={width-right} y1={yy} y2={yy} stroke="#40516a" strokeDasharray="4 4"/><text x={left-8} y={yy+4} fill="#c2cfdf" fontSize="10" textAnchor="end">{val.toLocaleString(undefined,{maximumFractionDigits:1})}</text></g>;})}
 {series.map(s=>{const coords=points.map((p,i)=>({x:x(i),y:p[s.key]===undefined?undefined:y(p[s.key]!)})).filter((p):p is {x:number;y:number}=>p.y!==undefined);const path=coords.map((p,i)=>(i?"L":"M")+p.x+","+p.y).join(" ");return <g key={s.key}><path d={path} fill="none" stroke={s.color} strokeWidth="2.5"/>{coords.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r="3" fill={s.color}/>)}</g>;})}
 {points.map((p,i)=>(points.length<=12||i%Math.ceil(points.length/12)===0)?<text key={p.date} x={x(i)} y={height-12} fill="#d2deec" fontSize="10" textAnchor="middle">{p.date.slice(5)}</text>:null)}
 </svg></div>}
 <div className="option-chart-legend">{series.map(s=><span key={s.key}><i style={{background:s.color}}/>{s.label}</span>)}</div></div>;
}
export default function LmeCharts({rows}:{rows:LmeMetric[]}){
 const metals=useMemo(()=>[...new Set(rows.map(r=>r.metal))].sort(),[rows]);const [selected,setSelected]=useState("");
 const active=metals.includes(selected)?selected:(metals[0]??"");
 const points=useMemo(()=>{const map=new Map<string,LmeMetric[]>();for(const row of rows.filter(r=>r.metal===active)){const group=map.get(row.reportDate)??[];group.push(row);map.set(row.reportDate,group);}
 return [...map.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([date,group])=>{const allLive=group.every(r=>r.onWarrantTonnes!==undefined),allCancelled=group.every(r=>r.cancelledWarrantsTonnes!==undefined);const total=group.reduce((n,r)=>n+r.totalInventoryTonnes,0),live=allLive?group.reduce((n,r)=>n+(r.onWarrantTonnes??0),0):undefined,cancelled=allCancelled?group.reduce((n,r)=>n+(r.cancelledWarrantsTonnes??0),0):undefined;return {date,inventory:total,live,cancelled,livePct:live!==undefined&&total>0?live/total*100:undefined,cancelledPct:cancelled!==undefined&&total>0?cancelled/total*100:undefined};});},[rows,active]);
 if(!rows.length)return null;
 return <div className="option-charts"><div className="option-chart-toolbar"><div><h3>LME Inventory Trends</h3><p className="muted">Daily history aggregated across imported warehouse regions; partial warrant series are omitted, not filled with zero.</p></div><label>Metal<select value={active} onChange={e=>setSelected(e.target.value)}>{metals.map(m=><option key={m} value={m}>{m}</option>)}</select></label></div><div className="option-chart-grid">
 <LineChart title="Total inventory and warrant tonnes" points={points} series={[{key:"inventory",label:"Total stock (t)",color:"#36a3a5"},{key:"live",label:"Live / on-warrant (t)",color:"#df9a43"},{key:"cancelled",label:"Cancelled warrants (t)",color:"#a78bfa"}]}/>
 <LineChart title="Warrant share of total stock" points={points} series={[{key:"livePct",label:"Live / on-warrant %",color:"#36a3a5"},{key:"cancelledPct",label:"Cancelled warrants %",color:"#df9a43"}]}/>
 </div></div>;
}
