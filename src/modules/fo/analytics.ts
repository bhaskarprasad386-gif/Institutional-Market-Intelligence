import type { FuturesObservation, FoMetrics, RolloverMetric } from "./types";
const DAY_MS=86400000;
export function calculateFoMetrics(row:FuturesObservation):FoMetrics {
  const trade=Date.parse(row.tradeDate+"T00:00:00Z"),expiry=Date.parse(row.expiryDate+"T00:00:00Z");
  if(!Number.isFinite(trade)||!Number.isFinite(expiry)||expiry<trade)throw new Error("Invalid trade date or expiry date.");
  if(!row.symbol.trim()||row.futuresClose<=0||row.spotClose<=0||row.openInterest<0)throw new Error("Symbol, prices and open interest must be valid.");
  const daysToExpiry=Math.max(0,Math.ceil((expiry-trade)/DAY_MS));
  const basis=row.futuresClose-row.spotClose;
  const costOfCarryAnnualizedPct=daysToExpiry>0?((row.futuresClose/row.spotClose)-1)*365/daysToExpiry*100:undefined;
  const oiChange=row.previousOpenInterest===undefined?undefined:row.openInterest-row.previousOpenInterest;
  const oiChangePct=row.previousOpenInterest && row.previousOpenInterest>0 && oiChange!==undefined?oiChange/row.previousOpenInterest*100:undefined;
  return {symbol:row.symbol,tradeDate:row.tradeDate,expiryDate:row.expiryDate,futuresClose:row.futuresClose,spotClose:row.spotClose,openInterest:row.openInterest,oiChange,oiChangePct,priceChangePct:undefined,basis,costOfCarryAnnualizedPct,daysToExpiry};
}
/** Rollover share is next-expiry OI / (near-expiry OI + next-expiry OI). */
export function calculateRolloverPct(symbol:string,tradeDate:string,nearExpiry:string,nextExpiry:string,nearOi:number,nextOi:number):RolloverMetric {
  if(nearOi<0||nextOi<0||nearOi+nextOi<=0)throw new Error("Near and next expiry OI must be non-negative and total OI must be positive.");
  return {symbol,tradeDate,nearExpiry,nextExpiry,nearOi,nextOi,rolloverPct:nextOi/(nearOi+nextOi)*100};
}
export function classifyPriceOi(priceChangePct:number,oiChangePct:number):"long_build_up"|"short_build_up"|"short_covering"|"long_unwinding"|"mixed" {
  if(priceChangePct>0&&oiChangePct>0)return "long_build_up";
  if(priceChangePct<0&&oiChangePct>0)return "short_build_up";
  if(priceChangePct>0&&oiChangePct<0)return "short_covering";
  if(priceChangePct<0&&oiChangePct<0)return "long_unwinding";
  return "mixed";
}
