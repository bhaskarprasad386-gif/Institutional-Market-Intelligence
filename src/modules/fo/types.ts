export interface FuturesObservation {
  symbol: string;
  tradeDate: string;
  expiryDate: string;
  futuresClose: number;
  spotClose: number;
  openInterest: number;
  previousOpenInterest?: number;
  previousFuturesClose?: number;
  volume?: number;
  lotSize?: number;
}
export interface FoMetrics {
  symbol: string; tradeDate: string; expiryDate: string;
  futuresClose: number; spotClose: number; openInterest: number;
  oiChange?: number; oiChangePct?: number; priceChangePct?: number;
  basis: number; costOfCarryAnnualizedPct?: number; daysToExpiry: number;
}
export type RolloverFlag = "HIGH" | "NORMAL" | "INSUFFICIENT_PEERS" | "ROLL_CREDIT";
export interface RolloverMetric {
  symbol: string; tradeDate: string; nearExpiry: string; nextExpiry: string;
  nearOi: number; nextOi: number; rolloverPct: number;
  nearFuturesClose: number; nextFuturesClose: number;
  rolloverCostPoints: number; rolloverCostPct: number;
  lotSize?: number; rolloverCostPerLot?: number;
  rolloverPctFlag: RolloverFlag; rolloverCostFlag: RolloverFlag;
  peerCount: number;
}
