/** Production & Shipping: production runs (planning, bulk upload) and the Order Shipping queue (pack / ship per line). */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { DateRangePicker } from "@/components/erp/date-range";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { useApiQuery, useDebounced, type ListResponse } from "@/lib/hooks";
import { humanise } from "@/lib/status";

interface Run {
  id: string;
  number: string;
  productName?: string | null;
  sku: string;
  warehouseName?: string | null;
  packId?: string | null;
  quantity: string;
  status: string;
  productionDate?: string | null;
}
interface Named {
  id: string;
  name: string;
}
interface Product {
  id: string;
  sku: string;
}
interface OrderLine {
  id: string;
  sku: string;
  productName?: string | null;
  uom?: string;
  status: string;
  allocatedQty?: string;
  packedQty?: string;
  shippedQty?: string;
  allocation?: { inventoryIds?: string[]; batchNo?: string | null } | null;
}
interface ShippingOrder {
  id: string;
  number: string;
  customerName: string;
  lines?: OrderLine[];
}

const RUN_STATUSES = ["planned", "posted", "reversed"];
const SHIPPING_STATUSES = ["pending_packing", "partially_packed", "packed", "partially_shipped", "shipped"];
/**
 * Explicit tone per shipping status, rather than Pill's substring detection: "partially_packed" /
 * "partially_shipped" both end in "packed"/"shipped" (a success word) and would read as done.
 */
const SHIPPING_TONE = { pending_packing: "warning", partially_packed: "warning", packed: "success", partially_shipped: "warning", shipped: "success" } as const;

// Mirrors the backend's PRODUCTION_BULK_UPLOAD_ALL_COLUMNS - one row per run (FIFO auto-consumption).
const BULK_COLUMNS = ["productSku", "quantity", "uom", "warehouseCode", "locationCode", "batchNo", "expiryDate", "asOf", "notes", "additionalComponents"];
const BULK_SAMPLE =
  `${BULK_COLUMNS.join(",")}\n` +
  "FG-0001,10,UNIT,WH-AA01,,BATCH-2026-09,,,First bulk production run,\n" +
  "FG-0002,5,UNIT,WH-AA01,,BATCH-2026-09B,,,Includes rework material,RM-0009:1.5:KG\n";

const dash = (v: string | null | undefined) => v || "—";

// ---- planning ----------------------------------------------------------------------------------

function PlanningDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { api } = useAuth();
  const [date, setDate] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [rows, setRows] = useState([{ productId: "", packId: "" }]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const products = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "finished_good", limit: 100 });
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { limit: 100 });
  const whList = warehouses.data?.data ?? [];
  // GET /warehouses already only returns the ones this actor can see, so "one row" means a locked warehouse.
  const locked = whList.length === 1;
  const effectiveWarehouse = locked ? whList[0].id : warehouseId;

  const patch = (i: number, p: Partial<(typeof rows)[number]>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));

  const submit = async () => {
    setError("");
    if (!date) return setError("Production date is required");
    if (!effectiveWarehouse) return setError("Warehouse is required");
    const items = rows.filter((r) => r.productId).map((r) => ({ productId: r.productId, packId: r.packId || null }));
    if (!items.length) return setError("Add at least one finished good");
    setSaving(true);
    try {
      await api("POST", "/api/v1/inventory/production/plan", { json: { productionDate: date, warehouseId: effectiveWarehouse, items } });
      onClose();
      onCreated();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Daily Production Planning"
      description="Reserve a Production ID and pack ID for each finished good you plan to build today - everything else is filled in later, in Complete Production."
      footer={<><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton onClick={submit} loading={saving}>Create planned runs</ActionButton></>}
    >
      <div className="flex flex-col gap-3">
        <InlineError message={error || products.error?.message} />
        <div className="form-grid">
          <Field label="Production date"><TextInput type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Warehouse">
            {locked ? <TextInput value={whList[0].name} disabled readOnly /> : <SelectInput value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="Select warehouse" options={whList.map((w) => ({ value: w.id, label: w.name }))} />}
          </Field>
        </div>
        <p className="mt-2 text-sm font-bold">Finished goods to plan</p>
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <div className="min-w-[10rem] flex-1"><SelectInput value={r.productId} onChange={(e) => patch(i, { productId: e.target.value })} placeholder="Finished good" options={(products.data?.data ?? []).map((p) => ({ value: p.id, label: p.sku }))} /></div>
            <div className="min-w-[10rem] flex-1"><TextInput placeholder="Pack ID (optional)" value={r.packId} onChange={(e) => patch(i, { packId: e.target.value })} /></div>
            <ActionButton size="sm" tone="danger" onClick={() => rows.length > 1 && setRows(rows.filter((_, j) => j !== i))}>Remove</ActionButton>
          </div>
        ))}
        <div><ActionButton size="sm" tone="ghost" onClick={() => setRows([...rows, { productId: "", packId: "" }])}>Add row</ActionButton></div>
      </div>
    </Modal>
  );
}

// ---- runs tab --------------------------------------------------------------------------------------

function RunsTab() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canProduce = can("inventory:produce");
  const [search, setSearch] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [status, setStatus] = useState("");
  const [range, setRange] = useState({ from: "", to: "" });
  const [page, setPage] = useState(1);
  const [planOpen, setPlanOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const debounced = useDebounced(search);
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { limit: 100 });
  const list = useApiQuery<ListResponse<Run>>("/api/v1/inventory/production", { page, limit: 20, q: debounced, warehouseId: warehouse, status, productionDateFrom: range.from, productionDateTo: range.to });
  const runs = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/inventory/production"] });
  const back = (fn: () => void) => () => { fn(); setPage(1); };

  const complete = (r: Run, cls = "") => r.status === "planned" && <Link to={`/production/complete/${r.id}`} className={`action-btn action-btn-primary whitespace-nowrap ${cls}`}>Complete Production</Link>;
  const numberLink = (r: Run) => <Link to={`/production/${r.id}`} className="rx-link">{r.number}</Link>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full flex-wrap items-center gap-3">
        <input className="search-input" style={{ width: "16rem" }} placeholder="Search Production ID or Pack ID…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <DateRangePicker from={range.from} to={range.to} onApply={(from, to) => { setRange({ from, to }); setPage(1); }} />
        <select className="filter-select" style={{ width: "11rem" }} value={warehouse} onChange={(e) => back(() => setWarehouse(e.target.value))()}>
          <option value="">All warehouses</option>
          {(warehouses.data?.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <select className="filter-select" style={{ width: "9rem" }} value={status} onChange={(e) => back(() => setStatus(e.target.value))()}>
          <option value="">All Status</option>
          {RUN_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex-1" />
        {canProduce && (
          <div className="flex flex-wrap gap-3">
            <BulkUploadButton onClick={() => setBulkOpen(true)} />
            <ActionButton onClick={() => setPlanOpen(true)}>Production Planning</ActionButton>
          </div>
        )}
      </div>
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Production ID", "SKU Name", "Warehouse", "Pack ID", "Qty", "Status", "Production Date", ""]} fit>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>{numberLink(r)}</td><td>{r.productName || r.sku}</td><td>{dash(r.warehouseName)}</td><td>{dash(r.packId)}</td><td>{format.qty(r.quantity)}</td>
              <td><Pill>{r.status}</Pill></td><td>{format.date(r.productionDate)}</td><td>{complete(r)}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {runs.map((r) => (
          <MobileRecordCard key={r.id} actions={complete(r, "w-full justify-center") || undefined}>
            <MobileRecordRow label="Production ID" value={numberLink(r)} />
            <MobileRecordRow label="SKU Name" value={r.productName || r.sku} />
            <MobileRecordRow label="Warehouse" value={dash(r.warehouseName)} />
            <MobileRecordRow label="Pack ID" value={dash(r.packId)} />
            <MobileRecordRow label="Qty" value={format.qty(r.quantity)} />
            <MobileRecordRow label="Status" value={<Pill>{r.status}</Pill>} />
            <MobileRecordRow label="Production Date" value={format.date(r.productionDate)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {planOpen && <PlanningDialog onClose={() => setPlanOpen(false)} onCreated={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload production runs"
        description="Upload a CSV with one row per production run (FIFO auto-consumption from the BOM). additionalComponents (optional) is SKU:QTY:UOM, pipe-separated for more than one."
        endpoint="/api/v1/inventory/production/bulk-upload"
        sampleCsv={BULK_SAMPLE}
        sampleFilename="production_bulk_upload_template.csv"
        errorFilename="production_bulk_upload_errors.csv"
        columns={BULK_COLUMNS}
        labelHeader="SKU Name"
        labelKey="label"
        successKey="runNumber"
        noun="production runs"
        verb="posted"
        onCompleted={refresh}
      />
    </div>
  );
}

// ---- order shipping tab -------------------------------------------------------------------------------

interface ShipRow {
  lineId: string;
  orderNumber: string;
  customerName: string;
  skuName: string;
  qty: string;
  status: keyof typeof SHIPPING_TONE;
  inventoryIds: string;
  actionLabel: string;
  actionMode: "" | "pack" | "ship";
  actionMax: number;
}

/** One row per allocated, non-cancelled SKU line - packing/shipping happens per line, not per order. */
function shippingRows(orders: ShippingOrder[]): ShipRow[] {
  const rows: ShipRow[] = [];
  for (const o of orders) {
    for (const l of o.lines ?? []) {
      if (l.status === "cancelled") continue;
      const allocated = Number(l.allocatedQty || 0);
      if (allocated <= 0) continue;
      const packed = Number(l.packedQty || 0);
      const shipped = Number(l.shippedQty || 0);
      const toPack = Math.max(allocated - packed, 0);
      const toShip = Math.max(packed - shipped, 0);
      const status: ShipRow["status"] = shipped >= allocated ? "shipped" : shipped > 0 ? "partially_shipped" : packed >= allocated ? "packed" : packed > 0 ? "partially_packed" : "pending_packing";
      // Fully shipped never offers an action, even when packedQty looks inconsistent (legacy whole-order ship).
      let action: [string, ShipRow["actionMode"], number] = ["", "", 0];
      if (shipped >= allocated) action = ["", "", 0];
      else if (toShip > 0) action = ["To be Shipped", "ship", toShip];
      else if (toPack > 0) action = ["Mark Packed", "pack", toPack];
      const ids = l.allocation?.inventoryIds ?? [];
      rows.push({
        lineId: l.id,
        orderNumber: o.number,
        customerName: o.customerName,
        skuName: l.productName || l.sku,
        qty: format.qty(String(allocated), l.uom),
        status,
        inventoryIds: ids.length ? ids.join(", ") : l.allocation?.batchNo || "—",
        actionLabel: action[0],
        actionMode: action[1],
        actionMax: action[2],
      });
    }
  }
  return rows;
}

function PackShipDialog({ row, onClose, onDone }: { row: ShipRow; onClose: () => void; onDone: (updated: ShippingOrder) => void }) {
  const { api } = useAuth();
  const isShip = row.actionMode === "ship";
  const max = format.qty(String(row.actionMax));
  const [qty, setQty] = useState(max);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setError("");
    const q = Number(qty);
    if (qty.trim() === "" || Number.isNaN(q)) return setError("Enter a valid quantity");
    if (q <= 0) return setError("Quantity must be greater than zero");
    if (q > Number(max || 0)) return setError(`Only ${max} is available to ${isShip ? "ship" : "pack"}`);
    setSaving(true);
    try {
      const updated = await api<ShippingOrder>("POST", `/api/v1/orders/lines/${row.lineId}/${isShip ? "ship" : "pack"}`, { json: { quantity: String(q) } });
      onClose();
      onDone(updated);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} descriptionSize="2" title={isShip ? "Mark Shipped" : "Mark Packed"} description={`${row.orderNumber} · ${row.skuName}`} footer={<><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton onClick={submit} loading={saving}>{isShip ? "Confirm Shipped" : "Confirm Packed"}</ActionButton></>}>
      <div className="flex flex-col gap-2">
        <Field label={isShip ? "Qty shipped" : "Qty packed"}><TextInput type="number" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
        <p className="text-xs text-[var(--muted-foreground)]">Up to {max} available</p>
        <InlineError message={error} />
      </div>
    </Modal>
  );
}

function ShippingTab() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sku, setSku] = useState("");
  const [active, setActive] = useState<ShipRow | null>(null);

  // partially_shipped is included so an order doesn't vanish once its first line ships; 'shipped' itself has nothing left to do.
  const orders = useQuery({
    queryKey: ["production-shipping-orders"],
    retry: false,
    queryFn: async () => {
      const list = await api<ListResponse<{ id: string }>>("GET", "/api/v1/orders", { params: { status: "allocated,partially_allocated,partially_shipped", limit: 100 } });
      return Promise.all(list.data.map((o) => api<ShippingOrder>("GET", `/api/v1/orders/${o.id}`)));
    },
  });
  const all = shippingRows(orders.data ?? []);
  const skuOptions = [...new Set(all.map((r) => r.skuName))].sort();
  const q = search.trim().toLowerCase();
  const rows = all.filter((r) => (!q || r.orderNumber.toLowerCase().includes(q)) && (!status || r.status === status) && (!sku || r.skuName === sku));

  const button = (r: ShipRow, cls = "") => r.actionLabel && <ActionButton size="sm" className={cls} onClick={() => setActive(r)}>{r.actionLabel}</ActionButton>;
  const pill = (r: ShipRow) => <Pill tone={SHIPPING_TONE[r.status]}>{humanise(r.status)}</Pill>;

  return (
    <div className="flex w-full flex-col items-start gap-3">
      <p className="text-xs text-[var(--muted-foreground)]">Orders with Finished Good stock already allocated, listed one row per SKU - pack and ship each line, partial quantities included.</p>
      <div className="flex flex-wrap gap-3">
        <input className="search-input" style={{ width: "16rem" }} placeholder="Search Order Number…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="filter-select" style={{ width: "11rem" }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All Status</option>
          {SHIPPING_STATUSES.map((s) => <option key={s} value={s}>{humanise(s)}</option>)}
        </select>
        <select className="filter-select" style={{ width: "12rem" }} value={sku} onChange={(e) => setSku(e.target.value)}>
          <option value="">All SKU Names</option>
          {skuOptions.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <InlineError message={orders.error?.message} />
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No allocated lines waiting to be packed or shipped.</p>
      ) : (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["Order Number", "Customer Name", "SKU Name", "Quantity", "Status", "Inventory ID", ""]} fit>
              {rows.map((r) => (
                <tr key={r.lineId}>
                  <td>{r.orderNumber}</td><td>{r.customerName}</td><td>{r.skuName}</td><td>{r.qty}</td><td>{pill(r)}</td><td>{r.inventoryIds}</td><td>{button(r)}</td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {rows.map((r) => (
              <MobileRecordCard key={r.lineId} actions={button(r) || undefined}>
                <MobileRecordRow label="Order" value={r.orderNumber} />
                <MobileRecordRow label="Customer" value={r.customerName} />
                <MobileRecordRow label="SKU Name" value={r.skuName} />
                <MobileRecordRow label="Qty" value={r.qty} />
                <MobileRecordRow label="Status" value={pill(r)} />
                <MobileRecordRow label="Inventory ID" value={r.inventoryIds} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      {active && <PackShipDialog row={active} onClose={() => setActive(null)} onDone={() => qc.invalidateQueries({ queryKey: ["production-shipping-orders"] })} />}
    </div>
  );
}

export default function ProductionPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("inventory:read") ? (
        <div className="flex w-full flex-col items-start gap-2">
          <div className="production-page-header w-full"><PageHeader eyebrow="Supply chain" title="Production & Shipping" /></div>
          <Tabs
            tabs={[
              { value: "runs", label: "Production", content: <div className="pt-4">{<RunsTab />}</div> },
              { value: "shipping", label: "Order Shipping", content: <div className="pt-4">{can("order:read") ? <ShippingTab /> : null}</div> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="inventory:read" />
      )}
    </Shell>
  );
}
