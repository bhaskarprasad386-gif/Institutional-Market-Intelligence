import * as XLSX from "xlsx";

export interface TabularPreview { headers: string[]; rows: Record<string, unknown>[]; totalRows: number; }
const MAX_FILE_BYTES = 15 * 1024 * 1024;
const MAX_IMPORT_ROWS = 50000;
const MAX_IMPORT_COLUMNS = 250;

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some(value => value.trim() !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (quoted) throw new Error("CSV में closing quote नहीं मिला।");
  row.push(cell);
  if (row.some(value => value.trim() !== "")) rows.push(row);
  return rows;
}

export async function readTabularFile(file: File): Promise<TabularPreview> {
  if (file.size > MAX_FILE_BYTES) throw new Error("File 15 MB से बड़ी है।");
  const ext = file.name.toLowerCase().split(".").pop();
  let matrix: unknown[][];
  if (ext === "csv") {
    const raw = await file.text();
    matrix = parseCsv(raw.replace(/^\uFEFF/, ""));
  } else if (ext === "xlsx" || ext === "xls") {
    const bytes = await file.arrayBuffer();
    const workbook = XLSX.read(bytes, { type: "array", cellDates: true, sheetRows: MAX_IMPORT_ROWS + 1 });
    const first = workbook.SheetNames[0];
    if (!first) throw new Error("Workbook में कोई sheet नहीं मिली।");
    matrix = XLSX.utils.sheet_to_json<unknown[]>(workbook.Sheets[first], { header: 1, raw: true, defval: "" });
  } else throw new Error("केवल CSV, XLSX या XLS file स्वीकार है।");
  if (matrix.length < 2) throw new Error("कम-से-कम header और एक data row जरूरी है।");
  if ((matrix[0] ?? []).length > MAX_IMPORT_COLUMNS) throw new Error("एक file में अधिकतम 250 columns स्वीकार हैं।");
  const headers = (matrix[0] ?? []).map((v, i) => String(v ?? "").trim() || `column_${i + 1}`);
  if (new Set(headers).size !== headers.length) throw new Error("Duplicate column headers मिले।");
  const data = matrix.slice(1).filter(row => row.some(v => String(v ?? "").trim() !== ""));
  if (!data.length) throw new Error("File में कोई data row नहीं मिली।");
  if (data.length > MAX_IMPORT_ROWS) throw new Error("एक file में अधिकतम 50,000 rows स्वीकार हैं।");
  const rows = data.map(row => Object.fromEntries(headers.map((h, i) => [h, row[i] ?? ""])));
  return { headers, rows, totalRows: data.length };
}

export function validatePreview(preview: TabularPreview): string[] {
  const errors: string[] = [];
  if (!preview.headers.length) errors.push("Header row खाली है।");
  if (preview.totalRows === 0) errors.push("कोई data row नहीं है।");
  return errors;
}
