import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRightLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Info,
  PackageCheck,
  PackagePlus,
  QrCode,
  Scan,
  Smartphone,
  Volume2,
  XCircle,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import { useAuth } from "@/lib/auth";

type MobileMode = "lookup" | "receive" | "putaway" | "pick" | "move";

export default function WmsMobilePage() {
  const { api } = useAuth();
  const [activeMode, setActiveMode] = useState<MobileMode>("lookup");
  const [warehouseId, setWarehouseId] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Sound feedback via Web Audio API
  const playFeedbackSound = (success: boolean) => {
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (success) {
        osc.frequency.setValueAtTime(880, ctx.currentTime); // High pitch A5
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.12);
      } else {
        osc.frequency.setValueAtTime(220, ctx.currentTime); // Low pitch A3 error buzz
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.25);
      }
    } catch {
      // Audio not supported or blocked
    }
  };

  // Fetch Warehouses
  const warehousesQuery = useQuery({
    queryKey: ["wms-mobile-warehouses"],
    queryFn: () => api<Array<{ id: string; name: string; code: string }>>("GET", "/api/v1/wms-bins/warehouses"),
  });

  const warehouses = warehousesQuery.data || [];
  useEffect(() => {
    if (warehouses.length > 0 && !warehouseId) {
      setWarehouseId(warehouses[0].id);
    }
  }, [warehouses, warehouseId]);

  // Mode: Lookup state
  const [lookupBarcode, setLookupBarcode] = useState("");
  const [lookupResult, setLookupResult] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);

  // Mode: Receive state
  const [recvPo, setRecvPo] = useState("PO-TEST-001");
  const [recvSku, setRecvSku] = useState("CELL-NMC-21700");
  const [recvQty, setRecvQty] = useState("25");
  const [recvBatch, setRecvBatch] = useState("");
  const [recvResult, setRecvResult] = useState<any>(null);

  // Mode: Putaway state
  const [putawayBin, setPutawayBin] = useState("QUARANTINE");
  const [putawayQty, setPutawayQty] = useState("25");
  const [putawayResult, setPutawayResult] = useState<any>(null);

  // Mode: Pick Verify state
  const [pickOrder, setPickOrder] = useState("");
  const [pickSku, setPickSku] = useState("");
  const [pickBin, setPickBin] = useState("QUARANTINE");
  const [pickResult, setPickResult] = useState<any>(null);

  // Mode: Move state
  const [moveSrcBin, setMoveSrcBin] = useState("QUARANTINE");
  const [moveDstBin, setMoveDstBin] = useState("BIN-A01-01");
  const [moveSku, setMoveSku] = useState("CELL-NMC-21700");
  const [moveQty, setMoveQty] = useState("5");
  const [moveResult, setMoveResult] = useState<any>(null);

  // Autofocus input on mode switch
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeMode]);

  // Handler: Scan & Lookup
  const handleUniversalScan = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!lookupBarcode.trim() || !warehouseId) return;

    setIsScanning(true);
    try {
      const res = await api<any>("POST", "/api/v1/wms-mobile/scan", {
        json: {
          warehouse_id: warehouseId,
          barcode: lookupBarcode.trim(),
          workflow_type: "general",
        },
      });
      setLookupResult(res);
      playFeedbackSound(res.status === "valid");
    } catch {
      setLookupResult({ status: "invalid", message: "Network scan error" });
      playFeedbackSound(false);
    } finally {
      setIsScanning(false);
      setLookupBarcode("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  // Handler: Mobile Receive
  const handleMobileReceive = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api<any>("POST", "/api/v1/wms-mobile/receive-item", {
        json: {
          warehouse_id: warehouseId,
          po_number: recvPo,
          sku: recvSku,
          received_qty: parseFloat(recvQty),
          batch_no: recvBatch || undefined,
        },
      });
      setRecvResult(res);
      playFeedbackSound(true);
    } catch (err: any) {
      alert("Receive failed: " + err);
      playFeedbackSound(false);
    }
  };

  // Handler: Putaway confirm
  const handleMobilePutaway = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api<any>("POST", "/api/v1/wms-mobile/confirm-putaway", {
        json: {
          warehouse_id: warehouseId,
          bin_barcode: putawayBin,
          quantity: parseFloat(putawayQty),
        },
      });
      setPutawayResult(res);
      playFeedbackSound(true);
    } catch (err: any) {
      alert("Putaway failed: " + err);
      playFeedbackSound(false);
    }
  };

  // Handler: Pick Verify
  const handlePickVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api<any>("POST", "/api/v1/wms-mobile/pick-verify", {
        json: {
          order_number: pickOrder,
          scanned_sku_barcode: pickSku,
          bin_code: pickBin,
          picked_qty: 1,
        },
      });
      setPickResult(res);
      playFeedbackSound(true);
    } catch (err: any) {
      alert("Pick verification error: " + err);
      playFeedbackSound(false);
    }
  };

  // Handler: Bin Move
  const handleBinMove = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api<any>("POST", "/api/v1/wms-mobile/bin-transfer", {
        json: {
          warehouse_id: warehouseId,
          source_bin_code: moveSrcBin,
          destination_bin_code: moveDstBin,
          sku_or_barcode: moveSku,
          quantity: parseFloat(moveQty),
        },
      });
      setMoveResult(res);
      playFeedbackSound(true);
    } catch (err: any) {
      alert("Transfer failed: " + err);
      playFeedbackSound(false);
    }
  };

  return (
    <Shell>
      {/* Mobile Scanner Container - Centered, Phone/Handheld form-factor (max-w-md) */}
      <div className="max-w-md mx-auto my-2 space-y-3 font-sans">
        {/* Header Bar */}
        <div className="bg-slate-900 text-white p-3.5 rounded-xl shadow-lg flex items-center justify-between border border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/20 text-primary flex items-center justify-center font-bold">
              <Smartphone className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-wide flex items-center gap-1.5">
                WMS Mobile Scanner <span className="bg-emerald-950/80 border border-emerald-500/30 text-emerald-300 text-[10px] px-1.5 py-0.2 rounded font-mono font-bold">ONLINE</span>
              </h1>
              <div className="text-[11px] text-slate-300 flex items-center gap-2 mt-0.5">
                <span className="flex items-center gap-1"><Volume2 className="w-3 h-3 text-emerald-300" /> Audio Cues</span>
                <span>•</span>
                <button
                  type="button"
                  aria-label="Hardware Wedge Auto-Refocus Trigger Accelerator"
                  onClick={() => inputRef.current?.focus()}
                  className="flex items-center gap-1 text-emerald-300 hover:underline font-semibold"
                >
                  <Scan className="w-3 h-3" /> Auto-Refocus Active
                </button>
              </div>
            </div>
          </div>

          <label htmlFor="wms-mobile-wh-select" className="sr-only">Active Warehouse</label>
          <select
            id="wms-mobile-wh-select"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
            className="text-xs bg-slate-800 text-slate-200 border border-slate-700 rounded-lg p-1.5 focus:outline-none"
            aria-label="Active Warehouse"
          >
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code}
              </option>
            ))}
          </select>
        </div>

        {/* Quick Navigation Modes */}
        <div className="grid grid-cols-5 gap-1.5 bg-slate-100 dark:bg-slate-900 p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-center">
          <button
            type="button"
            onClick={() => setActiveMode("lookup")}
            className={`py-2 px-1 rounded-lg text-[11px] font-bold flex flex-col items-center gap-1 transition-all ${
              activeMode === "lookup" ? "bg-primary text-white shadow" : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/50"
            }`}
          >
            <Scan className="w-4 h-4" /> Scan
          </button>
          <button
            type="button"
            onClick={() => setActiveMode("receive")}
            className={`py-2 px-1 rounded-lg text-[11px] font-bold flex flex-col items-center gap-1 transition-all ${
              activeMode === "receive" ? "bg-primary text-white shadow" : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/50"
            }`}
          >
            <PackagePlus className="w-4 h-4" /> Receive
          </button>
          <button
            type="button"
            onClick={() => setActiveMode("putaway")}
            className={`py-2 px-1 rounded-lg text-[11px] font-bold flex flex-col items-center gap-1 transition-all ${
              activeMode === "putaway" ? "bg-primary text-white shadow" : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/50"
            }`}
          >
            <QrCode className="w-4 h-4" /> Putaway
          </button>
          <button
            type="button"
            onClick={() => setActiveMode("pick")}
            className={`py-2 px-1 rounded-lg text-[11px] font-bold flex flex-col items-center gap-1 transition-all ${
              activeMode === "pick" ? "bg-primary text-white shadow" : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/50"
            }`}
          >
            <PackageCheck className="w-4 h-4" /> Pick
          </button>
          <button
            type="button"
            onClick={() => setActiveMode("move")}
            className={`py-2 px-1 rounded-lg text-[11px] font-bold flex flex-col items-center gap-1 transition-all ${
              activeMode === "move" ? "bg-primary text-white shadow" : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/50"
            }`}
          >
            <ArrowRightLeft className="w-4 h-4" /> Move
          </button>
        </div>

        {/* WORKFLOW SCREEN: 1. Universal Barcode Lookup */}
        {activeMode === "lookup" && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-4">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center justify-between">
              <span>Universal Barcode Resolver</span>
              <span className="text-[10px] text-slate-400">Aim Laser & Pull Trigger</span>
            </div>

            <form onSubmit={handleUniversalScan} className="space-y-3">
              <div className="relative">
                <label htmlFor="mobile-barcode-input" className="sr-only">Scan SKU, Bin, PO barcode</label>
                <input
                  id="mobile-barcode-input"
                  aria-label="Scan SKU, Bin, PO barcode"
                  ref={inputRef}
                  type="text"
                  value={lookupBarcode}
                  onChange={(e) => setLookupBarcode(e.target.value)}
                  placeholder="Scan SKU, Bin, PO barcode..."
                  className="w-full text-base font-mono p-3 pl-10 border-2 rounded-xl bg-slate-50 dark:bg-slate-950 border-primary focus:outline-none focus:ring-2 focus:ring-primary shadow-inner"
                  autoFocus
                />
                <Scan className="w-5 h-5 absolute left-3 top-3.5 text-primary" />
              </div>
              <p className="text-[11px] text-slate-500 flex items-center gap-1.5 px-0.5">
                <Info className="w-3.5 h-3.5 text-primary shrink-0" />
                <span>Supports symbologies: Code-128, GS1-128, DataMatrix, and QR codes.</span>
              </p>
              <button
                type="submit"
                disabled={isScanning}
                className="w-full py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl text-sm transition-all shadow flex items-center justify-center gap-2"
              >
                Resolve Barcode <ChevronRight className="w-4 h-4" />
              </button>
            </form>

            {lookupResult && (
              <div
                className={`p-3.5 rounded-xl border-2 text-xs space-y-1.5 ${
                  lookupResult.status === "valid"
                    ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-500 text-emerald-950 dark:text-emerald-100"
                    : "bg-rose-50 dark:bg-rose-950/30 border-rose-500 text-rose-950 dark:text-rose-100"
                }`}
              >
                <div className="flex items-center gap-2 font-bold text-sm">
                  {lookupResult.status === "valid" ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  ) : (
                    <XCircle className="w-5 h-5 text-rose-600" />
                  )}
                  <span>
                    {lookupResult.status === "valid" ? `MATCH: ${lookupResult.entity_type?.toUpperCase()}` : "UNRECOGNIZED"}
                  </span>
                </div>
                {lookupResult.status === "valid" ? (
                  <div className="space-y-1 pt-1 font-mono">
                    <div><strong>Identifier:</strong> {lookupResult.sku || lookupResult.bin_code || lookupResult.barcode}</div>
                    <div><strong>Description:</strong> {lookupResult.display_name}</div>
                    {lookupResult.uom && <div><strong>UOM:</strong> {lookupResult.uom}</div>}
                    {lookupResult.velocity_class && <div><strong>Velocity Tier:</strong> Class {lookupResult.velocity_class}</div>}
                  </div>
                ) : (
                  <div>{lookupResult.message}</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* WORKFLOW SCREEN: 2. Scan-to-Receive */}
        {activeMode === "receive" && (
          <form onSubmit={handleMobileReceive} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Dock Inward Scan (PO Receiving)
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">PO Number Barcode</label>
              <input
                type="text"
                value={recvPo}
                onChange={(e) => setRecvPo(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Item SKU Barcode</label>
              <input
                type="text"
                value={recvSku}
                onChange={(e) => setRecvSku(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Received Qty</label>
                <input
                  type="number"
                  step="any"
                  value={recvQty}
                  onChange={(e) => setRecvQty(e.target.value)}
                  className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Vendor Batch Lot</label>
                <input
                  type="text"
                  placeholder="Auto-generate"
                  value={recvBatch}
                  onChange={(e) => setRecvBatch(e.target.value)}
                  className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-sm transition-all shadow mt-2"
            >
              Confirm Dock Receipt
            </button>

            {recvResult && (
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500 rounded-lg text-xs space-y-1">
                <div className="font-bold text-emerald-800 dark:text-emerald-200">Receipt Confirmed</div>
                <div className="font-mono text-[11px]">Lot: {recvResult.batch_no} | Item: {recvResult.inventory_id}</div>
                <div className="text-slate-500">{recvResult.message}</div>
              </div>
            )}
          </form>
        )}

        {/* WORKFLOW SCREEN: 3. Directed Putaway */}
        {activeMode === "putaway" && (
          <form onSubmit={handleMobilePutaway} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Directed Putaway (Bin Confirmation)
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-lg border text-xs space-y-1">
              <span className="text-slate-400">System Suggested Optimal Bin:</span>
              <div className="font-mono text-base font-bold text-primary">QUARANTINE (Rack Bay 01)</div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Scan Destination Bin Barcode Tag</label>
              <input
                type="text"
                value={putawayBin}
                onChange={(e) => setPutawayBin(e.target.value)}
                placeholder="Scan bin barcode label..."
                className="w-full text-sm font-mono p-2.5 border-2 border-primary rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Quantity Placed</label>
              <input
                type="number"
                value={putawayQty}
                onChange={(e) => setPutawayQty(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl text-sm transition-all shadow mt-2"
            >
              Verify & Commit Putaway
            </button>

            {putawayResult && (
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500 rounded-lg text-xs space-y-1">
                <div className="font-bold text-emerald-800 dark:text-emerald-200 flex items-center gap-1">
                  <Check className="w-4 h-4" /> Bin Placement Verified
                </div>
                <div>{putawayResult.message}</div>
              </div>
            )}
          </form>
        )}

        {/* WORKFLOW SCREEN: 4. Pick Verification */}
        {activeMode === "pick" && (
          <form onSubmit={handlePickVerify} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Pick Verification (Prevent Wrong SKU)
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Sales Order No.</label>
              <input
                type="text"
                placeholder="e.g. SO-2026-001"
                value={pickOrder}
                onChange={(e) => setPickOrder(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Current Aisle / Bin</label>
              <input
                type="text"
                value={pickBin}
                onChange={(e) => setPickBin(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Scan Picked Item Barcode</label>
              <input
                type="text"
                placeholder="Scan product barcode..."
                value={pickSku}
                onChange={(e) => setPickSku(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border-2 border-primary rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl text-sm transition-all shadow mt-2"
            >
              Verify Picked Item
            </button>

            {pickResult && (
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500 rounded-lg text-xs space-y-1">
                <div className="font-bold text-emerald-800 dark:text-emerald-200 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> Pick Match Confirmed
                </div>
                <div>{pickResult.message}</div>
              </div>
            )}
          </form>
        )}

        {/* WORKFLOW SCREEN: 5. Bin-to-Bin Move */}
        {activeMode === "move" && (
          <form onSubmit={handleBinMove} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Floor Stock Relocation (Bin → Bin)
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Source Bin</label>
                <input
                  type="text"
                  value={moveSrcBin}
                  onChange={(e) => setMoveSrcBin(e.target.value)}
                  className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Target Bin</label>
                <input
                  type="text"
                  value={moveDstBin}
                  onChange={(e) => setMoveDstBin(e.target.value)}
                  className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">SKU / Item Barcode</label>
              <input
                type="text"
                value={moveSku}
                onChange={(e) => setMoveSku(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">Quantity to Transfer</label>
              <input
                type="number"
                value={moveQty}
                onChange={(e) => setMoveQty(e.target.value)}
                className="w-full text-sm font-mono p-2.5 border rounded-lg bg-slate-50 dark:bg-slate-950"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl text-sm transition-all shadow mt-2"
            >
              Execute Relocation
            </button>

            {moveResult && (
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500 rounded-lg text-xs space-y-1">
                <div className="font-bold text-emerald-800 dark:text-emerald-200">Relocation Completed</div>
                <div>{moveResult.message}</div>
              </div>
            )}
          </form>
        )}
      </div>
    </Shell>
  );
}
