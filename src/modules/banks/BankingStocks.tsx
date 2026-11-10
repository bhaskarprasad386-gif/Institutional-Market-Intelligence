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
