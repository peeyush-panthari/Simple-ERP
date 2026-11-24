import { lazy, Suspense, Component, type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layers } from "lucide-react";
import { PageSpinner } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      const isDev = import.meta.env.DEV;
      const message = isDev
        ? (this.state.error?.message || "An unexpected error occurred.")
        : "An unexpected error occurred. Please refresh the page or contact system support.";
      return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center p-4 text-center">
          <p className="mb-2 text-lg font-medium">Something went wrong.</p>
          <p className="mb-4 max-w-md text-sm text-[var(--muted-foreground)]">{message}</p>
          <button
            onClick={() => window.location.reload()}
            className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)]"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// One chunk per page, like one Reflex page per route.
const Users = lazy(() => import("@/routes/users"));
const Parties = lazy(() => import("@/routes/parties"));
const PartyDetail = lazy(() => import("@/routes/party-detail"));
const BusinessEntities = lazy(() => import("@/routes/business-entities"));
const FactoryWarehouse = lazy(() => import("@/routes/factory-warehouse"));
const Products = lazy(() => import("@/routes/products"));
const Procurement = lazy(() => import("@/routes/procurement"));
const Warehouse = lazy(() => import("@/routes/warehouse"));
const WarehouseQc = lazy(() => import("@/routes/warehouse-qc"));
const Inventory = lazy(() => import("@/routes/inventory"));
const InventoryItem = lazy(() => import("@/routes/inventory-item"));
const Production = lazy(() => import("@/routes/production"));
const ProductionNew = lazy(() => import("@/routes/production-new"));
const ProductionDetail = lazy(() => import("@/routes/production-detail"));
const Mrp = lazy(() => import("@/routes/mrp"));
const Returns = lazy(() => import("@/routes/returns"));
const Orders = lazy(() => import("@/routes/orders"));
const Logistics = lazy(() => import("@/routes/logistics"));
const Finance = lazy(() => import("@/routes/finance"));
const Configuration = lazy(() => import("@/routes/configuration"));
const Login = lazy(() => import("@/routes/login"));
const ForgotPassword = lazy(() => import("@/routes/forgot-password"));
const ResetPassword = lazy(() => import("@/routes/reset-password"));
const AcceptInvite = lazy(() => import("@/routes/accept-invite"));
const Home = lazy(() => import("@/routes/home"));
const Profile = lazy(() => import("@/routes/profile"));
const Audit = lazy(() => import("@/routes/audit"));
const Architecture = lazy(() => import("@/routes/architecture"));
const EmailConfig = lazy(() => import("@/routes/email-config"));
const Documents = lazy(() => import("@/routes/documents"));
const Notifications = lazy(() => import("@/routes/notifications"));
const LandedCost = lazy(() => import("@/routes/landed-cost"));
const Subcontracting = lazy(() => import("@/routes/subcontracting"));
const WmsBins = lazy(() => import("@/routes/wms-bins"));
const Drp = lazy(() => import("@/routes/drp"));
const Forecasting = lazy(() => import("@/routes/forecasting"));
const Traceability = lazy(() => import("@/routes/traceability"));
const FreightTms = lazy(() => import("@/routes/freight-tms"));
const VendorPortal = lazy(() => import("@/routes/vendor-portal"));
const CycleCounts = lazy(() => import("@/routes/cycle-counts"));
const StatutoryLogistics = lazy(() => import("@/routes/statutory-logistics"));
const BlanketPo = lazy(() => import("@/routes/blanket-po"));
const WmsMobile = lazy(() => import("@/routes/wms-mobile"));
const WavePicking = lazy(() => import("@/routes/wave-picking"));
const CustomerPortal = lazy(() => import("@/routes/customer-portal"));
const QualityIpqc = lazy(() => import("@/routes/quality-ipqc"));
const AvlGovernance = lazy(() => import("@/routes/avl-governance"));
const CapacityPlanning = lazy(() => import("@/routes/capacity-planning"));
const ShippingEngine = lazy(() => import("@/routes/shipping-engine"));
const ScControlTower = lazy(() => import("@/routes/sc-control-tower"));
const Training = lazy(() => import("@/routes/training"));
const DemoFlow = lazy(() => import("@/routes/demo-flow"));
const NotFound = lazy(() => import("@/routes/not-found"));
import { DemoFlowProvider } from "@/lib/demo-flow-context";
import { GuidedTourDock } from "@/components/erp/guided-tour-dock";

/** Every page except /login needs a session; a lapsed one bounces to /login. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted-foreground)]">Loading…</div>;
  if (status !== "authenticated") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function ModuleGuard({ module, children }: { module: string; children: ReactNode }) {
  const { isModuleEnabled, can, user } = useAuth();
  if (!isModuleEnabled(module)) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 rounded-full bg-[var(--muted)] p-4 text-[var(--muted-foreground)]">
          <Layers size={32} />
        </div>
        <h2 className="mb-2 text-xl font-semibold text-[var(--foreground)]">Module Not Enabled</h2>
        <p className="mb-6 max-w-md text-sm text-[var(--muted-foreground)]">
          This module is currently inactive for <strong>{user?.tenantName || "your business"}</strong>.
          You can enable it in system configuration.
        </p>
        <div className="flex items-center gap-3">
          <Link to="/" className="btn-secondary rounded px-4 py-2 text-sm">
            Dashboard
          </Link>
          {can("org:write") && (
            <Link to="/configuration" className="btn-primary rounded px-4 py-2 text-sm">
              Configure Modules
            </Link>
          )}
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

const guard = (el: ReactNode) => <RequireAuth>{el}</RequireAuth>;
const modGuard = (module: string, el: ReactNode) => (
  <RequireAuth>
    <ModuleGuard module={module}>{el}</ModuleGuard>
  </RequireAuth>
);

export default function App() {
  return (
    <ErrorBoundary>
      <DemoFlowProvider>
        <Suspense fallback={<PageSpinner />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/accept-invite" element={<AcceptInvite />} />
            <Route path="/" element={guard(<Home />)} />
            <Route path="/demo-flow" element={guard(<DemoFlow />)} />
            <Route path="/demo" element={guard(<DemoFlow />)} />
            <Route path="/users" element={guard(<Users />)} />
            <Route path="/parties" element={guard(<Parties />)} />
            <Route path="/party/:partyId" element={guard(<PartyDetail />)} />
            <Route path="/po-invoice" element={guard(<BusinessEntities />)} />
            <Route path="/factory-warehouse" element={guard(<FactoryWarehouse />)} />
            <Route path="/products" element={guard(<Products />)} />
            <Route path="/procurement" element={modGuard("procurement", <Procurement />)} />
            <Route path="/mrp" element={modGuard("planning_mrp", <Mrp />)} />
            <Route path="/warehouse" element={modGuard("warehouse_grn_qc", <Warehouse />)} />
            <Route path="/warehouse/qc/:grnId" element={modGuard("warehouse_grn_qc", <WarehouseQc />)} />
            <Route path="/warehouse-qc" element={modGuard("warehouse_grn_qc", <WarehouseQc />)} />
            <Route path="/inventory" element={modGuard("inventory_balances", <Inventory />)} />
            <Route path="/returns" element={modGuard("returns_management", <Returns />)} />
            <Route path="/inventory-item/:itemId" element={modGuard("inventory_balances", <InventoryItem />)} />
            <Route path="/production/new" element={modGuard("mfg_production", <ProductionNew />)} />
            <Route path="/production/complete/:runId" element={modGuard("mfg_production", <ProductionNew />)} />
            <Route path="/production/:runId" element={modGuard("mfg_production", <ProductionDetail />)} />
            <Route path="/production" element={modGuard("mfg_production", <Production />)} />
            <Route path="/orders" element={modGuard("sales_orders", <Orders />)} />
            <Route path="/logistics" element={modGuard("logistics_tms", <Logistics />)} />
            <Route path="/finance" element={modGuard("finance", <Finance />)} />
            <Route path="/configuration" element={guard(<Configuration />)} />
            <Route path="/profile" element={guard(<Profile />)} />
            <Route path="/audit" element={guard(<Audit />)} />
            <Route path="/architecture" element={guard(<Architecture />)} />
            <Route path="/email-config" element={guard(<EmailConfig />)} />
            <Route path="/documents" element={guard(<Documents />)} />
            <Route path="/notifications" element={guard(<Notifications />)} />
            <Route path="/landed-cost" element={modGuard("landed_cost", <LandedCost />)} />
            <Route path="/subcontracting" element={modGuard("mfg_subcontracting", <Subcontracting />)} />
            <Route path="/wms-bins" element={modGuard("wms_bins", <WmsBins />)} />
            <Route path="/drp" element={modGuard("planning_drp", <Drp />)} />
            <Route path="/forecasting" element={modGuard("planning_forecasting", <Forecasting />)} />
            <Route path="/traceability" element={modGuard("mfg_traceability", <Traceability />)} />
            <Route path="/freight-tms" element={modGuard("freight_tms", <FreightTms />)} />
            <Route path="/vendor-portal" element={modGuard("vendor_portal", <VendorPortal />)} />
            <Route path="/cycle-counts" element={modGuard("cycle_counts", <CycleCounts />)} />
            <Route path="/statutory-logistics" element={modGuard("statutory_logistics", <StatutoryLogistics />)} />
            <Route path="/blanket-po" element={modGuard("blanket_po", <BlanketPo />)} />
            <Route path="/wms-mobile" element={modGuard("wms_mobile", <WmsMobile />)} />
            <Route path="/wave-picking" element={modGuard("wave_picking", <WavePicking />)} />
            <Route path="/customer-portal" element={modGuard("customer_portal", <CustomerPortal />)} />
            <Route path="/quality-ipqc" element={modGuard("quality_ipqc", <QualityIpqc />)} />
            <Route path="/avl-governance" element={modGuard("avl_governance", <AvlGovernance />)} />
            <Route path="/capacity-planning" element={modGuard("capacity_planning", <CapacityPlanning />)} />
            <Route path="/shipping-engine" element={modGuard("shipping_engine", <ShippingEngine />)} />
            <Route path="/sc-control-tower" element={modGuard("sc_control_tower", <ScControlTower />)} />
            <Route path="/training" element={guard(<Training />)} />
            <Route path="*" element={guard(<NotFound />)} />
          </Routes>
        </Suspense>
        <GuidedTourDock />
      </DemoFlowProvider>
    </ErrorBoundary>
  );
}
