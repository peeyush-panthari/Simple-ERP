/** Finance: committed AR/AP, payables, receivables, payments, invoices, aging and working capital. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { ReasonDialog } from "@/components/erp/dialogs";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Panel, Pagination, Pill, SelectInput, StatCard, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";

const AP_STATUSES = ["draft", "open", "partially_paid", "settled", "cancelled", "disputed"];
const AR_STATUSES = ["open", "partially_paid", "settled", "written_off", "cancelled"];
// The Invoices tab never lists cancelled orders.
const INVOICE_ORDER_STATUSES = ["confirmed", "allocated", "partially_allocated", "shipped", "partially_shipped", "invoiced", "fulfilled", "partially_fulfilled"];
const PAYMENT_METHODS = ["bank_transfer", "cheque", "cash", "card", "upi"];

const errText = (exc: unknown) => (exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));
const cur = (c?: string | null) => c || "INR";

interface Payment {
  id: string;
  number: string;
  method: string;
  paymentDate?: string | null;
  amount: string;
  currency?: string | null;
  status: string;
  direction?: string;
  partyName?: string;
}
interface Invoice {
  id: string;
  number: string;
  vendorName?: string;
  vendorId?: string;
  customerName?: string;
  customerId?: string;
  orderNumber?: string;
  amount: string;
  paidAmount?: string;
  creditAmount?: string;
  outstanding: string;
  currency?: string | null;
  dueDate?: string | null;
  status: string;
  matchStatus?: string;
  matchNote?: string | null;
  payments?: Payment[];
}

/** Shared list chrome: filter select + error + desktop table / mobile cards. */
function StatusFilter({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <select className="filter-select" value={value} aria-label="Filter by all" onChange={(e) => onChange(e.target.value)}>
      <option value="">all</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

// ---- credit notes (dialog only, reached from AP / AR detail) ------------------------------------

function CreditNoteDialog({ target, onClose, onDone }: { target: { direction: "ar" | "ap"; invoiceId: string; partyId: string }; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = { direction: target.direction === "ar" ? "outbound" : "inbound", partyId: target.partyId, amount: String(f.get("amount") ?? ""), reason: String(f.get("reason") ?? "") };
    body[target.direction === "ar" ? "arInvoiceId" : "apInvoiceId"] = target.invoiceId;
    const ok = await run(async () => { await api("POST", "/api/v1/credit-notes", { json: body }); return true; });
    if (ok) { onClose(); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title="Issue credit note">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="amount" placeholder="Credit note amount" required />
        <TextArea name="reason" placeholder="Reason (min 5 characters)" required />
        <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton type="submit" loading={busy}>Issue credit note</ActionButton></div>
      </form>
    </Modal>
  );
}

// ---- invoice detail dialogs (AP and AR share a shape) ---------------------------------------------

function InvoiceDetail({ kind, id, onClose, onChanged }: { kind: "ap" | "ar"; id: string; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const path = `/api/v1/${kind}/${id}`;
  const q = useApiQuery<Invoice>(path);
  const inv = q.data;
  const [creditOpen, setCreditOpen] = useState(false);
  const c = cur(inv?.currency);
  const payments = (inv?.payments ?? []).map((p) => ({ ...p, amt: format.money(p.amount, cur(p.currency ?? c)), date: format.date(p.paymentDate) }));
  const canCredit = can("payment:approve") && !!inv && inv.outstanding !== "0.000000";

  return (
    <>
      <Modal open onClose={onClose} wide title={inv ? `${inv.number} — ${kind === "ap" ? inv.vendorName : inv.customerName}` : "Invoice"}
        footer={inv && <><ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>{canCredit && <ActionButton tone="ghost" onClick={() => setCreditOpen(true)}>Issue credit note</ActionButton>}</>}>
        {inv && (
          <div className="flex flex-col gap-3">
            <InlineError message={q.error?.message} />
            <div className="flex items-center gap-2">
              <Pill>{inv.status}</Pill>
              {kind === "ap" && <Pill>{`match: ${inv.matchStatus}`}</Pill>}
            </div>
            {kind === "ap" && inv.matchNote && <Note tone="warning">Match note: {inv.matchNote}</Note>}
            <div className="mt-1 flex flex-wrap gap-4 text-sm">
              <span>Amount: {format.money(inv.amount, c)}</span>
              <span>Paid: {format.money(inv.paidAmount, c)}</span>
              {kind === "ar" && <span>Credit: {format.money(inv.creditAmount, c)}</span>}
              <span className="font-bold">Outstanding: {format.money(inv.outstanding, c)}</span>
            </div>
            <h3 className="rx-heading-3 mt-3">Payment history</h3>
            <DesktopOnly className="w-full">
              <DataTable columns={["Payment", "Method", "Date", "Amount", "Status"]} minWidth={0} fit>
                {payments.map((p) => <tr key={p.id}><td>{p.number}</td><td>{p.method}</td><td>{p.date}</td><td>{p.amt}</td><td><Pill>{p.status}</Pill></td></tr>)}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {payments.map((p) => (
                <MobileRecordCard key={p.id}>
                  <MobileRecordRow label="Payment" value={p.number} />
                  <MobileRecordRow label="Method" value={p.method} />
                  <MobileRecordRow label="Date" value={p.date} />
                  <MobileRecordRow label="Amount" value={p.amt} />
                  <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </div>
        )}
      </Modal>
      {creditOpen && inv && (
        <CreditNoteDialog
          target={{ direction: kind, invoiceId: inv.id, partyId: (kind === "ap" ? inv.vendorId : inv.customerId) ?? "" }}
          onClose={() => setCreditOpen(false)}
          onDone={async () => {
            await qc.invalidateQueries({ queryKey: [path] });
            onChanged();
          }}
        />
      )}
    </>
  );
}

// ---- payables --------------------------------------------------------------------------------------

interface ApLine {
  poLineId: string;
  description: string;
  quantity: string;
  unitPrice: string;
  amount: string;
}

function PostApDialog({ onClose, onPosted }: { onClose: () => void; onPosted: () => void }) {
  const { api } = useAuth();
  const [lines, setLines] = useState<ApLine[]>([]);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ matchStatus?: string; matchVariance?: string } | null>(null);
  const [lf, setLf] = useState({ description: "", poLineId: "", quantity: "", unitPrice: "", amount: "" });

  const addLine = () => {
    if (!lf.description || !lf.amount) return;
    setLines([...lines, lf]);
    setLf({ description: "", poLineId: "", quantity: "", unitPrice: "", amount: "" });
  };
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    setError("");
    setResult(null);
    const body: Record<string, unknown> = {
      vendorId: get("vendorId"),
      vendorInvoiceNo: get("vendorInvoiceNo"),
      amount: get("amount"),
      lines: lines.map((l) => ({ ...(l.poLineId ? { poLineId: l.poLineId } : {}), description: l.description, ...(l.quantity ? { quantity: l.quantity } : {}), ...(l.unitPrice ? { unitPrice: l.unitPrice } : {}), amount: l.amount })),
    };
    if (get("poId")) body.poId = get("poId");
    if (get("varianceReason")) body.varianceReason = get("varianceReason");
    try {
      const r = await api<{ matchStatus?: string; matchVariance?: string }>("POST", "/api/v1/ap/invoices", { json: body });
      setResult(r);
      if (["matched", "not_applicable", "variance"].includes(r.matchStatus ?? "")) onPosted();
    } catch (exc) {
      setError(errText(exc));
    }
  };

  return (
    <Modal open onClose={onClose} title="Post vendor invoice" description="Link a PO to run three-way match, or leave it blank for a non-PO invoice." wide>
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        {result && <Note tone={result.matchStatus === "variance" ? "warning" : "info"}>{`matchStatus: ${result.matchStatus}${result.matchVariance ? ` (variance ${result.matchVariance})` : ""}`}</Note>}
        <DataTable columns={["Description", "Amount", ""]} minWidth={0} fit>
          {lines.map((l, i) => <tr key={i}><td>{l.description}</td><td>{format.money(l.amount)}</td><td><ActionButton size="sm" tone="danger" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</ActionButton></td></tr>)}
        </DataTable>
        <div className="flex flex-wrap gap-2">
          <div className="min-w-[10rem] flex-1"><TextInput placeholder="Line description" value={lf.description} onChange={(e) => setLf({ ...lf, description: e.target.value })} /></div>
          <TextInput style={{ width: "10rem" }} placeholder="PO line ID (opt.)" value={lf.poLineId} onChange={(e) => setLf({ ...lf, poLineId: e.target.value })} />
          <TextInput style={{ width: "6rem" }} placeholder="Qty (opt.)" value={lf.quantity} onChange={(e) => setLf({ ...lf, quantity: e.target.value })} />
          <TextInput style={{ width: "8rem" }} placeholder="Unit price (opt.)" value={lf.unitPrice} onChange={(e) => setLf({ ...lf, unitPrice: e.target.value })} />
          <TextInput style={{ width: "8rem" }} placeholder="Amount" value={lf.amount} onChange={(e) => setLf({ ...lf, amount: e.target.value })} />
          <ActionButton size="sm" onClick={addLine}>Add line</ActionButton>
        </div>
        <form onSubmit={submit} className="mt-2 flex flex-col gap-3">
          <TextInput name="vendorId" placeholder="Vendor ID" required />
          <TextInput name="vendorInvoiceNo" placeholder="Vendor's invoice number" required />
          <TextInput name="poId" placeholder="PO ID (optional - enables three-way match)" />
          <TextInput name="amount" placeholder="Total invoice amount" required />
          <TextArea name="varianceReason" placeholder="Variance reason (only needed if three-way match fails)" />
          <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Close</ActionButton><ActionButton type="submit">Post invoice</ActionButton></div>
        </form>
      </div>
    </Modal>
  );
}

function PayablesTab() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [postOpen, setPostOpen] = useState(false);
  const [openId, setOpenId] = useState("");
  const list = useApiQuery<ListResponse<Invoice>>("/api/v1/ap", { page, limit: 20, status });
  const rows = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/ap"] });
  const link = (p: Invoice) => <button type="button" className="rx-link" onClick={() => setOpenId(p.id)}>{p.number}</button>;
  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      {can("invoice:post") && <div className="flex w-full justify-end"><ActionButton onClick={() => setPostOpen(true)}>Post vendor invoice</ActionButton></div>}
      <StatusFilter value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={AP_STATUSES} />
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Invoice", "Vendor", "Amount", "Outstanding", "Due", "Status", "Match"]} fit>
          {rows.map((p) => <tr key={p.id}><td>{link(p)}</td><td>{p.vendorName}</td><td>{format.money(p.amount, cur(p.currency))}</td><td>{format.money(p.outstanding, cur(p.currency))}</td><td>{format.date(p.dueDate)}</td><td><Pill>{p.status}</Pill></td><td><Pill>{p.matchStatus ?? ""}</Pill></td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {rows.map((p) => (
          <MobileRecordCard key={p.id}>
            <MobileRecordRow label="Invoice" value={link(p)} />
            <MobileRecordRow label="Vendor" value={p.vendorName} />
            <MobileRecordRow label="Amount" value={format.money(p.amount, cur(p.currency))} />
            <MobileRecordRow label="Outstanding" value={format.money(p.outstanding, cur(p.currency))} />
            <MobileRecordRow label="Due" value={format.date(p.dueDate)} />
            <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
            <MobileRecordRow label="Match" value={<Pill>{p.matchStatus ?? ""}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {postOpen && <PostApDialog onClose={() => { setPostOpen(false); void refresh(); }} onPosted={refresh} />}
      {openId && <InvoiceDetail kind="ap" id={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
    </div>
  );
}

// ---- receivables -----------------------------------------------------------------------------------

function ReceivablesTab() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState("");
  const list = useApiQuery<ListResponse<Invoice>>("/api/v1/ar", { page, limit: 20, status });
  const rows = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/ar"] });
  const link = (p: Invoice) => <button type="button" className="rx-link" onClick={() => setOpenId(p.id)}>{p.number}</button>;
  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      <p className="text-xs text-[var(--muted-foreground)]">Receivables are only ever created automatically when a sales order is invoiced - there is no manual entry form here, matching Node exactly.</p>
      <StatusFilter value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={AR_STATUSES} />
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Invoice", "Customer", "Order", "Amount", "Outstanding", "Due", "Status"]} fit>
          {rows.map((p) => <tr key={p.id}><td>{link(p)}</td><td>{p.customerName}</td><td>{p.orderNumber}</td><td>{format.money(p.amount, cur(p.currency))}</td><td>{format.money(p.outstanding, cur(p.currency))}</td><td>{format.date(p.dueDate)}</td><td><Pill>{p.status}</Pill></td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {rows.map((p) => (
          <MobileRecordCard key={p.id}>
            <MobileRecordRow label="Invoice" value={link(p)} />
            <MobileRecordRow label="Customer" value={p.customerName} />
            <MobileRecordRow label="Order" value={p.orderNumber} />
            <MobileRecordRow label="Amount" value={format.money(p.amount, cur(p.currency))} />
            <MobileRecordRow label="Outstanding" value={format.money(p.outstanding, cur(p.currency))} />
            <MobileRecordRow label="Due" value={format.date(p.dueDate)} />
            <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {openId && <InvoiceDetail kind="ar" id={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
    </div>
  );
}

// ---- payments ---------------------------------------------------------------------------------------

function RecordPaymentDialog({ direction, onClose, onDone }: { direction: "inbound" | "outbound"; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const [allocs, setAllocs] = useState<{ invoiceId: string; amount: string }[]>([]);
  const [inv, setInv] = useState("");
  const [amt, setAmt] = useState("");
  const { run, busy, error, setError } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!allocs.length) return setError("Add at least one allocation");
    const f = new FormData(e.currentTarget);
    const ok = await run(async () => {
      await api("POST", direction === "inbound" ? "/api/v1/ar/payments" : "/api/v1/ap/payments", { json: { partyId: String(f.get("partyId") ?? ""), amount: String(f.get("amount") ?? ""), method: String(f.get("method") || "bank_transfer"), allocations: allocs } });
      return true;
    });
    if (ok) { onClose(); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title={direction === "inbound" ? "Record customer receipt" : "Record vendor payment"}>
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        <DataTable columns={["Invoice ID", "Amount", ""]} minWidth={0} fit>
          {allocs.map((a, i) => <tr key={i}><td>{a.invoiceId}</td><td>{format.money(a.amount)}</td><td><ActionButton size="sm" tone="danger" onClick={() => setAllocs(allocs.filter((_, j) => j !== i))}>Remove</ActionButton></td></tr>)}
        </DataTable>
        <div className="flex gap-2">
          <TextInput placeholder="Invoice ID" value={inv} onChange={(e) => setInv(e.target.value)} />
          <TextInput style={{ width: "8rem" }} placeholder="Amount" value={amt} onChange={(e) => setAmt(e.target.value)} />
          <ActionButton size="sm" onClick={() => { if (inv && amt) { setAllocs([...allocs, { invoiceId: inv, amount: amt }]); setInv(""); setAmt(""); } }}>Add allocation</ActionButton>
        </div>
        <form onSubmit={submit} className="mt-2 flex flex-col gap-3">
          <TextInput name="partyId" placeholder="Party (vendor/customer) ID" required />
          <TextInput name="amount" placeholder="Total payment amount" required />
          <SelectInput name="method" defaultValue="bank_transfer" options={PAYMENT_METHODS.map((m) => ({ value: m, label: m }))} />
          <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton type="submit" loading={busy}>Record payment</ActionButton></div>
        </form>
      </div>
    </Modal>
  );
}

function PaymentsTab() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const [direction, setDirection] = useState("");
  const [page, setPage] = useState(1);
  const [record, setRecord] = useState<"" | "inbound" | "outbound">("");
  const [reverseId, setReverseId] = useState("");
  const [approveError, setApproveError] = useState("");
  const list = useApiQuery<ListResponse<Payment>>("/api/v1/payments", { page, limit: 20, direction });
  const rows = list.data?.data ?? [];
  const canApprove = can("payment:approve");
  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["/api/v1/payments"] });
    await qc.invalidateQueries({ queryKey: ["/api/v1/ar"] });
    await qc.invalidateQueries({ queryKey: ["/api/v1/ap"] });
  };
  const approve = async (id: string) => {
    setApproveError("");
    try {
      await api("POST", `/api/v1/payments/${id}/approve`, { json: {} });
      await refresh();
    } catch (exc) {
      setApproveError(errText(exc));
    }
  };
  const actions = (p: Payment, cls = ""): ReactNode => (
    <div className="flex gap-2">
      {p.status === "pending_approval" && canApprove && <ActionButton size="sm" tone="ghost" className={cls} onClick={() => approve(p.id)}>Approve</ActionButton>}
      {p.status === "posted" && canApprove && <ActionButton size="sm" tone="danger" className={cls} onClick={() => setReverseId(p.id)}>Reverse</ActionButton>}
    </div>
  );
  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      {can("payment:write") && (
        <div className="flex w-full justify-end gap-2">
          <ActionButton tone="ghost" onClick={() => setRecord("outbound")}>Record AP payment</ActionButton>
          <ActionButton onClick={() => setRecord("inbound")}>Record AR payment</ActionButton>
        </div>
      )}
      <select className="filter-select" value={direction} aria-label="Filter by all" onChange={(e) => { setDirection(e.target.value); setPage(1); }}>
        <option value="">all</option><option value="inbound">inbound</option><option value="outbound">outbound</option>
      </select>
      <InlineError message={list.error?.message} />
      <InlineError message={approveError} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Payment", "Direction", "Party", "Amount", "Date", "Status", ""]} fit>
          {rows.map((p) => <tr key={p.id}><td>{p.number}</td><td><Pill>{p.direction ?? ""}</Pill></td><td>{p.partyName}</td><td>{format.money(p.amount, cur(p.currency))}</td><td>{format.date(p.paymentDate)}</td><td><Pill>{p.status}</Pill></td><td>{actions(p)}</td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {rows.map((p) => (
          <MobileRecordCard key={p.id} actions={actions(p, "w-full justify-center")}>
            <MobileRecordRow label="Payment" value={p.number} />
            <MobileRecordRow label="Direction" value={<Pill>{p.direction ?? ""}</Pill>} />
            <MobileRecordRow label="Party" value={p.partyName} />
            <MobileRecordRow label="Amount" value={format.money(p.amount, cur(p.currency))} />
            <MobileRecordRow label="Date" value={format.date(p.paymentDate)} />
            <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {record && <RecordPaymentDialog direction={record} onClose={() => setRecord("")} onDone={refresh} />}
      {reverseId && (
        <ReasonDialog
          title="Reverse payment"
          description="A reversal posts immediately and does not notify Order/Party - their settlement state can diverge after this."
          confirmLabel="Confirm reversal"
          onClose={() => setReverseId("")}
          onSubmit={async (reason) => {
            await api("POST", `/api/v1/payments/${reverseId}/reverse`, { json: { reason } });
            await refresh();
          }}
        />
      )}
    </div>
  );
}

// ---- invoices ---------------------------------------------------------------------------------------

interface OrderRow {
  id: string;
  number: string;
  customerName: string;
  orderDate?: string | null;
  total?: string;
  currency?: string | null;
  status: string;
  statusLabel: string;
  invoiceId?: string | null;
  invoiceNumber?: string | null;
}

function InvoicesTab() {
  const { api, apiBlob, can } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [invoiced, setInvoiced] = useState("");
  const [customer, setCustomer] = useState("");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  // Invoicing is decoupled from order status: Generate is enabled at any status, once per order; Download once an invoice exists.
  const list = useApiQuery<ListResponse<OrderRow>>("/api/v1/orders", { limit: 200 });
  const all = (list.data?.data ?? []).filter((o) => o.status !== "cancelled");
  const cust = customer.trim().toLowerCase();
  const q = search.trim().toLowerCase();
  const rows = all
    .filter((o) => !status || o.status === status)
    .filter((o) => invoiced !== "yes" || !!o.invoiceId)
    .filter((o) => invoiced !== "no" || !o.invoiceId)
    .filter((o) => !cust || (o.customerName ?? "").toLowerCase().includes(cust))
    .filter((o) => !q || (o.number ?? "").toLowerCase().includes(q) || (o.invoiceNumber ?? "").toLowerCase().includes(q));

  const generate = async (id: string) => {
    setError("");
    setBusyId(id);
    try {
      await api("POST", `/api/v1/orders/${id}/invoice`, { json: {} });
      await qc.invalidateQueries({ queryKey: ["/api/v1/orders"] });
    } catch (exc) {
      setError(errText(exc));
    } finally {
      setBusyId("");
    }
  };
  const download = async (o: OrderRow) => {
    setError("");
    try {
      const { blob, contentType } = await apiBlob(`/api/v1/orders/${o.id}/invoice/download`);
      const mime = contentType.split(";")[0].trim();
      downloadBlob(blob, `${o.number}-invoice.${mime === "application/pdf" ? "pdf" : "html"}`);
    } catch (exc) {
      setError(errText(exc));
    }
  };
  const statusCell = (o: OrderRow) => <div className="flex items-center gap-2"><Pill>{o.statusLabel}</Pill>{o.invoiceId && <Pill tone="success">Invoiced</Pill>}</div>;
  const buttons = (o: OrderRow, cls = "") => (
    <div className="flex gap-2">
      {can("order:invoice") && <ActionButton size="sm" className={cls} disabled={!!o.invoiceId || busyId === o.id} onClick={() => generate(o.id)}>Generate Invoice</ActionButton>}
      <ActionButton size="sm" tone="ghost" className={cls} disabled={!o.invoiceId} onClick={() => download(o)}>Download Invoice</ActionButton>
    </div>
  );

  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      <InlineError message={error || list.error?.message} />
      <div className="flex flex-wrap gap-2">
        <div className="flex items-center gap-1"><span className="text-xs text-[var(--muted-foreground)]">Status</span><StatusFilter value={status} onChange={setStatus} options={INVOICE_ORDER_STATUSES} /></div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-[var(--muted-foreground)]">Invoiced</span>
          <select className="filter-select" value={invoiced} aria-label="Filter by all" onChange={(e) => setInvoiced(e.target.value)}><option value="">all</option><option value="yes">yes</option><option value="no">no</option></select>
        </div>
        <TextInput style={{ width: "12rem" }} placeholder="Customer" value={customer} onChange={(e) => setCustomer(e.target.value)} />
        <TextInput style={{ width: "16rem" }} placeholder="Search order ID / invoice ID" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <DesktopOnly className="w-full">
        <DataTable columns={["Order", "Customer", "Date", "Total", "Status", ""]} fit>
          {rows.map((o) => <tr key={o.id}><td>{o.number}</td><td>{o.customerName}</td><td>{format.date(o.orderDate)}</td><td>{format.money(o.total, cur(o.currency))}</td><td>{statusCell(o)}</td><td>{buttons(o)}</td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {rows.map((o) => (
          <MobileRecordCard key={o.id} actions={buttons(o, "w-full justify-center")}>
            <MobileRecordRow label="Order" value={o.number} />
            <MobileRecordRow label="Customer" value={o.customerName} />
            <MobileRecordRow label="Date" value={format.date(o.orderDate)} />
            <MobileRecordRow label="Total" value={format.money(o.total, cur(o.currency))} />
            <MobileRecordRow label="Status" value={statusCell(o)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

// ---- aging ------------------------------------------------------------------------------------------

interface AgingReport {
  total?: string;
  buckets?: Record<string, string>;
  documents?: { number: string; partyName: string; dueDate?: string | null; outstanding: string; bucket: string }[];
}

function AgingTab() {
  const [side, setSide] = useState("ap");
  const ap = useApiQuery<AgingReport>("/api/v1/ap/aging");
  const ar = useApiQuery<AgingReport>("/api/v1/ar/aging");
  const report = (side === "ap" ? ap.data : ar.data) ?? {};
  const b = report.buckets ?? {};
  const docs = (report.documents ?? []).map((d) => ({ ...d, due: format.date(d.dueDate), out: format.money(d.outstanding) }));
  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      <select className="filter-select" value={side} aria-label="Filter by ap" onChange={(e) => setSide(e.target.value)}><option value="ap">ap</option><option value="ar">ar</option></select>
      <InlineError message={ap.error?.message || ar.error?.message} />
      <div className="flex flex-wrap gap-3">
        <StatCard label="Total outstanding" value={format.money(report.total)} />
        {["current", "0-30", "31-60", "61-90", "90+"].map((k) => <StatCard key={k} label={k === "current" ? "Current" : k} value={format.money(b[k])} />)}
      </div>
      <DesktopOnly className="w-full">
        <DataTable columns={["Document", "Party", "Due", "Outstanding", "Bucket"]} fit>
          {docs.map((d, i) => <tr key={i}><td>{d.number}</td><td>{d.partyName}</td><td>{d.due}</td><td>{d.out}</td><td><Pill>{d.bucket}</Pill></td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {docs.map((d, i) => (
          <MobileRecordCard key={i}>
            <MobileRecordRow label="Document" value={d.number} />
            <MobileRecordRow label="Party" value={d.partyName} />
            <MobileRecordRow label="Due" value={d.due} />
            <MobileRecordRow label="Outstanding" value={d.out} />
            <MobileRecordRow label="Bucket" value={<Pill>{d.bucket}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

// ---- working capital -------------------------------------------------------------------------------

interface WorkingCapital {
  complete?: boolean;
  incompleteReason?: string | null;
  workingCapital?: string;
  components?: { inventoryValue?: string };
  receivables?: { outstanding?: string };
  payables?: { outstanding?: string };
  trend?: { month: string; ar?: string; ap?: string; inventory?: string | null }[];
}

function WorkingCapitalTab() {
  const wcQ = useApiQuery<WorkingCapital>("/api/v1/working-capital");
  const cycleQ = useApiQuery<{ daysSalesOutstanding?: string | number; daysPayablesOutstanding?: string | number }>("/api/v1/working-capital/cycle");
  const wc = wcQ.data;
  const cycle = cycleQ.data;
  const trend = (wc?.trend ?? []).map((t) => ({ ...t, ar: format.money(t.ar), ap: format.money(t.ap), inv: t.inventory !== null && t.inventory !== undefined && t.inventory !== "" ? format.money(t.inventory) : "—" }));
  return (
    <div className="flex w-full flex-col items-start gap-3 pt-4">
      <InlineError message={wcQ.error?.message || cycleQ.error?.message} />
      {wc && wc.complete === false && <Note tone="warning">{wc.incompleteReason}</Note>}
      <div className="flex flex-wrap gap-3">
        <StatCard label="Working capital" value={format.money(wc?.workingCapital)} />
        <StatCard label="Inventory value" value={format.money(wc?.components?.inventoryValue)} />
        <StatCard label="AR outstanding" value={format.money(wc?.receivables?.outstanding)} />
        <StatCard label="AP outstanding" value={format.money(wc?.payables?.outstanding)} />
        <StatCard label="Days sales outstanding" value={String(cycle?.daysSalesOutstanding ?? "")} />
        <StatCard label="Days payables outstanding" value={String(cycle?.daysPayablesOutstanding ?? "")} />
      </div>
      <h3 className="rx-heading-3 mt-2">Trend (cumulative - not a historical snapshot)</h3>
      <DesktopOnly className="w-full">
        <DataTable columns={["Month", "AR", "AP", "Inventory"]} fit>
          {trend.map((t) => <tr key={t.month}><td>{t.month}</td><td>{t.ar}</td><td>{t.ap}</td><td>{t.inv}</td></tr>)}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {trend.map((t) => (
          <MobileRecordCard key={t.month}>
            <MobileRecordRow label="Month" value={t.month} />
            <MobileRecordRow label="AR" value={t.ar} />
            <MobileRecordRow label="AP" value={t.ap} />
            <MobileRecordRow label="Inventory" value={t.inv} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

// ---- committed AR/AP ---------------------------------------------------------------------------------

interface Committed {
  ap?: { total?: string; documents?: { number: string; vendorName: string; status: string; poDate?: string | null; committed: string; currency?: string | null }[] };
  ar?: { total?: string; documents?: { number: string; customerName: string; status: string; orderDate?: string | null; committed: string; currency?: string | null }[] };
}

function CommittedTab() {
  const q = useApiQuery<Committed>("/api/v1/finance/committed");
  const ap = (q.data?.ap?.documents ?? []).map((d) => ({ ...d, amt: format.money(d.committed, cur(d.currency)), date: format.date(d.poDate) }));
  const ar = (q.data?.ar?.documents ?? []).map((d) => ({ ...d, amt: format.money(d.committed, cur(d.currency)), date: format.date(d.orderDate) }));
  return (
    <div className="flex w-full flex-col items-start gap-4 pt-4">
      <InlineError message={q.error?.message} />
      <Panel title="Committed AP" subtitle="Purchase orders issued to a vendor but not yet received (GRN pending) — the future payable that hasn't posted yet." className="w-full">
        <div>
          <div className="mb-2 flex gap-3"><StatCard label="Committed payables" value={format.money(q.data?.ap?.total, "INR")} /></div>
          <DesktopOnly className="w-full">
            <DataTable columns={["PO", "Vendor", "Status", "PO date", "Committed"]} minWidth={0} fit>
              {ap.map((d, i) => <tr key={i}><td>{d.number}</td><td>{d.vendorName}</td><td><Pill>{d.status}</Pill></td><td>{d.date}</td><td>{d.amt}</td></tr>)}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {ap.map((d, i) => (
              <MobileRecordCard key={i}>
                <MobileRecordRow label="PO" value={d.number} />
                <MobileRecordRow label="Vendor" value={d.vendorName} />
                <MobileRecordRow label="Status" value={<Pill>{d.status}</Pill>} />
                <MobileRecordRow label="PO date" value={d.date} />
                <MobileRecordRow label="Committed" value={d.amt} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </div>
      </Panel>
      <Panel title="Committed AR" subtitle="Confirmed orders not yet allocated to stock — the future receivable that hasn't posted yet." className="w-full">
        <div>
          <div className="mb-2 flex gap-3"><StatCard label="Committed receivables" value={format.money(q.data?.ar?.total, "INR")} /></div>
          <DesktopOnly className="w-full">
            <DataTable columns={["Order", "Customer", "Status", "Order date", "Committed"]} minWidth={0} fit>
              {ar.map((d, i) => <tr key={i}><td>{d.number}</td><td>{d.customerName}</td><td><Pill>{d.status}</Pill></td><td>{d.date}</td><td>{d.amt}</td></tr>)}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {ar.map((d, i) => (
              <MobileRecordCard key={i}>
                <MobileRecordRow label="Order" value={d.number} />
                <MobileRecordRow label="Customer" value={d.customerName} />
                <MobileRecordRow label="Status" value={<Pill>{d.status}</Pill>} />
                <MobileRecordRow label="Order date" value={d.date} />
                <MobileRecordRow label="Committed" value={d.amt} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </div>
      </Panel>
    </div>
  );
}

export default function FinancePage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("finance:read") ? (
        <div className="flex w-full flex-col items-start gap-4">
          <PageHeader eyebrow="Demand" title="Finance" />
          <Tabs
            tabs={[
              { value: "committed", label: "Committed AR/AP", content: <CommittedTab /> },
              { value: "ap", label: "Account Payables", content: <PayablesTab /> },
              { value: "ar", label: "Account Receivables", content: <ReceivablesTab /> },
              { value: "payments", label: "Payments", content: <PaymentsTab /> },
              { value: "invoices", label: "Invoices", content: <InvoicesTab /> },
              { value: "aging", label: "Aging", content: <AgingTab /> },
              { value: "working_capital", label: "Working capital", content: <WorkingCapitalTab /> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="finance:read" />
      )}
    </Shell>
  );
}
