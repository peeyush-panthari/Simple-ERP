/**
 * Control tower - the dashboard for users with analytics:read. Users without
 * it get a plain landing message instead of a Forbidden block, since this is
 * the post-login landing page for everyone.
 */
import { Link } from "react-router-dom";
import { ArrowRight, Compass, Sparkles } from "lucide-react";
import { Shell } from "@/components/erp/shell";
import { Note, PageHeader, Panel, StatCard, PageSpinner } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

interface Dashboard {
  workingCapital?: { data?: { currency?: string; workingCapital?: string; receivables?: { outstanding?: string }; payables?: { outstanding?: string } } };
  inventory?: { available?: boolean };
  cycleTimes?: { orderToCash?: number | null; orderToShip?: number | null; shipToInvoice?: number | null; invoiceToCash?: number | null; sampleSize?: number };
  orderFunnel?: { stage: string; count: number }[];
  recentActivity?: { action: string; entityType?: string | null; entityId?: string | null; actorEmail?: string | null; createdAt?: string }[];
}

const days = (v: number | null | undefined, suffix = "d") => (v ? `${v}${suffix}` : "—");

function Content() {
  const { data: d, error, isLoading } = useApiQuery<Dashboard>("/api/v1/dashboard");

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <PageSpinner />
      </div>
    );
  }

  const wc = d?.workingCapital?.data ?? {};
  const currency = wc.currency || "INR";
  const cycle = d?.cycleTimes ?? {};
  const funnel = d?.orderFunnel ?? [];
  const maxCount = Math.max(0, ...funnel.map((f) => f.count));

  return (
    <div className="flex flex-col">
      {/* Onboarding Demo Tour Banner */}
      <div className="mb-4 rounded-2xl border border-teal-500/30 bg-gradient-to-r from-teal-500/10 via-[var(--card)] to-indigo-500/10 p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-start sm:items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-500/20 text-teal-700 dark:text-teal-300">
              <Compass size={22} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--foreground)]">
                New to Simple ERP? Explore How the Entire System Connects
              </h2>
              <p className="text-xs text-[var(--muted-foreground)]">
                Walk through an interactive guided tour across all 13 modules — from Demand &amp; MRP, Procurement, Warehouse GRN, QC, WMS, Manufacturing, Sales Orders, to Finance 3-Way Matching.
              </p>
            </div>
          </div>
          <Link
            to="/demo-flow"
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 px-3.5 py-2 text-xs font-semibold text-white shadow-xs transition-colors shrink-0"
          >
            <Sparkles size={14} />
            <span>Start Guided Demo Flow</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {error && <Note tone="warning">{error.message}</Note>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Working capital" value={format.money(wc.workingCapital, currency)} hint={wc.currency ?? ""} />
        <StatCard label="Receivables outstanding" value={format.money(wc.receivables?.outstanding, currency)} />
        <StatCard label="Payables outstanding" value={format.money(wc.payables?.outstanding, currency)} />
        <StatCard label="Order → cash" value={cycle.orderToCash ? `${cycle.orderToCash} days` : "—"} hint={`${cycle.sampleSize ?? 0} orders sampled`} />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel title="Order funnel">
          <div className="flex flex-col gap-3 px-4 py-4">
            {funnel.map((f) => (
              <div key={f.stage} className="flex w-full items-center gap-3">
                <span className="text-sm text-[var(--foreground)]" style={{ width: "10rem" }}>{f.stage}</span>
                <div className="w-full rounded-sm" style={{ height: "1.25rem", background: "var(--muted)" }}>
                  <div style={{ width: `${maxCount ? format.pyRound((f.count / maxCount) * 100, 1) : 0}%`, height: "100%", background: "var(--primary)", borderRadius: "0.25rem" }} />
                </div>
                <span className="numeric text-sm" style={{ width: "3rem", textAlign: "right" }}>{f.count}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Fulfillment cycle">
          <div className="flex flex-col gap-3 px-4 py-4">
            <StatCard label="Order → dispatch" value={days(cycle.orderToShip)} />
            <StatCard label="Dispatch → invoice" value={days(cycle.shipToInvoice)} />
            <StatCard label="Invoice → cash" value={days(cycle.invoiceToCash)} />
          </div>
        </Panel>
      </div>
      <div className="mt-4">
        <Panel
          title="Recent activity"
          subtitle="The nearest equivalent this monolith has to a cross-service event stream - real audit-log entries, not domain events."
        >
          <div className="px-4 py-3">
            {(d?.recentActivity ?? []).map((a, i) => (
              <div key={i} className="flex w-full items-start justify-between gap-3 border-b border-[var(--border)]/70 py-2">
                <div>
                  <p className="text-sm font-medium text-[var(--foreground)]">{a.action}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">{a.entityType ? `${a.entityType} / ${a.entityId}` : ""}</p>
                </div>
                <div>
                  <p className="text-right text-xs text-[var(--muted-foreground)]">{a.actorEmail}</p>
                  <p className="text-right text-xs text-[var(--muted-foreground)]">{a.createdAt}</p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      {d?.inventory?.available === false && (
        <div className="mt-4">
          <Note tone="warning">Inventory valuation is unavailable - the working capital figure above excludes it.</Note>
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  const { user, can } = useAuth();
  return (
    <Shell>
      <PageHeader eyebrow="Overview" title={`Welcome, ${user?.displayName ?? ""}`} />
      {can("analytics:read") ? <Content /> : <p className="text-sm text-[var(--muted-foreground)]">Modules are live under the sections in the sidebar.</p>}
    </Shell>
  );
}
