/** Party detail: core details, addresses, contacts, bank accounts, block/unblock. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, PageHeader, Panel, Pill, SelectInput, StatCard, TextArea, TextInput } from "@/components/erp/ui";
import type { PartyType } from "@/routes/parties";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction } from "@/lib/hooks";
import { INDIAN_STATE_NAMES, INDIAN_STATE_OPTIONS } from "@/lib/reference";

interface Address { id: string; type: string; label?: string | null; line1: string; city: string; stateCode?: string | null; postalCode?: string | null; isDefault?: boolean }
interface Contact { id: string; name: string; email?: string | null; phone?: string | null; isPrimary?: boolean }
interface Bank { id: string; accountName: string; bankName?: string | null; ifsc?: string | null; accountNumberMasked?: string | null; status: string }
interface PartyDetail {
  id: string; code: string; legalName: string; type: string; subtype?: string | null; status: string; taxId?: string | null;
  paymentTerms?: string | null; currency?: string | null; creditLimit?: string | null; creditUsed?: string | null; riskFlag?: string | null;
  addresses?: Address[]; contacts?: Contact[]; bankAccounts?: Bank[];
}

interface VendorScorecard {
  vendorId: string;
  vendorName: string;
  period: string;
  overallScore: number | string;
  otifScore: number | string;
  qualityScore: number | string;
  priceScore: number | string;
  grade: string;
  gradeLabel: string;
  totalPos: number;
  totalGrns: number;
  totalLinesReceived: number;
  totalLinesAccepted: number;
  totalLinesRejected: number;
  calculatedAt: string;
}

function VendorScorecardSection({ vendorId }: { vendorId: string }) {
  const scorecardQuery = useApiQuery<VendorScorecard>(`/api/v1/supplier-scorecards/vendor/${vendorId}`);
  const data = scorecardQuery.data;
  if (!data) return null;

  const tone = data.grade === "A" ? "success" : data.grade === "B" ? "info" : data.grade === "C" ? "warning" : "destructive";

  return (
    <Panel
      title="Supplier Performance Scorecard"
      aside={
        <Pill tone={tone}>
          Tier {data.grade}: {data.gradeLabel} ({data.overallScore}%)
        </Pill>
      }
    >
      <div className="flex w-full flex-col gap-3 px-4 py-3">
        <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Overall Score" value={`${data.overallScore}%`} />
          <StatCard label="OTIF (Delivery)" value={`${data.otifScore}%`} />
          <StatCard label="QC Acceptance" value={`${data.qualityScore}%`} />
          <StatCard label="Price Adherence" value={`${data.priceScore}%`} />
        </div>
        <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4 text-xs text-[var(--muted-foreground)]">
          <div><span className="font-semibold text-[var(--foreground)]">{data.totalPos}</span> Purchase Orders Placed</div>
          <div><span className="font-semibold text-[var(--foreground)]">{data.totalGrns}</span> Shipments Received</div>
          <div><span className="font-semibold text-emerald-600">{data.totalLinesAccepted}</span> Units Accepted at QC</div>
          <div><span className="font-semibold text-rose-600">{data.totalLinesRejected}</span> Units Rejected at QC</div>
        </div>
      </div>
    </Panel>
  );
}

function CoreDetails({ party, types, canWrite, onSaved }: { party: PartyDetail; types: PartyType[]; canWrite: boolean; onSaved: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const [subtype, setSubtype] = useState(party.subtype ?? "");
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const ok = await run(async () => {
      await api("PATCH", `/api/v1/parties/${party.id}`, {
        json: { legalName: get("legalName") || party.legalName, subtype: subtype || null, taxId: get("taxId") || null, paymentTerms: get("paymentTerms") || null, currency: get("currency") || null, creditLimit: get("creditLimit") || "0" },
      });
      return true;
    });
    if (ok) onSaved();
  };
  const cur = party.currency || "INR";
  return (
    <Panel title="Core details">
      <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
        <InlineError message={error} />
        <form onSubmit={submit} className="flex w-full flex-col items-start gap-3" key={party.id + (party.legalName ?? "")}>
          <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <Field label="Legal name"><TextInput name="legalName" defaultValue={party.legalName} disabled={!canWrite} /></Field>
            <Field label="Party label">
              <SelectInput value={subtype} onChange={(e) => setSubtype(e.target.value)} disabled={!canWrite} placeholder="Party label" options={types.filter((t) => t.status === "active").map((t) => ({ value: t.code, label: t.label }))} />
            </Field>
            <Field label="Tax ID / GSTIN"><TextInput name="taxId" defaultValue={party.taxId ?? ""} disabled={!canWrite} /></Field>
            <Field label="Payment terms"><TextInput name="paymentTerms" placeholder="e.g. NET30" defaultValue={party.paymentTerms ?? ""} disabled={!canWrite} /></Field>
            <Field label="Currency"><TextInput name="currency" placeholder="e.g. INR" defaultValue={party.currency ?? ""} disabled={!canWrite} /></Field>
            <Field label="Credit limit"><TextInput name="creditLimit" defaultValue={party.creditLimit ?? ""} disabled={!canWrite} /></Field>
            <StatCard label="Credit used" value={format.money(party.creditUsed, cur)} />
            <StatCard label="Risk" value={party.riskFlag} />
          </div>
          {canWrite && <ActionButton type="submit" loading={busy}>Save changes</ActionButton>}
        </form>
      </div>
    </Panel>
  );
}

/** A small "add a child record" dialog: a form that POSTs to /parties/{id}/{path} and refreshes the party. */
function AddDialog({ title, submitLabel, path, partyId, buildBody, onClose, onAdded, children, gridClass }: { title: string; submitLabel: string; path: string; partyId: string; buildBody: (get: (k: string) => string) => unknown; onClose: () => void; onAdded: () => void; children: React.ReactNode; gridClass: string }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const ok = await run(async () => {
      await api("POST", `/api/v1/parties/${partyId}/${path}`, { json: buildBody((k) => String(f.get(k) ?? "")) });
      return true;
    });
    if (ok) {
      onClose();
      onAdded();
    }
  };
  return (
    <Modal open onClose={onClose} title={title}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <div className={gridClass}>{children}</div>
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton>
          <ActionButton type="submit" loading={busy}>{submitLabel}</ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function Content({ id }: { id: string }) {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("party:write");
  const canBlock = can("party:block");
  const partyQuery = useApiQuery<PartyDetail>(`/api/v1/parties/${id}`);
  const types = useApiQuery<{ data: PartyType[] }>("/api/v1/party-types");
  const party = partyQuery.data;
  const [dialog, setDialog] = useState<"" | "block" | "address" | "contact" | "bank">("");
  const [pageError, setPageError] = useState("");
  const block = useAsyncAction();
  const refresh = () => qc.invalidateQueries({ queryKey: [`/api/v1/parties/${id}`] });

  const act = async (fn: () => Promise<unknown>) => {
    setPageError("");
    try {
      await fn();
      await refresh();
    } catch (exc) {
      setPageError(exc instanceof Error ? exc.message : String(exc));
    }
  };
  const submitBlock = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const reason = String(new FormData(e.currentTarget).get("reason") ?? "");
    const ok = await block.run(async () => {
      await api("POST", `/api/v1/parties/${id}/block`, { json: { reason } });
      return true;
    });
    if (ok) {
      setDialog("");
      await refresh();
    }
  };

  const yes = (v: boolean | undefined, label: string) => (v ? <Pill>{label}</Pill> : "");
  const addresses = party?.addresses ?? [];
  const contacts = party?.contacts ?? [];
  const banks = party?.bankAccounts ?? [];
  const stateName = (a: Address) => INDIAN_STATE_NAMES[a.stateCode ?? ""] ?? a.stateCode ?? "";
  const bankLine = (b: Bank) => `${b.bankName} / ${b.ifsc}`;

  return (
    <div className="party-detail-page flex w-full flex-col items-start gap-2">
      <Link to="/parties" className="rx-link">← Back to parties</Link>
      <InlineError message={pageError || partyQuery.error?.message} />
      {!party ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
      ) : (
        <>
          <div>
            <PageHeader
              fit
              eyebrow={null}
              title={party.legalName}
              titleSuffix={<span className="text-sm font-normal text-[var(--muted-foreground)]">{party.type} · {party.code}</span>}
              actions={
                <>
                  <Pill>{party.status}</Pill>
                  {canWrite && party.status !== "active" && <ActionButton onClick={() => act(() => api("POST", `/api/v1/parties/${id}/activate`))}>Activate</ActionButton>}
                  {canBlock && party.status === "active" && <ActionButton onClick={() => { block.setError(""); setDialog("block"); }}>Block</ActionButton>}
                  {canBlock && party.status === "blocked" && <ActionButton onClick={() => act(() => api("POST", `/api/v1/parties/${id}/unblock`, { json: { reason: "Unblocked from the party detail page" } }))}>Unblock</ActionButton>}
                </>
              }
            />
          </div>
          <div><CoreDetails party={party} types={types.data?.data ?? []} canWrite={canWrite} onSaved={refresh} /></div>

          <div>
            <Panel title="Addresses" aside={canWrite && <ActionButton size="sm" onClick={() => setDialog("address")}>Add address</ActionButton>}>
              <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
                <DesktopOnly className="w-full">
                  <DataTable columns={["Type", "Location name", "Address", "City", "State", "Postal code", "Default"]} fit>
                    {addresses.map((a) => (
                      <tr key={a.id}><td>{a.type}</td><td>{a.label}</td><td>{a.line1}</td><td>{a.city}</td><td>{stateName(a)}</td><td>{a.postalCode}</td><td>{yes(a.isDefault, "default")}</td></tr>
                    ))}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {addresses.map((a) => (
                    <MobileRecordCard key={a.id}>
                      <MobileRecordRow label="Type" value={a.type} /><MobileRecordRow label="Location name" value={a.label} /><MobileRecordRow label="Address" value={a.line1} />
                      <MobileRecordRow label="City" value={a.city} /><MobileRecordRow label="State" value={stateName(a)} /><MobileRecordRow label="Postal code" value={a.postalCode} />
                      <MobileRecordRow label="Default" value={yes(a.isDefault, "default")} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </div>
            </Panel>
          </div>

          <div className="grid w-full grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
            <Panel title="Contacts" aside={canWrite && <ActionButton size="sm" onClick={() => setDialog("contact")}>Add contact</ActionButton>}>
              <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
                <DesktopOnly className="w-full">
                  <DataTable columns={["Name", "Email", "Phone", "Primary"]} fit>
                    {contacts.map((c) => <tr key={c.id}><td>{c.name}</td><td>{c.email}</td><td>{c.phone}</td><td>{yes(c.isPrimary, "primary")}</td></tr>)}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {contacts.map((c) => (
                    <MobileRecordCard key={c.id}>
                      <MobileRecordRow label="Name" value={c.name} /><MobileRecordRow label="Email" value={c.email} /><MobileRecordRow label="Phone" value={c.phone} /><MobileRecordRow label="Primary" value={yes(c.isPrimary, "primary")} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </div>
            </Panel>
            <Panel title="Bank accounts" aside={canWrite && <ActionButton size="sm" onClick={() => setDialog("bank")}>Add bank account</ActionButton>}>
              <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
                <DesktopOnly className="w-full">
                  <DataTable columns={["Account", "Bank / IFSC", "Number", "Status"]} fit>
                    {banks.map((b) => <tr key={b.id}><td>{b.accountName}</td><td>{bankLine(b)}</td><td>{b.accountNumberMasked}</td><td><Pill>{b.status}</Pill></td></tr>)}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="w-full">
                  {banks.map((b) => (
                    <MobileRecordCard key={b.id}>
                      <MobileRecordRow label="Account" value={b.accountName} /><MobileRecordRow label="Bank / IFSC" value={bankLine(b)} /><MobileRecordRow label="Number" value={b.accountNumberMasked} /><MobileRecordRow label="Status" value={<Pill>{b.status}</Pill>} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
              </div>
            </Panel>
            {(party.type === "vendor" || party.type === "both") && (
              <VendorScorecardSection vendorId={party.id} />
            )}
          </div>

          <Modal open={dialog === "block"} onClose={() => setDialog("")} title="Block this party">
            <form onSubmit={submitBlock} className="flex flex-col gap-3">
              <InlineError message={block.error} />
              <TextArea name="reason" placeholder="Reason (min 5 characters)" required />
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setDialog("")}>Cancel</ActionButton>
                <ActionButton tone="danger" type="submit" loading={block.busy}>Block party</ActionButton>
              </div>
            </form>
          </Modal>

          {dialog === "address" && (
            <AddDialog title="Add address" submitLabel="Add address" path="addresses" partyId={id} onClose={() => setDialog("")} onAdded={refresh} gridClass="grid w-full grid-cols-1 gap-2 sm:grid-cols-2"
              buildBody={(g) => ({ type: g("type") || "billing", label: g("label") || null, line1: g("line1"), city: g("city"), stateCode: g("stateCode") || null, postalCode: g("postalCode") || null, country: g("country") || "IN", isDefault: false })}>
              <SelectInput name="type" defaultValue="billing" options={["billing", "shipping", "registered"].map((v) => ({ value: v, label: v }))} />
              <TextInput name="label" placeholder="Location name, e.g. Warehouse 2 (optional)" />
              <TextInput name="line1" placeholder="Address line 1" required />
              <TextInput name="city" placeholder="City" required />
              <SelectInput name="stateCode" placeholder="State" options={INDIAN_STATE_OPTIONS.map((o) => ({ value: o.value, label: `${o.value} — ${o.label}` }))} />
              <TextInput name="postalCode" placeholder="Postal code" />
            </AddDialog>
          )}
          {dialog === "contact" && (
            <AddDialog title="Add contact" submitLabel="Add contact" path="contacts" partyId={id} onClose={() => setDialog("")} onAdded={refresh} gridClass="grid w-full grid-cols-1 gap-2 sm:grid-cols-3"
              buildBody={(g) => ({ name: g("name"), role: g("role") || null, email: g("email") || null, phone: g("phone") || null, isPrimary: false })}>
              <TextInput name="name" placeholder="Contact name" required />
              <TextInput name="email" placeholder="Email" />
              <TextInput name="phone" placeholder="Phone" />
            </AddDialog>
          )}
          {dialog === "bank" && (
            <AddDialog title="Add bank account" submitLabel="Add bank account" path="bank-accounts" partyId={id} onClose={() => setDialog("")} onAdded={refresh} gridClass="grid w-full grid-cols-1 gap-2 sm:grid-cols-2"
              buildBody={(g) => ({ accountName: g("accountName"), accountNumber: g("accountNumber"), ifsc: g("ifsc") || null, swift: g("swift") || null, bankName: g("bankName"), branch: g("branch") || null })}>
              <TextInput name="accountName" placeholder="Account holder name" required />
              <TextInput name="accountNumber" placeholder="Account number" required />
              <TextInput name="bankName" placeholder="Bank name" required />
              <TextInput name="ifsc" placeholder="IFSC (domestic)" />
              <TextInput name="swift" placeholder="SWIFT (international)" />
            </AddDialog>
          )}
        </>
      )}
    </div>
  );
}

export default function PartyDetailPage() {
  const { can } = useAuth();
  const { partyId = "" } = useParams();
  return <Shell>{can("party:read") ? <Content id={partyId} /> : <Forbidden permission="party:read" />}</Shell>;
}
