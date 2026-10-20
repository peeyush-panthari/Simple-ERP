/**
 * Factory & Warehouse: the sites Simple operates, and which warehouse sits
 * inside which factory (used for delivery/pickup addresses on POs and
 * logistics). A controlled master list, not a day-to-day operational record.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import { GuidedFieldWalkthrough } from "@/components/erp/guided-field-walkthrough";
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useDemoTour } from "@/lib/demo-flow-context";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { COUNTRY_OPTIONS, INDIAN_STATE_NAMES, INDIAN_STATE_SELECT_OPTIONS } from "@/lib/reference";
import { cn } from "@/lib/utils";

interface Factory {
  id: string;
  code: string;
  name: string;
  status: string;
  city?: string | null;
  stateCode?: string | null;
  addressLine1?: string | null;
  postalCode?: string | null;
  warehouseCount?: number;
}
interface Warehouse {
  id: string;
  code: string;
  name: string;
  status: string;
  factoryId?: string | null;
  factoryName?: string | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  postalCode?: string | null;
  stateCode?: string | null;
}

const FACTORY_COLUMNS = ["code", "name", "addressLine1", "addressLine2", "city", "stateCode", "postalCode", "country", "contactEmail", "contactPhone", "notes", "status"];
const FACTORY_SAMPLE =
  `${FACTORY_COLUMNS.join(",")}\n` + ",Pune Plant,12 Industrial Rd,,Pune,27,411001,IN,,,,active\n" + ",Chennai Plant,88 Factory Rd,,Chennai,33,600001,IN,,,,active\n";
const WAREHOUSE_COLUMNS = ["code", "name", "status", "factoryCode", "allowedProductTypes", "addressLine1", "addressLine2", "city", "stateCode", "postalCode", "country", "contactEmail", "contactPhone", "capacityUnits", "notes"];
const WAREHOUSE_SAMPLE =
  `${WAREHOUSE_COLUMNS.join(",")}\n` +
  ",Pune Main Warehouse,active,,raw_material|consumable,12 Industrial Rd,,Pune,27,411001,IN,,,,\n" +
  ",Chennai Warehouse,active,,finished_good,88 Factory Rd,,Chennai,33,600001,IN,,,,\n";

const WAREHOUSE_STATUSES = ["active", "constrained", "inactive"].map((v) => ({ value: v, label: v }));
const stateOptions = INDIAN_STATE_SELECT_OPTIONS;
const stateLabel = (code?: string | null) => (code && INDIAN_STATE_NAMES[code] ? `${code} — ${INDIAN_STATE_NAMES[code]}` : code);

function FactoryDialog({ factory, onClose, onSaved }: { factory: Factory | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep2 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 1;

  const [activeWalkthroughField, setActiveWalkthroughField] = useState("name");
  const [name, setName] = useState(factory?.name ?? "");
  const [addressLine1, setAddressLine1] = useState(factory?.addressLine1 ?? "");
  const [city, setCity] = useState(factory?.city ?? "");
  const [stateCode, setStateCode] = useState(factory?.stateCode ?? "");
  const [postalCode, setPostalCode] = useState(factory?.postalCode ?? "");

  const autofillDemoPlant = () => {
    setName("Pune Assembly Plant 1");
    setAddressLine1("Plot 42, Hinjewadi Industrial Zone Phase 2");
    setCity("Pune");
    setStateCode("27");
    setPostalCode("411057");
  };

  const walkthroughFields = [
    {
      id: "name",
      label: "Factory Name (Required)",
      shortLabel: "Name",
      useCase: "Primary manufacturing facility entity that hosts assembly lines, shop-floor work centers, and working calendars.",
      guideline: "Descriptive facility identifier (e.g. Pune Assembly Plant 1).",
      restriction: "Required. Factory codes are generated automatically (FACT-XXXX).",
      sampleValueText: "Pune Assembly Plant 1",
      isFilled: Boolean(name),
      onFill: () => setName("Pune Assembly Plant 1"),
    },
    {
      id: "addressLine1",
      label: "Street Address",
      shortLabel: "Address",
      useCase: "Physical plant dispatch and delivery address printed on vendor purchase orders and gate-in records.",
      guideline: "Industrial park or plot details.",
      restriction: "Standard physical street address.",
      sampleValueText: "Plot 42, Hinjewadi Industrial Zone Phase 2",
      isFilled: Boolean(addressLine1),
      onFill: () => setAddressLine1("Plot 42, Hinjewadi Industrial Zone Phase 2"),
    },
    {
      id: "location",
      label: "City, State & Postal Code",
      shortLabel: "City/State",
      useCase: "Determines statutory GST tax jurisdiction (State code 27 = Maharashtra for intra-state CGST/SGST).",
      guideline: "2-digit Indian state code matching the registered tax entity.",
      restriction: "Mandatory for automated tax calculation.",
      sampleValueText: "Pune, State 27, PIN 411057",
      isFilled: Boolean(city && stateCode && postalCode),
      onFill: () => {
        setCity("Pune");
        setStateCode("27");
        setPostalCode("411057");
      },
    },
  ];

  const allWalkthroughFilled = Boolean(name && addressLine1 && city && stateCode);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body = {
      name: name || get("name"),
      addressLine1: addressLine1 || get("addressLine1") || null,
      city: city || get("city") || null,
      stateCode: stateCode || get("stateCode") || null,
      postalCode: postalCode || get("postalCode") || null,
    };
    const ok = await run(async () => {
      if (factory) await api("PATCH", `/api/v1/factories/${factory.id}`, { json: body });
      else await api("POST", "/api/v1/factories", { json: body });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };
  return (
    <Modal open onClose={onClose} title={factory ? "Edit factory" : "New factory"} description="Codes are generated automatically." descriptionSize="radix">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        {isTourStep2 && !factory && (
          <GuidedFieldWalkthrough
            dialogTitle="New factory"
            fields={walkthroughFields}
            activeFieldId={activeWalkthroughField}
            onSelectField={setActiveWalkthroughField}
            onFillAll={autofillDemoPlant}
            allFilled={allWalkthroughFilled}
            submitButtonLabel="Save"
            stepBadgeNumber={2}
            nextStepBadgeNumber={3}
          />
        )}
        <div className={cn(isTourStep2 && !factory && activeWalkthroughField === "name" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <TextInput
            name="name"
            placeholder="Name, e.g. Pune Plant"
            value={name}
            onFocus={() => setActiveWalkthroughField("name")}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className={cn(isTourStep2 && !factory && activeWalkthroughField === "addressLine1" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <TextInput
            name="addressLine1"
            placeholder="Address line 1"
            value={addressLine1}
            onFocus={() => setActiveWalkthroughField("addressLine1")}
            onChange={(e) => setAddressLine1(e.target.value)}
          />
        </div>
        <div className={cn(isTourStep2 && !factory && activeWalkthroughField === "location" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <div className="flex gap-2">
            <TextInput
              name="city"
              placeholder="City"
              value={city}
              onFocus={() => setActiveWalkthroughField("location")}
              onChange={(e) => setCity(e.target.value)}
            />
            <TextInput
              name="stateCode"
              placeholder="State code"
              value={stateCode}
              onFocus={() => setActiveWalkthroughField("location")}
              onChange={(e) => setStateCode(e.target.value)}
            />
            <TextInput
              name="postalCode"
              placeholder="Postal code"
              value={postalCode}
              onFocus={() => setActiveWalkthroughField("location")}
              onChange={(e) => setPostalCode(e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 items-center">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <div className="relative">
            {isTourStep2 && !factory && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  3
                </span>
              </span>
            )}
            <ActionButton
              type="submit"
              tone={isTourStep2 && !factory ? "primary" : undefined}
              loading={busy}
              className={cn(isTourStep2 && !factory && allWalkthroughFilled && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              Save
            </ActionButton>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function WarehouseDialog({ warehouse, factories, onClose, onSaved }: { warehouse: Warehouse | null; factories: Factory[]; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep2 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 1;

  const w: Partial<Warehouse> = warehouse ?? {};
  const [activeWalkthroughField, setActiveWalkthroughField] = useState("name");
  const [name, setName] = useState(w.name ?? "");
  const [status, setStatus] = useState(warehouse ? w.status || "active" : "active");
  const [factoryId, setFactoryId] = useState(w.factoryId ?? (factories[0]?.id || ""));
  const [addressLine1, setAddressLine1] = useState(w.addressLine1 ?? "");
  const [city, setCity] = useState(w.city ?? "");
  const [postalCode, setPostalCode] = useState(w.postalCode ?? "");
  const [stateCode, setStateCode] = useState(w.stateCode ?? "27");

  const autofillDemoWarehouse = () => {
    setName("Pune Central Warehouse");
    setStatus("active");
    if (factories.length > 0) {
      setFactoryId(factories[0].id);
    }
    setAddressLine1("Plot 42, Inbound Bay A & B");
    setCity("Pune");
    setStateCode("27");
    setPostalCode("411057");
  };

  const walkthroughFields = [
    {
      id: "name",
      label: "Warehouse Name (Required)",
      shortLabel: "Name",
      useCase: "Physical inventory storage facility with dock doors, receiving bays, and directed bin putaway.",
      guideline: "Descriptive storage location name (e.g. Pune Central Warehouse).",
      restriction: "Required. Unique warehouse code generated automatically.",
      sampleValueText: "Pune Central Warehouse",
      isFilled: Boolean(name),
      onFill: () => setName("Pune Central Warehouse"),
    },
    {
      id: "factoryId",
      label: "Status & Factory Topology Link",
      shortLabel: "Factory Link",
      useCase: "Geographically links storage site to manufacturing plant for internal stock transfer orders.",
      guideline: "Select the plant where this warehouse physically operates.",
      restriction: "Warehouse must be active to transact stock.",
      sampleValueText: "Active / Pune Plant",
      isFilled: Boolean(factoryId && status === "active"),
      onFill: () => {
        setStatus("active");
        if (factories.length > 0) setFactoryId(factories[0].id);
      },
    },
    {
      id: "location",
      label: "Inbound Dock Address & State",
      shortLabel: "Dock Address",
      useCase: "Ship-to destination printed on vendor POs and statutory e-Way Bills.",
      guideline: "Specify dock and gate identifiers for delivery drivers.",
      restriction: "State code must match the registered tax entity.",
      sampleValueText: "Plot 42, Inbound Bay A & B, Pune, State 27",
      isFilled: Boolean(addressLine1 && city && stateCode),
      onFill: () => {
        setAddressLine1("Plot 42, Inbound Bay A & B");
        setCity("Pune");
        setStateCode("27");
        setPostalCode("411057");
      },
    },
  ];

  const allWalkthroughFilled = Boolean(name && factoryId && addressLine1 && city);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body = {
      name: name || get("name"),
      status: status || get("status") || "active",
      addressLine1: addressLine1 || get("addressLine1") || null,
      addressLine2: get("addressLine2") || null,
      city: city || get("city") || null,
      postalCode: postalCode || get("postalCode") || null,
      stateCode: stateCode || get("stateCode") || null,
      country: get("country") || "IN",
      factoryId: factoryId || get("factoryId") || null,
    };
    const ok = await run(async () => {
      if (warehouse) await api("PATCH", `/api/v1/warehouses/${warehouse.id}`, { json: body });
      else await api("POST", "/api/v1/warehouses", { json: body });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };
  return (
    <Modal open onClose={onClose} descriptionSize="radix" title={warehouse ? "Edit warehouse" : "New warehouse"} description={warehouse ? undefined : "Codes are generated automatically."}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        {isTourStep2 && !warehouse && (
          <GuidedFieldWalkthrough
            dialogTitle="New warehouse"
            fields={walkthroughFields}
            activeFieldId={activeWalkthroughField}
            onSelectField={setActiveWalkthroughField}
            onFillAll={autofillDemoWarehouse}
            allFilled={allWalkthroughFilled}
            submitButtonLabel="Save"
            stepBadgeNumber={2}
            nextStepBadgeNumber={3}
          />
        )}
        {warehouse && <p className="text-sm text-[var(--muted-foreground)]">Code (immutable): {w.code}</p>}
        <div className={cn(isTourStep2 && !warehouse && activeWalkthroughField === "name" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <TextInput
            name="name"
            placeholder="Name"
            value={name}
            onFocus={() => setActiveWalkthroughField("name")}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className={cn(isTourStep2 && !warehouse && activeWalkthroughField === "factoryId" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-2")}>
          <SelectInput name="status" value={status} onChange={(e) => setStatus(e.target.value)} options={WAREHOUSE_STATUSES} />
          <SelectInput name="factoryId" placeholder="Factory (optional)" value={factoryId} onChange={(e) => setFactoryId(e.target.value)} options={factories.filter((f) => f.status === "active").map((f) => ({ value: f.id, label: f.name }))} />
        </div>
        <div className={cn(isTourStep2 && !warehouse && activeWalkthroughField === "location" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-2")}>
          <TextInput
            name="addressLine1"
            placeholder="Address line 1"
            value={addressLine1}
            onFocus={() => setActiveWalkthroughField("location")}
            onChange={(e) => setAddressLine1(e.target.value)}
          />
          <TextInput name="addressLine2" placeholder="Address line 2 (optional)" defaultValue={w.addressLine2 ?? ""} />
          <div className="flex gap-2">
            <TextInput name="city" placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
            <TextInput name="postalCode" placeholder="Postal code" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
          </div>
          <SelectInput name="stateCode" placeholder="State" value={stateCode} onChange={(e) => setStateCode(e.target.value)} options={stateOptions} />
        </div>
        <SelectInput name="country" placeholder="Country" defaultValue="IN" options={COUNTRY_OPTIONS} />
        <div className="flex justify-end gap-2 items-center">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <div className="relative">
            {isTourStep2 && !warehouse && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  3
                </span>
              </span>
            )}
            <ActionButton
              type="submit"
              tone={isTourStep2 && !warehouse ? "primary" : undefined}
              loading={busy}
              className={cn(isTourStep2 && !warehouse && allWalkthroughFilled && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              Save
            </ActionButton>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function FactoriesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep2 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 1;

  const list = useApiQuery<ListResponse<Factory>>("/api/v1/factories", { limit: 100 });
  const factories = list.data?.data ?? [];
  const [dialog, setDialog] = useState<{ factory: Factory | null } | null>(null);
  const [bulk, setBulk] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/factories"] });
  const location = (f: Factory) => (f.city ? `${f.city}, ${f.stateCode}` : "–");
  const edit = (f: Factory, cls?: string) => canWrite && <ActionButton size="sm" className={cls} onClick={() => setDialog({ factory: f })}>Edit</ActionButton>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center gap-2">
        <h2 className="rx-heading-6">Factories</h2>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulk(true)} />}
        {canWrite && (
          <div className="relative">
            {isTourStep2 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  2
                </span>
              </span>
            )}
            <ActionButton
              onClick={() => setDialog({ factory: null })}
              tone={isTourStep2 ? "primary" : undefined}
              className={cn(isTourStep2 && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              New factory
            </ActionButton>
          </div>
        )}
      </div>
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Code", "Name", "Location", "Warehouses", "Status", ""]} fit>
          {factories.map((f) => (
            <tr key={f.id}><td>{f.code}</td><td>{f.name}</td><td>{location(f)}</td><td>{f.warehouseCount}</td><td><Pill>{f.status}</Pill></td><td>{edit(f)}</td></tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {factories.map((f) => (
          <MobileRecordCard key={f.id} actions={edit(f, "w-full justify-center")}>
            <MobileRecordRow label="Code" value={f.code} /><MobileRecordRow label="Name" value={f.name} /><MobileRecordRow label="Location" value={location(f)} />
            <MobileRecordRow label="Warehouses" value={f.warehouseCount} /><MobileRecordRow label="Status" value={<Pill>{f.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {dialog && <FactoryDialog factory={dialog.factory} onClose={() => setDialog(null)} onSaved={refresh} />}
      <BulkUploadDialog open={bulk} onClose={() => setBulk(false)} title="Bulk upload factories" description="Upload a CSV with one row per factory." endpoint="/api/v1/factories/bulk-upload"
        sampleCsv={FACTORY_SAMPLE} sampleFilename="factory_bulk_upload_template.csv" errorFilename="factory_bulk_upload_errors.csv" columns={FACTORY_COLUMNS}
        labelHeader="Name" labelKey="name" successKey="code" noun="factories" onCompleted={refresh} />
    </div>
  );
}

function WarehousesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep2 = isTourActive && activeJourneyId === "administration" && currentJourneyStepIndex === 1;

  const list = useApiQuery<ListResponse<Warehouse>>("/api/v1/warehouses", { limit: 100 });
  const factories = useApiQuery<ListResponse<Factory>>("/api/v1/factories", { limit: 100 });
  const warehouses = list.data?.data ?? [];
  const [dialog, setDialog] = useState<{ warehouse: Warehouse | null } | null>(null);
  const [bulk, setBulk] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/warehouses"] });
  const city = (w: Warehouse) => (w.city ? `${w.city}, ${stateLabel(w.stateCode)}` : "–");
  const edit = (w: Warehouse, cls?: string) => canWrite && <ActionButton size="sm" className={cls} onClick={() => setDialog({ warehouse: w })}>Edit</ActionButton>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center gap-2">
        <h2 className="rx-heading-6">Warehouses</h2>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulk(true)} />}
        {canWrite && (
          <div className="relative">
            {isTourStep2 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  2
                </span>
              </span>
            )}
            <ActionButton
              onClick={() => setDialog({ warehouse: null })}
              tone={isTourStep2 ? "primary" : undefined}
              className={cn(isTourStep2 && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              New warehouse
            </ActionButton>
          </div>
        )}
      </div>
      <InlineError message={list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Code", "Name", "Status", "Factory", "City", ""]} fit>
          {warehouses.map((w) => (
            <tr key={w.id}><td>{w.code}</td><td>{w.name}</td><td><Pill>{w.status}</Pill></td><td>{w.factoryName || "–"}</td><td>{city(w)}</td><td>{edit(w)}</td></tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {warehouses.map((w) => (
          <MobileRecordCard key={w.id} actions={edit(w, "w-full justify-center")}>
            <MobileRecordRow label="Code" value={w.code} /><MobileRecordRow label="Name" value={w.name} /><MobileRecordRow label="Status" value={<Pill>{w.status}</Pill>} />
            <MobileRecordRow label="Factory" value={w.factoryName || "–"} /><MobileRecordRow label="City" value={city(w)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {dialog && <WarehouseDialog warehouse={dialog.warehouse} factories={factories.data?.data ?? []} onClose={() => setDialog(null)} onSaved={refresh} />}
      <BulkUploadDialog open={bulk} onClose={() => setBulk(false)} title="Bulk upload warehouses" description="Upload a CSV with one row per warehouse." endpoint="/api/v1/warehouses/bulk-upload"
        sampleCsv={WAREHOUSE_SAMPLE} sampleFilename="warehouse_bulk_upload_template.csv" errorFilename="warehouse_bulk_upload_errors.csv" columns={WAREHOUSE_COLUMNS}
        labelHeader="Name" labelKey="name" successKey="code" noun="warehouses" onCompleted={refresh} />
    </div>
  );
}

export default function FactoryWarehousePage() {
  const { can } = useAuth();
  const canWrite = can("warehouse:write");
  return (
    <Shell>
      {can("warehouse:read") ? (
        <div className="flex w-full flex-col items-start gap-4">
          <PageHeader eyebrow="Foundation" title="Factory & Warehouse" description="The factories and warehouses Simple operates, and which warehouse sits inside which factory." />
          <Tabs
            tabs={[
              { value: "factories", label: "Factories", content: <FactoriesTab canWrite={canWrite} /> },
              { value: "warehouses", label: "Warehouses", content: <WarehousesTab canWrite={canWrite} /> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="warehouse:read" />
      )}
    </Shell>
  );
}
