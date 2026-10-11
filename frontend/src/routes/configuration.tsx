/** Configuration: the controlled lists the rest of the app draws on - product categories, party types, sticker sizes. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { STICKER_PAGE_SIZES, stickerFitIssue, stickerTotal, type StickerLayout } from "@/lib/sticker";
import { cn } from "@/lib/utils";

const PRODUCT_TYPES = ["raw_material", "finished_good", "consumable", "service"];

interface Category { id: string; code: string; productCategory: string; productTypes?: string[]; productCount?: number; status: string }
interface PartyTypeRow { code: string; label: string; baseType: string; status: string }
interface StickerSize {
  id: string; name: string; pageSize: string; pageWidthMm: string; pageHeightMm: string; stickerWidthMm: string; stickerHeightMm: string; columns: number; rows: number;
  totalStickersPerPage: number; marginLeftMm: string; marginRightMm: string; marginTopMm: string; marginBottomMm: string; gapHorizontalMm: string; gapVerticalMm: string; status: string;
}

function CategoryDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const [types, setTypes] = useState<string[]>([]);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const name = String(new FormData(e.currentTarget).get("name") ?? "").trim();
    const ok = await run(async () => {
      await api("POST", "/api/v1/product-categories", { json: { productCategory: name, productTypes: types } });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };
  return (
    <Modal descriptionSize="radix" open onClose={onClose} title="New product category" description="Codes are generated automatically (PROD-AA01, PROD-AA02, …). Leave the product types unticked to allow any kind of product in this category.">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="name" placeholder="Name, e.g. Battery module" required />
        <p className="text-xs text-[var(--muted-foreground)]">Applies to (optional)</p>
        <div className="flex flex-wrap gap-2">
          {PRODUCT_TYPES.map((t) => (
            <ActionButton key={t} size="sm" tone={types.includes(t) ? "primary" : "ghost"} onClick={() => setTypes(types.includes(t) ? types.filter((x) => x !== t) : [...types, t])}>{t}</ActionButton>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Add category</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function PartyTypeDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const ok = await run(async () => {
      await api("POST", "/api/v1/party-types", { json: { label: String(f.get("label") ?? "").trim(), baseType: String(f.get("baseType") ?? "vendor") } });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };
  return (
    <Modal descriptionSize="radix" open onClose={onClose} title="New party type" description="A business classification for the party master. The ledger type decides whether parties of this kind can be used as vendors or customers.">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="label" placeholder='Label, e.g. "Vendor - Services"' required />
        <SelectInput name="baseType" defaultValue="vendor" options={["vendor", "customer", "both"].map((v) => ({ value: v, label: v }))} />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Add party type</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

const EMPTY_STICKER = { name: "", pageSize: "A4", pageWidthMm: "", pageHeightMm: "", stickerWidthMm: "", stickerHeightMm: "", columns: "", rows: "", marginLeftMm: "0", marginRightMm: "0", marginTopMm: "0", marginBottomMm: "0", gapHorizontalMm: "0", gapVerticalMm: "0" };
type StickerForm = typeof EMPTY_STICKER;

function StickerSizeDialog({ editing, onClose, onSaved }: { editing: StickerSize | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [f, setF] = useState<StickerForm>(
    editing
      ? { name: editing.name, pageSize: editing.pageSize, pageWidthMm: editing.pageWidthMm, pageHeightMm: editing.pageHeightMm, stickerWidthMm: editing.stickerWidthMm, stickerHeightMm: editing.stickerHeightMm, columns: String(editing.columns), rows: String(editing.rows), marginLeftMm: editing.marginLeftMm, marginRightMm: editing.marginRightMm, marginTopMm: editing.marginTopMm, marginBottomMm: editing.marginBottomMm, gapHorizontalMm: editing.gapHorizontalMm, gapVerticalMm: editing.gapVerticalMm }
      : EMPTY_STICKER,
  );
  const set = (k: keyof StickerForm) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const fitIssue = stickerFitIssue(f as StickerLayout);
  const whole = (s: string) => (/^\d+$/.test(s.trim()) ? Number(s.trim()) : 0);

  const submit = async () => {
    setError("");
    if (f.name.trim().length < 2) {
      setError("Name is required (at least 2 characters)");
      return;
    }
    const body: Record<string, unknown> = {
      name: f.name.trim(), pageSize: f.pageSize, stickerWidthMm: f.stickerWidthMm || "0", stickerHeightMm: f.stickerHeightMm || "0", columns: whole(f.columns), rows: whole(f.rows),
      marginLeftMm: f.marginLeftMm || "0", marginRightMm: f.marginRightMm || "0", marginTopMm: f.marginTopMm || "0", marginBottomMm: f.marginBottomMm || "0", gapHorizontalMm: f.gapHorizontalMm || "0", gapVerticalMm: f.gapVerticalMm || "0",
    };
    if (f.pageSize === "Custom") {
      body.pageWidthMm = f.pageWidthMm || "0";
      body.pageHeightMm = f.pageHeightMm || "0";
    }
    const ok = await run(async () => {
      if (editing) await api("PATCH", `/api/v1/sticker-sizes/${editing.id}`, { json: body });
      else await api("POST", "/api/v1/sticker-sizes", { json: body });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };

  const mmField = (label: string, k: keyof StickerForm) => (
    <div className="min-w-0 flex-1"><Field label={label}><TextInput value={f[k]} onChange={set(k)} /></Field></div>
  );
  const mmInline = (label: string, k: keyof StickerForm) => (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className="field-label whitespace-nowrap" style={{ marginBottom: 0 }}>{label}</span>
      <TextInput value={f[k]} onChange={set(k)} style={{ width: "5rem", flexShrink: 0 }} />
    </div>
  );
  const section = (t: string) => <p className="mt-2 text-xs font-bold uppercase tracking-wide text-[var(--muted-foreground)]">{t}</p>;

  return (
    <Modal descriptionSize="radix" open onClose={onClose} title={editing ? "Edit sticker size" : "New sticker size"} description="A saved page/sticker/layout template for printing labels." maxWidth="36rem">
      <div className="flex flex-col gap-3">
        <InlineError message={error} />
        <div className="flex w-full gap-3">
          <div className="min-w-0 flex-1"><Field label="Name" required><TextInput placeholder='e.g. "RM Label 50x30"' value={f.name} onChange={set("name")} /></Field></div>
          <div className="min-w-0 flex-1"><Field label="Page size"><SelectInput value={f.pageSize} onChange={set("pageSize")} options={STICKER_PAGE_SIZES.map((s) => ({ value: s, label: s }))} /></Field></div>
        </div>
        {f.pageSize === "Custom" && <div className="flex w-full gap-3">{mmField("Page width (mm)", "pageWidthMm")}{mmField("Page height (mm)", "pageHeightMm")}</div>}
        {section("Sticker")}
        <div className="flex w-full gap-3">{mmField("Sticker width (mm)", "stickerWidthMm")}{mmField("Sticker height (mm)", "stickerHeightMm")}</div>
        {section("Layout")}
        <div className="flex w-full items-end gap-3">
          {mmField("Number of columns", "columns")}
          {mmField("Number of rows", "rows")}
          <div className="min-w-0 flex-1"><Field label="Total stickers / page"><p className="text-sm font-bold">{stickerTotal(f.columns, f.rows)}</p></Field></div>
        </div>
        {section("Margins (paper edge → first sticker)")}
        <div className="flex w-full gap-3">{mmInline("Left margin (mm)", "marginLeftMm")}{mmInline("Right margin (mm)", "marginRightMm")}</div>
        <div className="flex w-full gap-3">{mmInline("Top margin (mm)", "marginTopMm")}{mmInline("Bottom margin (mm)", "marginBottomMm")}</div>
        {section("Gaps")}
        <div className="flex w-full gap-3">{mmField("Horizontal gap (mm)", "gapHorizontalMm")}{mmField("Vertical gap (mm)", "gapVerticalMm")}</div>
        {fitIssue && <Note tone="warning">{fitIssue}</Note>}
        <div className="mt-2 flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton onClick={submit} loading={busy}>{editing ? "Save" : "Add sticker size"}</ActionButton>
        </div>
      </div>
    </Modal>
  );
}

function CategoriesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useApiQuery<ListResponse<Category>>("/api/v1/product-categories", { limit: 200 });
  const [open, setOpen] = useState(false);
  return (
    <div className="flex w-full flex-col items-start gap-3">
      {canWrite && <div className="flex w-full justify-end"><ActionButton onClick={() => setOpen(true)}>New category</ActionButton></div>}
      <InlineError message={list.error?.message} />
      <div className="w-full">
        <DataTable columns={["Code", "Product Category", "Product Type", "Products", "Status"]} fit>
          {(list.data?.data ?? []).map((c) => (
            <tr key={c.id}><td>{c.code}</td><td>{c.productCategory}</td><td>{c.productTypes?.length ? c.productTypes.join(", ") : "Any product type"}</td><td>{c.productCount}</td><td><Pill>{c.status}</Pill></td></tr>
          ))}
        </DataTable>
      </div>
      {open && <CategoryDialog onClose={() => setOpen(false)} onSaved={() => qc.invalidateQueries({ queryKey: ["/api/v1/product-categories"] })} />}
    </div>
  );
}

function PartyTypesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useApiQuery<{ data: PartyTypeRow[] }>("/api/v1/party-types");
  const [open, setOpen] = useState(false);
  return (
    <div className="flex w-full flex-col items-start gap-3">
      {canWrite && <div className="flex w-full justify-end"><ActionButton onClick={() => setOpen(true)}>New party type</ActionButton></div>}
      <InlineError message={list.error?.message} />
      <div className="w-full">
        <DataTable columns={["Code", "Label", "Ledger type", "Status"]} fit>
          {(list.data?.data ?? []).map((t) => (
            <tr key={t.code}><td>{t.code}</td><td>{t.label}</td><td><Pill>{t.baseType}</Pill></td><td><Pill>{t.status}</Pill></td></tr>
          ))}
        </DataTable>
      </div>
      {open && <PartyTypeDialog onClose={() => setOpen(false)} onSaved={() => qc.invalidateQueries({ queryKey: ["/api/v1/party-types"] })} />}
    </div>
  );
}

function StickerSizesTab({ canWrite }: { canWrite: boolean }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const list = useApiQuery<{ data: StickerSize[] }>("/api/v1/sticker-sizes");
  const [dialog, setDialog] = useState<{ editing: StickerSize | null } | null>(null);
  const [actionError, setActionError] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/sticker-sizes"] });
  const act = async (fn: () => Promise<unknown>) => {
    setActionError("");
    try {
      await fn();
      await refresh();
    } catch (exc) {
      setActionError(exc instanceof Error ? exc.message : String(exc));
    }
  };
  const actions = (s: StickerSize, extra = "") =>
    canWrite ? (
      <div className={cn("flex flex-wrap gap-2", extra)}>
        <ActionButton size="sm" tone="ghost" onClick={() => setDialog({ editing: s })}>Edit</ActionButton>
        <ActionButton size="sm" tone="ghost" onClick={() => act(() => api("PATCH", `/api/v1/sticker-sizes/${s.id}`, { json: { status: s.status === "active" ? "inactive" : "active" } }))}>{s.status === "active" ? "Deactivate" : "Activate"}</ActionButton>
        <ActionButton size="sm" tone="danger" onClick={() => act(() => api("DELETE", `/api/v1/sticker-sizes/${s.id}`))}>Delete</ActionButton>
      </div>
    ) : null;
  const sizes = list.data?.data ?? [];
  return (
    <div className="flex w-full flex-col items-start gap-3">
      {canWrite && <div className="flex w-full justify-end"><ActionButton onClick={() => setDialog({ editing: null })}>New sticker size</ActionButton></div>}
      <InlineError message={actionError || list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Name", "Page Size", "Sticker", "Columns × Rows", "Total / Page", "Status", ""]} fit>
          {sizes.map((s) => (
            <tr key={s.id}><td>{s.name}</td><td>{s.pageSize}</td><td>{s.stickerWidthMm} × {s.stickerHeightMm} mm</td><td>{s.columns} × {s.rows}</td><td>{s.totalStickersPerPage}</td><td><Pill>{s.status}</Pill></td><td>{actions(s)}</td></tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {sizes.map((s) => (
          <MobileRecordCard key={s.id} actions={actions(s)}>
            <MobileRecordRow label="Name" value={s.name} /><MobileRecordRow label="Page" value={s.pageSize} /><MobileRecordRow label="Sticker" value={`${s.stickerWidthMm} × ${s.stickerHeightMm} mm`} />
            <MobileRecordRow label="Grid" value={`${s.columns} × ${s.rows}`} /><MobileRecordRow label="Total / page" value={s.totalStickersPerPage} /><MobileRecordRow label="Status" value={<Pill>{s.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {dialog && <StickerSizeDialog editing={dialog.editing} onClose={() => setDialog(null)} onSaved={refresh} />}
    </div>
  );
}

export default function ConfigurationPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("product:read") || can("party:read") || can("sticker_size:read") ? (
        <div className="flex w-full flex-col items-start gap-4">
          <PageHeader eyebrow="Foundation" title="Configuration" description="The controlled lists the rest of the app draws on." />
          <Tabs
            tabs={[
              { value: "categories", label: "Product Categories", content: <CategoriesTab canWrite={can("product:write")} /> },
              { value: "partyTypes", label: "Party Types", content: <PartyTypesTab canWrite={can("party:write")} /> },
              { value: "stickerSizes", label: "Sticker Size", content: <StickerSizesTab canWrite={can("sticker_size:write")} /> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="product:read" />
      )}
    </Shell>
  );
}
