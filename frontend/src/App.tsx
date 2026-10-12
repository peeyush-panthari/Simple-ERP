import { lazy, Suspense, Component, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
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
const NotFound = lazy(() => import("@/routes/not-found"));

/** Every page except /login needs a session; a lapsed one bounces to /login. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted-foreground)]">Loading…</div>;
  if (status !== "authenticated") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

const guard = (el: ReactNode) => <RequireAuth>{el}</RequireAuth>;

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageSpinner />}>
        <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />
        <Route path="/" element={guard(<Home />)} />
        <Route path="/users" element={guard(<Users />)} />
        <Route path="/parties" element={guard(<Parties />)} />
        <Route path="/party/:partyId" element={guard(<PartyDetail />)} />
        <Route path="/po-invoice" element={guard(<BusinessEntities />)} />
        <Route path="/factory-warehouse" element={guard(<FactoryWarehouse />)} />
        <Route path="/products" element={guard(<Products />)} />
        <Route path="/procurement" element={guard(<Procurement />)} />
        <Route path="/mrp" element={guard(<Mrp />)} />
        <Route path="/warehouse" element={guard(<Warehouse />)} />
        <Route path="/warehouse/qc/:grnId" element={guard(<WarehouseQc />)} />
        <Route path="/inventory" element={guard(<Inventory />)} />
        <Route path="/returns" element={guard(<Returns />)} />
        <Route path="/inventory-item/:itemId" element={guard(<InventoryItem />)} />
        <Route path="/production/new" element={guard(<ProductionNew />)} />
        <Route path="/production/complete/:runId" element={guard(<ProductionNew />)} />
        <Route path="/production/:runId" element={guard(<ProductionDetail />)} />
        <Route path="/production" element={guard(<Production />)} />
        <Route path="/orders" element={guard(<Orders />)} />
        <Route path="/logistics" element={guard(<Logistics />)} />
        <Route path="/finance" element={guard(<Finance />)} />
        <Route path="/configuration" element={guard(<Configuration />)} />
        <Route path="/profile" element={guard(<Profile />)} />
        <Route path="/audit" element={guard(<Audit />)} />
        <Route path="/architecture" element={guard(<Architecture />)} />
        <Route path="/email-config" element={guard(<EmailConfig />)} />
        <Route path="/documents" element={guard(<Documents />)} />
        <Route path="/notifications" element={guard(<Notifications />)} />
        <Route path="/landed-cost" element={guard(<LandedCost />)} />
        <Route path="/subcontracting" element={guard(<Subcontracting />)} />
        <Route path="/wms-bins" element={guard(<WmsBins />)} />
        <Route path="/drp" element={guard(<Drp />)} />
        <Route path="/forecasting" element={guard(<Forecasting />)} />
        <Route path="/traceability" element={guard(<Traceability />)} />
        <Route path="/freight-tms" element={guard(<FreightTms />)} />
        <Route path="/vendor-portal" element={guard(<VendorPortal />)} />
        <Route path="/cycle-counts" element={guard(<CycleCounts />)} />
        <Route path="/statutory-logistics" element={guard(<StatutoryLogistics />)} />
        <Route path="/blanket-po" element={guard(<BlanketPo />)} />
        <Route path="/wms-mobile" element={guard(<WmsMobile />)} />
        <Route path="/wave-picking" element={guard(<WavePicking />)} />
        <Route path="/customer-portal" element={guard(<CustomerPortal />)} />
        <Route path="/quality-ipqc" element={guard(<QualityIpqc />)} />
        <Route path="/avl-governance" element={guard(<AvlGovernance />)} />
        <Route path="/capacity-planning" element={guard(<CapacityPlanning />)} />
        <Route path="/shipping-engine" element={guard(<ShippingEngine />)} />
        <Route path="/sc-control-tower" element={guard(<ScControlTower />)} />
        <Route path="/training" element={guard(<Training />)} />
        <Route path="*" element={guard(<NotFound />)} />
      </Routes>
    </Suspense>
    </ErrorBoundary>
  );
}
