import type { DeliveryObservation, InstitutionalFlowObservation, SectorObservation } from "./types";
type Raw = Record<string, unknown>;
type Rejection = { rowNumber: number; reason: string };
const aliases: Record<string, string[]> = {
  symbol: ["symbol", "tckrsymb", "security", "scrip"],
  sector: ["sector", "industry", "sector_name"],
  tradeDate: ["trade_date", "trad_dt", "trddt", "date", "date1"],
  close: ["close", "clspric", "close_price", "closing_price"],
  previousClose: ["previous_close", "prevclose", "prvsclsgpric"],
  tradedValue: ["traded_value", "ttltrfval", "tottrdval", "turnover"],
  volume: ["volume", "ttltradgvol", "tottrdqty", "total_traded_quantity"],
  deliveryQuantity: ["delivery_quantity", "deliv_qty", "delqty", "delivery_qty"],
  deliveryPct: ["delivery_pct", "delivery_percent", "deliv_per", "deliv_pct"],
  deliveryValue: ["delivery_value", "delivery_val"],
  fiiNet: ["fii_net", "fii_net_value", "fii_net_purchase_sale"],
  diiNet: ["dii_net", "dii_net_value", "dii_net_purchase_sale"],
  unit: ["unit", "units"]
};
const normalize = (value: string) => value.toLowerCase().replace(/[ _-]/g, "");
function get(row: Raw, name: keyof typeof aliases): unknown {
  const entry = Object.entries(row).find(([header]) => aliases[name].some(alias => normalize(alias) === normalize(header)));
  return entry?.[1];
}
function number(value: unknown): number | undefined {
  if (value === null || value === undefined || String(value).trim() === "") return undefined;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : undefined;
}
function date(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0, 10);
  const text = String(value ?? "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const match = text.match(/^(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})$/);
  if (match) {
    const parsed = new Date(`${match[2]} ${match[1]}, ${match[3]} UTC`);
    if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  }
  return undefined;
}
function result<T>(rows: T[], rejected: Rejection[]) { return { rows, rejected }; }

export function mapSectorRows(input: Raw[], expectedDate?: string) {
  const rows: SectorObservation[] = [], rejected: Rejection[] = [];
  input.forEach((raw, index) => {
    const symbol = String(get(raw, "symbol") ?? "").trim();
    const sector = String(get(raw, "sector") ?? "").trim();
    const tradeDate = date(get(raw, "tradeDate"));
    const close = number(get(raw, "close"));
    const previousClose = number(get(raw, "previousClose"));
    const tradedValue = number(get(raw, "tradedValue"));
    if (!symbol || !sector || !tradeDate || close === undefined || previousClose === undefined ||
        close <= 0 || previousClose <= 0 || (expectedDate && tradeDate !== expectedDate)) {
      rejected.push({ rowNumber: index + 2, reason: "Missing/invalid symbol, sector, date, close or previous close; or date mismatch" });
      return;
    }
    rows.push({ symbol, sector, tradeDate, close, previousClose, tradedValue });
  });
  return result(rows, rejected);
}

export function mapDeliveryRows(input: Raw[], expectedDate?: string) {
  const rows: DeliveryObservation[] = [], rejected: Rejection[] = [];
  input.forEach((raw, index) => {
    const symbol = String(get(raw, "symbol") ?? "").trim();
    const tradeDate = date(get(raw, "tradeDate"));
    const close = number(get(raw, "close"));
    const volume = number(get(raw, "volume"));
    const deliveryQuantity = number(get(raw, "deliveryQuantity"));
    const suppliedPct = number(get(raw, "deliveryPct"));
    const deliveryPct = suppliedPct ?? (volume && deliveryQuantity !== undefined ? deliveryQuantity / volume * 100 : undefined);
    const deliveryValue = number(get(raw, "deliveryValue"));
    if (!symbol || !tradeDate || close === undefined || volume === undefined ||
        deliveryQuantity === undefined || deliveryPct === undefined ||
        close <= 0 || volume <= 0 || deliveryQuantity < 0 || deliveryQuantity > volume ||
        deliveryPct < 0 || deliveryPct > 100 || (expectedDate && tradeDate !== expectedDate)) {
      rejected.push({ rowNumber: index + 2, reason: "Missing/invalid delivery fields or market-date mismatch" });
      return;
    }
    rows.push({ symbol, tradeDate, close, volume, deliveryQuantity, deliveryPct, deliveryValue });
  });
  return result(rows, rejected);
}

export function mapInstitutionalFlowRows(input: Raw[], expectedDate?: string) {
  const rows: InstitutionalFlowObservation[] = [], rejected: Rejection[] = [];
  input.forEach((raw, index) => {
    const tradeDate = date(get(raw, "tradeDate"));
    const fiiNet = number(get(raw, "fiiNet"));
    const diiNet = number(get(raw, "diiNet"));
    const unit = String(get(raw, "unit") ?? "₹ crore").trim();
    if (!tradeDate || fiiNet === undefined || diiNet === undefined || !unit ||
        (expectedDate && tradeDate !== expectedDate)) {
      rejected.push({ rowNumber: index + 2, reason: "Missing/invalid date or FII/DII net values; or date mismatch" });
      return;
    }
    rows.push({ tradeDate, fiiNet, diiNet, unit });
  });
  return result(rows, rejected);
}
