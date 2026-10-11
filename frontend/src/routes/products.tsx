/** Products & BOM: catalogue with create/edit/bulk upload, and bills of material with versions, builder and bulk upload. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import {
  ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Pagination, Pill, SearchInput, SelectInput, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { PRODUCT_TYPES, UOM_OPTIONS, uomLabel } from "@/lib/reference";

interface Category {
  id: string;
  productCategory: string;
  productTypes?: string[] | null;
}
interface Product {
  id: string;
  sku: string;
  name: string;
  make?: string | null;
  modelNumber?: string | null;
  categoryId?: string | null;
  categoryName?: string | null;
  type: string;
  uom: string;
  status: string;
}
interface BomSummary {
  id: string;
  productSku: string;
  productName?: string | null;
  productCategory?: string | null;
  versionCount: number;
  activeVersion?: number | null;
  latestState: string;
}
interface BomComponent {
  sku?: string;
  productName?: string | null;
  quantity: string;
  uom: string;
}
interface BomVersion {
  id: string;
  version: number;
  state: string;
  effectiveFrom: string;
  effectiveTo?: string | null;
  yieldPercent: string;
  costRollup?: string | null;
  components?: BomComponent[];
}
interface BomDetail {
  id: string;
  productId: string;
  productSku: string;
  currency?: string | null;
  versions?: BomVersion[];
}
interface BuilderComponent {
  componentProductId: string;
  skuName: string;
  quantity: string;
  uom: string;
}

// Mirrors the backend's BULK_UPLOAD_ALL_COLUMNS in the products / boms routes.
const PRODUCT_BULK_COLUMNS = [
  "sku", "name", "make", "modelNumber", "description", "type", "categoryCode", "uom", "hsnCode",
  "batchTracked", "expiryTracked", "storageConditions", "reorderPoint", "reorderQty",
  "leadTimeDays", "currency", "purchasable", "sellable", "weightKg", "volumeM3",
];
const PRODUCT_BULK_SAMPLE =
  `${PRODUCT_BULK_COLUMNS.join(",")}\n` +
  ",Steel Rod 10mm,Acme Steel,,,raw_material,CAT-001,KG,,false,false,,100,500,14,INR,true,false,,\n" +
  ",Battery Module X1,Acme Battery,BM-X1,,finished_good,CAT-002,UNIT,,true,true,Store below 30C,10,50,30,INR,false,true,2.5,0.01\n";

const BOM_BULK_COLUMNS = [
  "productSku", "yieldPercent", "effectiveFrom", "effectiveTo", "notes", "routingNotes",
  "componentSku", "quantity", "uom", "scrapPercent", "isAlternate", "alternateForLine", "componentNotes",
];
const BOM_BULK_SAMPLE =
  `${BOM_BULK_COLUMNS.join(",")}\n` +
  "FG-0001,100,2026-09-20,,,,RM-0001,2,KG,5,,,\n" +
  "FG-0001,100,2026-09-20,,,,RM-0002,1,UNIT,0,,,\n";

const dash = (v: string | null | undefined) => v || "–";
const effective = (v: BomVersion) => `${v.effectiveFrom} → ${v.effectiveTo || "open"}`;

// ---- create / edit product ----------------------------------------------------------

function CreateProductDialog({ categories, onClose, onCreated }: { categories: Category[]; onClose: () => void; onCreated: () => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [type, setType] = useState("raw_material");
  const [categoryId, setCategoryId] = useState("");
  const typeCategories = categories.filter((c) => !c.productTypes?.length || c.productTypes.includes(type));

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    if (!categoryId) return setError("Category is required");
    if (!get("sku")) return setError("SKU ID is required");
    const ok = await run(async () => {
      await api("POST", "/api/v1/products", {
        json: {
          sku: get("sku"),
          name: get("name"),
          make: get("make"),
          modelNumber: get("modelNumber") || null,
          type,
          categoryId,
          uom: get("uom") || "UNIT",
          batchTracked: f.get("batchTracked") !== null,
          expiryTracked: f.get("expiryTracked") !== null,
          sellable: type === "finished_good",
        },
      });
      return true;
    });
    if (ok) {
      onClose();
      onCreated();
    }
  };

  return (
    <Modal open onClose={onClose} title="New product">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="sku" placeholder="SKU ID" required />
        <TextInput name="name" placeholder="SKU Name" required />
        <TextInput name="make" placeholder="Make" required />
        <TextInput name="modelNumber" placeholder="Model number (optional)" />
        <SelectInput
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setCategoryId("");
          }}
          placeholder="Product type"
          options={PRODUCT_TYPES.map((t) => ({ value: t, label: t }))}
        />
        <SelectInput value={categoryId} onChange={(e) => setCategoryId(e.target.value)} placeholder="Category" options={typeCategories.map((c) => ({ value: c.id, label: c.productCategory }))} />
        <SelectInput name="uom" defaultValue="UNIT" required options={UOM_OPTIONS} />
        <label className="check-row">
          <input type="checkbox" name="batchTracked" />
          <span>Batch tracked</span>
        </label>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Create product</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function EditProductDialog({ product, onClose, onSaved }: { product: Product; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const ok = await run(async () => {
      await api("PATCH", `/api/v1/products/${product.id}`, { json: { name: String(f.get("name") ?? ""), make: String(f.get("make") ?? ""), categoryId: null } });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };

  return (
    <Modal open onClose={onClose} title="Edit product">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <p className="text-xs text-[var(--muted-foreground)]">SKU ID (immutable): {product.sku}</p>
        <p className="text-xs text-[var(--muted-foreground)]">UOM (fixed after creation): {uomLabel(product.uom)}</p>
        <TextInput name="name" placeholder="SKU Name" defaultValue={product.name} required />
        <TextInput name="make" placeholder="Make" defaultValue={product.make ?? ""} required />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Save</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

// ---- products tab ---------------------------------------------------------------------

function ProductsTab() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("product:write");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  const categories = useApiQuery<ListResponse<Category>>("/api/v1/product-categories", { limit: 100 });
  const list = useApiQuery<ListResponse<Product>>("/api/v1/products", { page, limit: 15, q: debounced, type, status });
  const products = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/products"] });
  const edit = (p: Product, cls?: string) => canWrite && <ActionButton size="sm" className={cls} onClick={() => setEditing(p)}>Edit</ActionButton>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input
          className="search-input"
          style={{ width: "20rem" }}
          placeholder="Search SKU ID or SKU Name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <select className="filter-select" style={{ width: "11rem" }} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All Types</option>
          {PRODUCT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="filter-select" style={{ width: "11rem" }} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {["draft", "active", "deprecated"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && <ActionButton onClick={() => setCreateOpen(true)}>New product</ActionButton>}
      </div>
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["SKU ID", "SKU Name", "Make", "Model Number", "Product Category", "Product Type", "UOM", "Status", ""]} fit>
          {products.map((p) => (
            <tr key={p.id}>
              <td>{p.sku}</td>
              <td>{p.name}</td>
              <td>{p.make}</td>
              <td>{dash(p.modelNumber)}</td>
              <td>{dash(p.categoryName)}</td>
              <td><Pill>{p.type}</Pill></td>
              <td>{uomLabel(p.uom)}</td>
              <td><Pill>{p.status}</Pill></td>
              <td>{edit(p)}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {products.map((p) => (
          <MobileRecordCard key={p.id} actions={edit(p, "w-full justify-center")}>
            <MobileRecordRow label="SKU ID" value={p.sku} />
            <MobileRecordRow label="SKU Name" value={p.name} />
            <MobileRecordRow label="Make" value={p.make} />
            <MobileRecordRow label="Model Number" value={dash(p.modelNumber)} />
            <MobileRecordRow label="Product Category" value={dash(p.categoryName)} />
            <MobileRecordRow label="Product Type" value={<Pill>{p.type}</Pill>} />
            <MobileRecordRow label="UOM" value={uomLabel(p.uom)} />
            <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full">
        <Pagination meta={list.data?.meta} onPage={setPage} />
      </div>
      {createOpen && <CreateProductDialog categories={categories.data?.data ?? []} onClose={() => setCreateOpen(false)} onCreated={refresh} />}
      {editing && <EditProductDialog product={editing} onClose={() => setEditing(null)} onSaved={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload products"
        description="Upload a CSV with one row per product. categoryCode must match an existing category code (see Categories)."
        endpoint="/api/v1/products/bulk-upload"
        sampleCsv={PRODUCT_BULK_SAMPLE}
        sampleFilename="product_bulk_upload_template.csv"
        errorFilename="product_bulk_upload_errors.csv"
        columns={PRODUCT_BULK_COLUMNS}
        labelHeader="SKU Name"
        labelKey="name"
        successKey="sku"
        noun="products"
        onCompleted={refresh}
      />
    </div>
  );
}

// ---- BOM builder ------------------------------------------------------------------------

/**
 * `productId` set = adding a version to that (open) BOM; empty = a brand-new BOM,
 * so the finished-good picker is shown first.
 */
function BomBuilderDialog({ existingBom, onClose, onSaved }: { existingBom: BomDetail | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [productId, setProductId] = useState(existingBom?.productId ?? "");
  const [fgSearch, setFgSearch] = useState("");
  const [components, setComponents] = useState<BuilderComponent[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [quantity, setQuantity] = useState("");

  // The picker lists come straight from the catalogue rather than whatever page of the products table is open.
  const finished = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "finished_good", limit: 100 });
  const raw = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "raw_material", limit: 100 });
  const consumable = useApiQuery<ListResponse<Product>>("/api/v1/products", { type: "consumable", limit: 100 });
  const candidates = [...(raw.data?.data ?? []), ...(consumable.data?.data ?? [])];
  const q = fgSearch.trim().toLowerCase();
  const fgOptions = (finished.data?.data ?? []).filter((p) => !q || p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q));

  const addLine = () => {
    const product = candidates.find((p) => p.id === candidateId);
    if (!product || !quantity) return;
    setComponents([...components, { componentProductId: product.id, skuName: product.name || product.sku, quantity, uom: product.uom }]);
    setCandidateId("");
    setQuantity("");
  };

  const save = async () => {
    setError("");
    if (!components.length) return setError("Add at least one component");
    const body: Record<string, unknown> = {
      yieldPercent: "100",
      effectiveFrom: format.todayIso(),
      notes: null,
      components: components.map((c) => ({ componentProductId: c.componentProductId, quantity: c.quantity, uom: c.uom, scrapPercent: "0", isAlternate: false })),
    };
    const ok = await run(async () => {
      if (existingBom) {
        await api("POST", `/api/v1/boms/${existingBom.id}/versions`, { json: body });
      } else {
        body.productId = productId;
        await api("POST", "/api/v1/boms", { json: body });
      }
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };

  return (
    <Modal open onClose={onClose} title={existingBom ? "New BOM version" : "New BOM"}>
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        {!productId && (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-bold">Product Name</p>
            <p className="text-xs text-[var(--muted-foreground)]">Search and pick which finished good this BOM belongs to:</p>
            <SearchInput value={fgSearch} onChange={setFgSearch} placeholder="Search finished goods…" />
            <div className="flex max-h-56 flex-col overflow-y-auto">
              {fgOptions.map((p) => (
                <div key={p.id} className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-2 py-1.5">
                  <span className="text-sm">{p.sku} — {p.name}</span>
                  <ActionButton size="sm" tone="ghost" onClick={() => setProductId(p.id)}>Select</ActionButton>
                </div>
              ))}
            </div>
          </div>
        )}
        <p className="mt-2 text-sm font-bold">Components</p>
        <DataTable columns={["SKU Name", "Quantity", ""]} minWidth={0} fit>
          {components.map((c, i) => (
            <tr key={i}>
              <td>{c.skuName}</td>
              <td>{format.qty(c.quantity, c.uom)}</td>
              <td><ActionButton size="sm" tone="danger" onClick={() => setComponents(components.filter((_, j) => j !== i))}>Remove</ActionButton></td>
            </tr>
          ))}
        </DataTable>
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2">
          <SelectInput style={{ width: "auto", minWidth: "12rem" }} value={candidateId} onChange={(e) => setCandidateId(e.target.value)} placeholder="SKU Name" options={candidates.map((p) => ({ value: p.id, label: p.name }))} />
          <TextInput style={{ width: "8rem" }} placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLine(); } }} />
          <ActionButton size="sm" onClick={addLine}>Add line</ActionButton>
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton onClick={save} loading={busy}>Save BOM version</ActionButton>
        </div>
      </div>
    </Modal>
  );
}

// ---- BOM dialogs ---------------------------------------------------------------------------

function VersionDetailDialog({ version, onClose }: { version: BomVersion; onClose: () => void }) {
  const components = (version.components ?? []).map((c) => ({ ...c, skuName: c.productName || c.sku, qty: format.qty(c.quantity) }));
  return (
    <Modal open onClose={onClose} title={`Version ${version.version}`} footer={<ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--muted-foreground)]">
          <Pill>{version.state}</Pill>
          <span>{effective(version)}</span>
          <span>Yield {format.percent(version.yieldPercent)}</span>
        </div>
        <DesktopOnly className="w-full">
          <DataTable columns={["SKU Name", "Quantity", "UOM"]} minWidth={0} fit>
            {components.map((c, i) => (
              <tr key={i}>
                <td>{c.skuName}</td>
                <td>{c.qty}</td>
                <td>{uomLabel(c.uom)}</td>
              </tr>
            ))}
          </DataTable>
        </DesktopOnly>
        <MobileOnly className="w-full">
          {components.map((c, i) => (
            <MobileRecordCard key={i}>
              <MobileRecordRow label="SKU Name" value={c.skuName} />
              <MobileRecordRow label="Quantity" value={c.qty} />
              <MobileRecordRow label="UOM" value={uomLabel(c.uom)} />
            </MobileRecordCard>
          ))}
        </MobileOnly>
      </div>
    </Modal>
  );
}

function BomDialog({ bomId, onClose, onChanged }: { bomId: string; onClose: () => void; onChanged: () => void }) {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const { run, error } = useAsyncAction();
  const [viewId, setViewId] = useState("");
  const [builderOpen, setBuilderOpen] = useState(false);
  const path = `/api/v1/boms/${bomId}`;
  const detail = useApiQuery<BomDetail>(path);
  const bom = detail.data;
  const currency = bom?.currency || "INR";
  const versions = bom?.versions ?? [];
  const viewing = versions.find((v) => v.id === viewId);
  const reload = () => qc.invalidateQueries({ queryKey: [path] });

  const act = (versionId: string, verb: "submit" | "approve" | "reject", body?: unknown, refreshList = false) =>
    run(async () => {
      await api("POST", `${path}/versions/${versionId}/${verb}`, body === undefined ? {} : { json: body });
      await reload();
      if (refreshList) onChanged();
    });

  const actions = (v: BomVersion) => (
    <>
      <ActionButton size="sm" onClick={() => setViewId(v.id)}>View</ActionButton>
      {v.state === "draft" && can("bom:write") && <ActionButton size="sm" onClick={() => act(v.id, "submit")}>Submit</ActionButton>}
      {v.state === "pending_approval" && can("bom:approve") && (
        <>
          <ActionButton size="sm" onClick={() => act(v.id, "approve", {}, true)}>Approve</ActionButton>
          <ActionButton size="sm" tone="danger" onClick={() => act(v.id, "reject", { reason: "Rejected from the BOM dialog" })}>Reject</ActionButton>
        </>
      )}
    </>
  );

  return (
    <>
      <Modal
        open
        onClose={onClose}
        title={bom?.productSku ?? "BOM"}
        wide
        footer={
          <>
            <ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>
            {can("bom:write") && bom && <ActionButton onClick={() => setBuilderOpen(true)}>New version</ActionButton>}
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <InlineError message={error || detail.error?.message} />
          <DesktopOnly className="w-full">
            <DataTable columns={["Version", "State", "Effective", "Yield", "Cost", ""]} minWidth={0} fit>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td><Pill>{v.state}</Pill></td>
                  <td>{effective(v)}</td>
                  <td>{format.percent(v.yieldPercent)}</td>
                  <td>{format.money(v.costRollup, currency)}</td>
                  <td><div className="flex gap-2">{actions(v)}</div></td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {versions.map((v) => (
              <MobileRecordCard key={v.id} actions={<div className="flex flex-wrap gap-2">{actions(v)}</div>}>
                <MobileRecordRow label="Version" value={`v${v.version}`} />
                <MobileRecordRow label="State" value={<Pill>{v.state}</Pill>} />
                <MobileRecordRow label="Effective" value={effective(v)} />
                <MobileRecordRow label="Yield" value={format.percent(v.yieldPercent)} />
                <MobileRecordRow label="Cost" value={format.money(v.costRollup, currency)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </div>
      </Modal>
      {viewing && <VersionDetailDialog version={viewing} onClose={() => setViewId("")} />}
      {builderOpen && bom && (
        <BomBuilderDialog
          existingBom={bom}
          onClose={() => setBuilderOpen(false)}
          onSaved={() => {
            void reload();
            onChanged();
          }}
        />
      )}
    </>
  );
}

// ---- BOM tab -----------------------------------------------------------------------------------

function BomTab() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("bom:write");
  const [openId, setOpenId] = useState("");
  const [builderOpen, setBuilderOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const list = useApiQuery<ListResponse<BomSummary>>("/api/v1/boms", { limit: 100 });
  const boms = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/boms"] });
  const active = (b: BomSummary) => (b.activeVersion ? <Pill tone="success">{`v${b.activeVersion}`}</Pill> : <span>–</span>);

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center gap-3">
        <h2 className="rx-heading-6">Bills of material</h2>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && <ActionButton onClick={() => setBuilderOpen(true)}>New BOM</ActionButton>}
      </div>
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["SKU ID", "SKU Name", "Product Category", "Versions", "Active", "Latest state", ""]} fit>
          {boms.map((b) => (
            <tr key={b.id}>
              <td>{b.productSku}</td>
              <td>{dash(b.productName)}</td>
              <td>{dash(b.productCategory)}</td>
              <td>{b.versionCount}</td>
              <td>{active(b)}</td>
              <td><Pill>{b.latestState}</Pill></td>
              <td><ActionButton size="sm" onClick={() => setOpenId(b.id)}>Open</ActionButton></td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {boms.map((b) => (
          <MobileRecordCard key={b.id} actions={<ActionButton size="sm" className="w-full justify-center" onClick={() => setOpenId(b.id)}>Open</ActionButton>}>
            <MobileRecordRow label="SKU ID" value={b.productSku} />
            <MobileRecordRow label="SKU Name" value={dash(b.productName)} />
            <MobileRecordRow label="Product Category" value={dash(b.productCategory)} />
            <MobileRecordRow label="Versions" value={b.versionCount} />
            <MobileRecordRow label="Active" value={active(b)} />
            <MobileRecordRow label="Latest state" value={<Pill>{b.latestState}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {openId && <BomDialog bomId={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
      {builderOpen && <BomBuilderDialog existingBom={null} onClose={() => setBuilderOpen(false)} onSaved={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload BOMs"
        description="Upload a CSV with one row per component. Rows sharing the same Product SKU are grouped into a single BOM (a product can only have one)."
        endpoint="/api/v1/boms/bulk-upload"
        sampleCsv={BOM_BULK_SAMPLE}
        sampleFilename="bom_bulk_upload_template.csv"
        errorFilename="bom_bulk_upload_errors.csv"
        columns={BOM_BULK_COLUMNS}
        labelHeader="SKU Name"
        labelKey="productName"
        labelFallbackKey="productSku"
        successText="BOM created"
        successKey=""
        noun="BOMs"
        multiRow
        onCompleted={refresh}
      />
    </div>
  );
}

export default function ProductsPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("product:read") ? (
        <div className="flex w-full flex-col gap-4">
          <Tabs
            tabs={[
              { value: "products", label: "Products", content: <ProductsTab /> },
              { value: "bom", label: "BOM", content: <BomTab /> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="product:read" />
      )}
    </Shell>
  );
}
