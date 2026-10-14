/** One production run: pack details (editable), process-stage checklist, consumed materials and the finished goods it produced. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ScanToAddButton, useHardwareScanner } from "@/components/erp/scan";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, PageHeader, Pill, RecordNotFound, SelectInput, TextArea, TextInput } from "@/components/erp/ui";
import { ItemMultiSelect, type AvailableItem } from "@/components/erp/pickers";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, type ListResponse } from "@/lib/hooks";
import { gFormat, INT_FIELDS, MAX_UPLOAD_BYTES, PACK_FIELDS, readBase64 } from "@/lib/production";
import { bucketLabel } from "@/lib/status";
import { errMsg } from "@/lib/utils";

interface Stage {
  stageKey: string;
  label: string;
  sequence: number;
  completedAt?: string | null;
  associateName?: string | null;
}
interface Consumed {
  id: string;
  sku: string;
  productName?: string | null;
  quantity: string;
  uom?: string;
  unitCost?: string;
  isAdditional?: boolean;
  removable?: boolean;
}
interface FinishedGood {
  id: string;
  inventoryId: string;
  kind: string;
  quantity: string;
  availableQty: string;
  uom?: string;
  status: string;
  batchNo?: string | null;
}
interface RunDetail {
  id: string;
  number: string;
  status: string;
  sku: string;
  productName?: string | null;
  quantity: string;
  uom?: string;
  warehouseId: string;
  productionDate?: string | null;
  notes?: string | null;
  brandingDetails?: string | null;
  testReport?: { filename: string; url: string } | null;
  stages?: Stage[];
  consumed?: Consumed[];
  finishedGoods?: FinishedGood[];
  [k: string]: unknown;
}
interface Product {
  id: string;
  sku: string;
  uom: string;
}
interface ScannedItem {
  id: string;
  inventoryId: string;
  productId: string;
  sku: string;
  uom: string;
  status: string;
  warehouseId: string;
  availableQty: string;
}

const errText = errMsg;
const dash = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : String(v));
const EDIT_TEXT_KEYS = ["packId", "shift", ...PACK_FIELDS.map(([k]) => k)];

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value">{value}</span>
    </div>
  );
}

function Content({ runId }: { runId: string }) {
  const { api, apiBlob, can } = useAuth();
  const qc = useQueryClient();
  const path = `/api/v1/inventory/production/${runId}`;
  const q = useApiQuery<RunDetail>(path);
  const run = q.data;
  const [error, setError] = useState("");
  const [associate, setAssociate] = useState("");

  const setRun = (updater: (r: RunDetail) => RunDetail) => qc.setQueryData<RunDetail>([path, {}], (old) => (old ? updater(old) : old));

  // ---- stages ----
  const stages = run?.stages ?? [];
  const nextStage = stages.find((s) => !s.completedAt);
  const completeNext = async () => {
    if (!nextStage || !associate.trim()) return;
    try {
      const resp = await api<{ stages: Stage[] }>("POST", `${path}/stages/${nextStage.stageKey}/complete`, { json: { associateName: associate.trim() } });
      setRun((r) => ({ ...r, stages: resp.stages }));
      setAssociate("");
    } catch (exc) {
      setError(errText(exc));
    }
  };

  // ---- edit ----
  const [editing, setEditing] = useState(false);
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const [report, setReport] = useState<{ filename: string; contentType: string; base64: string } | null>(null);

  const rawQ = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "raw_material", limit: 100 }, { enabled: editing });
  const consQ = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "consumable", limit: 100 }, { enabled: editing });
  const candidates = [...(rawQ.data?.data ?? []), ...(consQ.data?.data ?? [])];

  const startEdit = () => {
    if (!run) return;
    const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
    setForm({ notes: str(run.notes), productionDate: str(run.productionDate), brandingDetails: str(run.brandingDetails), ...Object.fromEntries(EDIT_TEXT_KEYS.map((k) => [k, str(run[k])])) });
    setReport(null);
    setAddProductId("");
    setAddItems([]);
    setAddItemIds([]);
    setAddQty("");
    setAddError("");
    setEditError("");
    setEditing(true);
  };

  const save = async () => {
    setEditError("");
    const ints: Record<string, number | null> = {};
    for (const k of INT_FIELDS) {
      const v = (form[k] ?? "").trim();
      if (v && !/^[+-]?\d+$/.test(v)) return setEditError("Cells quantity / series / parallel count must be whole numbers");
      ints[k] = v ? parseInt(v, 10) : null;
    }
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        notes: form.notes || null,
        productionDate: form.productionDate || null,
        brandingDetails: form.brandingDetails || null,
        testReportFilename: report?.filename || null,
        testReportContentType: report?.contentType || null,
        testReportContentBase64: report?.base64 || null,
      };
      for (const k of EDIT_TEXT_KEYS) body[k] = form[k] || null;
      Object.assign(body, ints);
      const resp = await api<RunDetail>("PATCH", path, { json: body });
      qc.setQueryData([path, {}], resp);
      await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/production"] });
      setEditing(false);
    } catch (exc) {
      setEditError(errText(exc));
    } finally {
      setSaving(false);
    }
  };

  const onReport = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) return setEditError("File is too large — 10MB max");
    setReport({ filename: file.name, contentType: file.type || "application/pdf", base64: await readBase64(file) });
    setEditError("");
  };

  // ---- additional materials on a posted run: every add/remove is its own immediate API call ----
  const [addProductId, setAddProductId] = useState("");
  const [addItems, setAddItems] = useState<AvailableItem[]>([]);
  const [addItemIds, setAddItemIds] = useState<string[]>([]);
  const [addQty, setAddQty] = useState("");
  const [addError, setAddError] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const addProduct = candidates.find((p) => p.id === addProductId);
  const isUnit = addProduct?.uom === "UNIT";

  const pickProduct = async (pid: string) => {
    setAddProductId(pid);
    setAddItemIds([]);
    setAddQty("");
    setAddItems([]);
    if (!pid || !run?.warehouseId) return;
    try {
      const resp = await api<ListResponse<AvailableItem>>("GET", "/api/v1/inventory-items", { params: { productId: pid, warehouseId: run.warehouseId, available: "true", limit: 100 } });
      setAddItems(resp.data);
    } catch (exc) {
      setAddError(errText(exc));
    }
  };
  const pickItem = (id: string) => {
    setAddItemIds(id ? [id] : []);
    const item = addItems.find((i) => i.id === id);
    if (item) setAddQty(gFormat(item.availableQty));
  };
  const toggleItem = (id: string) => {
    const ids = addItemIds.includes(id) ? addItemIds.filter((i) => i !== id) : [...addItemIds, id];
    setAddItemIds(ids);
    setAddQty(ids.length ? String(ids.length) : "");
  };
  const qtyNum = Number(addQty);
  const pickValid = (() => {
    if (!addProductId || !addQty || Number.isNaN(qtyNum) || qtyNum <= 0) return false;
    if (!addItemIds.length) return true;
    if (isUnit) return addItemIds.length === Math.trunc(qtyNum) && qtyNum === Math.trunc(qtyNum);
    const item = addItems.find((i) => i.id === addItemIds[0]);
    return !!item && qtyNum <= Number(item.availableQty) + 1e-9;
  })();

  const submitAdditional = async (productId: string, uom: string, quantity: string, items: { itemId: string; productId: string; quantity: string }[] | null) => {
    setAddError("");
    setAddBusy(true);
    try {
      const consumed = await api<Consumed[]>("POST", `${path}/additional-components`, { json: { productId, quantity, uom, items } });
      setRun((r) => ({ ...r, consumed }));
      setAddProductId("");
      setAddItems([]);
      setAddItemIds([]);
      setAddQty("");
    } catch (exc) {
      setAddError(errText(exc));
    } finally {
      setAddBusy(false);
    }
  };
  const addLine = () => {
    if (!pickValid || !addProduct) return;
    const byId = Object.fromEntries(addItems.map((i) => [i.id, i]));
    const items = addItemIds.filter((id) => byId[id]).map((id) => ({ itemId: id, productId: addProductId, quantity: isUnit ? "1" : addQty }));
    void submitAdditional(addProductId, addProduct.uom, addQty, items.length ? items : null);
  };
  const removeAdditional = async (consumptionId: string) => {
    setAddError("");
    setAddBusy(true);
    try {
      const consumed = await api<Consumed[]>("DELETE", `${path}/additional-components/${consumptionId}`);
      setRun((r) => ({ ...r, consumed }));
    } catch (exc) {
      setAddError(errText(exc));
    } finally {
      setAddBusy(false);
    }
  };

  const validateScanned = (item: ScannedItem) => {
    if (!run) return;
    if (item.warehouseId !== run.warehouseId) return setAddError(`${item.inventoryId} is stocked at a different warehouse than this run`);
    if (item.status !== "accepted") return setAddError(`${item.inventoryId} is ${item.status.replaceAll("_", " ")}, not available to consume`);
    if (Number(item.availableQty) <= 0) return setAddError(`${item.inventoryId} has nothing left available`);
    if (!candidates.some((p) => p.id === item.productId)) return setAddError(`${item.sku} isn't a raw material or consumable that can be added here`);
    const contribute = item.uom === "UNIT" ? "1" : item.availableQty;
    void submitAdditional(item.productId, item.uom, contribute, [{ itemId: item.id, productId: item.productId, quantity: contribute }]);
  };
  const [scanning, setScanning] = useState(false);
  const scanPhoto = async (file: File) => {
    setAddError("");
    if (!run?.warehouseId) return;
    if (file.size > MAX_UPLOAD_BYTES) return setAddError("Photo is too large — 10MB max");
    setScanning(true);
    try {
      validateScanned(await api<ScannedItem>("POST", "/api/v1/inventory-items/decode-qr", { json: { imageBase64: await readBase64(file) } }));
    } catch (exc) {
      setAddError(errText(exc));
    } finally {
      setScanning(false);
    }
  };
  // Passive hardware scanner - only live while the additional-materials section is editable.
  useHardwareScanner(async (text) => {
    if (!text || !editing || !run?.warehouseId) return;
    setAddError("");
    try {
      validateScanned(await api<ScannedItem>("POST", "/api/v1/inventory-items/resolve-scan", { json: { text } }));
    } catch (exc) {
      setAddError(errText(exc));
    }
  }, editing);

  const downloadReport = async () => {
    if (!run?.testReport) return;
    try {
      const { blob } = await apiBlob(run.testReport.url);
      downloadBlob(blob, run.testReport.filename);
    } catch (exc) {
      setError(errText(exc));
    }
  };

  const consumed = (run?.consumed ?? []).map((c) => ({ ...c, skuName: format.lineDisplayName(c), qty: format.qty(c.quantity, c.uom), cost: format.money(c.unitCost) }));
  const additional = consumed.filter((c) => c.isAdditional);
  const fgs = (run?.finishedGoods ?? []).map((f) => ({ ...f, qty: format.qty(f.quantity, f.uom), avail: format.qty(f.availableQty, f.uom), statusLabel: bucketLabel(f.status) }));
  const canEdit = can("inventory:produce") && run?.status !== "reversed";

  const stageControl = (s: Stage) =>
    s.completedAt ? (
      <div className="flex items-center gap-2"><Pill tone="success">Done</Pill><span className="text-sm">{s.associateName}</span></div>
    ) : nextStage?.stageKey === s.stageKey ? (
      <div className="flex items-center gap-2">
        <TextInput style={{ width: "10rem" }} placeholder="Associate name" value={associate} onChange={(e) => setAssociate(e.target.value)} />
        <ActionButton size="sm" disabled={associate === ""} onClick={completeNext}>Mark done</ActionButton>
      </div>
    ) : (
      <Pill tone="muted">Locked</Pill>
    );

  if (q.error instanceof ApiError && q.error.status === 404) {
    return <RecordNotFound entity="Production Run" id={runId} backUrl="/production" />;
  }

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <Link to="/production" className="rx-link">← Back to production</Link>
      {!run ? (
        <>
          <InlineError message={q.error?.message} />
          {q.isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>}
        </>
      ) : (
        <>
          <PageHeader eyebrow="Production" title={run.number} description={format.lineDisplayName(run)} />
          <InlineError message={error} />
          <p className="text-sm">Quantity: {format.qty(run.quantity, run.uom)}</p>

          <p className="mt-2 text-base font-bold">Pack details</p>
          {editing ? (
            <div className="flex w-full flex-col gap-3">
              <InlineError message={editError} />
              <div className="form-grid">
                <Field label="Production date"><TextInput type="date" value={form.productionDate ?? ""} onChange={(e) => set("productionDate", e.target.value)} /></Field>
                <Field label="Pack ID"><TextInput value={form.packId ?? ""} onChange={(e) => set("packId", e.target.value)} /></Field>
                <Field label="Shift"><TextInput value={form.shift ?? ""} onChange={(e) => set("shift", e.target.value)} /></Field>
                {PACK_FIELDS.map(([k, l]) => <Field key={k} label={l}><TextInput value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>)}
              </div>
              <Field label="Notes"><TextArea value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} /></Field>
              <Field label="Branding details"><TextArea value={form.brandingDetails ?? ""} onChange={(e) => set("brandingDetails", e.target.value)} /></Field>
              <div className="w-full">
                <p className="field-label">Test report</p>
                {run.testReport && <p className="text-sm text-[var(--muted-foreground)]">Current: {run.testReport.filename}</p>}
                {report ? (
                  <div className="flex items-center gap-3 text-sm"><span>Replacing with: {report.filename}</span><ActionButton size="sm" tone="danger" onClick={() => setReport(null)}>Undo</ActionButton></div>
                ) : (
                  <label className="flex cursor-pointer flex-col items-center gap-1 rx-upload text-center text-sm hover:bg-[var(--secondary)]">
                    <span>Drag &amp; drop a PDF/image here to replace it, or click to select</span>
                    <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="hidden" onChange={(e) => void onReport(e.target.files?.[0])} />
                  </label>
                )}
              </div>

              <div className="mt-4 flex w-full flex-col items-start gap-3">
                <div className="flex w-full items-center gap-3">
                  <p className="text-sm font-bold">Additional raw materials (beyond BOM)</p>
                  <ScanToAddButton onPhoto={scanPhoto} busy={scanning || addBusy} />
                </div>
                <InlineError message={addError} />
                {additional.length > 0 && (
                  <>
                    <DesktopOnly className="w-full">
                      <DataTable columns={["SKU Name", "Qty", ""]} minWidth={0} fit>
                        {additional.map((c) => (
                          <tr key={c.id}>
                            <td>{c.skuName}</td><td>{c.qty}</td>
                            <td>{c.removable && <ActionButton size="sm" tone="danger" loading={addBusy} onClick={() => removeAdditional(c.id)}>Remove</ActionButton>}</td>
                          </tr>
                        ))}
                      </DataTable>
                    </DesktopOnly>
                    <MobileOnly className="w-full">
                      {additional.map((c) => (
                        <MobileRecordCard key={c.id} actions={c.removable ? <ActionButton size="sm" tone="danger" className="w-full justify-center" loading={addBusy} onClick={() => removeAdditional(c.id)}>Remove</ActionButton> : undefined}>
                          <MobileRecordRow label="SKU Name" value={c.skuName} />
                          <MobileRecordRow label="Qty" value={c.qty} />
                        </MobileRecordCard>
                      ))}
                    </MobileOnly>
                  </>
                )}
                <div className="flex w-full flex-wrap md:flex-nowrap items-center gap-2">
                  <div className="min-w-[8rem] flex-1"><SelectInput value={addProductId} onChange={(e) => void pickProduct(e.target.value)} placeholder="Raw material" options={candidates.map((p) => ({ value: p.id, label: p.sku }))} /></div>
                  <div className="min-w-[8rem] flex-1">
                    {isUnit ? (
                      <ItemMultiSelect items={addItems} selected={addItemIds} onToggle={toggleItem} />
                    ) : (
                      <select aria-label="Select Raw Material Inventory Batch" className="ui-select" disabled={addItems.length === 0} value={addItemIds[0] ?? ""} onChange={(e) => pickItem(e.target.value)}>
                        <option value="">{!addProductId ? "Select a raw material first" : addItems.length > 0 ? "Inventory ID (optional)" : "No stock at this warehouse"}</option>
                        {addItems.map((it) => <option key={it.id} value={it.id}>{`${it.inventoryId} (${it.availableQty} avail)`}</option>)}
                      </select>
                    )}
                  </div>
                  <TextInput style={{ width: "6rem" }} placeholder="Quantity" aria-label="Quantity to consume" value={addQty} onChange={(e) => setAddQty(e.target.value)} />
                  <ActionButton size="sm" disabled={!pickValid || addBusy} onClick={addLine}>Add line</ActionButton>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="detail-grid w-full">
                <DetailRow label="Production date" value={format.date(run.productionDate)} />
                <DetailRow label="Pack ID" value={dash(run.packId)} />
                <DetailRow label="Shift" value={dash(run.shift)} />
                {PACK_FIELDS.map(([k, l]) => <DetailRow key={k} label={l} value={dash(run[k])} />)}
                <DetailRow label="Notes" value={dash(run.notes)} />
              </div>
              {run.brandingDetails && (
                <div className="mt-2"><p className="field-label">Branding details</p><p className="text-sm">{run.brandingDetails}</p></div>
              )}
              {run.testReport && (
                <div className="mt-2">
                  <p className="field-label">Test report</p>
                  <button type="button" className="text-sm rx-link" onClick={downloadReport}>{run.testReport.filename}</button>
                </div>
              )}
            </>
          )}

          <p className="mt-2 text-base font-bold">Process stages</p>
          <DesktopOnly className="w-full">
            <DataTable columns={["#", "Stage", "Associate"]} fit>
              {stages.map((s) => <tr key={s.stageKey}><td>{s.sequence}</td><td>{s.label}</td><td>{stageControl(s)}</td></tr>)}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {stages.map((s) => (
              <MobileRecordCard key={s.stageKey}>
                <MobileRecordRow label="#" value={s.sequence} />
                <MobileRecordRow label="Stage" value={s.label} />
                <MobileRecordRow label="Status" value={stageControl(s)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>

          <p className="mt-2 text-base font-bold">Raw materials consumed</p>
          <DesktopOnly className="w-full">
            <DataTable columns={["SKU Name", "Quantity", "Unit cost", ""]} fit>
              {consumed.map((c) => <tr key={c.id}><td>{c.skuName}</td><td>{c.qty}</td><td>{c.cost}</td><td>{c.isAdditional ? <Pill>Beyond BOM</Pill> : "–"}</td></tr>)}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {consumed.map((c) => (
              <MobileRecordCard key={c.id}>
                <MobileRecordRow label="SKU Name" value={c.skuName} />
                <MobileRecordRow label="Quantity" value={c.qty} />
                <MobileRecordRow label="Unit cost" value={c.cost} />
                <MobileRecordRow label="Source" value={c.isAdditional ? <Pill>Beyond BOM</Pill> : "–"} />
              </MobileRecordCard>
            ))}
          </MobileOnly>

          <p className="mt-2 text-base font-bold">Finished Goods Produced</p>
          {fgs.length > 0 ? (
            <>
              <DesktopOnly className="w-full">
                <DataTable columns={["FG-ID", "Kind", "Quantity", "Available", "Status", "Batch"]} fit>
                  {fgs.map((f) => <tr key={f.id}><td>{f.inventoryId}</td><td>{f.kind}</td><td>{f.qty}</td><td>{f.avail}</td><td><Pill>{f.statusLabel}</Pill></td><td>{dash(f.batchNo)}</td></tr>)}
                </DataTable>
              </DesktopOnly>
              <MobileOnly className="w-full">
                {fgs.map((f) => (
                  <MobileRecordCard key={f.id}>
                    <MobileRecordRow label="FG-ID" value={f.inventoryId} />
                    <MobileRecordRow label="Kind" value={f.kind} />
                    <MobileRecordRow label="Qty" value={f.qty} />
                    <MobileRecordRow label="Available" value={f.avail} />
                    <MobileRecordRow label="Status" value={<Pill>{f.statusLabel}</Pill>} />
                    <MobileRecordRow label="Batch" value={dash(f.batchNo)} />
                  </MobileRecordCard>
                ))}
              </MobileOnly>
            </>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">No finished-good units recorded against this run.</p>
          )}

          {editing ? (
            <div className="mt-4 flex w-full justify-end gap-2">
              <ActionButton tone="ghost" onClick={() => { setEditing(false); setEditError(""); }}>Cancel</ActionButton>
              <ActionButton loading={saving} onClick={save}>Save</ActionButton>
            </div>
          ) : (
            canEdit && <div className="mt-4 flex w-full justify-end"><ActionButton tone="ghost" onClick={startEdit}>Edit</ActionButton></div>
          )}
        </>
      )}
    </div>
  );
}

export default function ProductionDetailPage() {
  const { can } = useAuth();
  const { runId = "" } = useParams();
  return <Shell>{can("inventory:read") ? <Content key={runId} runId={runId} /> : <Forbidden permission="inventory:read" />}</Shell>;
}
