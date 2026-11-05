export interface FuturesObservation {
  symbol:string; tradeDate:string; expiryDate:string; futuresClose:number; spotClose:number; openInterest:number;
  previousOpenInterest?:number; previousFuturesClose?:number; volume?:number; lotSize?:number;
}
export interface FoMetrics {
  symbol:string; tradeDate:string; expiryDate:string; futuresClose:number; spotClose:number; openInterest:number;
  oiChange?:number; oiChangePct?:number; priceChangePct?:number; basis:number; costOfCarryAnnualizedPct?:number; daysToExpiry:number;
}
export type RolloverFlag="HIGH"|"NORMAL"|"INSUFFICIENT_PEERS"|"ROLL_CREDIT";
export type BuildUpDirection="LONG_BUILD_UP"|"SHORT_BUILD_UP"|"SHORT_COVERING"|"LONG_UNWINDING"|"MIXED"|"INSUFFICIENT_DATA";
export interface RolloverMetric {
  symbol:string; tradeDate:string; nearExpiry:string; nextExpiry:string; nearOi:number; nextOi:number; rolloverPct:number;
  nearFuturesClose:number; nextFuturesClose:number; rolloverCostPoints:number; rolloverCostPct:number;
  farExpiry?:string|null; farOi?:number; totalOi?:number; nextFarOi?:number;
  extendedRolloverPct?:number; farSharePct?:number;
  nearOiChange?:number|null; nextOiChange?:number|null; farOiChange?:number|null; totalOiChange?:number|null;
  nearPriceChangePct?:number|null; nextPriceChangePct?:number|null;
  nearBuildUp?:BuildUpDirection; nextBuildUp?:BuildUpDirection;
  nearVolume?:number; nextVolume?:number; spotClose?:number|null;
  nextShareMomentum3d?:number|null; nextShareMomentum5d?:number|null;
  totalOiMomentum3dPct?:number|null; totalOiMomentum5dPct?:number|null;
  lotSize?:number; rolloverCostPerLot?:number; rolloverPctFlag:RolloverFlag; rolloverCostFlag:RolloverFlag; peerCount:number;
}
export interface HistoricalRolloverContext {
  sampleCount:number; rolloverPctMedian?:number; rolloverCostPctMedian?:number;
  rolloverPctPercentile?:number; rolloverCostPctPercentile?:number;
  rolloverPctStatus:"HIGH"|"NORMAL"|"LOW"|"INSUFFICIENT_HISTORY";
  rolloverCostStatus:"HIGH"|"NORMAL"|"LOW"|"INSUFFICIENT_HISTORY";
}
