import { useEffect, useMemo, useState } from "react";

type QuarterValue = { quarter: string; value: string | number | null; unit?: string };
type StockRow = {
  symbol: string; name: string; sector?: string | null; marketDate?: string | null;
  close?: number | null; previousClose?: number | null; dailyChangePct?: number | null;
  volume?: number | null; deliveryQuantity?: number | null; deliveryPct?: number | null;
  sma20Daily?: number | null; sma50Daily?: number | null; sma20Weekly?: number | null; sma50Weekly?: number | null;
  rsiDaily14?: number | null; rsiWeekly14?: number | null; dailyHistorySessions?: number; weeklyHistorySessions?: number;
  fiiPosition?: QuarterValue[] | null; diiPosition?: QuarterValue[] | null;
  earningsGuidance?: string | null; jefferiesReport?: string | null;
  latestOrderWin?: string | null; latestOrderBook?: string | null;
  relativeStrength?: number | null; relativeStrengthBias?: string | null;
  stockTailwind?: string | null; stockHeadwind?: string | null;
  sectorTrend?: string | null; sectorTailwind?: string | null; sectorHeadwind?: string | null;
  debtToEquity?: number | null; latestBulkBlockDeal?: string | null;
  latestPromoterPledge?: string | null; promoterBuying?: string | null;
  sectorCompanyNews?: string | null; opmPct?: number | null;
  roePct?: number | null; rocePct?: number | null; revenueGrowthPct?: number | null; profitGrowthPct?: number | null;
  operatingCashFlow?: number | null; interestCoverage?: number | null; peRatio?: number | null; evToEbitda?: number | null;
  promoterHoldingChangePct?: number | null; earningsSurprisePct?: number | null; oneMonthRelativeStrength?: number | null;
  threeMonthRelativeStrength?: number | null; sixMonthRelativeStrength?: number | null;
  technicalStatus?: string; deliveryStatus?: string;
};

const fmt = (v?: number | null, digits = 2) => v == null || !Number.isFinite(v) ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const qty = (v?: number | null) => v == null || !Number.isFinite(v) ? "—" : Math.round(v).toLocaleString("en-IN");
const pct = (v?: number | null) => v == null ? "—" : `${fmt(v)}%`;
const textOrDash = (v?: string | null) => v?.trim() || "—";
const quarterText = (values?: QuarterValue[] | null) => values?.length ? values.map(x => `${x.quarter}: ${x.value ?? "—"}${x.unit ? " " + x.unit : ""}`).join(" | ") : "—";

export default function Nifty50Stocks() {
  const [rows, setRows] = useState<StockRow[]>([]);
  const [marketDate, setMarketDate] = useState("—");
  const [sessions, setSessions] = useState(0);
  const [status, setStatus] = useState("NIFTY 50 EOD data loading…");
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("ALL");
  const [sort, setSort] = useState<"symbol" | "dailyChangePct" | "deliveryPct">("symbol");
  const [selected, setSelected] = useState<StockRow | null>(null);
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
    <p className="eyebrow">NSE CASH MARKET · FULL STOCK INTELLIGENCE MATRIX</p>
    <h2>NIFTY 50 Stock Intelligence</h2>
    <p className="muted">All requested technical, institutional, fundamental, order-flow and news columns are included. Missing or unverified source values remain blank; no values are fabricated.</p>
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
    <div className="nifty50-table-heading"><h3>Complete NIFTY 50 stock matrix</h3><span>{filtered.length} stocks · horizontally scroll to view all columns · click row for detail</span></div>
    <div className="table-wrap nifty50-table-wrap">
      <table className="nifty50-table nifty50-full-table">
        <thead>
          <tr>
            <th rowSpan={2}>#</th><th rowSpan={2}>Company</th><th rowSpan={2}>Symbol</th><th rowSpan={2}>Sector</th><th rowSpan={2}>LTP / EOD Close ₹</th><th rowSpan={2}>Change %</th>
            <th colSpan={2}>RSI 14</th><th colSpan={2}>SMA 20</th><th colSpan={2}>SMA 50</th>
            <th colSpan={3}>Volume & Delivery</th><th colSpan={2}>Institutional Position · 3 Quarters</th>
            <th colSpan={2}>Earnings & Broker Research</th><th colSpan={2}>Orders & Business</th>
            <th colSpan={1}>Relative Strength</th><th colSpan={2}>Stock Factors</th><th colSpan={3}>Sector Factors</th>
            <th colSpan={1}>Leverage</th><th colSpan={3}>Deals & Promoter</th><th colSpan={1}>News</th><th colSpan={1}>Profitability</th>
          </tr>
          <tr>
            <th>Daily</th><th>Weekly</th><th>Daily</th><th>Weekly</th><th>Daily</th><th>Weekly</th>
            <th>Traded Qty</th><th>Delivery Qty</th><th>Delivery %</th><th>FII · Q-1/Q-2/Q-3</th><th>DII · Q-1/Q-2/Q-3</th>
            <th>Earnings Guidance</th><th>Jefferies Report</th><th>Latest Order Win</th><th>Latest Order Book</th>
            <th>RS + / −</th><th>Tailwind</th><th>Headwind</th><th>Trend</th><th>Tailwind</th><th>Headwind</th>
            <th>Debt / Equity</th><th>Bulk / Block Deal</th><th>Promoter Pledge</th><th>Promoter Buying</th><th>Company / Sector News</th><th>OPM %</th>
          </tr>
        </thead>
        <tbody>{filtered.map((row,index)=><tr key={row.symbol} onClick={()=>setSelected(row)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setSelected(row);}}} tabIndex={0} aria-label={`Open ${row.name} details`} className={selected?.symbol===row.symbol?"selected":""}>
          <td>{index+1}</td><td>{row.name}</td><td><strong>{row.symbol}</strong></td><td>{textOrDash(row.sector)}</td><td>{fmt(row.close)}</td><td className={row.dailyChangePct == null ? "" : row.dailyChangePct >= 0 ? "positive" : "negative"}>{pct(row.dailyChangePct)}</td>
          <td>{fmt(row.rsiDaily14)}</td><td>{fmt(row.rsiWeekly14)}</td><td>{fmt(row.sma20Daily)}</td><td>{fmt(row.sma20Weekly)}</td><td>{fmt(row.sma50Daily)}</td><td>{fmt(row.sma50Weekly)}</td>
          <td>{qty(row.volume)}</td><td>{qty(row.deliveryQuantity)}</td><td>{pct(row.deliveryPct)}</td>
          <td>{quarterText(row.fiiPosition)}</td><td>{quarterText(row.diiPosition)}</td><td>{textOrDash(row.earningsGuidance)}</td><td>{textOrDash(row.jefferiesReport)}</td>
          <td>{textOrDash(row.latestOrderWin)}</td><td>{textOrDash(row.latestOrderBook)}</td>
          <td className={row.relativeStrength==null?"":row.relativeStrength>=0?"positive":"negative"}>{row.relativeStrength==null?textOrDash(row.relativeStrengthBias):`${fmt(row.relativeStrength)} · ${row.relativeStrength>=0?"Positive":"Negative"}`}</td>
          <td>{textOrDash(row.stockTailwind)}</td><td>{textOrDash(row.stockHeadwind)}</td><td>{textOrDash(row.sectorTrend)}</td><td>{textOrDash(row.sectorTailwind)}</td><td>{textOrDash(row.sectorHeadwind)}</td>
          <td>{fmt(row.debtToEquity)}</td><td>{textOrDash(row.latestBulkBlockDeal)}</td><td>{textOrDash(row.latestPromoterPledge)}</td><td>{textOrDash(row.promoterBuying)}</td><td>{textOrDash(row.sectorCompanyNews)}</td><td>{pct(row.opmPct)}</td>
        </tr>)}</tbody>
      </table>
    </div>
    {selected && <section className="nifty50-detail" aria-live="polite">
      <div className="nifty50-detail-head"><div><p className="eyebrow">STOCK DETAIL · {selected.symbol}</p><h3>{selected.name}</h3><p className="muted">{textOrDash(selected.sector)} · EOD date {selected.marketDate ?? marketDate}</p></div><button type="button" onClick={()=>setSelected(null)}>Close ×</button></div>
      <div className="nifty50-detail-grid">
        <article><small>LTP / EOD Close</small><strong>₹{fmt(selected.close)}</strong></article><article><small>RSI Daily / Weekly</small><strong>{fmt(selected.rsiDaily14)} / {fmt(selected.rsiWeekly14)}</strong></article>
        <article><small>SMA 20 Daily / Weekly</small><strong>{fmt(selected.sma20Daily)} / {fmt(selected.sma20Weekly)}</strong></article><article><small>SMA 50 Daily / Weekly</small><strong>{fmt(selected.sma50Daily)} / {fmt(selected.sma50Weekly)}</strong></article>
        <article><small>Volume / Delivery Qty</small><strong>{qty(selected.volume)} / {qty(selected.deliveryQuantity)}</strong></article><article><small>Delivery %</small><strong>{pct(selected.deliveryPct)}</strong></article>
        <article><small>FII Position · last 3 quarters</small><strong>{quarterText(selected.fiiPosition)}</strong></article><article><small>DII Position · last 3 quarters</small><strong>{quarterText(selected.diiPosition)}</strong></article>
        <article><small>ROE / ROCE</small><strong>{pct(selected.roePct)} / {pct(selected.rocePct)}</strong></article><article><small>Revenue / Profit Growth</small><strong>{pct(selected.revenueGrowthPct)} / {pct(selected.profitGrowthPct)}</strong></article>
        <article><small>Operating Cash Flow</small><strong>{fmt(selected.operatingCashFlow)}</strong></article><article><small>Interest Coverage</small><strong>{fmt(selected.interestCoverage)}</strong></article>
        <article><small>P/E · EV / EBITDA</small><strong>{fmt(selected.peRatio)} / {fmt(selected.evToEbitda)}</strong></article><article><small>Promoter Holding Change</small><strong>{pct(selected.promoterHoldingChangePct)}</strong></article>
        <article><small>Earnings Surprise</small><strong>{pct(selected.earningsSurprisePct)}</strong></article><article><small>RS 1M / 3M / 6M</small><strong>{fmt(selected.oneMonthRelativeStrength)} / {fmt(selected.threeMonthRelativeStrength)} / {fmt(selected.sixMonthRelativeStrength)}</strong></article>
      </div>
      <p className="nifty50-note">Status: {selected.technicalStatus ?? "TECHNICAL DATA PENDING"} · Delivery: {selected.deliveryStatus ?? "DELIVERY DATA PENDING"}. All non-EOD fields require source-backed enrichment with publication/reporting date; absent values remain blank.</p>
    </section>}
    <p className="nifty50-note">EOD technical source: NSE cash bhavcopy / security deliverable data. RSI uses Wilder 14-period calculation; weekly candles use the final available close of each ISO week. Fundamental, institutional, broker-report, deal, promoter and news fields are schema-ready but will remain blank until independently verified source data is connected. No estimates are shown as facts.</p>
  </section>;
}
