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
  volume?: number;
  ltp?: number;
  bid?: number;
  ask?: number;
  ivPct?: number;
}
export interface OptionMetric extends OptionObservation {
  daysToExpiry: number;
  moneynessPct: number;
  intrinsicValue?: number;
  timeValue?: number;
  oiChange?: number;
  oiChangePct?: number;
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
}
