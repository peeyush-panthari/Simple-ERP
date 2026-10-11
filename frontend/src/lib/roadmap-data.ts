export interface SchemaField {
  name: string;
  type: string;
  description: string;
  isKey?: boolean;
}

export interface SchemaTable {
  tableName: string;
  description: string;
  fields: SchemaField[];
}

export interface WorkflowStep {
  stepNumber: number;
  title: string;
  actor: string;
  action: string;
  output: string;
}

export interface RoadmapModuleData {
  id: string;
  title: string;
  subtitle: string;
  stage: "medium_term" | "long_term";
  targetRelease: string;
  department: string;
  iconName: string;
  executiveSummary: string;
  strategicProblem: string;
  solutionImpact: string;
  kpis: { metric: string; target: string; description: string }[];
  keyCapabilities: { title: string; description: string; tag: string }[];
  workflowSteps: WorkflowStep[];
  schemaTables: SchemaTable[];
  interactiveType:
    | "landed_cost_calc"
    | "subcontract_reconcile"
    | "bin_visualizer"
    | "drp_network"
    | "forecast_modeler"
    | "traceability_tree"
    | "container_stuffing"
    | "vendor_portal_asn";
}

export const ROADMAP_MODULES: Record<string, RoadmapModuleData> = {
  "landed-cost": {
    id: "landed-cost",
    title: "Landed Cost Tracking & Valuation",
    subtitle: "Inbound Cost Apportionment for True Inventory Valuation",
    stage: "medium_term",
    targetRelease: "Q3 2026",
    department: "Warehouse & Logistics",
    iconName: "Receipt",
    executiveSummary:
      "Accurately apportions indirect procurement and import expenditures—such as international freight, customs duties, insurance, port handling, and demurrage—directly to the inventory unit cost of received items (GRNs).",
    strategicProblem:
      "When companies only record the purchase invoice price on goods receipts, inventory assets are systematically undervalued, and product gross margins are inflated. Finance teams waste days doing manual month-end journal allocations.",
    solutionImpact:
      "Full GAAP/IFRS IAS 2 compliance, true moving average unit cost calculations, and precise product margin visibility down to the individual SKU level.",
    kpis: [
      { metric: "Gross Margin Accuracy", target: "+14.8%", description: "Eliminates surprise freight variance at period close" },
      { metric: "Reconciliation Labor", target: "-40 hrs/mo", description: "Automates multi-voucher landed cost apportionment" },
      { metric: "Audit Compliance", target: "100%", description: "Automated audit trail linking customs bills to inventory ledger" },
    ],
    keyCapabilities: [
      {
        title: "Multi-Voucher Allocation",
        description: "Aggregate shipping bills, customs documents, and port handling charges across multiple PO goods receipts in a single Landed Cost Voucher (LCV).",
        tag: "Inbound Logistics",
      },
      {
        title: "Dynamic Apportionment Rules",
        description: "Apportion charges flexibly by Item Value (ad valorem), Gross Weight (kg), Volume (CBM), or Quantity received.",
        tag: "Financial Control",
      },
      {
        title: "Automatic Moving Average Adjustment",
        description: "Recalculates current inventory Moving Average Cost (MAC) and generates valuation adjustment journals automatically.",
        tag: "Stock Ledger",
      },
      {
        title: "Multi-Currency Expense Ingestion",
        description: "Ingest freight bills in USD/EUR with customs exchange rates and post directly to local INR ledger.",
        tag: "Treasury",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Create Landed Cost Voucher", actor: "Logistics Specialist", action: "Selects one or more posted Goods Receipt Notes (GRNs) awaiting cost finalization.", output: "Draft LCV with line items" },
      { stepNumber: 2, title: "Record Expense Charges", actor: "Accounts Payable", action: "Enters invoices for Ocean Freight, Port Handling, Customs Duty, and Transit Insurance.", output: "Expense breakdown by vendor" },
      { stepNumber: 3, title: "Select Allocation Basis", actor: "Cost Accountant", action: "Assigns allocation rule (e.g. Customs by Value, Sea Freight by Volume/Weight).", output: "Item-level cost apportionment matrix" },
      { stepNumber: 4, title: "Post Valuation Adjustment", actor: "Finance Manager", action: "Approves voucher; system updates inventory unit cost and posts GL adjustment.", output: "Updated Moving Average Cost in Stock Ledger" },
    ],
    schemaTables: [
      {
        tableName: "landed_cost_vouchers",
        description: "Header entity representing a landed cost allocation event.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "voucher_no", type: "VARCHAR(64)", description: "Unique sequential voucher reference", isKey: true },
          { name: "status", type: "ENUM('draft', 'posted', 'void')", description: "Voucher lifecycle state" },
          { name: "posting_date", type: "DATE", description: "Effective financial posting date" },
          { name: "total_charges_base", type: "NUMERIC(14,2)", description: "Sum of all apportioned expenses in base currency" },
        ],
      },
      {
        tableName: "landed_cost_charges",
        description: "Individual expense lines (freight, duties, insurance) linked to service vendors.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "voucher_id", type: "UUID", description: "Foreign key to landed_cost_vouchers" },
          { name: "charge_type", type: "ENUM('freight', 'customs', 'insurance', 'handling', 'other')", description: "Category of expense" },
          { name: "apportion_by", type: "ENUM('value', 'weight', 'volume', 'quantity')", description: "Distribution method" },
          { name: "amount", type: "NUMERIC(14,2)", description: "Total expense amount" },
          { name: "vendor_party_id", type: "UUID", description: "Service provider (Carrier/Customs broker)" },
        ],
      },
      {
        tableName: "landed_cost_items",
        description: "Goods receipt line items receiving cost distribution and their revised unit cost.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "voucher_id", type: "UUID", description: "Foreign key to landed_cost_vouchers" },
          { name: "grn_line_id", type: "UUID", description: "Originating goods receipt item" },
          { name: "original_unit_cost", type: "NUMERIC(14,4)", description: "PO invoice purchase price" },
          { name: "apportioned_cost", type: "NUMERIC(14,4)", description: "Allocated indirect cost share" },
          { name: "effective_unit_cost", type: "NUMERIC(14,4)", description: "True landed unit cost" },
        ],
      },
    ],
    interactiveType: "landed_cost_calc",
  },

  subcontracting: {
    id: "subcontracting",
    title: "Subcontracting & Job-Work Management",
    subtitle: "Outsourced Manufacturing, Material Dispatch & Yield Reconciliation",
    stage: "medium_term",
    targetRelease: "Q3 2026",
    department: "Manufacturing & Operations",
    iconName: "Workflow",
    executiveSummary:
      "Tracks external processing and job-work operations (heat treatment, coating, precision machining, packaging). Manages raw material dispatch under statutory challans, monitors vendor WIP inventory, tracks scrap variance, and receives finished assemblies.",
    strategicProblem:
      "Raw materials dispatched to job-workers frequently go missing or suffer unaccounted scrap loss. Companies lack visibility into what materials are currently lying on supplier shop floors.",
    solutionImpact:
      "Complete inventory visibility at subcontractor locations, automated reconciliation of raw materials consumed versus assemblies received, and enforcement of scrap tolerance policies.",
    kpis: [
      { metric: "WIP Material Visibility", target: "100%", description: "Real-time stock balance across all external subcontractor locations" },
      { metric: "Scrap Loss Containment", target: "< 2.0%", description: "Instant alerts when actual vendor scrap exceeds BOM allowance" },
      { metric: "Challan Reconciliation Speed", target: "5x faster", description: "Automated statutory delivery challan matching" },
    ],
    keyCapabilities: [
      {
        title: "Subcontract Purchase Orders (SPO)",
        description: "Specify service operations, unit processing costs, and required BOM child parts to be supplied by company.",
        tag: "Procurement",
      },
      {
        title: "Statutory Delivery Challans",
        description: "Generate compliant Job-Work Challans (Form 55 / GST Section 143) documenting outbound raw material dispatches.",
        tag: "Compliance",
      },
      {
        title: "External Subcontractor WIP Warehouse",
        description: "Virtual warehouse ledger dedicated to each vendor showing on-hand material balances in their custody.",
        tag: "Inventory Ledger",
      },
      {
        title: "Scrap & Yield Reconciliation",
        description: "Auto-calculate theoretical consumption vs actual returned goods, flagging unauthorized material losses.",
        tag: "Quality & Costing",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Raise Subcontract PO", actor: "Production Planner", action: "Specifies target finished item, quantity, processing charge, and required raw material BOM.", output: "Subcontract Order (SPO-XXXX)" },
      { stepNumber: 2, title: "Material Dispatch Challan", actor: "Warehouse Dispatcher", action: "Transfers raw materials from Main Store to Vendor WIP Location with official Job-Work Challan.", output: "Delivery Challan & Inventory Transfer" },
      { stepNumber: 3, title: "Process & Return Assembly", actor: "Subcontractor / QA", action: "Vendor processes parts; receives finished goods at factory with QC inspection.", output: "Goods Receipt with QC Pass/Fail" },
      { stepNumber: 4, title: "Reconcile Yield & Process Billing", actor: "Accounts Payable", action: "Reconciles raw materials consumed vs returned scrap; approves service invoice for processing only.", output: "Job-Work Service Invoice Approved" },
    ],
    schemaTables: [
      {
        tableName: "subcontract_orders",
        description: "Orders governing external manufacturing service agreements.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "order_no", type: "VARCHAR(64)", description: "SPO Reference", isKey: true },
          { name: "vendor_party_id", type: "UUID", description: "Subcontractor / Job-worker" },
          { name: "service_item_id", type: "UUID", description: "Service operation or assembly SKU" },
          { name: "target_qty", type: "NUMERIC(12,2)", description: "Quantity of assemblies to produce" },
          { name: "service_rate", type: "NUMERIC(12,2)", description: "Processing fee per unit" },
        ],
      },
      {
        tableName: "subcontract_challans",
        description: "Material dispatch challans transferring raw materials to vendor custody.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "challan_no", type: "VARCHAR(64)", description: "Statutory challan identifier", isKey: true },
          { name: "order_id", type: "UUID", description: "Linked Subcontract Order" },
          { name: "dispatch_date", type: "DATE", description: "Shipment date" },
          { name: "expected_return_date", type: "DATE", description: "Due date under statutory time limits" },
        ],
      },
    ],
    interactiveType: "subcontract_reconcile",
  },

  "wms-bins": {
    id: "wms-bins",
    title: "Warehouse Bin Topology & Directed Putaway",
    subtitle: "3D Storage Hierarchy, ABC Velocity Profiling & Algorithmic Putaway",
    stage: "medium_term",
    targetRelease: "Q3 2026",
    department: "Warehouse & Logistics",
    iconName: "Layers",
    executiveSummary:
      "Upgrades flat warehouse inventory locations to multi-tiered physical storage topologies (Zone -> Aisle -> Rack -> Shelf -> Bin). Recommends optimal bin assignments based on item velocity (ABC), weight/cube limits, and shortest travel distance.",
    strategicProblem:
      "Workers waste hours searching for storage space, place heavy items on high racks risking safety, and store fast-moving items far from loading docks, drastically slowing fulfillment.",
    solutionImpact:
      "Maximizes volumetric warehouse utilization, slashes forklift travel times by up to 35%, and enforces strict weight and hazmat segregation rules.",
    kpis: [
      { metric: "Space Utilization", target: "+22%", description: "Dynamic utilization of cubic shelf capacity" },
      { metric: "Putaway Travel Time", target: "-35%", description: "Directed shortest-path routing for forklift operators" },
      { metric: "Storage Safety Adherence", target: "100%", description: "Automated weight threshold validation per rack tier" },
    ],
    keyCapabilities: [
      {
        title: "Hierarchical Topology Modeler",
        description: "Model zones (Bulk, Pick Face, Cold Store, Hazmat), aisles, vertical racks, and individual bin coordinates.",
        tag: "WMS Core",
      },
      {
        title: "ABC Velocity Zoning",
        description: "Places fast-moving SKUs (Class A) near shipping docks at ergonomic waist height; Class C placed in high-bay bulk.",
        tag: "Optimization",
      },
      {
        title: "Dynamic Cubic & Weight Checking",
        description: "Calculates available volume (CBM) and remaining weight capacity before suggesting bin locations.",
        tag: "Slotting Engine",
      },
      {
        title: "Barcode Bin Confirmation",
        description: "Scan bin location barcode to verify forklift driver put goods in the exact designated location.",
        tag: "Mobile Scanning",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "GRN Inspection Cleared", actor: "QC Inspector", action: "Item passes quality check and enters receiving staging area.", output: "Putaway Task Generated" },
      { stepNumber: 2, title: "Directed Putaway Calculation", actor: "WMS Engine", action: "Evaluates SKU velocity, current bin volume, weight limits, and assigns optimal Bin.", output: "Suggested Bin (e.g. A02-R04-S03-B01)" },
      { stepNumber: 3, title: "Forklift Transfer & Barcode Scan", actor: "Warehouse Operator", action: "Transports pallet to designated aisle and scans bin barcode to confirm placement.", output: "Location Verified" },
      { stepNumber: 4, title: "Stock Ledger Updated", actor: "System", action: "Item status transitions from Staging to Available at the specific bin coordinate.", output: "Real-time 3D Stock Record" },
    ],
    schemaTables: [
      {
        tableName: "warehouse_zones",
        description: "Major functional sectors within a warehouse facility.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "warehouse_id", type: "UUID", description: "Parent Warehouse" },
          { name: "zone_code", type: "VARCHAR(32)", description: "Zone Identifier (e.g. ZONE-RECEIVING, ZONE-BULK)" },
          { name: "zone_type", type: "ENUM('receiving', 'bulk', 'pick_face', 'quarantine', 'cold_storage')", description: "Functional category" },
        ],
      },
      {
        tableName: "storage_bins",
        description: "Granular addressable storage cells in racks.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "bin_code", type: "VARCHAR(64)", description: "Formatted coordinate (e.g. Z01-A03-R02-B04)", isKey: true },
          { name: "max_weight_kg", type: "NUMERIC(10,2)", description: "Structural weight rating" },
          { name: "max_volume_cbm", type: "NUMERIC(10,3)", description: "Cubic dimensions" },
          { name: "current_utilization_pct", type: "NUMERIC(5,2)", description: "Real-time fullness percentage" },
        ],
      },
    ],
    interactiveType: "bin_visualizer",
  },

  drp: {
    id: "drp",
    title: "Multi-Echelon DRP (Distribution Requirements Planning)",
    subtitle: "Multi-Tier Inventory Optimization & Inter-Facility Replenishment",
    stage: "medium_term",
    targetRelease: "Q4 2026",
    department: "Planning & Supply Chain",
    iconName: "Network",
    executiveSummary:
      "Synchronizes material demand and inventory replenishment across multi-tier enterprise networks (Central Plant -> Mother Hubs -> Regional DCs -> Local Depots). Coordinates planned transfer orders, transit lead times, and pooled safety stocks.",
    strategicProblem:
      "One regional warehouse suffers stockouts and lost customer orders while another facility sits on excessive slow-moving inventory, causing cash lockup and costly emergency truck dispatches.",
    solutionImpact:
      "Eliminates regional stockouts by time-phasing transfer orders, optimizes safety stock pooling, and slashes emergency transit costs.",
    kpis: [
      { metric: "Regional Stockouts", target: "-45%", description: "Proactive transfer before buffer penetration" },
      { metric: "Working Capital Reduction", target: "-16%", description: "Centralized safety stock pooling across network" },
      { metric: "Expedited Freight Costs", target: "-30%", description: "Eliminates unplanned express transfers" },
    ],
    keyCapabilities: [
      {
        title: "Multi-Tier Supply Tree Modeling",
        description: "Model parent-child replenishment nodes, transit lead times, and freight lane costs across the enterprise network.",
        tag: "SCM Network",
      },
      {
        title: "Time-Phased Planned Transfer Orders (PTO)",
        description: "Calculates future replenishment dates by factoring in transit durations, picking windows, and order lot sizes.",
        tag: "DRP Engine",
      },
      {
        title: "Safety Stock Pooling & Balancing",
        description: "Square-root rule safety stock calculation reducing total network inventory while maintaining 98%+ service levels.",
        tag: "Inventory Math",
      },
      {
        title: "Automated Transfer Order Release",
        description: "Converts planned replenishment recommendations into pick-and-pack stock transfers with a single click.",
        tag: "Execution",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Demand Signal Ingestion", actor: "DRP Engine", action: "Aggregates regional sales orders and demand forecasts across regional nodes.", output: "Net Regional Demand Schedule" },
      { stepNumber: 2, title: "Time-Phased Inventory Simulation", actor: "DRP Engine", action: "Projects future on-hand balances per node subtracting lead time and buffer.", output: "Projected Buffer Deficits" },
      { stepNumber: 3, title: "Planned Transfer Recommendation", actor: "Network Planner", action: "Reviews suggested inter-warehouse transfers (quantity, source, destination, dispatch date).", output: "Approved Transfer Plan" },
      { stepNumber: 4, title: "Dispatch & In-Transit Tracking", actor: "Logistics Team", action: "Source warehouse picks and ships goods; inventory moves to In-Transit ledger.", output: "Stock Received at Regional DC" },
    ],
    schemaTables: [
      {
        tableName: "distribution_lanes",
        description: "Transportation links between parent supply nodes and child distribution centers.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "source_wh_id", type: "UUID", description: "Supplying mother hub or plant" },
          { name: "destination_wh_id", type: "UUID", description: "Receiving regional distribution center" },
          { name: "transit_days", type: "INTEGER", description: "Standard transit lead time in days" },
          { name: "minimum_transfer_qty", type: "NUMERIC(10,2)", description: "Batch sizing constraint" },
        ],
      },
      {
        tableName: "planned_transfer_orders",
        description: "Time-phased transfer orders recommended by the DRP engine.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "sku_id", type: "UUID", description: "Item to replenish" },
          { name: "dispatch_date", type: "DATE", description: "Recommended departure date" },
          { name: "required_arrival_date", type: "DATE", description: "Date needed before stockout" },
          { name: "quantity", type: "NUMERIC(10,2)", description: "Transfer quantity" },
        ],
      },
    ],
    interactiveType: "drp_network",
  },

  forecasting: {
    id: "forecasting",
    title: "S&OP Demand Forecasting & Statistical Smoothing",
    subtitle: "Time-Series Models, Seasonal Decomposition & Collaborative Consensus",
    stage: "long_term",
    targetRelease: "Q1 2027",
    department: "Planning & Supply Chain",
    iconName: "LineChart",
    executiveSummary:
      "Enterprise Sales & Operations Planning (S&OP) demand engine utilizing time-series statistical smoothing (Holt-Winters, ARIMA, Weighted Moving Average) and collaborative consensus workflows between Sales, Marketing, and Operations.",
    strategicProblem:
      "Relying on gut-feel or unadjusted past-month sales causes severe bullwhip effects—leading to stockouts during promotional surges and millions of dollars in surplus stock thereafter.",
    solutionImpact:
      "Reduces Mean Absolute Percentage Error (MAPE) to under 12%, provides a single version of the truth across departments, and directly seeds the MRP material requirement runs.",
    kpis: [
      { metric: "Forecast Accuracy (MAPE)", target: "< 12%", description: "Best-fit model selection across SKU demand curves" },
      { metric: "Bullwhip Propagation", target: "-50%", description: "Smoothed demand variance across upstream suppliers" },
      { metric: "Obsolete Inventory Write-Offs", target: "-25%", description: "Prevents overproduction of declining product lifecycles" },
    ],
    keyCapabilities: [
      {
        title: "Automated Statistical Model Tournament",
        description: "Automatically competes Holt-Winters, ARIMA, and Exponential Smoothing against back-tested data to select the model with lowest error.",
        tag: "Analytics",
      },
      {
        title: "Seasonal & Promotional Adjustments",
        description: "Isolates baseline demand from recurring holiday seasonality and promotional uplift spikes.",
        tag: "S&OP",
      },
      {
        title: "Collaborative Consensus Workflow",
        description: "Allows Sales to submit customer overrides, Marketing to adjust for campaigns, and Operations to commit the locked consensus plan.",
        tag: "Governance",
      },
      {
        title: "Direct MRP Feed",
        description: "Seamlessly converts the locked consensus demand forecast into gross requirements in the MRP Planning module.",
        tag: "Integration",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Historical Sales Ingestion", actor: "System", action: "Aggregates past 24-36 months of shipment history, filtering out anomalous outliers.", output: "Cleaned Time-Series Data" },
      { stepNumber: 2, title: "Automated Model Tournament", actor: "Analytics Engine", action: "Runs multiple algorithms; identifies model with lowest Mean Absolute Percentage Error.", output: "Baseline Statistical Forecast" },
      { stepNumber: 3, title: "Consensus Review & Overrides", actor: "Sales & S&OP Team", action: "Applies market intelligence, promotional bumps, and customer pipeline overrides.", output: "Consensus Forecast Plan" },
      { stepNumber: 4, title: "MRP Plan Lock", actor: "Supply Chain Director", action: "Locks the monthly forecast and passes gross requirements to MRP for purchase & production orders.", output: "Production Schedule Seeded" },
    ],
    schemaTables: [
      {
        tableName: "demand_forecast_scenarios",
        description: "Forecast versions (e.g. Baseline Statistical, Sales Consensus, Executive Locked).",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "scenario_name", type: "VARCHAR(64)", description: "Scenario description", isKey: true },
          { name: "planning_horizon_months", type: "INTEGER", description: "Number of future periods forecasted" },
          { name: "status", type: "ENUM('draft', 'under_review', 'locked')", description: "Governance state" },
        ],
      },
      {
        tableName: "forecast_period_lines",
        description: "Time-bucketed SKU demand forecasts with baseline vs override adjustments.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "scenario_id", type: "UUID", description: "Parent scenario" },
          { name: "sku_id", type: "UUID", description: "Forecasted SKU" },
          { name: "period_date", type: "DATE", description: "Month/Bucket start date" },
          { name: "statistical_forecast_qty", type: "NUMERIC(12,2)", description: "Raw algorithmic prediction" },
          { name: "consensus_forecast_qty", type: "NUMERIC(12,2)", description: "Final overridden committed quantity" },
        ],
      },
    ],
    interactiveType: "forecast_modeler",
  },

  traceability: {
    id: "traceability",
    title: "Advanced Traceability & Genealogy (Recall Triage)",
    subtitle: "Bi-Directional Lot Trees, Component Genealogy & Instant Quarantining",
    stage: "long_term",
    targetRelease: "Q1 2027",
    department: "Manufacturing & Operations",
    iconName: "QrCode",
    executiveSummary:
      "End-to-end multi-tier lot and serial number genealogy. Maps raw material batch receipts to work order runs, machine stations, operator shifts, packaging lots, and customer shipment deliveries. Facilitates automated, instant recall isolation in minutes.",
    strategicProblem:
      "When a defect is discovered in the field, manufacturers spend days manually combing through paper logs. In panic, they recall entire months of production costing millions in collateral damage.",
    solutionImpact:
      "Pinpoint recall containment within 15 minutes, isolating only the exact serial/lot numbers affected by the defective raw material batch, saving customer trust and millions in recall losses.",
    kpis: [
      { metric: "Recall Containment Time", target: "< 15 mins", description: "Instant automated trace from raw lot to shipped customer orders" },
      { metric: "Recall Collateral Cost", target: "-80%", description: "Isolates exact sub-batches rather than blanket shutdowns" },
      { metric: "Audit Compliance", target: "100%", description: "Meets FDA 21 CFR Part 11, ISO 9001, and IATF 16949 standards" },
    ],
    keyCapabilities: [
      {
        title: "Forward Trace (Supplier -> Customer)",
        description: "Input a suspect raw material batch ID and instantly generate a complete list of every finished assembly and customer destination.",
        tag: "Recall Management",
      },
      {
        title: "Backward Trace (Customer -> Supplier)",
        description: "Input a customer RMA serial number to trace back to the exact work order, machine station, date/time, and vendor lot.",
        tag: "Root-Cause QA",
      },
      {
        title: "Instant Digital Quarantine Freeze",
        description: "Place a global digital hold on all unconsumed raw materials and unshipped finished goods matching the contaminated lineage.",
        tag: "Risk Prevention",
      },
      {
        title: "Customer Advisory Generator",
        description: "Auto-generates recall advisory notices with customer contacts, affected serial numbers, and return instructions.",
        tag: "Customer Success",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Incident Triggered", actor: "Quality Auditor", action: "Receives notification of contaminated supplier raw lot (e.g. chemical impurity).", output: "Recall Case Opened" },
      { stepNumber: 2, title: "Forward Genealogy Traversal", actor: "Genealogy Engine", action: "Traverses production ledger graph to identify every batch produced with that lot.", output: "Impacted Finished Goods & Shipments" },
      { stepNumber: 3, title: "Automated System Quarantine", actor: "Quality Manager", action: "Executes one-click freeze on all remaining warehouse inventory matching the lineage.", output: "Stock Locked from Dispatch" },
      { stepNumber: 4, title: "Customer Advisory Dispatch", actor: "Regulatory Officer", action: "Dispatches automated notification to affected customers with serial numbers.", output: "Customer Recall Notices Sent" },
    ],
    schemaTables: [
      {
        tableName: "lot_genealogy_edges",
        description: "Directed acyclic graph tracking raw material consumption into parent assemblies.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "parent_lot_id", type: "UUID", description: "Output lot (finished assembly or sub-assembly)" },
          { name: "child_lot_id", type: "UUID", description: "Consumed input component lot" },
          { name: "work_order_id", type: "UUID", description: "Production run where consumption occurred" },
          { name: "consumed_quantity", type: "NUMERIC(10,3)", description: "Quantity incorporated into parent lot" },
        ],
      },
      {
        tableName: "recall_events",
        description: "Formal recall containment cases and audit logs.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "case_no", type: "VARCHAR(64)", description: "Recall tracking code", isKey: true },
          { name: "root_cause_lot_id", type: "UUID", description: "Identified origin defective lot" },
          { name: "quarantine_status", type: "ENUM('active', 'contained', 'resolved')", description: "Status of containment" },
          { name: "affected_shipments_count", type: "INTEGER", description: "Total customer orders requiring notification" },
        ],
      },
    ],
    interactiveType: "traceability_tree",
  },

  "freight-tms": {
    id: "freight-tms",
    title: "Container & Freight Consolidation (3PL/Port TMS)",
    subtitle: "Multi-Modal Freight, 3D Container Stuffing & Port Demurrage Tracking",
    stage: "long_term",
    targetRelease: "Q2 2027",
    department: "Warehouse & Logistics",
    iconName: "Ship",
    executiveSummary:
      "Multi-modal transportation management system (TMS) specialized in container stuffing optimization (3D cubic packing), FCL/LCL consolidation, ocean/air tracking milestones, port drayage, and automated carrier freight bill audit.",
    strategicProblem:
      "Companies unknowingly ship 20-30% 'empty air' inside ocean containers, and pay thousands of dollars in avoidable port demurrage and detention fees due to manual milestone tracking.",
    solutionImpact:
      "Boosts container volume utilization above 88%, consolidates disparate LCL shipments into cost-effective FCL containers, and eliminates port detention fines.",
    kpis: [
      { metric: "Container Fill Rate", target: "+18%", description: "3D packing algorithm optimizing weight and volume" },
      { metric: "Freight Spend Savings", target: "-12.5%", description: "Consolidation of LCL into Full Container Load (FCL)" },
      { metric: "Port Demurrage Fines", target: "$0 / month", description: "Automated gate-in/gate-out detention milestone alerts" },
    ],
    keyCapabilities: [
      {
        title: "3D Container Stuffing Engine",
        description: "Visual 3D volumetric stacking optimization for 20ft, 40ft, and 40ft HC containers respecting carton orientations and axle weight.",
        tag: "Packing Tech",
      },
      {
        title: "FCL/LCL Freight Consolidation",
        description: "Pools purchase shipments across multiple vendors in the same origin port region into single consolidated marine containers.",
        tag: "Cost Reduction",
      },
      {
        title: "Port Milestone & Demurrage Timer",
        description: "Monitors customs release, vessel arrival, free-day countdowns, and triggers alerts before detention penalties accrue.",
        tag: "TMS Tracking",
      },
      {
        title: "Carrier Freight Audit",
        description: "Performs 3-way match between carrier contract tariff rates, billed surcharges (BAF, CAF, THC), and invoiced amounts.",
        tag: "Audit",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "Consolidation Planning", actor: "Logistics Coordinator", action: "Aggregates outbound sales orders or inbound PO shipments heading to the same corridor.", output: "Consolidated Shipment Manifest" },
      { stepNumber: 2, title: "3D Stuffing Optimization", actor: "Packing Engine", action: "Computes optimal carton orientation, center-of-gravity, and container fill percentage.", output: "3D Stacking Plan for Loading Crew" },
      { stepNumber: 3, title: "Vessel Booking & Tracking", actor: "Freight Forwarder", action: "Assigns container booking reference, tracking vessel voyage milestones in real-time.", output: "Live Container Location & ETA" },
      { stepNumber: 4, title: "Port Clearance & Drayage", actor: "Customs Agent", action: "Tracks port discharge and drayage gate-out before free-time expiration.", output: "Container Delivered without Demurrage" },
    ],
    schemaTables: [
      {
        tableName: "container_shipments",
        description: "FCL / Intermodal container consolidation units.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "container_number", type: "VARCHAR(32)", description: "ISO Container ID (e.g. MSCU-7482910)", isKey: true },
          { name: "container_type", type: "ENUM('20GP', '40GP', '40HC', '45HC')", description: "Standard container dimensions" },
          { name: "carrier_party_id", type: "UUID", description: "Shipping Line / 3PL Carrier" },
          { name: "utilization_cbm_pct", type: "NUMERIC(5,2)", description: "Volumetric space efficiency" },
        ],
      },
    ],
    interactiveType: "container_stuffing",
  },

  "vendor-portal": {
    id: "vendor-portal",
    title: "Vendor Self-Service Collaboration Portal",
    subtitle: "Supplier RFQ Bidding, PO Acknowledgment, Advance Shipping Notices & Invoicing",
    stage: "long_term",
    targetRelease: "Q2 2027",
    department: "Procurement & Sourcing",
    iconName: "Building",
    executiveSummary:
      "A dedicated, secure self-service portal empowering external suppliers to participate in RFQ bidding, confirm and acknowledge Purchase Orders, submit Advance Shipping Notices (ASNs) with pre-printed GS1 barcode labels, and check invoice payment statuses.",
    strategicProblem:
      "Procurement teams spend more than 30% of their workday answering supplier emails about PO status, payment timelines, and chasing missing shipping documents.",
    solutionImpact:
      "Dramatically reduces buyer administrative overhead, expedites warehouse receiving through supplier pre-labeled pallets, and gives suppliers transparency over their scorecards.",
    kpis: [
      { metric: "Supplier Email Overhead", target: "-65%", description: "Self-service tracking of POs, payments, and RFQs" },
      { metric: "Dock Receiving Speed", target: "3x faster", description: "Barcode scanning of supplier-generated Advance Shipping Notices" },
      { metric: "On-Time Quotation Turnaround", target: "+40%", description: "Online RFQ submission portal with built-in deadlines" },
    ],
    keyCapabilities: [
      {
        title: "Digital RFQ Bidding Room",
        description: "Vendors review specifications, download technical drawings, and input price breaks and lead times directly into comparative bid sheets.",
        tag: "Sourcing",
      },
      {
        title: "PO Confirmation & Milestone Acknowledgment",
        description: "Suppliers digitally accept purchase orders, commit to promised dispatch dates, and request line revisions online.",
        tag: "Purchasing",
      },
      {
        title: "Advance Shipping Notice (ASN) & Pallet Barcoding",
        description: "Suppliers create ASNs detailing batch numbers, expiry dates, and print standardized GS1-128 barcode labels prior to dispatch.",
        tag: "Logistics",
      },
      {
        title: "Self-Service Invoice & Payment Status",
        description: "Vendors view the 3-way matching status of their bills and projected bank payout dates without contacting accounts.",
        tag: "Finance Transparency",
      },
    ],
    workflowSteps: [
      { stepNumber: 1, title: "RFQ Invitation & Digital Bid", actor: "Vendor Sales Manager", action: "Logs into portal, reviews RFQ items, and submits competitive prices before deadline.", output: "Direct Bid Recorded in Sourcing Engine" },
      { stepNumber: 2, title: "Purchase Order Acceptance", actor: "Vendor Order Desk", action: "Accepts PO issued by company; confirms delivery milestone schedule.", output: "PO Status: Confirmed by Supplier" },
      { stepNumber: 3, title: "ASN Generation & Label Print", actor: "Vendor Shipping Team", action: "Creates Advance Shipping Notice with carton serials; prints GS1 barcode labels for boxes.", output: "ASN Created; Labels Applied" },
      { stepNumber: 4, title: "Dock Scanning & Auto 3-Way Match", actor: "Factory Warehouse", action: "Scans ASN barcodes at dock for 10-second receiving; system triggers invoice payment queue.", output: "Fast Dock Receipt & Scheduled Payout" },
    ],
    schemaTables: [
      {
        tableName: "vendor_portal_users",
        description: "Authorized external supplier credentials linked to approved party masters.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "vendor_party_id", type: "UUID", description: "Party master record" },
          { name: "email", type: "VARCHAR(255)", description: "Supplier login username", isKey: true },
          { name: "role", type: "ENUM('admin', 'order_manager', 'shipping_clerk', 'accountant')", description: "Portal user access tier" },
        ],
      },
      {
        tableName: "advance_shipping_notices",
        description: "Pre-arrival manifests submitted by suppliers prior to truck dispatch.",
        fields: [
          { name: "id", type: "UUID", description: "Primary Key", isKey: true },
          { name: "asn_number", type: "VARCHAR(64)", description: "Unique ASN identifier", isKey: true },
          { name: "po_id", type: "UUID", description: "Purchase Order reference" },
          { name: "carrier_name", type: "VARCHAR(128)", description: "Trucking company / Freight forwarder" },
          { name: "tracking_number", type: "VARCHAR(128)", description: "Carrier air waybill / LR number" },
          { name: "dispatch_date", type: "DATE", description: "Shipment date from supplier facility" },
        ],
      },
    ],
    interactiveType: "vendor_portal_asn",
  },
};
