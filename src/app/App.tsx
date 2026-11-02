import { useEffect, useState } from "react";
import { listRecentImports, saveImportedRows, type ImportRecord } from "../data/importRepository";
import { readTabularFile, validatePreview, type TabularPreview } from "../data/tabularImport";
import { mapEquityEodRows, type Exchange } from "../data/eodMapping";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TabularPreview | null>(null);
  const [source, setSource] = useState("");
  const [marketDate, setMarketDate] = useState("");
  const [exchange, setExchange] = useState<Exchange>("NSE");
  const [imports, setImports] = useState<ImportRecord[]>([]);
  const [message, setMessage] = useState("कोई file import नहीं हुई है।");
  const [busy, setBusy] = useState(false);
  useEffect(() => { listRecentImports().then(setImports).catch(() => setMessage("Local database उपलब्ध नहीं है।")); }, []);
  async function selectFile(next: File | null) {
    setFile(next); setPreview(null);
    if (!next) return;
    setBusy(true); setMessage("File पढ़ी जा रही है…");
    try { const result = await readTabularFile(next); setPreview(result); setMessage(`${result.totalRows.toLocaleString()} rows मिलीं। Preview में अधिकतम 100 rows दिखाई जाएँगी।`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "File पढ़ने में समस्या हुई।"); }
    finally { setBusy(false); }
  }
  async function importFile() {
    if (!file || !preview) return;
    const errors = validatePreview(preview);
    if (errors.length) { setMessage(errors.join(" ")); return; }
    setBusy(true);
    try {
      const full = await readTabularFile(file);
      if (full.totalRows > 100) { setMessage("एक बार में अधिकतम 100 rows import होंगी। कृपया file को छोटे हिस्सों में बाँटें।"); return; }
      const mapped = mapEquityEodRows(full.rows, exchange, marketDate);
      if (!mapped.rows.length) { setMessage(`कोई valid EOD row नहीं मिली। Rejected rows: ${mapped.rejected.length}. Header mapping जाँचें।`); return; }
      const result = await saveImportedRows(mapped.rows as unknown as Record<string, unknown>[], file.name, source, marketDate);
      setImports(current => [result, ...current].slice(0, 20));
      setMessage(`Import पूरा: ${result.rowCount} normalized ${exchange} EOD rows save हुईं; ${mapped.rejected.length} rows reject हुईं। Status: Imported / unverified.`);
      setFile(null); setPreview(null);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Import असफल रहा।"); }
    finally { setBusy(false); }
  }
  return <main className="shell">
    <header><div className="mark">IM</div><div><p className="eyebrow">DATA FOUNDATION · BATCH 2</p><h1>Institutional Market Intelligence</h1><p className="muted">NSE / BSE EOD data mapping · local-first research workspace</p></div></header>
    <section className="panel">
      <p className="eyebrow">EXCHANGE DATA CENTRE</p><h2>NSE / BSE Equity EOD Import</h2>
      <p className="muted">Exchange की CSV या Excel file चुनें। Recognized exchange headers को standard EOD schema में map किया जाएगा। यह direct exchange feed नहीं है; user-provided file import है।</p>
      <div className="form-grid">
        <label>Exchange<select value={exchange} onChange={e=>setExchange(e.target.value as Exchange)}><option value="NSE">NSE</option><option value="BSE">BSE</option></select></label>
        <label>Source / file provider<input value={source} onChange={e=>setSource(e.target.value)} placeholder="उदा. NSE bhavcopy / BSE bhavcopy"/></label>
        <label>Import market date<input type="date" value={marketDate} onChange={e=>setMarketDate(e.target.value)}/></label>
      </div>
      <label className="file-picker">Select CSV / Excel file<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>void selectFile(e.target.files?.[0] ?? null)}/></label>
      <div className="notice" role="status">{busy ? "Processing…" : message}</div>
      {preview && <><div className="preview-head"><strong>Raw preview · {preview.totalRows} rows</strong><span>{preview.headers.length} columns</span></div><div className="table-wrap"><table><thead><tr>{preview.headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{preview.rows.slice(0,8).map((row,i)=><tr key={i}>{preview.headers.map(h=><td key={h}>{String(row[h] ?? "")}</td>)}</tr>)}</tbody></table></div><button disabled={busy || !source.trim() || !marketDate} onClick={()=>void importFile()}>Validate and import EOD rows</button></>}
    </section>
    <section className="panel history"><p className="eyebrow">LOCAL HISTORY</p><h2>Recent imports</h2>{imports.length ? <div className="table-wrap"><table><thead><tr><th>File</th><th>Source</th><th>Import date</th><th>Rows saved</th><th>Status</th></tr></thead><tbody>{imports.map(item=><tr key={item.id}><td>{item.fileName}</td><td>{item.sourceName}</td><td>{item.marketDate}</td><td>{item.rowCount}</td><td><span className="tag">Imported · unverified</span></td></tr>)}</tbody></table></div> : <p className="muted">अभी कोई saved import नहीं है।</p>}</section>
    <footer>Mapped fields: symbol, trade date, OHLC, previous close, last price, volume, traded value and trades. Unsupported layouts or invalid rows are rejected, not guessed. Imported records remain unverified until independently reconciled with an authoritative source. Browser storage clear करने पर local history मिट सकती है।</footer>
  </main>;
}
