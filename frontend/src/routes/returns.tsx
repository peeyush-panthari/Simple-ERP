import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { RotateCcw, Undo2 } from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  DesktopOnly,
  Field,
  Forbidden,
  InlineError,
  Modal,
  PageHeader,
  Panel,
  Pill,
  SelectInput,
  StatCard,
  TextArea,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction, type ListResponse } from "@/lib/hooks";

interface RmaLine {
  id: string;
  lineNo: number;
  productId: string;
  sku: string;
  authorizedQty: string;
  receivedQty: string;
  restockedQty: string;
  scrappedQty: string;
  repairedQty: string;
  uom: string;
  unitPrice: string;
  inspectionStatus: string;
  dispositionNotes?: string | null;
}

interface Rma {
  id: string;
  number: string;
  customerId: string;
  customerName: string;
  orderNumber?: string | null;
  warehouseCode?: string | null;
  status: string;
  returnReason: string;
  carrier?: string | null;
  trackingNumber?: string | null;
  creditNoteNumber?: string | null;
  notes?: string | null;
  createdAt: string;
  lines: RmaLine[];
}

interface RtvLine {
  id: string;
  lineNo: number;
  productId: string;
  sku: string;
  quantity: string;
  uom: string;
  unitPrice: string;
  rejectionCode?: string | null;
  reason?: string | null;
}

interface Rtv {
  id: string;
  number: string;
  vendorId: string;
  vendorName: string;
  poNumber?: string | null;
  grnNumber?: string | null;
  warehouseCode?: string | null;
  status: string;
  returnReason: string;
  transporter?: string | null;
  vehicleNo?: string | null;
  lrNo?: string | null;
  debitNoteNumber?: string | null;
  notes?: string | null;
  createdAt: string;
  lines: RtvLine[];
}

function Content() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("warehouse:write") || can("orders:write") || can("po:write");

  const [activeTab, setActiveTab] = useState<"rma" | "rtv">("rma");
  const [dialog, setDialog] = useState<"" | "new-rma" | "receive-rma" | "inspect-rma" | "new-rtv" | "dispatch-rtv">("");
  const [selectedRma, setSelectedRma] = useState<Rma | null>(null);
  const [selectedRtv, setSelectedRtv] = useState<Rtv | null>(null);

  // Queries
  const rmasQuery = useApiQuery<Rma[]>("/api/v1/returns/rmas");
  const rtvsQuery = useApiQuery<Rtv[]>("/api/v1/returns/rtvs");
  const partiesQuery = useApiQuery<ListResponse<{ id: string; legalName: string; displayName?: string; type: string }>>(
    "/api/v1/parties",
    { limit: 100 }
  );
  const warehousesQuery = useApiQuery<ListResponse<{ id: string; name: string; code: string }>>(
    "/api/v1/warehouses",
    { limit: 100 }
  );
  const productsQuery = useApiQuery<ListResponse<{ id: string; sku: string; name: string; uom: string }>>(
    "/api/v1/products",
    { limit: 100 }
  );

  const asyncAction = useAsyncAction();

  const rmas = rmasQuery.data ?? [];
  const rtvs = rtvsQuery.data ?? [];
  const parties = partiesQuery.data?.data ?? [];
  const warehouses = warehousesQuery.data?.data ?? [];
  const products = productsQuery.data?.data ?? [];

  const customers = parties.filter((p) => p.type === "customer" || p.type === "both");
  const vendors = parties.filter((p) => p.type === "vendor" || p.type === "both");

  // RMA Handlers
  const handleCreateRma = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const customerId = String(f.get("customerId"));
    const warehouseId = String(f.get("warehouseId"));
    const returnReason = String(f.get("returnReason"));
    const productId = String(f.get("productId"));
    const authorizedQty = parseFloat(String(f.get("authorizedQty") || "1"));
    const unitPrice = parseFloat(String(f.get("unitPrice") || "0"));

    const ok = await asyncAction.run(async () => {
      await api("POST", "/api/v1/returns/rmas", {
        json: {
          customerId,
          warehouseId,
          returnReason,
          lines: [{ productId, authorizedQty, unitPrice, uom: "UNIT" }],
        },
      });
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["/api/v1/returns/rmas"] });
    }
  };

  const handleReceiveRma = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedRma) return;
    const f = new FormData(e.currentTarget);
    const carrier = String(f.get("carrier") || "");
    const trackingNumber = String(f.get("trackingNumber") || "");
    const qty = parseFloat(String(f.get("receivedQty") || "0"));

    const ok = await asyncAction.run(async () => {
      await api("POST", `/api/v1/returns/rmas/${selectedRma.id}/receive`, {
        json: {
          carrier: carrier || null,
          trackingNumber: trackingNumber || null,
          lines: selectedRma.lines.map((l) => ({ lineNo: l.lineNo, receivedQty: qty })),
        },
      });
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["/api/v1/returns/rmas"] });
    }
  };

  const handleInspectRma = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedRma) return;
    const f = new FormData(e.currentTarget);
    const restockedQty = parseFloat(String(f.get("restockedQty") || "0"));
    const scrappedQty = parseFloat(String(f.get("scrappedQty") || "0"));
    const repairedQty = parseFloat(String(f.get("repairedQty") || "0"));
    const notes = String(f.get("dispositionNotes") || "");

    const ok = await asyncAction.run(async () => {
      await api("POST", `/api/v1/returns/rmas/${selectedRma.id}/inspect`, {
        json: {
          dispositions: selectedRma.lines.map((l) => ({
            lineNo: l.lineNo,
            restockedQty,
            scrappedQty,
            repairedQty,
            dispositionNotes: notes || null,
            inspectionStatus: restockedQty > 0 ? "passed" : "scrapped",
          })),
        },
      });
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["/api/v1/returns/rmas"] });
    }
  };

  // RTV Handlers
  const handleCreateRtv = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const vendorId = String(f.get("vendorId"));
    const warehouseId = String(f.get("warehouseId"));
    const returnReason = String(f.get("returnReason"));
    const productId = String(f.get("productId"));
    const quantity = parseFloat(String(f.get("quantity") || "1"));
    const unitPrice = parseFloat(String(f.get("unitPrice") || "0"));

    const ok = await asyncAction.run(async () => {
      await api("POST", "/api/v1/returns/rtvs", {
        json: {
          vendorId,
          warehouseId,
          returnReason,
          lines: [{ productId, quantity, unitPrice, uom: "UNIT" }],
        },
      });
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["/api/v1/returns/rtvs"] });
    }
  };

  const handleDispatchRtv = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedRtv) return;
    const f = new FormData(e.currentTarget);
    const transporter = String(f.get("transporter") || "");
    const vehicleNo = String(f.get("vehicleNo") || "");
    const lrNo = String(f.get("lrNo") || "");

    const ok = await asyncAction.run(async () => {
      await api("POST", `/api/v1/returns/rtvs/${selectedRtv.id}/dispatch`, {
        json: { transporter: transporter || null, vehicleNo: vehicleNo || null, lrNo: lrNo || null },
      });
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["/api/v1/returns/rtvs"] });
    }
  };

  return (
    <div className="flex w-full flex-col gap-4 p-4">
      <PageHeader
        title="Reverse Logistics (Returns)"
        description="End-to-end customer return authorizations (RMA) and returns to vendors (RTV) with stock ledger updates and debit/credit notes."
        actions={
          canWrite && (
            <ActionButton
              onClick={() => {
                if (activeTab === "rma") setDialog("new-rma");
                else setDialog("new-rtv");
              }}
            >
              {activeTab === "rma" ? "Authorize Customer Return (RMA)" : "New Return to Vendor (RTV)"}
            </ActionButton>
          )
        }
      />

      <div className="flex border-b border-[var(--border)] gap-2">
        <button
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "rma"
              ? "border-[var(--primary)] text-[var(--primary)]"
              : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
          onClick={() => setActiveTab("rma")}
        >
          Customer Returns (RMA) ({rmas.length})
        </button>
        <button
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "rtv"
              ? "border-[var(--primary)] text-[var(--primary)]"
              : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
          onClick={() => setActiveTab("rtv")}
        >
          Supplier Returns (RTV) ({rtvs.length})
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {activeTab === "rma" ? (
          <>
            <StatCard label="Total RMAs" value={String(rmas.length)} />
            <StatCard label="Awaiting Receipt" value={String(rmas.filter((r) => r.status === "authorized").length)} />
            <StatCard label="In Inspection" value={String(rmas.filter((r) => r.status === "goods_received").length)} />
            <StatCard label="Completed" value={String(rmas.filter((r) => r.status === "completed").length)} />
          </>
        ) : (
          <>
            <StatCard label="Total RTVs" value={String(rtvs.length)} />
            <StatCard label="Approved / Pending Dispatch" value={String(rtvs.filter((r) => r.status === "approved").length)} />
            <StatCard label="Dispatched & Closed" value={String(rtvs.filter((r) => r.status === "completed").length)} />
            <StatCard label="Debit Notes Generated" value={String(rtvs.filter((r) => Boolean(r.debitNoteNumber)).length)} />
          </>
        )}
      </div>

      <InlineError message={asyncAction.error} />

      {activeTab === "rma" ? (
        <Panel title="Customer Returns (RMA) Book">
          <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
            {rmas.length === 0 ? (
              <div className="p-8 text-center border-2 border-dashed border-[var(--border)] rounded-xl w-full my-2">
                <RotateCcw className="w-10 h-10 mx-auto text-[var(--muted-foreground)] mb-2" />
                <h3 className="text-sm font-semibold text-[var(--foreground)]">No Active Customer Returns (RMA)</h3>
                <p className="text-xs text-[var(--muted-foreground)] max-w-sm mx-auto mt-1 mb-4">
                  Returns from customer sales orders or warranty claims queue here for inspection, disposition, and credit note issuance.
                </p>
                <div className="flex items-center justify-center gap-3">
                  <ActionButton size="sm" onClick={() => setDialog("new-rma")}>
                    Authorize Customer Return (RMA) →
                  </ActionButton>
                  <Link to="/orders" className="text-xs font-semibold text-[var(--primary)] hover:underline">
                    View Sales Orders
                  </Link>
                </div>
              </div>
            ) : (
              <DesktopOnly className="w-full">
                <DataTable
                  columns={[
                    "RMA #",
                    "Customer",
                    "Order Ref",
                    "Return Reason",
                    "Status",
                    "Items",
                    "Credit Note",
                    "Date",
                    "Actions",
                  ]}
                  fit
                >
                  {rmas.map((r) => (
                    <tr key={r.id}>
                      <td className="font-mono font-semibold text-[var(--primary)]">{r.number}</td>
                      <td>{r.customerName}</td>
                      <td>{r.orderNumber || "—"}</td>
                      <td className="max-w-[200px] truncate" title={r.returnReason}>
                        {r.returnReason}
                      </td>
                      <td>
                        <Pill
                          tone={
                            r.status === "completed"
                              ? "success"
                              : r.status === "goods_received"
                              ? "info"
                              : "warning"
                          }
                        >
                          {r.status}
                        </Pill>
                      </td>
                      <td>
                        {r.lines.map((l) => (
                          <div key={l.id} className="text-xs">
                            <span className="font-medium">{l.sku}</span>: {format.qty(l.authorizedQty)} {l.uom}
                          </div>
                        ))}
                      </td>
                      <td>
                        {r.creditNoteNumber ? (
                          <span className="font-mono text-xs font-semibold text-emerald-600">
                            {r.creditNoteNumber}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{format.date(r.createdAt)}</td>
                      <td>
                        <div className="flex items-center gap-1">
                          {canWrite && r.status === "authorized" && (
                            <ActionButton
                              size="sm"
                              onClick={() => {
                                setSelectedRma(r);
                                setDialog("receive-rma");
                              }}
                            >
                              Receive Goods
                            </ActionButton>
                          )}
                          {canWrite && r.status === "goods_received" && (
                            <ActionButton
                              size="sm"
                              onClick={() => {
                                setSelectedRma(r);
                                setDialog("inspect-rma");
                              }}
                            >
                              Inspect & Disposition
                            </ActionButton>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>
            )}
          </div>
        </Panel>
      ) : (
        <Panel title="Supplier Returns (RTV) Book">
          <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
            {rtvs.length === 0 ? (
              <div className="p-8 text-center border-2 border-dashed border-[var(--border)] rounded-xl w-full my-2">
                <Undo2 className="w-10 h-10 mx-auto text-[var(--muted-foreground)] mb-2" />
                <h3 className="text-sm font-semibold text-[var(--foreground)]">No Active Returns to Vendor (RTV)</h3>
                <p className="text-xs text-[var(--muted-foreground)] max-w-sm mx-auto mt-1 mb-4">
                  Rejected items from inbound receipt inspection or defective raw materials queue here for return delivery and vendor debit notes.
                </p>
                <div className="flex items-center justify-center gap-3">
                  <ActionButton size="sm" onClick={() => setDialog("new-rtv")}>
                    New Return to Vendor (RTV) →
                  </ActionButton>
                  <Link to="/warehouse" className="text-xs font-semibold text-[var(--primary)] hover:underline">
                    Inbound Warehouse Receipts
                  </Link>
                </div>
              </div>
            ) : (
              <DesktopOnly className="w-full">
                <DataTable
                  columns={[
                    "RTV #",
                    "Vendor",
                    "PO / GRN Ref",
                    "Return Reason",
                    "Status",
                    "Items",
                    "Debit Note",
                    "Date",
                    "Actions",
                  ]}
                  fit
                >
                  {rtvs.map((r) => (
                    <tr key={r.id}>
                      <td className="font-mono font-semibold text-[var(--primary)]">{r.number}</td>
                      <td>{r.vendorName}</td>
                      <td>{r.poNumber || r.grnNumber || "—"}</td>
                      <td className="max-w-[200px] truncate" title={r.returnReason}>
                        {r.returnReason}
                      </td>
                      <td>
                        <Pill tone={r.status === "completed" ? "success" : "warning"}>{r.status}</Pill>
                      </td>
                      <td>
                        {r.lines.map((l) => (
                          <div key={l.id} className="text-xs">
                            <span className="font-medium">{l.sku}</span>: {format.qty(l.quantity)} {l.uom}
                          </div>
                        ))}
                      </td>
                      <td>
                        {r.debitNoteNumber ? (
                          <span className="font-mono text-xs font-semibold text-emerald-600">
                            {r.debitNoteNumber}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{format.date(r.createdAt)}</td>
                      <td>
                        {canWrite && r.status === "approved" && (
                          <ActionButton
                            size="sm"
                            onClick={() => {
                              setSelectedRtv(r);
                              setDialog("dispatch-rtv");
                            }}
                          >
                            Dispatch Return
                          </ActionButton>
                        )}
                      </td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>
            )}
          </div>
        </Panel>
      )}

      {/* New RMA Dialog */}
      <Modal open={dialog === "new-rma"} onClose={() => setDialog("")} title="Authorize Customer Return (RMA)">
        <form onSubmit={handleCreateRma} className="flex flex-col gap-3">
          <InlineError message={asyncAction.error} />
          <Field label="Customer">
            <SelectInput
              name="customerId"
              required
              placeholder="Select Customer"
              options={customers.map((c) => ({ value: c.id, label: c.displayName || c.legalName }))}
            />
          </Field>
          <Field label="Receiving Warehouse">
            <SelectInput
              name="warehouseId"
              required
              placeholder="Select Warehouse"
              options={warehouses.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))}
            />
          </Field>
          <Field label="Product to Return">
            <SelectInput
              name="productId"
              required
              placeholder="Select Product"
              options={products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))}
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Authorized Quantity">
              <TextInput name="authorizedQty" type="number" defaultValue="1" required />
            </Field>
            <Field label="Unit Price (for credit refund)">
              <TextInput name="unitPrice" type="number" defaultValue="0" required />
            </Field>
          </div>
          <Field label="Return Reason">
            <TextInput name="returnReason" placeholder="e.g. Defective battery, wrong SKU, buyer remorse" required />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={asyncAction.busy}>
              Create RMA
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Receive RMA Dialog */}
      <Modal open={dialog === "receive-rma"} onClose={() => setDialog("")} title={`Receive Goods for ${selectedRma?.number}`}>
        <form onSubmit={handleReceiveRma} className="flex flex-col gap-3">
          <InlineError message={asyncAction.error} />
          <Field label="Carrier / Courier">
            <TextInput name="carrier" placeholder="e.g. BlueDart, Delhivery" />
          </Field>
          <Field label="Tracking / Docket #">
            <TextInput name="trackingNumber" placeholder="Tracking Number" />
          </Field>
          <Field label="Received Quantity">
            <TextInput
              name="receivedQty"
              type="number"
              defaultValue={selectedRma?.lines[0]?.authorizedQty ?? "1"}
              required
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={asyncAction.busy}>
              Confirm Goods Receipt
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Inspect & Disposition RMA Dialog */}
      <Modal open={dialog === "inspect-rma"} onClose={() => setDialog("")} title={`Inspection & Disposition — ${selectedRma?.number}`}>
        <form onSubmit={handleInspectRma} className="flex flex-col gap-3">
          <InlineError message={asyncAction.error} />
          <div className="text-xs text-[var(--muted-foreground)]">
            Specify where received items should be directed. Restocked items move to Available inventory. Eligible refund amounts will automatically create a draft AR Credit Note.
          </div>
          <Field label="Restock Qty (Put back to Available Stock)">
            <TextInput
              name="restockedQty"
              type="number"
              defaultValue={selectedRma?.lines[0]?.receivedQty ?? "1"}
              required
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Scrapped Qty (Damaged)">
              <TextInput name="scrappedQty" type="number" defaultValue="0" />
            </Field>
            <Field label="Repair/Rework Qty (Quarantine)">
              <TextInput name="repairedQty" type="number" defaultValue="0" />
            </Field>
          </div>
          <Field label="Disposition Notes">
            <TextArea name="dispositionNotes" placeholder="Inspection findings / notes" />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={asyncAction.busy}>
              Post Disposition & Generate Credit Note
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* New RTV Dialog */}
      <Modal open={dialog === "new-rtv"} onClose={() => setDialog("")} title="New Return to Vendor (RTV)">
        <form onSubmit={handleCreateRtv} className="flex flex-col gap-3">
          <InlineError message={asyncAction.error} />
          <Field label="Vendor / Supplier">
            <SelectInput
              name="vendorId"
              required
              placeholder="Select Vendor"
              options={vendors.map((v) => ({ value: v.id, label: v.displayName || v.legalName }))}
            />
          </Field>
          <Field label="Dispatching Warehouse">
            <SelectInput
              name="warehouseId"
              required
              placeholder="Select Warehouse"
              options={warehouses.map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))}
            />
          </Field>
          <Field label="Product to Return">
            <SelectInput
              name="productId"
              required
              placeholder="Select Product"
              options={products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))}
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Return Quantity">
              <TextInput name="quantity" type="number" defaultValue="1" required />
            </Field>
            <Field label="Unit Price (for debit note)">
              <TextInput name="unitPrice" type="number" defaultValue="0" required />
            </Field>
          </div>
          <Field label="Return Reason">
            <TextInput name="returnReason" placeholder="e.g. Failed QC inspection at GRN, spec mismatch" required />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={asyncAction.busy}>
              Approve Return
            </ActionButton>
          </div>
        </form>
      </Modal>

      {/* Dispatch RTV Dialog */}
      <Modal open={dialog === "dispatch-rtv"} onClose={() => setDialog("")} title={`Dispatch Return to Vendor — ${selectedRtv?.number}`}>
        <form onSubmit={handleDispatchRtv} className="flex flex-col gap-3">
          <InlineError message={asyncAction.error} />
          <div className="text-xs text-[var(--muted-foreground)]">
            Dispatching issues the returned inventory out of the warehouse ledger and issues an AP Debit Note for finance settlement.
          </div>
          <Field label="Transporter">
            <TextInput name="transporter" placeholder="e.g. VRL Logistics, Gati" required />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Vehicle #">
              <TextInput name="vehicleNo" placeholder="e.g. MH 12 AB 1234" />
            </Field>
            <Field label="LR / Docket #">
              <TextInput name="lrNo" placeholder="LR Number" />
            </Field>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={asyncAction.busy}>
              Confirm Dispatch & Issue Debit Note
            </ActionButton>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default function ReturnsPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("warehouse:read") || can("orders:read") || can("po:read") ? (
        <Content />
      ) : (
        <Forbidden permission="warehouse:read" />
      )}
    </Shell>
  );
}
