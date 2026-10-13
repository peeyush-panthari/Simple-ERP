import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { 
  HelpCircle, 
  X, 
  BookOpen, 
  Command, 
  Headphones, 
  CheckCircle2, 
  Layers,
  Sparkles,
  ArrowRight
} from "lucide-react";

interface RouteSop {
  title: string;
  sopSteps: string[];
  docLink?: string;
}

const ROUTE_SOPS: Record<string, RouteSop> = {
  "/mrp": {
    title: "Material Requirements Planning (MRP) SOP",
    sopSteps: [
      "Ensure all sales orders, forecast scenarios, and parent BOMs are locked.",
      "Click 'Run MRP Calculation' to generate gross-to-net explosions.",
      "Review Net Order Quantity suggestions against supplier lead times.",
      "Select suggested lines and click 'Release Selected' to generate draft POs and Production Orders.",
    ],
  },
  "/forecasting": {
    title: "Demand Forecasting & Consensus SOP",
    sopSteps: [
      "Review automated tournament champion models (Holt-Winters vs Exponential Smoothing).",
      "Inspect Mean Absolute Percentage Error (MAPE) against historical sales.",
      "Collaboratively override manual adjustment buckets for promotional spikes.",
      "Lock Consensus Plan and click 'Push to MRP Gross Demand'.",
    ],
  },
  "/procurement": {
    title: "Procurement & Purchase Orders SOP",
    sopSteps: [
      "Create Purchase Requisition or review MRP-generated planned purchase orders.",
      "Issue RFQ to approved vendors on the AVL (Approved Vendor List).",
      "Verify 2-tier approval thresholds (Lead Buyer → Plant Head).",
      "Dispatch PO to vendor via automated SMTP queue or export PDF.",
    ],
  },
  "/warehouse": {
    title: "GRN & Inbound Receiving SOP",
    sopSteps: [
      "Verify vendor ASN document against physical lorry receipt at the dock.",
      "Create GRN and select PO line items received.",
      "Assign initial staging bay. Items immediately route to Quality Station (/warehouse/qc).",
      "Once QC passes, print serialized 2D Datamatrix QR labels.",
    ],
  },
  "/wms-bins": {
    title: "Directed Bin Putaway & Storage SOP",
    sopSteps: [
      "Scan received pallet QR code at warehouse staging area.",
      "System suggests optimal bin by weight limit and velocity class (Fast/Slow moving).",
      "Operator confirms putaway by scanning target rack barcode.",
      "Double-entry stock ledger updates bin occupancy and physical balance.",
    ],
  },
  "/wms-mobile": {
    title: "Mobile Terminal Scanner SOP",
    sopSteps: [
      "Use hardware barcode laser or camera scanner to resolve SKU, Bin, or PO barcode.",
      "For inbound receiving, scan PO barcode to pre-populate line items.",
      "For pick & pack, follow directed wave routing by aisle number.",
      "Confirm each step by scanning destination tote or shipping pallet.",
    ],
  },
  "/production": {
    title: "Manufacturing Execution & Work Orders SOP",
    sopSteps: [
      "Review planned work orders released from MRP demand schedule.",
      "Verify component availability and backflushing inventory in staging bay.",
      "Issue raw materials to production floor with FIFO traceability.",
      "Record finished goods output, yield variance, and scrap quantities.",
    ],
  },
  "/orders": {
    title: "Sales Orders & Fulfillment SOP",
    sopSteps: [
      "Enter customer purchase order and check automated credit limit balance.",
      "System runs row-locked inventory allocation against available stock.",
      "Release order to warehouse for wave picking and pack verification.",
      "Generate customer tax invoice and hand over to Logistics TMS.",
    ],
  },
  "/finance": {
    title: "Finance, Billing & 3-Way Matching SOP",
    sopSteps: [
      "Automated 3-Way Matching executes between PO lines, GRN receipts, and Vendor Invoice.",
      "Approve variance exceptions within tolerance thresholds (±2%).",
      "Schedule AP disbursements according to contracted credit terms.",
      "Post real-time journal entries to the General Ledger.",
    ],
  },
  "/landed-cost": {
    title: "Landed Cost Apportionment SOP",
    sopSteps: [
      "Create Landed Cost Voucher and attach related Inbound GRN receipts.",
      "Enter third-party freight invoices, customs duties, and clearing charges.",
      "Select apportionment basis: Value-weighted (Duty/CIF) or Weight-weighted (Freight).",
      "Post voucher to capitalise freight expenses into inventory unit valuations.",
    ],
  },
  "/statutory-logistics": {
    title: "e-Way Bill & Statutory Compliance SOP",
    sopSteps: [
      "Verify consignment value exceeds the ₹50,000 threshold under GST Rule 138.",
      "Ensure HSN codes, transporter GSTIN, and vehicle registration numbers are accurate.",
      "Click 'Generate e-Way Bill' to fetch 12-digit statutory clearance.",
      "Attach printed e-Way Bill copy with outward tax invoice for vehicle transit.",
    ],
  },
};

const DEFAULT_SOP: RouteSop = {
  title: "General Enterprise Workflow Guidelines",
  sopSteps: [
    "Navigate between modules using the left sidebar or global search (Cmd/Ctrl + K).",
    "All master tables support real-time filtering, status chips, and CSV exports.",
    "Data modifications are strictly governed by RBAC permissions and immutable audit logs.",
    "For complete interactive journey flowcharts, explore the Interactive Training module.",
  ],
};

export function GlobalHelpDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Listen for Shift + ? keypress to toggle help
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "?" && !["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName)) {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const activeSop = ROUTE_SOPS[location.pathname] || DEFAULT_SOP;

  return (
    <>
      {/* Top Header Trigger Button */}
      <button
        type="button"
        className="header-pill relative"
        aria-label="Open persistent help, SOPs, and keyboard shortcuts"
        title="Help, SOPs & Shortcuts (Press '?')"
        onClick={() => setIsOpen(true)}
      >
        <HelpCircle size={16} />
      </button>

      {/* Slide-over Drawer Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs animate-in fade-in duration-200">
          <div 
            className="fixed inset-0" 
            onClick={() => setIsOpen(false)} 
            aria-hidden="true" 
          />

          <div 
            role="dialog" 
            aria-label="Help & Documentation Drawer" 
            aria-modal="true"
            className="relative z-10 w-full max-w-md bg-[var(--card)] text-[var(--foreground)] border-l border-[var(--border)] shadow-2xl h-full flex flex-col overflow-y-auto animate-in slide-in-from-right duration-200"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--muted)]/40">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
                  <BookOpen size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--foreground)]">Operator Guidance & SOPs</h2>
                  <p className="text-[11px] text-[var(--muted-foreground)]">Contextual help for active screen</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close help drawer"
                className="p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              >
                <X size={18} />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-5 space-y-6 flex-1">
              {/* Contextual SOP for Current Screen */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--primary)] flex items-center gap-1.5">
                    <Layers size={14} /> Active Screen SOP
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]">
                    {location.pathname}
                  </span>
                </div>

                <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--background)] space-y-2">
                  <h3 className="text-xs font-bold text-[var(--foreground)]">{activeSop.title}</h3>
                  <ul className="space-y-2 text-xs text-[var(--muted-foreground)]">
                    {activeSop.sopSteps.map((step, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                        <span className="leading-snug">{step}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Keyboard Shortcut Cheat Sheet */}
              <div className="space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)] flex items-center gap-1.5">
                  <Command size={14} /> Keyboard Shortcuts
                </span>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--background)] flex items-center justify-between">
                    <span className="text-[var(--muted-foreground)]">Global Search</span>
                    <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] font-semibold border border-[var(--border)]">
                      ⌘ / Ctrl + K
                    </kbd>
                  </div>
                  <div className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--background)] flex items-center justify-between">
                    <span className="text-[var(--muted-foreground)]">Help & SOPs</span>
                    <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] font-semibold border border-[var(--border)]">
                      Shift + ?
                    </kbd>
                  </div>
                  <div className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--background)] flex items-center justify-between">
                    <span className="text-[var(--muted-foreground)]">Close / Dismiss</span>
                    <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] font-semibold border border-[var(--border)]">
                      Esc
                    </kbd>
                  </div>
                  <div className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--background)] flex items-center justify-between">
                    <span className="text-[var(--muted-foreground)]">New Action</span>
                    <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] font-semibold border border-[var(--border)]">
                      Alt + N
                    </kbd>
                  </div>
                </div>
              </div>

              {/* Dedicated Interactive Training Card */}
              <div className="p-4 rounded-xl border border-teal-500/30 bg-teal-500/5 space-y-2">
                <div className="flex items-center gap-2 text-teal-700 dark:text-teal-300 font-bold text-xs">
                  <Sparkles size={16} />
                  <span>Interactive Enterprise Master Flowchart</span>
                </div>
                <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                  Learn complete multi-stage workflows with Upperline & Downline inputs, guard validations, and accounting ledger links.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    navigate("/training");
                  }}
                  className="w-full mt-2 py-2 px-3 rounded-lg bg-teal-700 hover:bg-teal-800 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors"
                >
                  <span>Open Interactive Training (/training)</span>
                  <ArrowRight size={14} />
                </button>
              </div>

              {/* Support & Admin Hotline */}
              <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--muted)]/30 space-y-1.5 text-xs">
                <div className="font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                  <Headphones size={14} className="text-[var(--primary)]" />
                  <span>Operations & ERP Help Desk</span>
                </div>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Need assistance with posting permissions or workflow approvals?
                </p>
                <div className="text-[11px] font-mono text-[var(--foreground)] pt-1">
                  Email: <span className="text-[var(--primary)]">support@simple-erp.local</span> • Ext: <span className="font-bold">#4411</span>
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-3 border-t border-[var(--border)] bg-[var(--muted)]/20 text-center text-[10px] text-[var(--muted-foreground)]">
              Simple ERP v2.4 • System Status: Operational
            </div>
          </div>
        </div>
      )}
    </>
  );
}
