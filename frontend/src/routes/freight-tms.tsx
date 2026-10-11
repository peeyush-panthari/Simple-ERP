import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  FileCheck,
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
import { qty } from "@/lib/format";

interface ContainerRecord {
  id: string;
  container_number: string;
  booking_reference: string;
  container_type: string;
  carrier_name: string;
  origin_port: string;
  destination_port: string;
  vessel_name: string | null;
  voyage_number: string | null;
  etd: string | null;
  eta: string | null;
  discharge_date: string | null;
  status: string;
  total_volume_cbm: number;
  total_weight_kg: number;
  volume_utilization_pct: number;
  weight_utilization_pct: number;
  demurrage_days_left: number | null;
  demurrage_risk: "safe" | "high_risk" | "penalty_incurred";
  contracted_freight_cost: number;
  audited_freight_cost: number;
  items_count: number;
}

export default function FreightTmsPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [containerNo, setContainerNo] = useState("");
  const [bookingRef, setBookingRef] = useState("");
  const [containerType, setContainerType] = useState("40HC");
  const [originPort, setOriginPort] = useState("Nhava Sheva (INNSA)");
  const [destPort, setDestPort] = useState("Port of Rotterdam (NLRTM)");
  const [vesselName, setVesselName] = useState("EVER GIVEN");
  const [freightCost, setFreightCost] = useState("2450");

  const [packingContainer, setPackingContainer] = useState<ContainerRecord | null>(null);
  const [packQty, setPackQty] = useState("100");
  const [packCbm, setPackCbm] = useState("0.08");
  const [packWeight, setPackWeight] = useState("12.5");
  const [pkgType, setPkgType] = useState("Carton");

  const [auditContainer, setAuditContainer] = useState<ContainerRecord | null>(null);
  const [billedRate, setBilledRate] = useState("");

  const { data: containersData } = useQuery({
    queryKey: ["freight-tms", "containers"],
    queryFn: () => api<{ containers: ContainerRecord[] }>("GET", "/api/v1/freight-tms/containers"),
  });

  const containers = containersData?.containers || [];

  const handleCreateContainer = async () => {
    if (!containerNo.trim() || !bookingRef.trim()) return;
    await api("POST", "/api/v1/freight-tms/containers", {
      json: {
        container_number: containerNo.trim(),
        booking_reference: bookingRef.trim(),
        container_type: containerType,
        origin_port: originPort,
        destination_port: destPort,
        vessel_name: vesselName,
        contracted_freight_cost: parseFloat(freightCost) || 0,
      },
    });
    setShowCreateModal(false);
    setContainerNo("");
    setBookingRef("");
    qc.invalidateQueries({ queryKey: ["freight-tms"] });
  };

  const handlePackItem = async () => {
    if (!packingContainer) return;
    await api("POST", `/api/v1/freight-tms/containers/${packingContainer.id}/pack-item`, {
      json: {
        product_id: "00000000-0000-0000-0000-000000000000",
        quantity: parseFloat(packQty) || 1,
        unit_cbm: parseFloat(packCbm) || 0.01,
        unit_weight_kg: parseFloat(packWeight) || 1.0,
        package_type: pkgType,
      },
    });
    setPackingContainer(null);
    qc.invalidateQueries({ queryKey: ["freight-tms"] });
  };

  const handleAuditRate = async () => {
    if (!auditContainer || !billedRate) return;
    const res = await api<any>("POST", `/api/v1/freight-tms/containers/${auditContainer.id}/audit-rate?billed_cost=${billedRate}`);
    alert(`Freight Audit Complete: ${res.audit_verdict} (Variance: $${res.variance_amount})`);
    setAuditContainer(null);
    setBilledRate("");
    qc.invalidateQueries({ queryKey: ["freight-tms"] });
  };

  const avgFill = containers.length
    ? containers.reduce((acc, c) => acc + c.volume_utilization_pct, 0) / containers.length
    : 0;
  const highRiskDemurrage = containers.filter((c) => c.demurrage_risk !== "safe").length;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="Container & Freight Consolidation TMS"
          description="Volumetric 3D container stuffing, LCL to FCL ocean pooling, port demurrage countdown radar & carrier tariff rate audits"
          actions={
            <div className="flex gap-2">
              <ActionButton
                tone="ghost"
                size="sm"
                onClick={() => qc.invalidateQueries({ queryKey: ["freight-tms"] })}
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
                Book Container
              </ActionButton>
            </div>
          }
        />

        {/* High-level KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Active Marine Containers"
            value={containers.length.toString()}
            hint="Consolidation in progress"
            tone="info"
          />
          <StatCard
            label="Average Volume Utilization"
            value={`${avgFill.toFixed(1)}%`}
            hint="Target: > 85% Fill"
            tone="success"
          />
          <StatCard
            label="Port Demurrage Alerts"
            value={highRiskDemurrage.toString()}
            hint="Free-time expiration warnings"
            tone={highRiskDemurrage > 0 ? "destructive" : "muted"}
          />
          <StatCard
            label="Tariff Rate Audit"
            value="3-Way Match"
            hint="BAF / CAF / THC verified"
            tone="warning"
          />
        </div>

        {/* Marine Container Consolidation Table */}
        <Panel title="Ocean & Multi-Modal Freight Consolidation Manifests">
          <DataTable
            columns={[
              "Container # & Type",
              "Voyage & Vessel",
              "Route (Port -> Port)",
              "CBM Fill %",
              "Weight Fill %",
              "Demurrage Radar",
              "Freight Spend",
              "Status",
              "Actions",
            ]}
          >
            {containers.map((c) => (
              <TableRow
                key={c.id}
                cells={[
                  <div>
                    <div className="font-semibold text-[var(--foreground)] font-mono">{c.container_number}</div>
                    <div className="text-xs text-[var(--muted-foreground)]">Type: {c.container_type} | Ref: {c.booking_reference}</div>
                  </div>,
                  <div>
                    <div className="font-medium text-xs text-[var(--foreground)]">{c.vessel_name || "TBA"}</div>
                    <div className="text-[11px] text-[var(--muted-foreground)] font-mono">{c.carrier_name}</div>
                  </div>,
                  <div className="text-xs">
                    <div>{c.origin_port}</div>
                    <div className="text-[var(--muted-foreground)]">↳ {c.destination_port}</div>
                  </div>,
                  <div>
                    <div className="font-mono text-xs font-semibold">{c.volume_utilization_pct}%</div>
                    <div className="w-20 bg-[var(--muted)] rounded-full h-1.5 mt-1 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full"
                        style={{ width: `${Math.min(100, c.volume_utilization_pct)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-[var(--muted-foreground)]">{c.total_volume_cbm} CBM</span>
                  </div>,
                  <div>
                    <div className="font-mono text-xs font-semibold">{c.weight_utilization_pct}%</div>
                    <span className="text-[10px] text-[var(--muted-foreground)]">{qty(c.total_weight_kg, "kg")}</span>
                  </div>,
                  <div>
                    {c.demurrage_days_left !== null ? (
                      <Pill tone={c.demurrage_risk === "penalty_incurred" ? "destructive" : (c.demurrage_risk === "high_risk" ? "warning" : "success")}>
                        {c.demurrage_days_left} Free Days
                      </Pill>
                    ) : (
                      <span className="text-xs text-[var(--muted-foreground)]">On Water (Sailed)</span>
                    )}
                  </div>,
                  <div className="font-mono text-xs">
                    <div>${c.contracted_freight_cost.toFixed(2)}</div>
                    {c.audited_freight_cost > 0 && (
                      <div className="text-[10px] text-emerald-500">Audited: ${c.audited_freight_cost.toFixed(2)}</div>
                    )}
                  </div>,
                  <Pill tone={c.status === "stuffing" ? "warning" : "info"}>{c.status.toUpperCase()}</Pill>,
                  <div className="flex gap-2">
                    <ActionButton
                      size="sm"
                      tone="ghost"
                      onClick={() => setPackingContainer(c)}
                    >
                      <Box className="h-3 w-3 mr-1" />
                      Pack Cargo
                    </ActionButton>
                    <ActionButton
                      size="sm"
                      tone="ghost"
                      onClick={() => {
                        setAuditContainer(c);
                        setBilledRate(c.contracted_freight_cost.toString());
                      }}
                    >
                      <FileCheck className="h-3 w-3 mr-1" />
                      Audit
                    </ActionButton>
                  </div>,
                ]}
              />
            ))}
          </DataTable>
        </Panel>

        {/* Modal: Book Container */}
        {showCreateModal && (
          <Modal
            open={showCreateModal}
            title="Book Consolidated Marine Container"
            onClose={() => setShowCreateModal(false)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handleCreateContainer}>
                  Create Consolidation Plan
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="ISO Container #" required>
                  <TextInput
                    placeholder="e.g. MSCU-918234-1"
                    value={containerNo}
                    onChange={(e) => setContainerNo(e.target.value)}
                  />
                </Field>
                <Field label="Shipping Line Booking Ref" required>
                  <TextInput
                    placeholder="e.g. BKG-2026-778"
                    value={bookingRef}
                    onChange={(e) => setBookingRef(e.target.value)}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Container Size">
                  <select
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                    value={containerType}
                    onChange={(e) => setContainerType(e.target.value)}
                  >
                    <option value="20GP">20' Standard GP (33.2 CBM, 28T)</option>
                    <option value="40GP">40' Standard GP (67.7 CBM, 28.6T)</option>
                    <option value="40HC">40' High Cube HC (76.3 CBM, 28.5T)</option>
                    <option value="45HC">45' High Cube HC (86.0 CBM, 27.8T)</option>
                  </select>
                </Field>
                <Field label="Contracted Freight Fee ($)">
                  <TextInput
                    type="number"
                    value={freightCost}
                    onChange={(e) => setFreightCost(e.target.value)}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Origin Port">
                  <TextInput
                    value={originPort}
                    onChange={(e) => setOriginPort(e.target.value)}
                  />
                </Field>
                <Field label="Destination Port">
                  <TextInput
                    value={destPort}
                    onChange={(e) => setDestPort(e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Vessel & Voyage">
                <TextInput
                  value={vesselName}
                  onChange={(e) => setVesselName(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}

        {/* Modal: 3D Pack Cargo */}
        {packingContainer && (
          <Modal
            open={!!packingContainer}
            title={`Pack Cargo Line into ${packingContainer.container_number}`}
            onClose={() => setPackingContainer(null)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setPackingContainer(null)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handlePackItem}>
                  Confirm Stuffing & Recalculate
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <p className="text-xs text-[var(--muted-foreground)]">
                The 3D packing engine dynamically checks remaining cubic capacity and payload axle weight before slotting.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Package Quantity" required>
                  <TextInput
                    type="number"
                    value={packQty}
                    onChange={(e) => setPackQty(e.target.value)}
                  />
                </Field>
                <Field label="Package Form">
                  <select
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                    value={pkgType}
                    onChange={(e) => setPkgType(e.target.value)}
                  >
                    <option value="Carton">Standard Corrugated Carton</option>
                    <option value="Pallet">Euro Wooden Pallet</option>
                    <option value="Crate">Reinforced Wooden Crate</option>
                  </select>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Unit Volume (CBM)">
                  <TextInput
                    type="number"
                    value={packCbm}
                    onChange={(e) => setPackCbm(e.target.value)}
                  />
                </Field>
                <Field label="Unit Gross Weight (kg)">
                  <TextInput
                    type="number"
                    value={packWeight}
                    onChange={(e) => setPackWeight(e.target.value)}
                  />
                </Field>
              </div>
            </div>
          </Modal>
        )}

        {/* Modal: Freight Tariff Audit */}
        {auditContainer && (
          <Modal
            open={!!auditContainer}
            title={`Carrier Freight Bill Audit: ${auditContainer.container_number}`}
            onClose={() => setAuditContainer(null)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setAuditContainer(null)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handleAuditRate}>
                  Perform 3-Way Audit
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <div className="p-3 bg-[var(--muted)]/20 rounded-lg text-xs space-y-1">
                <div className="flex justify-between">
                  <span>Contracted Ocean Base Tariff:</span>
                  <span className="font-mono font-bold">${auditContainer.contracted_freight_cost}</span>
                </div>
                <div className="flex justify-between text-[var(--muted-foreground)]">
                  <span>Origin / Destination:</span>
                  <span>{auditContainer.origin_port} ➔ {auditContainer.destination_port}</span>
                </div>
              </div>
              <Field label="Carrier Billed Invoice Total ($)" required>
                <TextInput
                  type="number"
                  placeholder="Include BAF, CAF, Bunker and THC surcharges"
                  value={billedRate}
                  onChange={(e) => setBilledRate(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
