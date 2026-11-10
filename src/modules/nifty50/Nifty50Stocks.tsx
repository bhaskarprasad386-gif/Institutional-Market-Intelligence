import { useEffect, useMemo, useState } from "react";

type StockRow = {
  symbol: string; name: string; sector?: string | null; marketDate?: string | null;
  close?: number | null; previousClose?: number | null; dailyChangePct?: number | null;
  volume?: number | null; deliveryQuantity?: number | null; deliveryPct?: number | null;
  sma20Daily?: number | null; sma50Daily?: number | null; sma20Weekly?: number | null; sma50Weekly?: number | null;
  rsiDaily14?: number | null; rsiWeekly14?: number | null; dailyHistorySessions?: number; weeklyHistorySessions?: number;
  technicalStatus?: string; deliveryStatus?: string;
};

const fmt = (v?: number | null, digits = 2) => v == null || !Number.isFinite(v) ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const qty = (v?: number | null) => v == null || !Number.isFinite(v) ? "—" : Math.round(v).toLocaleString("en-IN");
const pct = (v?: number | null) => v == null ? "—" : `${fmt(v)}%`;

export default function Nifty50Stocks() {
  const [rows, setRows] = useState<StockRow[]>([]);
  const [marketDate, setMarketDate] = useState("—");
  const [sessions, setSessions] = useState(0);
  const [status, setStatus] = useState("NIFTY 50 EOD data loading…");
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("ALL");
  const [sort, setSort] = useState<"symbol" | "dailyChangePct" | "deliveryPct">("symbol");
  useEffect(() => {
    let active = true;
    fetch("data/nifty50-eod-latest.json", { cache: "no-store" })
      .then(response => { if (!response.ok) throw new Error(`NIFTY 50 EOD snapshot unavailable (HTTP ${response.status})`); return response.json(); })
      .then(data => {
        if (!active) return;
        const stocks = Array.isArray(data.rows) ? data.rows as StockRow[] : [];
        setRows(stocks); setMarketDate(data.marketDate ?? "—"); setSessions(data.sessionsAvailable ?? 0);
        const ready = stocks.filter(row => row.close != null).length;
        setStatus(`NSE EOD · ${ready}/${stocks.length} stocks with close · ${data.constituentStatus ?? "constituents status unavailable"}`);
      })
      .catch(error => { if (active) setStatus(error instanceof Error ? error.message : "NIFTY 50 EOD data unavailable"); });
    return () => { active = false; };
  }, []);
  const sectors = useMemo(() => ["ALL", ...Array.from(new Set(rows.map(row => row.sector).filter((x): x is string => !!x))).sort()], [rows]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(row => (!q || row.symbol.toLowerCase().includes(q) || row.name.toLowerCase().includes(q)) && (sector === "ALL" || row.sector === sector))
      .sort((a,b) => sort === "symbol" ? a.symbol.localeCompare(b.symbol) : (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
  }, [rows, query, sector, sort]);
  const ready = rows.filter(row => row.close != null).length;
  return <section className="panel nifty50-page">
    <p className="eyebrow">NSE CASH MARKET · DAILY EOD INTELLIGENCE</p>
    <h2>NIFTY 50 Stock Intelligence</h2>
    <p className="muted">50 constituents · daily and weekly technical indicators · delivery participation. EOD snapshot only; this is not a live LTP feed.</p>
    <div className="nifty50-kpis">
      <article><small>Constituents</small><strong>{rows.length || "—"}</strong></article>
      <article><small>Latest market date</small><strong>{marketDate}</strong></article>
      <article><small>Stocks with EOD close</small><strong>{ready}/{rows.length || 50}</strong></article>
      <article><small>Archived sessions</small><strong>{sessions.toLocaleString("en-IN")}</strong></article>
    </div>
    <p className="nifty50-status" role="status">{status}</p>
    <div className="nifty50-toolbar">
      <label>Search stock<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Company or NSE symbol"/></label>
      <label>Sector<select value={sector} onChange={e=>setSector(e.target.value)}>{sectors.map(x=><option key={x} value={x}>{x === "ALL" ? "All sectors" : x}</option>)}</select></label>
      <label>Sort by<select value={sort} onChange={e=>setSort(e.target.value as typeof sort)}><option value="symbol">Symbol</option><option value="dailyChangePct">Daily change %</option><option value="deliveryPct">Delivery %</option></select></label>
    </div>
    <div className="table-wrap nifty50-table-wrap">
      <table className="nifty50-table">
        <thead>
          <tr><th rowSpan={2}>#</th><th rowSpan={2}>Company</th><th rowSpan={2}>Symbol</th><th rowSpan={2}>Sector</th><th rowSpan={2}>EOD LTP / Close ₹</th><th rowSpan={2}>Change %</th><th colSpan={2}>RSI 14</th><th colSpan={2}>SMA 20</th><th colSpan={2}>SMA 50</th><th rowSpan={2}>Volume Qty</th><th rowSpan={2}>Delivery Qty</th><th rowSpan={2}>Delivery %</th><th rowSpan={2}>History</th></tr>
          <tr><th>Daily</th><th>Weekly</th><th>Daily</th><th>Weekly</th><th>Daily</th><th>Weekly</th></tr>
        </thead>
        <tbody>{filtered.map((row,index)=><tr key={row.symbol}>
          <td>{index+1}</td><td>{row.name}</td><td><strong>{row.symbol}</strong></td><td>{row.sector ?? "—"}</td>
          <td>{fmt(row.close)}</td><td className={row.dailyChangePct == null ? "" : row.dailyChangePct >= 0 ? "positive" : "negative"}>{pct(row.dailyChangePct)}</td>
          <td>{fmt(row.rsiDaily14)}</td><td>{fmt(row.rsiWeekly14)}</td>
          <td>{fmt(row.sma20Daily)}</td><td>{fmt(row.sma20Weekly)}</td><td>{fmt(row.sma50Daily)}</td><td>{fmt(row.sma50Weekly)}</td>
          <td>{qty(row.volume)}</td><td>{qty(row.deliveryQuantity)}</td><td>{pct(row.deliveryPct)}</td>
          <td>{row.dailyHistorySessions ?? 0}D / {row.weeklyHistorySessions ?? 0}W</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="nifty50-note">Source: NSE Full Bhavcopy and Security Deliverable Data; constituents: NSE Indices. RSI uses Wilder's 14-period calculation. Weekly candles use the last available trading-session close in each ISO week. SMA/RSI remain blank until sufficient archived history exists. LTP is represented by the latest EOD close; intraday live prices are not included.</p>
  </section>;
}
