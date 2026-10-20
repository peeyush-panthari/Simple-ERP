import type { NavGroupName } from "./nav";

export type EnterpriseStream =
  | "Plan-to-Produce"
  | "Procure-to-Pay"
  | "Warehouse & WMS"
  | "Order-to-Cash"
  | "Finance & Accounting"
  | "Governance";

export type EnterprisePhase =
  | "Phase 1: Enterprise Foundation & Master Setup"
  | "Phase 2: Demand Planning & Procurement"
  | "Phase 3: Inbound Logistics & Receiving"
  | "Phase 4: Manufacturing & Assembly Execution"
  | "Phase 5: Sales Fulfillment & Outbound Logistics"
  | "Phase 6: Reverse Logistics, Finance & Governance";

export interface DemoConnection {
  moduleName: string;
  route: string;
  document: string;
  dataPassed: string;
  relationship: string;
}

export interface InteractiveFormField {
  name: string;
  label: string;
  type: "text" | "number" | "select" | "checkbox_group" | "date" | "readonly";
  defaultValue: string | number | boolean | string[];
  options?: { label: string; value: string; hint?: string }[];
  helperText?: string;
  prefix?: string;
  suffix?: string;
}

export interface InteractiveActivity {
  activityTitle: string;
  instructions: string;
  formFields: InteractiveFormField[];
  submitButtonText: string;
  successMessage: string;
  createdDocumentType: string;
  createdDocumentId: string;
  keyDetails: Record<string, string>;
  ledgerImpact: string;
}

export interface DemoWorkflowAction {
  id: string;
  actionNumber: number;
  title: string;
  shortTitle: string;
  actor: string;
  permissionRequired: string;
  triggerEvent: string;
  stepByStepInstructions: string[];
  systemValidations: string[];
  tablesAndLedgersMutated: string[];
  outputDocument: string;
  interactiveActivity?: InteractiveActivity;
  simulation: {
    scenarioDescription: string;
    initialState: string;
    buttonLabel: string;
    successState: string;
    executionLog: string[];
    databaseEffect: string;
  };
}

export interface P2PStage {
  stageNumber: number;
  id: string;
  title: string;
  shortTitle: string;
  role: string;
  department: string;
  route: string;
  inputDocument: string;
  outputDocument: string;
  description: string;
  formFields: InteractiveFormField[];
  submitButtonText: string;
  successTitle: string;
  successSummary: string;
  ledgerEffect: string;
  executionLogs: string[];
}

export interface DemoFlowStep {
  stepNumber: number;
  id: string;
  title: string;
  shortTitle: string;
  route: string;
  navGroup?: NavGroupName;
  phase: EnterprisePhase;
  stream: EnterpriseStream;
  category: string;
  iconName: string;
  actorRole: string;
  summary: string;
  businessPurpose: string;
  keyObjectives: string[];
  workflows: DemoWorkflowAction[];
  upstreamConnections: DemoConnection[];
  downstreamConnections: DemoConnection[];
  businessControls: string[];
}

export interface ERPJourneyStep {
  stepNumber: number;
  id: string;
  title: string;
  shortTitle: string;
  route: string;
  navGroup: NavGroupName;
  actorRole: string;
  department: string;
  targetElementSelector?: string;
  description: string;
  actionPrompt: string;
  sampleAction: {
    label: string;
    description: string;
    buttonText: string;
    successMessage: string;
    sampleData: Record<string, any>;
    ledgerImpact?: string;
  };
  keyTakeaway: string;
}

export interface ERPJourney {
  id: string;
  journeyNumber: number;
  title: string;
  shortTitle: string;
  tagline: string;
  description: string;
  persona: string;
  department: string;
  color: string;
  badgeClass: string;
  borderClass: string;
  bgClass: string;
  iconName: string;
  estimatedMinutes: number;
  recommendedStart?: boolean;
  steps: ERPJourneyStep[];
}

export const ENTERPRISE_PHASES: Record<
  EnterprisePhase,
  {
    phaseNumber: number;
    title: string;
    shortTitle: string;
    description: string;
    color: string;
    badgeClass: string;
    stepRange: string;
  }
> = {
  "Phase 1: Enterprise Foundation & Master Setup": {
    phaseNumber: 1,
    title: "Phase 1: Enterprise Foundation & Master Setup",
    shortTitle: "1. Foundation Setup",
    description: "Establish legal entities, multi-facility infrastructure, RBAC permissions, suppliers/customers, and engineering BOM recipes before executing operational transactions.",
    color: "#475569",
    badgeClass: "bg-slate-500/10 text-slate-800 dark:text-slate-200 border border-slate-500/20",
    stepRange: "Steps 1–5",
  },
  "Phase 2: Demand Planning & Procurement": {
    phaseNumber: 2,
    title: "Phase 2: Demand Planning & Procurement",
    shortTitle: "2. Planning & Sourcing",
    description: "Forecast commercial demand, explode multi-level BOM component deficits via MRP, and execute multi-vendor RFQ bidding with tiered PO authorizations.",
    color: "#0f766e",
    badgeClass: "bg-teal-500/10 text-teal-800 dark:text-teal-200 border border-teal-500/20",
    stepRange: "Steps 6–8",
  },
  "Phase 3: Inbound Logistics & Receiving": {
    phaseNumber: 3,
    title: "Phase 3: Inbound Logistics & Receiving",
    shortTitle: "3. Receiving & Quality",
    description: "Monitor carrier arrival with supplier ASN notices, generate dock GRNs, enforce mandatory QC testing, and execute directed WMS rack/bin putaway.",
    color: "#2563eb",
    badgeClass: "bg-blue-500/10 text-blue-800 dark:text-blue-200 border border-blue-500/20",
    stepRange: "Steps 9–12",
  },
  "Phase 4: Manufacturing & Assembly Execution": {
    phaseNumber: 4,
    title: "Phase 4: Manufacturing & Assembly Execution",
    shortTitle: "4. Manufacturing Execution",
    description: "Issue raw materials with FIFO lot traceability, execute shop-floor assembly routing, record in-process IPQC inspection, and convert WIP into Finished Goods.",
    color: "#7c3aed",
    badgeClass: "bg-purple-500/10 text-purple-800 dark:text-purple-200 border border-purple-500/20",
    stepRange: "Step 13",
  },
  "Phase 5: Sales Fulfillment & Outbound Logistics": {
    phaseNumber: 5,
    title: "Phase 5: Sales Fulfillment & Outbound Logistics",
    shortTitle: "5. Sales & Shipping",
    description: "Book customer sales orders, audit credit limits, lock inventory rows with zero overselling, wave pick with mobile terminals, pack, and generate statutory e-Way bills.",
    color: "#d97706",
    badgeClass: "bg-amber-500/10 text-amber-800 dark:text-amber-200 border border-amber-500/20",
    stepRange: "Steps 14–16",
  },
  "Phase 6: Reverse Logistics, Finance & Governance": {
    phaseNumber: 6,
    title: "Phase 6: Reverse Logistics, Finance & Governance",
    shortTitle: "6. Finance & Governance",
    description: "Manage customer RMA returns, execute automated 3-way invoice matching, capitalize landed freight costs, and review real-time OTIF control tower metrics.",
    color: "#059669",
    badgeClass: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200 border border-emerald-500/20",
    stepRange: "Steps 17–19",
  },
};

export const ENTERPRISE_STREAMS: Record<
  EnterpriseStream,
  {
    name: string;
    description: string;
    color: string;
    badgeClass: string;
    borderClass: string;
    bgClass: string;
  }
> = {
  "Plan-to-Produce": {
    name: "Plan-to-Produce (Manufacturing)",
    description: "Catalog engineering, BOM specs, demand forecasting, MRP explosions, and assembly execution.",
    color: "#7c3aed",
    badgeClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20",
    borderClass: "border-purple-500",
    bgClass: "bg-purple-500/5",
  },
  "Procure-to-Pay": {
    name: "Procure-to-Pay (P2P)",
    description: "Requisitions, supplier RFQs, multi-tier PO approvals, and vendor compliance.",
    color: "#0f766e",
    badgeClass: "bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20",
    borderClass: "border-teal-500",
    bgClass: "bg-teal-500/5",
  },
  "Warehouse & WMS": {
    name: "Warehouse & WMS Logistics",
    description: "Dock inward, QC dispositions, directed bin putaway, stock ledgers, and wave picking.",
    color: "#2563eb",
    badgeClass: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20",
    borderClass: "border-blue-500",
    bgClass: "bg-blue-500/5",
  },
  "Order-to-Cash": {
    name: "Order-to-Cash (O2C)",
    description: "Sales orders, credit limit audits, row-locked FIFO allocation, and packing/shipping dispatch.",
    color: "#d97706",
    badgeClass: "bg-amber-500/10 text-amber-800 dark:text-amber-200 border border-amber-500/20",
    borderClass: "border-amber-500",
    bgClass: "bg-amber-500/5",
  },
  "Finance & Accounting": {
    name: "Finance & Accounting Control",
    description: "Automated 3-way matching, AP vendor payouts, AR collections, and landed cost capitalization.",
    color: "#059669",
    badgeClass: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20",
    borderClass: "border-emerald-500",
    bgClass: "bg-emerald-500/5",
  },
  Governance: {
    name: "Supply Chain Control & Governance",
    description: "Executive KPIs, On-Time In-Full (OTIF) tracking, immutable audit trails, and RBAC.",
    color: "#475569",
    badgeClass: "bg-slate-500/10 text-slate-700 dark:text-slate-300 border border-slate-500/20",
    borderClass: "border-slate-500",
    bgClass: "bg-slate-500/5",
  },
};

/**
 * 6 Core Self-Guided Enterprise Journeys
 * Built specifically for role-based, hands-on learning across real ERP screens.
 */
export const ERP_JOURNEYS: ERPJourney[] = [
  // 1. Administration of ERP (Recommended Starting Point)
  {
    id: "administration",
    journeyNumber: 1,
    title: "1. Administration of ERP",
    shortTitle: "Administration",
    tagline: "Day-0 Foundation: Users, Roles, Multi-Plant Topography, BOMs & System Configuration",
    description: "The essential starting point for any ERP: configure organizational identities, access governance, physical manufacturing plants, warehouse dock topography, item catalogs, and engineering BOM recipes before transactions begin.",
    persona: "System Administrator & Operations Director",
    department: "Enterprise Administration & Plant Governance",
    color: "#475569",
    badgeClass: "bg-slate-500/15 text-slate-800 dark:text-slate-200 border-slate-500/30",
    borderClass: "border-slate-500",
    bgClass: "bg-slate-500/5",
    iconName: "ShieldCheck",
    estimatedMinutes: 4,
    recommendedStart: true,
    steps: [
      {
        stepNumber: 1,
        id: "admin-users",
        title: "Users, Roles & Site Access Governance",
        shortTitle: "Users & Roles",
        route: "/users",
        navGroup: "Administration",
        actorRole: "Security Admin (user:read, user:write, user:assign_role)",
        department: "IT & Information Security",
        targetElementSelector: "button:has-text('Invite user')",
        description: "Configure personnel identities, enforce Argon2id credential standards, and assign granular RBAC roles (Lead Buyer, QC Chemist, Warehouse Receiver). Scope users strictly to their authorized physical manufacturing plants.",
        actionPrompt: "Click '+ Invite user' to onboard a new operator and scope their access to the Pune facility.",
        sampleAction: {
          label: "Onboard Rahul Sharma (Warehouse Receiver)",
          description: "Invites rahul.s@axon-industries.com with 'Warehouse Receiver' role and restricts access strictly to Warehouse WH-PUNE-01.",
          buttonText: "Simulate User Invitation & Facility Scoping",
          successMessage: "User invited with Argon2id token; scoped to WH-PUNE-01 and FACT-PUNE-01. Cross-site tampering locked out.",
          sampleData: {
            name: "Rahul Sharma",
            email: "rahul.s@axon-industries.com",
            role: "Warehouse Receiver",
            facilityScope: ["WH-PUNE-01", "FACT-PUNE-01"],
          },
          ledgerImpact: "users and user_role_warehouses tables mutated; Casbin RBAC policy loaded into cache.",
        },
        keyTakeaway: "Role-based access control (RBAC) ensures operators only see actions appropriate to their job, while site scoping prevents cross-plant data leakage.",
      },
      {
        stepNumber: 2,
        id: "admin-facilities",
        title: "Facilities, Factories & Warehouse Topography",
        shortTitle: "Factory & Warehouse",
        route: "/factory-warehouse",
        navGroup: "Administration",
        actorRole: "Operations Director (warehouse:read, warehouse:write)",
        department: "Industrial Engineering",
        targetElementSelector: "button:has-text('New factory')",
        description: "Establish physical manufacturing plants with assembly lines, working calendars, and distribution warehouses with designated staging bays, dock doors, and quarantine holding zones.",
        actionPrompt: "Commission Pune Assembly Plant 1 with 3 SMT lines and configure Pune Central Warehouse with dock receiving bays.",
        sampleAction: {
          label: "Commission Plant & Central Warehouse",
          description: "Creates FACT-PUNE-01 (Pune Assembly Plant 1) with 3 production lines and WH-PUNE-01 with dock and quarantine bays.",
          buttonText: "Simulate Facility Commissioning",
          successMessage: "Factory FACT-PUNE-01 & Warehouse WH-PUNE-01 commissioned with 3 active assembly lines and 4 staging zones.",
          sampleData: {
            factoryCode: "FACT-PUNE-01",
            factoryName: "Pune Assembly Plant 1",
            lines: 3,
            warehouseCode: "WH-PUNE-01",
            warehouseName: "Pune Central Warehouse",
            stagingBays: ["Dock-01", "Dock-02", "Quarantine-A", "Outbound-Bay-1"],
          },
          ledgerImpact: "factories and warehouses tables mutated; production scheduling engine enabled for site.",
        },
        keyTakeaway: "Every inventory transaction, work order, and dock receiving note requires a verified physical facility reference.",
      },
      {
        stepNumber: 3,
        id: "admin-products",
        title: "Product Master Catalog & Engineering BOM Recipes",
        shortTitle: "Products & BOM",
        route: "/products",
        navGroup: "Administration",
        actorRole: "Catalog Engineer & Product Manager (product:read, bom:write)",
        department: "R&D and Product Engineering",
        targetElementSelector: "button:has-text('New product')",
        description: "Define master SKU catalog identities (Finished Goods, Raw Materials, WIP Sub-assemblies), specify Units of Measure (UOM), and construct multi-level Engineering Bills of Materials (BOM) with component multipliers.",
        actionPrompt: "Create SKU-MOT-500 (500W Electric Motor) and register its 4-part BOM assembly recipe.",
        sampleAction: {
          label: "Register SKU-MOT-500 & Assembly BOM",
          description: "Creates Finished Good SKU-MOT-500 with Standard Cost ₹750, Selling Price ₹1,200, and multi-tier BOM (Winding Wire, Rotor Core, Ball Bearing, Aluminum Enclosure).",
          buttonText: "Simulate SKU & BOM Creation",
          successMessage: "SKU-MOT-500 committed to master catalog; Engineering BOM-v1 locked for MRP gross-to-net explosion.",
          sampleData: {
            sku: "SKU-MOT-500",
            name: "500W Industrial Electric Motor",
            uom: "Unit",
            standardCost: "₹750.00",
            hsnCode: "8501",
            bomComponents: [
              "SKU-WIRE-01 (12.5m Copper Wire)",
              "SKU-ROTOR-01 (1x Rotor Core)",
              "SKU-BEARING-01 (2x Ball Bearings)",
              "SKU-HOUSING-01 (1x Motor Shell)",
            ],
          },
          ledgerImpact: "products and bills_of_material tables mutated; version BOM-v1 released.",
        },
        keyTakeaway: "Engineering BOMs are the single source of truth for both MRP procurement explosion and shop-floor manufacturing execution.",
      },
      {
        stepNumber: 4,
        id: "admin-configuration",
        title: "Enterprise Configuration & System Rules",
        shortTitle: "Configuration & Rules",
        route: "/configuration",
        navGroup: "Administration",
        actorRole: "System Administrator (product:read, org:write)",
        department: "Corporate Operations",
        targetElementSelector: "input",
        description: "Set enterprise-wide operational policies: statutory GSTIN tax parameters, auto-numbering prefixes (PR-, PO-, GRN-, WO-, SO-, INV-), automated email notification triggers, and approval thresholds.",
        actionPrompt: "Review and activate system document numbering sequences and statutory tax calculation profiles.",
        sampleAction: {
          label: "Activate System Numbering & Tax Engine",
          description: "Locks global sequential numbering (PO-{YYYY}-{0000}) and enables automatic CGST/SGST/IGST tax engine.",
          buttonText: "Simulate Config Activation",
          successMessage: "Enterprise configuration active. Audit logging enabled with SHA-256 integrity checks.",
          sampleData: {
            numberingSequences: ["PR-XXXX", "PO-XXXX", "GRN-XXXX", "WO-XXXX", "SO-XXXX", "INV-XXXX"],
            defaultTaxEngine: "GST-IN (CGST 9% + SGST 9% / IGST 18%)",
            approvalThresholds: "POs > ₹1,00,000 require VP/Director authorization",
          },
          ledgerImpact: "tenant_settings and configuration tables updated with immutable audit log timestamp.",
        },
        keyTakeaway: "Standardized numbering and automated tax rules ensure regulatory compliance and seamless 3-way matching across documents.",
      },
    ],
  },

  // 2. Plan to Order
  {
    id: "plan-to-order",
    journeyNumber: 2,
    title: "2. Plan to Order",
    shortTitle: "Plan to Order",
    tagline: "Demand Forecasting, S&OP Consensus, Multi-Echelon DRP & MRP Net Requirements",
    description: "Translate commercial customer market demand into consensus sales forecasts, calculate safety stock buffers across multi-echelon regional hubs, and explode multi-level BOMs into planned Purchase Requisitions.",
    persona: "Supply Chain Planner & Demand Forecaster",
    department: "Integrated Supply Chain Planning",
    color: "#0f766e",
    badgeClass: "bg-teal-500/15 text-teal-800 dark:text-teal-200 border-teal-500/30",
    borderClass: "border-teal-500",
    bgClass: "bg-teal-500/5",
    iconName: "LineChart",
    estimatedMinutes: 4,
    steps: [
      {
        stepNumber: 1,
        id: "pto-forecasting",
        title: "Demand Forecasting & Consensus S&OP",
        shortTitle: "Demand Forecasting",
        route: "/forecasting",
        navGroup: "Planning & SCM",
        actorRole: "Demand Planning Manager (forecasting:read)",
        department: "Supply Chain Planning",
        targetElementSelector: "button:has-text('Run forecast')",
        description: "Execute statistical tournament forecasting (Holt-Winters exponential smoothing vs Auto-ARIMA) across 24 months of sales history. Lock monthly unconstrained commercial demand.",
        actionPrompt: "Run statistical forecast for SKU-MOT-500 to establish baseline demand of 400 units for next month.",
        sampleAction: {
          label: "Execute Tournament Forecast on SKU-MOT-500",
          description: "Compares 3 time-series algorithms and locks consensus demand of 400 motors with 94.2% historical accuracy.",
          buttonText: "Simulate Forecast Generation",
          successMessage: "Forecast calculated: 400 units required for Pune Plant; seasonal lift of +8.5% factored in.",
          sampleData: {
            sku: "SKU-MOT-500",
            winningModel: "Triple Holt-Winters Additive",
            projectedDemand: "400 Units",
            confidenceInterval: "95% (378 - 422 units)",
          },
          ledgerImpact: "demand_forecasts table updated; consensus plan locked for DRP/MRP.",
        },
        keyTakeaway: "Accurate statistical forecasting prevents overproduction while guarding against critical component stockouts.",
      },
      {
        stepNumber: 2,
        id: "pto-drp",
        title: "Multi-Echelon Distribution Requirements Planning (DRP)",
        shortTitle: "Distribution DRP",
        route: "/drp",
        navGroup: "Planning & SCM",
        actorRole: "Supply Chain Network Planner (drp:read)",
        department: "Logistics Network Planning",
        targetElementSelector: "button",
        description: "Analyze regional hub inventory levels (Pune Central vs Mumbai Hub vs Bangalore Depot) to calculate replenishment transit requirements and maintain optimal safety stock buffers.",
        actionPrompt: "Audit network inventory distribution and generate cross-dock replenishment transfers.",
        sampleAction: {
          label: "Net Regional Safety Stock Buffers",
          description: "Calculates that Pune Central requires 400 units to support both local assembly and regional branch distribution.",
          buttonText: "Simulate DRP Calculation",
          successMessage: "DRP netting complete: 400 units allocated to Pune Master Schedule with zero stockout risk.",
          sampleData: {
            puneStock: "12 Units (Below safety buffer of 50)",
            regionalDemand: "400 Units",
            recommendedNetting: "Build 400 units at FACT-PUNE-01",
          },
          ledgerImpact: "drp_network_plans table committed.",
        },
        keyTakeaway: "Multi-echelon DRP prevents bullwhip effects across multi-warehouse supply chains.",
      },
      {
        stepNumber: 3,
        id: "pto-mrp",
        title: "Material Requirements Planning (MRP) Gross-to-Net Explosion",
        shortTitle: "MRP Explosion",
        route: "/mrp",
        navGroup: "Planning & SCM",
        actorRole: "MRP Planner (mrp:read, inventory:read)",
        department: "Materials Management",
        targetElementSelector: "button:has-text('Run MRP')",
        description: "Explode the BOM recipe for 400 finished motors against warehouse stock, on-order POs, and supplier lead times to identify net raw material component deficits.",
        actionPrompt: "Run MRP gross-to-net engine to calculate raw material component shortfalls.",
        sampleAction: {
          label: "Run MRP on SKU-MOT-500 (400 Units)",
          description: "Calculates gross requirement of 5,000m copper wire; nets against 0m available stock; offsets 10-day supplier lead time.",
          buttonText: "Simulate MRP Gross-to-Net Explosion",
          successMessage: "MRP explosion complete: Net deficit of 5,000m Copper Wire (SKU-WIRE-01) flagged for immediate purchase.",
          sampleData: {
            finishedGood: "SKU-MOT-500 (400 Units)",
            grossWireRequired: "5,000 Meters",
            stockOnHand: "0 Meters",
            plannedOrderType: "Purchase Requisition (PR)",
            leadTimeOffset: "10 Days",
          },
          ledgerImpact: "mrp_runs table logged; planned_orders created with status='suggested'.",
        },
        keyTakeaway: "MRP automatically calculates exactly what raw materials to buy, in what quantities, and by what date.",
      },
      {
        stepNumber: 4,
        id: "pto-release-pr",
        title: "Release Planned Requisitions to Procurement",
        shortTitle: "Release PR",
        route: "/procurement",
        navGroup: "Procurement",
        actorRole: "Lead Buyer (pr:read, pr:approve)",
        department: "Purchasing & Sourcing",
        targetElementSelector: "button",
        description: "Convert MRP planned purchase suggestions into formal, approved Purchase Requisitions (PR-3042) ready for supplier bidding and purchase order issuance.",
        actionPrompt: "Review MRP planned requirement and release formal Purchase Requisition PR-3042.",
        sampleAction: {
          label: "Approve & Release PR-3042 (₹1,25,000)",
          description: "Authorizes PR-3042 for 5,000m Copper Wire against GL Cost Center 'Assembly Plant 1' with required date in 10 days.",
          buttonText: "Simulate Requisition Release",
          successMessage: "PR-3042 approved & released to Procurement queue. Plan-to-Order journey successfully bridged to Sourcing!",
          sampleData: {
            prNumber: "PR-3042",
            sku: "SKU-WIRE-01 (Copper Enamelled Winding Wire 0.85mm)",
            qty: "5,000 Meters",
            estimatedCost: "₹1,25,000",
            status: "Approved - Sourcing Pending",
          },
          ledgerImpact: "purchase_requisitions table updated to status='approved'; cost center commitment logged.",
        },
        keyTakeaway: "Releasing planned orders ensures purchasing teams only buy materials validated by real production schedules.",
      },
    ],
  },

  // 3. Procurement to Pay (P2P)
  {
    id: "procure-to-pay",
    journeyNumber: 3,
    title: "3. Procurement to Pay (P2P)",
    shortTitle: "Procure to Pay",
    tagline: "Vendor Qualification, Requisitions, RFQs, PO Approvals, Dock GRN & 3-Way Match Remittance",
    description: "The complete commercial expenditure lifecycle: onboard AVL suppliers, float competitive RFQs, authorize purchase orders, receive goods at the dock, verify quality, and post automated 3-way matched invoice disbursements.",
    persona: "Lead Buyer & Accounts Payable Controller",
    department: "Strategic Sourcing & Finance AP",
    color: "#2563eb",
    badgeClass: "bg-blue-500/15 text-blue-800 dark:text-blue-200 border-blue-500/30",
    borderClass: "border-blue-500",
    bgClass: "bg-blue-500/5",
    iconName: "ShoppingCart",
    estimatedMinutes: 6,
    steps: [
      {
        stepNumber: 1,
        id: "p2p-parties",
        title: "Commercial Partner Directory & Approved Vendor List (AVL)",
        shortTitle: "Vendor Onboarding",
        route: "/parties",
        navGroup: "Procurement",
        actorRole: "Vendor Manager (party:read, party:write)",
        department: "Vendor Management",
        targetElementSelector: "button:has-text('New supplier')",
        description: "Onboard supplier Acme Copper Ltd, record statutory 15-digit GSTIN, PAN, and corporate bank remittance details. Perform vendor qualification audit to grant Grade-A Approved Vendor List (AVL) status.",
        actionPrompt: "Verify Acme Copper Ltd GSTIN (27AAACA1234A1Z5) and attach corporate bank disbursement account.",
        sampleAction: {
          label: "Onboard Acme Copper Ltd (VEN-ACM-01)",
          description: "Registers Acme Copper Ltd with verified GSTIN, IFSC code HDFC0000123, and approved status on the AVL.",
          buttonText: "Simulate Vendor Qualification",
          successMessage: "Acme Copper Ltd (VEN-ACM-01) active on AVL with Grade-A qualification score (96%).",
          sampleData: {
            vendorCode: "VEN-ACM-01",
            vendorName: "Acme Copper Industries Ltd",
            gstin: "27AAACA1234A1Z5",
            bankAccount: "HDFC Bank A/C ****5678",
            avlStatus: "Approved (Grade A)",
          },
          ledgerImpact: "parties table updated; vendor portal credentials generated.",
        },
        keyTakeaway: "Purchasing only from Approved Vendor List (AVL) suppliers guarantees quality standards and statutory GST compliance.",
      },
      {
        stepNumber: 2,
        id: "p2p-rfq",
        title: "Purchase Requisitions & Multi-Vendor RFQ Bidding",
        shortTitle: "Sourcing RFQ",
        route: "/procurement",
        navGroup: "Procurement",
        actorRole: "Sourcing Buyer (sourcing:read, sourcing:write)",
        department: "Procurement",
        targetElementSelector: "button",
        description: "Review PR-3042, float Request for Quotation RFQ-901 to 3 qualified wire suppliers, and evaluate quotes against unit price, delivery lead times, and payment terms in the bid comparison matrix.",
        actionPrompt: "Float RFQ-901 to Acme Copper and Bharat Cables; award contract to Acme Copper at ₹25/m.",
        sampleAction: {
          label: "Float RFQ-901 & Select Winning Bid",
          description: "Float RFQ for 5,000m copper wire. Acme Copper bids ₹25.00/m (7-day lead time); Bharat Cables bids ₹26.50/m. Award to Acme Copper.",
          buttonText: "Simulate RFQ Bid Evaluation",
          successMessage: "RFQ-901 awarded to Acme Copper Ltd at ₹25.00/m. Total base value: ₹1,25,000 + 18% GST.",
          sampleData: {
            rfqNumber: "RFQ-901",
            winningVendor: "Acme Copper Ltd",
            agreedRate: "₹25.00 per meter",
            leadTime: "7 Days",
            savingsVsBudget: "₹7,500 (5.6% below baseline)",
          },
          ledgerImpact: "rfqs and rfq_bids tables mutated; contract award locked.",
        },
        keyTakeaway: "Multi-vendor competitive bidding drives down unit costs and establishes clear commercial accountability.",
      },
      {
        stepNumber: 3,
        id: "p2p-po",
        title: "Purchase Order Issuance & Tier-2 Digital Authorization",
        shortTitle: "Purchase Order",
        route: "/procurement",
        navGroup: "Procurement",
        actorRole: "Procurement Director (po:read, po:write)",
        department: "Procurement & Finance",
        targetElementSelector: "button:has-text('New purchase order')",
        description: "Generate legally binding Purchase Order PO-9002 (₹1,47,500 incl. GST). Enforce two-tier managerial sign-off for purchase orders exceeding ₹1,00,000 threshold and dispatch digitally to supplier.",
        actionPrompt: "Approve and authorize PO-9002 with digital signature seal and dispatch to Acme Copper via email.",
        sampleAction: {
          label: "Authorize & Dispatch PO-9002",
          description: "Signs PO-9002 with Director digital signature; locks price terms and dispatches PDF via automated SMTP webhook.",
          buttonText: "Simulate PO Authorization",
          successMessage: "PO-9002 authorized & dispatched. Delivery date set for 2026-10-24 at Pune Central Warehouse Dock.",
          sampleData: {
            poNumber: "PO-9002",
            vendor: "Acme Copper Ltd",
            grossAmount: "₹1,47,500 (Base ₹1,25,000 + GST ₹22,500)",
            deliveryTerms: "DAP Pune Central Warehouse",
            status: "Dispatched to Supplier",
          },
          ledgerImpact: "purchase_orders table updated to 'authorized'; commitment logged against procurement budget.",
        },
        keyTakeaway: "Tiered PO authorization prevents unauthorized spending and guarantees executive control over cash commitments.",
      },
      {
        stepNumber: 4,
        id: "p2p-grn",
        title: "Dock Inward Receiving, GRN & QR Lot Labeling",
        shortTitle: "Dock GRN",
        route: "/warehouse",
        navGroup: "Warehouse & Logistics",
        actorRole: "Warehouse Receiver (warehouse:read, grn:write)",
        department: "Warehouse Logistics",
        targetElementSelector: "button:has-text('New GRN')",
        description: "Acme delivery truck arrives at dock door 3. Warehouse receiver verifies physical packaging against PO-9002, creates Goods Receipt Note GRN-4401, and prints 2D serialized QR lot labels for quarantine inspection.",
        actionPrompt: "Receive 5,000m copper wire delivery, create GRN-4401, and print QR stickers for lot LOT-26-W01.",
        sampleAction: {
          label: "Create Goods Receipt Note GRN-4401",
          description: "Generates GRN-4401 for 5,000m copper wire. Status set to 'Dock Quarantine' pending QC clearance.",
          buttonText: "Simulate Dock GRN Generation",
          successMessage: "GRN-4401 created. 5 serialized 2D QR pallet labels printed. Raw materials moved to Quarantine Bay A.",
          sampleData: {
            grnNumber: "GRN-4401",
            poReference: "PO-9002",
            quantityReceived: "5,000 Meters",
            lotNumber: "LOT-26-W01",
            warehouseLocation: "Quarantine Bay A",
          },
          ledgerImpact: "goods_receipt_notes created; stock ledger debited with status='quarantine'.",
        },
        keyTakeaway: "Serialized QR labels establish lot traceability from the exact moment goods arrive on the factory dock.",
      },
      {
        stepNumber: 5,
        id: "p2p-invoice",
        title: "Vendor Invoice Ingestion & Automated 3-Way Matching",
        shortTitle: "3-Way Match",
        route: "/po-invoice",
        navGroup: "Finance",
        actorRole: "Accounts Payable Specialist (org:read, finance:read)",
        department: "Finance & Accounts Payable",
        targetElementSelector: "button:has-text('New Invoice')",
        description: "Supplier commercial invoice BILL-ACM-9901 is ingested. Simple ERP executes automated 3-way matching: PO-9002 line rates vs GRN-4401 accepted quantities vs Invoice bill totals with 0.00% variance.",
        actionPrompt: "Audit 3-way match triad and post Accounts Payable liability journal.",
        sampleAction: {
          label: "Execute Automated 3-Way Match",
          description: "Validates PO-9002 (₹1,47,500) == GRN-4401 (5,000m) == BILL-ACM-9901 (₹1,47,500). Verifies 18% GST input tax credit.",
          buttonText: "Simulate 3-Way Match Verification",
          successMessage: "3-Way Match passed with 0.00% variance. AP liability posted to General Ledger (Acme Copper credited ₹1,47,500).",
          sampleData: {
            invoiceNumber: "BILL-ACM-9901",
            poMatched: "PO-9002 (100% Match)",
            grnMatched: "GRN-4401 (100% Match)",
            variance: "₹0.00 (0.00%)",
            taxCreditEligible: "₹22,500 (GSTR-2B Claim)",
          },
          ledgerImpact: "vendor_invoices updated to 'approved'; gl_entries posted: Debit Inventory ₹1,25k, Debit Input Tax ₹22.5k, Credit AP ₹147.5k.",
        },
        keyTakeaway: "Automated 3-way matching prevents duplicate invoices, overbilling, and paying for rejected or unreceived materials.",
      },
      {
        stepNumber: 6,
        id: "p2p-payout",
        title: "Accounts Payable Disbursement & Bank Remittance",
        shortTitle: "Bank Payment",
        route: "/finance",
        navGroup: "Finance",
        actorRole: "Finance Controller (finance:read, finance:write)",
        department: "Treasury & Finance",
        targetElementSelector: "button:has-text('New payment')",
        description: "Treasury authorizes bank disbursement voucher PAY-8819. Dispatches RTGS wire instruction to HDFC Bank corporate gateway and clears Accounts Payable liability on the general ledger.",
        actionPrompt: "Authorize RTGS wire payment of ₹1,47,500 to Acme Copper Ltd to conclude Procure-to-Pay cycle.",
        sampleAction: {
          label: "Issue Payment Voucher PAY-8819",
          description: "Generates RTGS bank transfer instruction to Acme Copper's verified bank account; closes PO-9002 as Fully Paid.",
          buttonText: "Simulate RTGS Remittance Disbursement",
          successMessage: "Payment Voucher PAY-8819 executed via RTGS. Accounts Payable balance zeroed. P2P lifecycle closed!",
          sampleData: {
            paymentVoucher: "PAY-8819",
            beneficiary: "Acme Copper Industries Ltd",
            disbursedAmount: "₹1,47,500.00",
            bankReference: "RTGS-HDFC-9912048",
            poStatus: "Fully Reconciled & Closed",
          },
          ledgerImpact: "payment_vouchers created; gl_entries posted: Debit AP ₹1,47,500 / Credit Corporate Bank ₹1,47,500.",
        },
        keyTakeaway: "Integrated disbursement reconciliation eliminates manual bank statement chasing and closes the vendor audit loop.",
      },
    ],
  },

  // 4. Plan to Production
  {
    id: "plan-to-production",
    journeyNumber: 4,
    title: "4. Plan to Production",
    shortTitle: "Plan to Production",
    tagline: "Work Orders, Rough-Cut Capacity, FIFO Material Issues & In-Process QC Assembly",
    description: "Transform planned production schedules into shop-floor Work Orders, allocate machine assembly lines, stage raw materials under strict FIFO lot rotation, execute manufacturing routing, and receive Finished Goods into warehouse stock.",
    persona: "Production Manager & Plant Engineer",
    department: "Manufacturing Operations & Shop Floor",
    color: "#7c3aed",
    badgeClass: "bg-purple-500/15 text-purple-800 dark:text-purple-200 border-purple-500/30",
    borderClass: "border-purple-500",
    bgClass: "bg-purple-500/5",
    iconName: "Factory",
    estimatedMinutes: 5,
    steps: [
      {
        stepNumber: 1,
        id: "ptp-wo-release",
        title: "Work Order Release from Master Schedule",
        shortTitle: "Work Order Release",
        route: "/mrp",
        navGroup: "Planning & SCM",
        actorRole: "Production Planner (mrp:read, inventory:read)",
        department: "Production Planning",
        targetElementSelector: "button",
        description: "Convert MRP planned production requirements into formal Work Order WO-8001 for 400 units of SKU-MOT-500. Release to Pune Plant Line 1 schedule.",
        actionPrompt: "Release Work Order WO-8001 for 400 electric motors with scheduled completion in 5 days.",
        sampleAction: {
          label: "Release Work Order WO-8001",
          description: "Generates Work Order WO-8001; pulls multi-tier BOM recipe and schedules 400 units on Assembly Line 1.",
          buttonText: "Simulate Work Order Release",
          successMessage: "Work Order WO-8001 released to shop floor. Component pick list generated for warehouse staging.",
          sampleData: {
            woNumber: "WO-8001",
            targetSKU: "SKU-MOT-500 (500W Electric Motor)",
            plannedQuantity: "400 Units",
            targetPlant: "Pune Assembly Plant 1 (Line 1)",
            targetDate: "2026-10-29",
          },
          ledgerImpact: "work_orders table created with status='released'; component reservations placed in inventory.",
        },
        keyTakeaway: "Work orders convert abstract production plans into actionable shop-floor assembly tasks with committed component reservations.",
      },
      {
        stepNumber: 2,
        id: "ptp-capacity",
        title: "Rough-Cut Capacity Planning (RCCP) & Shift Balancing",
        shortTitle: "Capacity Planning",
        route: "/capacity-planning",
        navGroup: "Manufacturing",
        actorRole: "Industrial Engineer (capacity_planning:read)",
        department: "Manufacturing Engineering",
        targetElementSelector: "button",
        description: "Analyze machine center loading and operator labor shifts across Stator Winding, Rotor Insertion, and Final Dynamometer Testing to prevent manufacturing bottlenecks.",
        actionPrompt: "Evaluate Assembly Line 1 capacity: assign 2 shifts to ensure 92% optimal machine utilization without overtime.",
        sampleAction: {
          label: "Balance Line 1 Shift Capacity",
          description: "Validates 320 standard hours of machine time across 2 shifts; flags zero bottleneck risks.",
          buttonText: "Simulate Capacity Optimization",
          successMessage: "Line 1 capacity balanced at 92% utilization. Winding and assembly work centers cleared for execution.",
          sampleData: {
            assemblyLine: "Line 1 (SMT + Winding)",
            requiredHours: "320 Machine Hours",
            allocatedShifts: "2 Shifts (Shift A + Shift B)",
            bottleneckStatus: "Clear (Max station loading 92%)",
          },
          ledgerImpact: "work_center_schedules updated in database.",
        },
        keyTakeaway: "Rough-cut capacity planning guarantees work orders can actually be finished on time without overloading machines or staff.",
      },
      {
        stepNumber: 3,
        id: "ptp-material-issue",
        title: "FIFO Raw Material Lot Staging & Shop-Floor Execution",
        shortTitle: "Material Issue",
        route: "/production",
        navGroup: "Manufacturing",
        actorRole: "Shop Floor Lead (inventory:read, production:write)",
        department: "Shop Floor Assembly",
        targetElementSelector: "button:has-text('Issue Materials')",
        description: "Pick and stage raw materials from warehouse racks using strict First-In, First-Out lot rotation. Issue 5,000m copper wire (LOT-26-W01) from raw materials ledger into Work-In-Progress (WIP).",
        actionPrompt: "Execute FIFO component issue for WO-8001 and start assembly run on Line 1.",
        sampleAction: {
          label: "Issue Raw Material Lots to WO-8001",
          description: "Transfers 5,000m wire (LOT-26-W01), 400 rotor cores, and 800 bearings from warehouse storage into shop-floor WIP.",
          buttonText: "Simulate Material Issue to Line",
          successMessage: "Components issued via FIFO. Work-In-Progress ledger debited ₹3,00,000. Assembly run active on Line 1.",
          sampleData: {
            wireIssued: "5,000m from LOT-26-W01 (FIFO)",
            rotorsIssued: "400 Units from LOT-26-R02",
            bearingsIssued: "800 Units from LOT-26-B05",
            wipLedgerValue: "₹3,00,000.00",
          },
          ledgerImpact: "inventory_movements recorded; stock balances debited from raw materials and credited to WIP.",
        },
        keyTakeaway: "Strict FIFO lot issuance ensures component traceability so any supplier defect can be isolated to an exact production run.",
      },
      {
        stepNumber: 4,
        id: "ptp-ipqc-receipt",
        title: "In-Process QC (IPQC) & Finished Goods Receipt",
        shortTitle: "IPQC & Receipt",
        route: "/quality-ipqc",
        navGroup: "Manufacturing",
        actorRole: "Quality Assurance Chemist (quality_ipqc:read)",
        department: "Quality Assurance",
        targetElementSelector: "button",
        description: "Perform shop-floor electrical insulation and torque dynamometer testing on assembled motors. Generate Certificate of Analysis (CoA) and receive 400 completed Finished Goods into available inventory.",
        actionPrompt: "Record 100% pass on dynamometer torque testing and receive 400 units of SKU-MOT-500 into Finished Goods storage.",
        sampleAction: {
          label: "Complete IPQC & Receive Finished Goods",
          description: "Approves CoA QC-IPQC-881; closes Work Order WO-8001 and moves 400 motors from WIP into Finished Goods warehouse storage.",
          buttonText: "Simulate IPQC Clearance & FG Receipt",
          successMessage: "400 units of SKU-MOT-500 received into Finished Goods inventory (BIN-FG-01). Standard asset value: ₹3,00,000.",
          sampleData: {
            ipqcInspection: "QC-IPQC-881 (Passed 400/400)",
            finishedGoodsLot: "LOT-FG-2026-M400",
            receivedQuantity: "400 Units",
            destinationBin: "BIN-FG-01 (Pune Finished Goods)",
            woStatus: "Completed & Closed",
          },
          ledgerImpact: "inventory updated: WIP debited, Finished Goods credited; work_orders status='completed'.",
        },
        keyTakeaway: "Mandatory in-process quality gates ensure defective assemblies are caught on the line before ever reaching customers.",
      },
    ],
  },

  // 5. Order to Cash (O2C)
  {
    id: "order-to-cash",
    journeyNumber: 5,
    title: "5. Order to Cash (O2C)",
    shortTitle: "Order to Cash",
    tagline: "B2B Sales Orders, Credit Checks, Row-Locked Stock Allocation, Wave Picking & e-Way Bill Dispatch",
    description: "Manage the enterprise revenue lifecycle: capture customer sales orders, execute real-time credit limit audits, lock inventory rows with zero overselling, wave pick with mobile barcode scanners, and generate statutory GST e-Way bills.",
    persona: "B2B Sales Lead & Outbound Dispatch Manager",
    department: "Commercial Sales & Outbound Logistics",
    color: "#d97706",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200 border-amber-500/30",
    borderClass: "border-amber-500",
    bgClass: "bg-amber-500/5",
    iconName: "ClipboardList",
    estimatedMinutes: 5,
    steps: [
      {
        stepNumber: 1,
        id: "otc-so-entry",
        title: "B2B Sales Order Entry & Automated Credit Limit Audit",
        shortTitle: "Sales Order",
        route: "/orders",
        navGroup: "Sales & Orders",
        actorRole: "Commercial Sales Officer (order:read, order:write)",
        department: "B2B Commercial Sales",
        targetElementSelector: "button:has-text('New order')",
        description: "Book sales order SO-5001 from customer Bharat Industrial Dynamics for 100 units of SKU-MOT-500 (₹4,20,000 + GST). System audits customer credit limit (₹10,00,000) and outstanding balance.",
        actionPrompt: "Create Sales Order SO-5001 for 100 electric motors and verify credit check clearance.",
        sampleAction: {
          label: "Book Sales Order SO-5001",
          description: "Enters SO-5001. Customer credit check passes (Exposure: ₹4,95,600 vs ₹10,00,000 limit). Order confirmed.",
          buttonText: "Simulate Sales Order Booking",
          successMessage: "Sales Order SO-5001 booked and confirmed. Credit limit audited and approved.",
          sampleData: {
            orderNumber: "SO-5001",
            customer: "Bharat Industrial Dynamics Ltd",
            skuOrdered: "SKU-MOT-500 (100 Units)",
            totalOrderValue: "₹4,95,600 (Base ₹4,20,000 + 18% GST)",
            creditStatus: "Approved (Exposure: 49.5% of limit)",
          },
          ledgerImpact: "orders and order_items rows inserted with status='confirmed'.",
        },
        keyTakeaway: "Real-time credit limit validation protects company cash flow by blocking shipments to delinquent accounts.",
      },
      {
        stepNumber: 2,
        id: "otc-allocation",
        title: "Row-Locked FIFO Inventory Allocation",
        shortTitle: "Stock Allocation",
        route: "/orders",
        navGroup: "Sales & Orders",
        actorRole: "Fulfillment Coordinator (order:read, inventory:read)",
        department: "Order Fulfillment",
        targetElementSelector: "button",
        description: "Execute database row-level locking (`SELECT FOR UPDATE`) against Finished Goods inventory to reserve 100 units of SKU-MOT-500 from LOT-FG-2026-M400, eliminating risk of overselling.",
        actionPrompt: "Allocate 100 units from Finished Goods inventory to SO-5001.",
        sampleAction: {
          label: "Allocate 100 Motors to SO-5001",
          description: "Locks 100 units to SO-5001. Available-to-Promise (ATP) stock decrements from 400 to 300 units.",
          buttonText: "Simulate Inventory Row Allocation",
          successMessage: "100 units allocated to SO-5001 with row-level lock. Zero overselling risk.",
          sampleData: {
            allocatedSKU: "SKU-MOT-500",
            quantityAllocated: "100 Units",
            sourceLot: "LOT-FG-2026-M400",
            remainingATP: "300 Units Available",
          },
          ledgerImpact: "inventory_allocations row inserted; order status='allocated'.",
        },
        keyTakeaway: "Row-locked inventory allocation ensures that stock promised to a customer cannot be accidentally poached by another salesperson.",
      },
      {
        stepNumber: 3,
        id: "otc-wave-picking",
        title: "Wave Picking & Mobile Barcode Verification",
        shortTitle: "Wave Picking",
        route: "/wave-picking",
        navGroup: "Warehouse & Logistics",
        actorRole: "Warehouse Pick Supervisor (wave_picking:read)",
        department: "Outbound Logistics",
        targetElementSelector: "button",
        description: "Consolidate orders into outbound wave WAVE-042. Direct picker along the shortest travel path through Finished Goods aisles using mobile barcode scanners to scan each carton QR code.",
        actionPrompt: "Release picking wave WAVE-042 and confirm scan verification of 100 motor cartons.",
        sampleAction: {
          label: "Release & Confirm Wave Picking",
          description: "Directs picker to BIN-FG-01. Mobile scanner verifies 100% of carton barcodes match SO-5001 specifications.",
          buttonText: "Simulate Wave Pick & Pack",
          successMessage: "Wave WAVE-042 picked and packed into 10 master pallets with verified barcode manifest.",
          sampleData: {
            waveId: "WAVE-042",
            pickLocation: "BIN-FG-01 (Pune Finished Goods)",
            itemsPicked: "100 Units (100% verified)",
            packType: "10 Wooden Crates on Heat-Treated Pallets",
          },
          ledgerImpact: "wave_picks updated to 'picked'; goods staged at Outbound Bay 1.",
        },
        keyTakeaway: "Barcode-directed wave picking cuts warehouse travel time by 40% and virtually eliminates mis-picks.",
      },
      {
        stepNumber: 4,
        id: "otc-shipping-eway",
        title: "Carrier Booking, AWB & Statutory GST e-Way Bill",
        shortTitle: "e-Way Bill & Dispatch",
        route: "/shipping-engine",
        navGroup: "Warehouse & Logistics",
        actorRole: "Outbound Logistics Lead (shipping_engine:read)",
        department: "Outbound Freight TMS",
        targetElementSelector: "button",
        description: "Assign commercial carrier (Blue Dart Logistics), generate Air Waybill AWB-7721, and communicate via API with the national NIC portal to generate the statutory GST e-Way Bill and tax invoice IRN QR code.",
        actionPrompt: "Generate e-Way Bill EWB-9921 and carrier dispatch manifest for vehicle MH-14-CC-5678.",
        sampleAction: {
          label: "Generate e-Way Bill & Dispatch Truck",
          description: "Generates statutory e-Way Bill EWB-9921 and AWB-7721 with encrypted IRN QR code for vehicle highway transit.",
          buttonText: "Simulate Carrier Dispatch & e-Way Bill",
          successMessage: "e-Way Bill EWB-9921 generated. Truck MH-14-CC-5678 dispatched from Outbound Bay 1.",
          sampleData: {
            carrier: "Blue Dart Express Logistics",
            awbNumber: "AWB-7721-BD",
            ewayBillNumber: "EWB-9921-2026-MH",
            vehicleNumber: "MH-14-CC-5678",
            transitStatus: "In-Transit to Customer",
          },
          ledgerImpact: "shipments recorded; statutory_logistics log registered; order status='dispatched'.",
        },
        keyTakeaway: "Automated e-Way bill and IRN generation ensures transport trucks are never delayed or penalized at state border checkpoints.",
      },
      {
        stepNumber: 5,
        id: "otc-ar-invoice",
        title: "Accounts Receivable Commercial Invoicing & Ledger",
        shortTitle: "AR Invoicing",
        route: "/finance",
        navGroup: "Finance",
        actorRole: "Finance Billing Accountant (finance:read, org:read)",
        department: "Finance & Accounts Receivable",
        targetElementSelector: "button",
        description: "Generate commercial tax invoice INV-2026-001 upon vehicle gate dispatch. Post double-entry accounting entries: Debit Accounts Receivable (₹4,95,600), Credit Sales Revenue (₹4,20,000), Credit Output GST (₹75,600).",
        actionPrompt: "Post final sales invoice INV-2026-001 and establish Accounts Receivable ledger balance.",
        sampleAction: {
          label: "Post Sales Invoice INV-2026-001",
          description: "Generates GST-compliant commercial tax invoice; books ₹4,20,000 revenue and establishes customer AR receivable.",
          buttonText: "Simulate AR Invoice & Ledger Posting",
          successMessage: "Tax Invoice INV-2026-001 posted. Revenue recognized. Order-to-Cash cycle completed successfully!",
          sampleData: {
            taxInvoice: "INV-2026-001",
            billedCustomer: "Bharat Industrial Dynamics Ltd",
            grossReceivable: "₹4,95,600 (Net-30 Terms)",
            revenueRecognized: "₹4,20,000.00",
            outputGstPayable: "₹75,600.00",
          },
          ledgerImpact: "customer_invoices created; gl_entries posted: Debit AR ₹4,95,600 / Credit Revenue ₹4,20,000, Credit GST ₹75,600.",
        },
        keyTakeaway: "Automatic invoice posting upon dispatch ensures accurate revenue recognition and prevents unbilled shipments.",
      },
    ],
  },

  // 6. Inventory & Warehouse Management
  {
    id: "inventory-management",
    journeyNumber: 6,
    title: "6. Inventory Management",
    shortTitle: "Inventory & WMS",
    tagline: "Inbound ASN, Dock Receiving, AQL QC Sampling, Directed Bins, Cycle Counts & RMA Returns",
    description: "Operate end-to-end modern warehouse logistics: security gate check-ins with Gate Passes, dock pallet intake, AQL quality control sampling, directed high-density bin putaway, continuous cycle counts, and reverse logistics returns (RMA).",
    persona: "Warehouse Supervisor & QC Inspector",
    department: "Warehouse Logistics & Quality Assurance",
    color: "#059669",
    badgeClass: "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200 border-emerald-500/30",
    borderClass: "border-emerald-500",
    bgClass: "bg-emerald-500/5",
    iconName: "Warehouse",
    estimatedMinutes: 5,
    steps: [
      {
        stepNumber: 1,
        id: "inv-gate-checkin",
        title: "Inbound Logistics TMS, Vendor ASN & Gate Check-In",
        shortTitle: "Gate Check-In",
        route: "/logistics",
        navGroup: "Warehouse & Logistics",
        actorRole: "Security Gatekeeper (logistics:read)",
        department: "Factory Gate Security",
        targetElementSelector: "button:has-text('Gate entry')",
        description: "Monitor carrier vehicle transit via supplier Advanced Shipping Notice (ASN-1092). Record vehicle arrival at plant gate, inspect driver paperwork, and generate Security Gate Pass GP-1092.",
        actionPrompt: "Log carrier truck arrival at Gate 2 and issue Gate Pass GP-1092.",
        sampleAction: {
          label: "Issue Security Gate Pass GP-1092",
          description: "Records arrival of vehicle MH-12-AB-1234 carrying Acme Copper delivery; issues Gate Pass GP-1092 directing truck to Dock Bay 3.",
          buttonText: "Simulate Gate Check-In",
          successMessage: "Gate Pass GP-1092 issued. Delivery truck routed to Dock Bay 3 for pallet unloading.",
          sampleData: {
            gatePassNumber: "GP-1092",
            vehicleNumber: "MH-12-AB-1234",
            supplierASN: "ASN-1092 (Acme Copper)",
            assignedDock: "Dock Bay 3",
          },
          ledgerImpact: "gate_entries table updated; dock schedule updated in real-time.",
        },
        keyTakeaway: "Gate check-ins ensure that all incoming vehicles are authorized and matched against active POs before entering the facility.",
      },
      {
        stepNumber: 2,
        id: "inv-dock-grn",
        title: "Dock Inward Receiving & 2D QR Lot Label Printing",
        shortTitle: "Dock Receiving",
        route: "/warehouse",
        navGroup: "Warehouse & Logistics",
        actorRole: "Dock Receiver (warehouse:read, grn:write)",
        department: "Inbound Receiving",
        targetElementSelector: "button:has-text('New GRN')",
        description: "Unload delivery pallets at dock door 3, inspect physical packaging against PO-9002, generate Goods Receipt Note GRN-4401, and print serialized 2D QR lot labels for quarantine inspection.",
        actionPrompt: "Receive 5,000m copper wire delivery, create GRN-4401, and print QR stickers for lot LOT-26-W01.",
        sampleAction: {
          label: "Generate GRN-4401 & Print QR Labels",
          description: "Creates GRN-4401 for 5,000m wire; prints 5 serialized 2D QR pallet labels and moves goods into Quarantine Bay A.",
          buttonText: "Simulate Dock GRN & QR Printing",
          successMessage: "GRN-4401 created. 5 QR pallet tags printed. Stock moved to Quarantine Bay A.",
          sampleData: {
            grnNumber: "GRN-4401",
            poNumber: "PO-9002",
            quantity: "5,000 Meters",
            quarantineLot: "LOT-26-W01",
          },
          ledgerImpact: "goods_receipt_notes created; stock ledger debited with status='quarantine'.",
        },
        keyTakeaway: "Pallet QR labels enable rapid mobile barcode scanning throughout the entire warehouse lifecycle.",
      },
      {
        stepNumber: 3,
        id: "inv-qc-clearance",
        title: "Quality Control (QC), AQL Sampling & Lot Clearance",
        shortTitle: "QC Clearance",
        route: "/warehouse-qc",
        navGroup: "Warehouse & Logistics",
        actorRole: "Quality Control Chemist (warehouse:read)",
        department: "Quality Assurance",
        targetElementSelector: "button",
        description: "Pull ISO 2859-1 sample specimens from Quarantine Bay A, execute wire conductivity and insulation testing, attach Certificate of Analysis (CoA), and clear lot from Quarantine to Approved status.",
        actionPrompt: "Record QC sampling results, verify 0 defects, and approve lot LOT-26-W01 for warehouse putaway.",
        sampleAction: {
          label: "Approve QC Certificate QC-PASS-4401",
          description: "Logs zero defects in 32 sample specimens; approves Certificate of Analysis and unlocks lot for high-density bin putaway.",
          buttonText: "Simulate QC Lot Approval",
          successMessage: "QC clearance approved (QC-PASS-4401). Lot LOT-26-W01 unlocked for directed putaway.",
          sampleData: {
            qcRecordId: "QC-PASS-4401",
            lotNumber: "LOT-26-W01",
            samplesTested: "32 Specimens (AQL 0.65 Level II)",
            testResults: "Conductivity: 100.8% IACS | Insulation: 5.2 kV (Passed)",
            disposition: "Approved for Storage",
          },
          ledgerImpact: "qc_inspections created; stock ledger status changed from 'quarantine' to 'approved'.",
        },
        keyTakeaway: "Formal QC sampling prevents substandard raw materials from entering production lines and creating defective assemblies.",
      },
      {
        stepNumber: 4,
        id: "inv-wms-putaway",
        title: "Directed WMS Bins & Double-Entry Stock Ledger Putaway",
        shortTitle: "Directed Putaway",
        route: "/wms-bins",
        navGroup: "Warehouse & Logistics",
        actorRole: "Forklift Operator (wms_bins:read, warehouse:read)",
        department: "WMS Storage Operations",
        targetElementSelector: "button",
        description: "WMS algorithm computes optimal storage slot based on SKU velocity and dimensions. Forklift operator scans rack barcode at Aisle A, Bay 03, Shelf 2 to complete directed putaway into Available stock.",
        actionPrompt: "Scan destination bin BIN-A-03-02 and confirm putaway of 5,000m copper wire into Available stock.",
        sampleAction: {
          label: "Execute Directed Putaway into BIN-A-03-02",
          description: "Scans rack barcode; updates double-entry stock ledger: debits Staging Bay A and credits BIN-A-03-02 with status='Available'.",
          buttonText: "Simulate Directed Bin Putaway",
          successMessage: "Putaway confirmed. 5,000m copper wire stored in BIN-A-03-02. Stock is now available for production.",
          sampleData: {
            destinationBin: "BIN-A-03-02 (Aisle A, Bay 03, Shelf 2)",
            quantityStored: "5,000 Meters",
            stockStatus: "Available for Manufacturing",
            wmsRoute: "Optimal travel path: 38 meters",
          },
          ledgerImpact: "inventory_movements recorded; stock balance active at specific bin location.",
        },
        keyTakeaway: "Directed bin putaway optimizes warehouse space utilization and eliminates lost inventory.",
      },
      {
        stepNumber: 5,
        id: "inv-cycle-counts",
        title: "ABC Velocity Cycle Counting & Variance Reconciliation",
        shortTitle: "Cycle Counting",
        route: "/cycle-counts",
        navGroup: "Warehouse & Logistics",
        actorRole: "Inventory Controller (cycle_count:read)",
        department: "Inventory Control",
        targetElementSelector: "button:has-text('New count')",
        description: "Initiate ABC velocity cycle counting routine for high-value Class-A items. Operator performs blind physical counts with mobile scanner, reconciling physical stock with system ledger records.",
        actionPrompt: "Execute cycle count CC-2026-10 for high-velocity raw materials in Aisle A.",
        sampleAction: {
          label: "Execute Cycle Count CC-2026-10",
          description: "Performs blind count across 15 high-value bins; reports 99.8% inventory record accuracy (IRA) with zero material variance.",
          buttonText: "Simulate Cycle Count Reconciliation",
          successMessage: "Cycle count CC-2026-10 completed. Inventory Record Accuracy verified at 99.8%.",
          sampleData: {
            countId: "CC-2026-10",
            category: "Class-A High-Value Inventory",
            accuracyRate: "99.8% (0 critical variances)",
            auditCertification: "ISO 9001 Inventory Control Stamp",
          },
          ledgerImpact: "cycle_counts table recorded with timestamp and operator sign-off.",
        },
        keyTakeaway: "Regular cycle counting maintains 99%+ inventory accuracy year-round without shutting down plants for annual physical audits.",
      },
      {
        stepNumber: 6,
        id: "inv-returns-rma",
        title: "Reverse Logistics, Customer RMA Intake & Technical Triage",
        shortTitle: "Returns & RMA",
        route: "/returns",
        navGroup: "Warehouse & Logistics",
        actorRole: "Returns Specialist (returns:read, warehouse:read)",
        department: "Reverse Logistics",
        targetElementSelector: "button:has-text('New return')",
        description: "Authorize customer Return Merchandise Authorization (RMA-201) for warranty inspection. Receive returned motor at reverse dock, perform technical triage, and issue Credit Note to conclude reverse logistics.",
        actionPrompt: "Process customer return RMA-201, inspect unit at return triage bay, and authorize Credit Note.",
        sampleAction: {
          label: "Authorize Customer RMA-201 & Credit Note",
          description: "Receives returned motor; technical triage confirms minor bearing defect; authorizes credit note CR-101 for customer refund.",
          buttonText: "Simulate RMA Intake & Credit Note",
          successMessage: "RMA-201 processed. Unit routed to refurbishment line; credit note CR-101 issued. Full inventory loop complete!",
          sampleData: {
            rmaNumber: "RMA-201",
            originalOrder: "SO-5001",
            triageDisposition: "Refurbish & Restock (Minor Bearing Wear)",
            creditNoteIssued: "CR-101 (₹4,956.00)",
          },
          ledgerImpact: "customer_returns created; credit_notes table updated; inventory updated in refurbishment warehouse.",
        },
        keyTakeaway: "Structured RMA triage protects customer trust while recovering salvageable value through refurbishment.",
      },
    ],
  },
];

export const DEMO_FLOW_STEPS: DemoFlowStep[] = [

    {
    stepNumber: 1,
    id: "users-security",
    title: "Users, Roles & Site Access Governance",
    shortTitle: "1. Users & Roles",
    route: "/users",
    navGroup: "Administration",
    phase: "Phase 1: Enterprise Foundation & Master Setup",
    stream: "Governance",
    category: "Master Data & Setup",
    iconName: "ShieldCheck",
    actorRole: "System Administrator (user:read, user:write, user:assign_role)",
    summary: "Manages enterprise personnel accounts, RBAC permission roles, MFA enforcement, and site-scoped access to specific factories and warehouses.",
    businessPurpose:
      "Enforces the principle of least privilege: operators only see buttons and data appropriate to their job, and multi-facility workers cannot tamper with inventory at plants where they do not work.",
    keyObjectives: [
      "Create user accounts with secure Argon2id hashed credentials and email invitation handshakes.",
      "Assign granular RBAC roles (Lead Buyer, QC Chemist, Warehouse Lead, Accounts Payable).",
      "Scope users to specific physical warehouses and factories (`user_role_warehouses`, `user_role_factories`).",
    ],
    workflows: [
      {
        id: "usr-invite-assign",
        actionNumber: 1,
        title: "Invite Operator & Assign Granular RBAC Role",
        shortTitle: "Invite User",
        actor: "Security Admin",
        permissionRequired: "user:write",
        triggerEvent: "New employee onboarding in Procurement / Warehouse",
        stepByStepInstructions: [
          "Navigate to 'Users & roles' (/users).",
          "Click '+ Invite User' in the header toolbar.",
          "Enter user full name (e.g. 'Rahul Sharma') and corporate email ('rahul.s@axon-industries.com').",
          "Select Role: 'Warehouse Receiver' (grants `warehouse:read`, `warehouse:receive`, `grn:write`).",
          "Click 'Send Invitation Email' to dispatch onboarding link.",
        ],
        systemValidations: [
          "Email must be unique and have valid RFC 5322 syntax.",
          "Role must exist in the system roles dictionary.",
        ],
        tablesAndLedgersMutated: [
          "users table (insert user with status='invited')",
          "user_roles table (bind user to role)",
        ],
        outputDocument: "User Invitation Token & Account Record",
        simulation: {
          scenarioDescription: "Onboarding Warehouse Operator Rahul Sharma with 'Warehouse Receiver' role.",
          initialState: "Unregistered Operator",
          buttonLabel: "Simulate User Onboarding",
          successState: "User Invited & Role Assigned",
          executionLog: [
            "Generating secure invitation token ✓",
            "Creating user record rahul.s@axon-industries.com in Postgres ✓",
            "Assigning role 'Warehouse Receiver' with 4 permissions ✓",
            "Queueing invite email via SMTP worker ✓",
          ],
          databaseEffect: "users row created; user_roles junction record inserted.",
        },
      },
      {
        id: "usr-site-scope",
        actionNumber: 2,
        title: "Enforce Multi-Facility Site Scoping",
        shortTitle: "Scope Site Access",
        actor: "Security Admin",
        permissionRequired: "user:write",
        triggerEvent: "Restricting operator access to specific physical facility",
        stepByStepInstructions: [
          "Click on the newly created user record in the Users table.",
          "Under the 'Facility Scope' tab, toggle 'Restrict to Authorized Facilities'.",
          "Select Warehouse: 'WH-PUNE-01' and Factory: 'FACT-PUNE-01'.",
          "Click 'Save Facility Scope'.",
        ],
        systemValidations: [
          "User queries across Inventory, GRN, and Production automatically filter by WHERE warehouse_id IN ('WH-PUNE-01').",
          "Cross-facility tampering returns HTTP 403 Forbidden.",
        ],
        tablesAndLedgersMutated: [
          "user_role_warehouses table",
          "user_role_factories table",
        ],
        outputDocument: "Site Scoping Enforcement Matrix",
        simulation: {
          scenarioDescription: "Restricting Rahul Sharma strictly to Pune Warehouse (WH-PUNE-01).",
          initialState: "Global Access (Unscoped)",
          buttonLabel: "Simulate Site Scoping",
          successState: "Site Scope Enforced: WH-PUNE-01 Only",
          executionLog: [
            "Inserting WH-PUNE-01 into user_role_warehouses ✓",
            "Casbin policy rules updated in memory ✓",
            "User sessions restricted from querying Mumbai or Bangalore stock ✓",
          ],
          databaseEffect: "user_role_warehouses junction record committed.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Facilities & Factories",
        route: "/factory-warehouse",
        document: "Facility Master",
        dataPassed: "Available warehouse and factory IDs for scoping.",
        relationship: "Users are scoped to physical facilities",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "All ERP Modules",
        route: "/",
        document: "Security Context & Session Token",
        dataPassed: "User ID, permissions array, authorized facility IDs.",
        relationship: "Injected into every API request header for authorization",
      },
      {
        moduleName: "Audit Trail",
        route: "/audit",
        document: "User Attribution",
        dataPassed: "Email and User ID stamped onto every database mutation.",
        relationship: "Provides accountability for audit trail",
      },
    ],
    businessControls: [
      "Root System Admin role cannot be deleted or unassigned.",
      "Failed login attempts > 5 lock the account for 15 minutes to prevent brute-force attacks.",
    ],
  },

  // STEP 4: PARTIES & AVL,

    {
    stepNumber: 2,
    id: "facilities-warehouses",
    title: "Facilities, Factories & Warehouse Topography",
    shortTitle: "2. Factories & Facilities",
    route: "/factory-warehouse",
    navGroup: "Administration",
    phase: "Phase 1: Enterprise Foundation & Master Setup",
    stream: "Warehouse & WMS",
    category: "Master Data & Setup",
    iconName: "Factory",
    actorRole: "Operations Director / Industrial Engineer (warehouse:read, warehouse:write)",
    summary: "Sets up physical manufacturing plants, distribution warehouses, dock receiving bays, and storage zones.",
    businessPurpose:
      "All physical inventory, assembly lines, and receiving docks belong to a specific physical facility. Multi-facility tracking ensures stock balances and manufacturing capacities are partitioned accurately.",
    keyObjectives: [
      "Create manufacturing factories with assembly line capacities and working shift calendars.",
      "Configure central and regional distribution warehouses with designated staging bays.",
      "Enforce site-level multi-tenancy so users only access their assigned physical plants.",
    ],
    workflows: [
      {
        id: "fac-create-plant",
        actionNumber: 1,
        title: "Define Manufacturing Plant & Production Lines",
        shortTitle: "Create Plant",
        actor: "Operations Director",
        permissionRequired: "factory:write",
        triggerEvent: "Plant commissioning or expansion",
        stepByStepInstructions: [
          "Navigate to 'Factory & Warehouse' (/factory-warehouse).",
          "Under the 'Factories' tab, click '+ New Factory'.",
          "Provide Factory Code (e.g. 'FACT-PUNE-01') and Name ('Pune Assembly Plant 1').",
          "Link to owning Legal Entity ('Axon Industries Pvt Ltd').",
          "Specify operating address, timezone, and production line count (e.g. 3 lines).",
          "Click 'Save Factory'.",
        ],
        systemValidations: [
          "Factory code must be unique across the tenant database.",
          "Owning legal entity must be active.",
        ],
        tablesAndLedgersMutated: ["factories table (new plant record)"],
        outputDocument: "Factory Facility Record (FACT-PUNE-01)",
        simulation: {
          scenarioDescription: "Commissioning Pune Assembly Plant 1 with 3 SMT and Assembly Lines.",
          initialState: "Unmapped Facility",
          buttonLabel: "Simulate Factory Creation",
          successState: "Factory FACT-PUNE-01 Commissioned",
          executionLog: [
            "Verifying entity ENT-001 active status ✓",
            "Assigning facility code FACT-PUNE-01 ✓",
            "Creating 3 production lines in plant topology ✓",
            "Manufacturing scheduler enabled for plant ✓",
          ],
          databaseEffect: "factories table row inserted; production line capacity initialized.",
        },
      },
      {
        id: "fac-create-warehouse",
        actionNumber: 2,
        title: "Configure Receiving Warehouse & Staging Bays",
        shortTitle: "Create Warehouse",
        actor: "Warehouse Manager",
        permissionRequired: "warehouse:write",
        triggerEvent: "Warehouse setup for inbound goods intake",
        stepByStepInstructions: [
          "Under 'Warehouses' tab, click '+ New Warehouse'.",
          "Enter Warehouse Code (e.g. 'WH-PUNE-01') and Name ('Pune Central Warehouse').",
          "Designate operational zones: Inbound Dock Staging, Quarantine Bay, Active Storage, Outbound Shipping.",
          "Save warehouse record.",
        ],
        systemValidations: [
          "Warehouse code must be unique.",
          "Facility must have at least one Inbound Staging Bay and one Quarantine Bay configured.",
        ],
        tablesAndLedgersMutated: ["warehouses table (new warehouse record)"],
        outputDocument: "Warehouse Master (WH-PUNE-01)",
        simulation: {
          scenarioDescription: "Setting up Pune Central Warehouse with dock receiving and quarantine bays.",
          initialState: "No Inbound Docks Configured",
          buttonLabel: "Simulate Warehouse Setup",
          successState: "Warehouse WH-PUNE-01 Active",
          executionLog: [
            "Creating warehouse WH-PUNE-01 in Postgres ✓",
            "Configuring Inbound Dock Bay 1 & Bay 2 ✓",
            "Creating QC Quarantine Hold Zone ✓",
            "Stock ledger partitions created for warehouse ✓",
          ],
          databaseEffect: "warehouses table row inserted; GRN intake enabled for WH-PUNE-01.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Business Entities",
        route: "/po-invoice",
        document: "Corporate Owner",
        dataPassed: "Legal Entity ENT-001 owning the facility.",
        relationship: "Ownership hierarchy",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "WMS Directed Bins",
        route: "/wms-bins",
        document: "Warehouse Geometry",
        dataPassed: "Warehouse WH-01 parent container for aisles, racks, and bins.",
        relationship: "Bins reside inside Warehouses",
      },
      {
        moduleName: "Users & Site Access Scoping",
        route: "/users",
        document: "Facility Access List",
        dataPassed: "Factory and Warehouse IDs available for user permission binding.",
        relationship: "Enforces physical user access boundaries",
      },
    ],
    businessControls: [
      "Physical inventory cannot be posted to non-existent or inactive warehouse facilities.",
      "Warehouse deletion is hard-blocked if any stock ledger rows exist.",
    ],
  },

  // STEP 3: USERS & ROLES,

    {
    stepNumber: 3,
    id: "products-bom-catalog",
    title: "Product Master Catalog & Engineering BOM Recipes",
    shortTitle: "3. Products & BOM",
    route: "/products",
    navGroup: "Administration",
    phase: "Phase 1: Enterprise Foundation & Master Setup",
    stream: "Plan-to-Produce",
    category: "Master Data & Setup",
    iconName: "Boxes",
    actorRole: "Product Manager / Engineering (product:read, bom:write)",
    summary: "Defines central SKU identities, standard valuation costs, HSN tax classifications, and multi-level Bill of Materials (BOM) assembly recipes.",
    businessPurpose:
      "Every material purchased, assembled, stocked, or sold references an SKU. Multi-level BOMs provide the exact component recipe for MRP planning and manufacturing runs.",
    keyObjectives: [
      "Define serialized Finished Goods (FG) and raw material (RM) components with HSN codes.",
      "Construct multi-level BOM trees with component multipliers, scrap percentages, and work centers.",
      "Lock engineering revisions (BOM-v1) to prevent unauthorized recipe changes during live production.",
    ],
    workflows: [
      {
        id: "prd-create-sku",
        actionNumber: 1,
        title: "Register Item Master SKU & Standard Cost",
        shortTitle: "Create SKU",
        actor: "Catalog Engineer",
        permissionRequired: "product:write",
        triggerEvent: "New product development or component introduction",
        stepByStepInstructions: [
          "Navigate to 'Product Catalog' (/products).",
          "Click '+ New Product' button.",
          "Enter SKU Code (e.g. 'SKU-MOT-500') and Name ('500W Industrial Electric Motor').",
          "Select Category: 'Finished Goods' and Unit of Measure (UOM): 'Unit'.",
          "Enter HSN Code '8501' (Electric Motors - 18% GST).",
          "Specify Standard Cost: ₹750.00 and Selling Price: ₹1,200.00.",
          "Click 'Save Product Master'.",
        ],
        systemValidations: [
          "SKU code must be unique across the tenant.",
          "HSN code must exist in GST tax schedule.",
        ],
        tablesAndLedgersMutated: ["products table (new SKU row)"],
        outputDocument: "Item Master Record (SKU-MOT-500)",
        simulation: {
          scenarioDescription: "Creating finished good SKU-MOT-500 (500W Electric Motor).",
          initialState: "Unregistered Item",
          buttonLabel: "Simulate SKU Registration",
          successState: "SKU-MOT-500 Registered & Active",
          executionLog: [
            "Validating HSN code 8501 (18% GST Bracket) ✓",
            "Checking SKU code uniqueness in Postgres ✓",
            "Setting standard valuation cost: ₹750.00 ✓",
            "Publishing SKU to Inventory and Sales catalogs ✓",
          ],
          databaseEffect: "products row committed with active=true.",
        },
      },
      {
        id: "prd-create-bom",
        actionNumber: 2,
        title: "Build Multi-Level Engineering BOM & Lock Revision",
        shortTitle: "Build & Lock BOM",
        actor: "Production Engineer",
        permissionRequired: "bom:write",
        triggerEvent: "Engineering release of assembly recipe",
        stepByStepInstructions: [
          "In the Product Catalog, click on 'SKU-MOT-500' and open the 'BOM Recipe' tab.",
          "Click '+ Create New BOM Revision'.",
          "Enter Revision Name: 'BOM-MOT-V1'.",
          "Add Child Component 1: 'SKU-ROTOR-01', Qty: 1.0 Unit, Scrap Allowance: 1%.",
          "Add Child Component 2: 'SKU-STATOR-01', Qty: 1.0 Unit, Scrap Allowance: 1%.",
          "Add Child Component 3: 'SKU-COPPER-WIRE', Qty: 10.0 Meters, Scrap Allowance: 3%.",
          "Click 'Lock Engineering Revision' to make this BOM active for MRP explosion.",
        ],
        systemValidations: [
          "Recursive child-parent loops strictly blocked by graph traversal validation.",
          "Locked revisions cannot be edited once active production orders exist.",
        ],
        tablesAndLedgersMutated: [
          "boms table (header record)",
          "bom_items table (child component lines)",
        ],
        outputDocument: "Locked BOM Specification (BOM-MOT-V1)",
        simulation: {
          scenarioDescription: "Constructing and locking BOM-MOT-V1 with Rotor, Stator, and Copper Wire.",
          initialState: "No Assembly Recipe Attached",
          buttonLabel: "Simulate Lock BOM-MOT-V1",
          successState: "BOM-MOT-V1 Locked & Active for MRP",
          executionLog: [
            "Validating non-recursive component graph ✓",
            "Calculating rolled-up standard cost: ₹750.00 ✓",
            "Generating SHA-256 engineering lock signature ✓",
            "BOM status marked 'Active' for MRP engine ✓",
          ],
          databaseEffect: "boms and bom_items rows inserted with is_locked=true.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Facilities & Factories",
        route: "/factory-warehouse",
        document: "Operating Facility",
        dataPassed: "Manufacturing plants capable of assembling this SKU.",
        relationship: "Product routing relies on facilities",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Demand Forecasting & MRP",
        route: "/forecasting",
        document: "BOM Recipe & Components",
        dataPassed: "Parent SKUs and child component ratios for demand netting.",
        relationship: "MRP uses BOM to calculate raw material needs",
      },
      {
        moduleName: "Sales Catalog & Orders",
        route: "/orders",
        document: "Sellable SKUs",
        dataPassed: "Active items, prices, and tax rates for customer sales orders.",
        relationship: "Customers buy registered SKUs",
      },
    ],
    businessControls: [
      "BOM revisions locked once associated with an active production work order.",
      "Zero-unit component lines are blocked at API validation layer.",
    ],
  },

  // =========================================================================
  // PHASE 2: DEMAND PLANNING & SOURCING (Plan-to-Procure)
  // =========================================================================

  // STEP 6: DEMAND FORECASTING,

    {
    stepNumber: 4,
    id: "business-entities",
    title: "Business Entities, Legal Profiles & Seller Master",
    shortTitle: "4. Business Entities",
    route: "/po-invoice",
    navGroup: "Administration",
    phase: "Phase 1: Enterprise Foundation & Master Setup",
    stream: "Governance",
    category: "Master Data & Setup",
    iconName: "Building2",
    actorRole: "Corporate Controller / Legal Officer (org:read, org:write)",
    summary: "Configures the legal company profile, statutory PAN/GSTIN tax registrations, bank accounts, and authorized signatories for purchase orders and tax invoices.",
    businessPurpose:
      "A company cannot legally transact, issue purchase orders, or generate GST tax invoices without verified corporate entities and statutory tax IDs.",
    keyObjectives: [
      "Establish primary operating company entities with registered legal addresses and PAN numbers.",
      "Register state-specific GSTIN certificates for multi-state tax compliance (CGST/SGST vs IGST).",
      "Attach corporate bank disbursement accounts with IFSC codes and authorized digital signature seals.",
    ],
    workflows: [
      {
        id: "be-create-entity",
        actionNumber: 1,
        title: "Create Legal Entity & PAN Registration",
        shortTitle: "Create Entity",
        actor: "Corporate Legal Lead",
        permissionRequired: "org:write",
        triggerEvent: "Corporate incorporation or subsidiary onboarding",
        stepByStepInstructions: [
          "Navigate to 'PO & Invoice Master' (/po-invoice) via the Finance menu.",
          "Click the '+ New Business Entity' button in the top action bar.",
          "Enter Entity Legal Name (e.g. 'Axon Industries Private Limited') and Company Type (Private Limited).",
          "Provide Corporate Permanent Account Number (PAN) in 10-character alphanumeric format.",
          "Click 'Save Entity Record' to persist in database.",
        ],
        systemValidations: [
          "Enforces valid Indian PAN regex pattern: [A-Z]{5}[0-9]{4}[A-Z]{1}.",
          "Hard uniqueness block prevents duplicate corporate entity registration.",
        ],
        tablesAndLedgersMutated: ["business_entities table (insert row with active=true)"],
        outputDocument: "Registered Business Entity Master (ENT-001)",
        simulation: {
          scenarioDescription: "Registering new enterprise entity 'Axon Industries Pvt Ltd' with statutory PAN.",
          initialState: "Unregistered (No corporate identity configured)",
          buttonLabel: "Simulate Entity Registration",
          successState: "Entity ENT-001 Registered & Active",
          executionLog: [
            "Validating PAN checksum: AAAAA9999A ✓",
            "Checking corporate registry uniqueness ✓",
            "Creating business entity row 'Axon Industries Pvt Ltd' in Postgres ✓",
            "Entity status marked 'Active' for PO and Invoice generation ✓",
          ],
          databaseEffect: "business_entities record ENT-001 committed with SHA-256 validation stamp.",
        },
      },
      {
        id: "be-gstin-bank",
        actionNumber: 2,
        title: "Attach GSTIN Tax ID & Corporate Bank Accounts",
        shortTitle: "Add GSTIN & Bank",
        actor: "Finance Manager",
        permissionRequired: "org:write",
        triggerEvent: "Tax registration setup for regional manufacturing hub",
        stepByStepInstructions: [
          "Open the registered entity detail drawer.",
          "Click '+ Add GSTIN Registration'.",
          "Enter 15-digit GSTIN (e.g. '27AAAAA9999A1Z5' for Maharashtra state).",
          "Click '+ Add Bank Account', enter Bank Name, Account Number, and IFSC code.",
          "Set as 'Default Seller Account' for automated customer wire remittance instructions.",
        ],
        systemValidations: [
          "GSTIN first 2 digits must match valid State Code dictionary (e.g. 27 = Maharashtra, 29 = Karnataka).",
          "Bank IFSC code verified against RBI master dictionary format [A-Z]{4}0[A-Z0-9]{6}.",
        ],
        tablesAndLedgersMutated: [
          "business_entity_gstins table",
          "business_entity_bank_details table",
        ],
        outputDocument: "Statutory Tax & Remittance Profile",
        simulation: {
          scenarioDescription: "Adding GSTIN 27AAAAA9999A1Z5 and HDFC Bank disbursement account.",
          initialState: "Pending Tax IDs (Inward POs cannot compute GST)",
          buttonLabel: "Simulate Attach GSTIN & Bank",
          successState: "GSTIN & Remittance Account Active",
          executionLog: [
            "Validating State Code 27 against GST master ✓",
            "Validating HDFC IFSC code HDFC0000123 ✓",
            "Binding GSTIN to ENT-001 corporate entity ✓",
            "Invoicing engine unlocked for tax computation ✓",
          ],
          databaseEffect: "GSTIN linked to ENT-001; bank account encrypted in database.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Corporate Legal Registry",
        route: "/po-invoice",
        document: "Certificate of Incorporation",
        dataPassed: "Company Name, Registered Address, PAN, GSTIN documents.",
        relationship: "Corporate foundation setup",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Facilities & Factories",
        route: "/factory-warehouse",
        document: "Owning Entity Reference",
        dataPassed: "Entity ID for operating manufacturing and distribution sites.",
        relationship: "Facilities are legally owned by Business Entities",
      },
      {
        moduleName: "Purchase Orders & Procurement",
        route: "/procurement",
        document: "Buyer Legal Identity",
        dataPassed: "Entity GSTIN, Billing Address, and Legal Signatory for PO PDF header.",
        relationship: "Identifies buyer on purchase contracts",
      },
    ],
    businessControls: [
      "Cannot issue purchase orders or sales tax invoices without at least one active Entity with valid GSTIN.",
      "GSTIN and PAN changes are locked to users with 'org:write' permission and audited.",
    ],
  },

  // STEP 2: FACILITIES & FACTORIES,

    {
    stepNumber: 5,
    id: "parties-avl",
    title: "Commercial Partner Directory & Approved Vendor List (AVL)",
    shortTitle: "5. Vendors & Customers",
    route: "/parties",
    navGroup: "Procurement",
    phase: "Phase 1: Enterprise Foundation & Master Setup",
    stream: "Procure-to-Pay",
    category: "Master Data & Setup",
    iconName: "Building",
    actorRole: "Vendor Manager / Credit Controller (party:read, party:write, party:block)",
    summary: "Registers suppliers (vendors), commercial customers, and logistics transporters with payment terms, credit limits, and AVL quality compliance status.",
    businessPurpose:
      "Enterprise purchasing and sales require verified commercial counterparties. AVL governance blocks unvetted vendors from being awarded purchase orders, and customer credit limits prevent bad debt.",
    keyObjectives: [
      "Register Vendors, Customers, and Transporters with GSTIN, PAN, and address books.",
      "Enforce Approved Vendor List (AVL) governance with ISO certifications and quality audit dates.",
      "Configure customer credit terms (Net 30/60) and credit limit caps (e.g. ₹5,00,000).",
    ],
    workflows: [
      {
        id: "pty-create-vendor",
        actionNumber: 1,
        title: "Onboard Vendor & Qualify on Approved Vendor List (AVL)",
        shortTitle: "Onboard Vendor",
        actor: "Vendor Governance Specialist",
        permissionRequired: "party:write",
        triggerEvent: "Supplier onboarding following procurement qualification",
        stepByStepInstructions: [
          "Navigate to 'Supplier Directory' (/parties).",
          "Click '+ New Party' in the top right toolbar.",
          "Select Party Type: 'Vendor'.",
          "Enter Party Legal Name ('Acme Components India Pvt Ltd') and Code ('VEND-ACME-01').",
          "Enter Supplier GSTIN, Contact Person, and Billing Address.",
          "Under Compliance, toggle 'Approved Vendor List (AVL) Active'.",
          "Set Vendor Quality Rating to 'Grade A' and save party.",
        ],
        systemValidations: [
          "Supplier GSTIN verified against statutory format.",
          "Only vendors with AVL status 'Active' can be selected on Purchase Orders.",
        ],
        tablesAndLedgersMutated: [
          "parties table (new vendor record)",
          "party_addresses table",
          "avl_compliance table",
        ],
        outputDocument: "Approved Vendor Master Record (VEND-ACME-01)",
        simulation: {
          scenarioDescription: "Onboarding supplier Acme Components with Grade-A AVL approval.",
          initialState: "Unqualified Supplier",
          buttonLabel: "Simulate Vendor AVL Approval",
          successState: "Vendor VEND-ACME-01 Approved on AVL",
          executionLog: [
            "Validating Vendor GSTIN 27AABCA1234F1Z5 ✓",
            "Creating vendor profile 'Acme Components' ✓",
            "Stamping AVL Qualification: Grade A (Valid for 12 months) ✓",
            "Procurement buyer pool updated with supplier ✓",
          ],
          databaseEffect: "parties row inserted with is_vendor=true, avl_status='approved'.",
        },
      },
      {
        id: "pty-create-customer",
        actionNumber: 2,
        title: "Register B2B Customer & Set Credit Limit",
        shortTitle: "Onboard Customer",
        actor: "Credit Controller",
        permissionRequired: "party:write",
        triggerEvent: "New enterprise customer contract signing",
        stepByStepInstructions: [
          "In the Party Directory, click '+ New Party'.",
          "Select Party Type: 'Customer'.",
          "Enter Name ('AutoCorp Mobility Solutions') and Code ('CUST-AUTOCORP-01').",
          "Enter Customer GSTIN and Shipping Address.",
          "Set Payment Terms to 'Net 30 Days'.",
          "Set Credit Limit to ₹5,00,000 and Overdue Grace Period to 15 Days.",
          "Click 'Save Customer'.",
        ],
        systemValidations: [
          "Credit limit cannot be negative.",
          "Overdue aging threshold configured for automated order release blocks.",
        ],
        tablesAndLedgersMutated: [
          "parties table (is_customer=true)",
          "party_credit_limits table",
        ],
        outputDocument: "Customer Account Profile (CUST-AUTOCORP-01)",
        simulation: {
          scenarioDescription: "Registering AutoCorp with ₹5,00,000 credit limit and Net 30 terms.",
          initialState: "New Customer Prospect",
          buttonLabel: "Simulate Customer Setup",
          successState: "Customer Active (₹5,00,000 Credit Limit)",
          executionLog: [
            "Validating GSTIN and billing address ✓",
            "Registering customer CUST-AUTOCORP-01 in Postgres ✓",
            "Configuring credit terms Net 30, Limit ₹5,00,000 ✓",
            "Enabling Order Intake for AutoCorp ✓",
          ],
          databaseEffect: "parties row committed; credit limits initialized.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Business Entities",
        route: "/po-invoice",
        document: "Operating Entity",
        dataPassed: "Owning company for commercial counterparty contracts.",
        relationship: "Commercial agreement boundary",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Procurement & Purchase Orders",
        route: "/procurement",
        document: "Approved Vendor",
        dataPassed: "Vendor ID VEND-ACME-01, AVL status, payment terms for PO creation.",
        relationship: "POs must specify approved vendors",
      },
      {
        moduleName: "Sales Orders",
        route: "/orders",
        document: "Customer Account",
        dataPassed: "Customer ID, credit limit, shipping address for SO creation.",
        relationship: "Sales orders must specify registered customers",
      },
    ],
    businessControls: [
      "System strictly blocks PO issuance to any vendor marked 'Blocked' or 'Delisted'.",
      "Customer orders are auto-frozen if overdue balance exceeds the approved credit limit.",
    ],
  },

  // STEP 5: PRODUCTS & BOM,

    {
    stepNumber: 6,
    id: "demand-forecasting",
    title: "Demand Forecasting, Tournament Modeling & Consensus S&OP",
    shortTitle: "6. Demand Forecasting",
    route: "/forecasting",
    navGroup: "Planning & SCM",
    phase: "Phase 2: Demand Planning & Procurement",
    stream: "Plan-to-Produce",
    category: "Planning & SCM",
    iconName: "LineChart",
    actorRole: "Demand Planner (forecasting:read, forecasting:write)",
    summary: "Applies statistical forecasting algorithms to trailing sales history, compares MAPE accuracy, applies manual commercial overrides, and locks consensus demand.",
    businessPurpose:
      "Prevents stockouts and excess holding costs by predicting upcoming customer demand months in advance before committing procurement funds.",
    keyObjectives: [
      "Run automated tournament models (Holt-Winters, Double Exponential Smoothing, Croston's intermittent model).",
      "Inspect Mean Absolute Percentage Error (MAPE) to objectively choose the lowest-error statistical model.",
      "Collaboratively enter manual market adjustments (promotions, seasonal surges) and lock consensus demand.",
    ],
    workflows: [
      {
        id: "fc-run-tournament",
        actionNumber: 1,
        title: "Execute Automated Tournament Forecasting Algorithm",
        shortTitle: "Run Forecast",
        actor: "Demand Planner",
        permissionRequired: "forecasting:write",
        triggerEvent: "Monthly S&OP cycle initiation",
        stepByStepInstructions: [
          "Navigate to 'Demand Forecasting' (/forecasting).",
          "Select SKU: 'SKU-MOT-500' and Forecast Horizon: 'Next 6 Months'.",
          "Click 'Run Tournament Models'.",
          "System runs Holt-Winters (MAPE 8.2%), Double Exponential (MAPE 12.4%), Moving Average (MAPE 19.1%).",
          "Inspect tournament winner (Holt-Winters crowned champion with lowest error).",
        ],
        systemValidations: [
          "Requires minimum 12 months of sales history for seasonality detection.",
          "Error rate MAPE > 25% flags a high-volatility warning badge.",
        ],
        tablesAndLedgersMutated: ["forecast_runs table", "forecast_baseline_series table"],
        outputDocument: "Statistical Baseline Forecast (FCT-2026-Q4)",
        simulation: {
          scenarioDescription: "Running tournament model on SKU-MOT-500 across 24 months of sales actuals.",
          initialState: "Uncalculated Demand Horizon",
          buttonLabel: "Simulate Tournament Forecast",
          successState: "Holt-Winters Winner (MAPE 8.2%)",
          executionLog: [
            "Ingesting 24-month order shipment history ✓",
            "Evaluating Holt-Winters additive model: MAPE 8.2% ✓",
            "Evaluating Double Exponential: MAPE 12.4% ✓",
            "Holt-Winters crowned champion: 500 units/month projected ✓",
          ],
          databaseEffect: "forecast_runs row inserted with tournament results.",
        },
      },
      {
        id: "fc-lock-consensus",
        actionNumber: 2,
        title: "Apply Commercial Overrides & Lock Consensus Demand",
        shortTitle: "Lock Consensus",
        actor: "SCM Director",
        permissionRequired: "forecasting:write",
        triggerEvent: "Consensus sign-off meeting between Sales and Operations",
        stepByStepInstructions: [
          "In the Forecast review grid, inspect monthly suggested demand (500 units/mo).",
          "Add commercial promotional bump (+50 units in October for festive surge).",
          "Click 'Lock Consensus Plan'.",
          "Click 'Push to MRP Gross Demand' to transfer numbers into the material calculation engine.",
        ],
        systemValidations: [
          "Past periods cannot be modified.",
          "Consensus lock requires SCM Director authorization.",
        ],
        tablesAndLedgersMutated: [
          "consensus_demand_plans table",
          "mrp_gross_demands table",
        ],
        outputDocument: "Approved Consensus Demand Schedule",
        simulation: {
          scenarioDescription: "Adjusting to 550 units and pushing to MRP Planning queue.",
          initialState: "Draft Statistical Projection",
          buttonLabel: "Simulate Push to MRP",
          successState: "Consensus Locked & Pushed to MRP",
          executionLog: [
            "Applying promo override: 500 -> 550 units ✓",
            "Signing off consensus demand PLN-2026-Q4 ✓",
            "Pushing gross requirement to MRP demand queue ✓",
          ],
          databaseEffect: "mrp_gross_demands rows created for 6 months.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Product Catalog",
        route: "/products",
        document: "Active SKUs & Lead Times",
        dataPassed: "Finished good SKU codes and historical product categories.",
        relationship: "Specifies what items can be forecasted",
      },
      {
        moduleName: "Sales Orders & Billing",
        route: "/orders",
        document: "Historical Shipments",
        dataPassed: "24-month sales shipment quantities.",
        relationship: "Time-series baseline data",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Material Requirements Planning (MRP)",
        route: "/mrp",
        document: "Gross Demand Schedule",
        dataPassed: "Monthly projected demand units by SKU.",
        relationship: "Feeds gross requirements into MRP explosion",
      },
    ],
    businessControls: [
      "Locked forecast periods cannot be modified without audit revision log.",
      "High-variance overrides (>30% of statistical baseline) require explanatory comment.",
    ],
  },

  // STEP 7: MRP & DRP,

    {
    stepNumber: 7,
    id: "mrp-drp-planning",
    title: "Material Requirements Planning (MRP) & Multi-Echelon DRP",
    shortTitle: "7. MRP Planning",
    route: "/mrp",
    navGroup: "Planning & SCM",
    phase: "Phase 2: Demand Planning & Procurement",
    stream: "Plan-to-Produce",
    category: "Planning & SCM",
    iconName: "SlidersHorizontal",
    actorRole: "Supply Chain Planner (mrp:read, mrp:calculate, mrp:release)",
    summary: "Explodes gross customer and forecast demand into child component requirements, nets out on-hand stock and safety levels, and converts deficits into planned purchase and work orders.",
    businessPurpose:
      "Calculates exactly what raw materials to buy and what assemblies to manufacture so factory lines never halt for missing parts and warehouses do not over-stock.",
    keyObjectives: [
      "Explode parent product demand into raw material requirements using locked BOM ratios.",
      "Net out on-hand warehouse inventory, incoming purchase orders, and committed safety stocks.",
      "Convert deficit net requirements into actionable Purchase Requisitions (PR) and Production Work Orders (WO).",
    ],
    workflows: [
      {
        id: "mrp-calculate",
        actionNumber: 1,
        title: "Run Gross-to-Net Component Explosion Calculation",
        shortTitle: "Run MRP Explosion",
        actor: "MRP Planner",
        permissionRequired: "mrp:calculate",
        triggerEvent: "Weekly planning cycle or large sales order booking",
        stepByStepInstructions: [
          "Navigate to 'MRP Planning' (/mrp).",
          "Select Planning Horizon: 'Next 60 Days' and Target Plant: 'FACT-PUNE-01'.",
          "Click 'Calculate Gross-to-Net MRP'.",
          "Calculation executes: Gross Demand (550 Motors) × BOM Ratios: 550 Rotors, 550 Stators, 5,500m Copper Wire.",
          "Netting: System detects 500m Copper Wire on-hand; flags Net Deficit of 5,000m Copper Wire.",
        ],
        systemValidations: [
          "Enforces supplier replenishment lead-time offset (e.g. 14 days lead time = order must be placed today).",
          "Calculates scrap allowance multipliers defined in BOM.",
        ],
        tablesAndLedgersMutated: [
          "mrp_runs table",
          "mrp_planned_orders table (staging rows)",
        ],
        outputDocument: "MRP Explosion Run (MRP-RUN-802)",
        simulation: {
          scenarioDescription: "Calculating gross-to-net needs for 550 Motors; netting out 500m on-hand wire.",
          initialState: "Uncalculated Inventory Requirements",
          buttonLabel: "Simulate MRP Calculation",
          successState: "Net Deficit: 5,000m Copper Wire Needed",
          executionLog: [
            "Exploding BOM-MOT-V1 across 550 parent units ✓",
            "Gross raw copper wire needed: 5,500m (incl. 3% scrap) ✓",
            "Netting on-hand stock in WH-PUNE-01: 500m available ✓",
            "Net planned deficit: 5,000m Copper Wire needed by Day 14 ✓",
          ],
          databaseEffect: "mrp_planned_orders staged with planned replenishment actions.",
        },
      },
      {
        id: "mrp-release-orders",
        actionNumber: 2,
        title: "Release Planned Orders to Procurement & Manufacturing",
        shortTitle: "Release Orders",
        actor: "SCM Planner",
        permissionRequired: "mrp:release",
        triggerEvent: "Planner reviews and approves suggested procurement & assembly lines",
        stepByStepInstructions: [
          "In the MRP suggestions table, select the 5,000m Copper Wire planned line.",
          "Select the 550 unit Motor assembly planned line.",
          "Click 'Release Selected Planned Orders'.",
          "System automatically converts the raw material deficit into Purchase Requisition PR-3042.",
          "System automatically converts the assembly demand into Planned Work Order WO-1050.",
        ],
        systemValidations: [
          "Checks user authorization `mrp:release`.",
          "Prevents duplicate releases of already-actioned MRP suggestion lines.",
        ],
        tablesAndLedgersMutated: [
          "purchase_requisitions table (new PR-3042)",
          "production_runs table (new WO-1050)",
          "mrp_planned_orders (status -> 'released')",
        ],
        outputDocument: "Requisition PR-3042 & Work Order WO-1050",
        simulation: {
          scenarioDescription: "Releasing PR-3042 for 5,000m wire and WO-1050 for 550 motors.",
          initialState: "Staged MRP Suggestions",
          buttonLabel: "Simulate Release to ERP Modules",
          successState: "PR-3042 & WO-1050 Created",
          executionLog: [
            "Creating Purchase Requisition PR-3042 for 5,000m copper wire ✓",
            "Routing PR-3042 to Procurement buyer pool ✓",
            "Creating planned Work Order WO-1050 for assembly floor ✓",
            "MRP lines marked as 'Released' ✓",
          ],
          databaseEffect: "purchase_requisitions and production_runs rows committed in Postgres.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Demand Forecasting & Sales",
        route: "/forecasting",
        document: "Consensus Forecast & Confirmed SOs",
        dataPassed: "Gross independent demand schedule.",
        relationship: "Primary demand driver",
      },
      {
        moduleName: "Warehouse Stock Ledger",
        route: "/inventory",
        document: "Physical On-Hand & Safety Stock",
        dataPassed: "Real-time stock balance across all bins and warehouses.",
        relationship: "Current inventory position",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Procurement & Sourcing",
        route: "/procurement",
        document: "Purchase Requisition (PR)",
        dataPassed: "Raw material SKU codes, deficit quantities, and required delivery dates.",
        relationship: "Triggers supplier quoting and PO creation",
      },
      {
        moduleName: "Manufacturing & Production",
        route: "/production",
        document: "Planned Work Orders (WO)",
        dataPassed: "Assembly quantities, BOM recipe, and scheduled start dates.",
        relationship: "Schedules shop-floor manufacturing runs",
      },
    ],
    businessControls: [
      "Lead time offset validation ensures orders are placed before supplier minimum fulfillment days.",
      "Safety stock thresholds cannot be depleted without executive override.",
    ],
  },

  // STEP 8: PROCUREMENT & PURCHASE ORDERS,

    {
    stepNumber: 8,
    id: "procurement-sourcing-po",
    title: "Procurement, Multi-Vendor RFQ Bidding & Purchase Orders",
    shortTitle: "8. Procurement & PO",
    route: "/procurement",
    navGroup: "Procurement",
    phase: "Phase 2: Demand Planning & Procurement",
    stream: "Procure-to-Pay",
    category: "Procurement & Sourcing",
    iconName: "ShoppingCart",
    actorRole: "Purchasing Officer / Plant Buyer (po:read, po:write, po:approve)",
    summary: "Manages purchase requisitions, multi-vendor RFQ bidding, landed price comparison, 2-tier approval thresholds, and legally binding supplier purchase orders.",
    businessPurpose:
      "Secures raw materials from qualified AVL vendors at competitive pricing under strict authorization controls, preventing maverick buying and budget overruns.",
    keyObjectives: [
      "Approve purchase requisitions (PR) and convert them into multi-vendor Requests for Quotation (RFQs).",
      "Evaluate vendor quotation bids including freight, taxes, and payment terms to award the best price.",
      "Enforce 2-tier approval limits (<₹50k Buyer, >₹50k Plant Head) and dispatch authorized PO PDFs via SMTP.",
    ],
    workflows: [
      {
        id: "po-raise-requisition",
        actionNumber: 1,
        title: "Raise New Purchase Requisition (PR)",
        shortTitle: "Raise New Requisition",
        actor: "Plant Engineer / Department Requester (pr:create)",
        permissionRequired: "pr:create",
        triggerEvent: "Shop floor or maintenance team needs raw materials or consumable parts",
        stepByStepInstructions: [
          "Navigate to 'Procurement' (/procurement) and select the 'Requisitions' tab.",
          "Click the '+ New Requisition' button in the top action toolbar.",
          "Select Requesting Department (e.g. 'Plant 1 - Motor Assembly') and Priority ('Standard' or 'Urgent').",
          "Specify the 'Required By' target delivery date (allowing adequate supplier lead time).",
          "Click '+ Add Line Item' and search for SKU-WIRE-01 (Copper Enamelled Winding Wire).",
          "Enter Quantity: 5,000 Meters, unit estimate ₹25.00/m, and assign GL Cost Center 402.",
          "Add business justification note ('Scheduled Q4 Stator Winding Batch #44') and click 'Submit Requisition'.",
        ],
        systemValidations: [
          "Quantity must be strictly greater than 0; SKU must be active in engineering catalog.",
          "Target delivery date must respect supplier lead time (minimum 7 days ahead) unless marked 'Emergency Breakdown'.",
          "Cost center budget balance verified in real time; alerts if department exceeds quarterly allocation.",
        ],
        tablesAndLedgersMutated: [
          "purchase_requisitions (created with status='submitted', req_number='PR-3042')",
          "purchase_requisition_lines table (item_id, qty=5000, estimated_unit_cost=25.00)",
        ],
        outputDocument: "Submitted Purchase Requisition (PR-3042: ₹1,25,000)",
        simulation: {
          scenarioDescription: "Plant engineer creates Requisition PR-3042 for 5,000m copper wire with ₹1,25,000 budget.",
          initialState: "New Requisition Draft Form",
          buttonLabel: "Simulate Submit New Requisition",
          successState: "PR-3042 Submitted & Routed to Sourcing",
          executionLog: [
            "Validating Department 402 quarterly OpEx budget allowance ✓",
            "Checking SKU-WIRE-01 standard lead time (14 days) ✓",
            "Creating purchase_requisitions record PR-3042 (Status: Submitted) ✓",
            "Routing PR-3042 to Buyer approval inbox with audit timestamp ✓",
          ],
          databaseEffect: "purchase_requisitions row PR-3042 created with 1 line item; status='submitted'.",
        },
      },
      {
        id: "po-rfq-bidding",
        actionNumber: 2,
        title: "Review PR & Float Multi-Vendor RFQ Bidding",
        shortTitle: "Float RFQ & Compare Quotes",
        actor: "Lead Buyer (rfq:create, rfq:compare)",
        permissionRequired: "rfq:create",
        triggerEvent: "Requisition PR-3042 approved by department manager and ready for market sourcing",
        stepByStepInstructions: [
          "Open Requisition PR-3042 in the Buyer Workbench.",
          "Click 'Convert to Sourcing RFQ' to initiate competitive bidding.",
          "Select 3 qualified suppliers from Approved Vendor List (AVL): Acme Components, Beta Metal, Zenith Cables.",
          "Set submission deadline (5 business days) and commercial Incoterms ('DAP - Delivered at Place').",
          "Click 'Dispatch RFQ Invitations' (triggers automated vendor portal notifications and email).",
          "As vendor quotes arrive, open 'Bid Comparison Matrix' to evaluate landed rate, freight, and delivery SLA.",
        ],
        systemValidations: [
          "Multi-vendor policy: purchases > ₹1,00,000 require quotes from at least 2 independent AVL vendors.",
          "Vendor eligibility check: vendor must possess valid GSTIN, active bank profile, and ISO-9001 rating >= B.",
        ],
        tablesAndLedgersMutated: [
          "sourcing_rfqs table (rfq_number='RFQ-901', status='published')",
          "sourcing_rfq_vendors table (links 3 invited suppliers)",
          "sourcing_quotations table (stores incoming item price bids)",
        ],
        outputDocument: "RFQ-901 Published & Bid Comparison Matrix Ready",
        simulation: {
          scenarioDescription: "Buyer floats RFQ-901 to 3 AVL vendors and receives landed quotation bids.",
          initialState: "PR-3042 Approved in Buyer Queue",
          buttonLabel: "Simulate Float RFQ & Solicit Bids",
          successState: "3 Vendor Bids Ingested in Matrix",
          executionLog: [
            "Validating AVL compliance for Acme Components, Beta Metal, Zenith Cables ✓",
            "RFQ-901 published with DAP delivery terms ✓",
            "Incoming quote: Acme Components at ₹25.00/m (Delivery: 10 days) ✓",
            "Incoming quote: Beta Metal at ₹27.00/m (Delivery: 14 days) ✓",
            "Incoming quote: Zenith Cables at ₹26.50/m (Delivery: 12 days) ✓",
            "Landed comparison matrix computed: Acme Components ranked #1 (L1 lowest price) ✓",
          ],
          databaseEffect: "sourcing_rfqs and sourcing_quotations populated; L1 vendor flagged.",
        },
      },
      {
        id: "po-create-new-order",
        actionNumber: 3,
        title: "Create Direct New Purchase Order (PO)",
        shortTitle: "Create New Purchase Order",
        actor: "Purchasing Officer / Buyer (po:create, po:write)",
        permissionRequired: "po:write",
        triggerEvent: "Buyer awards RFQ-901 to winning supplier or initiates standard repeat procurement",
        stepByStepInstructions: [
          "In '/procurement', click the primary '+ Create Purchase Order' button.",
          "Select Vendor: 'Acme Components Ltd' (system auto-populates GSTIN, payment terms Net 30, and billing address).",
          "Select Receiving Facility & Delivery Address: 'Factory Plant 1 - Main Receiving Dock'.",
          "Add Line Items: SKU-WIRE-01, Quantity 5,000 Meters, Negotiated Unit Rate ₹25.00/m.",
          "Confirm HSN Code 8544 and statutory GST (CGST 9% + SGST 9% = ₹22,500; Total PO Value = ₹1,47,500).",
          "Set Delivery Schedule (Expected Date: Day 14) and packaging guidelines (moisture-barrier spools).",
          "Click 'Save & Submit for Approval' to assign official number PO-9002.",
        ],
        systemValidations: [
          "Supplier must have active contract terms and zero open legal/quality holds.",
          "Unit rate variance check: alerts if negotiated price deviates >10% from historical 90-day moving average.",
          "Total PO value determines required signoff tier (<₹50k Buyer auto-approval, >₹50k Tier-2 Plant Head signoff).",
        ],
        tablesAndLedgersMutated: [
          "purchase_orders table (created with status='pending_approval', po_number='PO-9002')",
          "purchase_order_lines table (item_id, qty=5000, rate=25.00, tax_amount=22500)",
          "budget_encumbrances (locks ₹1,47,500 committed spend against procurement budget)",
        ],
        outputDocument: "Draft Purchase Order (PO-9002: ₹1,47,500)",
        simulation: {
          scenarioDescription: "Creating formal PO-9002 for Acme Components with 5,000m copper wire @ ₹25/m.",
          initialState: "L1 Vendor Selected from RFQ Matrix",
          buttonLabel: "Simulate Create Purchase Order",
          successState: "PO-9002 Generated (₹1,47,500)",
          executionLog: [
            "Validating Acme Components vendor status (Active AVL, GSTIN 27AAACA1234A1Z5) ✓",
            "Calculating statutory GST: 18% (CGST 9% ₹11,250 + SGST 9% ₹11,250) ✓",
            "Writing purchase_orders and purchase_order_lines records in Postgres ✓",
            "Encumbering ₹1,47,500 in General Ledger procurement commitment balance ✓",
            "PO-9002 status marked 'Pending Tier-2 Approval' (Exceeds ₹50,000 threshold) ✓",
          ],
          databaseEffect: "purchase_orders record PO-9002 created in draft status with budget encumbrance.",
        },
      },
      {
        id: "po-tier-approval",
        actionNumber: 4,
        title: "Tier-2 Executive Approval & Vendor Dispatch",
        shortTitle: "Approve & Dispatch PO",
        actor: "Plant Head / VP Operations (po:approve)",
        permissionRequired: "po:approve",
        triggerEvent: "PO-9002 value (₹1,47,500) exceeds ₹50,000 single-buyer approval threshold",
        stepByStepInstructions: [
          "Plant Head logs in and opens the 'Approvals' tab in Procurement workbench.",
          "Selects PO-9002 to review line items, requisition justification, and vendor scorecard.",
          "Inspects the attached budget audit report: confirms ₹1,47,500 is within Q4 CapEx/OpEx allocation.",
          "Clicks 'Authorize Purchase Order' to apply cryptographic digital signature.",
          "System locks PO lines from edits, generates official signed PDF, and queues SMTP email dispatch to vendor.",
        ],
        systemValidations: [
          "Separation of duties: creator of the PO cannot approve their own order.",
          "Dual authorization enforced: orders exceeding ₹50,000 require user role with `po:approve` privilege.",
          "Cannot issue PO to vendor with expired quality audit or lapsed statutory tax certificate.",
        ],
        tablesAndLedgersMutated: [
          "purchase_orders (status -> 'issued', approved_by=user_id, approved_at=now())",
          "notifications table (queued email dispatch to orders@acme-components.com)",
          "audit_logs (cryptographic signature hash recorded)",
        ],
        outputDocument: "Authorized Purchase Order PDF Dispatched to Vendor",
        simulation: {
          scenarioDescription: "Plant Head authorises PO-9002; PDF generated and sent to supplier.",
          initialState: "PO-9002 Pending Tier-2 Approval",
          buttonLabel: "Simulate Tier-2 Approval & Dispatch",
          successState: "PO-9002 Issued & Dispatched via SMTP",
          executionLog: [
            "Verifying Plant Head approval authority (`po:approve`) ✓",
            "Applying cryptographic digital signature hash to PO-9002 ✓",
            "Rendering authorized PO PDF with corporate seal ✓",
            "Status updated to 'Issued'; committed procurement budget recorded ✓",
            "PDF dispatched to supplier orders@acme-components.com with delivery SLA token ✓",
          ],
          databaseEffect: "purchase_orders status updated to 'issued'; warehouse inward queue alerted.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "MRP Planning",
        route: "/mrp",
        document: "Purchase Requisition (PR)",
        dataPassed: "Deficit raw materials, required dates, and quantities.",
        relationship: "Demand origin",
      },
      {
        moduleName: "Parties Directory",
        route: "/parties",
        document: "Approved Vendor Master",
        dataPassed: "Vendor GSTIN, payment terms (Net 30), bank accounts, and AVL status.",
        relationship: "Vendor qualification",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Inbound Logistics TMS",
        route: "/logistics",
        document: "Issued PO-9002",
        dataPassed: "Consignee address, expected dispatch date, and line items.",
        relationship: "Enables vendor dispatch ASN and lorry tracking",
      },
      {
        moduleName: "Inbound Receiving & GRN",
        route: "/warehouse",
        document: "PO Lines Pending Receipt",
        dataPassed: "Expected SKUs, allowed receipt tolerances, and unit prices.",
        relationship: "Warehouse gate receipt benchmark",
      },
    ],
    businessControls: [
      "Purchase orders cannot be approved for vendors whose compliance status is 'Blocked' or 'Delisted'.",
      "Tiered monetary approval strictly enforced by user permission matrix.",
    ],
  },

  // =========================================================================
  // PHASE 3: INBOUND LOGISTICS, DOCK RECEIVING & WAREHOUSING
  // =========================================================================

  // STEP 9: INBOUND LOGISTICS & GATE ENTRY,

    {
    stepNumber: 9,
    id: "inbound-logistics-gate",
    title: "Inbound Logistics TMS, Vendor ASN & Factory Gate Check-In",
    shortTitle: "9. Inbound Logistics",
    route: "/logistics",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 3: Inbound Logistics & Receiving",
    stream: "Warehouse & WMS",
    category: "Warehouse & Logistics",
    iconName: "Truck",
    actorRole: "Logistics Coordinator / Gate Security (logistics:read, logistics:write)",
    summary: "Tracks shipment in-transit, registers vendor Advance Shipping Notices (ASN), verifies statutory e-Way bills, and records lorry gate entry at the factory dock.",
    businessPurpose:
      "Gives warehouse managers advance visibility into inbound deliveries so they can pre-allocate dock bays and labor, and prevents illegal unmanifested transport from entering the plant.",
    keyObjectives: [
      "Receive vendor Advance Shipping Notices (ASN) with carrier tracking and container counts.",
      "Verify statutory compliance including vehicle registration and e-Way bills before lorry arrival.",
      "Record physical gate entry at the factory dock and issue Gate Entry Pass (GEP) to direct unloading.",
    ],
    workflows: [
      {
        id: "log-inbound-asn",
        actionNumber: 1,
        title: "Log Vendor Advance Shipping Notice (ASN)",
        shortTitle: "Log Vendor ASN",
        actor: "Logistics Specialist",
        permissionRequired: "logistics:write",
        triggerEvent: "Vendor dispatches lorry from their factory",
        stepByStepInstructions: [
          "Navigate to 'Logistics' (/logistics) and click 'Inbound ASNs' tab.",
          "Click '+ Register Inbound ASN'.",
          "Select Purchase Order: 'PO-9002'.",
          "Enter Transporter: 'TCI Freight', Vehicle #: 'MH-12-AB-1234', Lorry Receipt (LR) #: 'LR-88219'.",
          "Enter Shipped Quantity: 5,000m Copper Wire in 25 Spools.",
          "Save ASN.",
        ],
        systemValidations: [
          "Shipped quantity cannot exceed open PO quantity balance.",
          "Transporter must be registered in the Party Master.",
        ],
        tablesAndLedgersMutated: ["inbound_asns table", "inbound_asn_items table"],
        outputDocument: "Advance Shipping Notice (ASN-410)",
        simulation: {
          scenarioDescription: "Vendor Acme dispatches 5,000m wire via TCI Freight lorry MH-12-AB-1234.",
          initialState: "PO-9002 Awaiting Shipment",
          buttonLabel: "Simulate Log Vendor ASN",
          successState: "ASN-410 Logged (In-Transit)",
          executionLog: [
            "Validating vehicle number MH-12-AB-1234 format ✓",
            "Matching line items against open PO-9002 balance ✓",
            "Logging ASN-410 with Lorry Receipt LR-88219 ✓",
            "Dock crew alerted of expected 2 PM delivery window ✓",
          ],
          databaseEffect: "inbound_asns row committed; shipment status set to 'in_transit'.",
        },
      },
      {
        id: "log-gate-checkin",
        actionNumber: 2,
        title: "Record Physical Gate Entry & Issue Dock Gate Pass",
        shortTitle: "Gate Check-In",
        actor: "Gate Security Guard",
        permissionRequired: "logistics:write",
        triggerEvent: "Transport lorry physically pulls up at factory security gate",
        stepByStepInstructions: [
          "Security guard opens 'Gate Check-In' screen on tablet or PC.",
          "Scan or search vehicle number 'MH-12-AB-1234'.",
          "Match physical driver challan against ASN-410.",
          "Verify statutory e-Way bill # against government GST portal.",
          "Click 'Authorize Gate Entry' and print Gate Entry Pass (GEP-108).",
          "Direct driver to Dock Bay 3 for unloading.",
        ],
        systemValidations: [
          "Lorry blocked if vehicle registration does not match ASN.",
          "Consignments >₹50,000 must carry valid statutory e-Way bill.",
        ],
        tablesAndLedgersMutated: [
          "gate_entry_passes table (new GEP record)",
          "inbound_asns (status -> 'docked')",
        ],
        outputDocument: "Gate Entry Pass (GEP-108: Dock Bay 3)",
        simulation: {
          scenarioDescription: "Lorry MH-12-AB-1234 arrives at gate; security validates documents and issues GEP-108.",
          initialState: "In-Transit (At Factory Gate)",
          buttonLabel: "Simulate Gate Check-In",
          successState: "Docked at Bay 3 (Gate Pass GEP-108)",
          executionLog: [
            "Validating driver delivery challan against ASN-410 ✓",
            "Verifying active 12-digit e-Way bill on GST portal ✓",
            "Issuing Gate Entry Pass GEP-108 for Dock Bay 3 ✓",
            "Warehouse receiving team notified to begin unloading ✓",
          ],
          databaseEffect: "gate_entry_passes row created; dock status updated to 'docked'.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Procurement",
        route: "/procurement",
        document: "Issued PO-9002",
        dataPassed: "Vendor details, ordered quantities, delivery deadlines.",
        relationship: "Shipment authorization",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Warehouse Inbound Receiving",
        route: "/warehouse",
        document: "Gate Entry Pass & ASN",
        dataPassed: "Physical lorry arrival, container counts, supplier delivery challan.",
        relationship: "Directs dock crew to generate GRN",
      },
    ],
    businessControls: [
      "Vehicle cannot check-in without matching open PO reference.",
      "Consignments exceeding ₹50,000 must carry active statutory e-Way bill.",
    ],
  },

  // STEP 10: WAREHOUSE RECEIVING & GRN,

    {
    stepNumber: 10,
    id: "warehouse-grn-labels",
    title: "Dock Inward Receiving, GRN & 2D QR Label Printing",
    shortTitle: "10. Dock GRN",
    route: "/warehouse",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 3: Inbound Logistics & Receiving",
    stream: "Warehouse & WMS",
    category: "Warehouse & Logistics",
    iconName: "Warehouse",
    actorRole: "Warehouse Receiver (warehouse:read, warehouse:receive)",
    summary: "Verifies delivered packages against PO line items, creates Goods Receipt Notes (GRN), and prints serialized barcode labels.",
    businessPurpose:
      "Formally acknowledges the physical transfer of goods from the supplier into the enterprise's legal custody.",
    keyObjectives: [
      "Tally physical cartons against vendor invoice and PO line quantities.",
      "Generate official Goods Receipt Note (GRN) with inward batch tracking.",
      "Print serialized 2D Datamatrix QR stickers for every pallet and container.",
    ],
    workflows: [
      {
        id: "wh-tally-dock",
        actionNumber: 1,
        title: "Inspect Physical Consignment & Tally Packages",
        shortTitle: "Tally Consignment",
        actor: "Dock Inward Operator",
        permissionRequired: "warehouse:receive",
        triggerEvent: "Lorry docked at Bay 3 with Gate Pass GEP-108",
        stepByStepInstructions: [
          "Navigate to 'Inbound Receiving' (/warehouse).",
          "Search Gate Pass 'GEP-108' or scan PO barcode 'PO-9002'.",
          "Unload 25 spools of copper wire onto inbound staging pallets.",
          "Inspect outer packaging for freight damage or seal tampering.",
          "Confirm package tally: 25 of 25 spools received in sound condition.",
        ],
        systemValidations: [
          "Discrepant package counts must be flagged with photos.",
        ],
        tablesAndLedgersMutated: ["dock_tally_sheets table"],
        outputDocument: "Dock Inward Tally Sheet",
        simulation: {
          scenarioDescription: "Unloading 25 spools of wire from lorry; verifying physical condition.",
          initialState: "Lorry Docked at Bay 3",
          buttonLabel: "Simulate Tally Verification",
          successState: "25/25 Packages Verified Intact",
          executionLog: [
            "Matching 25 spools against supplier delivery challan ✓",
            "Checking outer packaging integrity: Zero damage ✓",
            "Palletizing 25 spools onto Inbound Staging Pallets ✓",
          ],
          databaseEffect: "dock_tally_sheets row committed.",
        },
      },
      {
        id: "wh-create-grn",
        actionNumber: 2,
        title: "Generate Goods Receipt Note (GRN) in Quarantine Status",
        shortTitle: "Generate GRN",
        actor: "Inward Supervisor",
        permissionRequired: "warehouse:receive",
        triggerEvent: "Package tally verified against PO-9002 lines",
        stepByStepInstructions: [
          "Click 'Generate Goods Receipt Note (GRN)'.",
          "Select PO-9002 Line 1: SKU-COPPER-WIRE.",
          "Enter Received Qty: 5,000 Meters.",
          "Provide Supplier Invoice Number (e.g. 'INV-ACME-4012').",
          "Click 'Post GRN'.",
          "System creates GRN-3012 in 'Quarantine' status and routes lot to Quality Inspection.",
        ],
        systemValidations: [
          "Over-delivery cap: Quantity cannot exceed PO quantity by >5% tolerance.",
          "Material is placed in Quarantine status; cannot be issued to production until QC approved.",
        ],
        tablesAndLedgersMutated: [
          "grns table (new GRN-3012)",
          "grn_items table",
          "inventory_items table (quarantine bucket)",
        ],
        outputDocument: "Goods Receipt Note (GRN-3012: In Quarantine)",
        simulation: {
          scenarioDescription: "Creating GRN-3012 for 5,000m copper wire; lot placed in quarantine.",
          initialState: "Tally Verified (Unreceived in ERP)",
          buttonLabel: "Simulate Post GRN-3012",
          successState: "GRN-3012 Created (In Quarantine)",
          executionLog: [
            "Validating receipt quantity: 5,000m matches PO-9002 ✓",
            "Posting Goods Receipt Note GRN-3012 in Postgres ✓",
            "Inventory placed in 'Quarantine' hold location ✓",
            "Stock ledger debits 'Inbound Quarantine' ledger ✓",
            "Triggering inspection task in Quality Control station ✓",
          ],
          databaseEffect: "grns and grn_items rows inserted; inventory_items row added in quarantine.",
        },
      },
      {
        id: "wh-print-qr",
        actionNumber: 3,
        title: "Print Serialized 2D Datamatrix QR Labels",
        shortTitle: "Print QR Labels",
        actor: "Receiving Clerk",
        permissionRequired: "warehouse:receive",
        triggerEvent: "GRN-3012 generated",
        stepByStepInstructions: [
          "In the GRN view, click 'Print QR Stickers' button.",
          "Select Sticker Format: '4x2 inch Industrial Pallet Label'.",
          "System compiles 2D Datamatrix QR containing: SKU code, GRN number, Batch ID, and Received Date.",
          "Thermal label printer generates 25 serialized container stickers.",
          "Affix stickers to each spool pallet.",
        ],
        systemValidations: [
          "QR data encoded with cryptographic tamper-detection checksum.",
        ],
        tablesAndLedgersMutated: ["label_print_logs table"],
        outputDocument: "25 Serialized 2D QR Labels Affixed",
        simulation: {
          scenarioDescription: "Generating 25 serialized QR stickers for GRN-3012.",
          initialState: "Unlabeled Pallets",
          buttonLabel: "Simulate Print QR Stickers",
          successState: "25 QR Labels Generated & Printed",
          executionLog: [
            "Compiling 2D Datamatrix barcode payloads ✓",
            "Embedding SKU-COPPER-WIRE, GRN-3012, Batch B-2026-91 ✓",
            "Sending raw ZPL/EPL commands to industrial thermal printer ✓",
            "Pallets tagged with machine-readable tracking barcodes ✓",
          ],
          databaseEffect: "label_print_logs record committed.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Procurement & Purchase Orders",
        route: "/procurement",
        document: "Issued PO-9002",
        dataPassed: "Ordered SKUs, agreed prices, and allowed receipt over-delivery tolerance.",
        relationship: "Receipt baseline",
      },
      {
        moduleName: "Inbound Logistics TMS",
        route: "/logistics",
        document: "Gate Entry Pass & Challan",
        dataPassed: "Carrier LR number, vehicle number, and package count.",
        relationship: "Physical gate authorization",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Quality Inspection (QC)",
        route: "/warehouse-qc",
        document: "Quarantined GRN Lot",
        dataPassed: "GRN-3012, received quantity, batch number, and supplier name.",
        relationship: "Triggers mandatory quality testing",
      },
      {
        moduleName: "Finance & 3-Way Matching",
        route: "/finance",
        document: "GRN Receipt Quantities",
        dataPassed: "Confirmed received line quantities and receipt timestamp.",
        relationship: "Supplies physical leg of 3-Way invoice match",
      },
    ],
    businessControls: [
      "Receipt quantities cannot exceed PO quantity beyond configured over-delivery tolerance (default 5%).",
      "Received goods immediately placed in 'Quarantine' status; cannot be issued to production until QC approved.",
    ],
  },

  // STEP 11: QUALITY CONTROL,

    {
    stepNumber: 11,
    id: "quality-control-qc",
    title: "Quality Control (QC), AQL Sampling & Lot Clearance",
    shortTitle: "11. Quality QC",
    route: "/warehouse-qc",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 3: Inbound Logistics & Receiving",
    stream: "Warehouse & WMS",
    category: "Warehouse & Quality",
    iconName: "ShieldCheck",
    actorRole: "Quality Inspector (qc:read, qc:inspect, qc:disposition)",
    summary: "Executes sampling plans, records test results, and dispositions lots to Accepted, Rejected, or Quarantined.",
    businessPurpose:
      "Prevents defective or non-compliant raw materials from contaminating the production line and customer shipments.",
    keyObjectives: [
      "Follow AQL (Acceptable Quality Limit) sampling inspection procedures.",
      "Record parametric inspection values (dimensions, tensile strength, visual surface flaws).",
      "Issue disposition: Approve for putaway, quarantine for rework, or reject for Return to Vendor (RTV).",
    ],
    workflows: [
      {
        id: "qc-aql-sample",
        actionNumber: 1,
        title: "AQL Statistical Sampling Intake",
        shortTitle: "Take AQL Samples",
        actor: "QA Technician",
        permissionRequired: "qc:inspect",
        triggerEvent: "GRN-3012 arrives in Quarantine inspection bay",
        stepByStepInstructions: [
          "Navigate to 'Quality Inspection Station' (/warehouse-qc).",
          "Select pending inspection GRN-3012 (5,000m Copper Wire).",
          "System calculates ISO 2859-1 General Inspection Level II sample size: 32 random test cut samples.",
          "Technician draws samples across multiple pallets.",
        ],
        systemValidations: [
          "Inspection cannot proceed without verified sample size.",
        ],
        tablesAndLedgersMutated: ["qc_inspections table (status='in_progress')"],
        outputDocument: "QC Inspection Work Sheet (QC-2026-809)",
        simulation: {
          scenarioDescription: "Drawing 32 random samples from GRN-3012 for lab testing.",
          initialState: "Awaiting QA Intake",
          buttonLabel: "Simulate AQL Sampling",
          successState: "32 Test Samples Drawn",
          executionLog: [
            "Calculating sample size: Lot size 5,000 -> 32 test units ✓",
            "Logging sample draws from Pallet 1, 3, 5, 12, 20 ✓",
            "Opening inspection record QC-2026-809 ✓",
          ],
          databaseEffect: "qc_inspections row created with sample_count=32.",
        },
      },
      {
        id: "qc-disposition",
        actionNumber: 2,
        title: "Record Parametric Test Readings & Clear Lot",
        shortTitle: "Pass QC Clearance",
        actor: "Quality Manager",
        permissionRequired: "qc:disposition",
        triggerEvent: "Lab tests completed on 32 samples",
        stepByStepInstructions: [
          "Enter test readings: Wire Diameter (0.80mm ±0.01mm) -> Measured: 0.802mm ✓.",
          "Enter Electrical Resistance (<0.034 Ω/m) -> Measured: 0.032 Ω/m ✓.",
          "Enter Tensile Strength (>220 MPa) -> Measured: 245 MPa ✓.",
          "Select Lot Disposition: 'Accepted 100%'.",
          "Click 'Sign & Release Quality Certificate of Analysis (CoA)'.",
        ],
        systemValidations: [
          "Out-of-spec readings automatically force lot rejection or quarantine escalation.",
          "Sign-off requires authorized QC Manager role.",
        ],
        tablesAndLedgersMutated: [
          "qc_inspections (status -> 'passed')",
          "inventory_items (bucket: 'quarantine' -> 'available')",
          "certificates_of_analysis table",
        ],
        outputDocument: "Certificate of Analysis & QC Release Certificate",
        simulation: {
          scenarioDescription: "All 32 test samples pass parameters; releasing lot to WMS putaway.",
          initialState: "In-Progress (Pending Test Sign-Off)",
          buttonLabel: "Simulate Pass QC Clearance",
          successState: "QC Passed (Cleared for Putaway)",
          executionLog: [
            "Validating dimensional tolerances: 100% pass ✓",
            "Validating electrical resistance: 100% pass ✓",
            "Applying Quality Manager digital sign-off ✓",
            "Generating Certificate of Analysis CoA-3012 ✓",
            "Inventory status updated: 'Quarantine' -> 'Available' ✓",
            "Directed WMS putaway task automatically generated ✓",
          ],
          databaseEffect: "inventory_items bucket updated to 'available'; putaway task created.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Inbound Receiving (GRN)",
        route: "/warehouse",
        document: "GRN-3012 Inbound Lot",
        dataPassed: "Quarantine batch number, SKU code, and manufacturer mill test report.",
        relationship: "Inspection target",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Directed WMS Bins & Storage",
        route: "/wms-bins",
        document: "QC Accepted Pallets",
        dataPassed: "Cleared batch IDs, accepted quantities, handling requirements.",
        relationship: "Initiates directed warehouse putaway",
      },
      {
        moduleName: "Vendor Returns (RTV) & Finance",
        route: "/returns",
        document: "Defective Lot Rejection Notice",
        dataPassed: "Rejected quantities, failure reason, and photos.",
        relationship: "Triggers return to vendor and finance debit note",
      },
    ],
    businessControls: [
      "Strict zero-bypass policy: System completely blocks putaway or production issue of un-inspected lots.",
      "Rejection requires root cause categorization (packaging defect, dimensional out-of-spec, chemical failure).",
    ],
  },

  // STEP 12: WMS DIRECTED BINS,

    {
    stepNumber: 12,
    id: "wms-directed-bins",
    title: "Directed WMS Bins, Optimal Putaway & Double-Entry Stock Ledger",
    shortTitle: "12. WMS Putaway",
    route: "/wms-bins",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 3: Inbound Logistics & Receiving",
    stream: "Warehouse & WMS",
    category: "Warehouse & Logistics",
    iconName: "Layers",
    actorRole: "WMS Forklift Driver / Warehouse Lead (wms:read, bin:putaway)",
    summary: "Directs pallet putaway into optimal warehouse bins by weight/velocity and maintains the stock ledger.",
    businessPurpose:
      "Maximizes warehouse space utilization, enforces strict FIFO/FEFO picking order, and maintains an immutable audit trail of every stock movement.",
    keyObjectives: [
      "Recommend optimal bin location based on item velocity class (Fast/Slow moving) and rack weight limits.",
      "Scan rack barcodes via handheld mobile scanner to confirm exact putaway coordinates.",
      "Maintain double-entry stock accounting (every debit from source location has matching credit to destination).",
    ],
    workflows: [
      {
        id: "wms-directed-putaway",
        actionNumber: 1,
        title: "Scan Pallet & Receive Directed Bin Recommendation",
        shortTitle: "Direct Putaway",
        actor: "Forklift Operator",
        permissionRequired: "bin:putaway",
        triggerEvent: "Pallet released from QC inspection bay",
        stepByStepInstructions: [
          "Forklift operator opens mobile scanner at staging bay (/wms-bins or /wms-mobile).",
          "Scan Pallet QR code 'GRN-3012-P1'.",
          "System evaluates item velocity class (Heavy Raw Material) and current rack occupancy.",
          "System directs operator to Rack A, Bay 04, Shelf 2: 'BIN-A-04-2'.",
        ],
        systemValidations: [
          "Rejects bin if pallet weight exceeds shelf max weight capacity (e.g. 1,000 kg).",
          "Prevents co-mingling of incompatible materials.",
        ],
        tablesAndLedgersMutated: ["wms_putaway_tasks table (in_progress)"],
        outputDocument: "Directed Putaway Route Card",
        simulation: {
          scenarioDescription: "Directing 500kg copper wire pallet to heavy lower rack Bin A-04-2.",
          initialState: "Pallet at Staging Bay",
          buttonLabel: "Simulate Scan Pallet QR",
          successState: "Directed to Optimal Bin A-04-2",
          executionLog: [
            "Scanning Pallet QR GRN-3012-P1 ✓",
            "Weight: 500kg -> Evaluating lower heavy-duty tiers ✓",
            "Recommending Bin A-04-2 (Velocity: Class A, Capacity: 45% available) ✓",
          ],
          databaseEffect: "wms_putaway_tasks row created with recommended_bin='BIN-A-04-2'.",
        },
      },
      {
        id: "wms-confirm-bin",
        actionNumber: 2,
        title: "Scan Bin Barcode & Post Double-Entry Stock Movement",
        shortTitle: "Confirm Storage",
        actor: "Forklift Operator",
        permissionRequired: "bin:putaway",
        triggerEvent: "Operator deposits pallet in designated rack",
        stepByStepInstructions: [
          "Operator navigates to Rack A-04.",
          "Deposits pallet onto shelf 2.",
          "Scans rack barcode sticker 'BIN-A-04-2' with handheld scanner.",
          "System confirms match and posts double-entry stock movement.",
        ],
        systemValidations: [
          "Scan of wrong rack barcode generates audio warning and halts confirmation.",
          "Stock ledger forbids negative inventory balance.",
        ],
        tablesAndLedgersMutated: [
          "wms_bins table (capacity updated)",
          "stock_ledger table (double-entry movement)",
          "inventory_items (location_id -> BIN-A-04-2)",
        ],
        outputDocument: "Stock Ledger Movement Confirmation",
        simulation: {
          scenarioDescription: "Scanning rack barcode BIN-A-04-2 to confirm physical placement.",
          initialState: "Forklift at Rack A-04",
          buttonLabel: "Simulate Scan & Confirm Bin",
          successState: "Stored in Bin A-04-2 (Available)",
          executionLog: [
            "Scanning barcode 'BIN-A-04-2' ✓",
            "Barcode match confirmed ✓",
            "Double-entry ledger: Credit Staging Bay, Debit Bin A-04-2 ✓",
            "5,000m Copper Wire now available for Manufacturing Issue ✓",
          ],
          databaseEffect: "stock_ledger row committed; bin capacity incremented to 85%.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Quality Inspection (QC)",
        route: "/warehouse-qc",
        document: "QC Cleared Pallet",
        dataPassed: "Item SKU, lot number, cleared quantity, unit weight.",
        relationship: "Storage candidate",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Manufacturing & Work Orders",
        route: "/production",
        document: "Raw Material On-Hand Stock",
        dataPassed: "Bin coordinates, available quantities, and lot FIFO dates.",
        relationship: "Enables component picking for work orders",
      },
      {
        moduleName: "Sales Order Allocation",
        route: "/orders",
        document: "Available Inventory Balance",
        dataPassed: "Total unallocated stock by facility.",
        relationship: "Enables sales order reservation",
      },
    ],
    businessControls: [
      "System rejects putaway if bin weight capacity would be exceeded.",
      "Double-entry stock ledger forbids negative inventory under all circumstances.",
    ],
  },

  // =========================================================================
  // PHASE 4: MANUFACTURING & SHOP-FLOOR EXECUTION (Plan-to-Produce)
  // =========================================================================

  // STEP 13: MANUFACTURING & ASSEMBLY,

    {
    stepNumber: 13,
    id: "manufacturing-work-orders",
    title: "Manufacturing Execution (MES), Work Orders & Assembly Routing",
    shortTitle: "13. Manufacturing",
    route: "/production",
    navGroup: "Manufacturing",
    phase: "Phase 4: Manufacturing & Assembly Execution",
    stream: "Plan-to-Produce",
    category: "Manufacturing & Operations",
    iconName: "Factory",
    actorRole: "Shop Floor Supervisor / Plant Manager (production:read, production:run)",
    summary: "Executes work orders, issues raw materials using FIFO lot rotation, backflushes components against the BOM recipe, tracks in-process IPQC inspection, and completes serialized Finished Goods assembly.",
    businessPurpose:
      "Transforms raw materials and components into finished sellable products while accurately tracking scrap, labor costs, and component consumption.",
    keyObjectives: [
      "Release planned work orders (WO-1050) to the shop-floor assembly line.",
      "Issue raw materials using FIFO lot rotation and backflush components against the BOM recipe.",
      "Record station progress, scrap variances, and inspect finished goods before putting them into stock.",
    ],
    workflows: [
      {
        id: "mfg-issue-materials",
        actionNumber: 1,
        title: "Release Work Order & Issue Raw Materials via FIFO",
        shortTitle: "Issue Raw Materials",
        actor: "Shop Floor Supervisor",
        permissionRequired: "production:run",
        triggerEvent: "Work Order WO-1050 scheduled for Line 1 assembly",
        stepByStepInstructions: [
          "Navigate to 'Production & Runs' (/production).",
          "Open scheduled Work Order 'WO-1050' (500 Motors to assemble).",
          "Click 'Release Work Order to Assembly Line'.",
          "Click 'Issue Raw Materials'.",
          "System picks raw copper wire from Bin A-04-2 using oldest FIFO lot date.",
          "Materials move from Warehouse into Work-in-Progress (WIP) staging.",
        ],
        systemValidations: [
          "Enforces FIFO lot consumption: older batches must be consumed before newer ones.",
          "Stock deduction uses database row-level lock to prevent double-issuance.",
        ],
        tablesAndLedgersMutated: [
          "production_runs (status -> 'in_progress')",
          "stock_ledger (debit WIP, credit Warehouse Bin)",
        ],
        outputDocument: "Material Issue Slip (MIS-8812)",
        simulation: {
          scenarioDescription: "Issuing 5,000m copper wire from Bin A-04-2 to Line 1 WIP staging.",
          initialState: "WO-1050 Planned (Materials in Bin)",
          buttonLabel: "Simulate Material Issue",
          successState: "Materials Issued to Line 1 WIP",
          executionLog: [
            "Selecting oldest lot B-2026-91 via FIFO rules ✓",
            "Deducting 5,000m wire from Bin A-04-2 ✓",
            "Debiting Work-in-Progress (WIP) inventory account ✓",
            "WO-1050 status updated to 'In-Progress' ✓",
          ],
          databaseEffect: "stock_ledger row posted; production_runs status set to in_progress.",
        },
      },
      {
        id: "mfg-complete-assembly",
        actionNumber: 2,
        title: "Complete Assembly Run & Convert WIP to Finished Goods",
        shortTitle: "Complete Assembly",
        actor: "Assembly Lead",
        permissionRequired: "production:run",
        triggerEvent: "Physical assembly and end-of-line testing complete",
        stepByStepInstructions: [
          "In Work Order WO-1050, click 'Complete Production Run'.",
          "Enter Assembled Good Units: 500 Motors.",
          "Enter Scrap / Rejection: 4 Motors (0.8% scrap - within 1% allowance).",
          "Enter Machine Run Hours: 16.5 hrs.",
          "Click 'Submit Run Completion & Generate FG Serial Stickers'.",
          "System converts WIP valuation into Finished Goods inventory (Bin FG-02-1).",
        ],
        systemValidations: [
          "Scrap exceeding 5% requires Plant Manager digital override.",
          "Finished goods serialized with unique serial numbers (MOT-2026-0001 to 0500).",
        ],
        tablesAndLedgersMutated: [
          "production_runs (status -> 'completed')",
          "production_run_items table",
          "inventory_items (500 new FG items)",
          "stock_ledger (credit WIP, debit Finished Goods)",
        ],
        outputDocument: "Production Completion Record & Serialized FG Labels",
        simulation: {
          scenarioDescription: "Assembly complete: 500 electric motors assembled and serialized.",
          initialState: "Line 1 Running (WO-1050 in WIP)",
          buttonLabel: "Simulate Complete Assembly Run",
          successState: "500 Motors Converted to Finished Goods",
          executionLog: [
            "Backflushing 500 Rotors, 500 Stators, 5,000m wire against BOM ✓",
            "Logging scrap: 4 defective units recorded to scrap variance ✓",
            "Crediting WIP account ₹3,75,000; Debiting Finished Goods ₹3,75,000 ✓",
            "Minting 500 unique serial numbers (MOT-2026-0001...0500) ✓",
            "500 Motors added to Finished Goods inventory (Bin FG-02-1) ✓",
          ],
          databaseEffect: "production_runs marked completed; 500 inventory_items rows added.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "MRP Planning & BOM",
        route: "/mrp",
        document: "Planned Work Order & BOM",
        dataPassed: "Target SKU, assembly quantity, recipe components, routing steps.",
        relationship: "Manufacturing instructions",
      },
      {
        moduleName: "Warehouse Stock Ledger",
        route: "/wms-bins",
        document: "Raw Materials in Bins",
        dataPassed: "Allocated raw components ready for shop-floor issue.",
        relationship: "Component supply",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Finished Goods Inventory",
        route: "/inventory",
        document: "Completed Finished Goods",
        dataPassed: "500 assembled Electric Motors, serial numbers, unit production cost.",
        relationship: "Supplies sellable stock to inventory",
      },
      {
        moduleName: "Cost Accounting & Finance",
        route: "/finance",
        document: "Material & Labor Variance Report",
        dataPassed: "Actual component consumption vs standard BOM recipe, scrap percentages.",
        relationship: "Calculates manufacturing variance for GL",
      },
    ],
    businessControls: [
      "Work order cannot be closed if component consumption deviates by >10% without supervisor scrap sign-off.",
      "Raw materials are deducted via row-locked database transactions to prevent double-consumption.",
    ],
  },

  // =========================================================================
  // PHASE 5: SALES, WAREHOUSE PICKING & OUTBOUND DISPATCH (Order-to-Cash)
  // =========================================================================

  // STEP 14: SALES ORDERS & ALLOCATION,

    {
    stepNumber: 14,
    id: "sales-orders-allocation",
    title: "Sales Orders, Customer Credit Audit & Row-Locked Stock Allocation",
    shortTitle: "14. Sales Orders",
    route: "/orders",
    navGroup: "Sales & Orders",
    phase: "Phase 5: Sales Fulfillment & Outbound Logistics",
    stream: "Order-to-Cash",
    category: "Sales & Fulfillment",
    iconName: "ClipboardList",
    actorRole: "Sales Operations / Account Manager (order:read, order:write, order:allocate)",
    summary: "Books customer purchase orders, runs automated credit limit and overdue aging checks, and locks inventory via row-level FIFO reservations with zero double-selling risk.",
    businessPurpose:
      "Captures customer revenue commitments while ensuring products are never promised beyond available stock or customer credit limits.",
    keyObjectives: [
      "Capture customer purchase orders with pricing rules, delivery dates, and tax breakdown.",
      "Automatically audit customer credit balances and block orders if overdue limits are exceeded.",
      "Execute database row-locked FIFO inventory allocation to reserve stock without double-selling risk.",
    ],
    workflows: [
      {
        id: "so-intake-credit",
        actionNumber: 1,
        title: "Book Sales Order & Run Automated Credit Audit",
        shortTitle: "Book Order & Credit Check",
        actor: "Sales Officer",
        permissionRequired: "order:write",
        triggerEvent: "Customer AutoCorp sends signed purchase order",
        stepByStepInstructions: [
          "Navigate to 'Sales Orders' (/orders).",
          "Click '+ New Sales Order'.",
          "Select Customer: 'AutoCorp Mobility Solutions' (CUST-AUTOCORP-01).",
          "System runs automated credit audit: Checks credit limit (₹5,00,000) vs current outstanding (₹1,50,000) -> Available Credit: ₹3,50,000 ✓.",
          "Checks overdue aging: Zero invoices overdue > 60 days ✓.",
          "Add Line Item: SKU-MOT-500, Qty: 500 Motors @ ₹1,200.00 = ₹6,00,000 + 18% GST.",
          "Click 'Confirm Sales Order'.",
        ],
        systemValidations: [
          "System automatically places order on 'Credit Hold' if customer has invoices overdue by >60 days.",
          "Selling price cannot be below minimum floor margin without VP Sales sign-off.",
        ],
        tablesAndLedgersMutated: [
          "orders table (new SO-5011)",
          "order_lines table",
        ],
        outputDocument: "Confirmed Sales Order (SO-5011)",
        simulation: {
          scenarioDescription: "Booking order SO-5011 for 500 Motors from AutoCorp; running credit check.",
          initialState: "Customer Purchase Order Received",
          buttonLabel: "Simulate Book Order & Credit Check",
          successState: "SO-5011 Confirmed (Credit Audit Passed)",
          executionLog: [
            "Auditing customer AutoCorp credit balance: ₹3,50,000 credit buffer ✓",
            "Checking invoice aging: Zero overdue flags ✓",
            "Creating Sales Order SO-5011 for 500 Motors ✓",
            "Order status marked 'Confirmed' (Awaiting Stock Allocation) ✓",
          ],
          databaseEffect: "orders and order_lines rows committed with status='confirmed'.",
        },
      },
      {
        id: "so-allocate-stock",
        actionNumber: 2,
        title: "Execute Row-Locked FIFO Inventory Allocation",
        shortTitle: "Allocate Stock",
        actor: "Fulfillment Coordinator",
        permissionRequired: "order:allocate",
        triggerEvent: "Order approved for warehouse fulfillment",
        stepByStepInstructions: [
          "Open confirmed Sales Order SO-5011.",
          "Click 'Allocate Inventory' button.",
          "System initiates transaction with row-level locks on `inventory_items` table.",
          "System queries oldest available Finished Goods motors in Bin FG-02-1.",
          "Locks 500 units: Moves status from 'Available' to 'Allocated' (Reserved for SO-5011).",
          "Order status updates to 'Allocated 100%' and releases pick task to warehouse.",
        ],
        systemValidations: [
          "Row-locked reservation prevents concurrent race conditions or overselling.",
          "Orders cannot be partially allocated if customer requested 'Complete Shipment Only'.",
        ],
        tablesAndLedgersMutated: [
          "inventory_items (reserved_order_id = SO-5011)",
          "orders (status -> 'allocated')",
          "order_allocations table",
        ],
        outputDocument: "Stock Allocation Lock & Warehouse Pick Release",
        simulation: {
          scenarioDescription: "Locking 500 motors from Bin FG-02-1 via row-level FIFO transaction.",
          initialState: "SO-5011 Confirmed (Unallocated)",
          buttonLabel: "Simulate Row-Locked Allocation",
          successState: "100% Allocated (Ready for Wave Pick)",
          executionLog: [
            "Acquiring PostgreSQL row-level locks on inventory_items ✓",
            "Reserving 500 Motors from Bin FG-02-1 (Serial MOT-0001 to 0500) ✓",
            "Available inventory decremented by 500; Allocated incremented by 500 ✓",
            "Zero double-selling risk; order released to Wave Picking queue ✓",
          ],
          databaseEffect: "inventory_items tagged with order_id=SO-5011; orders status='allocated'.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Parties & Customer Master",
        route: "/parties",
        document: "Customer Account Profile",
        dataPassed: "Credit limit (₹5,00,000), billing/shipping address, and payment terms.",
        relationship: "Customer validation",
      },
      {
        moduleName: "Finished Goods Inventory",
        route: "/inventory",
        document: "Available FG Stock",
        dataPassed: "On-hand Finished Goods balance available for reservation.",
        relationship: "Inventory availability",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Warehouse Wave Picking",
        route: "/wave-picking",
        document: "Allocated Pick List",
        dataPassed: "Order number, reserved SKU, bin locations, and delivery urgency.",
        relationship: "Releases picking task to warehouse crew",
      },
      {
        moduleName: "Finance & Customer Billing",
        route: "/finance",
        document: "Sales Order Line Details",
        dataPassed: "Agreed prices, GST tax calculations, and payment terms.",
        relationship: "Prepares sales tax invoice",
      },
    ],
    businessControls: [
      "Automated credit check blocks order release if customer has invoices overdue by >60 days.",
      "Row-locked reservation guarantees zero possibility of ghost allocations or overselling.",
    ],
  },

  // STEP 15: WAVE PICKING & PACKING,

    {
    stepNumber: 15,
    id: "wave-picking-packing",
    title: "Warehouse Wave Picking, Mobile Terminals & Carton Packing",
    shortTitle: "15. Wave Picking",
    route: "/wave-picking",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 5: Sales Fulfillment & Outbound Logistics",
    stream: "Warehouse & WMS",
    category: "Warehouse & Logistics",
    iconName: "Package",
    actorRole: "Dispatch Lead / Shipping Clerk (wave:pick, shipping:dispatch)",
    summary: "Batches orders into optimized pick waves, packs cartons with weighment, and generates e-Way bills.",
    businessPurpose:
      "Fulfills customer orders rapidly with minimal warehouse travel distance while complying with transport regulations.",
    keyObjectives: [
      "Batch multiple customer orders into single-pass pick waves to cut travel time by up to 40%.",
      "Verify packed cartons with barcode scanning and precision scale weighment check.",
      "Generate statutory GST e-Way bills and carrier Airway Bills (AWB) for outward transport.",
    ],
    workflows: [
      {
        id: "wp-wave-batch",
        actionNumber: 1,
        title: "Create Pick Wave & Execute Mobile Scanner Aisle Routing",
        shortTitle: "Execute Wave Pick",
        actor: "Warehouse Picker",
        permissionRequired: "wave:pick",
        triggerEvent: "Batch of allocated orders released for 2 PM shipping cutoff",
        stepByStepInstructions: [
          "Navigate to 'Wave & Batch Picking' (/wave-picking).",
          "Select Orders scheduled for AutoCorp and regional shipments.",
          "Click 'Generate Pick Wave' (Wave WAVE-812).",
          "Picker logs in to mobile terminal (/wms-mobile).",
          "Terminal displays optimized snake-path aisle routing (Bin FG-02-1).",
          "Picker scans bin barcode, picks 500 Motors into wave cart, and scans item barcodes.",
        ],
        systemValidations: [
          "Scanning incorrect barcode buzzes error and prevents picking wrong SKU.",
          "Pick wave enforces FIFO lot picking sequence.",
        ],
        tablesAndLedgersMutated: [
          "pick_waves table",
          "pick_wave_items table (status -> 'picked')",
        ],
        outputDocument: "Completed Wave Pick Cart (WAVE-812)",
        simulation: {
          scenarioDescription: "Picker follows mobile directed route to pick 500 motors from Bin FG-02-1.",
          initialState: "Allocated Order in Pick Queue",
          buttonLabel: "Simulate Wave Pick Run",
          successState: "500 Motors Picked into Wave Cart",
          executionLog: [
            "Batching SO-5011 into Pick Wave WAVE-812 ✓",
            "Directing picker via mobile scanner to Bin FG-02-1 ✓",
            "Scanning and verifying 500 serialized motor barcodes ✓",
            "Transferring picked items to Packing Bench 2 ✓",
          ],
          databaseEffect: "pick_waves status marked 'picked'; items moved to packing bench.",
        },
      },
      {
        id: "wp-pack-weigh",
        actionNumber: 2,
        title: "Pack Shipping Cartons & Digital Scale Weighment Audit",
        shortTitle: "Pack & Weighment",
        actor: "Packer & Shipping Clerk",
        permissionRequired: "wave:pick",
        triggerEvent: "Wave cart arrives at Packing Bench 2",
        stepByStepInstructions: [
          "Packing clerk opens packing screen for SO-5011.",
          "Scan carton box and pack 20 motors per industrial carton (25 cartons total).",
          "Place cartons onto integrated digital scale.",
          "Scale records actual weight: 420.5 kg (Expected: 420.0 kg, Variance: +0.12% - within 2% tolerance).",
          "Click 'Confirm Packing & Print Shipping Labels'.",
        ],
        systemValidations: [
          "Weight discrepancy > 2% halts packing to catch missing items or packing errors.",
          "Every outer carton gets machine-readable shipping label with tracking barcode.",
        ],
        tablesAndLedgersMutated: [
          "shipment_packages table (carton details & weights)",
          "orders (status -> 'packed')",
        ],
        outputDocument: "25 Manifested Shipping Cartons with Labels",
        simulation: {
          scenarioDescription: "Packing 500 motors into 25 cartons; digital scale verifies weight 420.5 kg.",
          initialState: "Picked Items at Packing Bench",
          buttonLabel: "Simulate Pack & Weighment",
          successState: "25 Cartons Packed & Weighed",
          executionLog: [
            "Cartonizing 500 motors into 25 reinforced corrugated boxes ✓",
            "Digital scale reading: 420.5 kg (Tolerance check passed: 0.12%) ✓",
            "Generating shipping carton labels with 2D Datamatrix codes ✓",
            "Order SO-5011 status updated to 'Packed' ✓",
          ],
          databaseEffect: "shipment_packages rows created; orders status set to 'packed'.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Sales Order Management",
        route: "/orders",
        document: "Allocated Sales Orders",
        dataPassed: "Order SO-5011 lines, customer delivery address, and transport priority.",
        relationship: "Fulfillment requirement",
      },
      {
        moduleName: "WMS Directed Bins",
        route: "/wms-bins",
        document: "Bin Coordinates",
        dataPassed: "Precise aisle, rack, and shelf location of reserved goods.",
        relationship: "Picker routing blueprint",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Outbound Freight TMS",
        route: "/freight-tms",
        document: "Manifested Consignment",
        dataPassed: "Transporter name, vehicle number, package dimensions, and e-Way bill #.",
        relationship: "Carrier pickup coordination",
      },
      {
        moduleName: "Finance & Accounts Receivable",
        route: "/finance",
        document: "Proof of Delivery / Dispatch Confirmation",
        dataPassed: "Shipped line quantities, serial numbers, and dispatch timestamp.",
        relationship: "Triggers final customer tax invoice and revenue recognition",
      },
    ],
    businessControls: [
      "Weight tolerance check: If packed box weight deviates by >2% from expected SKU weight, packing is halted.",
      "Consignments exceeding ₹50,000 strictly blocked from dispatch without verified 12-digit e-Way bill.",
    ],
  },

  // STEP 16: OUTBOUND SHIPPING & E-WAY BILLS,

    {
    stepNumber: 16,
    id: "outbound-shipping-eway",
    title: "Outbound Freight TMS, Statutory e-Way Bills & Carrier Dispatch",
    shortTitle: "16. Outbound Shipping",
    route: "/shipping-engine",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 5: Sales Fulfillment & Outbound Logistics",
    stream: "Order-to-Cash",
    category: "Warehouse & Logistics",
    iconName: "Truck",
    actorRole: "Logistics Manager / Shipping Officer (shipping:dispatch, statutory:write)",
    summary: "Executes carrier rate shopping, generates mandatory 12-digit GST e-Way bills, prints Airway Bills (AWB), and executes physical lorry handover.",
    businessPurpose:
      "Ensures regulatory tax compliance under Indian GST Rule 138 (e-Way Bill) while securing fast, cost-effective carrier freight delivery to customers.",
    keyObjectives: [
      "Rate-shop across registered transporters to select fastest SLA at lowest landed cost.",
      "Connect directly to statutory GST portal to generate 12-digit e-Way Bill for consignments > ₹50,000.",
      "Record outward vehicle loading, print handover manifests, and deduct stock from inventory.",
    ],
    workflows: [
      {
        id: "shp-gen-eway",
        actionNumber: 1,
        title: "Generate Statutory GST e-Way Bill",
        shortTitle: "Generate e-Way Bill",
        actor: "Statutory Compliance Clerk",
        permissionRequired: "statutory:write",
        triggerEvent: "Consignment value exceeds ₹50,000 (SO-5011 value: ₹7,08,000)",
        stepByStepInstructions: [
          "Navigate to 'Statutory Logistics' (/statutory-logistics).",
          "Select packed shipment for Order SO-5011.",
          "Verify consignee GSTIN, HSN Code (8501), and Transporter ID.",
          "Enter Carrier Vehicle Number (e.g. 'MH-14-EN-9912').",
          "Click 'Generate e-Way Bill via GST API'.",
          "System fetches statutory 12-digit e-Way Bill #882910488219 and prints transit copy.",
        ],
        systemValidations: [
          "Mandatory for consignments >₹50,000 under GST Rule 138; dispatch blocked without it.",
          "HSN code must match registered products.",
        ],
        tablesAndLedgersMutated: [
          "statutory_eway_bills table",
          "orders (eway_bill_number stamped)",
        ],
        outputDocument: "Statutory 12-Digit GST e-Way Bill #882910488219",
        simulation: {
          scenarioDescription: "Generating GST e-Way bill for ₹7,08,000 consignment to AutoCorp.",
          initialState: "Packed (No Statutory Clearance)",
          buttonLabel: "Simulate Generate e-Way Bill",
          successState: "e-Way Bill #882910488219 Generated",
          executionLog: [
            "Validating consignee GSTIN 27AABCA9999A1Z5 ✓",
            "Connecting to statutory e-Way Bill gateway API ✓",
            "Fetching 12-digit e-Way Bill #882910488219 (Valid 72 hrs) ✓",
            "Printing statutory transit transport copy ✓",
          ],
          databaseEffect: "statutory_eway_bills row inserted; orders stamped with eway_bill_number.",
        },
      },
      {
        id: "shp-carrier-dispatch",
        actionNumber: 2,
        title: "Hand Over Consignment to Carrier & Post Inventory Relinquishment",
        shortTitle: "Carrier Dispatch",
        actor: "Dispatch Lead",
        permissionRequired: "shipping:dispatch",
        triggerEvent: "Transporter lorry docked at Outbound Bay 4",
        stepByStepInstructions: [
          "Load 25 cartons into transporter vehicle.",
          "Driver signs transport manifest with driver license number.",
          "Click 'Confirm Outward Carrier Dispatch'.",
          "System posts final inventory relief: Debits Cost of Goods Sold (COGS), Credits Finished Goods Inventory.",
          "Order status updates to 'Dispatched' (In-Transit).",
        ],
        systemValidations: [
          "Carrier driver must sign physical/digital manifest before gate pass release.",
          "Stock ledger decreases physical inventory count immediately upon dispatch confirmation.",
        ],
        tablesAndLedgersMutated: [
          "orders (status -> 'dispatched')",
          "stock_ledger (credit Finished Goods, debit COGS)",
          "inventory_items (status -> 'shipped')",
        ],
        outputDocument: "Carrier Handover Manifest & Outward Dispatch Pass",
        simulation: {
          scenarioDescription: "Driver signs manifest; 500 motors dispatched to AutoCorp.",
          initialState: "Packed & Staged at Outbound Bay 4",
          buttonLabel: "Simulate Outward Dispatch",
          successState: "Dispatched (In-Transit to Customer)",
          executionLog: [
            "Loading 25 cartons into vehicle MH-14-EN-9912 ✓",
            "Recording transporter driver sign-off on manifest ✓",
            "Stock ledger posted: Relieving 500 Motors from inventory ✓",
            "Debiting Cost of Goods Sold (COGS) ₹3,75,000 in Finance ✓",
            "Customer notified of dispatch with tracking link ✓",
          ],
          databaseEffect: "stock_ledger posted; orders status set to 'dispatched'.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Wave Picking & Packing",
        route: "/wave-picking",
        document: "Packed Cartons",
        dataPassed: "Carton weights, counts, and shipping labels.",
        relationship: "Shipping manifests packed goods",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Finance & Accounts Receivable",
        route: "/finance",
        document: "Outward Dispatch Record",
        dataPassed: "Shipped line items and proof of delivery carrier receipt.",
        relationship: "Triggers final customer tax invoice and revenue recognition",
      },
    ],
    businessControls: [
      "Consignments exceeding ₹50,000 strictly blocked from dispatch without verified 12-digit e-Way bill.",
      "Stock ledger decrements physical balance at exact moment of carrier handover.",
    ],
  },

  // =========================================================================
  // PHASE 6: REVERSE LOGISTICS, FINANCE & ENTERPRISE CONTROL
  // =========================================================================

  // STEP 17: CUSTOMER RETURNS (RMA),

    {
    stepNumber: 17,
    id: "returns-reverse-logistics",
    title: "Customer Returns, Technical Triage & Reverse Logistics (RMA)",
    shortTitle: "17. Returns & RMA",
    route: "/returns",
    navGroup: "Warehouse & Logistics",
    phase: "Phase 6: Reverse Logistics, Finance & Governance",
    stream: "Order-to-Cash",
    category: "Warehouse & Logistics",
    iconName: "RotateCcw",
    actorRole: "Customer Service Lead / Quality Specialist (return:read, return:triage)",
    summary: "Manages return merchandise authorizations (RMA), dock intake of returned units, quality triage (restock vs rework vs scrap), and triggers credit notes.",
    businessPurpose:
      "Handles customer returns transparently, ensuring returned items are inspected before restocked, and customer accounts are credited accurately.",
    keyObjectives: [
      "Issue authorized Return Merchandise Authorizations (RMA) against verified customer invoices.",
      "Execute technical triage: Restock to inventory, rework in manufacturing, or scrap with write-off.",
      "Generate automated customer credit notes to adjust Accounts Receivable ledgers.",
    ],
    workflows: [
      {
        id: "rma-create-auth",
        actionNumber: 1,
        title: "Issue Return Merchandise Authorization (RMA)",
        shortTitle: "Authorize RMA",
        actor: "Customer Support Lead",
        permissionRequired: "return:write",
        triggerEvent: "Customer reports 2 motors damaged in transit",
        stepByStepInstructions: [
          "Navigate to 'Returns & RMA' (/returns).",
          "Click '+ New RMA Request'.",
          "Select Customer 'AutoCorp' and Sales Order 'SO-5011'.",
          "Select SKU 'SKU-MOT-500', Quantity: 2 Units.",
          "Reason: 'Transit Damage - Cracked Terminal Block'.",
          "Click 'Authorize RMA' and email return shipping label to customer.",
        ],
        systemValidations: [
          "Return quantity cannot exceed previously shipped invoice quantity.",
          "RMA must be raised within warranty / return window (30 days).",
        ],
        tablesAndLedgersMutated: ["returns table (new RMA-104)"],
        outputDocument: "RMA Authorization (RMA-104)",
        simulation: {
          scenarioDescription: "Authorizing return of 2 transit-damaged motors for AutoCorp.",
          initialState: "Customer Return Request",
          buttonLabel: "Simulate Authorize RMA",
          successState: "RMA-104 Authorized",
          executionLog: [
            "Verifying purchase history on invoice INV-2026-401 ✓",
            "Confirming warranty window valid (7 days elapsed) ✓",
            "Creating Return Authorization RMA-104 for 2 motors ✓",
            "Reverse logistics pickup arranged with carrier ✓",
          ],
          databaseEffect: "returns row created with status='authorized'.",
        },
      },
      {
        id: "rma-triage-credit",
        actionNumber: 2,
        title: "Technical Quality Triage & Customer Credit Note",
        shortTitle: "Triage & Credit Note",
        actor: "QA Inspector & Finance",
        permissionRequired: "return:triage",
        triggerEvent: "Returned units arrive at warehouse reverse dock",
        stepByStepInstructions: [
          "Technician inspects returned units at reverse quarantine bay.",
          "Triage Decision: Unit 1 terminal block repaired -> Restock to B-Grade stock. Unit 2 stator cracked -> Write-off to Scrap.",
          "Submit Triage Record.",
          "Finance generates Credit Note CN-2026-09 for ₹2,400 + tax.",
        ],
        systemValidations: [
          "Scrap requires reason code and photo evidence.",
          "Credit note automatically offsets customer outstanding balance.",
        ],
        tablesAndLedgersMutated: [
          "returns (status -> 'completed')",
          "credit_notes table",
          "stock_ledger (restock 1 unit to B-Grade, scrap 1 unit)",
        ],
        outputDocument: "Customer Credit Note (CN-2026-09)",
        simulation: {
          scenarioDescription: "Triaging 2 returned motors and issuing customer Credit Note CN-2026-09.",
          initialState: "Units at Reverse Dock",
          buttonLabel: "Simulate Triage & Credit Note",
          successState: "Triaged & Credit Note CN-2026-09 Issued",
          executionLog: [
            "Technical inspection completed: 1 reworkable, 1 scrap ✓",
            "Restocking 1 motor to B-Grade inventory (Bin FG-B-01) ✓",
            "Writing off 1 motor to Scrap Expense ledger ✓",
            "Issuing Credit Note CN-2026-09 (₹2,832 incl. GST) to AutoCorp ✓",
          ],
          databaseEffect: "credit_notes row created; customer AR balance credited.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Sales Orders & Billing",
        route: "/orders",
        document: "Customer Invoice",
        dataPassed: "Original order lines, serial numbers, invoice prices.",
        relationship: "Returns reference original sales invoice",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Finance & Accounts Receivable",
        route: "/finance",
        document: "Credit Note",
        dataPassed: "Credit amount to offset customer account balance.",
        relationship: "Reduces customer debt",
      },
      {
        moduleName: "Warehouse Stock Ledger",
        route: "/inventory",
        document: "Restock Movement",
        dataPassed: "Restocked B-Grade items or scrap write-off entries.",
        relationship: "Updates inventory records",
      },
    ],
    businessControls: [
      "Returns cannot be approved without referencing valid original invoice.",
      "Scrap write-offs >₹10,000 require Plant Manager authorization.",
    ],
  },

  // STEP 18: FINANCE & 3-WAY MATCHING,

    {
    stepNumber: 18,
    id: "finance-3way-match-ledger",
    title: "Financial Settlement, 3-Way Invoice Matching & General Ledger",
    shortTitle: "18. Finance & Ledger",
    route: "/finance",
    navGroup: "Finance",
    phase: "Phase 6: Reverse Logistics, Finance & Governance",
    stream: "Finance & Accounting",
    category: "Finance & Accounting",
    iconName: "Receipt",
    actorRole: "Financial Controller / AP Accountant (invoice:read, invoice:post, gl:read)",
    summary: "Reconciles vendor bills via automated 3-way matching (PO vs GRN vs Vendor Invoice), schedules AP payment disbursements, generates customer AR tax invoices, and posts balanced journal entries to the General Ledger.",
    businessPurpose:
      "Guarantees financial integrity: vendors are paid only for what was actually ordered and received, and revenue is recognized accurately.",
    keyObjectives: [
      "Execute automated 3-Way Matching comparing Purchase Order lines, GRN dock receipts, and Vendor Invoices.",
      "Apportion third-party freight and customs duty into inventory valuation using Landed Cost Vouchers.",
      "Maintain real-time General Ledger (GL) double-entry accounting with audit-ready trial balance.",
    ],
    workflows: [
      {
        id: "fin-3way-match",
        actionNumber: 1,
        title: "Execute Automated 3-Way Matching & Approve AP Vendor Bill",
        shortTitle: "3-Way Invoice Match",
        actor: "Accounts Payable Accountant",
        permissionRequired: "invoice:post",
        triggerEvent: "Vendor Acme submits tax invoice for PO-9002 (₹1,47,500)",
        stepByStepInstructions: [
          "Navigate to 'Finance & Billing' (/finance) and select 'Accounts Payable'.",
          "Click '+ Enter Vendor Bill'.",
          "Link Purchase Order: 'PO-9002' and Inward Receipt: 'GRN-3012'.",
          "Click 'Run Automated 3-Way Reconciliation'.",
          "System verifies: PO Price (₹25/m) == Invoice Price (₹25/m) and GRN Qty (5,000m) == Billed Qty (5,000m).",
          "Variance: 0.0% -> Match Confirmed 100%.",
          "Click 'Approve Vendor Bill for Disbursement'.",
        ],
        systemValidations: [
          "Price or quantity variance exceeding ±2% auto-freezes bill and flags buyer exception.",
          "Prevents paying duplicate invoice numbers from the same vendor.",
        ],
        tablesAndLedgersMutated: [
          "vendor_bills table (status='approved')",
          "gl_journal_entries (debit Inward Clearing, credit Accounts Payable)",
        ],
        outputDocument: "Approved Vendor Bill (V-INV-9921) & GL Entries",
        simulation: {
          scenarioDescription: "Reconciling PO-9002, GRN-3012, and Acme invoice with 0.0% variance.",
          initialState: "Vendor Invoice Submitted",
          buttonLabel: "Simulate Run 3-Way Match",
          successState: "Matched 100% (Scheduled for Payment)",
          executionLog: [
            "Leg 1: PO-9002 Contract Price = ₹25.00/m ✓",
            "Leg 2: GRN-3012 Dock Receipt = 5,000 Meters received ✓",
            "Leg 3: Vendor Invoice = 5,000m @ ₹25.00 + 18% GST ✓",
            "3-Way Match Variance: 0.00% (Within ±1% tolerance) ✓",
            "Posting AP Vendor Bill V-INV-9921 in General Ledger ✓",
            "Debiting 'Inventory Inward Clearing' ₹1,25,000 ✓",
            "Crediting 'Accounts Payable' ₹1,47,500 ✓",
          ],
          databaseEffect: "vendor_bills posted; double-entry journal entries committed.",
        },
      },
      {
        id: "fin-ar-invoice",
        actionNumber: 2,
        title: "Post Customer Tax Invoice & Recognize Revenue",
        shortTitle: "Customer Tax Invoice",
        actor: "Accounts Receivable Lead",
        permissionRequired: "invoice:post",
        triggerEvent: "Goods dispatched with e-Way bill confirmed to AutoCorp",
        stepByStepInstructions: [
          "Under 'Accounts Receivable', open Dispatched Order 'SO-5011'.",
          "Click 'Generate Customer Tax Invoice'.",
          "System computes: 500 Motors @ ₹1,200 = ₹6,00,000 + 18% IGST (₹1,08,000) = ₹7,08,000.",
          "Click 'Post Tax Invoice & Send to Customer'.",
          "System debits Accounts Receivable (AutoCorp) and credits Sales Revenue.",
        ],
        systemValidations: [
          "Invoice cannot be generated prior to physical carrier dispatch confirmation.",
          "Tax breakdown must strictly match statutory GST rate brackets.",
        ],
        tablesAndLedgersMutated: [
          "customer_invoices table (INV-2026-401)",
          "gl_journal_entries (debit AR, credit Revenue, credit Output GST)",
        ],
        outputDocument: "Customer Tax Invoice (INV-2026-401: ₹7,08,000)",
        simulation: {
          scenarioDescription: "Posting Tax Invoice INV-2026-401 for AutoCorp upon carrier dispatch.",
          initialState: "Dispatched (Unbilled)",
          buttonLabel: "Simulate Post Tax Invoice",
          successState: "Tax Invoice INV-2026-401 Posted",
          executionLog: [
            "Calculating tax: Base ₹6,00,000 + 18% IGST ₹1,08,000 = ₹7,08,000 ✓",
            "Generating Tax Invoice INV-2026-401 with QR code ✓",
            "Debiting Accounts Receivable (AutoCorp) ₹7,08,000 ✓",
            "Crediting Sales Revenue ₹6,00,000; Crediting GST Payable ₹1,08,000 ✓",
            "Net 30 payment collection schedule initiated ✓",
          ],
          databaseEffect: "customer_invoices created; GL entries posted in balance.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "Procurement & Purchase Orders",
        route: "/procurement",
        document: "Authorized PO-9002",
        dataPassed: "Contracted unit prices, line item totals, payment terms.",
        relationship: "First leg of 3-Way match",
      },
      {
        moduleName: "Inbound Receiving (GRN)",
        route: "/warehouse",
        document: "Dock Receipt GRN-3012",
        dataPassed: "Actual received quantities and inspection clearance timestamp.",
        relationship: "Second leg of 3-Way match",
      },
      {
        moduleName: "Shipping & Order Fulfillment",
        route: "/shipping-engine",
        document: "Outward Dispatch Record",
        dataPassed: "Shipped line items and proof of delivery carrier receipt.",
        relationship: "Revenue recognition basis",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Executive Dashboard & Control Tower",
        route: "/",
        document: "Financial Health & Working Capital",
        dataPassed: "Real-time receivables, payables outstanding, and gross margin.",
        relationship: "Executive financial visibility",
      },
    ],
    businessControls: [
      "Invoices with quantity or price variance exceeding ±2% are auto-flagged and frozen until buyer approval.",
      "Double-entry balance check: Total debits must equal total credits for every posted journal entry.",
    ],
  },

  // STEP 19: CONTROL TOWER & AUDIT,

    {
    stepNumber: 19,
    id: "control-tower-audit",
    title: "Supply Chain Control Tower & Immutable Audit Governance",
    shortTitle: "19. Control Tower",
    route: "/sc-control-tower",
    navGroup: "Overview",
    phase: "Phase 6: Reverse Logistics, Finance & Governance",
    stream: "Governance",
    category: "Overview & Governance",
    iconName: "LayoutDashboard",
    actorRole: "Chief Operating Officer / Auditor (analytics:read, audit:read)",
    summary: "Tracks real-time enterprise KPIs, OTIF compliance, inventory turns, and tamper-proof immutable audit logs.",
    businessPurpose:
      "Gives executives complete visibility across all operational nodes, identifying bottlenecks before they cause delays.",
    keyObjectives: [
      "Monitor On-Time In-Full (OTIF) delivery metrics for both suppliers and customer fulfillment.",
      "Track working capital velocity, inventory turnover ratio, and fulfillment cycle days.",
      "Inspect tamper-proof audit trail of every database mutation with user email, timestamp, and IP address.",
    ],
    workflows: [
      {
        id: "ct-kpi-monitor",
        actionNumber: 1,
        title: "Monitor Real-Time SC Health, OTIF & Bottlenecks",
        shortTitle: "Monitor SC Health",
        actor: "VP of Supply Chain",
        permissionRequired: "analytics:read",
        triggerEvent: "Daily operations morning standup review",
        stepByStepInstructions: [
          "Navigate to 'Supply Chain Control Tower' (/sc-control-tower).",
          "Inspect Supplier OTIF Scorecard: Acme Components (100% On-Time, In-Full).",
          "Inspect Fulfillment Cycle Times: Order-to-Ship (1.8 Days), Order-to-Cash (32 Days).",
          "Review Working Capital Dashboard: Receivables vs Payables buffer.",
        ],
        systemValidations: [
          "Metrics calculated dynamically from live database transactions.",
        ],
        tablesAndLedgersMutated: ["kpi_snapshots table"],
        outputDocument: "Daily Supply Chain Health Dashboard",
        simulation: {
          scenarioDescription: "Inspecting live OTIF metrics and fulfillment cycle times across the 19 modules.",
          initialState: "Live Operations Telemetry",
          buttonLabel: "Simulate Pull Live SC Telemetry",
          successState: "Telemetry Synced: 100% OTIF",
          executionLog: [
            "Calculating Supplier Inbound OTIF: 100% On-Time ✓",
            "Calculating Customer Fulfillment OTIF: 100% In-Full ✓",
            "Working capital receivables outstanding: ₹7,08,000 ✓",
            "Zero operational chokepoints detected across all 19 modules ✓",
          ],
          databaseEffect: "kpi_snapshots row logged.",
        },
      },
      {
        id: "ct-audit-verify",
        actionNumber: 2,
        title: "Inspect Cryptographic Write-Once Audit Trail",
        shortTitle: "Verify Audit Trail",
        actor: "Compliance Auditor",
        permissionRequired: "audit:read",
        triggerEvent: "Quarterly ISO / Statutory compliance verification",
        stepByStepInstructions: [
          "Navigate to 'Audit Trail' (/audit).",
          "Filter by Entity: 'PO-9002' or 'SO-5011'.",
          "System displays append-only tamper-proof log of every user action.",
          "Each row records: Timestamp, Actor Email, Action, Entity ID, and Before/After JSON payload.",
        ],
        systemValidations: [
          "Audit trail is write-once, append-only; even database superusers cannot modify or delete past logs.",
        ],
        tablesAndLedgersMutated: ["audit_log table"],
        outputDocument: "Audit Trail Compliance Certification",
        simulation: {
          scenarioDescription: "Auditing transaction chain from Demand to Payment verification.",
          initialState: "Full Enterprise Cycle Complete (19/19 Steps)",
          buttonLabel: "Simulate Generate Audit Verification",
          successState: "Audit Certified (Zero Discrepancies)",
          executionLog: [
            "Validating cryptographic audit hash chain across all 19 modules ✓",
            "Verifying immutable logs: PO-9002 -> GRN-3012 -> WO-1050 -> SO-5011 -> INV-401 ✓",
            "All transactions verified with user digital signatures ✓",
            "Complete enterprise lifecycle demonstration finished successfully! ✓",
          ],
          databaseEffect: "audit_log compliance check stamped.",
        },
      },
    ],
    upstreamConnections: [
      {
        moduleName: "All 18 Preceding Modules",
        route: "/",
        document: "Cross-System Event Stream",
        dataPassed: "Status transitions, timestamped transactions, and operational logs from every department.",
        relationship: "Central aggregated telemetry",
      },
    ],
    downstreamConnections: [
      {
        moduleName: "Executive Leadership & Board",
        route: "/",
        document: "Strategic KPI Reporting",
        dataPassed: "EBITDA, inventory turn velocity, customer fulfillment rates, and supplier reliability.",
        relationship: "Strategic business decisions",
      },
    ],
    businessControls: [
      "Audit trail records are write-once, append-only; even system administrators cannot modify or delete past logs.",
      "Anomalous multi-failure login attempts trigger automatic account lockouts and security alerts.",
    ],
  },
];

export const DEMO_CASE_STUDY = {
  title: "The Life of an Order: Product SKU-MOT-500 (Industrial Motor)",
  scenario:
    "Follow a complete customer transaction for 500 electric motors as it cascades chronologically through the 19 enterprise modules of Simple ERP.",
  stages: [
    {
      step: 1,
      module: "Business Entities (/po-invoice)",
      action: "Company registers entity 'Axon Industries Pvt Ltd' with GSTIN 27AAAAA9999A1Z5 and bank details.",
    },
    {
      step: 2,
      module: "Factories & Warehouses (/factory-warehouse)",
      action: "Operations commissions Pune Assembly Plant 1 and Central Warehouse with staging and quarantine bays.",
    },
    {
      step: 3,
      module: "Users & Security (/users)",
      action: "Security Admin onboards operators and scopes their access strictly to Pune Warehouse (WH-PUNE-01).",
    },
    {
      step: 4,
      module: "Parties & AVL (/parties)",
      action: "Qualifies supplier Acme Components on Approved Vendor List (AVL) and registers customer AutoCorp.",
    },
    {
      step: 5,
      module: "Products & BOM (/products)",
      action: "Engineering defines SKU-MOT-500 and locks multi-level BOM-MOT-V1 specifying Rotor, Stator, and Copper Wire.",
    },
    {
      step: 6,
      module: "Demand Forecasting (/forecasting)",
      action: "Tournament model runs on 24-month history; Holt-Winters crowned winner and consensus plan locked at 550 units.",
    },
    {
      step: 7,
      module: "MRP Planning (/mrp)",
      action: "Gross-to-net calculation explodes BOM, detects shortage of 5,000m copper wire, and releases PR-3042 & WO-1050.",
    },
    {
      step: 8,
      module: "Procurement & PO (/procurement)",
      action: "Lead buyer issues RFQ-901 to 3 AVL vendors, awards Acme at ₹25/m, and Plant Head authorizes PO-9002 via SMTP.",
    },
    {
      step: 9,
      module: "Inbound Logistics (/logistics)",
      action: "Acme dispatches lorry MH-12-AB-1234; gate security validates documents and issues Gate Pass GEP-108.",
    },
    {
      step: 10,
      module: "Dock GRN Receiving (/warehouse)",
      action: "Dock verifies 25 spools, generates GRN-3012 in quarantine status, and prints serialized 2D QR stickers.",
    },
    {
      step: 11,
      module: "Quality QC Station (/warehouse-qc)",
      action: "QC chemist tests 32 samples for diameter and conductivity; passes lot and signs Certificate of Analysis.",
    },
    {
      step: 12,
      module: "Directed WMS Putaway (/wms-bins)",
      action: "Forklift driver scans QR, system directs optimal lower rack Bin A-04-2, and stock ledger updates to available.",
    },
    {
      step: 13,
      module: "Manufacturing Execution (/production)",
      action: "Work Order WO-1050 issues copper wire with FIFO lot tracking, completes assembly, and outputs 500 Finished Goods Motors.",
    },
    {
      step: 14,
      module: "Sales Orders & Allocation (/orders)",
      action: "Customer AutoCorp orders 500 motors; credit limit verified; row-locked FIFO reserves stock with zero overselling.",
    },
    {
      step: 15,
      module: "Wave Picking & Packing (/wave-picking)",
      action: "Wave picking gathers motors via mobile scanner; digital scale verifies weight 420.5 kg in 25 cartons.",
    },
    {
      step: 16,
      module: "Outbound TMS & e-Way Bill (/shipping-engine)",
      action: "Generates mandatory 12-digit GST e-Way Bill #882910488219 and lorry dispatches with manifest handover.",
    },
    {
      step: 17,
      module: "Returns & RMA (/returns)",
      action: "Customer RMA-104 triaged for 2 transit-damaged units; 1 repaired to B-Grade, 1 scrapped, and credit note issued.",
    },
    {
      step: 18,
      module: "Finance & 3-Way Match (/finance)",
      action: "3-Way Match reconciles PO-9002, GRN-3012, and vendor invoice with 0.0% variance; tax invoice INV-401 posted to AR.",
    },
    {
      step: 19,
      module: "SC Control Tower & Audit (/sc-control-tower)",
      action: "Executive review confirms 100% OTIF fulfillment; tamper-proof cryptographic audit log records complete chain of custody.",
    },
  ],
};

export const PROCURE_TO_PAY_STAGES: P2PStage[] = [
  {
    stageNumber: 1,
    id: "p2p-pr",
    title: "1. Raise Purchase Requisition (PR)",
    shortTitle: "1. Raise PR",
    role: "Plant Maintenance / Stator Assembly Engineer",
    department: "Plant 1 - Motor Winding Line",
    route: "/procurement",
    inputDocument: "Bill of Materials (BOM) Deficit / Schedule",
    outputDocument: "PR-3042: Submitted (₹1,25,000)",
    description: "Shop floor identifies raw material shortfall for Q4 motor stator run. Engineer creates and submits formal purchase requisition.",
    formFields: [
      {
        name: "department",
        label: "Requesting Department",
        type: "select",
        defaultValue: "dept-assembly-1",
        options: [
          { label: "Plant 1 - Motor Stator Assembly", value: "dept-assembly-1" },
          { label: "Plant 1 - Mechanical Tooling", value: "dept-tooling" },
          { label: "Plant 2 - Substation Maintenance", value: "dept-maint-2" },
        ],
      },
      {
        name: "sku",
        label: "Requested Raw Material SKU",
        type: "select",
        defaultValue: "SKU-WIRE-01",
        options: [
          { label: "SKU-WIRE-01 — Copper Enamelled Winding Wire 0.85mm", value: "SKU-WIRE-01" },
          { label: "SKU-ROTOR-01 — Precision Rotor Core Laminations", value: "SKU-ROTOR-01" },
          { label: "SKU-BEARING-01 — Deep Groove Ball Bearing 6205", value: "SKU-BEARING-01" },
        ],
      },
      {
        name: "quantity",
        label: "Requisition Quantity",
        type: "number",
        defaultValue: 5000,
        suffix: "Meters",
        helperText: "Calculated from BOM: 12.5m wire × 400 motor stators",
      },
      {
        name: "estimatedRate",
        label: "Estimated Unit Rate (₹)",
        type: "number",
        defaultValue: 25.0,
        prefix: "₹",
        suffix: "per meter",
      },
      {
        name: "requiredDate",
        label: "Required On-Site Date",
        type: "date",
        defaultValue: "2026-10-28",
        helperText: "Must respect minimum supplier lead time of 10 days",
      },
      {
        name: "costCenter",
        label: "GL Cost Center & Budget",
        type: "select",
        defaultValue: "CC-402",
        options: [
          { label: "Cost Center 402 — Stator Winding (Available: ₹8.4L)", value: "CC-402" },
          { label: "Cost Center 405 — Plant Maintenance (Available: ₹3.1L)", value: "CC-405" },
        ],
      },
      {
        name: "justification",
        label: "Business Justification",
        type: "text",
        defaultValue: "Scheduled Q4 High-Torque Motor Stator Production Batch #44",
      },
    ],
    submitButtonText: "Submit Purchase Requisition (PR-3042)",
    successTitle: "Requisition PR-3042 Successfully Submitted",
    successSummary: "PR-3042 for 5,000m Copper Wire (₹1,25,000) logged in PostgreSQL with status 'submitted'. Budget verified against Cost Center 402.",
    ledgerEffect: "Budget reserve check passed; routed to Lead Buyer inbox for sourcing.",
    executionLogs: [
      "Verifying Department 402 quarterly OpEx budget allowance (Available: ₹8,40,000) ✓",
      "Validating SKU-WIRE-01 active engineering specification ✓",
      "Checking required-by date against supplier minimum lead time (14 days) ✓",
      "purchase_requisitions row PR-3042 created in status='submitted' ✓",
    ],
  },
  {
    stageNumber: 2,
    id: "p2p-rfq",
    title: "2. Float Multi-Vendor RFQ & Compare Quotes",
    shortTitle: "2. Float RFQ",
    role: "Lead Sourcing Buyer",
    department: "Central Procurement & Commercial",
    route: "/procurement",
    inputDocument: "Approved Requisition PR-3042",
    outputDocument: "RFQ-901 Published & Bids Ingested",
    description: "Buyer converts approved PR into competitive multi-vendor RFQ. 3 AVL suppliers submit bids; system evaluates landed price comparison matrix.",
    formFields: [
      {
        name: "sourcePr",
        label: "Linked Purchase Requisition",
        type: "readonly",
        defaultValue: "PR-3042 (5,000m Copper Wire — Est. ₹1,25,000)",
      },
      {
        name: "vendors",
        label: "Select Approved AVL Suppliers to Invite",
        type: "checkbox_group",
        defaultValue: ["Acme Copper & Components", "Beta Metal Corp", "Zenith Cables Ltd"],
        options: [
          { label: "Acme Copper & Components (Grade A, ISO-9001)", value: "Acme Copper & Components" },
          { label: "Beta Metal Corp (Grade B, ISO-9001)", value: "Beta Metal Corp" },
          { label: "Zenith Cables Ltd (Grade A, ISO-9001)", value: "Zenith Cables Ltd" },
        ],
      },
      {
        name: "incoterms",
        label: "Delivery Incoterms",
        type: "select",
        defaultValue: "DAP",
        options: [
          { label: "DAP — Delivered at Place (Pune Plant 1 Inward Dock)", value: "DAP" },
          { label: "FOB — Free on Board (Vendor Factory Gate)", value: "FOB" },
          { label: "CIF — Cost, Insurance & Freight", value: "CIF" },
        ],
      },
      {
        name: "deadlineDays",
        label: "Quotation Submission Window",
        type: "select",
        defaultValue: "5",
        options: [
          { label: "5 Business Days (Standard Sourcing)", value: "5" },
          { label: "3 Business Days (Expedited)", value: "3" },
        ],
      },
    ],
    submitButtonText: "Dispatch RFQ-901 & Generate Bid Comparison Matrix",
    successTitle: "RFQ-901 Dispatched & Landed Quotes Compared",
    successSummary: "Bids received: Acme Copper ₹25.00/m (10d), Beta Metal ₹27.00/m (14d), Zenith Cables ₹26.50/m (12d). Acme Copper selected as L1 winning bidder.",
    ledgerEffect: "sourcing_rfqs and sourcing_quotations tables populated; L1 recommendation logged.",
    executionLogs: [
      "Auditing AVL qualification certificates for 3 invited suppliers ✓",
      "Publishing RFQ-901 package with engineering drawing DWG-W44 ✓",
      "Ingesting vendor quotation 1: Acme Copper @ ₹25.00/m landed ✓",
      "Ingesting vendor quotation 2: Beta Metal @ ₹27.00/m landed ✓",
      "Ingesting vendor quotation 3: Zenith Cables @ ₹26.50/m landed ✓",
      "Quote matrix computed: Acme Copper awarded order as L1 lowest bidder ✓",
    ],
  },
  {
    stageNumber: 3,
    id: "p2p-po",
    title: "3. Generate Legally Binding Purchase Order (PO)",
    shortTitle: "3. Create PO",
    role: "Senior Purchasing Officer",
    department: "Procurement & Purchase Contracts",
    route: "/procurement",
    inputDocument: "Awarded RFQ-901 Quotation (Acme Copper)",
    outputDocument: "PO-9002: Pending Tier-2 Approval",
    description: "Buyer creates formal purchase order for Acme Copper with delivery dates, packaging specs, statutory GST tax calculation, and payment terms.",
    formFields: [
      {
        name: "vendor",
        label: "Selected Vendor",
        type: "readonly",
        defaultValue: "Acme Copper & Components Ltd (GSTIN: 27AAACA1234A1Z5)",
      },
      {
        name: "deliveryFacility",
        label: "Ship-To & Inward Receiving Facility",
        type: "select",
        defaultValue: "WH-CENTRAL-01",
        options: [
          { label: "Pune Plant 1 — Main Inward Dock (WH-CENTRAL-01)", value: "WH-CENTRAL-01" },
          { label: "Nagpur Plant 2 — Regional Hub", value: "WH-NAG-01" },
        ],
      },
      {
        name: "lineItem",
        label: "Line Item",
        type: "readonly",
        defaultValue: "SKU-WIRE-01 — Copper Winding Wire 0.85mm (5,000m @ ₹25.00/m)",
      },
      {
        name: "subtotal",
        label: "Order Subtotal (₹)",
        type: "readonly",
        defaultValue: "₹1,25,000.00",
      },
      {
        name: "taxCode",
        label: "Statutory Tax Code",
        type: "select",
        defaultValue: "GST18",
        options: [
          { label: "GST 18% (9% CGST ₹11,250 + 9% SGST ₹11,250 = ₹22,500)", value: "GST18" },
          { label: "IGST 18% (Inter-state Integrated GST = ₹22,500)", value: "IGST18" },
        ],
      },
      {
        name: "totalValue",
        label: "Total Legally Binding Order Value (₹)",
        type: "readonly",
        defaultValue: "₹1,47,500.00 (Incl. 18% GST)",
      },
      {
        name: "paymentTerms",
        label: "Commercial Payment Terms",
        type: "select",
        defaultValue: "NET30",
        options: [
          { label: "Net 30 Days (Bank Transfer upon 3-Way Match)", value: "NET30" },
          { label: "Net 45 Days", value: "NET45" },
        ],
      },
    ],
    submitButtonText: "Create Purchase Order (PO-9002)",
    successTitle: "Purchase Order PO-9002 Created",
    successSummary: "PO-9002 generated for ₹1,47,500. Encumbered ₹1,47,500 committed spend in General Ledger. Marked 'Pending Tier-2 Approval' (>₹50,000 threshold).",
    ledgerEffect: "purchase_orders & purchase_order_lines rows created; budget_encumbrances balance credited.",
    executionLogs: [
      "Verifying Acme Copper compliance & active bank payout profile ✓",
      "Calculating 18% GST: CGST ₹11,250 + SGST ₹11,250 = ₹22,500 ✓",
      "Writing purchase_orders record PO-9002 to PostgreSQL ✓",
      "Encumbering ₹1,47,500 in General Ledger procurement commitment balance ✓",
      "Flagging PO-9002 for mandatory Tier-2 authorization (>₹50,000 policy) ✓",
    ],
  },
  {
    stageNumber: 4,
    id: "p2p-approval",
    title: "4. Executive Tier-2 PO Authorization & Dispatch",
    shortTitle: "4. Tier-2 Approval",
    role: "Plant Head / VP Operations",
    department: "Executive Plant Operations",
    route: "/procurement",
    inputDocument: "Draft PO-9002 (₹1,47,500)",
    outputDocument: "Authorized PO-9002 PDF Dispatched to Supplier",
    description: "Plant Head verifies expenditure against CapEx/OpEx allocation, enters cryptographic approval signature, and automatically dispatches PO PDF via SMTP.",
    formFields: [
      {
        name: "orderSummary",
        label: "Reviewing Order",
        type: "readonly",
        defaultValue: "PO-9002 — Acme Copper & Components Ltd (Total: ₹1,47,500.00)",
      },
      {
        name: "budgetAudit",
        label: "Real-Time Department Budget Audit",
        type: "readonly",
        defaultValue: "Cost Center 402: Q4 Allocation ₹25,00,000 | Spent: ₹14,20,000 | Remaining: ₹10,80,000 (Sufficient)",
      },
      {
        name: "approverRole",
        label: "Approving Authority",
        type: "readonly",
        defaultValue: "Dr. Vikram Joshi — Plant Head (Permission: po:approve)",
      },
      {
        name: "signaturePin",
        label: "Digital Authorization PIN / Approval Seal",
        type: "text",
        defaultValue: "••••",
        helperText: "Cryptographic HMAC signature stamped onto official purchase contract",
      },
    ],
    submitButtonText: "Authorize & Dispatch PO to Supplier via SMTP",
    successTitle: "PO-9002 Authorized & Legally Issued",
    successSummary: "Digital signature stamped. Encrypted PDF generated with corporate seal. Dispatched via email worker to orders@acme-copper.com.",
    ledgerEffect: "purchase_orders status updated to 'issued'; dock receiving queue notified.",
    executionLogs: [
      "Verifying approver authority (`po:approve` for amounts > ₹50,000) ✓",
      "Applying cryptographic digital signature hash 88f2a... to PO-9002 ✓",
      "Rendering official PO PDF with corporate seal and HSN tax breakdown ✓",
      "purchase_orders status updated to 'issued'; approved_at timestamp stamped ✓",
      "Dispatched PO-9002 PDF to orders@acme-copper.com with delivery SLA token ✓",
    ],
  },
  {
    stageNumber: 5,
    id: "p2p-asn-gate",
    title: "5. Supplier ASN & Factory Gate Security Check-In",
    shortTitle: "5. ASN & Gate-In",
    role: "Inbound TMS Specialist & Security Officer",
    department: "Inbound Logistics & Security Gate",
    route: "/logistics",
    inputDocument: "Supplier ASN-ACM-8812 & Delivery Challan",
    outputDocument: "Gate Pass GP-1092 & Dock Appointment A-2",
    description: "Supplier dispatches consignment. Logistics ingests ASN notice; factory security verifies truck registration, weighs vehicle, and issues Gate Pass.",
    formFields: [
      {
        name: "asnNumber",
        label: "Supplier Advanced Shipping Notice (ASN)",
        type: "text",
        defaultValue: "ASN-ACM-8812",
        helperText: "EDI / Supplier Portal dispatch pre-alert",
      },
      {
        name: "carrier",
        label: "Logistics Carrier & Truck Number",
        type: "text",
        defaultValue: "Safexpress Logistics — MH-12-Q-4491",
      },
      {
        name: "dispatchQty",
        label: "Dispatched Quantity",
        type: "readonly",
        defaultValue: "5,000 Meters (10 Wooden Spools @ 500m)",
      },
      {
        name: "grossWeight",
        label: "Weighbridge Gross Weight (kg)",
        type: "number",
        defaultValue: 8450,
        suffix: "kg",
      },
      {
        name: "dockDoor",
        label: "Assigned Unloading Dock Bay",
        type: "select",
        defaultValue: "DOCK-A-02",
        options: [
          { label: "Dock Bay A-2 (Heavy Metals & Spools)", value: "DOCK-A-02" },
          { label: "Dock Bay A-1 (Electronics & Small Parts)", value: "DOCK-A-01" },
        ],
      },
    ],
    submitButtonText: "Issue Security Gate Entry Pass (GP-1092)",
    successTitle: "Gate Entry Pass GP-1092 Generated",
    successSummary: "Vehicle MH-12-Q-4491 logged at Gate 1. Gate Pass GP-1092 issued. Dock Bay A-2 reserved; warehouse inward receiving team notified.",
    ledgerEffect: "inbound_shipments & gate_passes records updated; inward SLA clock started.",
    executionLogs: [
      "Cross-referencing ASN-ACM-8812 against active Purchase Order PO-9002 ✓",
      "Validating carrier Safexpress GPS telematics geofence entry ✓",
      "Logging gross truck weight 8,450 kg at weighbridge #1 ✓",
      "Generating security Gate Pass GP-1092; assigning Dock Bay A-2 ✓",
    ],
  },
  {
    stageNumber: 6,
    id: "p2p-grn",
    title: "6. Dock Inward Unloading, GRN & 2D QR Labels",
    shortTitle: "6. Dock GRN & QR",
    role: "Warehouse Inward Receiving Specialist",
    department: "Central Receiving Dock A-2",
    route: "/warehouse",
    inputDocument: "Gate Pass GP-1092 & Delivery Challan DC-8819",
    outputDocument: "GRN-4401 & 10 GS1 QR Lot Stickers",
    description: "Warehouse operator unloads truck, physically counts spools, inspects for transit damage, issues GRN, and prints 2D QR lot traceability stickers.",
    formFields: [
      {
        name: "deliveryChallan",
        label: "Supplier Delivery Challan Number",
        type: "text",
        defaultValue: "DC-8819",
      },
      {
        name: "expectedQty",
        label: "Ordered PO Quantity",
        type: "readonly",
        defaultValue: "5,000 Meters (10 Spools)",
      },
      {
        name: "receivedQty",
        label: "Physically Verified Inward Quantity",
        type: "number",
        defaultValue: 5000,
        suffix: "Meters",
        helperText: "10 wooden spools counted and verified intact",
      },
      {
        name: "damageCount",
        label: "Transit Damage / Defect Count",
        type: "number",
        defaultValue: 0,
        suffix: "Meters",
      },
      {
        name: "stagingZone",
        label: "Initial Receiving Staging Zone",
        type: "select",
        defaultValue: "QUARANTINE_STAGE",
        options: [
          { label: "QUARANTINE_STAGE — Mandatory QC Hold (Default)", value: "QUARANTINE_STAGE" },
        ],
      },
    ],
    submitButtonText: "Create Goods Receipt Note (GRN-4401) & Print QR Stickers",
    successTitle: "GRN-4401 Created & 2D QR Labels Printed",
    successSummary: "Goods Receipt Note GRN-4401 issued for 5,000m copper wire. 10 GS1 QR stickers printed for Lot LOT-WIRE-202610-01. Stock held in Quarantine.",
    ledgerEffect: "goods_receipt_notes created; inventory_items placed in status='quarantine'; zero stock leak enforced.",
    executionLogs: [
      "Physical count verified: 10 Spools @ 500m = 5,000 Meters (Variance: 0.0%) ✓",
      "Zero transit damage detected; challan DC-8819 stamped and signed ✓",
      "Generating Goods Receipt Note GRN-4401 linked to PO-9002 ✓",
      "Printing 10 GS1 Datamatrix 2D QR stickers for Lot LOT-WIRE-202610-01 ✓",
      "Staging consignment in Dock Quarantine Zone A-2 pending QA testing ✓",
    ],
  },
  {
    stageNumber: 7,
    id: "p2p-qc",
    title: "7. Mandatory Quality Control (QC) & Lot Clearance",
    shortTitle: "7. QC Lot Testing",
    role: "Quality Assurance Inspector",
    department: "Quality Control Laboratory",
    route: "/warehouse-qc",
    inputDocument: "Quarantined GRN-4401 (Lot LOT-WIRE-202610-01)",
    outputDocument: "Certified QC Certificate QC-PASS-4401",
    description: "QA inspector takes AQL samples, tests copper diameter gauge and electrical breakdown voltage, and signs cryptographic release certificate.",
    formFields: [
      {
        name: "lotNumber",
        label: "Lot Under Inspection",
        type: "readonly",
        defaultValue: "LOT-WIRE-202610-01 (5,000m Copper Wire)",
      },
      {
        name: "aqlStandard",
        label: "Sampling Inspection Standard",
        type: "select",
        defaultValue: "AQL-LEVEL-2",
        options: [
          { label: "ISO 2859-1 / AQL Level II Normal (200m sampled across Spools #1 & #5)", value: "AQL-LEVEL-2" },
        ],
      },
      {
        name: "testDiameter",
        label: "Test 1: Wire Gauge / Diameter (Spec: 0.850 ± 0.020 mm)",
        type: "number",
        defaultValue: 0.852,
        suffix: "mm (PASS)",
      },
      {
        name: "testVoltage",
        label: "Test 2: Insulation Breakdown Voltage (Spec: > 1,500 V)",
        type: "number",
        defaultValue: 1850,
        suffix: "V (PASS)",
      },
      {
        name: "visualInspection",
        label: "Test 3: Surface Enamel Uniformity",
        type: "select",
        defaultValue: "PASS",
        options: [
          { label: "PASS — Smooth, uniform enamel, zero flaking or pinholes", value: "PASS" },
          { label: "FAIL — Flaking / exposed copper", value: "FAIL" },
        ],
      },
      {
        name: "disposition",
        label: "Final QA Disposition Decision",
        type: "select",
        defaultValue: "APPROVE_CLEAR",
        options: [
          { label: "Approve & Clear Lot to Active Inventory", value: "APPROVE_CLEAR" },
          { label: "Reject & Quarantine for Supplier Return (RTV)", value: "REJECT_RTV" },
        ],
      },
    ],
    submitButtonText: "Sign QC Release Certificate (QC-PASS-4401)",
    successTitle: "Quality Certificate Certified & Lot Cleared",
    successSummary: "All tests PASSED within engineering tolerances. Lot LOT-WIRE-202610-01 released from QUARANTINE to AVAILABLE_FOR_PUTAWAY.",
    ledgerEffect: "qc_inspections certified; lot state updated to cleared; WMS putaway engine alerted.",
    executionLogs: [
      "Conducting micrometric gauge test: Measured 0.852mm (Tolerance: 0.830 - 0.870mm) ✓",
      "Performing high-potential electrical breakdown test: 1,850V sustained for 60s ✓",
      "Visual optical inspection confirmed 100% enamel adhesion ✓",
      "Generating Certificate of Analysis COA-4401 signed by QA Inspector S. Sharma ✓",
      "Inventory state transition: QUARANTINE ➔ AVAILABLE_FOR_PUTAWAY ✓",
    ],
  },
  {
    stageNumber: 8,
    id: "p2p-putaway",
    title: "8. Directed WMS Bins & Optimal Rack Putaway",
    shortTitle: "8. WMS Putaway",
    role: "Forklift Driver & WMS Systems Planner",
    department: "Central Warehouse Operations",
    route: "/wms-bins",
    inputDocument: "Cleared Lot LOT-WIRE-202610-01 (GRN-4401)",
    outputDocument: "Stock Ledger Updated (Bin BIN-A-03-01: +5,000m)",
    description: "WMS algorithm computes optimal storage bin based on ABC velocity and heavy-material weight limits. Forklift operator scans bin to confirm putaway.",
    formFields: [
      {
        name: "itemToStore",
        label: "Item & Cleared Lot",
        type: "readonly",
        defaultValue: "SKU-WIRE-01 — Lot LOT-WIRE-202610-01 (5,000m)",
      },
      {
        name: "algorithmStrategy",
        label: "WMS Putaway Optimization Strategy",
        type: "select",
        defaultValue: "HEAVY_FAST",
        options: [
          { label: "Class A Heavy Velocity (Ground Level Rack, Close to Stator Line)", value: "HEAVY_FAST" },
          { label: "Upper Racking (Light Parts Only)", value: "UPPER_LIGHT" },
        ],
      },
      {
        name: "recommendedBin",
        label: "WMS Recommended Optimal Bin Location",
        type: "readonly",
        defaultValue: "Aisle A, Bay 03, Shelf 1 (BIN-A-03-01)",
        helperText: "Lower heavy-duty beam; weight capacity 2,500 kg (Load: 420 kg)",
      },
      {
        name: "barcodeScanConfirm",
        label: "Forklift Barcode Scan Confirmation",
        type: "text",
        defaultValue: "BIN-A-03-01",
        helperText: "Scan barcode label on rack beam to prevent misplacement",
      },
    ],
    submitButtonText: "Confirm Bin Scan & Post Double-Entry Putaway",
    successTitle: "Putaway Confirmed into Bin A-03-01",
    successSummary: "5,000m Copper Wire successfully placed into Bin BIN-A-03-01. Stock ledger balance updated to available. Materials ready for MES production orders.",
    ledgerEffect: "inventory_items location set to BIN-A-03-01; stock_ledger_entries double-entry move posted.",
    executionLogs: [
      "WMS algorithm evaluates weight distribution: 420 kg allocated to Shelf 1 ✓",
      "Scanning barcode BIN-A-03-01 via handheld warehouse terminal ✓",
      "Bin location confirmed with zero location discrepancy ✓",
      "Double-entry stock ledger updated: Debit Bin A-03-01 (+5,000m) / Credit Inward Staging ✓",
      "Available-to-Produce (ATP) quantity incremented; MES Work Orders unblocked ✓",
    ],
  },
  {
    stageNumber: 9,
    id: "p2p-3way-match",
    title: "9. Automated 3-Way Match & Bank Payment Disbursement",
    shortTitle: "9. 3-Way Match & Pay",
    role: "Accounts Payable Specialist & CFO",
    department: "Corporate Finance & Treasury",
    route: "/finance",
    inputDocument: "Vendor Bill BILL-ACM-9901 + PO-9002 + GRN-4401",
    outputDocument: "Payment Voucher PAY-8819 & General Ledger Journal",
    description: "Finance runs automated 3-Way Reconciliation matching PO, GRN, and Vendor Invoice with 0% variance, posts GL journal, and authorizes bank remittance.",
    formFields: [
      {
        name: "vendorBillNumber",
        label: "Supplier Commercial Tax Invoice",
        type: "text",
        defaultValue: "BILL-ACM-9901",
      },
      {
        name: "threeWayAudit",
        label: "3-Way Match Document Triad",
        type: "readonly",
        defaultValue: "PO-9002 (₹1,47,500) ⇄ GRN-4401 (5,000m Accepted) ⇄ BILL-ACM-9901 (₹1,47,500)",
      },
      {
        name: "varianceCheck",
        label: "Quantity & Price Variance Audit",
        type: "readonly",
        defaultValue: "Quantity Variance: 0.00% | Unit Rate Variance: 0.00% | Status: PERFECT MATCH",
      },
      {
        name: "glAccounts",
        label: "Double-Entry General Ledger Journal Posting",
        type: "readonly",
        defaultValue: "Debit Inventory (₹1,25,000) + Debit Input GST (₹22,500) | Credit Accounts Payable Acme Copper (₹1,47,500)",
      },
      {
        name: "paymentMethod",
        label: "Disbursement Remittance Method",
        type: "select",
        defaultValue: "RTGS",
        options: [
          { label: "RTGS Bank Transfer — HDFC Corporate A/C ****5678", value: "RTGS" },
          { label: "NEFT National Electronic Transfer", value: "NEFT" },
        ],
      },
    ],
    submitButtonText: "Execute 3-Way Match & Authorize Net-30 Payment Voucher",
    successTitle: "3-Way Match Passed & Payment Voucher PAY-8819 Authorized",
    successSummary: "Reconciliation verified with 0.00% variance. General Ledger journal posted. Bank disbursement PAY-8819 scheduled for Acme Copper. Complete Procure-to-Pay cycle closed!",
    ledgerEffect: "gl_entries journal posted; accounts_payable credited; payment_vouchers issued; purchase order closed.",
    executionLogs: [
      "Auditing PO-9002 vs GRN-4401: 5,000m ordered = 5,000m accepted (0% variance) ✓",
      "Auditing GRN-4401 vs BILL-ACM-9901: Rate ₹25.00/m matched to contract terms ✓",
      "Auditing statutory GST input tax credit: 18% (₹22,500) eligible for GSTR-2B claim ✓",
      "Posting double-entry journal: Debit Raw Inventory (₹1,25,000) / Credit AP (₹1,47,500) ✓",
      "Authorizing Payment Voucher PAY-8819 via HDFC Bank Corporate Remittance API ✓",
      "Procure-to-Pay (P2P) lifecycle successfully concluded with zero audit flags ✓",
    ],
  },
];

