import {
  Award,
  Boxes,
  Building,
  Building2,
  Bell,
  ClipboardCheck,
  ClipboardList,
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
  { label: "SC Control Tower", path: "/sc-control-tower", permission: "sc_control_tower:read", icon: LayoutDashboard, group: "Overview" },
  { label: "System status", path: "/architecture", permission: "analytics:read", icon: Network, group: "Overview" },

  // 2. Planning & Supply Chain (SCM)
  { label: "MRP Planning", path: "/mrp", permission: "mrp:read", alsoWith: ["inventory:read"], icon: SlidersHorizontal, group: "Planning & SCM" },
  {
    label: "Multi-Echelon DRP",
    path: "/drp",
    permission: "drp:read",
    alsoWith: ["inventory:read", "warehouse:read"],
    icon: Network,
    group: "Planning & SCM",
  },
  {
    label: "Demand Forecasting",
    path: "/forecasting",
    permission: "forecasting:read",
    alsoWith: ["inventory:read"],
    icon: LineChart,
    group: "Planning & SCM",
  },

  // 3. Procurement & Sourcing
  {
    label: "Procurement",
    path: "/procurement",
    permission: "po:read",
    alsoWith: ["pr:read", "pr:approve", "pr:team_approve", "sourcing:read"],
    icon: ShoppingCart,
    group: "Procurement",
  },
  { label: "Supplier Directory", path: "/parties", permission: "party:read", icon: Building2, group: "Procurement" },
  {
    label: "Vendor Portal",
    path: "/vendor-portal",
    permission: "vendor_portal:read",
    icon: Building,
    group: "Procurement",
  },
  {
    label: "Blanket POs (BPA)",
    path: "/blanket-po",
    permission: "blanket_po:read",
    icon: FileSpreadsheet,
    group: "Procurement",
  },
  {
    label: "Approved Vendor List (AVL)",
    path: "/avl-governance",
    permission: "avl_governance:read",
    icon: Award,
    group: "Procurement",
  },

  // 4. Warehouse & Logistics
  { label: "GRN & QC", path: "/warehouse", permission: "warehouse:read", icon: Warehouse, group: "Warehouse & Logistics" },
  { label: "Inventory", path: "/inventory", permission: "inventory:read", icon: Boxes, group: "Warehouse & Logistics" },
  {
    label: "Cycle Counting",
    path: "/cycle-counts",
    permission: "cycle_count:read",
    icon: ClipboardCheck,
    group: "Warehouse & Logistics",
  },
  { label: "Returns (RMA/RTV)", path: "/returns", permission: "returns:read", alsoWith: ["warehouse:read"], icon: Truck, group: "Warehouse & Logistics" },
  {
    label: "Landed Cost Tracking",
    path: "/landed-cost",
    permission: "landed_cost:read",
    alsoWith: ["warehouse:read"],
    icon: Receipt,
    group: "Warehouse & Logistics",
  },
  {
    label: "Directed Putaway & Bins",
    path: "/wms-bins",
    permission: "wms_bins:read",
    alsoWith: ["warehouse:read"],
    icon: Layers,
    group: "Warehouse & Logistics",
  },
  { label: "Logistics TMS", path: "/logistics", permission: "logistics:read", icon: Truck, group: "Warehouse & Logistics" },
  {
    label: "e-Way Bill & IRN",
    path: "/statutory-logistics",
    permission: "statutory_logistics:read",
    icon: FileBadge,
    group: "Warehouse & Logistics",
  },
  {
    label: "Freight Consolidation",
    path: "/freight-tms",
    permission: "freight:read",
    alsoWith: ["logistics:read"],
    icon: Ship,
    group: "Warehouse & Logistics",
  },
  {
    label: "WMS Mobile Scanner",
    path: "/wms-mobile",
    permission: "wms_mobile:use",
    icon: Smartphone,
    group: "Warehouse & Logistics",
  },
  {
    label: "Wave & Batch Picking",
    path: "/wave-picking",
    permission: "wave_picking:read",
    icon: Layers,
    group: "Warehouse & Logistics",
  },
  {
    label: "Shipping Engine & AWBs",
    path: "/shipping-engine",
    permission: "shipping_engine:read",
    icon: Truck,
    group: "Warehouse & Logistics",
  },

  // 5. Manufacturing & Operations
  { label: "Production & Runs", path: "/production", permission: "inventory:read", icon: Factory, group: "Manufacturing" },
  {
    label: "Subcontracting & Job-Work",
    path: "/subcontracting",
    permission: "subcontracting:read",
    alsoWith: ["inventory:read", "warehouse:read"],
    icon: Workflow,
    group: "Manufacturing",
  },
  {
    label: "Batch Traceability",
    path: "/traceability",
    permission: "traceability:read",
    alsoWith: ["inventory:read"],
    icon: QrCode,
    group: "Manufacturing",
  },
  {
    label: "Quality IPQC & CoA",
    path: "/quality-ipqc",
    permission: "quality_ipqc:read",
    icon: ShieldCheck,
    group: "Manufacturing",
  },
  {
    label: "Capacity Planning (RCCP)",
    path: "/capacity-planning",
    permission: "capacity_planning:read",
    icon: SlidersHorizontal,
    group: "Manufacturing",
  },

  // 6. Sales & Orders
  { label: "Orders", path: "/orders", permission: "order:read", icon: ClipboardList, group: "Sales & Orders" },
  {
    label: "Customer B2B Portal",
    path: "/customer-portal",
    permission: "customer_portal:read",
    icon: Building,
    group: "Sales & Orders",
  },

  // 7. Finance & Accounting
  { label: "PO & Invoice", path: "/po-invoice", permission: "org:read", icon: Receipt, group: "Finance" },
  { label: "Finance & AR/AP", path: "/finance", permission: "finance:read", icon: Wallet, group: "Finance" },

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
];

/** Bottom tab bar has room for four modules plus "More" (which opens the full grouped nav). */
export const MOBILE_TAB_PATHS = ["/", "/warehouse", "/production", "/orders"];

/** "*" grants everything; "resource:*" grants every action on a resource. */
export function permits(granted: readonly string[], permission: string): boolean {
  if (granted.includes("*") || granted.includes(permission)) return true;
  return granted.includes(`${permission.split(":")[0]}:*`);
}

export function visibleNav(granted: readonly string[]): NavItem[] {
  return NAV_ITEMS.filter((i) => permits(granted, i.permission) || (i.alsoWith ?? []).some((p) => permits(granted, p)));
}

export function groupedNav(granted: readonly string[]): { group: NavGroupName; items: NavItem[] }[] {
  const visible = visibleNav(granted);
  return NAV_GROUPS.map((group) => ({ group, items: visible.filter((i) => i.group === group) })).filter((g) => g.items.length > 0);
}

export function mobileTabItems(granted: readonly string[]): NavItem[] {
  return visibleNav(granted)
    .filter((i) => MOBILE_TAB_PATHS.includes(i.path))
    .sort((a, b) => MOBILE_TAB_PATHS.indexOf(a.path) - MOBILE_TAB_PATHS.indexOf(b.path));
}
