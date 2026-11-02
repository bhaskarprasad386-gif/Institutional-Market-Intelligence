export type OptionType = "CE" | "PE";
export interface OptionObservation {
  underlying: string;
  symbol: string;
  tradeDate: string;
  expiryDate: string;
  strike: number;
  optionType: OptionType;
  spotPrice: number;
  openInterest: number;
  previousOpenInterest?: number;
  previousLtp?: number;
  volume?: number;
  ltp?: number;
  bid?: number;
  ask?: number;
  ivPct?: number;
}
export interface OptionMetric extends OptionObservation {
  daysToExpiry: number;
  moneynessPct: number;
  moneyness: "ITM" | "ATM" | "OTM";
  intrinsicValue?: number;
  timeValue?: number;
  oiChange?: number;
  oiChangePct?: number;
  priceChangePct?: number;
  priceOiSignal: "LONG_BUILD_UP" | "SHORT_BUILD_UP" | "SHORT_COVERING" | "LONG_UNWINDING" | "MIXED" | "INSUFFICIENT_DATA";
  ivPercentile?: number;
  volumeOiRatio?: number;
  delta?: number;
  gamma?: number;
  thetaPerDay?: number;
  vegaPerVolPoint?: number;
  unusualActivity: boolean;
}
export interface OptionExpirySummary {
  underlying: string;
  tradeDate: string;
  expiryDate: string;
  callOi: number;
  putOi: number;
  pcrOi?: number;
  callVolume: number;
  putVolume: number;
  pcrVolume?: number;
  maxPainStrike?: number;
  maxPainPayout?: number;
  atmIvSkewPct?: number;
  atmIvPct?: number;
  expectedMovePct?: number;
  expectedMovePoints?: number;
}
