/**
 * PO & Invoice: Simple's own legal entities (name, address, tax ID) - the
 * seller identity stamped onto a purchase order or customer invoice. Multiple
 * entries let different business verticals raise documents under their own
 * registration.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { CheckRow } from "@/components/erp/extras";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { COUNTRY_OPTIONS, INDIAN_STATE_NAMES, indianStateSelectOptions } from "@/lib/reference";
import { errMsg } from "@/lib/utils";

interface Entity {
  id: string;
  code: string;
  name: string;
  status: string;
  isDefault?: boolean;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  stateCode?: string | null;
  postalCode?: string | null;
  country?: string | null;
  taxId?: string | null;
  pan?: string | null;
  contactEmail?: string | null;
  contactPhone?: string | null;
  bankName?: string | null;
  bankBranch?: string | null;
  bankAccountNumber?: string | null;
  bankIfsc?: string | null;
}

// Mirrors the backend's bulk-upload columns for business entities.
const BULK_COLUMNS = [
  "code", "name", "addressLine1", "addressLine2", "city", "stateCode", "postalCode", "country",
  "taxId", "taxIdCountry", "pan", "contactEmail", "contactPhone",
  "bankName", "bankBranch", "bankAccountNumber", "bankIfsc", "isDefault", "status",
];
const BULK_SAMPLE =
  `${BULK_COLUMNS.join(",")}\n` +
  ",Battery Vertical Pvt Ltd,12 Industrial Rd,,Pune,27,411001,IN,,,,accounts@example.com,,HDFC Bank,MG Road,000123456789,HDFC0001234,true,active\n" +
  ",Chemicals Vertical Pvt Ltd,88 Market St,,Bengaluru,29,560001,IN,,,,accounts2@example.com,,,,,,false,active\n";

const stateName = (e: Entity) => (e.stateCode && INDIAN_STATE_NAMES[e.stateCode] ? `${e.stateCode} — ${INDIAN_STATE_NAMES[e.stateCode]}` : e.stateCode);
const bankSummary = (e: Entity) => (e.bankName && e.bankAccountNumber ? `${e.bankName} ••${e.bankAccountNumber.slice(-4)}` : e.bankName || "");

function EntityDialog({ entity, onClose, onSaved }: { entity: Entity | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const [isDefault, setIsDefault] = useState(!!entity?.isDefault);
  const e: Partial<Entity> = entity ?? {};

  const submit = async (ev: FormEvent<HTMLFormElement>) => {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body = {
      name: get("name"),
      addressLine1: get("addressLine1") || null,
      addressLine2: get("addressLine2") || null,
      city: get("city") || null,
      stateCode: get("stateCode") || null,
      postalCode: get("postalCode") || null,
      country: get("country") || "IN",
      taxId: get("taxId") || null,
      pan: get("pan") || null,
      contactEmail: get("contactEmail") || null,
      contactPhone: get("contactPhone") || null,
      bankName: get("bankName") || null,
      bankBranch: get("bankBranch") || null,
      bankAccountNumber: get("bankAccountNumber") || null,
      bankIfsc: get("bankIfsc") || null,
      isDefault,
    };
    const ok = await run(async () => {
      if (entity) await api("PATCH", `/api/v1/business-entities/${entity.id}`, { json: body });
      else await api("POST", "/api/v1/business-entities", { json: body });
      return true;
    });
    if (ok) {
      onClose();
      onSaved();
    }
  };

  return (
    <Modal open onClose={onClose} title={entity ? "Edit business entity" : "New business entity"}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <Field label="Legal Entity Name" required>
          <TextInput name="name" placeholder="Name, e.g. Battery Vertical Pvt Ltd" defaultValue={e.name ?? ""} required />
        </Field>
        <Field label="Address Line 1">
          <TextInput name="addressLine1" placeholder="Address line 1" defaultValue={e.addressLine1 ?? ""} />
        </Field>
        <Field label="Address Line 2">
          <TextInput name="addressLine2" placeholder="Address line 2 (optional)" defaultValue={e.addressLine2 ?? ""} />
        </Field>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label="City">
              <TextInput name="city" placeholder="City" defaultValue={e.city ?? ""} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="Postal Code">
              <TextInput name="postalCode" placeholder="Postal code" defaultValue={e.postalCode ?? ""} />
            </Field>
          </div>
        </div>
        <Field label="State">
          <SelectInput name="stateCode" placeholder="State" defaultValue={e.stateCode ?? ""} options={indianStateSelectOptions()} />
        </Field>
        <Field label="Country">
          <SelectInput name="country" placeholder="Country" defaultValue="IN" options={COUNTRY_OPTIONS} />
        </Field>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label="Tax ID / GSTIN" hint="15-digit GSTIN (e.g. 22AAAAA0000A1Z5)" htmlFor="entity-tax-id">
              <TextInput id="entity-tax-id" name="taxId" placeholder="22AAAAA0000A1Z5" defaultValue={e.taxId ?? ""} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="Company PAN" hint="10-digit PAN (e.g. AAAAA0000A)" htmlFor="entity-pan">
              <TextInput id="entity-pan" name="pan" placeholder="AAAAA0000A" defaultValue={e.pan ?? ""} />
            </Field>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label="Contact Email">
              <TextInput name="contactEmail" placeholder="Contact email (optional)" defaultValue={e.contactEmail ?? ""} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="Contact Phone">
              <TextInput name="contactPhone" placeholder="Contact phone (optional)" defaultValue={e.contactPhone ?? ""} />
            </Field>
          </div>
        </div>
        <hr className="border-[var(--border)]" />
        <p className="text-sm font-bold text-[var(--muted-foreground)]">Bank details</p>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label="Bank Name">
              <TextInput name="bankName" placeholder="Bank name (optional)" defaultValue={e.bankName ?? ""} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="Branch">
              <TextInput name="bankBranch" placeholder="Branch (optional)" defaultValue={e.bankBranch ?? ""} />
            </Field>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label="Account Number">
              <TextInput name="bankAccountNumber" placeholder="Account number (optional)" defaultValue={e.bankAccountNumber ?? ""} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="IFSC Code">
              <TextInput name="bankIfsc" placeholder="IFSC code (optional)" defaultValue={e.bankIfsc ?? ""} />
            </Field>
          </div>
        </div>
        <CheckRow label="Default entity for new POs/invoices" checked={isDefault} onChange={setIsDefault} />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Save</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function Content() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("org:write");
  const list = useApiQuery<ListResponse<Entity>>("/api/v1/business-entities", { limit: 100 });
  const entities = list.data?.data ?? [];
  const [dialog, setDialog] = useState<{ entity: Entity | null } | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [actionError, setActionError] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/business-entities"] });

  const setStatus = async (id: string, status: string) => {
    setActionError("");
    try {
      await api("PATCH", `/api/v1/business-entities/${id}`, { json: { status } });
      await refresh();
    } catch (exc) {
      setActionError(errMsg(exc));
    }
  };
  const actions = (e: Entity, cls?: string) => (
    <>
      <ActionButton size="sm" className={cls} onClick={() => setDialog({ entity: e })}>Edit</ActionButton>
      {e.status === "active" ? (
        <ActionButton size="sm" tone="danger" className={cls} onClick={() => setStatus(e.id, "inactive")}>Deactivate</ActionButton>
      ) : (
        <ActionButton size="sm" tone="ghost" className={cls} onClick={() => setStatus(e.id, "active")}>Activate</ActionButton>
      )}
    </>
  );
  const dash = (v: React.ReactNode) => v || "–";
  const location = (e: Entity) => (e.city ? `${e.city}, ${stateName(e)}` : "–");
  const isDefault = (e: Entity) => (e.isDefault ? <Pill tone="success">Default</Pill> : <span>–</span>);

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader
        eyebrow="Foundation"
        title="PO & Invoice"
        description="Simple's own legal entities"
        actions={
          canWrite && (
            <>
              <BulkUploadButton onClick={() => setBulkOpen(true)} />
              <ActionButton onClick={() => setDialog({ entity: null })}>New business entity</ActionButton>
            </>
          )
        }
      />
      <InlineError message={actionError || list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Code", "Name", "Location", "Tax Reference", "Bank", "Default", "Status", ""]} fit>
          {entities.map((e) => (
            <tr key={e.id}>
              <td>{e.code}</td>
              <td>{e.name}</td>
              <td>{location(e)}</td>
              <td>{dash(e.taxId)}</td>
              <td>{dash(bankSummary(e))}</td>
              <td>{isDefault(e)}</td>
              <td><Pill>{e.status}</Pill></td>
              <td><div className="flex gap-2">{actions(e)}</div></td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {entities.map((e) => (
          <MobileRecordCard key={e.id} actions={actions(e, "w-full justify-center")}>
            <MobileRecordRow label="Code" value={e.code} />
            <MobileRecordRow label="Name" value={e.name} />
            <MobileRecordRow label="Location" value={location(e)} />
            <MobileRecordRow label="Tax Reference" value={dash(e.taxId)} />
            <MobileRecordRow label="Bank" value={dash(bankSummary(e))} />
            <MobileRecordRow label="Default" value={isDefault(e)} />
            <MobileRecordRow label="Status" value={<Pill>{e.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      {dialog && <EntityDialog entity={dialog.entity} onClose={() => setDialog(null)} onSaved={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload business entities"
        description="Upload a CSV with one row per business entity."
        endpoint="/api/v1/business-entities/bulk-upload"
        sampleCsv={BULK_SAMPLE}
        sampleFilename="business_entity_bulk_upload_template.csv"
        errorFilename="business_entity_bulk_upload_errors.csv"
        columns={BULK_COLUMNS}
        labelHeader="Name"
        labelKey="name"
        successKey="code"
        noun="business entities"
        onCompleted={refresh}
      />
    </div>
  );
}

export default function BusinessEntitiesPage() {
  const { can } = useAuth();
  return <Shell>{can("org:read") ? <Content /> : <Forbidden permission="org:read" />}</Shell>;
}
