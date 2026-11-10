import { useMemo, useState } from "react";
import type { FoMetrics } from "../fo/types";

type Props = { futures: FoMetrics[]; status: string };

const BANK_STOCKS = [
  { symbol: "AUBANK", name: "AU Small Finance Bank" },
  { symbol: "AXISBANK", name: "Axis Bank" },
  { symbol: "BANDHANBNK", name: "Bandhan Bank" },
  { symbol: "BANKBARODA", name: "Bank of Baroda" },
  { symbol: "BANKINDIA", name: "Bank of India" },
  { symbol: "CANBK", name: "Canara Bank" },
  { symbol: "CENTRALBK", name: "Central Bank of India" },
  { symbol: "CUB", name: "City Union Bank" },
  { symbol: "DCBBANK", name: "DCB Bank" },
  { symbol: "FEDERALBNK", name: "Federal Bank" },
  { symbol: "HDFCBANK", name: "HDFC Bank" },
  { symbol: "ICICIBANK", name: "ICICI Bank" },
  { symbol: "IDFCFIRSTB", name: "IDFC First Bank" },
  { symbol: "INDIANB", name: "Indian Bank" },
  { symbol: "INDUSINDBK", name: "IndusInd Bank" },
  { symbol: "IOB", name: "Indian Overseas Bank" },
  { symbol: "J&KBANK", name: "Jammu & Kashmir Bank" },
  { symbol: "KARURVYSYA", name: "Karur Vysya Bank" },
  { symbol: "KOTAKBANK", name: "Kotak Mahindra Bank" },
  { symbol: "MAHABANK", name: "Bank of Maharashtra" },
  { symbol: "PNB", name: "Punjab National Bank" },
  { symbol: "RBLBANK", name: "RBL Bank" },
  { symbol: "SBIN", name: "State Bank of India" },
  { symbol: "UCOBANK", name: "UCO Bank" },
  { symbol: "UNIONBANK", name: "Union Bank of India" },
  { symbol: "YESBANK", name: "Yes Bank" }
];

const fmt = (value?: number) => value === undefined || !Number.isFinite(value) ? "—" : value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
export default function BankingStocks({ futures, status }: Props) {
  const [query, setQuery] = useState("");
  const [coverage, setCoverage] = useState<"all" | "available" | "missing">("all");
  const latestDate = useMemo(() => futures.reduce((latest, row) => row.tradeDate > latest ? row.tradeDate : latest, ""), [futures]);
  const rows = useMemo(() => {
    const latest = futures.filter(row => row.tradeDate === latestDate);
    const bySymbol = new Map<string, FoMetrics[]>();
    for (const row of latest) {
      if (!BANK_STOCKS.some(bank => bank.symbol === row.symbol)) continue;
      const group = bySymbol.get(row.symbol) ?? [];
      group.push(row);
      bySymbol.set(row.symbol, group);
    }
    return BANK_STOCKS.map(bank => {
      const contracts = (bySymbol.get(bank.symbol) ?? []).sort((a, b) => a.expiryDate.localeCompare(b.expiryDate));
      return { ...bank, metric: contracts[0] };
    }).filter(row => {
      const matches = (row.symbol + " " + row.name).toLowerCase().includes(query.trim().toLowerCase());
      const hasData = Boolean(row.metric);
      return matches && (coverage === "all" || (coverage === "available" ? hasData : !hasData));
    });
  }, [futures, latestDate, query, coverage]);
  const available = rows.filter(row => row.metric).length;
  const positiveOi = rows.filter(row => (row.metric?.oiChangePct ?? 0) > 0).length;
  return <section className="panel bank-stocks">
    <p className="eyebrow">NSE CASH BANKING UNIVERSE · F&O EOD SNAPSHOT</p>
    <h2>Banking Stocks</h2>
    <p className="muted">इस अलग page पर केवल NSE-listed banking shares की सूची है। उपलब्ध आंकड़े मौजूदा NSE F&O EOD dataset से हैं; यह live price feed नहीं है। जिन shares का futures contract या data उपलब्ध नहीं है, उन्हें blank दिखाया जाएगा—कोई price या signal अनुमान से नहीं भरा जाएगा।</p>
    <div className="notice" role="status">{status}</div>
    <div className="bank-kpis">
      <article><span>Bank stocks in universe</span><strong>{BANK_STOCKS.length}</strong></article>
      <article><span>Futures data available</span><strong>{available}</strong></article>
      <article><span>Positive OI change</span><strong>{positiveOi}</strong></article>
      <article><span>Latest market date</span><strong>{latestDate || "—"}</strong></article>
    </div>
    <div className="bank-toolbar">
      <label>Search bank<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search symbol or bank name"/></label>
      <label>Data coverage<select value={coverage} onChange={event => setCoverage(event.target.value as typeof coverage)}><option value="all">All banking stocks</option><option value="available">Data available</option><option value="missing">Data unavailable</option></select></label>
    </div>
    <div className="table-wrap"><table><thead><tr><th>Bank</th><th>Symbol</th><th>Nearest futures expiry</th><th>Futures close</th><th>Spot reference</th><th>Basis</th><th>Price change %</th><th>OI</th><th>OI change %</th><th>Annualized CoC %</th><th>Coverage</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.symbol}><td>{row.name}</td><td><strong>{row.symbol}</strong></td><td>{row.metric?.expiryDate ?? "—"}</td><td>{fmt(row.metric?.futuresClose)}</td><td>{fmt(row.metric?.spotClose)}</td><td>{fmt(row.metric?.basis)}</td><td>{fmt(row.metric?.priceChangePct)}</td><td>{fmt(row.metric?.openInterest)}</td><td>{fmt(row.metric?.oiChangePct)}</td><td>{fmt(row.metric?.costOfCarryAnnualizedPct)}</td><td>{row.metric ? "EOD available" : "No futures row"}</td></tr>)}</tbody>
    </table></div>
    <p className="muted">Nearest expiry is selected from the latest available market date. Spot reference is the spot field carried in the NSE F&amp;O bhavcopy, not a separate live cash-market quote. OI change and price change remain blank when the source does not provide sufficient previous-session data.</p>
  </section>;
}
