/** Configuration: the controlled lists the rest of the app draws on - product categories, party types, sticker sizes. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, useMemo, useEffect, type FormEvent } from "react";
import { Check, CheckCircle2, Sparkles, SlidersHorizontal } from "lucide-react";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import { GuidedFieldWalkthrough } from "@/components/erp/guided-field-walkthrough";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useDemoTour } from "@/lib/demo-flow-context";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { STICKER_PAGE_SIZES, stickerFitIssue, stickerTotal, type StickerLayout } from "@/lib/sticker";
import { cn, errMsg } from "@/lib/utils";
import { PRODUCT_TYPES } from "@/lib/reference";
import { ALL_ERP_MODULES, INDUSTRY_PRESETS, type ErpModuleDefinition } from "@/lib/modules";

interface Category { id: string; code: string; productCategory: string; productTypes?: string[]; productCount?: number; status: string }
interface PartyTypeRow { code: string; label: string; baseType: string; status: string }
interface StickerSize {
  id: string; name: string; pageSize: string; pageWidthMm: string; pageHeightMm: string; stickerWidthMm: string; stickerHeightMm: string; columns: number; rows: number;
  totalStickersPerPage: number; marginLeftMm: string; marginRightMm: string; marginTopMm: string; marginBottomMm: string; gapHorizontalMm: string; gapVerticalMm: string; status: string;
}

function CategoryDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep4 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 3;

  const [activeWalkthroughField, setActiveWalkthroughField] = useState("name");
  const [name, setName] = useState("");
  const [types, setTypes] = useState<string[]>([]);

  const autofillDemoCategory = () => {
    setName("Electric Motors & Powertrains");
    setTypes(["finished_good", "subassembly"]);
  };

  const walkthroughFields = [
    {
      id: "name",
      label: "Category Name (Taxonomy Label)",
      shortLabel: "Category Name",
      useCase: "Master grouping for financial balance sheet reporting, gross margin analytics, and warehouse storage classification.",
      guideline: "Descriptive category name (e.g. Electric Motors & Powertrains).",
      restriction: "Required. Must be unique across active categories. Code (PROD-AAXX) is auto-assigned.",
      sampleValueText: "Electric Motors & Powertrains",
      isFilled: Boolean(name),
      onFill: () => setName("Electric Motors & Powertrains"),
    },
    {
      id: "types",
      label: "Applicable Product Types (Optional)",
      shortLabel: "Product Types",
      useCase: "Constrains which product types can select this category during SKU creation to avoid improper GL mapping.",
      guideline: "Tag with finished_good and subassembly for motor components.",
      restriction: "Leave unticked to allow all product types. Ticked options enforce category restriction.",
      sampleValueText: "finished_good, subassembly",
      isFilled: types.includes("finished_good") && types.includes("subassembly"),
      onFill: () => setTypes(["finished_good", "subassembly"]),
    },
  ];

  const allWalkthroughFilled = Boolean(name);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const finalName = name || String(new FormData(e.currentTarget).get("name") ?? "").trim();
    const ok = await run(async () => {
      await api("POST", "/api/v1/product-categories", { json: { productCategory: finalName, productTypes: types } });
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
        {isTourStep4 && (
          <GuidedFieldWalkthrough
            dialogTitle="New product category"
            fields={walkthroughFields}
            activeFieldId={activeWalkthroughField}
            onSelectField={setActiveWalkthroughField}
            onFillAll={autofillDemoCategory}
            allFilled={allWalkthroughFilled}
            submitButtonLabel="Add category"
            stepBadgeNumber={2}
            nextStepBadgeNumber={3}
          />
        )}
        <div className={cn(isTourStep4 && activeWalkthroughField === "name" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <TextInput
            name="name"
            placeholder="Name, e.g. Battery module"
            value={name}
            onFocus={() => setActiveWalkthroughField("name")}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className={cn(isTourStep4 && activeWalkthroughField === "types" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-1.5")}>
          <p className="text-xs text-[var(--muted-foreground)]">Applies to (optional)</p>
          <div className="flex flex-wrap gap-2">
            {PRODUCT_TYPES.map((t) => (
              <ActionButton
                key={t}
                size="sm"
                tone={types.includes(t) ? "primary" : "ghost"}
                onClick={() => {
                  setActiveWalkthroughField("types");
                  setTypes(types.includes(t) ? types.filter((x) => x !== t) : [...types, t]);
                }}
              >
                {t}
              </ActionButton>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 items-center">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <div className="relative">
            {isTourStep4 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  3
                </span>
              </span>
            )}
            <ActionButton
              type="submit"
              tone={isTourStep4 ? "primary" : undefined}
              loading={busy}
              className={cn(isTourStep4 && allWalkthroughFilled && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              Add category
            </ActionButton>
          </div>
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
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep4 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 3;

  const list = useApiQuery<ListResponse<Category>>("/api/v1/product-categories", { limit: 200 });
  const [open, setOpen] = useState(false);
  return (
    <div className="flex w-full flex-col items-start gap-3">
      {canWrite && (
        <div className="flex w-full justify-end">
          <div className="relative">
            {isTourStep4 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  4
                </span>
              </span>
            )}
            <ActionButton
              onClick={() => setOpen(true)}
              tone={isTourStep4 ? "primary" : undefined}
              className={cn(isTourStep4 && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              New category
            </ActionButton>
          </div>
        </div>
      )}
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
      setActionError(errMsg(exc));
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

interface TenantModulesData {
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  enabledModules: string[];
  currentPreset?: string;
}

function ModulesCustomizerTab({ canWrite }: { canWrite: boolean }) {
  const { api, reloadUser, user } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const query = useApiQuery<TenantModulesData>("/api/v1/tenant/modules");
  const [selectedPreset, setSelectedPreset] = useState<string>("full");
  const [enabledList, setEnabledList] = useState<string[]>(["*"]);

  useEffect(() => {
    if (query.data) {
      const active = query.data.enabledModules || ["*"];
      setEnabledList(active);
      setSelectedPreset(query.data.currentPreset || (active.includes("*") ? "full" : "custom"));
    }
  }, [query.data]);

  const allModuleIds = useMemo(() => ALL_ERP_MODULES.map((m) => m.id), []);

  const isModuleActive = (id: string) => {
    return enabledList.includes("*") || enabledList.includes(id);
  };

  const handleApplyPreset = (presetKey: string) => {
    setSelectedPreset(presetKey);
    const preset = INDUSTRY_PRESETS[presetKey];
    if (preset) {
      setEnabledList(preset.modules);
    }
  };

  const handleToggleModule = (id: string) => {
    setSelectedPreset("custom");
    if (enabledList.includes("*")) {
      const withoutOne = allModuleIds.filter((m) => m !== id);
      setEnabledList(withoutOne);
    } else if (enabledList.includes(id)) {
      setEnabledList(enabledList.filter((m) => m !== id));
    } else {
      const next = [...enabledList, id];
      if (next.length === allModuleIds.length) {
        setEnabledList(["*"]);
      } else {
        setEnabledList(next);
      }
    }
  };

  const handleSave = async () => {
    setSuccessMessage(null);
    await run(async () => {
      await api("PUT", "/api/v1/tenant/modules", {
        json: {
          enabledModules: enabledList,
          preset: selectedPreset,
        },
      });
      await reloadUser();
      setSuccessMessage("Module configuration saved! Your navigation and workflows are now customized for your business.");
      setTimeout(() => setSuccessMessage(null), 6000);
    });
  };

  const groupedModules = useMemo(() => {
    const groups: Record<string, ErpModuleDefinition[]> = {};
    ALL_ERP_MODULES.forEach((m) => {
      if (!groups[m.group]) groups[m.group] = [];
      groups[m.group].push(m);
    });
    return groups;
  }, []);

  const activeCount = enabledList.includes("*") ? allModuleIds.length : enabledList.length;

  return (
    <div className="flex w-full flex-col items-start gap-5">
      <div className="flex w-full flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
        <div>
          <h3 className="text-base font-semibold text-[var(--foreground)]">Enterprise Module Customizer</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            Configure active workflows for <strong>{user?.tenantName || "this company"}</strong>. Workflows and sidebar items will only appear for selected modules.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Pill tone="info">
            {activeCount} of {allModuleIds.length} Modules Active
          </Pill>
          {canWrite && (
            <ActionButton onClick={handleSave} loading={busy}>
              Save Active Modules
            </ActionButton>
          )}
        </div>
      </div>

      <InlineError message={error || query.error?.message} />
      {successMessage && (
        <div className="w-full rounded-md bg-[var(--success)]/10 border border-[var(--success)]/30 p-3 text-sm text-[var(--success)] flex items-center gap-2">
          <CheckCircle2 size={16} />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Preset Profiles */}
      <div className="w-full flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] flex items-center gap-1.5">
          <Sparkles size={14} /> Quick-Pick Industry Profile
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {Object.entries(INDUSTRY_PRESETS).map(([key, preset]) => {
            const isSelected = selectedPreset === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => canWrite && handleApplyPreset(key)}
                disabled={!canWrite}
                className={cn(
                  "flex flex-col text-left p-3.5 rounded-lg border transition-all",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/5 ring-1 ring-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)]/50",
                  !canWrite && "opacity-75 cursor-default",
                )}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="text-xs font-bold text-[var(--foreground)] line-clamp-1">{preset.label.split("(")[0]}</span>
                  {isSelected && <Check size={14} className="text-[var(--primary)] shrink-0" />}
                </div>
                <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-2 leading-relaxed">{preset.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Grouped Module Checkboxes */}
      <div className="w-full flex flex-col gap-4 mt-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] flex items-center gap-1.5">
            <SlidersHorizontal size={14} /> Modular Capabilities Checklist
          </label>
          {canWrite && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setSelectedPreset("full");
                  setEnabledList(["*"]);
                }}
                className="text-xs text-[var(--primary)] hover:underline"
              >
                Enable All
              </button>
              <span className="text-[var(--muted-foreground)]">•</span>
              <button
                type="button"
                onClick={() => {
                  setSelectedPreset("custom");
                  setEnabledList([]);
                }}
                className="text-xs text-[var(--muted-foreground)] hover:underline"
              >
                Deselect All
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-5">
          {Object.entries(groupedModules).map(([groupName, modules]) => (
            <div key={groupName} className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <div className="bg-[var(--muted)]/50 px-4 py-2.5 border-b border-[var(--border)] flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">{groupName}</span>
                <span className="text-[11px] text-[var(--muted-foreground)]">
                  {modules.filter((m) => isModuleActive(m.id)).length} of {modules.length} active
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
                {modules.map((mod) => {
                  const active = isModuleActive(mod.id);
                  return (
                    <div
                      key={mod.id}
                      onClick={() => canWrite && handleToggleModule(mod.id)}
                      className={cn(
                        "flex items-start gap-3 p-3.5 transition-colors cursor-pointer select-none",
                        active ? "bg-[var(--card)]" : "bg-[var(--muted)]/20 opacity-70",
                        canWrite ? "hover:bg-[var(--muted)]/40" : "cursor-default",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={() => {}}
                        disabled={!canWrite}
                        className="mt-0.5 h-4 w-4 rounded border-[var(--border)] text-[var(--primary)] focus:ring-[var(--primary)]"
                      />
                      <div className="flex flex-col min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={cn("text-xs font-medium", active ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]")}>
                            {mod.name}
                          </span>
                        </div>
                        <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed mt-0.5">{mod.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ConfigurationPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("product:read") || can("party:read") || can("sticker_size:read") || can("org:read") || can("user:read") ? (
        <div className="flex w-full flex-col items-start gap-4">
          <PageHeader eyebrow="Foundation" title="Configuration" description="System controlled lists, sticker layouts, and active ERP module settings." />
          <Tabs
            tabs={[
              { value: "modules", label: "Active Modules & Setup", content: <ModulesCustomizerTab canWrite={can("org:write") || can("user:write")} /> },
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
