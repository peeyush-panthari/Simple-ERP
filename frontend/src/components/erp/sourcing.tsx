/**
 * Procurement > Sourcing: request for quotation -> record each vendor's quotation -> compare and award -> purchase orders.
 * Started from an approved requisition (`RfqStartDialog`); listed and worked in `SourcingTab`.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ReasonDialog } from "@/components/erp/dialogs";
import { CheckRow } from "@/components/erp/extras";
import { trimDecimal, useRefreshRequisitions, type Requisition } from "@/components/erp/requisitions";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Field, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, Pagination, Pill, SelectInput, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { GST_RATE_OPTIONS } from "@/lib/reference";
import { humanise, type Tone } from "@/lib/status";

export const RFQ_BASE = "/api/v1/purchase-rfqs";

interface RfqRow {
  id: string;
  number: string;
  status: string;
  requisitionId?: string | null;
  requisitionNumber?: string | null;
  warehouseCode?: string | null;
  dueDate?: string | null;
  requiredBy?: string | null;
  itemsSummary?: string;
  lineCount?: number;
  vendorCount?: number;
  quotedCount?: number;
}
interface RfqLine {
  id: string;
  lineNo: number;
  sku?: string | null;
  itemName: string;
  notes?: string | null;
  quantity: string;
  uom: string;
  inCatalogue: boolean;
  awardedVendorId?: string | null;
  awardedVendorName?: string | null;
  awardReason?: string | null;
  purchaseOrderNumber?: string | null;
}
interface QuotationLine {
  rfqLineId: string;
  unitPrice: string | null;
  taxCode: string;
  leadTimeDays?: number | null;
  notes?: string | null;
}
interface Quotation {
  vendorId: string;
  quoteRef?: string | null;
  quoteDate?: string | null;
  validUntil?: string | null;
  paymentTerms?: string | null;
  deliveryDays?: number | null;
  charges: string;
  notes?: string | null;
  expired?: boolean;
  lines: QuotationLine[];
}
interface RfqVendor {
  vendorId: string;
  vendorName: string;
  vendorEmail?: string | null;
  status: string;
  emailState: string;
  emailError?: string | null;
  quotation: Quotation | null;
}
interface Rfq extends RfqRow {
  warehouseId?: string | null;
  terms?: string | null;
  notes?: string | null;
  createdByName?: string | null;
  awardedByName?: string | null;
  cancelledReason?: string | null;
  lines: RfqLine[];
  vendors: RfqVendor[];
  purchaseOrders: { id: string; number: string; vendorName?: string | null }[];
  created?: { id: string; number: string; vendorId: string }[];
  skippedFreeTextItems?: string[];
}
interface Offer {
  unitPrice: string;
  taxCode: string;
  grossAmount: string;
  leadTimeDays?: number | null;
  isLowest: boolean;
  overLowestPct?: string | null;
  expired: boolean;
}
interface CompLine {
  rfqLineId: string;
  lineNo: number;
  itemName: string;
  quantity: string;
  uom: string;
  quoteCount: number;
  offers: Record<string, Offer>;
  suggestedVendorId?: string | null;
  awardedVendorId?: string | null;
  awardReason?: string | null;
}
interface CompVendor {
  vendorId: string;
  vendorName: string;
  status: string;
  quoteRef?: string | null;
  validUntil?: string | null;
  expired: boolean;
  paymentTerms?: string | null;
  charges: string;
  quotedLineCount: number;
  coversAllLines: boolean;
  basketTotal?: string | null;
  longestLeadDays?: number | null;
}
interface Comparison {
  lines: CompLine[];
  vendors: CompVendor[];
  suggestedTotal?: string | null;
  cheapestSingleVendorId?: string | null;
  cheapestSingleVendorTotal?: string | null;
  unquotedLineIds: string[];
}
interface VendorParty {
  id: string;
  displayName: string;
  email?: string | null;
}
interface Named {
  id: string;
  name: string;
}

const STATUS_TONE: Record<string, Tone> = { open: "info", awarded: "warning", ordered: "success", cancelled: "destructive" };
const STATUS_LABEL: Record<string, string> = { open: "Collecting quotes", awarded: "Awarded", ordered: "PO raised", cancelled: "Cancelled" };
export const rfqStatusPill = (s: string) => <Pill tone={STATUS_TONE[s] ?? "muted"}>{STATUS_LABEL[s] ?? humanise(s)}</Pill>;

export function useRefreshSourcing() {
  const qc = useQueryClient();
  const refreshRequisitions = useRefreshRequisitions();
  return async () => {
    await qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(RFQ_BASE) });
    await qc.invalidateQueries({ queryKey: ["/api/v1/purchase-orders"] });
    await refreshRequisitions();
  };
}

const EMAIL_LABEL: Record<string, { text: string; tone: Tone }> = {
  sent: { text: "Email sent", tone: "success" },
  queued: { text: "Email queued", tone: "info" },
  failed: { text: "Email failed", tone: "destructive" },
  skipped: { text: "No email address", tone: "warning" },
  not_sent: { text: "Not emailed", tone: "muted" },
};
const VENDOR_TONE: Record<string, Tone> = { invited: "muted", quoted: "success", declined: "destructive" };
const VENDOR_LABEL: Record<string, string> = { invited: "Waiting for quote", quoted: "Quoted", declined: "Declined" };

// ---- start sourcing / invite vendors ---------------------------------------------------------------------------------

function VendorPicker({ vendors, selected, onToggle, exclude = [] }: { vendors: VendorParty[]; selected: string[]; onToggle: (id: string) => void; exclude?: string[] }) {
  const [q, setQ] = useState("");
  const shown = vendors.filter((v) => !exclude.includes(v.id) && (!q || v.displayName.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="flex flex-col gap-2">
      <input className="search-input" placeholder="Search vendors…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded-md border border-[var(--border)] p-2">
        {shown.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">No vendors to show</p>}
        {shown.map((v) => (
          <CheckRow
            key={v.id}
            checked={selected.includes(v.id)}
            onChange={() => onToggle(v.id)}
            label={<>{v.displayName}{!v.email && <span className="text-xs text-[var(--muted-foreground)]"> · no email on file</span>}</>}
          />
        ))}
      </div>
      <p className="text-xs text-[var(--muted-foreground)]">{selected.length} selected. Ask at least two or three vendors so there is something to compare.</p>
    </div>
  );
}

function useVendors() {
  const list = useApiQuery<ListResponse<VendorParty>>("/api/v1/parties", { type: "vendor", status: "active", limit: 200 });
  return list.data?.data ?? [];
}

export function RfqStartDialog({ requisition, onClose, onStarted }: { requisition: Requisition; onClose: () => void; onStarted: (rfqId: string) => void }) {
  const { api } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, busy, error, setError } = useAsyncAction();
  const vendors = useVendors();
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const [picked, setPicked] = useState<string[]>([]);
  const [dueDate, setDueDate] = useState("");
  const [requiredBy, setRequiredBy] = useState(requisition.requiredBy ?? "");
  const [warehouseId, setWarehouseId] = useState(requisition.warehouseId ?? "");
  const [terms, setTerms] = useState("");
  const [notes, setNotes] = useState("");
  const [send, setSend] = useState(true);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!picked.length) return setError("Choose at least one vendor to ask");
    const rfq = await run(() =>
      api<Rfq>("POST", RFQ_BASE, { json: { requisitionId: requisition.id, vendorIds: picked, dueDate: dueDate || null, requiredBy: requiredBy || null, warehouseId: warehouseId || null, terms: terms.trim() || null, notes: notes.trim() || null, send } }),
    );
    if (rfq) {
      await refresh();
      onStarted(rfq.id);
      onClose();
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      wide
      title={`Request quotations for ${requisition.number}`}
      description="Each chosen vendor is asked to quote for the items on the requisition. You record what they reply, then compare."
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" form="rfq-start-form" loading={busy}>Start sourcing</ActionButton>
        </>
      }
    >
      <form id="rfq-start-form" onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <div className="rounded-md border border-[var(--border)] p-3 text-sm">
          <p className="mb-1 font-bold">Items</p>
          {(requisition.lines ?? []).map((l) => (
            <p key={l.id}>{l.itemName} — {format.qty(trimDecimal(l.quantity), l.uom)}{!l.inCatalogue && <span className="text-[var(--muted-foreground)]"> (new item)</span>}</p>
          ))}
        </div>
        <Field label="Vendors to ask" required>
          <VendorPicker vendors={vendors} selected={picked} onToggle={toggle} />
        </Field>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <Field label="Vendors reply by">
            <TextInput type="date" min={format.todayIso()} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </Field>
          <Field label="Goods needed by">
            <TextInput type="date" value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)} />
          </Field>
          <Field label="Deliver to">
            <SelectInput key={warehouses.data ? "loaded" : "loading"} value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="Not sure yet" options={(warehouses.data?.data ?? []).map((w) => ({ value: w.id, label: w.name }))} />
          </Field>
        </div>
        <Field label="Terms for the vendors" hint="Shown in the request">
          <TextArea value={terms} onChange={(e) => setTerms(e.target.value)} placeholder="e.g. Prices to include delivery. Quotation valid for 30 days." maxLength={1000} />
        </Field>
        <Field label="Internal notes" hint="Not sent to vendors">
          <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
        </Field>
        <CheckRow checked={send} onChange={setSend} label="Email the request to each vendor now (vendors without an email address are flagged, and you can send it yourself)" />
      </form>
    </Modal>
  );
}

function InviteDialog({ rfq, onClose }: { rfq: Rfq; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, busy, error } = useAsyncAction();
  const vendors = useVendors();
  const [picked, setPicked] = useState<string[]>([]);
  const [send, setSend] = useState(true);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const ok = await run(async () => {
      await api("POST", `${RFQ_BASE}/${rfq.id}/vendors`, { json: { vendorIds: picked, send } });
      await refresh();
      return true;
    });
    if (ok) onClose();
  };
  return (
    <Modal open onClose={onClose} title={`Invite more vendors to ${rfq.number}`}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <VendorPicker vendors={vendors} exclude={rfq.vendors.map((v) => v.vendorId)} selected={picked} onToggle={(id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))} />
        <CheckRow checked={send} onChange={setSend} label="Email the request now" />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy} disabled={!picked.length}>Invite</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

// ---- record a vendor's quotation --------------------------------------------------------------------------------------

interface QuoteLineForm {
  unitPrice: string;
  taxCode: string;
  leadTimeDays: string;
  notes: string;
}

function QuotationDialog({ rfq, vendor, onClose }: { rfq: Rfq; vendor: RfqVendor; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, busy, error, setError } = useAsyncAction();
  const q = vendor.quotation;
  const [head, setHead] = useState({
    quoteRef: q?.quoteRef ?? "",
    quoteDate: q?.quoteDate ?? "",
    validUntil: q?.validUntil ?? "",
    paymentTerms: q?.paymentTerms ?? "",
    deliveryDays: q?.deliveryDays != null ? String(q.deliveryDays) : "",
    charges: q ? trimDecimal(q.charges) : "0",
    notes: q?.notes ?? "",
  });
  const [lines, setLines] = useState<Record<string, QuoteLineForm>>(() =>
    Object.fromEntries(
      rfq.lines.map((l) => {
        const ql = q?.lines.find((x) => x.rfqLineId === l.id);
        return [l.id, { unitPrice: ql?.unitPrice ? trimDecimal(ql.unitPrice) : "", taxCode: ql?.taxCode ?? "GST18", leadTimeDays: ql?.leadTimeDays != null ? String(ql.leadTimeDays) : "", notes: ql?.notes ?? "" }];
      }),
    ),
  );
  const setLine = (id: string, patch: Partial<QuoteLineForm>) => setLines((p) => ({ ...p, [id]: { ...p[id], ...patch } }));
  const setH = (patch: Partial<typeof head>) => setHead((h) => ({ ...h, ...patch }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!rfq.lines.some((l) => lines[l.id].unitPrice.trim() !== "")) return setError("Enter a price for at least one item - or record the vendor as declined");
    const ok = await run(async () => {
      await api("PUT", `${RFQ_BASE}/${rfq.id}/quotations/${vendor.vendorId}`, {
        json: {
          quoteRef: head.quoteRef.trim() || null,
          quoteDate: head.quoteDate || null,
          validUntil: head.validUntil || null,
          paymentTerms: head.paymentTerms.trim() || null,
          deliveryDays: head.deliveryDays ? Number(head.deliveryDays) : null,
          charges: head.charges.trim() || "0",
          notes: head.notes.trim() || null,
          lines: rfq.lines.map((l) => {
            const f = lines[l.id];
            const priced = f.unitPrice.trim() !== "";
            return { rfqLineId: l.id, unitPrice: priced ? f.unitPrice.trim() : null, taxCode: f.taxCode, leadTimeDays: priced && f.leadTimeDays ? Number(f.leadTimeDays) : null, notes: f.notes.trim() || null };
          }),
        },
      });
      await refresh();
      return true;
    });
    if (ok) onClose();
  };

  return (
    <Modal
      open
      onClose={onClose}
      wide
      title={`Quotation from ${vendor.vendorName}`}
      description="Enter what the vendor offered. Leave an item's price empty if they did not quote it."
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" form="quotation-form" loading={busy}>Save quotation</ActionButton>
        </>
      }
    >
      <form id="quotation-form" onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <Field label="Their quotation no."><TextInput value={head.quoteRef} onChange={(e) => setH({ quoteRef: e.target.value })} maxLength={80} /></Field>
          <Field label="Quotation date"><TextInput type="date" value={head.quoteDate} onChange={(e) => setH({ quoteDate: e.target.value })} /></Field>
          <Field label="Valid until"><TextInput type="date" value={head.validUntil} onChange={(e) => setH({ validUntil: e.target.value })} /></Field>
          <Field label="Payment terms"><TextInput value={head.paymentTerms} onChange={(e) => setH({ paymentTerms: e.target.value })} placeholder="e.g. Net 30" maxLength={120} /></Field>
          <Field label="Delivery in (days)"><TextInput inputMode="numeric" value={head.deliveryDays} onChange={(e) => setH({ deliveryDays: e.target.value })} /></Field>
          <Field label="Freight / other charges" hint="Added to the total"><TextInput inputMode="decimal" value={head.charges} onChange={(e) => setH({ charges: e.target.value })} /></Field>
        </div>
        <DataTable columns={["Item", "Qty", "Unit price (before GST)", "GST", "Lead time (days)", "Note"]} minWidth={0} fit>
          {rfq.lines.map((l) => (
            <tr key={l.id}>
              <td>{l.itemName}</td>
              <td>{format.qty(trimDecimal(l.quantity), l.uom)}</td>
              <td><TextInput style={{ width: "8rem" }} inputMode="decimal" aria-label={`Unit price for ${l.itemName}`} value={lines[l.id].unitPrice} onChange={(e) => setLine(l.id, { unitPrice: e.target.value })} /></td>
              <td><SelectInput style={{ width: "5.5rem" }} aria-label={`GST for ${l.itemName}`} value={lines[l.id].taxCode} onChange={(e) => setLine(l.id, { taxCode: e.target.value })} options={GST_RATE_OPTIONS} /></td>
              <td><TextInput style={{ width: "5rem" }} inputMode="numeric" aria-label={`Lead time for ${l.itemName}`} value={lines[l.id].leadTimeDays} onChange={(e) => setLine(l.id, { leadTimeDays: e.target.value })} /></td>
              <td><TextInput style={{ width: "10rem" }} aria-label={`Note for ${l.itemName}`} value={lines[l.id].notes} onChange={(e) => setLine(l.id, { notes: e.target.value })} maxLength={500} /></td>
            </tr>
          ))}
        </DataTable>
        <Field label="Notes"><TextArea value={head.notes} onChange={(e) => setH({ notes: e.target.value })} maxLength={1000} /></Field>
      </form>
    </Modal>
  );
}

// ---- compare & award ----------------------------------------------------------------------------------------------------

function CompareAward({ rfq }: { rfq: Rfq }) {
  const { api, can } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, busy, error } = useAsyncAction();
  const comp = useApiQuery<Comparison>(`${RFQ_BASE}/${rfq.id}/comparison`);
  const c = comp.data;
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const editable = rfq.status === "open" || rfq.status === "awarded";
  const locked = rfq.status !== "open" || !can("sourcing:award");

  // Start from what is already awarded, otherwise from the lowest price per item.
  useEffect(() => {
    if (!c) return;
    setChoice(Object.fromEntries(c.lines.filter((l) => l.awardedVendorId ?? l.suggestedVendorId).map((l) => [l.rfqLineId, (l.awardedVendorId ?? l.suggestedVendorId) as string])));
    setReasons(Object.fromEntries(c.lines.filter((l) => l.awardReason).map((l) => [l.rfqLineId, l.awardReason as string])));
  }, [c]);

  const vendorName = (id: string) => c?.vendors.find((v) => v.vendorId === id)?.vendorName ?? "";
  const needsReason = (l: CompLine, vendorId: string) => {
    const o = l.offers[vendorId];
    return !!o && (!o.isLowest || l.quoteCount < 2 || o.expired);
  };
  const reasonWhy = (l: CompLine, vendorId: string) => {
    const o = l.offers[vendorId];
    return [!o?.isLowest && "not the lowest price", l.quoteCount < 2 && "only one vendor quoted", o?.expired && "quotation expired"].filter(Boolean).join(", ");
  };

  const selected = useMemo(() => {
    if (!c) return { total: 0, used: [] as string[] };
    const used = new Set<string>();
    let total = 0;
    for (const l of c.lines) {
      const v = choice[l.rfqLineId];
      if (v && l.offers[v]) {
        total += Number(l.offers[v].grossAmount);
        used.add(v);
      }
    }
    for (const v of used) total += Number(c.vendors.find((x) => x.vendorId === v)?.charges ?? 0);
    return { total, used: [...used] };
  }, [c, choice]);

  if (comp.isLoading || !c) return <p className="text-sm text-[var(--muted-foreground)]">Loading the comparison…</p>;
  const quotedVendors = c.vendors.filter((v) => v.quotedLineCount > 0);
  if (quotedVendors.length === 0) return <EmptyState title="No quotations recorded yet" hint="Record what each vendor offered on the Vendors & quotations tab, and they appear here side by side." />;

  const pending = c.lines.filter((l) => l.quoteCount > 0);
  const missingReason = pending.some((l) => choice[l.rfqLineId] && needsReason(l, choice[l.rfqLineId]) && (reasons[l.rfqLineId] ?? "").trim().length < 3);
  const submit = () =>
    run(async () => {
      await api("POST", `${RFQ_BASE}/${rfq.id}/award`, { json: { awards: pending.map((l) => ({ rfqLineId: l.rfqLineId, vendorId: choice[l.rfqLineId], reason: reasons[l.rfqLineId]?.trim() || null })) } });
      await refresh();
    });

  return (
    <div className="flex flex-col gap-3">
      <InlineError message={error || comp.error?.message} />
      {rfq.status === "awarded" && <Note>Awarded{rfq.awardedByName ? ` by ${rfq.awardedByName}` : ""}. Raise the purchase orders, or reopen to change the award.</Note>}
      {rfq.status === "ordered" && <Note>Purchase orders have been raised: {rfq.purchaseOrders.map((p) => p.number).join(", ")}.</Note>}
      {c.unquotedLineIds.length > 0 && <Note tone="warning">No vendor has quoted: {c.lines.filter((l) => c.unquotedLineIds.includes(l.rfqLineId)).map((l) => l.itemName).join(", ")}. Those items are left out of the award.</Note>}
      <p className="text-xs text-[var(--muted-foreground)]">Prices include GST. The lowest landed price per item is marked; choose a different vendor and you will be asked why.</p>
      <div className="data-table-wrap">
        <table className="data-table data-table-fit">
          <thead>
            <tr>
              <th>Item</th>
              {quotedVendors.map((v) => (
                <th key={v.vendorId}>
                  {v.vendorName}
                  <div className="text-[11px] font-normal normal-case text-[var(--muted-foreground)]">
                    {v.quoteRef ? `${v.quoteRef} · ` : ""}{v.paymentTerms || "terms n/a"}{v.validUntil ? ` · valid to ${format.date(v.validUntil)}` : ""}{v.expired ? " (expired)" : ""}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {c.lines.map((l) => (
              <tr key={l.rfqLineId}>
                <td>
                  <div className="font-semibold">{l.itemName}</div>
                  <div className="text-xs text-[var(--muted-foreground)]">{format.qty(trimDecimal(l.quantity), l.uom)}</div>
                  {l.quoteCount === 0 && <div className="text-xs text-[var(--muted-foreground)]">No quotes</div>}
                  {choice[l.rfqLineId] && needsReason(l, choice[l.rfqLineId]) && (
                    <div className="mt-1">
                      <TextInput
                        style={{ width: "14rem" }}
                        placeholder={`Why? (${reasonWhy(l, choice[l.rfqLineId])})`}
                        aria-label={`Reason for ${l.itemName}`}
                        value={reasons[l.rfqLineId] ?? ""}
                        disabled={locked}
                        onChange={(e) => setReasons({ ...reasons, [l.rfqLineId]: e.target.value })}
                        maxLength={500}
                      />
                    </div>
                  )}
                </td>
                {quotedVendors.map((v) => {
                  const o = l.offers[v.vendorId];
                  if (!o) return <td key={v.vendorId} className="text-[var(--muted-foreground)]">—</td>;
                  const on = choice[l.rfqLineId] === v.vendorId;
                  return (
                    <td key={v.vendorId} style={on ? { background: "color-mix(in oklab, var(--primary) 10%, transparent)" } : undefined}>
                      <label className="flex cursor-pointer items-start gap-2">
                        <input type="radio" name={`award-${l.rfqLineId}`} checked={on} disabled={locked} onChange={() => setChoice({ ...choice, [l.rfqLineId]: v.vendorId })} aria-label={`Award ${l.itemName} to ${v.vendorName}`} />
                        <span>
                          <span className="font-semibold">{format.money(o.grossAmount)}</span>{" "}
                          {o.isLowest ? <Pill tone="success">Lowest</Pill> : o.overLowestPct ? <Pill tone="muted">{`+${Number(o.overLowestPct).toFixed(1)}%`}</Pill> : null}
                          <span className="block text-xs text-[var(--muted-foreground)]">
                            {format.money(o.unitPrice)} + {o.taxCode.replace("GST", "")}% GST{o.leadTimeDays != null ? ` · ${o.leadTimeDays}d` : ""}
                          </span>
                        </span>
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <td className="font-bold">Whole basket (all items + freight)</td>
              {quotedVendors.map((v) => (
                <td key={v.vendorId}>
                  {v.coversAllLines ? <span className="font-semibold">{format.money(v.basketTotal)}</span> : <span className="text-[var(--muted-foreground)]">{v.quotedLineCount} of {c.lines.length} items</span>}
                  {v.vendorId === c.cheapestSingleVendorId && <> <Pill tone="success">Cheapest single vendor</Pill></>}
                  {Number(v.charges) > 0 && <span className="block text-xs text-[var(--muted-foreground)]">incl. {format.money(v.charges)} freight</span>}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
        <span className="font-bold">Your selection: {format.money(selected.total)}</span>
        {c.suggestedTotal && <span className="text-[var(--muted-foreground)]">Lowest per item: {format.money(c.suggestedTotal)}</span>}
        {c.cheapestSingleVendorId && <span className="text-[var(--muted-foreground)]">Cheapest single vendor: {vendorName(c.cheapestSingleVendorId)} {format.money(c.cheapestSingleVendorTotal)}</span>}
        <span className="text-[var(--muted-foreground)]">{selected.used.length} purchase order{selected.used.length === 1 ? "" : "s"} would follow</span>
      </div>
      {editable && !locked && (
        <div className="flex justify-end gap-2">
          <ActionButton loading={busy} disabled={missingReason || pending.some((l) => !choice[l.rfqLineId])} onClick={submit}>Award to the selected vendors</ActionButton>
        </div>
      )}
      {missingReason && !locked && <p className="text-xs text-[var(--muted-foreground)]">Fill in the reason for each item that is not simply the lowest offer from a real choice of vendors.</p>}
    </div>
  );
}

// ---- detail ------------------------------------------------------------------------------------------------------------

function VendorsPanel({ rfq }: { rfq: Rfq }) {
  const { api, can } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, error } = useAsyncAction();
  const [quoteFor, setQuoteFor] = useState<RfqVendor | null>(null);
  const [inviting, setInviting] = useState(false);
  const open = rfq.status === "open";
  const write = can("sourcing:write") && open;
  const act = (vendor: RfqVendor, verb: string, method: "POST" | "DELETE" = "POST") => run(async () => { await api(method, `${RFQ_BASE}/${rfq.id}/vendors/${vendor.vendorId}${verb}`); await refresh(); });

  return (
    <div className="flex flex-col gap-3">
      <InlineError message={error} />
      {rfq.terms && <p className="text-sm"><b>Terms sent: </b>{rfq.terms}</p>}
      <DataTable columns={["Vendor", "Request", "Quotation", ""]} minWidth={0} fit>
        {rfq.vendors.map((v) => {
          const em = EMAIL_LABEL[v.emailState] ?? EMAIL_LABEL.not_sent;
          return (
            <tr key={v.vendorId}>
              <td>{v.vendorName}<div className="text-xs text-[var(--muted-foreground)]">{v.vendorEmail || "no email on file"}</div></td>
              <td><Pill tone={em.tone}>{em.text}</Pill>{v.emailError && <div className="max-w-56 text-xs text-[var(--muted-foreground)]">{v.emailError}</div>}</td>
              <td>
                <Pill tone={VENDOR_TONE[v.status] ?? "muted"}>{VENDOR_LABEL[v.status] ?? v.status}</Pill>
                {v.quotation && <div className="text-xs text-[var(--muted-foreground)]">{v.quotation.quoteRef || "no ref"}{v.quotation.validUntil ? ` · valid to ${format.date(v.quotation.validUntil)}` : ""}{v.quotation.expired ? " (expired)" : ""}</div>}
              </td>
              <td>
                {write && (
                  <div className="flex flex-wrap gap-2">
                    {v.status !== "declined" && <ActionButton size="sm" onClick={() => setQuoteFor(v)}>{v.quotation ? "Edit quotation" : "Record quotation"}</ActionButton>}
                    {!v.quotation && v.status === "invited" && <ActionButton size="sm" tone="ghost" onClick={() => act(v, "/resend")}>{v.emailState === "sent" ? "Resend request" : "Send request"}</ActionButton>}
                    {!v.quotation && v.status === "invited" && <ActionButton size="sm" tone="ghost" onClick={() => act(v, "/decline")}>Declined</ActionButton>}
                    {!v.quotation && <ActionButton size="sm" tone="danger" onClick={() => act(v, "", "DELETE")}>Remove</ActionButton>}
                  </div>
                )}
              </td>
            </tr>
          );
        })}
      </DataTable>
      {write && <div><ActionButton tone="ghost" onClick={() => setInviting(true)}>Invite more vendors</ActionButton></div>}
      {quoteFor && <QuotationDialog rfq={rfq} vendor={quoteFor} onClose={() => setQuoteFor(null)} />}
      {inviting && <InviteDialog rfq={rfq} onClose={() => setInviting(false)} />}
    </div>
  );
}

function PurchaseOrdersDialog({ rfq, onClose }: { rfq: Rfq; onClose: () => void }) {
  const { api } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, busy, error } = useAsyncAction();
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const comp = useApiQuery<Comparison>(`${RFQ_BASE}/${rfq.id}/comparison`);
  const [warehouseId, setWarehouseId] = useState(rfq.warehouseId ?? "");
  const [expectedDate, setExpectedDate] = useState("");
  const [result, setResult] = useState<Rfq | null>(null);

  // What will be raised: the awarded, catalogue items grouped per winning vendor, at their quoted prices.
  const plan = useMemo(() => {
    const by = new Map<string, { name: string; items: string[]; total: number; charges: number }>();
    for (const l of rfq.lines) {
      if (!l.awardedVendorId || l.purchaseOrderNumber || !l.inCatalogue) continue;
      const cl = comp.data?.lines.find((x) => x.rfqLineId === l.id);
      const o = cl?.offers[l.awardedVendorId];
      const cur = by.get(l.awardedVendorId) ?? { name: l.awardedVendorName ?? "", items: [], total: 0, charges: Number(comp.data?.vendors.find((v) => v.vendorId === l.awardedVendorId)?.charges ?? 0) };
      cur.items.push(l.itemName);
      cur.total += Number(o?.grossAmount ?? 0);
      by.set(l.awardedVendorId, cur);
    }
    return [...by.values()];
  }, [rfq, comp.data]);
  const freeText = rfq.lines.filter((l) => l.awardedVendorId && !l.inCatalogue).map((l) => l.itemName);

  const submit = async () => {
    const res = await run(() => api<Rfq>("POST", `${RFQ_BASE}/${rfq.id}/purchase-orders`, { json: { warehouseId: warehouseId || null, expectedDate: expectedDate || null } }));
    if (res) {
      await refresh();
      setResult(res);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={result ? "Purchase orders raised" : `Raise purchase orders for ${rfq.number}`}
      description={result ? undefined : "One purchase order per winning vendor, priced from their quotation."}
      footer={
        result ? (
          <ActionButton onClick={onClose}>Done</ActionButton>
        ) : (
          <>
            <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
            <ActionButton loading={busy} disabled={plan.length === 0} onClick={submit}>Create {plan.length} purchase order{plan.length === 1 ? "" : "s"}</ActionButton>
          </>
        )
      }
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        {result ? (
          <>
            <p className="text-sm">Created: {(result.created ?? []).map((c) => c.number).join(", ")}. The requisition is now marked as ordered.</p>
            {(result.skippedFreeTextItems ?? []).length > 0 && <Note tone="warning">Not ordered, because they are not in the product list yet: {(result.skippedFreeTextItems ?? []).join(", ")}. Set them up under Products &amp; BOM and raise a purchase order for them.</Note>}
          </>
        ) : (
          <>
            {plan.map((p) => (
              <div key={p.name} className="rounded-md border border-[var(--border)] p-3 text-sm">
                <p className="font-bold">{p.name}</p>
                <p>{p.items.join(", ")}</p>
                <p className="text-[var(--muted-foreground)]">About {format.money(p.total + p.charges)} incl. GST{p.charges > 0 ? " and freight" : ""}</p>
              </div>
            ))}
            {freeText.length > 0 && <Note tone="warning">Not ordered, as they are not in the product list yet: {freeText.join(", ")}.</Note>}
            <Field label="Deliver to" required={!rfq.warehouseId}>
              <SelectInput key={warehouses.data ? "loaded" : "loading"} value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="Choose a warehouse" options={(warehouses.data?.data ?? []).map((w) => ({ value: w.id, label: w.name }))} />
            </Field>
            <Field label="Expected delivery" hint="Blank = the requisition's date or the vendor's lead time">
              <TextInput type="date" min={format.todayIso()} value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} />
            </Field>
          </>
        )}
      </div>
    </Modal>
  );
}

export function RfqDetailDialog({ id, onClose, onOpenRequisition }: { id: string; onClose: () => void; onOpenRequisition?: (id: string) => void }) {
  const { api, can } = useAuth();
  const refresh = useRefreshSourcing();
  const { run, error } = useAsyncAction();
  const [mode, setMode] = useState<"" | "cancel" | "orders">("");
  const [tab, setTab] = useState("vendors");
  const path = `${RFQ_BASE}/${id}`;
  const detail = useApiQuery<Rfq>(path);
  const rfq = detail.data;

  return (
    <>
      <Modal
        open
        onClose={onClose}
        wide
        maxWidth="60rem"
        title={rfq ? `${rfq.number} — ${rfq.requisitionNumber ?? "sourcing"}` : "Request for quotation"}
        footer={
          rfq && (
            <>
              <ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>
              {can("sourcing:write") && ["open", "awarded"].includes(rfq.status) && !rfq.purchaseOrders.length && <ActionButton tone="danger" onClick={() => setMode("cancel")}>Cancel RFQ</ActionButton>}
              {can("sourcing:award") && rfq.status === "awarded" && <ActionButton tone="ghost" onClick={() => run(async () => { await api("POST", `${path}/reopen`); await refresh(); })}>Reopen</ActionButton>}
              {can("sourcing:award") && can("po:write") && rfq.status === "awarded" && <ActionButton onClick={() => setMode("orders")}>Create purchase orders</ActionButton>}
            </>
          )
        }
      >
        {rfq && (
          <div className="flex flex-col gap-3">
            <InlineError message={error || detail.error?.message} />
            <div className="flex flex-wrap items-center gap-3">
              {rfqStatusPill(rfq.status)}
              {rfq.requisitionId && onOpenRequisition && <button type="button" className="rx-link text-sm" onClick={() => onOpenRequisition(rfq.requisitionId as string)}>Requisition {rfq.requisitionNumber}</button>}
            </div>
            {rfq.status === "cancelled" && <Note>Cancelled: {rfq.cancelledReason}</Note>}
            <div className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm md:grid-cols-3">
              <span>Vendors reply by: {format.date(rfq.dueDate)}</span>
              <span>Goods needed by: {format.date(rfq.requiredBy)}</span>
              <span>Deliver to: {rfq.warehouseCode || "—"}</span>
            </div>
            <p className="text-sm"><b>Items: </b>{rfq.lines.map((l) => `${l.itemName} (${format.qty(trimDecimal(l.quantity), l.uom)})`).join(", ")}</p>
            <Tabs
              value={tab}
              onValueChange={setTab}
              tabs={[
                { value: "vendors", label: `Vendors & quotations (${rfq.vendors.filter((v) => v.quotation).length}/${rfq.vendors.length})`, content: <VendorsPanel rfq={rfq} /> },
                { value: "compare", label: "Compare & award", content: <CompareAward rfq={rfq} /> },
              ]}
            />
          </div>
        )}
      </Modal>
      {mode === "cancel" && rfq && (
        <ReasonDialog title={`Cancel ${rfq.number}`} description="The requisition goes back to approved, so sourcing can start again." confirmLabel="Cancel RFQ" minLength={3} placeholder="Why is it being cancelled?" onClose={() => setMode("")} onSubmit={async (reason) => { await api("POST", `${path}/cancel`, { json: { reason } }); await refresh(); onClose(); }} />
      )}
      {mode === "orders" && rfq && <PurchaseOrdersDialog rfq={rfq} onClose={() => setMode("")} />}
    </>
  );
}

// ---- tab -------------------------------------------------------------------------------------------------------------------

export function SourcingTab({ openId, onOpen, onOpenRequisition }: { openId: string; onOpen: (id: string) => void; onOpenRequisition?: (id: string) => void }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  const list = useApiQuery<ListResponse<RfqRow>>(RFQ_BASE, { page, limit: 20, q: debounced, status });
  const rows = list.data?.data ?? [];
  const link = (r: RfqRow) => <button type="button" className="rx-link" onClick={() => onOpen(r.id)}>{r.number}</button>;
  const quoted = (r: RfqRow) => `${r.quotedCount ?? 0} of ${r.vendorCount ?? 0} quoted`;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <Note>An approved requisition goes out for quotation from its own page (<b>Start sourcing</b>). Record each vendor&apos;s reply here, compare the offers, award, and raise the purchase orders.</Note>
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input className="search-input" style={{ width: "20rem" }} placeholder="Search RFQ, requisition, item or vendor…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <select className="filter-select" style={{ width: "11rem" }} value={status} aria-label="Filter by All Status" onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <InlineError message={list.error?.message} />
      {!list.isLoading && rows.length === 0 && <div className="w-full"><EmptyState title={debounced || status ? "No RFQs match" : "No sourcing yet"} hint="Approve a requisition, then press Start sourcing on it." /></div>}
      {rows.length > 0 && (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["RFQ", "Requisition", "Items", "Vendors", "Reply by", "Status"]} fit>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{link(r)}</td>
                  <td>{r.requisitionNumber || "—"}</td>
                  <td>{r.itemsSummary}</td>
                  <td>{quoted(r)}</td>
                  <td>{format.date(r.dueDate)}</td>
                  <td>{rfqStatusPill(r.status)}</td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {rows.map((r) => (
              <MobileRecordCard key={r.id}>
                <MobileRecordRow label="RFQ" value={link(r)} />
                <MobileRecordRow label="Requisition" value={r.requisitionNumber || "—"} />
                <MobileRecordRow label="Items" value={r.itemsSummary} />
                <MobileRecordRow label="Vendors" value={quoted(r)} />
                <MobileRecordRow label="Reply by" value={format.date(r.dueDate)} />
                <MobileRecordRow label="Status" value={rfqStatusPill(r.status)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {openId && <RfqDetailDialog id={openId} onClose={() => onOpen("")} onOpenRequisition={onOpenRequisition} />}
    </div>
  );
}
