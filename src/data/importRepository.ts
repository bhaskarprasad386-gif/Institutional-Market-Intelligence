import type { DataProvenance, Observation } from "../core/domain";
import { openLocalDatabase } from "./storage";

export interface ImportRecord { id: string; fileName: string; sourceName: string; marketDate: string; importedAt: string; rowCount: number; }
export async function saveImportedRows(rows: Record<string, unknown>[], fileName: string, sourceName: string, marketDate: string): Promise<ImportRecord> {
  if (!sourceName.trim()) throw new Error("Source name जरूरी है।");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(marketDate) || Number.isNaN(Date.parse(marketDate))) throw new Error("Market date YYYY-MM-DD में दें।");
  if (!rows.length) throw new Error("Import करने के लिए rows नहीं हैं।");
  const db = await openLocalDatabase();
  const importedAt = new Date().toISOString();
  const batchId = crypto.randomUUID();
  const provenance: DataProvenance = { sourceName: sourceName.trim(), marketDate, retrievedAt: importedAt, status: "imported" };
  const tx = db.transaction(["observations", "imports"], "readwrite");
  const observationStore = tx.objectStore("observations");
  rows.forEach((value, index) => {
    const observation: Observation<Record<string, unknown>> = { id: `${batchId}:${index}`, value, provenance };
    observationStore.put(observation);
  });
  const record: ImportRecord = { id: batchId, fileName, sourceName: sourceName.trim(), marketDate, importedAt, rowCount: rows.length };
  tx.objectStore("imports").put(record);
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("Import transaction failed."));
    tx.onabort = () => reject(tx.error ?? new Error("Import transaction aborted."));
  });
  db.close();
  return record;
}

export async function listRecentImports(): Promise<ImportRecord[]> {
  const db = await openLocalDatabase();
  const records = await new Promise<ImportRecord[]>((resolve, reject) => {
    const req = db.transaction("imports", "readonly").objectStore("imports").getAll();
    req.onsuccess = () => resolve((req.result as ImportRecord[]).sort((a,b) => b.importedAt.localeCompare(a.importedAt)).slice(0, 20));
    req.onerror = () => reject(req.error);
  });
  db.close();
  return records;
}
