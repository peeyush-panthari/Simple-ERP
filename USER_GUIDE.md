# Simple ERP | Module User Guide & FAQs

**A practical, screen-by-screen manual for everyday use of the Simple ERP system — what each screen is for, how to reach it, and how to complete the tasks it supports.**

*Version:* 2.4.0 Enterprise Edition  
*Date of Revision:* October 2026  
*Status:* Complete Operational Reference Manual

---

## Table of Contents

1. [Platform Architecture & Navigation Overview](#1-platform-architecture-navigation-overview)
2. [Login & Authentication (`/login`)](#2-login-authentication)
3. [Dashboard (Control Tower) (`/`)](#3-dashboard-control-tower)
4. [Parties: Vendors, Customers & Transporters (`/parties`)](#4-parties-vendors-customers-transporters)
5. [Product Catalog & Bill of Materials (BOM) (`/products`)](#5-product-catalog-bill-of-materials-bom)
6. [Procurement: Purchase Orders (`/procurement`)](#6-procurement-purchase-orders)
7. [Inventory: Stock Balances, Ledger & Item Detail (`/inventory`)](#7-inventory-stock-balances-ledger-item-detail)
8. [GRN & QC: Goods Receipt Notes, Quality Control & QR Labels (`/warehouse`)](#8-grn-qc-goods-receipt-notes-quality-control-qr-labels)
9. [Factory & Warehouse Setup (`/factory-warehouse`) [EXPANDED MODULE]](#9-factory-warehouse-setup)
10. [Production, BOM Execution & Finished Goods Allocation (`/production`)](#10-production-bom-execution-finished-goods-allocation)
11. [Sales Orders: Intake & Sales Book (`/orders`)](#11-sales-orders-intake-sales-book)
12. [Logistics: Transport, Carrier RFQ & Dispatch (`/logistics`)](#12-logistics-transport-carrier-rfq-dispatch)
13. [Finance: Payables, Receivables, Invoicing & Payments (`/finance`)](#13-finance-payables-receivables-invoicing-payments)
14. [PO & Invoice: Business Entities & Seller Identity Setup (`/po-invoice`) [EXPANDED MODULE]](#14-po-invoice-business-entities-seller-identity-setup)
15. [Configuration: Categories, Party Types & Sticker Sizes (`/configuration`) [EXPANDED MODULE]](#15-configuration-categories-party-types-sticker-sizes)
16. [Users & Roles Administration (`/users`)](#16-users-roles-administration)
17. [Documents: Archive, Reprint & Storage (`/documents`)](#17-documents-archive-reprint-storage)
18. [Notifications: Delivery Log & Outbound Messaging (`/notifications`)](#18-notifications-delivery-log-outbound-messaging)
19. [Audit Trail: Compliance & Action Log (`/audit`)](#19-audit-trail-compliance-action-log)
20. [User Profile & Security (`/profile`)](#20-user-profile-security)
21. [General & Cross-Cutting FAQs](#21-general-cross-cutting-faqs)

---

## 1. Platform Architecture & Navigation Overview

Simple ERP is built around a secure, role-based access control (RBAC) model and enterprise site scoping (governing physical access to factories and warehouses). 

### Navigation Hierarchy
The system groups operational modules into business domains within the collapsible sidebar:
* **Overview & Analytics:** Control Tower (`/`), SC Control Tower (`/sc-control-tower`), System Status (`/architecture`).
* **Planning & SCM:** MRP Planning (`/mrp`), Multi-Echelon DRP (`/drp`), Demand Forecasting (`/forecasting`).
* **Procurement:** Purchase Orders & Requisitions (`/procurement`), Supplier Directory (`/parties`), Vendor Portal (`/vendor-portal`), Blanket POs (`/blanket-po`), Approved Vendor List (`/avl-governance`).
* **Warehouse & Logistics:** GRN & QC Receiving (`/warehouse`), Inventory Balances & Ledger (`/inventory`), Cycle Counting (`/cycle-counts`), Returns RMA/RTV (`/returns`), Landed Cost Tracking (`/landed-cost`), Directed Putaway & Bins (`/wms-bins`), Logistics TMS (`/logistics`), Statutory Logistics e-Way Bills (`/statutory-logistics`), Freight Consolidation (`/freight-tms`), WMS Mobile Scanner (`/wms-mobile`), Wave & Batch Picking (`/wave-picking`), Shipping Engine & AWBs (`/shipping-engine`).
* **Manufacturing & Operations:** Production Runs & Assembly (`/production`), Subcontracting (`/subcontracting`), Batch Traceability (`/traceability`), Quality IPQC & CoA (`/quality-ipqc`), Capacity Planning RCCP (`/capacity-planning`).
* **Sales & Orders:** Sales Orders Book & Allocation (`/orders`), Customer B2B Portal (`/customer-portal`).
* **Finance:** PO & Invoice Master Entities (`/po-invoice`), Finance AR/AP & Payments (`/finance`).
* **Administration & Master Data:** Products & BOM Catalog (`/products`), Factory & Warehouse (`/factory-warehouse`), Configuration (`/configuration`), Users & Roles (`/users`), Email Config (`/email-config`), Documents Archive (`/documents`), Notifications Log (`/notifications`), Audit Trail (`/audit`), Training Module (`/training`).

### Permissions Model
* **Sidebar Visibility:** The navigation bar strictly renders only the modules for which your user roles possess read permissions (e.g., `inventory:read`, `po:read`, `org:read`, `warehouse:read`, `product:read`). If a whole module is absent from your sidebar, your role is not assigned its read permission.
* **Action Buttons & Modals:** Write operations and high-stakes business functions are gated by granular sub-permissions (e.g., `party:write`, `party:block`, `po:short_close`, `po:cancel`, `invoice:post`, `payment:approve`). Without these specific permissions, buttons are either hidden or gracefully disabled.
* **Site Scoping (Multi-Facility Security):** When an administrator scopes a user's role assignment to specific factories or warehouses (configured in *Users & Roles*), all entity selectors, stock queries, receiving drop-downs, and dispatch filters throughout the ERP are automatically restricted to only those authorized facilities.

### Responsive & Mobile Adaptations
* **Desktop View:** Features dense, interactive data tables with column sorting, contextual action buttons, batch actions, and comprehensive multi-filter toolbars.
* **Mobile View:** On narrow touchscreens (smartphones and handheld warehouse terminals), tables automatically transform into stacked record cards (`MobileRecordCard`). A persistent bottom navigation bar surfaces the top four everyday workflows (*Control Tower*, *GRN & QC*, *Production*, *Orders*), accompanied by a "More" drawer granting access to the remainder of authorized modules.

---

## 2. Login & Authentication
`GETTING STARTED` • Route: `/login` • Access: Public / Auto-redirected

### Purpose
The sign-in screen is the front door to Simple ERP. It establishes who you are and, from that, which modules and buttons you will see everywhere else in the system. Every screen in the app checks your permissions before showing its content, and those permissions come from the session created here.

### How to Get There
You do not navigate to this screen deliberately — if you open Simple ERP without a valid session, you are sent here automatically. The address is `/login`. Once you are signed in, the app never shows this screen again unless you sign out or your session is fully invalidated.

### Layout Overview
* A centered card holds the Simple ERP logo, the heading **"Sign in"**, and a short line reminding you that your role determines which modules and actions are available.
* Below that is the sign-in form: an **Email** field, a **Password** field, and — only once the server tells the page it is needed — an **Authentication code** field for multi-factor authentication (MFA).
* If a sign-in attempt fails, a red banner appears above the button with the reason the server gave.
* The **Sign in** button reads *"Signing in…"* and disables itself while your credentials are being checked, so a second click cannot fire a duplicate request.

### Key Fields & What They Mean
* **Email:** Your account's registered email address. Required.
* **Password:** Your account password. Required.
* **Authentication code:** A 6-digit, numbers-only code from your authenticator app (TOTP). This field only appears after you submit a correct email and password for an account that has MFA enabled — it is not shown up front.

### Step-by-Step: Common Tasks

#### To sign in
1. Open Simple ERP in your browser — you will land on the Sign in screen if you are not already signed in.
2. Enter your **Email** and **Password**.
3. Click **Sign in**.
4. If your account does not use MFA, you are taken straight to the Control Tower (the home dashboard).

#### To sign in with multi-factor authentication
1. Enter your **Email** and **Password** and click **Sign in**.
2. Because your account has MFA enabled, the form reveals an **Authentication code** field instead of logging you in.
3. Open your authenticator app on your phone, read the current 6-digit code, and type it into the field.
4. Click **Sign in** again to complete the process.

#### To sign out
1. From any screen, look at the top-right of the header.
2. Click the sign-out icon next to your profile pill.
3. You are returned to the Sign in screen and your session tokens are cleared from this browser.

### Validation Rules & Things That Can Go Wrong
* An incorrect email or password shows a red inline error with the exact message the server returned (for example, *"invalid credentials"*) — the form does not tell you specifically which field was wrong for security reasons.
* A correct email/password combination on an MFA-enabled account does not show an error — it silently reveals the Authentication code field instead.
* An incorrect or expired authentication code is rejected the same way as a bad password, with an inline error.
* The Sign in button is disabled for the whole time your request is being processed, to prevent double-submission.

### Frequently Asked Questions

**Q: I forgot my password — where do I reset it?**  
A: There is no self-service "forgot password" link on the Sign-in screen. If you cannot sign in, contact an administrator. Once you are signed in, you can change your own password any time from your Profile page.

**Q: Why does the page suddenly ask me for a 6-digit code?**  
A: Your account has multi-factor authentication enabled. This is expected — enter the current code from your authenticator app.

**Q: My session keeps timing out. Why?**  
A: Simple ERP uses short-lived access tokens that refresh automatically in the background while you use the app. You are only returned to Sign in if the longer-lived refresh token itself has expired or been invalidated (for example, because it was already used once from another tab or device).

**Q: Why was I redirected to Sign in from a page I had bookmarked?**  
A: Every page requires an active, authenticated session. If your session was not active when you opened the link, you are sent to Sign in first and returned to your intended page after you log in.

---

## 3. Dashboard (Control Tower)
`OVERVIEW` • Route: `/` • Permission required: `analytics:read`

### Purpose
The Control Tower gives an immediate, company-wide snapshot of current operational and financial health: open orders, production progress, working capital, inventory valuation, and recent system activity. It is the first screen you see after signing in, provided your account holds the analytics permission.

### How to Get There
Click the Simple ERP logo in the header, or the **"Control tower"** item at the top of the Overview group in the sidebar. The address is simply `/` — it is the page you land on immediately after signing in. Seeing the dashboard's charts and figures requires the `analytics:read` permission; without it, you still land on this page after signing in, but you see a plain message pointing you to the modules in the sidebar instead of the dashboard content.

### Layout Overview
* Top statistics strip: high-level cards summarizing **Open orders**, **Production runs**, **Working capital**, and **Inventory valuation** — clicking an operational card takes you straight to the corresponding module.
* Middle charts: a visual breakdown of order volume over time and production output vs. target.
* Bottom panel: a **Recent activity** feed showing the latest actions across the company (same data as the Audit Trail, but presented as a quick glance).
* If the server cannot load inventory valuation, a yellow advisory note appears explaining that the working capital figure excludes inventory until stock valuations finish computing.

### Key Fields & What They Mean
* **Open orders:** The total count and monetary value of sales orders currently in progress (confirmed, allocated, or partially fulfilled) that have not yet reached completed or cancelled.
* **Production runs:** The count of manufacturing runs currently open or in-flight across all factories.
* **Working capital:** Current assets minus current liabilities, computed from accounts receivable, inventory value, and accounts payable.
* **Inventory valuation:** The total monetary value of on-hand raw materials and finished goods, based on current weighted average cost (WAC).

### Step-by-Step: Common Tasks

#### To review current operational health
1. Open the dashboard (land on `/` after signing in or click the logo).
2. Check the top stat cards for unexpected changes in open orders or pending production.
3. Review the Recent activity list to see what colleagues have posted or approved recently.

#### To drill into a metric
1. Click the stat card you want to investigate (for example, Open orders).
2. The browser navigates directly to the Orders module with current records displayed.

### Validation Rules & Things That Can Go Wrong
* If the dashboard's data fails to load, a warning banner shows the server's error message and the stat cards will not populate.
* If inventory valuation specifically is unavailable, the rest of the dashboard still loads, but a note explains that the working-capital figure excludes inventory.

### Frequently Asked Questions

**Q: Why don't I see any charts or figures on my home page?**  
A: You need the `analytics:read` permission. Without it, the home page still loads (it is the landing page for every signed-in user) but shows only a short message pointing you to the modules in the sidebar.

**Q: Does the dashboard update automatically while I'm looking at it?**  
A: No — the figures are loaded once when you land on or navigate to the page. Revisit or reload the page to refresh them.

**Q: Why does the working capital figure look low or say something is missing?**  
A: If inventory valuation could not be computed at that moment, the working-capital figure is calculated without it, and a warning note is shown so you know the number is incomplete rather than simply low.

**Q: What does "Recent activity" actually show?**  
A: It reuses the same Audit Log entries described in the Audit Log chapter — it is not a separate live event feed, just the newest audit entries.

---

## 4. Parties: Vendors, Customers & Transporters
`FOUNDATION` • Route: `/parties` • Detail: `/parties/:id` • Permissions: `party:read` (view), `party:write` (create/edit/upload), `party:block` (block/unblock)

### Purpose
Every organization Simple ERP transacts with — vendors you buy from, customers you sell to, and transporters/carriers used in logistics — is recorded once here as a "party". This is the master record that Procurement, Orders, Logistics and Finance all draw their vendor/customer names, credit terms, addresses, contacts and bank details from.

### How to Get There
Sidebar → Foundation → Party master (path `/parties`). Requires the `party:read` permission. Clicking a party's code or its Open button takes you to that party's own detail page (`/parties/:id`).

### Layout Overview
* **List page:** a search box (matches code, name or tax ID), a **Type filter** (*All / Vendor / Customer / Both*), and a **Status filter** (*All / Draft / Active / Blocked / Inactive*).
* If you hold `party:write`, you also see **Bulk Upload** and **New party** buttons.
* The table lists Party Code (a link), legal and display name, a Party Label pill, GST/tax ID, payment terms, credit used vs. credit limit, a Status pill, and row actions (*Activate*, when applicable, and *Open*).
* **Detail page:** a header with the party's legal name, type and code, a Status pill, and — depending on your permissions and the party's current status — *Activate*, *Block* or *Unblock* buttons.
* A **Core details** panel: an editable form for legal name, party label (subtype), tax ID / GSTIN, payment terms, currency and credit limit, plus read-only Credit used and Risk stat cards.
* An **Addresses** panel listing every address on file (type, location name, line 1, city, state, postal code, and whether it is the default), with an *Add address* button.
* A **Contacts** panel (name, email, phone, primary flag) with an *Add contact* button.
* A **Bank accounts** panel (account name, bank/IFSC, masked account number, status) with an *Add bank account* button.

### Key Fields & What They Mean
* **Party Code:** An automatically generated identifier for the party; also the link to its detail page.
* **Party label / subtype:** The specific classification chosen from Configuration's Party Types list (for example *"Vendor"*, *"Vendor – Services"*, *"Customer"*). This determines whether the party behaves as a vendor, a customer, or both.
* **Tax ID / GSTIN:** The party's statutory tax registration number (15 characters in India).
* **Payment terms:** Agreed credit terms such as NET30, NET15, or Immediate.
* **Credit limit / Credit used:** The maximum outstanding balance allowed for this party and how much of that limit is currently used. This is what Orders checks before letting a new sales order through.
* **Status:** *Draft*, *Active*, *Blocked*, or *Inactive*. Only an Active party can be freely transacted with; a Blocked party has been deliberately frozen.

### Step-by-Step: Common Tasks

#### To create a new party
1. Go to Party master and click **New party**.
2. Enter the **Legal name** and choose a **Party label** (this determines whether it is treated as a vendor, customer, or both).
3. Optionally fill in Tax ID / GSTIN, Payment terms, Currency and Credit limit.
4. Optionally fill in a Billing address (line 1, city, postal code, state).
5. If the party label is a customer type, you can also add a Shipping address with its own location name.
6. Optionally add a Primary contact (name, email, phone).
7. Click **Create party**.

#### To bulk-upload multiple parties from a spreadsheet
1. Click **Bulk Upload** on the Party master screen.
2. Click **Download sample CSV** to get a correctly headed template.
3. Fill in one row per party in the template and save it as a CSV file.
4. Drag the file onto the upload area (or click to select it).
5. Click **Process upload**.
6. Review the results table — each row shows Success with the new party code, or Error with the reason.
7. If any rows failed, click **Download error file** to get a CSV of just the failed rows with their error messages, so you can fix and re-upload them.

#### To activate a draft or blocked party
1. Find the party in the list (or open its detail page).
2. Click **Activate** next to it (list) or at the top of its detail page.

#### To block a party
1. Open the party's detail page.
2. Click **Block** (only shown for an Active party, and only if you hold `party:block`).
3. Type a reason of at least 5 characters explaining why.
4. Click **Block party** to confirm.

#### To edit a party's core details
1. Open the party's detail page.
2. Change any of Legal name, Party label, Tax ID, Payment terms, Currency, or Credit limit in the Core details panel.
3. Click **Save changes**.

#### To add an address, contact, or bank account
1. Open the party's detail page.
2. Click **Add address** / **Add contact** / **Add bank account** in the relevant panel.
3. Fill in the required fields (for an address: type, line 1, city; for a contact: name; for a bank account: account holder name, account number, bank name).
4. Click the corresponding **Add** button in the dialog.

### Validation Rules & Things That Can Go Wrong
* Creating a party requires a Legal name; other fields are optional.
* Blocking a party requires a written reason of at least 5 characters.
* Any save that fails on the server (for example, a duplicate tax ID) shows a red inline error explaining what went wrong, without closing the dialog.
* A bulk upload's per-row failures never block the rows that succeeded — you get a mixed results table and can re-upload only the corrected rows.

### Frequently Asked Questions

**Q: What is the difference between a Vendor, a Customer, and a "Both" party?**  
A: It comes from the Party label you choose, which is itself defined in Configuration → Party Types. A vendor-type party can be used on purchase orders, a customer-type party can be used on sales orders, and a "both" party can be used on either.

**Q: Why don't I see the New party or Bulk Upload buttons?**  
A: These require the `party:write` permission. Without it, you can still view and search the party list.

**Q: Why can't I click Block on this party?**  
A: Block requires the `party:block` permission, and it is only offered while the party's status is Active.

**Q: What happens when a party is Blocked?**  
A: The party's status changes to Blocked and stays that way, with the reason recorded, until someone with `party:block` clicks Unblock. Screens elsewhere in the app that create new documents against a party are expected to respect this status.

**Q: How do I bring in a large number of vendors or customers at once?**  
A: Use Bulk Upload rather than creating them one at a time — download the sample CSV, fill in one row per party, and upload it.

**Q: Why did creating a sales order fail with a credit-limit message?**  
A: Orders checks the customer's Credit used against their Credit limit here on the Party record. If the new order would exceed it, order creation is blocked unless the user has permission to explicitly override it.

---

## 5. Product Catalog & Bill of Materials (BOM)
`FOUNDATION` • Route: `/products` • Permissions: `product:read` (view), `product:write` (create/edit/upload), `bom:read` (view BOMs), `bom:write` (create/version BOMs), `bom:approve` (approve/reject BOMs)

### Purpose
The Product Catalog is the master directory of everything Simple ERP buys, sells, or manufactures: raw materials, finished goods, consumables and services. Tied directly to each finished good is its Bill of Materials (BOM) — the precise recipe of raw materials and consumables needed to produce one unit of that good.

### How to Get There
Sidebar → Foundation → Products & BOM (path `/products`). Requires `product:read` for the Products tab and `bom:read` for the BOM tab.

### Layout Overview
* **Two tabs:** *Products* and *BOM*.
* **Products tab:** a search box (matches SKU ID or product name), Category and Product Type filters, a Status filter, and — with `product:write` — **Bulk Upload** and **New product** buttons.
* The Products table lists SKU ID (a link), Product Name, Type, Category, Unit of Measure (UOM), Average Cost, Status, and Edit / Deprecate actions per row.
* **New product dialog:** Category picker (sets which product types are allowed), SKU ID (can be typed or left blank to auto-generate), Product Name, Type (raw material, finished good, consumable, service), UOM, Description, and an optional Initial Cost.
* **BOM tab:** a list of finished goods that have a BOM, showing Product SKU, Product Name, Active Version, Total Components, and a Status pill.
* **BOM detail view:** the version history for a finished good's recipe. Each version shows its component lines (component SKU, description, quantity per finished unit, and UOM), its status (draft, pending approval, active, rejected, superseded), and action buttons: *Submit* (moves draft to pending approval), *Approve* and *Reject* (for approvers), and *New version*.

### Key Fields & What They Mean
* **SKU ID:** The primary identifier for the product across the entire system. Once saved, a product's SKU ID and UOM cannot be changed.
* **Product Type:** raw_material (purchased for manufacturing), finished_good (manufactured or sold), consumable (used during operations), or service.
* **Unit of Measure (UOM):** pcs, kg, m, ltr, etc. Used consistently across inventory, BOMs, orders, and receipts.
* **BOM Active Version:** The single approved recipe currently used by Production when building this finished good.
* **Component Quantity:** The quantity of a raw material required to build exactly one unit of the finished good.

### Step-by-Step: Common Tasks

#### To create a new product
1. Go to Products & BOM → Products tab and click **New product**.
2. Select the **Category** (this determines which product types are valid).
3. Enter the **SKU ID** (or leave it blank to auto-generate).
4. Enter the **Product Name**, choose the **Product Type**, and choose the **UOM**.
5. Optionally fill in Description and Initial Cost.
6. Click **Create product**.

#### To bulk-upload products from a spreadsheet
1. Click **Bulk Upload** on the Products tab.
2. Download the sample CSV.
3. Fill in one row per product and upload the file.
4. Click **Process upload**.
5. Review the per-row results and download the error file for any rows that failed, if needed.

#### To create a brand-new BOM for a finished good
1. Go to the BOM tab and click **New BOM**.
2. Search for and select the finished good this BOM belongs to.
3. For each raw material or consumable the finished good needs, choose it and enter a **Quantity**, then click **Add line**.
4. Remove any line you added by mistake with its Remove button.
5. Click **Save BOM version**.

#### To add a new version to an existing BOM
1. Open the BOM from the BOM tab.
2. Click **New version**.
3. Add or remove component lines as needed.
4. Click **Save BOM version**.

#### To submit, approve, or reject a BOM version
1. Open the BOM and find the version in its list.
2. While it is in draft state and you hold `bom:write`, click **Submit** to move it to pending approval.
3. While it is pending approval and you hold `bom:approve`, click **Approve** to put it into effect, or **Reject** to send it back.

#### To bulk-upload BOMs from a spreadsheet
1. Click **Bulk Upload** on the BOM tab.
2. Download the sample CSV — note that rows sharing the same Product SKU are grouped into a single BOM (a product can only have one BOM).
3. Fill in one row per component and upload the file.
4. Click **Process upload** and review the results, downloading the error file if needed.

### Validation Rules & Things That Can Go Wrong
* Creating a product requires a Category and a SKU ID.
* Saving a BOM version requires at least one component line.
* Once a product is created, its SKU ID and UOM can never be changed from the Edit dialog.
* Bulk upload results are shown per row (or per BOM group, for the BOM upload) with a clear success/error split and a downloadable error file.

### Frequently Asked Questions

**Q: Why can't I change a product's SKU ID or unit of measure?**  
A: Both are fixed at creation because other records (inventory, purchase orders, BOMs) reference the product by these values. If you made a genuine mistake, you would need to deprecate the product and create a new one.

**Q: Why don't I see Approve/Reject buttons on a BOM version?**  
A: Approve and Reject only appear while the version is in the pending_approval state, and only if you hold the `bom:approve` permission.

**Q: What happens when I submit a BOM version?**  
A: It moves from draft to pending_approval, where someone with approval rights can approve or reject it. It is not yet in effect until approved.

**Q: Can a finished good have more than one BOM?**  
A: No — a product has exactly one BOM, which can carry multiple versions over time (only one of which is the Active version at any moment).

**Q: How does the BOM bulk-upload CSV group rows into separate BOMs?**  
A: Every row that shares the same Product SKU column is treated as one component of that product's single BOM version — you list several rows, one per component.

---

## 6. Procurement: Purchase Orders
`SUPPLY CHAIN` • Route: `/procurement` • Permissions: `po:read` (view), `po:write` (create/upload), `po:email` (resend email), `po:cancel` (cancel PO), `po:short_close` (short close PO)

### Purpose
Procurement is where purchase orders (POs) to vendors are raised, tracked, and — when needed — cancelled or short-closed. In this system a PO is issued immediately when it is created; there is no separate approval workflow to click through before it goes out.

### How to Get There
Sidebar → Supply chain → Procurement (path `/procurement`). Requires `po:read`.

### Layout Overview
* A search box (PO number or vendor), an **All vendors filter**, an **All Status filter**, and — with `po:write` — **Bulk Upload** and **New purchase order** buttons.
* The table lists PO number (a link), Vendor, Deliver-to warehouse, Value, Expected date, a Status pill, and a Download PDF button.
* Opening a PO shows its status, its approval-tier description, an email-state pill, the subtotal/tax/total, and a line table with ordered, received and rejected quantities per SKU alongside unit price, tax and gross amounts.
* From the detail dialog you can **Download PDF**, **Resend email** (if the vendor email failed), and — depending on status and permissions — **Short close PO** or **Cancel PO**.

### Key Fields & What They Mean
* **Vendor:** The party the PO is raised against — must be an active vendor-type party.
* **Invoice to (business entity):** Which of Simple ERP's own legal entities is the buyer of record on this PO (from the PO & Invoice module).
* **Ship to (warehouse):** The warehouse the goods should be delivered to (from Factory & Warehouse).
* **Unit price:** Entered before GST; the selected GST % is added per line to compute the line's tax and gross amount.
* **Status:** draft, pending_approval, approved, issued, partially_received, received, closed, or cancelled — in practice, new POs go straight to issued.
* **Email state:** Whether the PO email to the vendor was sent successfully or failed.

### Step-by-Step: Common Tasks

#### To create a new purchase order
1. Go to Procurement and click **New purchase order**.
2. Choose the **Vendor**, the **Invoice to** (business entity), and the **Ship to** (warehouse).
3. Optionally enter Terms of Payment and Mode of Payment.
4. Enter the **Expected date**.
5. For each product you want to order, choose the Product, enter the **Qty**, the **Price** (before GST), and the **GST %**, then click **Add line**.
6. Repeat for every product on the order, removing any line you no longer want with its Remove button.
7. Click **Create**.

#### To bulk-upload purchase orders from a spreadsheet
1. Click **Bulk Upload** on the Procurement screen.
2. Download the sample CSV — rows sharing the same PO Ref column are grouped into a single purchase order.
3. Fill in one row per line item and upload the file.
4. Click **Process upload** and review the results table, downloading the error file for any failed rows.

#### To download a PO as a PDF
1. Click **Download PDF** next to the PO in the list, or from inside its detail dialog.

#### To resend a PO email that failed
1. Open the PO's detail dialog — a "failed" email-state pill appears if the original send did not go through.
2. Click **Resend email**.

#### To short-close a purchase order
1. Open the PO's detail dialog (status must be issued or partially_received, and you must hold `po:short_close`).
2. Click **Short close PO**.
3. Type a reason of at least 5 characters — the dialog reminds you this writes off the outstanding balance and blocks any further goods receipt against this PO.
4. Click **Confirm short close**.

#### To cancel a purchase order
1. Open the PO's detail dialog (not allowed once it is cancelled, closed, or fully received; you must hold `po:cancel`).
2. Click **Cancel PO**.
3. Type a reason of at least 5 characters.
4. Click **Confirm cancel**.

### Validation Rules & Things That Can Go Wrong
* Creating a PO requires a Vendor, a Ship to warehouse, and at least one line.
* Cancel and Short close both require a typed reason of at least 5 characters.
* Short close is only offered while the PO is issued or partially_received; Cancel is hidden once the PO is cancelled, closed, or fully received.
* Line amounts are always computed from a GST-exclusive unit price plus the selected GST rate — the form reminds you of this next to the line-adding row.

### Frequently Asked Questions

**Q: Why is there no approval step before my PO goes to the vendor?**  
A: In this system, a purchase order is issued immediately on creation — there is no separate submit-for-approval workflow to click through, even though the status field still has approval-related values defined.

**Q: Why can't I cancel this PO anymore?**  
A: Cancel is not offered once a PO has been fully received, closed, or already cancelled.

**Q: What's the difference between Cancel and Short close?**  
A: Cancel voids the PO outright. Short close is used when a PO has been partially received and you want to formally write off the remaining, undelivered balance rather than wait for it — it also stops any further goods receipt against that PO.

**Q: The email to my vendor shows "failed" — what do I do?**  
A: Open the PO and click Resend email; this is offered specifically when the email state is failed and you hold the `po:email` permission.

**Q: How does a Purchase Order relate to a GRN?**  
A: A PO's lines are received against it through the GRN & QC screen — the PO's received/rejected quantities update as goods are received and quality-checked.

---

## 7. Inventory: Stock Balances, Ledger & Item Detail
`SUPPLY CHAIN` • Route: `/inventory` • Detail: `/inventory/:id` • Permissions: `inventory:read` (view), `inventory:write` (adjustments/transfers/quarantine)

### Purpose
Inventory is the central ledger of all physical materials owned by the business: raw materials, finished goods, and rejected stock. It provides both aggregate stock balances (by warehouse and condition) and a unit-level ledger of every serialized piece or lot, supporting transfers, condition moves, and manual adjustments.

### How to Get There
Sidebar → Supply chain → Inventory (path `/inventory`). Requires `inventory:read`. The page has two top-level tabs — **Stock Balances** and **Inventory Ledger** — and each of those has **Raw Material**, **Finished Goods** and **Rejected Raw Material** sub-tabs.

### Layout Overview
* **Stock Balances tab:** a warehouse filter, an Inventory value stat card, and a **Count/Cost toggle** that switches every quantity column to a money value using each SKU's average cost. Columns differ slightly by sub-tab:
  * *Raw Material:* Under QC, On hand, Rejected, Damaged, Expired and Total.
  * *Finished Goods:* On hand, Reserved, Rejected, Damaged, Expired and Total.
  * *Rejected Raw Material:* Just the rejected quantity.
* **Inventory Ledger tab:** action buttons for **Transfer**, **Bulk Upload Transfers**, **Pending Transfers**, **Move / quarantine**, **Bulk Upload Adjustments** and **Post adjustment** (each shown only if you hold the matching permission), a **Scan to Jump** box (on the Raw Material and Rejected sub-tabs) that lets you type or scan an Inventory ID and jump straight to that unit's own detail page, and filters for Status, Location and SKU Name.
* The Raw Material ledger table lists Inventory ID (a link), SKU, UOM, Qty, Status, Location and Vendor Inventory ID. The Finished Goods ledger lists FG-ID, SKU, UOM, Status, Qty, Allocated, Available and Location. The Rejected Raw Material ledger adds **Return to Vendor** and **Discard** buttons per row.
* **Post adjustment dialog:** choose a SKU and Warehouse, a condition Bucket, and a Direction (Write off or Add stock), then one or more lines each optionally tied to a specific Inventory ID, a quantity, and a UOM, plus a required Reason.
* **Move / quarantine dialog:** the same SKU/Warehouse/lines pattern, but with a From bucket and a To bucket instead of a single bucket and direction.
* **Transfer dialog:** choose a SKU, a Source warehouse and a Destination warehouse, then one or more lines (optionally tied to a specific Inventory ID) with quantities — dispatching leaves the source stock "in transit" immediately.
* **Pending Transfers dialog:** every transfer still in transit, each with a **Complete** button to land it as available at the destination once it has physically arrived.
* **Finished Good detail dialog (opened from a produced FG-ID):** status, quantity, allocated/available quantities, warehouse, batch, production run, and the order it is allocated to (if any); a Transfer to another warehouse control and a Change condition control; and a movement-history table.

### Key Fields & What They Mean
* **Bucket / condition:** Which pool a unit's quantity currently sits in: *available*, *quarantine* (rejected in QC), *damaged*, *expired*, or *in transit*.
* **Under QC:** Raw-material stock that has been received but has not yet cleared quality control — it counts toward the total on hand even though it has no separate stock-balance row of its own.
* **Reserved / Allocated:** For finished goods, the portion of on-hand stock already reserved against a specific sales-order line (see Finished Goods Allocation in the Production chapter).
* **Inventory ID / FG-ID:** The unique identifier printed (as a QR code) on a physical unit's label — raw materials and rejected raw materials use Inventory IDs; produced finished goods use FG-IDs.
* **Vendor Inventory ID:** An optional secondary identifier taken from the vendor's own QR code or label, attached from the unit's detail page when the receiving GRN had "Vendor's QR and ID" turned on.

### Step-by-Step: Common Tasks

#### To check current stock levels
1. Go to Inventory and stay on the Stock Balances tab.
2. Choose Raw Material, Finished Goods, or Rejected Raw Material.
3. Optionally filter by warehouse.
4. Toggle Count / Cost to see quantities or their monetary value.

#### To find a specific unit using Scan to Jump
1. Go to Inventory → Inventory Ledger, on the Raw Material or Rejected Raw Material sub-tab.
2. Click into the **Scan to Jump** box.
3. Scan the unit's QR code with a hardware scanner (or type its Inventory ID) and press Enter.
4. You are taken directly to that unit's own detail page.

#### To post a stock adjustment
1. Go to Inventory Ledger and click **Post adjustment**.
2. Choose the **SKU Name**, the **Warehouse**, the **Bucket**, and the **Direction** (Write off or Add stock).
3. Optionally pick a specific Inventory ID for a line — leave it unpicked to adjust by quantity only.
4. Enter the **Quantity** (and UOM) for each line, adding more lines if needed.
5. Type a **Reason** of at least 5 characters.
6. Click **Post**.

#### To move or quarantine stock
1. Go to Inventory Ledger and click **Move / quarantine**.
2. Choose the **SKU Name**, the **Warehouse**, the **From bucket** and the **To bucket**.
3. Optionally pick specific Inventory IDs per line, and enter quantities.
4. Type a **Reason** of at least 5 characters.
5. Click **Move**.

#### To transfer stock between warehouses
1. Go to Inventory Ledger and click **Transfer**.
2. Choose the **SKU Name**, the **Source warehouse** and the **Destination warehouse**.
3. Optionally pick specific Inventory IDs per line, and enter quantities.
4. Optionally add a Reason.
5. Click **Dispatch** — the stock immediately leaves the source and sits in transit.

#### To complete a pending transfer
1. Click **Pending Transfers** on the Inventory Ledger screen.
2. Find the transfer that has physically arrived.
3. Click **Complete** — the stock lands as available at the destination warehouse.

#### To dispose of a rejected item
1. Go to Inventory Ledger → Rejected Raw Material.
2. Find the item and click **Return to Vendor** or **Discard**, as appropriate.

#### To bulk-upload adjustments or transfers
1. Click **Bulk Upload Adjustments** or **Bulk Upload Transfers** on the Inventory Ledger screen.
2. Download the sample CSV (for adjustments, remember a negative quantity writes stock off).
3. Fill in one row per adjustment or transfer and upload the file.
4. Click **Process upload** and review the results, downloading the error file if needed.

### Validation Rules & Things That Can Go Wrong
* Both Post adjustment and Move / quarantine require a Reason of at least 5 characters.
* Move / quarantine requires the From and To buckets to be different.
* Transfer, Move/quarantine and Post adjustment all require the SKU Name and Warehouse(s) to be selected before you can add lines.
* An Inventory ID already picked on one line of a dialog cannot also be picked on another line in the same submission.
* An item sitting "in transit" cannot be adjusted — it is excluded from the Post adjustment picker.

### Frequently Asked Questions

**Q: What's the difference between Stock Balances and Inventory Ledger?**  
A: Stock Balances is an aggregate, SKU-level summary (how much exists in each condition). Inventory Ledger is the per-unit view — individual Inventory IDs/FG-IDs — and is also where you perform transfers, adjustments and status changes.

**Q: Why is some of my received stock showing as "Under QC" instead of available?**  
A: Raw material only becomes available once it clears quality control on the GRN & QC screen; before that it sits under QC and is only reflected in the Stock Balances total, not as a separate available balance.

**Q: I transferred stock but it's not showing as available at the destination yet — why?**  
A: A transfer leaves the source immediately but sits "in transit" until someone completes it from the Pending Transfers dialog once it has physically arrived.

**Q: How do I fix a scanned vendor QR that didn't attach correctly?**  
A: Open the specific unit's own detail page (via Scan to Jump or its link) and use the Vendor QR & ID panel there to re-scan the photo, or type the Vendor Inventory ID in manually.

**Q: What do the condition buckets (available, quarantine, damaged, expired) actually mean?**  
A: They are the different pools a unit's quantity can sit in. "Quarantine" means rejected in quality control. Move / quarantine is how you deliberately move quantity between these buckets, for example flagging previously-available stock as damaged.

---

## 8. GRN & QC: Goods Receipt Notes, Quality Control & QR Labels
`SUPPLY CHAIN` • Route: `/warehouse` • Dedicated QC Page: `/warehouse/qc/:id` • Permissions: `warehouse:read` (module view), `grn:read` (GRN list), `grn:write` (receive goods/cancel), `qc:write` (execute inspections)

### Purpose
GRN & QC is the operational gateway for all incoming materials purchased on purchase orders. It records physical gate delivery (Goods Receipt Note / GRN), generates unique QR-code labels for every unit received, subjects shipments to quality inspection (piece-by-piece serialized or bulk lot-based QC), and automatically posts accepted stock into inventory while isolating rejected stock in quarantine.

### How to Get There
Sidebar → Supply chain (or Warehouse & Logistics) → **GRN & QC** (path `/warehouse`). Requires `warehouse:read` and `grn:read`. Quality inspections open on a dedicated page per receipt (`/warehouse/qc/:id`).

### Layout Overview
* **GRN Tab:**
  * Search box, Vendor filter, Warehouse filter, Status filter, and **Scan to Jump** box.
  * Action buttons (with `grn:write`): **Bulk Upload** and **Receive goods**.
  * Table columns: GRN number (link to detail dialog), PO number, Vendor, Warehouse, Received Goods value, Status pill (*under_qc*, *posted*, *rejected*, *cancelled*), and Received date.
* **Receive Goods Dialog:**
  * Purchase order selector (filtered to open/issued POs).
  * Receiving Warehouse confirm/select.
  * Received lines: SKU, Received Quantity, and **Batch number** (mandatory if the SKU is flagged as batch-tracked in its category).
  * Statutory & Transport: **Invoice number** (mandatory), Vehicle number, Delivery note.
  * Label Configuration: **Sticker size** template picker (from Configuration → Sticker Size), and a **"Vendor's QR and ID"** checkbox.
* **GRN Detail Dialog:**
  * Shows received SKUs, drillable into individual generated Inventory IDs.
  * **Download all QR codes** (as a .zip of PNGs or a printable multi-sticker PDF sheet).
  * **Edit button** (active only while the receipt is in *under_qc* status): lets you modify warehouse, quantities, batch numbers, or add/remove SKU lines.
  * **Cancel GRN button** (available while *under_qc* or *posted*): requires a mandatory explanation of at least 5 characters.
* **QC Tab:**
  * Lists all GRNs awaiting inspection.
  * Each row features a prominent **Test / QC** link opening the dedicated inspection interface, plus a **Bulk Upload** button for lot-level QC decisions.
* **Dedicated QC Page (`/warehouse/qc/:id`):**
  * Search box by Inventory ID, status and product filters.
  * **Serialised Lines (Piece-tracked):** Rendered as individual unit rows showing Inventory ID, barcode preview, and **Accept** / **Reject** buttons, with an optional vendor-QR scan field per item. Rejecting any unit opens a prompt requiring a rejection reason.
  * **Non-serialised Lines (Lot-tracked):** Rendered with Accepted Quantity and Rejected Quantity numeric inputs with a per-line Save button. Rejections require a written reason.
  * Once all items on a receipt have been adjudicated, the receipt automatically transitions from *under_qc* to *posted* (or *rejected*), and accepted stock immediately lands in available inventory.

### Key Fields & What They Mean
* **GRN Status:**
  * *under_qc:* Goods arrived at dock, QR labels printed, awaiting inspection. Stock is quarantined and not yet available for production or dispatch.
  * *posted:* Inspection completed; accepted goods are live in active stock; rejected items moved to the warehouse's QUARANTINE hold bin.
  * *rejected:* All items on the receipt failed inspection.
  * *cancelled:* Receipt voided; stock reversed; PO remaining quantity restored.
* **Batch Number:** Mandatory lot identifier for traceability on batch-managed SKUs.
* **Sticker Size:** Template from *Configuration → Sticker Size* dictating the label format for thermal or laser printing.
* **Vendor's QR and ID:** Flag indicating that incoming goods carry vendor-supplied barcodes to be cross-referenced alongside internal Inventory IDs.

### Step-by-Step: Common Tasks

#### To receive goods against a purchase order
1. Go to GRN & QC → GRN tab and click **Receive goods**.
2. Choose the **Purchase order**.
3. Confirm or change the receiving **Warehouse**.
4. For each line, enter the **Received quantity**, and a **Batch number** if the SKU requires one.
5. Enter the vendor's **Invoice number**, and optionally the Vehicle number and Delivery note.
6. Optionally choose a **Sticker size** template, and tick **Vendor's QR and ID** if vendor labels will be scanned later.
7. Click **Create receipt**.

#### To run quality control on a received GRN
1. Go to the **QC tab** and click **Test / QC** next to the GRN.
2. For a serialized line, click **Accept** or **Reject** on each individual Inventory ID; any rejection requires typing a reason.
3. For a non-serialized lot line, type the **Accepted** and **Rejected** quantities and click Save for that line.
4. Repeat until every line and unit has a recorded decision — the receipt automatically posts to inventory once resolved.

#### To download printable QR code labels
1. Open the GRN's detail dialog (or its QC page).
2. Click **Download all QR codes** for a ZIP archive of individual PNGs, or **Download all QR codes in PDF** for a printable multi-label sheet formatted to your selected sticker size.

#### To edit or cancel a GRN
1. Open the GRN's detail dialog from the GRN tab.
2. While still in *under_qc*, click **Edit** to modify lines, quantities, or batches, then Save.
3. To void a receipt, click **Cancel GRN**, provide a reason of at least 5 characters, and confirm. If the GRN was already posted, the stock receipt is deducted from inventory and the PO's open balance is restored.

### Validation Rules & Things That Can Go Wrong
* An Invoice number is mandatory on every receipt.
* Batch numbers are strictly validated: if a SKU belongs to a category marked *requiresBatch*, the receipt will reject lines submitted without a batch string.
* Rejections require an explanation of at least 5 characters.
* A GRN can only be edited while in *under_qc* status. Once posted or rejected, line data is locked.

### Frequently Asked Questions

**Q: What's the difference between "under_qc" and "posted"?**  
A: *under_qc* means goods arrived at the dock but have not cleared inspection; they cannot be consumed by Production or allocated to Orders. *posted* means QC passed and accepted units are live in available stock.

**Q: Why does cancelling a posted GRN reverse other records?**  
A: Because posting increments physical stock balances and decrements the open quantity on the PO. Cancelling reverses both sides to prevent inventory drift.

**Q: Can I scan vendor barcodes with a handheld scanner?**  
A: Yes. On the QC inspection screen or the Inventory item detail page, focus on the barcode field and scan the vendor label using any standard USB or Bluetooth 2D barcode scanner.

---

## 9. Factory & Warehouse Setup
`ADMINISTRATION / FOUNDATION` • Route: `/factory-warehouse` • Permissions: `warehouse:read` (view), `warehouse:write` (create/edit/upload)

### Purpose
Factory & Warehouse defines and governs the physical operational footprint of the enterprise. It manages the two primary levels of physical infrastructure:
1. **Factories:** Physical manufacturing campuses, assembly plants, and administrative production facilities. Tracks geographical location, contact personnel, and aggregates the count of operational warehouses hosted within each facility.
2. **Warehouses:** Inventory storage depots, raw-material stockrooms, transit hubs, and finished-goods distribution centers. Tracks physical capacity, allowed product types, operational status (*active*, *constrained*, *inactive*), address, and structural linkage to parent factories.
3. **Automatic Quarantine Bin Provisioning:** Every warehouse automatically provisions a dedicated `QUARANTINE` hold bin upon creation to isolate goods that fail Quality Control.
4. **Site Scoping & Role Security:** Forms the architectural foundation for user role site scoping—restricting storekeepers, QC inspectors, and shop floor managers to only the specific factories or warehouses they are assigned to.

### How to Get There
Sidebar → Administration (or Foundation) → **Factory & Warehouse** (path `/factory-warehouse`). Requires `warehouse:read` to view and `warehouse:write` to create or modify.

### Layout Overview
* **Header:** Displays eyebrow "Foundation", Title **"Factory & Warehouse"**, and description *"The factories and warehouses Simple operates, and which warehouse sits inside which factory."*
* **Two Tabs:** **Factories** and **Warehouses**.

#### Tab 1: Factories
* **Action Toolbar:** Displays "Factories" heading, with **Bulk Upload** and **New factory** buttons (when holding `warehouse:write`).
* **Desktop Table:**
  * **Code:** Unique factory code (e.g., `FAC-001`), automatically generated.
  * **Name:** Facility name (e.g., "Pune Manufacturing Plant").
  * **Location:** City and State code (e.g., "Pune, 27").
  * **Warehouses:** Live count of storage warehouses physically located within this factory.
  * **Status:** Visual pill (*active* or *inactive*).
  * **Actions:** Edit button per row.
* **Mobile View:** Renders responsive `MobileRecordCard` components with labeled rows and full-width Edit actions.
* **New / Edit Factory Dialog:**
  * **Name (required):** Name of the production facility.
  * **Address Line 1:** Street address.
  * **City, State Code, Postal Code:** City, two-digit state code, and PIN/postal code.
  * **Action Buttons:** Cancel and Save.

#### Tab 2: Warehouses
* **Action Toolbar:** Displays "Warehouses" heading, with **Bulk Upload** and **New warehouse** buttons.
* **Desktop Table:**
  * **Code:** Unique, immutable warehouse identifier (e.g., `WH-001`).
  * **Name:** Warehouse name (e.g., "Pune Main Raw Materials Warehouse").
  * **Status:** Pill displaying operational condition:
    * `active` (green): Normal daily operations.
    * `constrained` (yellow/warning): Space or operational bottleneck.
    * `inactive` (gray/danger): Decommissioned or suspended site.
  * **Factory:** Parent factory name if physically located inside a plant, or "–" for standalone distribution hubs.
  * **City:** City and full Indian State Name (e.g., "Pune, 27 — Maharashtra").
  * **Actions:** Edit button per row.
* **Mobile View:** Stacked mobile cards showing Code, Name, Status, Factory, City, and Edit.
* **New / Edit Warehouse Dialog:**
  * **Code Display:** For existing warehouses, displays the permanent immutable code. For new warehouses, indicates code will be generated automatically.
  * **Name (required):** Operating name of the storage facility.
  * **Status Dropdown:** Choose between `active`, `constrained`, and `inactive`.
  * **Factory Dropdown (optional):** Lists all active factories, allowing you to link this warehouse to its parent industrial site. Leave unselected for standalone regional warehouses.
  * **Address Fields:** Address Line 1, Address Line 2 (optional), City, Postal Code, State (with Indian State dropdown selector), and Country (default "IN").
  * **Action Buttons:** Cancel and Save.

### Key Fields & What They Mean
* **Factory Code:** Generated automatically sequentially (`FAC-001`, `FAC-002`...). Permanent site code.
* **Warehouse Code:** Generated automatically sequentially (`WH-001`, `WH-002`...). Once assigned, a warehouse code is strictly immutable because it forms foreign keys across inventory, purchase orders, BOM execution, and audit tables.
* **Warehouse Status:**
  * `active:` Fully operational. Eligible for purchase order deliveries, inventory storage, production consumption, transfers, and order dispatches.
  * `constrained:` The warehouse is operational but flagged for physical space limitations, safety caps, or operational constraints.
  * `inactive:` Decommissioned or dormant. Excluded from new PO delivery drop-downs, production issues, and sales order fulfillment.
* **Parent Factory Linkage:** Establishes which physical manufacturing plant a warehouse resides within. Essential for capacity planning and internal stock transfers.
* **Automatic Quarantine Bin (`QUARANTINE`):** Every warehouse automatically creates an internal location record with code `QUARANTINE` (named *"Quarantine hold"*). When goods fail QC in GRN inspection, the system automatically routes them to this bin.
* **Allowed Product Types:** Configurable list (*raw_material*, *finished_good*, *consumable*) dictating which categories of stock are permitted in this facility.

### Step-by-Step: Common Tasks

#### To add a new manufacturing factory
1. Go to **Factory & Warehouse** → **Factories** tab.
2. Click **New factory**.
3. Enter the **Name** (e.g., "Hosur Assembly Plant").
4. Enter the street address, City, State code, and Postal code.
5. Click **Save**. The factory code is assigned automatically.

#### To add a new warehouse and link it to a factory
1. Go to the **Warehouses** tab.
2. Click **New warehouse**.
3. Enter the **Name** (e.g., "Hosur Battery Cell Store").
4. Select the **Status** (default is *active*).
5. In the **Factory** dropdown, select the parent factory (e.g., "Hosur Assembly Plant"). Leave blank if this is a standalone off-site logistics depot.
6. Fill in the street address, City, Postal code, State, and Country.
7. Click **Save**. The warehouse is created, and its `QUARANTINE` bin is automatically provisioned in the database.

#### To edit an existing factory or warehouse
1. Find the factory or warehouse in its respective tab.
2. Click **Edit** on that row.
3. Update the allowable fields (address, name, status, or parent factory linkage).
4. Click **Save**. Note that a warehouse's code is read-only and cannot be changed.

#### To bulk-upload factories from a CSV spreadsheet
1. On the **Factories** tab, click **Bulk Upload**.
2. Click **Download sample CSV** to obtain `factory_bulk_upload_template.csv`.
3. Columns include: `code, name, addressLine1, addressLine2, city, stateCode, postalCode, country, contactEmail, contactPhone, notes, status`.
4. Populate your rows (the `name` column is mandatory; `code` can be left blank for automatic generation).
5. Drag and drop the CSV into the upload modal and click **Process upload**.
6. Review results and download the error report for any failed rows.

#### To bulk-upload warehouses from a CSV spreadsheet
1. On the **Warehouses** tab, click **Bulk Upload**.
2. Click **Download sample CSV** to obtain `warehouse_bulk_upload_template.csv`.
3. Columns include: `code, name, status, factoryCode, allowedProductTypes, addressLine1, addressLine2, city, stateCode, postalCode, country, contactEmail, contactPhone, capacityUnits, notes`.
4. To link a warehouse to a factory in bulk, provide the parent factory's code in the `factoryCode` column (the factory must already exist).
5. Process the upload and review per-row outcomes.

### Validation Rules & Things That Can Go Wrong
* **Code Immutability:** Once a warehouse or factory is created, its code can never be edited.
* **Mandatory Name:** Creating a factory or warehouse requires a non-empty name.
* **Factory Linkage Integrity:** If you link a warehouse to a factory, that factory must be in *active* status. Linking to an inactive or non-existent factory code fails with an error.
* **Quarantine Guarantee:** The system will not permit removing or bypassing a warehouse's initial quarantine bin.
* **Deactivation Safeguards:** Changing a warehouse to *inactive* does not delete historical records, but blocks new PO line destinations and new production allocations to that site.

### Frequently Asked Questions

**Q: Can a warehouse exist without being linked to any factory?**  
A: Yes. Many supply chains operate central distribution centers, finished goods depots, or regional 3PL hubs that are not located inside a manufacturing plant. Leaving the Factory selector blank creates an independent standalone warehouse.

**Q: What does the "constrained" warehouse status do?**  
A: The *constrained* status indicates that the warehouse is still operational but experiencing capacity bottlenecks or restrictions. It signals to planners and store managers that new large shipments should be diverted when possible.

**Q: Why can't I edit a warehouse's code?**  
A: Warehouse codes (like `WH-001`) are foundational foreign keys stored across inventory ledgers, stock movement logs, purchase order lines, and production orders. Allowing them to change would break historical ledger integrity.

**Q: How does setting up factories and warehouses affect user permissions?**  
A: Under *Users & Roles Administration*, an administrator can restrict any user's role assignment to specific factories or warehouses (Site Access scoping). If a user is scoped to "Pune Plant", they will only see warehouses and stock belonging to Pune Plant across the entire ERP.

---

## 10. Production, BOM Execution & Finished Goods Allocation
`SUPPLY CHAIN` • Route: `/production` • Detail: `/production/:id` • Orders Allocation: `/orders` • Permissions: `inventory:read` (module view), `production:plan` (create runs), `production:complete` (complete runs), `order:allocate` (finished goods allocation)

### Purpose
This module records the manufacturing of finished goods — consuming raw materials according to a product's BOM, producing traceable finished-good units, and tracking who completed each assembly stage. It also covers packing and shipping already-allocated order lines, and the Finished Goods Allocation workspace where specific finished-good units are reserved against sales-order lines (that workspace's controls physically live on the Orders page's Order Allocation tab).

### How to Get There
Sidebar → Supply chain (or Manufacturing) → **Production & Runs** (path `/production`). Finished Goods Allocation lives on Sidebar → Demand → Orders → **Order Allocation tab** (`/orders`).

### Layout Overview
* **Two tabs on the main Production page:** **Production** and **Order Shipping**.
* **Production Tab:**
  * Stat cards for Planned runs and Active runs.
  * Status filter (*all*, *draft*, *in_progress*, *completed*, *cancelled*), and a **Daily Production Planning** button (with `production:plan`).
  * Table lists Run number (a link), Finished Good SKU, Target Quantity, Warehouse, Status, and a **Complete Production** button (with `production:complete`).
* **Daily Production Planning Dialog:**
  * Select Finished Good and Target Quantity; select the manufacturing Warehouse.
  * The system pulls the active BOM version and displays the required components.
  * A component table shows Required, Available, and Variance. If any component has insufficient stock, it flags **Short** in red.
  * **Auto-pick button:** Automatically selects available Inventory IDs greedily from stock to satisfy requirements.
* **Complete Production Dialog / Detail Page:**
  * Records the actual produced quantity.
  * Generates unique finished good identifiers (**FG-IDs**) with printable serial QR labels.
  * Confirms component consumption from inventory and flags assembly completion.
* **Order Shipping Tab:**
  * Lists customer sales order lines that have already been allocated finished goods.
  * Controls for **Pack** and **Ship** to transition goods through dispatch stages.
* **Order Allocation Tab (under `/orders`):**
  * Dedicated split-screen workspace:
  * Left pane: **Orders Queue** showing confirmed orders with unallocated lines.
  * Right pane: **Unit Pool** displaying available on-hand finished goods in the selected warehouse.
  * Checkbox controls to pick and reserve specific FG-IDs against order lines.

### Key Fields & What They Mean
* **Production Run Number:** Unique run identifier (e.g., `RUN-001`).
* **FG-ID:** The unique serialization code assigned to each finished good unit produced.
* **BOM Variance:** Difference between standard BOM requirement and actual consumed materials.
* **Auto-pick:** Automated matching algorithm that allocates earliest available stock units to meet production component requirements.
* **Reserved Stock:** Finished goods locked against specific customer sales orders that cannot be allocated elsewhere.

### Step-by-Step: Common Tasks

#### To plan a new production run
1. Go to **Production & Runs** → Production tab and click **Daily Production Planning**.
2. Select the **Finished Good** to build, enter the **Target quantity**, and pick the **Warehouse**.
3. Review the component requirements table.
4. Click **Auto-pick** to automatically select raw materials from available inventory, or pick specific Inventory IDs manually.
5. Verify no line shows "Short".
6. Click **Create production run**.

#### To complete a production run and generate FG units
1. Find the in-progress run and click **Complete Production** (or open its detail page).
2. Enter the actual produced quantity.
3. Review consumed raw materials.
4. Confirm completion. The system generates unique FG-IDs, debits raw materials from inventory, and credits the finished goods to available stock.
5. Download or print the generated FG serial QR code labels.

#### To allocate finished goods to a sales order
1. Navigate to **Orders** → **Order Allocation tab**.
2. Select the customer order from the left-hand queue.
3. Select an unallocated order line.
4. From the unit pool on the right, select the specific FG-IDs you wish to allocate.
5. Click **Confirm allocation**.

#### To pack and ship allocated orders
1. Go to **Production & Runs** → **Order Shipping tab**.
2. Find the allocated order line.
3. Click **Pack** when items are boxed and labeled.
4. Click **Ship** when the consignment leaves the loading dock.

### Validation Rules & Things That Can Go Wrong
* A production run cannot be created or completed while any BOM component requirement remains **Short**.
* One allocation can only draw stock from a single warehouse. To fulfill from multiple warehouses, allocate lines separately.
* Pack and Ship quantities cannot exceed the quantity allocated.

### Frequently Asked Questions

**Q: What does Auto-pick actually do?**  
A: It is a convenience tool that greedily matches component requirements against available inventory. It is not an algorithmic FIFO/FEFO optimizer, but a rapid starting point that you can fine-tune manually.

**Q: Why can't I change the warehouse on a run I am completing?**  
A: The warehouse was locked when the run was planned and materials were reserved. Changing the site would require cancelling the run and re-planning.

**Q: Where do I actually allocate finished goods to a customer's order?**  
A: On the Orders page under its *Order Allocation* tab — not on the Production page, even though Production is where the goods were manufactured.

---

## 11. Sales Orders: Intake & Sales Book
`DEMAND` • Route: `/orders` • Permissions: `order:read` (view), `order:write` (create/cancel/upload), `order:override_credit` (credit limit override)

### Purpose
This is order intake: recording what a customer has ordered, at what price, with what terms. Allocating specific stock, packing, shipping and invoicing an order are handled by other modules against the same underlying order — this screen does not perform any of those steps itself.

### How to Get There
Sidebar → Demand (or Sales & Orders) → **Orders** (path `/orders`). Requires `order:read`. The page features two tabs: **Sales Book** (described here) and **Order Allocation** (described in the Production chapter).

### Layout Overview
* **Sales Book tab:**
  * Stat cards for **Open order value** and **Orders count**.
  * Status filter, and — with `order:write` — **Bulk Upload** and **New order** buttons.
  * Table lists Order number (a link), Customer, Total, Promised date, Logistics Cost (who bears it), and a Status pill alongside an Invoiced indicator.
* **New Order Dialog:**
  * Customer picker (search over active customer-type parties).
  * Customer PO number (optional reference).
  * Line-adding area: SKU search, Qty, UOM, unit price (excluding GST), and GST %.
  * Optional attachments (e.g., technical specifications, inverter drawings).
  * Commercial fields: Payment terms, Inverter details, Accessories required, Branding, and **Logistics cost borne by** selector (*Company* / *Client* / *Equally shared*).
* **Order Detail Dialog:**
  * Full status display, subtotal, tax breakdown, and total.
  * Payment status: Paid vs. Outstanding balance with a *Payment pending* or *Fully paid* pill.
  * Per-line table showing quantity ordered, unit price, and allocation status.
  * **Cancel order button** (available prior to shipment, requires a 5-character reason).

### Key Fields & What They Mean
* **Customer:** The party purchasing the goods; must be an active customer party.
* **Unit Price:** Entered excluding GST. The system computes applicable GST and gross amounts per line.
* **Logistics Cost Borne By:** Records commercial agreement (*Company*, *Client*, or *Equally shared*) for logistics reference.
* **Status:** *confirmed*, *allocated*, *partially_allocated*, *shipped*, *partially_shipped*, *invoiced*, *fulfilled*, *partially_fulfilled*, or *cancelled*.
* **Invoiced Pill:** Indicates whether a customer tax invoice has been generated in Finance, independent of shipping status.

### Step-by-Step: Common Tasks

#### To create a new sales order
1. Go to **Orders** → **Sales Book tab** and click **New order**.
2. Search for and select the **Customer**.
3. Optionally enter the customer's PO reference number.
4. For each product, select the SKU, enter quantity, unit price (ex-tax), and GST %, then click **Add line**.
5. Fill in commercial details (Payment terms, logistics cost sharing, branding notes).
6. Click **Create**.

#### To override a credit limit block
1. If creating an order for a customer who has exceeded their credit limit, a red warning banner appears.
2. If your role holds `order:override_credit`, a **"Create anyway (override credit limit)"** button is revealed.
3. Click the override button to confirm creation.

#### To cancel an order
1. Open the order's detail dialog.
2. While the order is in *confirmed*, *allocated*, or *partially_allocated* status, click **Cancel order**.
3. Provide a written reason of at least 5 characters.
4. Click **Confirm cancel**.

### Validation Rules & Things That Can Go Wrong
* An order requires an active customer and at least one valid line item.
* An order cannot be cancelled once any line has been physically shipped.
* Credit limit checks are strictly evaluated against the party's current credit used plus the gross value of the proposed order.

### Frequently Asked Questions

**Q: Why can't I allocate, pack, ship, or invoice from this screen?**  
A: This page handles order intake. Allocation takes place on the Order Allocation tab, packing and shipping occur in Production & Shipping, and invoicing is executed in Finance.

**Q: What does the "Invoiced" pill mean versus the main status pill?**  
A: Fulfillment (shipping) and accounting (invoicing) are decoupled. An order can be fully shipped but not yet invoiced, or invoiced prior to dispatch.

---

## 12. Logistics: Transport, Carrier RFQ & Dispatch
`DEMAND` • Route: `/logistics` • Permissions: `logistics:read` (view), `logistics:write` (create requests/award/dispatch)

### Purpose
Logistics arranges transportation for outgoing customer shipments, incoming vendor pickups, and inter-warehouse stock transfers. It manages carrier quotation requests (RFQs), captures bids from transporters, awards freight contracts, and tracks dispatches through to delivery.

### How to Get There
Sidebar → Demand (or Warehouse & Logistics) → **Logistics TMS** (path `/logistics`). Requires `logistics:read`.

### Layout Overview
* Top statistics strip: Open requests, Pending awards, In-transit dispatches, and Delivered.
* Filter bar: Status filter (*all*, *draft*, *rfq_sent*, *awarded*, *in_transit*, *delivered*), and a **New logistics request** button (with `logistics:write`).
* Table lists Request number (a link), Type (*Customer Delivery*, *Vendor Pickup*, *Inter-warehouse Transfer*), Origin, Destination, Required Date, Awarded Transporter, and Status pill.
* **Logistics Request Dialog:**
  * Request type, Pickup address (origin warehouse or party), Delivery address (destination customer or site).
  * Consignment weight, volume, cargo description, and pickup/delivery window dates.
  * **Carrier RFQ Section:** Multi-select picker to invite registered transporter parties to submit freight quotes.
  * **Quotations Panel:** Lists bids submitted by carriers (rate, transit time, vehicle type).
  * **Award Quote Action:** Select the winning transporter bid. If you select a higher-priced bid over the lowest quote, a mandatory justification field is displayed.
  * **Create Dispatch Action:** Transitions an awarded quote into an active dispatch with driver details, vehicle number, and tracking ID.

### Key Fields & What They Mean
* **Logistics Type:** *customer_delivery*, *vendor_pickup*, or *internal_transfer*.
* **Origin / Destination:** Physical facilities or addresses between which goods are moved.
* **Award Justification:** Mandatory written explanation required whenever a logistics manager awards a shipment to a carrier whose quoted price is not the lowest available bid.
* **Vehicle & Driver Details:** Vehicle registration number, driver name, and mobile number captured at dispatch.

### Step-by-Step: Common Tasks

#### To create a logistics transport request
1. Go to **Logistics TMS** and click **New logistics request**.
2. Select the **Request type**.
3. Choose the **Origin** (e.g., your warehouse) and the **Destination** (e.g., customer site).
4. Enter estimated weight, volume, and required pickup date.
5. In the Transporters field, select one or more carrier parties to receive the RFQ.
6. Click **Create request**.

#### To award a freight quotation
1. Open the logistics request once carrier quotes have been entered.
2. Review the quotes table.
3. Click **Award** next to the selected carrier quote.
4. If the selected bid is not the lowest price, enter a justification explaining your choice (e.g., vehicle availability, specialized handling, transit speed).
5. Confirm award.

#### To create a dispatch
1. Once awarded, click **Create dispatch**.
2. Enter the **Vehicle number**, **Driver name**, and **Driver phone**.
3. Optionally enter LR / Bilty number and tracking reference.
4. Click **Dispatch consignment**. The status moves to *in_transit*.

### Validation Rules & Things That Can Go Wrong
* Creating a dispatch requires an awarded quote.
* Selecting a non-lowest bid without providing a justification is blocked by the system.
* Completed dispatches cannot be reverted.

### Frequently Asked Questions

**Q: Can I create a dispatch without running an RFQ?**  
A: Yes, if your organization uses a single contracted transporter, you can invite that sole carrier, record their rate, award it, and proceed immediately to dispatch.

**Q: What happens when a consignment is delivered?**  
A: Opening the dispatch record and clicking "Mark Delivered" updates the status, records the timestamp in the audit trail, and closes the logistics request.

---

## 13. Finance: Payables, Receivables, Invoicing & Payments
`DEMAND / FINANCE` • Route: `/finance` • Permissions: `finance:read` (view), `invoice:post` (post AP invoices), `order:invoice` (generate customer invoices), `payment:write` (record payments), `payment:approve` (approve/reverse payments)

### Purpose
Finance is the accounting hub of Simple ERP where money owed to vendors (Accounts Payable) and owed by customers (Accounts Receivable) is tracked, three-way vendor invoice matching is performed, customer tax invoices are generated and downloaded, payments are recorded and approved, credit notes are issued, and aging schedules and working capital are monitored.

### How to Get There
Sidebar → Finance → **Finance & AR/AP** (path `/finance`). Requires `finance:read`.

### Layout Overview
Seven dedicated operational tabs:
1. **Committed AR/AP:** Future exposures — purchase orders issued but not yet received (Committed AP) and sales orders confirmed but not yet invoiced (Committed AR).
2. **Account Payables:** Lists all vendor invoices, payment statuses, and **Three-Way Match** statuses. Features the **Post vendor invoice** button (with `invoice:post`).
3. **Account Receivables:** Read-only ledger of customer receivables automatically generated from sales invoices.
4. **Payments:** Inbound customer receipts and outbound vendor disbursements. Action buttons for **Record AP payment**, **Record AR payment**, **Approve**, and **Reverse**.
5. **Invoices:** Central billing console to generate customer tax invoices from fulfilled sales orders and download final PDFs.
6. **Aging:** Visual aging schedule bucketed into Current, 0–30, 31–60, 61–90, and 90+ days past due.
7. **Working Capital:** Executive metrics including Days Sales Outstanding (DSO), Days Payables Outstanding (DPO), inventory valuation, and monthly trends.

### Key Fields & What They Mean
* **Three-Way Matching:** Automatic reconciliation between Vendor Invoice lines, Purchase Order lines, and Goods Receipt Notes (GRN). Flags *matched* or *variance*.
* **Variance Reason:** Mandatory justification required when posting a vendor invoice whose amount differs from the PO/GRN receipt.
* **Payment Direction:** *inbound* (customer AR collection) or *outbound* (vendor AP disbursement).
* **Payment Method:** *bank_transfer*, *cheque*, *cash*, *card*, or *upi*.
* **Match Status:** *matched*, *variance*, or *unmatched*.

### Step-by-Step: Common Tasks

#### To post a vendor invoice with three-way matching
1. Go to Finance → **Account Payables tab** and click **Post vendor invoice**.
2. Select the **Vendor** and enter the **Vendor's invoice number**.
3. Enter the **PO ID** to link the invoice to its purchase order and receipts.
4. Enter line items and amounts.
5. If the system flags a price or quantity variance, enter an explanation in the **Variance reason** field.
6. Click **Post invoice**.

#### To generate and download a customer invoice
1. Go to the **Invoices tab**.
2. Find the eligible sales order (order must be confirmed or shipped).
3. Click **Generate Invoice**. The legal seller entity stamped on the invoice is drawn from the PO & Invoice module.
4. Click **Download Invoice** to save the generated PDF.

#### To record and approve a payment
1. Go to the **Payments tab** and click **Record AP payment** (or **Record AR payment**).
2. Allocate payment amounts across one or more outstanding invoices.
3. Enter total amount, date, and payment method (e.g., bank transfer).
4. Click **Record payment**. The payment enters *pending_approval*.
5. A user with `payment:approve` clicks **Approve** on the payment row to post it to the ledger.

#### To issue a credit note
1. Open an AP or AR invoice that has an outstanding balance.
2. Click **Issue credit note**.
3. Enter the credit note amount and a written reason of at least 5 characters.
4. Click **Confirm**.

### Validation Rules & Things That Can Go Wrong
* Receivables cannot be created by hand; they are strictly spawned when a customer sales order is invoiced.
* Reversing an approved payment requires a mandatory 5-character reason. Note that a reversal posts immediately in Finance but does not automatically un-allocate stock in Orders.
* Invoices cannot be generated for sales orders that have been cancelled or have zero billable lines.

### Frequently Asked Questions

**Q: Why is the "Generate Invoice" button disabled for an order?**  
A: The order has not reached an eligible fulfillment milestone, or an invoice has already been generated for it.

**Q: What is the difference between Payment Status and Match Status on AP?**  
A: *Payment Status* (*unpaid*, *partially_paid*, *settled*) reflects cash settlement. *Match Status* (*matched*, *variance*) reflects whether the bill reconciles with the PO and GRN.

---

## 14. PO & Invoice: Business Entities & Seller Identity Setup
`FINANCE / FOUNDATION` • Route: `/po-invoice` • Permissions: `org:read` (view), `org:write` (create/edit/upload), `po:read` (dropdown resolution)

### Purpose
PO & Invoice manages the organization's own registered legal business entities (subsidiaries, operating companies, manufacturing entities, and state GST branches). These legal entities act as:
1. **Seller of Record on Invoices:** The legal name, registered office address, GSTIN, PAN, and corporate identity stamped onto customer sales invoices and delivery challans.
2. **Buyer / Bill-To Party on POs:** The corporate identity and billing address on purchase orders issued to vendors.
3. **Remittance Banking Rails:** The official bank account name, branch, account number, and IFSC code printed on customer invoices directing where wire payments (NEFT/RTGS/IMPS) should be remitted.
4. **Multi-Vertical Operations:** Allows different operating divisions (e.g., Battery Division vs. Chemicals Division) to raise official documents under distinct legal registrations and tax IDs within a single Simple ERP tenant.

### How to Get There
Sidebar → Finance (or Foundation) → **PO & Invoice** (path `/po-invoice`). Requires `org:read` to view and `org:write` to create, modify, or bulk upload.

### Layout Overview
* **Header:** Displays eyebrow "Foundation", Title **"PO & Invoice"**, and description *"Simple's own legal entities"*.
* **Action Toolbar:** Displays **Bulk Upload** and **New business entity** buttons when holding `org:write`.
* **Desktop Table:**
  * **Code:** Unique entity code (e.g., `ENT-001`), generated automatically.
  * **Name:** Registered corporate name (e.g., "Simple ERP Technologies Pvt Ltd").
  * **Location:** City and Indian State representation (e.g., "Pune, 27 — Maharashtra").
  * **Tax ID:** Registered Tax ID / GSTIN (e.g., `27AABCF1234F1Z5`).
  * **Bank:** Masked bank summary showing Bank Name and last 4 digits (e.g., `HDFC Bank ••4321`).
  * **Default:** Green **Default** pill indicating the primary entity pre-selected on all new documents, or "–".
  * **Status:** Pill displaying *active* or *inactive*.
  * **Actions:** **Edit** button and **Activate** / **Deactivate** toggle button per row.
* **Mobile View:** Stacked `MobileRecordCard` components rendering Code, Name, Location, Tax ID, Bank, Default badge, Status, and full-width actions.
* **New / Edit Business Entity Dialog:**
  * **Name (required):** Registered company name.
  * **Address Lines:** Address Line 1 and Address Line 2.
  * **City & Postal Code:** City and 6-digit postal PIN code.
  * **State & Country:** State selector pre-populated with Indian GST state codes (e.g., "27 — Maharashtra", "29 — Karnataka") and Country (default "IN").
  * **Tax Identifiers:**
    * *Tax ID / GSTIN (optional):* 15-character Goods and Services Tax Identification Number.
    * *Company PAN (optional):* 10-character Permanent Account Number.
  * **Contact Details:**
    * *Contact Email:* Official finance and accounts email address.
    * *Contact Phone:* Accounts department telephone number.
  * **Bank Details:**
    * *Bank Name:* Commercial bank name (e.g., "State Bank of India", "HDFC Bank").
    * *Bank Branch:* Branch locality.
    * *Bank Account Number:* Full current account number.
    * *Bank IFSC Code:* 11-character Indian Financial System Code for wire transfers.
  * **Default Setting:** A checkbox labeled **"Default entity for new POs/invoices"**.
  * **Action Buttons:** Cancel and Save.

### Key Fields & What They Mean
* **Entity Code:** Sequential immutable identifier (`ENT-001`, `ENT-002`...).
* **Default Entity:** Exactly one business entity can be designated as the system default at any given time. When users create a new Purchase Order in Procurement or generate an Invoice in Finance, this default entity is automatically selected in the entity dropdown. Marking an entity as default automatically removes the default flag from all other entities in the database.
* **Tax ID / GSTIN:** The 15-character statutory GST registration. Must begin with the 2-digit state code matching the entity's registered state.
* **PAN:** The 10-character corporate Permanent Account Number used for statutory direct-tax filings and TDS reporting.
* **Bank Details:** The banking coordinates printed on the bottom footer of customer invoices to guide remittances.
* **Status:** *active* entities are selectable on new documents. *inactive* entities are preserved for historical audit trails but cannot be chosen for new POs or invoices.

### Step-by-Step: Common Tasks

#### To create a new legal business entity
1. Navigate to **PO & Invoice** (under Finance or Foundation).
2. Click **New business entity**.
3. Enter the registered **Name** (e.g., "Simple ERP Energy Solutions Pvt Ltd").
4. Enter the registered address: Address Line 1, City, Postal code, and select the **State** from the dropdown.
5. In the statutory section, enter the **Tax ID / GSTIN** and **Company PAN**.
6. In the contact section, enter the **Contact email** (e.g., `billing@axon-erp.local`) and phone.
7. In the Bank details section, enter the **Bank name**, **Branch**, **Account number**, and **IFSC code**.
8. If this entity should be the primary seller pre-populated on new POs and sales invoices, tick **"Default entity for new POs/invoices"**.
9. Click **Save**.

#### To update banking details or registered address
1. Locate the entity in the PO & Invoice table.
2. Click **Edit**.
3. Update the address lines or enter new banking details.
4. Click **Save**. Note: Historical documents already rendered to immutable PDF retain their original stamped information, while all new documents generated will reflect the updated details.

#### To set or switch the default entity
1. Open the entity you want to make default by clicking **Edit**.
2. Tick the checkbox **"Default entity for new POs/invoices"**.
3. Click **Save**. The system updates this entity to default and clears the default status from the previous entity.

#### To deactivate an entity
1. Locate the active entity in the table.
2. Click **Deactivate**.
3. The entity's status changes to *inactive*. It will no longer be offered in dropdowns when creating purchase orders or issuing invoices. To restore it later, click **Activate**.

#### To bulk-upload business entities from a CSV
1. Click **Bulk Upload** on the PO & Invoice screen.
2. Click **Download sample CSV** to obtain `business_entity_bulk_upload_template.csv`.
3. The template contains columns:
   `code, name, addressLine1, addressLine2, city, stateCode, postalCode, country, taxId, taxIdCountry, pan, contactEmail, contactPhone, bankName, bankBranch, bankAccountNumber, bankIfsc, isDefault, status`
4. Fill in your entity details. Set `isDefault` to `true` on the row you wish to make the primary entity.
5. Upload the CSV and click **Process upload**.
6. Review the results summary. Any rows failing validation can be downloaded in an error report.

### Validation Rules & Things That Can Go Wrong
* **Mandatory Name:** Entity creation requires a valid Name string.
* **Single Default Exclusivity:** The system enforces that only one business entity holds `isDefault=true` at any time. When an entity is saved with default enabled, a database trigger or transaction unsets default on all other entities.
* **First Entity Default Rule:** The very first business entity created in a new organization is automatically set as the default entity, regardless of whether the checkbox was ticked.
* **Historical Document Integrity:** Deactivating an entity leaves all purchase orders, goods receipts, and customer invoices previously generated under that entity completely intact.

### Frequently Asked Questions

**Q: What does marking an entity "Default" do?**  
A: It becomes the entity automatically pre-selected when anyone raises a new purchase order in Procurement or generates a new invoice in Finance.

**Q: Can I have more than one active business entity?**  
A: Yes. This is specifically designed for companies operating multiple legal entities, separate regional GST registrations, or distinct business divisions that must invoice under separate corporate entities.

**Q: If I deactivate an entity, do past invoices or POs change?**  
A: No. Past invoices and purchase orders maintain historical integrity. Deactivation only prevents the entity from being chosen for new transactions.

**Q: Where do the bank details entered here actually show up?**  
A: They are printed directly on the PDF invoices generated for customers in the Finance module, instructing clients where to send payment remittances.

---

## 15. Configuration: Categories, Party Types & Sticker Sizes
`ADMINISTRATION / FOUNDATION` • Route: `/configuration` • Permissions: Accessible with `product:read`, `party:read`, or `sticker_size:read`; modifying requires `product:write`, `party:write`, or `sticker_size:write`

### Purpose
Configuration maintains the system-wide controlled master reference catalogs and hardware formatting templates that downstream operational modules depend upon:
1. **Product Categories:** The taxonomy hierarchy used when creating products. Defines allowable product types (*raw_material*, *finished_good*, *consumable*, *service*), batch and expiry tracking requirements, and default tax codes.
2. **Party Types:** The classification taxonomy for vendors, customers, and logistics transporters that governs accounting ledger compatibility (*vendor*, *customer*, *both*).
3. **Sticker Size Templates:** Physical label templates used by warehouse staff when printing barcode and QR-code inventory labels upon receiving goods in GRN & QC. Supports standard paper formats (A4, A5, Letter) and custom thermal rolls, configuring exact sticker dimensions, grid rows/columns, sheet margins, and label gaps, complete with live mathematical boundary fit checking.

### How to Get There
Sidebar → Administration (or Foundation) → **Configuration** (path `/configuration`). The page displays three tabs: **Product Categories**, **Party Types**, and **Sticker Size**. Each tab is displayed based on whether you hold the corresponding read permission.

### Layout Overview
* **Header:** Displays eyebrow "Foundation", Title **"Configuration"**, and description *"The controlled lists the rest of the app draws on."*
* **Three Tabs:** **Product Categories**, **Party Types**, and **Sticker Size**.

#### Tab 1: Product Categories
* **Toolbar:** Displays **New category** button (with `product:write`).
* **Desktop Table:**
  * **Code:** Sequential code (e.g., `PROD-AA01`, `PROD-AA02`), generated automatically.
  * **Product Category:** Category title (e.g., "Lithium Ion Cells", "Solar Inverters", "Packaging Material").
  * **Product Type:** Shows restricted product types or *"Any product type"*.
  * **Products:** Live count of catalog products currently assigned to this category.
  * **Status:** Active or inactive status pill.
* **New Category Dialog:**
  * **Name Input:** Name of the category (e.g., "Battery Modules").
  * **"Applies to (optional)" Pills:** Interactive toggles for `raw_material`, `finished_good`, `consumable`, and `service`. Clicking a pill toggles its inclusion. If all are left unselected, the category is available for any product type.
  * **Buttons:** Cancel and Add category.

#### Tab 2: Party Types
* **Toolbar:** Displays **New party type** button (with `party:write`).
* **Desktop Table:**
  * **Code:** Unique code (e.g., `PT-01`).
  * **Label:** Business classification label (e.g., "Raw Material Supplier", "OEM Distributor", "Logistics Transporter").
  * **Ledger Type:** Pill indicating accounting compatibility: `vendor`, `customer`, or `both`.
  * **Status:** Status pill.
* **New Party Type Dialog:**
  * **Label Input:** Descriptive name (e.g., "Contract Manufacturer").
  * **Ledger Type Dropdown:** Select `vendor`, `customer`, or `both`.
  * **Buttons:** Cancel and Add party type.

#### Tab 3: Sticker Size (QR Label Templates)
* **Toolbar:** Displays **New sticker size** button (with `sticker_size:write`).
* **Desktop Table:**
  * **Name:** Template identifier (e.g., "A4 24-Up Standard Label", "Thermal 50x30 Roll").
  * **Page Size:** Sheet format (`A4`, `A5`, `Letter`, `Custom`).
  * **Sticker Dimensions:** Width × Height in millimeters (e.g., `64.0 × 33.8 mm`).
  * **Columns × Rows:** Grid specification (e.g., `3 × 8`).
  * **Total / Page:** Automatically computed product of columns × rows (e.g., `24`).
  * **Status:** Active / inactive pill.
  * **Actions:** Edit, Activate/Deactivate toggle, and Delete (with confirmation).
* **Mobile View:** Stacked mobile cards showing all layout parameters with touch-friendly action buttons.
* **New / Edit Sticker Size Dialog (36rem width):**
  * **Name (required):** Minimum 2 characters (e.g., "Receiving Bin Label 70x35").
  * **Page Size Dropdown:** Choose from `A4`, `A5`, `Letter`, or `Custom`. Selecting `Custom` immediately reveals:
    * *Page width (mm):* Numeric width of custom roll or sheet.
    * *Page height (mm):* Numeric height.
  * **Sticker Section:**
    * *Sticker width (mm):* Exact width of an individual peelable sticker.
    * *Sticker height (mm):* Exact height of an individual sticker.
  * **Layout Grid Section:**
    * *Number of columns:* Number of horizontal labels across the page.
    * *Number of rows:* Number of vertical labels down the page.
    * *Total stickers / page:* Live calculated display (`columns × rows`).
  * **Margins Section (Paper Edge to First Sticker):**
    * *Left margin (mm)* and *Right margin (mm)*.
    * *Top margin (mm)* and *Bottom margin (mm)*.
  * **Gaps Section (Spacing Between Adjacent Stickers):**
    * *Horizontal gap (mm):* Space between columns.
    * *Vertical gap (mm):* Space between rows.
  * **Live Mathematical Boundary Verification:**
    * The dialog performs real-time arithmetic verifying whether the specified grid and margins physically fit within the selected page dimensions:
      $$	ext{Total Width} = (	ext{cols} 	imes 	ext{width}) + ((	ext{cols} - 1) 	imes 	ext{gapH}) + 	ext{marginL} + 	ext{marginR} \le 	ext{pageWidth}$$
      $$	ext{Total Height} = (	ext{rows} 	imes 	ext{height}) + ((	ext{rows} - 1) 	imes 	ext{gapV}) + 	ext{marginT} + 	ext{marginB} \le 	ext{pageHeight}$$
    * If either axis exceeds page limits, a prominent warning alert appears dynamically explaining the exact dimension conflict (e.g., *"Layout exceeds page width by 4.2mm"*).
  * **Buttons:** Cancel and Add sticker size (or Save).

### Key Fields & What They Mean
* **Category Product Types:** Restricts categories so users cannot assign a raw material category to a finished good product, enforcing clean catalog governance.
* **Party Ledger Type:** Determines where parties assigned this type can be selected across the system. A party type marked `vendor` cannot be selected on customer sales orders, preventing billing errors.
* **Custom Page Size:** Enables support for specialized direct-thermal and thermal-transfer roll printers (e.g., Zebra, TSC) where the page size equals the individual label dimensions (e.g., 1 column × 1 row on continuous feed).
* **Margins and Gaps:** Precision millimeter controls that align PDF sticker output with die-cut sticker sheets (e.g., Avery label templates).

### Step-by-Step: Common Tasks

#### To create a new product category
1. Go to **Configuration** → **Product Categories** tab.
2. Click **New category**.
3. Enter the **Name** (e.g., "Power Inverters").
4. Under "Applies to", click to select applicable product types (e.g., `finished_good`). Leave unselected if applicable to all types.
5. Click **Add category**.

#### To create a new party classification type
1. Go to the **Party Types** tab.
2. Click **New party type**.
3. Enter the **Label** (e.g., "Freight Forwarder").
4. Select the **Ledger type** (`vendor`, `customer`, or `both`). For a freight forwarder, select `vendor`.
5. Click **Add party type**.

#### To configure an A4 multi-sticker sheet template
1. Go to the **Sticker Size** tab and click **New sticker size**.
2. Enter the **Name** (e.g., "A4 24-Up Avery 70x37").
3. Select **Page size** as `A4`.
4. Enter **Sticker width** as `70` and **Sticker height** as `37`.
5. Enter **Number of columns** as `3` and **Number of rows** as `8` (Total: 24).
6. Enter margins: Left `0`, Right `0`, Top `0`, Bottom `0`.
7. Enter gaps: Horizontal gap `0`, Vertical gap `0`.
8. Ensure no fit warning appears.
9. Click **Add sticker size**.

#### To configure a thermal roll label template
1. Click **New sticker size**.
2. Enter Name: "Zebra 50x30 Continuous".
3. Select **Page size** as `Custom`. Enter Page width `50` and Page height `30`.
4. Enter Sticker width `50` and Sticker height `30`.
5. Set Columns `1` and Rows `1` (Total: 1).
6. Set all margins and gaps to `0`.
7. Click **Add sticker size**.

#### To edit, deactivate, or delete a sticker template
1. Locate the template in the Sticker Size table.
2. Click **Edit** to modify dimensions or margins.
3. Click **Deactivate** to hide it from warehouse receiving dropdowns without deleting history.
4. Click **Delete** to permanently remove an unused template.

### Validation Rules & Things That Can Go Wrong
* **Category Deletion Lock:** A product category cannot be deleted if any products in the catalog are currently assigned to it, or if subcategories exist under it.
* **Category Maximum Depth:** Category hierarchies are constrained to a maximum depth of 5 levels to prevent infinite recursion or unwieldy menu nesting.
* **Sticker Name Length:** A sticker size template requires a unique name of at least 2 characters.
* **Page Boundary Enforcement:** The server verifies layout arithmetic upon save. If margins, gaps, and sticker dimensions exceed paper boundaries, the API rejects the request with a layout violation error.

### Frequently Asked Questions

**Q: Where are Sticker Size templates actually used in daily operations?**  
A: They appear directly in the **Receive goods** dialog in the **GRN & QC** module. When warehouse staff receive a purchase order, they select their preferred sticker template (e.g., "A4 24-Up" or "Thermal 50x30"), and the system formats the generated QR code PDF accordingly.

**Q: Why does my sticker template show a warning saying it "doesn't fit"?**  
A: The sum of your sticker widths multiplied by the column count, plus the horizontal gaps and margins, exceeds the total physical width of the sheet (or the equivalent occurred on the vertical axis). Adjust your dimensions until the warning clears.

**Q: Can I change a Party Type's ledger type after creating it?**  
A: Party types can be edited or deactivated via the API, but you should avoid changing ledger types if existing parties are already actively transacting in Procurement or Sales.

---

## 16. Users & Roles Administration
`FOUNDATION` • Route: `/users` • Permissions: `user:read` (view), `user:write` (invite/edit/roles), `user:delete` (deactivate/delete)

### Purpose
Users & Roles is where user accounts are created and invited, where permissions are assigned through roles, and where a user's access can be scoped to specific warehouses or factories.

### How to Get There
Sidebar → Foundation → Users & roles (path `/users`). Requires `user:read`.

### Layout Overview
* **Two tabs:** **Users** and **Roles**.
* **Users tab:** search box, Role filter, Status filter, and an **Invite user** button (with `user:write`).
* Table lists User (display name and email), Role pill, Site access summary, Status, and **Manage roles** / **Deactivate** actions.
* **Invite user dialog:** Email, Display name, Role selector, and an optional Password field.
* **Manage roles dialog:** change the user's role assignment, and a **Site access** section listing every warehouse and factory with checkboxes to restrict access.
* **Roles tab:** lists system roles (built-in) and custom roles, showing Role name, Description, User count, and an **Edit** button. A **Create role** button opens a dialog to name the role, describe it, and tick the individual permissions it should carry.

### Key Fields & What They Mean
* **Site access (role scoping):** Restricts a user's visibility and actions across the entire app to specific warehouses and/or factories. If none are selected, access is unrestricted company-wide.
* **Segregation of duties:** Custom roles can be flagged to allow or prevent segregation-of-duties overrides.

### Step-by-Step: Common Tasks

#### To invite a new user
1. Go to Users & roles → Users tab and click **Invite user**.
2. Enter the **Email** and **Display name**.
3. Choose their **Role**.
4. Optionally enter an initial password (if omitted, the account is invited to set their own password).
5. Click **Send invitation**.

#### To restrict a user to specific warehouses or factories
1. Find the user and click **Manage roles**.
2. Under **Site access**, tick the specific warehouses and/or factories this user is allowed to work with.
3. Click **Save assignments**.

#### To create a custom role
1. Go to the **Roles tab** and click **Create role**.
2. Enter a Name and Description.
3. Tick every permission this role should carry.
4. Click **Create role**.

### Frequently Asked Questions

**Q: What does "Site access" actually restrict?**  
A: It limits which warehouses and factories a user can see in pickers across Inventory, Production, Procurement, and Logistics.

**Q: Why can't I delete a role?**  
A: Built-in system roles can never be deleted. Custom roles cannot be deleted while any user is still assigned to them.

---

## 17. Documents: Archive, Reprint & Storage
`PLATFORM` • Route: `/documents` • Permissions: `document:read` (view/download), `document:reprint` (re-issue)

### Purpose
A single, searchable company library of every document the system has generated (purchase order PDFs, customer invoices, delivery challans, QR label sheets) as well as uploaded attachments, with the ability to download or reprint from one place.

### How to Get There
Sidebar → Platform → Documents (path `/documents`). Requires `document:read`.

### Layout Overview
* Filter fields for **Related type**, **Related ID**, **Template**, and a free-text **Search filename** box.
* Table lists Filename, Kind (*generated* or *uploaded*), Template, Related record, Scan status, Created date, and **Download** / **Reprint** buttons.

### Key Fields & What They Mean
* **Reprint:** Specifically re-issues an existing generated document (e.g., printing a duplicate invoice copy) without regenerating or altering financial numbers.

### Frequently Asked Questions

**Q: How do I find every document tied to a specific order or PO?**  
A: Set the Related type filter to `order` or `purchase_order` and enter the document ID in the Related ID box.

---

## 18. Notifications: Delivery Log & Outbound Messaging
`PLATFORM` • Route: `/notifications` • Permissions: `notification:read` (view), `notification:write` (retry)

### Purpose
A delivery log of every outbound notification (email and SMS) the system has attempted to dispatch, showing delivery statuses, provider responses, and allowing one-click retries of failed messages.

### How to Get There
Sidebar → Platform → Notifications (path `/notifications`). Requires `notification:read`.

### Layout Overview
* Table listing When, Outcome badge (*sent*, *failed*, *bounced*), Provider, Attempt count, Delivery detail, and a **Retry** button for any failed message.

---

## 19. Audit Trail: Compliance & Action Log
`PLATFORM` • Route: `/audit` • Permissions: `audit:read`

### Purpose
An immutable, append-only chronological log of every significant action performed across the entire system. Essential for statutory compliance, security audits, and forensic review of who performed or authorized critical operations.

### How to Get There
Sidebar → Platform → Audit trail (path `/audit`). Requires `audit:read`.

### Layout Overview
* A continuous table displaying When (timestamp), Actor email, Action (e.g., `po.cancelled`, `party.blocked`, `warehouse.created`), Entity (type and UUID), and the **Reason** string entered by the user.

### Frequently Asked Questions

**Q: Can an audit entry be edited or cleared?**  
A: No. The audit log is strictly append-only by architectural design and database constraints.

---

## 20. User Profile & Security
`ACCOUNT` • Route: `/profile` • Permissions: Accessible to all signed-in users

### Purpose
The personal account management screen where any authenticated user can view their assigned permissions, update their password, and configure Multi-Factor Authentication (MFA).

### How to Get There
Click your avatar or name badge in the top-right of the header and select **"Your profile & security"** (path `/profile`).

### Step-by-Step: Common Tasks

#### To enrol in Multi-Factor Authentication (MFA)
1. Go to your Profile page.
2. In the Multi-Factor Authentication panel, click **Enrol MFA**.
3. Scan the displayed QR code (or copy the secret key) into your authenticator app (Google Authenticator, Authy, Microsoft Authenticator).
4. Enter the current 6-digit code shown in your app into the confirmation box.
5. Click **Confirm**. MFA is now active on your account.

#### To change your account password
1. Go to your Profile page.
2. In the Change Password section, enter your **Current password**.
3. Enter your **New password** and confirm it in **Confirm new password**.
4. Click **Update password**.

---

## 21. General & Cross-Cutting FAQs
`CROSS-CUTTING`

### Signing in & Passwords
**Q: I can't sign in — what should I do?**  
A: Check your email and password. There is no public self-service password reset link on the login screen. Contact an administrator to reset your credentials. Once signed in, you can update your password from your Profile.

**Q: Why was I signed out unexpectedly?**  
A: Sessions use rotating refresh tokens. If your token expires or is invalidated (such as opening the app simultaneously in multiple conflicting browsers), you are returned to `/login`.

### Permissions & Visibility
**Q: Why is a whole module missing from my sidebar?**  
A: The sidebar only renders modules you possess the read permission for (e.g., `inventory:read`, `org:read`, `warehouse:read`). If a module is missing, ask an admin to grant that permission.

**Q: I can view a screen, but the "New", "Edit", or "Delete" buttons are missing?**  
A: Read access and write access are separate permissions. For example, viewing factories requires `warehouse:read`, but creating or modifying them requires `warehouse:write`.

### Site Scoping (Multi-Facility Operations)
**Q: Why do I only see certain warehouses in a dropdown while a colleague sees all of them?**  
A: Your account has been assigned site-scoped permissions under *Users & Roles*. You are restricted to viewing only the specific warehouses or factories assigned to your user account.

### Bulk Uploads
**Q: Which modules support bulk CSV uploads?**  
A: Parties, Products, BOMs, Purchase Orders, GRNs, QC Decisions, Stock Adjustments, Stock Transfers, Production Runs, Sales Orders, Business Entities, Factories, and Warehouses.

**Q: If some rows fail during a bulk upload, do the valid rows get saved?**  
A: Yes. Bulk uploads evaluate each row independently. Valid records are committed, and failed rows are packaged into a downloadable error CSV for correction.

---
*End of User Guide — Simple ERP System Manual*
