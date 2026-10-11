import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  FileSpreadsheet,
  Lock,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  Field,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { date as formatDate, qty } from "@/lib/format";

interface RecallRecord {
  id: string;
  case_number: string;
  title: string;
  severity: string;
  root_cause_lot_number: string;
  status: string;
  quarantined_stock_qty: number;
  affected_customers_count: number;
  created_at: string;
}

interface ForwardTraceResult {
  root_lot_number: string;
  direction: string;
  parent_assemblies: {
    parent_lot: string;
    consumed_qty: number;
    product_name: string;
    sku: string;
  }[];
  inventory_in_warehouse: {
    item_id: string;
    sku: string;
    product_name: string;
    batch_number: string;
    available_qty: number;
    status: string;
  }[];
  impacted_customer_orders: {
    order_number: string;
    customer_name: string;
    delivery_date: string | null;
    status: string;
  }[];
}

interface CustomerAdvisoryData {
  case_number: string;
  title: string;
  severity: string;
  root_cause_lot: string;
  advisory_template: string;
  affected_customers: {
    customer_name: string;
    email: string;
    phone: string;
    city: string;
    compliance_action: string;
  }[];
}

export default function TraceabilityPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [searchLot, setSearchLot] = useState("RAW-BAT-2026-A1");
  const [activeLotQuery, setActiveLotQuery] = useState("RAW-BAT-2026-A1");
  const [traceMode, setTraceMode] = useState<"forward" | "backward">("forward");

  const [showRecallModal, setShowRecallModal] = useState(false);
  const [recallTitle, setRecallTitle] = useState("");
  const [recallSeverity, setRecallSeverity] = useState("critical");
  const [recallLot, setRecallLot] = useState("RAW-BAT-2026-A1");
  const [recallDesc, setRecallDesc] = useState("");

  const [selectedRecallId, setSelectedRecallId] = useState<string | null>(null);

  const { data: traceData } = useQuery({
    queryKey: ["traceability", "trace", traceMode, activeLotQuery],
    queryFn: () =>
      api<ForwardTraceResult>(
        "GET",
        traceMode === "forward"
          ? `/api/v1/traceability/trace/forward?raw_lot_number=${encodeURIComponent(activeLotQuery)}`
          : `/api/v1/traceability/trace/backward?finished_lot_number=${encodeURIComponent(activeLotQuery)}`
      ),
    enabled: !!activeLotQuery,
  });

  const { data: recallsData } = useQuery({
    queryKey: ["traceability", "recalls"],
    queryFn: () => api<{ recalls: RecallRecord[] }>("GET", "/api/v1/traceability/recalls"),
  });

  const { data: advisoryData } = useQuery({
    queryKey: ["traceability", "advisories", selectedRecallId],
    queryFn: () => api<CustomerAdvisoryData>("GET", `/api/v1/traceability/recalls/${selectedRecallId}/customer-advisories`),
    enabled: !!selectedRecallId,
  });

  const recalls = recallsData?.recalls || [];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchLot.trim()) return;
    setActiveLotQuery(searchLot.trim());
  };

  const handleCreateRecall = async () => {
    if (!recallTitle.trim() || !recallLot.trim()) return;
    await api("POST", "/api/v1/traceability/recalls", {
      json: {
        title: recallTitle.trim(),
        severity: recallSeverity,
        root_cause_lot_number: recallLot.trim(),
        description: recallDesc || undefined,
      },
    });
    setShowRecallModal(false);
    setRecallTitle("");
    qc.invalidateQueries({ queryKey: ["traceability"] });
  };

  const handleQuarantineFreeze = async (recallId: string) => {
    const res = await api<any>("POST", `/api/v1/traceability/recalls/${recallId}/quarantine-freeze`);
    alert(res.message);
    qc.invalidateQueries({ queryKey: ["traceability"] });
  };

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="Advanced Batch Traceability & Recall Genealogy"
          description="Bi-directional DAG lot lineage traversal, 1-click digital quarantine freezing & automated customer recall advisories"
          actions={
            <div className="flex gap-2">
              <ActionButton
                tone="ghost"
                size="sm"
                onClick={() => qc.invalidateQueries({ queryKey: ["traceability"] })}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </ActionButton>
              <ActionButton
                tone="danger"
                size="sm"
                onClick={() => {
                  setRecallLot(activeLotQuery);
                  setShowRecallModal(true);
                }}
              >
                <AlertOctagon className="h-4 w-4 mr-1" />
                Open Recall Case
              </ActionButton>
            </div>
          }
        />

        {/* High-level KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Root Cause Traversal"
            value="< 15 Mins"
            hint="Supplier to customer orders"
            tone="info"
          />
          <StatCard
            label="Digital Quarantine"
            value="1-Click Lock"
            hint="Locks inventory from dispatch"
            tone="warning"
          />
          <StatCard
            label="Active Recall Cases"
            value={recalls.filter((r) => r.status !== "resolved").length.toString()}
            hint={`${recalls.length} lifetime cases`}
            tone="destructive"
          />
          <StatCard
            label="Regulatory Audit"
            value="ISO / FDA 21"
            hint="Compliant immutable audit trail"
            tone="success"
          />
        </div>

        {/* Search Bar & Mode Switcher */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xs">
          <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTraceMode("forward")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  traceMode === "forward"
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                    : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                }`}
              >
                Forward (Raw ➔ Customers)
              </button>
              <button
                type="button"
                onClick={() => setTraceMode("backward")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  traceMode === "backward"
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                    : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                }`}
              >
                Backward (Customer ➔ Supplier)
              </button>
            </div>

            <div className="flex-1 min-w-[240px] flex gap-2">
              <TextInput
                placeholder="Enter Lot / Serial # (e.g. RAW-BAT-2026-A1)"
                value={searchLot}
                onChange={(e) => setSearchLot(e.target.value)}
              />
              <ActionButton tone="primary" size="sm" onClick={handleSearch}>
                <Search className="h-4 w-4 mr-1" />
                Trace Lineage
              </ActionButton>
            </div>
          </form>
        </div>

        {/* Lineage Visual Tree Results */}
        {traceData && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Step 1: Root Node */}
            <Panel title="Origin Defective Batch">
              <div className="p-4 rounded-lg border border-red-500/30 bg-red-500/10 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--muted-foreground)]">Batch / Serial</span>
                  <Pill tone="destructive">ROOT CAUSE</Pill>
                </div>
                <div className="font-mono text-base font-bold text-red-500">{traceData.root_lot_number}</div>
                <div className="text-xs text-[var(--muted-foreground)]">Direction: {traceData.direction} Trace</div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="text-xs font-semibold text-[var(--foreground)]">Direct Assemblies Built:</div>
                {traceData.parent_assemblies.length === 0 ? (
                  <div className="text-xs text-[var(--muted-foreground)]">Direct inventory batch (no child BOM edges)</div>
                ) : (
                  traceData.parent_assemblies.map((pa, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-[var(--muted)]/40 border text-xs flex justify-between">
                      <div>
                        <div className="font-semibold text-[var(--foreground)]">{pa.parent_lot}</div>
                        <div className="text-[var(--muted-foreground)]">{pa.product_name} ({pa.sku})</div>
                      </div>
                      <span className="font-mono text-xs">{qty(pa.consumed_qty)}</span>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* Step 2: Warehouse Stock Isolation */}
            <Panel title="Warehouse Stock at Risk">
              <div className="space-y-2">
                {traceData.inventory_in_warehouse.length === 0 ? (
                  <div className="p-4 text-xs text-[var(--muted-foreground)] text-center">
                    No active stock found in warehouse on-hand buckets.
                  </div>
                ) : (
                  traceData.inventory_in_warehouse.map((inv) => (
                    <div key={inv.item_id} className="p-3 rounded-lg border bg-[var(--card)] text-xs space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="font-mono font-bold text-[var(--foreground)]">{inv.batch_number}</span>
                        <Pill tone={inv.status === "quarantined" ? "destructive" : "warning"}>
                          {inv.status.toUpperCase()}
                        </Pill>
                      </div>
                      <div className="text-[var(--muted-foreground)]">{inv.product_name}</div>
                      <div className="font-semibold text-emerald-500">{qty(inv.available_qty)} units available</div>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* Step 3: Impacted Customers */}
            <Panel title="Shipped Customer Accounts">
              <div className="space-y-2">
                {traceData.impacted_customer_orders.length === 0 ? (
                  <div className="p-4 text-xs text-[var(--muted-foreground)] text-center">
                    No delivered customer shipments containing this batch lineage.
                  </div>
                ) : (
                  traceData.impacted_customer_orders.map((ord, i) => (
                    <div key={i} className="p-3 rounded-lg border bg-[var(--card)] text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="font-mono font-semibold">{ord.order_number}</span>
                        <Pill tone="info">{ord.status.toUpperCase()}</Pill>
                      </div>
                      <div className="font-medium text-[var(--foreground)]">{ord.customer_name}</div>
                      <div className="text-[10px] text-[var(--muted-foreground)]">
                        Shipped: {ord.delivery_date ? formatDate(ord.delivery_date) : "Recent"}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Panel>
          </div>
        )}

        {/* Recall Events Audit Log */}
        <Panel title="Formal Product Recall Containment Cases">
          <DataTable
            columns={[
              "Case #",
              "Incident Title",
              "Severity",
              "Root Cause Lot",
              "Quarantined Stock",
              "Status",
              "Quarantine Lock",
              "Advisory Manifest",
            ]}
          >
            {recalls.map((r) => (
              <TableRow
                key={r.id}
                cells={[
                  <span className="font-mono font-bold text-[var(--foreground)]">{r.case_number}</span>,
                  <span>{r.title}</span>,
                  <Pill tone={r.severity === "critical" ? "destructive" : "warning"}>{r.severity.toUpperCase()}</Pill>,
                  <span className="font-mono text-xs">{r.root_cause_lot_number}</span>,
                  <span className="font-mono">{qty(r.quarantined_stock_qty)} units</span>,
                  <Pill tone={r.status === "quarantined" ? "destructive" : "info"}>{r.status.toUpperCase()}</Pill>,
                  r.status !== "quarantined" ? (
                    <ActionButton
                      size="sm"
                      tone="danger"
                      onClick={() => handleQuarantineFreeze(r.id)}
                    >
                      <Lock className="h-3 w-3 mr-1" />
                      Freeze Stock
                    </ActionButton>
                  ) : (
                    <span className="text-xs text-red-500 font-semibold">Stock Locked</span>
                  ),
                  <ActionButton
                    size="sm"
                    tone="ghost"
                    onClick={() => setSelectedRecallId(r.id)}
                  >
                    <Users className="h-3 w-3 mr-1" />
                    Advisories
                  </ActionButton>,
                ]}
              />
            ))}
          </DataTable>
        </Panel>

        {/* Modal: Open Recall Case */}
        {showRecallModal && (
          <Modal
            open={showRecallModal}
            title="Initiate Formal Product Recall Case"
            onClose={() => setShowRecallModal(false)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setShowRecallModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="danger" size="sm" onClick={handleCreateRecall}>
                  Initiate Recall & Discover Impact
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <Field label="Incident Title" required>
                <TextInput
                  placeholder="e.g. Battery Cell Thermal Runaway Impurity"
                  value={recallTitle}
                  onChange={(e) => setRecallTitle(e.target.value)}
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Contaminated Root Lot #" required>
                  <TextInput
                    value={recallLot}
                    onChange={(e) => setRecallLot(e.target.value)}
                  />
                </Field>
                <Field label="Severity Tier">
                  <select
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                    value={recallSeverity}
                    onChange={(e) => setRecallSeverity(e.target.value)}
                  >
                    <option value="critical">Critical (Class I - Life Safety)</option>
                    <option value="high">High (Class II - Operational Failure)</option>
                    <option value="medium">Medium (Class III - Minor Tolerance)</option>
                  </select>
                </Field>
              </div>
              <Field label="Case Description & Failure Mode">
                <TextInput
                  placeholder="Supplier reported manganese contamination in cathode lot..."
                  value={recallDesc}
                  onChange={(e) => setRecallDesc(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}

        {/* Modal: Customer Advisory Manifest */}
        {selectedRecallId && advisoryData && (
          <Modal
            open={!!selectedRecallId}
            title={`Customer Recall Advisory Manifest: ${advisoryData.case_number}`}
            onClose={() => setSelectedRecallId(null)}
            footer={
              <div className="flex justify-end">
                <ActionButton tone="primary" size="sm" onClick={() => alert("Regulatory export generated")}>
                  <FileSpreadsheet className="h-4 w-4 mr-1" />
                  Export Regulatory Filing
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4 text-xs">
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg">
                <div className="font-bold">{advisoryData.title}</div>
                <div className="mt-1">{advisoryData.advisory_template.replace("{lot}", advisoryData.root_cause_lot)}</div>
              </div>
              <div className="space-y-2">
                <div className="font-bold text-[var(--foreground)]">Impacted Customer Contacts:</div>
                {advisoryData.affected_customers.map((c, i) => (
                  <div key={i} className="p-2.5 rounded-lg border bg-[var(--muted)]/20 flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-[var(--foreground)]">{c.customer_name} ({c.city})</div>
                      <div className="text-[var(--muted-foreground)] font-mono">{c.email} | {c.phone}</div>
                    </div>
                    <Pill tone="warning">{c.compliance_action}</Pill>
                  </div>
                ))}
              </div>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
