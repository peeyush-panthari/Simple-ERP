/** Inventory item detail - the QR-code landing page for one physical unit (a piece or a lot). */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ScanToAddButton } from "@/components/erp/scan";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, PageHeader, Panel, Pill, RecordNotFound, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, type ListResponse } from "@/lib/hooks";
import { BUCKET_OPTIONS, bucketLabel, humanise, rawItemStatusLabel } from "@/lib/status";

interface ItemDetail {
  id: string;
  inventoryId: string;
  status: string;
  productId: string;
  warehouseId: string;
  grnId: string;
  uom: string;
  batchNo?: string | null;
  locationId?: string | null;
  quantity?: string;
  availableQty?: string;
  acceptedQty?: string;
  rejectedQty?: string;
  consumedQty?: string;
  vendorQrEnabled?: boolean;
  vendorInventoryId?: string | null;
  [k: string]: unknown;
}
interface Warehouse {
  id: string;
  code: string;
  name: string;
}
interface Loc {
  id: string;
  code: string;
  type: string;
  status: string;
}
interface LedgerRow {
  at?: string;
  movementType?: string;
  bucket?: string;
  quantity: string;
  uom?: string;
  referenceNo?: string | null;
  reason?: string | null;
}

const errText = (exc: unknown) => (exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));
const dash = (v: unknown) => (v ? String(v) : "—");

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value">{value}</span>
    </div>
  );
}

function Success({ children }: { children: ReactNode }) {
  return <div className="note note-info" style={{ borderColor: "var(--success)" }}>{children}</div>;
}

function Content({ itemId }: { itemId: string }) {
  const { api, apiBlob, can } = useAuth();
  const qc = useQueryClient();
  const itemPath = `/api/v1/inventory-items/${itemId}`;
  const itemQ = useApiQuery<ItemDetail>(itemPath);
  const item = itemQ.data;
  const [action, setAction] = useState("");

  // QR image: a blob URL from the authorised endpoint.
  const qr = useQuery({ queryKey: [`${itemPath}/qr`], retry: false, queryFn: async () => (await apiBlob(`${itemPath}/qr`)).blob, enabled: !!item });
  const [qrUrl, setQrUrl] = useState("");
  useEffect(() => {
    if (!qr.data) return;
    const url = URL.createObjectURL(qr.data);
    setQrUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [qr.data]);

  // Raw material has no per-piece ledger reference, so movements are scoped by product + warehouse (+ batch).
  const ledger = useApiQuery<ListResponse<LedgerRow>>(
    "/api/v1/inventory/ledger",
    { productId: item?.productId, warehouseId: item?.warehouseId, limit: 100, batchNo: item?.batchNo ?? undefined },
    { enabled: !!item },
  );
  const movements = (ledger.data?.data ?? []).map((r) => ({ ...r, qty: format.qty(r.quantity, r.uom), at: format.dateTime(r.at), bucketLabel: bucketLabel(r.bucket), movement: humanise(r.movementType) }));

  const warehouses = useApiQuery<ListResponse<Warehouse>>("/api/v1/warehouses", { status: "active", limit: 100 });
  const destWarehouses = (warehouses.data?.data ?? []).filter((w) => w.id !== item?.warehouseId);

  // ---- QC ----
  const [rejectionCode, setRejectionCode] = useState("");
  const [qcError, setQcError] = useState("");
  const decide = async (decision: "accept" | "reject") => {
    if (!item) return;
    setQcError("");
    try {
      const entry: Record<string, unknown> = { itemId: item.id, decision };
      if (decision === "reject") entry.rejectionCode = rejectionCode || "QC-FAIL";
      await api("POST", `/api/v1/grns/${item.grnId}/qc`, { json: { items: [entry], lines: [] } });
      setAction("");
      await qc.invalidateQueries({ queryKey: [itemPath] });
    } catch (exc) {
      setQcError(errText(exc));
    }
  };

  // ---- transfer ----
  const defaultQty = item?.availableQty || item?.quantity || "";
  const [trQty, setTrQty] = useState("");
  const [trDest, setTrDest] = useState("");
  const [trLoc, setTrLoc] = useState("");
  const [trReason, setTrReason] = useState("");
  const [trError, setTrError] = useState("");
  const [trOk, setTrOk] = useState("");
  const destLocations = useApiQuery<ListResponse<Loc>>(`/api/v1/warehouses/${trDest}/locations`, undefined, { enabled: !!trDest });
  const locOptions = (trDest ? (destLocations.data?.data ?? []) : []).filter((l) => l.type !== "quarantine" && l.status === "active");

  // ---- adjustment (status change) ----
  const [scFrom, setScFrom] = useState("available");
  const [scTo, setScTo] = useState("quarantine");
  const [scQty, setScQty] = useState("");
  const [scReason, setScReason] = useState("");
  const [scError, setScError] = useState("");
  const [scOk, setScOk] = useState("");

  // Quantities prefill from the item once loaded.
  useEffect(() => {
    setTrQty(defaultQty);
    setScQty(defaultQty);
  }, [defaultQty]);

  const refreshLedger = () => qc.invalidateQueries({ queryKey: ["/api/v1/inventory/ledger"] });

  const submitTransfer = async () => {
    if (!item) return;
    setTrError("");
    setTrOk("");
    if (!trDest) return setTrError("Pick a destination warehouse");
    if (!trQty) return setTrError("Enter a quantity");
    try {
      const resp = await api<{ number?: string }>("POST", "/api/v1/inventory/transfers", {
        json: {
          productId: item.productId,
          batchNo: item.batchNo || null,
          quantity: trQty,
          uom: item.uom,
          sourceWarehouseId: item.warehouseId,
          sourceLocationId: item.locationId || null,
          destWarehouseId: trDest,
          destLocationId: trLoc || null,
          reason: trReason || null,
        },
      });
      setTrOk(`Transfer ${resp.number ?? ""} created — in transit until the destination confirms receipt.`);
      await refreshLedger();
    } catch (exc) {
      setTrError(errText(exc));
    }
  };

  const submitStatus = async () => {
    if (!item) return;
    setScError("");
    setScOk("");
    if (scFrom === scTo) return setScError("Source and destination status are the same");
    if (!scQty) return setScError("Enter a quantity");
    if (scReason.trim().length < 5) return setScError("Reason must be at least 5 characters");
    try {
      await api("POST", "/api/v1/inventory/status-change", { json: { productId: item.productId, warehouseId: item.warehouseId, quantity: scQty, uom: item.uom, from: scFrom, to: scTo, reason: scReason } });
      setScOk(`Moved ${scQty} ${item.uom} from ${scFrom} to ${scTo}.`);
      await refreshLedger();
    } catch (exc) {
      setScError(errText(exc));
    }
  };

  // ---- vendor QR & ID ----
  const [vqError, setVqError] = useState("");
  const [vqBusy, setVqBusy] = useState(false);
  const [vqManual, setVqManual] = useState("");
  // Reload the item afterwards instead of using the POST response - that is the plain serializer without the enriched fields.
  const uploadVendorQr = async (file: File) => {
    setVqError("");
    if (file.size > 10 * 1024 * 1024) return setVqError("Photo is too large — 10MB max");
    setVqBusy(true);
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      await api("POST", `${itemPath}/vendor-qr`, { json: { imageBase64: b64 } });
      await qc.invalidateQueries({ queryKey: [itemPath] });
    } catch (exc) {
      setVqError(errText(exc));
    } finally {
      setVqBusy(false);
    }
  };
  const saveVendorManual = async () => {
    setVqError("");
    const text = vqManual.trim();
    if (!text) return setVqError("Enter the Vendor Inventory ID");
    try {
      await api("POST", `${itemPath}/vendor-qr`, { json: { vendorInventoryId: text } });
      setVqManual("");
      await qc.invalidateQueries({ queryKey: [itemPath] });
    } catch (exc) {
      setVqError(errText(exc));
    }
  };

  const downloadQr = async () => {
    if (!item) return;
    const { blob } = await apiBlob(`${itemPath}/qr?label=1`);
    downloadBlob(blob, `${item.inventoryId || "inventory-item"}-qr.png`);
  };

  const toggle = (a: string) => setAction(action === a ? "" : a);
  const i = item;

  if (itemQ.error instanceof ApiError && itemQ.error.status === 404) {
    return <RecordNotFound entity="Inventory Item" id={itemId} backUrl="/inventory" backLabel="← Back to inventory" />;
  }

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <Link to="/inventory" className="rx-link font-medium">← Back to inventory</Link>
      <InlineError message={itemQ.error?.message} />
      {!i ? (
        itemQ.isError ? (
          <RecordNotFound entity="Inventory Item" id={itemId} backUrl="/inventory" backLabel="← Back to inventory" />
        ) : (
          <div>
            <h1 className="text-xl font-bold mb-2">Inventory Item</h1>
            <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
          </div>
        )
      ) : (
        <>
          <PageHeader fit eyebrow="Inventory" title={i.inventoryId} titleSuffix={<Pill>{rawItemStatusLabel(i as never)}</Pill>} />
          {i.status === "under_qc" ? (
            can("grn:post") && <ActionButton onClick={() => toggle("qc")}>QC / Test</ActionButton>
          ) : (
            <div className="flex gap-2">
              {can("inventory:transfer") && <ActionButton tone="ghost" onClick={() => toggle("transfer")}>Transfer</ActionButton>}
              {can("inventory:adjust") && <ActionButton tone="ghost" onClick={() => toggle("adjustment")}>Post Adjustment</ActionButton>}
            </div>
          )}

          {action === "qc" && (
            <Panel title="QC this unit" className="w-full">
              <div className="flex flex-col gap-3 p-4">
                <InlineError message={qcError} />
                <TextInput placeholder="Rejection code (used when you reject)" value={rejectionCode} onChange={(e) => setRejectionCode(e.target.value)} />
                <div className="flex gap-2">
                  <ActionButton className="!bg-[var(--success)]" onClick={() => decide("accept")}>Accept</ActionButton>
                  <ActionButton tone="danger" onClick={() => decide("reject")}>Reject</ActionButton>
                </div>
              </div>
            </Panel>
          )}

          {action === "transfer" && (
            <Panel title="Transfer this unit" subtitle="Moves it to a different warehouse or bin — stays in transit until the destination confirms receipt." className="w-full">
              <form className="flex flex-col gap-3 p-4" onSubmit={(e) => { e.preventDefault(); void submitTransfer(); }}>
                <InlineError message={trError} />
                {trOk && <Success>{trOk}</Success>}
                <Field label="Destination warehouse">
                  <SelectInput value={trDest} onChange={(e) => { setTrDest(e.target.value); setTrLoc(""); }} placeholder="Warehouse" options={destWarehouses.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))} />
                </Field>
                <Field label="Destination bin (optional)">
                  <SelectInput value={trLoc} onChange={(e) => setTrLoc(e.target.value)} placeholder="Bin" options={locOptions.map((l) => ({ value: l.id, label: l.code }))} />
                </Field>
                <Field label={`Quantity (${i.uom})`}><TextInput value={trQty} onChange={(e) => setTrQty(e.target.value)} /></Field>
                <Field label="Reason (optional)"><TextInput value={trReason} onChange={(e) => setTrReason(e.target.value)} /></Field>
                <div><ActionButton type="submit">Start transfer</ActionButton></div>
              </form>
            </Panel>
          )}

          {action === "adjustment" && (
            <Panel title="Post adjustment" subtitle="Moves stock between buckets — e.g. flag available stock as damaged." className="w-full">
              <form className="flex flex-col gap-3 p-4" onSubmit={(e) => { e.preventDefault(); void submitStatus(); }}>
                <InlineError message={scError} />
                {scOk && <Success>{scOk}</Success>}
                <div className="flex gap-3">
                  <div className="flex-1"><Field label="From"><SelectInput value={scFrom} onChange={(e) => setScFrom(e.target.value)} options={BUCKET_OPTIONS} /></Field></div>
                  <div className="flex-1"><Field label="To"><SelectInput value={scTo} onChange={(e) => setScTo(e.target.value)} options={BUCKET_OPTIONS} /></Field></div>
                </div>
                <Field label={`Quantity (${i.uom})`}><TextInput value={scQty} onChange={(e) => setScQty(e.target.value)} /></Field>
                <Field label="Reason (min 5 characters)"><TextInput value={scReason} onChange={(e) => setScReason(e.target.value)} /></Field>
                <div><ActionButton type="submit">Post adjustment</ActionButton></div>
              </form>
            </Panel>
          )}

          <div className="flex w-full flex-col items-start gap-4 md:flex-row">
            <Panel title="QR code" className="shrink-0">
              <div className="flex flex-col items-center gap-2">
                {qrUrl ? <img src={qrUrl} alt="QR code" width={150} height={150} /> : <div style={{ width: 150, height: 150 }} />}
                <ActionButton size="sm" tone="ghost" onClick={downloadQr}>Download QR code</ActionButton>
              </div>
            </Panel>
            <Panel title="Details" className="w-full flex-1">
              <div className="inventory-item-details-grid grid grid-cols-1 gap-x-10 md:grid-cols-2">
                <DetailRow label="Inventory ID" value={i.inventoryId} />
                <DetailRow label="Product name" value={String(i.productName ?? "")} />
                <DetailRow label="Product make" value={dash(i.productMake)} />
                <DetailRow label="Product category" value={dash(i.productCategory)} />
                <DetailRow label="Product type" value={String(i.productType ?? "")} />
                <DetailRow label="PO number" value={String(i.poNumber ?? "")} />
                <DetailRow label="Vendor name" value={String(i.vendorName ?? "")} />
                <DetailRow label="GRN number" value={String(i.grnNumber ?? "")} />
                <DetailRow label="Warehouse name" value={String(i.warehouseName ?? "")} />
                <DetailRow label="Receiving date" value={format.date(i.receivedDate as string)} />
                <DetailRow label="Total Inventory" value={format.qty(i.quantity, i.uom)} />
                <DetailRow label="Available Qty" value={format.qty(i.availableQty, i.uom)} />
                <DetailRow label="Consumed Qty" value={format.qty(i.consumedQty, i.uom)} />
                <DetailRow label="Rejected Qty" value={format.qty(i.rejectedQty, i.uom)} />
                <DetailRow label="Price" value={format.money(i.unitPrice as string)} />
                <DetailRow label="GST" value={format.percent(i.taxRate as string)} />
                <DetailRow label="Total price" value={format.money(i.totalAmount as string)} />
              </div>
            </Panel>
          </div>

          {i.vendorQrEnabled && (
            <Panel title="Vendor QR & ID" subtitle={`This unit was received with "Vendor's QR and ID" enabled — attach the vendor's own identifier by scanning their QR sticker or typing it in.`} className="w-full">
              <div className="flex flex-col items-start gap-3 p-4">
                <InlineError message={vqError} />
                <DetailRow label="Vendor Inventory ID" value={i.vendorInventoryId || "Not set yet"} />
                <ScanToAddButton onPhoto={uploadVendorQr} busy={vqBusy} label="Scan vendor QR" />
                <div className="flex w-full gap-2">
                  <TextInput placeholder="Or type the Vendor Inventory ID directly" value={vqManual} onChange={(e) => setVqManual(e.target.value)} />
                  <ActionButton size="sm" tone="ghost" onClick={saveVendorManual}>Save</ActionButton>
                </div>
              </div>
            </Panel>
          )}

          <Panel title="Actions" subtitle="Receiving, transfers and adjustments recorded against this SKU/warehouse/batch." className="w-full">
            <InlineError message={ledger.error?.message} />
            {movements.length > 0 ? (
              <>
                <DesktopOnly className="w-full">
                  <DataTable columns={["When", "Movement", "Bucket", "Qty", "Reference", "Reason"]} fit>
                    {movements.map((r, n) => (
                      <tr key={n}><td>{r.at}</td><td>{r.movement}</td><td>{r.bucketLabel}</td><td>{r.qty}</td><td>{dash(r.referenceNo)}</td><td>{dash(r.reason)}</td></tr>
                    ))}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {movements.map((r, n) => (
                    <MobileRecordCard key={n}>
                      <MobileRecordRow label="When" value={r.at} />
                      <MobileRecordRow label="Movement" value={r.movement} />
                      <MobileRecordRow label="Bucket" value={r.bucketLabel} />
                      <MobileRecordRow label="Qty" value={r.qty} />
                      <MobileRecordRow label="Reference" value={dash(r.referenceNo)} />
                      <MobileRecordRow label="Reason" value={dash(r.reason)} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </>
            ) : (
              <p className="p-4 text-sm text-[var(--muted-foreground)]">No recorded movements yet.</p>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}

export default function InventoryItemPage() {
  const { can } = useAuth();
  const { itemId = "" } = useParams();
  return <Shell>{can("inventory:read") ? <Content key={itemId} itemId={itemId} /> : <Forbidden permission="inventory:read" />}</Shell>;
}
