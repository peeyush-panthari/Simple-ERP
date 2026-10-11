import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  FileCheck2,
  Package,
  Plus,
  Printer,
  Send,
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

interface SubcontractOrderSummary {
  id: string;
  order_no: string;
  vendor_party_id: string;
  vendor_name: string;
  source_warehouse_id: string;
  warehouse_name: string;
  fg_product_id: string;
  fg_sku: string;
  fg_name: string;
  target_qty: number;
  received_qty: number;
  fulfillment_pct: number;
  service_rate: number;
  service_sac_code: string;
  total_service_fee: number;
  expected_delivery_date: string | null;
  status: string;
  challans_count: number;
  receipts_count: number;
  created_at: string | null;
}

interface OrderLineDetail {
  id: string;
  product_id: string;
  sku: string;
  name: string;
  hsn_code: string;
  required_qty: number;
  dispatched_qty: number;
  consumed_qty: number;
  scrap_qty: number;
  vendor_wip_balance: number;
  uom: string;
  estimated_unit_cost: number;
}

interface ChallanSummary {
  id: string;
  challan_no: string;
  challan_date: string;
  statutory_due_date: string;
  days_remaining_statutory: number;
  transport_mode: string;
  vehicle_no: string | null;
  eway_bill_no: string | null;
  total_taxable_value: number;
  total_challan_value: number;
  status: string;
  items_count: number;
}

interface ReceiptSummary {
  id: string;
  receipt_no: string;
  receipt_date: string;
  received_qty: number;
  accepted_qty: number;
  rejected_qty: number;
  actual_scrap_qty: number;
  allowable_scrap_qty: number;
  scrap_variance_qty: number;
  scrap_variance_pct: number;
  service_charges: number;
  vendor_challan_ref: string | null;
  vendor_invoice_no: string | null;
  qc_status: string;
}

interface OrderDetail {
  id: string;
  order_no: string;
  vendor_party_id: string;
  vendor_name: string;
  vendor_tax_id: string;
  principal_entity_name: string;
  principal_tax_id: string;
  source_warehouse_id: string;
  warehouse_name: string;
  fg_product_id: string;
  fg_sku: string;
  fg_name: string;
  target_qty: number;
  received_qty: number;
  balance_fg_qty: number;
  service_rate: number;
  service_sac_code: string;
  expected_delivery_date: string | null;
  status: string;
  notes: string | null;
  lines: OrderLineDetail[];
  challans: ChallanSummary[];
  receipts: ReceiptSummary[];
}

export default function SubcontractingPage() {
  const { api, can } = useAuth();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // Modals
  const [createOrderOpen, setCreateOrderOpen] = useState(false);
  const [issueChallanOpen, setIssueChallanOpen] = useState(false);
  const [recordReceiptOpen, setRecordReceiptOpen] = useState(false);
  const [viewStatutoryChallanId, setViewStatutoryChallanId] = useState<string | null>(null);

  // 1. Fetch Orders
  const { data: orders = [], isLoading: ordersLoading } = useQuery<SubcontractOrderSummary[]>({
    queryKey: ["subcontract-orders", statusFilter],
    queryFn: async () => {
      const qs = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      const res = await api<SubcontractOrderSummary[]>("GET", `/api/v1/subcontracting/orders${qs}`);
      return (res as unknown as { data: SubcontractOrderSummary[] })?.data || res || [];
    },
  });

  // 2. Fetch Selected Order Detail
  const { data: orderDetail } = useQuery<OrderDetail>({
    queryKey: ["subcontract-order-detail", selectedOrderId],
    queryFn: async () => {
      if (!selectedOrderId) return null as unknown as OrderDetail;
      const res = await api<OrderDetail>("GET", `/api/v1/subcontracting/orders/${selectedOrderId}`);
      return (res as unknown as { data: OrderDetail })?.data || res;
    },
    enabled: !!selectedOrderId,
  });

  // 3. Fetch Metadata for dropdowns
  const { data: meta } = useQuery<{
    vendors: { id: string; code: string; name: string; gstin: string }[];
    products: { id: string; sku: string; name: string; uom: string; hsn_code: string; type: string }[];
    warehouses: { id: string; code: string; name: string }[];
    entities: { id: string; name: string; gstin: string }[];
  }>({
    queryKey: ["subcontract-metadata"],
    queryFn: async () => {
      const res = await api<any>("GET", "/api/v1/subcontracting/metadata");
      return (res as any)?.data || res;
    },
  });

  // Filter orders
  const filteredOrders = orders.filter((o) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    return (
      o.order_no.toLowerCase().includes(q) ||
      o.vendor_name.toLowerCase().includes(q) ||
      o.fg_sku.toLowerCase().includes(q) ||
      o.fg_name.toLowerCase().includes(q)
    );
  });

  // KPI Calculations
  const activeOrdersCount = orders.filter((o) => ["confirmed", "dispatched", "partially_received"].includes(o.status)).length;
  const totalChallans = orders.reduce((s, o) => s + o.challans_count, 0);
  const totalReceipts = orders.reduce((s, o) => s + o.receipts_count, 0);
  const completedOrders = orders.filter((o) => o.status === "completed").length;

  return (
    <Shell>
      <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          eyebrow="Manufacturing &amp; Operations"
          title="Subcontracting &amp; Job-Work (Rule 55)"
          description="Manage outsourced job-work manufacturing under CGST Section 143, issue statutory Rule 55 Delivery Challans, track vendor WIP materials, and audit scrap tolerances."
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="primary"
                size="sm"
                onClick={() => setCreateOrderOpen(true)}
                disabled={!can("inventory:write")}
                className="gap-2"
              >
                <Plus size={15} />
                <span>New Job-Work Order</span>
              </ActionButton>
            </div>
          }
        />

        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Active Job Orders"
            value={activeOrdersCount}
            hint="Under vendor processing"
            tone="info"
          />
          <StatCard
            label="Rule 55 Challans"
            value={totalChallans}
            hint="Dispatched to Job Workers"
            tone="muted"
          />
          <StatCard
            label="FG Goods Receipts"
            value={totalReceipts}
            hint="SCR receipts from vendors"
            tone="muted"
          />
          <StatCard
            label="Orders Completed"
            value={completedOrders}
            hint="Fully received &amp; reconciled"
            tone="success"
          />
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-[var(--muted-foreground)]">Status:</span>
            {["all", "confirmed", "dispatched", "partially_received", "completed"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={cn(
                  "px-3 py-1 text-xs rounded-lg font-medium transition-colors",
                  statusFilter === st
                    ? "bg-blue-600 text-white font-semibold"
                    : "bg-[var(--secondary)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                {st === "all" ? "All Orders" : st.replace("_", " ").toUpperCase()}
              </button>
            ))}
          </div>

          <TextInput
            placeholder="Search Order #, Vendor, SKU..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full sm:w-64 text-xs"
          />
        </div>

        {/* Orders Table */}
        <Panel
          title="Job-Work Orders"
          subtitle={`${filteredOrders.length} subcontract manufacturing orders`}
        >
          {ordersLoading ? (
            <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
              Loading subcontract orders…
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="py-12 text-center text-xs text-[var(--muted-foreground)] space-y-3">
              <Package size={28} className="mx-auto text-[var(--muted-foreground)] opacity-50" />
              <p>No subcontract orders found matching the filter criteria.</p>
              <ActionButton size="sm" tone="primary" onClick={() => setCreateOrderOpen(true)}>
                Create First Subcontract Order
              </ActionButton>
            </div>
          ) : (
            <DataTable
              columns={[
                "Order #",
                "Job Worker (Vendor)",
                "Finished Good Item",
                "Target Qty",
                "Progress / Fulfillment",
                "Service Rate",
                "Status",
                "Action",
              ]}
            >
              {filteredOrders.map((o) => {
                const isSelected = selectedOrderId === o.id;
                return (
                  <TableRow
                    key={o.id}
                    selected={isSelected}
                    onClick={() => setSelectedOrderId(o.id)}
                    cells={[
                      <span className="font-semibold text-xs text-blue-600 dark:text-blue-400">
                        {o.order_no}
                      </span>,
                      <div>
                        <div className="font-medium text-xs text-[var(--foreground)]">{o.vendor_name}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)]">{o.warehouse_name}</div>
                      </div>,
                      <div>
                        <div className="font-semibold text-xs text-[var(--foreground)]">{o.fg_sku}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)] truncate max-w-[200px]">
                          {o.fg_name}
                        </div>
                      </div>,
                      <span className="text-xs font-semibold">{o.target_qty} units</span>,
                      <div className="w-36 space-y-1">
                        <div className="flex justify-between text-[11px]">
                          <span>
                            {o.received_qty} / {o.target_qty}
                          </span>
                          <span className="font-semibold">{o.fulfillment_pct}%</span>
                        </div>
                        <div className="w-full bg-[var(--border)] rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-emerald-500 h-1.5 rounded-full transition-all"
                            style={{ width: `${Math.min(o.fulfillment_pct, 100)}%` }}
                          />
                        </div>
                      </div>,
                      <div className="text-xs font-mono">
                        ₹{o.service_rate.toFixed(2)}/u
                        <div className="text-[10px] text-[var(--muted-foreground)]">
                          SAC {o.service_sac_code}
                        </div>
                      </div>,
                      <Pill
                        tone={
                          o.status === "completed"
                            ? "success"
                            : o.status === "dispatched" || o.status === "partially_received"
                            ? "warning"
                            : "info"
                        }
                      >
                        {o.status.replace("_", " ").toUpperCase()}
                      </Pill>,
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <ActionButton
                          size="sm"
                          tone="ghost"
                          onClick={() => setSelectedOrderId(o.id)}
                          className="text-[11px]"
                        >
                          Inspect
                        </ActionButton>
                        {o.status !== "completed" && (
                          <ActionButton
                            size="sm"
                            tone="primary"
                            onClick={() => {
                              setSelectedOrderId(o.id);
                              setIssueChallanOpen(true);
                            }}
                            className="text-[11px]"
                          >
                            Challan
                          </ActionButton>
                        )}
                      </div>,
                    ]}
                  />
                );
              })}
            </DataTable>
          )}
        </Panel>

        {/* Selected Order Detail Drawer / Section */}
        {selectedOrderId && orderDetail && (
          <div className="space-y-6 pt-4 border-t border-[var(--border)]">
            <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-xs">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold text-[var(--foreground)]">
                    {orderDetail.order_no} &mdash; {orderDetail.fg_sku} ({orderDetail.fg_name})
                  </h2>
                  <Pill tone={orderDetail.status === "completed" ? "success" : "warning"}>
                    {orderDetail.status.toUpperCase()}
                  </Pill>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  Job Worker: <strong className="text-[var(--foreground)]">{orderDetail.vendor_name}</strong> (GSTIN: {orderDetail.vendor_tax_id}) &bull; Warehouse: {orderDetail.warehouse_name}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <ActionButton
                  size="sm"
                  tone="ghost"
                  onClick={() => setIssueChallanOpen(true)}
                  className="gap-1.5"
                >
                  <Send size={14} />
                  <span>Dispatch Materials (Rule 55)</span>
                </ActionButton>
                <ActionButton
                  size="sm"
                  tone="primary"
                  onClick={() => setRecordReceiptOpen(true)}
                  className="gap-1.5"
                >
                  <CheckCircle2 size={14} />
                  <span>Receive Finished Goods (SCR)</span>
                </ActionButton>
              </div>
            </div>

            {/* Grid of Order Details */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 1. Raw Materials & Vendor WIP Tracking */}
              <div className="lg:col-span-2 space-y-4">
                <Panel
                  title="Bill of Materials &amp; Vendor WIP Stock"
                  subtitle="Tracks material issued to job worker, consumed in FG, and remaining WIP balance"
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-[var(--muted-foreground)] text-left">
                          <th className="pb-2 font-semibold">Material SKU</th>
                          <th className="pb-2 font-semibold">HSN</th>
                          <th className="pb-2 font-semibold">Required</th>
                          <th className="pb-2 font-semibold">Dispatched</th>
                          <th className="pb-2 font-semibold">Consumed</th>
                          <th className="pb-2 font-semibold">Scrap</th>
                          <th className="pb-2 font-semibold text-right">Vendor WIP Balance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {orderDetail.lines.map((l) => (
                          <tr key={l.id} className="hover:bg-[var(--secondary)]/30">
                            <td className="py-2.5 font-medium">
                              <div>{l.sku}</div>
                              <div className="text-[10px] text-[var(--muted-foreground)] truncate max-w-[160px]">{l.name}</div>
                            </td>
                            <td className="py-2.5 font-mono text-[11px] text-[var(--muted-foreground)]">
                              {l.hsn_code || "7204"}
                            </td>
                            <td className="py-2.5 font-medium">{l.required_qty} {l.uom}</td>
                            <td className="py-2.5 text-blue-600 font-semibold">{l.dispatched_qty} {l.uom}</td>
                            <td className="py-2.5 text-emerald-600">{l.consumed_qty} {l.uom}</td>
                            <td className="py-2.5 text-amber-600">{l.scrap_qty} {l.uom}</td>
                            <td className="py-2.5 font-bold text-right font-mono">
                              <span
                                className={cn(
                                  "px-2 py-0.5 rounded text-[11px]",
                                  l.vendor_wip_balance > 0
                                    ? "bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300"
                                    : "bg-gray-100 dark:bg-gray-800 text-[var(--muted-foreground)]"
                                )}
                              >
                                {l.vendor_wip_balance} {l.uom}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>

                {/* 2. Rule 55 Delivery Challans */}
                <Panel
                  title="Rule 55 Delivery Challans (Section 143)"
                  subtitle="Statutory transit challans with 1-year return period monitoring"
                >
                  {orderDetail.challans.length === 0 ? (
                    <div className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                      No delivery challans issued yet for this order.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {orderDetail.challans.map((ch) => (
                        <div
                          key={ch.id}
                          className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--background)] flex flex-wrap items-center justify-between gap-4"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs text-blue-600">{ch.challan_no}</span>
                              <span className="text-[10px] text-[var(--muted-foreground)] font-mono">
                                Date: {formatDate(ch.challan_date)}
                              </span>
                              <Pill tone="info">{ch.transport_mode}</Pill>
                            </div>
                            <div className="text-[11px] text-[var(--muted-foreground)] flex items-center gap-3">
                              <span>Vehicle: {ch.vehicle_no || "N/A"}</span>
                              {ch.eway_bill_no && <span>E-Way: {ch.eway_bill_no}</span>}
                              <span>Value: {money(ch.total_challan_value)}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            {/* Statutory 1-Year Return Timer Alert */}
                            <div className="text-right">
                              <div className="text-[10px] text-[var(--muted-foreground)]">Section 143(1)(a) Due:</div>
                              <div
                                className={cn(
                                  "text-xs font-bold",
                                  ch.days_remaining_statutory < 60 ? "text-rose-600" : "text-emerald-600"
                                )}
                              >
                                {formatDate(ch.statutory_due_date)} ({ch.days_remaining_statutory}d left)
                              </div>
                            </div>

                            <ActionButton
                              size="sm"
                              tone="ghost"
                              onClick={() => setViewStatutoryChallanId(ch.id)}
                              className="gap-1.5 text-xs"
                            >
                              <FileCheck2 size={14} />
                              <span>View Rule 55 Challan</span>
                            </ActionButton>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>
              </div>

              {/* 3. Receipts & Scrap Audit Summary */}
              <div className="space-y-4">
                <Panel
                  title="Receipts &amp; Scrap Reconciliation"
                  subtitle="Scrap generation vs BOM tolerance (5%)"
                >
                  {orderDetail.receipts.length === 0 ? (
                    <div className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                      No finished goods received back yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {orderDetail.receipts.map((rc) => (
                        <div
                          key={rc.id}
                          className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--background)] space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-xs text-[var(--foreground)]">{rc.receipt_no}</span>
                            <span className="text-[10px] text-[var(--muted-foreground)]">
                              {formatDate(rc.receipt_date)}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-[var(--border)]">
                            <div>
                              <span className="text-[var(--muted-foreground)]">Accepted FG:</span>{" "}
                              <strong className="text-emerald-600">{rc.accepted_qty} units</strong>
                            </div>
                            <div>
                              <span className="text-[var(--muted-foreground)]">Service Fee:</span>{" "}
                              <strong>{money(rc.service_charges)}</strong>
                            </div>
                          </div>

                          <div className="p-2 rounded-lg bg-[var(--secondary)]/50 space-y-1 text-[11px]">
                            <div className="flex justify-between">
                              <span className="text-[var(--muted-foreground)]">Actual Scrap:</span>
                              <span>{rc.actual_scrap_qty} kg</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[var(--muted-foreground)]">Allowable (5%):</span>
                              <span>{rc.allowable_scrap_qty} kg</span>
                            </div>
                            <div className="flex justify-between font-semibold pt-1 border-t border-[var(--border)]">
                              <span>Variance:</span>
                              <span
                                className={cn(
                                  rc.scrap_variance_qty > 0 ? "text-rose-600" : "text-emerald-600"
                                )}
                              >
                                {rc.scrap_variance_qty > 0 ? `+${rc.scrap_variance_qty}` : rc.scrap_variance_qty} kg ({rc.scrap_variance_pct}%)
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>
              </div>
            </div>
          </div>
        )}

        {/* Modal 1: Create New Subcontract Order */}
        {createOrderOpen && (
          <CreateOrderModal
            meta={meta}
            onClose={() => setCreateOrderOpen(false)}
            onSuccess={() => {
              setCreateOrderOpen(false);
              queryClient.invalidateQueries({ queryKey: ["subcontract-orders"] });
            }}
          />
        )}

        {/* Modal 2: Issue Delivery Challan (Rule 55) */}
        {issueChallanOpen && orderDetail && (
          <IssueChallanModal
            order={orderDetail}
            onClose={() => setIssueChallanOpen(false)}
            onSuccess={() => {
              setIssueChallanOpen(false);
              queryClient.invalidateQueries({ queryKey: ["subcontract-orders"] });
              queryClient.invalidateQueries({ queryKey: ["subcontract-order-detail", selectedOrderId] });
            }}
          />
        )}

        {/* Modal 3: Record Goods Receipt (SCR) */}
        {recordReceiptOpen && orderDetail && (
          <RecordReceiptModal
            order={orderDetail}
            onClose={() => setRecordReceiptOpen(false)}
            onSuccess={() => {
              setRecordReceiptOpen(false);
              queryClient.invalidateQueries({ queryKey: ["subcontract-orders"] });
              queryClient.invalidateQueries({ queryKey: ["subcontract-order-detail", selectedOrderId] });
            }}
          />
        )}

        {/* Modal 4: Statutory Indian GST Rule 55 Printable Challan View */}
        {viewStatutoryChallanId && (
          <StatutoryChallanViewModal
            challanId={viewStatutoryChallanId}
            onClose={() => setViewStatutoryChallanId(null)}
          />
        )}
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal 1: Create Order
// ------------------------------------------------------------------------------------------------
function CreateOrderModal({
  meta,
  onClose,
  onSuccess,
}: {
  meta?: any;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const [vendorId, setVendorId] = useState("");
  const [fgProductId, setFgProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [targetQty, setTargetQty] = useState("100");
  const [serviceRate, setServiceRate] = useState("25.00");
  const [deliveryDate, setDeliveryDate] = useState(
    new Date(Date.now() + 14 * 86400000).toISOString().split("T")[0]
  );
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("POST", "/api/v1/subcontracting/orders", {
        json: {
          vendor_party_id: vendorId || meta?.vendors[0]?.id,
          fg_product_id: fgProductId || meta?.products[0]?.id,
          source_warehouse_id: warehouseId || meta?.warehouses[0]?.id,
          target_qty: parseFloat(targetQty),
          service_rate: parseFloat(serviceRate),
          expected_delivery_date: deliveryDate,
          notes,
        },
      });
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to create subcontract order");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Create Subcontract Job-Work Order"
      description="Issue job-work instruction to vendor with BOM auto-decomposition."
      wide
      footer={
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton tone="primary" size="sm" loading={submitting} onClick={handleSubmit}>
            Create Order &amp; Link BOM
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block font-semibold mb-1">Job Worker (Vendor):</label>
            <select
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {meta?.vendors.map((v: any) => (
                <option key={v.id} value={v.id}>
                  {v.name} (GSTIN: {v.gstin})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold mb-1">Finished Good Product (Output):</label>
            <select
              value={fgProductId}
              onChange={(e) => setFgProductId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {meta?.products.map((p: any) => (
                <option key={p.id} value={p.id}>
                  {p.sku} &mdash; {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block font-semibold mb-1">Source Principal Warehouse:</label>
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)]"
              required
            >
              {meta?.warehouses.map((w: any) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold mb-1">Target Quantity:</label>
            <TextInput
              type="number"
              value={targetQty}
              onChange={(e) => setTargetQty(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Job-Work Service Rate (₹/unit):</label>
            <TextInput
              type="number"
              step="0.01"
              value={serviceRate}
              onChange={(e) => setServiceRate(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block font-semibold mb-1">Expected Delivery Date:</label>
            <TextInput
              type="date"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Processing Instructions / Notes:</label>
            <TextInput
              placeholder="e.g. Zinc electroplating as per IS 3618 grade 2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal 2: Issue Delivery Challan (CGST Rule 55)
// ------------------------------------------------------------------------------------------------
function IssueChallanModal({
  order,
  onClose,
  onSuccess,
}: {
  order: OrderDetail;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const [vehicleNo, setVehicleNo] = useState("MH-14-GH-4921");
  const [transporter, setTransporter] = useState("VRL Logistics");
  const [ewayBill, setEwayBill] = useState("241094829103");
  const [processing, setProcessing] = useState("Machining, heat treatment & rust prevention coating");
  const [dispatchQtys, setDispatchQtys] = useState<Record<string, number>>(
    Object.fromEntries(order.lines.map((l) => [l.product_id, l.required_qty]))
  );
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const items = order.lines.map((l) => ({
        product_id: l.product_id,
        sku: l.sku,
        description: l.name,
        hsn_code: l.hsn_code || "7204",
        quantity: dispatchQtys[l.product_id] || l.required_qty,
        uom: l.uom,
        taxable_rate: l.estimated_unit_cost || 120,
        gst_rate_pct: 18.0,
      }));

      await api("POST", `/api/v1/subcontracting/orders/${order.id}/challans`, {
        json: {
          items,
          vehicle_no: vehicleNo,
          transporter_name: transporter,
          eway_bill_no: ewayBill,
          nature_of_processing: processing,
        },
      });
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to generate delivery challan");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Issue Rule 55 Delivery Challan (Job-Work Dispatch)"
      description={`Dispatches raw materials to ${order.vendor_name} under CGST Section 143.`}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton tone="primary" size="sm" loading={submitting} onClick={handleSubmit}>
            Generate &amp; Dispatch Challan
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)]">
          <div>
            <label className="block font-semibold mb-1">Vehicle Number:</label>
            <TextInput
              value={vehicleNo}
              onChange={(e) => setVehicleNo(e.target.value)}
              placeholder="e.g. MH-12-AB-1234"
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Transporter Name:</label>
            <TextInput
              value={transporter}
              onChange={(e) => setTransporter(e.target.value)}
              placeholder="e.g. SafeXpress"
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">E-Way Bill Number:</label>
            <TextInput
              value={ewayBill}
              onChange={(e) => setEwayBill(e.target.value)}
              placeholder="12-digit E-way bill number"
            />
          </div>
        </div>

        <div>
          <label className="block font-semibold mb-1">Nature of Processing at Job-Worker:</label>
          <TextInput
            value={processing}
            onChange={(e) => setProcessing(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Raw Materials to Dispatch:</label>
          <div className="border border-[var(--border)] rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-[var(--secondary)] text-[var(--muted-foreground)]">
                <tr>
                  <th className="p-2 text-left">SKU &amp; Description</th>
                  <th className="p-2 text-left">HSN</th>
                  <th className="p-2 text-left">Req. Qty</th>
                  <th className="p-2 text-left">Dispatch Qty</th>
                  <th className="p-2 text-left">UOM</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {order.lines.map((l) => (
                  <tr key={l.id}>
                    <td className="p-2 font-medium">
                      <div>{l.sku}</div>
                      <div className="text-[10px] text-[var(--muted-foreground)]">{l.name}</div>
                    </td>
                    <td className="p-2 font-mono">{l.hsn_code || "7204"}</td>
                    <td className="p-2">{l.required_qty}</td>
                    <td className="p-2 w-32">
                      <TextInput
                        type="number"
                        value={dispatchQtys[l.product_id] ?? l.required_qty}
                        onChange={(e) =>
                          setDispatchQtys({
                            ...dispatchQtys,
                            [l.product_id]: parseFloat(e.target.value) || 0,
                          })
                        }
                      />
                    </td>
                    <td className="p-2 text-[var(--muted-foreground)]">{l.uom}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal 3: Record Goods Receipt (SCR)
// ------------------------------------------------------------------------------------------------
function RecordReceiptModal({
  order,
  onClose,
  onSuccess,
}: {
  order: OrderDetail;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { api } = useAuth();
  const balanceFg = Math.max(0, order.target_qty - order.received_qty);

  const [receivedQty, setReceivedQty] = useState(balanceFg.toString());
  const [acceptedQty, setAcceptedQty] = useState(balanceFg.toString());
  const [consumedRm, setConsumedRm] = useState(balanceFg.toString());
  const [actualScrap, setActualScrap] = useState("4.5");
  const [allowedScrapPct, setAllowedScrapPct] = useState("5.0");
  const [vendorChallan, setVendorChallan] = useState("JW-INV-9921");
  const [submitting, setSubmitting] = useState(false);

  // Live scrap variance calculation
  const rec = parseFloat(receivedQty) || 0;
  const acc = parseFloat(acceptedQty) || 0;
  const cRm = parseFloat(consumedRm) || 0;
  const actScrap = parseFloat(actualScrap) || 0;
  const allowPct = parseFloat(allowedScrapPct) || 5;

  const allowableScrap = (cRm * allowPct) / 100;
  const scrapVariance = actScrap - allowableScrap;
  const serviceFee = acc * order.service_rate;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("POST", `/api/v1/subcontracting/orders/${order.id}/receipts`, {
        json: {
          received_qty: rec,
          accepted_qty: acc,
          consumed_raw_material_qty: cRm,
          actual_scrap_qty: actScrap,
          allowed_scrap_pct: allowPct,
          vendor_challan_ref: vendorChallan,
          vendor_invoice_no: vendorChallan,
        },
      });
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to record goods receipt");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Record Job-Work Goods Receipt (SCR)"
      description={`Receives finished ${order.fg_sku} back from ${order.vendor_name}.`}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" size="sm" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton tone="primary" size="sm" loading={submitting} onClick={handleSubmit}>
            Confirm Receipt &amp; Post Ledger
          </ActionButton>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block font-semibold mb-1">Received FG Qty:</label>
            <TextInput
              type="number"
              value={receivedQty}
              onChange={(e) => {
                setReceivedQty(e.target.value);
                setAcceptedQty(e.target.value);
                setConsumedRm(e.target.value);
              }}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Accepted FG Qty (Post-QC):</label>
            <TextInput
              type="number"
              value={acceptedQty}
              onChange={(e) => setAcceptedQty(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block font-semibold mb-1">Vendor Invoice / DC Ref:</label>
            <TextInput
              value={vendorChallan}
              onChange={(e) => setVendorChallan(e.target.value)}
            />
          </div>
        </div>

        {/* Scrap Reconciliation Box */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--secondary)]/40 space-y-3">
          <div className="flex items-center justify-between font-semibold">
            <span>Material Consumption &amp; Scrap Audit</span>
            <span className="text-[11px] text-[var(--muted-foreground)]">
              Service Fee: {money(serviceFee)}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold mb-1">Raw Material Consumed:</label>
              <TextInput
                type="number"
                value={consumedRm}
                onChange={(e) => setConsumedRm(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-semibold mb-1">Actual Scrap Returned (kg):</label>
              <TextInput
                type="number"
                step="0.01"
                value={actualScrap}
                onChange={(e) => setActualScrap(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-semibold mb-1">BOM Allowed Scrap (%):</label>
              <TextInput
                type="number"
                step="0.1"
                value={allowedScrapPct}
                onChange={(e) => setAllowedScrapPct(e.target.value)}
              />
            </div>
          </div>

          <div className="p-3 rounded-lg bg-[var(--card)] border border-[var(--border)] flex items-center justify-between">
            <span className="text-[var(--muted-foreground)]">
              Allowable Scrap: <strong>{allowableScrap.toFixed(2)} kg</strong>
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[var(--muted-foreground)]">Scrap Variance:</span>
              <span
                className={cn(
                  "font-bold px-2 py-0.5 rounded",
                  scrapVariance > 0
                    ? "bg-rose-100 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300"
                    : "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300"
                )}
              >
                {scrapVariance > 0 ? `+${scrapVariance.toFixed(2)} kg (Overrun)` : `${scrapVariance.toFixed(2)} kg (Within Limit)`}
              </span>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------------------------------------
// Sub-Modal 4: Statutory Indian GST Rule 55 Delivery Challan Printable Layout
// ------------------------------------------------------------------------------------------------
function StatutoryChallanViewModal({
  challanId,
  onClose,
}: {
  challanId: string;
  onClose: () => void;
}) {
  const { api } = useAuth();
  const { data: doc, isLoading } = useQuery<any>({
    queryKey: ["statutory-challan", challanId],
    queryFn: async () => {
      const res = await api<any>("GET", `/api/v1/subcontracting/challans/${challanId}/statutory`);
      return (res as any)?.data || res;
    },
  });

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Statutory Delivery Challan (CGST Rule 55)"
      description="Official statutory layout under Section 143 of CGST Act, 2017 for Job-Work movements."
      wide
      footer={
        <div className="flex justify-between w-full">
          <ActionButton tone="ghost" size="sm" onClick={() => window.print()} className="gap-2">
            <Printer size={15} />
            <span>Print Challan</span>
          </ActionButton>
          <ActionButton tone="primary" size="sm" onClick={onClose}>
            Close
          </ActionButton>
        </div>
      }
    >
      {isLoading || !doc ? (
        <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
          Generating Rule 55 statutory document…
        </div>
      ) : (
        <div className="p-6 border border-gray-300 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 space-y-6 print:p-0 print:border-none">
          {/* Statutory Header */}
          <div className="text-center border-b pb-4 border-gray-200 dark:border-gray-800 space-y-1">
            <h1 className="text-base font-extrabold tracking-wider uppercase">
              DELIVERY CHALLAN FOR JOB-WORK
            </h1>
            <p className="text-[11px] font-semibold text-gray-500">
              [Issued under Section 143 of CGST Act, 2017 read with Rule 55 of CGST Rules, 2017]
            </p>
            <p className="text-[11px] font-medium text-emerald-600">
              SUPPLY ON RETURNABLE BASIS &bull; NOT FOR SALE
            </p>
          </div>

          {/* Document Reference Info */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="space-y-1">
              <div>
                <span className="font-semibold text-gray-500">Challan No:</span>{" "}
                <strong className="font-mono text-sm">{doc.challan_no}</strong>
              </div>
              <div>
                <span className="font-semibold text-gray-500">Challan Date:</span>{" "}
                <strong>{doc.challan_date}</strong>
              </div>
              <div>
                <span className="font-semibold text-gray-500">Subcontract Order:</span>{" "}
                <strong>{doc.order_no}</strong>
              </div>
            </div>

            <div className="space-y-1 text-right">
              <div>
                <span className="font-semibold text-gray-500">Statutory Return Due Date:</span>{" "}
                <strong className="text-rose-600 font-mono">{doc.statutory_due_date}</strong>
              </div>
              <div>
                <span className="font-semibold text-gray-500">Statutory Law:</span>{" "}
                <span>Section 143(1)(a) (1-Year Rule)</span>
              </div>
              <div>
                <span className="font-semibold text-gray-500">Mode of Transport:</span>{" "}
                <span>{doc.transport.mode} ({doc.transport.vehicle_no})</span>
              </div>
            </div>
          </div>

          {/* Consignor & Consignee 2-Column Box */}
          <div className="grid grid-cols-2 gap-4 p-3 rounded-lg border border-gray-200 dark:border-gray-800 text-xs bg-gray-50 dark:bg-gray-800/50">
            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-blue-600">
                Consignor (Principal / Sender)
              </span>
              <p className="font-bold">{doc.consignor.name}</p>
              <p className="text-gray-600 dark:text-gray-300">{doc.consignor.address}</p>
              <p className="font-mono">
                <strong>GSTIN:</strong> {doc.consignor.gstin}
              </p>
              <p>
                <strong>State:</strong> {doc.consignor.state} (Code: {doc.consignor.state_code})
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-blue-600">
                Consignee (Job-Worker / Receiver)
              </span>
              <p className="font-bold">{doc.consignee.name}</p>
              <p className="text-gray-600 dark:text-gray-300">{doc.consignee.address}</p>
              <p className="font-mono">
                <strong>GSTIN:</strong> {doc.consignee.gstin}
              </p>
              <p>
                <strong>State:</strong> {doc.consignee.state} (Code: {doc.consignee.state_code})
              </p>
            </div>
          </div>

          {/* Logistics Particulars */}
          <div className="grid grid-cols-3 gap-2 p-2.5 rounded-lg border border-gray-200 dark:border-gray-800 text-[11px]">
            <div>
              <span className="text-gray-500">Place of Supply:</span>{" "}
              <strong>{doc.place_of_supply}</strong>
            </div>
            <div>
              <span className="text-gray-500">Transporter:</span>{" "}
              <strong>{doc.transport.transporter}</strong>
            </div>
            <div>
              <span className="text-gray-500">E-Way Bill No:</span>{" "}
              <strong className="font-mono">{doc.transport.eway_bill_no}</strong>
            </div>
          </div>

          {/* Statutory Goods Table */}
          <div className="border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-800 font-semibold text-gray-600 dark:text-gray-300">
                <tr>
                  <th className="p-2">#</th>
                  <th className="p-2">Description of Goods</th>
                  <th className="p-2">HSN Code</th>
                  <th className="p-2">Qty</th>
                  <th className="p-2">Taxable Rate</th>
                  <th className="p-2">Taxable Value</th>
                  <th className="p-2">CGST</th>
                  <th className="p-2">SGST</th>
                  <th className="p-2 text-right">Total (₹)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:border-gray-800">
                {doc.items.map((it: any) => (
                  <tr key={it.line_no}>
                    <td className="p-2">{it.line_no}</td>
                    <td className="p-2 font-medium">
                      {it.sku} &mdash; {it.description}
                    </td>
                    <td className="p-2 font-mono">{it.hsn_code}</td>
                    <td className="p-2 font-semibold">
                      {it.quantity} {it.uom}
                    </td>
                    <td className="p-2 font-mono">₹{it.taxable_rate.toFixed(2)}</td>
                    <td className="p-2 font-mono font-semibold">₹{it.taxable_value.toFixed(2)}</td>
                    <td className="p-2 font-mono text-[11px]">₹{it.cgst_amount.toFixed(2)}</td>
                    <td className="p-2 font-mono text-[11px]">₹{it.sgst_amount.toFixed(2)}</td>
                    <td className="p-2 font-mono font-bold text-right">
                      ₹{(it.taxable_value + it.cgst_amount + it.sgst_amount).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50 dark:bg-gray-800 font-semibold border-t border-gray-200 dark:border-gray-800 text-xs">
                <tr>
                  <td colSpan={5} className="p-2 text-right">Total Consignment Valuation:</td>
                  <td className="p-2 font-mono font-bold">₹{doc.totals.taxable_value.toFixed(2)}</td>
                  <td className="p-2 font-mono">₹{doc.totals.cgst_amount.toFixed(2)}</td>
                  <td className="p-2 font-mono">₹{doc.totals.sgst_amount.toFixed(2)}</td>
                  <td className="p-2 font-mono font-bold text-right text-sm">
                    ₹{doc.totals.total_challan_value.toFixed(2)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Statutory Declaration & Signatory */}
          <div className="grid grid-cols-3 gap-6 pt-2 text-[11px]">
            <div className="col-span-2 space-y-2 text-gray-500">
              <p className="font-semibold text-gray-700 dark:text-gray-300">
                Statutory Declaration under Rule 55:
              </p>
              <p className="italic leading-relaxed border-l-2 border-blue-500 pl-3">
                "{doc.statutory_declaration}"
              </p>
              <p>
                <strong>Nature of Processing:</strong> {doc.nature_of_processing}
              </p>
            </div>

            <div className="text-center pt-8 border-t border-gray-300 dark:border-gray-700 flex flex-col justify-end">
              <p className="font-semibold">For {doc.consignor.name}</p>
              <div className="h-12" />
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                Authorized Signatory
              </p>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
