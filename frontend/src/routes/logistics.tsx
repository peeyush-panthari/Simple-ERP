/** Logistics: transport requests with RFQs, quotes, awarding, dispatch and proof of delivery. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton, DataTable, DesktopOnly, EmptyState, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Pagination, Pill, StatCard, TextArea, TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";

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
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState("");
  const list = useApiQuery<ListResponse<Request>>("/api/v1/transport-requests", { page, limit: 20, status });
  const requests = list.data?.data ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/transport-requests"] });
  const link = (r: Request) => <button type="button" className="rx-link" onClick={() => setOpenId(r.id)}>{r.number}</button>;

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader eyebrow="Demand" title="Logistics" />
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
    </div>
  );
}

export default function LogisticsPage() {
  const { can } = useAuth();
  return <Shell>{can("logistics:read") ? <Content /> : <Forbidden permission="logistics:read" />}</Shell>;
}
