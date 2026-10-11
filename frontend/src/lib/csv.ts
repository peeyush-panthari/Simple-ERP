/** CSV helpers shared by every module's bulk-upload dialog. */

function cell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

export function toCsv(columns: string[], rows: Record<string, unknown>[]): string {
  return [columns.join(","), ...rows.map((r) => columns.map((c) => cell(r[c])).join(","))].join("\r\n") + "\r\n";
}

export interface BulkResult {
  row?: number;
  status: "success" | "error" | string;
  error?: string | null;
  rowData?: Record<string, unknown>;
  rows?: Record<string, unknown>[];
  [k: string]: unknown;
}

/**
 * The original row data plus why each failed, as a downloadable CSV. `multiRow`:
 * each result carries a group's rows under `rows` (orders/POs, GRN/QC line
 * batches) - one CSV line per row, all sharing that result's error.
 */
export function errorCsv(columns: string[], results: BulkResult[], multiRow = false): string | null {
  const failed = results.filter((r) => r.status === "error");
  if (!failed.length) return null;
  const lines: Record<string, unknown>[] = [];
  for (const r of failed) {
    const rows = multiRow ? (r.rows?.length ? r.rows : [{}]) : [r.rowData ?? {}];
    for (const row of rows) lines.push({ ...row, error: r.error ?? "" });
  }
  return toCsv([...columns, "error"], lines);
}

export function downloadText(text: string, filename: string, mime = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
