import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Lock,
  Plus,
  RefreshCw,
  Send,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  Field,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { date as formatDate, qty } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Scenario {
  id: string;
  scenario_name: string;
  description: string | null;
  planning_horizon_months: number;
  status: string;
  locked_at: string | null;
  created_at: string;
  line_count: number;
  total_demand_qty: number;
  avg_mape_pct: number;
}

interface ForecastLine {
  id: string;
  product_id: string;
  product_name: string;
  sku: string;
  period_date: string;
  statistical_forecast_qty: number;
  sales_override_qty: number | null;
  marketing_uplift_qty: number | null;
  consensus_forecast_qty: number;
  champion_algorithm: string;
  mape_pct: number;
  notes: string | null;
}

export default function ForecastingPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [scenarioName, setScenarioName] = useState("");
  const [horizonMonths, setHorizonMonths] = useState("6");
  const [description, setDescription] = useState("");

  const [editingLineId, setEditingLineId] = useState<string | null>(null);
  const [salesOverrideVal, setSalesOverrideVal] = useState("");
  const [marketingUpliftVal, setMarketingUpliftVal] = useState("");
  const [consensusNotes, setConsensusNotes] = useState("");

  const { data: scenariosData } = useQuery({
    queryKey: ["forecasting", "scenarios"],
    queryFn: () => api<{ scenarios: Scenario[] }>("GET", "/api/v1/forecasting/scenarios"),
  });

  const scenarios = scenariosData?.scenarios || [];
  const activeScenarioId = selectedScenarioId || (scenarios.length > 0 ? scenarios[0].id : null);

  const { data: detailData } = useQuery({
    queryKey: ["forecasting", "scenario", activeScenarioId],
    queryFn: () => api<{ scenario: Scenario; lines: ForecastLine[] }>("GET", `/api/v1/forecasting/scenarios/${activeScenarioId}`),
    enabled: !!activeScenarioId,
  });

  const activeScenario = detailData?.scenario;
  const lines = detailData?.lines || [];

  const handleCreateScenario = async () => {
    if (!scenarioName.trim()) return;
    await api("POST", "/api/v1/forecasting/scenarios", {
      json: {
        scenario_name: scenarioName.trim(),
        description: description.trim() || undefined,
        planning_horizon_months: parseInt(horizonMonths, 10) || 6,
      },
    });
    setShowCreateModal(false);
    setScenarioName("");
    setDescription("");
    qc.invalidateQueries({ queryKey: ["forecasting"] });
  };

  const handleSaveOverride = async (lineId: string) => {
    await api("PATCH", `/api/v1/forecasting/lines/${lineId}`, {
      json: {
        sales_override_qty: salesOverrideVal !== "" ? parseFloat(salesOverrideVal) : undefined,
        marketing_uplift_qty: marketingUpliftVal !== "" ? parseFloat(marketingUpliftVal) : undefined,
        notes: consensusNotes || undefined,
      },
    });
    setEditingLineId(null);
    qc.invalidateQueries({ queryKey: ["forecasting", "scenario", activeScenarioId] });
    qc.invalidateQueries({ queryKey: ["forecasting", "scenarios"] });
  };

  const handleLockScenario = async () => {
    if (!activeScenarioId) return;
    await api("POST", `/api/v1/forecasting/scenarios/${activeScenarioId}/lock`);
    qc.invalidateQueries({ queryKey: ["forecasting"] });
  };

  const handleExportMrp = async () => {
    if (!activeScenarioId) return;
    const res = await api<{ message: string }>("POST", `/api/v1/forecasting/scenarios/${activeScenarioId}/export-mrp`);
    alert(res.message);
  };

  const skusMap = new Map<string, { sku: string; name: string; algo: string; mape: number; periods: ForecastLine[] }>();
  lines.forEach((l) => {
    if (!skusMap.has(l.product_id)) {
      skusMap.set(l.product_id, {
        sku: l.sku,
        name: l.product_name,
        algo: l.champion_algorithm,
        mape: l.mape_pct,
        periods: [],
      });
    }
    skusMap.get(l.product_id)!.periods.push(l);
  });
  const skuRows = Array.from(skusMap.values());

  const totalDemand = lines.reduce((acc, l) => acc + l.consensus_forecast_qty, 0);
  const avgMape = lines.length ? lines.reduce((acc, l) => acc + l.mape_pct, 0) / lines.length : 0;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="S&OP Demand Forecasting & Tournament Engine"
          description="Holt-Winters, Holt's Linear Trend, and Weighted Moving Average model tournament with collaborative consensus overrides"
          actions={
            <div className="flex gap-2">
              <ActionButton
                tone="ghost"
                size="sm"
                onClick={() => qc.invalidateQueries({ queryKey: ["forecasting"] })}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </ActionButton>
              <ActionButton
                tone="primary"
                size="sm"
                onClick={() => setShowCreateModal(true)}
              >
                <Plus className="h-4 w-4 mr-1" />
                New Forecast Run
              </ActionButton>
            </div>
          }
        />

        {/* High-level KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Total Projected Demand"
            value={qty(totalDemand)}
            hint="Across active horizon"
            tone="info"
          />
          <StatCard
            label="Avg Model Accuracy"
            value={`${(100 - avgMape).toFixed(1)}%`}
            hint={`Mean MAPE: ${avgMape.toFixed(1)}%`}
            tone="success"
          />
          <StatCard
            label="Active Scenarios"
            value={scenarios.length.toString()}
            hint={activeScenario?.status.toUpperCase() || "None"}
            tone="muted"
          />
          <StatCard
            label="Tournament Algorithm"
            value="Holt-Winters"
            hint="Best back-tested fit"
            tone="warning"
          />
        </div>

        {/* Scenario Selection Header & Governance Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xs">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-[var(--muted-foreground)]">Select Scenario:</span>
            <select
              className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)] focus:outline-hidden"
              value={activeScenarioId || ""}
              onChange={(e) => setSelectedScenarioId(e.target.value)}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.scenario_name} ({s.planning_horizon_months}M) — {s.status.toUpperCase()}
                </option>
              ))}
            </select>
            {activeScenario && (
              <Pill tone={activeScenario.status === "locked" ? "success" : "warning"}>
                {activeScenario.status.toUpperCase()}
              </Pill>
            )}
          </div>

          {activeScenario && (
            <div className="flex items-center gap-2">
              {activeScenario.status !== "locked" ? (
                <ActionButton
                  tone="ghost"
                  size="sm"
                  onClick={handleLockScenario}
                >
                  <Lock className="h-4 w-4 mr-1" />
                  Lock Consensus Plan
                </ActionButton>
              ) : (
                <ActionButton
                  tone="primary"
                  size="sm"
                  onClick={handleExportMrp}
                >
                  <Send className="h-4 w-4 mr-1" />
                  Push to MRP Gross Demand
                </ActionButton>
              )}
            </div>
          )}
        </div>

        {/* Matrix Workbench Table */}
        <Panel title="Collaborative Consensus Grid (Monthly Buckets per SKU)">
          {skuRows.length === 0 ? (
            <div className="p-8 text-center text-[var(--muted-foreground)]">
              No forecast lines found. Click "New Forecast Run" to execute the statistical model tournament.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[var(--muted)]/50 text-[var(--muted-foreground)] text-xs font-semibold">
                    <th className="p-3">SKU & Item Name</th>
                    <th className="p-3">Champion Model</th>
                    <th className="p-3">Error (MAPE)</th>
                    {skuRows[0]?.periods.map((p) => (
                      <th key={p.id} className="p-3 text-right">
                        {formatDate(p.period_date)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {skuRows.map((row) => (
                    <tr key={row.sku} className="hover:bg-[var(--muted)]/20 transition-colors">
                      <td className="p-3">
                        <div className="font-semibold text-[var(--foreground)]">{row.sku}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">{row.name}</div>
                      </td>
                      <td className="p-3">
                        <Pill tone="info">{row.algo}</Pill>
                      </td>
                      <td className="p-3 text-xs font-mono font-medium text-[var(--foreground)]">
                        {row.mape.toFixed(1)}%
                      </td>
                      {row.periods.map((p) => (
                        <td key={p.id} className="p-3 text-right">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingLineId(p.id);
                              setSalesOverrideVal(p.sales_override_qty?.toString() || "");
                              setMarketingUpliftVal(p.marketing_uplift_qty?.toString() || "");
                              setConsensusNotes(p.notes || "");
                            }}
                            className={cn(
                              "inline-flex flex-col items-end px-2.5 py-1 rounded-md text-right transition-all cursor-pointer",
                              p.sales_override_qty !== null || p.marketing_uplift_qty !== null
                                ? "bg-amber-500/10 border border-amber-500/30 text-amber-500"
                                : "hover:bg-[var(--muted)] text-[var(--foreground)]"
                            )}
                          >
                            <span className="font-bold font-mono">{qty(p.consensus_forecast_qty)}</span>
                            <span className="text-[10px] text-[var(--muted-foreground)]">
                              Stat: {qty(p.statistical_forecast_qty)}
                            </span>
                          </button>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        {/* Modal: New Forecast Run */}
        {showCreateModal && (
          <Modal
            open={showCreateModal}
            title="Execute Demand Forecasting Tournament"
            onClose={() => setShowCreateModal(false)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handleCreateScenario}>
                  Run Model Competition
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <Field label="Scenario Name" required>
                <TextInput
                  placeholder="e.g. Q3-Q4 Baseline S&OP"
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                />
              </Field>
              <Field label="Planning Horizon (Months)" required>
                <select
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:outline-hidden"
                  value={horizonMonths}
                  onChange={(e) => setHorizonMonths(e.target.value)}
                >
                  <option value="3">3 Months (Quarterly Short-Range)</option>
                  <option value="6">6 Months (Mid-Range S&OP)</option>
                  <option value="12">12 Months (Annual Operating Plan)</option>
                </select>
              </Field>
              <Field label="Description & Assumptions">
                <TextInput
                  placeholder="Promotion campaign assumptions, holiday season adjustments..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}

        {/* Modal: Edit Consensus Override */}
        {editingLineId && (
          <Modal
            open={!!editingLineId}
            title="Adjust Consensus Demand Bucket"
            onClose={() => setEditingLineId(null)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setEditingLineId(null)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={() => handleSaveOverride(editingLineId)}>
                  Save Consensus Override
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <p className="text-xs text-[var(--muted-foreground)]">
                Input market intelligence or promotional bump. The final consensus quantity will automatically update.
              </p>
              <Field label="Sales Team Override Qty">
                <TextInput
                  type="number"
                  placeholder="e.g. 120"
                  value={salesOverrideVal}
                  onChange={(e) => setSalesOverrideVal(e.target.value)}
                />
              </Field>
              <Field label="Marketing Campaign Uplift Qty">
                <TextInput
                  type="number"
                  placeholder="e.g. 25"
                  value={marketingUpliftVal}
                  onChange={(e) => setMarketingUpliftVal(e.target.value)}
                />
              </Field>
              <Field label="Override Justification & Notes">
                <TextInput
                  placeholder="Customer expansion agreement, advertising campaign..."
                  value={consensusNotes}
                  onChange={(e) => setConsensusNotes(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
