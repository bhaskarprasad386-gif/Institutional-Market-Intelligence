import type { DeliveryObservation, InstitutionalFlowMetric, InstitutionalFlowObservation, SectorMetric, SectorObservation } from "./types";

const direction = (value: number): "inflow" | "outflow" | "flat" =>
  value > 0 ? "inflow" : value < 0 ? "outflow" : "flat";

/** Equal-weight constituent return avoids implying unavailable index weights. */
export function calculateSectorMetrics(rows: SectorObservation[]): SectorMetric[] {
  const groups = new Map<string, SectorObservation[]>();
  for (const row of rows) {
    const key = row.tradeDate + "|" + row.sector.trim();
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
  }
  return [...groups.entries()].map(([key, group]) => {
    const [tradeDate, sector] = key.split("|");
    const returns = group.map(row => (row.close / row.previousClose - 1) * 100);
    const advancing = returns.filter(value => value > 0).length;
    const declining = returns.filter(value => value < 0).length;
    const unchanged = returns.length - advancing - declining;
    return {
      sector, tradeDate, constituentCount: group.length,
      averageReturnPct: returns.reduce((sum, value) => sum + value, 0) / returns.length,
      advancing, declining, unchanged,
      tradedValue: group.reduce((sum, row) => sum + (row.tradedValue ?? 0), 0)
    };
  }).sort((a, b) => a.tradeDate.localeCompare(b.tradeDate) || b.averageReturnPct - a.averageReturnPct);
}

export function validateDeliveryObservation(row: DeliveryObservation): DeliveryObservation {
  if (!row.symbol.trim() || !Number.isFinite(Date.parse(row.tradeDate)) ||
      row.close <= 0 || row.volume <= 0 || row.deliveryQuantity < 0 ||
      row.deliveryQuantity > row.volume) {
    throw new Error("Delivery row has invalid symbol, date, price, volume, or delivery quantity.");
  }
  const deliveryPct = row.deliveryQuantity / row.volume * 100;
  if (row.deliveryPct < 0 || row.deliveryPct > 100 ||
      Math.abs(row.deliveryPct - deliveryPct) > 0.5) {
    throw new Error("Delivery percentage does not reconcile with delivery quantity / volume.");
  }
  return { ...row, deliveryPct, deliveryValue: row.deliveryValue ?? row.deliveryQuantity * row.close };
}

export function calculateInstitutionalFlow(row: InstitutionalFlowObservation): InstitutionalFlowMetric {
  if (!Number.isFinite(Date.parse(row.tradeDate)) || !Number.isFinite(row.fiiNet) ||
      !Number.isFinite(row.diiNet) || !row.unit.trim()) {
    throw new Error("Institutional flow requires a valid date, numeric FII/DII net values, and unit.");
  }
  return {
    ...row, combinedNet: row.fiiNet + row.diiNet,
    fiiDirection: direction(row.fiiNet), diiDirection: direction(row.diiNet)
  };
}
