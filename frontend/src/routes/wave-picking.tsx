import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CheckCircle,
  Layers,
  MapPin,
  Package,
  Plus,
  RefreshCw,
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

interface PickWaveRecord {
  id: string;
  wave_number: string;
  warehouse_id: string;
  warehouse_name: string;
  wave_type: string;
  status: string;
  carrier_name: string | null;
  cutoff_time: string | null;
  total_orders: number;
  total_lines: number;
  total_units: number;
  picked_units: number;
  progress_pct: number;
  created_at: string;
}

interface PickWaveOrderLine {
  id: string;
  order_id: string;
  order_number: string;
  customer_name: string;
  sequence_no: number;
  status: string;
  tote_barcode: string | null;
}

interface PickWavePickLine {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  uom: string;
  location_code: string;
  pick_sequence: number;
  batch_no: string | null;
  required_qty: number;
  picked_qty: number;
  status: string;
}

interface OpenOrderCandidate {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name: string;
  status: string;
  total_lines: number;
  total_units: number;
  created_at: string | null;
}

export default function WavePickingPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [selectedWaveId, setSelectedWaveId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form states for creating Wave
  const [selectedWarehouseId, setSelectedWarehouseId] = useState("");
  const [waveType, setWaveType] = useState("carrier_cutoff");
  const [carrierName, setCarrierName] = useState("Blue Dart Express");
  const [notes, setNotes] = useState("");
  const [selectedOrderIds, setSelectedOrderIds] = useState<string[]>([]);

  // 1. Fetch Waves
  const wavesQuery = useQuery({
    queryKey: ["pick-waves"],
    queryFn: () => api<{ waves: PickWaveRecord[] }>("GET", "/api/v1/wave-picking/waves"),
  });
  const waves = wavesQuery.data?.waves ?? [];

  // Auto-select first wave
  const activeWaveId = selectedWaveId || (waves[0]?.id ?? null);

  // 2. Fetch Selected Wave Detail
  const waveDetailQuery = useQuery({
    queryKey: ["pick-wave-detail", activeWaveId],
    queryFn: () =>
      api<{ wave: PickWaveRecord; orders: PickWaveOrderLine[]; lines: PickWavePickLine[] }>(
        "GET",
        `/api/v1/wave-picking/waves/${activeWaveId}`
      ),
    enabled: !!activeWaveId,
  });

  const currentWave = waveDetailQuery.data?.wave;
  const currentOrders = waveDetailQuery.data?.orders ?? [];
  const currentLines = waveDetailQuery.data?.lines ?? [];

  // 3. Fetch Candidate Open Orders
  const openOrdersQuery = useQuery({
    queryKey: ["open-orders-for-wave"],
    queryFn: () => api<{ open_orders: OpenOrderCandidate[] }>("GET", "/api/v1/wave-picking/open-orders"),
    enabled: showCreateModal,
  });
  const openOrders = openOrdersQuery.data?.open_orders ?? [];

  // 4. Fetch Warehouses
  const warehousesQuery = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<{ data: Array<{ id: string; name: string; code: string }> }>("GET", "/api/v1/warehouses"),
  });
  const warehouses = warehousesQuery.data?.data ?? [];

  // Handler: Create Wave
  const handleCreateWave = async (e: React.FormEvent) => {
    e.preventDefault();
    const whId = selectedWarehouseId || (warehouses[0]?.id ?? "");
    if (!whId) {
      alert("Please select a fulfillment warehouse.");
      return;
    }
    if (selectedOrderIds.length === 0) {
      alert("Please select at least one sales order to include in the wave.");
      return;
    }

    try {
      const res = await api<{ id: string; wave_number: string }>("POST", "/api/v1/wave-picking/waves/create", {
        json: {
          warehouse_id: whId,
          wave_type: waveType,
          carrier_name: carrierName,
          order_ids: selectedOrderIds,
          notes,
        },
      });
      setShowCreateModal(false);
      setSelectedOrderIds([]);
      qc.invalidateQueries({ queryKey: ["pick-waves"] });
      setSelectedWaveId(res.id);
      alert(`Pick Wave ${res.wave_number} generated with serpentine pick path!`);
    } catch (err) {
      alert("Failed to create pick wave: " + err);
    }
  };

  // Handler: Confirm Line Pick
  const handleConfirmLinePick = async (lineId: string, requiredQty: number) => {
    if (!activeWaveId) return;
    try {
      await api("POST", `/api/v1/wave-picking/waves/${activeWaveId}/confirm-pick`, {
        json: {
          line_id: lineId,
          picked_qty: requiredQty,
        },
      });
      qc.invalidateQueries({ queryKey: ["pick-wave-detail", activeWaveId] });
      qc.invalidateQueries({ queryKey: ["pick-waves"] });
    } catch (err) {
      alert("Failed to confirm pick: " + err);
    }
  };

  // Handler: Complete Wave
  const handleCompleteWave = async () => {
    if (!activeWaveId) return;
    try {
      await api("POST", `/api/v1/wave-picking/waves/${activeWaveId}/complete`);
      qc.invalidateQueries({ queryKey: ["pick-wave-detail", activeWaveId] });
      qc.invalidateQueries({ queryKey: ["pick-waves"] });
      alert("Wave completed! All constituent orders sorted into consolidation totes.");
    } catch (err) {
      alert("Failed to complete wave: " + err);
    }
  };

  const toggleSelectOrder = (orderId: string) => {
    setSelectedOrderIds((prev) =>
      prev.includes(orderId) ? prev.filter((id) => id !== orderId) : [...prev, orderId]
    );
  };

  return (
    <Shell>
      <PageHeader
        title="Wave & Batch Picking Optimization Engine"
        description="Multi-order batch consolidation, serpentine warehouse routing, carrier cutoff sorting, and put-wall pack consolidation."
        actions={
          <div className="flex gap-2">
            <ActionButton
              tone="primary"
              onClick={() => {
                if (warehouses.length > 0 && !selectedWarehouseId) setSelectedWarehouseId(warehouses[0].id);
                setShowCreateModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              New Pick Wave
            </ActionButton>
            <ActionButton
              tone="ghost"
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["pick-waves"] });
                if (activeWaveId) qc.invalidateQueries({ queryKey: ["pick-wave-detail", activeWaveId] });
              }}
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
          label="Active Waves"
          value={waves.filter((w) => w.status !== "completed").length}
          hint="In fulfillment process"
        />
        <StatCard
          label="Total Orders Batched"
          value={waves.reduce((sum, w) => sum + w.total_orders, 0)}
          hint="Consolidated orders"
        />
        <StatCard
          label="Total Units Picked"
          value={qty(waves.reduce((sum, w) => sum + w.picked_units, 0))}
          hint="Floor units handled"
        />
        <StatCard
          label="Avg Floor Travel Savings"
          value="~58%"
          hint="Vs. discrete order picking"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Waves Registry */}
        <div className="lg:col-span-1 space-y-4">
          <Panel title="Pick Waves Registry">
            <div className="space-y-3">
              {waves.map((w) => {
                const isSelected = w.id === activeWaveId;
                return (
                  <div
                    key={w.id}
                    onClick={() => setSelectedWaveId(w.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                          {w.wave_number}
                        </span>
                        <div className="text-xs text-slate-500">{w.warehouse_name}</div>
                      </div>
                      <Pill
                        tone={
                          w.status === "completed"
                            ? "success"
                            : w.status === "picked"
                            ? "info"
                            : w.status === "in_progress"
                            ? "warning"
                            : "muted"
                        }
                      >
                        {w.status.replace("_", " ").toUpperCase()}
                      </Pill>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 mb-2">
                      <span>{w.total_orders} Orders</span>
                      <span>•</span>
                      <span>{w.total_lines} SKUs</span>
                      <span>•</span>
                      <span>{qty(w.total_units)} Units</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="space-y-1 mb-2">
                      <div className="flex justify-between text-[11px] text-slate-500">
                        <span>Pick Progress</span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">
                          {w.progress_pct}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, w.progress_pct)}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex justify-between items-center text-xs pt-2 border-t border-slate-100 dark:border-slate-800 text-slate-400">
                      <span>{w.carrier_name || "Express Delivery"}</span>
                      <span>{formatDate(w.created_at)}</span>
                    </div>
                  </div>
                );
              })}

              {waves.length === 0 && (
                <div className="text-center py-8 text-sm text-slate-400">
                  No pick waves found. Click "New Pick Wave" to consolidate orders.
                </div>
              )}
            </div>
          </Panel>
        </div>

        {/* Right Column: Wave Detail & Consolidated Pick Path */}
        <div className="lg:col-span-2 space-y-4">
          {currentWave ? (
            <>
              <Panel
                title={`Pick Wave: ${currentWave.wave_number}`}
                aside={
                  <div className="flex gap-2">
                    {currentWave.status !== "completed" && (
                      <ActionButton tone="primary" size="sm" onClick={handleCompleteWave}>
                        <Check className="w-4 h-4 mr-1.5" />
                        Finalize Wave & Pack
                      </ActionButton>
                    )}
                  </div>
                }
              >
                {/* Meta summary */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg text-xs mb-4">
                  <div>
                    <span className="text-slate-400">Warehouse:</span>
                    <div className="font-semibold text-slate-800 dark:text-slate-200">
                      {currentWave.warehouse_name}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-400">Wave Optimization:</span>
                    <div className="font-semibold text-slate-800 dark:text-slate-200">
                      {currentWave.wave_type.replace("_", " ").toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-400">Carrier Cutoff:</span>
                    <div className="font-semibold text-slate-800 dark:text-slate-200">
                      {currentWave.carrier_name || "Direct Dispatch"}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-400">Fulfillment Progress:</span>
                    <div className="font-semibold text-emerald-600">
                      {qty(currentWave.picked_units)} / {qty(currentWave.total_units)} Units ({currentWave.progress_pct}%)
                    </div>
                  </div>
                </div>

                {/* Serpentine Pick Path Table */}
                <div className="mb-6">
                  <h3 className="text-xs font-semibold uppercase text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-primary" />
                    Serpentine Aisle-Optimized Pick Path
                  </h3>
                  <DataTable
                    columns={[
                      "Seq #",
                      "Bin Location",
                      "SKU / Description",
                      "Required Qty",
                      "Picked Qty",
                      "Status",
                      "Action",
                    ]}
                  >
                    {currentLines.map((line) => (
                      <TableRow
                        key={line.id}
                        cells={[
                          <span className="font-mono font-bold text-xs text-primary">
                            #{line.pick_sequence}
                          </span>,
                          <div className="font-mono font-bold text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded w-fit">
                            {line.location_code}
                          </div>,
                          <div>
                            <div className="font-medium text-xs">{line.sku}</div>
                            <div className="text-[10px] text-slate-400 truncate max-w-[160px]">
                              {line.product_name}
                            </div>
                          </div>,
                          <div className="text-xs font-semibold">
                            {qty(line.required_qty)} {line.uom}
                          </div>,
                          <div className="text-xs font-bold text-emerald-600">
                            {qty(line.picked_qty)} {line.uom}
                          </div>,
                          <Pill tone={line.status === "picked" ? "success" : "warning"}>
                            {line.status.toUpperCase()}
                          </Pill>,
                          <div>
                            {line.status !== "picked" && (
                              <button
                                type="button"
                                onClick={() => handleConfirmLinePick(line.id, line.required_qty)}
                                className="text-xs text-primary font-medium hover:underline flex items-center gap-1"
                              >
                                <CheckCircle className="w-3.5 h-3.5" /> Pick
                              </button>
                            )}
                          </div>,
                        ]}
                      />
                    ))}
                  </DataTable>
                </div>

                {/* Constituent Orders Table */}
                <div>
                  <h3 className="text-xs font-semibold uppercase text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                    <Package className="w-3.5 h-3.5 text-primary" />
                    Batched Customer Orders & Consolidation Totes
                  </h3>
                  <DataTable
                    columns={[
                      "Order #",
                      "Customer Name",
                      "Tote Barcode",
                      "Sort Status",
                    ]}
                  >
                    {currentOrders.map((ord) => (
                      <TableRow
                        key={ord.id}
                        cells={[
                          <span className="font-mono font-bold text-xs">{ord.order_number}</span>,
                          <span className="text-xs">{ord.customer_name}</span>,
                          <div className="font-mono text-xs bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded w-fit border border-amber-200 dark:border-amber-900/50">
                            {ord.tote_barcode}
                          </div>,
                          <Pill tone={ord.status === "packed" ? "success" : "info"}>
                            {ord.status.toUpperCase()}
                          </Pill>,
                        ]}
                      />
                    ))}
                  </DataTable>
                </div>
              </Panel>
            </>
          ) : (
            <Panel title="Wave Details">
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <Layers className="w-12 h-12 mb-3 text-slate-300 dark:text-slate-700" />
                <div className="text-sm font-medium">No wave selected</div>
                <div className="text-xs text-slate-500 mt-1">
                  Select a pick wave from the left list to review the serpentine pick path or confirm picks.
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>

      {/* Modal: New Pick Wave */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Generate Wave & Batch Picking Plan"
      >
        <form onSubmit={handleCreateWave} className="space-y-4">
          <Field label="Warehouse Facility">
            <select
              value={selectedWarehouseId}
              onChange={(e) => setSelectedWarehouseId(e.target.value)}
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

          <div className="grid grid-cols-2 gap-3">
            <Field label="Wave Optimization Strategy">
              <select
                value={waveType}
                onChange={(e) => setWaveType(e.target.value)}
                className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              >
                <option value="carrier_cutoff">Carrier Departure Cutoff</option>
                <option value="zone_batch">Aisle Zone Batching</option>
                <option value="single_line_multi_order">Single-Line Multi-Order High Velocity</option>
              </select>
            </Field>

            <Field label="Outbound Carrier / Cutoff">
              <TextInput
                value={carrierName}
                onChange={(e) => setCarrierName(e.target.value)}
                placeholder="e.g. Blue Dart Express - 17:00 Cutoff"
              />
            </Field>
          </div>

          <Field label="Wave Notes / Instructions">
            <TextInput
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Batching North Zone e-commerce dispatches"
            />
          </Field>

          {/* Orders Checklist */}
          <div className="space-y-2 pt-2">
            <div className="flex justify-between items-center text-xs font-semibold text-slate-700 dark:text-slate-300">
              <span>Select Sales Orders to Batch ({selectedOrderIds.length} selected):</span>
              <button
                type="button"
                onClick={() => setSelectedOrderIds(openOrders.map((o) => o.id))}
                className="text-primary hover:underline text-[11px]"
              >
                Select All ({openOrders.length})
              </button>
            </div>

            <div className="max-h-56 overflow-y-auto space-y-2 border p-2 rounded-md bg-slate-50 dark:bg-slate-900">
              {openOrders.map((ord) => {
                const checked = selectedOrderIds.includes(ord.id);
                return (
                  <div
                    key={ord.id}
                    onClick={() => toggleSelectOrder(ord.id)}
                    className={`flex items-center justify-between p-2 rounded cursor-pointer border transition-all ${
                      checked
                        ? "bg-white dark:bg-slate-800 border-primary shadow-xs"
                        : "bg-white/50 dark:bg-slate-800/50 border-transparent hover:border-slate-300"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {}}
                        className="rounded text-primary focus:ring-primary"
                      />
                      <div>
                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                          {ord.order_number}
                        </div>
                        <div className="text-[10px] text-slate-500">{ord.customer_name}</div>
                      </div>
                    </div>
                    <div className="text-right text-xs">
                      <span className="font-semibold">{ord.total_lines} lines</span>
                      <div className="text-[10px] text-slate-400">{qty(ord.total_units)} units</div>
                    </div>
                  </div>
                );
              })}

              {openOrders.length === 0 && (
                <div className="text-center py-6 text-xs text-slate-400">
                  No open unbatched sales orders available. New confirmed orders will appear here automatically.
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowCreateModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Compute & Release Wave
            </ActionButton>
          </div>
        </form>
      </Modal>
    </Shell>
  );
}
