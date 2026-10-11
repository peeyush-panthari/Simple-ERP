/**
 * The CSV bulk-upload dialog every module shares: pick/drop a CSV, POST its
 * text as `csvContent`, show a per-row (or per-group) result table and offer
 * the failed rows back as a CSV. Replaces the near-identical dialog each
 * Reflex state module carried its own copy of.
 */
import { Upload } from "lucide-react";
import { useState, type DragEvent } from "react";
import { ActionButton, DataTable, InlineError, Modal, Pill } from "@/components/erp/ui";
import { downloadText, errorCsv, type BulkResult } from "@/lib/csv";
import { useAuth } from "@/lib/auth";
import { useAsyncAction } from "@/lib/hooks";

interface BulkResponse {
  summary?: { successCount?: number; errorCount?: number; totalRows?: number; totalGroups?: number };
  results?: BulkResult[];
}

export function BulkUploadDialog({
  open,
  onClose,
  title,
  description,
  endpoint,
  sampleCsv,
  sampleFilename,
  errorFilename,
  columns,
  labelHeader,
  labelKey,
  labelFallbackKey,
  successKey,
  successText,
  verb = "created",
  noun,
  multiRow = false,
  wide = false,
  onCompleted,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  endpoint: string;
  sampleCsv: string;
  sampleFilename: string;
  errorFilename: string;
  /** The CSV's own columns - the error file repeats them, then adds `error`. */
  columns: string[];
  /** Header + result key for the identifying column ("Legal name" / legalName). */
  labelHeader: string;
  labelKey: string;
  /** Used when the row has no `labelKey` value (BOM upload: product name, else SKU). */
  labelFallbackKey?: string;
  /** Result key shown on success (the created code/number). */
  successKey: string;
  /** Fixed (or computed) success text instead of a result key. */
  successText?: string | ((r: BulkResult) => string);
  /** "created" in "N of M parties created successfully". */
  verb?: string;
  /** "parties created successfully" -> noun = "parties". */
  noun: string;
  multiRow?: boolean;
  wide?: boolean;
  onCompleted?: () => void;
}) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [result, setResult] = useState<BulkResponse | null>(null);

  const reset = () => {
    setFilename("");
    setContent("");
    setResult(null);
    setError("");
  };
  const close = () => {
    reset();
    onClose();
  };

  const load = async (file: File | undefined) => {
    if (!file) return;
    try {
      const text = (await file.text()).replace(/^﻿/, "");
      setFilename(file.name);
      setContent(text);
      setError("");
      setResult(null);
    } catch {
      setError("Could not read the file as text — please upload a plain CSV file");
    }
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    void load(e.dataTransfer.files[0]);
  };

  const submit = async () => {
    if (!content) {
      setError("Select a CSV file first");
      return;
    }
    setResult(null);
    const resp = await run(() => api<BulkResponse>("POST", endpoint, { json: { csvContent: content } }));
    if (resp) {
      setResult(resp);
      onCompleted?.();
    }
  };

  const results = result?.results ?? [];
  const summary = result?.summary;
  const total = summary?.totalRows ?? summary?.totalGroups ?? 0;
  const failedCsv = errorCsv(columns, results, multiRow);

  return (
    <Modal open={open} onClose={close} title={title} wide={wide} description={description}>
      <div className="flex flex-col gap-3">
        <div className="flex justify-end">
          <ActionButton size="sm" tone="ghost" onClick={() => downloadText(sampleCsv, sampleFilename)}>
            Download sample CSV
          </ActionButton>
        </div>
        <InlineError message={error} />
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          className="flex cursor-pointer flex-col items-center gap-1 rx-upload text-center text-sm hover:bg-[var(--secondary)]"
        >
          <span>Drag &amp; drop a CSV file here, or click to select</span>
          {filename && <span className="font-bold">Selected: {filename}</span>}
          <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => void load(e.target.files?.[0])} />
        </label>
        <div className="flex justify-end">
          <ActionButton onClick={submit} disabled={!filename} loading={busy}>
            {busy ? "Processing…" : "Process upload"}
          </ActionButton>
        </div>
        {result && (
          <div className="flex flex-col gap-2 border-t border-[var(--border)] pt-3">
            <p className="text-sm font-bold">{summary?.successCount ?? 0} of {total} {noun} {verb} successfully.</p>
            <DataTable columns={["Row", labelHeader, "Status", "Result / Error"]} minWidth={0} fit>
              {results.map((r, i) => (
                <tr key={i}>
                  <td>{r.row ?? i + 1}</td>
                  <td>{String(r[labelKey] || (labelFallbackKey ? r[labelFallbackKey] : "") || "")}</td>
                  <td><Pill>{r.status}</Pill></td>
                  <td>{r.status === "success" ? (typeof successText === "function" ? successText(r) : (successText ?? String(r[successKey] ?? ""))) : r.error}</td>
                </tr>
              ))}
            </DataTable>
            {failedCsv && (
              <div>
                <ActionButton size="sm" tone="danger" onClick={() => downloadText(failedCsv, errorFilename)}>
                  Download error file
                </ActionButton>
              </div>
            )}
          </div>
        )}
        <div className="flex justify-end">
          <ActionButton tone="ghost" onClick={close}>Close</ActionButton>
        </div>
      </div>
    </Modal>
  );
}

/** The one "Bulk Upload" button: same look, size, icon and wording on every page (`label` only where a page has several, e.g. Transfers / Adjustments). */
export function BulkUploadButton({ onClick, label = "Bulk Upload" }: { onClick: () => void; label?: string }) {
  return (
    <ActionButton onClick={onClick}>
      <Upload size={15} aria-hidden />
      {label}
    </ActionButton>
  );
}
