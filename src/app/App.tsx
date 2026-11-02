import { useEffect, useState } from "react";
import { listRecentImports, saveImportedRows, type ImportRecord } from "../data/importRepository";
import { readTabularFile, validatePreview, type TabularPreview } from "../data/tabularImport";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TabularPreview | null>(null);
  const [source, setSource] = useState("");
  const [marketDate, setMarketDate] = useState("");
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
      const result = await saveImportedRows(full.rows, file.name, source, marketDate);
      setImports(current => [result, ...current].slice(0, 20));
      setMessage(`Import सफल: ${result.rowCount} rows local browser storage में save हुईं। Status: Imported / unverified.`);
      setFile(null); setPreview(null);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Import असफल रहा।"); }
    finally { setBusy(false); }
  }
  return <main className="shell">
    <header><div className="mark">IM</div><div><p className="eyebrow">DATA FOUNDATION · BATCH 1</p><h1>Institutional Market Intelligence</h1><p className="muted">EOD research workspace · local-first data management</p></div></header>
    <section className="panel">
      <p className="eyebrow">DATA CENTRE</p><h2>CSV / Excel Import</h2>
      <p className="muted">अपनी CSV, XLSX या XLS file चुनें। Data इसी browser के IndexedDB में रहेगा; किसी backend server पर upload नहीं होगा।</p>
      <div className="form-grid">
        <label>Source / file provider<input value={source} onChange={e=>setSource(e.target.value)} placeholder="उदा. NSE bhavcopy / broker export"/></label>
        <label>Market date<input type="date" value={marketDate} onChange={e=>setMarketDate(e.target.value)}/></label>
      </div>
      <label className="file-picker">Select CSV / Excel file<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>void selectFile(e.target.files?.[0] ?? null)}/></label>
      <div className="notice" role="status">{busy ? "Processing…" : message}</div>
      {preview && <><div className="preview-head"><strong>Preview · {preview.totalRows} rows</strong><span>{preview.headers.length} columns</span></div><div className="table-wrap"><table><thead><tr>{preview.headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{preview.rows.slice(0,8).map((row,i)=><tr key={i}>{preview.headers.map(h=><td key={h}>{String(row[h] ?? "")}</td>)}</tr>)}</tbody></table></div><button disabled={busy || !source.trim() || !marketDate} onClick={()=>void importFile()}>Import to this browser</button></>}
    </section>
    <section className="panel history"><p className="eyebrow">LOCAL HISTORY</p><h2>Recent imports</h2>{imports.length ? <div className="table-wrap"><table><thead><tr><th>File</th><th>Source</th><th>Market date</th><th>Rows</th><th>Status</th></tr></thead><tbody>{imports.map(item=><tr key={item.id}><td>{item.fileName}</td><td>{item.sourceName}</td><td>{item.marketDate}</td><td>{item.rowCount}</td><td><span className="tag">Imported · unverified</span></td></tr>)}</tbody></table></div> : <p className="muted">अभी कोई saved import नहीं है।</p>}</section>
    <footer>Data is local to this browser profile. Imported files are not independently verified. Browser storage clear करने पर local history मिट सकती है। Live NSE/BSE connectors अभी enabled नहीं हैं; कोई market signal generate नहीं होता।</footer>
  </main>;
}
