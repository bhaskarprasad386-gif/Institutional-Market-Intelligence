import type {LmeObservation,LmeMetric} from "./types";
const groupKey=(row:LmeObservation)=>row.metal+"|"+(row.warehouseRegion?.trim().toUpperCase()??"UNSPECIFIED");
export interface LmeSignalThresholds {inventoryMovePct:number;cancelledWarrantSpikePct:number;}\nexport const DEFAULT_LME_SIGNAL_THRESHOLDS:LmeSignalThresholds={inventoryMovePct:5,cancelledWarrantSpikePct:35};\nexport function calculateLmeMetrics(rows:LmeObservation[],thresholds:LmeSignalThresholds=DEFAULT_LME_SIGNAL_THRESHOLDS):LmeMetric[]{
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
  const inventoryStatus:LmeMetric["inventoryStatus"]=dayChange===undefined?"INSUFFICIENT_HISTORY":dayChange>0?"BUILD":dayChange<0?"DRAW":"FLAT";\n  const inventorySignal:LmeMetric["inventorySignal"]=dayChangePct===undefined?"INSUFFICIENT_HISTORY":dayChangePct<=-Math.abs(thresholds.inventoryMovePct)?"STOCK_DROP":dayChangePct>=Math.abs(thresholds.inventoryMovePct)?"STOCK_INFLOW":"NORMAL";\n  const cwPct=row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined;\n  const cwChange=previous?.cancelledWarrantsTonnes!==undefined&&row.cancelledWarrantsTonnes!==undefined?row.cancelledWarrantsTonnes-previous.cancelledWarrantsTonnes:undefined;\n  const cancelledWarrantSignal:LmeMetric["cancelledWarrantSignal"]=cwPct===undefined?"INSUFFICIENT_DATA":cwPct>=thresholds.cancelledWarrantSpikePct?"CW_SPIKE":cwChange!==undefined&&cwChange<0?"CW_DECLINE_POSSIBLE_REWARRANTING":"NORMAL";\n  const cash3mSpread=row.cashPrice!==undefined&&row.threeMonthPrice!==undefined?row.cashPrice-row.threeMonthPrice:undefined;\n  const cash3mSpreadPct=cash3mSpread!==undefined&&row.threeMonthPrice!>0?cash3mSpread/row.threeMonthPrice!*100:undefined;\n  const cash3mStructure:LmeMetric["cash3mStructure"]=cash3mSpread===undefined?"INSUFFICIENT_DATA":cash3mSpread>0?"BACKWARDATION":cash3mSpread<0?"CONTANGO":"FLAT";
  previousByGroup.set(key,row);
  return {...row,dailyChangeTonnes:dayChange,dailyChangePct:dayChangePct,inventorySignal,cancelledWarrantSignal,cash3mSpread,cash3mSpreadPct,cash3mStructure,onWarrantPct:row.onWarrantTonnes!==undefined&&row.totalInventoryTonnes>0?row.onWarrantTonnes/row.totalInventoryTonnes*100:undefined,cancelledWarrantPct:row.cancelledWarrantsTonnes!==undefined&&row.totalInventoryTonnes>0?row.cancelledWarrantsTonnes/row.totalInventoryTonnes*100:undefined,impliedWithdrawalsTonnes:dayChange!==undefined&&dayChange<0?Math.abs(dayChange):undefined,balanceExpectedClosingTonnes:expected,balanceVarianceTonnes:variance,balanceStatus,inventoryStatus};
 });
}
