import type {LmeObservation,LmeMetric} from "./types";
const groupKey=(row:LmeObservation)=>row.metal+"|"+(row.warehouseRegion?.trim().toUpperCase()??"UNSPECIFIED");
export function calculateLmeMetrics(rows:LmeObservation[]):LmeMetric[]{
 const sorted=[...rows].sort((a,b)=>groupKey(a).localeCompare(groupKey(b))||a.reportDate.localeCompare(b.reportDate));
 const previousByGroup=new Map<string,LmeObservation>();
 return sorted.map(row=>{
  const key=groupKey(row),previous=previousByGroup.get(key);
  const dayChange=row.dailyChangeTonnes??(previous?row.totalInventoryTonnes-previous.totalInventoryTonnes:undefined);
  const dayChangePct=previous&&previous.totalInventoryTonnes>0&&dayChange!==undefined?dayChange/previous.totalInventoryTonnes*100:undefined;
  const inputs=row.openingStockTonnes!==undefined&&row.deliveredInTonnes!==undefined&&row.deliveredOutTonnes!==undefined;
  const expected=inputs?row.openingStockTonnes!+row.deliveredInTonnes!-row.deliveredOutTonnes!:undefined;
  const variance=expected!==undefined?row.totalInventoryTonnes-expected:undefined;
  const balanceStatus:LmeMetric["balanceStatus"]=variance===undefined?"INSUFFICIENT_DATA":Math.abs(variance)<=Math.max(1,row.totalInventoryTonnes*0.000001)?"RECONCILED":"VARIANCE";
  const inventoryStatus:LmeMetric["inventoryStatus"]=dayChange===undefined?"INSUFFICIENT_HISTORY":dayChange>0?"BUILD":dayChange<0?"DRAW":"FLAT";
  previousByGroup.set(key,row);
  return {...row,dailyChangeTonnes:dayChange,dailyChangePct:dayChangePct,onWarrantPct:row.onWarrantTonnes!==undefined&&row.totalInventoryTonnes>0?row.onWarrantTonnes/row.totalInventoryTonnes*100:undefined,cancelledWarrantPct:row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined,impliedWithdrawalsTonnes:dayChange!==undefined&&dayChange<0?Math.abs(dayChange):undefined,balanceExpectedClosingTonnes:expected,balanceVarianceTonnes:variance,balanceStatus,inventoryStatus};
 });
}
