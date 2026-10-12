/** Procurement: purchase-order list, create, detail (cancel / short close / PDF / resend email) and CSV bulk upload. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { ReasonDialog } from "@/components/erp/dialogs";
import { REQUISITION_BASE, RequisitionsTab, trimDecimal, useRefreshRequisitions, useRequisitionCounts, type Requisition } from "@/components/erp/requisitions";
import { AcknowledgementPanel, DispatchPanel, PoTrail, ackPill, shipmentPill } from "@/components/erp/po-vendor";
import { RfqStartDialog, SourcingTab } from "@/components/erp/sourcing";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { GST_RATE_OPTIONS } from "@/lib/reference";

interface Po {
  id: string;
  number: string;
  revision?: number;
  vendorName: string;
  warehouseCode: string;
  total: string;
  subtotal?: string;
  taxTotal?: string;
  expectedDate?: string | null;
  status: string;
  approvalTierDescription?: string | null;
  emailState?: string | null;
  issuedAt?: string | null;
  receiptStatus?: string;
  ackStatus?: string;
  ackDate?: string | null;
  documentCount?: number;
  dispatchStatus?: string;
  dispatchCount?: number;
  inTransitCount?: number;
  lines?: PoLine[];
}
interface PoLine {
  id?: string;
  sku?: string;
  productName?: string | null;
  quantity: string;
  uom?: string;
  receivedQty?: string;
  rejectedQty?: string;
  unitPrice: string;
  taxAmount?: string;
  grossAmount?: string;
}
interface Vendor {
  id: string;
  displayName: string;
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
interface StagedLine {
  productId: string;
  skuName: string;
  quantity: string;
  uom: string;
  unitPrice: string;
  taxCode: string;
  fromRequisition?: boolean;
}

const STATUSES = ["draft", "pending_approval", "approved", "issued", "partially_received", "received", "closed", "cancelled"];

// Mirrors the backend's BULK_UPLOAD_ALL_COLUMNS in the purchase-orders route: one row per line, grouped by poRef.
const BULK_COLUMNS = ["poRef", "vendorCode", "businessEntityCode", "warehouseCode", "paymentTerms", "paymentMode", "expectedDate", "productSku", "quantity", "uom", "unitPrice", "taxCode"];
const BULK_SAMPLE =
  `${BULK_COLUMNS.join(",")}\n` +
  "PO1,PTY-0001,,WH-AA01,NET30,Bank Transfer,2026-09-20,SKU-001,100,KG,250.00,GST18\n" +
  "PO1,PTY-0001,,WH-AA01,NET30,Bank Transfer,2026-09-20,SKU-002,50,NOS,80.00,GST18\n" +
  "PO2,PTY-0002,,WH-AA01,NET45,Cheque,2026-09-25,SKU-003,10,NOS,1200.00,GST5\n";

const GST_LABELS = Object.fromEntries(GST_RATE_OPTIONS.map((o) => [o.value, o.label]));

/** Fetches a PO's document and saves it - a PDF, or the HTML fallback when the PDF engine is off. */
function usePdfDownload() {
  const { apiBlob } = useAuth();
  return async (po: { id: string; number: string }) => {
    const { blob, contentType } = await apiBlob(`/api/v1/purchase-orders/${po.id}/pdf`);
    const mime = contentType.split(";")[0].trim();
    downloadBlob(blob, `${po.number}.${mime === "application/pdf" ? "pdf" : "html"}`);
  };
}

// ---- create --------------------------------------------------------------------------

function CreateDialog({ vendors, onClose, onCreated, fromRequisition }: { vendors: Vendor[]; onClose: () => void; onCreated: (po: Po) => void | Promise<void>; fromRequisition?: Requisition }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  // Raised from a purchase requisition: its catalogue items arrive already listed, and only the prices are left to fill in.
  const [lines, setLines] = useState<StagedLine[]>(
    (fromRequisition?.lines ?? [])
      .filter((l) => l.productId)
      .map((l) => ({ productId: l.productId as string, skuName: l.itemName, quantity: trimDecimal(l.quantity), uom: l.uom, unitPrice: "", taxCode: "GST0", fromRequisition: true })),
  );
  const [createdPo, setCreatedPo] = useState<Po | null>(null);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [taxCode, setTaxCode] = useState("GST0");

  // Three independent lookups, fetched in parallel by react-query.
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const entities = useApiQuery<ListResponse<Named>>("/api/v1/business-entities", { status: "active", limit: 100 });
  const products = useApiQuery<ListResponse<Product>>("/api/v1/products", { purchasable: "true", status: "active", limit: 200 });
  const productList = products.data?.data ?? [];

  const addLine = () => {
    const product = productList.find((p) => p.id === productId);
    if (!product || !quantity || !unitPrice) return;
    setLines([...lines, { productId, skuName: product.name || product.sku, quantity, uom: product.uom, unitPrice, taxCode: taxCode || "GST0" }]);
    setProductId("");
    setQuantity("");
    setUnitPrice("");
    setTaxCode("GST0");
  };

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    if (!get("vendorId")) return setError("Vendor is required");
    if (!get("warehouseId")) return setError("Ship to (warehouse) is required");
    if (!lines.length) return setError("Add at least one line");
    if (lines.some((l) => l.unitPrice === "")) return setError("Enter a unit price for every line");
    const done = await run(async () => {
      // A retry after the link step failed must not raise a second order.
      const po = createdPo ?? await api<Po>("POST", "/api/v1/purchase-orders", {
        json: {
          vendorId: get("vendorId"),
          warehouseId: get("warehouseId"),
          businessEntityId: get("businessEntityId") || null,
          paymentTerms: get("paymentTerms") || null,
          paymentMode: get("paymentMode") || null,
          expectedDate: get("expectedDate"),
          notes: fromRequisition ? `Raised from purchase requisition ${fromRequisition.number}` : undefined,
          lines: lines.map((l) => ({ productId: l.productId, quantity: l.quantity, uom: l.uom, unitPrice: l.unitPrice, taxCode: l.taxCode })),
        },
      });
      setCreatedPo(po);
      await onCreated(po);
      return po;
    });
    if (done) onClose();
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={fromRequisition ? `New purchase order for ${fromRequisition.number}` : "New purchase order"}
      description={fromRequisition ? "Items and quantities come from the requisition. Choose the vendor and enter each unit price." : undefined}
      wide
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" form="po-details-form" loading={busy}>Create</ActionButton>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        <form id="po-details-form" onSubmit={submit} className="flex flex-col gap-3">
          <SelectInput name="vendorId" defaultValue="" placeholder="Vendor" options={vendors.map((v) => ({ value: v.id, label: v.displayName }))} />
          <SelectInput name="businessEntityId" defaultValue="" placeholder="Invoice to (business entity)" options={(entities.data?.data ?? []).map((v) => ({ value: v.id, label: v.name }))} />
          <SelectInput key={warehouses.data ? "loaded" : "loading"} name="warehouseId" defaultValue={fromRequisition?.warehouseId ?? ""} placeholder="Ship to (warehouse)" options={(warehouses.data?.data ?? []).map((v) => ({ value: v.id, label: v.name }))} />
          <TextInput name="paymentTerms" placeholder="Terms of Payment (e.g. Net 30)" />
          <TextInput name="paymentMode" placeholder="Mode of Payment (e.g. Bank Transfer)" />
          <TextInput name="expectedDate" type="date" required />
        </form>
        <p className="mt-2 text-sm font-bold">Products</p>
        <DataTable columns={["SKU Name", "Qty", "Price", "GST %", ""]} minWidth={0} fit>
          {lines.map((l, i) => (
            <tr key={i}>
              <td>{l.skuName}</td>
              <td>{format.qty(l.quantity, l.uom)}</td>
              <td>
                {fromRequisition && l.fromRequisition ? (
                  <TextInput style={{ width: "7rem" }} placeholder="Unit price" inputMode="decimal" value={l.unitPrice} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, unitPrice: e.target.value } : x)))} />
                ) : format.money(l.unitPrice)}
              </td>
              <td>
                {fromRequisition && l.fromRequisition ? (
                  <SelectInput style={{ width: "6rem" }} value={l.taxCode} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, taxCode: e.target.value } : x)))} options={GST_RATE_OPTIONS} />
                ) : (GST_LABELS[l.taxCode] ?? l.taxCode)}
              </td>
              <td><ActionButton size="sm" tone="danger" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</ActionButton></td>
            </tr>
          ))}
        </DataTable>
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2">
          <SelectInput style={{ width: "14rem" }} value={productId} onChange={(e) => setProductId(e.target.value)} placeholder="Product" options={productList.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))} />
          <TextInput style={{ width: "6rem" }} placeholder="Qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          <TextInput style={{ width: "10rem" }} placeholder="Unit price (before GST)" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
          <SelectInput style={{ width: "6rem" }} value={taxCode} onChange={(e) => setTaxCode(e.target.value)} options={GST_RATE_OPTIONS} />
          <ActionButton size="sm" onClick={addLine}>Add line</ActionButton>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">Unit price is the price before GST — GST is added per line at the selected rate.</p>
      </div>
    </Modal>
  );
}

// ---- detail --------------------------------------------------------------------------

function DetailDialog({ poId, onClose, onChanged }: { poId: string; onClose: () => void; onChanged: () => void }) {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const download = usePdfDownload();
  const { run, error } = useAsyncAction();
  const [mode, setMode] = useState<"" | "cancel" | "shortClose">("");
  const path = `/api/v1/purchase-orders/${poId}`;
  const detail = useApiQuery<Po>(path);
  const po = detail.data;
  const reload = async () => {
    await qc.invalidateQueries({ queryKey: [path] });
    onChanged();
  };

  const lines = (po?.lines ?? []).map((l) => ({
    ...l,
    skuName: l.productName || l.sku,
    ordered: format.qty(l.quantity, l.uom),
    received: format.qty(l.receivedQty),
    rejected: format.qty(l.rejectedQty),
    price: format.money(l.unitPrice),
    tax: format.money(l.taxAmount),
    gross: format.money(l.grossAmount),
  }));
  const status = po?.status ?? "";
  const canCancel = can("po:cancel") && !["cancelled", "closed", "received"].includes(status);
  const canShortClose = can("po:short_close") && ["issued", "partially_received"].includes(status);

  return (
    <>
      <Modal
        open
        onClose={onClose}
        wide
        title={po ? `${po.number} (r${po.revision}) — ${po.vendorName}` : "Purchase order"}
        footer={
          po && (
            <>
              <ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>
              <ActionButton tone="ghost" onClick={() => run(() => download(po))}>Download PDF</ActionButton>
              {can("po:email") && po.emailState === "failed" && (
                <ActionButton tone="ghost" onClick={() => run(async () => { await api("POST", `${path}/send-email`, { json: {} }); await reload(); })}>Resend email</ActionButton>
              )}
              {canShortClose && <ActionButton tone="ghost" onClick={() => setMode("shortClose")}>Short close PO</ActionButton>}
              {canCancel && <ActionButton tone="danger" onClick={() => setMode("cancel")}>Cancel PO</ActionButton>}
            </>
          )
        }
      >
        {po && (
          <div className="flex flex-col gap-3">
            <InlineError message={error || detail.error?.message} />
            <div className="flex flex-wrap items-center gap-3">
              <Pill>{po.status}</Pill>
              <span className="text-sm">Approval: {po.approvalTierDescription}</span>
              <Pill>{`email: ${po.emailState}`}</Pill>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <span>Subtotal: {format.money(po.subtotal)}</span>
              <span>Tax: {format.money(po.taxTotal)}</span>
              <span className="font-bold">Total: {format.money(po.total)}</span>
            </div>
            <PoTrail po={po} />
            <Tabs
              tabs={[
                {
                  value: "order",
                  label: "Order",
                  content: (
                    <div className="flex flex-col gap-3">
            <DesktopOnly className="w-full">
                      <DataTable columns={["SKU Name", "Ordered", "Received", "Rejected", "Unit price", "Tax", "Gross"]} minWidth={0} fit>
                        {lines.map((l, i) => (
                          <tr key={i}>
                            <td>{l.skuName}</td><td>{l.ordered}</td><td>{l.received}</td><td>{l.rejected}</td><td>{l.price}</td><td>{l.tax}</td><td>{l.gross}</td>
                          </tr>
                        ))}
                      </DataTable>
                    </DesktopOnly>
                    <MobileOnly className="w-full">
                      {lines.map((l, i) => (
                        <MobileRecordCard key={i}>
                          <MobileRecordRow label="SKU Name" value={l.skuName} />
                          <MobileRecordRow label="Ordered" value={l.ordered} />
                          <MobileRecordRow label="Received" value={l.received} />
                          <MobileRecordRow label="Rejected" value={l.rejected} />
                          <MobileRecordRow label="Unit price" value={l.price} />
                          <MobileRecordRow label="Tax" value={l.tax} />
                          <MobileRecordRow label="Gross" value={l.gross} />
                        </MobileRecordCard>
                      ))}
                    </MobileOnly>
                            </div>
                  ),
                },
                { value: "vendor", label: <>Acknowledgement &amp; documents{po.ackStatus && po.ackStatus !== "pending" ? <> {ackPill(po.ackStatus)}</> : null}</>, content: <AcknowledgementPanel poId={poId} /> },
                { value: "dispatch", label: <>Dispatch{po.dispatchStatus && po.dispatchStatus !== "none" ? <> {shipmentPill(po.dispatchStatus, po.inTransitCount)}</> : null}</>, content: <DispatchPanel poId={poId} /> },
              ]}
            />
          </div>
        )}
      </Modal>
      {mode === "cancel" && (
        <ReasonDialog
          title="Cancel purchase order"
          confirmLabel="Confirm cancel"
          onClose={() => setMode("")}
          onSubmit={async (reason) => {
            await api("POST", `${path}/cancel`, { json: { reason } });
            await reload();
            onClose(); // the order is cancelled: nothing more to do in this dialog
          }}
        />
      )}
      {mode === "shortClose" && (
        <ReasonDialog
          title="Short close purchase order"
          descriptionSize="2"
          description="The outstanding balance will be written off — no further goods receipts will be accepted against this PO."
          confirmLabel="Confirm short close"
          onClose={() => setMode("")}
          onSubmit={async (reason) => {
            await api("POST", `${path}/short-close`, { json: { reason } });
            await reload();
            onClose();
          }}
        />
      )}
    </>
  );
}

// ---- page ------------------------------------------------------------------------------

function PurchaseOrdersView() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const download = usePdfDownload();
  const canWrite = can("po:write");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [vendor, setVendor] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [openId, setOpenId] = useState("");
  const { run, error: actionError } = useAsyncAction();

  const vendors = useApiQuery<ListResponse<Vendor>>("/api/v1/parties", { type: "vendor", limit: 100 });
  const list = useApiQuery<ListResponse<Po>>("/api/v1/purchase-orders", { page, limit: 20, q: debounced, status, vendorId: vendor });
  const pos = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/purchase-orders"] });
  const pdf = (p: Po, cls?: string) => <ActionButton size="sm" tone="ghost" className={cls} onClick={() => run(() => download(p))}>Download PDF</ActionButton>;
  const link = (p: Po) => <button type="button" className="rx-link" onClick={() => setOpenId(p.id)}>{p.number}</button>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input className="search-input" style={{ width: "20rem" }} placeholder="Search PO number or vendor…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <select className="filter-select" style={{ width: "12rem" }} value={vendor} onChange={(e) => { setVendor(e.target.value); setPage(1); }}>
          <option value="">All vendors</option>
          {(vendors.data?.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.displayName}</option>)}
        </select>
        <select className="filter-select" style={{ width: "11rem" }} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && <ActionButton onClick={() => setCreateOpen(true)}>New purchase order</ActionButton>}
      </div>
      <InlineError message={actionError || list.error?.message} />
      {pos.length === 0 && !list.isLoading ? (
        <EmptyState title="No purchase orders found" hint="Adjust your search, date range or status filters, or create a new purchase order." />
      ) : (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["PO", "Vendor", "Deliver to", "Value", "Expected", "Status", "Vendor", ""]} fit>
              {pos.map((p) => (
                <tr key={p.id}>
                  <td>{link(p)}</td>
                  <td>{p.vendorName}</td>
                  <td>{p.warehouseCode}</td>
                  <td>{format.money(p.total)}</td>
                  <td>{format.date(p.expectedDate)}</td>
                  <td><Pill>{p.status}</Pill></td>
                  <td>
                    <div className="flex flex-col items-start gap-1">
                      {ackPill(p.ackStatus ?? "pending")}
                      {p.dispatchStatus && p.dispatchStatus !== "none" && shipmentPill(p.dispatchStatus, p.inTransitCount)}
                    </div>
                  </td>
                  <td>{pdf(p)}</td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {pos.map((p) => (
              <MobileRecordCard key={p.id} actions={pdf(p, "w-full justify-center")}>
                <MobileRecordRow label="PO" value={link(p)} />
                <MobileRecordRow label="Vendor" value={p.vendorName} />
                <MobileRecordRow label="Deliver to" value={p.warehouseCode} />
                <MobileRecordRow label="Value" value={format.money(p.total)} />
                <MobileRecordRow label="Expected" value={format.date(p.expectedDate)} />
                <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
                <MobileRecordRow label="Vendor ack" value={ackPill(p.ackStatus ?? "pending")} />
                <MobileRecordRow label="Shipment" value={shipmentPill(p.dispatchStatus ?? "none", p.inTransitCount)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full">
        <Pagination meta={list.data?.meta} onPage={setPage} />
      </div>
      {createOpen && <CreateDialog vendors={vendors.data?.data ?? []} onClose={() => setCreateOpen(false)} onCreated={() => refresh()} />}
      {openId && <DetailDialog poId={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload purchase orders"
        description="Upload a CSV with one row per line item. Rows sharing the same PO Ref are grouped into a single purchase order."
        endpoint="/api/v1/purchase-orders/bulk-upload"
        sampleCsv={BULK_SAMPLE}
        sampleFilename="po_bulk_upload_template.csv"
        errorFilename="po_bulk_upload_errors.csv"
        columns={BULK_COLUMNS}
        labelHeader="PO Ref"
        labelKey="poRef"
        successKey="poNumber"
        noun="purchase orders"
        multiRow
        onCompleted={refresh}
      />
    </div>
  );
}

/** Turns an approved requisition into a purchase order, then records the link back on the requisition. */
function RequisitionPoDialog({ requisition, onClose }: { requisition: Requisition; onClose: () => void }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const refreshRequisitions = useRefreshRequisitions();
  const vendors = useApiQuery<ListResponse<Vendor>>("/api/v1/parties", { type: "vendor", limit: 100 });
  return (
    <CreateDialog
      vendors={vendors.data?.data ?? []}
      fromRequisition={requisition}
      onClose={onClose}
      onCreated={async (po) => {
        await api("POST", `${REQUISITION_BASE}/${requisition.id}/link-po`, { json: { purchaseOrderId: po.id } });
        await qc.invalidateQueries({ queryKey: ["/api/v1/purchase-orders"] });
        await refreshRequisitions();
      }}
    />
  );
}

function Content() {
  const { can } = useAuth();
  const canOrders = can("po:read");
  const canRequisitions = can("pr:read") || can("pr:approve") || can("pr:team_approve");
  const canSourcing = can("sourcing:read");
  const counts = useRequisitionCounts(canRequisitions);
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState(() => (initialTab === "requisitions" && canRequisitions) || (!canOrders && canRequisitions) ? "requisitions" : !canOrders && canSourcing ? "sourcing" : "orders");
  const [poFor, setPoFor] = useState<Requisition | null>(null);
  const [sourceFor, setSourceFor] = useState<Requisition | null>(null);
  const [rfqId, setRfqId] = useState("");
  const [requisitionId, setRequisitionId] = useState("");
  const toReview = (counts.data?.awaitingReview ?? 0) + (counts.data?.awaitingMyApproval ?? 0);

  const handleTabChange = (newTab: string) => {
    setTab(newTab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", newTab);
      return next;
    }, { replace: true });
  };

  const openRfq = (id: string) => {
    setRfqId(id);
    if (id) handleTabChange("sourcing");
  };
  const openRequisition = (id: string) => {
    setRequisitionId(id);
    setRfqId("");
    handleTabChange("requisitions");
  };

  const views = [
    canRequisitions && {
      value: "requisitions",
      label: <>Purchase requisitions{toReview > 0 ? <> <Pill tone="warning">{`${toReview} to review`}</Pill></> : null}</>,
      content: <RequisitionsTab onCreatePo={can("po:write") ? setPoFor : undefined} onStartSourcing={can("sourcing:write") ? setSourceFor : undefined} onOpenRfq={canSourcing ? openRfq : undefined} openId={requisitionId} onOpenIdChange={setRequisitionId} />,
    },
    canSourcing && { value: "sourcing", label: "Sourcing (RFQ)", content: <SourcingTab openId={rfqId} onOpen={setRfqId} onOpenRequisition={canRequisitions ? openRequisition : undefined} /> },
    canOrders && { value: "orders", label: "Purchase orders", content: <PurchaseOrdersView /> },
  ].filter(Boolean) as { value: string; label: ReactNode; content: ReactNode }[];

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader eyebrow="Supply chain" title="Procurement" />
      {views.length > 1 ? <Tabs value={tab} onValueChange={handleTabChange} tabs={views} /> : views[0]?.content}
      {poFor && <RequisitionPoDialog requisition={poFor} onClose={() => setPoFor(null)} />}
      {sourceFor && <RfqStartDialog requisition={sourceFor} onClose={() => setSourceFor(null)} onStarted={(id) => openRfq(id)} />}
    </div>
  );
}

export default function ProcurementPage() {
  const { can } = useAuth();
  const allowed = can("po:read") || can("pr:read") || can("pr:approve") || can("pr:team_approve") || can("sourcing:read");
  return <Shell>{allowed ? <Content /> : <Forbidden permission="po:read" />}</Shell>;
}
