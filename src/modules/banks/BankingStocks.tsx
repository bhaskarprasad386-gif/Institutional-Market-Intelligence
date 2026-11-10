import { useEffect, useMemo, useState } from "react";

type Props = { futures: unknown[]; status: string };

const LAYER_ONE_FACTORS = [
  { name: "Net Interest Margin (NIM)", target: "> 4%" },
  { name: "Net NPA", target: "< 1%" },
  { name: "Slippage Run-Rate", target: "Declining trend" },
  { name: "Core PPOP Growth", target: "> 20%" },
  { name: "Cost-to-Income", target: "< 45%" },
  { name: "Credit-Deposit (CD) Ratio", target: "75–80%" },
  { name: "Provision Coverage Ratio (PCR)", target: "≥ 75%" },
  { name: "CASA Ratio", target: "> 40%" },
  { name: "Restructured Book", target: "< 1%" },
  { name: "NPA Upgrade", target: "Improving trend" },
  { name: "TLAC / AT1 Bond", target: "Capital strength review" },
  { name: "RAM Mix Shift", target: "Quality mix improvement" },
  { name: "Opex Savings", target: "Sustainable cost reduction" }
];

const LAYER_TWO_FACTORS = [
  { id: "analyst", name: "Bank-wise Broker Upgrade / Downgrade Reports", target: "Upgrade / downgrade and estimate revisions" },
  { id: "credit", name: "RBI Fortnightly Credit Growth", target: "Scheduled commercial bank credit YoY" },
  { id: "gsec10y", name: "10-Year Government Bond Yield", target: "10-year benchmark G-Sec yield" },
  { id: "repo", name: "RBI Repo Rate Scenario", target: "Policy repo rate and MPC stance" },
  { id: "liquidity", name: "RBI LTRO / Liquidity Window", target: "Net liquidity injected (+) / absorbed (-)" },
  { id: "sixth", name: "Sixth Macro / External Factor", target: "Original factor name not supplied; awaiting confirmation" }
];

const BANK_STOCKS = [
  { symbol: "HDFCBANK", name: "HDFC Bank" },
  { symbol: "ICICIBANK", name: "ICICI Bank" },
  { symbol: "SBIN", name: "State Bank of India" },
  { symbol: "KOTAKBANK", name: "Kotak Mahindra Bank" },
  { symbol: "AXISBANK", name: "Axis Bank" },
  { symbol: "PNB", name: "Punjab National Bank" },
  { symbol: "UNIONBANK", name: "Union Bank of India" },
  { symbol: "BANKBARODA", name: "Bank of Baroda" },
  { symbol: "CANBK", name: "Canara Bank" },
  { symbol: "FEDERALBNK", name: "Federal Bank" }
];

export default function BankingStocks(_props: Props) {
  const [search, setSearch] = useState("");
  const [marketRows, setMarketRows] = useState<Record<string, any>>({});
  const [macroRows, setMacroRows] = useState<Record<string, any>>({});
  const [macroStatus, setMacroStatus] = useState("RBI macro snapshot loading…");
  const [marketStatus, setMarketStatus] = useState("NSE bank EOD snapshot loading…");
  useEffect(() => {
    let active = true;
    fetch("data/bank-macro-latest.json", { cache: "no-store" })
      .then(response => { if (!response.ok) throw new Error("RBI macro snapshot unavailable"); return response.json(); })
      .then(data => {
        if (!active) return;
        const mapped: Record<string, any> = {};
        for (const row of data.factors ?? []) mapped[row.id] = row;
        setMacroRows(mapped);
        setMacroStatus("Official-source macro data updated " + (data.updatedAt ?? "date unavailable"));
      })
      .catch(error => { if (active) setMacroStatus(error instanceof Error ? error.message : "Macro data unavailable"); });
    fetch("data/bank-market-daily.json", { cache: "no-store" })
      .then(response => { if (!response.ok) throw new Error("NSE bank snapshot unavailable"); return response.json(); })
      .then(data => {
        if (!active) return;
        const mapped: Record<string, any> = {};
        for (const row of data.rows ?? []) mapped[row.symbol] = row;
        setMarketRows(mapped);
        setMarketStatus("NSE EOD · " + (data.marketDate ?? "history pending") + " · " + (data.sessionsAvailable ?? 0) + " sessions");
      })
      .catch(error => { if (active) setMarketStatus(error instanceof Error ? error.message : "NSE data unavailable"); });
    return () => { active = false; };
  }, []);
  const filteredBanks = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return BANK_STOCKS;
    return BANK_STOCKS.filter((bank) =>
      bank.name.toLowerCase().includes(query) || bank.symbol.toLowerCase().includes(query)
    );
  }, [search]);

  return <section className="panel bank-stocks">
    <p className="eyebrow">NIFTY 100 · BANKING STOCKS</p>
    <h2>Banking Stocks</h2>
    <p className="muted">NIFTY 100 में शामिल बैंकिंग शेयरों की सूची।</p>

    <section className="bank-layer-one" aria-labelledby="bank-layer-one-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">LAYER 1 · FUNDAMENTAL INTELLIGENCE</p><h3 id="bank-layer-one-title">Core Banking Factors</h3></div>
        <span>13 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_ONE_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span><div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <h4 className="bank-matrix-title">Bank-wise Fundamental Intelligence Matrix</h4>
      <p className="bank-layer-note">हर बैंक के सामने सभी 13 Layer 1 factors एक ही row में हैं। Verified financial-statement values जुड़ने तक cells खाली (—) रहेंगे।</p>
      <div className="table-wrap bank-table-wrap bank-layer-one-table-wrap">
        <table className="bank-data-table bank-layer-one-table">
          <thead><tr><th>Sr. No.</th><th>Bank Name</th><th>NSE Symbol</th>{LAYER_ONE_FACTORS.map((factor, index) => <th key={factor.name} title={factor.target}>{index + 1}. {factor.name}</th>)}</tr></thead>
          <tbody>{filteredBanks.map((bank) => <tr key={bank.symbol}><td>{BANK_STOCKS.findIndex((item) => item.symbol === bank.symbol) + 1}</td><td>{bank.name}</td><td><strong>{bank.symbol}</strong></td>{LAYER_ONE_FACTORS.map((factor) => <td key={factor.name}>—</td>)}</tr>)}</tbody>
        </table>
      </div>
      <p className="bank-layer-note">ये screening criteria हैं, verified bank-wise readings नहीं। Actual values, reporting period और source जुड़ने के बाद ही status या score दिखेगा। Thresholds को bank type और historical trend के अनुसार validate करना होगा।</p>
    </section>

    <section className="bank-layer-one bank-layer-two" aria-labelledby="bank-layer-two-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">LAYER 2 · MACRO &amp; EXTERNAL INTELLIGENCE</p><h3 id="bank-layer-two-title">Macro / External Factors</h3></div>
        <span>6 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_TWO_FACTORS.filter(factor => factor.id !== "analyst").map((factor, index) => {
          const reading = macroRows[factor.id];
          return <article className="bank-factor" key={factor.name}>
            <span className="bank-factor-number">{index + 2}</span><div><strong>{factor.name}</strong><small>Latest: {reading?.value ?? "—"}{reading?.unit ? " " + reading.unit : ""} · {reading?.asOf ?? "date unavailable"}</small>
              {(reading?.history ?? []).slice(1, 6).map((point: any) => <small key={point.date}>{point.date}: {point.value} {point.unit}</small>)}
              {reading?.sourceUrl && <a href={reading.sourceUrl} target="_blank" rel="noreferrer">Official source</a>}
            </div>
          </article>;
        })}
      </div>
      <section className="bank-data-section" aria-labelledby="bank-broker-reports-title">
        <div className="bank-layer-heading"><div><p className="eyebrow">BROKERAGE INTELLIGENCE</p><h4 id="bank-broker-reports-title">10 Banking Stocks — Upgrade / Downgrade &amp; Target Reports</h4></div><span>RESEARCH REPORTS</span></div>
        <p className="bank-layer-note">पहले केवल वे reports यहाँ हैं जिनमें broker की पुरानी और नई rating दोनों साफ दी गई हैं।</p>
        <div className="table-wrap bank-table-wrap"><table className="bank-data-table">
          <thead><tr><th>Bank</th><th>Broker</th><th>Date</th><th>Previous Rating</th><th>Current Rating</th><th>Action</th><th>Target (₹)</th><th>Source</th></tr></thead>
          <tbody>{(macroRows.analyst?.actionReports ?? []).map((item: any, index: number) => <tr key={item.symbol + "-" + index}><td>{item.bank} ({item.symbol})</td><td>{item.broker}</td><td>{item.date}</td><td>{item.previousRating}</td><td>{item.currentRating}</td><td><strong>{item.action}</strong></td><td>{item.target ?? "—"}</td><td><a href={item.sourceUrl} target="_blank" rel="noreferrer">{item.sourceName}</a></td></tr>)}</tbody>
        </table></div>
        <p className="bank-layer-note">इसके नीचे latest broker recommendations और target prices की पूरी उपलब्ध सूची है; केवल BUY/HOLD को rating change नहीं माना गया है।</p>
        <div className="table-wrap bank-table-wrap"><table className="bank-data-table">
          <thead><tr><th>Bank</th><th>Report Date</th><th>Broker</th><th>Rating</th><th>Target (₹)</th><th>Source</th></tr></thead>
          <tbody>{(macroRows.analyst?.reports ?? []).flatMap((bank: any) => (bank.items ?? []).map((item: any[], index: number) => <tr key={bank.symbol + "-" + index}><td>{bank.bank} ({bank.symbol})</td><td>{item[0]}</td><td>{item[1]}</td><td>{item[2]}</td><td>{item[3] ?? "—"}</td><td>{macroRows.analyst?.sourceUrl ? <a href={macroRows.analyst.sourceUrl} target="_blank" rel="noreferrer">Verify report</a> : "—"}</td></tr>))}</tbody>
        </table></div>
        {macroRows.analyst?.sourceUrl && <p className="bank-layer-note"><a href={macroRows.analyst.sourceUrl} target="_blank" rel="noreferrer">Broker research source and report archive</a></p>}
      </section>
      <p className="bank-layer-note" role="status">{macroStatus}. Macro cards में latest सहित पिछले उपलब्ध observations दिखते हैं। Credit growth fortnightly प्रकाशित होता है, इसलिए अभी पाँच verified observations उपलब्ध नहीं हैं; पुराने आंकड़े अनुमान से नहीं भरे गए हैं।</p>
    </section>

    <p className="bank-layer-note">Table columns: LTP = latest traded price; SMA = simple moving average; RSI uses 14-period daily and weekly candles. FII holding is shown for the latest three reported quarters. Values remain blank until a timestamped, verifiable market/data feed is connected.</p>
    <h3 className="bank-list-title">NIFTY 100 Banking Stocks</h3>
    <p className="bank-layer-note" role="status">{marketStatus}</p>
    <div className="bank-toolbar">
      <label>Search bank or NSE symbol
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="e.g. HDFC or SBIN" aria-label="Search banking stocks by bank name or NSE symbol" />
      </label>
      <p className="bank-layer-note" aria-live="polite">Showing {filteredBanks.length} of {BANK_STOCKS.length} banks</p>
    </div>
    <div className="table-wrap bank-table-wrap">
      <table className="bank-data-table">
        <thead>
          <tr><th rowSpan={2}>Serial No.</th><th rowSpan={2}>Bank Name</th><th rowSpan={2}>NSE Symbol</th><th rowSpan={2}>LTP</th><th rowSpan={2}>RS</th><th colSpan={2}>20 SMA</th><th colSpan={2}>50 SMA</th><th rowSpan={2}>RSI Daily</th><th rowSpan={2}>RSI Weekly</th></tr>
          <tr><th>Daily</th><th>Weekly</th><th>Daily</th><th>Weekly</th></tr>
        </thead>
        <tbody>{filteredBanks.map((bank) => <tr key={bank.symbol}><td>{BANK_STOCKS.findIndex((item) => item.symbol === bank.symbol) + 1}</td><td>{bank.name}</td><td><strong>{bank.symbol}</strong></td><td>{marketRows[bank.symbol]?.close ?? "—"}</td><td>—</td><td>{marketRows[bank.symbol]?.sma20Daily ?? "—"}</td><td>{marketRows[bank.symbol]?.sma20Weekly ?? "—"}</td><td>{marketRows[bank.symbol]?.sma50Daily ?? "—"}</td><td>{marketRows[bank.symbol]?.sma50Weekly ?? "—"}</td><td>—</td><td>—</td></tr>)}</tbody>
      </table>
    </div>

    <section className="bank-layer-one bank-data-section" aria-labelledby="bank-fii-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">OWNERSHIP INTELLIGENCE</p><h3 id="bank-fii-title">FII Holding — Last 3 Reported Quarters</h3></div>
        <span>QUARTERLY</span>
      </div>
      <p className="bank-layer-note">हर बैंक के लिए latest reported quarter और उससे पहले के दो quarters की FII shareholding (%)। Quarter labels, filing date और source verified filings से populate होंगे।</p>
      <div className="table-wrap bank-table-wrap">
        <table className="bank-data-table">
          <thead><tr><th>Serial No.</th><th>Bank Name</th><th>NSE Symbol</th><th>Latest Quarter FII %</th><th>Previous Quarter FII %</th><th>2 Quarters Back FII %</th><th>QoQ Change</th></tr></thead>
          <tbody>{filteredBanks.map((bank) => <tr key={bank.symbol}><td>{BANK_STOCKS.findIndex((item) => item.symbol === bank.symbol) + 1}</td><td>{bank.name}</td><td><strong>{bank.symbol}</strong></td><td>—</td><td>—</td><td>—</td><td>—</td></tr>)}</tbody>
        </table>
      </div>
    </section>

    <section className="bank-layer-one bank-data-section" aria-labelledby="bank-delivery-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">DELIVERY INTELLIGENCE</p><h3 id="bank-delivery-title">Daily Delivery Percentage</h3></div>
        <span>DAILY · EOD</span>
      </div>
      <p className="bank-layer-note">Delivery % = exchange-reported deliverable quantity ÷ traded quantity × 100. Latest session और previous sessions के आंकड़े date-stamped NSE bhavcopy से आएँगे; unavailable या invalid rows blank रहेंगी।</p>
      <div className="table-wrap bank-table-wrap">
        <table className="bank-data-table">
          <thead><tr><th>Serial No.</th><th>Bank Name</th><th>NSE Symbol</th><th>Latest Session Delivery %</th><th>Previous Session %</th><th>5-Session Average %</th><th>20-Session Average %</th></tr></thead>
          <tbody>{filteredBanks.map((bank) => <tr key={bank.symbol}><td>{BANK_STOCKS.findIndex((item) => item.symbol === bank.symbol) + 1}</td><td>{bank.name}</td><td><strong>{bank.symbol}</strong></td><td>{marketRows[bank.symbol]?.deliveryPct ?? "—"}</td><td>{marketRows[bank.symbol]?.deliveryPctPrevious ?? "—"}</td><td>{marketRows[bank.symbol]?.deliveryPct5SessionAvg ?? "—"}</td><td>{marketRows[bank.symbol]?.deliveryPct20SessionAvg ?? "—"}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  </section>;
}
