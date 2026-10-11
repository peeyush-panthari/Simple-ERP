/** QC for one GRN - its own page, not a dialog: a GRN can carry hundreds of inventory ids. */
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { GrnStatusPill, useQrDownloads } from "@/components/erp/grn";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, TextArea, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction } from "@/lib/hooks";
import { humanise, rawItemStatusLabel } from "@/lib/status";

interface QcGrn {
  id: string;
  number: string;
  status: string;
  lines?: { id: string; sku: string; productName?: string | null; uom?: string; receivedQty: string }[];
}
interface QcItem {
  id: string;
  grnLineId: string;
  inventoryId: string;
  kind: string;
  status: string;
  productName?: string | null;
  productMake?: string | null;
  vendorName?: string | null;
  vendorQrEnabled?: boolean;
  vendorInventoryId?: string | null;
  [k: string]: unknown;
}
interface Confirm {
  itemId: string;
  lineId: string;
  decision: "accept" | "reject";
}

const dash = (v: string | null | undefined) => v || "—";

function VendorScanField({ item, onSaved }: { item: QcItem; onSaved: (id: string, text: string) => void }) {
  const { api } = useAuth();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!item.vendorQrEnabled) return <span className="text-[var(--muted-foreground)]">—</span>;

  // A hardware scanner types the decoded text into the focused input, then Enter.
  const submit = async () => {
    const text = value.trim();
    if (!text) return;
    setError("");
    setBusy(true);
    try {
      await api("POST", `/api/v1/inventory-items/${item.id}/vendor-qr`, { json: { vendorInventoryId: text } });
      setValue("");
      onSaved(item.id, text);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col items-start gap-1">
      {item.vendorInventoryId && <span className="text-xs font-bold">{item.vendorInventoryId}</span>}
      <TextInput style={{ width: "12rem" }} placeholder="Scan or type Vendor ID" value={value} disabled={busy} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void submit(); } }} />
      {error && <span className="text-xs text-[var(--destructive)]">{error}</span>}
    </div>
  );
}

function Content({ grnId }: { grnId: string }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const qr = useQrDownloads();
  const grnPath = `/api/v1/grns/${grnId}`;
  const itemsPath = `${grnPath}/items`;
  const grnQ = useApiQuery<QcGrn>(grnPath);
  const itemsQ = useApiQuery<{ data: QcItem[] }>(itemsPath);
  const { run, error: actionError } = useAsyncAction();
  const grn = grnQ.data;
  const allItems = useMemo(() => itemsQ.data?.data ?? [], [itemsQ.data]);

  const [search, setSearch] = useState("");
  const [product, setProduct] = useState("");
  const [make, setMake] = useState("");
  const [status, setStatus] = useState("");
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [reason, setReason] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [accepted, setAccepted] = useState<Record<string, string>>({});
  const [rejected, setRejected] = useState<Record<string, string>>({});

  const productOptions = [...new Set(allItems.map((i) => i.productName).filter(Boolean) as string[])].sort();
  const makeOptions = [...new Set(allItems.map((i) => i.productMake).filter(Boolean) as string[])].sort();
  const statusOptions = [...new Set(allItems.map((i) => i.status).filter(Boolean))].sort();

  const q = search.trim().toLowerCase();
  const filtered = allItems
    .filter((i) => !q || (i.inventoryId || "").toLowerCase().includes(q))
    .filter((i) => !product || i.productName === product)
    .filter((i) => !make || i.productMake === make)
    .filter((i) => !status || i.status === status)
    .map((i) => ({ ...i, statusLabel: rawItemStatusLabel(i as never) }));
  const serialLineIds = [...new Set(filtered.filter((i) => i.kind === "piece").map((i) => i.grnLineId))];
  const pieceLineIds = new Set(allItems.filter((i) => i.kind === "piece").map((i) => i.grnLineId));
  const lotLines = (grn?.lines ?? []).filter((l) => !pieceLineIds.has(l.id)).map((l) => ({ ...l, skuName: l.productName || l.sku, received: format.qty(l.receivedQty, l.uom) }));

  const refreshAfterQc = async (updated: QcGrn) => {
    qc.setQueryData([grnPath, {}], updated);
    await qc.invalidateQueries({ queryKey: [itemsPath] });
    if (updated.status === "posted") await qc.invalidateQueries({ queryKey: ["/api/v1/grns"] });
  };

  /** One request for the whole batch - "Accept all" on a serialised line can be hundreds of pieces. */
  const decide = async (itemIds: string[], decision: "accept" | "reject", why: string) => {
    const items = itemIds.map((itemId) => ({ itemId, decision, ...(decision === "reject" ? { rejectionCode: why.slice(0, 40) || "QC-FAIL" } : {}) }));
    await refreshAfterQc(await api<QcGrn>("POST", `${grnPath}/qc`, { json: { items, lines: [] } }));
  };

  const openConfirm = (c: Confirm) => {
    setConfirm(c);
    setReason("");
    setConfirmError("");
  };
  const submitConfirm = async () => {
    if (!confirm) return;
    if (confirm.decision === "reject" && !reason.trim()) return setConfirmError("A rejection reason is required");
    const ids = confirm.itemId ? [confirm.itemId] : filtered.filter((i) => i.grnLineId === confirm.lineId && i.status === "under_qc").map((i) => i.id);
    setConfirmBusy(true);
    try {
      if (ids.length) await decide(ids, confirm.decision, reason.trim());
      setConfirm(null);
    } catch (exc) {
      setConfirmError(exc instanceof ApiError ? exc.detail : String(exc));
    } finally {
      setConfirmBusy(false);
    }
  };

  const saveLot = (lineId: string) =>
    run(async () => {
      const acc = accepted[lineId] || "0";
      const rej = rejected[lineId] || "0";
      const line: Record<string, unknown> = { lineId, acceptedQty: acc, rejectedQty: rej };
      if (Number(rej || 0) > 0) line.rejectionCode = "QC-FAIL";
      await refreshAfterQc(await api<QcGrn>("POST", `${grnPath}/qc`, { json: { items: [], lines: [line] } }));
    });

  // The vendor-qr response is the plain serializer (no productName/productMake/vendorName), so patch just this field in place.
  const patchVendorId = (id: string, text: string) =>
    qc.setQueryData<{ data: QcItem[] }>([itemsPath, {}], (old) => (old ? { ...old, data: old.data.map((i) => (i.id === id ? { ...i, vendorInventoryId: text } : i)) } : old));

  const decisionButtons = (i: QcItem) =>
    i.status === "under_qc" && (
      <div className="flex gap-2">
        <ActionButton size="sm" className="!bg-[var(--success)] !text-white" onClick={() => openConfirm({ itemId: i.id, lineId: "", decision: "accept" })}>Accept</ActionButton>
        <ActionButton size="sm" tone="danger" onClick={() => openConfirm({ itemId: i.id, lineId: "", decision: "reject" })}>Reject</ActionButton>
      </div>
    );

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <Link to="/warehouse" className="rx-link">← Back to GRN &amp; QC</Link>
      <InlineError message={actionError || grnQ.error?.message || itemsQ.error?.message} />
      {!grn ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
      ) : (
        <>
          <PageHeader eyebrow="Supply chain" title={`QC — ${grn.number}`} titleSuffix={<GrnStatusPill status={grn.status} />} description="The receipt posts to inventory automatically once everything is resolved." />
          <div className="mb-2 flex w-full flex-wrap md:flex-nowrap items-center gap-2">
            <input className="search-input" style={{ width: "20rem" }} placeholder="Search by Inventory ID…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select className="filter-select" style={{ width: "12rem" }} value={product} onChange={(e) => setProduct(e.target.value)}>
              <option value="">All products</option>
              {productOptions.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select className="filter-select" style={{ width: "12rem" }} value={make} onChange={(e) => setMake(e.target.value)}>
              <option value="">All makes</option>
              {makeOptions.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <select className="filter-select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All Status</option>
              {statusOptions.map((s) => <option key={s} value={s}>{humanise(s)}</option>)}
            </select>
            <div className="flex-1" />
            <ActionButton tone="ghost" onClick={() => run(() => qr.zip(grn))}>Download all QR codes</ActionButton>
            <ActionButton tone="ghost" onClick={() => run(() => qr.pdf(grn))}>Download all QR codes in PDF</ActionButton>
          </div>
          <div className="flex w-full flex-col gap-3">
            {serialLineIds.map((lineId) => {
              const rows = filtered.filter((i) => i.grnLineId === lineId);
              return (
                <div key={lineId} className="flex w-full flex-col items-start gap-2 rounded-lg border border-[var(--border)] p-3">
                  <div className="flex flex-wrap md:flex-nowrap items-center gap-2">
                    <span className="text-sm font-bold">Serialised line</span>
                    <ActionButton size="sm" onClick={() => openConfirm({ itemId: "", lineId, decision: "accept" })}>Accept all</ActionButton>
                    <ActionButton size="sm" tone="danger" onClick={() => openConfirm({ itemId: "", lineId, decision: "reject" })}>Reject all</ActionButton>
                  </div>
                  <DesktopOnly className="w-full">
                    <DataTable columns={["Inventory ID", "SKU Name", "Make", "Vendor name", "Status", "Vendor Inventory ID", ""]} minWidth={0} fit>
                      {rows.map((i) => (
                        <tr key={i.id}>
                          <td><Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link></td>
                          <td>{dash(i.productName)}</td>
                          <td>{dash(i.productMake)}</td>
                          <td>{dash(i.vendorName)}</td>
                          <td><Pill>{i.statusLabel}</Pill></td>
                          <td><VendorScanField item={i} onSaved={patchVendorId} /></td>
                          <td>{decisionButtons(i)}</td>
                        </tr>
                      ))}
                    </DataTable>
                  </DesktopOnly>
                  <MobileOnly className="w-full">
                    {rows.map((i) => (
                      <MobileRecordCard key={i.id} actions={decisionButtons(i) || undefined}>
                        <MobileRecordRow label="Inventory ID" value={<Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link>} />
                        <MobileRecordRow label="SKU Name" value={dash(i.productName)} />
                        <MobileRecordRow label="Make" value={dash(i.productMake)} />
                        <MobileRecordRow label="Vendor" value={dash(i.vendorName)} />
                        <MobileRecordRow label="Status" value={<Pill>{i.statusLabel}</Pill>} />
                        <MobileRecordRow label="Vendor Inventory ID" value={<VendorScanField item={i} onSaved={patchVendorId} />} />
                      </MobileRecordCard>
                    ))}
                  </MobileOnly>
                </div>
              );
            })}
          </div>
          {lotLines.length > 0 && (
            <>
              <DesktopOnly className="mt-3 w-full">
                <DataTable columns={["SKU Name", "Received", "Accepted", "Rejected", ""]} minWidth={0} fit>
                  {lotLines.map((l) => (
                    <tr key={l.id}>
                      <td>{l.skuName}</td>
                      <td>{l.received}</td>
                      <td><TextInput style={{ width: "7rem" }} placeholder="Accepted" value={accepted[l.id] ?? ""} onChange={(e) => setAccepted({ ...accepted, [l.id]: e.target.value })} /></td>
                      <td><TextInput style={{ width: "7rem" }} placeholder="Rejected" value={rejected[l.id] ?? ""} onChange={(e) => setRejected({ ...rejected, [l.id]: e.target.value })} /></td>
                      <td><ActionButton size="sm" onClick={() => saveLot(l.id)}>Save</ActionButton></td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>
              <MobileOnly className="mt-3 w-full">
                {lotLines.map((l) => (
                  <MobileRecordCard key={l.id} actions={<ActionButton size="sm" className="w-full justify-center" onClick={() => saveLot(l.id)}>Save</ActionButton>}>
                    <MobileRecordRow label="SKU Name" value={l.skuName} />
                    <MobileRecordRow label="Received" value={l.received} />
                    <div className="mobile-record-row-inputs">
                      <TextInput placeholder="Accepted" value={accepted[l.id] ?? ""} onChange={(e) => setAccepted({ ...accepted, [l.id]: e.target.value })} />
                      <TextInput placeholder="Rejected" value={rejected[l.id] ?? ""} onChange={(e) => setRejected({ ...rejected, [l.id]: e.target.value })} />
                    </div>
                  </MobileRecordCard>
                ))}
              </MobileOnly>
            </>
          )}
        </>
      )}
      {confirm && (
        <Modal
          open
          onClose={() => setConfirm(null)}
          title={`${confirm.decision === "reject" ? "Reject" : "Accept"} ${confirm.lineId ? "all pieces on this line?" : "this item?"}`}
          footer={
            <>
              <ActionButton tone="ghost" onClick={() => setConfirm(null)}>Back</ActionButton>
              <ActionButton
                tone={confirm.decision === "reject" ? "danger" : "primary"}
                className={confirm.decision === "reject" ? "" : "!bg-[var(--success)]"}
                disabled={confirmBusy || (confirm.decision === "reject" && reason === "")}
                onClick={submitConfirm}
              >
                {confirm.decision === "reject" ? "Confirm reject" : "Confirm accept"}
              </ActionButton>
            </>
          }
        >
          <div className="flex flex-col gap-3">
            <InlineError message={confirmError} />
            {confirm.decision === "reject" && <TextArea placeholder="Reason for rejection (required)" value={reason} onChange={(e) => setReason(e.target.value)} />}
          </div>
        </Modal>
      )}
    </div>
  );
}

export default function WarehouseQcPage() {
  const { can } = useAuth();
  const { grnId = "" } = useParams();
  return <Shell>{can("warehouse:read") ? <Content key={grnId} grnId={grnId} /> : <Forbidden permission="warehouse:read" />}</Shell>;
}
