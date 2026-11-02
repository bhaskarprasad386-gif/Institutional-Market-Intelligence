import {useMemo} from "react";
import type {LmeMetric} from "./types";
function sumWhenComplete(rows:LmeMetric[],field:"productionTonnes"|"importsTonnes"|"exportsTonnes"):number|undefined {
 return rows.length>0&&rows.every(row=>row[field]!==undefined)?rows.reduce((sum,row)=>sum+(row[field]??0),0):undefined;
}
export default function LmeSummary({rows}:{rows:LmeMetric[]}){
 const summaries=useMemo(()=>{
  const metals=[...new Set(rows.map(row=>row.metal))];
  return metals.map(metal=>{
   const all=rows.filter(row=>row.metal===metal),date=all.reduce((latest,row)=>row.reportDate>latest?row.reportDate:latest,"");
   const latest=all.filter(row=>row.reportDate===date),stock=latest.reduce((sum,row)=>sum+row.totalInventoryTonnes,0);
   const complete=(field:"onWarrantTonnes"|"cancelledWarrantsTonnes"|"dailyChangeTonnes")=>latest.length>0&&latest.every(row=>row[field]!==undefined);
   const live=complete("onWarrantTonnes")?latest.reduce((sum,row)=>sum+(row.onWarrantTonnes??0),0):undefined;
   const cancelled=complete("cancelledWarrantsTonnes")?latest.reduce((sum,row)=>sum+(row.cancelledWarrantsTonnes??0),0):undefined;
   return {metal,date,regions:latest.length,stock,change:complete("dailyChangeTonnes")?latest.reduce((sum,row)=>sum+(row.dailyChangeTonnes??0),0):undefined,
    livePct:live!==undefined&&stock>0?live/stock*100:undefined,cancelledPct:cancelled!==undefined&&stock>0?cancelled/stock*100:undefined,
    production:sumWhenComplete(latest,"productionTonnes"),imports:sumWhenComplete(latest,"importsTonnes"),exports:sumWhenComplete(latest,"exportsTonnes")};
  }).sort((a,b)=>a.metal.localeCompare(b.metal));
 },[rows]);
 if(!rows.length)return null;
 return <div className="table-wrap"><table><thead><tr><th>Metal</th><th>Latest date</th><th>Warehouse rows</th><th>Total stock t</th><th>Daily change t</th><th>Live warrant %</th><th>Cancelled warrant %</th><th>Production t</th><th>Imports t</th><th>Exports t</th></tr></thead><tbody>{summaries.map(row=><tr key={row.metal}><td><strong>{row.metal}</strong></td><td>{row.date}</td><td>{row.regions}</td><td>{row.stock.toLocaleString()}</td><td>{row.change?.toLocaleString()??"—"}</td><td>{row.livePct?.toFixed(2)??"—"}</td><td>{row.cancelledPct?.toFixed(2)??"—"}</td><td>{row.production?.toLocaleString()??"—"}</td><td>{row.imports?.toLocaleString()??"—"}</td><td>{row.exports?.toLocaleString()??"—"}</td></tr>)}</tbody></table></div>;
}
