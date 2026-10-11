import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  Plus,
  Printer,
  RefreshCw,
  Wrench,
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

interface IpqcRecord {
  id: string;
  inspection_number: string;
  production_run_id: string;
  production_run_number: string;
  product_id: string;
  sku: string;
  product_name: string;
  stage_name: string;
  sample_size: number;
  inspected_qty: number;
  passed_qty: number;
  failed_qty: number;
  status: string;
  parameters_checked: Array<{ parameter: string; specification: string; measured_value: string; decision: string }>;
  non_conformance_reason: string | null;
  corrective_action_required: boolean;
  inspected_at: string;
}

interface RunPendingInspection {
  id: string;
  run_number: string;
  product_id: string;
  sku: string;
  product_name: string;
  target_quantity: number;
  status: string;
  default_stage: string;
}

interface CoaRecord {
  id: string;
  coa_number: string;
  product_id: string;
  sku: string;
  product_name: string;
  batch_no: string;
  mfg_date: string;
  expiry_date: string | null;
  lot_size_qty: number;
  uom: string;
  test_standards: string;
  parameters_count: number;
  is_published: boolean;
  created_at: string;
}

interface CoaPrintSlip {
  coa_number: string;
  product_name: string;
  sku: string;
  batch_no: string;
  mfg_date: string;
  expiry_date: string;
  lot_size: string;
  standards: string;
  specifications: Array<{ test_name: string; method: string; specification: string; result: string; decision: string }>;
  qa_signoff: string;
  certified_date: string;
}

export default function QualityIpqcPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"ipqc" | "coa">("ipqc");
  const [showIpqcModal, setShowIpqcModal] = useState(false);
  const [showCoaModal, setShowCoaModal] = useState(false);
  const [printCoaId, setPrintCoaId] = useState<string | null>(null);

  // Form states: IPQC
  const [selectedRunId, setSelectedRunId] = useState("");
  const [stageName, setStageName] = useState("Stage 2: High-Voltage Torque & Wiring");
  const [sampleSize, setSampleSize] = useState("5");
  const [passedQty, setPassedQty] = useState("5");
  const [failedQty, setFailedQty] = useState("0");
  const [paramMeasured, setParamMeasured] = useState("12.4");
  const [ipqcStatus, setIpqcStatus] = useState("passed");
  const [nonConformance, setNonConformance] = useState("");

  // Form states: CoA
  const [selectedProductId, setSelectedProductId] = useState("");
  const [batchNo, setBatchNo] = useState("LOT-2026-B01");
  const [mfgDate, setMfgDate] = useState(new Date().toISOString().split("T")[0]);
  const [expiryDate, setExpiryDate] = useState(new Date(Date.now() + 86400000 * 365).toISOString().split("T")[0]);
  const [lotSizeQty, setLotSizeQty] = useState("500");
  const [testStandards, setTestStandards] = useState("ISO 9001:2015 / ASTM D638 / IEC 62133");
  const [coaResult, setCoaResult] = useState("48.2 MPa (Target >= 45.0)");

  // 1. Fetch IPQC Inspections
  const ipqcQuery = useQuery({
    queryKey: ["ipqc-inspections"],
    queryFn: () => api<{ inspections: IpqcRecord[] }>("GET", "/api/v1/quality/ipqc"),
  });
  const inspections = ipqcQuery.data?.inspections ?? [];

  // 2. Fetch Runs Pending Inspection
  const runsQuery = useQuery({
    queryKey: ["runs-pending-inspection"],
    queryFn: () => api<{ runs: RunPendingInspection[] }>("GET", "/api/v1/quality/runs-pending"),
  });
  const pendingRuns = runsQuery.data?.runs ?? [];

  // 3. Fetch CoAs
  const coaQuery = useQuery({
    queryKey: ["quality-coas"],
    queryFn: () => api<{ coas: CoaRecord[] }>("GET", "/api/v1/quality/coa"),
  });
  const coas = coaQuery.data?.coas ?? [];

  // 4. Fetch Products
  const productsQuery = useQuery({
    queryKey: ["products"],
    queryFn: () => api<{ data: Array<{ id: string; sku: string; name: string }> }>("GET", "/api/v1/products"),
  });
  const products = productsQuery.data?.data ?? [];

  // 5. Fetch Print Slip
  const printQuery = useQuery({
    queryKey: ["coa-print-slip", printCoaId],
    queryFn: () => api<CoaPrintSlip>("GET", `/api/v1/quality/coa/${printCoaId}/print`),
    enabled: !!printCoaId,
  });
  const printSlip = printQuery.data;

  // Handler: Record IPQC
  const handleRecordIpqc = async (e: React.FormEvent) => {
    e.preventDefault();
    const runId = selectedRunId || (pendingRuns[0]?.id ?? "");
    if (!runId) {
      alert("Please select a production run.");
      return;
    }

    try {
      const res = await api<{ inspection_number: string }>("POST", "/api/v1/quality/ipqc", {
        json: {
          production_run_id: runId,
          stage_name: stageName,
          sample_size: parseInt(sampleSize || "5", 10),
          inspected_qty: parseFloat(passedQty) + parseFloat(failedQty),
          passed_qty: parseFloat(passedQty || "0"),
          failed_qty: parseFloat(failedQty || "0"),
          status: ipqcStatus,
          parameters: [
            {
              parameter: "Critical Mechanical Torque",
              specification: "12.5 Nm +/- 0.5",
              measured_value: `${paramMeasured} Nm`,
              decision: ipqcStatus === "passed" ? "PASS" : "FAIL",
              uom: "Nm",
            },
            {
              parameter: "High Voltage Insulation Resistance",
              specification: ">= 500 MOhm",
              measured_value: "720 MOhm",
              decision: "PASS",
              uom: "MOhm",
            },
          ],
          non_conformance_reason: nonConformance || null,
          corrective_action_required: ipqcStatus === "failed",
        },
      });
      setShowIpqcModal(false);
      qc.invalidateQueries({ queryKey: ["ipqc-inspections"] });
      alert(`IPQC Inspection ${res.inspection_number} saved.`);
    } catch (err) {
      alert("Failed to record IPQC: " + err);
    }
  };

  // Handler: Generate CoA
  const handleGenerateCoa = async (e: React.FormEvent) => {
    e.preventDefault();
    const prodId = selectedProductId || (products[0]?.id ?? "");
    if (!prodId) {
      alert("Please select a product.");
      return;
    }

    try {
      const res = await api<{ coa_number: string }>("POST", "/api/v1/quality/coa", {
        json: {
          product_id: prodId,
          batch_no: batchNo,
          mfg_date: mfgDate,
          expiry_date: expiryDate,
          lot_size_qty: parseFloat(lotSizeQty || "100"),
          uom: "UNIT",
          test_standards: testStandards,
          specifications: [
            {
              test_name: "Tensile Strength at Break",
              method: "ASTM D638",
              specification: ">= 45.0 MPa",
              result: coaResult,
              decision: "PASS",
            },
            {
              test_name: "Thermal Dissipation Rating",
              method: "IEC 60068-2-14",
              specification: "Delta T <= 15 K",
              result: "Delta T = 11.4 K",
              decision: "PASS",
            },
            {
              test_name: "Dimensional Tolerance",
              method: "Vernier ISO 2768",
              specification: "+/- 0.05 mm",
              result: "+0.02 mm",
              decision: "PASS",
            },
          ],
        },
      });
      setShowCoaModal(false);
      qc.invalidateQueries({ queryKey: ["quality-coas"] });
      alert(`Certificate of Analysis ${res.coa_number} published.`);
    } catch (err) {
      alert("Failed to generate CoA: " + err);
    }
  };

  const totalPassed = inspections.filter((i) => i.status === "passed").length;
  const fpyRate = inspections.length > 0 ? Math.round((totalPassed / inspections.length) * 100) : 100;

  return (
    <Shell>
      <PageHeader
        title="In-Process Quality Control (IPQC) & Certificate of Analysis (CoA)"
        description="Mid-assembly station inspection gates, parameter tolerance checklists, and certified batch test reports for regulatory export compliance."
        actions={
          <div className="flex gap-2">
            <ActionButton
              tone="primary"
              onClick={() => {
                if (pendingRuns.length > 0 && !selectedRunId) setSelectedRunId(pendingRuns[0].id);
                setShowIpqcModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Record IPQC Check
            </ActionButton>
            <ActionButton
              tone="ghost"
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["ipqc-inspections"] });
                qc.invalidateQueries({ queryKey: ["quality-coas"] });
                qc.invalidateQueries({ queryKey: ["runs-pending-inspection"] });
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
          label="Stage Inspections Logged"
          value={inspections.length}
          hint="Production checkpoints"
        />
        <StatCard
          label="First-Pass Yield (FPY)"
          value={`${fpyRate}%`}
          hint="Zero rework milestone"
        />
        <StatCard
          label="Runs Awaiting Gate Pass"
          value={pendingRuns.length}
          hint="In-progress work orders"
        />
        <StatCard
          label="Published CoA Certificates"
          value={coas.length}
          hint="Authorized lot releases"
        />
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 mb-6 gap-6 text-sm font-medium">
        <button
          type="button"
          onClick={() => setActiveTab("ipqc")}
          className={`pb-3 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "ipqc"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Wrench className="w-4 h-4" />
          <span>In-Process QC (IPQC) Queue ({inspections.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("coa")}
          className={`pb-3 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "coa"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Award className="w-4 h-4" />
          <span>Certificate of Analysis (CoA) Registry ({coas.length})</span>
        </button>
      </div>

      {/* TAB 1: IPQC Inspections */}
      {activeTab === "ipqc" && (
        <Panel
          title="In-Process Stage Inspections"
          aside={
            <ActionButton
              tone="primary"
              size="sm"
              onClick={() => {
                if (pendingRuns.length > 0 && !selectedRunId) setSelectedRunId(pendingRuns[0].id);
                setShowIpqcModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Log Stage Test
            </ActionButton>
          }
        >
          <DataTable
            columns={[
              "Inspection #",
              "Production Run",
              "Assembly / SKU",
              "Inspection Station",
              "Sample Checked",
              "Pass / Fail",
              "Status",
            ]}
          >
            {inspections.map((i) => (
              <TableRow
                key={i.id}
                cells={[
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {i.inspection_number}
                  </span>,
                  <span className="font-mono text-xs">{i.production_run_number}</span>,
                  <div>
                    <div className="font-medium text-xs">{i.sku}</div>
                    <div className="text-[10px] text-slate-400">{i.product_name}</div>
                  </div>,
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {i.stage_name}
                  </span>,
                  <span className="text-xs font-mono">{i.sample_size} units</span>,
                  <div className="text-xs">
                    <span className="text-emerald-600 font-bold">{qty(i.passed_qty)} P</span>
                    {" / "}
                    <span className={i.failed_qty > 0 ? "text-rose-600 font-bold" : "text-slate-400"}>
                      {qty(i.failed_qty)} F
                    </span>
                  </div>,
                  <Pill tone={i.status === "passed" ? "success" : i.status === "failed" ? "destructive" : "warning"}>
                    {i.status.toUpperCase()}
                  </Pill>,
                ]}
              />
            ))}
            {inspections.length === 0 && (
              <TableRow
                cells={[
                  <div key="empty" className="text-center py-8 text-sm text-slate-400">
                    No in-process inspections logged yet. Click "Log Stage Test" to record mid-assembly parameters.
                  </div>,
                ]}
              />
            )}
          </DataTable>
        </Panel>
      )}

      {/* TAB 2: Certificate of Analysis */}
      {activeTab === "coa" && (
        <Panel
          title="Certificate of Analysis (CoA) Registry"
          aside={
            <ActionButton
              tone="primary"
              size="sm"
              onClick={() => {
                if (products.length > 0 && !selectedProductId) setSelectedProductId(products[0].id);
                setShowCoaModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Generate CoA
            </ActionButton>
          }
        >
          <DataTable
            columns={[
              "CoA #",
              "Finished Product",
              "Batch Lot #",
              "Mfg Date",
              "Expiry Date",
              "Lot Size",
              "Test Standard",
              "Action",
            ]}
          >
            {coas.map((c) => (
              <TableRow
                key={c.id}
                cells={[
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {c.coa_number}
                  </span>,
                  <div>
                    <div className="font-medium text-xs">{c.sku}</div>
                    <div className="text-[10px] text-slate-400">{c.product_name}</div>
                  </div>,
                  <span className="font-mono font-bold text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                    {c.batch_no}
                  </span>,
                  <span className="text-xs text-slate-500">{formatDate(c.mfg_date)}</span>,
                  <span className="text-xs text-slate-500">{c.expiry_date ? formatDate(c.expiry_date) : "—"}</span>,
                  <span className="text-xs font-semibold">
                    {qty(c.lot_size_qty)} {c.uom}
                  </span>,
                  <span className="text-xs text-slate-600 dark:text-slate-400">{c.test_standards}</span>,
                  <button
                    type="button"
                    onClick={() => setPrintCoaId(c.id)}
                    className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                  >
                    <Printer className="w-3.5 h-3.5" /> Print Certificate
                  </button>,
                ]}
              />
            ))}
            {coas.length === 0 && (
              <TableRow
                cells={[
                  <div key="empty" className="text-center py-8 text-sm text-slate-400">
                    No Certificates of Analysis generated yet. Click "Generate CoA" to certify a completed lot.
                  </div>,
                ]}
              />
            )}
          </DataTable>
        </Panel>
      )}

      {/* Modal: Record IPQC */}
      <Modal
        open={showIpqcModal}
        onClose={() => setShowIpqcModal(false)}
        title="Record In-Process Quality Inspection (IPQC)"
      >
        <form onSubmit={handleRecordIpqc} className="space-y-4">
          <Field label="Target Production Run">
            <select
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              required
            >
              {pendingRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.run_number} - {r.sku} ({r.product_name})
                </option>
              ))}
            </select>
          </Field>

          <Field label="Assembly Inspection Station">
            <TextInput
              value={stageName}
              onChange={(e) => setStageName(e.target.value)}
              placeholder="e.g. Stage 2: SMT Solder & Continuity"
              required
            />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Sample Size">
              <TextInput
                type="number"
                min="1"
                value={sampleSize}
                onChange={(e) => setSampleSize(e.target.value)}
                required
              />
            </Field>

            <Field label="Passed Qty">
              <TextInput
                type="number"
                min="0"
                value={passedQty}
                onChange={(e) => setPassedQty(e.target.value)}
                required
              />
            </Field>

            <Field label="Failed / Defect Qty">
              <TextInput
                type="number"
                min="0"
                value={failedQty}
                onChange={(e) => setFailedQty(e.target.value)}
                required
              />
            </Field>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg space-y-3 border">
            <div className="font-semibold text-xs text-slate-800 dark:text-slate-200">
              Parametric Calibration Check
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Torque Tolerance Reading (Nm)">
                <TextInput
                  value={paramMeasured}
                  onChange={(e) => setParamMeasured(e.target.value)}
                  placeholder="Spec: 12.5 Nm +/- 0.5"
                  required
                />
              </Field>
              <Field label="Station Clearance Decision">
                <select
                  value={ipqcStatus}
                  onChange={(e) => setIpqcStatus(e.target.value)}
                  className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 font-semibold"
                >
                  <option value="passed">PASS (Clear to next stage)</option>
                  <option value="failed">FAIL (Halt line & quarantine)</option>
                  <option value="conditionally_approved">CONDITIONAL (Approved with deviation note)</option>
                </select>
              </Field>
            </div>
          </div>

          {ipqcStatus === "failed" && (
            <Field label="Non-Conformance Root Cause & Rework Instructions">
              <TextInput
                value={nonConformance}
                onChange={(e) => setNonConformance(e.target.value)}
                placeholder="e.g. Insufficient solder paste on U4 pins; return to rework"
                required
              />
            </Field>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowIpqcModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Authorize IPQC Gate
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Modal: Generate CoA */}
      <Modal
        open={showCoaModal}
        onClose={() => setShowCoaModal(false)}
        title="Generate Certificate of Analysis (CoA)"
      >
        <form onSubmit={handleGenerateCoa} className="space-y-4">
          <Field label="Finished Good Product">
            <select
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              required
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} - {p.name}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Batch Lot Number">
              <TextInput
                value={batchNo}
                onChange={(e) => setBatchNo(e.target.value)}
                placeholder="e.g. LOT-2026-B01"
                required
              />
            </Field>
            <Field label="Lot Size Quantity">
              <TextInput
                type="number"
                value={lotSizeQty}
                onChange={(e) => setLotSizeQty(e.target.value)}
                required
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Manufacturing Date">
              <TextInput
                type="date"
                value={mfgDate}
                onChange={(e) => setMfgDate(e.target.value)}
                required
              />
            </Field>
            <Field label="Expiry Date">
              <TextInput
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
              />
            </Field>
          </div>

          <Field label="Governing Standard">
            <TextInput
              value={testStandards}
              onChange={(e) => setTestStandards(e.target.value)}
              placeholder="e.g. ISO 9001:2015 / ASTM D638 / IEC 62133"
              required
            />
          </Field>

          <Field label="Primary Analytical Test Result">
            <TextInput
              value={coaResult}
              onChange={(e) => setCoaResult(e.target.value)}
              placeholder="e.g. 48.2 MPa (Spec: >= 45.0 MPa)"
              required
            />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowCoaModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Publish Certificate
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Modal: Official CoA Print View */}
      <Modal
        open={!!printCoaId}
        onClose={() => setPrintCoaId(null)}
        title="Official Certificate of Analysis"
      >
        {printSlip ? (
          <div className="space-y-4 border p-5 rounded-lg bg-white dark:bg-slate-950 font-sans text-xs">
            <div className="text-center pb-4 border-b border-dashed">
              <div className="font-bold text-base tracking-widest text-primary uppercase">
                CERTIFICATE OF ANALYSIS (CoA)
              </div>
              <div className="text-[11px] text-slate-500 font-medium">
                QUALITY ASSURANCE & STATUTORY RELEASE REPORT
              </div>
              <div className="font-mono text-sm font-bold mt-1 text-slate-900 dark:text-slate-100">
                CoA Ref: {printSlip.coa_number}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs py-2 border-b">
              <div>
                <span className="text-slate-400">Product Name:</span>{" "}
                <strong className="text-slate-900 dark:text-slate-100">{printSlip.product_name}</strong>
              </div>
              <div>
                <span className="text-slate-400">SKU / Model:</span>{" "}
                <strong className="font-mono">{printSlip.sku}</strong>
              </div>
              <div>
                <span className="text-slate-400">Batch Lot No:</span>{" "}
                <strong className="font-mono">{printSlip.batch_no}</strong>
              </div>
              <div>
                <span className="text-slate-400">Certified Lot Size:</span>{" "}
                <strong>{printSlip.lot_size}</strong>
              </div>
              <div>
                <span className="text-slate-400">Manufacturing Date:</span>{" "}
                {formatDate(printSlip.mfg_date)}
              </div>
              <div>
                <span className="text-slate-400">Expiry Date:</span>{" "}
                {formatDate(printSlip.expiry_date)}
              </div>
            </div>

            {/* Specifications Grid */}
            <div className="space-y-2 py-2">
              <div className="font-semibold text-xs text-slate-800 dark:text-slate-200 uppercase">
                Analytical Test Results ({printSlip.standards})
              </div>
              <table className="w-full text-xs text-left border">
                <thead className="bg-slate-50 dark:bg-slate-900 border-b">
                  <tr>
                    <th className="p-2">Test Parameter</th>
                    <th className="p-2">Method</th>
                    <th className="p-2">Specification</th>
                    <th className="p-2">Observed Result</th>
                    <th className="p-2 text-right">Decision</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {printSlip.specifications.map((s, idx) => (
                    <tr key={idx}>
                      <td className="p-2 font-medium">{s.test_name}</td>
                      <td className="p-2 text-slate-500">{s.method}</td>
                      <td className="p-2 text-slate-600 dark:text-slate-400">{s.specification}</td>
                      <td className="p-2 font-mono font-semibold text-slate-900 dark:text-slate-100">
                        {s.result}
                      </td>
                      <td className="p-2 text-right">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                          {s.decision}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pt-4 border-t flex justify-between items-center text-[11px] text-slate-500">
              <div>
                <div className="font-bold text-slate-800 dark:text-slate-200">{printSlip.qa_signoff}</div>
                <div>Authorized Date: {printSlip.certified_date}</div>
              </div>
              <div className="flex gap-2">
                <ActionButton tone="ghost" onClick={() => setPrintCoaId(null)}>
                  Close
                </ActionButton>
                <ActionButton tone="primary" onClick={() => window.print()}>
                  <Printer className="w-4 h-4 mr-1.5" />
                  Print Official CoA
                </ActionButton>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center text-slate-400">Loading Certificate details...</div>
        )}
      </Modal>
    </Shell>
  );
}
