# Deploying Simple ERP

Everything runs from local-development defaults, so `docker compose up` needs
no configuration beyond `cp .env.example .env`. Every default is overridable by
environment variable, and the ones that are unsafe or simply non-functional off
a developer's laptop are **rejected at boot** once `APP_ENV=production` is set -
see `production_config_errors` in [backend/app/core/config.py](backend/app/core/config.py).

This document is the list of what has to change, and why each one matters. It
carries over the original app's deployment notes; what differs in this stack is
the topology (one origin, an nginx front door), the worker, and Redis/RabbitMQ.

## Topology

```
                  ┌───────────────────────────────┐
 browser ──TLS──▶ │ your TLS terminator / ingress │        (1 proxy hop)
                  └──────────────┬────────────────┘
                                 ▼
                       frontend  (nginx :80)
                          │  static React build
                          │  /api/*  ───────────────▶  api (uvicorn :8000)
                                                          │        │
                       migrate (one-shot)                 │        ├── postgres
                       worker  ── consumes ── rabbitmq ◀──┘        ├── redis
                                                                   └── (S3 / Gotenberg / SMTP)
```

* **The browser only ever talks to its own origin.** The frontend's nginx proxies
  `/api/` to the API, so there is no CORS to configure. `CORS_ALLOWED_ORIGINS` only
  matters if you serve the frontend from a different origin than the API.
* **The API and the worker are the same image** (`backend/Dockerfile`), started with a
  role: `api`, `worker` or `migrate` (see `docker-entrypoint.sh`).
* **Postgres is the source of truth.** Redis (login rate limit, dashboard cache) and
  RabbitMQ (notification delivery) are helpers: if either is down the API still serves -
  the limiter allows, the cache recomputes, and a queued notification is picked up by the
  worker's database sweep.

## Backend

### Required - the app will not boot without these

| Variable | Why |
|---|---|
| `APP_ENV=production` | Turns on the boot guard. |
| `JWT_SECRET` | The default is published in `.env.example`. Anyone with the repo can otherwise mint valid tokens. `python -c 'import secrets; print(secrets.token_urlsafe(48))'` |
| `ENCRYPTION_SECRET` | Encrypts party tax IDs at rest, and is equally public. **Rotating it makes existing encrypted values unreadable** - set it once, before real data. |
| `FRONTEND_BASE_URL` | Baked into inventory-item QR codes, which get printed and scanned by phones that are not the server. |
| `DATABASE_URL` | Managed Postgres almost always needs `?sslmode=require`. |

### Strongly recommended - logged as warnings at boot

| Variable | What goes wrong without it |
|---|---|
| `TRUSTED_PROXY_HOPS=1` | Behind a load balancer, every client IP the app records is the balancer's: login attempts, session rows, the login rate limiter and the public-intake throttle all collapse onto one address, so one bad actor locks out everybody. Set it to the number of proxies you actually run (compose's frontend nginx counts as one; add your own TLS terminator) - with none in front, leave it `0`, or callers can spoof their own IP. It also makes the app honour `X-Forwarded-Proto`/`-Host`. |
| `REDIS_URL` / `RATE_LIMIT_STORAGE_URI` | Without a shared store, rate limits are counted per worker process and reset on every deploy. Compose points both at the bundled Redis. |
| `S3_BUCKET` + `S3_ACCESS_KEY_ID` + `S3_SECRET_ACCESS_KEY` | All three, or none: generated documents fall back to local disk (`DOCUMENT_LOCAL_DIR`) and vanish when the container restarts. |
| `PDF_ENGINE` + `GOTENBERG_URL` | The `html` default serves HTML with a PDF's name. Use `gotenberg` (needs a Gotenberg service) or `weasyprint` (the image ships its native libraries; compose sets it). |
| `SMTP_*` | Compose defaults to the bundled Mailpit; real mail needs a real relay. |
| `CORS_ALLOWED_ORIGINS` | See the topology note - with the bundled frontend nothing calls the API cross-origin, so an empty value is correct and safest. |

### Async notifications (RabbitMQ worker)

`ASYNC_NOTIFICATIONS=false` (the code default) delivers email/SMS inline, exactly as the
original app does. `true` records a `queued` notification in the request's own transaction,
publishes a message **after commit**, and lets the `worker` service deliver it. Run at least
one worker whenever this is on. `WORKER_SWEEP_SECONDS` (default 30) is how often it re-scans
Postgres for rows whose message was lost or whose retry delay elapsed.

`ASYNC_PDF=true` does the same for generated documents (invoices, PO copies, reprints) on
`DOCUMENT_QUEUE` (`simple.documents`): the request records the document and the worker renders
it. A download that arrives first renders it on the spot, so the flag only ever adds speed. It has
no effect with `PDF_ENGINE=html`.

### Release steps

The `migrate` service runs before the API and worker start, on every `docker compose up`:

```bash
alembic upgrade head           # schema
python -m app.core.bootstrap   # default tenant, system roles, first admin, notification templates
```

Both are idempotent. Outside compose, run them once per deploy before the new version takes
traffic. Set `BOOTSTRAP_ADMIN_PASSWORD` before the first run - left blank, a random password is
generated and printed once in the `migrate` logs, which is a bad place for it.

### Probes

`/healthz` is liveness (no database), `/readyz` is readiness (runs `select 1`). Both answer
unauthenticated.

## Email Config (Foundation)

Outgoing mail is set per kind of email in the app under **Foundation -> Email Config** (permissions `email_config:read` /
`email_config:write`): one row per kind (`purchase-order.issued`, `logistics.rfq`, `invoice.issued`,
`logistics.pre-dispatch`, `user.invitation`) in the `email_configs` table, each with its own mailbox, sender, Cc/Bcc and
switches. The SMTP password is sealed with AES-GCM keyed from `ENCRYPTION_SECRET` (rotating that secret means typing the
mailbox passwords again). A kind with no row, or with "use its own mailbox" off, sends through the `SMTP_*` environment
settings below, exactly as before. In `APP_ENV=production` the app refuses a loopback/private SMTP host. Each send opens its
own connection and the api and worker read the same rows, so edits apply at once with no restart. A kind switched off fails
softly with "This kind of email is switched off in Foundation > Email Config" on the document (PO, RFQ invitation, invoice).

## Sending mail from Gmail / Google Workspace

The platform sends over plain SMTP, so any mailbox works. For a Gmail or Workspace address:

1. On the Google account turn on **2-Step Verification**, then create an **App password**
   (Google Account -> Security -> App passwords). It is a 16-character password used only by this app; your normal
   password will be rejected. (Workspace admins can block app passwords - then use a relay, below.)
2. Set, in `.env` (Compose) or the environment of the api **and** the worker:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true            # or: SMTP_PORT=465 and SMTP_SECURE=true
SMTP_USER=accounts@yourcompany.com
SMTP_PASSWORD=abcd efgh ijkl mnop
SMTP_FROM=Yourcompany <accounts@yourcompany.com>
```

3. Restart the api and worker, then trigger a real send (e.g. issue an invoice or send a PO email) and check the
   delivery log page (Notifications) - `sent` means Google accepted it; `failed` shows the SMTP error.

Things to know: Gmail rewrites the From address to the authenticated mailbox (or a verified "Send mail as"
alias), so keep `SMTP_FROM` equal to `SMTP_USER`; a personal Gmail allows ~500 recipients/day and Workspace
~2,000 - fine for invoices and POs, not for bulk mail. For higher volume or a dedicated sender domain use a
transactional relay (SES, SendGrid, Postmark, Mailgun) with the same four settings - and add SPF/DKIM/DMARC for your
domain so the mail lands in inboxes. Never put the password in git; use your platform's secret store.

## Files (documents, attachments, generated PDFs)

The api **and** the worker read and write document files, so they must share one store. In Compose that is
the `documents` volume mounted at `DOCUMENT_LOCAL_DIR=/data/documents` on both. (Found by running the stack:
with per-container storage the worker rendered a PDF the api could not find, and every download returned
409 `DOCUMENT_FILE_MISSING`.) In production prefer object storage - set `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, `S3_BUCKET` (and the endpoint/region settings) and no volume is needed.

## Backups

Compose runs a `backup` service (`deploy/backup/backup.sh`, on the stock `postgres` image):

* a `pg_dump -Fc` of the database every `BACKUP_INTERVAL_SECONDS` (default daily), plus a tarball of the
  document files when they live on the volume;
* a dump only counts once `pg_restore --list` can read it back and its sha256 is written (written under a
  temporary name, then renamed);
* the newest `BACKUP_KEEP` (default 14) generations are kept, older ones pruned with their checksum and archive;
* the container's health check fails when the last good backup is older than two intervals;
* `BACKUP_POST_HOOK` runs after each good backup with the dump path as `$1` - use it for the off-site copy,
  e.g. `rclone copy "$1" remote:simple-erp-backups`. A backup that lives only on the host that holds the database is
  not a backup.

Manual backup: `docker compose exec backup /bin/sh /backup/backup.sh once`. Files land in the `backups` volume
(`docker compose exec backup ls -l /backups`; copy one out with `docker compose cp backup:/backups/<file> .`).

Restore (`deploy/backup/restore.sh <dump> [database] [--replace] [--documents-into <dir>]`) verifies the checksum,
then restores into a **new** database by default so it can be inspected first:

```bash
docker compose exec backup /bin/sh /backup/restore.sh /backups/simple-erp-20260926-082057.dump simple_erp_check \
    --documents-into /tmp/docs_check
docker compose exec postgres psql -U simple_erp -d simple_erp_check -c "select count(*) from orders"
```

To recover for real: stop `api` and `worker`, run with the live database name and `--replace`, start them again.
Redis and RabbitMQ hold nothing that needs restoring (queues are rebuilt from the database by the sweeper).

Verified on 2026-09-26: a dump of a database with ~300 rows per main table restored into a second database with
identical row counts on every table checked (parties, orders, POs, ledger, audit) and all 7 document files back;
a tampered checksum was refused; pruning kept exactly `BACKUP_KEEP` generations.

## Web app (`frontend/`)

A static Vite build served by nginx. There are no build-time URLs to bake in: the app calls
`/api/...` on whatever origin served it. `VITE_API_BASE_URL` exists for the unusual case of
hosting the API elsewhere.

## Known limitations

* **Access and refresh tokens live in `localStorage`** (`frontend/src/lib/auth.tsx`), so any XSS
  on the web app can read them. Keep the token TTLs short and treat a Content-Security-Policy on
  the proxy as load-bearing.
* **Uploaded documents are never virus-scanned.** `MALWARE_SCANNER_URL` only decides whether a
  row starts at `scan_status='pending'`, and nothing ever advances it.
* **Identity is hand-rolled** (password + TOTP, role/permission model, audit logging, session tracking).

