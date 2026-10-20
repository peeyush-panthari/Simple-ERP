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
import { GuidedFieldWalkthrough } from "@/components/erp/guided-field-walkthrough";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, TextInput,
} from "@/components/erp/ui";
import { ScreenTourButton } from "@/components/erp/screen-tour";
import { useAuth } from "@/lib/auth";
import { useDemoTour } from "@/lib/demo-flow-context";
import * as format from "@/lib/format";
import { downloadBlob, useActiveWarehouses, useVendors, useApiQuery, useAsyncAction, useDebounced, usePagination, type ListResponse } from "@/lib/hooks";
import { GST_LABELS, GST_RATE_OPTIONS } from "@/lib/reference";
import { cn } from "@/lib/utils";

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
  displayName?: string;
  legalName?: string;
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
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep = isTourActive && ((activeJourneyId === "procure-to-pay" && currentJourneyStepIndex === 2) || (activeJourneyId === "plan-to-order" && currentJourneyStepIndex === 3));

  const [activeWalkthroughField, setActiveWalkthroughField] = useState("vendorId");
  const [vendorId, setVendorId] = useState("");
  const [warehouseId, setWarehouseId] = useState(fromRequisition?.warehouseId ?? "");
  const [paymentTerms, setPaymentTerms] = useState("NET30");
  const [paymentMode, setPaymentMode] = useState("Bank Transfer");
  const [expectedDate, setExpectedDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split("T")[0];
  });

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
  const [taxCode, setTaxCode] = useState("GST18");

  // Three independent lookups, fetched in parallel by react-query.
  const warehouses = useActiveWarehouses();
  const entities = useApiQuery<ListResponse<Named>>("/api/v1/business-entities", { status: "active", limit: 100 });
  const products = useApiQuery<ListResponse<Product>>("/api/v1/products", { purchasable: "true", status: "active", limit: 200 });
  const productList = products.data?.data ?? [];
  const warehouseList = warehouses.data?.data ?? [];

  const autofillDemoPo = () => {
    if (vendors.length > 0) setVendorId(vendors[0].id);
    if (warehouseList.length > 0) setWarehouseId(warehouseList[0].id);
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 14);
    setExpectedDate(futureDate.toISOString().split("T")[0]);
    setPaymentTerms("NET30");
    setPaymentMode("Bank Transfer");

    if (productList.length > 0) {
      const p = productList[0];
      setLines([
        {
          productId: p.id,
          skuName: p.name || p.sku,
          quantity: "100",
          uom: p.uom || "UNIT",
          unitPrice: "450.00",
          taxCode: "GST18",
        },
      ]);
    }
  };

  const walkthroughFields = [
    {
      id: "vendorId",
      label: "Approved Vendor Master Selection",
      shortLabel: "Vendor",
      useCase: "Legally binding commercial supplier for raw material supply, contractual delivery terms, and GST input tax credit.",
      guideline: "Select an active registered vendor from the Approved Vendor List (AVL).",
      restriction: "Required. Must be in active status with a valid GSTIN.",
      sampleValueText: vendors[0]?.displayName || "Axon Precision Components",
      isFilled: Boolean(vendorId),
      onFill: () => {
        if (vendors.length > 0) setVendorId(vendors[0].id);
      },
    },
    {
      id: "warehouseId",
      label: "Receiving Warehouse & Inward Dock",
      shortLabel: "Warehouse",
      useCase: "Designates the destination plant/warehouse where the physical shipment will be unloaded, inspected, and booked via GRN.",
      guideline: "Choose the receiving central factory or raw material warehouse.",
      restriction: "Required. Determines delivery location printed on the PO.",
      sampleValueText: warehouseList[0]?.name || "Pune Central Warehouse",
      isFilled: Boolean(warehouseId),
      onFill: () => {
        if (warehouseList.length > 0) setWarehouseId(warehouseList[0].id);
      },
    },
    {
      id: "expectedDate",
      label: "Required On-Dock Delivery Date",
      shortLabel: "Delivery Date",
      useCase: "Production supply milestone used by MRP planning engine to prevent stockouts and evaluate supplier On-Time Delivery.",
      guideline: "Standard supplier lead time date (14 days from today).",
      restriction: "Must be a future date.",
      sampleValueText: expectedDate,
      isFilled: Boolean(expectedDate),
      onFill: () => {
        const d = new Date();
        d.setDate(d.getDate() + 14);
        setExpectedDate(d.toISOString().split("T")[0]);
      },
    },
    {
      id: "lines",
      label: "Procurement Line Items & Contract Pricing",
      shortLabel: "Line Items",
      useCase: "Detailed bill of materials items with purchase price, order quantity, and statutory GST rate for three-way invoice matching.",
      guideline: "Add purchasable raw materials with verified unit prices.",
      restriction: "At least one line item with valid unit price is strictly required.",
      sampleValueText: productList[0] ? `${productList[0].name} (100 ${productList[0].uom} @ ₹450)` : "100 Units @ ₹450",
      isFilled: lines.length > 0 && lines.every((l) => Boolean(l.unitPrice)),
      onFill: () => {
        if (productList.length > 0) {
          const p = productList[0];
          setLines([
            {
              productId: p.id,
              skuName: p.name || p.sku,
              quantity: "100",
              uom: p.uom || "UNIT",
              unitPrice: "450.00",
              taxCode: "GST18",
            },
          ]);
        }
      },
    },
  ];

  const allWalkthroughFilled = Boolean(vendorId && warehouseId && lines.length > 0);

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
    const finalVendor = vendorId || get("vendorId");
    const finalWh = warehouseId || get("warehouseId");
    const finalExp = expectedDate || get("expectedDate");
    if (!finalVendor) return setError("Vendor is required");
    if (!finalWh) return setError("Ship to (warehouse) is required");
    if (!lines.length) return setError("Add at least one line");
    if (lines.some((l) => l.unitPrice === "")) return setError("Enter a unit price for every line");
    const done = await run(async () => {
      const po = createdPo ?? await api<Po>("POST", "/api/v1/purchase-orders", {
        json: {
          vendorId: finalVendor,
          warehouseId: finalWh,
          businessEntityId: get("businessEntityId") || null,
          paymentTerms: paymentTerms || get("paymentTerms") || null,
          paymentMode: paymentMode || get("paymentMode") || null,
          expectedDate: finalExp,
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
        <div className="flex justify-end gap-2 items-center">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <div className="relative">
            {isTourStep && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  3
                </span>
              </span>
            )}
            <ActionButton
              type="submit"
              form="po-details-form"
              tone={isTourStep ? "primary" : undefined}
              loading={busy}
              className={cn(isTourStep && allWalkthroughFilled && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              Create
            </ActionButton>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        {isTourStep && (
          <GuidedFieldWalkthrough
            dialogTitle="Purchase Order Creation"
            fields={walkthroughFields}
            activeFieldId={activeWalkthroughField}
            onSelectField={setActiveWalkthroughField}
            onFillAll={autofillDemoPo}
            allFilled={allWalkthroughFilled}
            submitButtonLabel="Create"
            stepBadgeNumber={2}
            nextStepBadgeNumber={3}
          />
        )}
        <form id="po-details-form" onSubmit={submit} className="flex flex-col gap-3">
          <div className={cn(isTourStep && activeWalkthroughField === "vendorId" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
            <SelectInput
              name="vendorId"
              value={vendorId}
              onFocus={() => setActiveWalkthroughField("vendorId")}
              onChange={(e) => setVendorId(e.target.value)}
              placeholder="Vendor"
              options={vendors.map((v) => ({ value: v.id, label: v.displayName || v.legalName || "" }))}
            />
          </div>
          <SelectInput name="businessEntityId" defaultValue="" placeholder="Invoice to (business entity)" options={(entities.data?.data ?? []).map((v) => ({ value: v.id, label: v.name }))} />
          <div className={cn(isTourStep && activeWalkthroughField === "warehouseId" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
            <SelectInput
              key={warehouses.data ? "loaded" : "loading"}
              name="warehouseId"
              value={warehouseId}
              onFocus={() => setActiveWalkthroughField("warehouseId")}
              onChange={(e) => setWarehouseId(e.target.value)}
              placeholder="Ship to (warehouse)"
              options={warehouseList.map((v) => ({ value: v.id, label: v.name }))}
            />
          </div>
          <div className="flex gap-2">
            <TextInput name="paymentTerms" placeholder="Terms of Payment (e.g. Net 30)" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} />
            <TextInput name="paymentMode" placeholder="Mode of Payment (e.g. Bank Transfer)" value={paymentMode} onChange={(e) => setPaymentMode(e.target.value)} />
          </div>
          <div className={cn(isTourStep && activeWalkthroughField === "expectedDate" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
            <TextInput
              name="expectedDate"
              type="date"
              value={expectedDate}
              onFocus={() => setActiveWalkthroughField("expectedDate")}
              onChange={(e) => setExpectedDate(e.target.value)}
              required
            />
          </div>
        </form>
        <div className={cn(isTourStep && activeWalkthroughField === "lines" && "rounded-lg p-2 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-2")}>
          <p className="text-sm font-bold">Products</p>
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
    skuName: format.lineDisplayName(l),
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
  const [page, setPage] = usePagination();
  const debounced = useDebounced(search);
  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [openId, setOpenId] = useState("");
  const { run, error: actionError } = useAsyncAction();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStepPo = isTourActive && ((activeJourneyId === "procure-to-pay" && currentJourneyStepIndex === 2) || (activeJourneyId === "plan-to-order" && currentJourneyStepIndex === 3));

  const vendors = useVendors();
  const list = useApiQuery<ListResponse<Po>>("/api/v1/purchase-orders", { page, limit: 20, q: debounced, status, vendorId: vendor });
  const pos = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/purchase-orders"] });
  const pdf = (p: Po, cls?: string) => <ActionButton size="sm" tone="ghost" className={cls} onClick={() => run(() => download(p))}>Download PDF</ActionButton>;
  const link = (p: Po) => <button type="button" className="rx-link" onClick={() => setOpenId(p.id)}>{p.number}</button>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <label htmlFor="po-search-input" className="sr-only">Search PO number or vendor</label>
        <input id="po-search-input" className="search-input" style={{ width: "20rem" }} placeholder="Search PO number or vendor…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <label htmlFor="po-vendor-filter" className="sr-only">Filter by vendor</label>
        <select id="po-vendor-filter" className="filter-select" style={{ width: "12rem" }} value={vendor} aria-label="Filter by All vendors" onChange={(e) => { setVendor(e.target.value); setPage(1); }}>
          <option value="">All vendors</option>
          {(vendors.data?.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.displayName || v.legalName}</option>)}
        </select>
        <label htmlFor="po-status-filter" className="sr-only">Filter by status</label>
        <select id="po-status-filter" className="filter-select" style={{ width: "11rem" }} value={status} aria-label="Filter by All Status" onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && (
          <div className="relative">
            {isTourStepPo && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  1
                </span>
              </span>
            )}
            <ActionButton
              onClick={() => setCreateOpen(true)}
              tone={isTourStepPo ? "primary" : undefined}
              className={cn(isTourStepPo && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              New purchase order
            </ActionButton>
          </div>
        )}
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
  const vendors = useVendors();
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
      <PageHeader
        eyebrow="Supply chain"
        title="Procurement"
        actions={
          <ScreenTourButton
            screenTitle="Procurement Hub"
            trainingModuleId="procurement"
            steps={[
              {
                title: "Purchase Requisitions",
                highlightTag: "Internal Demand",
                description: "Internal teams request inventory or non-stock supplies. Requisitions require approval before advancing to procurement.",
              },
              {
                title: "Sourcing & RFQ Comparison",
                highlightTag: "Supplier Bidding",
                description: "Send Request for Quotations (RFQs) to multiple qualified vendors and evaluate side-by-side landed quote matrices.",
              },
              {
                title: "PO Generation & Multi-Tier Approval",
                highlightTag: "Purchase Orders",
                description: "Generate legally binding Purchase Orders with automatic tiered authorization rules based on PO monetary threshold.",
              },
            ]}
          />
        }
      />
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
