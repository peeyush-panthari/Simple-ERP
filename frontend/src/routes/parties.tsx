/** Party Master: vendors/customers list with create + CSV bulk upload. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BulkUploadButton, BulkUploadDialog } from "@/components/erp/bulk-upload";
import { GuidedFieldWalkthrough } from "@/components/erp/guided-field-walkthrough";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Pagination, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useDemoTour } from "@/lib/demo-flow-context";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";
import { indianStateSelectOptions } from "@/lib/reference";
import { cn, errMsg } from "@/lib/utils";

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

const stateSelect = (name: string) => <SelectInput name={name} placeholder="State" options={indianStateSelectOptions()} />;

function CreatePartyDialog({ open, onClose, types, onCreated }: { open: boolean; onClose: () => void; types: PartyType[]; onCreated: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep1 = isTourActive && activeJourneyId === "procure-to-pay" && currentJourneyStepIndex === 0;

  const [activeWalkthroughField, setActiveWalkthroughField] = useState("legalName");
  const [legalName, setLegalName] = useState("");
  const [subtype, setSubtype] = useState("");
  const [taxId, setTaxId] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("NET30");
  const [currency, setCurrency] = useState("INR");
  const [creditLimit, setCreditLimit] = useState("1000000");
  const [addrLine1, setAddrLine1] = useState("");
  const [addrCity, setAddrCity] = useState("");
  const [addrPostal, setAddrPostal] = useState("");
  const [addrState, setAddrState] = useState("27");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");

  const subtypeMeta = types.find((t) => t.code === subtype);
  const isCustomer = subtypeMeta ? ["customer", "both"].includes(subtypeMeta.baseType) : false;

  const autofillDemoVendor = () => {
    setLegalName("Simple Precision Components Pvt Ltd");
    const vendorType = types.find((t) => t.baseType === "vendor") || types[0];
    if (vendorType) setSubtype(vendorType.code);
    setTaxId("27AAACA1234A1Z5");
    setPaymentTerms("NET30");
    setCurrency("INR");
    setCreditLimit("1000000");
    setAddrLine1("Plot 12, Chakan Industrial Phase 2");
    setAddrCity("Pune");
    setAddrState("27");
    setAddrPostal("410501");
    setContactName("Rajesh Kulkarni");
    setContactEmail("rajesh.k@simpleprecision.com");
    setContactPhone("+91-98220-44123");
  };

  const walkthroughFields = [
    {
      id: "legalName",
      label: "Legal Commercial Entity Name",
      shortLabel: "Legal Name",
      useCase: "Primary corporate identity printed on vendor contracts, purchase orders, statutory e-Invoices, and bank remittance vouchers.",
      guideline: "Full registered legal title (e.g. Simple Precision Components Pvt Ltd).",
      restriction: "Required field. Must match official GST and banking tax registration.",
      sampleValueText: "Simple Precision Components Pvt Ltd",
      isFilled: Boolean(legalName),
      onFill: () => setLegalName("Simple Precision Components Pvt Ltd"),
    },
    {
      id: "subtype",
      label: "Commercial Master Classification",
      shortLabel: "Party Type",
      useCase: "Governs transactional permissions: ensures vendors can be selected on POs and AP vouchers, while customers are restricted to sales orders.",
      guideline: "Select an active Vendor party label.",
      restriction: "Required for correct general ledger subledger categorization.",
      sampleValueText: types.find((t) => t.baseType === "vendor")?.label || "Vendor",
      isFilled: Boolean(subtype),
      onFill: () => {
        const v = types.find((t) => t.baseType === "vendor") || types[0];
        if (v) setSubtype(v.code);
      },
    },
    {
      id: "taxId",
      label: "Statutory Tax Identification (15-digit GSTIN)",
      shortLabel: "Tax ID / GSTIN",
      useCase: "Enables statutory CGST/SGST/IGST tax calculation, electronic invoice validation, and GST input tax credit (ITC) matching.",
      guideline: "15-character uppercase Indian GSTIN with state prefix (e.g. 27AAACA1234A1Z5 for Maharashtra).",
      restriction: "Determines tax jurisdiction for intra-state (CGST+SGST) vs inter-state (IGST).",
      sampleValueText: "27AAACA1234A1Z5",
      isFilled: Boolean(taxId),
      onFill: () => setTaxId("27AAACA1234A1Z5"),
    },
    {
      id: "paymentTerms",
      label: "Trade Payment Terms & Credit Limit",
      shortLabel: "Payment Terms",
      useCase: "Controls Accounts Payable invoice due dates, cash discount windows, and overdue aging schedules.",
      guideline: "Enter agreed trade credit duration (e.g. NET30, NET45, Advance).",
      restriction: "Used by AP payment run to schedule disbursement dates.",
      sampleValueText: "NET30 (₹10,00,000 Credit)",
      isFilled: Boolean(paymentTerms),
      onFill: () => {
        setPaymentTerms("NET30");
        setCurrency("INR");
        setCreditLimit("1000000");
      },
    },
    {
      id: "billingAddress",
      label: "Registered Manufacturing & Dispatch Site",
      shortLabel: "Address & State",
      useCase: "Physical plant dispatch address for delivery challans, PO dispatch, and statutory GST place-of-supply determination.",
      guideline: "Industrial park address, city, state code 27 (Maharashtra), and 6-digit postal code.",
      restriction: "State code must match the first 2 digits of the GSTIN.",
      sampleValueText: "Chakan Industrial Zone, Pune, State 27",
      isFilled: Boolean(addrLine1 && addrCity && addrState),
      onFill: () => {
        setAddrLine1("Plot 12, Chakan Industrial Phase 2");
        setAddrCity("Pune");
        setAddrState("27");
        setAddrPostal("410501");
        setContactName("Rajesh Kulkarni");
        setContactEmail("rajesh.k@simpleprecision.com");
      },
    },
  ];

  const allWalkthroughFilled = Boolean(legalName && subtype && taxId);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const finalLegalName = legalName || get("legalName");
    const finalSubtype = subtype || get("subtype");
    const finalTaxId = taxId || get("taxId");
    const finalTerms = paymentTerms || get("paymentTerms") || null;
    const finalCurrency = currency || get("currency") || null;
    const finalCredit = creditLimit || get("creditLimit") || "0";
    const finalLine1 = addrLine1 || get("addrLine1");
    const finalCity = addrCity || get("addrCity");
    const finalState = addrState || get("addrState");
    const finalPostal = addrPostal || get("addrPostal");
    const finalContact = contactName || get("contactName");
    const finalEmail = contactEmail || get("contactEmail");
    const finalPhone = contactPhone || get("contactPhone");

    const body: Record<string, unknown> = {
      legalName: finalLegalName,
      type: subtypeMeta ? subtypeMeta.baseType : "vendor",
      subtype: finalSubtype || null,
      taxId: finalTaxId || null,
      taxIdCountry: finalTaxId ? "IN" : null,
      paymentTerms: finalTerms,
      currency: finalCurrency,
      creditLimit: finalCredit,
      addresses: [] as unknown[],
      contacts: [] as unknown[],
    };
    if (finalLine1) {
      (body.addresses as unknown[]).push({ type: "billing", line1: finalLine1, city: finalCity, stateCode: finalState || null, postalCode: finalPostal || null, country: "IN", isDefault: true });
    }
    if (isCustomer && get("shipAddrLine1")) {
      (body.addresses as unknown[]).push({ type: "shipping", label: get("shipLocationName") || null, line1: get("shipAddrLine1"), city: get("shipAddrCity"), stateCode: get("shipAddrState") || null, postalCode: get("shipAddrPostal") || null, country: "IN", isDefault: true });
    }
    if (finalContact) {
      (body.contacts as unknown[]).push({ name: finalContact, email: finalEmail || null, phone: finalPhone || null, isPrimary: true });
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
        {isTourStep1 && (
          <GuidedFieldWalkthrough
            dialogTitle="Commercial Vendor Onboarding"
            fields={walkthroughFields}
            activeFieldId={activeWalkthroughField}
            onSelectField={setActiveWalkthroughField}
            onFillAll={autofillDemoVendor}
            allFilled={allWalkthroughFilled}
            submitButtonLabel="Add party"
            stepBadgeNumber={2}
            nextStepBadgeNumber={3}
          />
        )}
        <p className="text-sm font-bold">Core details</p>
        <div className={cn(isTourStep1 && activeWalkthroughField === "legalName" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <TextInput
            name="legalName"
            placeholder="Legal name"
            value={legalName}
            onFocus={() => setActiveWalkthroughField("legalName")}
            onChange={(e) => setLegalName(e.target.value)}
            required
          />
        </div>
        <div className={cn(isTourStep1 && activeWalkthroughField === "subtype" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <SelectInput
            value={subtype}
            onFocus={() => setActiveWalkthroughField("subtype")}
            onChange={(e) => setSubtype(e.target.value)}
            placeholder="Party label"
            options={types.filter((t) => t.status === "active").map((t) => ({ value: t.code, label: t.label }))}
          />
        </div>
        <div className={cn(isTourStep1 && activeWalkthroughField === "taxId" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all")}>
          <Field label="Tax Identification (GSTIN / PAN)" hint="15-digit state GSTIN (e.g. 22AAAAA0000A1Z5) or 10-digit PAN (e.g. AAAAA0000A)" htmlFor="party-tax-id">
            <TextInput
              id="party-tax-id"
              name="taxId"
              placeholder="22AAAAA0000A1Z5"
              value={taxId}
              onFocus={() => setActiveWalkthroughField("taxId")}
              onChange={(e) => setTaxId(e.target.value)}
            />
          </Field>
        </div>
        <div className={cn(isTourStep1 && activeWalkthroughField === "paymentTerms" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-2")}>
          <TextInput
            name="paymentTerms"
            placeholder="Payment terms, e.g. NET30"
            value={paymentTerms}
            onFocus={() => setActiveWalkthroughField("paymentTerms")}
            onChange={(e) => setPaymentTerms(e.target.value)}
          />
          <div className="flex gap-2">
            <TextInput
              name="currency"
              placeholder="Currency, e.g. INR"
              value={currency}
              onFocus={() => setActiveWalkthroughField("paymentTerms")}
              onChange={(e) => setCurrency(e.target.value)}
            />
            <TextInput
              name="creditLimit"
              placeholder="Credit limit"
              value={creditLimit}
              onFocus={() => setActiveWalkthroughField("paymentTerms")}
              onChange={(e) => setCreditLimit(e.target.value)}
            />
          </div>
        </div>
        <hr className="border-[var(--border)]" />
        <p className="text-sm font-bold">Billing address (optional)</p>
        <div className={cn(isTourStep1 && activeWalkthroughField === "billingAddress" && "rounded-lg p-1 ring-2 ring-teal-500 bg-teal-500/5 transition-all space-y-2")}>
          <TextInput
            name="addrLine1"
            placeholder="Address line 1"
            value={addrLine1}
            onFocus={() => setActiveWalkthroughField("billingAddress")}
            onChange={(e) => setAddrLine1(e.target.value)}
          />
          <div className="flex gap-2">
            <TextInput
              name="addrCity"
              placeholder="City"
              value={addrCity}
              onFocus={() => setActiveWalkthroughField("billingAddress")}
              onChange={(e) => setAddrCity(e.target.value)}
            />
            <TextInput
              name="addrPostal"
              placeholder="Postal code"
              value={addrPostal}
              onFocus={() => setActiveWalkthroughField("billingAddress")}
              onChange={(e) => setAddrPostal(e.target.value)}
            />
          </div>
          <SelectInput
            name="addrState"
            placeholder="State"
            value={addrState}
            onFocus={() => setActiveWalkthroughField("billingAddress")}
            onChange={(e) => setAddrState(e.target.value)}
            options={indianStateSelectOptions()}
          />
        </div>
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
        <TextInput name="contactName" placeholder="Contact name" value={contactName} onChange={(e) => setContactName(e.target.value)} />
        <div className="flex gap-2">
          <TextInput name="contactEmail" placeholder="Contact email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
          <TextInput name="contactPhone" placeholder="Contact phone" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
        </div>
        <div className="flex justify-end gap-2 items-center pt-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <div className="relative">
            {isTourStep1 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  3
                </span>
              </span>
            )}
            <ActionButton
              type="submit"
              tone={isTourStep1 ? "primary" : undefined}
              loading={busy}
              className={cn(isTourStep1 && allWalkthroughFilled && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              Add party
            </ActionButton>
          </div>
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
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourStep1 = isTourActive && activeJourneyId === "procure-to-pay" && currentJourneyStepIndex === 0;

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
      setActionError(errMsg(exc));
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
        <label htmlFor="party-search-input" className="sr-only">Search code, name, tax ID</label>
        <input id="party-search-input" className="search-input" style={{ width: "20rem" }} placeholder="Search code, name, tax ID…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <label htmlFor="party-type-filter" className="sr-only">Filter by party type</label>
        <select id="party-type-filter" className="filter-select" style={{ width: "11rem" }} value={type} aria-label="Filter by All Type" onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All Type</option>
          {TYPE_FILTER.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <label htmlFor="party-status-filter" className="sr-only">Filter by status</label>
        <select id="party-status-filter" className="filter-select" style={{ width: "11rem" }} value={status} aria-label="Filter by All Status" onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          {STATUS_FILTER.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div className="flex-1" />
        {canWrite && <BulkUploadButton onClick={() => setBulkOpen(true)} />}
        {canWrite && (
          <div className="relative">
            {isTourStep1 && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 z-10 pointer-events-none">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-teal-500 text-[10px] font-bold text-white items-center justify-center shadow-md">
                  1
                </span>
              </span>
            )}
            <ActionButton
              onClick={() => setCreateOpen(true)}
              tone={isTourStep1 ? "primary" : undefined}
              className={cn(isTourStep1 && "ring-2 ring-teal-500 ring-offset-2 shadow-lg animate-pulse")}
            >
              New party
            </ActionButton>
          </div>
        )}
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
