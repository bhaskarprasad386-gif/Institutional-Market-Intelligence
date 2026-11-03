import type { FuturesObservation, FoMetrics, RolloverMetric, RolloverFlag } from "./types";
const DAY_MS=86400000;
export function calculateFoMetrics(row:FuturesObservation):FoMetrics {
  const trade=Date.parse(row.tradeDate+"T00:00:00Z"),expiry=Date.parse(row.expiryDate+"T00:00:00Z");
  if(!Number.isFinite(trade)||!Number.isFinite(expiry)||expiry<trade)throw new Error("Invalid trade date or expiry date.");
  if(!row.symbol.trim()||row.futuresClose<=0||row.spotClose<=0||row.openInterest<0)throw new Error("Symbol, prices and open interest must be valid.");
  const daysToExpiry=Math.max(0,Math.ceil((expiry-trade)/DAY_MS));
  const basis=row.futuresClose-row.spotClose;
  const costOfCarryAnnualizedPct=daysToExpiry>0?((row.futuresClose/row.spotClose)-1)*365/daysToExpiry*100:undefined;
  const oiChange=row.previousOpenInterest===undefined?undefined:row.openInterest-row.previousOpenInterest;
  const priceChangePct=row.previousFuturesClose!==undefined&&row.previousFuturesClose>0?(row.futuresClose/row.previousFuturesClose-1)*100:undefined;
  const oiChangePct=row.previousOpenInterest!==undefined&&row.previousOpenInterest>0&&oiChange!==undefined?oiChange/row.previousOpenInterest*100:undefined;
  return {symbol:row.symbol,tradeDate:row.tradeDate,expiryDate:row.expiryDate,futuresClose:row.futuresClose,spotClose:row.spotClose,openInterest:row.openInterest,oiChange,oiChangePct,priceChangePct,basis,costOfCarryAnnualizedPct,daysToExpiry};
}
export function calculateRolloverPct(symbol:string,tradeDate:string,nearExpiry:string,nextExpiry:string,nearOi:number,nextOi:number):RolloverMetric {
  if(nearOi<0||nextOi<0||nearOi+nextOi<=0)throw new Error("Near and next expiry OI must be non-negative and total OI must be positive.");
  return {symbol,tradeDate,nearExpiry,nextExpiry,nearOi,nextOi,rolloverPct:nextOi/(nearOi+nextOi)*100,nearFuturesClose:0,nextFuturesClose:0,rolloverCostPoints:0,rolloverCostPct:0,rolloverPctFlag:"INSUFFICIENT_PEERS",rolloverCostFlag:"INSUFFICIENT_PEERS",peerCount:0};
}
export function classifyPriceOi(priceChangePct:number,oiChangePct:number):"long_build_up"|"short_build_up"|"short_covering"|"long_unwinding"|"mixed" {
  if(priceChangePct>0&&oiChangePct>0)return "long_build_up";
  if(priceChangePct<0&&oiChangePct>0)return "short_build_up";
  if(priceChangePct>0&&oiChangePct<0)return "short_covering";
  if(priceChangePct<0&&oiChangePct<0)return "long_unwinding";
  return "mixed";
}
function percentile75(values:number[]):number|undefined {
  if(!values.length)return undefined;
  const sorted=[...values].sort((a,b)=>a-b);
  return sorted[Math.ceil(0.75*sorted.length)-1];
}
/** Compare only same-session symbols; fewer than five peers is not enough to label a high reading. */
export function calculateRolloverFromRows(rows:FuturesObservation[]):RolloverMetric[] {
  const grouped=new Map<string,Map<string,{oi:number;weightedPrice:number;priceWeight:number;lotSizes:number[]}>>();
  for(const row of rows){
    if(row.expiryDate<row.tradeDate)continue;
    const key=row.symbol+"|"+row.tradeDate;
    const expiries=grouped.get(key)??new Map();
    const current=expiries.get(row.expiryDate)??{oi:0,weightedPrice:0,priceWeight:0,lotSizes:[]};
    current.oi+=row.openInterest;
    if(row.openInterest>0){current.weightedPrice+=row.futuresClose*row.openInterest;current.priceWeight+=row.openInterest;}
    if(row.lotSize&&row.lotSize>0)current.lotSizes.push(row.lotSize);
    expiries.set(row.expiryDate,current);grouped.set(key,expiries);
  }
  const draft:RolloverMetric[]=[];
  for(const [key,expiries] of grouped){
    const ordered=[...expiries.entries()].sort(([a],[b])=>a.localeCompare(b));
    if(ordered.length<2)continue;
    const [nearExpiry,near]=ordered[0], [nextExpiry,next]=ordered[1];
    if(near.oi+next.oi<=0||near.priceWeight<=0||next.priceWeight<=0)continue;
    const [symbol,tradeDate]=key.split("|");
    const nearFuturesClose=near.weightedPrice/near.priceWeight,nextFuturesClose=next.weightedPrice/next.priceWeight;
    const rolloverCostPoints=nextFuturesClose-nearFuturesClose;
    const rolloverCostPct=rolloverCostPoints/nearFuturesClose*100;
    const lotSize=near.lotSizes.length&&next.lotSizes.length&&near.lotSizes[0]===next.lotSizes[0]?near.lotSizes[0]:undefined;
    draft.push({...calculateRolloverPct(symbol,tradeDate,nearExpiry,nextExpiry,near.oi,next.oi),nearFuturesClose,nextFuturesClose,rolloverCostPoints,rolloverCostPct,lotSize,rolloverCostPerLot:lotSize===undefined?undefined:rolloverCostPoints*lotSize});
  }
  const byDate=new Map<string,RolloverMetric[]>();
  for(const row of draft){const group=byDate.get(row.tradeDate)??[];group.push(row);byDate.set(row.tradeDate,group);}
  const result:RolloverMetric[]=[];
  for(const group of byDate.values()){
    const pctCutoff=group.length>=5?percentile75(group.map(row=>row.rolloverPct)):undefined;
    const positiveCosts=group.filter(row=>row.rolloverCostPct>0);
    const costCutoff=positiveCosts.length>=5?percentile75(positiveCosts.map(row=>row.rolloverCostPct)):undefined;
    for(const row of group){
      const enough=group.length>=5;
      const rolloverPctFlag:RolloverFlag=!enough?"INSUFFICIENT_PEERS":row.rolloverPct>=pctCutoff!?"HIGH":"NORMAL";
      const rolloverCostFlag:RolloverFlag=row.rolloverCostPct<0?"ROLL_CREDIT":!enough||positiveCosts.length<5?"INSUFFICIENT_PEERS":row.rolloverCostPct>=costCutoff!?"HIGH":"NORMAL";
      result.push({...row,rolloverPctFlag,rolloverCostFlag,peerCount:group.length});
    }
  }
  return result.sort((a,b)=>a.tradeDate.localeCompare(b.tradeDate)||b.rolloverPct-a.rolloverPct);
}
