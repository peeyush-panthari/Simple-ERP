import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  FileText,
  Package,
  Plus,
  RefreshCw,
  RotateCcw,
  Truck,
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

interface CustomerSummary {
  customer_id: string | null;
  customer_name: string;
  open_orders_count: number;
  shipped_orders_count: number;
  total_receivables: number;
  active_rmas_count: number;
}

interface CustomerOrder {
  id: string;
  order_number: string;
  order_date: string | null;
  status: string;
  milestone: string;
  total_amount: number;
  currency: string;
  lines_count: number;
  carrier_name: string;
  tracking_number: string | null;
}

interface CustomerInvoice {
  id: string;
  invoice_number: string;
  order_number: string;
  issue_date: string;
  due_date: string;
  total_amount: number;
  amount_due: number;
  payment_status: string;
  irn_hash: string;
}

interface CustomerRma {
  id: string;
  ticket_number: string;
  customer_party_id: string;
  order_number: string;
  product_id: string;
  sku: string;
  return_qty: number;
  uom: string;
  reason_category: string;
  customer_notes: string;
  status: string;
  carrier_name: string | null;
  return_tracking_awb: string | null;
  resolution_notes: string | null;
  created_at: string;
}

export default function CustomerPortalPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"orders" | "invoices" | "rmas">("orders");
  const [showRmaModal, setShowRmaModal] = useState(false);

  // Form states for creating RMA
  const [orderNumber, setOrderNumber] = useState("");
  const [sku, setSku] = useState("");
  const [returnQty, setReturnQty] = useState("1");
  const [reasonCategory, setReasonCategory] = useState("damaged_in_transit");
  const [customerNotes, setCustomerNotes] = useState("");
  const [carrierName, setCarrierName] = useState("FedEx Express");
  const [trackingAwb, setTrackingAwb] = useState("");

  // 1. Fetch Summary
  const summaryQuery = useQuery({
    queryKey: ["customer-portal-summary"],
    queryFn: () => api<CustomerSummary>("GET", "/api/v1/customer-portal/summary"),
  });
  const summary = summaryQuery.data;

  // 2. Fetch Orders
  const ordersQuery = useQuery({
    queryKey: ["customer-portal-orders"],
    queryFn: () => api<{ orders: CustomerOrder[] }>("GET", "/api/v1/customer-portal/orders"),
  });
  const orders = ordersQuery.data?.orders ?? [];

  // 3. Fetch Invoices
  const invoicesQuery = useQuery({
    queryKey: ["customer-portal-invoices"],
    queryFn: () => api<{ invoices: CustomerInvoice[] }>("GET", "/api/v1/customer-portal/invoices"),
  });
  const invoices = invoicesQuery.data?.invoices ?? [];

  // 4. Fetch RMAs
  const rmasQuery = useQuery({
    queryKey: ["customer-portal-rmas"],
    queryFn: () => api<{ rmas: CustomerRma[] }>("GET", "/api/v1/customer-portal/rmas"),
  });
  const rmas = rmasQuery.data?.rmas ?? [];

  // 5. Fetch Products
  const productsQuery = useQuery({
    queryKey: ["products"],
    queryFn: () => api<{ data: Array<{ id: string; sku: string; name: string }> }>("GET", "/api/v1/products"),
  });
  const products = productsQuery.data?.data ?? [];

  // Handler: Submit RMA
  const handleSubmitRma = async (e: React.FormEvent) => {
    e.preventDefault();
    const prod = products.find((p) => p.sku === sku) || products[0];
    if (!prod) {
      alert("Please select a valid product SKU.");
      return;
    }

    try {
      const res = await api<{ ticket_number: string }>("POST", "/api/v1/customer-portal/rmas", {
        json: {
          order_number: orderNumber || "ORD-2026-001",
          product_id: prod.id,
          sku: prod.sku,
          return_qty: parseFloat(returnQty || "1"),
          uom: "UNIT",
          reason_category: reasonCategory,
          customer_notes: customerNotes || "Customer initiated RMA ticket",
          carrier_name: carrierName,
          return_tracking_awb: trackingAwb,
        },
      });
      setShowRmaModal(false);
      qc.invalidateQueries({ queryKey: ["customer-portal-rmas"] });
      qc.invalidateQueries({ queryKey: ["customer-portal-summary"] });
      alert(`Return Authorization ${res.ticket_number} created successfully.`);
    } catch (err) {
      alert("Failed to submit RMA request: " + err);
    }
  };

  return (
    <Shell>
      <PageHeader
        title={`Customer B2B Portal: ${summary?.customer_name || "Enterprise Account"}`}
        description="Self-service delivery tracking radar, e-Invoice settlements, and customer RMA return authorizations."
        actions={
          <div className="flex gap-2">
            <ActionButton
              tone="primary"
              onClick={() => {
                if (products.length > 0 && !sku) setSku(products[0].sku);
                setShowRmaModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Request Return (RMA)
            </ActionButton>
            <ActionButton
              tone="ghost"
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["customer-portal-summary"] });
                qc.invalidateQueries({ queryKey: ["customer-portal-orders"] });
                qc.invalidateQueries({ queryKey: ["customer-portal-invoices"] });
                qc.invalidateQueries({ queryKey: ["customer-portal-rmas"] });
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
          label="Active Orders in Fulfillment"
          value={summary?.open_orders_count ?? 0}
          hint="Processing or packing"
        />
        <StatCard
          label="Completed Dispatches"
          value={summary?.shipped_orders_count ?? 0}
          hint="Delivered to date"
        />
        <StatCard
          label="Outstanding Balance Due"
          value={money(summary?.total_receivables ?? 0)}
          hint="Pending invoices"
        />
        <StatCard
          label="Active RMA Tickets"
          value={summary?.active_rmas_count ?? 0}
          hint="In review or transit"
        />
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 mb-6 gap-6 text-sm font-medium">
        <button
          type="button"
          onClick={() => setActiveTab("orders")}
          className={`pb-3 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "orders"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Truck className="w-4 h-4" />
          <span>Order Tracking Radar ({orders.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("invoices")}
          className={`pb-3 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "invoices"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Tax Invoices & Statements ({invoices.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("rmas")}
          className={`pb-3 border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "rmas"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <RotateCcw className="w-4 h-4" />
          <span>RMA Returns & Replacements ({rmas.length})</span>
        </button>
      </div>

      {/* TAB 1: Order Tracking Radar */}
      {activeTab === "orders" && (
        <Panel title="Active & Recent Orders Radar">
          <DataTable
            columns={[
              "Order #",
              "Date",
              "Milestone Status",
              "Order Value",
              "Carrier & Tracking",
              "Status",
            ]}
          >
            {orders.map((o) => (
              <TableRow
                key={o.id}
                cells={[
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {o.order_number}
                  </span>,
                  <span className="text-xs text-slate-500">{o.order_date ? formatDate(o.order_date) : "—"}</span>,
                  <div className="flex items-center gap-2 text-xs">
                    <div className="flex items-center gap-1 font-semibold text-primary">
                      <Package className="w-3.5 h-3.5" />
                      <span>{o.milestone}</span>
                    </div>
                  </div>,
                  <span className="font-mono font-semibold text-xs text-slate-900 dark:text-slate-100">
                    {money(o.total_amount)}
                  </span>,
                  <div className="text-xs">
                    <span className="font-medium text-slate-700 dark:text-slate-300">{o.carrier_name}</span>
                    {o.tracking_number && (
                      <div className="text-[10px] font-mono text-primary font-medium">
                        AWB: {o.tracking_number}
                      </div>
                    )}
                  </div>,
                  <Pill
                    tone={
                      o.status === "shipped" || o.status === "fulfilled"
                        ? "success"
                        : o.status === "confirmed" || o.status === "packed"
                        ? "info"
                        : "muted"
                    }
                  >
                    {o.status.toUpperCase()}
                  </Pill>,
                ]}
              />
            ))}
            {orders.length === 0 && (
              <TableRow
                cells={[
                  <div key="empty" className="text-center py-8 text-sm text-slate-400">
                    No sales orders found for this customer account.
                  </div>,
                ]}
              />
            )}
          </DataTable>
        </Panel>
      )}

      {/* TAB 2: Invoices & Statements */}
      {activeTab === "invoices" && (
        <Panel title="Customer Billing Statements & Invoices">
          <DataTable
            columns={[
              "Invoice #",
              "Order Ref",
              "Issue Date",
              "Due Date",
              "Total Amount",
              "Amount Due",
              "Status",
              "Action",
            ]}
          >
            {invoices.map((inv) => (
              <TableRow
                key={inv.id}
                cells={[
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {inv.invoice_number}
                  </span>,
                  <span className="font-mono text-xs">{inv.order_number}</span>,
                  <span className="text-xs text-slate-500">{formatDate(inv.issue_date)}</span>,
                  <span className="text-xs text-slate-500">{formatDate(inv.due_date)}</span>,
                  <span className="font-mono font-semibold text-xs text-slate-900 dark:text-slate-100">
                    {money(inv.total_amount)}
                  </span>,
                  <span className="font-mono font-bold text-xs text-rose-600">
                    {money(inv.amount_due)}
                  </span>,
                  <Pill tone={inv.payment_status === "paid" ? "success" : "warning"}>
                    {inv.payment_status.toUpperCase()}
                  </Pill>,
                  <button
                    type="button"
                    onClick={() => alert(`Downloading statutory e-Invoice PDF for ${inv.invoice_number}`)}
                    className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
                  >
                    <Download className="w-3.5 h-3.5" /> PDF
                  </button>,
                ]}
              />
            ))}
            {invoices.length === 0 && (
              <TableRow
                cells={[
                  <div key="empty" className="text-center py-8 text-sm text-slate-400">
                    No billing statements or invoices found for this account.
                  </div>,
                ]}
              />
            )}
          </DataTable>
        </Panel>
      )}

      {/* TAB 3: RMA Returns */}
      {activeTab === "rmas" && (
        <Panel
          title="Return Material Authorizations (RMA)"
          aside={
            <ActionButton
              tone="primary"
              size="sm"
              onClick={() => {
                if (products.length > 0 && !sku) setSku(products[0].sku);
                setShowRmaModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Request Return
            </ActionButton>
          }
        >
          <DataTable
            columns={[
              "Ticket #",
              "Order Ref",
              "SKU / Item",
              "Return Qty",
              "Reason Category",
              "Carrier / Tracking",
              "Status",
            ]}
          >
            {rmas.map((r) => (
              <TableRow
                key={r.id}
                cells={[
                  <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                    {r.ticket_number}
                  </span>,
                  <span className="font-mono text-xs">{r.order_number}</span>,
                  <span className="font-medium text-xs">{r.sku}</span>,
                  <span className="text-xs font-semibold">
                    {qty(r.return_qty)} {r.uom}
                  </span>,
                  <span className="text-xs text-slate-600 dark:text-slate-400">
                    {r.reason_category.replace(/_/g, " ")}
                  </span>,
                  <div className="text-xs">
                    <div>{r.carrier_name || "Self Courier"}</div>
                    {r.return_tracking_awb && (
                      <span className="font-mono text-[10px] text-primary">{r.return_tracking_awb}</span>
                    )}
                  </div>,
                  <Pill
                    tone={
                      r.status === "approved" || r.status === "credited"
                        ? "success"
                        : r.status === "submitted" || r.status === "under_review"
                        ? "warning"
                        : "muted"
                    }
                  >
                    {r.status.toUpperCase()}
                  </Pill>,
                ]}
              />
            ))}
            {rmas.length === 0 && (
              <TableRow
                cells={[
                  <div key="empty" className="text-center py-8 text-sm text-slate-400">
                    No return tickets on file. Click "Request Return" to submit an RMA.
                  </div>,
                ]}
              />
            )}
          </DataTable>
        </Panel>
      )}

      {/* Modal: Request RMA */}
      <Modal
        open={showRmaModal}
        onClose={() => setShowRmaModal(false)}
        title="Submit Return Authorization (RMA) Request"
      >
        <form onSubmit={handleSubmitRma} className="space-y-4">
          <p className="text-xs text-slate-500">
            Submit a return or warranty replacement ticket for defective, damaged, or misdelivered goods.
          </p>

          <Field label="Original Sales Order #">
            <TextInput
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value)}
              placeholder="e.g. ORD-2026-0042"
              required
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Product Item SKU">
              <select
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
                required
              >
                {products.map((p) => (
                  <option key={p.id} value={p.sku}>
                    {p.sku} - {p.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Return Quantity">
              <TextInput
                type="number"
                min="1"
                step="any"
                value={returnQty}
                onChange={(e) => setReturnQty(e.target.value)}
                required
              />
            </Field>
          </div>

          <Field label="Primary Reason for Return">
            <select
              value={reasonCategory}
              onChange={(e) => setReasonCategory(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
            >
              <option value="damaged_in_transit">Damaged in Transit / Carton Puncture</option>
              <option value="defective_workmanship">Defective Workmanship / Component Failure</option>
              <option value="wrong_item">Wrong Item Delivered</option>
              <option value="excess_delivery">Excess / Unordered Quantity</option>
            </select>
          </Field>

          <Field label="Detailed Defect Description">
            <TextInput
              value={customerNotes}
              onChange={(e) => setCustomerNotes(e.target.value)}
              placeholder="Describe serial number, fault symptom, or packing condition"
              required
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Return Courier Service">
              <TextInput
                value={carrierName}
                onChange={(e) => setCarrierName(e.target.value)}
                placeholder="e.g. FedEx / Blue Dart"
              />
            </Field>

            <Field label="Return Consignment AWB #">
              <TextInput
                value={trackingAwb}
                onChange={(e) => setTrackingAwb(e.target.value)}
                placeholder="e.g. AWB-99882211"
              />
            </Field>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowRmaModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Submit Return Ticket
            </ActionButton>
          </div>
        </form>
      </Modal>
    </Shell>
  );
}
