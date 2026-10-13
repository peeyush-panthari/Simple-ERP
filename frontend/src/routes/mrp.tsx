/** Material Requirements Planning (MRP) Workbench. */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  DesktopOnly,
  Field,
  Forbidden,
  InfoTooltip,
  InlineError,
  MobileOnly,
  MobileRecordCard,
  MobileRecordRow,
  Modal,
  PageHeader,
  Panel,
  Pill,
  SelectInput,
  StatCard,
  TextInput,
} from "@/components/erp/ui";
import { ScreenTourButton } from "@/components/erp/screen-tour";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, useAsyncAction } from "@/lib/hooks";

interface PlannedOrder {
  id: string;
  mrpRunId: string;
  productId: string;
  sku: string;
  productName: string;
  orderType: "purchase" | "production";
  warehouseId: string;
  warehouseCode?: string | null;
  quantity: string;
  uom: string;
  suggestedOrderDate: string;
  requiredByDate: string;
  leadTimeDays: number;
  estimatedUnitCost?: string | null;
  status: "suggested" | "released" | "rejected";
  sourceDemand: string;
  releasedReferenceType?: string | null;
  releasedReferenceNumber?: string | null;
  createdAt: string;
}

interface MrpRun {
  id: string;
  number: string;
  horizonDays: number;
  warehouseCode?: string | null;
  status: string;
  totalSkusAnalyzed: number;
  plannedOrdersCount: number;
  notes?: string | null;
  createdBy?: string | null;
  createdAt: string;
  plannedOrders: PlannedOrder[];
}

function Content() {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const canWrite = can("inventory:write") || can("po:write");

  const [dialog, setDialog] = useState<"" | "run">("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selectedOrderIds, setSelectedOrderIds] = useState<string[]>([]);

  const runsQuery = useApiQuery<MrpRun[]>("/api/v1/mrp/runs");

  const runMrpAction = useAsyncAction();
  const releaseAction = useAsyncAction();

  const runs = runsQuery.data ?? [];
  const currentRun = runs.find((r) => r.id === selectedRunId) || runs[0] || null;

  const orders = (currentRun?.plannedOrders ?? []).filter((o) => {
    if (typeFilter === "all") return true;
    return o.orderType === typeFilter;
  });

  const handleRunSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const horizonDays = parseInt(String(f.get("horizonDays") || "30"), 10);
    const notes = String(f.get("notes") || "");

    const ok = await runMrpAction.run(async () => {
      const res = await api<MrpRun>("POST", "/api/v1/mrp/runs", {
        json: { horizonDays, notes: notes || null },
      });
      setSelectedRunId(res.id);
      return true;
    });

    if (ok) {
      setDialog("");
      qc.invalidateQueries({ queryKey: ["mrp-runs"] });
    }
  };

  const handleReleaseSelected = async () => {
    if (selectedOrderIds.length === 0) return;
    const ok = await releaseAction.run(async () => {
      await api("POST", "/api/v1/mrp/planned-orders/release", {
        json: { plannedOrderIds: selectedOrderIds },
      });
      return true;
    });
    if (ok) {
      setSelectedOrderIds([]);
      qc.invalidateQueries({ queryKey: ["mrp-runs"] });
    }
  };

  const toggleSelectOrder = (id: string) => {
    setSelectedOrderIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    const suggestedIds = orders.filter((o) => o.status === "suggested").map((o) => o.id);
    if (suggestedIds.every((id) => selectedOrderIds.includes(id))) {
      setSelectedOrderIds([]);
    } else {
      setSelectedOrderIds(suggestedIds);
    }
  };

  const purchaseCount = (currentRun?.plannedOrders ?? []).filter((o) => o.orderType === "purchase").length;
  const prodCount = (currentRun?.plannedOrders ?? []).filter((o) => o.orderType === "production").length;

  return (
    <div className="flex w-full flex-col gap-4 p-4">
      <PageHeader
        title="Material Requirements Planning (MRP)"
        description="Automated gross-to-net demand explosion across sales orders, safety stock, lead times, and active BOMs."
        actions={
          <div className="flex items-center gap-2">
            <ScreenTourButton
              screenTitle="MRP Planning"
              trainingModuleId="mrp"
              steps={[
                {
                  title: "Gross-to-Net Calculation Engine",
                  highlightTag: "Execution Engine",
                  description: "Click 'Run MRP Calculation' to explode dependent component requirements from BOMs, evaluate current stock, and schedule purchase/production orders.",
                },
                {
                  title: "Planned Orders Workbench",
                  highlightTag: "Workbench Grid",
                  description: "Review Net Requirements calculated via: Net Qty = (Gross Demand + Safety Stock) - (Projected On-Hand + Scheduled Receipts).",
                },
                {
                  title: "Release to Purchase & Production",
                  highlightTag: "Order Release Gates",
                  description: "Select suggested orders using the checkbox column and click 'Release Selected' to instantly dispatch requisitions to Procurement or Production queues.",
                },
              ]}
            />
            {canWrite && (
              <ActionButton onClick={() => setDialog("run")}>
                Run MRP Calculation
              </ActionButton>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Latest Run" value={currentRun?.number ?? "None"} />
        <StatCard label="SKUs Analyzed" value={currentRun ? String(currentRun.totalSkusAnalyzed) : "0"} />
        <StatCard label="Planned Purchases" value={String(purchaseCount)} />
        <StatCard label="Planned Production" value={String(prodCount)} />
      </div>

      <InlineError message={releaseAction.error} />

      <Panel
        title={currentRun ? `Planned Orders Workbench — ${currentRun.number}` : "Planned Orders Workbench"}
        aside={
          <div className="flex items-center gap-2">
            {runs.length > 1 && (
              <>
                <label htmlFor="mrp-run-select" className="sr-only">Select MRP Run</label>
                <SelectInput
                  id="mrp-run-select"
                  value={currentRun?.id ?? ""}
                  onChange={(e) => setSelectedRunId(e.target.value)}
                  options={runs.map((r) => ({
                    value: r.id,
                    label: `${r.number} (${format.date(r.createdAt)})`,
                  }))}
                />
              </>
            )}
            <label htmlFor="mrp-type-filter" className="sr-only">Filter planned orders by type</label>
            <SelectInput
              id="mrp-type-filter"
              aria-label="Filter planned orders by type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              options={[
                { value: "all", label: "All order types" },
                { value: "purchase", label: "Purchase only" },
                { value: "production", label: "Production only" },
              ]}
            />
            {canWrite && selectedOrderIds.length > 0 && (
              <ActionButton
                size="sm"
                loading={releaseAction.busy}
                onClick={handleReleaseSelected}
              >
                Release Selected ({selectedOrderIds.length})
              </ActionButton>
            )}
          </div>
        }
      >
        <div className="flex w-full flex-col items-start gap-2 px-4 py-3">
          {orders.length === 0 ? (
            <div className="py-8 text-center text-sm text-[var(--muted-foreground)] w-full">
              No planned orders generated. Click "Run MRP Calculation" to evaluate current inventory against open demand.
            </div>
          ) : (
            <>
              <DesktopOnly className="w-full">
                <DataTable
                  columns={[
                    <label key="select-all" className="inline-flex items-center cursor-pointer">
                      <span className="sr-only">Select all suggested orders</span>
                      <input
                        id="mrp-select-all"
                        type="checkbox"
                        aria-label="Select all"
                        checked={
                          orders.filter((o) => o.status === "suggested").length > 0 &&
                          orders
                            .filter((o) => o.status === "suggested")
                            .every((o) => selectedOrderIds.includes(o.id))
                        }
                        onChange={toggleSelectAll}
                      />
                    </label>,
                    "Type",
                    "SKU & Item Name",
                    <span className="inline-flex items-center">Net Requirements <InfoTooltip content="Net Qty = (Gross Requirements + Safety Stock) - (Projected Available + Scheduled Receipts)" /></span>,
                    "Required Date",
                    <span className="inline-flex items-center">Suggested Order Date <InfoTooltip content="Backward-scheduled target order release date calculated from supplier lead times." /></span>,
                    "Lead Time",
                    "Demand Source",
                    "Status",
                    "Released Reference",
                  ]}
                  fit
                >
                  {orders.map((o) => (
                    <tr key={o.id}>
                      <td className="w-8">
                        {o.status === "suggested" && (
                          <input
                            type="checkbox"
                            aria-label={`Select ${o.sku}`}
                            checked={selectedOrderIds.includes(o.id)}
                            onChange={() => toggleSelectOrder(o.id)}
                          />
                        )}
                      </td>
                      <td>
                        <Pill tone={o.orderType === "production" ? "info" : "muted"}>
                          {o.orderType === "production" ? "WORK ORDER" : "PURCHASE"}
                        </Pill>
                      </td>
                      <td>
                        <div className="font-medium">{o.sku}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">{o.productName}</div>
                      </td>
                      <td>
                        <span className="font-semibold">{format.qty(o.quantity)}</span> {o.uom}
                      </td>
                      <td>{format.date(o.requiredByDate)}</td>
                      <td>{format.date(o.suggestedOrderDate)}</td>
                      <td>{o.leadTimeDays} days</td>
                      <td className="max-w-[150px] truncate text-xs text-[var(--muted-foreground)]" title={o.sourceDemand}>
                        {o.sourceDemand}
                      </td>
                      <td>
                        <Pill tone={o.status === "released" ? "success" : o.status === "rejected" ? "destructive" : "warning"}>
                          {o.status}
                        </Pill>
                      </td>
                      <td>
                        {o.releasedReferenceNumber ? (
                          <span className="font-mono text-xs font-semibold text-[var(--primary)]">
                            {o.releasedReferenceNumber}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>

              <MobileOnly className="w-full">
                {orders.map((o) => (
                  <MobileRecordCard key={o.id}>
                    <MobileRecordRow
                      label="Type"
                      value={
                        <Pill tone={o.orderType === "production" ? "info" : "muted"}>
                          {o.orderType.toUpperCase()}
                        </Pill>
                      }
                    />
                    <MobileRecordRow label="Item" value={`${o.sku} — ${o.productName}`} />
                    <MobileRecordRow label="Quantity" value={`${format.qty(o.quantity)} ${o.uom}`} />
                    <MobileRecordRow label="Needed By" value={format.date(o.requiredByDate)} />
                    <MobileRecordRow label="Order By" value={format.date(o.suggestedOrderDate)} />
                    <MobileRecordRow label="Status" value={<Pill>{o.status}</Pill>} />
                  </MobileRecordCard>
                ))}
              </MobileOnly>
            </>
          )}
        </div>
      </Panel>

      <Modal open={dialog === "run"} onClose={() => setDialog("")} title="Run MRP Simulation">
        <form onSubmit={handleRunSubmit} className="flex flex-col gap-3">
          <InlineError message={runMrpAction.error} />
          <Field label="Planning Horizon (Days)">
            <SelectInput
              name="horizonDays"
              defaultValue="30"
              options={[
                { value: "14", label: "14 Days (2 Weeks)" },
                { value: "30", label: "30 Days (1 Month)" },
                { value: "60", label: "60 Days (2 Months)" },
                { value: "90", label: "90 Days (Quarter)" },
              ]}
            />
          </Field>
          <Field label="Notes (Optional)">
            <TextInput name="notes" placeholder="e.g. Q4 Peak Season Plan" />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton tone="ghost" onClick={() => setDialog("")}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" loading={runMrpAction.busy}>
              Execute MRP Run
            </ActionButton>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default function MrpPage() {
  const { can } = useAuth();
  return (
    <Shell>
      {can("inventory:read") || can("po:read") ? <Content /> : <Forbidden permission="inventory:read" />}
    </Shell>
  );
}
