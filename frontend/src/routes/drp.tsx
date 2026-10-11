import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Boxes,
  CheckCircle2,
  Compass,
  Cpu,
  Layers,
  Network,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Truck,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { date as formatDate, money } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DistributionLane {
  id: string;
  source_warehouse_id: string;
  source_warehouse_name: string;
  source_warehouse_code: string;
  dest_warehouse_id: string;
  dest_warehouse_name: string;
  dest_warehouse_code: string;
  transit_days: number;
  shipping_mode: string;
  carrier_name: string | null;
  cost_per_kg: number;
  is_active: boolean;
}

interface ReplenishmentPolicy {
  id: string;
  dest_warehouse_id: string;
  dest_warehouse_name: string;
  product_id: string;
  sku: string;
  product_name: string;
  policy_type: string;
  safety_stock_qty: number;
  reorder_point_qty: number;
  min_order_qty: number;
  order_multiple: number;
  target_stock_qty: number;
}

interface PlannedTransferOrder {
  id: string;
  pto_no: string;
  run_id: string;
  source_warehouse_id: string;
  source_warehouse_name: string;
  dest_warehouse_id: string;
  dest_warehouse_name: string;
  product_id: string;
  sku: string;
  product_name: string;
  uom: string;
  suggested_qty: number;
  firm_qty: number;
  planned_dispatch_date: string;
  required_delivery_date: string;
  status: string;
  released_transfer_id: string | null;
  released_transfer_number: string | null;
  recommendation_reason: string | null;
  created_at: string | null;
}

interface BucketProjection {
  bucket: string;
  gross_requirement: number;
  scheduled_receipt: number;
  projected_available: number;
  planned_order_receipt: number;
}

interface NetworkProjection {
  lane_id: string;
  source_warehouse: string;
  dest_warehouse: string;
  transit_days: number;
  product_id: string;
  sku: string;
  product_name: string;
  uom: string;
  initial_on_hand: number;
  safety_stock: number;
  target_stock: number;
  buckets: BucketProjection[];
}

export default function DrpPage() {
  const { api, can } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"workbench" | "projections" | "lanes" | "policies">("workbench");
  const [laneModalOpen, setLaneModalOpen] = useState(false);
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [runningDrp, setRunningDrp] = useState(false);
  const [calculationResult, setCalculationResult] = useState<any | null>(null);

  // 1. Fetch Distribution Lanes
  const { data: lanes = [] } = useQuery<DistributionLane[]>({
    queryKey: ["drp-lanes"],
    queryFn: async () => {
      const res = await api<DistributionLane[]>("GET", "/api/v1/drp/lanes");
      return (res as any)?.data || res || [];
    },
  });

  // 2. Fetch Replenishment Policies
  const { data: policies = [] } = useQuery<ReplenishmentPolicy[]>({
    queryKey: ["drp-policies"],
    queryFn: async () => {
      const res = await api<ReplenishmentPolicy[]>("GET", "/api/v1/drp/policies");
      return (res as any)?.data || res || [];
    },
  });

  // 3. Fetch Planned Transfer Orders
  const { data: plannedOrders = [], isLoading: ptoLoading } = useQuery<PlannedTransferOrder[]>({
    queryKey: ["drp-planned-orders"],
    queryFn: async () => {
      const res = await api<PlannedTransferOrder[]>("GET", "/api/v1/drp/planned-orders");
      return (res as any)?.data || res || [];
    },
  });

  // 4. Fetch Warehouses and Products for dropdowns
  const { data: warehouses = [] } = useQuery<any[]>({
    queryKey: ["drp-wh-list"],
    queryFn: async () => {
      const res = await api<any[]>("GET", "/api/v1/warehouses");
      return (res as any)?.data || res || [];
    },
  });

  const { data: products = [] } = useQuery<any[]>({
    queryKey: ["drp-prod-list"],
    queryFn: async () => {
      const res = await api<any[]>("GET", "/api/v1/products");
      return (res as any)?.data || res || [];
    },
  });

  // Run DRP Calculation Engine
  const handleRunDrp = async () => {
    setRunningDrp(true);
    try {
      const res = await api<any>("POST", "/api/v1/drp/calculate", {
        json: { commit: true },
      });
      const data = (res as any)?.data || res;
      setCalculationResult(data);
      queryClient.invalidateQueries({ queryKey: ["drp-planned-orders"] });
      setActiveTab("projections");
    } catch (err: any) {
      alert(err.message || "Failed to execute DRP calculation engine");
    } finally {
      setRunningDrp(false);
    }
  };

  // 1-Click Release PTO to Transfers
  const handleReleasePto = async (ptoId: string) => {
    try {
      const res = await api<any>("POST", `/api/v1/drp/planned-orders/${ptoId}/release`);
      const trf = (res as any)?.data || res;
      alert(`Successfully released PTO! Created live Transfer #${trf.transfer_number}`);
      queryClient.invalidateQueries({ queryKey: ["drp-planned-orders"] });
    } catch (err: any) {
      alert(err.message || "Failed to release planned transfer order");
    }
  };

  // KPI Metrics
  const suggestedPtos = plannedOrders.filter((p) => p.status === "suggested").length;
  const releasedPtos = plannedOrders.filter((p) => p.status === "released").length;
  const totalSuggestedUnits = plannedOrders
    .filter((p) => p.status === "suggested")
    .reduce((s, p) => s + p.firm_qty, 0);

  return (
    <Shell>
      <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          eyebrow="Planning &amp; Supply Chain"
          title="Multi-Echelon DRP (Distribution Requirements Planning)"
          description="Algorithmic multi-tier inventory replenishment across Mother Distribution Centers and Regional Satellite Hubs with time-phased net requirements."
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                size="sm"
                onClick={() => setLaneModalOpen(true)}
                disabled={!can("inventory:write")}
                className="gap-2"
              >
                <Network size={15} />
                <span>Configure Lanes</span>
              </ActionButton>
              <ActionButton
                tone="primary"
                size="sm"
                onClick={handleRunDrp}
                loading={runningDrp}
                disabled={!can("inventory:write")}
                className="gap-2"
              >
                <Cpu size={15} />
                <span>Run DRP Engine</span>
              </ActionButton>
            </div>
          }
        />

        {/* KPI Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Active Distribution Lanes"
            value={lanes.length}
            hint="Parent-to-Hub transport corridors"
            tone="info"
          />
          <StatCard
            label="Replenishment Orders Needed"
            value={suggestedPtos}
            hint={`${totalSuggestedUnits} units suggested`}
            tone={suggestedPtos > 0 ? "warning" : "muted"}
          />
          <StatCard
            label="Transfers Released"
            value={releasedPtos}
            hint="Active in-transit transfers"
            tone="success"
          />
          <StatCard
            label="Replenishment Policies"
            value={policies.length}
            hint="Active SKU Min-Max targets"
            tone="muted"
          />
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2 text-xs font-semibold">
          {[
            { id: "workbench", label: "Planned Transfer Orders (Workbench)", icon: Boxes },
            { id: "projections", label: "Time-Phased Stock Matrix", icon: Layers },
            { id: "lanes", label: "Network Topology & Lanes", icon: Truck },
            { id: "policies", label: "Replenishment Policies", icon: Compass },
          ].map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-xl transition-all",
                  isActive
                    ? "bg-blue-600 text-white font-bold shadow-xs"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
                )}
              >
                <Icon size={14} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* TAB 1: Planned Transfer Orders Workbench */}
        {activeTab === "workbench" && (
          <Panel
            title="Planned Transfer Orders (PTO)"
            subtitle={`${plannedOrders.length} algorithmic replenishment orders generated across network nodes`}
            aside={
              <div className="flex items-center gap-2">
                <ActionButton
                  size="sm"
                  tone="ghost"
                  onClick={() => queryClient.invalidateQueries({ queryKey: ["drp-planned-orders"] })}
                  className="gap-1.5"
                >
                  <RefreshCw size={13} />
                  <span>Refresh</span>
                </ActionButton>
              </div>
            }
          >
            {ptoLoading ? (
              <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
                Loading planned transfer orders…
              </div>
            ) : plannedOrders.length === 0 ? (
              <div className="py-12 text-center text-xs text-[var(--muted-foreground)] space-y-3">
                <Boxes size={28} className="mx-auto text-[var(--muted-foreground)] opacity-50" />
                <p>No planned transfer orders generated yet.</p>
                <ActionButton size="sm" tone="primary" onClick={handleRunDrp} loading={runningDrp}>
                  Run DRP Engine Now
                </ActionButton>
              </div>
            ) : (
              <DataTable
                columns={[
                  "PTO #",
                  "Source DC (Mother)",
                  "Destination Hub",
                  "Product Item",
                  "Qty",
                  "Planned Dispatch",
                  "Required Delivery",
                  "Status",
                  "Action",
                ]}
              >
                {plannedOrders.map((p) => {
                  return (
                    <TableRow
                      key={p.id}
                      cells={[
                        <span className="font-bold text-xs text-blue-600 dark:text-blue-400">
                          {p.pto_no}
                        </span>,
                        <div>
                          <div className="font-medium text-xs text-[var(--foreground)]">
                            {p.source_warehouse_name}
                          </div>
                          <div className="text-[10px] text-[var(--muted-foreground)]">Parent Node</div>
                        </div>,
                        <div>
                          <div className="font-medium text-xs text-[var(--foreground)]">
                            {p.dest_warehouse_name}
                          </div>
                          <div className="text-[10px] text-[var(--muted-foreground)]">Regional Hub</div>
                        </div>,
                        <div>
                          <div className="font-semibold text-xs text-[var(--foreground)]">{p.sku}</div>
                          <div className="text-[10px] text-[var(--muted-foreground)] truncate max-w-[180px]">
                            {p.product_name}
                          </div>
                        </div>,
                        <span className="font-bold text-xs">
                          {p.firm_qty} {p.uom}
                        </span>,
                        <span className="text-xs font-mono text-amber-600 dark:text-amber-400">
                          {formatDate(p.planned_dispatch_date)}
                        </span>,
                        <span className="text-xs font-mono text-[var(--foreground)]">
                          {formatDate(p.required_delivery_date)}
                        </span>,
                        <div>
                          <Pill tone={p.status === "released" ? "success" : "warning"}>
                            {p.status.toUpperCase()}
                          </Pill>
                          {p.released_transfer_number && (
                            <div className="text-[10px] text-[var(--muted-foreground)] font-mono mt-0.5">
                              {p.released_transfer_number}
                            </div>
                          )}
                        </div>,
                        <div>
                          {p.status === "suggested" ? (
                            <ActionButton
                              size="sm"
                              tone="primary"
                              onClick={() => handleReleasePto(p.id)}
                              className="text-[11px] gap-1.5"
                            >
                              <Send size={12} />
                              <span>1-Click Release</span>
                            </ActionButton>
                          ) : (
                            <span className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                              <CheckCircle2 size={13} />
                              Released
                            </span>
                          )}
                        </div>,
                      ]}
                    />
                  );
                })}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 2: Time-Phased Stock Matrix */}
        {activeTab === "projections" && (
          <div className="space-y-6">
            {!calculationResult && (
              <div className="p-8 text-center rounded-2xl border border-[var(--border)] bg-[var(--card)] space-y-3">
                <Sparkles size={28} className="mx-auto text-blue-600" />
                <h3 className="font-bold text-sm">Time-Phased Multi-Echelon Simulation</h3>
                <p className="text-xs text-[var(--muted-foreground)] max-w-md mx-auto">
                  Run the DRP engine to compute 4-week forward inventory projections, safety stock breaches, and lead-time-offset replenishment orders.
                </p>
                <ActionButton size="sm" tone="primary" onClick={handleRunDrp} loading={runningDrp}>
                  Calculate 4-Week Net Projections
                </ActionButton>
              </div>
            )}

            {calculationResult && (
              <div className="space-y-6">
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <span className="text-xs font-semibold text-[var(--muted-foreground)]">Run ID:</span>{" "}
                    <strong className="font-mono text-xs">{calculationResult.run_id}</strong> &bull;{" "}
                    <span className="text-xs text-[var(--muted-foreground)]">Calculated:</span>{" "}
                    <span className="text-xs font-semibold">{formatDate(calculationResult.calculated_at)}</span>
                  </div>
                  <div className="text-xs text-[var(--muted-foreground)]">
                    Generated <strong>{calculationResult.planned_orders_count} planned replenishment orders</strong> across {calculationResult.total_lanes} lanes.
                  </div>
                </div>

                {calculationResult.projections?.map((proj: NetworkProjection, idx: number) => (
                  <div
                    key={`${proj.lane_id}-${proj.sku}-${idx}`}
                    className="p-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] space-y-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-[var(--foreground)]">{proj.sku}</span>
                          <span className="text-xs text-[var(--muted-foreground)]">({proj.product_name})</span>
                        </div>
                        <div className="text-xs text-[var(--muted-foreground)] flex items-center gap-2">
                          <span>{proj.source_warehouse}</span>
                          <ArrowRight size={12} className="text-blue-600" />
                          <strong className="text-[var(--foreground)]">{proj.dest_warehouse}</strong>
                          <span>({proj.transit_days}d transit)</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs font-mono">
                        <div>
                          <span className="text-[var(--muted-foreground)]">Starting On-Hand:</span>{" "}
                          <strong>{proj.initial_on_hand}</strong>
                        </div>
                        <div>
                          <span className="text-[var(--muted-foreground)]">Safety Stock:</span>{" "}
                          <strong className="text-rose-600">{proj.safety_stock}</strong>
                        </div>
                        <div>
                          <span className="text-[var(--muted-foreground)]">Target Stock:</span>{" "}
                          <strong className="text-emerald-600">{proj.target_stock}</strong>
                        </div>
                      </div>
                    </div>

                    {/* Weekly Matrix Grid */}
                    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-[var(--secondary)] text-[var(--muted-foreground)]">
                          <tr>
                            <th className="p-2.5 text-left font-semibold">DRP Planning Metric</th>
                            {proj.buckets.map((b) => (
                              <th key={b.bucket} className="p-2.5 text-center font-semibold">
                                {b.bucket}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]">
                          <tr>
                            <td className="p-2.5 font-medium text-[var(--muted-foreground)]">Gross Requirements (Demand)</td>
                            {proj.buckets.map((b, i) => (
                              <td key={i} className="p-2.5 text-center font-mono">
                                {b.gross_requirement}
                              </td>
                            ))}
                          </tr>
                          <tr>
                            <td className="p-2.5 font-medium text-[var(--muted-foreground)]">Scheduled Receipts (In-Transit)</td>
                            {proj.buckets.map((b, i) => (
                              <td key={i} className="p-2.5 text-center font-mono text-blue-600">
                                {b.scheduled_receipt > 0 ? `+${b.scheduled_receipt}` : "0"}
                              </td>
                            ))}
                          </tr>
                          <tr className="bg-[var(--secondary)]/30 font-semibold">
                            <td className="p-2.5 font-semibold">Projected Available Balance (PAB)</td>
                            {proj.buckets.map((b, i) => (
                              <td
                                key={i}
                                className={cn(
                                  "p-2.5 text-center font-mono",
                                  b.projected_available < proj.safety_stock
                                    ? "text-rose-600 dark:text-rose-400 font-bold"
                                    : "text-emerald-600 dark:text-emerald-400 font-bold"
                                )}
                              >
                                {b.projected_available}
                              </td>
                            ))}
                          </tr>
                          <tr className="bg-blue-50/40 dark:bg-blue-950/20 font-bold">
                            <td className="p-2.5 text-blue-700 dark:text-blue-300">
                              Planned Order Receipts (PTO)
                            </td>
                            {proj.buckets.map((b, i) => (
                              <td key={i} className="p-2.5 text-center font-mono text-blue-600">
                                {b.planned_order_receipt > 0 ? (
                                  <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300">
                                    +{b.planned_order_receipt}
                                  </span>
                                ) : (
                                  "—"
                                )}
                              </td>
                            ))}
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Network Topology & Lanes */}
        {activeTab === "lanes" && (
          <Panel
            title="Multi-Echelon Distribution Network"
            subtitle="Configured transit corridors between Mother Distribution Centers and Hubs"
            aside={
              <ActionButton
                size="sm"
                tone="primary"
                onClick={() => setLaneModalOpen(true)}
                disabled={!can("inventory:write")}
                className="gap-1.5"
              >
                <Plus size={14} />
                <span>Add Distribution Lane</span>
              </ActionButton>
            }
          >
            {lanes.length === 0 ? (
              <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
                No distribution lanes configured yet.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Source DC (Parent)",
                  "Destination Hub (Child)",
                  "Transit Lead Time",
                  "Transport Mode",
                  "Carrier Name",
                  "Freight Cost / kg",
                  "Status",
                ]}
              >
                {lanes.map((l) => (
                  <TableRow
                    key={l.id}
                    cells={[
                      <div>
                        <div className="font-semibold text-xs text-[var(--foreground)]">
                          {l.source_warehouse_name}
                        </div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">{l.source_warehouse_code}</div>
                      </div>,
                      <div>
                        <div className="font-semibold text-xs text-[var(--foreground)]">
                          {l.dest_warehouse_name}
                        </div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">{l.dest_warehouse_code}</div>
                      </div>,
                      <span className="text-xs font-semibold">{l.transit_days} days</span>,
                      <Pill tone="info">{l.shipping_mode}</Pill>,
                      <span className="text-xs text-[var(--muted-foreground)]">{l.carrier_name || "Direct Fleet"}</span>,
                      <span className="text-xs font-mono">{money(l.cost_per_kg)}</span>,
                      <Pill tone={l.is_active ? "success" : "muted"}>
                        {l.is_active ? "ACTIVE" : "INACTIVE"}
                      </Pill>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 4: Replenishment Policies */}
        {activeTab === "policies" && (
          <Panel
            title="SKU Replenishment Policies"
            subtitle="Min-Max safety thresholds, reorder points, and batch sizing"
            aside={
              <ActionButton
                size="sm"
                tone="primary"
                onClick={() => setPolicyModalOpen(true)}
                disabled={!can("inventory:write")}
                className="gap-1.5"
              >
                <Plus size={14} />
                <span>Set SKU Policy</span>
              </ActionButton>
            }
          >
            {policies.length === 0 ? (
              <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
                No SKU replenishment policies defined. Default safety parameters applied automatically.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Destination Warehouse",
                  "SKU",
                  "Policy Type",
                  "Safety Stock",
                  "Reorder Point",
                  "MOQ",
                  "Order Multiple",
                  "Target Stock",
                ]}
              >
                {policies.map((p) => (
                  <TableRow
                    key={p.id}
                    cells={[
                      <span className="font-semibold text-xs text-[var(--foreground)]">
                        {p.dest_warehouse_name}
                      </span>,
                      <div>
                        <div className="font-semibold text-xs text-blue-600">{p.sku}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">{p.product_name}</div>
                      </div>,
                      <Pill tone="info">{p.policy_type.toUpperCase()}</Pill>,
                      <span className="font-bold text-xs text-rose-600">{p.safety_stock_qty}</span>,
                      <span className="text-xs">{p.reorder_point_qty}</span>,
                      <span className="text-xs">{p.min_order_qty}</span>,
                      <span className="text-xs">{p.order_multiple}</span>,
                      <span className="font-bold text-xs text-emerald-600">{p.target_stock_qty}</span>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* Modal: Add Lane */}
        {laneModalOpen && (
          <AddLaneModal
            warehouses={warehouses}
            onClose={() => setLaneModalOpen(false)}
            onSuccess={() => {
              setLaneModalOpen(false);
              queryClient.invalidateQueries({ queryKey: ["drp-lanes"] });
            }}
          />
        )}

        {/* Modal: Set Policy */}
        {policyModalOpen && (
          <SetPolicyModal
            warehouses={warehouses}
            products={products}
            onClose={() => setPolicyModalOpen(false)}
            onSuccess={() => {
              setPolicyModalOpen(false);
              queryClient.invalidateQueries({ queryKey: ["drp-policies"] });
            }}
          />
        )}
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal: Add Lane
// ------------------------------------------------------------------------------------------------
function AddLaneModal({
  warehouses,
  onClose,
  onSuccess,
}: {
  warehouses: any[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const [srcWh, setSrcWh] = useState(warehouses[0]?.id || "");
  const [dstWh, setDstWh] = useState(warehouses[1]?.id || "");
  const [transitDays, setTransitDays] = useState("3");
  const [mode, setMode] = useState("Road");
  const [carrier, setCarrier] = useState("North-South Express");
  const [cost, setCost] = useState("14.50");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("POST", "/api/v1/drp/lanes", {
        json: {
          source_warehouse_id: srcWh,
          dest_warehouse_id: dstWh,
          transit_days: parseInt(transitDays, 10),
          shipping_mode: mode,
          carrier_name: carrier,
          cost_per_kg: parseFloat(cost),
          is_active: true,
        },
      });
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to create distribution lane");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Create Distribution Lane"
      description="Define supply chain replenishment transit corridor between warehouses."
      footer={
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton tone="primary" size="sm" loading={submitting} onClick={handleSubmit}>
            Save Lane
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold mb-1">Source DC (Mother Node):</label>
            <select
              value={srcWh}
              onChange={(e) => setSrcWh(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold mb-1">Destination Hub (Child Node):</label>
            <select
              value={dstWh}
              onChange={(e) => setDstWh(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block font-semibold mb-1">Transit Lead Time (Days):</label>
            <TextInput
              type="number"
              value={transitDays}
              onChange={(e) => setTransitDays(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Transport Mode:</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
            >
              <option value="Road">Road</option>
              <option value="Rail">Rail</option>
              <option value="Air">Air</option>
              <option value="Express">Express</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold mb-1">Cost / kg (₹):</label>
            <TextInput
              type="number"
              step="0.01"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="block font-semibold mb-1">Preferred Carrier / 3PL Name:</label>
          <TextInput
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
            placeholder="e.g. BlueDart / VRL Logistics"
          />
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal: Set Replenishment Policy
// ------------------------------------------------------------------------------------------------
function SetPolicyModal({
  warehouses,
  products,
  onClose,
  onSuccess,
}: {
  warehouses: any[];
  products: any[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const [destWh, setDestWh] = useState(warehouses[0]?.id || "");
  const [productId, setProductId] = useState(products[0]?.id || "");
  const [policyType, setPolicyType] = useState("min_max");
  const [safetyStock, setSafetyStock] = useState("25");
  const [reorderPoint, setReorderPoint] = useState("50");
  const [moq, setMoq] = useState("10");
  const [multiple, setMultiple] = useState("5");
  const [targetStock, setTargetStock] = useState("100");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("POST", "/api/v1/drp/policies", {
        json: {
          dest_warehouse_id: destWh,
          product_id: productId,
          policy_type: policyType,
          safety_stock_qty: parseFloat(safetyStock),
          reorder_point_qty: parseFloat(reorderPoint),
          min_order_qty: parseFloat(moq),
          order_multiple: parseFloat(multiple),
          target_stock_qty: parseFloat(targetStock),
        },
      });
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to save policy");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Configure SKU Replenishment Policy"
      description="Define safety stock buffer and lot-sizing rules."
      footer={
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton tone="primary" size="sm" loading={submitting} onClick={handleSubmit}>
            Save Policy
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold mb-1">Destination Warehouse:</label>
            <select
              value={destWh}
              onChange={(e) => setDestWh(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold mb-1">Product SKU:</label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} &mdash; {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block font-semibold mb-1">Replenishment Policy Method:</label>
          <select
            value={policyType}
            onChange={(e) => setPolicyType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
          >
            <option value="min_max">Min-Max (Safety Stock / Target Buffer)</option>
            <option value="lot_for_lot">Lot-for-Lot (Exact Net Demand)</option>
            <option value="order_up_to">Order-Up-To Level</option>
            <option value="fixed_order_qty">Fixed Order Quantity</option>
          </select>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block font-semibold mb-1">Safety Stock (SS):</label>
            <TextInput
              type="number"
              value={safetyStock}
              onChange={(e) => setSafetyStock(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Reorder Point (ROP):</label>
            <TextInput
              type="number"
              value={reorderPoint}
              onChange={(e) => setReorderPoint(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Target Stock (Max):</label>
            <TextInput
              type="number"
              value={targetStock}
              onChange={(e) => setTargetStock(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold mb-1">Min Order Qty (MOQ):</label>
            <TextInput
              type="number"
              value={moq}
              onChange={(e) => setMoq(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Order Multiple / Pallet Size:</label>
            <TextInput
              type="number"
              value={multiple}
              onChange={(e) => setMultiple(e.target.value)}
              required
            />
          </div>
        </div>
      </form>
    </Modal>
  );
}
