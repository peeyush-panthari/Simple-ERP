import {
  Award,
  Boxes,
  Building,
  Building2,
  Bell,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Container,
  Factory,
  FileBadge,
  FileSpreadsheet,
  FileText,
  GraduationCap,
  Layers,
  LayoutDashboard,
  LineChart,
  Mail,
  Network,
  Package,
  QrCode,
  Receipt,
  ScrollText,
  ShieldCheck,
  Ship,
  ShoppingCart,
  SlidersHorizontal,
  Smartphone,
  Truck,
  Wallet,
  Warehouse,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export const NAV_GROUPS = [
  "Overview",
  "Planning & SCM",
  "Procurement",
  "Warehouse & Logistics",
  "Manufacturing",
  "Sales & Orders",
  "Finance",
  "Administration",
] as const;

export type NavGroupName = (typeof NAV_GROUPS)[number];

export interface NavItem {
  label: string;
  path: string;
  permission: string;
  /** Other permissions that also open this module (Procurement is also the home of purchase requisitions). */
  alsoWith?: string[];
  icon: LucideIcon;
  group: NavGroupName;
  /** Identifier of the ERP module. Omitted for core platform infrastructure. */
  module?: string;
  /** Badge label for roadmap / upcoming features */
  badge?: string;
  /** Roadmap development horizon */
  roadmapStage?: "medium_term" | "long_term";
}

/**
 * Enterprise ERP Navigation Hierarchy
 * Structured logically by operational departments and business functions.
 */
export const NAV_ITEMS: NavItem[] = [
  // 1. Overview & Analytics
  { label: "Control tower", path: "/", permission: "analytics:read", icon: LayoutDashboard, group: "Overview" },
  { label: "SC Control Tower", path: "/sc-control-tower", permission: "sc_control_tower:read", icon: LayoutDashboard, group: "Overview", module: "sc_control_tower" },
  { label: "System status", path: "/architecture", permission: "analytics:read", icon: Network, group: "Overview" },

  // 2. Planning & Supply Chain (SCM)
  { label: "MRP Planning", path: "/mrp", permission: "mrp:read", alsoWith: ["inventory:read"], icon: SlidersHorizontal, group: "Planning & SCM", module: "planning_mrp" },
  {
    label: "Multi-Echelon DRP",
    path: "/drp",
    permission: "drp:read",
    alsoWith: ["inventory:read", "warehouse:read"],
    icon: Network,
    group: "Planning & SCM",
    module: "planning_drp",
  },
  {
    label: "Demand Forecasting",
    path: "/forecasting",
    permission: "forecasting:read",
    alsoWith: ["inventory:read"],
    icon: LineChart,
    group: "Planning & SCM",
    module: "planning_forecasting",
  },

  // 3. Procurement & Sourcing
  {
    label: "Procurement",
    path: "/procurement",
    permission: "po:read",
    alsoWith: ["pr:read", "pr:approve", "pr:team_approve", "sourcing:read"],
    icon: ShoppingCart,
    group: "Procurement",
    module: "procurement",
  },
  { label: "Supplier Directory", path: "/parties", permission: "party:read", icon: Building2, group: "Procurement" },
  {
    label: "Vendor Portal",
    path: "/vendor-portal",
    permission: "vendor_portal:read",
    icon: Building,
    group: "Procurement",
    module: "vendor_portal",
  },
  {
    label: "Blanket POs (BPA)",
    path: "/blanket-po",
    permission: "blanket_po:read",
    icon: FileSpreadsheet,
    group: "Procurement",
    module: "blanket_po",
  },
  {
    label: "Approved Vendor List (AVL)",
    path: "/avl-governance",
    permission: "avl_governance:read",
    icon: Award,
    group: "Procurement",
    module: "avl_governance",
  },

  // 4. Warehouse & Logistics
  { label: "GRN & QC", path: "/warehouse", permission: "warehouse:read", icon: Warehouse, group: "Warehouse & Logistics", module: "warehouse_grn_qc" },
  { label: "Inventory", path: "/inventory", permission: "inventory:read", icon: Boxes, group: "Warehouse & Logistics", module: "inventory_balances" },
  {
    label: "Cycle Counting",
    path: "/cycle-counts",
    permission: "cycle_count:read",
    icon: ClipboardCheck,
    group: "Warehouse & Logistics",
    module: "cycle_counts",
  },
  { label: "Returns (RMA/RTV)", path: "/returns", permission: "returns:read", alsoWith: ["warehouse:read"], icon: Truck, group: "Warehouse & Logistics", module: "returns_management" },
  {
    label: "Landed Cost Tracking",
    path: "/landed-cost",
    permission: "landed_cost:read",
    alsoWith: ["warehouse:read"],
    icon: Receipt,
    group: "Warehouse & Logistics",
    module: "landed_cost",
  },
  {
    label: "Directed Putaway & Bins",
    path: "/wms-bins",
    permission: "wms_bins:read",
    alsoWith: ["warehouse:read"],
    icon: Layers,
    group: "Warehouse & Logistics",
    module: "wms_bins",
  },
  { label: "Logistics TMS", path: "/logistics", permission: "logistics:read", icon: Truck, group: "Warehouse & Logistics", module: "logistics_tms" },
  {
    label: "e-Way Bill & IRN",
    path: "/statutory-logistics",
    permission: "statutory_logistics:read",
    icon: FileBadge,
    group: "Warehouse & Logistics",
    module: "statutory_logistics",
  },
  {
    label: "Freight Consolidation",
    path: "/freight-tms",
    permission: "freight:read",
    alsoWith: ["logistics:read"],
    icon: Ship,
    group: "Warehouse & Logistics",
    module: "freight_tms",
  },
  {
    label: "WMS Mobile Scanner",
    path: "/wms-mobile",
    permission: "wms_mobile:use",
    icon: Smartphone,
    group: "Warehouse & Logistics",
    module: "wms_mobile",
  },
  {
    label: "Wave & Batch Picking",
    path: "/wave-picking",
    permission: "wave_picking:read",
    icon: Layers,
    group: "Warehouse & Logistics",
    module: "wave_picking",
  },
  {
    label: "Shipping Engine & AWBs",
    path: "/shipping-engine",
    permission: "shipping_engine:read",
    icon: Truck,
    group: "Warehouse & Logistics",
    module: "shipping_engine",
  },

  // 5. Manufacturing & Operations
  { label: "Production & Runs", path: "/production", permission: "inventory:read", icon: Factory, group: "Manufacturing", module: "mfg_production" },
  {
    label: "Subcontracting & Job-Work",
    path: "/subcontracting",
    permission: "subcontracting:read",
    alsoWith: ["inventory:read", "warehouse:read"],
    icon: Workflow,
    group: "Manufacturing",
    module: "mfg_subcontracting",
  },
  {
    label: "Batch Traceability",
    path: "/traceability",
    permission: "traceability:read",
    alsoWith: ["inventory:read"],
    icon: QrCode,
    group: "Manufacturing",
    module: "mfg_traceability",
  },
  {
    label: "Quality IPQC & CoA",
    path: "/quality-ipqc",
    permission: "quality_ipqc:read",
    icon: ShieldCheck,
    group: "Manufacturing",
    module: "quality_ipqc",
  },
  {
    label: "Capacity Planning (RCCP)",
    path: "/capacity-planning",
    permission: "capacity_planning:read",
    icon: SlidersHorizontal,
    group: "Manufacturing",
    module: "capacity_planning",
  },

  // 6. Sales & Orders
  { label: "Orders", path: "/orders", permission: "order:read", icon: ClipboardList, group: "Sales & Orders", module: "sales_orders" },
  {
    label: "Customer B2B Portal",
    path: "/customer-portal",
    permission: "customer_portal:read",
    icon: Building,
    group: "Sales & Orders",
    module: "customer_portal",
  },

  // 7. Finance & Accounting
  { label: "PO & Invoice", path: "/po-invoice", permission: "org:read", icon: Receipt, group: "Finance" },
  { label: "Finance & AR/AP", path: "/finance", permission: "finance:read", icon: Wallet, group: "Finance", module: "finance" },

  // 8. Administration & Master Data
  { label: "Products & BOM", path: "/products", permission: "product:read", icon: Package, group: "Administration" },
  { label: "Factory & Warehouse", path: "/factory-warehouse", permission: "warehouse:read", icon: Container, group: "Administration" },
  { label: "Configuration", path: "/configuration", permission: "product:read", icon: SlidersHorizontal, group: "Administration" },
  { label: "Users & roles", path: "/users", permission: "user:read", icon: ShieldCheck, group: "Administration" },
  { label: "Email Config", path: "/email-config", permission: "email_config:read", icon: Mail, group: "Administration" },
  { label: "Documents", path: "/documents", permission: "document:read", icon: FileText, group: "Administration" },
  { label: "Notifications", path: "/notifications", permission: "notification:read", icon: Bell, group: "Administration" },
  { label: "Audit trail", path: "/audit", permission: "audit:read", icon: ScrollText, group: "Administration" },
  {
    label: "Training Module",
    path: "/training",
    permission: "training:read",
    alsoWith: ["user:read", "audit:read", "analytics:read", "product:read"],
    icon: GraduationCap,
    group: "Administration",
  },
  {
    label: "System Demo Flow",
    path: "/demo-flow",
    permission: "demo:read",
    alsoWith: ["training:read", "user:read"],
    icon: Compass,
    group: "Administration",
  },
];

/** Bottom tab bar has room for four modules plus "More" (which opens the full grouped nav). */
export const MOBILE_TAB_PATHS = ["/", "/warehouse", "/production", "/orders"];

/** "*" grants everything; "resource:*" grants every action on a resource. */
export function permits(granted: readonly string[], permission: string): boolean {
  if (granted.includes("*") || granted.includes(permission)) return true;
  return granted.includes(`${permission.split(":")[0]}:*`);
}

export function visibleNav(granted: readonly string[], enabledModules: readonly string[] = ["*"]): NavItem[] {
  return NAV_ITEMS.filter((i) => {
    const isModuleActive = !i.module || enabledModules.includes("*") || enabledModules.includes(i.module);
    const hasPermission = permits(granted, i.permission) || (i.alsoWith ?? []).some((p) => permits(granted, p));
    return isModuleActive && hasPermission;
  });
}

export function groupedNav(granted: readonly string[], enabledModules: readonly string[] = ["*"]): { group: NavGroupName; items: NavItem[] }[] {
  const visible = visibleNav(granted, enabledModules);
  return NAV_GROUPS.map((group) => ({ group, items: visible.filter((i) => i.group === group) })).filter((g) => g.items.length > 0);
}

export function mobileTabItems(granted: readonly string[], enabledModules: readonly string[] = ["*"]): NavItem[] {
  return visibleNav(granted, enabledModules)
    .filter((i) => MOBILE_TAB_PATHS.includes(i.path))
    .sort((a, b) => MOBILE_TAB_PATHS.indexOf(a.path) - MOBILE_TAB_PATHS.indexOf(b.path));
}

export interface BreadcrumbSegment {
  label: string;
  to?: string;
}

/** Resolves path segments into a semantic breadcrumb hierarchy. */
export function resolveBreadcrumbs(pathname: string): BreadcrumbSegment[] {
  if (pathname === "/" || pathname === "/login") return [];
  if (pathname === "/demo") {
    return [{ label: "Home", to: "/" }, { label: "Administration" }, { label: "System Demo Flow" }];
  }

  // Match exact root nav item first
  const exact = NAV_ITEMS.find((item) => item.path === pathname);
  if (exact) {
    return [
      { label: "Home", to: "/" },
      { label: exact.group },
      { label: exact.label },
    ];
  }

  // Handle nested sub-views
  if (pathname.startsWith("/party/")) {
    return [
      { label: "Home", to: "/" },
      { label: "Procurement", to: "/procurement" },
      { label: "Supplier Directory", to: "/parties" },
      { label: "Party Details" },
    ];
  }
  if (pathname.startsWith("/warehouse/qc/")) {
    return [
      { label: "Home", to: "/" },
      { label: "Warehouse & Logistics", to: "/warehouse" },
      { label: "GRN & QC", to: "/warehouse" },
      { label: "Quality Inspection Station" },
    ];
  }
  if (pathname.startsWith("/inventory-item/")) {
    return [
      { label: "Home", to: "/" },
      { label: "Warehouse & Logistics", to: "/inventory" },
      { label: "Inventory", to: "/inventory" },
      { label: "Item Record" },
    ];
  }
  if (pathname.startsWith("/production/complete/")) {
    return [
      { label: "Home", to: "/" },
      { label: "Manufacturing", to: "/production" },
      { label: "Production & Runs", to: "/production" },
      { label: "Complete Run" },
    ];
  }
  if (pathname.startsWith("/production/")) {
    return [
      { label: "Home", to: "/" },
      { label: "Manufacturing", to: "/production" },
      { label: "Production & Runs", to: "/production" },
      { label: "Run Record" },
    ];
  }

  // Fallback for any other path: split segments
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: BreadcrumbSegment[] = [{ label: "Home", to: "/" }];
  let accum = "";
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    accum += `/${seg}`;
    const match = NAV_ITEMS.find((n) => n.path === accum);
    const label = match ? match.label : seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const isLast = i === segments.length - 1;
    crumbs.push(isLast ? { label } : { label, to: accum });
  }
  return crumbs;
}
