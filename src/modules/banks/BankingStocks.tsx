type Props = { futures: unknown[]; status: string };

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
