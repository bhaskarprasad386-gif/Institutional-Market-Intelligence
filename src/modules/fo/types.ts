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
}
export interface FoMetrics {
  symbol: string; tradeDate: string; expiryDate: string;
  futuresClose: number; spotClose: number; openInterest: number;
  oiChange?: number; oiChangePct?: number; priceChangePct?: number;
  basis: number; costOfCarryAnnualizedPct?: number; daysToExpiry: number;
}
export interface RolloverMetric { symbol: string; tradeDate: string; nearExpiry: string; nextExpiry: string; nearOi: number; nextOi: number; rolloverPct: number; }
