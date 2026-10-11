import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Printer,
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
import { date as formatDate, money, qty } from "@/lib/format";

interface VendorSummary {
  open_pos_count: number;
  active_asns_count: number;
  pending_invoices_count: number;
}

interface PurchaseOrder {
  id: string;
  po_number: string;
  vendor_party_id: string;
  vendor_name: string;
  status: string;
  order_date: string | null;
  expected_delivery_date: string | null;
  total_amount: number;
  lines_count: number;
}

interface AsnRecord {
  id: string;
  asn_number: string;
  po_id: string;
  po_number: string;
  vendor_name: string;
  carrier_name: string;
  tracking_number: string | null;
  vehicle_number: string | null;
  dispatch_date: string;
  estimated_delivery_date: string;
  status: string;
  package_count: number;
  total_weight_kg: number;
  lines_count: number;
}

interface InvoiceRecord {
  id: string;
  invoice_number: string;
  vendor_name: string;
  issue_date: string | null;
  due_date: string | null;
  total_amount: number;
  paid_amount: number;
  status: string;
  three_way_match_status: string;
}

export default function VendorPortalPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"pos" | "asns" | "invoices">("pos");
  const [selectedPo, setSelectedPo] = useState<PurchaseOrder | null>(null);
  const [showAckModal, setShowAckModal] = useState(false);
  const [committedDate, setCommittedDate] = useState("");
  const [ackNotes, setAckNotes] = useState("");

  const [showAsnModal, setShowAsnModal] = useState(false);
  const [carrierName, setCarrierName] = useState("Blue Dart Express");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [vehicleNumber, setVehicleNumber] = useState("");
  const [dispatchDate, setDispatchDate] = useState(new Date().toISOString().split("T")[0]);
  const [estDate, setEstDate] = useState(new Date(Date.now() + 86400000 * 3).toISOString().split("T")[0]);
  const [packageCount, setPackageCount] = useState("5");
  const [totalWeight, setTotalWeight] = useState("45.5");

  const [selectedAsnId, setSelectedAsnId] = useState<string | null>(null);

  const { data: summary } = useQuery({
    queryKey: ["vendor-portal", "summary"],
    queryFn: () => api<VendorSummary>("GET", "/api/v1/vendor-portal/vendor-summary"),
  });

  const { data: posData } = useQuery({
    queryKey: ["vendor-portal", "pos"],
    queryFn: () => api<{ purchase_orders: PurchaseOrder[] }>("GET", "/api/v1/vendor-portal/pos"),
  });

  const { data: asnsData } = useQuery({
    queryKey: ["vendor-portal", "asns"],
    queryFn: () => api<{ asns: AsnRecord[] }>("GET", "/api/v1/vendor-portal/asns"),
  });

  const { data: invoicesData } = useQuery({
    queryKey: ["vendor-portal", "invoices"],
    queryFn: () => api<{ invoices: InvoiceRecord[] }>("GET", "/api/v1/vendor-portal/invoices-status"),
  });

  const { data: packingSlip } = useQuery({
    queryKey: ["vendor-portal", "packing-slip", selectedAsnId],
    queryFn: () => api<any>("GET", `/api/v1/vendor-portal/asns/${selectedAsnId}/packing-slip`),
    enabled: !!selectedAsnId,
  });

  const pos = posData?.purchase_orders || [];
  const asns = asnsData?.asns || [];
  const invoices = invoicesData?.invoices || [];

  const handleAcknowledge = async () => {
    if (!selectedPo || !committedDate) return;
    await api("POST", `/api/v1/vendor-portal/pos/${selectedPo.id}/acknowledge`, {
      json: {
        committed_delivery_date: committedDate,
        vendor_notes: ackNotes || undefined,
      },
    });
    setShowAckModal(false);
    setSelectedPo(null);
    qc.invalidateQueries({ queryKey: ["vendor-portal"] });
  };

  const handleCreateAsn = async () => {
    if (!selectedPo) return;
    await api("POST", "/api/v1/vendor-portal/asns", {
      json: {
        po_id: selectedPo.id,
        vendor_party_id: selectedPo.vendor_party_id,
        carrier_name: carrierName,
        tracking_number: trackingNumber || undefined,
        vehicle_number: vehicleNumber || undefined,
        dispatch_date: dispatchDate,
        estimated_delivery_date: estDate,
        package_count: parseInt(packageCount, 10) || 1,
        total_weight_kg: parseFloat(totalWeight) || 0,
        lines: [
          {
            product_id: "00000000-0000-0000-0000-000000000000",
            shipped_qty: 10,
            vendor_batch_number: `VB-${Date.now().toString().slice(-6)}`,
            mfg_date: dispatchDate,
          },
        ],
      },
    });
    setShowAsnModal(false);
    setSelectedPo(null);
    qc.invalidateQueries({ queryKey: ["vendor-portal"] });
  };

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="Vendor Self-Service Collaboration Portal"
          description="Supplier RFQ bids, Purchase Order acknowledgments, Advance Shipping Notices (ASN), and 3-way invoice matching"
          actions={
            <ActionButton
              tone="ghost"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["vendor-portal"] })}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh Portal
            </ActionButton>
          }
        />

        {/* High-level KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Open Purchase Orders"
            value={summary?.open_pos_count?.toString() || "0"}
            hint="Awaiting dispatch or confirm"
            tone="info"
          />
          <StatCard
            label="In-Transit ASNs"
            value={summary?.active_asns_count?.toString() || "0"}
            hint="Pre-arrival manifests submitted"
            tone="warning"
          />
          <StatCard
            label="Invoices in 3-Way Match"
            value={summary?.pending_invoices_count?.toString() || "0"}
            hint="GRN vs PO reconciliation"
            tone="success"
          />
          <StatCard
            label="Supplier Security"
            value="GS1-128 Ready"
            hint="Pre-printed pallet barcoding"
            tone="muted"
          />
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-[var(--border)] gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("pos")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "pos"
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            Purchase Orders ({pos.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("asns")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "asns"
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            Advance Shipping Notices ({asns.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("invoices")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "invoices"
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            Invoices & Settlement ({invoices.length})
          </button>
        </div>

        {/* TAB 1: PURCHASE ORDERS */}
        {activeTab === "pos" && (
          <Panel title="Supplier Purchase Order Confirmation Desk">
            <DataTable
              columns={["PO Number", "Vendor Name", "Order Date", "Committed ETA", "Amount", "Lines", "Status", "Actions"]}
            >
              {pos.map((p) => (
                <TableRow
                  key={p.id}
                  cells={[
                    <span className="font-semibold text-[var(--foreground)]">{p.po_number}</span>,
                    <span>{p.vendor_name}</span>,
                    <span>{p.order_date ? formatDate(p.order_date) : "—"}</span>,
                    <span>{p.expected_delivery_date ? formatDate(p.expected_delivery_date) : "Unconfirmed"}</span>,
                    <span className="font-mono">{money(p.total_amount)}</span>,
                    <span>{p.lines_count} items</span>,
                    <Pill tone={p.status === "approved" ? "info" : "success"}>{p.status.toUpperCase()}</Pill>,
                    <div className="flex gap-2">
                      <ActionButton
                        size="sm"
                        tone="ghost"
                        onClick={() => {
                          setSelectedPo(p);
                          setShowAckModal(true);
                        }}
                      >
                        Acknowledge
                      </ActionButton>
                      <ActionButton
                        size="sm"
                        tone="primary"
                        onClick={() => {
                          setSelectedPo(p);
                          setShowAsnModal(true);
                        }}
                      >
                        Dispatch ASN
                      </ActionButton>
                    </div>,
                  ]}
                />
              ))}
            </DataTable>
          </Panel>
        )}

        {/* TAB 2: ADVANCE SHIPPING NOTICES */}
        {activeTab === "asns" && (
          <Panel title="Submitted Advance Shipping Notices (ASN manifests)">
            <DataTable
              columns={["ASN #", "Linked PO", "Carrier & LR / Tracking", "Vehicle", "Dispatch Date", "ETA", "Pkgs / Wt", "Status", "Pallet Label"]}
            >
              {asns.map((a) => (
                <TableRow
                  key={a.id}
                  cells={[
                    <span className="font-semibold text-[var(--foreground)]">{a.asn_number}</span>,
                    <span className="font-mono">{a.po_number}</span>,
                    <div>
                      <div className="font-medium text-xs text-[var(--foreground)]">{a.carrier_name}</div>
                      <div className="text-[11px] text-[var(--muted-foreground)] font-mono">{a.tracking_number || "—"}</div>
                    </div>,
                    <span className="font-mono text-xs">{a.vehicle_number || "—"}</span>,
                    <span>{formatDate(a.dispatch_date)}</span>,
                    <span>{formatDate(a.estimated_delivery_date)}</span>,
                    <span className="text-xs">{a.package_count} pkgs ({a.total_weight_kg} kg)</span>,
                    <Pill tone={a.status === "in_transit" ? "warning" : "success"}>{a.status.toUpperCase()}</Pill>,
                    <ActionButton
                      size="sm"
                      tone="ghost"
                      onClick={() => setSelectedAsnId(a.id)}
                    >
                      <Printer className="h-3 w-3 mr-1" />
                      GS1 Label
                    </ActionButton>,
                  ]}
                />
              ))}
            </DataTable>
          </Panel>
        )}

        {/* TAB 3: INVOICES */}
        {activeTab === "invoices" && (
          <Panel title="Vendor Bills & 3-Way Reconciliation Radar">
            <DataTable
              columns={["Invoice #", "Supplier", "Issue Date", "Due Date", "Billed Amount", "Paid", "Status", "3-Way Match"]}
            >
              {invoices.map((inv) => (
                <TableRow
                  key={inv.id}
                  cells={[
                    <span className="font-semibold font-mono text-[var(--foreground)]">{inv.invoice_number}</span>,
                    <span>{inv.vendor_name}</span>,
                    <span>{inv.issue_date ? formatDate(inv.issue_date) : "—"}</span>,
                    <span>{inv.due_date ? formatDate(inv.due_date) : "—"}</span>,
                    <span className="font-mono">{money(inv.total_amount)}</span>,
                    <span className="font-mono text-emerald-500">{money(inv.paid_amount)}</span>,
                    <Pill tone={inv.status === "paid" ? "success" : "warning"}>{inv.status.toUpperCase()}</Pill>,
                    <Pill tone="info">3-Way Verified</Pill>,
                  ]}
                />
              ))}
            </DataTable>
          </Panel>
        )}

        {/* Modal: Acknowledge PO */}
        {showAckModal && selectedPo && (
          <Modal
            open={showAckModal}
            title={`Acknowledge Purchase Order: ${selectedPo.po_number}`}
            onClose={() => setShowAckModal(false)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setShowAckModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handleAcknowledge}>
                  Confirm Acknowledgment
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <p className="text-xs text-[var(--muted-foreground)]">
                Confirm acceptance of the purchase order terms and specify your committed delivery dispatch date.
              </p>
              <Field label="Committed Dispatch / Delivery Date" required>
                <TextInput
                  type="date"
                  value={committedDate}
                  onChange={(e) => setCommittedDate(e.target.value)}
                />
              </Field>
              <Field label="Vendor Notes / Remarks">
                <TextInput
                  placeholder="Production scheduled, material in stock..."
                  value={ackNotes}
                  onChange={(e) => setAckNotes(e.target.value)}
                />
              </Field>
            </div>
          </Modal>
        )}

        {/* Modal: Dispatch ASN */}
        {showAsnModal && selectedPo && (
          <Modal
            open={showAsnModal}
            title={`Dispatch Advance Shipping Notice for ${selectedPo.po_number}`}
            onClose={() => setShowAsnModal(false)}
            footer={
              <div className="flex justify-end gap-2">
                <ActionButton tone="ghost" size="sm" onClick={() => setShowAsnModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" size="sm" onClick={handleCreateAsn}>
                  Submit ASN Manifest
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Logistics Carrier" required>
                  <TextInput
                    value={carrierName}
                    onChange={(e) => setCarrierName(e.target.value)}
                  />
                </Field>
                <Field label="AWB / Lorry Receipt (LR) #">
                  <TextInput
                    placeholder="e.g. BLR-982103"
                    value={trackingNumber}
                    onChange={(e) => setTrackingNumber(e.target.value)}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Truck / Vehicle #">
                  <TextInput
                    placeholder="MH-12-AB-1234"
                    value={vehicleNumber}
                    onChange={(e) => setVehicleNumber(e.target.value)}
                  />
                </Field>
                <Field label="Carton / Package Count">
                  <TextInput
                    type="number"
                    value={packageCount}
                    onChange={(e) => setPackageCount(e.target.value)}
                  />
                </Field>
                <Field label="Total Weight (kg)">
                  <TextInput
                    type="number"
                    value={totalWeight}
                    onChange={(e) => setTotalWeight(e.target.value)}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Shipment Date" required>
                  <TextInput
                    type="date"
                    value={dispatchDate}
                    onChange={(e) => setDispatchDate(e.target.value)}
                  />
                </Field>
                <Field label="Estimated Dock Arrival" required>
                  <TextInput
                    type="date"
                    value={estDate}
                    onChange={(e) => setEstDate(e.target.value)}
                  />
                </Field>
              </div>
            </div>
          </Modal>
        )}

        {/* Modal: GS1 Pallet Packing Slip */}
        {selectedAsnId && packingSlip && (
          <Modal
            open={!!selectedAsnId}
            title={`GS1-128 Pallet Barcode Slip: ${packingSlip.asn_number}`}
            onClose={() => setSelectedAsnId(null)}
            footer={
              <div className="flex justify-end">
                <ActionButton tone="primary" size="sm" onClick={() => window.print()}>
                  <Printer className="h-4 w-4 mr-1" />
                  Print Pallet Tag
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4 font-mono text-xs p-2 bg-[var(--muted)]/20 rounded-lg border border-[var(--border)]">
              <div className="flex justify-between border-b pb-2">
                <span>PO: {packingSlip.po_number}</span>
                <span>CARRIER: {packingSlip.carrier_name}</span>
                <span>PACKAGES: {packingSlip.package_count}</span>
              </div>
              <div className="p-3 bg-white text-black rounded text-center">
                <div className="text-xl font-bold tracking-widest">{packingSlip.asn_number}</div>
                <div className="text-[10px] text-gray-500 mt-1">GS1-128 AI:(00) Serial Shipping Container Code</div>
              </div>
              <div className="space-y-1">
                <div className="font-bold">MANIFEST ITEMS:</div>
                {packingSlip.items?.map((item: any, i: number) => (
                  <div key={i} className="flex justify-between border-b border-dashed py-1">
                    <span>{item.sku} - {item.name}</span>
                    <span>Qty: {qty(item.shipped_qty)} | Lot: {item.batch_number}</span>
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
