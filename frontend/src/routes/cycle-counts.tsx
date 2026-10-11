import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  EyeOff,
  Plus,
  RefreshCw,
  Search,
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
import { date as formatDate, money, qty } from "@/lib/format";

interface CycleCountSession {
  id: string;
  session_number: string;
  warehouse_id: string;
  warehouse_name: string;
  warehouse_code: string;
  counting_type: string;
  target_abc_class: string | null;
  status: string;
  blind_count: boolean;
  scheduled_date: string;
  completed_at: string | null;
  total_items_count: number;
  discrepancy_items_count: number;
  net_variance_value: number;
  notes: string | null;
  created_at: string;
}

interface CycleCountLine {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  location_code: string;
  batch_no: string;
  system_qty: number | null;
  counted_qty: number | null;
  variance_qty: number | null;
  unit_cost: number;
  variance_value: number | null;
  status: string;
  recount_count: number;
  notes: string | null;
}

export default function CycleCountsPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRecountModal, setShowRecountModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);

  // Form states
  const [targetAbc, setTargetAbc] = useState<string>("A");
  const [countingType, setCountingType] = useState<string>("abc_scheduled");
  const [blindCount, setBlindCount] = useState<boolean>(true);
  const [notes, setNotes] = useState<string>("");

  // Counting inputs: map of lineId -> countedQty string
  const [countInputs, setCountInputs] = useState<Record<string, string>>({});
  const [recountReason, setRecountReason] = useState("");
  const [selectedRecountLineId, setSelectedRecountLineId] = useState<string | null>(null);
  const [supervisorNotes, setSupervisorNotes] = useState("");

  // 1. Fetch sessions
  const sessionsQuery = useQuery({
    queryKey: ["cycle-count-sessions"],
    queryFn: () => api<{ sessions: CycleCountSession[] }>("GET", "/api/v1/cycle-counts/sessions"),
  });

  // 2. Fetch warehouses for dropdown
  const warehousesQuery = useQuery({
    queryKey: ["wms-warehouses"],
    queryFn: () => api<Array<{ id: string; name: string; code: string }>>("GET", "/api/v1/wms-bins/warehouses"),
  });

  const [selectedWhId, setSelectedWhId] = useState<string>("");

  // 3. Fetch session detail if selected
  const detailQuery = useQuery({
    queryKey: ["cycle-count-detail", selectedSessionId],
    queryFn: () => api<{ session: CycleCountSession; lines: CycleCountLine[] }>("GET", `/api/v1/cycle-counts/sessions/${selectedSessionId}`),
    enabled: !!selectedSessionId,
  });

  const sessions = sessionsQuery.data?.sessions || [];
  const warehouses = warehousesQuery.data || [];
  const currentSession = detailQuery.data?.session;
  const currentLines = detailQuery.data?.lines || [];

  // Summary statistics
  const activeSessionsCount = sessions.filter((s) => s.status === "in_progress" || s.status === "pending_review").length;
  const totalDiscrepancies = sessions.reduce((acc, s) => acc + s.discrepancy_items_count, 0);
  const netVarianceTotal = sessions.reduce((acc, s) => acc + s.net_variance_value, 0);

  // Handler: Generate new session
  const handleGenerateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    const whId = selectedWhId || (warehouses[0]?.id ?? "");
    if (!whId) return;

    try {
      const res = await api<{ id: string }>("POST", "/api/v1/cycle-counts/generate", {
        json: {
          warehouse_id: whId,
          target_abc_class: targetAbc,
          counting_type: countingType,
          blind_count: blindCount,
          notes,
        },
      });
      setShowCreateModal(false);
      qc.invalidateQueries({ queryKey: ["cycle-count-sessions"] });
      setSelectedSessionId(res.id);
    } catch (err) {
      alert("Failed to generate cycle count session: " + err);
    }
  };

  // Handler: Record physical counts
  const handleSaveCounts = async () => {
    if (!selectedSessionId) return;
    const items = Object.entries(countInputs).map(([lineId, val]) => ({
      line_id: lineId,
      counted_qty: parseFloat(val || "0"),
    }));
    if (items.length === 0) {
      alert("Please enter physical count for at least one item");
      return;
    }

    try {
      await api("POST", `/api/v1/cycle-counts/sessions/${selectedSessionId}/record-count`, {
        json: { counts: items },
      });
      qc.invalidateQueries({ queryKey: ["cycle-count-detail", selectedSessionId] });
      qc.invalidateQueries({ queryKey: ["cycle-count-sessions"] });
      alert("Physical counts recorded successfully");
    } catch (err) {
      alert("Failed to record counts: " + err);
    }
  };

  // Handler: Recount request
  const handleRecount = async () => {
    if (!selectedSessionId || !selectedRecountLineId) return;
    try {
      await api("POST", `/api/v1/cycle-counts/sessions/${selectedSessionId}/recount-request`, {
        json: { line_ids: [selectedRecountLineId], reason: recountReason },
      });
      setShowRecountModal(false);
      qc.invalidateQueries({ queryKey: ["cycle-count-detail", selectedSessionId] });
      alert("Recount requested for line");
    } catch (err) {
      alert("Failed to request recount: " + err);
    }
  };

  // Handler: Approve & Adjust
  const handleApproveAdjust = async () => {
    if (!selectedSessionId) return;
    try {
      await api("POST", `/api/v1/cycle-counts/sessions/${selectedSessionId}/approve-adjust`, {
        json: { supervisor_notes: supervisorNotes },
      });
      setShowApproveModal(false);
      qc.invalidateQueries({ queryKey: ["cycle-count-detail", selectedSessionId] });
      qc.invalidateQueries({ queryKey: ["cycle-count-sessions"] });
      alert("Cycle count approved and stock variance adjustments posted to ledger");
    } catch (err) {
      alert("Failed to approve adjustments: " + err);
    }
  };

  return (
    <Shell>
      <PageHeader
        title="Cycle Counting & Inventory Audits"
        description="Perpetual ABC inventory counting, blind audit sheets, discrepancy analysis, and supervisor variance reconciliation."
        actions={
          <div className="flex gap-2">
            <ActionButton
              tone="primary"
              onClick={() => {
                if (warehouses.length > 0 && !selectedWhId) setSelectedWhId(warehouses[0].id);
                setShowCreateModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Schedule Cycle Count
            </ActionButton>
            <ActionButton
              tone="ghost"
              onClick={() => qc.invalidateQueries({ queryKey: ["cycle-count-sessions"] })}
            >
              <RefreshCw className="w-4 h-4 mr-1.5" />
              Refresh
            </ActionButton>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Active Audit Sessions"
          value={activeSessionsCount}
          hint="In progress or review"
        />
        <StatCard
          label="Total Audit Sessions"
          value={sessions.length}
          hint="Recorded to date"
        />
        <StatCard
          label="Flagged Discrepancies"
          value={totalDiscrepancies}
          hint="Physical vs. system gaps"
        />
        <StatCard
          label="Net Variance Impact"
          value={money(netVarianceTotal)}
          hint="Shrinkage value balance"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Sessions List */}
        <div className="lg:col-span-1 space-y-4">
          <Panel title="Audit Sessions">
            <div className="space-y-3">
              {sessions.map((s) => {
                const isSelected = s.id === selectedSessionId;
                return (
                  <div
                    key={s.id}
                    onClick={() => setSelectedSessionId(s.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                          {s.session_number}
                        </span>
                        <div className="text-xs text-slate-500">{s.warehouse_name}</div>
                      </div>
                      <Pill
                        tone={
                          s.status === "completed"
                            ? "success"
                            : s.status === "in_progress"
                            ? "info"
                            : "warning"
                        }
                      >
                        {s.status.replace("_", " ").toUpperCase()}
                      </Pill>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 mb-2">
                      <span className="font-medium bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                        Class {s.target_abc_class || "ALL"}
                      </span>
                      <span>•</span>
                      <span>{s.total_items_count} items</span>
                      <span>•</span>
                      {s.blind_count ? (
                        <span className="flex items-center gap-1 text-amber-600 font-medium">
                          <EyeOff className="w-3 h-3" /> Blind Mode
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-slate-500">
                          <Eye className="w-3 h-3" /> Standard
                        </span>
                      )}
                    </div>

                    <div className="flex justify-between items-center text-xs pt-2 border-t border-slate-100 dark:border-slate-800">
                      <span className="text-slate-400">{formatDate(s.scheduled_date)}</span>
                      <span className={s.net_variance_value < 0 ? "text-rose-600 font-medium" : "text-emerald-600 font-medium"}>
                        {money(s.net_variance_value)}
                      </span>
                    </div>
                  </div>
                );
              })}

              {sessions.length === 0 && (
                <div className="text-center py-8 text-sm text-slate-400">
                  No cycle count sessions found. Click "Schedule Cycle Count" to start.
                </div>
              )}
            </div>
          </Panel>
        </div>

        {/* Right Column: Count Sheet & Reconciliation */}
        <div className="lg:col-span-2 space-y-4">
          {currentSession ? (
            <Panel
              title={`Count Sheet: ${currentSession.session_number}`}
              aside={
                <div className="flex gap-2">
                  {currentSession.status === "in_progress" && (
                    <ActionButton
                      tone="primary"
                      size="sm"
                      onClick={handleSaveCounts}
                    >
                      Submit Counts
                    </ActionButton>
                  )}
                  {currentSession.status === "pending_review" && (
                    <ActionButton
                      tone="primary"
                      size="sm"
                      onClick={() => setShowApproveModal(true)}
                    >
                      Approve & Post Adjustments
                    </ActionButton>
                  )}
                </div>
              }
            >
              {/* Session Meta Bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg text-xs mb-4">
                <div>
                  <span className="text-slate-400">Warehouse:</span>
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    {currentSession.warehouse_name} ({currentSession.warehouse_code})
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Target Category:</span>
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    ABC Class {currentSession.target_abc_class || "ALL"}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Count Mode:</span>
                  <div className="font-semibold flex items-center gap-1 text-slate-800 dark:text-slate-200">
                    {currentSession.blind_count ? (
                      <span className="text-amber-600 font-medium flex items-center gap-1">
                        <EyeOff className="w-3.5 h-3.5" /> Blind Count (Quantities Masked)
                      </span>
                    ) : (
                      <span className="text-slate-600 flex items-center gap-1">
                        <Eye className="w-3.5 h-3.5" /> Open Count
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Net Discrepancy Value:</span>
                  <div className={`font-semibold ${currentSession.net_variance_value < 0 ? "text-rose-600" : "text-emerald-600"}`}>
                    {money(currentSession.net_variance_value)}
                  </div>
                </div>
              </div>

              {/* Items Grid */}
              <DataTable
                columns={[
                  "SKU / Item",
                  "Location",
                  "Batch Lot",
                  "System Qty",
                  "Physical Count",
                  "Variance",
                  "Status",
                  "Actions",
                ]}
              >
                {currentLines.map((line) => {
                  const inputVal = countInputs[line.id] ?? (line.counted_qty !== null ? String(line.counted_qty) : "");
                  return (
                    <TableRow
                      key={line.id}
                      cells={[
                        <div>
                          <div className="font-medium text-slate-900 dark:text-slate-100">{line.sku}</div>
                          <div className="text-xs text-slate-500 truncate max-w-[180px]">{line.product_name}</div>
                        </div>,
                        <span className="font-mono text-xs">{line.location_code}</span>,
                        <span className="text-xs text-slate-600 dark:text-slate-400">{line.batch_no}</span>,
                        <div className="text-right text-xs">
                          {line.system_qty !== null ? (
                            qty(line.system_qty)
                          ) : (
                            <span className="text-amber-600 italic">*** Blind ***</span>
                          )}
                        </div>,
                        <div className="text-right">
                          {currentSession.status === "in_progress" ? (
                            <input
                              type="number"
                              step="any"
                              min="0"
                              placeholder="Count..."
                              value={inputVal}
                              onChange={(e) => setCountInputs({ ...countInputs, [line.id]: e.target.value })}
                              className="w-24 text-right px-2 py-1 text-xs border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                          ) : (
                            <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                              {line.counted_qty !== null ? qty(line.counted_qty) : "—"}
                            </span>
                          )}
                        </div>,
                        <div className="text-right text-xs">
                          {line.variance_qty !== null ? (
                            <span className={line.variance_qty < 0 ? "text-rose-600 font-bold" : line.variance_qty > 0 ? "text-emerald-600 font-bold" : "text-slate-400"}>
                              {line.variance_qty > 0 ? `+${line.variance_qty}` : line.variance_qty}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </div>,
                        <Pill
                          tone={
                            line.status === "approved" || line.status === "adjusted"
                              ? "success"
                              : line.status === "recount_requested"
                              ? "warning"
                              : line.status === "pending_review"
                              ? "info"
                              : "muted"
                          }
                        >
                          {line.status.toUpperCase()}
                        </Pill>,
                        <div className="text-right">
                          {currentSession.status !== "completed" && line.variance_qty !== null && line.variance_qty !== 0 && (
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedRecountLineId(line.id);
                                setShowRecountModal(true);
                              }}
                              className="text-xs text-amber-600 hover:text-amber-700 underline"
                            >
                              Recount
                            </button>
                          )}
                        </div>,
                      ]}
                    />
                  );
                })}
              </DataTable>
            </Panel>
          ) : (
            <Panel title="Count Sheet Detail">
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <Search className="w-12 h-12 mb-3 text-slate-300 dark:text-slate-700" />
                <div className="text-sm font-medium">No session selected</div>
                <div className="text-xs text-slate-500 mt-1">
                  Select an audit session from the list on the left to review lines or input counts.
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>

      {/* Modal: Schedule Session */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Schedule Cycle Count Session"
      >
        <form onSubmit={handleGenerateSession} className="space-y-4">
          <Field label="Warehouse">
            <select
              value={selectedWhId}
              onChange={(e) => setSelectedWhId(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              required
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.code})
                </option>
              ))}
            </select>
          </Field>

          <Field label="Counting Method">
            <select
              value={countingType}
              onChange={(e) => setCountingType(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
            >
              <option value="abc_scheduled">ABC Scheduled Velocity Count</option>
              <option value="spot_audit">Random Spot Audit</option>
              <option value="annual_full">Annual Full Physical Inventory</option>
            </select>
          </Field>

          <Field label="Target Velocity Class">
            <select
              value={targetAbc}
              onChange={(e) => setTargetAbc(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
            >
              <option value="A">Class A (Top 20% high value / fast-moving monthly)</option>
              <option value="B">Class B (Medium velocity quarterly)</option>
              <option value="C">Class C (Slow moving semi-annual)</option>
              <option value="ALL">All Active Bins</option>
            </select>
          </Field>

          <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 rounded border border-amber-200 dark:border-amber-900/50">
            <input
              type="checkbox"
              id="blindToggle"
              checked={blindCount}
              onChange={(e) => setBlindCount(e.target.checked)}
              className="rounded text-primary focus:ring-primary"
            />
            <label htmlFor="blindToggle" className="text-xs text-amber-900 dark:text-amber-200 font-medium">
              Blind Count Mode (System quantities hidden from warehouse floor auditors)
            </label>
          </div>

          <Field label="Audit Notes / Instructions">
            <TextInput
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Q4 High-Voltage Battery Pack physical reconciliation"
            />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowCreateModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Generate Session
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Modal: Request Recount */}
      <Modal
        open={showRecountModal}
        onClose={() => setShowRecountModal(false)}
        title="Request Line Item Recount"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Flag this line for secondary blind verification by a separate auditor due to significant discrepancy.
          </p>
          <Field label="Recount Reason">
            <TextInput
              value={recountReason}
              onChange={(e) => setRecountReason(e.target.value)}
              placeholder="e.g. Physical count differs by > 5%; recount adjacent bins"
            />
          </Field>
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setShowRecountModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="ghost" onClick={handleRecount}>
              Confirm Recount
            </ActionButton>
          </div>
        </div>
      </Modal>

      {/* Modal: Approve & Adjust */}
      <Modal
        open={showApproveModal}
        onClose={() => setShowApproveModal(false)}
        title="Supervisor Approval & Stock Ledger Adjustment"
      >
        <div className="space-y-4">
          <div className="p-3 bg-rose-50 dark:bg-rose-950/30 rounded border border-rose-200 dark:border-rose-900/50 text-xs text-rose-800 dark:text-rose-200">
            <strong>Audit Impact Sign-off:</strong> Approving this session will finalize variances and automatically post stock adjustments to the master <strong>StockLedger</strong> and <strong>StockBalance</strong> tables.
          </div>
          <Field label="Supervisor Sign-off Notes">
            <TextInput
              value={supervisorNotes}
              onChange={(e) => setSupervisorNotes(e.target.value)}
              placeholder="e.g. Verified carton damage in Bay 4; write-off approved"
            />
          </Field>
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setShowApproveModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" onClick={handleApproveAdjust}>
              Sign Off & Post Adjustments
            </ActionButton>
          </div>
        </div>
      </Modal>
    </Shell>
  );
}
