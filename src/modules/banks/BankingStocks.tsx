import { useMemo, useState } from "react";

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
  { name: "Jefferies / Global Analyst Reports", target: "Upgrade / downgrade and estimate revisions" },
  { name: "RBI Fortnightly Credit Growth", target: "12–15% reference; compare current trend" },
  { name: "10-Year Government Bond Yield", target: "Yield movement and bank treasury impact" },
  { name: "RBI Repo Rate Scenario", target: "Current policy rate and direction" },
  { name: "RBI LTRO / Liquidity Window", target: "Policy announcements and liquidity impact" },
  { name: "Sixth Macro / External Factor", target: "Not specified in supplied matrix" }
];

const LAYER_THREE_FACTORS = [
  { name: "Foreign Room Availability", target: "FPI headroom / ownership limit" },
  { name: "Liquidity Coverage Ratio (LCR)", target: "120%–135% reference; verify RBI rules" },
  { name: "Risk-Weighted Assets (RWA) Optimization", target: "Capital efficiency and risk mix" },
  { name: "Insider Buying", target: "Disclosed insider purchases" },
  { name: "Bulk / Block Deals", target: "Exchange-disclosed large transactions" },
  { name: "FII Positions Matrix", target: "Available disclosed institutional positioning" },
  { name: "MSCI / FTSE Inflows", target: "Index inclusion, weight changes and flows" },
  { name: "Off-Market Clearing", target: "Verified disclosed transfer activity" },
  { name: "SLB Short Recall", target: "Stock-lending availability / recall data" },
  { name: "Margin Stress", target: "Margin requirements and stress indicators" },
  { name: "Custodian Fails", target: "Settlement-fail data, if accessible" },
  { name: "Asset Repricing", target: "Material disclosed asset valuation changes" },
  { name: "Iceberg Orders", target: "Only where reliable order-book evidence exists" },
  { name: "Pool Transfer", target: "Verified depository / settlement disclosures" },
  { name: "FPI Re-classification", target: "Official ownership-category changes" },
  { name: "Clearing Stress", target: "Clearing and settlement risk indicators" },
  { name: "P-Notes / ODI Flow", target: "Published regulatory / market disclosures" },
  { name: "OTC Swap Unwind", target: "Only verified reported activity" },
  { name: "Float Reduction", target: "Change in tradable public float" },
  { name: "ADR / GDR Premium", target: "Where a comparable listed instrument exists" },
  { name: "RBI Ban Status", target: "Official RBI restrictions / supervisory notices" }
];


const LAYER_FOUR_FACTORS = [
  { name: "Relative Strength", target: "Bank stock performance versus NIFTY 100 / sector benchmark" },
  { name: "Quiet Price + High Delivery %", target: "Price compression with elevated delivery; confirm volume and multi-session context" },
  { name: "Positional Rollover", target: "F&O rollover quantity and cost; distinguish fresh positions from rollovers" },
  { name: "RSI — Daily", target: "14-period RSI on daily candles" },
  { name: "RSI — Weekly", target: "14-period RSI on weekly candles" }
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
      <p className="bank-layer-note">ये screening criteria हैं, verified bank-wise readings नहीं। Actual values, reporting period और source जुड़ने के बाद ही status या score दिखेगा। Thresholds को bank type और historical trend के अनुसार validate करना होगा।</p>
    </section>

    <section className="bank-layer-one bank-layer-two" aria-labelledby="bank-layer-two-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">LAYER 2 · MACRO &amp; EXTERNAL INTELLIGENCE</p><h3 id="bank-layer-two-title">Macro / External Factors</h3></div>
        <span>6 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_TWO_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span><div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <p className="bank-layer-note">दिए गए screenshots में छह factors की category बताई गई है, लेकिन केवल पाँच के नाम स्पष्ट हैं। छठे factor का नाम मिलने तक placeholder रखा गया है। Current macro values official source और reporting date के साथ ही अपडेट होंगे।</p>
    </section>

    <section className="bank-layer-one bank-layer-three" aria-labelledby="bank-layer-three-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">LAYER 3 · INSTITUTIONAL &amp; HIDDEN FLOW INTELLIGENCE</p><h3 id="bank-layer-three-title">Institutional / Hidden Liquidity Factors</h3></div>
        <span>21 VISIBLE ITEMS · SOURCE SAYS 20</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_THREE_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span><div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <p className="bank-layer-note">आपके screenshots में इस category को 20 factors कहा गया है, लेकिन दिखाई देने वाली numbering से 21 entries मिलती हैं। सभी 21 visible entries सुरक्षित रखी गई हैं; final Mother Matrix count reconcile होने तक count mismatch स्पष्ट रखा है। कुछ indicators का granular data public नहीं होता—ऐसे मामलों में अनुमानित value या fabricated signal नहीं दिखेगा।</p>
    </section>


    <section className="bank-layer-one bank-layer-four" aria-labelledby="bank-layer-four-title">
      <div className="bank-layer-heading">
        <div><p className="eyebrow">LAYER 4 · MARKET FOOTPRINT</p><h3 id="bank-layer-four-title">Price, Delivery &amp; Positioning Factors</h3></div>
        <span>5 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_FOUR_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span><div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <p className="bank-layer-note">Delivery percentage या rollover अकेले accumulation / bullish signal नहीं हैं। इन्हें traded volume, price trend, futures open interest, expiry और multi-session history के साथ verify करना होगा। जिन stocks में F&amp;O उपलब्ध नहीं है, वहाँ positional rollover लागू नहीं होगा।</p>
    </section>

    <p className="bank-layer-note">Table columns: LTP = latest traded price; FII Position = stock-specific disclosed FII holding / activity trend (Positive / Negative); RS = relative strength versus the selected benchmark (Positive / Negative); RSI uses 14-period daily and weekly candles. Values remain blank until a timestamped, verifiable market/data feed is connected.</p>
    <h3 className="bank-list-title">NIFTY 100 Banking Stocks</h3>
    <div className="bank-toolbar">
      <label>Search bank or NSE symbol
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="e.g. HDFC or SBIN" aria-label="Search banking stocks by bank name or NSE symbol" />
      </label>
      <p className="bank-layer-note" aria-live="polite">Showing {filteredBanks.length} of {BANK_STOCKS.length} banks</p>
    </div>
    <div className="table-wrap bank-table-wrap">
      <table className="bank-data-table">
        <thead><tr><th>Serial No.</th><th>Bank Name</th><th>NSE Symbol</th><th>LTP</th><th>FII Position</th><th>RS</th><th>RSI Daily</th><th>RSI Weekly</th></tr></thead>
        <tbody>{filteredBanks.map((bank) => <tr key={bank.symbol}><td>{BANK_STOCKS.findIndex((item) => item.symbol === bank.symbol) + 1}</td><td>{bank.name}</td><td><strong>{bank.symbol}</strong></td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>)}</tbody>
      </table>
    </div>
  </section>;
}
