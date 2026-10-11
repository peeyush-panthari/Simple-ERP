"""Permission catalogue and system roles. Ported verbatim - framework-agnostic."""

from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    # Identity
    "user:read": "View users",
    "user:write": "Create and edit users",
    "user:deactivate": "Deactivate users",
    "role:read": "View roles",
    "role:write": "Create and edit roles",
    "role:assign": "Assign roles to users",
    "audit:read": "View audit trail",
    "org:read": "View business entities (PO & Invoice)",
    "org:write": "Create and edit business entities",
    # Party
    "party:read": "View parties",
    "party:write": "Create and edit parties",
    "party:approve": "Approve bank detail changes and activation",
    "party:block": "Block or unblock parties",
    # Product & BOM
    "product:read": "View products",
    "product:write": "Create and edit products",
    "product:publish": "Publish and deprecate products",
    "bom:read": "View bills of material",
    "bom:write": "Draft and revise BOM versions",
    "bom:approve": "Approve BOM versions",
    # Procurement
    "po:read": "View purchase orders",
    "po:write": "Create and edit purchase orders",
    "po:approve": "Approve purchase orders",
    "po:issue": "Issue purchase orders to vendors",
    "po:cancel": "Cancel purchase orders",
    "po:short_close": "Force-close a purchase order with an outstanding balance",
    "po:email": "Send purchase order emails",
    "po:vendor": "Record the vendor's acknowledgement, vendor documents and dispatch details on a purchase order",
    # Purchase requisitions (employee -> Purchase department)
    "pr:read": "View your own purchase requisitions",
    "pr:write": "Raise, edit and cancel your own purchase requisitions",
    "pr:team_approve": "Approve or reject purchase requisitions raised by the people who report to you",
    "pr:approve": "Review everyone's purchase requisitions (Purchase department): approve, reject, send out for quotation",
    # Sourcing (RFQ to vendors, quotation comparison, award -> purchase orders)
    "sourcing:read": "View sourcing events (RFQs), quotations and comparisons",
    "sourcing:write": "Start sourcing, invite vendors and record their quotations",
    "sourcing:award": "Choose the winning quotation per item and raise the purchase orders",
    # Warehouse
    "warehouse:read": "View warehouses and locations",
    "warehouse:write": "Create and edit warehouses and locations",
    "grn:read": "View goods receipts",
    "grn:write": "Create goods receipts",
    "grn:post": "Post goods receipts to inventory",
    # Inventory
    "inventory:read": "View balances and ledger",
    "inventory:reserve": "Create and release reservations",
    "inventory:transfer": "Create and complete transfers",
    "inventory:adjust": "Post adjustments and status changes",
    "inventory:produce": "Post finished-goods production",
    # Order
    "order:read": "View sales orders",
    "order:write": "Create and edit sales orders",
    "order:confirm": "Confirm sales orders",
    "order:allocate": "Allocate stock to orders",
    "order:pack": "Mark an allocated order as packed for shipping",
    "order:ship": "Mark orders shipped and fulfilled",
    "order:invoice": "Generate invoices",
    "order:cancel": "Cancel sales orders",
    "order:override-logistics": "Raise logistics before full payment",
    # Logistics
    "logistics:read": "View transport requests and RFQs",
    "logistics:write": "Create transport requests and RFQs",
    "logistics:quote": "Record carrier quotations",
    "logistics:approve": "Award quotations",
    "logistics:dispatch": "Create dispatches and confirm delivery",
    # Finance
    "finance:read": "View AP, AR and working capital",
    "invoice:post": "Post vendor and customer invoices",
    "payment:write": "Record payments",
    "payment:approve": "Approve payments, refunds and write-offs",
    # Configuration
    "sticker_size:read": "View sticker size templates",
    "sticker_size:write": "Create, edit and delete sticker size templates",
    # Foundation
    "email_config:read": "View the outgoing email setup (never the password)",
    "email_config:write": "Change the outgoing email setup and send test emails",
    # Platform
    "notification:read": "View delivery logs",
    "notification:send": "Send notifications",
    "document:read": "Download generated documents",
    "document:write": "Generate documents",
    "analytics:read": "View dashboards and KPIs",
    "training:read": "View ERP training module and workflows",
    # Roadmap Modules
    "landed_cost:read": "View landed cost tracking and apportionment",
    "landed_cost:write": "Create and post landed cost vouchers",
    "subcontracting:read": "View subcontracting and job-work orders",
    "subcontracting:write": "Create subcontracting orders, challans and receipts",
    "wms_bins:read": "View warehouse bin topology and putaway rules",
    "wms_bins:write": "Manage bin topology and execute putaway/picking tasks",
    "drp:read": "View multi-echelon distribution requirements planning",
    "drp:write": "Manage distribution requirements plans and inter-warehouse transfers",
    "forecasting:read": "View statistical demand forecasting and S&OP models",
    "forecasting:write": "Create and update demand forecast scenarios",
    "traceability:read": "View lot genealogy and recall trees",
    "traceability:write": "Initiate lot recalls and digital quarantine freezes",
    "freight:read": "View freight container consolidation and multi-modal TMS",
    "freight:write": "Manage freight containers, pack cargo and audit carrier rates",
    "vendor_portal:read": "View vendor self-service collaboration portal",
    "vendor_portal:write": "Manage vendor portal actions, ASNs and acknowledgements",
    # Phase 1 Supply Chain Modules
    "cycle_count:read": "View inventory cycle counts and audit sessions",
    "cycle_count:write": "Create and execute cycle count sessions and adjustments",
    "statutory_logistics:read": "View statutory e-Way Bills and GST e-Invoices",
    "statutory_logistics:write": "Generate and manage statutory e-Way Bills and e-Invoices",
    "blanket_po:read": "View blanket purchase orders and rate contracts",
    "blanket_po:write": "Create and manage blanket POs and call-off releases",
    "wms_mobile:use": "Access mobile RF barcode scanner floor interface",
    # Phase 2 Supply Chain Modules
    "wave_picking:read": "View wave and batch picking plans and pick paths",
    "wave_picking:write": "Create pick waves, release batches and confirm picks",
    "customer_portal:read": "View customer self-service portal orders and invoices",
    "customer_portal:write": "Manage customer portal settings and process RMA requests",
    "quality_ipqc:read": "View in-process quality inspections and certificates of analysis",
    "quality_ipqc:write": "Perform IPQC stage testing and authorize CoA certificates",
    "avl_governance:read": "View approved vendor list and supplier compliance certifications",
    "avl_governance:write": "Manage vendor qualification status and audit certificates",
    # Phase 3 Supply Chain Modules
    "capacity_planning:read": "View work center finite capacity planning and RCCP schedules",
    "capacity_planning:write": "Manage work centers and schedule production jobs",
    "shipping_engine:read": "View carrier rates, live AWBs, and parcel shipments",
    "shipping_engine:write": "Perform rate shopping, generate AWBs, and print thermal labels",
    "sc_control_tower:read": "View supply chain control tower, OTIF, DOH, and volatility heatmaps",
    "sc_control_tower:write": "Configure control tower benchmark thresholds and refresh snapshots",
    "system:admin": "Full administrative access",
}

ALL_PERMISSIONS: list[str] = list(PERMISSIONS.keys())

SYSTEM_ROLES: dict[str, dict] = {
    "System Admin": {
        "description": "All modules, role management, policy setup, emergency overrides",
        "permissions": ["*"],
    },
}


def permits(granted: list[str], required: str) -> bool:
    if "*" in granted:
        return True
    if required in granted:
        return True
    resource = required.split(":")[0]
    return f"{resource}:*" in granted


def permits_all(granted: list[str], required: list[str]) -> bool:
    return all(permits(granted, r) for r in required)


def permits_any(granted: list[str], required: list[str]) -> bool:
    return any(permits(granted, r) for r in required)


def can_grant(granter_permissions: list[str], requested: list[str]) -> list[str]:
    """Least-privilege guard: returns the subset of `requested` the granter does NOT hold."""
    if "*" in granter_permissions:
        return []
    return [p for p in requested if not permits(granter_permissions, p)]
