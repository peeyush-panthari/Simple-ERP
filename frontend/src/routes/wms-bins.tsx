import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Compass,
  Plus,
  Warehouse,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  Modal,
  PageHeader,
  Panel,
  StatCard,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface BinData {
  id: string;
  code: string;
  name: string;
  status: string;
  velocity_class: "A" | "B" | "C";
  capacity_units: number;
  stored_units: number;
  utilization_pct: number;
  max_weight_kg: number;
  barcode: string;
  items_count: number;
  stored_skus: string[];
}

interface WarehouseRef {
  id: string;
  code: string;
  name: string;
}

export default function WmsBinsPage() {
  const { api, can } = useAuth();
  const queryClient = useQueryClient();

  const [selectedWarehouseId, setSelectedWarehouseId] = useState<string>("");
  const [selectedAisle, setSelectedAisle] = useState<string>("");
  const [selectedBin, setSelectedBin] = useState<BinData | null>(null);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [suggestModalOpen, setSuggestModalOpen] = useState(false);
  const [searchSku, setSearchSku] = useState("");

  // 1. Fetch Warehouses
  const { data: warehouses = [] } = useQuery<WarehouseRef[]>({
    queryKey: ["wms-warehouses"],
    queryFn: async () => {
      const res = await api<WarehouseRef[]>("GET", "/api/v1/wms-bins/warehouses");
      if (res.length > 0 && !selectedWarehouseId) {
        setSelectedWarehouseId(res[0].id);
      }
      return res;
    },
  });

  const activeWarehouseId = selectedWarehouseId || (warehouses[0]?.id ?? "");

  // 2. Fetch Rack Matrix
  const { data: matrixData, isLoading: matrixLoading } = useQuery<{
    total_bins: number;
    bins: BinData[];
  }>({
    queryKey: ["rack-matrix", activeWarehouseId, selectedAisle],
    queryFn: () =>
      api<{ total_bins: number; bins: BinData[] }>(
        "GET",
        `/api/v1/wms-bins/rack-matrix?warehouse_id=${activeWarehouseId}${selectedAisle ? `&aisle_code=${encodeURIComponent(selectedAisle)}` : ""}`
      ),
    enabled: !!activeWarehouseId,
  });

  // 3. Fetch Putaway Tasks
  const { data: putawayTasks = [] } = useQuery<any[]>({
    queryKey: ["putaway-tasks", activeWarehouseId],
    queryFn: () =>
      api<any[]>("GET", `/api/v1/wms-bins/tasks?warehouse_id=${activeWarehouseId}`),
    enabled: !!activeWarehouseId,
  });

  const bins = matrixData?.bins || [];

  // Filtered by search SKU
  const displayedBins = bins.filter((b) => {
    if (!searchSku.trim()) return true;
    const q = searchSku.toLowerCase();
    return b.code.toLowerCase().includes(q) || b.stored_skus.some((s) => s.toLowerCase().includes(q));
  });

  // KPI calculations
  const totalCapacity = bins.reduce((s, b) => s + b.capacity_units, 0);
  const totalStored = bins.reduce((s, b) => s + b.stored_units, 0);
  const avgOccupancy = totalCapacity > 0 ? Math.round((totalStored / totalCapacity) * 100) : 0;
  const classACount = bins.filter((b) => b.velocity_class === "A").length;

  return (
    <Shell>
      <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          eyebrow="Warehouse &amp; Logistics"
          title="Warehouse Bin Topology &amp; Directed Putaway"
          description="Manage 3D physical storage coordinates (Zone > Aisle > Rack > Shelf > Bin), ABC velocity slotting, and algorithmic putaway."
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                size="sm"
                onClick={() => setSuggestModalOpen(true)}
                className="gap-2"
              >
                <Compass size={15} />
                <span>Directed Putaway Engine</span>
              </ActionButton>
              <ActionButton
                tone="primary"
                size="sm"
                onClick={() => setGenerateModalOpen(true)}
                disabled={!can("warehouse:write")}
                className="gap-2"
              >
                <Plus size={15} />
                <span>Batch Generate Bins</span>
              </ActionButton>
            </div>
          }
        />

        {/* Facility Selector & Quick Filters */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <div className="flex items-center gap-3">
            <Warehouse className="text-blue-600" size={20} />
            <div className="flex items-center gap-2">
              <label htmlFor="wms-facility-select" className="text-xs font-semibold text-[var(--muted-foreground)]">Facility:</label>
              <select
                id="wms-facility-select"
                aria-label="Warehouse Facility"
                value={activeWarehouseId}
                onChange={(e) => setSelectedWarehouseId(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-semibold"
              >
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} &mdash; {w.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="wms-aisle-select" className="text-xs font-semibold text-[var(--muted-foreground)]">Aisle:</label>
              <select
                id="wms-aisle-select"
                aria-label="Storage Aisle"
                value={selectedAisle}
                onChange={(e) => setSelectedAisle(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-semibold"
              >
                <option value="">All Aisles</option>
                {Array.from(new Set(bins.map((b) => b.code.split("-")[0]))).filter(Boolean).map((a) => (
                  <option key={a} value={a}>
                    Aisle {a}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <label htmlFor="wms-bins-search" className="sr-only">Find SKU or Bin Code</label>
            <TextInput
              id="wms-bins-search"
              placeholder="Find SKU or Bin Code..."
              value={searchSku}
              onChange={(e) => setSearchSku(e.target.value)}
              className="w-full sm:w-56 text-xs"
            />
          </div>
        </div>

        {/* KPI Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Addressable Bins"
            value={bins.length}
            hint="Active storage coordinates"
            tone="info"
          />
          <StatCard
            label="Average Rack Occupancy"
            value={`${avgOccupancy}%`}
            hint={`${totalStored} / ${totalCapacity} units stored`}
            tone={avgOccupancy > 85 ? "warning" : "success"}
          />
          <StatCard
            label="Class A (High Velocity) Slots"
            value={classACount}
            hint="Ergonomic waist-height tiers"
            tone="muted"
          />
          <StatCard
            label="Pending Putaway Tasks"
            value={putawayTasks.length}
            hint="Staged items awaiting slotting"
            tone={putawayTasks.length > 0 ? "warning" : "muted"}
          />
        </div>

        {/* 2D/3D Rack Matrix Visualizer */}
        <Panel
          title="Interactive Storage Rack Matrix"
          subtitle="Visual cells indicate current storage occupancy. Click any bin cell to inspect stored items and weight headroom."
          aside={
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> &lt;60% (Optimal)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-amber-500" /> 60-85% (Medium)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-rose-500" /> &gt;85% (Near Full)
              </span>
            </div>
          }
        >
          {matrixLoading ? (
            <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
              Loading warehouse rack matrix…
            </div>
          ) : displayedBins.length === 0 ? (
            <div className="py-12 text-center text-xs text-[var(--muted-foreground)] space-y-3">
              <p>No storage bins configured for this facility yet.</p>
              <ActionButton
                size="sm"
                tone="primary"
                onClick={() => setGenerateModalOpen(true)}
              >
                Auto-Generate Default Bins
              </ActionButton>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {displayedBins.map((b) => {
                const isSelected = selectedBin?.id === b.id;
                const color =
                  b.utilization_pct === 0
                    ? "border-dashed border-gray-300 dark:border-gray-700 bg-transparent text-[var(--muted-foreground)]"
                    : b.utilization_pct > 85
                    ? "bg-rose-500/15 border-rose-500/40 text-rose-700 dark:text-rose-300"
                    : b.utilization_pct > 55
                    ? "bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-300"
                    : "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300";

                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setSelectedBin(b)}
                    className={cn(
                      "p-3 rounded-xl border text-left transition relative cursor-pointer group hover:scale-[1.02]",
                      color,
                      isSelected && "ring-2 ring-[var(--primary)] ring-offset-2"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold">{b.code}</span>
                      <span className="text-[9px] font-mono font-semibold px-1 py-0.2 rounded bg-black/10 dark:bg-white/10">
                        {b.velocity_class}
                      </span>
                    </div>

                    <div className="mt-2 text-xs truncate font-medium">
                      {b.stored_skus.length > 0 ? b.stored_skus.join(", ") : "Empty Cell"}
                    </div>

                    <div className="mt-1 flex items-center justify-between text-[10px] opacity-80 font-mono">
                      <span>{b.stored_units}/{b.capacity_units} u</span>
                      <span className="font-bold">{b.utilization_pct}%</span>
                    </div>

                    {/* Mini progress bar */}
                    <div className="w-full bg-black/10 dark:bg-white/10 h-1.5 rounded-full overflow-hidden mt-2">
                      <div
                        style={{ width: `${Math.min(100, b.utilization_pct)}%` }}
                        className={cn(
                          "h-full rounded-full",
                          b.utilization_pct > 85
                            ? "bg-rose-500"
                            : b.utilization_pct > 55
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                        )}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        {/* Selected Bin Detail Modal */}
        {selectedBin && (
          <Modal
            open={!!selectedBin}
            onClose={() => setSelectedBin(null)}
            title={`Bin Inspector: ${selectedBin.code}`}
            description={`Barcode: ${selectedBin.barcode} • Velocity Class: ${selectedBin.velocity_class}`}
            footer={
              <ActionButton tone="ghost" size="sm" onClick={() => setSelectedBin(null)}>
                Close
              </ActionButton>
            }
          >
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)]">
                <div>
                  <span className="text-[var(--muted-foreground)] block">Storage Occupancy</span>
                  <span className="text-base font-bold font-mono">
                    {selectedBin.stored_units} / {selectedBin.capacity_units} units ({selectedBin.utilization_pct}%)
                  </span>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)] block">Max Payload Rating</span>
                  <span className="text-base font-bold font-mono">{selectedBin.max_weight_kg} kg</span>
                </div>
              </div>

              <div>
                <h4 className="font-semibold uppercase tracking-wider text-[var(--muted-foreground)] text-[10px] mb-2">
                  Stored Materials in this Cell
                </h4>
                {selectedBin.stored_skus.length === 0 ? (
                  <div className="p-4 text-center rounded-lg border border-dashed text-[var(--muted-foreground)]">
                    This storage bin is currently empty and available for directed putaway.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedBin.stored_skus.map((sku, i) => (
                      <div key={i} className="p-3 rounded-lg border border-[var(--border)] flex justify-between items-center">
                        <span className="font-mono font-bold text-blue-600">{sku}</span>
                        <span className="font-mono text-emerald-600 font-semibold">Available Stock</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Modal>
        )}

        {/* Directed Putaway Engine Modal */}
        {suggestModalOpen && (
          <PutawaySuggestModal
            open={suggestModalOpen}
            onClose={() => setSuggestModalOpen(false)}
            warehouseId={activeWarehouseId}
          />
        )}

        {/* Batch Generate Coordinates Modal */}
        {generateModalOpen && (
          <BatchGenerateModal
            open={generateModalOpen}
            onClose={() => setGenerateModalOpen(false)}
            warehouseId={activeWarehouseId}
            onSuccess={() => {
              queryClient.invalidateQueries({ queryKey: ["rack-matrix"] });
              setGenerateModalOpen(false);
            }}
          />
        )}
      </div>
    </Shell>
  );
}

/** Directed Putaway Engine Simulator Modal */
function PutawaySuggestModal({
  open,
  onClose,
  warehouseId,
}: {
  open: boolean;
  onClose: () => void;
  warehouseId: string;
}) {
  const { api } = useAuth();
  const [sku, setSku] = useState("MOTOR-CNC-901");
  const [quantity, setQuantity] = useState(10);
  const [weightKg, setWeightKg] = useState(25.0);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runSuggest = async () => {
    if (!sku.trim()) return;
    setLoading(true);
    try {
      const res = await api<any>("POST", "/api/v1/wms-bins/suggest", {
        json: {
          warehouse_id: warehouseId,
          sku,
          quantity,
          weight_kg: weightKg,
        },
      });
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Directed Putaway Recommendation Engine"
      description="Algorithmic slotting engine evaluates velocity, rack weight limits, and ergonomic tier access."
      footer={
        <div className="flex items-center justify-end gap-2 w-full">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Close
          </ActionButton>
          <ActionButton
            tone="primary"
            size="sm"
            onClick={runSuggest}
            loading={loading}
          >
            Calculate Optimal Bin
          </ActionButton>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Incoming SKU</label>
            <TextInput value={sku} onChange={(e) => setSku(e.target.value)} />
          </div>
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Quantity</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Gross Weight (kg)</label>
            <input
              type="number"
              value={weightKg}
              onChange={(e) => setWeightKg(Number(e.target.value))}
              className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-mono"
            />
          </div>
        </div>

        {result && (
          <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                <CheckCircle2 size={16} />
                Recommended Target Bin Coordinate
              </span>
              <span className="font-mono font-bold text-sm bg-[var(--card)] px-2.5 py-1 rounded border border-emerald-500/40 text-blue-600">
                {result.suggested_bin?.bin_code}
              </span>
            </div>

            <p className="text-xs text-[var(--muted-foreground)]">
              {result.suggested_bin?.recommendation_reason} &bull; Velocity Rating: Class{" "}
              <strong>{result.suggested_bin?.velocity_class}</strong> &bull; Capacity Headroom:{" "}
              <strong>{result.suggested_bin?.max_weight_kg} kg</strong>
            </p>

            <div className="p-2.5 rounded bg-[var(--card)] border border-[var(--border)] flex items-center justify-between text-[11px] font-mono">
              <span>Barcode Tag: <strong>{result.suggested_bin?.barcode}</strong></span>
              <span className="text-emerald-600 font-bold">Shortest Forklift Path</span>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

/** Batch Generate Coordinates Modal */
function BatchGenerateModal({
  open,
  onClose,
  warehouseId,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  warehouseId: string;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const [zoneCode, setZoneCode] = useState("ZONE-A");
  const [aislePrefix, setAislePrefix] = useState("A01");
  const [racksCount, setRacksCount] = useState(4);
  const [shelvesCount, setShelvesCount] = useState(3);
  const [binsPerShelf, setBinsPerShelf] = useState(2);
  const [loading, setLoading] = useState(false);

  const totalCalculated = racksCount * shelvesCount * binsPerShelf;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api("POST", "/api/v1/wms-bins/batch-generate", {
        json: {
          warehouse_id: warehouseId,
          zone_code: zoneCode,
          aisle_prefix: aislePrefix,
          racks_count: racksCount,
          shelves_count: shelvesCount,
          bins_per_shelf: binsPerShelf,
          default_weight_kg: 500.0,
        },
      });
      onSuccess();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Rapid 3D Coordinate Generator"
      description="Create multi-tiered warehouse hierarchy: Zone > Aisle > Racks > Shelves > Bins with automated velocity tiers."
      footer={
        <div className="flex items-center justify-end gap-2 w-full">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton
            tone="primary"
            size="sm"
            onClick={handleSubmit}
            loading={loading}
          >
            Generate {totalCalculated} Bins
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Zone Code</label>
            <TextInput value={zoneCode} onChange={(e) => setZoneCode(e.target.value)} required />
          </div>
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Aisle Prefix</label>
            <TextInput value={aislePrefix} onChange={(e) => setAislePrefix(e.target.value)} required />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Racks in Aisle</label>
            <input
              type="number"
              min={1}
              max={10}
              value={racksCount}
              onChange={(e) => setRacksCount(Number(e.target.value))}
              className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Shelves / Rack</label>
            <input
              type="number"
              min={1}
              max={6}
              value={shelvesCount}
              onChange={(e) => setShelvesCount(Number(e.target.value))}
              className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-[10px] text-[var(--muted-foreground)] mb-1">Bins / Shelf</label>
            <input
              type="number"
              min={1}
              max={5}
              value={binsPerShelf}
              onChange={(e) => setBinsPerShelf(Number(e.target.value))}
              className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs font-mono"
            />
          </div>
        </div>

        <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-[11px] space-y-1">
          <div className="font-semibold text-blue-700 dark:text-blue-300">Automated Velocity Slotting:</div>
          <div className="text-[var(--muted-foreground)]">
            • Tier 1 (Waist Height) &rarr; Class A (Fastest Moving)<br/>
            • Tier 2 (Chest Height) &rarr; Class B (Standard Moving)<br/>
            • Tier 3+ (Upper Racks) &rarr; Class C (Bulk Storage)
          </div>
        </div>
      </form>
    </Modal>
  );
}
