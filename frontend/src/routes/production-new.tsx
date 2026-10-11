/**
 * New production run / Complete production (a planned run) - one page, five sections. The BOM is
 * exploded for one finished unit and the operator picks which Inventory IDs to consume per component;
 * beyond-BOM raw materials can be added by hand, by camera photo of an inventory QR, or with a
 * hardware scanner.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ScanToAddButton, useHardwareScanner } from "@/components/erp/scan";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Note, PageHeader, Pill, SelectInput, TextArea, TextInput } from "@/components/erp/ui";
import { Chip, ItemMultiSelect, type AvailableItem } from "@/components/erp/pickers";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { useApiQuery, type ListResponse } from "@/lib/hooks";
import { autoPick, gFormat, INT_FIELDS, isCovered, MAX_UPLOAD_BYTES, PACK_FIELDS, pickedQty, readBase64, TEAM_FIELDS, type AdditionalLine, type Pick, type Requirement } from "@/lib/production";

interface Product {
  id: string;
  sku: string;
  name?: string;
  uom: string;
}
interface Named {
  id: string;
  name: string;
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
interface Run {
  id: string;
  number: string;
  status: string;
  productId: string;
  warehouseId: string;
  packId?: string | null;
  productionDate?: string | null;
}

const errText = (exc: unknown) => (exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));
const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="flex w-full flex-col items-start gap-3">
    <p className="text-base font-bold">{title}</p>
    {children}
  </div>
);
const Rule = () => <hr className="w-full border-[var(--border)]" />;

function Content({ completeRunId }: { completeRunId: string }) {
  const { api } = useAuth();
  const navigate = useNavigate();
  const completing = !!completeRunId;

  const finished = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "finished_good", limit: 100 });
  const warehousesQ = useApiQuery<ListResponse<Named>>("/api/v1/warehouses", { limit: 100 });
  const raw = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "raw_material", limit: 100 });
  const consumable = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "consumable", limit: 100 });
  const rawCandidates = [...(raw.data?.data ?? []), ...(consumable.data?.data ?? [])];
  const warehouses = warehousesQ.data?.data ?? [];

  const [error, setError] = useState("");
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [batchNo, setBatchNo] = useState("");
  const [productionDate, setProductionDate] = useState("");
  const [packId, setPackId] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const [testReport, setTestReport] = useState<{ filename: string; contentType: string; base64: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // ---- BOM ----
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [available, setAvailable] = useState<Record<string, AvailableItem[]>>({});
  const [picks, setPicks] = useState<Record<string, Pick[]>>({});
  const [bomPickItem, setBomPickItem] = useState<Record<string, string>>({});

  const loadAvailable = async (wh: string, reqs: Requirement[]) => {
    if (!wh || !reqs.length) return;
    try {
      const responses = await Promise.all(reqs.map((r) => api<ListResponse<AvailableItem>>("GET", "/api/v1/inventory-items", { params: { productId: r.productId, warehouseId: wh, available: "true", limit: 100 } })));
      setAvailable(Object.fromEntries(reqs.map((r, i) => [r.productId, responses[i].data])));
    } catch (exc) {
      setError(errText(exc));
      setAvailable({});
    }
  };

  /** Re-explodes the BOM (always for one finished unit) and re-reads stock for the warehouse. */
  const pickProduct = async (pid: string, wh = warehouseId) => {
    setProductId(pid);
    setRequirements([]);
    setPicks({});
    setBomPickItem({});
    if (!pid) return;
    try {
      const boms = await api<ListResponse<{ id: string }>>("GET", "/api/v1/boms", { params: { productId: pid, limit: 1 } });
      const bomId = boms.data[0]?.id;
      if (!bomId) return;
      const explosion = await api<{ requirements: Requirement[] }>("GET", `/api/v1/boms/${bomId}/explode`, { params: { quantity: "1" } });
      setRequirements(explosion.requirements);
      await loadAvailable(wh, explosion.requirements);
    } catch (exc) {
      setError(errText(exc));
    }
  };

  const pickWarehouse = async (wh: string) => {
    setWarehouseId(wh);
    // In-progress add-line and BOM pick dropdowns referenced the old warehouse's Inventory IDs; added lines are left alone.
    setAddProductId("");
    setAddItems([]);
    setAddItemIds([]);
    setAddQty("");
    setScanError("");
    setBomPickItem({});
    await loadAvailable(wh, requirements);
  };

  // ---- Complete Production: prefill + lock from the planned run ----
  useEffect(() => {
    if (!completeRunId) return;
    let cancelled = false;
    (async () => {
      try {
        const run = await api<Run>("GET", `/api/v1/inventory/production/${completeRunId}`);
        if (cancelled) return;
        if (run.status !== "planned") {
          setError(`${run.number} is ${run.status} and cannot be completed — only a planned run can be`);
          return;
        }
        setPackId(run.packId ?? "");
        setProductionDate(run.productionDate ?? "");
        setWarehouseId(run.warehouseId);
        await pickProduct(run.productId, run.warehouseId);
      } catch (exc) {
        if (!cancelled) setError(errText(exc));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completeRunId]);

  const updatePicks = (pid: string, fn: (current: Pick[]) => Pick[]) => setPicks((prev) => ({ ...prev, [pid]: fn(prev[pid] ?? []) }));
  const toggleBomPick = (pid: string, itemId: string) => {
    const item = (available[pid] ?? []).find((i) => i.id === itemId);
    updatePicks(pid, (current) => (current.some((p) => p.itemId === itemId) ? current.filter((p) => p.itemId !== itemId) : item ? [...current, { itemId, inventoryId: item.inventoryId, quantity: "1" }] : current));
  };
  /** Non-UNIT requirement: picking an Inventory ID commits at most what is still outstanding, capped at what it holds. */
  const setBomPick = (pid: string, itemId: string) => {
    setBomPickItem((prev) => ({ ...prev, [pid]: itemId }));
    if (!itemId) return;
    const item = (available[pid] ?? []).find((i) => i.id === itemId);
    if (!item) return;
    const req = requirements.find((r) => r.productId === pid);
    updatePicks(pid, (current) => {
      if (current.some((p) => p.itemId === itemId)) return current;
      const remaining = req ? Number(req.quantity) - pickedQty(current) : Number(item.availableQty);
      const qty = remaining > 0 ? Math.min(remaining, Number(item.availableQty)) : Number(item.availableQty);
      return [...current, { itemId, inventoryId: item.inventoryId, quantity: String(qty) }];
    });
  };

  const allCovered = requirements.length > 0 && requirements.every((r) => isCovered(r.quantity, picks[r.productId]));
  const canSubmit = !!productId && !!warehouseId && allCovered;

  // ---- additional raw materials (beyond BOM): every valid pick auto-saves as one line per product ----
  const [added, setAdded] = useState<AdditionalLine[]>([]);
  const [addProductId, setAddProductId] = useState("");
  const [addItems, setAddItems] = useState<AvailableItem[]>([]);
  const [addItemIds, setAddItemIds] = useState<string[]>([]);
  const [addQty, setAddQty] = useState("");
  const [scanError, setScanError] = useState("");
  const [scanning, setScanning] = useState(false);
  const addProduct = rawCandidates.find((p) => p.id === addProductId);
  const addIsUnit = addProduct?.uom === "UNIT";

  const upsert = (pid: string, ids: string[], qtyStr: string, itemsList: AvailableItem[]) => {
    if (!pid || !qtyStr) return;
    const qty = Number(qtyStr);
    if (Number.isNaN(qty) || qty <= 0) return;
    const product = rawCandidates.find((p) => p.id === pid);
    if (!product) return;
    const unit = product.uom === "UNIT";
    if (unit && !ids.length) return;
    const byId = Object.fromEntries(itemsList.map((i) => [i.id, i]));
    const picked = ids.filter((id) => byId[id]).map((id) => ({ itemId: id, inventoryId: byId[id].inventoryId, quantity: unit ? "1" : qtyStr }));
    const row: AdditionalLine = { productId: pid, sku: product.sku, skuName: product.name || product.sku, uom: product.uom, quantity: qtyStr, items: picked };
    setAdded((prev) => [...prev.filter((c) => c.productId !== pid), row]);
  };

  const pickAddProduct = async (pid: string) => {
    setAddProductId(pid);
    setAddItemIds([]);
    setAddQty("");
    setAddItems([]);
    if (!pid || !warehouseId) return;
    try {
      const resp = await api<ListResponse<AvailableItem>>("GET", "/api/v1/inventory-items", { params: { productId: pid, warehouseId, available: "true", limit: 100 } });
      setAddItems(resp.data);
    } catch (exc) {
      setError(errText(exc));
    }
  };
  const pickAddItem = (itemId: string) => {
    setAddItemIds(itemId ? [itemId] : []);
    const item = addItems.find((i) => i.id === itemId);
    if (!item) return;
    const q = gFormat(item.availableQty);
    setAddQty(q);
    upsert(addProductId, [itemId], q, addItems);
  };
  const toggleAddItem = (itemId: string) => {
    const ids = addItemIds.includes(itemId) ? addItemIds.filter((i) => i !== itemId) : [...addItemIds, itemId];
    setAddItemIds(ids);
    setAddQty(ids.length ? String(ids.length) : "");
    if (ids.length) upsert(addProductId, ids, String(ids.length), addItems);
    else if (addProductId) setAdded((prev) => prev.filter((c) => c.productId !== addProductId));
  };
  const changeAddQty = (v: string) => {
    setAddQty(v);
    upsert(addProductId, addItemIds, v, addItems);
  };

  /** Folds one scanned Inventory ID into `added` - same one-row-per-product shape as the manual form. */
  const validateAndMerge = (item: ScannedItem) => {
    if (added.some((c) => c.items.some((i) => i.itemId === item.id))) return setScanError(`${item.inventoryId} is already added`);
    if (item.warehouseId !== warehouseId) return setScanError(`${item.inventoryId} is stocked at a different warehouse than this run`);
    if (item.status !== "accepted") return setScanError(`${item.inventoryId} is ${item.status.replaceAll("_", " ")}, not available to consume`);
    if (Number(item.availableQty) <= 0) return setScanError(`${item.inventoryId} has nothing left available`);
    if (!rawCandidates.some((p) => p.id === item.productId)) return setScanError(`${item.sku} isn't a raw material or consumable that can be added here`);
    const contribute = item.uom === "UNIT" ? "1" : item.availableQty;
    const entry = { itemId: item.id, inventoryId: item.inventoryId, quantity: contribute };
    setAdded((prev) => {
      const at = prev.findIndex((c) => c.productId === item.productId);
      if (at === -1) {
        const product = rawCandidates.find((p) => p.id === item.productId);
        return [...prev, { productId: item.productId, sku: item.sku, skuName: product?.name || item.sku, uom: item.uom, quantity: contribute, items: [entry] }];
      }
      const existing = prev[at];
      const merged = { ...existing, quantity: String(Number(existing.quantity) + Number(contribute)), items: [...existing.items, entry] };
      return [...prev.slice(0, at), merged, ...prev.slice(at + 1)];
    });
  };

  const scanPhoto = async (file: File) => {
    setScanError("");
    if (!warehouseId) return setScanError("Select a warehouse first");
    if (file.size > MAX_UPLOAD_BYTES) return setScanError("Photo is too large — 10MB max");
    setScanning(true);
    try {
      const item = await api<ScannedItem>("POST", "/api/v1/inventory-items/decode-qr", { json: { imageBase64: await readBase64(file) } });
      validateAndMerge(item);
    } catch (exc) {
      setScanError(errText(exc));
    } finally {
      setScanning(false);
    }
  };
  // Passive hardware (HID) scanner: no-ops until a warehouse is picked, so it can stay mounted for the whole page.
  useHardwareScanner(async (text) => {
    if (!text || !warehouseId) return;
    setScanError("");
    try {
      validateAndMerge(await api<ScannedItem>("POST", "/api/v1/inventory-items/resolve-scan", { json: { text } }));
    } catch (exc) {
      setScanError(errText(exc));
    }
  });

  const onTestReport = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) return setError("File is too large — 10MB max");
    setTestReport({ filename: file.name, contentType: file.type || "application/pdf", base64: await readBase64(file) });
    setError("");
  };

  const submit = async () => {
    setError("");
    const ints: Record<string, number | null> = {};
    for (const k of INT_FIELDS) {
      const v = (form[k] ?? "").trim();
      if (v && !/^[+-]?\d+$/.test(v)) return setError("Cells quantity, No's of series and No's of parallel must be whole numbers");
      ints[k] = v ? parseInt(v, 10) : null;
    }
    const body: Record<string, unknown> = {
      batchNo: batchNo || null,
      consumedItems: Object.entries(picks).flatMap(([pid, list]) => list.map((p) => ({ itemId: p.itemId, productId: pid, quantity: p.quantity }))),
      additionalComponents: added.length
        ? added.map((c) => ({ productId: c.productId, quantity: c.quantity, uom: c.uom, items: c.items.length ? c.items.map((i) => ({ itemId: i.itemId, productId: c.productId, quantity: i.quantity })) : null }))
        : null,
      productionDate: productionDate || null,
      shift: form.shift || null,
      bmsMakeModel: form.bmsMakeModel || null,
      screenType: form.screenType || null,
      bmsId: form.bmsId || null,
      bluetoothId: form.bluetoothId || null,
      iotId: form.iotId || null,
      cellsName: form.cellsName || null,
      cellsQuantity: ints.cellsQuantity,
      seriesCount: ints.seriesCount,
      parallelCount: ints.parallelCount,
      enclosureName: form.enclosureName || null,
      chargeCapacity: form.chargeCapacity || null,
      dischargeCapacity: form.dischargeCapacity || null,
      brandingDetails: form.brandingDetails || null,
      testReportFilename: testReport?.filename || null,
      testReportContentType: testReport?.contentType || null,
      testReportContentBase64: testReport?.base64 || null,
    };
    for (const [k] of TEAM_FIELDS) body[k] = (form[k] ?? "").trim() || null;
    setSubmitting(true);
    try {
      if (completeRunId) {
        // productId/warehouseId/packId/quantity/uom are locked from planning; the backend reads them off the planned run.
        await api("POST", `/api/v1/inventory/production/${completeRunId}/complete`, { json: body });
        navigate(`/production/${completeRunId}`);
        return;
      }
      body.productId = productId;
      body.warehouseId = warehouseId;
      body.quantity = "1"; // a production run always builds exactly one finished unit (a pack)
      body.uom = "UNIT";
      body.packId = packId || null;
      await api("POST", "/api/v1/inventory/production", { json: body });
      navigate("/production");
    } catch (exc) {
      setError(errText(exc));
    } finally {
      setSubmitting(false);
    }
  };

  const productSku = finished.data?.data.find((p) => p.id === productId)?.sku ?? "";
  const warehouseName = warehouses.find((w) => w.id === warehouseId)?.name ?? "";
  const text = (k: string, label: string) => (
    <Field key={k} label={label}><TextInput value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>
  );

  return (
    <div className="flex w-full max-w-[64rem] flex-col items-start gap-4">
      <Link to="/production" className="rx-link">← Back to Production</Link>
      <PageHeader eyebrow="Supply chain" title={completing ? "Complete production" : "New production run"} />
      <InlineError message={error} />

      <Section title="Basic details">
        {completing && <Note>Finished good, warehouse and pack ID were set in Daily Production Planning and can&apos;t be changed here.</Note>}
        <div className="form-grid">
          <Field label="Finished good">
            {completing ? <TextInput value={productSku} disabled readOnly /> : <SelectInput value={productId} onChange={(e) => void pickProduct(e.target.value)} placeholder="Select finished good" options={(finished.data?.data ?? []).map((p) => ({ value: p.id, label: p.sku }))} />}
          </Field>
          <Field label="Warehouse">
            {completing ? <TextInput value={warehouseName} disabled readOnly /> : <SelectInput value={warehouseId} onChange={(e) => void pickWarehouse(e.target.value)} placeholder="Select warehouse" options={warehouses.map((w) => ({ value: w.id, label: w.name }))} />}
          </Field>
          <Field label="Batch (optional)"><TextInput value={batchNo} onChange={(e) => setBatchNo(e.target.value)} /></Field>
          <Field label="Production date"><TextInput type="date" value={productionDate} onChange={(e) => setProductionDate(e.target.value)} /></Field>
          <Field label="Pack ID"><TextInput value={packId} onChange={(e) => setPackId(e.target.value)} disabled={completing} /></Field>
        </div>
      </Section>
      <Rule />

      <Section title="Pack details">
        <div className="form-grid">{PACK_FIELDS.map(([k, l]) => text(k, l))}</div>
      </Section>
      <Rule />

      <Section title="Raw material details">
        {requirements.length > 0 && (
          <div className="flex w-full flex-col gap-2">
            <p className="text-sm font-bold">Bill of Material</p>
            {requirements.map((r) => {
              const pid = r.productId;
              const items = available[pid] ?? [];
              const list = picks[pid] ?? [];
              const covered = isCovered(r.quantity, list);
              return (
                <div key={pid} className="mb-2 flex w-full flex-col items-start gap-2 rounded-lg border border-[var(--border)] p-3">
                  <div className="flex w-full flex-wrap md:flex-nowrap items-center gap-2">
                    <span className="shrink-0 text-sm font-bold">{r.sku}: need {format.qty(r.quantity, r.uom)}</span>
                    {covered ? <Pill tone="success">Covered</Pill> : <Pill tone="destructive">Short</Pill>}
                    <ActionButton size="sm" tone="ghost" className="shrink-0" onClick={() => updatePicks(pid, (current) => autoPick(r.quantity, current, items))}>Auto-pick</ActionButton>
                    <div className="min-w-[8rem] flex-1">
                      {r.uom === "UNIT" ? (
                        <ItemMultiSelect items={items} selected={list.map((p) => p.itemId)} onToggle={(id) => toggleBomPick(pid, id)} />
                      ) : (
                        <select className="ui-select" disabled={items.length === 0} value={bomPickItem[pid] ?? ""} onChange={(e) => setBomPick(pid, e.target.value)}>
                          <option value="">{!warehouseId ? "Select a warehouse first" : items.length > 0 ? "Inventory ID" : "No stock at this warehouse"}</option>
                          {items.map((it) => <option key={it.id} value={it.id}>{`${it.inventoryId} (${it.availableQty} avail)`}</option>)}
                        </select>
                      )}
                    </div>
                  </div>
                  {list.length > 0 && (
                    <div className="chip-row">
                      {list.map((p) => (
                        <Chip key={p.itemId} label={format.qty(p.quantity) === "1" ? p.inventoryId : `${p.inventoryId} (${format.qty(p.quantity)})`} onRemove={() => updatePicks(pid, (current) => current.filter((x) => x.itemId !== p.itemId))} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <div className="flex w-full flex-col items-start gap-3">
          <div className="flex w-full items-center gap-3">
            <p className="text-sm font-bold">Additional raw materials (beyond BOM)</p>
            <ScanToAddButton onPhoto={scanPhoto} busy={scanning} />
          </div>
          <InlineError message={scanError} />
          {added.length > 0 && (
            <>
              <DesktopOnly className="w-full">
                <DataTable columns={["SKU Name", "Qty", "Inventory ID(s)", ""]} minWidth={0} fit>
                  {added.map((c, i) => (
                    <tr key={c.productId}>
                      <td>{c.skuName}</td><td>{format.qty(c.quantity, c.uom)}</td><td>{c.items.length ? c.items.map((x) => x.inventoryId).join(", ") : "Auto (FIFO)"}</td>
                      <td><ActionButton size="sm" tone="danger" onClick={() => setAdded(added.filter((_, j) => j !== i))}>Remove</ActionButton></td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>
              <MobileOnly className="w-full">
                {added.map((c, i) => (
                  <MobileRecordCard key={c.productId} actions={<ActionButton size="sm" tone="danger" className="w-full justify-center" onClick={() => setAdded(added.filter((_, j) => j !== i))}>Remove</ActionButton>}>
                    <MobileRecordRow label="SKU Name" value={c.skuName} />
                    <MobileRecordRow label="Qty" value={format.qty(c.quantity, c.uom)} />
                    <MobileRecordRow label="Inventory ID(s)" value={c.items.length ? c.items.map((x) => x.inventoryId).join(", ") : "Auto (FIFO)"} />
                  </MobileRecordCard>
                ))}
              </MobileOnly>
            </>
          )}
          <div className="flex w-full flex-wrap md:flex-nowrap items-center gap-2">
            <div className="min-w-[8rem] flex-1">
              <SelectInput value={addProductId} onChange={(e) => void pickAddProduct(e.target.value)} placeholder="Raw material" options={rawCandidates.map((p) => ({ value: p.id, label: p.sku }))} />
            </div>
            <div className="min-w-[8rem] flex-1">
              {addIsUnit ? (
                <ItemMultiSelect items={addItems} selected={addItemIds} onToggle={toggleAddItem} />
              ) : (
                <select className="ui-select" disabled={addItems.length === 0} value={addItemIds[0] ?? ""} onChange={(e) => pickAddItem(e.target.value)}>
                  <option value="">{!addProductId ? "Select a raw material first" : addItems.length > 0 ? "Inventory ID (optional)" : "No stock at this warehouse"}</option>
                  {addItems.map((it) => <option key={it.id} value={it.id}>{`${it.inventoryId} (${it.availableQty} avail)`}</option>)}
                </select>
              )}
            </div>
            <TextInput style={{ width: "6rem" }} placeholder="Quantity" value={addQty} onChange={(e) => changeAddQty(e.target.value)} />
            {/* The current pick is already auto-saved; this just clears the picker to start on a different material. */}
            <ActionButton size="sm" tone="ghost" onClick={() => { setAddProductId(""); setAddItems([]); setAddItemIds([]); setAddQty(""); }}>Add line</ActionButton>
          </div>
        </div>
      </Section>
      <Rule />

      <Section title="Production team">
        <div className="form-grid">
          {text("shift", "Shift")}
          {TEAM_FIELDS.map(([k, l]) => text(k, l))}
        </div>
      </Section>
      <Rule />

      <Section title="Others">
        <Field label="Branding details"><TextArea value={form.brandingDetails ?? ""} onChange={(e) => set("brandingDetails", e.target.value)} /></Field>
        <div className="mt-2 w-full">
          <p className="field-label">Test report</p>
          {testReport ? (
            <div className="flex items-center gap-3 text-sm">
              <span>{testReport.filename}</span>
              <ActionButton size="sm" tone="danger" onClick={() => setTestReport(null)}>Remove</ActionButton>
            </div>
          ) : (
            <label className="flex cursor-pointer flex-col items-center gap-1 rx-upload text-center text-sm hover:bg-[var(--secondary)]">
              <span>Drag &amp; drop a PDF/image here, or click to select</span>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="hidden" onChange={(e) => void onTestReport(e.target.files?.[0])} />
            </label>
          )}
        </div>
      </Section>

      <div className="mt-4 flex w-full justify-end gap-2">
        <Link to="/production" className="action-btn action-btn-primary">Cancel</Link>
        <ActionButton disabled={!canSubmit || submitting} onClick={submit}>{completing ? "Complete production" : "Post production"}</ActionButton>
      </div>
    </div>
  );
}

export default function ProductionNewPage() {
  const { can } = useAuth();
  const { runId = "" } = useParams();
  return <Shell>{can("inventory:produce") ? <Content key={runId} completeRunId={runId} /> : <Forbidden permission="inventory:produce" />}</Shell>;
}
