import { useEffect, useState } from "react";
import { listRecentImports, saveImportedRows, type ImportRecord } from "../data/importRepository";
import { readTabularFile, validatePreview, type TabularPreview } from "../data/tabularImport";
import { mapEquityEodRows, type Exchange } from "../data/eodMapping";
import { mapFuturesRows } from "../modules/fo/mapping";
import { calculateFoMetrics, calculateRolloverFromRows, classifyPriceOi } from "../modules/fo/analytics";
import type { FoMetrics, RolloverMetric } from "../modules/fo/types";
import { calculateSectorMetrics, calculateInstitutionalFlow, validateDeliveryObservation } from "../modules/flows/analytics";
import { mapSectorRows, mapDeliveryRows, mapInstitutionalFlowRows } from "../modules/flows/mapping";
import type { SectorMetric, DeliveryObservation, InstitutionalFlowMetric } from "../modules/flows/types";
import { evaluateRecommendation, calculateCompanyResultMetrics } from "../modules/research/analytics";
import { mapRecommendationRows, mapCompanyResultRows } from "../modules/research/mapping";
import type { RecommendationEvaluation, CompanyResultMetric } from "../modules/research/types";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TabularPreview | null>(null);
  const [source, setSource] = useState("");
  const [marketDate, setMarketDate] = useState("");
  const [exchange, setExchange] = useState<Exchange>("NSE");
  const [foFile, setFoFile] = useState<File | null>(null);
  const [foMetrics, setFoMetrics] = useState<FoMetrics[]>([]);
  const [rolloverMetrics, setRolloverMetrics] = useState<RolloverMetric[]>([]);
  const [sectorFile, setSectorFile] = useState<File | null>(null);
  const [deliveryFile, setDeliveryFile] = useState<File | null>(null);
  const [flowFile, setFlowFile] = useState<File | null>(null);
  const [sectorMetrics, setSectorMetrics] = useState<SectorMetric[]>([]);
  const [deliveryRows, setDeliveryRows] = useState<DeliveryObservation[]>([]);
  const [flowMetrics, setFlowMetrics] = useState<InstitutionalFlowMetric[]>([]);
  const [researchFile, setResearchFile] = useState<File | null>(null);
  const [resultsFile, setResultsFile] = useState<File | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationEvaluation[]>([]);
  const [companyResults, setCompanyResults] = useState<CompanyResultMetric[]>([]);
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
    <header><div className="mark">IM</div><div><p className="eyebrow">DATA FOUNDATION · BATCH 2 / 3</p><h1>Institutional Market Intelligence</h1><p className="muted">NSE / BSE EOD data mapping · local-first research workspace</p></div></header>
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
    <section className="panel"><p className="eyebrow">F&O INTELLIGENCE · BATCH 3</p><h2>Futures OI / Cost of Carry Import</h2><p className="muted">Futures bhavcopy या अपने broker export से symbol, trade date, expiry, futures close, spot close और OI import करें। यह manual file import है; कोई live feed नहीं।</p><label className="file-picker">Select futures CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFoFile(e.target.files?.[0]??null)}/></label><button disabled={!foFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!foFile)return;setBusy(true);try{const parsed=await readTabularFile(foFile);const mapped=mapFuturesRows(parsed.rows);const valid=mapped.rows.filter(row=>row.tradeDate===marketDate);const rejected=mapped.rejected.length+mapped.rows.length-valid.length;if(!valid.length){setMessage("कोई valid futures row नहीं मिली; headers और selected market date जाँचें।");return;}const metrics=valid.map(calculateFoMetrics);const saved=await saveImportedRows(valid as unknown as Record<string,unknown>[],foFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setFoMetrics(metrics);setRolloverMetrics(calculateRolloverFromRows(valid));setMessage(`F&O import: ${valid.length} rows saved; ${rejected} rejected (including date mismatch). Status: Imported / unverified.`);setFoFile(null);}catch(error){setMessage(error instanceof Error?error.message:"F&O import failed.");}finally{setBusy(false);}}}>Validate and import futures data</button>{foMetrics.length>0&&<><h3>Calculated futures metrics</h3><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Expiry</th><th>Futures − Spot</th><th>Price change %</th><th>Build-up signal</th><th>Annualized CoC %</th><th>OI</th><th>OI change %</th><th>Days to expiry</th></tr></thead><tbody>{foMetrics.slice(0,50).map((m,i)=><tr key={m.symbol+i}><td>{m.symbol}</td><td>{m.expiryDate}</td><td>{m.basis.toFixed(2)}</td><td>{m.priceChangePct?.toFixed(2)??"—"}</td><td>{m.priceChangePct!==undefined&&m.oiChangePct!==undefined?classifyPriceOi(m.priceChangePct,m.oiChangePct).replaceAll("_"," "):"Insufficient history"}</td><td>{m.costOfCarryAnnualizedPct?.toFixed(2)??"—"}</td><td>{m.openInterest.toLocaleString()}</td><td>{m.oiChangePct?.toFixed(2)??"—"}</td><td>{m.daysToExpiry}</td></tr>)}</tbody></table></div>{rolloverMetrics.length>0&&<><h3>Expiry rollover (nearest two expiries)</h3><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Near expiry</th><th>Near OI</th><th>Next expiry</th><th>Next OI</th><th>Rollover %</th></tr></thead><tbody>{rolloverMetrics.map((r,i)=><tr key={r.symbol+i}><td>{r.symbol}</td><td>{r.nearExpiry}</td><td>{r.nearOi.toLocaleString()}</td><td>{r.nextExpiry}</td><td>{r.nextOi.toLocaleString()}</td><td>{r.rolloverPct.toFixed(2)}%</td></tr>)}</tbody></table></div></>}</>}</section>
    <section className="panel">
      <p className="eyebrow">SECTOR / DELIVERY / INSTITUTIONAL · BATCH 4</p><h2>Sector Rotation, Delivery & Institutional Flows</h2>
      <p className="muted">तीनों datasets user-supplied CSV/Excel से import होते हैं। Sector labels आपकी file से आते हैं; कोई sector mapping या FII/DII value अनुमान से नहीं बनाई जाती। Source और market date ऊपर दिए गए controls से लिए जाते हैं।</p>
      <h3>Sector rotation</h3>
      <p className="muted">Required columns: symbol, sector, trade date, close, previous close. Return equal-weighted constituent average है, index-weighted return नहीं।</p>
      <label className="file-picker">Select sector constituents CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setSectorFile(e.target.files?.[0]??null)}/></label>
      <button disabled={!sectorFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!sectorFile)return;setBusy(true);try{const parsed=await readTabularFile(sectorFile);const mapped=mapSectorRows(parsed.rows,marketDate);if(!mapped.rows.length){setMessage(`No valid sector rows; ${mapped.rejected.length} rejected. Check headers and date.`);return;}const metrics=calculateSectorMetrics(mapped.rows);const saved=await saveImportedRows(mapped.rows as unknown as Record<string,unknown>[],sectorFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setSectorMetrics(metrics);setMessage(`Sector import: ${mapped.rows.length} rows saved; ${mapped.rejected.length} rejected. Imported / unverified.`);setSectorFile(null);}catch(error){setMessage(error instanceof Error?error.message:"Sector import failed.");}finally{setBusy(false);}}}>Import sector data</button>
      {sectorMetrics.length>0&&<div className="table-wrap"><table><thead><tr><th>Sector</th><th>Constituents</th><th>Avg return %</th><th>Advancing</th><th>Declining</th><th>Traded value</th></tr></thead><tbody>{sectorMetrics.map((m,i)=><tr key={m.sector+i}><td>{m.sector}</td><td>{m.constituentCount}</td><td>{m.averageReturnPct.toFixed(2)}</td><td>{m.advancing}</td><td>{m.declining}</td><td>{m.tradedValue.toLocaleString()}</td></tr>)}</tbody></table></div>}
      <h3>Delivery scanner data</h3>
      <p className="muted">Required columns: symbol, date, close, volume, delivery quantity. Delivery percentage is calculated if absent and reconciled if supplied.</p>
      <label className="file-picker">Select delivery CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setDeliveryFile(e.target.files?.[0]??null)}/></label>
      <button disabled={!deliveryFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!deliveryFile)return;setBusy(true);try{const parsed=await readTabularFile(deliveryFile);const mapped=mapDeliveryRows(parsed.rows,marketDate);const valid:DeliveryObservation[]=[];for(const row of mapped.rows){try{valid.push(validateDeliveryObservation(row));}catch{}}if(!valid.length){setMessage(`No valid delivery rows; ${mapped.rejected.length + mapped.rows.length} rejected. Check delivery quantity / volume.`);return;}const saved=await saveImportedRows(valid as unknown as Record<string,unknown>[],deliveryFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setDeliveryRows(valid);setMessage(`Delivery import: ${valid.length} rows saved; ${mapped.rejected.length + mapped.rows.length-valid.length} rejected. Imported / unverified.`);setDeliveryFile(null);}catch(error){setMessage(error instanceof Error?error.message:"Delivery import failed.");}finally{setBusy(false);}}}>Import delivery data</button>
      {deliveryRows.length>0&&<div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Close</th><th>Volume</th><th>Delivery qty</th><th>Delivery %</th><th>Delivery value</th></tr></thead><tbody>{deliveryRows.slice(0,100).map((m,i)=><tr key={m.symbol+i}><td>{m.symbol}</td><td>{m.close.toFixed(2)}</td><td>{m.volume.toLocaleString()}</td><td>{m.deliveryQuantity.toLocaleString()}</td><td>{m.deliveryPct.toFixed(2)}%</td><td>{m.deliveryValue?.toLocaleString()??"—"}</td></tr>)}</tbody></table></div>}
      <h3>FII / DII cash market activity</h3>
      <p className="muted">Required columns: date, FII net, DII net. Default unit is ₹ crore only when no unit column is provided; confirm source file units before interpreting values.</p>
      <label className="file-picker">Select FII / DII CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFlowFile(e.target.files?.[0]??null)}/></label>
      <button disabled={!flowFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!flowFile)return;setBusy(true);try{const parsed=await readTabularFile(flowFile);const mapped=mapInstitutionalFlowRows(parsed.rows,marketDate);if(!mapped.rows.length){setMessage(`No valid FII/DII rows; ${mapped.rejected.length} rejected. Check headers and date.`);return;}const metrics=mapped.rows.map(calculateInstitutionalFlow);const saved=await saveImportedRows(mapped.rows as unknown as Record<string,unknown>[],flowFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setFlowMetrics(metrics);setMessage(`FII/DII import: ${mapped.rows.length} rows saved; ${mapped.rejected.length} rejected. Imported / unverified.`);setFlowFile(null);}catch(error){setMessage(error instanceof Error?error.message:"FII/DII import failed.");}finally{setBusy(false);}}}>Import institutional flow data</button>
      {flowMetrics.length>0&&<div className="table-wrap"><table><thead><tr><th>Date</th><th>FII net</th><th>FII direction</th><th>DII net</th><th>DII direction</th><th>Combined net</th><th>Unit</th></tr></thead><tbody>{flowMetrics.map((m,i)=><tr key={m.tradeDate+i}><td>{m.tradeDate}</td><td>{m.fiiNet.toLocaleString()}</td><td>{m.fiiDirection}</td><td>{m.diiNet.toLocaleString()}</td><td>{m.diiDirection}</td><td>{m.combinedNet.toLocaleString()}</td><td>{m.unit}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel">
      <p className="eyebrow">BROKER RESEARCH & COMPANY INTELLIGENCE · BATCH 5</p><h2>Broker Recommendations</h2>
      <p className="muted">Public broker/research reports को CSV/Excel में import करें। Required: broker, symbol, BUY/HOLD/SELL rating, published date. Target, published entry, stop-loss और source URL optional हैं। Platform कोई broker call या target स्वयं generate नहीं करता।</p>
      <label className="file-picker">Select broker research CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setResearchFile(e.target.files?.[0]??null)}/></label>
      <button disabled={!researchFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!researchFile)return;setBusy(true);try{const parsed=await readTabularFile(researchFile);const mapped=mapRecommendationRows(parsed.rows);const valid=mapped.rows.filter(row=>row.publishedDate<=marketDate);const rejected=mapped.rejected.length+mapped.rows.length-valid.length;if(!valid.length){setMessage(`No valid broker recommendations; ${rejected} rejected or after selected market date.`);return;}const saved=await saveImportedRows(valid as unknown as Record<string,unknown>[],researchFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setRecommendations(valid.map(evaluateRecommendation));setMessage(`Broker research: ${valid.length} recommendations saved; ${rejected} rejected/date-filtered. Imported / unverified.`);setResearchFile(null);}catch(error){setMessage(error instanceof Error?error.message:"Broker research import failed.");}finally{setBusy(false);}}}>Import broker recommendations</button>
      {recommendations.length>0&&<><h3>Imported recommendation register</h3><div className="table-wrap"><table><thead><tr><th>Broker</th><th>Symbol</th><th>Rating</th><th>Published</th><th>Target</th><th>Entry</th><th>Stop-loss</th><th>Observed return %</th><th>Evaluation</th><th>Source</th></tr></thead><tbody>{recommendations.map((r,i)=><tr key={r.broker+r.symbol+i}><td>{r.broker}</td><td>{r.symbol}</td><td>{r.rating}</td><td>{r.publishedDate}</td><td>{r.targetPrice??"—"}</td><td>{r.publishedEntry??"—"}</td><td>{r.publishedStopLoss??"—"}</td><td>{r.observedReturnPct?.toFixed(2)??"—"}</td><td>{r.evaluationStatus==="not_evaluated"?"Not evaluated":"Observed price only"}</td><td>{r.sourceUrl?<a href={r.sourceUrl} target="_blank" rel="noreferrer">Open report</a>:r.sourceTitle??"—"}</td></tr>)}</tbody></table></div><p className="muted">A single observed price cannot prove historical target/stop-loss hit. Price-path evaluation requires dated historical OHLC observations and is not claimed here.</p></>}
      <h2>Company Results & Guidance</h2>
      <p className="muted">Import published financials and prior-period / guidance values when available. Growth and actual-versus-guidance calculations appear only when both input values exist. Values and management commentary remain source-attributed, not independently verified.</p>
      <label className="file-picker">Select company results CSV / Excel<input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setResultsFile(e.target.files?.[0]??null)}/></label>
      <button disabled={!resultsFile||!source.trim()||!marketDate||busy} onClick={async()=>{if(!resultsFile)return;setBusy(true);try{const parsed=await readTabularFile(resultsFile);const mapped=mapCompanyResultRows(parsed.rows);const valid=mapped.rows.filter(row=>row.publishedDate<=marketDate);const rejected=mapped.rejected.length+mapped.rows.length-valid.length;if(!valid.length){setMessage(`No valid company result rows; ${rejected} rejected or after selected market date.`);return;}const saved=await saveImportedRows(valid as unknown as Record<string,unknown>[],resultsFile.name,source,marketDate);setImports(current=>[saved,...current].slice(0,20));setCompanyResults(valid.map(calculateCompanyResultMetrics));setMessage(`Company results: ${valid.length} rows saved; ${rejected} rejected/date-filtered. Imported / unverified.`);setResultsFile(null);}catch(error){setMessage(error instanceof Error?error.message:"Company results import failed.");}finally{setBusy(false);}}}>Import company results</button>
      {companyResults.length>0&&<div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Period</th><th>Revenue</th><th>Revenue growth %</th><th>EBITDA</th><th>EBITDA growth %</th><th>PAT</th><th>PAT growth %</th><th>EPS</th><th>EPS growth %</th><th>Operating margin %</th><th>Net margin %</th><th>Debt</th><th>Operating cash flow</th><th>Free cash flow</th><th>Revenue vs guidance %</th><th>EBITDA vs guidance %</th><th>PAT vs guidance %</th></tr></thead><tbody>{companyResults.map((r,i)=><tr key={r.symbol+r.period+i}><td>{r.symbol}</td><td>{r.period}</td><td>{r.revenue??"—"}</td><td>{r.revenueGrowthPct?.toFixed(2)??"—"}</td><td>{r.ebitda??"—"}</td><td>{r.ebitdaGrowthPct?.toFixed(2)??"—"}</td><td>{r.pat??"—"}</td><td>{r.patGrowthPct?.toFixed(2)??"—"}</td><td>{r.eps??"—"}</td><td>{r.epsGrowthPct?.toFixed(2)??"—"}</td><td>{r.operatingMarginPct??"—"}</td><td>{r.netMarginPct??"—"}</td><td>{r.debt??"—"}</td><td>{r.operatingCashFlow??"—"}</td><td>{r.freeCashFlow??"—"}</td><td>{r.revenueVsGuidancePct?.toFixed(2)??"—"}</td><td>{r.ebitdaVsGuidancePct?.toFixed(2)??"—"}</td><td>{r.patVsGuidancePct?.toFixed(2)??"—"}</td></tr>)}</tbody></table></div>}
      {companyResults.some(r=>r.guidanceText||r.managementCommentary)&&<div className="notice"><strong>Management commentary / guidance</strong>{companyResults.filter(r=>r.guidanceText||r.managementCommentary).map((r,i)=><p key={r.symbol+i}>{r.symbol} · {r.period}: {r.guidanceText??""} {r.managementCommentary??""}</p>)}</div>}
    </section>
    <section className="panel history"><p className="eyebrow">LOCAL HISTORY</p><h2>Recent imports</h2>{imports.length ? <div className="table-wrap"><table><thead><tr><th>File</th><th>Source</th><th>Import date</th><th>Rows saved</th><th>Status</th></tr></thead><tbody>{imports.map(item=><tr key={item.id}><td>{item.fileName}</td><td>{item.sourceName}</td><td>{item.marketDate}</td><td>{item.rowCount}</td><td><span className="tag">Imported · unverified</span></td></tr>)}</tbody></table></div> : <p className="muted">अभी कोई saved import नहीं है।</p>}</section>
    <footer>Mapped fields: symbol, trade date, OHLC, previous close, last price, volume, traded value and trades. Unsupported layouts or invalid rows are rejected, not guessed. Imported records remain unverified until independently reconciled with an authoritative source. Browser storage clear करने पर local history मिट सकती है।</footer>
  </main>;
}
