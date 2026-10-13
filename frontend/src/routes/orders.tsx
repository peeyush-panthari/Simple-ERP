/** Orders: Sales Book (create / list / detail / cancel / bulk upload) and Order Allocation (manual FG unit picking). */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { ReasonDialog } from "@/components/erp/dialogs";
import { OrderAllocation } from "@/components/erp/order-allocation";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, StatCard, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, type ListResponse } from "@/lib/hooks";
import { GST_RATE_OPTIONS } from "@/lib/reference";
import { humanise } from "@/lib/status";
import { readBase64, MAX_UPLOAD_BYTES } from "@/lib/production";

interface Order {
  id: string;
  number: string;
  customerName: string;
  status: string;
  statusLabel: string;
  invoiceId?: string | null;
  total?: string;
  subtotal?: string;
  taxTotal?: string;
  promisedDate?: string | null;
  logisticsCostBorneBy?: string | null;
  customerRef?: string | null;
  paymentTerms?: string | null;
  inverterDetails?: string | null;
  inverterAttachment?: { filename: string; url: string } | null;
  accessoriesRequired?: string | null;
  branding?: string | null;
  settlement?: { paidAmount?: string; outstanding?: string; paidPercent?: string; fullyPaid?: boolean } | null;
  lines?: OrderLine[];
}
interface OrderLine {
  id: string;
  sku: string;
  productName?: string | null;
  quantity: string;
  uom?: string;
  unitPrice?: string;
  grossAmount?: string;
  status: string;
  allocation?: { batchNo?: string | null; quantity?: string; status?: string } | null;
}
interface Party {
  id: string;
  code: string;
  displayName: string;
}
interface Product {
  id: string;
  sku: string;
  name: string;
  uom?: string;
}
interface StagedLine {
  productId: string;
  sku: string;
  productName: string;
  quantity: string;
  uom: string;
  unitPrice: string;
  taxCode: string;
}

const UOMS = ["UNIT", "KG", "G", "M", "MM", "L", "BOX"];
const STATUSES = ["confirmed", "allocated", "partially_allocated", "shipped", "partially_shipped", "invoiced", "fulfilled", "partially_fulfilled", "cancelled"];
const LOGISTICS_COST_OPTIONS = ["Simple", "Client", "Equally shared"];
const GST_LABELS = Object.fromEntries(GST_RATE_OPTIONS.map((o) => [o.value, o.label]));

// Mirrors the backend's BULK_UPLOAD_ALL_COLUMNS in the orders route: one row per SO line, grouped by soRef.
const BULK_COLUMNS = ["soRef", "customerCode", "customerRef", "promisedDate", "paymentTerms", "deliveryLine1", "deliveryCity", "deliveryStateCode", "deliveryPostalCode", "productSku", "quantity", "uom", "unitPrice", "taxCode"];
const BULK_SAMPLE =
  `${BULK_COLUMNS.join(",")}\n` +
  "SO1,PTY-0001,,2026-09-25,NET30,,,,,SKU-001,10,UNIT,500.00,GST18\n" +
  "SO1,PTY-0001,,2026-09-25,NET30,,,,,SKU-002,5,UNIT,250.00,GST18\n" +
  "SO2,PTY-0002,,2026-09-28,NET15,12 Custom Delivery Rd,Mumbai,27,400001,SKU-003,2,UNIT,1200.00,GST5\n";

const dash = (v: string | null | undefined) => v || "—";

/** Search-or-browse box: focusing the (empty) input loads a browsable list; typing narrows it via the endpoint's `q` filter. */
function SearchPicker<T extends { id: string }>({
  path, params, placeholder, chosen, onChoose, onClear, render, choiceLabel, width,
}: {
  path: string;
  params: Record<string, string | number>;
  placeholder: string;
  chosen: boolean;
  onChoose: (row: T) => void;
  onClear: () => void;
  render: (row: T) => ReactNode;
  choiceLabel: string;
  width?: string;
}) {
  const { api } = useAuth();
  const [text, setText] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const search = async (value: string) => {
    setText(value);
    try {
      setResults((await api<ListResponse<T>>("GET", path, { params: { ...params, ...(value.trim() ? { q: value } : {}) } })).data);
    } catch {
      setResults([]);
    }
  };
  if (chosen) {
    return (
      <div className="flex gap-2" style={{ width }}>
        <TextInput value={choiceLabel} readOnly />
        <ActionButton size="sm" tone="ghost" onClick={() => { setText(""); setResults([]); onClear(); }}>{width ? "×" : "Change"}</ActionButton>
      </div>
    );
  }
  return (
    <div className="relative" style={{ width: width ?? "100%" }}>
      <TextInput placeholder={placeholder} value={text} onChange={(e) => { onClear(); void search(e.target.value); }} onFocus={() => { if (!results.length) void search(text); }} />
      {results.length > 0 && (
        <div className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded border border-[var(--border)] bg-[var(--card)] shadow-md">
          {results.map((r) => (
            <div key={r.id} className="cursor-pointer px-2.5 py-1.5 hover:bg-[var(--muted)]" onClick={() => { onChoose(r); setResults([]); }}>{render(r)}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- create ---------------------------------------------------------------------------------

function CreateDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { api } = useAuth();
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [customer, setCustomer] = useState<Party | null>(null);
  const [lines, setLines] = useState<StagedLine[]>([]);
  const [product, setProduct] = useState<Product | null>(null);
  const [lineUom, setLineUom] = useState("UNIT");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [gst, setGst] = useState("GST18");
  const [f, setF] = useState({ customerRef: "", paymentTerms: "", inverterDetails: "", accessoriesRequired: "", branding: "", logisticsCostBorneBy: "" });
  const set = (k: keyof typeof f, v: string) => setF((p) => ({ ...p, [k]: v }));
  const [attach, setAttach] = useState<{ filename: string; contentType: string; base64: string } | null>(null);
  const [attachOpen, setAttachOpen] = useState(false);
  const [attachError, setAttachError] = useState("");

  const addLine = () => {
    if (!product || !qty || !price) return;
    setLines([...lines, { productId: product.id, sku: product.sku, productName: product.name, quantity: qty, uom: lineUom || "UNIT", unitPrice: price, taxCode: gst || "GST18" }]);
    setProduct(null);
    setLineUom("UNIT");
    setQty("");
    setPrice("");
    setGst("GST18");
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) return setAttachError("File is too large — 10MB max");
    setAttach({ filename: file.name, contentType: file.type || "application/pdf", base64: await readBase64(file) });
    setAttachError("");
  };

  const submit = async (override = false) => {
    setError("");
    setErrorCode("");
    if (!customer) return setError("Search for and select a customer");
    if (!lines.length) return setError("Add at least one line");
    const body: Record<string, unknown> = {
      customerId: customer.id,
      // No warehouse/promised date here - the server routes to the warehouse that can best fulfil the lines and defaults the date.
      lines: lines.map((l) => ({ productId: l.productId, quantity: l.quantity, uom: l.uom, unitPrice: l.unitPrice, taxCode: l.taxCode })),
    };
    for (const k of ["customerRef", "paymentTerms", "inverterDetails", "accessoriesRequired", "branding", "logisticsCostBorneBy"] as const) if (f[k]) body[k] = f[k];
    if (attach) Object.assign(body, { inverterDetailsFilename: attach.filename, inverterDetailsContentType: attach.contentType, inverterDetailsContentBase64: attach.base64 });
    // No draft stage: creation confirms the order, running the credit-limit check; a resubmit can override it.
    if (override) body.allowCreditOverride = true;
    setBusy(true);
    try {
      await api("POST", "/api/v1/orders", { json: body });
      onClose();
      onCreated();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
      setErrorCode(exc instanceof ApiError ? (exc.code ?? "") : "");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Modal open onClose={onClose} title="New sales order" description="Records the order as received from the customer. Allocation, shipping and invoicing happen in other modules." maxWidth="52rem" wide
        footer={<><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton loading={busy} onClick={() => submit(false)}>Create</ActionButton></>}>
        <div className="flex flex-col gap-3">
          <InlineError message={error} />
          {errorCode === "CREDIT_LIMIT_EXCEEDED" && <div><ActionButton size="sm" className="!bg-[var(--warning)]" onClick={() => submit(true)}>Create anyway (override credit limit)</ActionButton></div>}
          <p className="text-xs text-[var(--muted-foreground)]">Customer</p>
          <SearchPicker<Party>
            path="/api/v1/parties"
            params={{ type: "customer", status: "active", limit: 50 }}
            placeholder="Search or browse customers…"
            chosen={!!customer}
            choiceLabel={customer?.displayName ?? ""}
            onChoose={setCustomer}
            onClear={() => setCustomer(null)}
            render={(p) => <><p className="text-sm font-medium">{p.displayName}</p><p className="text-xs text-[var(--muted-foreground)]">{p.code}</p></>}
          />
          <TextInput placeholder="Customer PO number (optional)" value={f.customerRef} onChange={(e) => set("customerRef", e.target.value)} />
          <DesktopOnly className="mt-2 w-full">
            <DataTable columns={["SKU Name", "Qty", "Price (excl. GST)", "GST", ""]} minWidth={0} fit>
              {lines.map((l, i) => (
                <tr key={i}>
                  <td>{l.productName}</td><td>{format.qty(l.quantity, l.uom)}</td><td>{format.money(l.unitPrice)}</td><td>{GST_LABELS[l.taxCode] ?? l.taxCode}</td>
                  <td><ActionButton size="sm" tone="danger" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</ActionButton></td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="mt-2 w-full">
            {lines.map((l, i) => (
              <MobileRecordCard key={i} actions={<ActionButton size="sm" tone="danger" className="w-full justify-center" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</ActionButton>}>
                <MobileRecordRow label="SKU Name" value={l.productName} />
                <MobileRecordRow label="Qty" value={format.qty(l.quantity, l.uom)} />
                <MobileRecordRow label="Price (excl. GST)" value={format.money(l.unitPrice)} />
                <MobileRecordRow label="GST" value={GST_LABELS[l.taxCode] ?? l.taxCode} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
          <div className="flex flex-wrap items-start gap-2">
            <SearchPicker<Product>
              path="/api/v1/products"
              params={{ status: "active", sellable: "true", limit: 50 }}
              placeholder="Search or browse SKUs…"
              chosen={!!product}
              choiceLabel={product?.sku ?? ""}
              width="min(14rem, calc(100vw - 2rem))"
              onChoose={(p) => { setProduct(p); setLineUom(p.uom || "UNIT"); }}
              onClear={() => { setProduct(null); setLineUom("UNIT"); }}
              render={(p) => <><p className="text-sm font-medium">{p.sku}</p><p className="text-xs text-[var(--muted-foreground)]">{p.name}</p></>}
            />
            <TextInput style={{ width: "6rem" }} placeholder="Qty" value={qty} onChange={(e) => setQty(e.target.value)} />
            <SelectInput style={{ width: "6rem" }} value={lineUom} onChange={(e) => setLineUom(e.target.value)} options={UOMS.map((u) => ({ value: u, label: u }))} />
            <TextInput style={{ width: "9rem" }} placeholder="Unit price (excl. GST)" value={price} onChange={(e) => setPrice(e.target.value)} />
            <SelectInput style={{ width: "6rem" }} value={gst} onChange={(e) => setGst(e.target.value)} options={GST_RATE_OPTIONS} />
            <ActionButton size="sm" onClick={addLine}>Add line</ActionButton>
          </div>
          <p className="text-xs text-[var(--muted-foreground)]">Unit price is excluding GST — GST is added per line at the selected rate.</p>
          <div><ActionButton tone="ghost" onClick={() => setAttachOpen(true)}>{attach ? `Attached: ${attach.filename}` : "Attach document"}</ActionButton></div>
          <TextInput placeholder="Payment terms (optional, e.g. NET30)" value={f.paymentTerms} onChange={(e) => set("paymentTerms", e.target.value)} />
          <TextArea placeholder="Inverter details (model, capacity, etc.)" value={f.inverterDetails} onChange={(e) => set("inverterDetails", e.target.value)} />
          <TextArea placeholder="Accessories required" value={f.accessoriesRequired} onChange={(e) => set("accessoriesRequired", e.target.value)} />
          <TextInput placeholder="Branding" value={f.branding} onChange={(e) => set("branding", e.target.value)} />
          <div className="flex flex-col gap-1">
            <span className="shrink-0 text-sm">Logistics cost to be borne by</span>
            <div className="w-full"><SelectInput value={f.logisticsCostBorneBy} onChange={(e) => set("logisticsCostBorneBy", e.target.value)} placeholder="Select…" options={LOGISTICS_COST_OPTIONS.map((o) => ({ value: o, label: o }))} /></div>
          </div>
        </div>
      </Modal>
      {attachOpen && (
        <Modal open onClose={() => setAttachOpen(false)} title="Attach a document" description="Attached to this order's inverter details." footer={<ActionButton onClick={() => setAttachOpen(false)}>Done</ActionButton>}>
          <div className="flex flex-col gap-3">
            <InlineError message={attachError} />
            {attach ? (
              <div className="flex items-center justify-between text-sm"><span>{attach.filename}</span><ActionButton size="sm" tone="danger" onClick={() => { setAttach(null); setAttachError(""); }}>Remove</ActionButton></div>
            ) : (
              <label className="flex cursor-pointer flex-col items-center gap-1 rx-upload text-center text-sm hover:bg-[var(--secondary)]">
                <span>Drag &amp; drop a document here, or click to select</span>
                <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="hidden" onChange={(e) => void onFile(e.target.files?.[0])} />
              </label>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}

// ---- detail ----------------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex w-full gap-3">
      <span className="w-44 shrink-0 text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

function DetailDialog({ orderId, onClose, onChanged }: { orderId: string; onClose: () => void; onChanged: () => void }) {
  const { api, apiBlob, can } = useAuth();
  const qc = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [error, setError] = useState("");
  const path = `/api/v1/orders/${orderId}`;
  const q = useApiQuery<Order>(path);
  const o = q.data;
  const s = o?.settlement ?? {};
  // Only while confirmed/allocated/partially_allocated - not once anything has shipped.
  const canCancel = can("order:cancel") && !!o && ["confirmed", "allocated", "partially_allocated"].includes(o.status);

  const lines = (o?.lines ?? []).map((l) => {
    const a = l.allocation;
    return {
      ...l,
      name: l.productName || l.sku,
      qty: format.qty(l.quantity, l.uom),
      price: format.money(l.unitPrice),
      gross: format.money(l.grossAmount),
      allocText: a ? `${format.qty(a.quantity, l.uom)} reserved — ${a.batchNo || "unbatched"}` : "Not allocated",
      allocStatus: a ? humanise(a.status) : "",
    };
  });
  const allocationCell = (l: (typeof lines)[number]) => (
    <div className="flex flex-wrap items-center gap-2"><span className="text-xs">{l.allocText}</span>{l.allocStatus && <Pill>{l.allocStatus}</Pill>}</div>
  );

  const downloadAttachment = async () => {
    if (!o?.inverterAttachment) return;
    try {
      const { blob } = await apiBlob(o.inverterAttachment.url);
      downloadBlob(blob, o.inverterAttachment.filename);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };

  return (
    <>
      <Modal open onClose={onClose} wide maxWidth="48rem" title={o ? `${o.number} — ${o.customerName}` : "Order"}
        footer={o && <><ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>{canCancel && <ActionButton tone="danger" onClick={() => setCancelOpen(true)}>Cancel order</ActionButton>}</>}>
        {o && (
          <div className="flex flex-col gap-3">
            <InlineError message={error || q.error?.message} />
            <div className="flex items-center gap-2">
              <Pill>{o.statusLabel}</Pill>
              {o.invoiceId ? <Pill tone="success">Invoiced</Pill> : <Pill tone="warning">Not invoiced</Pill>}
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <span>Subtotal (excl. GST): {format.money(o.subtotal)}</span>
              <span>Tax: {format.money(o.taxTotal)}</span>
              <span className="font-bold">Total: {format.money(o.total)}</span>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span>Paid: {format.money(s.paidAmount)} ({format.percent(s.paidPercent)})</span>
              <span>Outstanding: {format.money(s.outstanding)}</span>
              {s.fullyPaid ? <Pill tone="success">Fully paid</Pill> : <Pill tone="warning">Payment pending</Pill>}
            </div>
            <hr className="border-[var(--border)]" />
            <div className="flex flex-col gap-1">
              <DetailRow label="Customer PO number" value={dash(o.customerRef)} />
              <DetailRow label="Payment terms" value={dash(o.paymentTerms)} />
              <DetailRow label="Inverter details" value={dash(o.inverterDetails)} />
              {o.inverterAttachment && <DetailRow label="Inverter attachment" value={<button type="button" className="rx-link" onClick={downloadAttachment}>{o.inverterAttachment.filename}</button>} />}
              <DetailRow label="Accessories required" value={dash(o.accessoriesRequired)} />
              <DetailRow label="Branding" value={dash(o.branding)} />
              <DetailRow label="Logistics cost borne by" value={dash(o.logisticsCostBorneBy)} />
            </div>
            <hr className="border-[var(--border)]" />
            <DesktopOnly className="w-full">
              <DataTable columns={["SKU Name", "Ordered", "Unit price (excl. GST)", "Gross", "Status", "Allocation"]} minWidth={0} fit>
                {lines.map((l) => <tr key={l.id}><td>{l.name}</td><td>{l.qty}</td><td>{l.price}</td><td>{l.gross}</td><td><Pill>{l.status}</Pill></td><td>{allocationCell(l)}</td></tr>)}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {lines.map((l) => (
                <MobileRecordCard key={l.id}>
                  <MobileRecordRow label="SKU Name" value={l.name} />
                  <MobileRecordRow label="Ordered" value={l.qty} />
                  <MobileRecordRow label="Unit price (excl. GST)" value={l.price} />
                  <MobileRecordRow label="Gross" value={l.gross} />
                  <MobileRecordRow label="Status" value={<Pill>{l.status}</Pill>} />
                  <MobileRecordRow label="Allocation" value={allocationCell(l)} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </div>
        )}
      </Modal>
      {cancelOpen && (
        <ReasonDialog
          title="Cancel order"
          confirmLabel="Confirm cancel"
          onClose={() => setCancelOpen(false)}
          onSubmit={async (reason) => {
            await api("POST", `${path}/cancel`, { json: { reason } });
            await qc.invalidateQueries({ queryKey: [path] });
            onChanged();
            onClose();
          }}
        />
      )}
    </>
  );
}

// ---- sales book ----------------------------------------------------------------------------------

function SalesBook() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("order:write");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [openId, setOpenId] = useState("");
  const list = useApiQuery<ListResponse<Order>>("/api/v1/orders", { page, limit: 20, status });
  const orders = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/orders"] });
  // Sums only the current page - there is no backend aggregate for it, so the label says so.
  const openValue = orders.filter((o) => !["cancelled", "fulfilled"].includes(o.status)).reduce((s, o) => s + Number(o.total || 0), 0);
  const link = (o: Order) => <button type="button" className="rx-link" onClick={() => setOpenId(o.id)}>{o.number}</button>;
  const statusCell = (o: Order) => <div className="flex items-center gap-2"><Pill>{o.statusLabel}</Pill>{o.invoiceId && <Pill tone="success">Invoiced</Pill>}</div>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      {canWrite && (
        <div className="flex w-full justify-end gap-3">
          <BulkUploadButton onClick={() => setBulkOpen(true)} />
          <ActionButton onClick={() => setCreateOpen(true)}>New order</ActionButton>
        </div>
      )}
      <div className="flex gap-4">
        <StatCard label="Open order value (this page)" value={format.money(openValue)} />
        <StatCard label="Orders on this page" value={orders.length} />
      </div>
      <label htmlFor="orders-status-filter" className="sr-only">Filter by status</label>
      <select id="orders-status-filter" className="filter-select" value={status} aria-label="Filter by all" onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
        <option value="">all</option>
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <InlineError message={list.error?.message} />
      {orders.length === 0 && !list.isLoading ? (
        <EmptyState title="No sales orders found" hint="Adjust your status filter or create a new order." />
      ) : (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["Order", "Customer", "Total", "Promised", "Logistics Cost", "Status"]} fit>
              {orders.map((o) => (
                <tr key={o.id}><td>{link(o)}</td><td>{o.customerName}</td><td>{format.money(o.total)}</td><td>{format.date(o.promisedDate)}</td><td>{o.logisticsCostBorneBy || "—"}</td><td>{statusCell(o)}</td></tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {orders.map((o) => (
              <MobileRecordCard key={o.id}>
                <MobileRecordRow label="Order" value={link(o)} />
                <MobileRecordRow label="Customer" value={o.customerName} />
                <MobileRecordRow label="Total" value={format.money(o.total)} />
                <MobileRecordRow label="Promised" value={format.date(o.promisedDate)} />
                <MobileRecordRow label="Logistics cost" value={o.logisticsCostBorneBy || "—"} />
                <MobileRecordRow label="Status" value={statusCell(o)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {createOpen && <CreateDialog onClose={() => setCreateOpen(false)} onCreated={refresh} />}
      {openId && <DetailDialog orderId={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload sales orders"
        description="Upload a CSV with one row per line item. Rows sharing the same SO Ref are grouped into a single order."
        endpoint="/api/v1/orders/bulk-upload"
        sampleCsv={BULK_SAMPLE}
        sampleFilename="sales_order_bulk_upload_template.csv"
        errorFilename="sales_order_bulk_upload_errors.csv"
        columns={BULK_COLUMNS}
        labelHeader="SO Ref"
        labelKey="soRef"
        successKey="orderNumber"
        noun="sales orders"
        multiRow
        onCompleted={refresh}
      />
    </div>
  );
}

export default function OrdersPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("order:read") ? (
        <div className="flex w-full flex-col items-start gap-2">
          <div className="orders-page-header w-full"><PageHeader eyebrow="Demand" title="Orders" /></div>
          <Tabs
            tabs={[
              { value: "sales_order", label: "Sales Book", content: <div className="pt-4"><SalesBook /></div> },
              { value: "allocation", label: "Order Allocation", content: <div className="pt-4">{can("order:allocate") ? <OrderAllocation /> : null}</div> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="order:read" />
      )}
    </Shell>
  );
}
