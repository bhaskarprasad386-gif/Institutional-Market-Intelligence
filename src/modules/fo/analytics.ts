import type {FuturesObservation,FoMetrics,RolloverMetric,RolloverFlag,HistoricalRolloverContext} from "./types";
const DAY_MS=86400000;
export function calculateFoMetrics(row:FuturesObservation):FoMetrics {
 const trade=Date.parse(row.tradeDate+"T00:00:00Z"),expiry=Date.parse(row.expiryDate+"T00:00:00Z");
 if(!Number.isFinite(trade)||!Number.isFinite(expiry)||expiry<trade)throw new Error("Invalid trade date or expiry date.");
 if(!row.symbol.trim()||row.futuresClose<=0||row.spotClose<=0||row.openInterest<0)throw new Error("Symbol, prices and open interest must be valid.");
 const daysToExpiry=Math.max(0,Math.ceil((expiry-trade)/DAY_MS)),basis=row.futuresClose-row.spotClose;
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
export function classifyPriceOi(p:number,o:number):"long_build_up"|"short_build_up"|"short_covering"|"long_unwinding"|"mixed" {
 if(p>0&&o>0)return "long_build_up";if(p<0&&o>0)return "short_build_up";if(p>0&&o<0)return "short_covering";if(p<0&&o<0)return "long_unwinding";return "mixed";
}
function percentile75(v:number[]):number|undefined {if(!v.length)return undefined;const s=[...v].sort((a,b)=>a-b);return s[Math.ceil(.75*s.length)-1];}
export function calculateRolloverFromRows(rows:FuturesObservation[]):RolloverMetric[] {
 const grouped=new Map<string,Map<string,{oi:number;weightedPrice:number;priceWeight:number;lotSizes:number[]}>>();
 for(const row of rows){if(row.expiryDate<row.tradeDate)continue;const key=row.symbol+"|"+row.tradeDate,expiries=grouped.get(key)??new Map();
  const c=expiries.get(row.expiryDate)??{oi:0,weightedPrice:0,priceWeight:0,lotSizes:[]};c.oi+=row.openInterest;
  if(row.openInterest>0){c.weightedPrice+=row.futuresClose*row.openInterest;c.priceWeight+=row.openInterest;}
  if(row.lotSize&&row.lotSize>0)c.lotSizes.push(row.lotSize);expiries.set(row.expiryDate,c);grouped.set(key,expiries);
 }
 const draft:RolloverMetric[]=[];
 for(const [key,expiries] of grouped){const ordered=[...expiries.entries()].sort(([a],[b])=>a.localeCompare(b));if(ordered.length<2)continue;
  const [nearExpiry,near]=ordered[0],[nextExpiry,next]=ordered[1];if(near.oi+next.oi<=0||near.priceWeight<=0||next.priceWeight<=0)continue;
  const [symbol,tradeDate]=key.split("|"),nearFuturesClose=near.weightedPrice/near.priceWeight,nextFuturesClose=next.weightedPrice/next.priceWeight;
  const rolloverCostPoints=nextFuturesClose-nearFuturesClose,rolloverCostPct=rolloverCostPoints/nearFuturesClose*100;
  const nearLots=new Set(near.lotSizes),nextLots=new Set(next.lotSizes);
  const lotSize=nearLots.size===1&&nextLots.size===1&&[...nearLots][0]===[...nextLots][0]?[...nearLots][0]:undefined;
  draft.push({...calculateRolloverPct(symbol,tradeDate,nearExpiry,nextExpiry,near.oi,next.oi),nearFuturesClose,nextFuturesClose,rolloverCostPoints,rolloverCostPct,lotSize,rolloverCostPerLot:lotSize===undefined?undefined:rolloverCostPoints*lotSize});
 }
 const byDate=new Map<string,RolloverMetric[]>();for(const r of draft){const g=byDate.get(r.tradeDate)??[];g.push(r);byDate.set(r.tradeDate,g);}
 const result:RolloverMetric[]=[];
 for(const g of byDate.values()){const pc=g.length>=5?percentile75(g.map(r=>r.rolloverPct)):undefined,positive=g.filter(r=>r.rolloverCostPct>0),cc=positive.length>=5?percentile75(positive.map(r=>r.rolloverCostPct)):undefined;
  for(const r of g){const enough=g.length>=5,pctFlag:RolloverFlag=!enough?"INSUFFICIENT_PEERS":r.rolloverPct>=pc!?"HIGH":"NORMAL",costFlag:RolloverFlag=r.rolloverCostPct<0?"ROLL_CREDIT":!enough||positive.length<5?"INSUFFICIENT_PEERS":r.rolloverCostPct>=cc!?"HIGH":"NORMAL";result.push({...r,rolloverPctFlag:pctFlag,rolloverCostFlag:costFlag,peerCount:g.length});}
 }
 return result.sort((a,b)=>a.tradeDate.localeCompare(b.tradeDate)||b.rolloverPct-a.rolloverPct);
}
function median(v:number[]):number|undefined {if(!v.length)return undefined;const s=[...v].sort((a,b)=>a-b),m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;}
function rank(v:number,s:number[]):number {if(!s.length)return 0;const below=s.filter(x=>x<v).length,equal=s.filter(x=>x===v).length;return (below+equal/2)/s.length*100;}
function status(p:number,n:number):HistoricalRolloverContext["rolloverPctStatus"] {return n<5?"INSUFFICIENT_HISTORY":p>=80?"HIGH":p<=20?"LOW":"NORMAL";}
export function calculateHistoricalRolloverContextFromMetrics(current:RolloverMetric[],history:RolloverMetric[]):Map<string,HistoricalRolloverContext> {
 const bySymbol=new Map<string,RolloverMetric[]>();for(const item of history){const list=bySymbol.get(item.symbol)??[];list.push(item);bySymbol.set(item.symbol,list);}
 const out=new Map<string,HistoricalRolloverContext>();
 for(const row of current){const target=(Date.parse(row.nearExpiry+"T00:00:00Z")-Date.parse(row.tradeDate+"T00:00:00Z"))/DAY_MS,cycles=new Map<string,RolloverMetric>();
  for(const c of bySymbol.get(row.symbol)??[]){if(c.tradeDate>=row.tradeDate||(c.nearExpiry===row.nearExpiry&&c.nextExpiry===row.nextExpiry))continue;const key=c.nearExpiry+"|"+c.nextExpiry,dte=(Date.parse(c.nearExpiry+"T00:00:00Z")-Date.parse(c.tradeDate+"T00:00:00Z"))/DAY_MS,old=cycles.get(key);
   if(!old){cycles.set(key,c);continue;}const oldDte=(Date.parse(old.nearExpiry+"T00:00:00Z")-Date.parse(old.tradeDate+"T00:00:00Z"))/DAY_MS;
   if(Math.abs(dte-target)<Math.abs(oldDte-target)||(Math.abs(dte-target)===Math.abs(oldDte-target)&&c.tradeDate>old.tradeDate))cycles.set(key,c);
  }
  const samples=[...cycles.values()],pv=samples.map(x=>x.rolloverPct),cv=samples.map(x=>x.rolloverCostPct),pr=rank(row.rolloverPct,pv),cr=rank(row.rolloverCostPct,cv),n=samples.length;
  out.set(row.symbol+"|"+row.nearExpiry+"|"+row.nextExpiry,{sampleCount:n,rolloverPctMedian:median(pv),rolloverCostPctMedian:median(cv),rolloverPctPercentile:n>=5?pr:undefined,rolloverCostPctPercentile:n>=5?cr:undefined,rolloverPctStatus:status(pr,n),rolloverCostStatus:status(cr,n)});
 }
 return out;
}
export function calculateHistoricalRolloverContext(current:RolloverMetric[],historyRows:FuturesObservation[]):Map<string,HistoricalRolloverContext> {
 const byDate=new Map<string,FuturesObservation[]>();for(const r of historyRows){const a=byDate.get(r.tradeDate)??[];a.push(r);byDate.set(r.tradeDate,a);}
 return calculateHistoricalRolloverContextFromMetrics(current,[...byDate.values()].flatMap(calculateRolloverFromRows));
}

/**
 * Add point-in-time momentum using only observations dated on or before each
 * current row. A 3-session momentum needs the current observation plus the
 * observation three archived sessions earlier (four observations total).
 */
export function calculateRolloverMomentum(current:RolloverMetric[],history:RolloverMetric[]):RolloverMetric[] {
 const bySymbol=new Map<string,RolloverMetric[]>();
 for(const row of history){const list=bySymbol.get(row.symbol)??[];list.push(row);bySymbol.set(row.symbol,list);}
 for(const list of bySymbol.values())list.sort((a,b)=>a.tradeDate.localeCompare(b.tradeDate));
 return current.map(row=>{
  const prior=(bySymbol.get(row.symbol)??[]).filter(x=>x.tradeDate<=row.tradeDate&&x.tradeDate!==row.tradeDate);
  const series=[...prior.slice(-5),row];
  const nextShare=(x:RolloverMetric)=>x.nearOi+x.nextOi>0?x.nextOi/(x.nearOi+x.nextOi)*100:undefined;
  const calc=(sessions:number,field:"share"|"oi")=>{
   if(series.length<=sessions)return undefined;
   const old=series[series.length-1-sessions],now=series[series.length-1];
   if(field==="share"){const a=nextShare(old),b=nextShare(now);return a===undefined||b===undefined?undefined:b-a;}
   const a=old.totalOi??(old.nearOi+old.nextOi),b=now.totalOi??(now.nearOi+now.nextOi);
   return a>0?(b/a-1)*100:undefined;
  };
  return {...row,nextShareMomentum3d:calc(3,"share"),nextShareMomentum5d:calc(5,"share"),totalOiMomentum3dPct:calc(3,"oi"),totalOiMomentum5dPct:calc(5,"oi")};
 });
}
