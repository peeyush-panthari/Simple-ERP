export interface UpperlineConnect {
  nodeId: string;
  sourceModule: string;
  label: string;
  dataPassed: string;
  isHardDependency: boolean;
}

export interface DownlineConnect {
  nodeId: string;
  targetModule: string;
  label: string;
  dataPassed: string;
  isTrigger: boolean;
}

export interface MasterWorkflowValidation {
  name: string;
  rule: string;
  errorCode?: string;
  severity: "Hard Blocker (422/409)" | "Approval Escalation" | "Warning Alert";
}

export type EnterpriseStream =
  | "Procure-to-Pay"
  | "Plan-to-Produce"
  | "Order-to-Cash"
  | "Warehouse & WMS"
  | "Finance & Accounting"
  | "Governance";

export interface EnterpriseWorkflowNode {
  id: string;
  code: string;
  title: string;
  module: string;
  moduleId: string;
  stream: EnterpriseStream;
  stageOrder: number; // 1 to 6 (Pipeline Column)
  actor: string;
  actorRole: string;
  summary: string;
  inputDocuments: string[];
  outputDocuments: string[];
  upperlineConnects: UpperlineConnect[];
  downlineConnects: DownlineConnect[];
  keyValidations: MasterWorkflowValidation[];
  ledgerImpact: string;
  failureImpact: string;
}

export const STREAM_METADATA: Record<
  EnterpriseStream,
  { label: string; color: string; badgeClass: string; borderClass: string; bgClass: string; icon: string; description: string }
> = {
  "Procure-to-Pay": {
    label: "Procure-to-Pay (P2P)",
    color: "#0f766e", // teal-700
    badgeClass: "bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20",
    borderClass: "border-teal-500",
    bgClass: "bg-teal-500/5",
    icon: "ShoppingCart",
    description: "Requisitions, multi-vendor RFQs, PO tier approvals, vendor ASN notices, and payment settlement",
  },
  "Plan-to-Produce": {
    label: "Plan-to-Produce (Manufacturing)",
    color: "#6d28d9", // purple-700
    badgeClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20",
    borderClass: "border-purple-500",
    bgClass: "bg-purple-500/5",
    icon: "Factory",
    description: "Multi-level BOM engineering, demand forecasting, MRP explosions, component backflushing, and serialized FG",
  },
  "Order-to-Cash": {
    label: "Order-to-Cash (O2C)",
    color: "#b45309", // amber-700
    badgeClass: "bg-amber-500/10 text-amber-800 dark:text-amber-200 border border-amber-500/20",
    borderClass: "border-amber-500",
    bgClass: "bg-amber-500/5",
    icon: "ClipboardList",
    description: "Sales orders, automated credit limit audits, row-locked FIFO allocation, wave picking, shipping, and customer invoicing",
  },
  "Warehouse & WMS": {
    label: "Warehouse, Receiving & WMS",
    color: "#1d4ed8", // blue-700
    badgeClass: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20",
    borderClass: "border-blue-500",
    bgClass: "bg-blue-500/5",
    icon: "Warehouse",
    description: "Dock inward, mandatory QC disposition, directed bin putaway, double-entry stock ledgers, and cycle counts",
  },
  "Finance & Accounting": {
    label: "Finance & Accounting Control",
    color: "#047857", // emerald-700
    badgeClass: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20",
    borderClass: "border-emerald-500",
    bgClass: "bg-emerald-500/5",
    icon: "Receipt",
    description: "Automated 3-Way Matching, AP vendor billing, AR customer collections, landed cost apportionment, and GL balance",
  },
  Governance: {
    label: "System Administration & Governance",
    color: "#334155", // slate-700
    badgeClass: "bg-slate-500/10 text-slate-700 dark:text-slate-300 border border-slate-500/20",
    borderClass: "border-slate-500",
    bgClass: "bg-slate-500/5",
    icon: "ShieldCheck",
    description: "RBAC least-privilege matrix, facility access scoping, per-purpose email SMTP queues, and immutable audit logs",
  },
};

export const ENTERPRISE_MASTER_FLOWCHART: EnterpriseWorkflowNode[] = [
  // -------------------------------------------------------------
  // STAGE 1: DEMAND INITIATION, MASTER DATA & BOM ENGINEERING
  // -------------------------------------------------------------
  {
    id: "BOM_MANAGE",
    code: "MFG-01",
    title: "BOM Engineering & Version Approval",
    module: "Manufacturing & Operations",
    moduleId: "manufacturing",
    stream: "Plan-to-Produce",
    stageOrder: 1,
    actor: "Process Engineer",
    actorRole: "bom:write / bom:approve",
    summary:
      "Defines multi-level Bill of Materials hierarchy, raw material component ratios, scrap factor percentages, and routing stages with strict approval lock.",
    inputDocuments: ["Engineering Drawings", "Component Catalog", "Engineering Change Notice (ECN)"],
    outputDocuments: ["Approved BOM Version (BOM-v1, BOM-v2)"],
    upperlineConnects: [
      {
        nodeId: "RBAC_GOVERN",
        sourceModule: "Administration",
        label: "Engineering Authority Check",
        dataPassed: "User permissions: bom:write, bom:approve",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "MRP_EXPLODE",
        targetModule: "Planning & SCM",
        label: "Detonates Component Requirements",
        dataPassed: "Parent SKU, Child Component Ratios, Scrap %",
        isTrigger: true,
      },
      {
        nodeId: "PROD_SCHEDULE",
        targetModule: "Manufacturing",
        label: "Active Assembly Recipe",
        dataPassed: "Approved BOM Version ID, Routing Stages",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "No Circular BOM References",
        rule: "Parent finished good SKU cannot exist as a child or sub-assembly at any depth in its tree.",
        errorCode: "BOM_CIRCULAR_DEPENDENCY",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Component Active Status Guard",
        rule: "All child components must exist as active products in the system catalog.",
        errorCode: "COMPONENT_INACTIVE",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "No immediate ledger entry; sets standard cost foundation for inventory valuation.",
    failureImpact: "Engineering edits rejected; invalid BOM versions cannot be scheduled for manufacturing runs.",
  },

  {
    id: "FORECAST",
    code: "PLN-01",
    title: "Demand Forecasting & Master Schedule",
    module: "Planning, MRP & SCM",
    moduleId: "planning",
    stream: "Plan-to-Produce",
    stageOrder: 1,
    actor: "Demand Planner",
    actorRole: "forecasting:write",
    summary:
      "Combines historical consumption patterns, seasonal trends, and open customer orders using statistical models (Holt-Winters, moving averages) to build the unconstrained Master Production Schedule (MPS).",
    inputDocuments: ["Sales Order History", "Market Forecast Plan", "Customer Backorders"],
    outputDocuments: ["Demand Forecast Scenario", "Master Production Schedule (MPS)"],
    upperlineConnects: [
      {
        nodeId: "SO_BOOK",
        sourceModule: "Sales & Orders",
        label: "Historical & Firm Order Intake",
        dataPassed: "Confirmed Order Quantities, Delivery Due Dates, Customer Trends",
        isHardDependency: false,
      },
    ],
    downlineConnects: [
      {
        nodeId: "DRP_PLAN",
        targetModule: "Planning & SCM",
        label: "Multi-Warehouse Demand Distribution",
        dataPassed: "Regional SKU demand, Safety stock thresholds",
        isTrigger: true,
      },
      {
        nodeId: "MRP_EXPLODE",
        targetModule: "Planning & SCM",
        label: "Gross Demand Detonation",
        dataPassed: "Target Finished Good Quantities, Horizon Weeks",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Planning Horizon Boundaries",
        rule: "Forecast horizon must be bounded between 1 and 52 weeks.",
        errorCode: "FORECAST_HORIZON_INVALID",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "Planning forecast model only; no general ledger impact.",
    failureImpact: "Under-forecasting leads to stockouts; over-forecasting leads to working capital lockup.",
  },

  {
    id: "DRP_PLAN",
    code: "PLN-02",
    title: "Distribution Requirements Planning (DRP)",
    module: "Planning, MRP & SCM",
    moduleId: "planning",
    stream: "Plan-to-Produce",
    stageOrder: 1,
    actor: "Logistics Planner",
    actorRole: "drp:write",
    summary:
      "Calculates multi-echelon inventory balancing across central Mother Hubs and regional Spoke Warehouses to prevent stockouts based on local lead times.",
    inputDocuments: ["Forecast Demand per Region", "Warehouse Safety Stock Settings"],
    outputDocuments: ["DRP Replenishment Schedule", "Planned Transfer Requisitions"],
    upperlineConnects: [
      {
        nodeId: "FORECAST",
        sourceModule: "Planning & SCM",
        label: "Regional Demand Input",
        dataPassed: "SKU demand schedule per territory",
        isHardDependency: true,
      },
      {
        nodeId: "STOCK_LEDGER",
        sourceModule: "Inventory Management",
        label: "Current Hub & Spoke Balances",
        dataPassed: "On-Hand Stock, In-Transit Balances, Reserved Qty",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "STOCK_TRANSFER",
        targetModule: "Inventory Management",
        label: "Executes Inter-Warehouse Movements",
        dataPassed: "Source Hub ID, Destination Spoke ID, Transfer Qty",
        isTrigger: true,
      },
      {
        nodeId: "MRP_EXPLODE",
        targetModule: "Planning & SCM",
        label: "Aggregate Central Manufacturing Demand",
        dataPassed: "Consolidated Mother Hub net requirements",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Transit Lead-Time Offsetting",
        rule: "Transfer ship date = Requirement date - Inter-warehouse transit days.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Generates planned stock transfer recommendations.",
    failureImpact: "Regional spoke warehouse faces stockout while central hub holds idle inventory.",
  },

  // -------------------------------------------------------------
  // STAGE 2: REQUIREMENTS EXPLOSION & DEMAND INITIATION
  // -------------------------------------------------------------
  {
    id: "MRP_EXPLODE",
    code: "PLN-03",
    title: "Gross-to-Net MRP Explosion",
    module: "Planning, MRP & SCM",
    moduleId: "planning",
    stream: "Plan-to-Produce",
    stageOrder: 2,
    actor: "MRP Engine / SC Planner",
    actorRole: "mrp:read / inventory:read",
    summary:
      "Performs algorithmic Gross-to-Net calculation: explodes active BOMs, nets against On-Hand stock and incoming PO receipts, offsets supplier lead times, and creates planned orders.",
    inputDocuments: ["Master Production Schedule", "Active Approved BOMs", "Current Stock Balances", "Open PO Pipeline"],
    outputDocuments: ["Planned Purchase Orders (Buy)", "Planned Work Orders (Make)"],
    upperlineConnects: [
      {
        nodeId: "FORECAST",
        sourceModule: "Planning & SCM",
        label: "Gross Demand Schedule",
        dataPassed: "Finished Good Requirements, Timeline",
        isHardDependency: true,
      },
      {
        nodeId: "BOM_MANAGE",
        sourceModule: "Manufacturing",
        label: "BOM Component Explosion",
        dataPassed: "Child components, UOM ratios, Scrap %",
        isHardDependency: true,
      },
      {
        nodeId: "STOCK_LEDGER",
        sourceModule: "Inventory Management",
        label: "Nets Against Available Inventory",
        dataPassed: "On-Hand Stock, Allocated Stock, Safety Stock",
        isHardDependency: true,
      },
      {
        nodeId: "PO_ISSUE",
        sourceModule: "Procurement",
        label: "Nets Against Scheduled Inbound PO Receipts",
        dataPassed: "Open PO Quantities, Promised Delivery Dates",
        isHardDependency: false,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PR_RAISE",
        targetModule: "Procurement",
        label: "Converts Raw Material Shortages to PRs",
        dataPassed: "Raw Material SKU, Net Shortage Qty, Required Order Date",
        isTrigger: true,
      },
      {
        nodeId: "PROD_SCHEDULE",
        targetModule: "Manufacturing",
        label: "Converts Finished Good Shortages to Runs",
        dataPassed: "FG SKU, Target Batch Qty, Planned Start Date",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Gross-to-Net Conservation Formula",
        rule: "Net Requirement = Gross Demand - (On Hand + Scheduled Inbound Receipts - Allocated - Safety Stock).",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Supplier Minimum Order Qty (MOQ)",
        rule: "Suggested planned order quantity must round up to the vendor MOQ and batch multiples.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "Creates planned order suggestions; no physical ledger mutation.",
    failureImpact: "Incorrect material procurement resulting in line stoppages or excess raw inventory.",
  },

  {
    id: "PR_RAISE",
    code: "PROC-01",
    title: "Purchase Requisition Creation",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 2,
    actor: "Employee / SC Planner",
    actorRole: "pr:write",
    summary:
      "Raises formal internal demand for goods. Can be auto-generated by MRP or created manually by staff. Captures needed-by date, destination warehouse, department, and mandatory justification.",
    inputDocuments: ["MRP Planned Orders", "Internal Material Request"],
    outputDocuments: ["Purchase Requisition (PR-0001) in 'submitted' status"],
    upperlineConnects: [
      {
        nodeId: "MRP_EXPLODE",
        sourceModule: "Planning & SCM",
        label: "Automated Net Shortage Trigger",
        dataPassed: "Target SKU, Shortage Qty, Warehouse ID",
        isHardDependency: false,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PR_APPROVE",
        targetModule: "Procurement",
        label: "Routes to Manager Approval",
        dataPassed: "PR ID, Requester ID, Department, Estimated Cost",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Positive Quantity Check",
        rule: "Line quantities must be strictly positive numbers (> 0).",
        errorCode: "PR_VALIDATION_FAILED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Mandatory Business Reason",
        rule: "Submission requires non-empty business justification text.",
        errorCode: "PR_REASON_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Needed-By Date Validity",
        rule: "Needed-by delivery date must be today or in the future.",
        errorCode: "PR_INVALID_DATE",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Creates uncommitted demand record; no financial ledger entry.",
    failureImpact: "Requisition rejected; items cannot be sourced or purchased.",
  },

  {
    id: "PR_APPROVE",
    code: "PROC-02",
    title: "Requisition Manager & Purchase Review",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 2,
    actor: "Reporting Manager & Central Buyer",
    actorRole: "pr:team_approve / pr:approve",
    summary:
      "Two-phase approval gate: first routes to the requester's direct reporting manager ('reports_to_user_id'), followed by Central Purchase Department review.",
    inputDocuments: ["Submitted Purchase Requisition", "Department Budget"],
    outputDocuments: ["Approved Purchase Requisition ('approved')"],
    upperlineConnects: [
      {
        nodeId: "PR_RAISE",
        sourceModule: "Procurement",
        label: "Submitted Requisition",
        dataPassed: "PR Details, Line Items, Cost Estimate",
        isHardDependency: true,
      },
      {
        nodeId: "RBAC_GOVERN",
        sourceModule: "Administration",
        label: "Reporting Hierarchy Verification",
        dataPassed: "Requester reports_to_user_id mapping",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "RFQ_SOURCING",
        targetModule: "Procurement",
        label: "Initiates Sourcing Event (if competitive bidding needed)",
        dataPassed: "Approved PR line items, Needed-by dates",
        isTrigger: false,
      },
      {
        nodeId: "PO_ISSUE",
        targetModule: "Procurement",
        label: "Direct PO Creation (if contracted vendor exists)",
        dataPassed: "Approved PR lines, Deliver-to warehouse",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "No Self-Approval Prohibited",
        rule: "Requester ID cannot equal Approver ID. Users cannot approve their own PRs.",
        errorCode: "PR_SELF_APPROVAL_PROHIBITED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Mandatory Rejection Feedback",
        rule: "Rejecting a PR requires entering a clear explanation for the requester.",
        errorCode: "PR_REASON_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "No financial GL entry; flags requisition as approved for corporate expenditure.",
    failureImpact: "Requisition blocked or returned to draft; buying process halts.",
  },

  {
    id: "SO_BOOK",
    code: "ORD-01",
    title: "Customer Sales Order Booking",
    module: "Sales & Order Fulfillment",
    moduleId: "orders",
    stream: "Order-to-Cash",
    stageOrder: 2,
    actor: "Sales Rep / Customer Portal",
    actorRole: "order:write",
    summary:
      "Captures customer purchase commitment with SKU lines, contracted prices, shipping address, GST jurisdiction, and delivery terms.",
    inputDocuments: ["Customer PO / Quotation", "Price List", "Party Master Record"],
    outputDocuments: ["Sales Order (SO-1001) in 'draft' or 'confirmed'"],
    upperlineConnects: [
      {
        nodeId: "RBAC_GOVERN",
        sourceModule: "Administration",
        label: "Sales Rep Permissions Check",
        dataPassed: "Role permission: order:write",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "CREDIT_CHECK",
        targetModule: "Sales & Finance",
        label: "Mandatory Financial Risk Audit",
        dataPassed: "Customer ID, Order Total, Current Open AR Exposure",
        isTrigger: true,
      },
      {
        nodeId: "FORECAST",
        targetModule: "Planning & SCM",
        label: "Firm Order Demand Ingestion",
        dataPassed: "SKUs, Quantities, Delivery Timelines",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Active Customer Master Check",
        rule: "Customer party must have type='customer' or 'both', status='active', and not blocked.",
        errorCode: "CUSTOMER_BLOCKED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Statutory Tax Jurisdiction Match",
        rule: "Shipping address state code must correctly drive CGST+SGST vs IGST tax split.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Records unfulfilled sales backlog; no revenue recognized until shipment.",
    failureImpact: "Order cannot be confirmed; inventory cannot be allocated.",
  },

  {
    id: "CREDIT_CHECK",
    code: "ORD-02",
    title: "Automated Credit Limit & Overdue Audit",
    module: "Sales & Finance",
    moduleId: "orders",
    stream: "Order-to-Cash",
    stageOrder: 2,
    actor: "Credit Control Engine",
    actorRole: "order:confirm / finance:read",
    summary:
      "Verifies customer's total financial exposure: checks approved credit limit against unpaid Accounts Receivable plus unbilled open orders. Also flags overdue overdue invoices.",
    inputDocuments: ["Sales Order Total", "Customer Credit Limit", "AR Aging Subledger"],
    outputDocuments: ["Credit Audit Sign-Off ('cleared' or 'credit_hold')"],
    upperlineConnects: [
      {
        nodeId: "SO_BOOK",
        sourceModule: "Sales & Orders",
        label: "Sales Order Total Value",
        dataPassed: "Customer ID, Order Gross Amount",
        isHardDependency: true,
      },
      {
        nodeId: "AR_INVOICE",
        sourceModule: "Finance & Accounts Receivable",
        label: "Open Unpaid Receivables Balance",
        dataPassed: "Outstanding AR Invoices, Days Past Due",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "STOCK_ALLOC",
        targetModule: "Sales & Orders",
        label: "Clears Order for Stock Reservation",
        dataPassed: "Cleared Order ID, Allocation Priority",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Credit Exposure Ceiling Guard",
        rule: "Current Unpaid AR + Order Value <= Customer Approved Credit Limit.",
        errorCode: "CREDIT_LIMIT_EXCEEDED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Overdue Aging Threshold",
        rule: "Customer cannot have invoices overdue > 60 days without Finance Controller waiver.",
        errorCode: "CUSTOMER_OVERDUE_BLOCK",
        severity: "Approval Escalation",
      },
    ],
    ledgerImpact: "Increases soft credit exposure against customer master.",
    failureImpact: "Order placed on 'Credit Hold'; warehouse picking and allocation strictly frozen.",
  },

  // -------------------------------------------------------------
  // STAGE 3: SOURCING, CONTRACTING & WORK ORDER SCHEDULING
  // -------------------------------------------------------------
  {
    id: "RFQ_SOURCING",
    code: "PROC-03",
    title: "Sourcing RFQ & Multi-Vendor Bidding",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 3,
    actor: "Sourcing Specialist / Buyer",
    actorRole: "sourcing:write",
    summary:
      "Selects multiple approved suppliers from the Supplier Directory. Sends automated RFQ invitation emails with secure login-free quotation submission links.",
    inputDocuments: ["Approved PR Lines", "Approved Vendor List (AVL)"],
    outputDocuments: ["Purchase RFQ (PRFQ-0001) with Vendor Quotations"],
    upperlineConnects: [
      {
        nodeId: "PR_APPROVE",
        sourceModule: "Procurement",
        label: "Approved Requisition Lines",
        dataPassed: "SKUs, Target Quantities, Spec Sheets",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "RFQ_AWARD",
        targetModule: "Procurement",
        label: "Feeds Vendor Quotes for Comparative Evaluation",
        dataPassed: "Vendor Quotations (Price, GST %, Freight, Lead Time)",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Approved Vendor List (AVL) Compliance",
        rule: "Invited suppliers must be qualified on the AVL with valid compliance certificates.",
        errorCode: "VENDOR_NOT_IN_AVL",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Minimum Bidder Count Rule",
        rule: "Competitive bidding requires inviting at least 2 active vendors unless sole-source waiver exists.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "No financial impact; logs price discovery records.",
    failureImpact: "Vendor cannot submit bids; sourcing event remains in open draft.",
  },

  {
    id: "RFQ_AWARD",
    code: "PROC-04",
    title: "Landed Quotation Comparison & Award",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 3,
    actor: "Sourcing Committee / Lead Buyer",
    actorRole: "sourcing:award",
    summary:
      "Evaluates quotations side-by-side on true landed cost (Base Price + GST + Freight). Pre-selects lowest bidder per item. Enforces mandatory justification for non-lowest awards.",
    inputDocuments: ["Submitted Vendor Quotations", "Freight Quotations"],
    outputDocuments: ["Awarded RFQ Lines with Audit Justification Logs"],
    upperlineConnects: [
      {
        nodeId: "RFQ_SOURCING",
        sourceModule: "Procurement",
        label: "Vendor Quotations",
        dataPassed: "Rates, Validity Dates, Payment Terms",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PO_ISSUE",
        targetModule: "Procurement",
        label: "Auto-Generates Purchase Orders",
        dataPassed: "Winning Vendor IDs, Awarded Item Lines, Quoted Prices & Terms",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Non-Lowest Quote Justification",
        rule: "Awarding a line to a higher-priced quote strictly mandates a non-empty audit justification text.",
        errorCode: "AWARD_JUSTIFICATION_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Quotation Expiry Check",
        rule: "Quotation validity timestamp must not have elapsed.",
        errorCode: "QUOTATION_EXPIRED",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "No financial ledger entry; creates legally binding procurement award.",
    failureImpact: "Award blocked; purchase orders cannot be auto-generated.",
  },

  {
    id: "PO_ISSUE",
    code: "PROC-05",
    title: "Purchase Order Issuance & Tier Approval",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 3,
    actor: "Purchase Manager / Approver",
    actorRole: "po:write / po:approve",
    summary:
      "Generates legal POs linked to tenant business entities. Enforces multi-tier approval thresholds (L1: ₹50K, L2: ₹2.5L, L3: ₹10L). Renders PDF and updates committed spend ledger.",
    inputDocuments: ["Awarded RFQ Lines / Approved PR", "Business Entity Master", "Vendor Master"],
    outputDocuments: ["Purchase Order (PO-3001) in 'issued' status", "Official PO PDF"],
    upperlineConnects: [
      {
        nodeId: "RFQ_AWARD",
        sourceModule: "Procurement",
        label: "Awarded Pricing & Vendor",
        dataPassed: "Vendor ID, Item Rates, Terms, Quantities",
        isHardDependency: false,
      },
      {
        nodeId: "PR_APPROVE",
        sourceModule: "Procurement",
        label: "Direct Approved PR Conversion",
        dataPassed: "PR Lines, Deliver-to Warehouse",
        isHardDependency: false,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PO_VENDOR_ACK",
        targetModule: "Procurement",
        label: "Transmits PO to Supplier for Acknowledgement",
        dataPassed: "PO PDF, Line Item Specifications, Delivery Due Date",
        isTrigger: true,
      },
      {
        nodeId: "THREE_WAY_MATCH",
        targetModule: "Finance & Accounting",
        label: "Provides Contracted Rates for 3-Way Match",
        dataPassed: "PO Number, Line Unit Prices, Payment Terms",
        isTrigger: false,
      },
      {
        nodeId: "GATE_INWARD",
        targetModule: "Warehouse & GRN",
        label: "Opens Inbound Receiving Line Balance",
        dataPassed: "PO Number, SKU, Ordered Quantity, Open Balance",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "PO Value Tier Approval Guard",
        rule: "Orders exceeding Tier thresholds (L1/L2/L3) mandate approval by authorized management roles.",
        errorCode: "PO_TIER_APPROVAL_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Active Business Entity GSTIN",
        rule: "PO must be linked to a registered tenant Business Entity with GSTIN matching delivery jurisdiction.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Updates Committed Spend Ledger in Finance against department budget.",
    failureImpact: "PO stays in unissued draft; supplier cannot ship; warehouse cannot receive goods.",
  },

  {
    id: "PROD_SCHEDULE",
    code: "MFG-02",
    title: "Production Run / Work Order Scheduling",
    module: "Manufacturing & Operations",
    moduleId: "manufacturing",
    stream: "Plan-to-Produce",
    stageOrder: 3,
    actor: "Production Planner",
    actorRole: "inventory:produce",
    summary:
      "Schedules discrete manufacturing work orders for finished goods. Verifies active approved BOM version, allocates factory line capacity, and verifies raw component availability.",
    inputDocuments: ["MRP Planned Orders", "Active Approved BOM", "Shop-Floor Shift Calendar"],
    outputDocuments: ["Production Run (WO-5001) in 'planned' status"],
    upperlineConnects: [
      {
        nodeId: "MRP_EXPLODE",
        sourceModule: "Planning & SCM",
        label: "Net Manufacturing Requirements",
        dataPassed: "FG SKU, Planned Batch Quantity, Start Date",
        isHardDependency: false,
      },
      {
        nodeId: "BOM_MANAGE",
        sourceModule: "Manufacturing",
        label: "Assembly Structure & Routing Stages",
        dataPassed: "Active BOM Version ID, Component ratios",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "MATERIAL_ISSUE",
        targetModule: "Manufacturing & Inventory",
        label: "Issues Raw Components to Line",
        dataPassed: "Run ID, BOM Component SKU List, Required Quantities",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Active BOM Version Requirement",
        rule: "Target product must have at least one currently active, approved BOM version.",
        errorCode: "NO_ACTIVE_BOM",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Factory Capacity Availability",
        rule: "Work center finite capacity must not be over-committed on target shift.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "Creates work order plan; no physical inventory movement.",
    failureImpact: "Shop-floor work order cannot be released; production line remains idle.",
  },

  {
    id: "STOCK_ALLOC",
    code: "ORD-03",
    title: "Row-Locked FIFO/FEFO Stock Allocation",
    module: "Sales & Order Fulfillment",
    moduleId: "orders",
    stream: "Order-to-Cash",
    stageOrder: 3,
    actor: "Allocation Engine",
    actorRole: "order:allocate",
    summary:
      "Executes row-locked automated allocation against available finished goods. Employs FIFO (First-In, First-Out) or FEFO (First-Expired, First-Out) rules. Prevents race conditions.",
    inputDocuments: ["Confirmed Sales Order", "Available Stock Balances"],
    outputDocuments: ["Allocated Sales Order", "Finished Good Allocation Rows"],
    upperlineConnects: [
      {
        nodeId: "CREDIT_CHECK",
        sourceModule: "Sales & Finance",
        label: "Credit Clearance",
        dataPassed: "Approved Sales Order ID",
        isHardDependency: true,
      },
      {
        nodeId: "STOCK_LEDGER",
        sourceModule: "Inventory Management",
        label: "Available Unreserved Inventory",
        dataPassed: "SKU, Serial IDs, Location Bins, Expiry Dates",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "WAVE_PICK",
        targetModule: "Warehouse & Sales",
        label: "Queues Items for Physical Warehouse Picking",
        dataPassed: "Allocated Serial IDs, Storage Bin Locations, Order Lines",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Available to Promise (ATP) Stock Sufficiency",
        rule: "Allocated quantity <= (On Hand - Already Allocated - Quarantine).",
        errorCode: "INSUFFICIENT_STOCK_TO_ALLOCATE",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Postgres Row Lock Concurrency",
        rule: "Uses SELECT ... FOR UPDATE on inventory balance rows to prevent double-allocation.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Increases 'Allocated' count in Stock Balance; decreases 'Available for Sale' count.",
    failureImpact: "Order placed in backorder queue; picking cannot commence until new stock arrives.",
  },

  // -------------------------------------------------------------
  // STAGE 4: INBOUND SHIPPING, MATERIAL ISSUE & WAREHOUSE PICKING
  // -------------------------------------------------------------
  {
    id: "PO_VENDOR_ACK",
    code: "PROC-06",
    title: "Vendor Acknowledgement & Document Compliance",
    module: "Procurement & Sourcing",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 4,
    actor: "Buyer / Vendor Portal User",
    actorRole: "po:vendor",
    summary:
      "Captures supplier's formal acceptance of the PO, delivery date confirmations, and compliance document uploads (Proforma Invoice, Certificate of Analysis CoA, MSDS).",
    inputDocuments: ["Issued Purchase Order", "Vendor Order Confirmation", "Quality Certificates"],
    outputDocuments: ["PO Status 'acknowledged' / 'acknowledged_with_changes'", "Stored Vendor Documents"],
    upperlineConnects: [
      {
        nodeId: "PO_ISSUE",
        sourceModule: "Procurement",
        label: "Issued PO",
        dataPassed: "PO Number, Specifications, Delivery Timeline",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "ASN_DISPATCH",
        targetModule: "Procurement & Logistics",
        label: "Unlocks Inbound Shipment Creation",
        dataPassed: "Confirmed delivery quantities and schedules",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Delivery Date Confirmation Guard",
        rule: "Confirmed vendor delivery date cannot exceed PO needed-by date without buyer concurrence.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "Updates supplier delivery commitment in supplier scorecard analytics.",
    failureImpact: "Buyer alerted to vendor exceptions; potential PO amendment required.",
  },

  {
    id: "ASN_DISPATCH",
    code: "PROC-07",
    title: "Vendor Inbound Dispatch Notice (ASN)",
    module: "Procurement & Logistics",
    moduleId: "procurement",
    stream: "Procure-to-Pay",
    stageOrder: 4,
    actor: "Buyer / Logistics Coordinator",
    actorRole: "po:vendor / logistics:write",
    summary:
      "Records supplier's outbound shipment from their factory: captures vehicle number, transporter name, LR/AWB docket, packing slip, and statutory e-Way Bill.",
    inputDocuments: ["Vendor Tax Invoice", "Packing List", "Transporter Lorry Receipt (LR)"],
    outputDocuments: ["PO Inbound Dispatch Record in 'in_transit' status"],
    upperlineConnects: [
      {
        nodeId: "PO_VENDOR_ACK",
        sourceModule: "Procurement",
        label: "Acknowledged PO",
        dataPassed: "PO Lines, Open Balance",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "GATE_INWARD",
        targetModule: "Warehouse & GRN",
        label: "Enables Dock Gate Security Inward",
        dataPassed: "Vehicle Number, Transporter LR, Vendor Invoice No, Expected Due Date",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Over-Dispatch Prevention",
        rule: "Total dispatched quantity cannot exceed open balance on the purchase order.",
        errorCode: "PO_OVER_DISPATCH_BREACH",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "High-Value Statutory e-Way Bill Check",
        rule: "Consignments with invoice value > ₹50,000 display warning if 12-digit e-Way bill is omitted.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "PO open quantity marked as 'In Transit' from vendor.",
    failureImpact: "Warehouse cannot match arriving truck against open inbound dispatch.",
  },

  {
    id: "MATERIAL_ISSUE",
    code: "MFG-03",
    title: "Raw Material Issue & Component Backflushing",
    module: "Manufacturing & Inventory",
    moduleId: "manufacturing",
    stream: "Plan-to-Produce",
    stageOrder: 4,
    actor: "Line Supervisor / Store Keeper",
    actorRole: "inventory:produce",
    summary:
      "Issues required raw material lots from warehouse to shop floor. Decrements stock ledger raw materials, prevents negative balances, and debits Work in Progress (WIP).",
    inputDocuments: ["Scheduled Work Order", "BOM Pick List"],
    outputDocuments: ["Material Issue Slip", "Production Consumption Journal"],
    upperlineConnects: [
      {
        nodeId: "PROD_SCHEDULE",
        sourceModule: "Manufacturing",
        label: "Scheduled Work Order",
        dataPassed: "Target Batch Qty, BOM Component List",
        isHardDependency: true,
      },
      {
        nodeId: "STOCK_LEDGER",
        sourceModule: "Inventory Management",
        label: "Available Raw Materials",
        dataPassed: "Lot IDs, Serial Numbers, Bin Locations",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "IPQC_STAGE",
        targetModule: "Manufacturing",
        label: "Releases Physical Parts to Assembly Stations",
        dataPassed: "Issued lot numbers, Work Order ID",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Component Stock Sufficiency",
        rule: "Warehouse unreserved inventory must equal or exceed BOM requirement * batch size.",
        errorCode: "INSUFFICIENT_COMPONENT_STOCK",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Strict Negative Inventory Guard",
        rule: "Stock balance for any raw material SKU cannot drop below zero.",
        errorCode: "NEGATIVE_INVENTORY_PROHIBITED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "CREDIT: Raw Material Inventory (Asset) / DEBIT: Work in Progress (WIP).",
    failureImpact: "Production run cannot start; assembly line halted due to raw material shortage.",
  },

  {
    id: "WAVE_PICK",
    code: "WMS-01",
    title: "Warehouse Wave & Batch Picking",
    module: "Warehouse & WMS",
    moduleId: "orders",
    stream: "Order-to-Cash",
    stageOrder: 4,
    actor: "Warehouse Picker",
    actorRole: "order:pack / warehouse:read",
    summary:
      "Consolidates allocated order lines into optimized picking waves. Generates travel-path sequenced pick tasks for mobile RF scanners or pick carts.",
    inputDocuments: ["Allocated Sales Orders", "Warehouse Bin Topology Map"],
    outputDocuments: ["Pick Wave List", "Staged Cartons at Packing Station"],
    upperlineConnects: [
      {
        nodeId: "STOCK_ALLOC",
        sourceModule: "Sales & Orders",
        label: "Allocated Order Lines",
        dataPassed: "Order ID, SKU, Serial IDs, Allocated Quantities",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PACK_CARTON",
        targetModule: "Sales & Orders",
        label: "Physical Units Delivered to Packing Bench",
        dataPassed: "Picked item barcodes, Staged Tote ID",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Barcode Scan Verification",
        rule: "Physical scan of item barcode must exactly match the allocated lot/serial ID.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Changes item physical location from Storage Bin to Staging / Packing Bay.",
    failureImpact: "Incorrect item picked; packing verification halts until discrepancy resolved.",
  },

  {
    id: "PACK_CARTON",
    code: "ORD-04",
    title: "Carton Packing & Weighment",
    module: "Sales & Order Fulfillment",
    moduleId: "orders",
    stream: "Order-to-Cash",
    stageOrder: 4,
    actor: "Packing Bench Operator",
    actorRole: "order:pack",
    summary:
      "Packs picked goods into shipping cartons. Records gross package weight (kg), dimensions (LxWxH), inserts packing slip, and seals boxes.",
    inputDocuments: ["Picked Items", "Carton Barcode"],
    outputDocuments: ["Packing Slip", "Package Dimension & Weight Manifest"],
    upperlineConnects: [
      {
        nodeId: "WAVE_PICK",
        sourceModule: "Warehouse & WMS",
        label: "Picked Goods Manifest",
        dataPassed: "Order lines, Verified Barcodes",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "TRANSPORT_REQ",
        targetModule: "Logistics TMS",
        label: "Transmits Freight Specs for Carrier Selection",
        dataPassed: "Package Count, Total Gross Weight, CBM Volume, Destination Pincode",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Pack Quantity Integrity",
        rule: "Packed quantity cannot exceed allocated quantity for any order line.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Items marked 'Packed'; inventory staged for carrier dispatch.",
    failureImpact: "Shipment delayed at dock; carrier label cannot be printed without weight.",
  },

  {
    id: "TRANSPORT_REQ",
    code: "LOG-01",
    title: "Transport Consolidation & Rate Shopping",
    module: "Logistics & Transportation (TMS)",
    moduleId: "logistics",
    stream: "Order-to-Cash",
    stageOrder: 4,
    actor: "Logistics Specialist",
    actorRole: "logistics:write / logistics:quote",
    summary:
      "Aggregates packed parcels into consolidated route shipments. Queries integrated courier APIs (Delhivery, BlueDart, FedEx) for real-time freight rates and transit lead times.",
    inputDocuments: ["Packed Order Manifests", "Carrier Tariff Rate Cards"],
    outputDocuments: ["Consolidated Transport Request", "Awarded Carrier Booking"],
    upperlineConnects: [
      {
        nodeId: "PACK_CARTON",
        sourceModule: "Sales & Orders",
        label: "Package Weights & Dimensions",
        dataPassed: "Weight kg, Volumetric CBM, Destination Pincode",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "EWAY_DISPATCH",
        targetModule: "Logistics TMS",
        label: "Generates Shipping Label & Waybill",
        dataPassed: "Carrier Code, Service Type, Booking Reference",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Destination Pincode Serviceability",
        rule: "Destination postal code must be serviceable by selected carrier route.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Estimates freight expense commitment.",
    failureImpact: "Carrier label cannot be generated; box cannot leave the shipping bay.",
  },

  // -------------------------------------------------------------
  // STAGE 5: RECEIVING, INSPECTION, ASSEMBLY & INVOICING
  // -------------------------------------------------------------
  {
    id: "GATE_INWARD",
    code: "WH-01",
    title: "Dock Gate Inward & PO Line Counting",
    module: "Warehouse, GRN & QC",
    moduleId: "warehouse",
    stream: "Warehouse & WMS",
    stageOrder: 5,
    actor: "Receiving Clerk",
    actorRole: "warehouse:read / grn:write",
    summary:
      "Physical receipt of goods at warehouse inbound dock. Matches arriving vehicle with open PO dispatch, counts cartons, and enters received quantities into draft GRN.",
    inputDocuments: ["Transporter Delivery Challan", "Vendor Invoice", "PO Dispatch Notice"],
    outputDocuments: ["Draft Goods Receipt Note (GRN-2001) in 'under_qc'"],
    upperlineConnects: [
      {
        nodeId: "ASN_DISPATCH",
        sourceModule: "Procurement & Logistics",
        label: "Inbound Dispatch Notice",
        dataPassed: "Vehicle Number, LR Docket, Transporter Name",
        isHardDependency: true,
      },
      {
        nodeId: "PO_ISSUE",
        sourceModule: "Procurement",
        label: "Receivable PO Line Balance",
        dataPassed: "PO Number, Ordered Qty, Open Remaining Qty",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "QC_INSPECTION",
        targetModule: "Warehouse, GRN & QC",
        label: "Stages Goods in QC Quarantine Bay for Inspection",
        dataPassed: "GRN ID, Received Quantity, Batch Number, Vendor Invoice No",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Over-Receipt Tolerance Limit",
        rule: "Received quantity cannot exceed PO open balance + 5% allowable tolerance.",
        errorCode: "PO_OVER_RECEIPT_TOLERANCE_BREACH",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "PO Receivable Status Guard",
        rule: "PO must be in 'issued', 'acknowledged', or 'partial' status.",
        errorCode: "PO_NOT_RECEIVABLE",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Creates temporary receiving buffer; items NOT yet available for consumption.",
    failureImpact: "Receiving rejected at dock; driver directed back or PO amendment required.",
  },

  {
    id: "QC_INSPECTION",
    code: "WH-02",
    title: "Quality Control (QC) & Inspection Disposition",
    module: "Warehouse, GRN & QC",
    moduleId: "warehouse",
    stream: "Warehouse & WMS",
    stageOrder: 5,
    actor: "QC Engineer / Quality Manager",
    actorRole: "warehouse:read (QC Disposition) / grn:post",
    summary:
      "Inspects physical materials against technical specifications. Dispositions line into: Accepted Qty, Rejected Qty (with mandatory reason code), and Quarantine Qty. Posts final GRN.",
    inputDocuments: ["Draft GRN", "Product Spec Sheet", "Vendor CoA Test Certificate"],
    outputDocuments: ["Posted GRN Record", "Inspection Sign-Off Sheet"],
    upperlineConnects: [
      {
        nodeId: "GATE_INWARD",
        sourceModule: "Warehouse, GRN & QC",
        label: "Dock Received Materials",
        dataPassed: "GRN ID, Received Units, Batch/Lot Number",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PUTAWAY_BINS",
        targetModule: "Warehouse & WMS",
        label: "Releases Accepted Units for Putaway",
        dataPassed: "Accepted SKU, Lot ID, Quantity, Quality Status",
        isTrigger: true,
      },
      {
        nodeId: "STOCK_LEDGER",
        targetModule: "Inventory Management",
        label: "Posts Double-Entry Stock Ledger Journals",
        dataPassed: "Increases On-Hand Balance, Updates Moving Average Cost",
        isTrigger: true,
      },
      {
        nodeId: "THREE_WAY_MATCH",
        targetModule: "Finance & Accounting",
        label: "Provides Certified Accepted Quantities for Billing",
        dataPassed: "GRN Number, Vendor Invoice No, Accepted Line Quantities",
        isTrigger: true,
      },
      {
        nodeId: "CREDIT_NOTE",
        targetModule: "Finance & Returns",
        label: "Triggers Return to Vendor (RTV) for Rejected Goods",
        dataPassed: "Rejected Quantities, Rejection Reason Code, Vendor ID",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Quantity Conservation Principle",
        rule: "Accepted Qty + Rejected Qty + Quarantine Qty must EXACTLY equal Received Qty.",
        errorCode: "QC_QTY_MISMATCH",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Mandatory Rejection Code",
        rule: "Any rejected quantity (> 0) strictly requires an approved rejection reason code.",
        errorCode: "REJECTION_CODE_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Immutable Posted State",
        rule: "Once posted, a GRN cannot be edited; reversals require formal cancellation transaction.",
        errorCode: "GRN_ALREADY_POSTED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT: Inventory Asset (1400) / CREDIT: GRN Unbilled Clearing (2110).",
    failureImpact: "GRN cannot be posted; inventory cannot be used in production or fulfilled to orders.",
  },

  {
    id: "PUTAWAY_BINS",
    code: "WH-03",
    title: "Labeling & Directed Bin Putaway",
    module: "Warehouse, GRN & QC",
    moduleId: "warehouse",
    stream: "Warehouse & WMS",
    stageOrder: 5,
    actor: "Material Handler",
    actorRole: "warehouse:read / wms_bins:write",
    summary:
      "Prints adhesive thermal QR barcode labels for accepted cartons. Uses mobile RF scanner to scan pallet QR, scans destination warehouse rack/bin barcode, and confirms putaway.",
    inputDocuments: ["Posted GRN Accepted Lines", "Thermal Sticker Template (50x25mm)"],
    outputDocuments: ["Printed QR Barcodes", "Completed Putaway Task"],
    upperlineConnects: [
      {
        nodeId: "QC_INSPECTION",
        sourceModule: "Warehouse, GRN & QC",
        label: "Accepted Quality Disposition",
        dataPassed: "SKU, Accepted Qty, Serial/Lot IDs",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "STOCK_LEDGER",
        targetModule: "Inventory Management",
        label: "Updates Bin-Level Inventory Location",
        dataPassed: "Item ID, Specific Bin Code (e.g. RACK-A-02-B)",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Bin Product Category Compatibility",
        rule: "Putaway bin must be authorized for the product category (Hazmat, Cold Chain, Standard).",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Bin Volumetric Capacity",
        rule: "Current bin weight/CBM + incoming pallet cannot exceed maximum rack load limit.",
        severity: "Warning Alert",
      },
    ],
    ledgerImpact: "Updates item sub-location from Receiving Dock to Storage Bin.",
    failureImpact: "Items remain staged in dock aisles, causing floor congestion.",
  },

  {
    id: "IPQC_STAGE",
    code: "MFG-04",
    title: "In-Process Quality Checks (IPQC)",
    module: "Manufacturing & Operations",
    moduleId: "manufacturing",
    stream: "Plan-to-Produce",
    stageOrder: 5,
    actor: "IPQC Inspector",
    actorRole: "quality_ipqc:write",
    summary:
      "Performs quality checks at each shop-floor routing stage (e.g. SMT, Mechanical Fitment, Electrical Hi-Pot, Burn-in). Logs test values and issues Certificate of Analysis (CoA).",
    inputDocuments: ["Work Order Routing Traveler", "IPQC Inspection Checklist"],
    outputDocuments: ["Stage Sign-Off Record", "Quality Certificate of Analysis (CoA)"],
    upperlineConnects: [
      {
        nodeId: "MATERIAL_ISSUE",
        sourceModule: "Manufacturing & Inventory",
        label: "Issued Raw Materials",
        dataPassed: "Work Order ID, Component Lot IDs",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "FG_CONVERT",
        targetModule: "Manufacturing",
        label: "Unlocks Final Finished Goods Completion",
        dataPassed: "Passed Stage Records, Good Units Count",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Sequential Routing Stage Gate",
        rule: "Subsequent production stages cannot be completed until preceding stage passes inspection.",
        errorCode: "STAGE_SEQUENCE_VIOLATION",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Tracks labor and machine overhead accumulation in Work in Progress (WIP).",
    failureImpact: "Work order frozen; defective sub-assemblies quarantined before final packaging.",
  },

  {
    id: "FG_CONVERT",
    code: "MFG-05",
    title: "Finished Goods Conversion & Serialized Minting",
    module: "Manufacturing & Operations",
    moduleId: "manufacturing",
    stream: "Plan-to-Produce",
    stageOrder: 5,
    actor: "Production Head",
    actorRole: "inventory:produce",
    summary:
      "Closes work order. Records final good yield and scrap. Mints unique serialized finished good records (FG-XXXX). Converts WIP into Available finished goods stock.",
    inputDocuments: ["Completed IPQC Stages", "Final Yield Count", "Scrap Report"],
    outputDocuments: ["Serialized Finished Good Items", "Closed Production Run"],
    upperlineConnects: [
      {
        nodeId: "IPQC_STAGE",
        sourceModule: "Manufacturing",
        label: "Passed Inspection Gate",
        dataPassed: "Verified Good Units Count",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "STOCK_LEDGER",
        targetModule: "Inventory Management",
        label: "Credits Finished Goods Stock Balance",
        dataPassed: "FG SKU, Serial Numbers, Completed Qty, Unit Cost",
        isTrigger: true,
      },
      {
        nodeId: "STOCK_ALLOC",
        targetModule: "Sales & Orders",
        label: "Makes Stock Available for Customer Orders",
        dataPassed: "Available FG Inventory Balance",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Yield Material Conservation",
        rule: "Completed quantity + scrap count must be bounded by issued raw material BOM ratios.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "CREDIT: Work in Progress WIP (1450) / DEBIT: Finished Goods Inventory Asset (1420).",
    failureImpact: "Finished goods cannot be invoiced or shipped to waiting customers.",
  },

  {
    id: "EWAY_DISPATCH",
    code: "LOG-02",
    title: "Statutory e-Way Bill & Dispatch Outward",
    module: "Logistics & Transportation (TMS)",
    moduleId: "logistics",
    stream: "Order-to-Cash",
    stageOrder: 5,
    actor: "Gate Dispatch Officer",
    actorRole: "logistics:dispatch / order:ship",
    summary:
      "Generates 12-digit NIC statutory e-Way Bill with signed QR code. Prints thermal carrier shipping label (AWB), assigns driver phone/vehicle number, and marks consignment dispatched.",
    inputDocuments: ["Packed Cartons", "Carrier Booking AWB", "Sales Tax Invoice Details"],
    outputDocuments: ["Statutory e-Way Bill", "Carrier Thermal Shipping Label", "Outward Dispatch Notice"],
    upperlineConnects: [
      {
        nodeId: "TRANSPORT_REQ",
        sourceModule: "Logistics TMS",
        label: "Awarded Carrier Booking",
        dataPassed: "Carrier ID, AWB Docket, Vehicle Number",
        isHardDependency: true,
      },
      {
        nodeId: "PACK_CARTON",
        sourceModule: "Sales & Orders",
        label: "Packed Goods Manifest",
        dataPassed: "Carton IDs, Gross Weight kg",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "AR_INVOICE",
        targetModule: "Finance & Accounts Receivable",
        label: "Proof of Dispatch Triggers Official Tax Invoice",
        dataPassed: "Order ID, Shipped Date, Carrier Tracking AWB",
        isTrigger: true,
      },
      {
        nodeId: "POD_DELIVERY",
        targetModule: "Logistics TMS",
        label: "Initiates In-Transit Tracking",
        dataPassed: "Consignment ID, Tracking Number, Carrier API Webhook",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Mandatory e-Way Bill for Value > ₹50,000",
        rule: "Statutory Indian GST regulations require valid 12-digit e-Way bill for shipments > ₹50K.",
        errorCode: "EWAY_BILL_MANDATORY",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Advance Payment Settlement Guard",
        rule: "For Advance payment customers, order must be paid or hold 'order:override-logistics' permission.",
        errorCode: "PAYMENT_NOT_SETTLED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "CREDIT: Finished Goods Inventory (1420) / DEBIT: Cost of Goods Sold COGS (5000).",
    failureImpact: "Truck detained at state check-posts; heavy statutory penalties for missing e-Way bills.",
  },

  {
    id: "AR_INVOICE",
    code: "FIN-01",
    title: "Customer Tax Invoice & Revenue Recognition",
    module: "Finance & Accounts Receivable",
    moduleId: "finance",
    stream: "Order-to-Cash",
    stageOrder: 5,
    actor: "Billing Officer",
    actorRole: "order:invoice / invoice:post",
    summary:
      "Generates statutory customer GST tax invoice. Renders PDF with signed IRN QR code, emails invoice to customer accounts, and posts Accounts Receivable debit.",
    inputDocuments: ["Shipped Sales Order", "Customer Billing Profile", "GST Rate Master"],
    outputDocuments: ["Customer Tax Invoice (INV-9001)", "AR Ledger Entry"],
    upperlineConnects: [
      {
        nodeId: "EWAY_DISPATCH",
        sourceModule: "Logistics TMS",
        label: "Confirmed Outward Dispatch",
        dataPassed: "Order ID, Shipped Line Quantities, Dispatch Date",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "CREDIT_CHECK",
        targetModule: "Sales & Orders",
        label: "Updates Customer Open AR Balance",
        dataPassed: "New Invoice Amount, Due Date",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "One-Invoice Enforcement",
        rule: "A sales order line cannot be invoiced more than once.",
        errorCode: "ORDER_ALREADY_INVOICED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Statutory GST Tax Splitting",
        rule: "Intra-state sales split equally into CGST+SGST; inter-state sales map to IGST.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT: Accounts Receivable (1200) / CREDIT: Sales Revenue (4000) & GST Tax Payable (2200).",
    failureImpact: "Revenue unrecognized; customer cannot process payment remittance.",
  },

  {
    id: "THREE_WAY_MATCH",
    code: "FIN-02",
    title: "Automated 3-Way Match Verification",
    module: "Finance & Accounts Payable",
    moduleId: "finance",
    stream: "Finance & Accounting",
    stageOrder: 5,
    actor: "3-Way Match Audit Engine",
    actorRole: "finance:read",
    summary:
      "Strict automated triangle verification: compares 1) Contracted Purchase Order rates, 2) Accepted GRN physical quantities, and 3) Vendor Tax Invoice billed rates & counts.",
    inputDocuments: ["Purchase Order (PO)", "Posted GRN Line Receipts", "Vendor Tax Invoice"],
    outputDocuments: ["3-Way Match Audit Status ('matched' or 'variance_hold')"],
    upperlineConnects: [
      {
        nodeId: "PO_ISSUE",
        sourceModule: "Procurement",
        label: "Contracted Price Agreement",
        dataPassed: "PO Line Item Price, Payment Terms, Freight Terms",
        isHardDependency: true,
      },
      {
        nodeId: "QC_INSPECTION",
        sourceModule: "Warehouse, GRN & QC",
        label: "Certified Accepted Physical Goods",
        dataPassed: "GRN Accepted Qty, Batch ID, Rejection Deductions",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "AP_VOUCHER",
        targetModule: "Finance & Accounts Payable",
        label: "Unlocks Invoice for Payment Voucher Posting",
        dataPassed: "Matched Invoice ID, Verified Payable Total",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Billed Quantity <= Accepted GRN Quantity",
        rule: "Vendor billed quantity cannot exceed the physically accepted quantity on the linked GRN.",
        errorCode: "MATCH_QTY_VARIANCE",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Billed Price <= PO Contracted Price",
        rule: "Unit price on vendor invoice must match contracted PO unit price (0% tolerance).",
        errorCode: "MATCH_PRICE_VARIANCE",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Prevents over-billing; unblocks GRN Clearing account.",
    failureImpact: "Invoice placed on 'Variance Hold'; payment disbursement strictly locked.",
  },

  {
    id: "AP_VOUCHER",
    code: "FIN-03",
    title: "Accounts Payable Invoice Booking",
    module: "Finance & Accounts Payable",
    moduleId: "finance",
    stream: "Finance & Accounting",
    stageOrder: 5,
    actor: "Accounts Payable Specialist",
    actorRole: "invoice:post",
    summary:
      "Formal financial booking of supplier liability. Establishes payment due date based on contracted credit terms (Net 30, Net 60). Adds to AP aging subledger.",
    inputDocuments: ["Matched 3-Way Match Verification", "Vendor Tax Invoice PDF"],
    outputDocuments: ["Posted AP Invoice (AP-7001)", "AP Liability Subledger Row"],
    upperlineConnects: [
      {
        nodeId: "THREE_WAY_MATCH",
        sourceModule: "Finance & Accounts Payable",
        label: "Cleared Match Result",
        dataPassed: "Verified Line Amounts, Tax Breakdown",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "LANDED_COST",
        targetModule: "Finance & Logistics",
        label: "Feeds Indirect Freight / Customs Bills for Apportionment",
        dataPassed: "Freight Invoice Amount, Transporter ID, Linked PO",
        isTrigger: false,
      },
      {
        nodeId: "PAYMENT_DISBURSE",
        targetModule: "Finance & Treasury",
        label: "Queues Bill in Payment Schedule",
        dataPassed: "Payable Amount, Vendor Bank IFSC, Due Date",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Duplicate Invoice Detection",
        rule: "Combination of (vendor_id, invoice_number) must be globally unique in tenant.",
        errorCode: "DUPLICATE_VENDOR_INVOICE",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Open Accounting Period Check",
        rule: "Transaction date must fall within an open accounting period.",
        errorCode: "ACCOUNTING_PERIOD_CLOSED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT: GRN Unbilled Clearing (2110) / CREDIT: Accounts Payable Liability (2000).",
    failureImpact: "Vendor liability unrecorded; payment disbursement cannot proceed.",
  },

  // -------------------------------------------------------------
  // STAGE 6: SETTLEMENT, POD CLOSING, VALUATION & AUDIT
  // -------------------------------------------------------------
  {
    id: "POD_DELIVERY",
    code: "LOG-03",
    title: "Proof of Delivery (POD) & Milestone Closing",
    module: "Logistics & Transportation (TMS)",
    moduleId: "logistics",
    stream: "Order-to-Cash",
    stageOrder: 6,
    actor: "Delivery Coordinator",
    actorRole: "logistics:dispatch",
    summary:
      "Captures final consignee delivery confirmation. Uploads signed and stamped physical Proof of Delivery (POD) slip. Closes logistics consignment.",
    inputDocuments: ["Signed Consignee Delivery Challan", "Carrier Electronic Delivery Webhook"],
    outputDocuments: ["Verified POD Document Attachment", "Closed Dispatch Notice ('delivered')"],
    upperlineConnects: [
      {
        nodeId: "EWAY_DISPATCH",
        sourceModule: "Logistics TMS",
        label: "Outward Shipment",
        dataPassed: "Dispatch ID, Tracking AWB",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PAYMENT_DISBURSE",
        targetModule: "Finance & Treasury",
        label: "Unlocks Transporter Freight Bill Payout",
        dataPassed: "Closed Dispatch ID, Confirmed Delivery Date",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Mandatory Signed POD Document Attachment",
        rule: "Marking a dispatch 'delivered' requires uploading a legible signed POD document.",
        errorCode: "POD_ATTACHMENT_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Confirms fulfillment completion in CRM and order management.",
    failureImpact: "Carrier freight invoice held from payment; disputed customer claims.",
  },

  {
    id: "LANDED_COST",
    code: "FIN-04",
    title: "Landed Cost Apportionment & Valuation Adjustment",
    module: "Finance & Logistics",
    moduleId: "finance",
    stream: "Finance & Accounting",
    stageOrder: 6,
    actor: "Cost Accountant",
    actorRole: "landed_cost:write",
    summary:
      "Apportions indirect procurement expenses (ocean freight, customs duty, port handling, transit insurance) across received GRN lines. Recalculates true Moving Average Unit Cost.",
    inputDocuments: ["Customs Bill of Entry", "Freight Invoices", "Posted GRN Receipts"],
    outputDocuments: ["Landed Cost Voucher (LCV-101)", "Stock Valuation Adjustment Journal"],
    upperlineConnects: [
      {
        nodeId: "AP_VOUCHER",
        sourceModule: "Finance & Accounts Payable",
        label: "Expense Bills",
        dataPassed: "Customs Duty, Freight charges, Port handling fees",
        isHardDependency: true,
      },
      {
        nodeId: "QC_INSPECTION",
        sourceModule: "Warehouse, GRN & QC",
        label: "Target Received Goods Receipts",
        dataPassed: "GRN line values, Quantities, Gross weights",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "STOCK_LEDGER",
        targetModule: "Inventory Management",
        label: "Updates Moving Average Unit Cost in Stock Ledger",
        dataPassed: "SKU, Adjusted Unit Moving Average Cost (MAC)",
        isTrigger: true,
      },
    ],
    keyValidations: [
      {
        name: "Apportionment Balance Conservation",
        rule: "Total expense voucher amount must exactly equal the sum of item apportioned costs.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT: Inventory Asset Valuation (1400) / CREDIT: Freight / Customs Expense Clearing (5100).",
    failureImpact: "Product profit margins distorted; GAAP/IFRS IAS 2 compliance audit failure.",
  },

  {
    id: "PAYMENT_DISBURSE",
    code: "FIN-05",
    title: "Dual-Custody Bank Payment Disbursement",
    module: "Finance & Treasury",
    moduleId: "finance",
    stream: "Finance & Accounting",
    stageOrder: 6,
    actor: "Treasury Officer & Finance Controller",
    actorRole: "payment:write / payment:approve",
    summary:
      "Disburses bank payouts to suppliers (NEFT/RTGS). Enforces maker-checker dual approval for amounts > ₹1,00,000. Reconciles vendor balance and issues payment advice.",
    inputDocuments: ["Approved AP Invoices", "Bank Account Balance"],
    outputDocuments: ["Payment Voucher", "Bank Advice File", "Settlement Allocation Log"],
    upperlineConnects: [
      {
        nodeId: "AP_VOUCHER",
        sourceModule: "Finance & Accounts Payable",
        label: "Matured Payable Bills",
        dataPassed: "Vendor Bank Details, Payable Net Amount, UTR Ref",
        isHardDependency: true,
      },
    ],
    downlineConnects: [
      {
        nodeId: "PO_VENDOR_ACK",
        targetModule: "Procurement",
        label: "Updates Supplier Account Standing",
        dataPassed: "Settlement confirmation, Vendor Statement",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Maker-Checker Segregation for Payouts",
        rule: "Payments exceeding ₹1,00,000 mandate independent approval by Finance Controller.",
        errorCode: "PAYMENT_APPROVAL_REQUIRED",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Allocation Balance Integrity",
        rule: "Payment allocation amount cannot exceed open balance of target invoice.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT: Accounts Payable (2000) / CREDIT: Bank Account Asset (1010).",
    failureImpact: "Vendor credit put on hold; potential supply disruption.",
  },

  {
    id: "CREDIT_NOTE",
    code: "FIN-06",
    title: "Debit/Credit Notes & Return Reconciliation",
    module: "Finance & Quality",
    moduleId: "finance",
    stream: "Finance & Accounting",
    stageOrder: 6,
    actor: "Senior Accountant",
    actorRole: "finance:read / payment:write",
    summary:
      "Processes debit notes for rejected vendor shipments (RTV) and credit notes for customer warranty returns (RMA). Reconciles subledgers without deleting historical invoices.",
    inputDocuments: ["RTV Rejection Challan", "Customer RMA Slip", "Original Invoice"],
    outputDocuments: ["Credit Note / Debit Note Voucher"],
    upperlineConnects: [
      {
        nodeId: "QC_INSPECTION",
        sourceModule: "Warehouse, GRN & QC",
        label: "Rejected Inbound Goods",
        dataPassed: "Rejected Quantities, Unit Rates, Vendor ID",
        isHardDependency: false,
      },
    ],
    downlineConnects: [
      {
        nodeId: "AP_VOUCHER",
        targetModule: "Finance & Accounts Payable",
        label: "Reduces Vendor Payable Liability",
        dataPassed: "Debit Note Offset Amount",
        isTrigger: false,
      },
      {
        nodeId: "CREDIT_CHECK",
        targetModule: "Sales & Orders",
        label: "Restores Customer Credit Headroom",
        dataPassed: "Credit Note Offset Amount",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Original Invoice Balance Cap",
        rule: "Credit note amount cannot exceed the remaining balance of the referenced invoice.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "DEBIT/CREDIT adjustment offsetting original AR / AP ledger postings.",
    failureImpact: "Disputed ledger accounts with trading partners.",
  },

  {
    id: "RBAC_GOVERN",
    code: "ADM-01",
    title: "RBAC Governance & Immutable Audit Logging",
    module: "Administration & Master Data",
    moduleId: "administration",
    stream: "Governance",
    stageOrder: 6,
    actor: "System Administrator & Auditor",
    actorRole: "system:admin / audit:read",
    summary:
      "Enterprise security backbone: enforces least-privilege role permissions, facility warehouse data scopes, AES-encrypted SMTP email credentials, and immutable append-only audit trail.",
    inputDocuments: ["Role Definitions", "User Invitations", "Security Policies"],
    outputDocuments: ["Active RBAC Permission Tokens", "Append-Only Audit Log Records"],
    upperlineConnects: [],
    downlineConnects: [
      {
        nodeId: "BOM_MANAGE",
        targetModule: "Manufacturing",
        label: "Gates Engineering Revisions",
        dataPassed: "Permission: bom:write, bom:approve",
        isTrigger: false,
      },
      {
        nodeId: "PR_APPROVE",
        targetModule: "Procurement",
        label: "Enforces Manager Hierarchy & Thresholds",
        dataPassed: "Reporting lines, approval limits",
        isTrigger: false,
      },
      {
        nodeId: "PO_ISSUE",
        targetModule: "Procurement",
        label: "Gates Purchasing Authority",
        dataPassed: "po:write, po:approve",
        isTrigger: false,
      },
      {
        nodeId: "QC_INSPECTION",
        targetModule: "Warehouse",
        label: "Gates Receiving & Stock Ledger Posting",
        dataPassed: "grn:post, warehouse:read",
        isTrigger: false,
      },
      {
        nodeId: "PAYMENT_DISBURSE",
        targetModule: "Finance",
        label: "Enforces Dual-Custody Banking Authority",
        dataPassed: "payment:approve",
        isTrigger: false,
      },
    ],
    keyValidations: [
      {
        name: "Least-Privilege Role Granting Guard",
        rule: "An administrator cannot bestow permissions they do not personally hold.",
        errorCode: "LEAST_PRIVILEGE_VIOLATION",
        severity: "Hard Blocker (422/409)",
      },
      {
        name: "Append-Only Audit Immutability",
        rule: "Audit trail log has no update or delete routes; historical actions are strictly immutable.",
        severity: "Hard Blocker (422/409)",
      },
    ],
    ledgerImpact: "Underpins audit and statutory ISO/SOX compliance across all modules.",
    failureImpact: "Unauthorized privilege escalation or unauthorized security breaches.",
  },
];

// Helper functions for graph navigation
export function getNodeById(id: string): EnterpriseWorkflowNode | undefined {
  return ENTERPRISE_MASTER_FLOWCHART.find((n) => n.id === id);
}

export function getNodesByStream(stream: EnterpriseStream | "All"): EnterpriseWorkflowNode[] {
  if (stream === "All") return ENTERPRISE_MASTER_FLOWCHART;
  return ENTERPRISE_MASTER_FLOWCHART.filter((n) => n.stream === stream);
}

export function getUpperlineNodes(nodeId: string): EnterpriseWorkflowNode[] {
  const current = getNodeById(nodeId);
  if (!current) return [];
  const upperIds = current.upperlineConnects.map((u) => u.nodeId);
  return ENTERPRISE_MASTER_FLOWCHART.filter((n) => upperIds.includes(n.id));
}

export function getDownlineNodes(nodeId: string): EnterpriseWorkflowNode[] {
  const current = getNodeById(nodeId);
  if (!current) return [];
  const downIds = current.downlineConnects.map((d) => d.nodeId);
  return ENTERPRISE_MASTER_FLOWCHART.filter((n) => downIds.includes(n.id));
}
