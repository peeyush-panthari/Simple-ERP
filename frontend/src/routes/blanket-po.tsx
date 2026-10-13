import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileSpreadsheet,
  FileText,
  Plus,
  RefreshCw,
  Send,
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

interface BlanketPoRecord {
  id: string;
  bpa_number: string;
  vendor_name: string;
  vendor_id: string;
  start_date: string;
  end_date: string;
  currency: string;
  target_amount: number;
  released_amount: number;
  utilization_pct: number;
  status: string;
  lines_count: number;
  created_at: string;
}

interface BlanketPoLine {
  id: string;
  product_id: string;
  sku: string;
  name: string;
  agreed_rate: number;
  committed_qty: number;
  released_qty: number;
  remaining_qty: number;
  uom: string;
}

interface BlanketPoDetail {
  bpa: {
    id: string;
    bpa_number: string;
    vendor_name: string;
    vendor_id: string;
    start_date: string;
    end_date: string;
    currency: string;
    target_amount: number;
    released_amount: number;
    status: string;
    payment_terms: string | null;
    notes: string | null;
  };
  lines: BlanketPoLine[];
}

export default function BlanketPoPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [selectedBpaId, setSelectedBpaId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showReleaseModal, setShowReleaseModal] = useState(false);

  // Form states for creating BPA
  const [vendorId, setVendorId] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [endDate, setEndDate] = useState(new Date(Date.now() + 86400000 * 365).toISOString().split("T")[0]);
  const [targetAmount, setTargetAmount] = useState("500000");
  const [paymentTerms, setPaymentTerms] = useState("Net 45 Days");
  const [notes, setNotes] = useState("");

  // Product line builder
  const [productId, setProductId] = useState("");
  const [agreedRate, setAgreedRate] = useState("280");
  const [committedQty, setCommittedQty] = useState("1000");

  // Release form states
  const [releaseWhId, setReleaseWhId] = useState("");
  const [expectedDate, setExpectedDate] = useState(new Date(Date.now() + 86400000 * 14).toISOString().split("T")[0]);
  const [releaseQtys, setReleaseQtys] = useState<Record<string, string>>({});

  // 1. Fetch BPAs
  const bpasQuery = useQuery({
    queryKey: ["blanket-pos"],
    queryFn: () => api<{ blanket_pos: BlanketPoRecord[] }>("GET", "/api/v1/blanket-pos"),
  });

  // 2. Fetch Vendors for dropdown
  const vendorsQuery = useQuery({
    queryKey: ["vendor-parties"],
    queryFn: async () => {
      const res = await api<any>("GET", "/api/v1/parties?type=vendor&limit=100");
      return Array.isArray(res) ? res : res?.data || [];
    },
  });

  // 3. Fetch Products for line item dropdown
  const productsQuery = useQuery({
    queryKey: ["bpa-products"],
    queryFn: async () => {
      const res = await api<any>("GET", "/api/v1/products?limit=200");
      return Array.isArray(res) ? res : res?.data || [];
    },
  });

  // 4. Fetch Warehouses for release
  const warehousesQuery = useQuery({
    queryKey: ["bpa-warehouses"],
    queryFn: async () => {
      const res = await api<any>("GET", "/api/v1/wms-bins/warehouses");
      return Array.isArray(res) ? res : res?.data || res?.warehouses || [];
    },
  });

  // 5. Fetch BPA Detail
  const detailQuery = useQuery({
    queryKey: ["blanket-po-detail", selectedBpaId],
    queryFn: () => api<BlanketPoDetail>("GET", `/api/v1/blanket-pos/${selectedBpaId}`),
    enabled: !!selectedBpaId,
  });

  const bpas = Array.isArray(bpasQuery.data?.blanket_pos) ? bpasQuery.data.blanket_pos : [];
  const vendors: Array<{ id: string; display_name?: string; code?: string; legalName?: string; name?: string }> = Array.isArray(vendorsQuery.data) ? vendorsQuery.data : [];
  const products: Array<{ id: string; sku: string; name?: string }> = Array.isArray(productsQuery.data) ? productsQuery.data : [];
  const warehouses: Array<{ id: string; name: string; code: string }> = Array.isArray(warehousesQuery.data) ? warehousesQuery.data : [];
  const currentBpa = detailQuery.data?.bpa;
  const currentLines = Array.isArray(detailQuery.data?.lines) ? detailQuery.data.lines : [];

  // Summary Metrics
  const totalContractedVal = bpas.reduce((acc, b) => acc + b.target_amount, 0);
  const totalReleasedVal = bpas.reduce((acc, b) => acc + b.released_amount, 0);
  const overallUtilization = totalContractedVal > 0 ? Math.round((totalReleasedVal / totalContractedVal) * 100) : 0;

  // Handler: Create BPA
  const handleCreateBpa = async (e: React.FormEvent) => {
    e.preventDefault();
    const vId = vendorId || (vendors[0]?.id ?? "");
    const pId = productId || (products[0]?.id ?? "");
    if (!vId || !pId) {
      alert("Please select a vendor and product");
      return;
    }

    try {
      const res = await api<{ id: string }>("POST", "/api/v1/blanket-pos", {
        json: {
          vendor_id: vId,
          start_date: startDate,
          end_date: endDate,
          target_amount: parseFloat(targetAmount),
          payment_terms: paymentTerms,
          notes,
          lines: [
            {
              product_id: pId,
              agreed_rate: parseFloat(agreedRate),
              committed_qty: parseFloat(committedQty),
              uom: "UNIT",
            },
          ],
        },
      });
      setShowCreateModal(false);
      qc.invalidateQueries({ queryKey: ["blanket-pos"] });
      setSelectedBpaId(res.id);
      alert("Blanket Purchase Agreement established successfully");
    } catch (err) {
      alert("Failed to create Blanket Agreement: " + err);
    }
  };

  // Handler: Release Call-off PO
  const handleReleasePo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBpaId) return;
    const whId = releaseWhId || (warehouses[0]?.id ?? "");
    if (!whId) {
      alert("Please select a receiving warehouse");
      return;
    }

    const items = Object.entries(releaseQtys)
      .map(([bpaLineId, val]) => ({
        bpa_line_id: bpaLineId,
        release_qty: parseFloat(val || "0"),
      }))
      .filter((i) => i.release_qty > 0);

    if (items.length === 0) {
      alert("Please enter release quantity for at least one item");
      return;
    }

    try {
      const res = await api<{ po_number: string; release_total: number }>("POST", `/api/v1/blanket-pos/${selectedBpaId}/release`, {
        json: {
          warehouse_id: whId,
          expected_delivery_date: expectedDate,
          lines: items,
        },
      });
      setShowReleaseModal(false);
      qc.invalidateQueries({ queryKey: ["blanket-pos"] });
      qc.invalidateQueries({ queryKey: ["blanket-po-detail", selectedBpaId] });
      alert(`Call-off Purchase Order ${res.po_number} generated for ${money(res.release_total)}`);
    } catch (err) {
      alert("Failed to release call-off PO: " + err);
    }
  };

  return (
    <Shell>
      <PageHeader
        title="Blanket Purchase Orders & Rate Contracts"
        description="Annual long-term vendor procurement agreements, fixed negotiated pricing, commitment draw-downs, and instant call-off PO generation."
        actions={
          <div className="flex gap-2">
            <ActionButton
              tone="primary"
              onClick={() => {
                if (vendors.length > 0 && !vendorId) setVendorId(vendors[0].id);
                if (products.length > 0 && !productId) setProductId(products[0].id);
                setShowCreateModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              New Blanket Agreement
            </ActionButton>
            <ActionButton
              tone="ghost"
              onClick={() => qc.invalidateQueries({ queryKey: ["blanket-pos"] })}
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
          label="Active Rate Contracts"
          value={bpas.filter((b) => b.status === "active").length}
          hint="Under management"
        />
        <StatCard
          label="Total Committed Value"
          value={money(totalContractedVal)}
          hint="Annual procurement ceiling"
        />
        <StatCard
          label="Released Call-off Spend"
          value={money(totalReleasedVal)}
          hint="Total drawn down"
        />
        <StatCard
          label="Overall Contract Utilization"
          value={`${overallUtilization}%`}
          hint="Portfolio progress"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Agreements List */}
        <div className="lg:col-span-1 space-y-4">
          <Panel title="Blanket Agreements (BPA)">
            <div className="space-y-3">
              {bpas.map((b) => {
                const isSelected = b.id === selectedBpaId;
                return (
                  <div
                    key={b.id}
                    onClick={() => setSelectedBpaId(b.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                          {b.bpa_number}
                        </span>
                        <div className="text-xs text-slate-500 font-medium truncate max-w-[160px]">
                          {b.vendor_name}
                        </div>
                      </div>
                      <Pill tone={b.status === "active" ? "success" : "muted"}>
                        {b.status.toUpperCase()}
                      </Pill>
                    </div>

                    {/* Progress Bar */}
                    <div className="space-y-1 mb-2">
                      <div className="flex justify-between text-[11px] text-slate-500">
                        <span>Utilization</span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">
                          {b.utilization_pct}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, b.utilization_pct)}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex justify-between items-center text-xs pt-2 border-t border-slate-100 dark:border-slate-800 text-slate-500">
                      <span>{money(b.released_amount)} drawn</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        Target: {money(b.target_amount)}
                      </span>
                    </div>
                  </div>
                );
              })}

              {bpas.length === 0 && (
                <div className="p-8 text-center border-2 border-dashed border-[var(--border)] rounded-xl w-full">
                  <FileText className="w-10 h-10 mx-auto text-[var(--muted-foreground)] mb-2" />
                  <h3 className="text-sm font-semibold text-[var(--foreground)]">No Blanket Purchase Agreements</h3>
                  <p className="text-xs text-[var(--muted-foreground)] max-w-sm mx-auto mt-1 mb-4">
                    Long-term rate contracts allow fixed negotiated pricing and rapid call-off purchase order releases.
                  </p>
                  <ActionButton size="sm" onClick={() => setShowCreateModal(true)}>
                    Create Rate Agreement →
                  </ActionButton>
                </div>
              )}
            </div>
          </Panel>
        </div>

        {/* Right Column: BPA Details & Releases */}
        <div className="lg:col-span-2 space-y-4">
          {currentBpa ? (
            <Panel
              title={`Agreement Contract: ${currentBpa.bpa_number}`}
              aside={
                currentBpa.status === "active" && (
                  <ActionButton
                    tone="primary"
                    size="sm"
                    onClick={() => {
                      if (warehouses.length > 0 && !releaseWhId) setReleaseWhId(warehouses[0].id);
                      setShowReleaseModal(true);
                    }}
                  >
                    <Send className="w-4 h-4 mr-1.5" />
                    Issue Call-off PO
                  </ActionButton>
                )
              }
            >
              {/* Contract Meta Banner */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg text-xs mb-4">
                <div>
                  <span className="text-slate-400">Contractor / Vendor:</span>
                  <div className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                    {currentBpa.vendor_name}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Validity Horizon:</span>
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    {formatDate(currentBpa.start_date)} → {formatDate(currentBpa.end_date)}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Payment Terms:</span>
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    {currentBpa.payment_terms || "Net 30 Days"}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Remaining Commitment:</span>
                  <div className="font-semibold text-emerald-600">
                    {money(currentBpa.target_amount - currentBpa.released_amount)}
                  </div>
                </div>
              </div>

              {/* Contract Lines */}
              <DataTable
                columns={[
                  "SKU / Description",
                  "Agreed Rate",
                  "Committed Qty",
                  "Released Qty",
                  "Available to Draw",
                ]}
              >
                {currentLines.map((line) => (
                  <TableRow
                    key={line.id}
                    cells={[
                      <div>
                        <div className="font-medium text-slate-900 dark:text-slate-100">{line.sku}</div>
                        <div className="text-xs text-slate-500">{line.name}</div>
                      </div>,
                      <div className="text-right font-semibold text-xs">
                        {money(line.agreed_rate)} / {line.uom}
                      </div>,
                      <div className="text-right text-xs">
                        {qty(line.committed_qty)} {line.uom}
                      </div>,
                      <div className="text-right text-xs text-slate-600 dark:text-slate-400">
                        {qty(line.released_qty)} {line.uom}
                      </div>,
                      <div className="text-right font-bold text-xs text-emerald-600">
                        {qty(line.remaining_qty)} {line.uom}
                      </div>,
                    ]}
                  />
                ))}
              </DataTable>
            </Panel>
          ) : (
            <Panel title="Contract Details">
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <FileSpreadsheet className="w-12 h-12 mb-3 text-slate-300 dark:text-slate-700" />
                <div className="text-sm font-medium">No agreement selected</div>
                <div className="text-xs text-slate-500 mt-1">
                  Select a Blanket Purchase Order from the left panel to review contract lines or issue call-offs.
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>

      {/* Modal: New BPA */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Establish Blanket Purchase Agreement (BPA)"
      >
        <form onSubmit={handleCreateBpa} className="space-y-4">
          <Field label="Vendor Partner">
            <select
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              className="w-full text-sm p-2 border rounded-md bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"
              required
            >
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.display_name || v.legalName || v.name || v.code} ({v.code})
                </option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Agreement Start Date">
              <TextInput type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
            </Field>
            <Field label="Agreement Expiry Date">
              <TextInput type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Total Commitment Target (₹)">
              <TextInput
                type="number"
                value={targetAmount}
                onChange={(e) => setTargetAmount(e.target.value)}
                placeholder="e.g. 500000"
                required
              />
            </Field>
            <Field label="Payment Terms">
              <TextInput
                value={paymentTerms}
                onChange={(e) => setPaymentTerms(e.target.value)}
                placeholder="e.g. Net 45 Days"
              />
            </Field>
          </div>

          <Field label="Contract Notes / Remarks">
            <TextInput
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Master Supply Agreement 2026-2027 Rate Lock"
            />
          </Field>

          <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg space-y-3 border">
            <div className="font-semibold text-xs text-slate-800 dark:text-slate-200">
              Contract Product Line Commitment
            </div>
            <Field label="Product Item">
              <select
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
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
              <Field label="Negotiated Unit Price (₹)">
                <TextInput
                  type="number"
                  value={agreedRate}
                  onChange={(e) => setAgreedRate(e.target.value)}
                  placeholder="e.g. 280.00"
                  required
                />
              </Field>
              <Field label="Committed Contract Qty">
                <TextInput
                  type="number"
                  value={committedQty}
                  onChange={(e) => setCommittedQty(e.target.value)}
                  placeholder="e.g. 1000"
                  required
                />
              </Field>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowCreateModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Establish Agreement
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Modal: Issue Call-Off PO */}
      <Modal
        open={showReleaseModal}
        onClose={() => setShowReleaseModal(false)}
        title="Issue Call-Off Purchase Order"
      >
        <form onSubmit={handleReleasePo} className="space-y-4">
          <p className="text-xs text-slate-500">
            Draws down agreed materials against BPA <strong>{currentBpa?.bpa_number}</strong> with pre-approved rates, bypassing procurement quotation cycles.
          </p>

          <Field label="Receiving Warehouse Destination">
            <select
              value={releaseWhId}
              onChange={(e) => setReleaseWhId(e.target.value)}
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

          <Field label="Committed Delivery Due Date">
            <TextInput
              type="date"
              value={expectedDate}
              onChange={(e) => setExpectedDate(e.target.value)}
              required
            />
          </Field>

          <div className="space-y-3 pt-2">
            <div className="font-semibold text-xs text-slate-700 dark:text-slate-300">
              Draw-down Quantities by Line:
            </div>
            {currentLines.map((line) => (
              <div key={line.id} className="flex items-center justify-between p-2.5 bg-slate-50 dark:bg-slate-900 rounded border">
                <div>
                  <div className="font-medium text-xs">{line.sku}</div>
                  <div className="text-[10px] text-slate-400">
                    Remaining: {line.remaining_qty} @ {money(line.agreed_rate)}
                  </div>
                </div>
                <div className="w-32">
                  <TextInput
                    type="number"
                    step="any"
                    max={line.remaining_qty}
                    placeholder={`Max ${line.remaining_qty}`}
                    value={releaseQtys[line.id] || ""}
                    onChange={(e) => setReleaseQtys({ ...releaseQtys, [line.id]: e.target.value })}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setShowReleaseModal(false)}>
              Cancel
            </ActionButton>
            <ActionButton tone="primary" type="submit">
              Generate Release PO
            </ActionButton>
          </div>
        </form>
      </Modal>
    </Shell>
  );
}
