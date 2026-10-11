import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
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
import { date as formatDate, money } from "@/lib/format";

interface EwayBillRecord {
  id: string;
  eway_bill_number: string;
  document_type: string;
  doc_number: string;
  doc_date: string;
  supply_type: string;
  sub_supply_type: string;
  from_gstin: string;
  from_pincode: string;
  to_gstin: string | null;
  to_pincode: string;
  total_invoice_value: number;
  cgst_value: number;
  sgst_value: number;
  igst_value: number;
  hsn_code: string;
  transporter_name: string | null;
  vehicle_number: string | null;
  status: string;
  valid_until: string | null;
  created_at: string;
}

interface PrintSlipData {
  form_title: string;
  eway_bill_number: string;
  eway_bill_date: string;
  valid_until: string;
  doc_number: string;
  doc_date: string;
  part_a: {
    from_gstin: string;
    to_gstin: string;
    dispatch_from_pincode: string;
    ship_to_pincode: string;
    total_invoice_value: number;
    hsn_code: string;
    reason_for_transportation: string;
  };
  part_b: {
    mode: string;
    vehicle_number: string;
    transporter_name: string;
    transporter_id: string;
  };
  qr_code_data: string;
}

export default function StatutoryLogisticsPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showVehicleModal, setShowVehicleModal] = useState(false);
  const [showPrintModal, setShowPrintModal] = useState(false);
  const [selectedEwbId, setSelectedEwbId] = useState<string | null>(null);

  // Generate form state
  const [distanceKm, setDistanceKm] = useState("350");
  const [subSupplyType, setSubSupplyType] = useState("Supply");
  const [transporterName, setTransporterName] = useState("VRL Logistics Ltd");
  const [transporterGstin, setTransporterGstin] = useState("27AAACT2727Q1ZT");
  const [transportMode, setTransportMode] = useState("1");
  const [vehicleNo, setVehicleNo] = useState("MH-12-RN-8877");
  const [vehicleType, setVehicleType] = useState("R");

  // Vehicle update state
  const [newVehicleNo, setNewVehicleNo] = useState("");
  const [breakdownReason, setBreakdownReason] = useState("1");
  const [breakdownRemark, setBreakdownRemark] = useState("Truck breakdown; cargo shifted to relief truck");

  // Fetch e-Way bills
  const billsQuery = useQuery({
    queryKey: ["eway-bills"],
    queryFn: () => api<{ eway_bills: EwayBillRecord[] }>("GET", "/api/v1/statutory/eway-bills"),
  });

  // Fetch print slip if modal open
  const printSlipQuery = useQuery({
    queryKey: ["eway-bill-print-slip", selectedEwbId],
    queryFn: () => api<PrintSlipData>("GET", `/api/v1/statutory/eway-bills/${selectedEwbId}/print-slip`),
    enabled: !!selectedEwbId && showPrintModal,
  });

  const bills = billsQuery.data?.eway_bills || [];
  const slip = printSlipQuery.data;

  // Handler: Generate e-Way bill
  const handleGenerateEwayBill = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api("POST", "/api/v1/statutory/eway-bills/generate", {
        json: {
          approximate_distance_km: parseInt(distanceKm) || 250,
          sub_supply_type: subSupplyType,
          transporter_name: transporterName,
          transporter_id: transporterGstin,
          transport_mode: transportMode,
          vehicle_number: vehicleNo,
          vehicle_type: vehicleType,
        },
      });
      setShowGenerateModal(false);
      qc.invalidateQueries({ queryKey: ["eway-bills"] });
      alert("Statutory Form GST EWB-01 generated successfully");
    } catch (err) {
      alert("Failed to generate e-Way bill: " + err);
    }
  };

  // Handler: Update Part B vehicle
  const handleUpdateVehicle = async () => {
    if (!selectedEwbId || !newVehicleNo) return;
    try {
      await api("PATCH", `/api/v1/statutory/eway-bills/${selectedEwbId}/update-vehicle`, {
        json: {
          vehicle_number: newVehicleNo,
          reason_code: breakdownReason,
          reason_remark: breakdownRemark,
        },
      });
      setShowVehicleModal(false);
      qc.invalidateQueries({ queryKey: ["eway-bills"] });
      alert("Part-B Vehicle details updated in statutory transit record");
    } catch (err) {
      alert("Failed to update vehicle: " + err);
    }
  };

  return (
    <Shell>
      <PageHeader
        title="Statutory Logistics & e-Way Bills"
        description="Form GST EWB-01 compliance, NIC electronic payload generation, Part-B transit vehicle management, and statutory printable manifests."
        actions={
          <div className="flex gap-2">
            <ActionButton tone="primary" onClick={() => setShowGenerateModal(true)}>
              <Plus className="w-4 h-4 mr-1.5" />
              Generate e-Way Bill
            </ActionButton>
            <ActionButton tone="ghost" onClick={() => qc.invalidateQueries({ queryKey: ["eway-bills"] })}>
              <RefreshCw className="w-4 h-4 mr-1.5" />
              Refresh
            </ActionButton>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Active e-Way Bills"
          value={bills.filter((b) => b.status === "active").length}
          hint="Valid for transit"
        />
        <StatCard
          label="Total Cargo Consigned"
          value={money(bills.reduce((acc, b) => acc + b.total_invoice_value, 0))}
          hint="Covered under permits"
        />
        <StatCard
          label="Total Tax Cleared"
          value={money(bills.reduce((acc, b) => acc + b.cgst_value + b.sgst_value + b.igst_value, 0))}
          hint="GST compliance total"
        />
        <StatCard
          label="Interstate Movement"
          value={bills.filter((b) => b.from_pincode.slice(0, 2) !== b.to_pincode.slice(0, 2)).length}
          hint="Cross-border manifests"
        />
      </div>

      <Panel title="e-Way Bills Registry (Form GST EWB-01)">
        <DataTable
          columns={[
            "e-Way Bill No.",
            "Doc Reference",
            "Consignor → Consignee",
            "Consignment Value",
            "Vehicle & Transporter",
            "Validity Period",
            "Status",
            "Actions",
          ]}
        >
          {bills.map((b) => (
            <TableRow
              key={b.id}
              cells={[
                <div>
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {b.eway_bill_number}
                  </span>
                  <div className="text-[10px] text-slate-500 font-medium">{b.sub_supply_type}</div>
                </div>,
                <div className="text-xs">
                  <div className="font-medium text-slate-800 dark:text-slate-200">{b.doc_number}</div>
                  <div className="text-[10px] text-slate-400">{formatDate(b.doc_date)}</div>
                </div>,
                <div className="text-xs">
                  <div className="font-mono text-[11px] text-slate-700 dark:text-slate-300">
                    {b.from_gstin.slice(0, 10)}... ({b.from_pincode})
                  </div>
                  <div className="text-[10px] text-slate-400">
                    → {b.to_gstin ? `${b.to_gstin.slice(0, 10)}...` : "URP"} ({b.to_pincode})
                  </div>
                </div>,
                <div className="text-right text-xs">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">{money(b.total_invoice_value)}</div>
                  <div className="text-[10px] text-slate-400">
                    GST: {money(b.cgst_value + b.sgst_value + b.igst_value)}
                  </div>
                </div>,
                <div className="text-xs">
                  <div className="font-mono font-semibold text-slate-800 dark:text-slate-200">{b.vehicle_number || "Awaiting Part-B"}</div>
                  <div className="text-[10px] text-slate-500 truncate max-w-[140px]">{b.transporter_name}</div>
                </div>,
                <div className="text-xs">
                  {b.valid_until ? (
                    <span className="text-slate-700 dark:text-slate-300">{formatDate(b.valid_until)}</span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </div>,
                <Pill tone={b.status === "active" ? "success" : "muted"}>
                  {b.status.toUpperCase()}
                </Pill>,
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedEwbId(b.id);
                      setNewVehicleNo(b.vehicle_number || "");
                      setShowVehicleModal(true);
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Change Vehicle
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedEwbId(b.id);
                      setShowPrintModal(true);
                    }}
                    className="text-xs text-slate-600 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1"
                  >
                    <Printer className="w-3.5 h-3.5" /> Print
                  </button>
                </div>,
              ]}
            />
          ))}
          {bills.length === 0 && (
            <TableRow
              cells={[
                <div key="empty" className="text-center py-8 text-sm text-slate-400">
                  No statutory e-Way Bills generated yet. Click "Generate e-Way Bill" to create one.
                </div>,
              ]}
            />
          )}
        </DataTable>
      </Panel>

      {/* Modal: Generate e-Way Bill */}
      <Modal
        open={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        title="Generate Form GST EWB-01 (e-Way Bill)"
      >
        <form onSubmit={handleGenerateEwayBill} className="space-y-4">
          <Field label="Transaction Category">
            <select
              value={subSupplyType}
              onChange={(e) => setSubSupplyType(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
            >
              <option value="Supply">Regular Tax Invoice Supply</option>
              <option value="JobWork">Subcontracting Job-Work (Rule 55 Challan)</option>
              <option value="Transfer">Inter-Warehouse Branch Transfer</option>
              <option value="Export">Export Consignment</option>
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Approximate Distance (km)">
              <TextInput
                type="number"
                value={distanceKm}
                onChange={(e) => setDistanceKm(e.target.value)}
                placeholder="e.g. 350"
                required
              />
            </Field>
            <Field label="Transport Mode">
              <select
                value={transportMode}
                onChange={(e) => setTransportMode(e.target.value)}
                className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              >
                <option value="1">1 - Road Cargo</option>
                <option value="2">2 - Rail Cargo</option>
                <option value="3">3 - Air Freight</option>
                <option value="4">4 - Sea Vessel</option>
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Transporter Name">
              <TextInput
                value={transporterName}
                onChange={(e) => setTransporterName(e.target.value)}
                placeholder="e.g. VRL Logistics Ltd"
                required
              />
            </Field>
            <Field label="Transporter GSTIN / ID">
              <TextInput
                value={transporterGstin}
                onChange={(e) => setTransporterGstin(e.target.value)}
                placeholder="e.g. 27AAACT2727Q1ZT"
                required
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Vehicle Number (Part B)">
              <TextInput
                value={vehicleNo}
                onChange={(e) => setVehicleNo(e.target.value)}
                placeholder="e.g. MH-12-RN-8877"
                required
              />
            </Field>
            <Field label="Vehicle Type">
              <select
                value={vehicleType}
                onChange={(e) => setVehicleType(e.target.value)}
                className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              >
                <option value="R">Regular Commercial Truck</option>
                <option value="O">Over Dimensional Cargo (ODC)</option>
              </select>
            </Field>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowGenerateModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Generate e-Way Bill
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Modal: Update Part-B Vehicle */}
      <Modal
        open={showVehicleModal}
        onClose={() => setShowVehicleModal(false)}
        title="Update Part-B Vehicle in Transit"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Mandatory under CGST Rule 138(5): Update vehicle registration number when cargo is transshipped or relieved following breakdown.
          </p>
          <Field label="New Relief Vehicle Registration No.">
            <TextInput
              value={newVehicleNo}
              onChange={(e) => setNewVehicleNo(e.target.value)}
              placeholder="e.g. MH-14-GH-9988"
              required
            />
          </Field>
          <Field label="Reason for Vehicle Change">
            <select
              value={breakdownReason}
              onChange={(e) => setBreakdownReason(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
            >
              <option value="1">1 - Breakdown / Axle Failure</option>
              <option value="2">2 - Hub Transshipment</option>
              <option value="3">3 - Traffic Police / Legal Directive</option>
            </select>
          </Field>
          <Field label="Reason Remark">
            <TextInput
              value={breakdownRemark}
              onChange={(e) => setBreakdownRemark(e.target.value)}
              placeholder="Provide remark for audit inspection"
            />
          </Field>
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setShowVehicleModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" onClick={handleUpdateVehicle}>
              Update Transit Vehicle
            </ActionButton>
          </div>
        </div>
      </Modal>

      {/* Modal: Form GST EWB-01 Print Slip */}
      <Modal
        open={showPrintModal}
        onClose={() => setShowPrintModal(false)}
        title="Form GST EWB-01 (Statutory e-Way Bill)"
      >
        {slip ? (
          <div className="space-y-4 border p-4 rounded-lg bg-white dark:bg-slate-950 font-sans text-xs">
            <div className="text-center pb-3 border-b border-dashed">
              <h2 className="font-bold text-sm tracking-wide">GOVERNMENT OF INDIA</h2>
              <div className="font-semibold text-primary">{slip.form_title}</div>
              <div className="font-mono text-sm font-bold mt-1 text-slate-900 dark:text-slate-100">
                e-Way Bill No: {slip.eway_bill_number}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] pb-3 border-b">
              <div>
                <span className="text-slate-400">Generation Date:</span> {formatDate(slip.eway_bill_date)}
              </div>
              <div className="text-right">
                <span className="text-slate-400">Valid Until:</span>{" "}
                <strong className="text-emerald-600">{formatDate(slip.valid_until)}</strong>
              </div>
            </div>

            {/* Part A */}
            <div className="space-y-1.5">
              <div className="font-bold text-xs uppercase text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded">
                PART - A (Consignment Details)
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] px-2">
                <div>
                  <span className="text-slate-400">GSTIN of Supplier:</span> {slip.part_a.from_gstin}
                </div>
                <div>
                  <span className="text-slate-400">GSTIN of Recipient:</span> {slip.part_a.to_gstin}
                </div>
                <div>
                  <span className="text-slate-400">Dispatch PIN:</span> {slip.part_a.dispatch_from_pincode}
                </div>
                <div>
                  <span className="text-slate-400">Delivery PIN:</span> {slip.part_a.ship_to_pincode}
                </div>
                <div>
                  <span className="text-slate-400">Doc No. & Date:</span> {slip.doc_number} ({formatDate(slip.doc_date)})
                </div>
                <div>
                  <span className="text-slate-400">Value of Goods:</span> <strong>{money(slip.part_a.total_invoice_value)}</strong>
                </div>
                <div>
                  <span className="text-slate-400">HSN Code:</span> {slip.part_a.hsn_code}
                </div>
                <div>
                  <span className="text-slate-400">Reason:</span> {slip.part_a.reason_for_transportation}
                </div>
              </div>
            </div>

            {/* Part B */}
            <div className="space-y-1.5 pt-2">
              <div className="font-bold text-xs uppercase text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded">
                PART - B (Vehicle & Transporter Details)
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] px-2">
                <div>
                  <span className="text-slate-400">Mode:</span> {slip.part_b.mode}
                </div>
                <div>
                  <span className="text-slate-400">Vehicle No:</span>{" "}
                  <strong className="font-mono text-primary">{slip.part_b.vehicle_number}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Transporter:</span> {slip.part_b.transporter_name}
                </div>
                <div>
                  <span className="text-slate-400">Transporter ID:</span> {slip.part_b.transporter_id}
                </div>
              </div>
            </div>

            {/* QR Verification Barcode */}
            <div className="pt-3 border-t text-center">
              <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded inline-block font-mono text-[9px] text-slate-500 break-all max-w-[400px]">
                {slip.qr_code_data}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Scan with official NIC e-Way Bill mobile app for instant highway officer verification
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <ActionButton tone="ghost" onClick={() => setShowPrintModal(false)}>
                Close
              </ActionButton>
              <ActionButton tone="primary" onClick={() => window.print()}>
                <Printer className="w-4 h-4 mr-1.5" />
                Print EWB-01
              </ActionButton>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center text-slate-400">Loading statutory slip...</div>
        )}
      </Modal>
    </Shell>
  );
}
