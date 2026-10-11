/**
 * Purchase order, after issue: the vendor's acknowledgement, the documents they send (proforma invoice, technical papers...) and
 * their dispatch documentation (transport, e-way bill, packing list, delivery challan) - the steps between the PO and the GRN.
 * The buyer records these from the vendor's emails and papers; there is no vendor login.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ReasonDialog } from "@/components/erp/dialogs";
import { trimDecimal } from "@/components/erp/requisitions";
import {
  ActionButton, DataTable, Field, InlineError, Modal, Note, Pill, SelectInput, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, useAsyncAction } from "@/lib/hooks";
import { MAX_UPLOAD_BYTES, readBase64 } from "@/lib/production";
import type { Tone } from "@/lib/status";

const PO_BASE = "/api/v1/purchase-orders";

interface Ack {
  status: string;
  date?: string | null;
  ref?: string | null;
  confirmedDate?: string | null;
  notes?: string | null;
  recordedBy?: string | null;
}
export interface PoDoc {
  id: string;
  dispatchId?: string | null;
  docType: string;
  docTypeLabel: string;
  referenceNo?: string | null;
  description?: string | null;
  filename: string;
  bytes: number;
  uploadedByName?: string | null;
  uploadedAt?: string | null;
}
interface DispatchLine {
  poLineId: string;
  sku?: string | null;
  itemName?: string | null;
  quantity: string;
  uom?: string | null;
}
interface Dispatch {
  id: string;
  number: string;
  status: string;
  dispatchDate: string;
  expectedArrival?: string | null;
  overdue: boolean;
  transporter?: string | null;
  vehicleNo?: string | null;
  lrNo?: string | null;
  driverName?: string | null;
  driverPhone?: string | null;
  packages?: number | null;
  grossWeightKg?: string | null;
  invoiceNo?: string | null;
  invoiceDate?: string | null;
  invoiceValue?: string | null;
  packingListNo?: string | null;
  deliveryChallanNo?: string | null;
  deliveryChallanDate?: string | null;
  ewayBillNo?: string | null;
  ewayBillValidUntil?: string | null;
  ewayBillExpired: boolean;
  warning?: string | null;
  notes?: string | null;
  deliveredAt?: string | null;
  autoDelivered: boolean;
  cancelledReason?: string | null;
  lines: DispatchLine[];
  documents: PoDoc[];
}
interface Dispatchable {
  poLineId: string;
  sku?: string | null;
  itemName?: string | null;
  uom: string;
  ordered: string;
  received: string;
  inTransit: string;
  canDispatch: string;
}
interface Tracking {
  poStatus: string;
  expectedDate?: string | null;
  acknowledgement: Ack;
  documents: PoDoc[];
  dispatches: Dispatch[];
  dispatchable: Dispatchable[];
  docTypes: { vendor: Record<string, string>; dispatch: Record<string, string> };
}

export const ACK_LABEL: Record<string, string> = { pending: "Awaiting vendor", acknowledged: "Acknowledged", acknowledged_with_changes: "Acknowledged with changes", declined: "Declined" };
export const ACK_TONE: Record<string, Tone> = { pending: "muted", acknowledged: "success", acknowledged_with_changes: "warning", declined: "destructive" };
const DISPATCH_TONE: Record<string, Tone> = { in_transit: "info", delivered: "success", cancelled: "destructive" };
const DISPATCH_LABEL: Record<string, string> = { in_transit: "In transit", delivered: "Arrived", cancelled: "Cancelled" };

export const ackPill = (s: string) => <Pill tone={ACK_TONE[s] ?? "muted"}>{ACK_LABEL[s] ?? s}</Pill>;
export const shipmentPill = (status: string, inTransit = 0) =>
  status === "none" ? <span className="text-[var(--muted-foreground)]">—</span> : <Pill tone={status === "in_transit" ? "info" : "success"}>{status === "in_transit" ? `In transit${inTransit > 1 ? ` (${inTransit})` : ""}` : "Arrived"}</Pill>;

function useTracking(poId: string) {
  return useApiQuery<Tracking>(`${PO_BASE}/${poId}/vendor-tracking`);
}

function useRefreshTracking() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(PO_BASE) });
}

const size = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

function useDocDownload(poId: string) {
  const { apiBlob } = useAuth();
  return async (d: PoDoc) => {
    const { blob } = await apiBlob(`${PO_BASE}/${poId}/documents/${d.id}/download`);
    downloadBlob(blob, d.filename);
  };
}

// ---- progress trail -----------------------------------------------------------------------------------------------------

export interface PoProgress {
  status: string;
  issuedAt?: string | null;
  ackStatus?: string;
  ackDate?: string | null;
  documentCount?: number;
  dispatchStatus?: string;
  dispatchCount?: number;
  inTransitCount?: number;
  receiptStatus?: string;
}

/** Issued -> vendor acknowledged -> vendor documents -> dispatched -> goods received (GRN). */
export function PoTrail({ po }: { po: PoProgress }) {
  type St = "done" | "current" | "todo" | "bad";
  const dot: Record<St, string> = { done: "var(--success, #16a34a)", current: "var(--primary)", todo: "var(--border)", bad: "var(--destructive, #dc2626)" };
  const ack = po.ackStatus ?? "pending";
  const steps: { label: string; state: St; detail: string }[] = [
    { label: "PO issued", state: "done", detail: format.date(po.issuedAt) },
    { label: "Vendor acknowledgement", state: ack === "declined" ? "bad" : ack === "pending" ? "current" : "done", detail: ACK_LABEL[ack] ?? ack },
    { label: "Vendor documents", state: (po.documentCount ?? 0) > 0 ? "done" : "todo", detail: (po.documentCount ?? 0) > 0 ? `${po.documentCount} file${po.documentCount === 1 ? "" : "s"}` : "none yet" },
    { label: "Dispatch", state: po.dispatchStatus === "none" || !po.dispatchStatus ? "todo" : po.dispatchStatus === "in_transit" ? "current" : "done", detail: po.dispatchStatus === "in_transit" ? `${po.inTransitCount} in transit` : po.dispatchStatus === "delivered" ? "arrived" : "not dispatched" },
    { label: "Goods received (GRN)", state: po.receiptStatus === "full" ? "done" : po.receiptStatus === "partial" ? "current" : "todo", detail: po.receiptStatus === "full" ? "complete" : po.receiptStatus === "partial" ? "partly received" : "nothing yet" },
  ];
  return (
    <ol className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-sm" aria-label="Order progress">
      {steps.map((s) => (
        <li key={s.label} className="flex items-baseline gap-2">
          <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: dot[s.state] }} />
          <span className={s.state === "todo" ? "text-[var(--muted-foreground)]" : "font-semibold"}>{s.label}</span>
          <span className="text-[var(--muted-foreground)]">{s.detail}</span>
        </li>
      ))}
    </ol>
  );
}

// ---- upload -----------------------------------------------------------------------------------------------------------

function UploadDialog({ poId, types, dispatch, onClose }: { poId: string; types: Record<string, string>; dispatch?: Dispatch; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshTracking();
  const { run, busy, error, setError } = useAsyncAction();
  const [docType, setDocType] = useState(Object.keys(types)[0]);
  const [file, setFile] = useState<File | null>(null);
  const [ref, setRef] = useState("");
  const [description, setDescription] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return setError("Choose the file to upload");
    if (file.size > MAX_UPLOAD_BYTES) return setError(`${file.name} is ${size(file.size)}; the limit is 10 MB`);
    const ok = await run(async () => {
      await api("POST", `${PO_BASE}/${poId}/documents`, {
        json: { docType, filename: file.name, contentType: file.type || "application/octet-stream", contentBase64: await readBase64(file), referenceNo: ref.trim() || null, description: description.trim() || null, dispatchId: dispatch?.id ?? null },
      });
      await refresh();
      return true;
    });
    if (ok) onClose();
  };

  return (
    <Modal open onClose={onClose} title={dispatch ? `Attach a document to ${dispatch.number}` : "Upload a vendor document"} description="PDF, image, spreadsheet, Word or text file, up to 10 MB.">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <Field label="Document type" required>
          <SelectInput value={docType} onChange={(e) => setDocType(e.target.value)} options={Object.entries(types).map(([value, label]) => ({ value, label }))} />
        </Field>
        <Field label="File" required>
          <input type="file" className="text-sm" accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.txt,.xlsx,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
        <Field label="Their reference number" hint="e.g. PI number, challan number">
          <TextInput value={ref} onChange={(e) => setRef(e.target.value)} maxLength={80} />
        </Field>
        <Field label="Description">
          <TextArea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
        </Field>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Upload</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function DocList({ poId, docs, canWrite, empty }: { poId: string; docs: PoDoc[]; canWrite: boolean; empty: string }) {
  const { api } = useAuth();
  const refresh = useRefreshTracking();
  const download = useDocDownload(poId);
  const { run, error } = useAsyncAction();
  if (docs.length === 0) return <p className="text-sm text-[var(--muted-foreground)]">{empty}</p>;
  return (
    <div className="flex flex-col gap-1">
      <InlineError message={error} />
      {docs.map((d) => (
        <div key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-[var(--border)] px-3 py-2 text-sm">
          <span className="font-semibold">{d.docTypeLabel}</span>
          {d.referenceNo && <span>{d.referenceNo}</span>}
          <button type="button" className="rx-link" onClick={() => run(() => download(d))}>{d.filename}</button>
          <span className="text-xs text-[var(--muted-foreground)]">{size(d.bytes)} · {d.uploadedByName} · {format.date(d.uploadedAt)}</span>
          {d.description && <span className="w-full text-xs text-[var(--muted-foreground)]">{d.description}</span>}
          {canWrite && <ActionButton size="sm" tone="danger" className="ml-auto" onClick={() => run(async () => { await api("DELETE", `${PO_BASE}/${poId}/documents/${d.id}`); await refresh(); })}>Remove</ActionButton>}
        </div>
      ))}
    </div>
  );
}

// ---- acknowledgement & vendor documents ---------------------------------------------------------------------------------------

function AckDialog({ poId, current, onClose }: { poId: string; current: Ack; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshTracking();
  const { run, busy, error } = useAsyncAction();
  const [status, setStatus] = useState(current.status === "pending" ? "acknowledged" : current.status);
  const [ackDate, setAckDate] = useState(current.date ?? format.todayIso());
  const [ref, setRef] = useState(current.ref ?? "");
  const [confirmed, setConfirmed] = useState(current.confirmedDate ?? "");
  const [notes, setNotes] = useState(current.notes ?? "");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const ok = await run(async () => {
      await api("PUT", `${PO_BASE}/${poId}/acknowledgement`, { json: { status, ackDate: ackDate || null, ackRef: ref.trim() || null, confirmedDate: confirmed || null, notes: notes.trim() || null } });
      await refresh();
      return true;
    });
    if (ok) onClose();
  };
  return (
    <Modal open onClose={onClose} title="Vendor acknowledgement" description="Record the vendor's reply to the purchase order.">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <Field label="Their reply" required>
          <SelectInput value={status} onChange={(e) => setStatus(e.target.value)} options={[{ value: "acknowledged", label: "Acknowledged - accepted as issued" }, { value: "acknowledged_with_changes", label: "Acknowledged with changes" }, { value: "declined", label: "Declined - cannot supply" }]} />
        </Field>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Acknowledged on"><TextInput type="date" max={format.todayIso()} value={ackDate} onChange={(e) => setAckDate(e.target.value)} /></Field>
          <Field label="Their reference"><TextInput value={ref} onChange={(e) => setRef(e.target.value)} maxLength={80} placeholder="e.g. order confirmation no." /></Field>
        </div>
        {status !== "declined" && <Field label="Delivery date they confirmed" hint="Blank = as ordered"><TextInput type="date" value={confirmed} onChange={(e) => setConfirmed(e.target.value)} /></Field>}
        <Field label={status === "acknowledged" ? "Notes" : status === "declined" ? "Why they declined" : "What they changed"} required={status !== "acknowledged"}>
          <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
        </Field>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Save</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

export function AcknowledgementPanel({ poId }: { poId: string }) {
  const { api, can } = useAuth();
  const refresh = useRefreshTracking();
  const { run, error: actionError } = useAsyncAction();
  const t = useTracking(poId);
  const [dialog, setDialog] = useState<"" | "ack" | "upload">("");
  const d = t.data;
  if (!d) return <p className="text-sm text-[var(--muted-foreground)]">{t.error?.message ?? "Loading…"}</p>;
  const live = ["issued", "partially_received"].includes(d.poStatus);
  const canWrite = can("po:vendor") && live;
  const ack = d.acknowledgement;
  const have = new Set(d.documents.map((x) => x.docType));
  const expected: [string, string][] = [["po_acknowledgement", "PO acknowledgement"], ["proforma_invoice", "Proforma invoice"], ["technical_document", "Technical documents"]];

  return (
    <div className="flex flex-col gap-4">
      <InlineError message={actionError || t.error?.message} />
      <section className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-base font-bold">Vendor acknowledgement</p>
          {ackPill(ack.status)}
          <div className="flex-1" />
          {canWrite && <ActionButton size="sm" onClick={() => setDialog("ack")}>{ack.status === "pending" ? "Record acknowledgement" : "Update"}</ActionButton>}
          {canWrite && ack.status !== "pending" && <ActionButton size="sm" tone="ghost" onClick={() => run(async () => { await api("DELETE", `${PO_BASE}/${poId}/acknowledgement`); await refresh(); })}>Clear</ActionButton>}
        </div>
        {ack.status === "pending" ? (
          <p className="text-sm text-[var(--muted-foreground)]">The vendor has not replied yet. When they confirm the order, record it here.</p>
        ) : (
          <div className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm md:grid-cols-2">
            <span>Acknowledged on: {format.date(ack.date)}</span>
            <span>Their reference: {ack.ref || "—"}</span>
            <span>Delivery they confirmed: {ack.confirmedDate ? format.date(ack.confirmedDate) : "as ordered"}{ack.confirmedDate && d.expectedDate && ack.confirmedDate !== d.expectedDate ? ` (ordered for ${format.date(d.expectedDate)})` : ""}</span>
            <span>Recorded by: {ack.recordedBy || "—"}</span>
            {ack.notes && <span className="md:col-span-2">Notes: {ack.notes}</span>}
          </div>
        )}
        {ack.status === "declined" && <Note tone="warning">The vendor declined this order. Cancel it and place it elsewhere, or agree something new with them and issue an amended order.</Note>}
        {ack.status === "acknowledged_with_changes" && <Note tone="warning">The vendor changed something. If it is acceptable, carry on; if not, amend the order or talk to them.</Note>}
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-base font-bold">Vendor documents</p>
          <div className="flex flex-wrap gap-1">{expected.map(([k, label]) => <Pill key={k} tone={have.has(k) ? "success" : "muted"}>{`${have.has(k) ? "✓" : "○"} ${label}`}</Pill>)}</div>
          <div className="flex-1" />
          {canWrite && <ActionButton size="sm" onClick={() => setDialog("upload")}>Upload document</ActionButton>}
        </div>
        <DocList poId={poId} docs={d.documents} canWrite={canWrite} empty="No documents from the vendor yet. Upload their acknowledgement, proforma invoice and any technical documents." />
      </section>
      {dialog === "ack" && <AckDialog poId={poId} current={ack} onClose={() => setDialog("")} />}
      {dialog === "upload" && <UploadDialog poId={poId} types={d.docTypes.vendor} onClose={() => setDialog("")} />}
    </div>
  );
}

// ---- dispatch documentation ---------------------------------------------------------------------------------------------------

interface DispatchForm {
  dispatchDate: string;
  expectedArrival: string;
  transporter: string;
  vehicleNo: string;
  lrNo: string;
  driverName: string;
  driverPhone: string;
  packages: string;
  grossWeightKg: string;
  invoiceNo: string;
  invoiceDate: string;
  invoiceValue: string;
  packingListNo: string;
  deliveryChallanNo: string;
  deliveryChallanDate: string;
  ewayBillNo: string;
  ewayBillValidUntil: string;
  notes: string;
}

function DispatchDialog({ poId, tracking, edit, onClose }: { poId: string; tracking: Tracking; edit?: Dispatch; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshTracking();
  const { run, busy, error, setError } = useAsyncAction();
  const s = (v: string | number | null | undefined) => (v == null ? "" : String(v));
  const [f, setF] = useState<DispatchForm>({
    dispatchDate: edit?.dispatchDate ?? format.todayIso(), expectedArrival: s(edit?.expectedArrival), transporter: s(edit?.transporter), vehicleNo: s(edit?.vehicleNo), lrNo: s(edit?.lrNo),
    driverName: s(edit?.driverName), driverPhone: s(edit?.driverPhone), packages: s(edit?.packages), grossWeightKg: edit?.grossWeightKg ? trimDecimal(edit.grossWeightKg) : "",
    invoiceNo: s(edit?.invoiceNo), invoiceDate: s(edit?.invoiceDate), invoiceValue: edit?.invoiceValue ? trimDecimal(edit.invoiceValue) : "", packingListNo: s(edit?.packingListNo),
    deliveryChallanNo: s(edit?.deliveryChallanNo), deliveryChallanDate: s(edit?.deliveryChallanDate), ewayBillNo: s(edit?.ewayBillNo), ewayBillValidUntil: s(edit?.ewayBillValidUntil), notes: s(edit?.notes),
  });
  const set = (patch: Partial<DispatchForm>) => setF((p) => ({ ...p, ...patch }));
  // What can be shipped per item: everything still open on a new dispatch; on an edit, this shipment's own share is available again.
  const rows = tracking.dispatchable.map((d) => {
    const own = Number(edit?.lines.find((l) => l.poLineId === d.poLineId)?.quantity ?? 0);
    return { ...d, room: Number(d.canDispatch) + own, own };
  });
  const [qty, setQty] = useState<Record<string, string>>(() => Object.fromEntries(rows.map((r) => [r.poLineId, edit ? (r.own ? trimDecimal(String(r.own)) : "") : r.room > 0 ? trimDecimal(String(r.room)) : ""])));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const lines = rows.filter((r) => qty[r.poLineId]?.trim()).map((r) => ({ poLineId: r.poLineId, quantity: qty[r.poLineId].trim() }));
    if (!lines.length) return setError("Enter the quantity shipped for at least one item");
    const n = (v: string) => v.trim() || null;
    const body = {
      dispatchDate: f.dispatchDate, expectedArrival: n(f.expectedArrival), transporter: n(f.transporter), vehicleNo: n(f.vehicleNo), lrNo: n(f.lrNo), driverName: n(f.driverName), driverPhone: n(f.driverPhone),
      packages: f.packages ? Number(f.packages) : null, grossWeightKg: n(f.grossWeightKg), invoiceNo: n(f.invoiceNo), invoiceDate: n(f.invoiceDate), invoiceValue: n(f.invoiceValue), packingListNo: n(f.packingListNo),
      deliveryChallanNo: n(f.deliveryChallanNo), deliveryChallanDate: n(f.deliveryChallanDate), ewayBillNo: n(f.ewayBillNo), ewayBillValidUntil: n(f.ewayBillValidUntil), notes: n(f.notes), lines,
    };
    const ok = await run(async () => {
      await (edit ? api("PATCH", `${PO_BASE}/${poId}/dispatches/${edit.id}`, { json: body }) : api("POST", `${PO_BASE}/${poId}/dispatches`, { json: body }));
      await refresh();
      return true;
    });
    if (ok) onClose();
  };
  const T = (label: string, key: keyof DispatchForm, extra: { type?: string; hint?: string; placeholder?: string; mode?: "numeric" | "decimal"; max?: number } = {}) => (
    <Field label={label} hint={extra.hint}>
      <TextInput type={extra.type} placeholder={extra.placeholder} inputMode={extra.mode} maxLength={extra.max} value={f[key]} onChange={(e) => set({ [key]: e.target.value })} />
    </Field>
  );

  return (
    <Modal
      open
      onClose={onClose}
      wide
      maxWidth="52rem"
      title={edit ? `Edit ${edit.number}` : "Record a dispatch"}
      description="What the vendor has shipped, and the papers that travel with it. Fill in what applies."
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" form="dispatch-form" loading={busy}>{edit ? "Save changes" : "Record dispatch"}</ActionButton>
        </>
      }
    >
      <form id="dispatch-form" onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <p className="text-sm font-bold">Transport</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {T("Dispatch date", "dispatchDate", { type: "date" })}
          {T("Expected arrival", "expectedArrival", { type: "date" })}
          {T("Transporter", "transporter", { max: 120 })}
          {T("Vehicle number", "vehicleNo", { placeholder: "MH12AB1234", max: 30 })}
          {T("LR / docket / AWB no.", "lrNo", { max: 60 })}
          {T("Packages", "packages", { mode: "numeric" })}
          {T("Driver name", "driverName", { max: 120 })}
          {T("Driver phone", "driverPhone", { max: 30 })}
          {T("Gross weight (kg)", "grossWeightKg", { mode: "decimal" })}
        </div>
        <p className="mt-1 text-sm font-bold">Documents</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {T("Vendor invoice no.", "invoiceNo", { max: 60 })}
          {T("Invoice date", "invoiceDate", { type: "date" })}
          {T("Invoice value", "invoiceValue", { mode: "decimal", hint: "Incl. GST" })}
          {T("Packing list no.", "packingListNo", { max: 60 })}
          {T("Delivery challan no.", "deliveryChallanNo", { max: 60 })}
          {T("Challan date", "deliveryChallanDate", { type: "date" })}
          {T("E-way bill no.", "ewayBillNo", { hint: "12 digits", max: 20 })}
          {T("E-way bill valid until", "ewayBillValidUntil", { type: "date" })}
        </div>
        <p className="mt-1 text-sm font-bold">Items in this shipment</p>
        <DataTable columns={["Item", "Ordered", "Received", "On the road", "Can ship", "Shipping now"]} minWidth={0} fit>
          {rows.map((r) => (
            <tr key={r.poLineId}>
              <td>{r.itemName}</td>
              <td>{format.qty(trimDecimal(r.ordered), r.uom)}</td>
              <td>{format.qty(trimDecimal(r.received), r.uom)}</td>
              <td>{format.qty(trimDecimal(r.inTransit), r.uom)}</td>
              <td>{format.qty(trimDecimal(String(r.room)), r.uom)}</td>
              <td><TextInput style={{ width: "6rem" }} inputMode="decimal" aria-label={`Quantity of ${r.itemName}`} disabled={r.room <= 0} value={qty[r.poLineId] ?? ""} onChange={(e) => setQty({ ...qty, [r.poLineId]: e.target.value })} /></td>
            </tr>
          ))}
        </DataTable>
        <Field label="Notes"><TextArea value={f.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={2000} /></Field>
      </form>
    </Modal>
  );
}

function DispatchCard({ poId, d, types, canWrite, onEdit }: { poId: string; d: Dispatch; types: Record<string, string>; canWrite: boolean; onEdit: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshTracking();
  const { run, error } = useAsyncAction();
  const [mode, setMode] = useState<"" | "cancel" | "attach">("");
  const open = d.status === "in_transit";
  const kv = (label: string, value?: string | number | null) => (value ? <span>{label}: <b>{value}</b></span> : null);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--border)] p-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-base font-bold">{d.number}</p>
        <Pill tone={DISPATCH_TONE[d.status] ?? "muted"}>{DISPATCH_LABEL[d.status] ?? d.status}</Pill>
        {d.overdue && <Pill tone="destructive">Overdue</Pill>}
        {d.ewayBillExpired && <Pill tone="destructive">E-way bill expired</Pill>}
        {d.autoDelivered && <span className="text-xs text-[var(--muted-foreground)]">marked arrived by a goods receipt</span>}
        <div className="flex-1" />
        {canWrite && open && (
          <div className="flex flex-wrap gap-2">
            <ActionButton size="sm" tone="ghost" onClick={() => setMode("attach")}>Attach document</ActionButton>
            <ActionButton size="sm" tone="ghost" onClick={onEdit}>Edit</ActionButton>
            <ActionButton size="sm" onClick={() => run(async () => { await api("POST", `${PO_BASE}/${poId}/dispatches/${d.id}/deliver`, { json: {} }); await refresh(); })}>Mark arrived</ActionButton>
            <ActionButton size="sm" tone="danger" onClick={() => setMode("cancel")}>Cancel</ActionButton>
          </div>
        )}
      </div>
      <InlineError message={error} />
      {d.warning && <Note tone="warning">{d.warning}</Note>}
      {d.status === "cancelled" && d.cancelledReason && <p className="text-sm text-[var(--muted-foreground)]">Cancelled: {d.cancelledReason}</p>}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {kv("Dispatched", format.date(d.dispatchDate))}
        {kv("Expected", d.expectedArrival ? format.date(d.expectedArrival) : null)}
        {kv("Arrived", d.deliveredAt ? format.date(d.deliveredAt) : null)}
        {kv("Transporter", d.transporter)}
        {kv("Vehicle", d.vehicleNo)}
        {kv("LR / AWB", d.lrNo)}
        {kv("Driver", [d.driverName, d.driverPhone].filter(Boolean).join(" · "))}
        {kv("Packages", d.packages)}
        {kv("Weight", d.grossWeightKg ? `${trimDecimal(d.grossWeightKg)} kg` : null)}
        {kv("Invoice", [d.invoiceNo, d.invoiceDate ? format.date(d.invoiceDate) : null].filter(Boolean).join(", "))}
        {kv("Invoice value", d.invoiceValue ? format.money(d.invoiceValue) : null)}
        {kv("Packing list", d.packingListNo)}
        {kv("Delivery challan", [d.deliveryChallanNo, d.deliveryChallanDate ? format.date(d.deliveryChallanDate) : null].filter(Boolean).join(", "))}
        {kv("E-way bill", [d.ewayBillNo, d.ewayBillValidUntil ? `valid to ${format.date(d.ewayBillValidUntil)}` : null].filter(Boolean).join(", "))}
      </div>
      {d.notes && <p className="whitespace-pre-line text-sm">{d.notes}</p>}
      <p className="text-sm">{d.lines.map((l) => `${l.itemName} × ${format.qty(trimDecimal(l.quantity), l.uom)}`).join("; ")}</p>
      <DocList poId={poId} docs={d.documents} canWrite={canWrite && open} empty="No files attached to this shipment yet." />
      {mode === "attach" && <UploadDialog poId={poId} types={types} dispatch={d} onClose={() => setMode("")} />}
      {mode === "cancel" && <ReasonDialog title={`Cancel ${d.number}`} description="The quantity becomes available to ship again." confirmLabel="Cancel dispatch" minLength={3} placeholder="Why is it being cancelled?" onClose={() => setMode("")} onSubmit={async (reason) => { await api("POST", `${PO_BASE}/${poId}/dispatches/${d.id}/cancel`, { json: { reason } }); await refresh(); }} />}
    </div>
  );
}

export function DispatchPanel({ poId }: { poId: string }) {
  const { can } = useAuth();
  const t = useTracking(poId);
  const [dialog, setDialog] = useState<Dispatch | "new" | null>(null);
  const d = t.data;
  if (!d) return <p className="text-sm text-[var(--muted-foreground)]">{t.error?.message ?? "Loading…"}</p>;
  const live = ["issued", "partially_received"].includes(d.poStatus);
  const canWrite = can("po:vendor") && live;
  const room = d.dispatchable.some((x) => Number(x.canDispatch) > 0);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-base font-bold">Dispatch documentation</p>
        <div className="flex-1" />
        {canWrite && <ActionButton size="sm" disabled={!room} onClick={() => setDialog("new")}>Record dispatch</ActionButton>}
      </div>
      {d.dispatches.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Nothing dispatched yet. When the vendor ships, record the transport details, packing list, delivery challan and e-way bill here; the receiving team then sees what is on its way.</p>}
      {canWrite && !room && d.dispatches.length > 0 && <p className="text-xs text-[var(--muted-foreground)]">Everything ordered is already shipped or received.</p>}
      {d.dispatches.map((x) => <DispatchCard key={x.id} poId={poId} d={x} types={d.docTypes.dispatch} canWrite={canWrite} onEdit={() => setDialog(x)} />)}
      {dialog && <DispatchDialog poId={poId} tracking={d} edit={dialog === "new" ? undefined : dialog} onClose={() => setDialog(null)} />}
    </div>
  );
}

/** For the receiving team: what the vendor says is on its way for a purchase order. */
export function InboundShipments({ poId }: { poId: string }) {
  const t = useTracking(poId);
  const live = (t.data?.dispatches ?? []).filter((d) => d.status === "in_transit");
  if (live.length === 0) return null;
  return (
    <Note>
      <b>Vendor dispatch:</b>{" "}
      {live.map((d) => `${d.number} — ${d.lines.map((l) => `${l.itemName} × ${format.qty(trimDecimal(l.quantity), l.uom)}`).join(", ")}${d.transporter ? `, ${d.transporter}` : ""}${d.vehicleNo ? `, vehicle ${d.vehicleNo}` : ""}${d.lrNo ? `, LR ${d.lrNo}` : ""}${d.expectedArrival ? `, due ${format.date(d.expectedArrival)}` : ""}${d.ewayBillNo ? `, e-way bill ${d.ewayBillNo}` : ""}${d.packingListNo ? `, packing list ${d.packingListNo}` : ""}`).join("  |  ")}
    </Note>
  );
}
