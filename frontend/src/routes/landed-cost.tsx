import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  Plus,
  ShieldCheck,
  Truck,
  X,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  InfoTooltip,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface LandedCostItem {
  id: string;
  grn_id: string;
  grn_number: string;
  grn_line_id: string;
  product_id: string;
  sku: string;
  product_name?: string;
  quantity: number;
  uom: string;
  weight_kg: number;
  volume_cbm: number;
  base_unit_price: number;
  base_total_amount: number;
  allocated_charges: number;
  final_unit_cost: number;
  cost_variance_pct: number;
}

interface LandedCostCharge {
  id?: string;
  charge_type: string;
  description?: string;
  vendor_id?: string;
  vendor_name?: string;
  invoice_ref?: string;
  amount: number;
  apportion_by: "value" | "weight" | "volume" | "quantity";
}

interface LandedCostReceipt {
  id?: string;
  grn_id: string;
  grn_number: string;
  receipt_date: string;
  vendor_name?: string;
  grand_total: number;
  lines?: any[];
}

interface GlEntry {
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  vendor: string;
  ref: string;
}

interface LandedCostVoucher {
  id: string;
  voucher_no: string;
  posting_date: string;
  status: "draft" | "posted" | "cancelled";
  currency: string;
  total_charges: number;
  notes?: string;
  created_by?: string;
  posted_by?: string;
  posted_at?: string;
  created_at: string;
  receipts: LandedCostReceipt[];
  charges: LandedCostCharge[];
  items: LandedCostItem[];
  gl_entries?: GlEntry[];
}

const CHARGE_TYPES = [
  { value: "freight", label: "Ocean / Air Freight" },
  { value: "customs", label: "Customs & Import Tariff" },
  { value: "handling", label: "Port Terminal Handling" },
  { value: "insurance", label: "Marine Transit Insurance" },
  { value: "demurrage", label: "Port Demurrage / Storage" },
  { value: "other", label: "Other Indirect Surcharge" },
];

const APPORTION_METHODS = [
  { value: "value", label: "By Item Value (Ad Valorem)" },
  { value: "weight", label: "By Gross Weight (kg)" },
  { value: "volume", label: "By Volume (CBM)" },
  { value: "quantity", label: "By Unit Quantity" },
];

export default function LandedCostPage() {
  const { api, can } = useAuth();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedVoucher, setSelectedVoucher] = useState<LandedCostVoucher | null>(null);

  // Queries
  const { data: vouchers = [], isLoading: vouchersLoading } = useQuery<LandedCostVoucher[]>({
    queryKey: ["landed-costs", statusFilter],
    queryFn: () =>
      api<LandedCostVoucher[]>(
        "GET",
        statusFilter === "all" ? "/api/v1/landed-costs" : `/api/v1/landed-costs?status=${statusFilter}`
      ),
  });

  const { data: eligibleGrns = [], isLoading: grnsLoading } = useQuery<any[]>({
    queryKey: ["eligible-grns"],
    queryFn: () => api<any[]>("GET", "/api/v1/landed-costs/eligible-grns"),
    enabled: createModalOpen,
  });

  // Post Voucher Mutation
  const postMutation = useMutation({
    mutationFn: (voucherId: string) => api<LandedCostVoucher>("POST", `/api/v1/landed-costs/${voucherId}/post`),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["landed-costs"] });
      setSelectedVoucher(updated);
    },
  });

  // Cancel Voucher Mutation
  const cancelMutation = useMutation({
    mutationFn: (voucherId: string) => api<LandedCostVoucher>("POST", `/api/v1/landed-costs/${voucherId}/cancel`),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["landed-costs"] });
      setSelectedVoucher(updated);
    },
  });

  // KPI Calculations
  const totalApportioned = vouchers
    .filter((v) => v.status === "posted")
    .reduce((sum, v) => sum + (v.total_charges || 0), 0);
  const postedCount = vouchers.filter((v) => v.status === "posted").length;
  const draftCount = vouchers.filter((v) => v.status === "draft").length;

  const filteredVouchers = vouchers.filter((v) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      v.voucher_no.toLowerCase().includes(q) ||
      (v.notes && v.notes.toLowerCase().includes(q)) ||
      v.receipts.some((r) => r.grn_number.toLowerCase().includes(q) || (r.vendor_name && r.vendor_name.toLowerCase().includes(q)))
    );
  });

  return (
    <Shell>
      <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          eyebrow="Warehouse &amp; Logistics"
          title="Landed Cost Tracking &amp; Valuation"
          description="Apportion customs tariffs, sea/air freight, transit insurance, and port handling into inventory moving average costs under IAS 2."
          actions={
            <ActionButton
              tone="primary"
              size="sm"
              onClick={() => setCreateModalOpen(true)}
              disabled={!can("landed_cost:write")}
              className="gap-2"
            >
              <Plus size={15} />
              <span>Create Landed Cost Voucher</span>
            </ActionButton>
          }
        />

        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Inbound Apportioned"
            value={`₹${totalApportioned.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`}
            hint={`${postedCount} posted vouchers`}
            tone="success"
          />
          <StatCard
            label="Draft Vouchers"
            value={draftCount}
            hint="Awaiting cost finalization"
            tone={draftCount > 0 ? "warning" : "muted"}
          />
          <StatCard
            label="Eligible Receipts"
            value={eligibleGrns.length || "—"}
            hint="Posted GRNs awaiting costing"
            tone="info"
          />
          <StatCard
            label="Valuation Standard"
            value="IAS 2 / GAAP"
            hint="Moving Average Capitalization"
            tone="muted"
          />
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {(["all", "draft", "posted", "cancelled"] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition",
                  statusFilter === st
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm"
                    : "bg-[var(--muted)]/60 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                {st}
              </button>
            ))}
          </div>

          <div className="w-full sm:w-64">
            <label htmlFor="landed-cost-search" className="sr-only">Search voucher, GRN, vendor</label>
            <TextInput
              id="landed-cost-search"
              placeholder="Search voucher, GRN, vendor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Vouchers Table */}
        <Panel
          title="Landed Cost Vouchers"
          subtitle={`${filteredVouchers.length} vouchers recorded`}
        >
          <DataTable
            columns={[
              "Voucher #",
              "Posting Date",
              "Status",
              "GRN Receipts",
              "Items",
              <span key="apportioned" className="inline-flex items-center gap-1">Total Apportioned <InfoTooltip content="Apportionment formula: Freight & Customs duty allocated by Value-weighted (Duty/CIF allocation by line monetary value) or Weight-weighted (Freight allocation by physical kg)." /></span>,
              "Created By",
              "Actions",
            ]}
          >
            {filteredVouchers.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-8 text-xs text-[var(--muted-foreground)]">
                  {vouchersLoading ? "Loading vouchers…" : "No landed cost vouchers found."}
                </td>
              </tr>
            ) : (
              filteredVouchers.map((v) => (
                <TableRow
                  key={v.id}
                  onClick={() => setSelectedVoucher(v)}
                  selected={selectedVoucher?.id === v.id}
                  cells={[
                    <span className="font-mono font-bold text-blue-600 dark:text-blue-400">{v.voucher_no}</span>,
                    <span>{v.posting_date}</span>,
                    <Pill tone={v.status === "posted" ? "success" : v.status === "draft" ? "warning" : "muted"}>
                      {v.status}
                    </Pill>,
                    <span className="font-mono text-xs">
                      {v.receipts.map((r) => r.grn_number).join(", ") || "—"}
                    </span>,
                    <span>{v.items.length} lines</span>,
                    <span className="font-mono font-bold">
                      ₹{v.total_charges.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </span>,
                    <span className="text-xs text-[var(--muted-foreground)]">{v.created_by || "system"}</span>,
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedVoucher(v);
                      }}
                      className="text-xs text-blue-600 hover:underline font-medium"
                    >
                      View Details &rarr;
                    </button>,
                  ]}
                />
              ))
            )}
          </DataTable>
        </Panel>

        {/* Voucher Detail Modal */}
        {selectedVoucher && (
          <Modal
            open={!!selectedVoucher}
            onClose={() => setSelectedVoucher(null)}
            title={`Landed Cost Voucher: ${selectedVoucher.voucher_no}`}
            description={`Posted on ${selectedVoucher.posting_date} • Currency: ${selectedVoucher.currency}`}
            wide
            footer={
              <div className="flex items-center justify-end gap-2 w-full">
                {selectedVoucher.status === "draft" && (
                  <>
                    <ActionButton
                      tone="danger"
                      size="sm"
                      onClick={() => cancelMutation.mutate(selectedVoucher.id)}
                      loading={cancelMutation.isPending}
                    >
                      Cancel Voucher
                    </ActionButton>
                    <ActionButton
                      tone="primary"
                      size="sm"
                      onClick={() => postMutation.mutate(selectedVoucher.id)}
                      loading={postMutation.isPending}
                    >
                      Post to Inventory Valuation
                    </ActionButton>
                  </>
                )}
                <ActionButton tone="ghost" size="sm" onClick={() => setSelectedVoucher(null)}>
                  Close
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-6 max-h-[75vh] overflow-y-auto pr-1">
              {/* Status Header */}
              <div className="flex flex-wrap items-center justify-between p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] gap-4">
                <div>
                  <div className="text-xs font-semibold text-[var(--muted-foreground)]">Voucher Lifecycle Status</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Pill tone={selectedVoucher.status === "posted" ? "success" : selectedVoucher.status === "draft" ? "warning" : "muted"}>
                      {selectedVoucher.status.toUpperCase()}
                    </Pill>
                    {selectedVoucher.posted_at && (
                      <span className="text-xs text-[var(--muted-foreground)]">
                        at {new Date(selectedVoucher.posted_at).toLocaleString()} by {selectedVoucher.posted_by}
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-[var(--muted-foreground)]">Total Capitalized Inbound Charges</div>
                  <div className="text-lg font-mono font-bold text-[var(--primary)] mt-0.5">
                    ₹{selectedVoucher.total_charges.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </div>

              {/* Linked Receipts */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Linked Goods Receipts (GRNs)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {selectedVoucher.receipts.map((r, i) => (
                    <div key={i} className="p-3 rounded-lg border border-[var(--border)] bg-[var(--card)] flex justify-between items-center text-xs">
                      <div>
                        <div className="font-mono font-bold text-blue-600">{r.grn_number}</div>
                        <div className="text-[var(--muted-foreground)] mt-0.5">{r.vendor_name || "Supplier"} • {r.receipt_date}</div>
                      </div>
                      <div className="font-mono font-semibold">
                        Base: ₹{r.grand_total.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Expense Charges Apportioned */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Inbound Charges Breakdown
                </h4>
                <div className="rounded-xl border border-[var(--border)] overflow-hidden">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[var(--muted)]/40 border-b border-[var(--border)] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Expense Category</th>
                        <th className="py-2.5 px-3">Service Vendor</th>
                        <th className="py-2.5 px-3">Invoice / BL Ref</th>
                        <th className="py-2.5 px-3">Allocation Basis</th>
                        <th className="py-2.5 px-3 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {selectedVoucher.charges.map((c, i) => (
                        <tr key={i}>
                          <td className="py-2.5 px-3 font-medium capitalize">{c.charge_type.replace("_", " ")}</td>
                          <td className="py-2.5 px-3 text-[var(--muted-foreground)]">{c.vendor_name || "—"}</td>
                          <td className="py-2.5 px-3 font-mono">{c.invoice_ref || "—"}</td>
                          <td className="py-2.5 px-3 capitalize">By {c.apportion_by}</td>
                          <td className="py-2.5 px-3 text-right font-mono font-semibold">
                            ₹{c.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recalculated Item Valuation Table */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Item Cost Apportionment &amp; Valuation Impact
                </h4>
                <div className="rounded-xl border border-[var(--border)] overflow-hidden">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[var(--muted)]/40 border-b border-[var(--border)] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">SKU &amp; Product</th>
                        <th className="py-2.5 px-3">Qty</th>
                        <th className="py-2.5 px-3">Base PO Price</th>
                        <th className="py-2.5 px-3 text-right">Allocated Charge</th>
                        <th className="py-2.5 px-3 text-right font-bold text-[var(--primary)]">True Landed Cost</th>
                        <th className="py-2.5 px-3 text-right">Markup %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)] font-mono">
                      {selectedVoucher.items.map((itm, i) => (
                        <tr key={i}>
                          <td className="py-2.5 px-3 font-sans">
                            <span className="font-mono font-semibold text-blue-600 block">{itm.sku}</span>
                            <span className="text-[11px] text-[var(--muted-foreground)]">{itm.product_name || "Material Line"}</span>
                          </td>
                          <td className="py-2.5 px-3">{itm.quantity} {itm.uom}</td>
                          <td className="py-2.5 px-3">₹{itm.base_unit_price.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right text-emerald-600">+₹{itm.allocated_charges.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right font-bold text-blue-600 dark:text-blue-400">
                            ₹{itm.final_unit_cost.toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right text-amber-600">+{itm.cost_variance_pct.toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Double-Entry GL Journal Entries */}
              {selectedVoucher.gl_entries && selectedVoucher.gl_entries.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] flex items-center gap-1.5">
                    <ShieldCheck size={14} className="text-emerald-500" />
                    Double-Entry General Ledger (GL) Audit Preview
                  </h4>
                  <div className="rounded-xl border border-[var(--border)] overflow-hidden">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-[var(--muted)]/40 border-b border-[var(--border)] font-semibold">
                        <tr>
                          <th className="py-2 px-3">Account Code &amp; Name</th>
                          <th className="py-2 px-3">Sub-Ledger Party</th>
                          <th className="py-2 px-3 text-right">Debit (₹)</th>
                          <th className="py-2 px-3 text-right">Credit (₹)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)] font-mono text-[11px]">
                        {selectedVoucher.gl_entries.map((gl, i) => (
                          <tr key={i}>
                            <td className="py-2 px-3">
                              <span className="font-semibold block text-[var(--foreground)]">{gl.account_name}</span>
                              <span className="text-[10px] text-[var(--muted-foreground)]">{gl.account_code}</span>
                            </td>
                            <td className="py-2 px-3 text-[var(--muted-foreground)] font-sans">{gl.vendor}</td>
                            <td className="py-2 px-3 text-right font-semibold text-blue-600">
                              {gl.debit > 0 ? `₹${gl.debit.toFixed(2)}` : "—"}
                            </td>
                            <td className="py-2 px-3 text-right font-semibold text-slate-600">
                              {gl.credit > 0 ? `₹${gl.credit.toFixed(2)}` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </Modal>
        )}

        {/* Voucher Creator Wizard Dialog */}
        {createModalOpen && (
          <CreateVoucherWizard
            open={createModalOpen}
            onClose={() => setCreateModalOpen(false)}
            eligibleGrns={eligibleGrns}
            grnsLoading={grnsLoading}
            onCreated={(voucher) => {
              queryClient.invalidateQueries({ queryKey: ["landed-costs"] });
              setCreateModalOpen(false);
              setSelectedVoucher(voucher);
            }}
          />
        )}
      </div>
    </Shell>
  );
}

/** New Voucher Creation Wizard Component */
function CreateVoucherWizard({
  open,
  onClose,
  eligibleGrns,
  grnsLoading,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  eligibleGrns: any[];
  grnsLoading: boolean;
  onCreated: (voucher: LandedCostVoucher) => void;
}) {
  const { api } = useAuth();
  const [selectedGrnIds, setSelectedGrnIds] = useState<string[]>([]);
  const [charges, setCharges] = useState<LandedCostCharge[]>([
    { charge_type: "freight", description: "Ocean Freight", amount: 5000, apportion_by: "value", vendor_name: "TransGlobal Shipping" },
    { charge_type: "customs", description: "Customs Duty Assessment", amount: 2500, apportion_by: "value", vendor_name: "Central Customs Port" },
  ]);
  const [notes, setNotes] = useState("");
  const [previewCalculation, setPreviewCalculation] = useState<any>(null);
  const [calculating, setCalculating] = useState(false);
  const [saving, setSaving] = useState(false);

  // Toggle GRN selection
  const toggleGrn = (grnId: string) => {
    setSelectedGrnIds((prev) =>
      prev.includes(grnId) ? prev.filter((id) => id !== grnId) : [...prev, grnId]
    );
  };

  // Compile selected items
  const selectedGrnObjects = eligibleGrns.filter((g) => selectedGrnIds.includes(g.id));
  const candidateItems = selectedGrnObjects.flatMap((g) => g.lines || []);

  // Add Charge row
  const addChargeRow = () => {
    setCharges((prev) => [
      ...prev,
      { charge_type: "handling", description: "Port Handling", amount: 1000, apportion_by: "value" },
    ]);
  };

  const removeChargeRow = (idx: number) => {
    setCharges((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateCharge = (idx: number, field: keyof LandedCostCharge, val: any) => {
    setCharges((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, [field]: val } : c))
    );
  };

  // Preview calculate
  const runPreviewCalculate = async () => {
    if (candidateItems.length === 0 || charges.length === 0) return;
    setCalculating(true);
    try {
      const res = await api<any>("POST", "/api/v1/landed-costs/calculate", {
        json: {
          items: candidateItems,
          charges: charges,
        },
      });
      setPreviewCalculation(res);
    } finally {
      setCalculating(false);
    }
  };

  // Save Voucher
  const handleSave = async (postImmediately: boolean) => {
    if (selectedGrnObjects.length === 0 || charges.length === 0) return;
    setSaving(true);
    try {
      const payload = {
        posting_date: new Date().toISOString().split("T")[0],
        currency: "INR",
        notes,
        receipts: selectedGrnObjects.map((g) => ({
          grn_id: g.id,
          grn_number: g.number,
          receipt_date: g.received_date,
          vendor_name: g.vendor_name,
          grand_total: g.grand_total,
        })),
        charges: charges.map((c) => ({
          charge_type: c.charge_type,
          description: c.description,
          vendor_name: c.vendor_name,
          invoice_ref: c.invoice_ref,
          amount: Number(c.amount),
          apportion_by: c.apportion_by,
        })),
        items: candidateItems,
      };

      const created = await api<LandedCostVoucher>("POST", "/api/v1/landed-costs", { json: payload });

      if (postImmediately) {
        const posted = await api<LandedCostVoucher>("POST", `/api/v1/landed-costs/${created.id}/post`);
        onCreated(posted);
      } else {
        onCreated(created);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Landed Cost Voucher (LCV)"
      description="Select goods receipts and apportion indirect charges across lines to calculate true landed cost."
      wide
      footer={
        <div className="flex items-center justify-end gap-2 w-full">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton
            tone="ghost"
            size="sm"
            onClick={() => handleSave(false)}
            loading={saving}
            disabled={selectedGrnIds.length === 0 || charges.length === 0}
          >
            Save as Draft
          </ActionButton>
          <ActionButton
            tone="primary"
            size="sm"
            onClick={() => handleSave(true)}
            loading={saving}
            disabled={selectedGrnIds.length === 0 || charges.length === 0}
          >
            Post &amp; Capitalize
          </ActionButton>
        </div>
      }
    >
      <div className="space-y-6 max-h-[75vh] overflow-y-auto pr-1">
        {/* Step 1: Select GRNs */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--primary)] flex items-center gap-1.5">
              <Boxes size={14} />
              Step 1: Select Posted Goods Receipts (GRNs)
            </h4>
            <span className="text-xs text-[var(--muted-foreground)]">
              {selectedGrnIds.length} GRN(s) selected • {candidateItems.length} items
            </span>
          </div>

          <div className="max-h-44 overflow-y-auto rounded-xl border border-[var(--border)] divide-y divide-[var(--border)]">
            {grnsLoading ? (
              <div className="p-4 text-center text-xs text-[var(--muted-foreground)]">Loading eligible GRNs…</div>
            ) : eligibleGrns.length === 0 ? (
              <div className="p-4 text-center text-xs text-[var(--muted-foreground)]">No eligible posted GRNs found.</div>
            ) : (
              eligibleGrns.map((g) => {
                const isSelected = selectedGrnIds.includes(g.id);
                return (
                  <div
                    key={g.id}
                    onClick={() => toggleGrn(g.id)}
                    className={cn(
                      "p-3 flex items-center justify-between text-xs cursor-pointer transition",
                      isSelected ? "bg-blue-500/10" : "hover:bg-[var(--muted)]/30"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="rounded accent-blue-600"
                      />
                      <div>
                        <span className="font-mono font-bold text-blue-600">{g.number}</span>
                        <span className="text-[var(--muted-foreground)] ml-2">
                          {g.vendor_name || "Supplier"} • PO: {g.po_number || "—"} • {g.received_date}
                        </span>
                      </div>
                    </div>
                    <div className="text-right font-mono">
                      <span className="font-semibold">₹{g.grand_total.toLocaleString()}</span>
                      <span className="text-[10px] text-[var(--muted-foreground)] block">({g.lines_count} lines)</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Step 2: Enter Expense Charges */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--primary)] flex items-center gap-1.5">
              <Truck size={14} />
              Step 2: Enter Inbound Indirect Charges
            </h4>
            <button
              type="button"
              onClick={addChargeRow}
              className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-medium"
            >
              <Plus size={13} /> Add Charge Line
            </button>
          </div>

          <div className="space-y-2">
            {charges.map((charge, idx) => (
              <div key={idx} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--muted)]/20 grid grid-cols-1 sm:grid-cols-5 gap-2 items-center text-xs">
                <div>
                  <label className="block text-[10px] text-[var(--muted-foreground)] mb-0.5">Category</label>
                  <select
                    value={charge.charge_type}
                    onChange={(e) => updateCharge(idx, "charge_type", e.target.value)}
                    className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--card)] text-xs"
                  >
                    {CHARGE_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--muted-foreground)] mb-0.5">Carrier / Vendor</label>
                  <input
                    type="text"
                    placeholder="Vendor Name"
                    value={charge.vendor_name || ""}
                    onChange={(e) => updateCharge(idx, "vendor_name", e.target.value)}
                    className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--card)] text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--muted-foreground)] mb-0.5">Invoice / BL #</label>
                  <input
                    type="text"
                    placeholder="BL-90412"
                    value={charge.invoice_ref || ""}
                    onChange={(e) => updateCharge(idx, "invoice_ref", e.target.value)}
                    className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--card)] text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--muted-foreground)] mb-0.5">Amount (₹)</label>
                  <input
                    type="number"
                    value={charge.amount}
                    onChange={(e) => updateCharge(idx, "amount", Number(e.target.value) || 0)}
                    className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--card)] text-xs font-mono font-bold"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <label className="block text-[10px] text-[var(--muted-foreground)] mb-0.5">Apportion By</label>
                    <select
                      value={charge.apportion_by}
                      onChange={(e) => updateCharge(idx, "apportion_by", e.target.value as any)}
                      className="w-full px-2 py-1 rounded border border-[var(--border)] bg-[var(--card)] text-xs"
                    >
                      {APPORTION_METHODS.map((m) => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                  {charges.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeChargeRow(idx)}
                      className="mt-4 p-1 text-rose-500 hover:text-rose-700"
                      title="Remove charge"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-xs font-semibold">
              Total Inbound Charges: ₹{charges.reduce((s, c) => s + (Number(c.amount) || 0), 0).toLocaleString()}
            </span>
            <ActionButton
              tone="primary"
              size="sm"
              onClick={runPreviewCalculate}
              loading={calculating}
              disabled={candidateItems.length === 0 || charges.length === 0}
            >
              Simulate Apportionment
            </ActionButton>
          </div>
        </div>

        {/* Step 3: Simulation Results Preview */}
        {previewCalculation && (
          <div className="space-y-3 pt-3 border-t border-[var(--border)]">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-600 flex items-center gap-1.5">
                <CheckCircle2 size={14} />
                Calculated Landed Cost Impact
              </h4>
              <span className="text-xs font-mono font-semibold text-blue-600">
                Total Capitalized: ₹{previewCalculation.total_charges.toLocaleString()}
              </span>
            </div>

            <div className="max-h-48 overflow-y-auto rounded-xl border border-[var(--border)] overflow-hidden">
              <table className="w-full text-xs text-left">
                <thead className="bg-[var(--muted)]/40 border-b border-[var(--border)] font-semibold">
                  <tr>
                    <th className="py-2 px-3">SKU</th>
                    <th className="py-2 px-3">Qty</th>
                    <th className="py-2 px-3">Base PO Price</th>
                    <th className="py-2 px-3 text-right">Charge Share</th>
                    <th className="py-2 px-3 text-right font-bold text-blue-600">True Landed Cost</th>
                    <th className="py-2 px-3 text-right">Markup %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] font-mono text-[11px]">
                  {previewCalculation.calculated_items.map((itm: any, idx: number) => (
                    <tr key={idx}>
                      <td className="py-2 px-3 font-semibold text-blue-600 font-sans">{itm.sku}</td>
                      <td className="py-2 px-3">{itm.quantity} {itm.uom}</td>
                      <td className="py-2 px-3">₹{Number(itm.base_unit_price).toFixed(2)}</td>
                      <td className="py-2 px-3 text-right text-emerald-600">+₹{Number(itm.allocated_charges).toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-bold text-blue-600 dark:text-blue-400">
                        ₹{Number(itm.final_unit_cost).toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right text-amber-600">+{Number(itm.cost_variance_pct).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Simulated Accounting Entry Preview */}
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs flex items-center justify-between">
              <span>
                <strong>Accounting Impact:</strong> System will debit Inventory Inbound Valuation Asset and credit carrier clearing sub-ledgers.
              </span>
              <span className="font-mono text-[11px] font-bold text-emerald-600">Double-Entry Balanced</span>
            </div>
          </div>
        )}

        <div className="space-y-1">
          <label className="text-xs font-medium text-[var(--muted-foreground)] block">
            Voucher Internal Notes / Audit Remarks
          </label>
          <TextInput
            placeholder="e.g. Inbound customs duty and shipping for import container MSCU-8821"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  );
}
