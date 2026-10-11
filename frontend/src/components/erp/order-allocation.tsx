/**
 * Order Allocation (Orders tab): an Orders Queue and a Stock Overview on top, and a workspace below
 * where specific FinishedGoodItem units are picked against one order's lines via
 * POST /orders/:id/allocate-items (the manual path). Picks are staged per line so switching lines
 * keeps what is already checked; "Confirm allocation" submits every line with picks, one call each.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ActionButton, DataTable, DesktopOnly, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Panel, Pill, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import * as format from "@/lib/format";
import { useApiQuery, type ListResponse } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface Line {
  id: string;
  productId: string;
  sku: string;
  description?: string | null;
  uom: string;
  status: string;
  quantity: string;
  allocatedQty: string;
}
interface AllocOrder {
  id: string;
  number: string;
  customerName: string;
  promisedDate?: string | null;
  lines: Line[];
}
interface Unit {
  id: string;
  inventoryId: string;
  productId: string;
  warehouseId?: string;
  availableQty: string;
  uom: string;
  receivedDate?: string | null;
}
interface Existing {
  allocationId: string;
  inventoryId?: string | null;
  quantity: string;
  uom: string;
}

const ALLOCATABLE = "confirmed,partially_allocated";
const g = (n: number) => String(Number(n.toFixed(10))); // Python's :g for the values shown here
const errText = (exc: unknown) => (exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));

function Progress({ percent }: { percent: number }) {
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${percent}%` }} />
    </div>
  );
}

export function OrderAllocation() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [orderId, setOrderId] = useState("");
  const [lineId, setLineId] = useState("");
  const [linePicks, setLinePicks] = useState<Record<string, string[]>>({});
  const [pickQty, setPickQty] = useState<Record<string, string>>({});
  const [pickError, setPickError] = useState("");
  const [allocateError, setAllocateError] = useState("");
  const [busy, setBusy] = useState(false);

  const products = useApiQuery<ListResponse<{ id: string; name: string }>>("/api/v1/products", { type: "finished_good", limit: 200 });
  const fgIds = useMemo(() => new Set((products.data?.data ?? []).map((p) => p.id)), [products.data]);

  // Every allocatable order's detail (an N+1 fetch), narrowed to non-cancelled finished-good lines.
  const orders = useQuery({
    queryKey: ["allocation-orders", [...fgIds].sort().join(",")],
    enabled: products.isSuccess,
    retry: false,
    queryFn: async () => {
      const list = await api<ListResponse<{ id: string }>>("GET", "/api/v1/orders", { params: { status: ALLOCATABLE, limit: 100 } });
      const details = await Promise.all(list.data.map((o) => api<AllocOrder>("GET", `/api/v1/orders/${o.id}`)));
      return details.map((o) => ({ ...o, lines: o.lines.filter((l) => fgIds.has(l.productId) && l.status !== "cancelled") })).filter((o) => o.lines.length > 0);
    },
  });
  const balances = useApiQuery<ListResponse<{ productId: string; sku?: string; onHand?: string; reserved?: string }>>("/api/v1/inventory/balances", { limit: 200 });
  const warehouses = useApiQuery<ListResponse<{ id: string; name: string }>>("/api/v1/warehouses", { limit: 100 });
  const whName = Object.fromEntries((warehouses.data?.data ?? []).map((w) => [w.id, w.name]));

  // The unit pool spans every warehouse (orders carry none of their own); narrowed per line below.
  const pool = useApiQuery<ListResponse<Unit>>("/api/v1/inventory/finished-goods", { available: "true", limit: 200 }, { enabled: !!orderId });
  const poolItems = useMemo(() => pool.data?.data ?? [], [pool.data]);
  const existing = useApiQuery<Existing[]>(`/api/v1/orders/lines/${lineId}/allocations`, undefined, { enabled: !!lineId });

  const refreshAll = async () => {
    await qc.invalidateQueries({ queryKey: ["allocation-orders"] });
    await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/balances"] });
    await qc.invalidateQueries({ queryKey: ["/api/v1/inventory/finished-goods"] });
    await qc.invalidateQueries({ queryKey: [`/api/v1/orders/lines/${lineId}/allocations`] });
  };

  const stagedQty = (id: string) => (linePicks[id] ?? []).reduce((s, iid) => s + (Number(pickQty[iid] ?? "0") || 0), 0);

  const queue = (orders.data ?? []).map((o) => {
    const allocated = o.lines.reduce((s, l) => s + Number(l.allocatedQty), 0);
    const ordered = o.lines.reduce((s, l) => s + Number(l.quantity), 0);
    return { ...o, date: format.date(o.promisedDate), allocatedText: `${g(allocated)} / ${g(ordered)}`, full: ordered > 0 && allocated >= ordered - 1e-9 };
  });
  const order = queue.find((o) => o.id === orderId);
  const itemsById = Object.fromEntries(poolItems.map((i) => [i.id, i]));
  const lines = (order?.lines ?? []).map((l) => {
    const remaining = Math.max(Number(l.quantity) - Number(l.allocatedQty), 0);
    const staged = stagedQty(l.id);
    return {
      ...l,
      remaining,
      remainingText: format.qty(String(remaining), l.uom),
      staged,
      percent: remaining > 0 ? Math.round(Math.min(staged / remaining, 1) * 100) : 100,
      chips: (linePicks[l.id] ?? []).filter((iid) => itemsById[iid]).map((iid) => itemsById[iid].inventoryId),
    };
  });
  const line = lines.find((l) => l.id === lineId);

  const overview = useMemo(() => {
    const names = Object.fromEntries((products.data?.data ?? []).map((p) => [p.id, p.name]));
    const by: Record<string, { id: string; name: string; avail: number; alct: number }> = {};
    for (const b of balances.data?.data ?? []) {
      if (!fgIds.has(b.productId)) continue;
      const a = (by[b.productId] ??= { id: b.productId, name: names[b.productId] ?? b.sku ?? "", avail: 0, alct: 0 });
      a.avail += Number(b.onHand || 0);
      a.alct += Number(b.reserved || 0);
    }
    return Object.values(by)
      .sort((a, b) => b.avail - a.avail)
      .map((r) => ({ ...r, percent: r.avail + r.alct > 0 ? Math.round((r.alct / (r.avail + r.alct)) * 100) : 0 }));
  }, [balances.data, products.data, fgIds]);

  const pickedElsewhere = new Set(Object.entries(linePicks).filter(([id]) => id !== lineId).flatMap(([, ids]) => ids));
  const unitPool = poolItems
    .filter((i) => line && i.productId === line.productId && !pickedElsewhere.has(i.id))
    .map((i) => ({ ...i, received: format.date(i.receivedDate), free: format.qty(i.availableQty, i.uom), warehouse: whName[i.warehouseId ?? ""] ?? "—" }))
    .sort((a, b) => (a.receivedDate ?? "").localeCompare(b.receivedDate ?? ""));
  const picked = linePicks[lineId] ?? [];

  const togglePick = (itemId: string) => {
    const item = itemsById[itemId];
    if (!item) return;
    if (picked.includes(itemId)) {
      setLinePicks({ ...linePicks, [lineId]: picked.filter((i) => i !== itemId) });
      const { [itemId]: _drop, ...rest } = pickQty;
      setPickQty(rest);
      setPickError("");
      return;
    }
    // One allocation (one line, one submit) draws from a single warehouse - mirrors the backend's own rejection.
    if (picked.length) {
      const existingWh = picked.map((iid) => itemsById[iid]?.warehouseId).find((w) => w !== undefined);
      if (existingWh !== undefined && item.warehouseId !== existingWh) return setPickError("Clear your other picks first — one allocation can only come from one warehouse.");
    }
    setPickError("");
    setLinePicks({ ...linePicks, [lineId]: [...picked, itemId] });
    setPickQty({ ...pickQty, [itemId]: item.availableQty });
  };

  const clearLine = () => {
    setPickQty(Object.fromEntries(Object.entries(pickQty).filter(([k]) => !picked.includes(k))));
    setLinePicks({ ...linePicks, [lineId]: [] });
    setPickError("");
  };

  const pickedTotal = lines.reduce((s, l) => s + l.staged, 0);
  const remainingTotal = lines.reduce((s, l) => s + l.remaining, 0);
  const hasPicks = lines.some((l) => (linePicks[l.id] ?? []).length > 0);

  const selectOrder = (o: (typeof queue)[number]) => {
    setOrderId(o.id);
    setPickError("");
    setAllocateError("");
    setLineId(o.lines[0]?.id ?? "");
  };
  const clearWorkspace = () => {
    setOrderId("");
    setLineId("");
    setLinePicks({});
    setPickQty({});
    setPickError("");
  };

  const removeAllocation = async (allocationId: string) => {
    setBusy(true);
    setAllocateError("");
    try {
      await api("DELETE", `/api/v1/orders/allocations/${allocationId}`);
      await refreshAll();
    } catch (exc) {
      setAllocateError(errText(exc));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    const withPicks = lines.map((l) => [l.id, linePicks[l.id] ?? []] as const).filter(([, ids]) => ids.length);
    if (!withPicks.length || !orderId) return;
    setBusy(true);
    setAllocateError("");
    let qtyState = { ...pickQty };
    let picksState = { ...linePicks };
    try {
      for (const [id, itemIds] of withPicks) {
        try {
          await api("POST", `/api/v1/orders/${orderId}/allocate-items`, { json: { orderLineId: id, items: itemIds.map((iid) => ({ itemId: iid, quantity: qtyState[iid] || "0" })) } });
        } catch (exc) {
          setAllocateError(`Line ${id}: ${errText(exc)}`);
          return;
        }
        // Clear this line's staged picks as soon as it is committed, so a later line's failure cannot resubmit it.
        qtyState = Object.fromEntries(Object.entries(qtyState).filter(([k]) => !itemIds.includes(k)));
        picksState = { ...picksState, [id]: [] };
        setPickQty(qtyState);
        setLinePicks(picksState);
      }
      await refreshAll();
      const fresh = await orders.refetch();
      if (!fresh.data?.some((o) => o.id === orderId)) clearWorkspace();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="flex w-full flex-wrap items-stretch gap-4">
        <Panel title="Orders Queue" subtitle={`${queue.length} orders`} className="min-w-[18rem] flex-[2]">
          <InlineError message={orders.error?.message} />
          {queue.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted-foreground)]">No orders with finished-good lines right now.</p>
          ) : (
            <>
              <DesktopOnly className="w-full">
                <DataTable columns={["Order", "Customer", "Date", "Lines", "Allocated"]} minWidth={0} fit>
                  {queue.map((o) => (
                    <tr key={o.id} className={cn(o.id === orderId && "workspace-row-selected")}>
                      <td><button type="button" className="rx-link" onClick={() => selectOrder(o)}>{o.number}</button></td>
                      <td>{o.customerName}</td>
                      <td>{o.date}</td>
                      <td>{o.lines.length}</td>
                      <td><span className="font-medium" style={{ color: o.full ? "var(--warning)" : "var(--muted-foreground)" }}>{o.allocatedText}</span></td>
                    </tr>
                  ))}
                </DataTable>
              </DesktopOnly>
              <MobileOnly className="w-full">
                {queue.map((o) => (
                  <MobileRecordCard key={o.id}>
                    <MobileRecordRow label="Order" value={<button type="button" className="rx-link" onClick={() => selectOrder(o)}>{o.number}</button>} />
                    <MobileRecordRow label="Customer" value={o.customerName} />
                    <MobileRecordRow label="Date" value={o.date} />
                    <MobileRecordRow label="Lines" value={o.lines.length} />
                    <MobileRecordRow label="Allocated" value={o.allocatedText} />
                  </MobileRecordCard>
                ))}
              </MobileOnly>
            </>
          )}
        </Panel>
        <Panel title="Stock Overview" aside={<span className="text-sm text-[var(--muted-foreground)]">by SKU</span>} className="stock-overview-panel min-w-[18rem] flex-1">
          {overview.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted-foreground)]">No finished-good stock yet.</p>
          ) : (
            <div className="flex w-full flex-col gap-3 px-5 py-2">
              {overview.map((r) => (
                <div key={r.id} className="w-full py-2.5">
                  <div className="flex w-full justify-between">
                    <span className="text-base font-medium">{r.name}</span>
                    <span className="text-sm text-[var(--muted-foreground)]">{format.qty(r.avail)} avail · {format.qty(r.alct)} alct</span>
                  </div>
                  <Progress percent={r.percent} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Allocation workspace" subtitle="Unit pool spans every warehouse - one allocation can only draw from one of them at a time." className="w-full">
        {!orderId || !order ? (
          <p className="p-4 text-sm text-[var(--muted-foreground)]">Pick an order from the queue above to start allocating.</p>
        ) : (
          <div className="flex flex-col gap-3 p-4">
            <InlineError message={allocateError} />
            <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
              <Pill tone="info">{order.number}</Pill>
              <span>{order.customerName}</span>
              <span>·</span>
              <span>{order.date}</span>
            </div>
            <div className="flex w-full flex-wrap items-start gap-4">
              <div className="w-72 shrink-0">
                <p className="mb-2 text-xs font-bold text-[var(--muted-foreground)]">Order lines · select to load unit pool</p>
                {lines.map((l) => (
                  <div key={l.id} onClick={() => { setLineId(l.id); setPickError(""); setAllocateError(""); }} className={cn("mb-1.5 w-full cursor-pointer rounded-lg px-3 py-2.5", l.id === lineId && "workspace-row-selected")}>
                    <div className="flex w-full justify-between">
                      <span className="text-sm font-bold">{l.description || l.sku}</span>
                      <span className="text-xs text-[var(--muted-foreground)]">{g(l.staged)} / {l.remainingText}</span>
                    </div>
                    <Progress percent={l.percent} />
                    {l.chips.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{l.chips.map((c) => <Pill key={c} tone="muted">{c}</Pill>)}</div>}
                  </div>
                ))}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold">{line ? `Unit pool · ${line.sku} — ${unitPool.length} available` : "Unit pool"}</p>
                {(existing.data?.length ?? 0) > 0 && (
                  <div className="mt-2 flex w-full flex-col gap-1">
                    <p className="text-xs font-bold text-[var(--muted-foreground)]">Already allocated to this line</p>
                    {existing.data!.map((a) => (
                      <div key={a.allocationId} className="flex w-full items-center justify-between">
                        <span className="text-xs">{a.inventoryId || "—"}: {a.quantity} {a.uom}</span>
                        <ActionButton size="sm" tone="danger" loading={busy} onClick={() => removeAllocation(a.allocationId)}>Remove</ActionButton>
                      </div>
                    ))}
                  </div>
                )}
                {pickError && <div className="mt-2"><InlineError message={pickError} /></div>}
                <DesktopOnly className="mt-2 w-full">
                  <DataTable columns={["", "Inventory ID", "Warehouse", "Received", "Qty"]} minWidth={0} fit>
                    {unitPool.map((i) => {
                      const on = picked.includes(i.id);
                      return (
                        <tr key={i.id} className={cn(on && "workspace-row-selected")}>
                          <td><input type="checkbox" checked={on} onChange={() => togglePick(i.id)} /></td>
                          <td><Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link></td>
                          <td>{i.warehouse}</td>
                          <td>{i.received}</td>
                          <td>{on ? <TextInput style={{ width: "6rem" }} value={pickQty[i.id] ?? ""} onChange={(e) => setPickQty({ ...pickQty, [i.id]: e.target.value })} /> : <span className="text-xs text-[var(--muted-foreground)]">{i.free}</span>}</td>
                        </tr>
                      );
                    })}
                  </DataTable>
                </DesktopOnly>
                <MobileOnly className="mt-2 w-full">
                  {unitPool.map((i) => (
                    <MobileRecordCard key={i.id} actions={<label className="check-row"><input type="checkbox" checked={picked.includes(i.id)} onChange={() => togglePick(i.id)} /><span>Pick this unit</span></label>}>
                      <MobileRecordRow label="Inventory ID" value={<Link to={`/inventory-item/${i.id}`} className="rx-link">{i.inventoryId}</Link>} />
                      <MobileRecordRow label="Warehouse" value={i.warehouse} />
                      <MobileRecordRow label="Received" value={i.received} />
                    </MobileRecordCard>
                  ))}
                </MobileOnly>
                {unitPool.length === 0 && <p className="mt-2 text-sm text-[var(--muted-foreground)]">No available units for this line&apos;s SKU.</p>}
              </div>
            </div>
            <hr className="my-3 border-[var(--border)]" />
            <div className="flex w-full flex-wrap items-center gap-3 md:flex-nowrap">
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wide text-[var(--muted-foreground)]">Clipped</span>
                <span className="text-xs text-[var(--muted-foreground)]">{g(pickedTotal)} / {g(remainingTotal)}</span>
              </div>
              <div className="min-w-[6rem] flex-1"><Progress percent={remainingTotal > 0 ? Math.round(Math.min(pickedTotal / remainingTotal, 1) * 100) : 100} /></div>
              <span className="shrink-0 whitespace-nowrap text-xs text-[var(--muted-foreground)]">{line ? `Line ${line.sku} needs ${line.remainingText} more` : ""}</span>
              <ActionButton size="sm" tone="ghost" disabled={!line} onClick={clearLine}>Clear line</ActionButton>
              <ActionButton size="sm" disabled={!hasPicks} loading={busy} onClick={confirm}>Confirm allocation</ActionButton>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
