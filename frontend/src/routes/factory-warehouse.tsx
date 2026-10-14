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
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { COUNTRY_OPTIONS, INDIAN_STATE_NAMES, INDIAN_STATE_SELECT_OPTIONS } from "@/lib/reference";

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
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body = { name: get("name"), addressLine1: get("addressLine1") || null, city: get("city") || null, stateCode: get("stateCode") || null, postalCode: get("postalCode") || null };
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
        <TextInput name="name" placeholder="Name, e.g. Pune Plant" defaultValue={factory?.name ?? ""} required />
        <TextInput name="addressLine1" placeholder="Address line 1" defaultValue={factory?.addressLine1 ?? ""} />
        <div className="flex gap-2">
          <TextInput name="city" placeholder="City" defaultValue={factory?.city ?? ""} />
          <TextInput name="stateCode" placeholder="State code" defaultValue={factory?.stateCode ?? ""} />
          <TextInput name="postalCode" placeholder="Postal code" defaultValue={factory?.postalCode ?? ""} />
        </div>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Save</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function WarehouseDialog({ warehouse, factories, onClose, onSaved }: { warehouse: Warehouse | null; factories: Factory[]; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const w: Partial<Warehouse> = warehouse ?? {};
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body = {
      name: get("name"), status: get("status") || "active", addressLine1: get("addressLine1") || null, addressLine2: get("addressLine2") || null, city: get("city") || null,
      postalCode: get("postalCode") || null, stateCode: get("stateCode") || null, country: get("country") || "IN", factoryId: get("factoryId") || null,
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
        {warehouse && <p className="text-sm text-[var(--muted-foreground)]">Code (immutable): {w.code}</p>}
        <TextInput name="name" placeholder="Name" defaultValue={w.name ?? ""} required />
        <SelectInput name="status" defaultValue={warehouse ? w.status : "active"} options={WAREHOUSE_STATUSES} />
        <SelectInput name="factoryId" placeholder="Factory (optional)" defaultValue={w.factoryId ?? ""} options={factories.filter((f) => f.status === "active").map((f) => ({ value: f.id, label: f.name }))} />
        <TextInput name="addressLine1" placeholder="Address line 1" defaultValue={w.addressLine1 ?? ""} />
        <TextInput name="addressLine2" placeholder="Address line 2 (optional)" defaultValue={w.addressLine2 ?? ""} />
        <div className="flex gap-2">
          <TextInput name="city" placeholder="City" defaultValue={w.city ?? ""} />
          <TextInput name="postalCode" placeholder="Postal code" defaultValue={w.postalCode ?? ""} />
        </div>
        <SelectInput name="stateCode" placeholder="State" defaultValue={w.stateCode ?? ""} options={stateOptions} />
        <SelectInput name="country" placeholder="Country" defaultValue="IN" options={COUNTRY_OPTIONS} />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Save</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function FactoriesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
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
        {canWrite && <ActionButton onClick={() => setDialog({ factory: null })}>New factory</ActionButton>}
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
        {canWrite && <ActionButton onClick={() => setDialog({ warehouse: null })}>New warehouse</ActionButton>}
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
