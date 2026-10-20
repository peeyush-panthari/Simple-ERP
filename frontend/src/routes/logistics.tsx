/** Logistics: transport requests with RFQs, quotes, awarding, dispatch and proof of delivery. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";
import { GuidedFieldWalkthrough } from "@/components/erp/guided-field-walkthrough";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Field, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Pagination, Pill, StatCard, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useDemoTour } from "@/lib/demo-flow-context";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface Request {
  id: string;
  number: string;
  lane: string;
  orderNumber?: string | null;
  status: string;
  rfqCount?: number;
  bestQuote?: string | null;
  awardedCarrier?: string | null;
  source?: string;
  overrideReason?: string | null;
  rfqs?: Rfq[];
  dispatches?: Dispatch[];
}
interface Rfq {
  id: string;
  number: string;
  status: string;
  dueAt?: string | null;
  quotations?: Quote[];
}
interface Quote {
  id: string;
  carrierName: string;
  amount: string;
  transitDays?: number | null;
  validUntil?: string | null;
  status: string;
}
interface Dispatch {
  id: string;
  number: string;
  carrierName: string;
  status: string;
  dispatchedAt?: string | null;
  podUrl?: string | null;
}

const STATUSES = ["pending", "rfq_sent", "quotation_received", "approved", "dispatched", "delivered", "cancelled"];

// ---- small dialogs ---------------------------------------------------------------------------------

function RfqDialog({ requestId, onClose, onDone }: { requestId: string; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const [text, setText] = useState("");
  const ids = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ids.length) return setError("Select at least one carrier");
    const ok = await run(async () => { await api("POST", `/api/v1/transport-requests/${requestId}/rfq`, { json: { carrierIds: ids } }); return true; });
    if (ok) { onClose(); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title="Send RFQ" description="Enter carrier (vendor party) IDs to invite, one per line.">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        {ids.length === 1 && <Note tone="warning">A single-carrier RFQ has no competitive tension and won&apos;t be awardable without a justification.</Note>}
        <TextArea rows={4} placeholder="One carrier (vendor party) ID per line" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton type="submit" loading={busy}>Send RFQ</ActionButton></div>
      </form>
    </Modal>
  );
}

function QuoteDialog({ rfqId, onClose, onDone }: { rfqId: string; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const { run, busy, error } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const body: Record<string, unknown> = { carrierId: get("carrierId"), amount: get("amount") };
    if (get("transitDays")) body.transitDays = parseInt(get("transitDays"), 10);
    if (get("validUntil")) body.validUntil = get("validUntil");
    const ok = await run(async () => { await api("POST", `/api/v1/rfqs/${rfqId}/quotes`, { json: body }); return true; });
    if (ok) { onClose(); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title="Record a quote">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="carrierId" placeholder="Carrier (vendor party) ID" required />
        <TextInput name="amount" placeholder="Amount" required />
        <TextInput name="transitDays" placeholder="Transit days (optional)" />
        <TextInput name="validUntil" type="date" placeholder="Valid until (optional)" />
        <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton type="submit" loading={busy}>Record quote</ActionButton></div>
      </form>
    </Modal>
  );
}

function PodDialog({ dispatchId, onClose, onDone }: { dispatchId: string; onClose: () => void; onDone: () => void }) {
  const { api } = useAuth();
  const { run, busy, error, setError } = useAsyncAction();
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const receivedBy = String(f.get("receivedBy") ?? "");
    if (receivedBy.length < 2) return setError("Received-by name must be at least 2 characters");
    const ok = await run(async () => { await api("POST", `/api/v1/dispatches/${dispatchId}/pod`, { json: { podUrl: String(f.get("podUrl") ?? ""), receivedBy } }); return true; });
    if (ok) { onClose(); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title="Record proof of delivery">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        <TextInput name="podUrl" placeholder="POD document URL" required />
        <TextInput name="receivedBy" placeholder="Received by (name)" required />
        <div className="flex justify-end gap-2"><ActionButton tone="ghost" onClick={onClose}>Cancel</ActionButton><ActionButton type="submit" loading={busy}>Record delivery</ActionButton></div>
      </form>
    </Modal>
  );
}

function GateEntryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourGateStep = isTourActive && activeJourneyId === "inventory-management" && currentJourneyStepIndex === 0;

  const [vehicleNumber, setVehicleNumber] = useState("");
  const [supplierAsn, setSupplierAsn] = useState("");
  const [driverName, setDriverName] = useState("");
  const [assignedDock, setAssignedDock] = useState("");
  const [grossWeight, setGrossWeight] = useState("");
  const [activeStepKey, setActiveStepKey] = useState("vehicleNumber");
  const [submitted, setSubmitted] = useState(false);

  const fields = [
    {
      key: "vehicleNumber",
      label: "Vehicle Registration Number",
      required: true,
      sampleValue: "MH-12-AB-1234",
      useCase: "Commercial carrier transport vehicle crossing the factory gate security perimeter.",
      guidelines: "Must match the vehicle registration number declared on the carrier e-Way bill and supplier ASN.",
      onFill: () => setVehicleNumber("MH-12-AB-1234"),
    },
    {
      key: "supplierAsn",
      label: "Supplier ASN / PO Reference",
      required: true,
      sampleValue: "ASN-1092 (Acme Copper Ltd / PO-9002)",
      useCase: "Validates active supplier dispatch against an authorized Simple ERP Purchase Order.",
      guidelines: "Gate entry is rejected if no active PO commitment exists in the system.",
      onFill: () => setSupplierAsn("ASN-1092 (Acme Copper Ltd / PO-9002)"),
    },
    {
      key: "driverName",
      label: "Driver Name & Mobile Contact",
      required: true,
      sampleValue: "Ramesh Kumar (+91 98765 43210)",
      useCase: "Captures carrier custodian identity for facility security and statutory gate pass audit.",
      guidelines: "Driver phone number is required for dock SMS paging when unload bay clears.",
      onFill: () => setDriverName("Ramesh Kumar (+91 98765 43210)"),
    },
    {
      key: "assignedDock",
      label: "Designated Unloading Dock",
      required: true,
      sampleValue: "Dock Bay 3 - Inbound Quarantine",
      useCase: "Directs incoming heavy trailer directly to the correct dock door to prevent yard congestion.",
      guidelines: "Assigned based on SKU category (bulk metals vs delicate electronics vs HAZMAT).",
      onFill: () => setAssignedDock("Dock Bay 3 - Inbound Quarantine"),
    },
    {
      key: "grossWeight",
      label: "Weighbridge Inward Weight (kg)",
      required: true,
      sampleValue: "14,250",
      useCase: "First physical weight check to detect en-route material pilferage or wet weather tampering.",
      guidelines: "Net weight variance > 0.5% vs packing slip triggers immediate QC supervisor hold.",
      onFill: () => setGrossWeight("14,250"),
    },
  ];

  const handleFillAll = () => {
    setVehicleNumber("MH-12-AB-1234");
    setSupplierAsn("ASN-1092 (Acme Copper Ltd / PO-9002)");
    setDriverName("Ramesh Kumar (+91 98765 43210)");
    setAssignedDock("Dock Bay 3 - Inbound Quarantine");
    setGrossWeight("14,250");
  };

  const isComplete = Boolean(
    vehicleNumber.trim() &&
    supplierAsn.trim() &&
    driverName.trim() &&
    assignedDock.trim() &&
    grossWeight.trim()
  );

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!isComplete) return;
    setSubmitted(true);
  };

  if (!open) return null;

  return (
    <Modal
      open
      onClose={onClose}
      wide
      title="Inbound Gate Check-In & Security Pass"
      description="Record carrier arrival, verify Advance Shipping Notice (ASN), and assign dock bay for intake."
    >
      {submitted ? (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 mb-3">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-bold text-[var(--foreground)]">Gate Pass GP-1092 Issued</h3>
          <p className="mt-1 text-sm text-[var(--muted-foreground)] max-w-md">
            Vehicle <strong className="text-[var(--foreground)]">{vehicleNumber}</strong> successfully checked in at Gate 2.
            Carrier routed to <strong className="text-[var(--foreground)]">{assignedDock}</strong> for Goods Receipt Note (GRN) generation.
          </p>
          <div className="mt-6 flex gap-3">
            <ActionButton tone="primary" onClick={onClose}>Done</ActionButton>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {isTourGateStep && (
            <div className="flex items-center justify-between rounded-lg border border-teal-500/30 bg-teal-500/5 px-3 py-2 text-xs text-teal-800 dark:text-teal-200">
              <span className="font-medium">
                Step 1 of Inventory Management: Check in carrier delivery vehicle and issue Security Gate Pass.
              </span>
              <button
                type="button"
                onClick={handleFillAll}
                className="font-bold underline hover:opacity-80"
              >
                Autofill all fields
              </button>
            </div>
          )}

          <GuidedFieldWalkthrough
            activeStepKey={activeStepKey}
            onStepChange={setActiveStepKey}
            fields={fields}
            values={{
              vehicleNumber,
              supplierAsn,
              driverName,
              assignedDock,
              grossWeight,
            }}
            onFillAll={handleFillAll}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Vehicle Registration Number" required>
              <TextInput
                value={vehicleNumber}
                onChange={(e) => setVehicleNumber(e.target.value)}
                placeholder="e.g. MH-12-AB-1234"
                className={cn(activeStepKey === "vehicleNumber" && "ring-2 ring-teal-500 bg-teal-500/5")}
                required
              />
            </Field>

            <Field label="Supplier ASN / PO Reference" required>
              <TextInput
                value={supplierAsn}
                onChange={(e) => setSupplierAsn(e.target.value)}
                placeholder="e.g. ASN-1092"
                className={cn(activeStepKey === "supplierAsn" && "ring-2 ring-teal-500 bg-teal-500/5")}
                required
              />
            </Field>

            <Field label="Driver Name & Mobile Contact" required>
              <TextInput
                value={driverName}
                onChange={(e) => setDriverName(e.target.value)}
                placeholder="e.g. Ramesh Kumar (+91 98765 43210)"
                className={cn(activeStepKey === "driverName" && "ring-2 ring-teal-500 bg-teal-500/5")}
                required
              />
            </Field>

            <Field label="Designated Unloading Dock" required>
              <TextInput
                value={assignedDock}
                onChange={(e) => setAssignedDock(e.target.value)}
                placeholder="e.g. Dock Bay 3 - Inbound Quarantine"
                className={cn(activeStepKey === "assignedDock" && "ring-2 ring-teal-500 bg-teal-500/5")}
                required
              />
            </Field>

            <div className="md:col-span-2">
              <Field label="Weighbridge Inward Gross Weight (kg)" required>
                <TextInput
                  value={grossWeight}
                  onChange={(e) => setGrossWeight(e.target.value)}
                  placeholder="e.g. 14,250"
                  className={cn(activeStepKey === "grossWeight" && "ring-2 ring-teal-500 bg-teal-500/5")}
                  required
                />
              </Field>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
            <ActionButton tone="ghost" type="button" onClick={onClose}>Cancel</ActionButton>
            <div className="relative inline-block">
              <ActionButton
                type="submit"
                tone="primary"
                disabled={!isComplete}
                className={cn(
                  isTourGateStep && isComplete && "ring-2 ring-teal-500 ring-offset-2 animate-pulse",
                  isTourGateStep && "font-semibold"
                )}
              >
                Issue Security Gate Pass GP-1092
              </ActionButton>
              {isTourGateStep && isComplete && (
                <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-teal-500 text-white font-bold text-[10px] shadow animate-bounce pointer-events-none">
                  3
                </span>
              )}
            </div>
          </div>
        </form>
      )}
    </Modal>
  );
}

// ---- detail --------------------------------------------------------------------------------------------

function DetailDialog({ requestId, onClose, onChanged }: { requestId: string; onClose: () => void; onChanged: () => void }) {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const path = `/api/v1/transport-requests/${requestId}`;
  const q = useApiQuery<Request>(path);
  const r = q.data;
  const [actionError, setActionError] = useState("");
  const [rfqOpen, setRfqOpen] = useState(false);
  const [quoteRfq, setQuoteRfq] = useState("");
  const [podDispatch, setPodDispatch] = useState("");

  // Award: the >5%-premium justification rule lives server-side. Try with no justification first and only
  // reveal the inline field when the server answers AWARD_JUSTIFICATION_REQUIRED (its message names the premium).
  const [award, setAward] = useState<{ rfqId: string; quotationId: string } | null>(null);
  const [justification, setJustification] = useState("");
  const [awardError, setAwardError] = useState("");
  const [needJustification, setNeedJustification] = useState(false);

  const reload = async () => {
    await qc.invalidateQueries({ queryKey: [path] });
    onChanged();
  };
  const cancelAward = () => {
    setAward(null);
    setJustification("");
    setAwardError("");
    setNeedJustification(false);
  };
  const attemptAward = async (target: { rfqId: string; quotationId: string }, why: string) => {
    setAwardError("");
    const body: Record<string, unknown> = { quotationId: target.quotationId };
    if (why.trim()) body.justification = why.trim();
    try {
      await api("POST", `/api/v1/rfqs/${target.rfqId}/award`, { json: body });
      cancelAward();
      await reload();
    } catch (exc) {
      setAwardError(exc instanceof ApiError ? exc.detail : String(exc));
      setNeedJustification(exc instanceof ApiError && exc.code === "AWARD_JUSTIFICATION_REQUIRED");
    }
  };
  const startAward = (rfqId: string, quotationId: string) => {
    const target = { rfqId, quotationId };
    setAward(target);
    setJustification("");
    setNeedJustification(false);
    void attemptAward(target, "");
  };

  const createDispatch = async () => {
    setActionError("");
    try {
      await api("POST", "/api/v1/dispatches", { json: { transportRequestId: requestId } });
      await reload();
    } catch (exc) {
      setActionError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };

  const status = r?.status ?? "";
  const rfqs = (r?.rfqs ?? []).map((rfq) => ({
    ...rfq,
    due: format.date(rfq.dueAt),
    quotes: (rfq.quotations ?? []).map((x) => ({ ...x, amt: format.money(x.amount), valid: format.date(x.validUntil) })),
  }));
  const dispatches = (r?.dispatches ?? []).map((d) => ({ ...d, when: format.date(d.dispatchedAt) }));

  return (
    <>
      <Modal open onClose={onClose} wide title={r ? `${r.number} — ${r.lane}` : "Transport request"}
        footer={r && <><ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>{can("logistics:dispatch") && status === "approved" && <ActionButton onClick={createDispatch}>Create dispatch</ActionButton>}</>}>
        {r && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2"><Pill>{status}</Pill><span className="text-xs text-[var(--muted-foreground)]">source: {r.source}</span></div>
            {r.orderNumber && <p className="text-sm">Order: {r.orderNumber}</p>}
            {r.overrideReason && <p className="text-sm text-[var(--warning)]">Override reason: {r.overrideReason}</p>}
            <InlineError message={actionError || q.error?.message} />
            <div className="mt-2 flex w-full items-center">
              <h3 className="rx-heading-3">RFQs</h3>
              <div className="flex-1" />
              {["pending", "rfq_sent", "quotation_received"].includes(status) && can("logistics:write") && <ActionButton size="sm" onClick={() => setRfqOpen(true)}>Send RFQ</ActionButton>}
            </div>
            {rfqs.map((rfq) => (
              <div key={rfq.id} className="flex w-full flex-col items-start gap-2 border-b border-[var(--border)] py-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-bold">{rfq.number}</span>
                  <Pill>{rfq.status}</Pill>
                  <span className="text-xs text-[var(--muted-foreground)]">due {rfq.due}</span>
                  {rfq.status === "open" && can("logistics:quote") && <ActionButton size="sm" tone="ghost" onClick={() => setQuoteRfq(rfq.id)}>Record quote</ActionButton>}
                </div>
                <DataTable columns={["Carrier", "Amount", "Transit", "Valid until", "Status", ""]} minWidth={0} fit>
                  {rfq.quotes.flatMap((x) => {
                    const awarding = award?.rfqId === rfq.id && award.quotationId === x.id;
                    return [
                      <tr key={x.id}>
                        <td>{x.carrierName}</td><td>{x.amt}</td><td>{x.transitDays}</td><td>{x.valid}</td><td><Pill>{x.status}</Pill></td>
                        <td>{x.status === "received" && can("logistics:approve") && <ActionButton size="sm" tone="ghost" onClick={() => startAward(rfq.id, x.id)}>Award</ActionButton>}</td>
                      </tr>,
                      awarding && awardError && (
                        <tr key={`${x.id}-award`}>
                          <td colSpan={6}>
                            <div className="flex w-full flex-col gap-2">
                              <InlineError message={awardError} />
                              {needJustification && (
                                <div className="flex items-center gap-2">
                                  <TextInput style={{ width: "20rem" }} placeholder="Justification for this award" value={justification} onChange={(e) => setJustification(e.target.value)} />
                                  <ActionButton size="sm" onClick={() => award && attemptAward(award, justification)}>Award with justification</ActionButton>
                                  <ActionButton size="sm" tone="ghost" onClick={cancelAward}>Cancel</ActionButton>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      ),
                    ];
                  })}
                </DataTable>
              </div>
            ))}
            <h3 className="rx-heading-3 mt-3">Dispatches</h3>
            <DataTable columns={["Dispatch", "Carrier", "Status", "Dispatched", "POD", ""]} minWidth={0} fit>
              {dispatches.map((d) => (
                <tr key={d.id}>
                  <td>{d.number}</td><td>{d.carrierName}</td><td><Pill>{d.status}</Pill></td><td>{d.when}</td><td>{d.podUrl}</td>
                  <td>{d.status === "dispatched" && can("logistics:dispatch") && <ActionButton size="sm" tone="ghost" onClick={() => setPodDispatch(d.id)}>Record POD</ActionButton>}</td>
                </tr>
              ))}
            </DataTable>
          </div>
        )}
      </Modal>
      {rfqOpen && <RfqDialog requestId={requestId} onClose={() => setRfqOpen(false)} onDone={reload} />}
      {quoteRfq && <QuoteDialog rfqId={quoteRfq} onClose={() => setQuoteRfq("")} onDone={reload} />}
      {podDispatch && <PodDialog dispatchId={podDispatch} onClose={() => setPodDispatch("")} onDone={reload} />}
    </>
  );
}

// ---- page -------------------------------------------------------------------------------------------------

function Content() {
  const qc = useQueryClient();
  const { isTourActive, activeJourneyId, currentJourneyStepIndex } = useDemoTour();
  const isTourGateStep = isTourActive && activeJourneyId === "inventory-management" && currentJourneyStepIndex === 0;

  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState("");
  const [gateDialogOpen, setGateDialogOpen] = useState(false);
  const list = useApiQuery<ListResponse<Request>>("/api/v1/transport-requests", { page, limit: 20, status });
  const requests = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/transport-requests"] });
  const link = (r: Request) => <button type="button" className="rx-link" onClick={() => setOpenId(r.id)}>{r.number}</button>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader
        eyebrow="Demand"
        title="Logistics"
        actions={
          <div className="relative inline-block">
            <ActionButton
              className={cn(
                isTourGateStep && "ring-2 ring-teal-500 ring-offset-2 animate-pulse font-semibold"
              )}
              onClick={() => setGateDialogOpen(true)}
            >
              Gate entry
            </ActionButton>
            {isTourGateStep && (
              <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-teal-500 text-white font-bold text-[10px] shadow animate-bounce pointer-events-none">
                1
              </span>
            )}
          </div>
        }
      />
      <div className="flex gap-4"><StatCard label="Requests on this page" value={requests.length} /></div>
      <label htmlFor="logistics-status-filter" className="sr-only">Filter by status</label>
      <select id="logistics-status-filter" className="filter-select" value={status} aria-label="Filter by all" onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
        <option value="">all</option>
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <InlineError message={list.error?.message} />
      {requests.length === 0 ? (
        <EmptyState title="No logistics transport requests" hint="Try adjusting your status filter or creating a new transport request." />
      ) : (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["Request", "Lane", "Order", "Status", "RFQs", "Best quote", "Awarded"]} fit>
              {requests.map((r) => (
                <tr key={r.id}><td>{link(r)}</td><td>{r.lane}</td><td>{r.orderNumber}</td><td><Pill>{r.status}</Pill></td><td>{r.rfqCount}</td><td>{format.money(r.bestQuote)}</td><td>{r.awardedCarrier}</td></tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {requests.map((r) => (
              <MobileRecordCard key={r.id}>
                <MobileRecordRow label="Request" value={link(r)} />
                <MobileRecordRow label="Lane" value={r.lane} />
                <MobileRecordRow label="Order" value={r.orderNumber} />
                <MobileRecordRow label="Status" value={<Pill>{r.status}</Pill>} />
                <MobileRecordRow label="RFQs" value={r.rfqCount} />
                <MobileRecordRow label="Best quote" value={format.money(r.bestQuote)} />
                <MobileRecordRow label="Awarded" value={r.awardedCarrier} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full"><Pagination meta={list.data?.meta} onPage={setPage} /></div>
      {openId && <DetailDialog requestId={openId} onClose={() => setOpenId("")} onChanged={refresh} />}
      <GateEntryDialog open={gateDialogOpen} onClose={() => setGateDialogOpen(false)} />
    </div>
  );
}

export default function LogisticsPage() {
  const { can } = useAuth();
  return <Shell>{can("logistics:read") ? <Content /> : <Forbidden permission="logistics:read" />}</Shell>;
}
