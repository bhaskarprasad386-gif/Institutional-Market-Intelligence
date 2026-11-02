export type Exchange = "NSE" | "BSE";
export interface EodEquityRow {
  exchange: Exchange;
  symbol: string;
  tradeDate: string;
  series?: string;
  open?: number;
  high?: number;
  low?: number;
  close: number;
  previousClose?: number;
  last?: number;
  volume?: number;
  tradedValue?: number;
  trades?: number;
  sourceFields: Record<string, unknown>;
}
export interface MappingResult { rows: EodEquityRow[]; rejected: { rowNumber: number; reason: string }[]; }

const aliases: Record<string, string[]> = {
  symbol: ["symbol", "tckrsymb", "sc_name", "security name", "security"],
  series: ["series", "sctysrs", "sc_group"],
  tradeDate: ["date1", "trddt", "trad_dt", "tradDt", "trade_date", "date"],
  open: ["open", "opnpric", "open price"],
  high: ["high", "hghpric", "high price"],
  low: ["low", "lwpric", "low price"],
  close: ["close", "clspric", "close price"],
  previousClose: ["prevclose", "prvsclsgpric", "previous close"],
  last: ["last", "lastpric", "last price"],
  volume: ["tottrdqty", "ttltradgvol", "no_of_shrs", "volume", "total traded quantity"],
  tradedValue: ["tottrdval", "ttltrfval", "net_turnov", "traded value"],
  trades: ["totaltrades", "ttlnbofntrsexctd", "no_trades", "trades"]
};
const key = (s: string) => s.toLowerCase().replace(/[ _-]/g, "");
function field(row: Record<string, unknown>, name: keyof typeof aliases): unknown {
  const entries = Object.entries(row);
  const found = entries.find(([k]) => aliases[name].some(a => key(k) === key(a)));
  return found?.[1];
}
function numberValue(value: unknown): number | undefined {
  if (value === null || value === undefined || String(value).trim() === "" || String(value).trim() === "-") return undefined;
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n : undefined;
}
function dateValue(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0,10);
  const s = String(value ?? "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})$/);
  if (m) { const d = new Date(`${m[2]} ${m[1]}, ${m[3]} UTC`); if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0,10); }
  const compact = s.match(/^(\d{2})(\d{2})(\d{4})$/);
  if (compact) return `${compact[3]}-${compact[2]}-${compact[1]}`;
  return undefined;
}
export function mapEquityEodRows(input: Record<string, unknown>[], exchange: Exchange, expectedMarketDate?: string): MappingResult {
  const rows: EodEquityRow[] = [];
  const rejected: MappingResult["rejected"] = [];
  input.forEach((raw, index) => {
    const symbol = String(field(raw, "symbol") ?? "").trim();
    const tradeDate = dateValue(field(raw, "tradeDate"));
    const close = numberValue(field(raw, "close"));
    if (!symbol || !tradeDate || close === undefined || close <= 0) {
      rejected.push({ rowNumber: index + 2, reason: !symbol ? "Symbol missing" : !tradeDate ? "Trade date missing/invalid" : "Close price missing/invalid" });
      return;
    }
    const open = numberValue(field(raw, "open")), high = numberValue(field(raw, "high")), low = numberValue(field(raw, "low"));
    if ((high !== undefined && low !== undefined && high < low) || (open !== undefined && open <= 0) || (high !== undefined && high <= 0) || (low !== undefined && low <= 0)) {
      rejected.push({ rowNumber: index + 2, reason: "OHLC values inconsistent" }); return;
    }
    rows.push({ exchange, symbol, tradeDate, series: String(field(raw, "series") ?? "") || undefined, open, high, low, close,
      previousClose: numberValue(field(raw, "previousClose")), last: numberValue(field(raw, "last")),
      volume: numberValue(field(raw, "volume")), tradedValue: numberValue(field(raw, "tradedValue")), trades: numberValue(field(raw, "trades")), sourceFields: raw });
  });
  return { rows, rejected };
}
