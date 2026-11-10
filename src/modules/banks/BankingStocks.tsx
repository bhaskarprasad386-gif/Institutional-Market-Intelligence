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
\nconst BANK_STOCKS = [
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
  return <section className="panel bank-stocks">
    <p className="eyebrow">NIFTY 100 · BANKING STOCKS</p>
    <h2>Banking Stocks</h2>
    <p className="muted">NIFTY 100 में शामिल बैंकिंग शेयरों की सूची।</p>

    <section className="bank-layer-one" aria-labelledby="bank-layer-one-title">
      <div className="bank-layer-heading">
        <div>
          <p className="eyebrow">LAYER 1 · FUNDAMENTAL INTELLIGENCE</p>
          <h3 id="bank-layer-one-title">Core Banking Factors</h3>
        </div>
        <span>13 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_ONE_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span>
          <div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <p className="bank-layer-note">ये screening criteria हैं, किसी बैंक के verified live/quarterly readings नहीं। Actual values, reporting period और source data जुड़ने के बाद ही factor status या score दिखाया जाएगा। Thresholds को bank type और historical trend के अनुसार validate करना होगा।</p>
    </section>


    <section className="bank-layer-one bank-layer-two" aria-labelledby="bank-layer-two-title">
      <div className="bank-layer-heading">
        <div>
          <p className="eyebrow">LAYER 2 · MACRO &amp; EXTERNAL INTELLIGENCE</p>
          <h3 id="bank-layer-two-title">Macro / External Factors</h3>
        </div>
        <span>6 FACTORS</span>
      </div>
      <div className="bank-factor-grid">
        {LAYER_TWO_FACTORS.map((factor, index) => <article className="bank-factor" key={factor.name}>
          <span className="bank-factor-number">{index + 1}</span>
          <div><strong>{factor.name}</strong><small>{factor.target}</small></div>
        </article>)}
      </div>
      <p className="bank-layer-note">दिए गए screenshots में छह factors की category बताई गई है, लेकिन केवल पाँच के नाम स्पष्ट हैं। छठे factor का नाम मिलने तक उसे placeholder रखा गया है। Repo rate और bond yield जैसे आंकड़े current official source तथा reporting date के साथ ही अपडेट होंगे।</p>
    </section>

    <h3 className="bank-list-title">NIFTY 100 Banking Stocks</h3>
    <div className="table-wrap">
      <table>
        <thead><tr><th>Serial No.</th><th>Bank Name</th><th>NSE Symbol</th></tr></thead>
        <tbody>{BANK_STOCKS.map((bank, index) => <tr key={bank.symbol}>
          <td>{index + 1}</td>
          <td>{bank.name}</td>
          <td><strong>{bank.symbol}</strong></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>;
}
