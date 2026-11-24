# Simple ERP | Company Onboarding Guide

**The Definitive Operational and Technical Manual for Onboarding New Companies, Subsidiaries, and Business Units onto Simple ERP**

*Version:* 2.4.0 Enterprise Edition  
*Date of Revision:* November 2026  
*Status:* Official Deployment & Implementation Standard  
*Companion Documents:* [USER_GUIDE.md](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/USER_GUIDE.md), [README.md](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/README.md), [DEPLOYMENT.md](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/DEPLOYMENT.md)

---

## Table of Contents

1. [Executive Overview & Onboarding Architecture](#1-executive-overview--onboarding-architecture)
   - 1.1 [Tenants vs. Business Entities](#11-tenants-vs-business-entities)
   - 1.2 [The 8-Phase Onboarding Lifecycle](#12-the-8-phase-onboarding-lifecycle)
   - 1.3 [Pre-Requisites & Readiness Checklist](#13-pre-requisites--readiness-checklist)
2. [Phase 1: Environment Provisioning & System Bootstrap](#2-phase-1-environment-provisioning--system-bootstrap)
   - 2.1 [Infrastructure Launch via Docker Compose](#21-infrastructure-launch-via-docker-compose)
   - 2.2 [Database Migration & Idempotent Bootstrap](#22-database-migration--idempotent-bootstrap)
   - 2.3 [First Administrator Credentials & Initial Sign-In](#23-first-administrator-credentials--initial-sign-in)
3. [Phase 2: Setup-Time Module Customization (Per-Company Tailoring)](#3-phase-2-setup-time-module-customization-per-company-tailoring)
   - 3.1 [Why Tailor Modules per Business Unit?](#31-why-tailor-modules-per-business-unit)
   - 3.2 [Using the Active Modules & Setup Console](#32-using-the-active-modules--setup-console)
   - 3.3 [Selecting One-Click Industry Presets](#33-selecting-one-click-industry-presets)
   - 3.4 [Granular 24-Module Registry & Dependency Graph](#34-granular-24-module-registry--dependency-graph)
   - 3.5 [API-Driven Configuration](#35-api-driven-configuration)
4. [Phase 3: Legal Company & Statutory Profile Setup](#4-phase-3-legal-company--statutory-profile-setup)
   - 4.1 [Defining Business Entities (`/po-invoice`)](#41-defining-business-entities-po-invoice)
   - 4.2 [Statutory Tax & Regulatory Setup (GSTIN, PAN, State Codes)](#42-statutory-tax--regulatory-setup-gstin-pan-state-codes)
   - 4.3 [Corporate Remittance Banking Rails](#43-corporate-remittance-banking-rails)
   - 4.4 [Multi-Entity & Multi-GSTIN Architectures](#44-multi-entity--multi-gstin-architectures)
   - 4.5 [Bulk Entity Ingestion via CSV](#45-bulk-entity-ingestion-via-csv)
5. [Phase 4: Physical Topography & Storage Topography Commissioning](#5-phase-4-physical-topography--storage-topography-commissioning)
   - 5.1 [Commissioning Manufacturing Plants & Factories (`/factory-warehouse`)](#51-commissioning-manufacturing-plants--factories-factory-warehouse)
   - 5.2 [Commissioning Warehouses & Distribution Centers](#52-commissioning-warehouses--distribution-centers)
   - 5.3 [Automated Quarantine and Inbound Locations](#53-automated-quarantine-and-inbound-locations)
   - 5.4 [Commissioning WMS Storage Topography: Zones, Racks & Bins (`/wms-bins`)](#54-commissioning-wms-storage-topography-zones-racks--bins-wms-bins)
   - 5.5 [Bulk Warehouse & Factory CSV Import](#55-bulk-warehouse--factory-csv-import)
6. [Phase 5: Master Data Migration & Catalog Setup](#6-phase-5-master-data-migration--catalog-setup)
   - 6.1 [Product Categories, Tax Slabs & Units of Measure (`/configuration`)](#61-product-categories-tax-slabs--units-of-measure-configuration)
   - 6.2 [Product Catalog & Stock Definitions (`/products`)](#62-product-catalog--stock-definitions-products)
   - 6.3 [Bills of Materials (BOM) & Routing Operations](#63-bills-of-materials-bom--routing-operations)
   - 6.4 [Vendor Onboarding & AVL Qualification (`/parties`, `/avl-governance`)](#64-vendor-onboarding--avl-qualification-parties-avl-governance)
   - 6.5 [Customer Master & Commercial Terms (`/parties`)](#65-customer-master--commercial-terms-parties)
   - 6.6 [Bulk Master Data Migration Pipelines](#66-bulk-master-data-migration-pipelines)
7. [Phase 6: Team, Roles & Multi-Site Scoping (RBAC)](#7-phase-6-team-roles--multi-site-scoping-rbac)
   - 7.1 [User Provisioning & Invitation Lifecycles (`/users`)](#71-user-provisioning--invitation-lifecycles-users)
   - 7.2 [Role Assignment & System Permissions](#72-role-assignment--system-permissions)
   - 7.3 [Managerial Approval Routing ("Reports To")](#73-managerial-approval-routing-reports-to)
   - 7.4 [Site Scoping (Facility-Level Data Isolation)](#74-site-scoping-facility-level-data-isolation)
   - 7.5 [Authentication Policies & MFA Enforcement (`/profile`)](#75-authentication-policies--mfa-enforcement-profile)
8. [Phase 7: Communications, Statutory Gateways & Hardware Setup](#8-phase-7-communications-statutory-gateways--hardware-setup)
   - 8.1 [Outbound SMTP Mailbox Routing (`/email-config`)](#81-outbound-smtp-mailbox-routing-email-config)
   - 8.2 [Statutory Logistics Gateways: NIC e-Way Bills & e-Invoicing (`/statutory-logistics`)](#82-statutory-logistics-gateways-nic-e-way-bills--e-invoicing-statutory-logistics)
   - 8.3 [Thermal Barcode & Label Sizing (`/configuration`)](#83-thermal-barcode--label-sizing-configuration)
   - 8.4 [Mobile Handheld Scanners & WMS Setup (`/wms-mobile`)](#84-mobile-handheld-scanners--wms-setup-wms-mobile)
9. [Phase 8: Opening Balances, Cutover & Go-Live Protocol](#9-phase-8-opening-balances-cutover--go-live-protocol)
   - 9.1 [Pre-Cutover Freeze Protocol](#91-pre-cutover-freeze-protocol)
   - 9.2 [Opening Stock Balance Ingestion & Ledger Validation (`/inventory`)](#92-opening-stock-balance-ingestion--ledger-validation-inventory)
   - 9.3 [Open Purchase Orders & In-Flight Sourcing Migration](#93-open-purchase-orders--in-flight-sourcing-migration)
   - 9.4 [Open Sales Orders & Fulfillment Migration](#94-open-sales-orders--fulfillment-migration)
   - 9.5 [Accounts Payable & Receivable Opening Positions (`/finance`)](#95-accounts-payable--receivable-opening-positions-finance)
   - 9.6 [End-to-End "Golden Flow" Validation Run](#96-end-to-end-golden-flow-validation-run)
   - 9.7 [Formal Go-Live Sign-Off Checklist](#97-formal-go-live-sign-off-checklist)
10. [Appendix: Master Data CSV Templates, Schemas & Troubleshooting](#10-appendix-master-data-csv-templates-schemas--troubleshooting)
    - 10.1 [CSV Specifications Reference](#101-csv-specifications-reference)
    - 10.2 [Common Onboarding Pitfalls & Remediation](#102-common-onboarding-pitfalls--remediation)
    - 10.3 [Tenant Data Reset & Emergency Rollback Procedures](#103-tenant-data-reset--emergency-rollback-procedures)

---

## 1. Executive Overview & Onboarding Architecture

Simple ERP is a modular monolithic enterprise resource planning platform engineered for manufacturing, supply chain, inventory, and financial control. When onboarding a new organization, business unit, or operating subsidiary, implementation teams must understand the foundational architectural boundaries of the system.

### 1.1 Tenants vs. Business Entities

A common source of confusion in enterprise software is the distinction between a **Software Tenant** and a **Legal Business Entity**. Simple ERP strictly delineates these concepts:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TENANT (Software Container)                     │
│  - Database isolation boundary (tenants table)                         │
│  - User directory & System Admin accounts                              │
│  - Global Security Policies & AuthPolicy                               │
│  - Enabled Module Registry (e.g. Trading vs Discrete Mfg)              │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │               BUSINESS ENTITIES (Legal Tax Entities)           │   │
│   │                                                                │   │
│   │  ┌───────────────────────────┐  ┌───────────────────────────┐  │   │
│   │  │ Business Entity 1         │  │ Business Entity 2         │  │   │
│   │  │ Code: ENT-001 (Default)   │  │ Code: ENT-002             │  │   │
│   │  │ "Acme Industries Pvt Ltd" │  │ "Acme Logistics LLP"      │  │   │
│   │  │ GSTIN: 27AABCA1234A1Z5    │  │ GSTIN: 29AABCA1234A1Z8    │  │   │
│   │  │ State: 27 (Maharashtra)   │  │ State: 29 (Karnataka)     │  │   │
│   │  │ Remittance Bank Account A │  │ Remittance Bank Account B │  │   │
│   │  └─────────────┬─────────────┘  └─────────────┬─────────────┘  │   │
│   └────────────────┼──────────────────────────────┼────────────────┘   │
│                    │                              │                    │
│   ┌────────────────▼──────────────────────────────▼────────────────┐   │
│   │               PHYSICAL INFRASTRUCTURE TOPOGRAPHY               │   │
│   │  ┌───────────────────────────┐  ┌───────────────────────────┐  │   │
│   │  │ Factories (Plant 101)     │  │ Central DC / Warehouses   │  │   │
│   │  │ Production Lines & Work   │  │ Storage Zones, Aisles,    │  │   │
│   │  │ Centers                   │  │ Racks, Bins & Benches     │  │   │
│   │  └───────────────────────────┘  └───────────────────────────┘  │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

1. **The Tenant (`tenants` table):**
   * Represents the overall enterprise account, multi-tenant database slice, and security boundary.
   * Encapsulates authentication credentials, identity profiles, user roles, security policies, and the **Enabled Modules configuration** (which determines what software modules are active).
   * Holds the base currency (default: `INR`) and home country (default: `IN`).

2. **The Business Entity (`business_entities` table):**
   * Represents an official legal entity (e.g., private limited company, partnership, LLC) registered with statutory revenue authorities.
   * Holds the 15-digit **GSTIN**, **PAN**, legal registered office address, and statutory banking details.
   * Stamped as the **Seller of Record** on customer tax invoices and debit notes.
   * Stamped as the **Buyer / Bill-To Party** on supplier purchase orders.
   * Multiple legal entities can coexist within a single tenant to facilitate multi-division, multi-state, or multi-vertical operations without requiring separate software instances.

---

### 1.2 The 8-Phase Onboarding Lifecycle

A production onboarding progresses through eight sequential, auditable phases:

```mermaid
flowchart TD
    P1["Phase 1: Environment Provisioning<br/>Docker, DB Migrations & Admin Bootstrap"]
    P2["Phase 2: Setup-Time Module Customization<br/>Select Industry Presets & Active Modules"]
    P3["Phase 3: Legal Company & Tax Profile<br/>Business Entities, GSTIN, PAN & Banking"]
    P4["Phase 4: Physical Topography<br/>Factories, Warehouses, Zones & Bins"]
    P5["Phase 5: Master Data & Catalog Migration<br/>UOM, Tax Slabs, SKUs, BOMs, Vendors & Customers"]
    P6["Phase 6: Team, Roles & Multi-Site Scoping<br/>User Accounts, RBAC Scoping & Manager Approvals"]
    P7["Phase 7: Communications & Statutory Rails<br/>SMTP Mailboxes, NIC e-Way Bills, Thermal Printers"]
    P8["Phase 8: Opening Balances & Cutover<br/>Inventory Adjustments, In-Flight Orders, Go-Live"]

    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8
```

| Phase | Focus Area | Key System Screens / APIs | Deliverable |
|---|---|---|---|
| **Phase 1** | Infra & Bootstrap | CLI / `python -m app.core.bootstrap` | Running system & Superadmin access |
| **Phase 2** | Module Tailoring | `/configuration` (`GET/PUT /api/v1/tenant/modules`) | Clean, domain-focused application shell |
| **Phase 3** | Legal Entity Setup | `/po-invoice` (`/api/v1/business-entities`) | Registered corporate seller/buyer identity |
| **Phase 4** | Physical Topography | `/factory-warehouse`, `/wms-bins` | Plants, warehouses, bins & putaway zones |
| **Phase 5** | Master Catalog | `/products`, `/parties`, `/avl-governance` | Items, BOMs, supplier directory & AVL |
| **Phase 6** | People & Security | `/users`, `/profile` | Employees, site scoping, approval hierarchy |
| **Phase 7** | External Rails | `/email-config`, `/statutory-logistics` | SMTP mailers, NIC e-Way bill gateway |
| **Phase 8** | Cutover & Go-Live | `/inventory`, `/finance`, `/orders`, `/procurement` | Stock balances, open POs/SOs, live sign-off |

---

### 1.3 Pre-Requisites & Readiness Checklist

Before beginning onboarding, the implementation lead must gather the following statutory, operational, and technical assets:

- [ ] **Corporate Registration:** Certificate of Incorporation, Legal Registered Name, Corporate Identity Number (CIN).
- [ ] **Statutory Tax Credentials:** PAN card, 15-digit GSTIN certificates for all operating states, registered state codes.
- [ ] **Banking Rails:** Official bank account numbers, IFSC codes, bank branch names, and account names for invoice remittance.
- [ ] **Physical Facilities Data:** List of operating plants, warehouses, 3PL depots, square footage, postal PIN codes, and designated warehouse managers.
- [ ] **Storage Layout:** Physical aisle, rack, shelf, and bin numbering maps, including cold-storage or hazardous quarantine requirements.
- [ ] **Master Data Cleansing:** Clean CSV extracts of legacy SKUs, descriptions, HSN codes, base UOMs, and active Bills of Materials (BOM).
- [ ] **Counterparty Directories:** Supplier list (with GSTIN, payment terms, contact emails) and customer list (with billing/shipping addresses and credit limits).
- [ ] **Statutory Gateway Credentials:** Production credentials for the National Informatics Centre (NIC) e-Way Bill / e-Invoice portal.
- [ ] **Outbound Mail Infrastructure:** SMTP credentials (host, port, app password, TLS mode) for business communications (e.g. Google Workspace, M365, Amazon SES).

---

## 2. Phase 1: Environment Provisioning & System Bootstrap

Every company deployment begins with launching the containerized stack and executing the idempotent database bootstrap.

### 2.1 Infrastructure Launch via Docker Compose

Simple ERP runs as a high-performance modular monolith. Ensure Docker and Docker Compose are installed on the host server, then configure the production environment variables:

```bash
# 1. Clone repository or stage release archive
cd "/opt/simple-erp"

# 2. Configure secrets and connection parameters
cp .env.example .env
nano .env
```

Ensure the following core variables are configured in `.env`:
* `DATABASE_URL`: `postgresql+psycopg://simple_app:secret@postgres:5432/simple_erp`
* `REDIS_URL`: `redis://redis:6379/0`
* `RABBITMQ_URL`: `amqp://simple_mq:secret@rabbitmq:5672//`
* `BOOTSTRAP_ADMIN_EMAIL`: `admin@yourcompany.com`
* `BOOTSTRAP_ADMIN_PASSWORD`: A strong initial password (e.g., `Company#Admin2026!`)
* `JWT_SECRET`: A 32+ character cryptographically random string

Launch the infrastructure services:
```bash
docker compose up -d --build
```

Container startup sequencing is orchestrated automatically:
1. `postgres`, `redis`, and `rabbitmq` pass their internal health checks.
2. The `migrate` container runs `alembic upgrade head`, building the complete relational schema from 48 migration steps.
3. The `migrate` container invokes `python -m app.core.bootstrap` to seed the database idempotently, then exits with code 0.
4. The `api` and `worker` services start once `migrate` completes successfully.

---

### 2.2 Database Migration & Idempotent Bootstrap

The bootstrap runner ([bootstrap.py](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/backend/app/core/bootstrap.py)) guarantees that a fresh database receives the foundational primitives required for operational readiness:

1. **Default Tenant Provisioning:** Creates the primary tenant record with `INR` base currency and `IN` country.
2. **Security & Authentication Policy:** Seeds default password complexity rules, session timeouts, and rate limits in `AuthPolicy`.
3. **Core System Roles:** Seeds the 10 standard system roles and assigns granular system permissions:
   * `System Admin`, `Warehouse Manager`, `Warehouse Operator`, `Purchase Manager`, `Buyer`, `Production Manager`, `Quality Inspector`, `Sales Manager`, `Finance Manager`, `Transporter`.
4. **Default Party Types:** Seeds standard classification codes (`raw_material_vendor`, `production_vendor`, `customer`).
5. **System Notification Templates:** Seeds default Jinja-templated emails for purchase orders, RFQ invitations, invoice delivery, dispatch notes, and user invitations.

> [!NOTE]
> The bootstrap script is completely idempotent. It can be safely executed repeatedly against an existing database without overwriting or duplicating production data.

---

### 2.3 First Administrator Credentials & Initial Sign-In

1. Navigate to the application URL in a modern web browser: `http://localhost:5173` (or your domain, e.g. `https://erp.yourcompany.com`).
2. The application will automatically route unauthenticated sessions to `/login`.
3. Sign in with the bootstrap credentials:
   * **Email:** The value defined in `BOOTSTRAP_ADMIN_EMAIL` (default: `admin@simple-erp.local`).
   * **Password:** The value defined in `BOOTSTRAP_ADMIN_PASSWORD` (or the one-time random password output in `docker compose logs migrate`).
4. Upon successful sign-in, the system redirects to the main Control Tower dashboard (`/`).

---

## 3. Phase 2: Setup-Time Module Customization (Per-Company Tailoring)

A major strength of Simple ERP is its ability to adapt its interface and active workflows to the exact business model of the onboarding company. A pure trading company does not need manufacturing and shop-floor assembly screens; a third-party logistics (3PL) warehouse does not need bills of materials or MRP runs.

### 3.1 Why Tailor Modules per Business Unit?

1. **Elimination of UI Clutter:** Navigation sidebars and operational cockpits display only the tools relevant to the company's daily operations.
2. **Hardened Security & Compliance:** Disabling unused modules eliminates unneeded attack surface and prevents accidental creation of orphaned records.
3. **Zero Complexity Overhead:** Small teams can start with a lean procurement or trading setup and unlock advanced modules (like DRP or Capacity Planning) as business maturity evolves.

---

### 3.2 Using the Active Modules & Setup Console

1. In the sidebar, navigate to **Administration -> Configuration** (path `/configuration`).
2. Click on the tab titled **"Active Modules & Setup"** (represented by the layers icon).
3. The console displays:
   * **Current Active Count:** Displays how many of the 24 modules are active for your company (e.g., `11 of 24 modules active`).
   * **Industry Presets:** 5 one-click configuration cards with detailed workflow breakdowns.
   * **Granular Module Checklist:** Interactive toggles grouped by business domain.

![Active Modules & Setup Console](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/frontend/src/routes/configuration.tsx)

---

### 3.3 Selecting One-Click Industry Presets

Simple ERP provides five certified presets that match common commercial operating models:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        INDUSTRY PRESET MATRIX                          │
├──────────────────────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┤
│ Preset Name          │ SCM │ PR  │ WMS │ MFG │ SLS │ FIN │ SEC │ ADM │
├──────────────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ 1. Trading & Dist.   │  –  │  ✓  │  ✓  │  –  │  ✓  │  ✓  │  ✓  │  ✓  │
│ 2. Discrete Mfg.     │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │
│ 3. Logistics 3PL     │  –  │  –  │  ✓  │  –  │  –  │  –  │  ✓  │  ✓  │
│ 4. Lean Procurement  │  –  │  ✓  │  –  │  –  │  –  │  ✓  │  ✓  │  ✓  │
│ 5. Full Enterprise   │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │
└──────────────────────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

#### Preset 1: Trading & Distribution
* **Best For:** Wholesale distributors, importers, B2B trading houses, retail suppliers.
* **Active Domains:** Procurement, Inventory, Quality Receiving, Sales Orders, Logistics TMS, Statutory e-Way Bills, Accounts Payable/Receivable, Finance Invoicing.
* **Excluded:** MRP Planning, Production Runs, Subcontracting, Traceability, Capacity Planning.

#### Preset 2: Discrete Manufacturing & Assembly
* **Best For:** Automotive component makers, electronics manufacturers, machine builders, fabricated metal plants.
* **Active Domains:** Full Suite with heavy emphasis on Multi-Level BOMs, MRP Planning, Production Orders, In-Process QC, Subcontracting, Batch Traceability, and Landed Cost accounting.

#### Preset 3: Logistics 3PL & Fulfillment Hub
* **Best For:** Warehousing service providers, freight forwarders, fulfillment centers.
* **Active Domains:** Directed Putaway & Bins, WMS Mobile Scanning, Wave & Batch Picking, Shipping Engine, Carrier RFQs, Transport Management (TMS), Statutory Logistics (e-Way Bills).

#### Preset 4: Lean SCM / Pure Procurement
* **Best For:** Corporate purchasing departments, shared service centers, trading desks.
* **Active Domains:** Purchase Requisitions, Manager Approvals, Sourcing RFQs, Supplier Directory, Approved Vendor List (AVL) Governance, Blanket POs, Vendor Invoicing.

#### Preset 5: Enterprise Full Suite
* **Best For:** Vertically integrated conglomerates operating end-to-end supply chains from raw material sourcing and manufacturing to warehousing and omni-channel distribution.
* **Active Domains:** All 24 modules enabled simultaneously.

---

### 3.4 Granular 24-Module Registry & Dependency Graph

When configuring modules manually, the system enforces functional dependencies to prevent system anomalies:

```mermaid
graph TD
    PRD[Product Catalog & BOM] --> MRP[MRP Planning]
    PRD --> WMS[Inventory & Warehouse]
    PRD --> PROD[Production Assembly]
    MRP --> PROD
    PROD --> TRACE[Batch Traceability]
    PROD --> IPQC[Quality IPQC]
    PROD --> SUBC[Subcontracting]
    WMS --> BINS[Directed Putaway & Bins]
    WMS --> WAVE[Wave Picking]
    WMS --> SCAN[WMS Mobile Scanner]
    PO[Procurement & POs] --> GRN[GRN & Receiving]
    GRN --> FIN[Finance & 3-Way Match]
    ORD[Sales Orders] --> SHIP[Shipping & Logistics]
    SHIP --> EWBL[Statutory e-Way Bills]
    ORD --> FIN
```

* **Core Foundation (Always Required):** `control_tower`, `configuration`, `users_roles`, `audit_trail` cannot be disabled.
* **Manufacturing Dependency:** Enabling `production` requires `products_catalog` and `procurement` to be active.
* **WMS Dependency:** Enabling `wms_bins`, `wms_mobile`, or `wave_picking` requires `inventory` and `warehouse_grn`.
* **Finance Dependency:** Enabling `finance` requires at least `procurement` or `sales_orders` to be enabled for ledger postings.

Clicking **"Save Active Modules"** immediately applies the selection. The web shell dynamically re-renders the navigation sidebar (`visibleNav`), while backend routes enforce permission checks and URL guards (`ModuleGuard`).

---

### 3.5 API-Driven Configuration

For automated tenant provisioning scripts, module selections can be retrieved and updated via REST API:

```http
# Fetch current active modules
GET /api/v1/tenant/modules
Authorization: Bearer <ADMIN_JWT_TOKEN>

# Response:
{
  "tenantId": "d3b07384-d113-4966-bf52-78d1be30925e",
  "activeModules": [
    "control_tower", "procurement", "inventory", "warehouse_grn",
    "sales_orders", "finance", "products_catalog", "configuration",
    "users_roles", "audit_trail", "statutory_logistics"
  ],
  "availableModules": [ ... 24 module specifications ... ],
  "industryPresets": [ ... 5 preset specifications ... ]
}
```

```http
# Update active modules (Trading & Distribution preset)
PUT /api/v1/tenant/modules
Authorization: Bearer <ADMIN_JWT_TOKEN>
Content-Type: application/json

{
  "modules": [
    "control_tower", "procurement", "inventory", "warehouse_grn",
    "sales_orders", "finance", "products_catalog", "configuration",
    "users_roles", "audit_trail", "statutory_logistics", "logistics_tms"
  ]
}
```

---

## 4. Phase 3: Legal Company & Statutory Profile Setup

Once the software modules are tailored, you must configure the official legal entity (or entities) that will conduct commercial operations.

### 4.1 Defining Business Entities (`/po-invoice`)

1. In the sidebar, navigate to **Finance -> PO & Invoice** (path `/po-invoice`).
2. Click **New business entity** (requires permission `org:write`).
3. Fill in the statutory details in the modal dialog:
   * **Entity Name (Required):** The legal registered name as per the Certificate of Incorporation (e.g., `Acme Advanced Materials Private Limited`).
   * **Entity Code:** A unique short code (e.g., `ENT-001`, or leave blank to auto-generate).
   * **Default Entity Toggle:** Turn ON **Set as default entity** if this is the primary legal entity for purchase orders and tax invoices.
   * **Address Line 1 & Line 2:** The official registered office address.
   * **City & Postal PIN Code:** Municipal location and 6-digit postal PIN code.
   * **State & Country:** Select the official Indian state (e.g., `27 — Maharashtra`) and Country (`IN`).

---

### 4.2 Statutory Tax & Regulatory Setup (GSTIN, PAN, State Codes)

The statutory fields entered here govern the legal compliance of all outbound documents:

1. **Tax ID / GSTIN:** Enter the 15-character Goods and Services Tax Identification Number (e.g., `27AABCA1234A1Z5`):
   * Characters 1–2: State Code (`27` = Maharashtra).
   * Characters 3–12: Company PAN (`AABCA1234A`).
   * Character 13: Entity number of the same PAN in the state (`1`).
   * Character 14: Default alphabet (`Z`).
   * Character 15: Checksum digit (`5`).
2. **Company PAN:** Enter the 10-character Permanent Account Number.
3. **Official Contact Email:** Accounts department email printed on invoices for billing queries (e.g., `billing@acme.com`).
4. **Official Contact Phone:** Corporate finance telephone number.

---

### 4.3 Corporate Remittance Banking Rails

The banking information configured here is automatically rendered on the footer of all customer tax invoices and sales orders, instructing customers where to remit electronic payments (NEFT/RTGS/IMPS):

* **Bank Name:** Commercial bank (e.g., `HDFC Bank Limited`).
* **Branch Name:** Commercial branch locality (e.g., `Nariman Point, Mumbai`).
* **Account Number:** Current Account number (e.g., `50200012345678`).
* **IFSC Code:** 11-character Indian Financial System Code (e.g., `HDFC0000123`).

Click **Create business entity** to commit the record.

---

### 4.4 Multi-Entity & Multi-GSTIN Architectures

If your company operates across multiple Indian states (e.g., a factory in Maharashtra and a distribution warehouse in Karnataka) or operates multiple business verticals:

1. Repeat the creation process for each state GSTIN (e.g., create `ENT-002` for the Karnataka branch with GSTIN `29AABCA1234A1Z8`).
2. When creating purchase orders or issuing sales invoices, the user selects which legal entity is the contracting party.
3. Simple ERP automatically applies intra-state CGST+SGST or inter-state IGST tax calculations based on the originating Business Entity GSTIN and the delivery/destination Party GSTIN.

---

### 4.5 Bulk Entity Ingestion via CSV

For multi-entity holding companies, use the bulk upload facility:
1. In `/po-invoice`, click **Bulk Upload**.
2. Upload a UTF-8 encoded CSV matching the specification below:

```csv
name,code,addressLine1,city,stateCode,postalCode,country,taxId,pan,bankName,bankAccountNumber,bankIfsc,isDefault
Acme Materials Pvt Ltd,ENT-001,Plot 42 MIDC,Pune,27,411018,IN,27AABCA1234A1Z5,AABCA1234A,HDFC Bank,50200012345678,HDFC0000123,true
Acme Logistics LLP,ENT-002,Peenya Ind Area,Bengaluru,29,560058,IN,29AABCA1234A1Z8,AABCA1234A,ICICI Bank,000205001234,ICIC0000002,false
```

---

## 5. Phase 4: Physical Topography & Storage Topography Commissioning

Before receiving goods or recording stock balances, you must model your physical infrastructure: manufacturing plants, warehouses, and storage bins.

### 5.1 Commissioning Manufacturing Plants & Factories (`/factory-warehouse`)

1. In the sidebar, navigate to **Administration -> Factory & Warehouse** (path `/factory-warehouse`).
2. Click on the **Factories** tab.
3. Click **New factory** (requires `org:write`).
4. Enter the plant attributes:
   * **Factory Name:** (e.g., `Chakan Manufacturing Plant 1`).
   * **Factory Code:** (e.g., `FAC-001`).
   * **Address & Location:** Street address, city, state, postal PIN code.
   * **Capacity Units:** Rated throughput units per month.
   * **Notes:** Operational shifts, safety protocols, or site contacts.
5. Click **Create factory**.

---

### 5.2 Commissioning Warehouses & Distribution Centers

1. In `/factory-warehouse`, switch to the **Warehouses** tab.
2. Click **New warehouse**.
3. Configure the warehouse attributes:
   * **Warehouse Name:** (e.g., `Central Finished Goods Warehouse`).
   * **Warehouse Code:** (e.g., `WH-001`).
   * **Associated Factory:** (Optional) Select the parent factory if this warehouse is co-located with a production plant. Leave blank for standalone distribution centers.
   * **Allowed Product Types:** Select the inventory types permitted in this warehouse: `raw_material`, `wip`, `finished_goods`, `consumable`. Restricting types prevents production operators from mistakenly shipping unfinished goods to a trading depot.
   * **Address & Contact:** Warehouse location and email of the warehouse manager.
4. Click **Create warehouse**.

---

### 5.3 Automated Quarantine and Inbound Locations

> [!IMPORTANT]
> When any warehouse is created in Simple ERP, the system **automatically provisions an active quarantine storage location** ([warehouses/router.py#L112-L116](file:///Users/Peeyush/Documents/Programming Prep/Simple ERP/backend/app/domains/warehouses/router.py#L112-L116)):
> * Location Code: `QUARANTINE`
> * Location Name: `Quarantine hold`
> * Location Type: `quarantine`
>
> All rejected materials from Goods Receipt Note (GRN) quality inspections and Returned Material Authorizations (RMA) are automatically routed into this quarantine location, sequestering them from available-to-promise inventory.

---

### 5.4 Commissioning WMS Storage Topography: Zones, Racks & Bins (`/wms-bins`)

If your company uses the Directed Putaway & Bins module (`wms_bins`):

1. Navigate to **Warehouse & Logistics -> Directed Putaway & Bins** (path `/wms-bins`).
2. Model the storage hierarchy:
   * **Zones:** Define functional areas (e.g., `ZONE-FAST` for fast-moving picking, `ZONE-BULK` for pallet racking, `ZONE-COLD` for temperature-controlled storage).
   * **Aisles, Racks & Shelves:** Specify physical coordinates (e.g., Aisle 04, Rack B, Shelf 02).
   * **Bins:** Define discrete storage locations (e.g., `BIN-A04-B02-01`):
     * Capacity limit in kilograms or cubic meters.
     * Pick sequence weighting (for optimizing wave-picking travel paths).
3. Click **Generate Bin Labels** to produce 2D DataMatrix/QR barcode labels for physical rack labeling.

---

### 5.5 Bulk Warehouse & Factory CSV Import

For enterprises with dozens of regional depots, import them via CSV:

```csv
# Warehouses bulk upload (POST /api/v1/warehouses/bulk-upload)
name,code,addressLine1,city,stateCode,postalCode,country,contactEmail,allowedProductTypes
Central Raw Materials WH,WH-001,Plot 12 Chakan,Pune,27,410501,IN,wh-pune@acme.com,raw_material|consumable
Finished Goods Hub,WH-002,Warehouse Zone 4,Bhiwandi,27,421302,IN,wh-bhiwandi@acme.com,finished_goods
```

---

## 6. Phase 5: Master Data Migration & Catalog Setup

Master data is the foundation of day-to-day transactional integrity. Ensure all legacy data is cleansed prior to loading.

### 6.1 Product Categories, Tax Slabs & Units of Measure (`/configuration`)

1. Navigate to **Administration -> Configuration** (path `/configuration`).
2. **Product Categories:** Create business categories (e.g., `Active Pharmaceutical Ingredients`, `Packaging Materials`, `Fasteners & Hardware`, `Finished Assemblies`).
3. **Harmonized System of Nomenclature (HSN/SAC):** Map HSN codes to standard GST tax slabs (e.g., HSN `8471` at 18%, HSN `7318` at 18%, HSN `3004` at 12%).
4. **Units of Measure (UOM):** Confirm standard base UOMs (`pcs`, `kg`, `meter`, `liter`, `box`, `roll`).

---

### 6.2 Product Catalog & Stock Definitions (`/products`)

1. Navigate to **Master Data -> Products & BOM Catalog** (path `/products`).
2. Click **New product** (requires `product:write`).
3. Configure the item attributes:
   * **Product Name:** Standard commercial name.
   * **SKU / Code:** Unique item master code (e.g., `RM-ST-001`).
   * **Product Type:** `raw_material`, `wip`, `finished_goods`, `consumable`, or `service`.
   * **Category & Base UOM:** Primary classification and unit of measure.
   * **HSN Code & GST Rate:** Statutory classification and default tax rate.
   * **Tracking Controls:**
     * **Batch Tracked (`is_batch_tracked`):** Turn ON for materials requiring lot numbers, mill test certificates, or batch genealogy.
     * **Expiry Tracked (`is_expiry_tracked`):** Turn ON for perishable or shelf-life-limited goods (enables First-Expired-First-Out / FEFO picking).
   * **Inventory Replenishment:** Safety stock threshold, reorder point, and standard vendor lead time in days.

---

### 6.3 Bills of Materials (BOM) & Routing Operations

For manufacturing operations:
1. In `/products`, switch to the **Bills of Materials** tab.
2. Click **New BOM**.
3. Select the target **Finished Good** or **WIP Sub-assembly**.
4. Define the recipe:
   * **Components:** Add raw material SKUs and required quantities per 1.0 unit of finished output.
   * **Scrap Allowance:** Enter standard component shrinkage or scrap percentage (e.g., 2.5%).
   * **Operations & Work Centers:** Assign routing operations (e.g., Laser Cutting -> CNC Bending -> Powder Coating -> Final Assembly) and standard labor cycle times.
5. Save the BOM in **Active** status.

---

### 6.4 Vendor Onboarding & AVL Qualification (`/parties`, `/avl-governance`)

1. Navigate to **Procurement -> Parties** (path `/parties`).
2. Click **New party** and select **Vendor**.
3. Enter commercial details:
   * **Legal Business Name:** Official supplier name.
   * **Party Code:** (e.g., `VND-001`).
   * **GSTIN & PAN:** Mandatory for tax invoice matching and input tax credit (ITC) reconciliation.
   * **Payment Terms:** Standard agreed terms (e.g., `Net 30`, `Net 45`, `Advance`, `Immediate`).
   * **Remittance Bank Account & IFSC:** For automated Accounts Payable disbursements.
   * **MSME Status:** Specify enterprise tier (`Micro`, `Small`, `Medium`, `Not Applicable`) to comply with statutory 45-day payment timelines.
4. **Approved Vendor List (AVL) Qualification (`/avl-governance`):**
   * Link the vendor to authorized product categories.
   * Assign qualification status (`Qualified`, `Probationary`, `Blacklisted`). Non-qualified vendors cannot be selected for RFQ awards or purchase orders.

---

### 6.5 Customer Master & Commercial Terms (`/parties`)

1. In `/parties`, click **New party** and select **Customer**.
2. Enter commercial details:
   * **Customer Legal Name:** Corporate or individual name.
   * **Billing Address & Shipping Address:** Separate addresses for multi-location deliveries.
   * **GSTIN & PAN:** For B2B e-Invoicing.
   * **Credit Limit:** Maximum outstanding receivables balance permitted (e.g., ₹5,000,000). The sales order engine will block confirmation if an order breaches this threshold.
   * **Default Price List & Payment Terms:** Agreed pricing tier and payment cycle.

---

### 6.6 Bulk Master Data Migration Pipelines

To import tens of thousands of legacy SKUs and counterparties, use Simple ERP's high-speed bulk ingestion endpoints:

```
Legacy ERP / Excel
       │
       ▼ (Cleanse & Transform)
UTF-8 Standard CSV Files
       │
       ├─► POST /api/v1/products/bulk-upload
       ├─► POST /api/v1/boms/bulk-upload
       ├─► POST /api/v1/parties/bulk-upload
       └─► POST /api/v1/avl-governance/bulk-upload
```

*(See [Section 10.1](#101-csv-specifications-reference) for comprehensive CSV column templates).*

---

## 7. Phase 6: Team, Roles & Multi-Site Scoping (RBAC)

Secure the application by establishing user accounts, role-based access controls, approval hierarchies, and physical site restrictions.

### 7.1 User Provisioning & Invitation Lifecycles (`/users`)

1. Navigate to **Administration -> Users & Roles** (path `/users`).
2. Click **Invite user** (requires `user:write`).
3. Fill in the user profile:
   * **Full Name:** (e.g., `Rajesh Kumar`).
   * **Work Email:** (e.g., `rajesh.kumar@acme.com`).
   * **Department:** (e.g., `Procurement`, `Warehouse Operations`, `Plant Finance`).
4. The system sends an email invitation with a secure, one-time activation token.

---

### 7.2 Role Assignment & System Permissions

Simple ERP ships with 10 hardened, production-ready system roles:

| System Role | Functional Scope | Key Permissions Included |
|---|---|---|
| **System Admin** | Global configuration, security & auditing | `*:*` (Full administrative authority) |
| **Warehouse Manager** | Inventory, stock adjustments, GRN QC & dispatch | `warehouse:*`, `inventory:*`, `grn:*`, `shipping:*` |
| **Warehouse Operator** | Putaway, bin transfers, mobile scanning, picking | `warehouse:read`, `inventory:read`, `wms:*` |
| **Purchase Manager** | Procurement approvals, RFQ awards, blanket POs | `po:*`, `pr:*`, `sourcing:*`, `avl:*` |
| **Buyer** | Purchase requisitions, RFQs, PO draft generation | `pr:write`, `sourcing:write`, `po:write` |
| **Production Manager**| Work orders, BOM execution, capacity planning | `production:*`, `bom:*`, `quality:*` |
| **Quality Inspector** | Inbound GRN QC, in-process QC, CoA certification | `grn:qc`, `quality:ipqc` |
| **Sales Manager** | Customer quotes, sales orders, credit overrides | `orders:*`, `party:read` |
| **Finance Manager** | Invoicing, AP/AR 3-way match, ledger payments | `invoice:*`, `payment:*`, `finance:*` |
| **Transporter** | Shipment vehicle details, LR/docket updates | `logistics:transporter`, `shipping:read` |

---

### 7.3 Managerial Approval Routing ("Reports To")

To prevent unauthorized corporate expenditures, Simple ERP enforces a strict dual-level approval workflow on Purchase Requisitions:

```
[Employee creates Requisition]
             │
             ▼
  [Status: "With manager"]
             │
      (Manager Approves)
             │
             ▼
  [Status: "With Purchase"]
             │
      (Purchase Approves)
             │
             ▼
[Approved -> Sourcing / PO Raised]
```

1. In `/users`, open a user's record and click **Manage roles**.
2. Locate the **Reports to** dropdown.
3. Select the user's direct line manager (e.g., assign `Vikram Mehta` as manager for `Rajesh Kumar`).
4. When `Rajesh Kumar` submits a purchase requisition, it is automatically routed to `Vikram Mehta` first. Purchase department buyers cannot see or act upon the requisition until the direct manager has formally approved it.

---

### 7.4 Site Scoping (Facility-Level Data Isolation)

In multi-plant or multi-warehouse enterprises, operators at Plant A must not accidentally view, alter, or allocate stock residing at Plant B:

1. In `/users`, select a user and click **Scope facilities**.
2. **Warehouse Scoping (`whIds`):** Check only the specific warehouses the user is authorized to manage (e.g., restrict a receiving clerk strictly to `WH-001`).
3. **Factory Scoping (`facIds`):** Check only the specific production plants the user is authorized to view.
4. **Enforcement:** Once scoped, all dropdown pickers, stock balances, GRN receiving screens, and dispatch consoles throughout Simple ERP are strictly restricted to the authorized facility IDs.

---

### 7.5 Authentication Policies & MFA Enforcement (`/profile`)

1. **Multi-Factor Authentication (MFA / TOTP):**
   * Each user navigates to **User Profile** (path `/profile`).
   * Under **Two-Factor Authentication**, click **Enable MFA**.
   * Scan the QR code using Google Authenticator, Microsoft Authenticator, or 1Password, and enter the 6-digit TOTP code.
2. **Tenant AuthPolicy Enforcement:**
   * System Administrators can mandate MFA globally across the tenant in `AuthPolicy`, requiring all users to complete MFA enrollment prior to accessing operational modules.

---

## 8. Phase 7: Communications, Statutory Gateways & Hardware Setup

Configure external integrations to automate document dispatch and legal compliance.

### 8.1 Outbound SMTP Mailbox Routing (`/email-config`)

Simple ERP allows different operational departments to send outbound transactional communications from distinct, specialized corporate mailboxes:

1. Navigate to **Foundation -> Email Config** (path `/email-config`).
2. Configure dedicated mailboxes across five independent communication channels:
   * **Purchase Orders:** Outbound PO delivery to suppliers (e.g., `procurement@acme.com`).
   * **Sourcing RFQs:** Quotation requests sent to vendors (e.g., `sourcing@acme.com`).
   * **Customer Invoices:** Official tax invoice PDFs sent to customers (e.g., `billing@acme.com`).
   * **Dispatch Notices:** Shipment notifications with tracking and e-Way bills (e.g., `logistics@acme.com`).
   * **User Invitations:** Team access and password reset emails (e.g., `security@acme.com`).
3. For each channel:
   * Enter the SMTP server hostname (e.g., `smtp.gmail.com`, `email-smtp.us-east-1.amazonaws.com`).
   * Enter port (`587` for STARTTLS, `465` for SSL/TLS).
   * Enter SMTP username and secure app password.
   * Click **Save**, then click **Send test email** to verify live connectivity.

---

### 8.2 Statutory Logistics Gateways: NIC e-Way Bills & e-Invoicing (`/statutory-logistics`)

Under Indian GST regulations, movement of goods exceeding ₹50,000 requires a statutory **e-Way Bill**, and B2B invoices must be registered on the **Invoice Registration Portal (IRN)**:

1. Navigate to **Warehouse & Logistics -> Statutory Logistics** (path `/statutory-logistics`).
2. Enter your **GSP (GST Suvidha Provider)** or direct **NIC API credentials**:
   * API Client ID & Client Secret.
   * NIC User ID & Production Password.
3. Once authenticated:
   * **Automated e-Way Bills:** When recording a dispatch, clicking **Generate e-Way Bill** transmits vehicle and consignment details directly to the government portal and stamps the 12-digit e-Way Bill number and validity date onto the shipping document.
   * **Automated e-Invoices:** Finalized sales invoices automatically receive a 64-character IRN hash and a government-signed QR code rendered directly onto the invoice PDF.

---

### 8.3 Thermal Barcode & Label Sizing (`/configuration`)

To ensure barcode readability on industrial thermal printers:
1. Navigate to **Administration -> Configuration** (path `/configuration`).
2. Open the **Sticker Sizes** tab.
3. Configure physical label geometries matching your warehouse printer stock:
   * **Small Bin Label:** `50mm x 25mm` (DataMatrix 2D barcode + Bin code).
   * **Pallet / GRN Label:** `100mm x 50mm` (1D Code-128 barcode + SKU + Batch + Expiry).
   * **Shipping Box Label:** `100mm x 150mm` (`4" x 6"` standard logistics label with e-Way Bill QR and address block).

---

### 8.4 Mobile Handheld Scanners & WMS Setup (`/wms-mobile`)

For warehouse terminal operators using Android barcode guns (Zebra, Honeywell, Datalogic):
1. Handheld scanners connect via standard web browser to `https://erp.yourcompany.com/wms-mobile`.
2. The UI switches to high-contrast, large-touch-target cards optimized for single-handed barcode scanning:
   * Scan Bin Barcode -> Scan Product Barcode -> Enter Received Quantity -> Auto-Confirm.

---

## 9. Phase 8: Opening Balances, Cutover & Go-Live Protocol

The final phase transitions the company from legacy systems to live execution on Simple ERP.

### 9.1 Pre-Cutover Freeze Protocol

1. **Cutover Date & Time:** Establish a hard transactional freeze window (typically Friday 6:00 PM to Sunday midnight).
2. **Legacy Freezes:**
   * Stop all sales order entry in the legacy system.
   * Complete all in-flight physical receipts and finish goods dispatches.
   * Conduct a physical wall-to-wall stock count across all warehouses.

---

### 9.2 Opening Stock Balance Ingestion & Ledger Validation (`/inventory`)

Opening inventory must be ingested as **Physical Inventory Adjustments** with exact batch, location, and unit cost valuation:

1. Prepare the Opening Stock CSV file matching the schema below:

```csv
# Opening Stock Adjustment CSV
warehouseCode,locationCode,sku,quantity,unitCost,batchNumber,manufacturingDate,expiryDate,reason
WH-001,ZONE-A01-01,RM-ST-001,1500.000,45.50,BATCH-202611-01,2026-11-01,2028-11-01,Opening Balance Cutover
WH-001,ZONE-A01-02,RM-AL-002,320.000,185.00,BATCH-202611-02,2026-11-01,2029-11-01,Opening Balance Cutover
WH-002,ZONE-FG-01,FG-MTR-01,85.000,1250.00,LOT-OCT26-09,2026-10-15,,Opening Balance Cutover
```

2. Post the opening balance CSV via REST API or using the UI Import tool:
   * Endpoint: `POST /api/v1/inventory/adjustments/bulk-upload`
3. **Ledger Verification:**
   * Navigate to **Warehouse & Logistics -> Inventory Balances** (`/inventory`).
   * Verify total on-hand quantities match physical stock count sheets exactly.
   * Open the **Ledger** tab and confirm initial ledger entries are marked with reason `"Opening Balance Cutover"`.

---

### 9.3 Open Purchase Orders & In-Flight Sourcing Migration

For existing supplier orders placed prior to cutover that will be received in Simple ERP:
1. Prepare an Open Purchase Orders CSV.
2. Ingest via `POST /api/v1/purchase-orders/bulk-upload`.
3. Set order status to `confirmed` so that warehouse receiving teams can immediately generate Goods Receipt Notes (GRN) upon delivery.

---

### 9.4 Open Sales Orders & Fulfillment Migration

For confirmed customer orders awaiting fulfillment:
1. Ingest via `POST /api/v1/orders/bulk-upload`.
2. Confirm orders so they appear immediately in the **Sales Orders Book** (`/orders`) ready for warehouse stock allocation and dispatch.

---

### 9.5 Accounts Payable & Receivable Opening Positions (`/finance`)

1. In **Finance -> PO & Invoice / Finance** (`/finance`), record opening invoices for outstanding AP balances owed to suppliers.
2. Record opening receivables for unpaid customer balances.
3. Validate total opening AP and AR against the legacy general ledger trial balance.

---

### 9.6 End-to-End "Golden Flow" Validation Run

Before opening the system to general users on Monday morning, the implementation team must execute one complete end-to-end "Golden Flow" test transaction:

```
1. Create Test Purchase Requisition (Employee)
   └─► 2. Manager Approval (Manager)
       └─► 3. PO Creation & Vendor Issuance (Purchase)
           └─► 4. Inbound GRN Receipt & Thermal QR Print (Warehouse)
               └─► 5. Quality Inspection & QC Acceptance (Quality)
                   └─► 6. Putaway to Bin Storage (WMS)
                       └─► 7. Sales Order Entry & Stock Allocation (Sales)
                           └─► 8. Pick, Pack & Dispatch with e-Way Bill (Logistics)
                               └─► 9. Customer Tax Invoice Generation (Finance)
                                   └─► 10. Payment Receipt & Ledger Reconciliation (Finance)
```

Confirm that every transition completes cleanly without errors, audit logs are correctly populated, and PDF documents render with accurate statutory headers and bank details.

---

### 9.7 Formal Go-Live Sign-Off Checklist

- [ ] **Infrastructure:** Docker containers healthy, Postgres backups automated, Redis caching operational.
- [ ] **Security:** Bootstrap admin password changed; user accounts provisioned; MFA enforced for finance/admin roles.
- [ ] **Site Scoping:** All warehouse and factory personnel restricted to their assigned facilities.
- [ ] **Master Data:** SKUs, BOMs, vendors, and customers fully reconciled and locked.
- [ ] **Stock Balances:** Opening inventory verified against signed physical count sheets.
- [ ] **Statutory Gateways:** NIC e-Way bill and SMTP email connections validated.
- [ ] **Executive Sign-Off:** Written sign-off executed by Chief Financial Officer (CFO), Head of Supply Chain, and Implementation Lead.
- [ ] **System Status:** Announce Simple ERP is **LIVE for Production Operations**.

---

## 10. Appendix: Master Data CSV Templates, Schemas & Troubleshooting

### 10.1 CSV Specifications Reference

All CSV files imported into Simple ERP must be UTF-8 encoded with standard comma separators.

#### 1. Business Entities CSV (`/api/v1/business-entities/bulk-upload`)
| Column Name | Type | Required | Description / Example |
|---|---|---|---|
| `name` | String | **Yes** | `Acme Technologies Pvt Ltd` |
| `code` | String | No | `ENT-001` (Auto-generated if empty) |
| `addressLine1` | String | No | `Plot 42 MIDC Industrial Area` |
| `city` | String | No | `Pune` |
| `stateCode` | String | No | `27` (2-digit Indian GST State Code) |
| `postalCode` | String | No | `411018` |
| `country` | String | No | `IN` (Default) |
| `taxId` | String | No | `27AABCA1234A1Z5` (15-character GSTIN) |
| `pan` | String | No | `AABCA1234A` (10-character PAN) |
| `bankName` | String | No | `HDFC Bank` |
| `bankAccountNumber` | String | No | `50200012345678` |
| `bankIfsc` | String | No | `HDFC0000123` |
| `isDefault` | Boolean | No | `true` or `false` |

#### 2. Warehouses CSV (`/api/v1/warehouses/bulk-upload`)
| Column Name | Type | Required | Description / Example |
|---|---|---|---|
| `name` | String | **Yes** | `Bhiwandi Central Fulfillment Depot` |
| `code` | String | No | `WH-BHW-01` |
| `city` | String | No | `Bhiwandi` |
| `stateCode` | String | No | `27` |
| `postalCode` | String | No | `421302` |
| `country` | String | No | `IN` |
| `contactEmail` | String | No | `wh-bhiwandi@acme.com` |
| `allowedProductTypes` | Pipe-delimited | No | `raw_material\|wip\|finished_goods` |

#### 3. Products Catalog CSV (`/api/v1/products/bulk-upload`)
| Column Name | Type | Required | Description / Example |
|---|---|---|---|
| `name` | String | **Yes** | `Hex M8 Stainless Steel Bolt` |
| `code` | String | **Yes** | `RM-BLT-M8-SS` |
| `type` | Enum | **Yes** | `raw_material`, `wip`, `finished_goods`, `consumable` |
| `category` | String | No | `Fasteners` |
| `uom` | String | **Yes** | `pcs`, `kg`, `meter` |
| `hsn` | String | No | `7318` |
| `taxRate` | Numeric | No | `18.00` |
| `isBatchTracked` | Boolean | No | `true` or `false` |
| `isExpiryTracked` | Boolean | No | `true` or `false` |

---

### 10.2 Common Onboarding Pitfalls & Remediation

| Issue Encountered | Root Cause | Remediation Protocol |
|---|---|---|
| **GSTIN Format Validation Error** | Invalid state code or checksum digit in the 15-character GSTIN string. | Verify GSTIN on the official GST Portal (`services.gst.gov.in`). Ensure state code (first 2 digits) matches `stateCode`. |
| **User Sees Blank Sidebar / Empty Screens** | User's assigned role lacks read permissions, or user is scoped to a facility that has no data. | Check `/users` -> **Manage roles** to ensure appropriate roles (`inventory:read`, `po:read`, etc.) and verify **Scope facilities** settings. |
| **Modules Missing from Navigation** | The module was toggled off during Phase 2 setup. | Navigate to `/configuration` -> **Active Modules & Setup** as an administrator and enable the required module. |
| **Opening Stock Upload Fails** | Warehouse code or location code does not exist in master records. | Commission the warehouse and putaway bins in `/factory-warehouse` and `/wms-bins` before running stock adjustments. |
| **Outbound Email Failure** | SMTP authentication blocked (e.g., Google Workspace blocking less secure apps). | Generate a dedicated 16-character **Google App Password** (under Google Account Security -> 2-Step Verification) and ensure `SMTP_FROM` matches `SMTP_USER`. |

---

### 10.3 Tenant Data Reset & Emergency Rollback Procedures

If a test migration goes awry during pre-cutover testing and you must wipe all operational records while preserving master configuration:

```bash
# Connect to PostgreSQL container
docker compose exec postgres psql -U simple_app -d simple_erp

-- TRUNCATE TRANSACTIONAL TABLES ONLY (Preserving Users, Tenants, Roles & Settings):
BEGIN;
TRUNCATE TABLE inventory_adjustments CASCADE;
TRUNCATE TABLE inventory_transfers CASCADE;
TRUNCATE TABLE inventory_ledgers CASCADE;
TRUNCATE TABLE inventory_lots CASCADE;
TRUNCATE TABLE goods_receipt_notes CASCADE;
TRUNCATE TABLE purchase_orders CASCADE;
TRUNCATE TABLE purchase_requisitions CASCADE;
TRUNCATE TABLE purchase_rfqs CASCADE;
TRUNCATE TABLE sales_orders CASCADE;
TRUNCATE TABLE invoices CASCADE;
TRUNCATE TABLE payments CASCADE;
COMMIT;
```

Once truncated, the opening balance migration (Phase 8) can be re-run with cleansed data.

---

*Simple ERP Enterprise Edition — Documentation maintained by the Systems & Engineering Core Team.*
