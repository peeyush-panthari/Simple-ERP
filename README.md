# Simple ERP - FastAPI stack

FastAPI + Postgres + Redis + RabbitMQ, run with Docker Compose, with a
React + TypeScript + Vite + Tailwind + shadcn/ui-style frontend. A modular
monolith (one deployable API, domain packages under `backend/app/domains/`),
not literal microservices - see the migration plan for why. The frontend is
being ported page by page - see "Frontend" below for what's done.

## Run it

```bash
cp .env.example .env            # set the secrets (see the file)
docker compose up --build
```

| What | Where |
|---|---|
| App (React frontend) | http://localhost:5173 |
| API + OpenAPI docs | http://localhost:8000 , `/docs` |
| Health / readiness | `/healthz` , `/readyz` (readiness = database reachable) |
| RabbitMQ management | http://localhost:15672 (user/password from `.env`) |
| Mailpit (all outgoing mail) | http://localhost:8025 |

Startup order: postgres, redis, rabbitmq healthy -> **`migrate`** (runs
`alembic upgrade head`, then the idempotent bootstrap: default tenant, system
roles, first administrator, built-in notification templates; exits) -> **`api`**
and **`worker`**. If `BOOTSTRAP_ADMIN_PASSWORD` is empty a random admin password
is generated and printed once in the `migrate` logs
(`docker compose logs migrate`), login `admin@axon-erp.local`.

One image, three roles (`backend/docker-entrypoint.sh`): `api`, `worker`,
`migrate`.

## What each piece is for

**Postgres** - the source of truth. The 48-migration Alembic chain builds the
whole schema from an empty database and matches the models exactly (checked
with `alembic compare_metadata`: zero differences).

**Redis** - (1) rate limiting: login is limited per client IP, counted in Redis
so the limit is shared by every API process and survives deploys. (2)
`GET /dashboard` is cached per tenant for `DASHBOARD_CACHE_SECONDS` (30 in
compose, 0 = off = recompute live, the default). Both fail open: if Redis is
down, requests still work - the limiter allows and the cache recomputes.

**RabbitMQ + worker** - notification delivery (email/SMS). With
`ASYNC_NOTIFICATIONS=true` a request only records a `queued` notification row in
its own transaction; **after commit** it publishes a message naming that row; the
worker (`python -m app.worker`) delivers it, writes the delivery log, and updates
the invoice / purchase order / RFQ invitation / dispatch that asked for the email
(`email_state` goes `queued` -> `sent`/`failed`). A slow or dead SMTP server can
therefore no longer hold an API worker or fail the business request. With
`ASYNC_NOTIFICATIONS=false` (the code default) delivery is inline, exactly as in
the original app.

The database row - not the message - is the source of truth:

* publish only happens after commit, and never for a rolled-back request;
* if RabbitMQ is down at publish time the failure is logged and swallowed;
* the worker also **sweeps** Postgres every `WORKER_SWEEP_SECONDS` for due
  `queued` rows (lost messages, and transient-failure retries using the backoff
  the row already records), independent of the broker;
* delivery locks the row and only acts on queued/failed ones, so a duplicate
  message or the consumer and sweeper meeting on one row sends once;
* a message that crashes the handler is rejected to `simple.notifications.dead`.

**PDFs** (`ASYNC_PDF=true`, set in compose) follow the same pattern. A generated document -
an invoice, a PO copy, a reprint - is recorded in the request (same row id, URL and file
name as before) and a message naming it is published after commit; the worker renders the PDF
and stores it. The database is again the source of truth: the worker's sweep renders any
document whose message was lost, rendering is idempotent (row-locked), and a download that
arrives before the worker has finished simply renders the document itself - so the worker
makes it faster, never possible. Only "Download PDF" style endpoints that stream a fresh
render in the response (`/purchase-orders/{id}/pdf`, the GRN QR sheet) stay synchronous,
since the PDF *is* their response. With `PDF_ENGINE=html` (the code default) nothing is
deferred; the html engine is instant.

## Email setup

**In the app (recommended):** sign in as an administrator and open **Foundation -> Email Config**. Each kind of email has
its own card - **purchase orders, logistics quotation requests (RFQ), customer invoices, dispatch notices, user
invitations** - and each is saved separately: its own mailbox (a Gmail / Google Workspace address, Microsoft 365, or any
SMTP server), sender name and address, reply-to, standing Cc/Bcc, a "send these emails" switch and a test button. Use
**Set up** on a card, pick a provider preset (or **copy another kind's mailbox**, password included, to reuse one account),
save, then **Send test email**. The **Setup guide** button (top right, and a link on each card) opens a step-by-step
pop-up on where to find every value: Gmail app password, Microsoft 365, other providers, what each field means, and what
common errors mean. Purchase orders can leave from `orders@yourcompany.com`, invoices from
`billing@yourcompany.com`, RFQs from `logistics@yourcompany.com`. Passwords are stored encrypted and never shown again.
Access is the `email_config:read` / `email_config:write` permissions (System Admin has both). A kind without its own
mailbox keeps using the server settings below; **Reset to default** on a card removes its setup.

**On the server (fallback / first boot):** out of the box every email goes to the bundled **Mailpit** catcher (http://localhost:8025) and nothing leaves your
machine. To send real mail, point the platform at any SMTP mailbox by setting these in `.env` (Compose) or in the
environment of **both** the `api` and the `worker`, then restart them:

| Setting | Meaning |
|---|---|
| `SMTP_HOST`, `SMTP_PORT` | the mail server, e.g. `smtp.gmail.com`, `587` |
| `SMTP_STARTTLS=true` | encrypt a plain connection (port 587) |
| `SMTP_SECURE=true` | encrypt from the start instead (port 465); use one of the two |
| `SMTP_USER`, `SMTP_PASSWORD` | the mailbox login (an app password, not your normal one) |
| `SMTP_FROM` | sender shown to recipients, e.g. `Yourcompany <accounts@yourcompany.com>` |

**Gmail or a company address on Google Workspace**

1. On that Google account turn on 2-Step Verification, then create an **App password**
   (Google Account -> Security -> App passwords). Workspace admins can block app passwords; if so use a relay
   (SES, SendGrid, Postmark, Mailgun) with the same five settings.
2. Put in `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_STARTTLS=true
   SMTP_USER=accounts@yourcompany.com
   SMTP_PASSWORD=<the 16-character app password>
   SMTP_FROM=Yourcompany <accounts@yourcompany.com>
   ```
3. `docker compose up -d api worker` (or restart your processes).
4. Send a real one (issue an invoice, or "send email" on a purchase order) and open **Notifications**: `sent`
   means the server accepted it, `failed` shows the SMTP error and can be retried from that page.

Keep `SMTP_FROM` equal to `SMTP_USER` (Gmail rewrites the sender to the signed-in mailbox). Gmail allows about 500
recipients a day (personal) or 2,000 (Workspace): fine for invoices and POs, not bulk mail. Add SPF/DKIM/DMARC for
your domain so mail reaches inboxes, and keep the password in a secret store, not in git. More detail in
[DEPLOYMENT.md](DEPLOYMENT.md#sending-mail-from-gmail--google-workspace).

## Procurement: requisition -> approval -> sourcing -> purchase order -> vendor steps -> GRN

Procurement has three tabs following the buying process: **Purchase requisitions**, **Sourcing (RFQ)** and **Purchase orders**
(a user only sees the tabs their permissions allow; a user with only requisition permissions sees just the first).

1. **Requisition (employee).** *New requisition*: priority, needed-by date, deliver-to warehouse, department, a reason, and
   items picked **from our products** or described as **something new** (free text, for things not in the product list yet).
   *Save as draft* keeps it private; *Submit* sends it on (a reason is required).
2. **Manager approval.** If the requester has a manager (Users & roles > *Manage roles* > **Reports to**, or when inviting a
   user), the requisition goes to that manager first (**With manager**). The manager approves (optional note) or rejects
   (a reason the requester sees; they edit and send it again, back to the manager). Someone with no manager on file skips this
   step. Only the requester's *current* manager can decide, so changing **Reports to** re-routes what is still waiting; nobody
   decides on their own requisition. Purchase does not see a requisition until its manager has approved it.
3. **Purchase review.** Purchase approves or rejects (**With Purchase**). An approved requisition can go two ways: *Create
   purchase order directly* (the dialog opens with the items filled in), or *Start sourcing (RFQ)*.
4. **Sourcing (RFQ).** *Start sourcing* asks the chosen vendors for a quotation (`PRFQ-0001`...): reply-by date, terms, and an
   email to each vendor with a login-free request (vendors without an email address are flagged; **Resend** later). The buyer
   records each vendor's reply as a *quotation* (price, GST, lead time per item; freight; validity; payment terms) or marks the
   vendor as declined. Invite more vendors, or withdraw one, while the RFQ is open.
5. **Compare & award.** Every offer side by side per item, with GST and freight included so it compares what would actually be
   paid: the lowest is marked, the others show how far above it they are, plus the whole-basket total per vendor and the
   cheapest single vendor. The lowest per item is preselected; choosing anything else, an item only one vendor quoted, or an
   expired quotation needs a **reason** (kept with the award). *Reopen* undoes an award until purchase orders exist.
6. **Purchase orders.** *Create purchase orders* raises **one PO per winning vendor**, priced from that vendor's quotation
   (their GST, payment terms, freight), linked back to the RFQ and requisition. The requisition becomes **PO raised** with the
   PO numbers. Free-text items cannot be ordered (no product yet): they are listed so they can be set up and ordered separately.
   Cancelling an RFQ sends the requisition back to *approved*.

7. **Vendor acknowledgement.** Open a purchase order > **Acknowledgement & documents**: record the vendor's reply - *acknowledged*,
   *acknowledged with changes* (say what changed, optionally the delivery date they confirmed) or *declined* (say why) - with their
   reference. The PO list shows it (**Vendor ack**), and a declined order gets a warning to cancel or amend it.
8. **Vendor document submission.** In the same tab, upload what the vendor sends: PO acknowledgement, proforma invoice, technical
   documents, test/quality certificates, other. Files (PDF, image, Word, Excel, CSV, text; up to 10 MB) are stored with the usual
   document storage and downloaded through the order, so anyone who can see the PO can read them. The vendor has no login: the
   buyer uploads what arrives by email.
9. **Dispatch documentation.** **Dispatch** tab > *Record dispatch* for each shipment (partial shipments are fine; you cannot ship
   more than is still open on the order): dispatch date, expected arrival, transporter, vehicle number, LR/docket/AWB, driver,
   packages, weight, the vendor's invoice, **packing list**, **delivery challan** and **e-way bill** (12 digits + validity) as they
   apply, and files attached to the shipment (packing list, challan, e-way bill, transport document, tax invoice). A shipment worth
   over Rs 50,000 without an e-way bill number gets a warning (never a block - it depends on the goods and the route); overdue
   shipments and expired e-way bills are flagged.
10. **GRN (unchanged).** The receiving team sees the open shipment (vehicle, LR, packing list, due date) when they pick the PO in
    *Receive goods*. Goods received against the PO are shared out over its shipments, oldest first: a fully covered shipment turns
    **Arrived** by itself, and goes back to *In transit* if that GRN is cancelled. *Mark arrived* does it by hand.

- **Permissions** (Users & roles): `po:vendor` records acknowledgements, vendor documents and dispatches (reading needs `po:read`, or
  `warehouse:read` for the receiving team); `pr:read` + `pr:write` employees; `pr:team_approve` managers; `pr:approve` Purchase review;
  `sourcing:read` / `sourcing:write` (run RFQs, record quotations) / `sourcing:award` (award and order, plus `po:write`).
  The product, warehouse and vendor pickers open up to these permissions.
- **Email**: the vendor request uses the *Purchase quotation requests (RFQ)* kind under Foundation > Email Config (own mailbox,
  Cc/Bcc, on/off) and the `purchase-rfq.issued` template (created by `python -m app.core.bootstrap`, which the Docker `migrate`
  step runs).
- API: `/api/v1/purchase-requisitions` (list, counts, create, get, patch, `submit`, `manager-approve`, `manager-reject`,
  `approve`, `reject`, `cancel`, `link-po`) and `/api/v1/purchase-rfqs` (list, create, get, `comparison`, `vendors`,
  `quotations/{vendorId}`, `award`, `reopen`, `purchase-orders`, `cancel`). Every step is audited.
- Local demo logins (dev database only, password `DevUser#Pass2026`): `employee@example.test` (reports to `manager@example.test`)
  and `purchase@example.test`.

## Feedback on every click

- **Loading:** a thin bar runs across the top of the window whenever the app is waiting for the server (after a short delay, so quick
  requests don't flicker), route pages show a spinner while they load, and a button that starts work (Save, Create, Approve, Sign in...)
  shows a spinner, ignores further clicks and is marked busy until the work finishes - so it can't be submitted twice.
- **One button colour:** every button is the same teal (`.action-btn-primary`); Cancel, destructive and secondary actions are told
  apart by their label. (`tone="ghost" | "danger"` still exists on `ActionButton` but maps to the same style - to bring back a red
  destructive button, change `ACTION_TONE` in `components/erp/ui.tsx` and add the rule back in `styles/theme.css`.)
- **Pressed feel:** buttons, the header controls, tabs, segmented toggles and menu items sink and darken while pressed
  (disabled with `prefers-reduced-motion`).
- **Dialogs:** Save closes the dialog once the save has finished; cancelling a record (order, PO, GRN, requisition, RFQ) closes it
  once the cancellation has gone through; Cancel / Back just closes.
- **Account menu:** the user button at the top right opens **Profile** (MFA enrolment and change password) and **Logout**.

## Behind a proxy

Set `TRUSTED_PROXY_HOPS` to the number of reverse proxies in front of the API.
`0` (default) ignores `X-Forwarded-For` entirely so callers cannot spoof their
IP past the login limiter or the public-intake throttle; `N` trusts the N-th
entry from the right.

## Tests

```bash
cd backend
.venv/bin/python -m pytest -q          # 735 tests
```

Real Postgres, no mocking of the database. The suite runs on its own database
(`axon_erp_migration_test`), separate from the dev one (`axon_erp_migration`, what `backend/.env`
points at): `tests/conftest.py` derives the test URL from `DATABASE_URL` by appending `_test`
(or use `TEST_DATABASE_URL`) and refuses to run against a name that doesn't end in `_test`.
Create it once with `createdb axon_erp_migration_test` (owner = the app role); the tables are
created by the suite itself. 604 of the tests are the
original Flask app's own suite, ported and run unchanged through `tests/flaskcompat.py`
(regenerate with `scripts/port_original_tests.py`); the rest cover the new pieces (RabbitMQ
publish/sweep, async PDF, Redis, proxy handling). The infra tests use a
throwaway `redis-server` on a private port (skipped if the binary is missing) and a recording
fake behind the `Broker` interface for RabbitMQ.

`scripts/compare_api.py` and `scripts/compare_flow.py` diff this API against a running copy of the
original Flask app on the same database (432 GETs plus a 48-step business scenario: no real
differences).

## Verified in a browser (against the running API)

Side by side with the running Reflex app on the same database (`scripts/compare_flow.py`: 48-step scenario,
0 differences). The UI comparison is measured, not eyeballed: a fingerprint of every text node and form
control (position, font, size, weight, colour) was collected from both apps for 19 pages at 1280px and 375px
plus 8 create dialogs, and diffed. That found and fixed, app-wide: the system font stack, Radix-sized buttons,
tabs, tables, inputs, selects, headings, badges and dialogs (600px, 24px padding, bold display title), the
indigo link colour, table header colour, page headers that shrink to their title, flush panels, and
Radix-style compact selects. What is left are colour-space differences of a few shades (Radix's neutral grey
vs. our bluish grey) and the deliberate deviations below.

Flows run end to end in the React UI: all 13 bulk uploads (each dialog's own sample CSV, through the real API,
plus real uploads for products, parties, business entities, factories and warehouses), GRN edit and cancel,
BOM version draft -> submit -> approve, AR payment and its reversal, credit note, POD entry, hardware-scanner
input (typed ID + Enter jumps to the item) and camera scanning (a QR photo decoded server-side and added to a
production run).

## Docker (verified)

`docker compose up --build` was run for real (Colima on this Mac; `docker-compose` binary): all eight services come
up healthy, `migrate` runs and exits, login works through the nginx frontend, and the **worker consumes both
queues from a real RabbitMQ**. Checked with generated data (`backend/scripts/dev_data.py`): every notification is
published, acked and lands in Mailpit (invoice and RFQ mails); every generated PDF is rendered by the worker with
WeasyPrint and downloads with 200. Broker outage: with RabbitMQ stopped the api stays ready (`/readyz` 200), the
business requests still succeed, the notifications wait as `queued`, and after the broker returns the worker
reconnects and delivers all of them. Running it also found and fixed a real bug: api and worker did not share the
document directory, so worker-rendered PDFs were unreadable by the api (see DEPLOYMENT.md, "Files").

```bash
cp .env.example .env     # ports in .env can be shifted (API_PORT, WEB_PORT, POSTGRES_PORT ...)
docker compose up --build -d
```

## Test data

`backend/scripts/dev_data.py [--scale 1] [--seed 7]` fills a database through the public API only (so every rule,
sequence, ledger and audit row comes from the real code): vendors, customers, products, POs received and QC'd
(some partial / under QC / cancelled), BOMs, production runs, sales orders in every state (allocated .. shipped,
invoiced, paid, credit-noted, reversed, cancelled), vendor invoices, transport requests through POD. Scale 8 gives
~540 orders, ~300 POs, ~13,000 inventory items; the main list endpoints answer in 5-17 ms and the dashboard in
~110 ms on that. `API_BASE`, `API_EMAIL`, `API_PASSWORD` point it at any stack (use a new `--seed` per run).

## Not verified yet

Firefox and Safari (only a Chromium-based browser was used), and a run against a copy of your real production data.

## Frontend (`frontend/`)

React 19 + TypeScript + Vite + Tailwind v4, TanStack Query for server state,
React Router, Radix primitives (the ones shadcn/ui wraps) for dialogs, tabs,
popovers. The browser only talks to its own origin: Vite proxies `/api` to the
API in dev, and the frontend container's nginx does in Compose - no CORS.

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 ; API on :8000 (VITE_API_PROXY_TARGET to change)
npm test               # 1300 tests
npm run build
```

Log in with a known account: `cd backend && .venv/bin/python scripts/dev_admin.py`
(creates `dev-admin@example.test` / `DevAdmin#Pass2026`).

**Design fidelity.** `src/styles/theme.css` is the Reflex app's `theme.css`
carried over verbatim (same OKLCH tokens, radii, shadows, fonts and component
recipes), and `src/components/erp/ui.tsx` is a 1:1 port of its `ui_kit.py`
(`Pill`, `PageHeader`, `Panel`, `StatCard`, `DataTable`, `Modal`, `Field`, ...),
so pages render with the same classes. Where the Reflex app mixed native Radix
Themes widgets with its own kit, the port uses the kit consistently (compact
`size="sm"` buttons stand in for Radix `size="1"`).

**Behaviour parity is tested, not eyeballed:** `src/test/golden.json` holds
1,270+ expected outputs generated by running the Reflex app's own Python
(`format.py` money/qty/date formatting - including the round-half-even ties
where Python and JS disagree - and the status-tone/label helpers from
`ui_kit.py`); the vitest suite asserts the TypeScript ports match. The auth
provider (single-flight refresh-token rotation, 401 retry, MFA, sign-out) has
its own tests.

**Every page is ported** - login, control tower, profile, audit trail, system
status, documents, notifications, users & roles, party master (+ detail), PO &
invoice (business entities), factory & warehouse, configuration, products & BOM,
procurement, GRN & QC (+ the per-GRN QC route), inventory (+ item detail),
production & shipping (list, order shipping, new / complete / detail), orders
(sales book + order allocation), logistics and finance. All 26 Reflex routes have
a React counterpart; an address that matches no page renders "Page not found".

Behaviours that differ from the Reflex app on purpose - fixes and polish, not
changes of workflow: products, procurement, orders, logistics, payables, receivables, payments
and the production run list get pagination controls (the old pages fetched `meta` but
never rendered a pager), destructive buttons keep a red tint (Reflex's theme override rendered them neutral), toolbars and filter rows wrap on phones (in Reflex the search box is squashed and the New/Bulk buttons sit off-screen), the architecture page also shows Redis and RabbitMQ health, the inventory-item action forms (QC / transfer / adjustment) keep inner padding (Reflex left them flush against the panel border), and the BOM builder's finished-good / component
pickers query the catalogue directly instead of whatever page of the products
table happened to be open. Test-report and inverter attachments download through
the authorised client (a bare link to `/api/v1/documents/...` carries no token).

**Seeding a dev database for browser checks** (API running on :8000):

```bash
cd backend
.venv/bin/python scripts/dev_admin.py                       # the dev-admin login
.venv/bin/python scripts/dev_seed.py                        # categories, products, vendor, customer, warehouse, factory
.venv/bin/python scripts/dev_stock.py SEED-RM-CELL 20       # PO -> GRN -> QC accept, so there is stock to consume
```
