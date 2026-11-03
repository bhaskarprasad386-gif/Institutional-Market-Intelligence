import { useEffect, useState } from "react";
import { downloadRawLmeFile, listRawLmeFiles, type RawLmeFileRecord } from "../../data/rawLmeArchive";

const sources = [
  { name: "Daily Stocks Breakdown", cadence: "Daily · T+2", access: "LME account login / registration", url: "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Stock-breakdown-report", fields: "Opening / closing stocks, live & cancelled warrants, delivered in/out, metal and warehouse location" },
  { name: "Daily Off-Warrant Stocks", cadence: "Daily · T+3 delayed", access: "LME website login / registration; T+1 is paid subscription", url: "https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/off-warrant-stock-reporting", fields: "Off-warrant stocks by metal, region and location" },
  { name: "Warehouse & Queue", cadence: "Monthly · around T+10", access: "LME account login / registration", url: "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Warehouse-and-queue-data", fields: "Warehouse-company stocks, deliveries in/out and queue waiting time" },
  { name: "Location Capacity", cadence: "Quarterly", access: "LME account login / registration", url: "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports", fields: "Approved warehouse location storage capacity" },
  { name: "Country of Origin Stocks", cadence: "Monthly · around T+10", access: "LME account login / registration", url: "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports", fields: "Open tonnage by country of origin and metal" },
  { name: "Official / Closing Prices", cadence: "Day-delayed on LME.com", access: "Registration; some datasets licensed", url: "https://www.lme.com/market-data/reports-and-data", fields: "Cash, 3M and closing reference prices" },
  { name: "Volumes & Open Interest", cadence: "Daily / monthly reports", access: "Report-specific website access", url: "https://www.lme.com/market-data/reports-and-data", fields: "Trading volumes, exchange and market open interest" },
  { name: "Commitments of Traders (CoTR)", cadence: "Weekly · T+2", access: "LME account login / registration", url: "https://www.lme.com/market-data/reports-and-data", fields: "Aggregate long / short positioning across four participant categories" }
];

export default function LmeDataSources() {
  const [files, setFiles] = useState<Omit<RawLmeFileRecord, "file">[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { listRawLmeFiles().then(setFiles).catch(e => setError(e instanceof Error ? e.message : "Raw archive unavailable.")); }, []);
  return <section className="lme-source-catalog">
    <h3>Official LME raw-data source catalogue</h3>
    <p className="muted">Source coverage and publication lag are shown separately. The app does not bypass LME login, licensing or download controls. After downloading an authorized report, import its original file below—the unchanged file is archived locally before our calculations.</p>
    <div className="lme-fetch-status" role="status">
      <div className="lme-fetch-status-head"><strong>Automated source check · Warehouse & Queue</strong><span className="lme-access-tag">REGISTERED ACCESS REQUIRED</span></div>
      <p><strong>Last checked:</strong> 3 Nov 2026 · GitHub Actions runner received HTTP 403 from the official LME report page.</p>
      <p><strong>Raw report fetched:</strong> No. No inventory values or signals were generated from this attempt.</p>
      <p>Next step: sign in or register on LME.com, download the authorized XLSX, then import it below. Automated unauthenticated collection will remain disabled until LME provides an authorized access method.</p>
      <a href="https://github.com/bhaskarprasad386-gif/Institutional-Market-Intelligence/actions/runs/41559009593" target="_blank" rel="noreferrer">View verified collector run ↗</a>
      <span className="lme-source-footnote">The workflow completed successfully because it recorded the access restriction correctly; that does not mean an XLSX was downloaded.</span>
    </div>
    <div className="table-wrap"><table><thead><tr><th>Raw report</th><th>Publication</th><th>Access</th><th>Raw fields</th><th>Official source</th></tr></thead><tbody>
      {sources.map(item => <tr key={item.name}><td><strong>{item.name}</strong></td><td>{item.cadence}</td><td>{item.access}</td><td>{item.fields}</td><td><a href={item.url} target="_blank" rel="noreferrer">Open LME report ↗</a></td></tr>)}
    </tbody></table></div>
    <h3>Original raw-file archive · this browser</h3>
    <p className="muted">Raw files stay in this browser’s IndexedDB and are not uploaded to the public GitHub repository. Keep a separate backup; clearing browser data can remove this archive.</p>
    {error && <div className="notice">{error}</div>}
    {files.length ? <div className="table-wrap"><table><thead><tr><th>Original file</th><th>Source</th><th>Market date</th><th>Size</th><th>Archived</th><th>Action</th></tr></thead><tbody>
      {files.map(file => <tr key={file.id}><td>{file.fileName}</td><td>{file.sourceName}</td><td>{file.marketDate}</td><td>{(file.sizeBytes / 1024).toFixed(1)} KB</td><td>{new Date(file.archivedAt).toLocaleString()}</td><td><button type="button" onClick={() => void downloadRawLmeFile(file.id).catch(e => setError(e instanceof Error ? e.message : "Download failed."))}>Download raw</button></td></tr>)}
    </tbody></table></div> : <p className="muted">अभी कोई original LME raw file archive नहीं हुई है।</p>}
  </section>;
}
