/**
 * Procurement > Purchase requisitions: an employee asks the Purchase department for something they need.
 * Employees raise, edit (draft / sent back) and cancel their own; Purchase (pr:approve) reviews everyone's submitted
 * ones - approve, reject with a reason, or turn an approved one into a purchase order (`onCreatePo`).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ReasonDialog } from "@/components/erp/dialogs";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Field, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, Pagination, Pill, Segmented, SelectInput,
  TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { UOM_OPTIONS } from "@/lib/reference";
import { humanise, type Tone } from "@/lib/status";

export interface RequisitionLine {
  id?: string;
  lineNo?: number;
  productId: string | null;
  sku?: string | null;
  itemName: string;
  notes?: string | null;
  quantity: string;
  uom: string;
  inCatalogue?: boolean;
}
export interface Requisition {
  id: string;
  number: string;
  status: string;
  priority: string;
  requesterId: string;
  requesterName: string;
  department?: string | null;
  warehouseId?: string | null;
  warehouseCode?: string | null;
  requiredBy?: string | null;
  justification?: string | null;
  submittedAt?: string | null;
  managerId?: string | null;
  managerName?: string | null;
  managerDecidedAt?: string | null;
  managerNote?: string | null;
  rejectedStage?: string | null;
  rfqId?: string | null;
  rfqNumber?: string | null;
  rfqStatus?: string | null;
  reviewedByName?: string | null;
  reviewedAt?: string | null;
  reviewNote?: string | null;
  purchaseOrderId?: string | null;
  purchaseOrderNumber?: string | null;
  cancelledReason?: string | null;
  createdAt?: string | null;
  lineCount?: number;
  itemsSummary?: string;
  lines?: RequisitionLine[];
}
interface Counts {
  mine: Record<string, number>;
  awaitingReview: number | null;
  awaitingMyApproval?: number | null;
}
interface Named {
  id: string;
  name: string;
}
interface Product {
  id: string;
  sku: string;
  name: string;
  uom: string;
}

export const REQUISITION_BASE = "/api/v1/purchase-requisitions";

const STATUSES = ["draft", "pending_manager", "submitted", "approved", "sourcing", "ordered", "rejected", "cancelled"];
const STATUS_TONE: Record<string, Tone> = { draft: "warning", pending_manager: "warning", submitted: "info", approved: "success", sourcing: "info", rejected: "destructive", ordered: "success", cancelled: "muted" };
const STATUS_LABEL: Record<string, string> = { pending_manager: "With manager", submitted: "With Purchase", sourcing: "Out for quotation", ordered: "PO raised" };
const PRIORITIES = ["low", "normal", "high", "urgent"];
const PRIORITY_TONE: Record<string, Tone> = { low: "muted", normal: "info", high: "warning", urgent: "destructive" };

const statusPill = (s: string) => <Pill tone={STATUS_TONE[s] ?? "muted"}>{STATUS_LABEL[s] ?? humanise(s)}</Pill>;
const priorityPill = (p: string) => <Pill tone={PRIORITY_TONE[p] ?? "muted"}>{humanise(p)}</Pill>;

/** Refreshes every requisition list, detail and count after any change. */
export function useRefreshRequisitions() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(REQUISITION_BASE) });
}

export function useRequisitionCounts(enabled: boolean) {
  return useApiQuery<Counts>(`${REQUISITION_BASE}/counts`, undefined, { enabled });
}

/** "25.000000" -> "25", "2.500000" -> "2.5" (the API returns fixed-scale decimals). */
export const trimDecimal = (v: string) => (v.includes(".") ? v.replace(/0+$/, "").replace(/\.$/, "") : v);

// ---- raise / edit --------------------------------------------------------------------

interface FormLine {
  productId: string | null;
  itemName: string;
  quantity: string;
  uom: string;
  notes: string;
}

function RequisitionForm({ initial, onClose, onSaved }: { initial?: Requisition; onClose: () => void; onSaved: (pr: Requisition) => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [priority, setPriority] = useState(initial?.priority ?? "normal");
  const [requiredBy, setRequiredBy] = useState(initial?.requiredBy ?? "");
  const [warehouseId, setWarehouseId] = useState(initial?.warehouseId ?? "");
  const [department, setDepartment] = useState(initial?.department ?? "");
  const [justification, setJustification] = useState(initial?.justification ?? "");
  const [lines, setLines] = useState<FormLine[]>((initial?.lines ?? []).map((l) => ({ productId: l.productId, itemName: l.itemName, quantity: trimDecimal(l.quantity), uom: l.uom, notes: l.notes ?? "" })));
  const [mode, setMode] = useState<"catalogue" | "new">("catalogue");
  const [productId, setProductId] = useState("");
  const [itemName, setItemName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [uom, setUom] = useState("UNIT");
  const [notes, setNotes] = useState("");

  const products = useApiQuery<ListResponse<Product>>("/api/v1/products", { purchasable: "true", status: "active", limit: 200 });
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const productList = products.data?.data ?? [];

  const addLine = () => {
    setError("");
    if (!quantity || Number(quantity) <= 0) return setError("Enter how many you need");
    if (mode === "catalogue") {
      const p = productList.find((x) => x.id === productId);
      if (!p) return setError("Pick a product, or switch to \"Something new\" to describe it");
      setLines([...lines, { productId: p.id, itemName: p.name || p.sku, quantity, uom: p.uom, notes: notes.trim() }]);
    } else {
      if (!itemName.trim()) return setError("Say what you need");
      setLines([...lines, { productId: null, itemName: itemName.trim(), quantity, uom, notes: notes.trim() }]);
    }
    setProductId("");
    setItemName("");
    setQuantity("");
    setNotes("");
  };

  const save = async (submit: boolean) => {
    if (!lines.length) return setError("Add at least one item");
    if (submit && justification.trim().length < 3) return setError("Say what the items are for, so Purchase can decide");
    const payload = {
      priority,
      department: department.trim() || null,
      warehouseId: warehouseId || null,
      requiredBy: requiredBy || null,
      justification: justification.trim() || null,
      lines: lines.map((l) => ({ productId: l.productId, itemName: l.productId ? null : l.itemName, quantity: l.quantity, uom: l.uom, notes: l.notes || null })),
      submit,
    };
    const saved = await run(() => (initial ? api<Requisition>("PATCH", `${REQUISITION_BASE}/${initial.id}`, { json: payload }) : api<Requisition>("POST", REQUISITION_BASE, { json: payload })));
    if (saved) onSaved(saved);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void save(true);
  };

  return (
    <Modal
      open
      onClose={onClose}
      wide
      title={initial ? `Edit ${initial.number}` : "New purchase requisition"}
      description="Tell Purchase what you need and why. Nothing is ordered until Purchase approves it."
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton tone="ghost" loading={busy} onClick={() => void save(false)}>Save as draft</ActionButton>
          <ActionButton type="submit" form="pr-form" loading={busy}>Submit to Purchase</ActionButton>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        {initial?.status === "rejected" && initial.reviewNote && <Note tone="warning">Purchase sent this back: {initial.reviewNote}</Note>}
        <form id="pr-form" onSubmit={onSubmit} className="flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="How urgent is it?">
              <SelectInput value={priority} onChange={(e) => setPriority(e.target.value)} options={PRIORITIES.map((p) => ({ value: p, label: humanise(p) }))} />
            </Field>
            <Field label="Needed by">
              <TextInput type="date" min={format.todayIso()} value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)} />
            </Field>
            <Field label="Deliver to">
              <SelectInput value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="Any / not sure" options={(warehouses.data?.data ?? []).map((w) => ({ value: w.id, label: w.name }))} />
            </Field>
            <Field label="Your department">
              <TextInput value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="e.g. Maintenance" maxLength={100} />
            </Field>
          </div>
          <Field label="Why do you need it?" required hint="Purchase reads this to decide">
            <TextArea value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="e.g. Line 2 conveyor bearings are worn out" maxLength={2000} />
          </Field>
        </form>

        <p className="mt-2 text-sm font-bold">Items</p>
        <DataTable columns={["Item", "Qty", "Note", ""]} minWidth={0} fit>
          {lines.map((l, i) => (
            <tr key={i}>
              <td>{l.itemName}{!l.productId && <> <Pill tone="muted">New item</Pill></>}</td>
              <td>{format.qty(l.quantity, l.uom)}</td>
              <td>{l.notes}</td>
              <td><ActionButton size="sm" tone="danger" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</ActionButton></td>
            </tr>
          ))}
        </DataTable>
        <div className="flex flex-col gap-2 rounded-md border border-[var(--border)] p-3">
          <Segmented value={mode} onChange={(v) => setMode(v as "catalogue" | "new")} options={[{ value: "catalogue", label: "From our products" }, { value: "new", label: "Something new" }]} />
          <div className="flex flex-wrap items-center gap-2 md:flex-nowrap">
            {mode === "catalogue" ? (
              <SelectInput style={{ width: "16rem" }} value={productId} onChange={(e) => setProductId(e.target.value)} placeholder="Product" options={productList.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))} />
            ) : (
              <>
                <TextInput style={{ width: "14rem" }} placeholder="What do you need?" value={itemName} onChange={(e) => setItemName(e.target.value)} maxLength={200} />
                <SelectInput style={{ width: "7rem" }} value={uom} onChange={(e) => setUom(e.target.value)} options={UOM_OPTIONS} />
              </>
            )}
            <TextInput style={{ width: "6rem" }} placeholder="Qty" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            <TextInput style={{ minWidth: "8rem", flex: 1 }} placeholder="Note (size, colour, model…)" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />
            <ActionButton size="sm" onClick={addLine}>Add item</ActionButton>
          </div>
          <p className="text-xs text-[var(--muted-foreground)]">
            {mode === "catalogue" ? "Pick something we already buy." : "Not in our product list yet? Describe it - Purchase will source it and set it up."}
          </p>
        </div>
      </div>
    </Modal>
  );
}

// ---- detail ----------------------------------------------------------------------------

function NoteDialog({ title, description, confirmLabel, onClose, onSubmit }: { title: string; description?: string; confirmLabel: string; onClose: () => void; onSubmit: (note: string) => Promise<void> }) {
  const { run, busy, error } = useAsyncAction();
  const [note, setNote] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const ok = await run(async () => {
      await onSubmit(note.trim());
      return true;
    });
    if (ok) onClose();
  };
  return (
    <Modal open onClose={onClose} title={title} description={description}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextArea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note for the requester (optional)" />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Back</ActionButton>
          <ActionButton type="submit" loading={busy}>{confirmLabel}</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

/** Where a requisition is on its way: raised -> manager -> Purchase -> sourcing -> purchase order. */
function Trail({ pr }: { pr: Requisition }) {
  type Step = { label: string; state: "done" | "current" | "todo" | "skipped" | "rejected"; detail?: string };
  const past = (s: string) => !["draft", "cancelled"].includes(s);
  const manager: Step = !pr.managerName && pr.status !== "pending_manager"
    ? { label: "Manager approval", state: pr.status === "draft" ? "todo" : "skipped", detail: pr.status === "draft" ? undefined : "no manager on file" }
    : pr.status === "pending_manager" ? { label: "Manager approval", state: "current", detail: `waiting for ${pr.managerName ?? "the manager"}` }
    : pr.rejectedStage === "manager" ? { label: "Manager approval", state: "rejected", detail: `${pr.managerName ?? "Manager"}: ${pr.managerNote ?? ""}` }
    : pr.managerDecidedAt ? { label: "Manager approval", state: "done", detail: `${pr.managerName}, ${format.date(pr.managerDecidedAt)}${pr.managerNote ? ` — ${pr.managerNote}` : ""}` }
    : { label: "Manager approval", state: "todo" };
  const purchase: Step = pr.status === "submitted" ? { label: "Purchase review", state: "current", detail: "waiting for Purchase" }
    : pr.rejectedStage === "purchase" ? { label: "Purchase review", state: "rejected", detail: `${pr.reviewedByName ?? "Purchase"}: ${pr.reviewNote ?? ""}` }
    : ["approved", "sourcing", "ordered"].includes(pr.status) ? { label: "Purchase review", state: "done", detail: `${pr.reviewedByName ?? "Purchase"}, ${format.date(pr.reviewedAt)}${pr.reviewNote ? ` — ${pr.reviewNote}` : ""}` }
    : { label: "Purchase review", state: "todo" };
  const sourcing: Step = pr.status === "sourcing" ? { label: "Sourcing", state: "current", detail: `${pr.rfqNumber} — collecting and comparing quotations` }
    : pr.rfqNumber && pr.status === "ordered" ? { label: "Sourcing", state: "done", detail: pr.rfqNumber }
    : { label: "Sourcing", state: pr.status === "ordered" ? "skipped" : "todo", detail: pr.status === "ordered" ? "ordered directly" : "optional" };
  const order: Step = pr.status === "ordered" ? { label: "Purchase order", state: "done", detail: pr.purchaseOrderNumber ?? undefined } : { label: "Purchase order", state: "todo" };
  const steps: Step[] = [{ label: "Raised", state: past(pr.status) ? "done" : "current", detail: `${pr.requesterName}, ${format.date(pr.submittedAt ?? pr.createdAt)}` }, manager, purchase, sourcing, order];
  const dot: Record<Step["state"], string> = { done: "var(--success, #16a34a)", current: "var(--primary)", todo: "var(--border)", skipped: "var(--border)", rejected: "var(--destructive, #dc2626)" };
  return (
    <ol className="m-0 flex list-none flex-col gap-1 p-0 text-sm" aria-label="Progress">
      {steps.map((st) => (
        <li key={st.label} className="flex items-baseline gap-2">
          <span aria-hidden className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: dot[st.state] }} />
          <span className={`shrink-0 whitespace-nowrap ${st.state === "todo" || st.state === "skipped" ? "text-[var(--muted-foreground)]" : "font-semibold"}`}>{st.label}</span>
          {st.detail && <span className="text-[var(--muted-foreground)]">{st.detail}</span>}
        </li>
      ))}
    </ol>
  );
}

function DetailDialog({ id, onClose, onCreatePo, onStartSourcing, onOpenRfq }: { id: string; onClose: () => void; onCreatePo?: (pr: Requisition) => void; onStartSourcing?: (pr: Requisition) => void; onOpenRfq?: (rfqId: string) => void }) {
  const { api, can, user } = useAuth();
  const refresh = useRefreshRequisitions();
  const { run, error } = useAsyncAction();
  const [mode, setMode] = useState<"" | "approve" | "reject" | "mgrApprove" | "mgrReject" | "cancel" | "edit">("");
  const path = `${REQUISITION_BASE}/${id}`;
  const detail = useApiQuery<Requisition>(path);
  const pr = detail.data;
  const act = (verb: string, json: unknown = {}) => api("POST", `${path}/${verb}`, { json }).then(() => refresh());

  const own = pr?.requesterId === user?.id;
  const reviewer = can("pr:approve");
  const canEdit = !!pr && own && can("pr:write") && ["draft", "rejected"].includes(pr.status);
  const canCancel = !!pr && ((own && can("pr:write")) || reviewer) && ["draft", "pending_manager", "submitted", "approved", "rejected"].includes(pr.status);
  const canManagerDecide = !!pr && can("pr:team_approve") && !own && pr.status === "pending_manager";
  const canReview = !!pr && reviewer && !own && pr.status === "submitted";
  const canSource = !!pr && reviewer && pr.status === "approved" && can("sourcing:write") && !!onStartSourcing;
  const canOrder = !!pr && reviewer && pr.status === "approved" && can("po:write") && !!onCreatePo;
  const lines = pr?.lines ?? [];

  return (
    <>
      <Modal
        open
        onClose={onClose}
        wide
        title={pr ? `${pr.number} — ${pr.requesterName}` : "Purchase requisition"}
        footer={
          pr && (
            <>
              <ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>
              {canCancel && pr.status !== "draft" && <ActionButton tone="danger" onClick={() => setMode("cancel")}>Cancel requisition</ActionButton>}
              {canCancel && pr.status === "draft" && <ActionButton tone="danger" onClick={() => run(async () => { await act("cancel"); onClose(); })}>Discard draft</ActionButton>}
              {canManagerDecide && <ActionButton tone="danger" onClick={() => setMode("mgrReject")}>Reject</ActionButton>}
              {canManagerDecide && <ActionButton onClick={() => setMode("mgrApprove")}>Approve</ActionButton>}
              {canReview && <ActionButton tone="danger" onClick={() => setMode("reject")}>Reject</ActionButton>}
              {canReview && <ActionButton onClick={() => setMode("approve")}>Approve</ActionButton>}
              {pr.rfqId && onOpenRfq && ["sourcing", "ordered"].includes(pr.status) && <ActionButton tone="ghost" onClick={() => { onOpenRfq(pr.rfqId as string); onClose(); }}>Open {pr.rfqNumber}</ActionButton>}
              {canOrder && <ActionButton tone="ghost" onClick={() => { onCreatePo?.(pr); onClose(); }}>Create purchase order directly</ActionButton>}
              {canSource && <ActionButton onClick={() => { onStartSourcing?.(pr); onClose(); }}>Start sourcing (RFQ)</ActionButton>}
              {canEdit && <ActionButton tone="ghost" onClick={() => setMode("edit")}>Edit</ActionButton>}
              {canEdit && <ActionButton onClick={() => run(async () => { await act("submit"); })}>{pr.status === "rejected" ? "Send again" : "Submit"}</ActionButton>}
            </>
          )
        }
      >
        {pr && (
          <div className="flex flex-col gap-3">
            <InlineError message={error || detail.error?.message} />
            <div className="flex flex-wrap items-center gap-3">
              {statusPill(pr.status)}
              {priorityPill(pr.priority)}
              {pr.purchaseOrderNumber && <span className="text-sm">Purchase order: <b>{pr.purchaseOrderNumber}</b></span>}
            </div>
            {pr.status === "rejected" && (
              <Note tone="warning">
                <b>{pr.rejectedStage === "manager" ? `${pr.managerName ?? "Your manager"} sent this back` : "Purchase sent this back"}</b>: {pr.rejectedStage === "manager" ? pr.managerNote : pr.reviewNote}
                {own ? " - edit it and send it again, or cancel it." : ""}
              </Note>
            )}
            {pr.status === "pending_manager" && <Note>{own ? `Waiting for ${pr.managerName ?? "your manager"} to approve it. It goes to Purchase after that.` : `Waiting for ${pr.managerName ?? "the manager"}'s approval.`}</Note>}
            {pr.status === "cancelled" && pr.cancelledReason && <Note>Cancelled: {pr.cancelledReason}</Note>}
            <Trail pr={pr} />
            <div className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm md:grid-cols-2">
              <span>Department: {pr.department || "—"}</span>
              <span>Needed by: {format.date(pr.requiredBy)}</span>
              <span>Deliver to: {pr.warehouseCode || "—"}</span>
              <span>Raised: {format.dateTime(pr.createdAt)}</span>
            </div>
            <div className="text-sm"><span className="font-bold">Why it is needed: </span>{pr.justification || "—"}</div>
            <DesktopOnly className="w-full">
              <DataTable columns={["Item", "SKU", "Qty", "Note"]} minWidth={0} fit>
                {lines.map((l) => (
                  <tr key={l.id}>
                    <td>{l.itemName}{!l.inCatalogue && <> <Pill tone="muted">New item</Pill></>}</td>
                    <td>{l.sku || "—"}</td>
                    <td>{format.qty(l.quantity, l.uom)}</td>
                    <td>{l.notes || ""}</td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {lines.map((l) => (
                <MobileRecordCard key={l.id}>
                  <MobileRecordRow label="Item" value={l.itemName} />
                  <MobileRecordRow label="SKU" value={l.sku || "—"} />
                  <MobileRecordRow label="Qty" value={format.qty(l.quantity, l.uom)} />
                  {l.notes ? <MobileRecordRow label="Note" value={l.notes} /> : null}
                </MobileRecordCard>
              ))}
            </MobileOnly>
            {(canOrder || canSource) && lines.some((l) => !l.inCatalogue) && (
              <Note tone="warning">Some items are not in the product list yet. They can be quoted, but only catalogue items are carried onto a purchase order - set the others up under Products &amp; BOM first.</Note>
            )}
          </div>
        )}
      </Modal>
      {mode === "mgrApprove" && pr && (
        <NoteDialog title={`Approve ${pr.number}`} description="It then goes to the Purchase department." confirmLabel="Approve" onClose={() => setMode("")} onSubmit={(note) => act("manager-approve", { note: note || null })} />
      )}
      {mode === "mgrReject" && pr && (
        <ReasonDialog title={`Reject ${pr.number}`} description="The requester sees this reason and can edit and send it again." confirmLabel="Reject" minLength={3} placeholder="Why is it being rejected?" onClose={() => setMode("")} onSubmit={(reason) => act("manager-reject", { reason })} />
      )}
      {mode === "approve" && pr && (
        <NoteDialog title={`Approve ${pr.number}`} description="The requester is told it is approved. Then start sourcing, or raise the purchase order directly." confirmLabel="Approve" onClose={() => setMode("")} onSubmit={(note) => act("approve", { note: note || null })} />
      )}
      {mode === "reject" && pr && (
        <ReasonDialog title={`Reject ${pr.number}`} description="The requester sees this reason and can edit and send it again." confirmLabel="Reject" minLength={3} placeholder="Why is it being rejected?" onClose={() => setMode("")} onSubmit={(reason) => act("reject", { reason })} />
      )}
      {mode === "cancel" && pr && (
        <ReasonDialog title={`Cancel ${pr.number}`} confirmLabel="Cancel requisition" minLength={3} placeholder="Why is it being cancelled?" onClose={() => setMode("")} onSubmit={(reason) => act("cancel", { reason }).then(onClose)} />
      )}
      {mode === "edit" && pr && <RequisitionForm initial={pr} onClose={() => setMode("")} onSaved={() => { setMode(""); void refresh(); }} />}
    </>
  );
}

// ---- tab ------------------------------------------------------------------------------

export function RequisitionsTab({ onCreatePo, onStartSourcing, onOpenRfq, openId: externalOpenId, onOpenIdChange }: { onCreatePo?: (pr: Requisition) => void; onStartSourcing?: (pr: Requisition) => void; onOpenRfq?: (rfqId: string) => void; openId?: string; onOpenIdChange?: (id: string) => void }) {
  const { can } = useAuth();
  const refresh = useRefreshRequisitions();
  const reviewer = can("pr:approve");
  const manager = can("pr:team_approve");
  const canRaise = can("pr:write");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [scope, setScope] = useState<"all" | "mine" | "team">("all");
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  const [formOpen, setFormOpen] = useState(false);
  const [localOpenId, setLocalOpenId] = useState("");
  const openId = externalOpenId ?? localOpenId;
  const setOpenId = (id: string) => (onOpenIdChange ? onOpenIdChange(id) : setLocalOpenId(id));

  const counts = useRequisitionCounts(true);
  const list = useApiQuery<ListResponse<Requisition>>(REQUISITION_BASE, { page, limit: 20, q: debounced, status, priority, mine: scope === "mine" ? "true" : "", team: scope === "team" ? "true" : "" });
  const rows = list.data?.data ?? [];
  const waiting = counts.data?.awaitingReview ?? 0;
  const waitingOnMe = counts.data?.awaitingMyApproval ?? 0;
  const link = (r: Requisition) => <button type="button" className="rx-link" onClick={() => setOpenId(r.id)}>{r.number}</button>;
  const showScope = (reviewer || manager) && canRaise;
  const scopeOptions = [{ value: "all", label: "All" }, { value: "mine", label: "Mine" }, ...(manager ? [{ value: "team", label: "My team" }] : [])];

  return (
    <div className="flex w-full flex-col items-start gap-4">
      {manager && waitingOnMe > 0 && !(status === "pending_manager" && scope === "team") && (
        <Note tone="warning">
          {waitingOnMe} requisition{waitingOnMe === 1 ? " from your team is" : "s from your team are"} waiting for your approval.{" "}
          <button type="button" className="rx-link" onClick={() => { setStatus("pending_manager"); setScope("team"); setPage(1); }}>Show them</button>
        </Note>
      )}
      {reviewer && waiting > 0 && status !== "submitted" && (
        <Note tone="warning">
          {waiting} purchase requisition{waiting === 1 ? " is" : "s are"} waiting for Purchase to review.{" "}
          <button type="button" className="rx-link" onClick={() => { setStatus("submitted"); setScope("all"); setPage(1); }}>Show them</button>
        </Note>
      )}
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input className="search-input" style={{ width: "20rem" }} placeholder="Search number, item or requester…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <select className="filter-select" style={{ width: "12rem" }} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? humanise(s)}</option>)}
        </select>
        <select className="filter-select" style={{ width: "10rem" }} value={priority} onChange={(e) => { setPriority(e.target.value); setPage(1); }}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{humanise(p)}</option>)}
        </select>
        {showScope && <Segmented value={scope} onChange={(v) => { setScope(v as "all" | "mine" | "team"); setPage(1); }} options={scopeOptions} />}
        <div className="flex-1" />
        {canRaise && <ActionButton onClick={() => setFormOpen(true)}>New requisition</ActionButton>}
      </div>
      <InlineError message={list.error?.message} />
      {!list.isLoading && rows.length === 0 && (
        <div className="w-full">
          <EmptyState
            title={debounced || status || priority ? "No requisitions match" : (reviewer || manager) && scope !== "mine" ? "Nothing has been raised yet" : "You have not raised a requisition yet"}
            hint={canRaise && !debounced && !status && !priority ? "Need something bought? Press New requisition and tell Purchase what and why." : undefined}
          />
        </div>
      )}
      {rows.length > 0 && (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["Requisition", "Requested by", "Items", "Priority", "Needed by", "Status"]} fit>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{link(r)}</td>
                  <td>{r.requesterName}{r.department ? <span className="text-[var(--muted-foreground)]"> · {r.department}</span> : null}</td>
                  <td>{r.itemsSummary}</td>
                  <td>{priorityPill(r.priority)}</td>
                  <td>{format.date(r.requiredBy)}</td>
                  <td>{statusPill(r.status)}</td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {rows.map((r) => (
              <MobileRecordCard key={r.id}>
                <MobileRecordRow label="Requisition" value={link(r)} />
                <MobileRecordRow label="Requested by" value={r.requesterName} />
                <MobileRecordRow label="Items" value={r.itemsSummary} />
                <MobileRecordRow label="Priority" value={priorityPill(r.priority)} />
                <MobileRecordRow label="Needed by" value={format.date(r.requiredBy)} />
                <MobileRecordRow label="Status" value={statusPill(r.status)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full">
        <Pagination meta={list.data?.meta} onPage={setPage} />
      </div>
      {formOpen && <RequisitionForm onClose={() => setFormOpen(false)} onSaved={(pr) => { setFormOpen(false); void refresh(); setOpenId(pr.id); }} />}
      {openId && <DetailDialog id={openId} onClose={() => setOpenId("")} onCreatePo={onCreatePo} onStartSourcing={onStartSourcing} onOpenRfq={onOpenRfq} />}
    </div>
  );
}
