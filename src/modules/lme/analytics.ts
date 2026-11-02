import type {LmeObservation,LmeMetric} from "./types";
const groupKey=(row:LmeObservation)=>(row.exchange??"LME")+"|"+row.metal+"|"+(row.warehouseRegion?.trim().toUpperCase()??"UNSPECIFIED");
export interface LmeSignalThresholds {inventoryMovePct:number;cancelledWarrantSpikePct:number;}
export const DEFAULT_LME_SIGNAL_THRESHOLDS:LmeSignalThresholds={inventoryMovePct:5,cancelledWarrantSpikePct:35};
export function calculateLmeMetrics(rows:LmeObservation[],thresholds:LmeSignalThresholds=DEFAULT_LME_SIGNAL_THRESHOLDS):LmeMetric[]{
 const sorted=[...rows].sort((a,b)=>groupKey(a).localeCompare(groupKey(b))||a.reportDate.localeCompare(b.reportDate));
 const previousByGroup=new Map<string,LmeObservation>();
 const spreadHistory=new Map<string,{date:string;spread:number}[]>();
 return sorted.map(row=>{
  const key=groupKey(row),previous=previousByGroup.get(key);
  const dayChange=row.dailyChangeTonnes??(previous?row.totalInventoryTonnes-previous.totalInventoryTonnes:undefined);
  const dayChangePct=previous&&previous.totalInventoryTonnes>0&&dayChange!==undefined?dayChange/previous.totalInventoryTonnes*100:undefined;
  const inputs=row.openingStockTonnes!==undefined&&row.deliveredInTonnes!==undefined&&row.deliveredOutTonnes!==undefined;
  const expected=inputs?row.openingStockTonnes!+row.deliveredInTonnes!-row.deliveredOutTonnes!:undefined;
  const variance=expected!==undefined?row.totalInventoryTonnes-expected:undefined;
  const balanceStatus:LmeMetric["balanceStatus"]=variance===undefined?"INSUFFICIENT_DATA":Math.abs(variance)<=Math.max(1,row.totalInventoryTonnes*0.000001)?"RECONCILED":"VARIANCE";
  const inventoryStatus:LmeMetric["inventoryStatus"]=dayChange===undefined?"INSUFFICIENT_HISTORY":dayChange>0?"BUILD":dayChange<0?"DRAW":"FLAT";
  const onChange=previous?.onWarrantTonnes!==undefined&&row.onWarrantTonnes!==undefined?row.onWarrantTonnes-previous.onWarrantTonnes:undefined;
  const offChange=previous?.offWarrantTonnes!==undefined&&row.offWarrantTonnes!==undefined?row.offWarrantTonnes-previous.offWarrantTonnes:undefined;
  const dualDrain=onChange!==undefined&&offChange!==undefined&&onChange<0&&offChange<0;
  const inventorySignal:LmeMetric["inventorySignal"]=dualDrain?"DUAL_STOCK_DRAIN":dayChangePct===undefined?"INSUFFICIENT_HISTORY":dayChangePct<=-Math.abs(thresholds.inventoryMovePct)?"STOCK_DROP":dayChangePct>=Math.abs(thresholds.inventoryMovePct)?"STOCK_INFLOW":"NORMAL";
  const cwPct=row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined;
  const cwChange=previous?.cancelledWarrantsTonnes!==undefined&&row.cancelledWarrantsTonnes!==undefined?row.cancelledWarrantsTonnes-previous.cancelledWarrantsTonnes:undefined;
  const cancelledWarrantSignal:LmeMetric["cancelledWarrantSignal"]=cwPct===undefined?"INSUFFICIENT_DATA":cwPct>=thresholds.cancelledWarrantSpikePct?"CW_SPIKE":cwChange!==undefined&&cwChange<0?"CW_DECLINE_POSSIBLE_REWARRANTING":"NORMAL";
  const cash3mSpread=row.cashPrice!==undefined&&row.threeMonthPrice!==undefined?row.cashPrice-row.threeMonthPrice:undefined;
  const priorSpreads=spreadHistory.get(key)??[];
  const spreadVelocity3Sessions=cash3mSpread!==undefined&&priorSpreads.length>=3?cash3mSpread-priorSpreads[priorSpreads.length-3].spread:undefined;
  const spreadVelocityFromDate=cash3mSpread!==undefined&&priorSpreads.length>=3?priorSpreads[priorSpreads.length-3].date:undefined;
  if(cash3mSpread!==undefined){priorSpreads.push({date:row.reportDate,spread:cash3mSpread});spreadHistory.set(key,priorSpreads.slice(-4));}
  const cash3mSpreadPct=cash3mSpread!==undefined&&row.threeMonthPrice!>0?cash3mSpread/row.threeMonthPrice!*100:undefined;
  const cash3mStructure:LmeMetric["cash3mStructure"]=cash3mSpread===undefined?"INSUFFICIENT_DATA":cash3mSpread>0?"BACKWARDATION":cash3mSpread<0?"CONTANGO":"FLAT";
  previousByGroup.set(key,row);
  return {...row,dailyChangeTonnes:dayChange,dailyChangePct:dayChangePct,offWarrantChangeTonnes:offChange,onWarrantChangeTonnes:onChange,spreadVelocity3Sessions,spreadVelocityFromDate,inventorySignal,cancelledWarrantSignal,cash3mSpread,cash3mSpreadPct,cash3mStructure,onWarrantPct:row.onWarrantTonnes!==undefined&&row.totalInventoryTonnes>0?row.onWarrantTonnes/row.totalInventoryTonnes*100:undefined,cancelledWarrantPct:row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined,impliedWithdrawalsTonnes:dayChange!==undefined&&dayChange<0?Math.abs(dayChange):undefined,balanceExpectedClosingTonnes:expected,balanceVarianceTonnes:variance,balanceStatus,inventoryStatus};
 });
}
