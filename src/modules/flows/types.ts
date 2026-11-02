export interface SectorObservation {
  symbol: string;
  sector: string;
  tradeDate: string;
  close: number;
  previousClose: number;
  tradedValue?: number;
}
export interface SectorMetric {
  sector: string;
  tradeDate: string;
  constituentCount: number;
  averageReturnPct: number;
  advancing: number;
  declining: number;
  unchanged: number;
  tradedValue: number;
}
export interface DeliveryObservation {
  symbol: string;
  tradeDate: string;
  close: number;
  volume: number;
  deliveryQuantity: number;
  deliveryPct: number;
  deliveryValue?: number;
}
export interface InstitutionalFlowObservation {
  tradeDate: string;
  fiiNet: number;
  diiNet: number;
  unit: string;
}
export interface InstitutionalFlowMetric extends InstitutionalFlowObservation {
  combinedNet: number;
  fiiDirection: "inflow" | "outflow" | "flat";
  diiDirection: "inflow" | "outflow" | "flat";
}
