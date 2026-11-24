/**
 * ERP Module Catalog and Industry Profile Presets.
 *
 * Allows administrators and setup wizards to toggle active ERP modules per company/business.
 * When a module is disabled, its navigation links are automatically hidden and its direct routes
 * are guarded.
 */

export interface ErpModuleDefinition {
  id: string;
  name: string;
  group: string;
  description: string;
  isCore?: boolean;
}

export interface IndustryPreset {
  label: string;
  description: string;
  modules: string[];
}

export const ALL_ERP_MODULES: ErpModuleDefinition[] = [
  // 1. Planning & Supply Chain (SCM)
  {
    id: "planning_mrp",
    name: "MRP Planning",
    group: "Planning & SCM",
    description: "Gross-to-net material requirements planning and demand explosion.",
  },
  {
    id: "planning_drp",
    name: "Multi-Echelon DRP",
    group: "Planning & SCM",
    description: "Distribution requirements planning across central and satellite depots.",
  },
  {
    id: "planning_forecasting",
    name: "Demand Forecasting",
    group: "Planning & SCM",
    description: "Holt-Winters, ARIMA, and tournament demand forecasting with MAPE analytics.",
  },
  {
    id: "sc_control_tower",
    name: "SC Control Tower",
    group: "Overview",
    description: "Cross-echelon visibility into shortages, open POs, and supply chain health.",
  },

  // 2. Procurement & Sourcing
  {
    id: "procurement",
    name: "Procurement & Purchase Orders",
    group: "Procurement",
    description: "Purchase requisitions, purchase orders, approval tiers, and vendor documents.",
  },
  {
    id: "sourcing_rfq",
    name: "Sourcing (RFQ)",
    group: "Procurement",
    description: "Supplier quotation requests, comparison matrices, and award to PO.",
  },
  {
    id: "blanket_po",
    name: "Blanket POs (BPA)",
    group: "Procurement",
    description: "Long-term rate contracts with cumulative drawdown tracking.",
  },
  {
    id: "avl_governance",
    name: "Approved Vendor List (AVL)",
    group: "Procurement",
    description: "Vendor qualification, status lifecycle, and supplier risk governance.",
  },
  {
    id: "vendor_portal",
    name: "Vendor Portal",
    group: "Procurement",
    description: "External supplier self-service portal for PO acknowledgement and dispatch.",
  },

  // 3. Warehouse & Inventory
  {
    id: "warehouse_grn_qc",
    name: "GRN & Inbound QC",
    group: "Warehouse & Logistics",
    description: "Goods receipt notes, QR sticker printing, and dock inspection routing.",
  },
  {
    id: "inventory_balances",
    name: "Inventory & Stock Ledger",
    group: "Warehouse & Logistics",
    description: "Multi-bucket stock ledger (available, quarantine, damaged, reserved).",
  },
  {
    id: "cycle_counts",
    name: "Cycle Counting",
    group: "Warehouse & Logistics",
    description: "ABC classification, periodic/blind counts, and discrepancy adjustments.",
  },
  {
    id: "returns_management",
    name: "Returns (RMA / RTV)",
    group: "Warehouse & Logistics",
    description: "Customer return authorizations (RMA) and return-to-vendor (RTV) debit notes.",
  },
  {
    id: "landed_cost",
    name: "Landed Cost Tracking",
    group: "Warehouse & Logistics",
    description: "Customs, freight, and insurance apportionment across inbound receipts.",
  },
  {
    id: "wms_bins",
    name: "WMS Bins & Directed Putaway",
    group: "Warehouse & Logistics",
    description: "Aisle, rack, bin layout management and velocity-based putaway rules.",
  },
  {
    id: "wms_mobile",
    name: "WMS Mobile Scanner",
    group: "Warehouse & Logistics",
    description: "Floor-ready camera and barcode scanner for fast warehouse receipts and picking.",
  },
  {
    id: "wave_picking",
    name: "Wave & Batch Picking",
    group: "Warehouse & Logistics",
    description: "Consolidated pick lists across multiple sales orders for warehouse throughput.",
  },

  // 4. Logistics & Transportation
  {
    id: "logistics_tms",
    name: "Logistics TMS",
    group: "Warehouse & Logistics",
    description: "Freight transport requests, carrier allocation, and shipment tracking.",
  },
  {
    id: "statutory_logistics",
    name: "e-Way Bill & IRN",
    group: "Warehouse & Logistics",
    description: "Statutory GST Rule 138 e-Way Bill generation and IRN e-Invoice compliance.",
  },
  {
    id: "freight_tms",
    name: "Freight Consolidation",
    group: "Warehouse & Logistics",
    description: "LTL/FTL shipment consolidation and multi-stop linehaul routing.",
  },
  {
    id: "shipping_engine",
    name: "Shipping Engine & AWBs",
    group: "Warehouse & Logistics",
    description: "Courier API integration, shipping label generation, and automated tracking.",
  },

  // 5. Manufacturing & Operations
  {
    id: "mfg_production",
    name: "Production & Work Orders",
    group: "Manufacturing",
    description: "Work order dispatch, BOM consumption, scrap recording, and FG serialization.",
  },
  {
    id: "mfg_subcontracting",
    name: "Subcontracting & Job-Work",
    group: "Manufacturing",
    description: "Challan 54F job-worker tracking, material reconciliation, and service POs.",
  },
  {
    id: "mfg_traceability",
    name: "Batch Traceability",
    group: "Manufacturing",
    description: "End-to-end forward and backward lot genealogy from supplier to customer.",
  },
  {
    id: "quality_ipqc",
    name: "Quality IPQC & CoA",
    group: "Manufacturing",
    description: "In-process quality inspection checkpoints and Certificate of Analysis issuance.",
  },
  {
    id: "capacity_planning",
    name: "Capacity Planning (RCCP)",
    group: "Manufacturing",
    description: "Rough-cut machine load balancing and shift capacity analysis.",
  },

  // 6. Sales & Orders
  {
    id: "sales_orders",
    name: "Sales Orders & Allocations",
    group: "Sales & Orders",
    description: "Sales order intake, automated FEFO/FIFO stock allocation, and dispatch.",
  },
  {
    id: "customer_portal",
    name: "Customer B2B Portal",
    group: "Sales & Orders",
    description: "External customer order tracking, invoice downloading, and RMA requests.",
  },

  // 7. Finance
  {
    id: "finance",
    name: "Finance & AR/AP",
    group: "Finance",
    description: "General ledger, 3-way matching, invoice settlements, and aging analytics.",
  },
];

export const INDUSTRY_PRESETS: Record<string, IndustryPreset> = {
  full: {
    label: "Full Enterprise Suite (All Modules)",
    description: "All supply chain, manufacturing, warehouse, and financial modules enabled.",
    modules: ["*"],
  },
  trading_distribution: {
    label: "Trading & Wholesale Distribution",
    description: "Designed for wholesale and retail distributors. Includes P2P, O2C, WMS, and Finance without shopfloor manufacturing.",
    modules: [
      "procurement",
      "sourcing_rfq",
      "blanket_po",
      "avl_governance",
      "warehouse_grn_qc",
      "inventory_balances",
      "cycle_counts",
      "returns_management",
      "landed_cost",
      "logistics_tms",
      "statutory_logistics",
      "shipping_engine",
      "sales_orders",
      "customer_portal",
      "finance",
    ],
  },
  discrete_manufacturing: {
    label: "Discrete Manufacturing & Assembly",
    description: "Focused on manufacturing execution: BOMs, work orders, MRP, IPQC, subcontracting, and batch traceability.",
    modules: [
      "planning_mrp",
      "procurement",
      "avl_governance",
      "warehouse_grn_qc",
      "inventory_balances",
      "cycle_counts",
      "mfg_production",
      "mfg_subcontracting",
      "mfg_traceability",
      "quality_ipqc",
      "capacity_planning",
      "sales_orders",
      "finance",
      "sc_control_tower",
    ],
  },
  logistics_3pl: {
    label: "Logistics, 3PL & Fulfillment",
    description: "Optimized for warehouse logistics: WMS bins, wave picking, courier shipping engine, and statutory e-Way Bills.",
    modules: [
      "warehouse_grn_qc",
      "inventory_balances",
      "cycle_counts",
      "wms_bins",
      "wms_mobile",
      "wave_picking",
      "returns_management",
      "logistics_tms",
      "freight_tms",
      "statutory_logistics",
      "shipping_engine",
      "sales_orders",
      "customer_portal",
      "finance",
    ],
  },
  lean_procurement: {
    label: "Lean Direct Procurement & Finance",
    description: "For service or operational businesses requiring requisitions, PO approval workflows, 3-way matching, and AP invoicing.",
    modules: [
      "procurement",
      "sourcing_rfq",
      "blanket_po",
      "warehouse_grn_qc",
      "inventory_balances",
      "finance",
    ],
  },
};
