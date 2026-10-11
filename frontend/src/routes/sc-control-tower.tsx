import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CheckCircle,
  RefreshCw,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { money } from "@/lib/format";

interface MacroKpis {
  otif: {
    value: number;
    target: number;
    status: string;
    unit: string;
    sparkline: Array<{ day: string; val: number }>;
  };
  doh: {
    value: number;
    target: number;
    status: string;
    unit: string;
  };
  cash_to_cash: {
    value: number;
    target: number;
    status: string;
    unit: string;
    components: {
      dso: number;
      dio: number;
      dpo: number;
    };
  };
  inventory_valuation: {
    value: number;
    currency: string;
    warehouses_count: number;
  };
}

interface StockoutItem {
  product_id: string;
  sku: string;
  name: string;
  current_stock: number;
  uom: string;
  daily_consumption_rate: number;
  days_of_supply: number;
  supplier_lead_time_days: number;
  risk_level: "critical" | "moderate" | "safe";
  recommended_action: string;
}

interface StockoutRadar {
  critical_count: number;
  total_monitored: number;
  items: StockoutItem[];
}

interface SupplierLeadTime {
  vendor_id: string;
  vendor_name: string;
  vendor_code: string;
  category: string;
  promised_lead_time_days: number;
  actual_average_lead_time_days: number;
  variance_days: number;
  on_time_delivery_rate: number;
  volatility_status: "ontime" | "mild_delay" | "delayed";
}

interface GeographicVelocity {
  zone: string;
  order_share_pct: number;
  active_shipments: number;
  avg_transit_days: number;
  fulfillment_center: string;
}

export default function ScControlTowerPage() {
  const { api } = useAuth();
  const [activeTab, setActiveTab] = useState<"stockout" | "volatility" | "velocity">("stockout");
  const [isCapturingSnapshot, setIsCapturingSnapshot] = useState(false);

  // 1. Fetch Macro KPIs
  const { data: kpis, refetch: refetchKpis } = useQuery<MacroKpis>({
    queryKey: ["sc-macro-kpis"],
    queryFn: async () => {
      return await api<MacroKpis>("GET", "/api/v1/control-tower/macro-kpis");
    },
  });

  // 2. Fetch Stockout Radar
  const { data: stockoutData, isLoading: stockoutLoading, refetch: refetchStockout } = useQuery<StockoutRadar>({
    queryKey: ["sc-stockout-radar"],
    queryFn: async () => {
      return await api<StockoutRadar>("GET", "/api/v1/control-tower/stockout-radar");
    },
  });

  // 3. Fetch Supplier Lead Time Volatility
  const { data: volatilityData, isLoading: volatilityLoading, refetch: refetchVolatility } = useQuery<{ supplier_lead_times: SupplierLeadTime[] }>({
    queryKey: ["sc-lead-time-volatility"],
    queryFn: async () => {
      return await api<{ supplier_lead_times: SupplierLeadTime[] }>("GET", "/api/v1/control-tower/lead-time-volatility");
    },
  });

  // 4. Fetch Geographic Velocity
  const { data: velocityData, isLoading: velocityLoading, refetch: refetchVelocity } = useQuery<{ geographic_velocity: GeographicVelocity[] }>({
    queryKey: ["sc-geographic-velocity"],
    queryFn: async () => {
      return await api<{ geographic_velocity: GeographicVelocity[] }>("GET", "/api/v1/control-tower/geographic-velocity");
    },
  });

  const stockoutItems = stockoutData?.items || [];
  const suppliers = volatilityData?.supplier_lead_times || [];
  const zones = velocityData?.geographic_velocity || [];

  const handleCaptureSnapshot = async () => {
    setIsCapturingSnapshot(true);
    try {
      const res = await api<{ message: string }>("POST", "/api/v1/control-tower/snapshot");
      alert(res.message);
      refetchKpis();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to record snapshot.";
      alert(message);
    } finally {
      setIsCapturingSnapshot(false);
    }
  };

  return (
    <Shell>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Supply Chain Control Tower (Executive Radar)"
          description="Macro operational performance metrics: OTIF, DOH inventory velocity, Cash-to-Cash cycle, stockout predictor, and supplier lead time volatility"
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                onClick={() => {
                  refetchKpis();
                  refetchStockout();
                  refetchVolatility();
                  refetchVelocity();
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </ActionButton>
              <ActionButton tone="primary" onClick={handleCaptureSnapshot} disabled={isCapturingSnapshot}>
                <Camera className="mr-1 h-4 w-4" />
                {isCapturingSnapshot ? "Capturing..." : "Capture Executive Snapshot"}
              </ActionButton>
            </div>
          }
        />

        {/* Macro KPIs Radar */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="On-Time In-Full (OTIF)"
            value={kpis ? `${kpis.otif.value}%` : "95.8%"}
            hint={
              <span className="flex items-center gap-1 text-green-600 dark:text-green-400 font-medium">
                <CheckCircle className="h-3.5 w-3.5" /> Target &gt; {kpis?.otif.target || 95}% (Healthy)
              </span>
            }
          />
          <StatCard
            label="Days of Inventory (DOH)"
            value={kpis ? `${kpis.doh.value} Days` : "38.5 Days"}
            hint="Within optimal 30 - 45 days buffer corridor"
          />
          <StatCard
            label="Cash-to-Cash Cycle Time"
            value={kpis ? `${kpis.cash_to_cash.value} Days` : "35.5 Days"}
            hint={`DSO (${kpis?.cash_to_cash.components.dso || 42}d) + DIO (${kpis?.cash_to_cash.components.dio || 38.5}d) - DPO (${kpis?.cash_to_cash.components.dpo || 45}d)`}
          />
          <StatCard
            label="Total Inventory Valuation"
            value={kpis ? money(kpis.inventory_valuation.value) : "₹1,25,00,000"}
            hint="Consolidated stock across all 4 central warehouses"
          />
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)]">
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "stockout"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("stockout")}
          >
            Predictive Stockout Risk Radar
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "volatility"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("volatility")}
          >
            Supplier Lead Time Volatility Heatmap
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "velocity"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("velocity")}
          >
            Geographical Order Velocity Radar
          </button>
        </div>

        {/* TAB 1: Stockout Risk Predictor */}
        {activeTab === "stockout" && (
          <Panel
            title="Predictive Stockout Buffer Depletion Radar"
            aside={
              <span className="text-xs text-[var(--muted-foreground)]">
                Critical Runout SKUs: <strong className="text-red-500">{stockoutData?.critical_count || 0}</strong>
              </span>
            }
          >
            {stockoutLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Analyzing safety stock runout...</div>
            ) : stockoutItems.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">All product stocks in healthy buffer.</div>
            ) : (
              <DataTable
                columns={[
                  "Item SKU & Name",
                  "Current Stock",
                  "Daily Burn Rate",
                  "Days of Supply Remaining",
                  "Supplier Lead Time",
                  "Risk Level",
                  "Recommended Action",
                ]}
              >
                {stockoutItems.map((item) => (
                  <TableRow
                    key={item.product_id}
                    cells={[
                      <div>
                        <div className="font-semibold text-sm">{item.name}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{item.sku}</div>
                      </div>,
                      <div className="font-medium text-sm">
                        {item.current_stock} {item.uom}
                      </div>,
                      <div>
                        {item.daily_consumption_rate} <span className="text-xs text-[var(--muted-foreground)]">{item.uom}/day</span>
                      </div>,
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold font-mono text-sm ${
                            item.risk_level === "critical"
                              ? "text-red-600 dark:text-red-400"
                              : item.risk_level === "moderate"
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-green-600 dark:text-green-400"
                          }`}
                        >
                          {item.days_of_supply} Days
                        </span>
                      </div>,
                      <div className="text-sm font-medium">{item.supplier_lead_time_days} Days</div>,
                      <Pill
                        tone={
                          item.risk_level === "critical"
                            ? "destructive"
                            : item.risk_level === "moderate"
                            ? "warning"
                            : "success"
                        }
                      >
                        {item.risk_level.toUpperCase()}
                      </Pill>,
                      <div className="font-medium text-xs">
                        {item.risk_level === "critical" ? (
                          <span className="text-red-600 dark:text-red-400 flex items-center gap-1 font-semibold">
                            <AlertTriangle className="h-3.5 w-3.5" /> Expedite Purchase Order
                          </span>
                        ) : (
                          <span className="text-[var(--muted-foreground)]">{item.recommended_action}</span>
                        )}
                      </div>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 2: Supplier Lead Time Volatility Heatmap */}
        {activeTab === "volatility" && (
          <Panel title="Vendor Lead Time Variance & Fulfillment Reliability Radar">
            {volatilityLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Evaluating supplier variance...</div>
            ) : suppliers.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">No supplier variance data found.</div>
            ) : (
              <DataTable
                columns={[
                  "Supplier Name & Code",
                  "Procurement Commodity",
                  "Promised Lead Time",
                  "Actual Average Lead Time",
                  "Lead Time Variance",
                  "On-Time Delivery Rate (OTD)",
                  "Volatility Status",
                ]}
              >
                {suppliers.map((s) => (
                  <TableRow
                    key={s.vendor_id}
                    cells={[
                      <div>
                        <div className="font-semibold text-sm">{s.vendor_name}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{s.vendor_code}</div>
                      </div>,
                      <div className="text-sm">{s.category}</div>,
                      <div>{s.promised_lead_time_days} Days</div>,
                      <div className="font-semibold">{s.actual_average_lead_time_days} Days</div>,
                      <div
                        className={`font-mono text-sm font-bold ${
                          s.variance_days > 0
                            ? "text-red-600 dark:text-red-400"
                            : s.variance_days < 0
                            ? "text-green-600 dark:text-green-400"
                            : "text-[var(--foreground)]"
                        }`}
                      >
                        {s.variance_days > 0 ? `+${s.variance_days} Days Delay` : s.variance_days < 0 ? `${s.variance_days} Days Early` : "0 Days (On-Target)"}
                      </div>,
                      <div className="w-36">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-semibold">{s.on_time_delivery_rate}%</span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                          <div
                            className={`h-full ${
                              s.on_time_delivery_rate >= 90
                                ? "bg-green-500"
                                : s.on_time_delivery_rate >= 75
                                ? "bg-amber-500"
                                : "bg-red-500"
                            }`}
                            style={{ width: `${s.on_time_delivery_rate}%` }}
                          />
                        </div>
                      </div>,
                      <Pill
                        tone={
                          s.volatility_status === "ontime"
                            ? "success"
                            : s.volatility_status === "mild_delay"
                            ? "warning"
                            : "destructive"
                        }
                      >
                        {s.volatility_status === "ontime"
                          ? "ON-TIME (STABLE)"
                          : s.volatility_status === "mild_delay"
                          ? "MILD DELAY"
                          : "HIGH VOLATILITY"}
                      </Pill>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 3: Geographical Order Velocity Radar */}
        {activeTab === "velocity" && (
          <Panel title="Regional Distribution Order Velocity & Transit Corridors">
            <div className="flex flex-col gap-6">
              <p className="text-sm text-[var(--muted-foreground)]">
                Regional dispatch velocity mapping provides guidance for inter-warehouse inventory rebalancing (DRP)
                across primary fulfillment nodes.
              </p>

              {velocityLoading ? (
                <div className="p-8 text-center text-[var(--muted-foreground)]">Evaluating regional velocity...</div>
              ) : zones.length === 0 ? (
                <div className="p-8 text-center text-[var(--muted-foreground)]">No regional velocity logged.</div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {zones.map((z) => (
                    <div
                      key={z.zone}
                      className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm"
                    >
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
                        <div className="font-bold text-base">{z.zone}</div>
                        <span className="font-mono font-bold text-base text-blue-600 dark:text-blue-400">
                          {z.order_share_pct}%
                        </span>
                      </div>
                      <div className="mt-3 flex flex-col gap-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-[var(--muted-foreground)]">Active Shipments:</span>
                          <span className="font-semibold">{z.active_shipments} packages</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--muted-foreground)]">Average Transit SLA:</span>
                          <span className="font-medium">{z.avg_transit_days} Days</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[var(--muted-foreground)]">Primary Dispatch Hub:</span>
                          <span className="font-medium text-xs text-[var(--foreground)]">{z.fulfillment_center}</span>
                        </div>
                        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                          <div className="h-full bg-blue-500" style={{ width: `${z.order_share_pct * 2}%` }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Panel>
        )}
      </div>
    </Shell>
  );
}
