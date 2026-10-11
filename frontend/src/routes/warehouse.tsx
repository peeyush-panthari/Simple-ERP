/** GRN & QC: goods receipts (receive, detail/edit/cancel, QR sticker downloads, bulk upload) and the under-QC queue. */
import { InboundShipments } from "@/components/erp/po-vendor";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { ReasonDialog } from "@/components/erp/dialogs";
import { GrnStatusPill, grnStatusLabel, useQrDownloads } from "@/components/erp/grn";
import { ScanToJumpBox } from "@/components/erp/scan";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, SelectInput, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { humanise, rawItemStatusLabel } from "@/lib/status";

interface Grn {
  id: string;
  number: string;
  poId?: string;
  poNumber: string;
  vendorName: string;
  warehouseId?: string;
  warehouseName: string;
  receivedGoodsValue?: string;
  receivedDate?: string;
  status: string;
  lines?: GrnLine[];
}
interface GrnLine {
  id: string;
  poLineId: string;
  sku: string;
  productName?: string | null;
  uom: string;
  orderedQty?: string;
  receivedQty: string;
  batchNo?: string | null;
  qualityStatus?: string | null;
}
interface GrnItem {
  id: string;
  grnLineId: string;
  inventoryId: string;
  kind: string;
  quantity: string;
  uom: string;
  status: string;
  locationCode?: string | null;
  [k: string]: unknown;
}
interface Named {
  id: string;
  name: string;
  code?: string;
}
interface PoLine {
  id: string;
  sku: string;
  productName?: string | null;
  quantity: string;
  uom: string;
  status: string;
  batchTracked?: boolean;
}
interface PoSummary {
  id: string;
  number: string;
  vendorName: string;
  warehouseId?: string;
  lines?: PoLine[];
}

const GRN_STATUSES = ["under_qc", "posted", "rejected", "cancelled"];

// Mirrors the backend's BULK_UPLOAD_ALL_COLUMNS / QC_BULK_UPLOAD_ALL_COLUMNS in the grns route.
const GRN_BULK_COLUMNS = [
  "grnRef", "poNumber", "receivedDate", "vehicleNumber", "deliveryNote", "gateEntryNo", "invoiceNumber", "notes",
  "stickerSizeName", "vendorQrEnabled", "lineSku", "receivedQty", "batchNo", "expiryDate", "manufactureDate", "locationCode",
];
const GRN_BULK_SAMPLE =
  `${GRN_BULK_COLUMNS.join(",")}\n` +
  "GRN1,PO-3001,2026-09-20,MH12AB1234,DN-001,GATE-01,INV-1001,,,false,SKU-001,100,BATCH-A,,,\n" +
  "GRN1,PO-3001,2026-09-20,MH12AB1234,DN-001,GATE-01,INV-1001,,,false,SKU-002,50,BATCH-B,,,\n";
const QC_BULK_COLUMNS = ["grnNumber", "lineSku", "acceptedQty", "rejectedQty", "rejectionCode", "rejectionNote"];
const QC_BULK_SAMPLE =
  `${QC_BULK_COLUMNS.join(",")}\n` +
  "GRN-8801,SKU-001,98,2,DAMAGED,2 units damaged in transit\n" +
  "GRN-8801,SKU-002,50,0,,\n";

const lineName = (l: { productName?: string | null; sku?: string }) => l.productName || l.sku || "";

// ---- receive goods -------------------------------------------------------------------------

interface ReceiveLine {
  poLineId: string;
  skuName: string;
  sku: string;
  ordered: string;
  receivedQty: string;
  batchNo: string;
  batchTracked: boolean;
}

function ReceiveDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { api, can } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [poId, setPoId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [lines, setLines] = useState<ReceiveLine[]>([]);
  const [stickerSizeId, setStickerSizeId] = useState("");
  const [vendorQr, setVendorQr] = useState(false);

  const pos = useApiQuery<ListResponse<PoSummary>>("/api/v1/purchase-orders", { status: "issued,partially_received", limit: 100 });
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const canSticker = can("sticker_size:read");
  const stickers = useApiQuery<ListResponse<Named>>("/api/v1/sticker-sizes", { status: "active" }, { enabled: canSticker });

  const pickPo = async (id: string) => {
    setPoId(id);
    setLines([]);
    setWarehouseId("");
    if (!id) return;
    await run(async () => {
      const po = await api<PoSummary>("GET", `/api/v1/purchase-orders/${id}`);
      setWarehouseId(po.warehouseId ?? "");
      setLines(
        (po.lines ?? [])
          .filter((l) => !["closed", "cancelled"].includes(l.status))
          .map((l) => ({ poLineId: l.id, sku: l.sku, skuName: lineName(l), ordered: format.qty(l.quantity), receivedQty: "", batchNo: "", batchTracked: !!l.batchTracked })),
      );
    });
  };
  const patch = (i: number, p: Partial<ReceiveLine>) => setLines(lines.map((l, j) => (j === i ? { ...l, ...p } : l)));

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const entered = lines.filter((l) => l.receivedQty);
    if (!entered.length) return setError("Enter a received quantity for at least one line");
    const missingBatch = entered.filter((l) => l.batchTracked && !l.batchNo.trim()).map((l) => l.sku);
    if (missingBatch.length) return setError(`Batch number is required for: ${missingBatch.join(", ")}`);
    if (!warehouseId) return setError("Select the warehouse the goods are being received into");
    if (!get("invoiceNumber").trim()) return setError("Invoice number is required");
    const ok = await run(async () => {
      await api("POST", "/api/v1/grns", {
        json: {
          poId,
          warehouseId,
          vehicleNumber: get("vehicleNumber") || null,
          deliveryNote: get("deliveryNote") || null,
          invoiceNumber: get("invoiceNumber"),
          stickerSizeId: stickerSizeId || null,
          vendorQrEnabled: vendorQr,
          lines: entered.map((l) => ({ poLineId: l.poLineId, receivedQty: l.receivedQty, batchNo: l.batchNo || null })),
        },
      });
      return true;
    });
    if (ok) {
      onClose();
      onCreated();
    }
  };

  const qtyInput = (l: ReceiveLine, i: number, w: string) => <TextInput style={{ width: w }} placeholder="Received qty" value={l.receivedQty} onChange={(e) => patch(i, { receivedQty: e.target.value })} />;
  const batchInput = (l: ReceiveLine, i: number, w: string) => (
    <TextInput
      style={{ width: w, ...(l.batchTracked && !l.batchNo ? { borderColor: "var(--destructive)" } : {}) }}
      placeholder={l.batchTracked ? "Batch no (required)" : "Batch no (optional)"}
      value={l.batchNo}
      onChange={(e) => patch(i, { batchNo: e.target.value })}
    />
  );

  return (
    <Modal
      open
      onClose={onClose}
      title="Receive goods"
      wide
      footer={
        <>
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" form="receive-form" loading={busy}>Create receipt</ActionButton>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        <SelectInput className="ui-select-auto" value={poId} onChange={(e) => void pickPo(e.target.value)} placeholder="Purchase order" options={(pos.data?.data ?? []).map((p) => ({ value: p.id, label: `${p.number} — ${p.vendorName}` }))} />
        {poId && <InboundShipments poId={poId} />}
        {poId && (
          <div className="flex flex-col gap-1">
            <p className="text-xs text-[var(--muted-foreground)]">Receiving into warehouse</p>
            <SelectInput className="ui-select-auto" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="Warehouse" options={(warehouses.data?.data ?? []).map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))} />
          </div>
        )}
        {lines.length > 0 && (
          <>
            <DesktopOnly className="w-full">
              <DataTable columns={["SKU Name", "Ordered", "Received", "Batch"]} minWidth={0} fit>
                {lines.map((l, i) => (
                  <tr key={l.poLineId}>
                    <td>{l.skuName}</td>
                    <td>{l.ordered}</td>
                    <td>{qtyInput(l, i, "8rem")}</td>
                    <td>{batchInput(l, i, "10rem")}</td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {lines.map((l, i) => (
                <MobileRecordCard key={l.poLineId}>
                  <MobileRecordRow label="SKU Name" value={l.skuName} />
                  <MobileRecordRow label="Ordered" value={l.ordered} />
                  <div className="mobile-record-row-inputs">
                    {qtyInput(l, i, "100%")}
                    {batchInput(l, i, "100%")}
                  </div>
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </>
        )}
        <form onSubmit={submit} id="receive-form" className="mt-2 flex flex-col gap-3">
          <TextInput name="invoiceNumber" placeholder="Invoice number" required />
          <div className="flex gap-2">
            <TextInput name="vehicleNumber" placeholder="Vehicle number (optional)" />
            <TextInput name="deliveryNote" placeholder="Delivery note (optional)" />
          </div>
          {canSticker && (
            <Field label="Sticker size" hint="Sizes the printed QR/label for every item on this receipt">
              <SelectInput value={stickerSizeId} onChange={(e) => setStickerSizeId(e.target.value)} options={[{ value: "", label: "No sticker size (default QR/label sizing)" }, ...(stickers.data?.data ?? []).map((s) => ({ value: s.id, label: s.name }))]} />
            </Field>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={vendorQr} onChange={(e) => setVendorQr(e.target.checked)} />
            <span>Vendor&apos;s QR and ID</span>
          </label>
          {vendorQr && <p className="text-xs text-[var(--muted-foreground)]">Every item on this receipt can then have the vendor&apos;s own QR code (or ID) attached from its own detail page.</p>}
        </form>
      </div>
    </Modal>
  );
}

// ---- GRN detail ---------------------------------------------------------------------------------

interface EditLine {
  id: string;
  poLineId: string;
  sku: string;
  skuName: string;
  uom: string;
  receivedQty: string;
  batchNo: string;
  batchTracked: boolean;
}

function DetailDialog({ grnId, onClose, onChanged }: { grnId: string; onClose: () => void; onChanged: () => void }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const qr = useQrDownloads();
  const { run, busy, error, setError } = useAsyncAction();
  const grnPath = `/api/v1/grns/${grnId}`;
  const grnQ = useApiQuery<Grn>(grnPath);
  const itemsQ = useApiQuery<{ data: GrnItem[] }>(`${grnPath}/items`);
  const grn = grnQ.data;
  const items = itemsQ.data?.data ?? [];
  const [lineId, setLineId] = useState("");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editWarehouse, setEditWarehouse] = useState("");
  const [editLines, setEditLines] = useState<EditLine[]>([]);
  const [poLines, setPoLines] = useState<PoLine[]>([]);
  const [warehouses, setWarehouses] = useState<Named[]>([]);
  const [addLineId, setAddLineId] = useState("");

  const reload = async () => {
    await qc.invalidateQueries({ queryKey: [grnPath] });
    await qc.invalidateQueries({ queryKey: [`${grnPath}/items`] });
    onChanged();
  };

  const startEdit = async () => {
    if (!grn) return;
    setError("");
    setAddLineId("");
    await run(async () => {
      const [w, po] = await Promise.all([
        api<ListResponse<Named>>("GET", "/api/v1/warehouses", { params: { status: "active", limit: 100 } }),
        api<PoSummary>("GET", `/api/v1/purchase-orders/${grn.poId}`),
      ]);
      const open = (po.lines ?? []).filter((l) => !["closed", "cancelled"].includes(l.status));
      const byId = Object.fromEntries(open.map((l) => [l.id, l]));
      setWarehouses(w.data);
      setPoLines(open);
      setEditWarehouse(grn.warehouseId ?? "");
      setEditLines((grn.lines ?? []).map((l) => ({ id: l.id, poLineId: l.poLineId, sku: l.sku, skuName: lineName(l), uom: l.uom, receivedQty: l.receivedQty, batchNo: l.batchNo ?? "", batchTracked: !!byId[l.poLineId]?.batchTracked })));
      setEditing(true);
    });
  };
  const patch = (i: number, p: Partial<EditLine>) => setEditLines(editLines.map((l, j) => (j === i ? { ...l, ...p } : l)));
  const available = poLines.filter((l) => !editLines.some((e) => e.poLineId === l.id));
  const addLine = () => {
    const pl = poLines.find((l) => l.id === addLineId);
    if (!pl) return;
    setEditLines([...editLines, { id: "", poLineId: pl.id, sku: pl.sku, skuName: lineName(pl), uom: pl.uom, receivedQty: "", batchNo: "", batchTracked: !!pl.batchTracked }]);
    setAddLineId("");
  };
  const saveEdit = async () => {
    setError("");
    if (!editLines.length) return setError("A GRN needs at least one line — remove the whole receipt instead of clearing every line");
    const noQty = editLines.filter((l) => !l.receivedQty).map((l) => l.sku);
    if (noQty.length) return setError(`Received quantity is required for: ${noQty.join(", ")}`);
    const noBatch = editLines.filter((l) => l.batchTracked && !l.batchNo.trim()).map((l) => l.sku);
    if (noBatch.length) return setError(`Batch number is required for: ${noBatch.join(", ")}`);
    const ok = await run(async () => {
      await api("PATCH", grnPath, { json: { warehouseId: editWarehouse, lines: editLines.map((l) => ({ id: l.id || null, poLineId: l.poLineId, receivedQty: l.receivedQty, batchNo: l.batchNo || null })) } });
      await reload();
      return true;
    });
    if (ok) setEditing(false);
  };

  const status = grn?.status ?? "";
  const lines = (grn?.lines ?? []).map((l) => ({ ...l, skuName: lineName(l), ordered: format.qty(l.orderedQty, l.uom), received: format.qty(l.receivedQty), quality: humanise(l.qualityStatus) }));
  const selectedLine = (grn?.lines ?? []).find((l) => l.id === lineId);
  const lineItems = items.filter((i) => i.grnLineId === lineId).map((i) => ({ ...i, qty: format.qty(i.quantity, i.uom), statusLabel: rawItemStatusLabel(i as never) }));

  return (
    <>
      <Modal open onClose={onClose} wide title={grn ? `${grn.number} — ${grn.poNumber}` : "GRN"} footer={<ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>}>
        {grn && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <GrnStatusPill status={grn.status} />
              <span>Vendor: {grn.vendorName}</span>
              <span>Warehouse: {grn.warehouseName}</span>
              <div className="flex-1" />
              <ActionButton size="sm" tone="ghost" onClick={() => run(() => qr.zip(grn))}>Download all QR codes</ActionButton>
              <ActionButton size="sm" tone="ghost" onClick={() => run(() => qr.pdf(grn))}>Download all QR codes in PDF</ActionButton>
              {status === "under_qc" && !editing && <ActionButton size="sm" tone="ghost" onClick={startEdit}>Edit</ActionButton>}
              {["under_qc", "posted"].includes(status) && !editing && <ActionButton size="sm" tone="danger" onClick={() => setCancelOpen(true)}>Cancel GRN</ActionButton>}
            </div>
            <InlineError message={error || grnQ.error?.message} />
            {editing ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <p className="text-xs text-[var(--muted-foreground)]">Receiving warehouse</p>
                  <SelectInput className="ui-select-auto" value={editWarehouse} onChange={(e) => setEditWarehouse(e.target.value)} placeholder="Warehouse" options={warehouses.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))} />
                </div>
                <DesktopOnly className="w-full">
                  <DataTable columns={["SKU Name", "UoM", "Received", "Batch", ""]} minWidth={0} fit>
                    {editLines.map((l, i) => (
                      <tr key={l.poLineId}>
                        <td>{l.skuName}</td>
                        <td>{l.uom}</td>
                        <td><TextInput style={{ width: "8rem" }} placeholder="Received qty" value={l.receivedQty} onChange={(e) => patch(i, { receivedQty: e.target.value })} /></td>
                        <td><TextInput style={{ width: "10rem" }} placeholder={l.batchTracked ? "Batch no (required)" : "Batch no (optional)"} value={l.batchNo} onChange={(e) => patch(i, { batchNo: e.target.value })} /></td>
                        <td><ActionButton size="sm" tone="danger" onClick={() => setEditLines(editLines.filter((_, j) => j !== i))}>Remove</ActionButton></td>
                      </tr>
                    ))}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {editLines.map((l, i) => (
                    <MobileRecordCard key={l.poLineId} actions={<ActionButton size="sm" tone="danger" className="w-full justify-center" onClick={() => setEditLines(editLines.filter((_, j) => j !== i))}>Remove</ActionButton>}>
                      <MobileRecordRow label="SKU Name" value={l.skuName} />
                      <MobileRecordRow label="UoM" value={l.uom} />
                      <div className="mobile-record-row-inputs">
                        <TextInput placeholder="Received qty" value={l.receivedQty} onChange={(e) => patch(i, { receivedQty: e.target.value })} />
                        <TextInput placeholder={l.batchTracked ? "Batch no (required)" : "Batch no (optional)"} value={l.batchNo} onChange={(e) => patch(i, { batchNo: e.target.value })} />
                      </div>
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
                <div className="flex flex-wrap items-center gap-2">
                  <SelectInput style={{ width: "16rem" }} value={addLineId} onChange={(e) => setAddLineId(e.target.value)} placeholder="Add a SKU from this PO" options={available.map((l) => ({ value: l.id, label: lineName(l) }))} />
                  <ActionButton size="sm" tone="ghost" onClick={addLine}>Add line</ActionButton>
                </div>
                <div className="flex justify-end gap-2">
                  <ActionButton size="sm" tone="ghost" onClick={() => { setEditing(false); setError(""); }}>Cancel</ActionButton>
                  <ActionButton size="sm" onClick={saveEdit} loading={busy}>Save changes</ActionButton>
                </div>
              </div>
            ) : lineId ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <ActionButton size="sm" tone="ghost" onClick={() => setLineId("")}>← Back to SKUs</ActionButton>
                  <p className="text-base font-bold">Inventory IDs for {selectedLine?.sku}</p>
                </div>
                <DesktopOnly className="w-full">
                  <DataTable columns={["Inventory ID", "Kind", "Qty", "Status", "Location"]} minWidth={0} fit>
                    {lineItems.map((i) => (
                      <tr key={i.id}>
                        <td><Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link></td>
                        <td>{i.kind}</td>
                        <td>{i.qty}</td>
                        <td><Pill>{i.statusLabel}</Pill></td>
                        <td>{i.locationCode}</td>
                      </tr>
                    ))}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {lineItems.map((i) => (
                    <MobileRecordCard key={i.id}>
                      <MobileRecordRow label="Inventory ID" value={<Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link>} />
                      <MobileRecordRow label="Kind" value={i.kind} />
                      <MobileRecordRow label="Qty" value={i.qty} />
                      <MobileRecordRow label="Status" value={<Pill>{i.statusLabel}</Pill>} />
                      <MobileRecordRow label="Location" value={i.locationCode} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="mt-2 text-base font-bold">SKUs received</p>
                <DesktopOnly className="w-full">
                  <DataTable columns={["SKU Name", "Ordered", "Received", "Batch", "Quality"]} minWidth={0} fit>
                    {lines.map((l) => (
                      <tr key={l.id}>
                        <td><button type="button" className="rx-link" onClick={() => setLineId(l.id)}>{l.skuName}</button></td>
                        <td>{l.ordered}</td>
                        <td>{l.received}</td>
                        <td>{l.batchNo}</td>
                        <td><Pill>{l.quality}</Pill></td>
                      </tr>
                    ))}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {lines.map((l) => (
                    <MobileRecordCard key={l.id}>
                      <MobileRecordRow label="SKU Name" value={<button type="button" className="rx-link" onClick={() => setLineId(l.id)}>{l.skuName}</button>} />
                      <MobileRecordRow label="Ordered" value={l.ordered} />
                      <MobileRecordRow label="Received" value={l.received} />
                      <MobileRecordRow label="Batch" value={l.batchNo} />
                      <MobileRecordRow label="Quality" value={<Pill>{l.quality}</Pill>} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </div>
            )}
          </div>
        )}
      </Modal>
      {cancelOpen && grn && (
        <ReasonDialog
          title={`Cancel ${grn.number}`}
          description={status === "posted" ? "This GRN is posted — cancelling reverses the stock receipt and gives the purchase order back its received quantities." : "This voids the receipt and its inventory rows."}
          confirmLabel="Confirm cancel"
          onClose={() => setCancelOpen(false)}
          onSubmit={async (reason) => {
            await api("POST", `${grnPath}/cancel`, { json: { reason: reason.trim() } });
            setEditing(false);
            setLineId("");
            await reload();
            onClose();
          }}
        />
      )}
    </>
  );
}

// ---- tabs -------------------------------------------------------------------------------------------

function GrnTab({ grns, filters, setFilters, vendors, warehouses, error, onRefresh }: {
  grns: Grn[];
  filters: { search: string; vendor: string; warehouse: string; status: string };
  setFilters: (f: { search: string; vendor: string; warehouse: string; status: string }) => void;
  vendors: { id: string; displayName: string }[];
  warehouses: Named[];
  error?: string;
  onRefresh: () => void;
}) {
  const { can } = useAuth();
  const canWrite = can("grn:write");
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [openId, setOpenId] = useState("");
  const set = (p: Partial<typeof filters>) => setFilters({ ...filters, ...p });
  const link = (g: Grn) => <button type="button" className="rx-link" onClick={() => setOpenId(g.id)}>{g.number}</button>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center gap-3">
        <h2 className="rx-heading-6">Goods Received Notes</h2>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && <ActionButton onClick={() => setReceiveOpen(true)}>Receive goods</ActionButton>}
      </div>
      <ScanToJumpBox />
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input className="search-input shrink-0" style={{ width: "20rem" }} placeholder="Search GRN number or PO number…" value={filters.search} onChange={(e) => set({ search: e.target.value })} />
        <select className="filter-select" style={{ width: "12rem" }} value={filters.vendor} onChange={(e) => set({ vendor: e.target.value })}>
          <option value="">All vendors</option>
          {vendors.map((v) => <option key={v.id} value={v.id}>{v.displayName}</option>)}
        </select>
        <select className="filter-select" style={{ width: "12rem" }} value={filters.warehouse} onChange={(e) => set({ warehouse: e.target.value })}>
          <option value="">All warehouses</option>
          {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <select className="filter-select" value={filters.status} onChange={(e) => set({ status: e.target.value })}>
          <option value="">All Status</option>
          {GRN_STATUSES.map((s) => <option key={s} value={s}>{grnStatusLabel(s)}</option>)}
        </select>
      </div>
      <InlineError message={error} />
      <DesktopOnly className="w-full">
        <DataTable columns={["GRN", "PO", "Vendor", "Warehouse", "Received Goods value", "Status", "Received"]} fit>
          {grns.map((g) => (
            <tr key={g.id}>
              <td>{link(g)}</td>
              <td>{g.poNumber}</td>
              <td>{g.vendorName}</td>
              <td>{g.warehouseName}</td>
              <td>{format.money(g.receivedGoodsValue)}</td>
              <td><GrnStatusPill status={g.status} /></td>
              <td>{format.date(g.receivedDate)}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {grns.map((g) => (
          <MobileRecordCard key={g.id}>
            <MobileRecordRow label="GRN" value={link(g)} />
            <MobileRecordRow label="PO" value={g.poNumber} />
            <MobileRecordRow label="Vendor" value={g.vendorName} />
            <MobileRecordRow label="Warehouse" value={g.warehouseName} />
            <MobileRecordRow label="Value" value={format.money(g.receivedGoodsValue)} />
            <MobileRecordRow label="Status" value={<GrnStatusPill status={g.status} />} />
            <MobileRecordRow label="Received" value={format.date(g.receivedDate)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {receiveOpen && <ReceiveDialog onClose={() => setReceiveOpen(false)} onCreated={onRefresh} />}
      {openId && <DetailDialog grnId={openId} onClose={() => setOpenId("")} onChanged={onRefresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload GRNs"
        description="Upload a CSV with one row per GRN line. Rows sharing the same GRN Ref are grouped into a single receipt against the given PO."
        endpoint="/api/v1/grns/bulk-upload"
        sampleCsv={GRN_BULK_SAMPLE}
        sampleFilename="grn_bulk_upload_template.csv"
        errorFilename="grn_bulk_upload_errors.csv"
        columns={GRN_BULK_COLUMNS}
        labelHeader="GRN Ref"
        labelKey="grnRef"
        successKey="grnNumber"
        noun="GRNs"
        multiRow
        onCompleted={onRefresh}
      />
    </div>
  );
}

function QcTab({ grns, onRefresh }: { grns: Grn[]; onRefresh: () => void }) {
  const { can } = useAuth();
  const canWrite = can("grn:write");
  const [bulkOpen, setBulkOpen] = useState(false);
  const qcLink = (g: Grn, cls = "") => canWrite && <Link to={`/warehouse/qc/${g.id}`} className={`action-btn action-btn-primary action-btn-sm ${cls}`}>Test / QC</Link>;
  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center gap-3">
        <h2 className="rx-heading-6">Goods under QC</h2>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
      </div>
      <DesktopOnly className="w-full">
        <DataTable columns={["GRN", "PO", "Vendor", ""]} fit>
          {grns.map((g) => (
            <tr key={g.id}>
              <td>{g.number}</td>
              <td>{g.poNumber}</td>
              <td>{g.vendorName}</td>
              <td>{qcLink(g)}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {grns.map((g) => (
          <MobileRecordCard key={g.id} actions={qcLink(g, "w-full justify-center")}>
            <MobileRecordRow label="GRN" value={g.number} />
            <MobileRecordRow label="PO" value={g.poNumber} />
            <MobileRecordRow label="Vendor" value={g.vendorName} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload QC decisions"
        description="Upload a CSV with one row per lot-line QC decision, grouped by GRN number. Serialised (piece-by-piece) QC isn't covered — use the GRN's own QC screen for those."
        endpoint="/api/v1/grns/qc/bulk-upload"
        sampleCsv={QC_BULK_SAMPLE}
        sampleFilename="qc_bulk_upload_template.csv"
        errorFilename="qc_bulk_upload_errors.csv"
        columns={QC_BULK_COLUMNS}
        labelHeader="GRN"
        labelKey="grnNumber"
        successKey="grnStatus"
        successText={(r) => `QC recorded (${r.grnStatus})`}
        noun="GRNs"
        verb="QC'd"
        multiRow
        onCompleted={onRefresh}
      />
    </div>
  );
}

function Content() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canGrn = can("grn:read");
  const [filters, setFilters] = useState({ search: "", vendor: "", warehouse: "", status: "" });
  const debounced = useDebounced(filters.search);
  const vendors = useApiQuery<ListResponse<{ id: string; displayName: string }>>("/api/v1/parties", { type: "vendor", limit: 100 }, { enabled: canGrn });
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { status: "active", limit: 100 }, { enabled: canGrn });
  const list = useApiQuery<ListResponse<Grn>>("/api/v1/grns", { limit: 50, q: debounced, vendorId: filters.vendor, warehouseId: filters.warehouse, status: filters.status }, { enabled: canGrn });
  const grns = list.data?.data ?? [];
  const underQc = grns.filter((g) => g.status === "under_qc");
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/grns"] });

  return (
    <div className="warehouse-page flex w-full flex-col gap-2">
      <PageHeader fit eyebrow="Supply chain" title="GRN & QC" />
      <Tabs
        tabs={[
          { value: "grn", label: "Goods Receipt Notes", content: <GrnTab grns={grns} filters={filters} setFilters={setFilters} vendors={vendors.data?.data ?? []} warehouses={warehouses.data?.data ?? []} error={list.error?.message} onRefresh={refresh} /> },
          { value: "qc", label: `Quality Check - RM (${underQc.length})`, content: <QcTab grns={underQc} onRefresh={refresh} /> },
        ]}
      />
    </div>
  );
}

export default function WarehousePage() {
  const { can } = useAuth();
  return <Shell>{can("warehouse:read") ? <Content /> : <Forbidden permission="warehouse read" />}</Shell>;
}
