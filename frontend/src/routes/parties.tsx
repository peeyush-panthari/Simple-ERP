/** Party Master: vendors/customers list with create + CSV bulk upload. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { INDIAN_STATE_OPTIONS } from "@/lib/reference";

export interface PartyType {
  code: string;
  label: string;
  baseType: string;
  status: string;
}
interface Party {
  id: string;
  code: string;
  legalName: string;
  displayName?: string | null;
  type: string;
  subtype?: string | null;
  taxId?: string | null;
  paymentTerms?: string | null;
  creditUsed?: string | null;
  creditLimit?: string | null;
  currency?: string | null;
  status: string;
}

const BULK_COLUMNS = [
  "legalName", "type", "subtype", "taxId", "taxIdCountry", "paymentTerms", "currency", "creditLimit",
  "billingLine1", "billingCity", "billingStateCode", "billingPostalCode",
  "shippingLocationName", "shippingLine1", "shippingCity", "shippingStateCode", "shippingPostalCode",
  "contactName", "contactEmail", "contactPhone",
];
const BULK_SAMPLE =
  `${BULK_COLUMNS.join(",")}\n` +
  "Acme Vendor Pvt Ltd,vendor,,,,NET30,INR,50000,12 Industrial Rd,Pune,27,411001,,,,,,Raj Kumar,raj@example.com,9999900001\n" +
  "Bright Retail Ltd,customer,,,,NET15,INR,25000,88 Market St,Bengaluru,29,560001,Main Store,90 Market St,Bengaluru,29,560002,Priya S,priya@example.com,9999900002\n";

const TYPE_FILTER = [
  { value: "vendor", label: "Vendor" },
  { value: "customer", label: "Customer" },
  { value: "both", label: "Both" },
];
const STATUS_FILTER = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "blocked", label: "Blocked" },
  { value: "inactive", label: "Inactive" },
];

const stateSelect = (name: string) => <SelectInput name={name} placeholder="State" options={INDIAN_STATE_OPTIONS.map((o) => ({ value: o.value, label: `${o.value} — ${o.label}` }))} />;

function CreatePartyDialog({ open, onClose, types, onCreated }: { open: boolean; onClose: () => void; types: PartyType[]; onCreated: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const [subtype, setSubtype] = useState("");
  const subtypeMeta = types.find((t) => t.code === subtype);
  const isCustomer = subtypeMeta ? ["customer", "both"].includes(subtypeMeta.baseType) : false;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body: Record<string, unknown> = {
      legalName: get("legalName"),
      type: subtypeMeta ? subtypeMeta.baseType : "vendor",
      subtype: subtype || null,
      taxId: get("taxId") || null,
      taxIdCountry: get("taxId") ? "IN" : null,
      paymentTerms: get("paymentTerms") || null,
      currency: get("currency") || null,
      creditLimit: get("creditLimit") || "0",
      addresses: [] as unknown[],
      contacts: [] as unknown[],
    };
    if (get("addrLine1")) {
      (body.addresses as unknown[]).push({ type: "billing", line1: get("addrLine1"), city: get("addrCity"), stateCode: get("addrState") || null, postalCode: get("addrPostal") || null, country: "IN", isDefault: true });
    }
    if (isCustomer && get("shipAddrLine1")) {
      (body.addresses as unknown[]).push({ type: "shipping", label: get("shipLocationName") || null, line1: get("shipAddrLine1"), city: get("shipAddrCity"), stateCode: get("shipAddrState") || null, postalCode: get("shipAddrPostal") || null, country: "IN", isDefault: true });
    }
    if (get("contactName")) {
      (body.contacts as unknown[]).push({ name: get("contactName"), email: get("contactEmail") || null, phone: get("contactPhone") || null, isPrimary: true });
    }
    const ok = await run(async () => {
      await api("POST", "/api/v1/parties", { json: body });
      return true;
    });
    if (ok) {
      onClose();
      onCreated();
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New party">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <p className="text-sm font-bold">Core details</p>
        <TextInput name="legalName" placeholder="Legal name" required />
        <SelectInput value={subtype} onChange={(e) => setSubtype(e.target.value)} placeholder="Party label" options={types.filter((t) => t.status === "active").map((t) => ({ value: t.code, label: t.label }))} />
        <TextInput name="taxId" placeholder="Tax ID / GSTIN (optional)" />
        <TextInput name="paymentTerms" placeholder="Payment terms, e.g. NET30" />
        <div className="flex gap-2">
          <TextInput name="currency" placeholder="Currency, e.g. INR" />
          <TextInput name="creditLimit" placeholder="Credit limit" />
        </div>
        <hr className="border-[var(--border)]" />
        <p className="text-sm font-bold">Billing address (optional)</p>
        <TextInput name="addrLine1" placeholder="Address line 1" />
        <div className="flex gap-2">
          <TextInput name="addrCity" placeholder="City" />
          <TextInput name="addrPostal" placeholder="Postal code" />
        </div>
        {stateSelect("addrState")}
        {isCustomer && (
          <>
            <hr className="border-[var(--border)]" />
            <p className="text-sm font-bold">Shipping address (optional)</p>
            <TextInput name="shipLocationName" placeholder="Location name, e.g. Warehouse 2 (to tell multiple shipping addresses apart)" />
            <TextInput name="shipAddrLine1" placeholder="Address line 1" />
            <div className="flex gap-2">
              <TextInput name="shipAddrCity" placeholder="City" />
              <TextInput name="shipAddrPostal" placeholder="Postal code" />
            </div>
            {stateSelect("shipAddrState")}
          </>
        )}
        <hr className="border-[var(--border)]" />
        <p className="text-sm font-bold">Primary contact (optional)</p>
        <TextInput name="contactName" placeholder="Contact name" />
        <div className="flex gap-2">
          <TextInput name="contactEmail" placeholder="Email" />
          <TextInput name="contactPhone" placeholder="Phone" />
        </div>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>Create party</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function Content() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("party:write");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);
  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [actionError, setActionError] = useState("");

  const types = useApiQuery<{ data: PartyType[] }>("/api/v1/party-types");
  const list = useApiQuery<ListResponse<Party>>("/api/v1/parties", { page, limit: 15, q: debouncedSearch, type, status });
  const parties = list.data?.data ?? [];
  const typeLabels = Object.fromEntries((types.data?.data ?? []).map((t) => [t.code, t.label]));
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/parties"] });

  const typeLabel = (p: Party) => typeLabels[p.subtype ?? ""] || (p.type ?? "").replace(/^./, (c) => c.toUpperCase());
  const credit = (p: Party) => `${format.money(p.creditUsed, p.currency || "INR")} / ${format.money(p.creditLimit, p.currency || "INR")}`;

  const activate = async (id: string) => {
    setActionError("");
    try {
      await api("POST", `/api/v1/parties/${id}/activate`);
      await refresh();
    } catch (exc) {
      setActionError(exc instanceof Error ? exc.message : String(exc));
    }
  };
  const actions = (p: Party, cls?: string) => (
    <>
      {canWrite && p.status !== "active" && (
        <ActionButton size="sm" className={cls} onClick={() => activate(p.id)}>Activate</ActionButton>
      )}
      <Link to={`/party/${p.id}`} className={`action-btn action-btn-primary action-btn-sm ${cls ?? ""}`}>Open</Link>
    </>
  );

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader eyebrow={null} title="Party Master" />
      <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
        <input className="search-input" style={{ width: "20rem" }} placeholder="Search code, name, tax ID…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <select className="filter-select" style={{ width: "11rem" }} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All Type</option>
          {TYPE_FILTER.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select className="filter-select" style={{ width: "11rem" }} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {STATUS_FILTER.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && <ActionButton onClick={() => setCreateOpen(true)}>New party</ActionButton>}
      </div>
      <InlineError message={actionError || list.error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["Party Code", "Legal name", "Party Label", "GST No", "Terms", "Credit used / limit", "Status", ""]} fit>
          {parties.map((p) => (
            <tr key={p.id}>
              <td><Link to={`/party/${p.id}`} className="rx-link">{p.code}</Link></td>
              <td>
                <div className="flex flex-col">
                  <span className="text-sm">{p.legalName}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">{p.displayName}</span>
                </div>
              </td>
              <td><Pill>{typeLabel(p)}</Pill></td>
              <td>{p.taxId}</td>
              <td>{p.paymentTerms}</td>
              <td>{credit(p)}</td>
              <td><Pill>{p.status}</Pill></td>
              <td><div className="flex gap-2">{actions(p)}</div></td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {parties.map((p) => (
          <MobileRecordCard key={p.id} actions={actions(p, "w-full justify-center")}>
            <MobileRecordRow label="Party Code" value={<Link to={`/party/${p.id}`} className="rx-link">{p.code}</Link>} />
            <MobileRecordRow label="Legal name" value={p.legalName} />
            <MobileRecordRow label="Display name" value={p.displayName} />
            <MobileRecordRow label="Party Label" value={<Pill>{typeLabel(p)}</Pill>} />
            <MobileRecordRow label="GST No" value={p.taxId} />
            <MobileRecordRow label="Terms" value={p.paymentTerms} />
            <MobileRecordRow label="Credit used / limit" value={credit(p)} />
            <MobileRecordRow label="Status" value={<Pill>{p.status}</Pill>} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
      <div className="w-full">
        <Pagination meta={list.data?.meta} onPage={setPage} />
      </div>
      {createOpen && <CreatePartyDialog open onClose={() => setCreateOpen(false)} types={types.data?.data ?? []} onCreated={refresh} />}
      <BulkUploadDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk upload parties"
        description="Upload a CSV with one row per party (vendor or customer)."
        endpoint="/api/v1/parties/bulk-upload"
        sampleCsv={BULK_SAMPLE}
        sampleFilename="party_bulk_upload_template.csv"
        errorFilename="party_bulk_upload_errors.csv"
        columns={BULK_COLUMNS}
        labelHeader="Legal name"
        labelKey="legalName"
        successKey="partyCode"
        noun="parties"
        onCompleted={refresh}
      />
    </div>
  );
}

export default function PartiesPage() {
  const { can } = useAuth();
  return <Shell>{can("party:read") ? <Content /> : <Forbidden permission="party:read" />}</Shell>;
}
