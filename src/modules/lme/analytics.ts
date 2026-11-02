import type {LmeObservation,LmeMetric} from "./types";
export function calculateLmeMetrics(rows:LmeObservation[]):LmeMetric[]{
 const sorted=[...rows].sort((a,b)=>a.metal.localeCompare(b.metal)||a.reportDate.localeCompare(b.reportDate));
 return sorted.map((row,index)=>{const previous=[...sorted.slice(0,index)].reverse().find(x=>x.metal===row.metal&&x.reportDate<row.reportDate);
 const dailyChangeTonnes=row.dailyChangeTonnes??(previous?row.totalInventoryTonnes-previous.totalInventoryTonnes:undefined);
 const dailyChangePct=previous&&previous.totalInventoryTonnes>0&&dailyChangeTonnes!==undefined?dailyChangeTonnes/previous.totalInventoryTonnes*100:undefined;
 const inventoryStatus:LmeMetric["inventoryStatus"]=dailyChangeTonnes===undefined?"INSUFFICIENT_HISTORY":dailyChangeTonnes>0?"BUILD":dailyChangeTonnes<0?"DRAW":"FLAT";
 return {...row,dailyChangeTonnes,dailyChangePct,onWarrantPct:row.onWarrantTonnes!==undefined&&row.totalInventoryTonnes>0?row.onWarrantTonnes/row.totalInventoryTonnes*100:undefined,cancelledWarrantPct:row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined,impliedWithdrawalsTonnes:dailyChangeTonnes!==undefined&&dailyChangeTonnes<0?Math.abs(dailyChangeTonnes):undefined,inventoryStatus};
 });
}
