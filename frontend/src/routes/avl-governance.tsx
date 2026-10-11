import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  CheckCircle,
  FileCheck,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
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

interface AvlVendor {
  id: string;
  vendor_party_id: string;
  vendor_name: string;
  vendor_code: string;
  product_id: string | null;
  sku: string;
  category: string;
  status: "approved" | "conditional_trial" | "disqualified";
  audit_score: number;
  qualification_date: string;
  max_po_limit: number | null;
  notes: string | null;
  created_at: string;
}

interface VendorCert {
  id: string;
  vendor_party_id: string;
  vendor_name: string;
  cert_type: string;
  certificate_number: string;
  issuing_body: string;
  issue_date: string;
  expiry_date: string;
  days_to_expiry: number;
  status: "valid" | "expiring_soon" | "expired";
  document_url: string | null;
  created_at: string;
}

interface PoEligibilityResult {
  eligible: boolean;
  reason: string;
  status: string;
}

export default function AvlGovernancePage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"avl" | "certs" | "checker">("avl");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Modals
  const [showQualifyModal, setShowQualifyModal] = useState(false);
  const [showCertModal, setShowCertModal] = useState(false);

  // Form states - Qualify Vendor
  const [vendorPartyId, setVendorPartyId] = useState("");
  const [selectedProductId, setSelectedProductId] = useState("");
  const [categoryName, setCategoryName] = useState("Electronics & Assemblies");
  const [qualificationStatus, setQualificationStatus] = useState<string>("approved");
  const [auditScore, setAuditScore] = useState<number>(85);
  const [maxPoLimit, setMaxPoLimit] = useState<string>("1000000");
  const [qualifyNotes, setQualifyNotes] = useState("");
  const [isSubmittingQualify, setIsSubmittingQualify] = useState(false);

  // Form states - Compliance Cert
  const [certVendorId, setCertVendorId] = useState("");
  const [certType, setCertType] = useState("ISO_9001");
  const [certNumber, setCertNumber] = useState("");
  const [issuingBody, setIssuingBody] = useState("TÜV SÜD");
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));
  const [expiryDate, setExpiryDate] = useState(
    new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  );
  const [docUrl, setDocUrl] = useState("");
  const [isSubmittingCert, setIsSubmittingCert] = useState(false);

  // Form states - PO Checker Simulator
  const [checkVendorId, setCheckVendorId] = useState("");
  const [checkProductId, setCheckProductId] = useState("");
  const [checkPoAmount, setCheckPoAmount] = useState("");
  const [isCheckingPo, setIsCheckingPo] = useState(false);
  const [poCheckResult, setPoCheckResult] = useState<PoEligibilityResult | null>(null);

  // 1. Fetch AVL Vendors
  const { data: avlData, isLoading: avlLoading, refetch: refetchAvl } = useQuery<{ vendors: AvlVendor[] }>({
    queryKey: ["avl-vendors", statusFilter],
    queryFn: async () => {
      const qs = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      return await api<{ vendors: AvlVendor[] }>("GET", `/api/v1/avl/vendors${qs}`);
    },
  });

  // 2. Fetch Compliance Certificates
  const { data: certsData, isLoading: certsLoading, refetch: refetchCerts } = useQuery<{ certificates: VendorCert[] }>({
    queryKey: ["avl-certs"],
    queryFn: async () => {
      return await api<{ certificates: VendorCert[] }>("GET", "/api/v1/avl/certs");
    },
  });

  // 3. Fetch Vendors & Products reference list
  const { data: vendorList = [] } = useQuery<{ id: string; displayName?: string; name?: string; code?: string }[]>({
    queryKey: ["party-vendors-list"],
    queryFn: async () => {
      const res = await api<{ data: { id: string; displayName?: string; name?: string; code?: string }[] }>(
        "GET",
        "/api/v1/parties?type=vendor&limit=100"
      );
      return res?.data || [];
    },
  });

  const { data: productList = [] } = useQuery<{ id: string; sku: string; name: string }[]>({
    queryKey: ["products-active-list"],
    queryFn: async () => {
      const res = await api<{ data: { id: string; sku: string; name: string }[] }>(
        "GET",
        "/api/v1/products?limit=200"
      );
      return res?.data || [];
    },
  });

  const vendors = avlData?.vendors || [];
  const certs = certsData?.certificates || [];

  // Filter vendors
  const filteredVendors = vendors.filter((v) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      v.vendor_name.toLowerCase().includes(term) ||
      v.vendor_code.toLowerCase().includes(term) ||
      v.sku.toLowerCase().includes(term) ||
      v.category.toLowerCase().includes(term)
    );
  });

  // KPI Calculations
  const totalApproved = vendors.filter((v) => v.status === "approved").length;
  const conditionalCount = vendors.filter((v) => v.status === "conditional_trial").length;
  const disqualifiedCount = vendors.filter((v) => v.status === "disqualified").length;
  const expiringCertsCount = certs.filter((c) => c.status === "expiring_soon" || c.status === "expired").length;

  // Actions
  const handleQualifySubmit = async () => {
    if (!vendorPartyId) {
      alert("Please select a vendor supplier.");
      return;
    }
    setIsSubmittingQualify(true);
    try {
      await api("POST", "/api/v1/avl/vendors", {
        json: {
          vendor_party_id: vendorPartyId,
          product_id: selectedProductId || null,
          category: categoryName,
          status: qualificationStatus,
          audit_score: auditScore,
          max_po_limit: maxPoLimit ? parseFloat(maxPoLimit) : null,
          notes: qualifyNotes || null,
        },
      });
      setShowQualifyModal(false);
      setVendorPartyId("");
      setSelectedProductId("");
      setQualifyNotes("");
      qc.invalidateQueries({ queryKey: ["avl-vendors"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to qualify supplier.";
      alert(message);
    } finally {
      setIsSubmittingQualify(false);
    }
  };

  const handleUpdateStatus = async (avlId: string, newStatus: string) => {
    try {
      await api("PATCH", `/api/v1/avl/vendors/${avlId}/status?status=${newStatus}`);
      qc.invalidateQueries({ queryKey: ["avl-vendors"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to update vendor status.";
      alert(message);
    }
  };

  const handleRegisterCert = async () => {
    if (!certVendorId || !certNumber.trim() || !issuingBody.trim()) {
      alert("Please complete required certificate fields.");
      return;
    }
    setIsSubmittingCert(true);
    try {
      await api("POST", "/api/v1/avl/certs", {
        json: {
          vendor_party_id: certVendorId,
          cert_type: certType,
          certificate_number: certNumber,
          issuing_body: issuingBody,
          issue_date: issueDate,
          expiry_date: expiryDate,
          document_url: docUrl || null,
        },
      });
      setShowCertModal(false);
      setCertVendorId("");
      setCertNumber("");
      setDocUrl("");
      qc.invalidateQueries({ queryKey: ["avl-certs"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to register certificate.";
      alert(message);
    } finally {
      setIsSubmittingCert(false);
    }
  };

  const handleRunPoCheck = async () => {
    if (!checkVendorId) {
      alert("Please select a vendor to test PO clearance.");
      return;
    }
    setIsCheckingPo(true);
    setPoCheckResult(null);
    try {
      let url = `/api/v1/avl/check-po?vendor_party_id=${checkVendorId}`;
      if (checkProductId) url += `&product_id=${checkProductId}`;
      if (checkPoAmount) url += `&order_amount=${checkPoAmount}`;

      const res = await api<PoEligibilityResult>("GET", url);
      setPoCheckResult(res);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to evaluate PO eligibility.";
      alert(message);
    } finally {
      setIsCheckingPo(false);
    }
  };

  return (
    <Shell>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Approved Vendor List (AVL) & Governance"
          description="Quality-accredited supplier qualification registry, ISO/RoHS compliance audits, and pre-award PO clearance gates"
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                onClick={() => {
                  refetchAvl();
                  refetchCerts();
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </ActionButton>
              {activeTab === "avl" && (
                <ActionButton tone="primary" onClick={() => setShowQualifyModal(true)}>
                  <Plus className="mr-1 h-4 w-4" /> Qualify Supplier (AVL)
                </ActionButton>
              )}
              {activeTab === "certs" && (
                <ActionButton tone="primary" onClick={() => setShowCertModal(true)}>
                  <FileCheck className="mr-1 h-4 w-4" /> Register Certificate
                </ActionButton>
              )}
            </div>
          }
        />

        {/* Top KPIs */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Approved AVL Suppliers"
            value={totalApproved.toString()}
            hint="Fully certified for production PO placement"
          />
          <StatCard
            label="Conditional / Trial"
            value={conditionalCount.toString()}
            hint="Subject to restricted order value ceiling"
          />
          <StatCard
            label="Disqualified Suppliers"
            value={disqualifiedCount.toString()}
            hint="Blocked from procurement requisition awards"
          />
          <StatCard
            label="Certificates Due / Expired"
            value={expiringCertsCount.toString()}
            hint="ISO/RoHS accreditation requiring QA audit"
          />
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)]">
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "avl"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("avl")}
          >
            Approved Vendor List (AVL) Matrix
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "certs"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("certs")}
          >
            Quality & Compliance Certifications (ISO/RoHS)
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "checker"
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("checker")}
          >
            Pre-Award PO Eligibility Radar
          </button>
        </div>

        {/* TAB 1: AVL Matrix */}
        {activeTab === "avl" && (
          <Panel
            title="Supplier Accreditation Matrix"
            aside={
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
                  <input
                    type="text"
                    placeholder="Search vendor, SKU, category..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-64 rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pl-9 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm"
                >
                  <option value="all">All Qualification Statuses</option>
                  <option value="approved">Approved</option>
                  <option value="conditional_trial">Conditional Trial</option>
                  <option value="disqualified">Disqualified</option>
                </select>
              </div>
            }
          >
            {avlLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading AVL registry...</div>
            ) : filteredVendors.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">
                No vendors qualified matching the current filter.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Supplier Name & Code",
                  "Qualified Scope",
                  "Audit Score",
                  "Qualification Status",
                  "Max PO Ceiling",
                  "Qualified On",
                  "Actions",
                ]}
              >
                {filteredVendors.map((v) => (
                  <TableRow
                    key={v.id}
                    cells={[
                      <div>
                        <div className="font-semibold text-sm">{v.vendor_name}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{v.vendor_code}</div>
                      </div>,
                      <div>
                        <div className="font-medium text-sm">{v.category}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">
                          {v.sku === "Category-Wide" ? "All category lines" : `SKU: ${v.sku}`}
                        </div>
                      </div>,
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold font-mono text-sm ${
                            v.audit_score >= 85
                              ? "text-green-600 dark:text-green-400"
                              : v.audit_score >= 70
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-red-600 dark:text-red-400"
                          }`}
                        >
                          {v.audit_score}/100
                        </span>
                        <div className="h-2 w-16 overflow-hidden rounded-full bg-[var(--border)]">
                          <div
                            className={`h-full ${
                              v.audit_score >= 85
                                ? "bg-green-500"
                                : v.audit_score >= 70
                                ? "bg-amber-500"
                                : "bg-red-500"
                            }`}
                            style={{ width: `${v.audit_score}%` }}
                          />
                        </div>
                      </div>,
                      <Pill
                        tone={
                          v.status === "approved"
                            ? "success"
                            : v.status === "conditional_trial"
                            ? "warning"
                            : "destructive"
                        }
                      >
                        {v.status === "approved"
                          ? "Approved"
                          : v.status === "conditional_trial"
                          ? "Conditional Trial"
                          : "Disqualified"}
                      </Pill>,
                      <div>{v.max_po_limit ? money(v.max_po_limit) : "No Ceiling (Unlimited)"}</div>,
                      <div>{formatDate(v.qualification_date)}</div>,
                      <div className="flex items-center gap-1.5">
                        {v.status !== "approved" && (
                          <ActionButton
                            size="sm"
                            tone="primary"
                            onClick={() => handleUpdateStatus(v.id, "approved")}
                          >
                            Approve
                          </ActionButton>
                        )}
                        {v.status !== "conditional_trial" && (
                          <ActionButton
                            size="sm"
                            tone="ghost"
                            onClick={() => handleUpdateStatus(v.id, "conditional_trial")}
                          >
                            Set Trial
                          </ActionButton>
                        )}
                        {v.status !== "disqualified" && (
                          <ActionButton
                            size="sm"
                            tone="danger"
                            onClick={() => handleUpdateStatus(v.id, "disqualified")}
                          >
                            Disqualify
                          </ActionButton>
                        )}
                      </div>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 2: Compliance Certificates */}
        {activeTab === "certs" && (
          <Panel
            title="Quality & Regulatory Accreditations (ISO / RoHS / REACH / IATF)"
            aside={
              <ActionButton tone="primary" onClick={() => setShowCertModal(true)}>
                <Plus className="mr-1 h-4 w-4" /> Add Certificate
              </ActionButton>
            }
          >
            {certsLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading compliance certificates...</div>
            ) : certs.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">
                No compliance certificates logged yet. Register supplier ISO/RoHS credentials.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Supplier",
                  "Standard / Type",
                  "Certificate No.",
                  "Auditing Body",
                  "Issue Date",
                  "Expiry Date",
                  "Audit Status",
                  "Document",
                ]}
              >
                {certs.map((c) => (
                  <TableRow
                    key={c.id}
                    cells={[
                      <div className="font-semibold text-sm">{c.vendor_name}</div>,
                      <div className="flex items-center gap-1.5 font-medium">
                        <Award className="h-4 w-4 text-blue-500" />
                        <span>{c.cert_type.replace(/_/g, " ")}</span>
                      </div>,
                      <span className="font-mono text-xs">{c.certificate_number}</span>,
                      <div>{c.issuing_body}</div>,
                      <div>{formatDate(c.issue_date)}</div>,
                      <div>
                        <div>{formatDate(c.expiry_date)}</div>
                        <div
                          className={`text-xs ${
                            c.days_to_expiry < 0
                              ? "font-semibold text-red-500"
                              : c.days_to_expiry < 30
                              ? "font-semibold text-amber-500"
                              : "text-[var(--muted-foreground)]"
                          }`}
                        >
                          {c.days_to_expiry < 0
                            ? `Expired ${Math.abs(c.days_to_expiry)}d ago`
                            : `${c.days_to_expiry} days left`}
                        </div>
                      </div>,
                      <Pill
                        tone={
                          c.status === "valid"
                            ? "success"
                            : c.status === "expiring_soon"
                            ? "warning"
                            : "destructive"
                        }
                      >
                        {c.status === "valid"
                          ? "Valid & Active"
                          : c.status === "expiring_soon"
                          ? "Expiring Soon"
                          : "Expired"}
                      </Pill>,
                      c.document_url ? (
                        <a
                          href={c.document_url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-blue-600 text-xs hover:underline dark:text-blue-400"
                        >
                          View PDF
                        </a>
                      ) : (
                        <span className="text-xs text-[var(--muted-foreground)]">On File</span>
                      ),
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 3: Pre-Award PO Clearance Checker */}
        {activeTab === "checker" && (
          <Panel title="Pre-Award Purchase Order Qualification Clearance Gate">
            <div className="flex flex-col gap-6">
              <p className="text-sm text-[var(--muted-foreground)]">
                Simulate procurement PO clearance rules. The ERP validates whether the selected supplier is accredited
                on the Approved Vendor List (AVL), checks audit standing, and enforces max order limits before contract
                award.
              </p>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Field label="Supplier Vendor *">
                  <select
                    value={checkVendorId}
                    onChange={(e) => setCheckVendorId(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="">-- Select Vendor --</option>
                    {vendorList.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.displayName || v.name || v.code}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Product SKU (Optional)">
                  <select
                    value={checkProductId}
                    onChange={(e) => setCheckProductId(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="">-- Any SKU / General Category --</option>
                    {productList.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} - {p.name}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Proposed PO Value (₹)">
                  <TextInput
                    type="number"
                    value={checkPoAmount}
                    onChange={(e) => setCheckPoAmount(e.target.value)}
                    placeholder="e.g. 500000"
                  />
                </Field>
              </div>

              <div>
                <ActionButton tone="primary" onClick={handleRunPoCheck} disabled={isCheckingPo}>
                  {isCheckingPo ? "Evaluating Clearance..." : "Evaluate PO Eligibility Gate"}
                </ActionButton>
              </div>

              {/* Clearance Results */}
              {poCheckResult && (
                <div
                  className={`rounded-lg border p-5 ${
                    poCheckResult.eligible
                      ? "border-green-200 bg-green-50 text-green-900 dark:border-green-900/50 dark:bg-green-950/20 dark:text-green-300"
                      : "border-red-200 bg-red-50 text-red-900 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {poCheckResult.eligible ? (
                      <ShieldCheck className="h-6 w-6 shrink-0 text-green-600 dark:text-green-400" />
                    ) : (
                      <ShieldAlert className="h-6 w-6 shrink-0 text-red-600 dark:text-red-400" />
                    )}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-base">
                          {poCheckResult.eligible
                            ? "CLEARANCE GRANTED: Supplier Eligible for PO Award"
                            : "PO PLACEMENT BLOCKED: Qualification Clearance Failed"}
                        </span>
                        <Pill tone={poCheckResult.eligible ? "success" : "destructive"}>
                          {poCheckResult.status.toUpperCase()}
                        </Pill>
                      </div>
                      <p className="mt-1 font-medium text-sm opacity-90">{poCheckResult.reason}</p>
                      {poCheckResult.eligible ? (
                        <div className="mt-3 flex items-center gap-2 text-xs opacity-80">
                          <CheckCircle className="h-4 w-4" />
                          <span>Supplier passes all AVL quality and accreditation threshold checks.</span>
                        </div>
                      ) : (
                        <div className="mt-3 flex items-center gap-2 text-xs opacity-80">
                          <ShieldAlert className="h-4 w-4" />
                          <span>Requires Quality Manager approval or formal vendor requalification.</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Panel>
        )}

        {/* Modal: Qualify Supplier */}
        {showQualifyModal && (
          <Modal open={showQualifyModal} title="Qualify Supplier for Approved Vendor List (AVL)" onClose={() => setShowQualifyModal(false)}>
            <div className="flex flex-col gap-4">
              <Field label="Supplier Vendor *">
                <select
                  value={vendorPartyId}
                  onChange={(e) => setVendorPartyId(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">-- Select Vendor --</option>
                  {vendorList.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.displayName || v.name || v.code}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Specific SKU Scope (Optional)">
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">Category-Wide (All Products)</option>
                  {productList.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.sku} - {p.name}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Commodity / Category">
                <TextInput
                  value={categoryName}
                  onChange={(e) => setCategoryName(e.target.value)}
                  placeholder="e.g. Precision CNC Machining"
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Initial Qualification Status">
                  <select
                    value={qualificationStatus}
                    onChange={(e) => setQualificationStatus(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="approved">Approved</option>
                    <option value="conditional_trial">Conditional Trial</option>
                    <option value="disqualified">Disqualified</option>
                  </select>
                </Field>

                <Field label="Audit Score (0-100)">
                  <TextInput
                    type="number"
                    value={auditScore.toString()}
                    onChange={(e) => setAuditScore(parseInt(e.target.value) || 0)}
                  />
                </Field>
              </div>

              <Field label="Max PO Limit Ceiling (₹)">
                <TextInput
                  type="number"
                  value={maxPoLimit}
                  onChange={(e) => setMaxPoLimit(e.target.value)}
                  placeholder="Leave empty for unlimited"
                />
              </Field>

              <Field label="Audit Notes & Remarks">
                <TextInput
                  value={qualifyNotes}
                  onChange={(e) => setQualifyNotes(e.target.value)}
                  placeholder="e.g. Passed ISO 9001 on-site plant inspection with zero major non-conformances"
                />
              </Field>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setShowQualifyModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleQualifySubmit} disabled={isSubmittingQualify}>
                  {isSubmittingQualify ? "Saving..." : "Add to Approved Vendor List"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}

        {/* Modal: Register Compliance Certificate */}
        {showCertModal && (
          <Modal open={showCertModal} title="Register Quality & Regulatory Accreditation" onClose={() => setShowCertModal(false)}>
            <div className="flex flex-col gap-4">
              <Field label="Supplier Vendor *">
                <select
                  value={certVendorId}
                  onChange={(e) => setCertVendorId(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">-- Select Vendor --</option>
                  {vendorList.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.displayName || v.name || v.code}
                    </option>
                  ))}
                </select>
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Accreditation Standard *">
                  <select
                    value={certType}
                    onChange={(e) => setCertType(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="ISO_9001">ISO 9001:2015 (Quality)</option>
                    <option value="IATF_16949">IATF 16949 (Automotive)</option>
                    <option value="ISO_14001">ISO 14001 (Environmental)</option>
                    <option value="ROHS">RoHS Compliance</option>
                    <option value="REACH">REACH Declaration</option>
                    <option value="GMP">Good Manufacturing Practice (GMP)</option>
                    <option value="CUSTOM">Custom QA Accreditation</option>
                  </select>
                </Field>

                <Field label="Certificate Number *">
                  <TextInput
                    value={certNumber}
                    onChange={(e) => setCertNumber(e.target.value)}
                    placeholder="e.g. CERT-ISO-9001-88421"
                  />
                </Field>
              </div>

              <Field label="Auditing / Certification Body *">
                <TextInput
                  value={issuingBody}
                  onChange={(e) => setIssuingBody(e.target.value)}
                  placeholder="e.g. TÜV Rheinland, BSI, DNV"
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Issue Date *">
                  <TextInput type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
                </Field>

                <Field label="Expiry Date *">
                  <TextInput type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
                </Field>
              </div>

              <Field label="Certificate Document URL (Optional)">
                <TextInput
                  value={docUrl}
                  onChange={(e) => setDocUrl(e.target.value)}
                  placeholder="https://docs.acme.com/certs/iso9001.pdf"
                />
              </Field>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setShowCertModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleRegisterCert} disabled={isSubmittingCert}>
                  {isSubmittingCert ? "Registering..." : "Register Accreditation"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
