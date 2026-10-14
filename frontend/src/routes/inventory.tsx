/**
 * Inventory: Stock Balances (SKU-level aggregate) and Inventory Ledger (per-unit), each with
 * Raw Material / Finished Goods / Rejected Raw Material views. Adjust / move / transfer / pending
 * transfers / bulk uploads and the finished-good item dialog live on the ledger tab.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { ScanToJumpBox } from "@/components/erp/scan";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Field, Forbidden, InfoTooltip, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, Segmented, SelectInput, StatCard, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { type Params } from "@/lib/api";
import { errText } from "@/lib/utils";
import * as format from "@/lib/format";
import { useApiQuery, type ListResponse } from "@/lib/hooks";
import { UOMS } from "@/lib/reference";
import { BUCKET_OPTIONS, bucketLabel, humanise, rawItemStatusLabel } from "@/lib/status";

type Category = "raw" | "finished" | "rejected";

interface Product {
  id: string;
  name: string;
  type: string;
}
interface Named {
  id: string;
  name: string;
}
interface Location {
  id: string;
  code: string;
  warehouseName: string;
}
interface Balance {
  productId: string;
  sku: string;
  uom?: string;
  onHand?: string;
  reserved?: string;
  quarantine?: string;
  damaged?: string;
  expired?: string;
}
interface Item {
  id: string;
  inventoryId: string;
  productId: string;
  sku: string;
  uom: string;
  status: string;
  quantity: string;
  availableQty?: string;
  consumedQty?: string;
  rejectedQty?: string;
  acceptedQty?: string;
  allocatedQty?: string;
  batchNo?: string | null;
  transferId?: string | null;
  locationId?: string | null;
  locationCode?: string | null;
  vendorInventoryId?: string | null;
  [k: string]: unknown;
}
interface Valuation {
  totalValue?: string;
  lines?: { productId: string; value: string }[];
}
interface Transfer {
  id: string;
  number: string;
  productName?: string | null;
  sku: string;
  quantity: string;
  uom: string;
  sourceWarehouseName: string;
  destWarehouseName: string;
  dispatchedAt?: string;
}

const ADJ_COLUMNS = ["productSku", "warehouseCode", "locationCode", "batchNo", "expiryDate", "quantity", "uom", "bucket", "reason", "unitCost"];
const ADJ_SAMPLE = `${ADJ_COLUMNS.join(",")}\nRM-0001,WH-AA01,,BATCH-A,,50,KG,available,Cycle count correction,\nRM-0002,WH-AA01,,,,-2,KG,available,Damaged in handling,\n`;
const TRF_COLUMNS = ["productSku", "batchNo", "quantity", "uom", "sourceWarehouseCode", "sourceLocationCode", "destWarehouseCode", "destLocationCode", "reason"];
const TRF_SAMPLE = `${TRF_COLUMNS.join(",")}\nRM-0001,,10,KG,WH-AA01,,WH-AA02,,Rebalancing stock\n`;

/** Inventory Ledger > Raw Material status filter - one option per rawItemStatusLabel() output. */
const RM_STATUS_OPTIONS = [
  { value: "under_qc", label: "Under QC" },
  { value: "available", label: "Available" },
  { value: "in_transit", label: "In Transit" },
  { value: "quarantine", label: "Rejected in QC" },
  { value: "damaged", label: "Damaged" },
  { value: "expired", label: "Expired" },
  { value: "consumed", label: "Consumed" },
  { value: "written_off", label: "Written Off" },
  { value: "rejected", label: "Rejected" },
  { value: "partial", label: "Partial" },
];
/** Stock Balances > Inventory value scoping per sub-tab (Raw Material keeps the combined figure). */
const VALUATION_BUCKET: Record<string, string> = { finished: "available", rejected: "quarantine" };
const VALUATION_TYPE: Record<string, string> = { finished: "finished_good", rejected: "raw_material" };
const DIRECTIONS = [
  { value: "writeoff", label: "Write off (reduce stock)" },
  { value: "add", label: "Add stock (increase stock)" },
];
const CATEGORY_TABS: { value: Category; label: string }[] = [
  { value: "raw", label: "Raw Material" },
  { value: "finished", label: "Finished Goods" },
  { value: "rejected", label: "Rejected Raw Material" },
];

const num = (v: unknown) => Number(v ?? 0) || 0;
const dash = (v: string | null | undefined) => v || "—";

// ---- movement dialogs (adjustment / move-quarantine / transfer share one shape) ------------------

type MoveKind = "adjust" | "status" | "transfer";
interface Line {
  itemId: string;
  quantity: string;
  uom: string;
}
const blankLine = (): Line => ({ itemId: "", quantity: "", uom: "UNIT" });

const MOVE_COPY: Record<MoveKind, { title: string; description: string; noPick: string; submit: string; reasonPlaceholder: string }> = {
  adjust: {
    title: "Post adjustment",
    description: "Corrects recorded stock to match physical reality. Pick a specific Inventory ID to adjust that exact unit — leave it unpicked to adjust by quantity only.",
    noPick: "No specific unit (aggregate only)",
    submit: "Post",
    reasonPlaceholder: "Required",
  },
  status: {
    title: "Move / quarantine",
    description: "Moves stock between condition buckets. Pick a specific Inventory ID to move that exact unit — leave it unpicked to move by quantity only.",
    noPick: "No specific unit (move by quantity)",
    submit: "Move",
    reasonPlaceholder: "Required",
  },
  transfer: {
    title: "Transfer",
    description: "Leaves the source into in-transit immediately; complete the transfer at the destination to land it in available.",
    noPick: "No specific unit (draw automatically)",
    submit: "Dispatch",
    reasonPlaceholder: "Optional",
  },
};

function MoveDialog({ kind, category, products, warehouses, onClose, onDone }: { kind: MoveKind; category: Category; products: Product[]; warehouses: Named[]; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const copy = MOVE_COPY[kind];
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [destId, setDestId] = useState("");
  const [bucket, setBucket] = useState("available"); // adjust bucket / status-change "from"
  const [toBucket, setToBucket] = useState("quarantine");
  const [direction, setDirection] = useState("writeoff");
  const [lines, setLines] = useState<Line[]>([blankLine()]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const skuOptions = products
    .filter((p) => p.type === (category === "finished" ? "finished_good" : "raw_material"))
    .map((p) => ({ value: p.id, label: p.name }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const params =
    kind === "adjust"
      ? { productId, warehouseId, status: "accepted", bucket, notFullyConsumed: "true", limit: 200 }
      : kind === "status"
        ? { productId, warehouseId, limit: 200, ...(bucket === "available" ? { available: "true" } : { status: "accepted", bucket }) }
        : { productId, warehouseId, available: "true", limit: 200 };
  const available = useApiQuery<ListResponse<Item>>("/api/v1/inventory-items", params, { enabled: !!productId && !!warehouseId });
  const items = useMemo(() => (productId && warehouseId ? (available.data?.data ?? []) : []), [available.data, productId, warehouseId]);
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const picked = new Set(lines.map((l) => l.itemId).filter(Boolean));

  const reset = () => setLines([blankLine()]);
  const patch = (i: number, p: Partial<Line>) => setLines(lines.map((l, j) => (j === i ? { ...l, ...p } : l)));
  const pick = (i: number, id: string) => {
    const item = byId[id];
    patch(i, { itemId: id, quantity: kind === "adjust" ? lines[i].quantity : (item?.availableQty ?? ""), uom: item?.uom || lines[i].uom || "UNIT" });
  };

  const submit = async () => {
    setError("");
    if (kind === "transfer") {
      if (!(productId && warehouseId && destId)) return setError("SKU Name, Source warehouse and Destination warehouse are required");
    } else {
      if (!(productId && warehouseId)) return setError("SKU Name and Warehouse are required");
      if (kind === "status" && bucket === toBucket) return setError("Source and destination status are the same");
      if (reason.trim().length < 5) return setError("Reason is required (at least 5 characters)");
    }
    const pending = lines.map((l, i) => ({ l, i })).filter(({ l }) => l.quantity);
    if (!pending.length) return setError("Add at least one line with a quantity");

    setBusy(true);
    const dispatched = new Set<number>();
    try {
      for (const { l, i } of pending) {
        const item = byId[l.itemId];
        try {
          if (kind === "adjust") {
            const magnitude = Math.abs(Number(l.quantity));
            if (!(magnitude > 0)) continue;
            await api("POST", "/api/v1/inventory/adjustments", {
              json: { productId, warehouseId, batchNo: item?.batchNo ?? null, quantity: String((direction === "writeoff" ? -1 : 1) * magnitude), uom: l.uom || "UNIT", bucket, reason, itemId: l.itemId || null },
            });
          } else if (kind === "status") {
            await api("POST", "/api/v1/inventory/status-change", {
              json: { productId, warehouseId, batchNo: item?.batchNo ?? null, quantity: l.quantity, uom: l.uom || "UNIT", from: bucket, to: toBucket, reason, itemId: l.itemId || null },
            });
          } else {
            await api("POST", "/api/v1/inventory/transfers", {
              json: { productId, batchNo: item?.batchNo ?? null, sourceWarehouseId: warehouseId, destWarehouseId: destId, quantity: l.quantity, uom: l.uom || "UNIT", reason: reason || null, itemId: l.itemId || null },
            });
          }
          dispatched.add(i);
        } catch (exc) {
          // Drop what already went through so a retry only re-sends what is still pending.
          setError(`${item ? item.inventoryId : `Line ${i + 1}`}: ${errText(exc)}`);
          setLines(lines.filter((_, j) => !dispatched.has(j)));
          return;
        }
      }
      onClose();
      onDone();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={copy.title} description={copy.description} maxWidth="42rem" footer={<><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton onClick={submit} loading={busy}>{copy.submit}</ActionButton></>}>
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        <Field label="SKU Name">
          <SelectInput value={productId} onChange={(e) => { setProductId(e.target.value); reset(); }} placeholder="Select a SKU" options={skuOptions} />
        </Field>
        {kind === "transfer" ? (
          <div className="flex gap-2">
            <div className="min-w-0 flex-1"><Field label="Source Warehouse"><SelectInput value={warehouseId} onChange={(e) => { setWarehouseId(e.target.value); reset(); }} placeholder="Select a warehouse" options={warehouses.map((w) => ({ value: w.id, label: w.name }))} /></Field></div>
            <div className="min-w-0 flex-1"><Field label="Destination Warehouse"><SelectInput value={destId} onChange={(e) => setDestId(e.target.value)} placeholder="Select a warehouse" options={warehouses.map((w) => ({ value: w.id, label: w.name }))} /></Field></div>
          </div>
        ) : (
          <>
            <Field label="Warehouse">
              <SelectInput value={warehouseId} onChange={(e) => { setWarehouseId(e.target.value); reset(); }} placeholder="Select a warehouse" options={warehouses.map((w) => ({ value: w.id, label: w.name }))} />
            </Field>
            <div className="flex gap-2">
              <div className="min-w-0 flex-1"><Field label={kind === "adjust" ? "Bucket" : "From"}><SelectInput value={bucket} onChange={(e) => { setBucket(e.target.value); reset(); }} options={BUCKET_OPTIONS} /></Field></div>
              <div className="min-w-0 flex-1">
                {kind === "adjust" ? (
                  <Field label="Direction"><SelectInput value={direction} onChange={(e) => setDirection(e.target.value)} options={DIRECTIONS} /></Field>
                ) : (
                  <Field label="To"><SelectInput value={toBucket} onChange={(e) => setToBucket(e.target.value)} options={BUCKET_OPTIONS} /></Field>
                )}
              </div>
            </div>
          </>
        )}
        <div className="flex flex-col gap-2">
          {lines.map((line, i) => {
            const item = byId[line.itemId];
            const options = items
              .filter((it) => (!picked.has(it.id) || it.id === line.itemId) && !(kind === "adjust" && it.transferId))
              .map((it) => ({ value: it.id, label: it.inventoryId }))
              .sort((a, b) => a.label.localeCompare(b.label));
            return (
              <div key={i} className="flex flex-wrap items-end gap-2">
                <div className="min-w-[9rem] flex-[2]">
                  <Field label="Inventory ID">
                    <select className="ui-select" value={line.itemId} onChange={(e) => pick(i, e.target.value)}>
                      <option value="">{copy.noPick}</option>
                      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="min-w-[5.5rem] flex-1"><Field label="Qty"><TextInput value={line.quantity} onChange={(e) => patch(i, { quantity: e.target.value })} /></Field></div>
                <div className="min-w-[5.5rem] flex-1"><Field label="UOM"><SelectInput value={line.uom} onChange={(e) => patch(i, { uom: e.target.value })} options={UOMS.map((u) => ({ value: u, label: u }))} /></Field></div>
                <div className="min-w-[6rem] shrink-0"><Field label="Available Qty"><p className="whitespace-nowrap text-sm">{item ? format.qty(item.availableQty) : "—"}</p></Field></div>
                <ActionButton size="sm" tone="danger" className="mb-1" onClick={() => lines.length > 1 && setLines(lines.filter((_, j) => j !== i))} aria-label="Remove line">×</ActionButton>
              </div>
            );
          })}
          <div><ActionButton size="sm" tone="ghost" onClick={() => setLines([...lines, blankLine()])}>Add line</ActionButton></div>
        </div>
        <Field label="Reason"><TextArea rows={4} placeholder={copy.reasonPlaceholder} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

// ---- pending transfers ------------------------------------------------------------------------

function PendingTransfersDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const list = useApiQuery<ListResponse<Transfer>>("/api/v1/inventory/transfers", { status: "in_transit", limit: 100 });
  const rows = (list.data?.data ?? []).map((t) => ({ ...t, qty: `${format.qty(t.quantity)} ${t.uom}`, when: format.dateTime(t.dispatchedAt), name: format.lineDisplayName(t) }));
  const complete = async (id: string) => {
    try {
      await api("POST", `/api/v1/inventory/transfers/${id}/complete`, { json: {} });
      await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/transfers"] });
      onDone();
    } catch (exc) {
      setError(errText(exc));
    }
  };
  return (
    <Modal open onClose={onClose} title="Pending Transfers" maxWidth="46rem" description="In-transit — dispatched from the source but not yet landed as available at the destination. Complete one once it's physically arrived." footer={<ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>}>
      <div className="flex flex-col gap-3">
        <InlineError message={error || list.error?.message} />
        {rows.length === 0 ? (
          <EmptyState title="No transfers in transit" hint="All inventory stock transfers have been received and completed." />
        ) : (
          <>
            <DesktopOnly className="w-full">
              <DataTable columns={["Transfer #", "SKU Name", "Quantity", "From", "To", "Dispatched", ""]} minWidth={0} fit>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>{t.number}</td><td>{t.name}</td><td>{t.qty}</td><td>{t.sourceWarehouseName}</td><td>{t.destWarehouseName}</td><td>{t.when}</td>
                    <td><ActionButton size="sm" onClick={() => complete(t.id)}>Complete</ActionButton></td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {rows.map((t) => (
                <MobileRecordCard key={t.id} actions={<ActionButton size="sm" onClick={() => complete(t.id)}>Complete</ActionButton>}>
                  <MobileRecordRow label="Transfer #" value={t.number} />
                  <MobileRecordRow label="SKU Name" value={t.name} />
                  <MobileRecordRow label="Quantity" value={t.qty} />
                  <MobileRecordRow label="From" value={t.sourceWarehouseName} />
                  <MobileRecordRow label="To" value={t.destWarehouseName} />
                  <MobileRecordRow label="Dispatched" value={t.when} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </>
        )}
      </div>
    </Modal>
  );
}

// ---- finished-good item dialog ----------------------------------------------------------------------

interface FgDetail extends Item {
  warehouseName?: string;
  productionRunNumber?: string;
  allocatedOrderNumber?: string | null;
}
interface LedgerRow {
  at?: string;
  movementType?: string;
  bucket?: string;
  quantity: string;
  uom?: string;
  reason?: string | null;
}

function FgDetailDialog({ itemId, warehouses, onClose, onChanged }: { itemId: string; warehouses: Named[]; onClose: () => void; onChanged: () => void }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [destId, setDestId] = useState("");
  const [statusTo, setStatusTo] = useState("quarantine");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const detail = useApiQuery<FgDetail>(`/api/v1/inventory/finished-goods/${itemId}`);
  const ledger = useApiQuery<ListResponse<LedgerRow>>("/api/v1/inventory/ledger", { referenceId: itemId, limit: 100 });
  const d = detail.data;
  const history = (ledger.data?.data ?? []).map((r) => ({ ...r, qty: format.qty(r.quantity, r.uom), at: format.dateTime(r.at), bucketLabel: bucketLabel(r.bucket), movement: humanise(r.movementType) }));

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: [`/api/v1/inventory/finished-goods/${itemId}`] });
      await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/ledger"] });
      onChanged();
    } catch (exc) {
      setError(errText(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={d ? `${d.inventoryId} — ${d.sku}` : "Finished good"} maxWidth="42rem" footer={<ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>}>
      {d && (
        <div className="flex flex-col gap-3">
          <InlineError message={error || detail.error?.message} />
          <div className="detail-grid">
            <MobileRecordRow label="Status" value={<Pill>{bucketLabel(d.status)}</Pill>} />
            <MobileRecordRow label="Quantity" value={format.qty(d.quantity, d.uom)} />
            <MobileRecordRow label="Allocated" value={format.qty(d.allocatedQty, d.uom)} />
            <MobileRecordRow label="Available" value={format.qty(d.availableQty, d.uom)} />
            <MobileRecordRow label="Warehouse" value={d.warehouseName} />
            <MobileRecordRow label="Batch" value={dash(d.batchNo)} />
            <MobileRecordRow label="Production run" value={d.productionRunNumber} />
            <MobileRecordRow label="Allocated to order" value={dash(d.allocatedOrderNumber)} />
          </div>
          <p className="mt-2 text-sm font-bold">Transfer to another warehouse</p>
          <div className="flex gap-2">
            <div className="min-w-0 flex-1"><SelectInput value={destId} onChange={(e) => setDestId(e.target.value)} placeholder="Destination warehouse" options={warehouses.map((w) => ({ value: w.id, label: w.name }))} /></div>
            <ActionButton size="sm" disabled={!destId} loading={busy} onClick={() => act(async () => { await api("POST", `/api/v1/inventory/finished-goods/${itemId}/transfer`, { json: { toWarehouseId: destId } }); setDestId(""); })}>Transfer</ActionButton>
          </div>
          <p className="mt-2 text-sm font-bold">Change condition</p>
          <div className="flex gap-2">
            <div className="min-w-0 flex-1"><SelectInput value={statusTo} onChange={(e) => setStatusTo(e.target.value)} options={BUCKET_OPTIONS} /></div>
            <ActionButton size="sm" loading={busy} onClick={() => act(() => api("POST", `/api/v1/inventory/finished-goods/${itemId}/status`, { json: { toStatus: statusTo } }))}>Apply</ActionButton>
          </div>
          <p className="mt-2 text-sm font-bold">Movement history</p>
          <DesktopOnly className="w-full">
            <DataTable columns={["When", "Movement", "Bucket", "Qty", "Reason"]} minWidth={0} fit>
              {history.map((r, i) => (
                <tr key={i}><td>{r.at}</td><td>{r.movement}</td><td>{r.bucketLabel}</td><td>{r.qty}</td><td>{dash(r.reason)}</td></tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {history.map((r, i) => (
              <MobileRecordCard key={i}>
                <MobileRecordRow label="When" value={r.at} />
                <MobileRecordRow label="Movement" value={r.movement} />
                <MobileRecordRow label="Bucket" value={r.bucketLabel} />
                <MobileRecordRow label="Qty" value={r.qty} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </div>
      )}
    </Modal>
  );
}

// ---- data ------------------------------------------------------------------------------------------------

/** One fetch per (category, warehouse, ledger-filter) combination - balances plus the per-unit items behind the tab. */
function useTabData(tab: Category, opts: { warehouseId: string; rmStatus: string; locationId: string; productId: string }, byId: Record<string, Product>, enabled: boolean) {
  const { api } = useAuth();
  const { warehouseId, rmStatus, locationId, productId } = opts;
  return useQuery({
    queryKey: ["inventory-tab", tab, warehouseId, rmStatus, locationId, productId, enabled],
    enabled,
    retry: false,
    queryFn: async () => {
      const get = <T,>(path: string, params: Params) => api<ListResponse<T>>("GET", path, { params });
      const wh = { warehouseId }; // "" is dropped from the query string
      if (tab === "finished") {
        const [balances, fg, grn] = await Promise.all([
          get<Balance>("/api/v1/inventory/balances", { limit: 200, ...wh }),
          get<Item>("/api/v1/inventory/finished-goods", { limit: 200 }),
          get<Item>("/api/v1/inventory-items", { limit: 200 }),
        ]);
        return {
          balances: balances.data.filter((b) => byId[b.productId]?.type === "finished_good"),
          items: [] as Item[],
          underQc: [] as Item[],
          fgItems: fg.data,
          // Rows already converted into a FinishedGoodItem are fully drained (Consumed) - skip the ghost entry.
          fgGrnItems: grn.data.filter((i) => byId[i.productId]?.type === "finished_good" && rawItemStatusLabel(i) !== "Consumed"),
        };
      }
      // The ledger table is filtered server-side to exactly the selected status - a client-side narrowing of a limit=200 page would misread.
      let itemParams: Params;
      if (tab === "rejected") itemParams = { hasRejected: "true" };
      else if (rmStatus === "available") itemParams = { status: "accepted", available: "true" };
      else if (rmStatus === "consumed") itemParams = { status: "accepted", fullyConsumed: "true" };
      else if (rmStatus === "written_off") itemParams = { status: "accepted", writtenOff: "true" };
      else if (rmStatus === "in_transit") itemParams = { status: "accepted", inTransit: "true" };
      else if (["quarantine", "damaged", "expired"].includes(rmStatus)) itemParams = { status: "accepted", bucket: rmStatus };
      else itemParams = { status: rmStatus };
      if (locationId) itemParams.locationId = locationId;
      if (productId) itemParams.productId = productId;
      const [balances, items, underQc] = await Promise.all([
        get<Balance>("/api/v1/inventory/balances", { limit: 200, ...wh }),
        get<Item>("/api/v1/inventory-items", { limit: 200, ...wh, ...itemParams }),
        // Stock Balances' "Under QC" column needs the full set regardless of the ledger's status filter.
        get<Item>("/api/v1/inventory-items", { limit: 200, ...wh, status: "under_qc" }),
      ]);
      const raw = <T extends { productId: string }>(rows: T[]) => rows.filter((r) => byId[r.productId]?.type === "raw_material");
      return { balances: raw(balances.data), items: raw(items.data), underQc: tab === "raw" ? raw(underQc.data) : [], fgItems: [] as Item[], fgGrnItems: [] as Item[] };
    },
  });
}

// ---- page -------------------------------------------------------------------------------------------------

function Content() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const [mainTab, setMainTab] = useState("balances");
  const [tab, setTab] = useState<Category>("raw");
  const [rmStatus, setRmStatus] = useState("available");
  const [warehouseId, setWarehouseId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [productId, setProductId] = useState("");
  const [fgStatus, setFgStatus] = useState("");
  const [view, setView] = useState("count");
  const [move, setMove] = useState<MoveKind | null>(null);
  const [pendingOpen, setPendingOpen] = useState(false);
  const [adjBulk, setAdjBulk] = useState(false);
  const [trfBulk, setTrfBulk] = useState(false);
  const [fgId, setFgId] = useState("");
  const [actionError, setActionError] = useState("");

  const products = useApiQuery<ListResponse<Product>>("/api/v1/products", { limit: 200 });
  const warehouses = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { limit: 100 });
  const productList = useMemo(() => products.data?.data ?? [], [products.data]);
  const byId = useMemo(() => Object.fromEntries(productList.map((p) => [p.id, p])), [productList]);
  const warehouseList = warehouses.data?.data ?? [];

  const locations = useQuery({
    queryKey: ["inventory-locations", warehouseList.map((w) => w.id).join(",")],
    enabled: warehouseList.length > 0,
    retry: false,
    queryFn: async () => {
      const all = await Promise.all(warehouseList.map((w) => api<ListResponse<{ id: string; code: string }>>("GET", `/api/v1/warehouses/${w.id}/locations`)));
      return warehouseList.flatMap((w, i) => all[i].data.map((l) => ({ ...l, warehouseName: w.name }) as Location));
    },
  });
  const locationOptions = (locations.data ?? []).map((l) => ({ value: l.id, label: `${l.warehouseName} — ${l.code}` })).sort((a, b) => a.label.localeCompare(b.label));

  // Best-effort: only feeds the Cost/Count toggle.
  const averageCosts = useQuery({
    queryKey: ["inventory-average-costs"],
    retry: false,
    queryFn: async () => Object.fromEntries((await api<ListResponse<{ productId: string; averageCost: string }>>("GET", "/api/v1/inventory/average-costs")).data.map((r) => [r.productId, r.averageCost])) as Record<string, string>,
  });

  const valuationParams: Record<string, string> = {};
  if (warehouseId) valuationParams.warehouseId = warehouseId;
  if (VALUATION_BUCKET[tab]) valuationParams.bucket = VALUATION_BUCKET[tab];
  const valuation = useApiQuery<Valuation>("/api/v1/inventory/valuation", valuationParams);

  const ready = productList.length > 0 || products.isSuccess;
  const data = useTabData(tab, { warehouseId, rmStatus, locationId, productId }, byId, ready);
  const d = data.data;
  const error = data.error?.message || products.error?.message || warehouses.error?.message || valuation.error?.message || actionError;

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["inventory-tab"] });
    await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/valuation"] });
  };
  const switchTab = (t: string) => {
    setTab(t as Category);
    setLocationId("");
    setProductId("");
    setFgStatus("");
  };

  const totalValue = useMemo(() => {
    const type = VALUATION_TYPE[tab];
    if (!type) return format.money(valuation.data?.totalValue ?? "0");
    // totalValue mixes every product type; narrow the bucket-scoped lines to this tab's own type.
    return format.money((valuation.data?.lines ?? []).filter((l) => byId[l.productId]?.type === type).reduce((s, l) => s + num(l.value), 0));
  }, [tab, valuation.data, byId]);

  // Stock Balances is SKU-level: the API returns one row per (product, warehouse, location, batch), summed here.
  const balanceRows = useMemo(() => {
    const bySku: Record<string, { sku: string; productId: string; uom: string; onHand: number; reserved: number; quarantine: number; damaged: number; expired: number; underQc: number }> = {};
    const row = (sku: string, uom: string | undefined, pid: string) => {
      const a = (bySku[sku] ??= { sku, productId: pid, uom: "", onHand: 0, reserved: 0, quarantine: 0, damaged: 0, expired: 0, underQc: 0 });
      if (!a.uom && uom) a.uom = uom;
      if (!a.productId && pid) a.productId = pid;
      return a;
    };
    for (const b of d?.balances ?? []) {
      const a = row(b.sku, b.uom, b.productId);
      a.onHand += num(b.onHand); a.reserved += num(b.reserved); a.quarantine += num(b.quarantine); a.damaged += num(b.damaged); a.expired += num(b.expired);
    }
    // Received-but-not-yet-QC-cleared raw stock has no StockBalance row, yet still counts toward Total.
    for (const i of d?.underQc ?? []) {
      if (i.status !== "under_qc") continue;
      row(i.sku, i.uom, i.productId).underQc += num(i.quantity) - num(i.acceptedQty) - num(i.rejectedQty);
    }
    const cost = view === "cost";
    return Object.values(bySku)
      .sort((a, b) => a.sku.localeCompare(b.sku))
      .map((a) => {
        const avg = num(averageCosts.data?.[a.productId]);
        const f = (q: number) => (cost ? format.money(q * avg) : format.qty(q));
        return {
          sku: a.sku,
          skuName: byId[a.productId]?.name || a.sku,
          uom: a.uom,
          onHand: f(a.onHand),
          reserved: f(a.reserved),
          quarantine: f(a.quarantine),
          damaged: f(a.damaged),
          expired: f(a.expired),
          underQc: f(a.underQc),
          total: f(a.underQc + a.onHand + a.quarantine + a.damaged + a.expired),
          fgTotal: f(a.onHand + a.reserved + a.quarantine + a.damaged + a.expired),
        };
      });
  }, [d, view, averageCosts.data, byId]);

  const items = (d?.items ?? []).map((i) => ({
    ...i,
    skuName: byId[i.productId]?.name || i.sku,
    qty: format.qty(i.quantity),
    rejected: format.qty(i.rejectedQty),
    statusLabel: rawItemStatusLabel(i as never),
    canDispose: i.status === "rejected",
  }));

  const fgRows = useMemo(() => {
    const produced = (d?.fgItems ?? []).map((i) => ({ ...i, source: "production", skuName: byId[i.productId]?.name || i.sku, qty: format.qty(i.quantity), allocated: format.qty(i.allocatedQty), avail: format.qty(i.availableQty), statusLabel: bucketLabel(i.status) }));
    const received = (d?.fgGrnItems ?? []).map((i) => ({ ...i, source: "grn", skuName: byId[i.productId]?.name || i.sku, qty: format.qty(i.quantity), allocated: format.qty("0"), avail: format.qty(i.availableQty), statusLabel: rawItemStatusLabel(i as never) }));
    return [...produced, ...received].sort((a, b) => a.inventoryId.localeCompare(b.inventoryId));
  }, [d, byId]);
  const fgStatusOptions = [...new Set(fgRows.map((r) => r.statusLabel))].sort();
  const fgFiltered = fgRows
    .filter((r) => !locationId || r.locationId === locationId)
    .filter((r) => !productId || r.productId === productId)
    .filter((r) => !fgStatus || r.statusLabel === fgStatus);

  const dispose = async (id: string, disposition: string) => {
    setActionError("");
    try {
      await api("POST", `/api/v1/inventory-items/${id}/dispose`, { json: { disposition } });
      await refresh();
    } catch (exc) {
      setActionError(errText(exc));
    }
  };

  const skuFilterOptions = productList
    .filter((p) => p.type === (tab === "finished" ? "finished_good" : "raw_material"))
    .map((p) => ({ value: p.id, label: p.name }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const categoryTabs = (
    <div className="tabs-list" role="tablist">
      {CATEGORY_TABS.map((c) => (
        <button key={c.value} type="button" role="tab" aria-selected={tab === c.value} data-state={tab === c.value ? "active" : "inactive"} className="tabs-trigger" onClick={() => switchTab(c.value)}>{c.label}</button>
      ))}
    </div>
  );

  const idLink = (i: { id: string; inventoryId: string }) => <Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link>;

  const warehouseFilter = (
    <div className="flex items-center gap-2">
      <label htmlFor="inventory-warehouse-filter" className="text-sm font-bold">Warehouse</label>
      <select id="inventory-warehouse-filter" className="filter-select" style={{ width: "14rem" }} value={warehouseId} aria-label="Filter by All warehouses" onChange={(e) => setWarehouseId(e.target.value)}>
        <option value="">All warehouses</option>
        {warehouseList.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
      </select>
    </div>
  );
  const balancesHeader = (
    <div className="flex w-full flex-wrap items-center gap-4">
      {warehouseFilter}
      <StatCard label="Inventory value" value={totalValue} />
      <div className="flex-1" />
      <Segmented value={view} onChange={setView} options={[{ value: "count", label: "Count" }, { value: "cost", label: "Cost" }]} />
    </div>
  );

  const balancesTable = (columns: string[], render: (b: (typeof balanceRows)[number]) => ReactNode[], cards: (b: (typeof balanceRows)[number]) => [string, ReactNode][]) => (
    balanceRows.length === 0 ? (
      <EmptyState title="No inventory balances found" hint="Try adjusting your warehouse, category, or search filters." />
    ) : (
      <>
        <DesktopOnly className="w-full">
          <DataTable columns={columns} fit>
            {balanceRows.map((b) => <tr key={b.sku}>{render(b).map((c, i) => <td key={i}>{c}</td>)}</tr>)}
          </DataTable>
        </DesktopOnly>
        <MobileOnly className="w-full">
          {balanceRows.map((b) => (
            <MobileRecordCard key={b.sku}>{cards(b).map(([l, v]) => <MobileRecordRow key={l} label={l} value={v} />)}</MobileRecordCard>
          ))}
        </MobileOnly>
      </>
    )
  );

  const balancesView =
    tab === "raw"
      ? balancesTable(
          ["SKU Name", "UOM", "Under QC", "On hand", "Rejected in QC", "Damaged", "Expired", "Total"],
          (b) => [b.skuName, b.uom, b.underQc, b.onHand, b.quarantine, b.damaged, b.expired, <b key="t">{b.total}</b>],
          (b) => [["SKU Name", b.skuName], ["UOM", b.uom], ["Under QC", b.underQc], ["On hand", b.onHand], ["Rejected in QC", b.quarantine], ["Damaged", b.damaged], ["Expired", b.expired], ["Total", b.total]],
        )
      : tab === "finished"
        ? balancesTable(
            ["SKU Name", "UOM", "On hand", "Reserved", "Rejected in QC", "Damaged", "Expired", "Total"],
            (b) => [b.skuName, b.uom, b.onHand, b.reserved, b.quarantine, b.damaged, b.expired, <b key="t">{b.fgTotal}</b>],
            (b) => [["SKU Name", b.skuName], ["UOM", b.uom], ["On hand", b.onHand], ["Reserved", b.reserved], ["Rejected in QC", b.quarantine], ["Damaged", b.damaged], ["Expired", b.expired], ["Total", b.fgTotal]],
          )
        : balancesTable(["SKU Name", "UOM", "Rejected in QC"], (b) => [b.skuName, b.uom, b.quarantine], (b) => [["SKU Name", b.skuName], ["UOM", b.uom], ["Rejected in QC", b.quarantine]]);

  const locationFilter = (
    <select className="filter-select" style={{ width: "12rem" }} value={locationId} aria-label="Filter by All locations" onChange={(e) => setLocationId(e.target.value)}>
      <option value="">All locations</option>
      {locationOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  const skuFilter = (
    <select className="filter-select" style={{ width: "14rem" }} value={productId} aria-label="Filter by All SKU Names" onChange={(e) => setProductId(e.target.value)}>
      <option value="">All SKU Names</option>
      {skuFilterOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  const actionButtons = (
    <>
      {can("inventory:transfer") && <BulkUploadButton onClick={() => setTrfBulk(true)} label="Bulk Upload Transfers" />}
      {can("inventory:transfer") && <ActionButton size="sm" tone="ghost" onClick={() => setMove("transfer")}>Transfer</ActionButton>}
      {can("inventory:transfer") && <ActionButton size="sm" tone="ghost" onClick={() => setPendingOpen(true)}>Pending Transfers</ActionButton>}
      {can("inventory:adjust") && <ActionButton size="sm" tone="ghost" onClick={() => setMove("status")}>Move / quarantine</ActionButton>}
      {can("inventory:adjust") && <BulkUploadButton onClick={() => setAdjBulk(true)} label="Bulk Upload Adjustments" />}
      {can("inventory:adjust") && <ActionButton size="sm" onClick={() => setMove("adjust")}>Post adjustment</ActionButton>}
    </>
  );

  const disposeButtons = (i: { id: string; canDispose: boolean }) =>
    i.canDispose && (
      <div className="flex flex-wrap gap-2">
        <ActionButton size="sm" tone="ghost" onClick={() => dispose(i.id, "returned_to_vendor")}>Return to Vendor</ActionButton>
        <ActionButton size="sm" tone="danger" onClick={() => dispose(i.id, "discarded")}>Discard</ActionButton>
      </div>
    );

  const fgIdLink = (i: (typeof fgRows)[number]) =>
    i.source === "production" ? (
      <button type="button" className="rx-link" onClick={() => setFgId(i.id)}>{i.inventoryId}</button>
    ) : (
      idLink(i)
    );

  const ledgerView =
    tab === "finished" ? (
      <>
        <div className="flex flex-wrap items-center gap-2">
          {actionButtons}
          <select className="filter-select" style={{ width: "11rem" }} value={fgStatus} aria-label="Filter by All Status" onChange={(e) => setFgStatus(e.target.value)}>
            <option value="">All Status</option>
            {fgStatusOptions.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {locationFilter}
          {skuFilter}
        </div>
        {fgFiltered.length === 0 ? (
          <EmptyState title="No finished goods found" hint="Try adjusting your status, warehouse, or SKU filters." />
        ) : (
          <>
            <DesktopOnly className="w-full">
              <DataTable columns={["FG-ID", "SKU Name", "UOM", "Status", "Qty", "Allocated", "Available", "Location"]} fit>
                {fgFiltered.map((i) => (
                  <tr key={`${i.source}-${i.id}`}>
                    <td>{fgIdLink(i)}</td><td>{i.skuName}</td><td>{i.uom}</td><td><Pill>{i.statusLabel}</Pill></td><td>{i.qty}</td><td>{i.allocated}</td><td>{i.avail}</td><td>{dash(i.locationCode)}</td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {fgFiltered.map((i) => (
                <MobileRecordCard key={`${i.source}-${i.id}`}>
                  <MobileRecordRow label="FG-ID" value={fgIdLink(i)} />
                  <MobileRecordRow label="SKU Name" value={i.skuName} />
                  <MobileRecordRow label="UOM" value={i.uom} />
                  <MobileRecordRow label="Status" value={<Pill>{i.statusLabel}</Pill>} />
                  <MobileRecordRow label="Qty" value={i.qty} />
                  <MobileRecordRow label="Allocated" value={i.allocated} />
                  <MobileRecordRow label="Available" value={i.avail} />
                  <MobileRecordRow label="Location" value={dash(i.locationCode)} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </>
        )}
      </>
    ) : tab === "raw" ? (
      <>
        <div className="flex flex-wrap items-center gap-2">
          {actionButtons}
          <select className="filter-select" value={rmStatus} aria-label="Filter by Raw Material Status" onChange={(e) => setRmStatus(e.target.value)}>
            {RM_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {locationFilter}
          {skuFilter}
        </div>
        {items.length === 0 ? (
          <EmptyState title="No raw material inventory items found" hint="Try adjusting your status or location filters." />
        ) : (
          <>
            <DesktopOnly className="w-full">
              <DataTable columns={["Inventory ID", "SKU Name", "UOM", <span className="inline-flex items-center">Qty <InfoTooltip content="Available balance tracked under First-In-First-Out (FIFO) consumption rules." /></span>, "Status", "Location", "Vendor Inventory ID"]} fit>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td>{idLink(i)}</td><td>{i.skuName}</td><td>{i.uom}</td><td>{i.qty}</td><td><Pill>{i.statusLabel}</Pill></td><td>{dash(i.locationCode)}</td><td>{dash(i.vendorInventoryId)}</td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {items.map((i) => (
                <MobileRecordCard key={i.id}>
                  <MobileRecordRow label="Inventory ID" value={idLink(i)} />
                  <MobileRecordRow label="SKU Name" value={i.skuName} />
                  <MobileRecordRow label="UOM" value={i.uom} />
                  <MobileRecordRow label="Qty" value={i.qty} />
                  <MobileRecordRow label="Status" value={<Pill>{i.statusLabel}</Pill>} />
                  <MobileRecordRow label="Location" value={dash(i.locationCode)} />
                  <MobileRecordRow label="Vendor Inventory ID" value={dash(i.vendorInventoryId)} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </>
        )}
      </>
    ) : (
      <>
        <div className="flex flex-wrap items-center gap-2">
          {actionButtons}
          {locationFilter}
          {skuFilter}
        </div>
        {items.length === 0 ? (
          <EmptyState title="No quarantine or rejected items" hint="No items currently require QC inspection or disposal." />
        ) : (
          <>
            <DesktopOnly className="w-full">
              <DataTable columns={["Inventory ID", "SKU Name", "UOM", "Status", "Rejected in QC", "Location", ""]} fit>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td>{idLink(i)}</td><td>{i.skuName}</td><td>{i.uom}</td><td><Pill>{i.statusLabel}</Pill></td><td>{i.rejected}</td><td>{dash(i.locationCode)}</td><td>{disposeButtons(i)}</td>
                  </tr>
                ))}
              </DataTable>
            </DesktopOnly>
            <MobileOnly className="w-full">
              {items.map((i) => (
                <MobileRecordCard key={i.id} actions={disposeButtons(i) || undefined}>
                  <MobileRecordRow label="Inventory ID" value={idLink(i)} />
                  <MobileRecordRow label="SKU Name" value={i.skuName} />
                  <MobileRecordRow label="UOM" value={i.uom} />
                  <MobileRecordRow label="Status" value={<Pill>{i.statusLabel}</Pill>} />
                  <MobileRecordRow label="Rejected in QC" value={i.rejected} />
                  <MobileRecordRow label="Location" value={dash(i.locationCode)} />
                </MobileRecordCard>
              ))}
            </MobileOnly>
          </>
        )}
      </>
    );

  return (
    <div className="flex w-full flex-col items-start gap-2">
      <div className="inventory-page-header w-full"><PageHeader eyebrow="Supply chain" title="Inventory" /></div>
      <Tabs
        value={mainTab}
        onValueChange={setMainTab}
        tabs={[
          {
            value: "balances",
            label: "Stock Balances",
            content: (
              <div className="flex w-full flex-col items-start gap-4 pt-4">
                {categoryTabs}
                <InlineError message={error} />
                {balancesHeader}
                {balancesView}
              </div>
            ),
          },
          {
            value: "ledger",
            label: "Inventory Ledger",
            content: (
              <div className="flex w-full flex-col items-start gap-4 pt-4">
                {categoryTabs}
                {tab !== "finished" && <ScanToJumpBox />}
                <InlineError message={error} />
                {ledgerView}
              </div>
            ),
          },
        ]}
      />
      {move && <MoveDialog kind={move} category={tab} products={productList} warehouses={warehouseList} onClose={() => setMove(null)} onDone={refresh} />}
      {pendingOpen && <PendingTransfersDialog onClose={() => setPendingOpen(false)} onDone={refresh} />}
      {fgId && <FgDetailDialog itemId={fgId} warehouses={warehouseList} onClose={() => setFgId("")} onChanged={refresh} />}
      <BulkUploadDialog
        open={adjBulk}
        onClose={() => setAdjBulk(false)}
        title="Bulk upload adjustments"
        description="Upload a CSV with one row per adjustment. Use a negative quantity to write stock off."
        endpoint="/api/v1/inventory/adjustments/bulk-upload"
        sampleCsv={ADJ_SAMPLE}
        sampleFilename="adjustment_bulk_upload_template.csv"
        errorFilename="adjustment_bulk_upload_errors.csv"
        columns={ADJ_COLUMNS}
        labelHeader="SKU Name"
        labelKey="label"
        successKey="reference"
        noun="adjustments"
        verb="posted"
        onCompleted={refresh}
      />
      <BulkUploadDialog
        open={trfBulk}
        onClose={() => setTrfBulk(false)}
        title="Bulk upload transfers"
        description="Upload a CSV with one row per inventory transfer."
        endpoint="/api/v1/inventory/transfers/bulk-upload"
        sampleCsv={TRF_SAMPLE}
        sampleFilename="transfer_bulk_upload_template.csv"
        errorFilename="transfer_bulk_upload_errors.csv"
        columns={TRF_COLUMNS}
        labelHeader="SKU Name"
        labelKey="label"
        successKey="transferNumber"
        noun="transfers"
        onCompleted={refresh}
      />
    </div>
  );
}

export default function InventoryPage() {
  const { can } = useAuth();
  return <Shell>{can("inventory:read") ? <Content /> : <Forbidden permission="inventory:read" />}</Shell>;
}
