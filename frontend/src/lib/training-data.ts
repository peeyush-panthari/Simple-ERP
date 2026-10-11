export interface WorkflowValidationDetail {
  category: "Pre-Condition" | "Business Logic" | "Data Integrity" | "Authorization";
  check: string;
  rule: string;
  errorCode?: string;
  onFailure: string;
}

export interface TrainingWorkflowStep {
  stepNumber: number;
  title: string;
  actor: string;
  actorRole: string;
  action: string;
  outputDoc: string;
  statusTransition?: string;
  interconnection: {
    upstreamModule?: string;
    upstreamEvent?: string;
    downstreamModule?: string;
    downstreamEvent?: string;
  };
  validations: WorkflowValidationDetail[];
}

export interface CrossModuleLink {
  targetModule: string;
  direction: "Inbound" | "Outbound";
  trigger: string;
  dataExchanged: string;
  ledgerEffect?: string;
}

export interface TrainingFaq {
  question: string;
  answer: string;
}

export interface TrainingIssue {
  issue: string;
  errorCode?: string;
  symptom: string;
  rootCause: string;
  stepByStepFix: string[];
  preventionTip: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export interface ModuleTrainingContent {
  id: string;
  title: string;
  subtitle: string;
  group: string;
  badge: string;
  iconName: string;
  summary: string;
  primaryUsers: string[];
  keyDocuments: string[];
  workflowSteps: TrainingWorkflowStep[];
  crossModuleInterconnections: CrossModuleLink[];
  trainingManual: {
    overview: string;
    sopWalkthrough: {
      step: string;
      uiPath: string;
      instructions: string;
      proTips?: string;
    }[];
    validationMatrix: {
      ruleName: string;
      scope: string;
      validationLogic: string;
      enforcementLevel: "Hard Block (422/409)" | "Warning Alert" | "Approval Escalation";
    }[];
    stateMachine: {
      fromState: string;
      toState: string;
      action: string;
      allowedRoles: string[];
      guardConditions: string;
    }[];
  };
  faqs: TrainingFaq[];
  troubleshooting: TrainingIssue[];
  quiz: QuizQuestion[];
}

export const TRAINING_MODULES: Record<string, ModuleTrainingContent> = {
  procurement: {
    id: "procurement",
    title: "Procurement & Sourcing",
    subtitle: "End-to-end buying lifecycle from requisition to vendor dispatch",
    group: "Procurement",
    badge: "Core Buying Flow",
    iconName: "ShoppingCart",
    summary:
      "Governs internal purchase requisitions (PR), multi-tier approval routing, vendor sourcing requests (RFQ), comparative bidding evaluation, purchase order (PO) generation, vendor acknowledgement, document compliance, and inbound dispatch tracking.",
    primaryUsers: ["Employees / Requesters", "Department Managers", "Procurement Officers", "Purchase Heads", "Vendors (Portal)"],
    keyDocuments: ["PR (Purchase Requisition)", "PRFQ (Sourcing Request)", "PO (Purchase Order)", "ASN / Dispatch Notice", "Vendor Proforma & CoA"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Raise Purchase Requisition",
        actor: "Requisitioner (Employee)",
        actorRole: "pr:write",
        action: "Selects items from existing product catalog or specifies non-standard free-text items. Specifies needed-by date, destination warehouse, department, and mandatory business justification.",
        outputDoc: "PR (Purchase Requisition in 'draft' or 'submitted')",
        statusTransition: "draft → submitted",
        interconnection: {
          upstreamModule: "Planning & SCM (MRP / DRP)",
          upstreamEvent: "Auto-generated from net material shortages or raised manually by employees",
          downstreamModule: "Manager Approval Routing",
          downstreamEvent: "Queues PR to employee's reporting manager if assigned",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Requester Active & Tenant Scope",
            rule: "Requester must be an active user in the tenant with assigned department.",
            onFailure: "HTTP 401/403: User account inactive or unauthenticated.",
          },
          {
            category: "Business Logic",
            check: "Needed-By Date Validity",
            rule: "Needed-by date must be today or in the future; past dates are rejected.",
            errorCode: "PR_INVALID_DATE",
            onFailure: "Field validation error: 'Needed-by date cannot be in the past.'",
          },
          {
            category: "Business Logic",
            check: "Line Quantities & Justification",
            rule: "Quantities must be strictly positive (> 0). Submission requires non-empty reason text.",
            errorCode: "PR_VALIDATION_FAILED",
            onFailure: "Submission blocked: 'A business reason is mandatory before submitting.'",
          },
          {
            category: "Data Integrity",
            check: "Destination Warehouse Validity",
            rule: "Deliver-to warehouse must exist and be active within the requester's permitted facility scope.",
            onFailure: "HTTP 422: Destination warehouse does not exist or is inactive.",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Manager Approval Routing",
        actor: "Direct Reporting Manager",
        actorRole: "pr:team_approve",
        action: "Reviews requisition details, cost estimate, and department budget. Can approve with optional comment or reject with mandatory rejection reason.",
        outputDoc: "PR with Manager Approval Record",
        statusTransition: "submitted → with_manager → with_purchase (or rejected)",
        interconnection: {
          upstreamModule: "Procurement / Employee PR",
          upstreamEvent: "PR submitted by direct subordinate",
          downstreamModule: "Purchase Department Review",
          downstreamEvent: "Moves to Central Purchase review queue once manager signs off",
        },
        validations: [
          {
            category: "Authorization",
            check: "Hierarchical Reports-To Guard",
            rule: "Only the user recorded in 'reports_to_user_id' can execute manager approval. Requesters cannot approve their own PR.",
            errorCode: "PR_SELF_APPROVAL_PROHIBITED",
            onFailure: "HTTP 403: 'You cannot approve your own purchase requisition.'",
          },
          {
            category: "Business Logic",
            check: "Mandatory Rejection Feedback",
            rule: "Rejecting a PR strictly requires a non-empty explanation so the requester knows what to correct.",
            errorCode: "PR_REASON_REQUIRED",
            onFailure: "Dialog block: 'Reason for rejection must be provided.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Purchase Department Review",
        actor: "Purchase Officer",
        actorRole: "pr:approve",
        action: "Purchase reviews technical specs, checks existing inventory balances across warehouses, and decides whether to create a direct PO or start competitive sourcing (RFQ).",
        outputDoc: "PR marked 'approved'",
        statusTransition: "with_purchase → approved",
        interconnection: {
          upstreamModule: "Manager Approval",
          upstreamEvent: "Manager sign-off completed (or bypassed if user has no manager)",
          downstreamModule: "Sourcing RFQ or Purchase Order",
          downstreamEvent: "Enables 'Create PO' or 'Start Sourcing' buttons",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Prior Step Completion",
            rule: "Purchase department cannot review a requisition before manager approval is complete.",
            errorCode: "INVALID_STATE_TRANSITION",
            onFailure: "HTTP 422: 'Requisition is still pending manager sign-off.'",
          },
          {
            category: "Authorization",
            check: "Central Buyer Authority",
            rule: "Requires 'pr:approve' permission. Standard employees or department managers cannot perform this step.",
            onFailure: "HTTP 403: Forbidden.",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Sourcing & Competitive Bidding (RFQ)",
        actor: "Sourcing Specialist / Buyer",
        actorRole: "sourcing:write",
        action: "Selects multiple approved vendors from the Supplier Directory, specifies quote-by deadline and terms. Automated emails send login-free quotation links.",
        outputDoc: "PRFQ (Purchase RFQ) with Vendor Quotation records",
        statusTransition: "open → quotations_received",
        interconnection: {
          upstreamModule: "Requisitions",
          upstreamEvent: "Approved PR lines converted into RFQ",
          downstreamModule: "Vendor Portal / Email Config",
          downstreamEvent: "Sends RFQ invitation email using 'purchase-rfq.issued' template",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Approved Vendor Status",
            rule: "Invited parties must have type='vendor' and status='active'. Blocked vendors are disallowed.",
            errorCode: "VENDOR_INACTIVE",
            onFailure: "UI warning / block: 'Vendor is currently blocked or inactive.'",
          },
          {
            category: "Data Integrity",
            check: "Product Association Guard",
            rule: "Free-text items must be converted to standard catalog products before RFQ award to ensure inventory traceability.",
            onFailure: "Award blocked: 'Free-text items must be mapped to products before ordering.'",
          },
        ],
      },
      {
        stepNumber: 5,
        title: "Quotation Comparison & Award",
        actor: "Sourcing Committee / Lead Buyer",
        actorRole: "sourcing:award",
        action: "Reviews landed quote comparisons side-by-side (base price, GST, freight, lead time). Lowest cost is auto-highlighted. Selecting non-lowest requires audit justification.",
        outputDoc: "Awarded RFQ Lines with Justification Logs",
        statusTransition: "quotations_received → awarded",
        interconnection: {
          upstreamModule: "Vendor Quotes",
          upstreamEvent: "Vendors submit quotations",
          downstreamModule: "Purchase Order Generation",
          downstreamEvent: "Automates creation of one PO per winning vendor",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Non-Lowest Award Justification",
            rule: "If an item is awarded to a vendor whose landed cost is higher than the lowest quote, a mandatory justification note must be entered.",
            errorCode: "AWARD_JUSTIFICATION_REQUIRED",
            onFailure: "HTTP 422: 'Award justification required when choosing a higher quote.'",
          },
          {
            category: "Business Logic",
            check: "Quote Expiry Check",
            rule: "Quotation validity date must not have expired. Expired quotes require explicit exception override.",
            onFailure: "Warning banner: 'Quotation expired on DD/MM/YYYY.'",
          },
        ],
      },
      {
        stepNumber: 6,
        title: "Purchase Order Issuance & Approval",
        actor: "Purchase Manager",
        actorRole: "po:write / po:approve",
        action: "Creates and issues the definitive purchase order. Multi-level value thresholds (L1: ₹50K, L2: ₹2.5L, L3: ₹10L) determine required approval tiers.",
        outputDoc: "Purchase Order ('issued' status) & PDF",
        statusTransition: "draft → submitted → approved → issued",
        interconnection: {
          upstreamModule: "Sourcing Award or Approved PR",
          upstreamEvent: "Awarded vendor lines populated into PO",
          downstreamModule: "Finance & Working Capital / Vendor Notification",
          downstreamEvent: "Committed spend ledger updated; PO PDF transmitted to vendor",
        },
        validations: [
          {
            category: "Business Logic",
            check: "PO Tier Approval Limits",
            rule: "Orders exceeding Tier thresholds require designated management approval; self-approval is strictly prevented.",
            errorCode: "PO_TIER_APPROVAL_REQUIRED",
            onFailure: "Issuance blocked: 'Requires Level 2 approval (exceeds ₹2,50,000)'.",
          },
          {
            category: "Pre-Condition",
            check: "Active Business Entity & Tax Registration",
            rule: "PO must be linked to a valid tenant Business Entity with GSTIN matching the delivery state destination.",
            onFailure: "HTTP 422: 'Invalid business entity or state tax jurisdiction mismatch.'",
          },
          {
            category: "Data Integrity",
            check: "Item Quantities & Price Precision",
            rule: "Quantities and unit prices must be strictly greater than 0; line GST rates must match approved HSN master.",
            onFailure: "Line error: 'Unit price must be positive.'",
          },
        ],
      },
      {
        stepNumber: 7,
        title: "Vendor Ack & Inbound Dispatch Notice (ASN)",
        actor: "Buyer / Vendor Portal User",
        actorRole: "po:vendor",
        action: "Records vendor's formal acknowledgement (or exceptions), attaches QA certificates/proforma invoice, and enters shipment dispatch details (transporter, vehicle, LR/AWB, e-Way Bill).",
        outputDoc: "PO Inbound Dispatch Record ('in_transit')",
        statusTransition: "PO status remains 'issued' or 'acknowledged'; dispatch is 'in_transit'",
        interconnection: {
          upstreamModule: "Purchase Order",
          upstreamEvent: "Vendor dispatches consignment from factory",
          downstreamModule: "Warehouse / GRN Receiving",
          downstreamEvent: "Receiving gate matches inbound truck with open dispatch record",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Over-Dispatch Prevention",
            rule: "Total dispatched quantity across shipments cannot exceed the open balance of the purchase order.",
            errorCode: "PO_OVER_DISPATCH_BREACH",
            onFailure: "HTTP 422: 'Cannot record dispatch: quantity exceeds remaining PO balance.'",
          },
          {
            category: "Data Integrity",
            check: "Statutory e-Way Bill Validation",
            rule: "Shipments with consignment value > ₹50,000 display an advisory warning if 12-digit e-Way bill number is missing.",
            onFailure: "Advisory banner: 'Consignment exceeds ₹50,000; statutory e-Way bill recommended.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Warehouse & GRN",
        direction: "Outbound",
        trigger: "PO Issued & Dispatch Recorded",
        dataExchanged: "PO Number, SKU, Ordered Quantity, Open Balance, Dispatch LR, Transporter",
        ledgerEffect: "Awaiting Receipt in Warehouse queue",
      },
      {
        targetModule: "Finance & Accounts Payable",
        direction: "Outbound",
        trigger: "PO Issued",
        dataExchanged: "Committed spend amount, Vendor payment terms, Currency, Delivery schedule",
        ledgerEffect: "Records Committed Spend against department budget",
      },
      {
        targetModule: "Planning & SCM",
        direction: "Inbound",
        trigger: "MRP Planned Orders / DRP Replenishment",
        dataExchanged: "Target SKU, Shortage Quantity, Warehouse ID, Recommended Order Date",
        ledgerEffect: "Converts Planned Order into Purchase Requisition",
      },
    ],
    trainingManual: {
      overview:
        "The Procurement module enforces strict governance over company purchasing. It balances user speed with financial control through tiered approvals, competitive bidding, vendor compliance auditing, and clean paperless document exchange.",
      sopWalkthrough: [
        {
          step: "1. Creating a Requisition",
          uiPath: "Procurement > Purchase Requisitions > '+ New requisition'",
          instructions:
            "Select the destination warehouse, delivery date, and add line items. Pick items from the product catalog or type a free-text item. Enter a business justification and click 'Submit' (or 'Save as draft' to finish later).",
          proTips: "If you don't have an assigned manager, your PR will skip manager review and route directly to Central Purchase.",
        },
        {
          step: "2. Manager Sign-Off",
          uiPath: "Procurement > Purchase Requisitions > Filter: 'With manager'",
          instructions:
            "Open pending requisitions raised by your direct team. Review line items and total estimated cost. Click 'Approve' to advance or 'Reject' with feedback.",
        },
        {
          step: "3. Conducting an RFQ Sourcing Event",
          uiPath: "Procurement > Sourcing (RFQ) > 'Start sourcing'",
          instructions:
            "Select PR lines to source. Choose 2 or more vendors. Set quotation deadline. The system emails RFQs with direct response links. As quotes arrive, input prices, GST, and freight.",
        },
        {
          step: "4. Comparing & Awarding Quotes",
          uiPath: "Procurement > Sourcing (RFQ) > Select Event > 'Compare & Award'",
          instructions:
            "The side-by-side comparison displays landed costs including GST and freight. The lowest price per SKU is pre-selected. If choosing a non-lowest quote, type a clear justification in the prompt.",
        },
        {
          step: "5. PO Creation & Issuance",
          uiPath: "Procurement > Purchase Orders > '+ New purchase order'",
          instructions:
            "Auto-generate from awarded RFQ or create directly from an approved PR. Select billing business entity, verify payment terms, and click 'Issue PO'.",
        },
        {
          step: "6. Recording Dispatch & Inbound Shipping",
          uiPath: "Procurement > Purchase Orders > PO Detail > 'Dispatch' tab",
          instructions:
            "Click 'Record dispatch'. Input vehicle number, transporter name, LR docket number, and upload vendor invoice / delivery challan.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Self-Approval Prohibition",
          scope: "Requisitions & POs",
          validationLogic: "session.user.id !== record.created_by_user_id on approval endpoints",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "PO Approval Value Tiers",
          scope: "PO Issuance",
          validationLogic: "Order total compared against configured L1, L2, L3 threshold settings",
          enforcementLevel: "Approval Escalation",
        },
        {
          ruleName: "Vendor Status Check",
          scope: "PO & RFQ Creation",
          validationLogic: "vendor.status === 'active' && vendor.blocked === false",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "Over-Dispatch Limit",
          scope: "Inbound Dispatch",
          validationLogic: "SUM(dispatched_qty) <= po_line.ordered_qty - po_line.cancelled_qty",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "draft", toState: "submitted", action: "Submit PR", allowedRoles: ["pr:write"], guardConditions: "Mandatory justification text" },
        { fromState: "submitted", toState: "with_manager", action: "Route to Manager", allowedRoles: ["System"], guardConditions: "Requester has reports_to_user_id" },
        { fromState: "with_manager", toState: "with_purchase", action: "Manager Approve", allowedRoles: ["pr:team_approve"], guardConditions: "Approver is assigned manager" },
        { fromState: "with_purchase", toState: "approved", action: "Purchase Approve", allowedRoles: ["pr:approve"], guardConditions: "Purchase reviewer check" },
        { fromState: "approved", toState: "po_raised", action: "Generate PO", allowedRoles: ["po:write"], guardConditions: "Valid vendor & entity selected" },
        { fromState: "issued", toState: "fulfilled", action: "Auto-close", allowedRoles: ["System"], guardConditions: "All lines received via GRN" },
      ],
    },
    faqs: [
      {
        question: "Why can't I see the 'Purchase orders' tab in Procurement?",
        answer: "Navigation tabs are permission-gated. If you only hold 'pr:read' or 'pr:write', you only see the 'Purchase requisitions' tab. Access to POs requires the 'po:read' permission.",
      },
      {
        question: "Can I order free-text items directly onto a Purchase Order?",
        answer: "No. Free-text items are meant for internal requisitioning before catalog setup. To generate a legal Purchase Order and track inventory, the item must be cataloged under 'Products & BOM' with an assigned SKU.",
      },
      {
        question: "What happens if a vendor quotes in USD or another foreign currency?",
        answer: "The RFQ and PO record the foreign currency and exchange rate. The landed cost and inventory valuation will calculate in base currency (INR) using the customs exchange rate on the transaction date.",
      },
      {
        question: "How do I cancel a PO that has already been partially delivered?",
        answer: "Use 'Short close' instead of Cancel. Short-closing freezes the remaining unfulfilled balance while preserving already-received goods receipts and invoice matching for past shipments.",
      },
    ],
    troubleshooting: [
      {
        issue: "PO Issuance Blocked: 'Requires Level 2 Approval'",
        errorCode: "PO_TIER_APPROVAL_REQUIRED",
        symptom: "Clicking 'Issue PO' gives an error message stating that the order exceeds your approval limit.",
        rootCause: "The total order value exceeds your role's approval threshold (e.g. ₹2,50,000 for L2).",
        stepByStepFix: [
          "Save the PO in 'draft' or 'submitted' status.",
          "Notify a designated Level 2 or Level 3 Purchase Approver.",
          "The authorized manager opens the PO and clicks 'Approve'.",
          "Once approved, click 'Issue PO' to release the order to the vendor.",
        ],
        preventionTip: "Review PO threshold matrix in Company Configuration before creating multi-lakh POs.",
      },
      {
        issue: "Vendor cannot be selected in PO create modal",
        errorCode: "PARTY_NOT_ELIGIBLE",
        symptom: "The vendor picker dropdown shows 'No matching active vendors' or the party name is greyed out.",
        rootCause: "The party is marked as 'customer' only, is in 'pending' activation, or has been temporarily 'blocked' by Finance.",
        stepByStepFix: [
          "Navigate to 'Parties' directory and locate the vendor.",
          "Check party type: must be 'vendor' or 'both'.",
          "Check status: if 'pending', complete bank account maker-checker approval.",
          "Check compliance: verify GSTIN and PAN details are active.",
        ],
        preventionTip: "Ensure vendor onboarding is fully approved prior to beginning sourcing events.",
      },
      {
        issue: "Manager approval button is missing or disabled on PR",
        symptom: "Requisition is stuck in 'With manager' but the manager cannot see the approve button.",
        rootCause: "The requester's 'Reports To' field was recently updated or point to another user account.",
        stepByStepFix: [
          "Check 'Users & roles' > Edit Requester > Verify 'Reports to' user.",
          "Only the exact user ID recorded as current manager can decide.",
          "Alternatively, a System Admin can reassign the requisition routing.",
        ],
        preventionTip: "Maintain accurate reporting hierarchies in Users & Roles when org changes occur.",
      },
    ],
    quiz: [
      {
        question: "What happens if a buyer selects a non-lowest quote in the RFQ comparison table?",
        options: [
          "The system automatically rejects the purchase order.",
          "The buyer is required to input a mandatory audit justification before awarding.",
          "The lower quotes are permanently deleted from system logs.",
          "An email alert is immediately sent to the vendor.",
        ],
        correctIndex: 1,
        explanation: "The ERP allows awarding higher quotes (e.g. due to better lead times or quality), but enforces compliance by requiring an audit justification.",
      },
      {
        question: "Who can approve a Purchase Requisition raised by employee Jane?",
        options: [
          "Jane herself, provided she has admin permissions.",
          "Any employee in the same department.",
          "Only Jane's designated reporting manager (Reports To) or Central Purchase (if no manager assigned).",
          "Any vendor on the Approved Vendor List.",
        ],
        correctIndex: 2,
        explanation: "Segregation of duties prohibits self-approval. Requisitions route strictly to the assigned reporting manager.",
      },
      {
        question: "How should a buyer handle a PO where 60 of 100 units were received and the vendor cannot deliver the rest?",
        options: [
          "Delete the PO record completely.",
          "Cancel the entire PO (reversing the received 60 units).",
          "Short-close the PO to close the remaining 40 units while retaining the received 60 units.",
          "Raise a credit note against the warehouse.",
        ],
        correctIndex: 2,
        explanation: "Short-closing is the standard ERP operation to terminate the remaining balance without affecting historical GRNs.",
      },
    ],
  },

  warehouse: {
    id: "warehouse",
    title: "Warehouse, GRN & QC",
    subtitle: "Inbound receiving, quality inspection, rejection tracking, and directed putaway",
    group: "Warehouse & Logistics",
    badge: "Material Inbound",
    iconName: "Warehouse",
    summary:
      "Oversees the physical receipt of goods against purchase orders, mandatory Quality Control (QC) inspection, acceptance/rejection disposition, barcode label printing, and putaway into designated storage bins.",
    primaryUsers: ["Gate Security", "Receiving Clerks", "QC Engineers", "Warehouse Supervisors"],
    keyDocuments: ["GRN (Goods Receipt Note)", "Inspection Report / QC Sheet", "Rejection Challan / RTV", "Putaway Task List", "Barcode / QR Stickers"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Gate Inward & Inbound Shipment Verification",
        actor: "Receiving Clerk",
        actorRole: "warehouse:read",
        action: "Inspects vehicle at inbound dock. Locates purchase order by typing PO number or scanning truck LR / e-Way bill docket. Verifies packing slip against PO open lines.",
        outputDoc: "Draft GRN Record",
        statusTransition: "new → draft",
        interconnection: {
          upstreamModule: "Procurement / Inbound Dispatch",
          upstreamEvent: "Truck arrives carrying PO consignment",
          downstreamModule: "GRN Creation",
          downstreamEvent: "Populates open line quantities into receipt screen",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "PO Receivable State Check",
            rule: "PO must be in 'issued', 'acknowledged', or 'partial' status. 'draft', 'cancelled', or 'fulfilled' POs cannot be received.",
            errorCode: "PO_NOT_RECEIVABLE",
            onFailure: "HTTP 422: 'PO is not receivable in its current status.'",
          },
          {
            category: "Pre-Condition",
            check: "Destination Warehouse Match",
            rule: "The receiving warehouse selected by the clerk must match the destination warehouse specified on the purchase order.",
            onFailure: "UI block: 'PO destination facility mismatch.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Record Goods Receipt (GRN)",
        actor: "Store Keeper",
        actorRole: "grn:write",
        action: "Counts delivered physical cartons. Enters received quantity, vendor invoice number, invoice date, delivery challan number, and batch/lot number if batch-tracked.",
        outputDoc: "GRN with Line Items ('under_qc')",
        statusTransition: "draft → under_qc",
        interconnection: {
          upstreamModule: "Purchase Order",
          upstreamEvent: "Physical goods unloaded at dock",
          downstreamModule: "Quality Control (QC Inspection)",
          downstreamEvent: "Generates pending QC inspection task",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Over-Delivery Tolerance Limit",
            rule: "Received quantity cannot exceed PO open balance + configured tolerance percentage (default: 5%).",
            errorCode: "PO_OVER_RECEIPT_TOLERANCE_BREACH",
            onFailure: "HTTP 422: 'Received quantity exceeds open balance plus tolerance limit.'",
          },
          {
            category: "Data Integrity",
            check: "Batch & Expiry Date Enforcement",
            rule: "For products flagged with 'batchTracked=true', a non-empty batch identifier is mandatory. If 'expiryTracked=true', expiry date must be in the future.",
            errorCode: "BATCH_INFO_REQUIRED",
            onFailure: "Form validation error: 'Batch number is required for this SKU.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Quality Control (QC) & Inspection Disposition",
        actor: "QC Inspector / Quality Engineer",
        actorRole: "warehouse:read (QC Disposition)",
        action: "Pulls physical test samples. Conducts visual and technical inspection against specs. Dispositions line into: Accepted Qty, Rejected Qty, and Quarantine Qty with mandatory Rejection Code.",
        outputDoc: "Completed Inspection Record",
        statusTransition: "under_qc → inspected",
        interconnection: {
          upstreamModule: "GRN Receiving",
          upstreamEvent: "Materials staged in QC quarantine bay",
          downstreamModule: "Inventory Stock Ledger & Returns",
          downstreamEvent: "Accepted units move to putaway; rejected units trigger Return to Vendor (RTV)",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Quantity Conservation Principle",
            rule: "Accepted Qty + Rejected Qty + Quarantine Qty must EXACTLY equal Received Qty on the line.",
            errorCode: "QC_QTY_MISMATCH",
            onFailure: "HTTP 422: 'Sum of accepted, rejected, and quarantine quantities must equal received quantity.'",
          },
          {
            category: "Business Logic",
            check: "Mandatory Rejection Code",
            rule: "Any rejected quantity (> 0) strictly requires selecting a standardized rejection reason code (e.g. DEF-DIM, DEF-SCRATCH, DEF-EXPIRED).",
            errorCode: "REJECTION_CODE_REQUIRED",
            onFailure: "Dialog block: 'Please specify a rejection reason code.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "GRN Posting & Inventory Ledger Update",
        actor: "Warehouse Manager",
        actorRole: "grn:post",
        action: "Posts final GRN. System creates serialized/batch inventory records in the stock balance and writes immutable journal entries to the stock ledger.",
        outputDoc: "Posted GRN & Stock Ledger Journal",
        statusTransition: "inspected → posted",
        interconnection: {
          upstreamModule: "QC Inspection",
          upstreamEvent: "QC Engineer signs off on disposition",
          downstreamModule: "Finance (3-Way Matching) & Putaway",
          downstreamEvent: "Unlocks line for 3-way matching in Accounts Payable; creates Putaway task",
        },
        validations: [
          {
            category: "Authorization",
            check: "Posting Authorization Guard",
            rule: "Requires 'grn:post' permission. Receiving clerks cannot post without supervisory authorization.",
            onFailure: "HTTP 403: Forbidden.",
          },
          {
            category: "Data Integrity",
            check: "Immutable Post State",
            rule: "Once posted, a GRN cannot be edited directly; corrections require an explicit cancellation reversal transaction.",
            errorCode: "GRN_ALREADY_POSTED",
            onFailure: "HTTP 409: 'Posted GRNs cannot be edited.'",
          },
        ],
      },
      {
        stepNumber: 5,
        title: "Barcode / QR Sticker Generation & Directed Putaway",
        actor: "Material Handler",
        actorRole: "warehouse:read",
        action: "Generates thermal adhesive QR stickers for each accepted unit/box. Scans QR code with handheld scanner and deposits pallet into designated warehouse bin location.",
        outputDoc: "Printed QR Barcodes & Closed Putaway Task",
        statusTransition: "putaway_pending → putaway_completed",
        interconnection: {
          upstreamModule: "GRN Posting",
          upstreamEvent: "Accepted inventory ledger rows generated",
          downstreamModule: "Manufacturing & Sales Picking",
          downstreamEvent: "Inventory marked as 'Available' in bin for production issue or order fulfillment",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Location Compatibility & Capacity",
            rule: "Putaway bin must be active and compatible with product category (e.g. Hazmat, Cold Chain, Finished Goods).",
            onFailure: "Scanner error: 'Destination bin not authorized for this SKU type.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Inventory Management",
        direction: "Outbound",
        trigger: "GRN Posted",
        dataExchanged: "SKU, Batch No, Accepted Qty, Bin Location, Moving Average Unit Cost",
        ledgerEffect: "Credit Stock Ledger: Increases On-Hand Balance",
      },
      {
        targetModule: "Finance & Accounts Payable",
        direction: "Outbound",
        trigger: "GRN Posted",
        dataExchanged: "GRN Number, Vendor Invoice No, Accepted Qty, PO Line Ref",
        ledgerEffect: "Creates Unbilled GRN accrual for 3-way match",
      },
      {
        targetModule: "Procurement",
        direction: "Outbound",
        trigger: "GRN Posted",
        dataExchanged: "PO Number, Line Received Qty",
        ledgerEffect: "Decrements PO open balance; sets PO to 'partial' or 'fulfilled'",
      },
    ],
    trainingManual: {
      overview:
        "The Warehouse & Receiving module acts as the physical gateway of the ERP. It guarantees that inventory counts, quality parameters, and vendor billing align perfectly before items enter available stock.",
      sopWalkthrough: [
        {
          step: "1. Finding the Inbound PO",
          uiPath: "GRN & QC > '+ Receive goods'",
          instructions:
            "Type or scan the PO number (e.g. 'PO-0012') or search by vendor name. The dialog loads open PO lines, remaining quantities, and expected delivery specs.",
        },
        {
          step: "2. Creating the Goods Receipt",
          uiPath: "GRN & QC > Receive Goods Dialog",
          instructions:
            "Enter Vendor Invoice Number, Challan Number, and Received Qty for each line. If the item is batch-tracked, enter the batch number printed on vendor packaging. Click 'Create GRN'.",
        },
        {
          step: "3. Conducting QC Disposition",
          uiPath: "GRN & QC > Locate GRN > Click 'QC / Inspect'",
          instructions:
            "Enter Accepted Qty and Rejected Qty. If items are rejected, pick the appropriate rejection code from the dropdown. Upload inspection test certificate if available. Click 'Submit inspection'.",
        },
        {
          step: "4. Printing Barcode Labels",
          uiPath: "GRN & QC > Select GRN > 'Print QR Stickers'",
          instructions:
            "Select thermal sticker format (e.g. 50x25mm). Click print to generate barcode stickers for pallet or carton tagging.",
        },
        {
          step: "5. Directed Putaway",
          uiPath: "WMS Directed Putaway / Handheld Scanner",
          instructions:
            "Scan the item QR code, scan the target rack bin location barcode, and confirm transfer to mark putaway complete.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Over-Receipt Tolerance Guard",
          scope: "GRN Creation",
          validationLogic: "received_qty <= po_open_qty * (1 + tolerance_pct)",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "QC Quantity Conservation",
          scope: "Inspection",
          validationLogic: "accepted_qty + rejected_qty + quarantine_qty === received_qty",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "Warehouse Access Scoping",
          scope: "Receiving & Posting",
          validationLogic: "actor.warehouse_scopes.includes(grn.warehouse_id) || actor.is_admin",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "draft", toState: "under_qc", action: "Submit for Inspection", allowedRoles: ["grn:write"], guardConditions: "Tolerance and batch check passed" },
        { fromState: "under_qc", toState: "inspected", action: "Record QC", allowedRoles: ["warehouse:read"], guardConditions: "Accepted + Rejected === Received" },
        { fromState: "inspected", toState: "posted", action: "Post GRN", allowedRoles: ["grn:post"], guardConditions: "Supervisor approval" },
        { fromState: "posted", toState: "cancelled", action: "Reverse Receipt", allowedRoles: ["grn:post"], guardConditions: "Inventory not yet consumed" },
      ],
    },
    faqs: [
      {
        question: "Can I receive more goods than the quantity stated on the Purchase Order?",
        answer: "Only within the pre-configured tolerance threshold (typically 5%). Any excess beyond 5% requires the buyer to amend the PO with an increased line quantity before the warehouse can receive it.",
      },
      {
        question: "What happens to goods that are rejected during QC inspection?",
        answer: "Rejected goods do NOT enter available inventory. They are placed in the physical and virtual 'quarantine' bucket. A Return to Vendor (RTV) debit note is initiated in the Returns module to send them back to the supplier.",
      },
      {
        question: "Can a posted GRN be edited if someone made a typo in the received quantity?",
        answer: "No. For audit integrity, posted GRNs are immutable. You must click 'Cancel / Reverse GRN' (which automatically unwinds stock ledger postings) and create a fresh GRN with the corrected count.",
      },
    ],
    troubleshooting: [
      {
        issue: "Cannot receive goods: 'Received quantity exceeds open balance plus tolerance'",
        errorCode: "PO_OVER_RECEIPT_TOLERANCE_BREACH",
        symptom: "System blocks GRN submission with an error banner when typing received count.",
        rootCause: "The quantity entered is higher than the remaining open quantity on the PO line plus the allowable over-delivery tolerance (e.g. 105 units for a 100-unit PO).",
        stepByStepFix: [
          "Check the physical count against the vendor delivery challan.",
          "If the delivery is genuine and accepted, contact the Purchasing agent.",
          "The buyer must open the PO and submit an 'Amend PO' request to increase line quantity.",
          "Once the PO revision is approved, refresh the GRN dialog and proceed.",
        ],
        preventionTip: "Ensure vendors receive and acknowledge firm PO quantities before shipping overages.",
      },
      {
        issue: "GRN Cancellation Blocked: 'Inventory item already consumed in production'",
        errorCode: "STOCK_CONSUMED_CANNOT_REVERSE",
        symptom: "Store manager attempts to cancel an incorrect GRN, but the operation fails with HTTP 409.",
        rootCause: "The received items have already been issued to an active production work order or allocated to a sales shipment.",
        stepByStepFix: [
          "Locate the serial/lot number in Inventory Item detail.",
          "Check movement history: identify which Production Run consumed the item.",
          "If the production run is still in draft/progress, remove the component from the run.",
          "Once stock is unconsumed, return to GRN and execute cancellation.",
        ],
        preventionTip: "Perform QC and verify receipt counts immediately upon dock arrival before releasing to production floors.",
      },
    ],
    quiz: [
      {
        question: "What is the mandatory condition when recording rejected items during QC inspection?",
        options: [
          "The items must be deleted from the database immediately.",
          "A valid rejection reason code must be assigned to the rejected quantity.",
          "The purchase order must be automatically cancelled.",
          "The vendor must be deleted from the master directory.",
        ],
        correctIndex: 1,
        explanation: "Rejection codes are mandatory so that supplier scorecard analytics can track quality defect trends.",
      },
      {
        question: "When are stock ledger journals written for inbound goods?",
        options: [
          "When the truck arrives at the security gate.",
          "When the draft GRN is saved.",
          "When the GRN is formally Posted after inspection sign-off.",
          "When the vendor invoice is paid by accounts.",
        ],
        correctIndex: 2,
        explanation: "Inventory assets are only officially debited to the stock ledger upon formal GRN posting.",
      },
      {
        question: "What happens if a user tries to edit an already posted GRN?",
        options: [
          "The edit is saved quietly without logs.",
          "The edit is blocked because posted GRNs are immutable; reversal is required.",
          "The system deletes all past invoices.",
          "The purchase order is automatically doubled.",
        ],
        correctIndex: 1,
        explanation: "Financial and audit regulations require that posted goods receipts remain strictly immutable.",
      },
    ],
  },

  inventory: {
    id: "inventory",
    title: "Inventory Management & WMS",
    subtitle: "Real-time stock ledger, multi-location balances, transfers, and warehouse bins",
    group: "Warehouse & Logistics",
    badge: "Stock Control",
    iconName: "Boxes",
    summary:
      "Maintains the definitive double-entry stock ledger, serialized and lot-tracked inventory items, storage bucket segregations (Available, Rejected in QC, Damaged, Expired), inter-warehouse transfers, cycle count adjustments, and mobile scanner integration.",
    primaryUsers: ["Warehouse Managers", "Inventory Controllers", "Material Handlers", "Internal Auditors"],
    keyDocuments: ["Stock Ledger Entry", "Stock Transfer Challan", "Inventory Adjustment Voucher", "Cycle Count Session Sheet", "Bin Topology Map"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Perpetual Stock Ledger Tracking",
        actor: "System Engine",
        actorRole: "inventory:read",
        action: "Continuously computes real-time stock balances across warehouses and sub-locations using double-entry journal postings (Debits/Credits).",
        outputDoc: "Stock Balance Summary & Item Ledger",
        statusTransition: "active",
        interconnection: {
          upstreamModule: "GRN / Production / Orders",
          upstreamEvent: "Inbound receipts, finished goods completions, or customer shipments",
          downstreamModule: "MRP Planning & Financial Valuation",
          downstreamEvent: "Provides accurate On-Hand, Allocated, and Available stock figures",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Strict Negative Inventory Prohibition",
            rule: "Stock balance for an SKU cannot drop below zero under any circumstances.",
            errorCode: "NEGATIVE_INVENTORY_PROHIBITED",
            onFailure: "HTTP 422: 'Transaction rejected: would result in negative inventory balance.'",
          },
          {
            category: "Data Integrity",
            check: "Optimistic Concurrency & Row Locking",
            rule: "Ledger posting queries acquire Postgres row-level locks on stock balance rows to prevent race conditions during concurrent picks.",
            onFailure: "HTTP 409: Concurrent balance update conflict; auto-retried with backoff.",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Inter-Warehouse Stock Transfer",
        actor: "Inventory Controller",
        actorRole: "inventory:transfer",
        action: "Initiates stock transfer between source and destination warehouses. Materials are deducted from source and placed into 'In Transit' until physically acknowledged at destination.",
        outputDoc: "Stock Transfer Order & Delivery Challan",
        statusTransition: "initiated → in_transit → completed",
        interconnection: {
          upstreamModule: "DRP Replenishment",
          upstreamEvent: "Spoke warehouse inventory falls below safety stock",
          downstreamModule: "Logistics TMS",
          downstreamEvent: "Generates transport request for inter-warehouse freight",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Available Stock Check at Source",
            rule: "Source warehouse must possess sufficient unallocated, available stock.",
            errorCode: "INSUFFICIENT_TRANSFER_STOCK",
            onFailure: "HTTP 422: 'Insufficient available stock at source warehouse.'",
          },
          {
            category: "Business Logic",
            check: "Distinct Source and Destination Facilities",
            rule: "Source warehouse ID cannot equal destination warehouse ID.",
            onFailure: "Validation error: 'Source and destination facilities must be different.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Status Change & Stock Bucket Segregation",
        actor: "Warehouse Quality Supervisor",
        actorRole: "inventory:adjust",
        action: "Moves physical stock between quality buckets: 'Available', 'Rejected in QC', 'Damaged', or 'Expired'. Items in non-available buckets cannot be allocated to sales or manufacturing.",
        outputDoc: "Stock Status Journal Voucher",
        statusTransition: "available ↔ quarantine / damaged / expired",
        interconnection: {
          upstreamModule: "Quality IPQC / Warehouse QC",
          upstreamEvent: "Defect discovered during handling or shelf-life expiry",
          downstreamModule: "Sales & Manufacturing Allocation",
          downstreamEvent: "Instantly locks inventory from being picked for orders",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Active Allocation Lock Check",
            rule: "Items currently reserved or allocated to an open sales order must have reservations released before moving to damaged/quarantine bucket.",
            errorCode: "ITEM_ALREADY_ALLOCATED",
            onFailure: "HTTP 422: 'Item is allocated to Order #SO-XXXX; release allocation before status change.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Cycle Counting & Physical Variance Reconciliation",
        actor: "Inventory Auditor",
        actorRole: "cycle_count:write",
        action: "Conducts scheduled or ABC cycle counts. Blind physical count is entered. System calculates positive or negative variances and posts adjusting stock ledger entries.",
        outputDoc: "Cycle Count Audit Reconciliation",
        statusTransition: "open → counted → reconciled",
        interconnection: {
          upstreamModule: "Scheduled Audit Plan",
          upstreamEvent: "Periodic audit cycle due date",
          downstreamModule: "Finance & Loss Accounts",
          downstreamEvent: "Posts inventory shrinkage or found stock journal to General Ledger",
        },
        validations: [
          {
            category: "Authorization",
            check: "Dual Custody & Maker-Checker for High Variances",
            rule: "Reconciliation adjustments exceeding ₹50,000 value require supervisor dual approval.",
            errorCode: "VARIANCE_APPROVAL_REQUIRED",
            onFailure: "Action blocked: 'Adjustment requires Finance Controller sign-off.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Sales & Order Fulfillment",
        direction: "Outbound",
        trigger: "Stock Balance Updated",
        dataExchanged: "Available to Promise (ATP) quantity per SKU and facility",
        ledgerEffect: "Supports order confirmation and stock allocation",
      },
      {
        targetModule: "Manufacturing & Production",
        direction: "Outbound",
        trigger: "Stock Issue to Work Order",
        dataExchanged: "Raw Material SKU, Lot ID, Quantity Consumed",
        ledgerEffect: "Credit Raw Material; Debit Work in Progress (WIP)",
      },
      {
        targetModule: "Finance & Cost Accounting",
        direction: "Outbound",
        trigger: "Stock Ledger Movement",
        dataExchanged: "Moving Average Cost, Total Valuation, Shrinkage Adjustments",
        ledgerEffect: "Inventory asset balance sheet valuation update",
      },
    ],
    trainingManual: {
      overview:
        "Simple ERP uses an immutable, transaction-logged stock ledger modeled after double-entry accounting. Every physical item movement, receipt, consumption, transfer, or scrap produces an auditable ledger record.",
      sopWalkthrough: [
        {
          step: "1. Viewing Live Inventory Balances",
          uiPath: "Inventory > Balances Table",
          instructions:
            "Filter by warehouse, SKU, or category. The table shows On Hand, Allocated (reserved for orders), and Available for Sale.",
        },
        {
          step: "2. Inspecting Individual Serial / Lot Items",
          uiPath: "Inventory > Click any SKU row > 'View Items'",
          instructions:
            "Examine item-level records: serial number, QR identifier, batch date, expiration date, and current storage bucket.",
        },
        {
          step: "3. Initiating an Inter-Warehouse Transfer",
          uiPath: "Inventory > 'Transfer stock'",
          instructions:
            "Select source warehouse, destination warehouse, SKU, and transfer quantity. Click 'Initiate Transfer'. The stock transitions to 'In Transit'.",
        },
        {
          step: "4. Executing Stock Adjustment / Bucket Change",
          uiPath: "Inventory > Select Item > 'Change bucket / status'",
          instructions:
            "Select target bucket (e.g. 'Damaged' or 'Rejected in QC'). Provide a mandatory reason code. Click 'Save adjustment'.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "No Negative Stock",
          scope: "All Movements",
          validationLogic: "current_balance - deduction >= 0",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "Allocation Conflict Guard",
          scope: "Transfers & Status Changes",
          validationLogic: "available_qty >= requested_qty",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "available", toState: "quarantine", action: "Flag Defect", allowedRoles: ["inventory:adjust"], guardConditions: "Item not currently reserved" },
        { fromState: "available", toState: "reserved", action: "Order Allocation", allowedRoles: ["order:allocate"], guardConditions: "Order in confirmed status" },
        { fromState: "reserved", toState: "consumed", action: "Ship / Produce", allowedRoles: ["order:ship", "inventory:produce"], guardConditions: "Pack / run completed" },
      ],
    },
    faqs: [
      {
        question: "What is the difference between 'On Hand' and 'Available' stock?",
        answer: "'On Hand' is total physical stock in the warehouse. 'Available' is On Hand minus stock that has already been allocated or soft-reserved for open customer orders or production runs.",
      },
      {
        question: "Can expired stock be sold if a customer requests it?",
        answer: "No. The system automatically locks expired lots into the 'Expired' bucket upon reaching their expiration date. They cannot be allocated to sales orders without formal QC re-certification.",
      },
    ],
    troubleshooting: [
      {
        issue: "Transfer failed: 'Transaction would result in negative inventory'",
        errorCode: "NEGATIVE_INVENTORY_PROHIBITED",
        symptom: "Stock transfer or component issue produces an error pop-up saying balance cannot be negative.",
        rootCause: "Another user allocated or shipped the remaining available units right before your transaction processed.",
        stepByStepFix: [
          "Refresh the inventory screen to inspect live balances.",
          "Check the 'Allocated' column to see which orders hold reservations.",
          "If urgent, coordinate with sales to reassign allocations or wait for incoming GRN.",
        ],
        preventionTip: "Use automated MRP planning to ensure safe buffer inventory is maintained.",
      },
    ],
    quiz: [
      {
        question: "What happens to stock placed in the 'Damaged' or 'Rejected in QC' bucket?",
        options: [
          "It is automatically marked for 50% discount sale.",
          "It is immediately deducted from Available stock and locked from sales allocation.",
          "It is shipped back to the vendor without paperwork.",
          "It continues to show as available to all sales reps.",
        ],
        correctIndex: 1,
        explanation: "Segregating stock into damaged/quarantine buckets protects order fulfillment from picking compromised goods.",
      },
    ],
  },

  manufacturing: {
    id: "manufacturing",
    title: "Manufacturing & Operations",
    subtitle: "Multi-level BOMs, work orders, component consumption, IPQC, and serialized FG",
    group: "Manufacturing",
    badge: "Shop Floor Execution",
    iconName: "Factory",
    summary:
      "Manages multi-level Bill of Materials (BOM) versioning, discrete production runs (work orders), shop-floor routing stages, raw material component backflushing/consumption, In-Process Quality Checks (IPQC), and finished goods conversion.",
    primaryUsers: ["Production Managers", "Line Supervisors", "Process Engineers", "IPQC Technicians"],
    keyDocuments: ["BOM (Bill of Materials)", "Production Run / Work Order", "Material Issue Slip", "IPQC Inspection Log", "Finished Good Serial Certificate"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "BOM Creation & Multi-Level Version Approval",
        actor: "Process Engineer",
        actorRole: "bom:write / bom:approve",
        action: "Defines finished good bill of materials: child raw materials, standard component ratios, expected scrap percentage, and routing stages. Moves from draft to approved status.",
        outputDoc: "Approved BOM Version",
        statusTransition: "draft → submitted → approved",
        interconnection: {
          upstreamModule: "Product Engineering",
          upstreamEvent: "New product SKU created or engineering change notice (ECN)",
          downstreamModule: "Production Planning & MRP",
          downstreamEvent: "Allows MRP to explode component requirements and allows work order creation",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Circular BOM Reference Prevention",
            rule: "An assembly cannot contain itself as a child component at any depth of the hierarchy.",
            errorCode: "BOM_CIRCULAR_DEPENDENCY",
            onFailure: "HTTP 422: 'Circular dependency detected: product cannot contain itself.'",
          },
          {
            category: "Pre-Condition",
            check: "Component SKU Active Status",
            rule: "All child components must exist as active products in the system catalog.",
            onFailure: "Validation error: 'Inactive or deprecated components cannot be added to a BOM.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Create Production Run (Work Order)",
        actor: "Production Planner",
        actorRole: "inventory:produce",
        action: "Selects finished good SKU, target build quantity, planned start date, factory facility, and warehouse. System automatically explodes the active BOM version.",
        outputDoc: "Production Run in 'Planned' status",
        statusTransition: "draft → planned",
        interconnection: {
          upstreamModule: "Sales Orders / MRP Planning",
          upstreamEvent: "Demand triggers need for finished goods manufacturing",
          downstreamModule: "Raw Material Availability Check",
          downstreamEvent: "Checks stock balances for all required BOM components",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Active Approved BOM Check",
            rule: "The target product must have at least one currently active, approved BOM version.",
            errorCode: "NO_ACTIVE_BOM",
            onFailure: "HTTP 422: 'Cannot create production run: no active approved BOM version found.'",
          },
          {
            category: "Business Logic",
            check: "Positive Production Quantity",
            rule: "Target build quantity must be strictly greater than 0.",
            onFailure: "Validation error: 'Target quantity must be greater than zero.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Component Issue & Material Consumption",
        actor: "Line Supervisor",
        actorRole: "inventory:produce",
        action: "Issues required raw materials from warehouse to the assembly line. Records exact lot/serial numbers consumed. Deducts materials from raw stock and debits Work in Progress (WIP).",
        outputDoc: "Production Consumption Log",
        statusTransition: "planned → in_progress",
        interconnection: {
          upstreamModule: "Inventory Stock Ledger",
          upstreamEvent: "Pulls available raw materials from warehouse",
          downstreamModule: "Routing & Assembly Stages",
          downstreamEvent: "Allows production line operators to proceed with assembly",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Component Availability Guard",
            rule: "Warehouse must have sufficient unreserved inventory for every BOM component.",
            errorCode: "INSUFFICIENT_COMPONENT_STOCK",
            onFailure: "HTTP 422: 'Insufficient raw materials available in warehouse to begin run.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Routing Stage Execution & IPQC Testing",
        actor: "IPQC Inspector",
        actorRole: "quality_ipqc:write",
        action: "Executes checklist at each production routing stage (e.g. SMT, Mechanical Assembly, Flashing, Burn-in). Tests parameters (voltage, tolerance, aesthetics) and signs off.",
        outputDoc: "Stage Sign-Off & Certificate of Analysis (CoA)",
        statusTransition: "stage: pending → passed",
        interconnection: {
          upstreamModule: "Assembly Line",
          upstreamEvent: "Physical units reach inspection milestone",
          downstreamModule: "Finished Goods Completion",
          downstreamEvent: "Mandatory gate before run can be closed",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Sequential Stage Gate Enforcement",
            rule: "Subsequent production stages cannot be completed until the preceding mandatory stage has passed inspection.",
            errorCode: "STAGE_SEQUENCE_VIOLATION",
            onFailure: "HTTP 422: 'Prior assembly stage must be passed before completing this stage.'",
          },
        ],
      },
      {
        stepNumber: 5,
        title: "Production Run Completion & FG Serial Generation",
        actor: "Production Head",
        actorRole: "inventory:produce",
        action: "Records actual good units produced and scrap count. System automatically mints serialized finished good records (FG-XXXX) and credits the Finished Goods stock ledger.",
        outputDoc: "Serialized FG Items & Completed Run Record",
        statusTransition: "in_progress → completed",
        interconnection: {
          upstreamModule: "Assembly & QC Sign-off",
          upstreamEvent: "Final testing completed",
          downstreamModule: "Finished Goods Warehouse & Sales Allocation",
          downstreamEvent: "Finished goods immediately become Available for order fulfillment",
        },
        validations: [
          {
            category: "Data Integrity",
            check: "Completion Yield Verification",
            rule: "Completed quantity + scrap quantity must be logically bounded by issued raw material limits.",
            onFailure: "HTTP 422: 'Completed yield exceeds component material allocation.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Warehouse & Finished Goods",
        direction: "Outbound",
        trigger: "Production Run Completed",
        dataExchanged: "FG SKU, Serial Numbers, Lot Number, Completed Quantity, Manufactured Date",
        ledgerEffect: "Credit FG Stock Ledger; Debit FG Inventory Value",
      },
      {
        targetModule: "Inventory (Raw Materials)",
        direction: "Outbound",
        trigger: "Components Issued",
        dataExchanged: "Raw Material SKUs, Lot Numbers, Quantities Consumed",
        ledgerEffect: "Credit Raw Material Inventory; Debit WIP",
      },
      {
        targetModule: "Batch Traceability",
        direction: "Outbound",
        trigger: "Serial Numbers Minted",
        dataExchanged: "Parent FG Serial mapped to Child Raw Material Lot IDs",
        ledgerEffect: "Creates bi-directional genealogy recall tree",
      },
    ],
    trainingManual: {
      overview:
        "The Manufacturing module bridges engineering specifications with shop-floor execution. It enforces strict BOM revision control, material accountability, and multi-stage quality gates to ensure defect-free finished goods.",
      sopWalkthrough: [
        {
          step: "1. Defining a Bill of Materials (BOM)",
          uiPath: "Products & BOM > Select Product > 'BOM' Tab > 'Draft new version'",
          instructions:
            "Add child components, quantities per unit, and scrap allowances. Submit the version for engineering approval.",
        },
        {
          step: "2. Creating a Work Order",
          uiPath: "Production & Runs > '+ New production run'",
          instructions:
            "Select target SKU, warehouse, and batch quantity. The system automatically selects the approved BOM version and validates component availability.",
        },
        {
          step: "3. Issuing Components & Starting Run",
          uiPath: "Production & Runs > Run Detail > 'Components' Tab",
          instructions:
            "Confirm component issue from the warehouse. Click 'Start run' to move into assembly.",
        },
        {
          step: "4. Completing Stages & IPQC",
          uiPath: "Production & Runs > Run Detail > 'Stages' Tab",
          instructions:
            "As batches progress through assembly, check off stage tasks and upload IPQC test readings.",
        },
        {
          step: "5. Completing the Run",
          uiPath: "Production & Runs > Run Detail > 'Complete run'",
          instructions:
            "Enter final good units produced and scrap count. System generates unique serial numbers for each finished unit.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "No Circular BOMs",
          scope: "BOM Configuration",
          validationLogic: "Depth-first search verification of parent-child SKU relations",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "Raw Material Sufficiency",
          scope: "Work Order Start",
          validationLogic: "warehouse_stock >= bom_qty * run_target_qty",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "draft", toState: "planned", action: "Plan Run", allowedRoles: ["inventory:produce"], guardConditions: "BOM approved" },
        { fromState: "planned", toState: "in_progress", action: "Start Assembly", allowedRoles: ["inventory:produce"], guardConditions: "Materials issued" },
        { fromState: "in_progress", toState: "completed", action: "Complete", allowedRoles: ["inventory:produce"], guardConditions: "All mandatory stages passed" },
      ],
    },
    faqs: [
      {
        question: "Can I edit a BOM while a production run is currently using it?",
        answer: "No. Approved BOM versions are locked. If you need to make design changes, create a new draft BOM revision (e.g. v2). Existing runs continue on v1 while future runs use v2.",
      },
    ],
    troubleshooting: [
      {
        issue: "Cannot start production run: 'Insufficient component stock'",
        errorCode: "INSUFFICIENT_COMPONENT_STOCK",
        symptom: "Clicking 'Start run' displays a table highlighting one or more components in red.",
        rootCause: "The warehouse does not have enough unallocated stock of one or more BOM raw materials.",
        stepByStepFix: [
          "Check the shortage table to identify the missing SKUs and quantities.",
          "Check if incoming purchase orders (POs) or GRNs are currently under inspection.",
          "If materials have not arrived, use MRP to generate an urgent purchase requisition.",
        ],
        preventionTip: "Run MRP lead-time reports before scheduling high-volume production batches.",
      },
    ],
    quiz: [
      {
        question: "What happens when a production run is officially Completed in Simple ERP?",
        options: [
          "All workers are automatically clocked out.",
          "Raw materials are credited back to the supplier.",
          "Serialized finished goods are generated and added to available finished goods inventory.",
          "A customer sales invoice is generated immediately.",
        ],
        correctIndex: 2,
        explanation: "Run completion converts consumed materials into serialized finished goods ready for customer shipping.",
      },
    ],
  },

  orders: {
    id: "orders",
    title: "Sales & Order Fulfillment",
    subtitle: "Customer master, credit limits, stock allocation, wave picking, and shipping",
    group: "Sales & Orders",
    badge: "Revenue Flow",
    iconName: "ClipboardList",
    summary:
      "Oversees customer sales orders, credit limit validation, automated FIFO/FEFO inventory allocation, wave/batch picking, box packing, shipping rate engine/AWB generation, and customer invoice generation.",
    primaryUsers: ["Sales Representatives", "Credit Controllers", "Fulfillment Specialists", "Shipping Clerks"],
    keyDocuments: ["Sales Order (SO)", "Pick List / Wave Batch", "Packing Slip", "Carrier Shipping Label / AWB", "Customer Tax Invoice"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Sales Order Entry & Credit Check",
        actor: "Sales Representative",
        actorRole: "order:write",
        action: "Inputs customer, line items, prices, and delivery terms. System checks customer status, outstanding overdue receivables, and credit limit balance.",
        outputDoc: "Sales Order in 'draft' or 'confirmed'",
        statusTransition: "draft → confirmed",
        interconnection: {
          upstreamModule: "Customer B2B Portal / CRM",
          upstreamEvent: "Customer places purchase order or contract",
          downstreamModule: "Inventory Allocation Engine",
          downstreamEvent: "Queues order for stock reservation",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Customer Status & Block Check",
            rule: "Party must be type='customer' or 'both', status='active', and not blocked.",
            errorCode: "CUSTOMER_BLOCKED",
            onFailure: "HTTP 422: 'Customer is currently blocked or inactive.'",
          },
          {
            category: "Business Logic",
            check: "Credit Limit & Exposure Verification",
            rule: "Total order value + current unpaid AR balance cannot exceed the customer's approved credit limit.",
            errorCode: "CREDIT_LIMIT_EXCEEDED",
            onFailure: "Confirmation blocked: 'Order exceeds customer credit limit by ₹XX,XXX.'",
          },
          {
            category: "Data Integrity",
            check: "Mandatory Shipping Address & GSTIN",
            rule: "A valid shipping address with pincode and GST state code is required for proper statutory tax calculation.",
            onFailure: "Validation error: 'Valid shipping address required.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Inventory Allocation & Stock Reservation",
        actor: "Order Allocation Engine",
        actorRole: "order:allocate",
        action: "Performs automated FIFO/FEFO (First-In, First-Out / First-Expired, First-Out) matching against available finished goods. Soft-locks serial/batch items to prevent duplicate sale.",
        outputDoc: "Allocated Order & Finished Good Allocation Records",
        statusTransition: "confirmed → allocated",
        interconnection: {
          upstreamModule: "Confirmed Sales Order",
          upstreamEvent: "Order passes credit check",
          downstreamModule: "Warehouse Wave Picking",
          downstreamEvent: "Generates pick tasks for warehouse operators",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Available Stock Sufficiency",
            rule: "Allocated quantity cannot exceed unreserved Available stock in the warehouse.",
            errorCode: "INSUFFICIENT_STOCK_TO_ALLOCATE",
            onFailure: "HTTP 422: 'Insufficient available finished goods to fulfill line.'",
          },
          {
            category: "Data Integrity",
            check: "Row-Level Stock Locking",
            rule: "Uses Postgres FOR UPDATE row locks to prevent concurrent race conditions across simultaneous sales orders.",
            onFailure: "HTTP 409: Concurrency conflict; automatically retried.",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Picking & Packing",
        actor: "Warehouse Picker & Packer",
        actorRole: "order:pack",
        action: "Picks physical units using handheld scanner. Packs into cartons/packages, records gross package weight and dimensions, and marks lines packed.",
        outputDoc: "Packing List & Package Dimensions Record",
        statusTransition: "allocated → packed",
        interconnection: {
          upstreamModule: "Inventory Allocation",
          upstreamEvent: "Items located in warehouse bins",
          downstreamModule: "Shipping Engine & Carrier Selection",
          downstreamEvent: "Sends weights and package counts to rate shopping engine",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Pack Quantity Integrity",
            rule: "Cannot pack more than the allocated quantity for any order line.",
            onFailure: "HTTP 422: 'Packed quantity cannot exceed allocated quantity.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Shipping Engine, AWB Generation & Dispatch",
        actor: "Logistics Specialist",
        actorRole: "order:ship",
        action: "Generates Air Waybill (AWB) or transport docket via integrated carriers (Delhivery, BlueDart, etc.). Prints thermal shipping label, confirms truck pickup, and marks order shipped.",
        outputDoc: "Carrier Shipping Label (AWB) & Dispatch Notice",
        statusTransition: "packed → shipped",
        interconnection: {
          upstreamModule: "Packed Order",
          upstreamEvent: "Cartons sealed with packing slips",
          downstreamModule: "Invoicing & Customer Tracking",
          downstreamEvent: "Transfers inventory out of stock ledger; triggers tax invoicing",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Payment / Settlement Guard",
            rule: "For Advance-payment customers, full payment must be recorded or an authorized override ('order:override-logistics') granted before shipping.",
            errorCode: "PAYMENT_NOT_SETTLED",
            onFailure: "HTTP 422: 'Order requires advance payment settlement before shipping.'",
          },
        ],
      },
      {
        stepNumber: 5,
        title: "Customer Invoicing & AR Posting",
        actor: "Billing Officer",
        actorRole: "order:invoice",
        action: "Generates statutory GST tax invoice. Renders official PDF, posts debit entry to Accounts Receivable (AR), and emails invoice to the customer.",
        outputDoc: "Customer Tax Invoice (INV-XXXX) & AR Ledger Entry",
        statusTransition: "shipped → invoiced → fulfilled",
        interconnection: {
          upstreamModule: "Order Shipping",
          upstreamEvent: "Proof of dispatch confirmed",
          downstreamModule: "Finance & Accounts Receivable",
          downstreamEvent: "Creates open receivable in customer aging report",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Single Invoice Enforcement",
            rule: "An order line cannot be invoiced more than once.",
            errorCode: "ORDER_ALREADY_INVOICED",
            onFailure: "HTTP 409: 'This order has already been invoiced.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Finance & AR",
        direction: "Outbound",
        trigger: "Order Invoiced",
        dataExchanged: "Invoice Number, Customer ID, Tax Breakdown (CGST/SGST/IGST), Total Payable",
        ledgerEffect: "Debit Accounts Receivable; Credit Sales Revenue",
      },
      {
        targetModule: "Inventory Stock Ledger",
        direction: "Outbound",
        trigger: "Order Shipped",
        dataExchanged: "SKU, Serial IDs, Shipped Quantity",
        ledgerEffect: "Credit Inventory Balance; Debit Cost of Goods Sold (COGS)",
      },
    ],
    trainingManual: {
      overview:
        "The Sales & Orders module drives the order-to-cash cycle. It coordinates credit risk checks, intelligent warehouse stock reservations, parcel shipping integrations, and statutory compliance.",
      sopWalkthrough: [
        {
          step: "1. Booking a Sales Order",
          uiPath: "Orders > '+ New order'",
          instructions:
            "Select customer, warehouse, and add line items. Check payment terms (e.g. Net 30 or Advance). Click 'Confirm order'.",
        },
        {
          step: "2. Allocating Inventory",
          uiPath: "Orders > Select Order > 'Allocate stock'",
          instructions:
            "Click 'Auto-allocate' to run FIFO/FEFO assignment or manually pick specific serialized units. Click 'Confirm allocation'.",
        },
        {
          step: "3. Packing Items",
          uiPath: "Orders > Select Order > 'Pack order'",
          instructions:
            "Confirm physical items are placed into cartons. Enter gross package weight in kg.",
        },
        {
          step: "4. Shipping & Generating AWB",
          uiPath: "Orders > Select Order > 'Ship order'",
          instructions:
            "Generate carrier shipping label or enter manual transporter LR number. Click 'Confirm shipment'.",
        },
        {
          step: "5. Issuing Customer Tax Invoice",
          uiPath: "Orders > Select Order > 'Generate invoice'",
          instructions:
            "Review GST tax summary, click 'Create invoice'. The PDF is rendered and emailed directly to customer accounts.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Credit Limit Enforcement",
          scope: "Order Confirmation",
          validationLogic: "unpaid_ar + order_value <= credit_limit",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "Advance Payment Guard",
          scope: "Shipping",
          validationLogic: "customer.terms !== 'advance' || order.paid_amount >= order.total",
          enforcementLevel: "Approval Escalation",
        },
      ],
      stateMachine: [
        { fromState: "draft", toState: "confirmed", action: "Confirm", allowedRoles: ["order:confirm"], guardConditions: "Credit check passed" },
        { fromState: "confirmed", toState: "allocated", action: "Allocate", allowedRoles: ["order:allocate"], guardConditions: "Stock available" },
        { fromState: "allocated", toState: "packed", action: "Pack", allowedRoles: ["order:pack"], guardConditions: "All items scanned" },
        { fromState: "packed", toState: "shipped", action: "Ship", allowedRoles: ["order:ship"], guardConditions: "Payment settled or credit approved" },
        { fromState: "shipped", toState: "invoiced", action: "Invoice", allowedRoles: ["order:invoice"], guardConditions: "Shipped status verified" },
      ],
    },
    faqs: [
      {
        question: "Can an order be partially shipped if some items are out of stock?",
        answer: "Yes. Simple ERP supports line-level packing and shipping. Lines with available inventory can be packed, shipped, and invoiced, while unfulfilled lines remain open.",
      },
    ],
    troubleshooting: [
      {
        issue: "Order Confirmation Blocked: 'Credit limit exceeded'",
        errorCode: "CREDIT_LIMIT_EXCEEDED",
        symptom: "Sales rep cannot confirm order; system throws a credit limit breach warning.",
        rootCause: "The customer has reached their approved credit limit due to outstanding unpaid invoices.",
        stepByStepFix: [
          "Check customer aging report in Finance to identify overdue unpaid bills.",
          "Request the customer remit payment for outstanding invoices.",
          "Alternatively, request Finance approve a temporary credit limit revision in Party Master.",
        ],
        preventionTip: "Review customer payment punctuality before booking high-value orders.",
      },
    ],
    quiz: [
      {
        question: "Why does the ERP perform row-level locking during inventory allocation?",
        options: [
          "To slow down server traffic.",
          "To prevent two concurrent orders from booking the exact same physical serial number.",
          "To delete old inventory records.",
          "To notify the customer by SMS.",
        ],
        correctIndex: 1,
        explanation: "Row locking ensures database concurrency integrity, completely eliminating double-allocation bugs.",
      },
    ],
  },

  finance: {
    id: "finance",
    title: "Finance & Accounts Payable/Receivable",
    subtitle: "3-Way matching, vendor invoices, customer billing, payments, and credit notes",
    group: "Finance",
    badge: "Financial Control",
    iconName: "Receipt",
    summary:
      "Oversees the core accounting integrity of Simple ERP: automated 3-Way Matching (PO vs. GRN vs. Vendor Invoice), Accounts Payable (AP), Accounts Receivable (AR), payment application, credit notes, aging reports, and landed cost reconciliation.",
    primaryUsers: ["Chief Financial Officer (CFO)", "Accounts Payable Specialists", "Accounts Receivable Officers", "Cost Accountants"],
    keyDocuments: ["AP Vendor Invoice", "AR Customer Invoice", "Payment Voucher", "Credit Note", "3-Way Match Verification Report"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Vendor Invoice Entry (AP Invoice)",
        actor: "Accounts Payable Clerk",
        actorRole: "invoice:post",
        action: "Enters supplier tax invoice details: invoice number, invoice date, due date, PO reference, and line items.",
        outputDoc: "Draft AP Invoice",
        statusTransition: "draft → submitted",
        interconnection: {
          upstreamModule: "Vendor / Procurement",
          upstreamEvent: "Vendor transmits tax invoice for delivered goods",
          downstreamModule: "3-Way Matching Engine",
          downstreamEvent: "Queues invoice for automated three-way verification",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Duplicate Vendor Invoice Detection",
            rule: "The combination of (vendor_id, invoice_number) must be globally unique within the tenant.",
            errorCode: "DUPLICATE_VENDOR_INVOICE",
            onFailure: "HTTP 409: 'An invoice with this number already exists for this vendor.'",
          },
          {
            category: "Pre-Condition",
            check: "Active Accounting Period Check",
            rule: "Invoice date must fall within an open financial accounting period.",
            errorCode: "ACCOUNTING_PERIOD_CLOSED",
            onFailure: "HTTP 422: 'Transaction date falls in a locked accounting period.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Automated 3-Way Matching Verification",
        actor: "3-Way Match Audit Engine",
        actorRole: "finance:read",
        action: "Verifies the 3-Way Match: 1) Purchase Order (contracted price & terms), 2) Goods Receipt Note (actual accepted physical count), 3) Vendor Invoice (billed rate & qty).",
        outputDoc: "Match Audit Status ('matched' or 'variance_exception')",
        statusTransition: "submitted → matched (or variance_flagged)",
        interconnection: {
          upstreamModule: "Warehouse (GRN) & Procurement (PO)",
          upstreamEvent: "Pulls accepted line quantities and contracted PO prices",
          downstreamModule: "Payment Approval",
          downstreamEvent: "Clears invoice for payment disbursement if match passes",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Quantity Match Guard",
            rule: "Billed invoice quantity cannot exceed the physically accepted quantity on the linked GRN.",
            errorCode: "MATCH_QTY_VARIANCE",
            onFailure: "Hold placed: 'Billed quantity (XX) exceeds accepted GRN quantity (YY).'",
          },
          {
            category: "Business Logic",
            check: "Price Tolerance Verification",
            rule: "Unit price on vendor invoice must match PO unit price within configured tolerance (default: 0.00%).",
            errorCode: "MATCH_PRICE_VARIANCE",
            onFailure: "Hold placed: 'Invoice unit price exceeds contracted PO price.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Payment Disbursement & Settlement Application",
        actor: "Treasury / Accounts Manager",
        actorRole: "payment:write / payment:approve",
        action: "Records bank payout, specifies reference/UTR number, and applies payment across open AP invoices. Reconciles vendor balance.",
        outputDoc: "Payment Voucher & Settlement Allocation Journal",
        statusTransition: "open → partially_paid → settled",
        interconnection: {
          upstreamModule: "Verified AP Invoice",
          upstreamEvent: "Invoice reaches due date",
          downstreamModule: "Vendor Ledger & General Ledger",
          downstreamEvent: "Reduces Accounts Payable liability",
        },
        validations: [
          {
            category: "Authorization",
            check: "Maker-Checker Payment Approval",
            rule: "Payments exceeding ₹1,00,000 require independent approval ('payment:approve') by Finance Controller.",
            errorCode: "PAYMENT_APPROVAL_REQUIRED",
            onFailure: "Disbursement blocked: 'Requires Finance Controller approval.'",
          },
          {
            category: "Business Logic",
            check: "Allocation Over-Payment Guard",
            rule: "Payment allocations cannot exceed the outstanding balance of any target invoice.",
            onFailure: "Validation error: 'Payment amount exceeds invoice balance.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Credit Notes & Financial Adjustments",
        actor: "Senior Accountant",
        actorRole: "finance:read",
        action: "Issues credit note for returned items, billing disputes, or volume rebates. Offsets open customer AR or vendor AP balances.",
        outputDoc: "Credit Note Voucher",
        statusTransition: "created → applied",
        interconnection: {
          upstreamModule: "Returns (RMA / RTV)",
          upstreamEvent: "Goods returned to warehouse",
          downstreamModule: "Customer / Vendor Balance",
          downstreamEvent: "Reduces total outstanding exposure",
        },
        validations: [
          {
            category: "Data Integrity",
            check: "Credit Reference Integrity",
            rule: "Credit note must reference a valid original invoice and cannot exceed the original invoice total.",
            onFailure: "HTTP 422: 'Credit note value exceeds referenced invoice balance.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Procurement",
        direction: "Inbound",
        trigger: "PO Contract Rates",
        dataExchanged: "Unit Price, Payment Terms, Freight Terms",
        ledgerEffect: "Used for 3-way match price verification",
      },
      {
        targetModule: "Warehouse (GRN)",
        direction: "Inbound",
        trigger: "GRN Accepted Qty",
        dataExchanged: "Accepted Qty, Vendor Invoice No, Batch Ref",
        ledgerEffect: "Used for 3-way match quantity verification",
      },
    ],
    trainingManual: {
      overview:
        "The Finance module acts as the ultimate truth of enterprise transactions. The core mechanism is the automated 3-Way Match, preventing over-billing, phantom receipts, and price creep.",
      sopWalkthrough: [
        {
          step: "1. Entering a Vendor Invoice",
          uiPath: "Finance & AR/AP > 'Invoices' Tab > '+ Record vendor invoice'",
          instructions:
            "Select vendor, enter invoice number, and select linked PO and GRN. System pulls line items.",
        },
        {
          step: "2. Reviewing 3-Way Match Status",
          uiPath: "Finance & AR/AP > Vendor Invoices > Click Invoice",
          instructions:
            "The system flags price or quantity differences in red. If match is green ('Matched'), invoice is ready for payout.",
        },
        {
          step: "3. Recording Payment Outflow",
          uiPath: "Finance & AR/AP > 'Payments' Tab > '+ Record payment'",
          instructions:
            "Select payee, payment method (NEFT/RTGS/Cheque), and apply payment against open invoices.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "No Duplicate Invoices",
          scope: "AP Invoicing",
          validationLogic: "UNIQUE(vendor_id, invoice_number)",
          enforcementLevel: "Hard Block (422/409)",
        },
        {
          ruleName: "3-Way Match Price & Qty",
          scope: "AP Posting",
          validationLogic: "billed_qty <= grn_accepted_qty && billed_rate <= po_rate",
          enforcementLevel: "Approval Escalation",
        },
      ],
      stateMachine: [
        { fromState: "open", toState: "partially_paid", action: "Partial Payment", allowedRoles: ["payment:write"], guardConditions: "Payment > 0" },
        { fromState: "partially_paid", toState: "settled", action: "Final Payment", allowedRoles: ["payment:write"], guardConditions: "Remaining balance == 0" },
      ],
    },
    faqs: [
      {
        question: "What is 3-Way Matching and why is it mandatory?",
        answer: "3-Way Matching compares Purchase Order, Goods Receipt Note, and Vendor Invoice to guarantee you only pay for what was contracted and physically received.",
      },
    ],
    troubleshooting: [
      {
        issue: "Invoice on hold: 'Billed quantity exceeds accepted GRN quantity'",
        errorCode: "MATCH_QTY_VARIANCE",
        symptom: "AP invoice status displays 'Variance Hold' and payment button is disabled.",
        rootCause: "The vendor billed for full quantity (e.g. 100), but the warehouse only accepted 90 (10 were rejected in QC).",
        stepByStepFix: [
          "Open the linked GRN to check QC inspection results.",
          "Confirm whether a debit note / RTV was issued for the rejected 10 units.",
          "Request the vendor provide an amended invoice or apply a debit note.",
        ],
        preventionTip: "Share warehouse QC inspection reports with vendor accounts before billing.",
      },
    ],
    quiz: [
      {
        question: "What three records are compared in 3-Way Matching?",
        options: [
          "Employee PR, Manager Approval, Quotation",
          "Purchase Order, Goods Receipt Note (GRN), and Vendor Tax Invoice",
          "Sales Order, Carrier AWB, Customer Review",
          "Bank Statement, Payroll, Audit Trail",
        ],
        correctIndex: 1,
        explanation: "3-Way Matching verifies the PO (price), GRN (quantity), and Vendor Invoice (bill).",
      },
    ],
  },

  logistics: {
    id: "logistics",
    title: "Logistics & Transportation (TMS)",
    subtitle: "Transport requests, freight RFQ, carrier selection, statutory e-Way bills, and POD",
    group: "Warehouse & Logistics",
    badge: "Freight Management",
    iconName: "Truck",
    summary:
      "Controls freight transportation for both customer sales dispatches and inbound vendor pickups. Enforces carrier bidding (Logistics RFQ), rate auditing, transporter LR/docket tracking, statutory NIC e-Way Bill generation, and Proof of Delivery (POD) closing.",
    primaryUsers: ["Logistics Coordinators", "Dispatch Clerks", "Fleet Managers", "Transporters"],
    keyDocuments: ["Transport Request (TR)", "Logistics RFQ / Carrier Quotation", "Dispatch Docket / LR", "e-Way Bill / e-Invoice IRN", "Proof of Delivery (POD)"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Transport Request Creation & Freight Consolidation",
        actor: "Dispatch Planner",
        actorRole: "logistics:write",
        action: "Aggregates packed sales shipments or inter-warehouse transfers by destination lane/zone. Evaluates total CBM volume and gross weight.",
        outputDoc: "Consolidated Transport Request (TR)",
        statusTransition: "draft → open",
        interconnection: {
          upstreamModule: "Sales Orders / Warehouse Transfer",
          upstreamEvent: "Order packed and staged at dispatch dock",
          downstreamModule: "Carrier Quoting / RFQ",
          downstreamEvent: "Transmits freight requirements to transporters",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "Origin and Destination Pincode Check",
            rule: "Source warehouse and delivery destination must have valid postal codes and state codes.",
            onFailure: "Validation error: 'Invalid origin or destination pincode.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Carrier Bidding & Quotation Award",
        actor: "Logistics Manager",
        actorRole: "logistics:quote / logistics:approve",
        action: "Sends freight RFQ to approved transporters. Compares freight rates. Awards shipment to selected carrier.",
        outputDoc: "Awarded Carrier Quotation",
        statusTransition: "rfq_sent → awarded",
        interconnection: {
          upstreamModule: "Transport Request",
          upstreamEvent: "Consolidated freight load published",
          downstreamModule: "Dispatch & Vehicle Assignment",
          downstreamEvent: "Transporter assigns driver and vehicle number",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Award Justification Check",
            rule: "Selecting a non-lowest freight rate requires audit justification.",
            onFailure: "HTTP 422: 'Justification required for non-lowest freight quote.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Statutory e-Way Bill & Dispatch Generation",
        actor: "Gate Dispatch Officer",
        actorRole: "logistics:dispatch",
        action: "Generates official 12-digit e-Way Bill and vehicle dispatch record (vehicle number, driver phone, LR/docket number). Transmit pre-dispatch advice to consignee.",
        outputDoc: "Dispatch Notice & Statutory e-Way Bill",
        statusTransition: "awarded → in_transit",
        interconnection: {
          upstreamModule: "Awarded Freight",
          upstreamEvent: "Truck arrives at dock for loading",
          downstreamModule: "In-Transit Tracking & Consignee",
          downstreamEvent: "Consignee receives live shipment tracking link",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Mandatory e-Way Bill for Value > ₹50,000",
            rule: "Consignments with invoice value > ₹50,000 require valid e-Way bill number and expiry timestamp.",
            errorCode: "EWAY_BILL_MANDATORY",
            onFailure: "Warning alert: 'High-value consignment requires e-Way bill.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Proof of Delivery (POD) & Carrier Settlement",
        actor: "Delivery Coordinator",
        actorRole: "logistics:dispatch",
        action: "Uploads physical signed and stamped Proof of Delivery (POD) slip. Confirms delivery timestamp and triggers freight invoice clearance in Finance.",
        outputDoc: "Signed POD Document & Closed Dispatch",
        statusTransition: "in_transit → delivered",
        interconnection: {
          upstreamModule: "Transporter Carrier",
          upstreamEvent: "Goods handed over to consignee",
          downstreamModule: "Finance / Carrier AP",
          downstreamEvent: "Unblocks carrier freight invoice for settlement",
        },
        validations: [
          {
            category: "Data Integrity",
            check: "Mandatory POD Image / File Attachment",
            rule: "Marking a dispatch 'delivered' requires uploading a legible POD document.",
            onFailure: "Validation error: 'Signed POD document attachment required.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Sales Orders",
        direction: "Outbound",
        trigger: "Dispatch Confirmed",
        dataExchanged: "Tracking AWB, Transporter Name, Expected Delivery Date",
        ledgerEffect: "Updates Order status to 'shipped'",
      },
    ],
    trainingManual: {
      overview:
        "The Logistics TMS module manages the movement of freight, optimizes multi-carrier shipping costs, ensures statutory e-Way bill compliance, and guarantees delivery through verified Proof of Delivery (POD).",
      sopWalkthrough: [
        {
          step: "1. Consolidating Transport Requests",
          uiPath: "Logistics TMS > 'Transport requests' Tab",
          instructions: "Select open orders headed to the same route and click 'Create consolidated RFQ'.",
        },
        {
          step: "2. Recording Carrier Quotes & Awarding",
          uiPath: "Logistics TMS > 'RFQs' Tab > Select RFQ",
          instructions: "Record quoted rates from transporters and award the winning carrier.",
        },
        {
          step: "3. Generating Dispatch & e-Way Bill",
          uiPath: "Logistics TMS > 'Dispatches' Tab > '+ Record dispatch'",
          instructions: "Enter vehicle number, LR docket number, and 12-digit e-Way bill number.",
        },
        {
          step: "4. Uploading Proof of Delivery (POD)",
          uiPath: "Logistics TMS > Open Dispatch > 'Upload POD'",
          instructions: "Upload signed delivery slip to mark consignment delivered.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Statutory e-Way Bill Limit",
          scope: "Dispatch Recording",
          validationLogic: "consignment_value > 50000 -> check eway_bill_number",
          enforcementLevel: "Warning Alert",
        },
      ],
      stateMachine: [
        { fromState: "open", toState: "in_transit", action: "Dispatch Truck", allowedRoles: ["logistics:dispatch"], guardConditions: "Vehicle number entered" },
        { fromState: "in_transit", toState: "delivered", action: "Confirm POD", allowedRoles: ["logistics:dispatch"], guardConditions: "POD attached" },
      ],
    },
    faqs: [
      {
        question: "When is an e-Way bill legally required in India?",
        answer: "Under GST rules, any inter-state or intra-state movement of goods valued above ₹50,000 mandates an e-Way bill.",
      },
    ],
    troubleshooting: [
      {
        issue: "Cannot mark dispatch delivered: 'POD attachment missing'",
        errorCode: "POD_ATTACHMENT_REQUIRED",
        symptom: "Attempting to confirm delivery throws an error.",
        rootCause: "System policy requires signed documentary evidence before marking delivery complete.",
        stepByStepFix: [
          "Obtain physical delivery challan or transporter electronic POD.",
          "Upload PDF/JPG file in the dispatch modal.",
          "Click 'Confirm Delivery'.",
        ],
        preventionTip: "Ensure drivers collect signatures upon handover.",
      },
    ],
    quiz: [
      {
        question: "What document must be attached before a carrier freight invoice is cleared for payment?",
        options: ["Quote PDF", "Signed Proof of Delivery (POD)", "Driver Driving License", "Factory Gate Pass"],
        correctIndex: 1,
        explanation: "Verified POD confirms delivery completion and unlocks carrier freight payments.",
      },
    ],
  },

  planning: {
    id: "planning",
    title: "Planning, MRP & SCM",
    subtitle: "Material Requirements Planning, multi-echelon DRP, and demand forecasting",
    group: "Planning & SCM",
    badge: "Supply Chain Intelligence",
    iconName: "SlidersHorizontal",
    summary:
      "Performs algorithmic Gross-to-Net Material Requirements Planning (MRP), multi-echelon Distribution Requirements Planning (DRP), finite capacity planning (RCCP), and statistical demand forecasting.",
    primaryUsers: ["Supply Chain Planners", "Master Production Schedulers (MPS)", "Procurement Planners"],
    keyDocuments: ["MRP Execution Plan", "Planned Purchase Order", "Planned Work Order", "DRP Transfer Schedule", "Forecast Scenario"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "Demand Aggregation & Forecasting",
        actor: "Demand Planner",
        actorRole: "forecasting:write",
        action: "Combines confirmed sales orders, historical shipments, and statistical forecast models (Holt-Winters, moving average) to create Master Production Schedule (MPS).",
        outputDoc: "Unconstrained Demand Schedule",
        statusTransition: "draft → active",
        interconnection: {
          upstreamModule: "Sales Orders / Customer Portal",
          upstreamEvent: "Customer order intake",
          downstreamModule: "MRP Explosion Engine",
          downstreamEvent: "Feeds gross finished goods demand into MRP engine",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Planning Horizon Boundary",
            rule: "Forecast horizon must be between 1 and 52 weeks.",
            onFailure: "Validation error: 'Planning horizon out of allowable bounds.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Gross-to-Net MRP Explosion",
        actor: "MRP Automation Engine",
        actorRole: "mrp:read",
        action: "Explodes multi-level BOMs for all finished goods. Calculates Gross Requirements, nets against current On-Hand and incoming POs, applies lead-time offsetting.",
        outputDoc: "Planned Orders (Planned POs & Planned Work Orders)",
        statusTransition: "calculated → proposed",
        interconnection: {
          upstreamModule: "BOM & Inventory Balances",
          upstreamEvent: "Current stock and BOM structures read from database",
          downstreamModule: "Procurement & Manufacturing",
          downstreamEvent: "Converts planned orders into actual Requisitions and Production Runs",
        },
        validations: [
          {
            category: "Data Integrity",
            check: "Lead Time & Minimum Order Qty (MOQ) Rules",
            rule: "Supplier lead times and lot-sizing rules (MOQ, batch multiples) must be respected.",
            onFailure: "Planning error: 'Missing supplier lead time data for SKU.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Planned Order Release & Action Approval",
        actor: "Supply Chain Planner",
        actorRole: "inventory:read",
        action: "Reviews proposed planned orders. Approves release: system auto-creates Purchase Requisitions for raw materials and planned Production Runs for finished goods.",
        outputDoc: "Released Purchase Requisitions & Work Orders",
        statusTransition: "proposed → released",
        interconnection: {
          upstreamModule: "MRP Explosion",
          upstreamEvent: "Planned orders generated",
          downstreamModule: "Procurement (PR) & Manufacturing (Runs)",
          downstreamEvent: "Directly populates operational execution queues",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Sanity Checks on Release Quantities",
            rule: "Planned orders cannot be released if the target warehouse is inactive.",
            onFailure: "Release error: 'Target facility is inactive.'",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "Procurement",
        direction: "Outbound",
        trigger: "Planned Orders Released",
        dataExchanged: "Raw Material SKU, Net Shortage Qty, Required Delivery Date, Facility",
        ledgerEffect: "Generates Purchase Requisitions",
      },
      {
        targetModule: "Manufacturing",
        direction: "Outbound",
        trigger: "Planned FG Orders Released",
        dataExchanged: "FG SKU, Target Batch Qty, Planned Start Date",
        ledgerEffect: "Creates Planned Production Runs",
      },
    ],
    trainingManual: {
      overview:
        "The Planning module ensures the company never runs out of stock while minimizing working capital tied up in excess inventory. The MRP engine balances lead times, safety stocks, and production capacity.",
      sopWalkthrough: [
        {
          step: "1. Running MRP Simulation",
          uiPath: "Planning & SCM > MRP Planning > 'Run MRP'",
          instructions: "Select planning horizon (e.g. Next 30 days) and target facilities. Click 'Execute MRP'.",
        },
        {
          step: "2. Reviewing Planned Orders",
          uiPath: "Planning & SCM > MRP Planning > 'Planned orders' Tab",
          instructions: "Review suggested orders. Filter by 'Buy' (Purchase) or 'Make' (Production).",
        },
        {
          step: "3. Releasing Planned Orders",
          uiPath: "Planning & SCM > Select Planned Orders > 'Release to Procurement / Production'",
          instructions: "Click 'Release'. System creates operational requisitions and work orders.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Lead Time Offsetting",
          scope: "MRP Calculation",
          validationLogic: "order_date = requirement_date - lead_time_days",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "proposed", toState: "released", action: "Release", allowedRoles: ["inventory:read"], guardConditions: "Valid facility" },
      ],
    },
    faqs: [
      {
        question: "How often should MRP be run?",
        answer: "Most manufacturing plants execute MRP daily (typically an overnight batch run) to incorporate the latest day's sales orders and goods receipts.",
      },
    ],
    troubleshooting: [
      {
        issue: "MRP suggests past-due order dates",
        errorCode: "PAST_DUE_LEAD_TIME",
        symptom: "Planned order shows suggested order date in the past.",
        rootCause: "Customer required date is sooner than the supplier's cumulative manufacturing and transit lead time.",
        stepByStepFix: [
          "Check supplier lead time on the product master.",
          "Contact supplier for expedited air freight or alternate vendor.",
          "Notify sales rep to adjust customer delivery expectation.",
        ],
        preventionTip: "Maintain accurate supplier lead times in Product Master.",
      },
    ],
    quiz: [
      {
        question: "What does the Gross-to-Net calculation in MRP do?",
        options: [
          "Calculates employee salary taxes.",
          "Subtracts current On-Hand stock and scheduled receipts from gross demand to find true shortage.",
          "Multiplies sales price by GST rate.",
          "Deletes old purchase orders.",
        ],
        correctIndex: 1,
        explanation: "Gross-to-Net converts gross customer demand into net purchase/production orders by accounting for stock on hand.",
      },
    ],
  },

  administration: {
    id: "administration",
    title: "Administration, Master Data & Security",
    subtitle: "RBAC permissions, user hierarchies, multi-entity setups, and audit trails",
    group: "Administration",
    badge: "System Governance",
    iconName: "ShieldCheck",
    summary:
      "Controls system security, Role-Based Access Control (RBAC), multi-tenant business entities, factory/warehouse topological hierarchies, email configuration, automated numbering sequences, and append-only audit trail logging.",
    primaryUsers: ["System Administrators", "Compliance Officers", "IT Operations", "Tenant Admins"],
    keyDocuments: ["User Master Record", "Role Permission Matrix", "Business Entity Certificate", "Facility Record", "Audit Log Trail"],
    workflowSteps: [
      {
        stepNumber: 1,
        title: "User Provisioning & Role Assignment",
        actor: "System Administrator",
        actorRole: "user:write / role:assign",
        action: "Invites new employees, sets temporary passwords or SSO integration, assigns department, assigns 'Reports To' manager, and grants role memberships.",
        outputDoc: "Active User Profile & Assigned Roles",
        statusTransition: "invited → active",
        interconnection: {
          upstreamModule: "HR Onboarding",
          upstreamEvent: "New employee joins company",
          downstreamModule: "All Operational Modules",
          downstreamEvent: "Allows user to sign in and interact with permitted ERP screens",
        },
        validations: [
          {
            category: "Business Logic",
            check: "Least-Privilege Role Granting Guard",
            rule: "An administrator cannot grant a role containing permissions that the granter does not personally hold (unless granter holds wildcard '*').",
            errorCode: "LEAST_PRIVILEGE_VIOLATION",
            onFailure: "HTTP 403: 'You cannot grant permissions you do not possess.'",
          },
          {
            category: "Data Integrity",
            check: "Unique Email Address",
            rule: "User email must be unique across the tenant.",
            onFailure: "HTTP 409: 'User with this email already exists.'",
          },
        ],
      },
      {
        stepNumber: 2,
        title: "Facility & Warehouse Scope Restriction",
        actor: "Operations Admin",
        actorRole: "warehouse:write",
        action: "Defines factory facilities and warehouse locations. Assigns warehouse scopes to users to restrict data visibility to specific physical buildings.",
        outputDoc: "Facility Hierarchy & User Scope Mapping",
        statusTransition: "active",
        interconnection: {
          upstreamModule: "Enterprise Architecture",
          upstreamEvent: "Company opens new warehouse or production facility",
          downstreamModule: "Warehouse, GRN & Inventory Operations",
          downstreamEvent: "Ensures staff at Warehouse A cannot view or post stock in Warehouse B",
        },
        validations: [
          {
            category: "Authorization",
            check: "Warehouse Scope Enforcement",
            rule: "All warehouse endpoints execute assert_warehouse_in_scope() against the authenticated actor.",
            onFailure: "HTTP 403: 'Access denied: warehouse outside authorized facility scope.'",
          },
        ],
      },
      {
        stepNumber: 3,
        title: "Per-Purpose Email & Mailbox Configuration",
        actor: "IT Administrator",
        actorRole: "email_config:write",
        action: "Sets up discrete SMTP mailboxes for each business flow: purchase orders, customer invoices, sourcing RFQs, dispatches, and user invites. Passwords stored with AES encryption.",
        outputDoc: "Configured Email Transports & Delivery Queues",
        statusTransition: "active",
        interconnection: {
          upstreamModule: "Mail Servers (Google Workspace / M365)",
          upstreamEvent: "Company email credentials configured",
          downstreamModule: "Procurement, Sales & Notifications",
          downstreamEvent: "Sends outbound transactional PDFs to vendors and customers",
        },
        validations: [
          {
            category: "Pre-Condition",
            check: "SMTP Connectivity & Test Verification",
            rule: "Email configuration can only be saved after running 'Send test email' to verify valid SMTP handshake.",
            onFailure: "Test failure: 'SMTP authentication failed. Check host, port, or app password.'",
          },
        ],
      },
      {
        stepNumber: 4,
        title: "Immutable System Audit Trail Inspection",
        actor: "Auditor / Compliance Officer",
        actorRole: "audit:read",
        action: "Inspects system-wide append-only audit trail. Records every create, update, approve, cancel, and delete event with user email, timestamp, IP address, and reason.",
        outputDoc: "Audit Trail Report",
        statusTransition: "immutable_log",
        interconnection: {
          upstreamModule: "All ERP Transactions",
          upstreamEvent: "Any state mutation or approval action across any module",
          downstreamModule: "Compliance & Security Review",
          downstreamEvent: "Provides SOX / ISO 9001 compliance audit trail",
        },
        validations: [
          {
            category: "Data Integrity",
            check: "Append-Only Audit Guarantee",
            rule: "Audit log table has no UPDATE or DELETE API endpoints; rows cannot be modified or purged.",
            onFailure: "Forbidden by system architecture.",
          },
        ],
      },
    ],
    crossModuleInterconnections: [
      {
        targetModule: "All ERP Modules",
        direction: "Outbound",
        trigger: "Role / Permission Changes",
        dataExchanged: "Active user permissions, warehouse scopes, manager routing",
        ledgerEffect: "Instantly gates all UI routes and API endpoints",
      },
    ],
    trainingManual: {
      overview:
        "The Administration module provides master data governance, identity lifecycle management, facility scoping, and compliance auditing across all functional ERP modules.",
      sopWalkthrough: [
        {
          step: "1. Managing Users & Roles",
          uiPath: "Administration > Users & roles",
          instructions: "Create users, assign roles (e.g. Buyer, Store Keeper, System Admin), and set 'Reports to' hierarchy.",
        },
        {
          step: "2. Setting Up Outgoing Email Mailboxes",
          uiPath: "Administration > Email Config",
          instructions: "Configure SMTP settings for POs, RFQs, Invoices, and test delivery.",
        },
        {
          step: "3. Reviewing Audit Logs",
          uiPath: "Administration > Audit trail",
          instructions: "Search audit logs by actor email, entity ID, or action type to trace transaction history.",
        },
      ],
      validationMatrix: [
        {
          ruleName: "Least-Privilege Guard",
          scope: "Role Assignment",
          validationLogic: "granter_permissions.contains_all(requested_permissions) || granter.has('*')",
          enforcementLevel: "Hard Block (422/409)",
        },
      ],
      stateMachine: [
        { fromState: "invited", toState: "active", action: "First Sign In", allowedRoles: ["User"], guardConditions: "Password set" },
      ],
    },
    faqs: [
      {
        question: "Can an admin delete audit log records to save disk space?",
        answer: "No. Audit logs in Simple ERP are strictly append-only and immutable to guarantee compliance with ISO, GST, and corporate audit standards.",
      },
    ],
    troubleshooting: [
      {
        issue: "User sees 'Forbidden: 403' on a page they need to access",
        errorCode: "PERMISSION_DENIED",
        symptom: "Screen displays a red shield icon indicating missing permission.",
        rootCause: "The user's assigned role is missing the required permission code (e.g. 'grn:post' or 'finance:read').",
        stepByStepFix: [
          "Check the required permission code listed on the forbidden panel.",
          "Navigate to 'Users & roles' > 'Manage roles'.",
          "Edit the user's role and check the checkbox for that permission.",
          "Save changes; the user refreshes their browser to regain access.",
        ],
        preventionTip: "Use standard pre-built roles for common operational personas.",
      },
    ],
    quiz: [
      {
        question: "Can an administrator grant a permission to another user that the administrator does not have?",
        options: [
          "Yes, administrators can always grant any permission.",
          "No, the least-privilege guard prevents granters from bestowing permissions they do not hold.",
          "Only on weekends.",
          "Only if the user requests it by email.",
        ],
        correctIndex: 1,
        explanation: "Simple ERP enforces least-privilege security so subordinate admins cannot escalate their own or others' privileges.",
      },
    ],
  },
};
