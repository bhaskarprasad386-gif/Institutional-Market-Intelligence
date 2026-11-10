import { useEffect, useMemo, useState } from "react";

type StockRow = {
  symbol: string; name: string; sector?: string | null; marketDate?: string | null;
  [key: string]: unknown;
};
type Column = { key: string; label: string; format?: "price" | "pct" | "qty" | "number" };
type ColumnGroup = { title: string; columns: Column[] };

const groups: ColumnGroup[] = [
  { title: "IDENTITY & MARKET", columns: [
    {key:"name",label:"Company"},{key:"symbol",label:"Symbol"},{key:"sector",label:"Sector"},
    {key:"marketDate",label:"EOD Date"},{key:"close",label:"EOD LTP / Close ₹",format:"price"},
    {key:"previousClose",label:"Previous Close ₹",format:"price"},{key:"dailyChangePct",label:"Daily Change %",format:"pct"},
    {key:"volume",label:"Traded Volume Qty",format:"qty"},{key:"deliveryQuantity",label:"Delivery Qty",format:"qty"},{key:"deliveryPct",label:"Delivery %",format:"pct"}
  ]},
  { title: "TECHNICAL INDICATORS", columns: [
    {key:"rsiDaily14",label:"RSI 14 Daily",format:"number"},{key:"rsiWeekly14",label:"RSI 14 Weekly",format:"number"},
    {key:"sma20Daily",label:"SMA 20 Daily ₹",format:"price"},{key:"sma20Weekly",label:"SMA 20 Weekly ₹",format:"price"},
    {key:"sma50Daily",label:"SMA 50 Daily ₹",format:"price"},{key:"sma50Weekly",label:"SMA 50 Weekly ₹",format:"price"},
    {key:"volumeRatio20D",label:"Volume / 20D Avg"},{key:"deliveryTrend",label:"Delivery Trend"},
    {key:"high52Week",label:"52W High ₹",format:"price"},{key:"low52Week",label:"52W Low ₹",format:"price"}
  ]},
  { title: "RELATIVE STRENGTH & SECTOR", columns: [
    {key:"relativeStrength1M",label:"Stock RS 1M",format:"pct"},{key:"relativeStrength3M",label:"Stock RS 3M",format:"pct"},
    {key:"relativeStrength6M",label:"Stock RS 6M",format:"pct"},{key:"relativeStrengthTrend",label:"Stock RS Trend"},
    {key:"stockTailwind",label:"Stock Tailwind"},{key:"stockHeadwind",label:"Stock Headwind"},
    {key:"sectorTrend",label:"Sector Trend"},{key:"sectorTailwind",label:"Sector Tailwind"},{key:"sectorHeadwind",label:"Sector Headwind"}
  ]},
  { title: "INSTITUTIONAL POSITIONING", columns: [
    {key:"fiiPosition3Q",label:"FII Position · Previous 3 Quarters"},{key:"diiPosition3Q",label:"DII Position · Previous 3 Quarters"},
    {key:"promoterHoldingChange",label:"Promoter Holding Change",format:"pct"},{key:"promoterBuying",label:"Promoter Buying"},
    {key:"promoterPledge",label:"Latest Promoter Pledge",format:"pct"},{key:"bulkBlockDeal",label:"Latest Bulk / Block Deal"}
  ]},
  { title: "FINANCIAL QUALITY & VALUATION", columns: [
    {key:"opmPct",label:"OPM %",format:"pct"},{key:"roePct",label:"ROE %",format:"pct"},{key:"rocePct",label:"ROCE %",format:"pct"},
    {key:"debtToEquity",label:"Debt / Equity",format:"number"},{key:"interestCoverage",label:"Interest Coverage",format:"number"},
    {key:"revenueGrowth",label:"Revenue Growth %",format:"pct"},{key:"profitGrowth",label:"Profit Growth %",format:"pct"},
    {key:"operatingCashFlow",label:"Operating Cash Flow ₹"},{key:"freeCashFlow",label:"Free Cash Flow ₹"},
    {key:"peVsSector",label:"P/E vs Sector"},{key:"evEbitdaVsSector",label:"EV / EBITDA vs Sector"}
  ]},
  { title: "EARNINGS, GUIDANCE & ORDERS", columns: [
    {key:"earningsGuidance",label:"Earnings Guidance"},{key:"earningsSurprise",label:"Latest Earnings Surprise"},
    {key:"epsRevision",label:"EPS Revision"},{key:"jefferiesReport",label:"Latest Jefferies Report"},
    {key:"latestOrderWin",label:"Latest Order Win"},{key:"latestOrderBook",label:"Latest Order Book"},
    {key:"orderBookToRevenue",label:"Order Book / Revenue"},{key:"executionStatus",label:"Order Execution / Cancellation"}
  ]},
  { title: "CORPORATE EVENTS, NEWS & RISK", columns: [
    {key:"corporateCalendar",label:"Corporate Calendar"},{key:"companyNews",label:"Company News"},
    {key:"sectorNews",label:"Sector News"},{key:"riskFlags",label:"Risk Flags"}
  ]}
];
const columns = groups.flatMap(group => group.columns);
const fmt = (v: unknown, format?: Column["format"]) => {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return "—";
    if (format === "qty") return Math.round(v).toLocaleString("en-IN");
    if (format === "pct") return v.toLocaleString("en-IN",{maximumFractionDigits:2}) + "%";
    return v.toLocaleString("en-IN",{minimumFractionDigits:format==="price"?2:0,maximumFractionDigits:2});
  }
  if (Array.isArray(v)) return v.map(x => typeof x === "object" ? JSON.stringify(x) : String(x)).join(" · ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};
const unavailable = (key: string) => ["fiiPosition3Q","diiPosition3Q","earningsGuidance","earningsSurprise","epsRevision","jefferiesReport","latestOrderWin","latestOrderBook","orderBookToRevenue","executionStatus","stockTailwind","stockHeadwind","sectorTrend","sectorTailwind","sectorHeadwind","debtToEquity","opmPct","roePct","rocePct","interestCoverage","revenueGrowth","profitGrowth","operatingCashFlow","freeCashFlow","peVsSector","evEbitdaVsSector","bulkBlockDeal","promoterPledge","promoterBuying","promoterHoldingChange","companyNews","sectorNews","riskFlags","corporateCalendar","relativeStrength1M","relativeStrength3M","relativeStrength6M","relativeStrengthTrend","volumeRatio20D","deliveryTrend","high52Week","low52Week"].includes(key);

export default function Nifty50Stocks() {
  const [rows, setRows] = useState<StockRow[]>([]);
  const [marketDate, setMarketDate] = useState("—");
  const [sessions, setSessions] = useState(0);
  const [status, setStatus] = useState("NIFTY 50 EOD data loading…");
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("ALL");
  const [sort, setSort] = useState("symbol");
  const [selected, setSelected] = useState<StockRow | null>(null);
  useEffect(() => {
    let active = true;
    fetch("data/nifty50-eod-latest.json", {cache:"no-store"})
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
  const sectors = useMemo(() => ["ALL", ...Array.from(new Set(rows.map(row => row.sector).filter((x): x is string => typeof x === "string" && !!x))).sort()], [rows]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(row => (!q || row.symbol.toLowerCase().includes(q) || row.name.toLowerCase().includes(q)) && (sector === "ALL" || row.sector === sector))
      .sort((a,b) => sort === "symbol" ? a.symbol.localeCompare(b.symbol) : (Number(b[sort]) || -Infinity) - (Number(a[sort]) || -Infinity));
  }, [rows, query, sector, sort]);
  const ready = rows.filter(row => row.close != null).length;
  return <section className="panel nifty50-page">
    <p className="eyebrow">NSE CASH MARKET · FULL STOCK INTELLIGENCE MATRIX</p>
    <h2>NIFTY 50 Stock Intelligence</h2>
    <p className="muted">Complete requested column layout across market data, technicals, relative strength, FII/DII, fundamentals, earnings, orders, corporate events and news. Missing data is shown as —, never fabricated.</p>
    <div className="nifty50-kpis">
      <article><small>Constituents</small><strong>{rows.length || "—"}</strong></article>
      <article><small>Latest market date</small><strong>{marketDate}</strong></article>
      <article><small>Stocks with EOD close</small><strong>{ready}/{rows.length || 50}</strong></article>
      <article><small>Archived sessions</small><strong>{sessions.toLocaleString("en-IN")}</strong></article>
    </div>
    <p className="nifty50-status" role="status">{status}</p>
    <div className="nifty50-toolbar">
      <label>Search stock<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Company or NSE symbol"/></label>
      <label>Sector<select value={sector} onChange={e=>setSector(e.target.value)}>{sectors.map(x=><option key={x} value={x}>{x==="ALL"?"All sectors":x}</option>)}</select></label>
      <label>Sort by<select value={sort} onChange={e=>setSort(e.target.value)}><option value="symbol">Symbol</option><option value="dailyChangePct">Daily change %</option><option value="deliveryPct">Delivery %</option><option value="rsiDaily14">Daily RSI</option><option value="relativeStrength3M">3M Relative strength</option></select></label>
    </div>
    <div className="nifty50-table-heading"><h3>Complete NIFTY 50 data matrix</h3><span>{filtered.length} stocks · {columns.length} columns · horizontal scroll</span></div>
    <div className="table-wrap nifty50-table-wrap nifty50-full-matrix">
      <table className="nifty50-table">
        <thead>
          <tr><th className="nifty50-sticky-col" rowSpan={2}>#</th>{groups.map(group=><th key={group.title} colSpan={group.columns.length}>{group.title}</th>)}</tr>
          <tr>{columns.map(col=><th key={col.key}>{col.label}</th>)}</tr>
        </thead>
        <tbody>{filtered.map((row,index)=><tr key={row.symbol} onClick={()=>setSelected(row)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setSelected(row);}}} tabIndex={0} aria-label={`Open ${row.name} details`} className={selected?.symbol===row.symbol?"selected":""}>
          <td className="nifty50-sticky-col">{index+1}</td>
          {columns.map(col=><td key={col.key} className={col.key==="dailyChangePct" && typeof row[col.key]==="number" ? (Number(row[col.key])>=0?"positive":"negative") : ""}>{fmt(row[col.key],col.format)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    {selected && <section className="nifty50-detail" aria-live="polite">
      <div className="nifty50-detail-head"><div><p className="eyebrow">SELECTED STOCK · {selected.symbol}</p><h3>{selected.name}</h3><p className="muted">{selected.sector ?? "Sector not provided"} · EOD date {String(selected.marketDate ?? marketDate)}</p></div><button type="button" onClick={()=>setSelected(null)}>Close ×</button></div>
      <div className="nifty50-detail-grid">{columns.map(col=><article key={col.key}><small>{col.label}</small><strong>{fmt(selected[col.key],col.format)}</strong></article>)}</div>
      <p className="nifty50-note">Values not yet sourced remain blank. For FII/DII, financial ratios, reports, orders, deals, pledge and news, source and reporting date will be added with the data ingestion layer.</p>
    </section>}
    <p className="nifty50-note">EOD close is not intraday live LTP. RSI uses Wilder's 14-period calculation; weekly candles use the last available trading-session close in each ISO week. Fundamentals, institutional positioning, analyst reports, orders and news are displayed as empty until verified source feeds are connected.</p>
  </section>;
}
