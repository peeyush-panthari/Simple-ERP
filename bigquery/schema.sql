-- =====================================================================
-- Simple ERP -- BigQuery schema (generated)
-- =====================================================================
-- Source of truth: app/services/bq_schema.py, which introspects
-- Base.metadata (the SQLAlchemy models in app/models/) at import time.
-- This file is a plain-SQL rendering of exactly what
-- `python scripts/bq_schema_sync.py --sql` reports right now, for
-- review/manual `bq query` use outside the app. It is NOT hand-maintained
-- - regenerate it (or just run bq_schema_sync.py directly against a real
-- GCP project) whenever a model changes, rather than hand-editing this.
--
-- Project : REPLACE_WITH_GCP_PROJECT_ID  (placeholder - see app/config.py:gcp_project_id)
-- Dataset : simple_erp_dev
-- Location: asia-south1
--
-- Every CheckConstraint / ForeignKeyConstraint / UniqueConstraint / Index
-- from the Postgres models is dropped (BigQuery enforces none of them) and
-- listed as a comment under its table instead, per Phase 2 of the plan at
-- /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md -- each one is a
-- candidate for an app-level check if it was the only guard.
--
-- 9 tables from the Postgres model set are DELIBERATELY OMITTED
-- below: verified (by diffing every frontend API call against every
-- backend route) to have no path that populates them in the app as it
-- actually runs today - shipping them to a fresh analytics warehouse would
-- just be permanently-empty tables. Re-add any of these the day the
-- frontend gains the workflow that writes to it:
--   - locations: no 'create location' UI anywhere, and no seed data - the zone/aisle/rack/bin tree is never populated
--   - logistics_invoices: backend route exists, logistics_state.py never calls POST or GET /logistics-invoices
--   - po_approval_records: no approve/reject UI - procurement_state.py: a PO is issued immediately on creation
--   - po_revisions: no amend UI - same module as po_approval_records
--   - product_aliases: backend has full CRUD (/products/:id/aliases), product_state.py never calls it
--   - product_images: backend has full CRUD (/products/:id/images), product_state.py never calls it
--   - product_specs: backend has full CRUD (/products/:id/specs), product_state.py never calls it
--   - putaway_tasks: POST /grns/:id/putaway is never called by the frontend, and would be unusable anyway (needs a location, and locations is empty)
--   - uom_conversions: backend has full CRUD (/products/:id/conversions), product_state.py never calls it
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev`
OPTIONS (location = "asia-south1");

-- ---- accounting_periods (7 columns) ----
-- dropped CheckConstraint 'accounting_periods_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.accounting_periods` (
  tenant_id STRING NOT NULL,
  period STRING NOT NULL,
  status STRING NOT NULL,
  closed_by STRING,
  closed_at TIMESTAMP,
  reopened_by STRING,
  reopened_at TIMESTAMP
)
CLUSTER BY tenant_id;

-- ---- audit_log (11 columns) ----
-- dropped Index 'audit_log_tenant_created_idx' - BigQuery has no indexes
-- dropped Index 'audit_log_tenant_entity_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.audit_log` (
  id STRING NOT NULL,
  tenant_id STRING,
  actor_id STRING,
  actor_email STRING,
  action STRING NOT NULL,
  entity_type STRING NOT NULL,
  entity_id STRING,
  reason STRING,
  correlation_id STRING,
  meta JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- business_entities (23 columns) ----
-- dropped UniqueConstraint 'business_entities_tenant_code_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'business_entities_tax_country_ck' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'business_entities_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.business_entities` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  name STRING NOT NULL,
  status STRING NOT NULL,
  is_default BOOL NOT NULL,
  address_line1 STRING,
  address_line2 STRING,
  city STRING,
  state_code STRING,
  postal_code STRING,
  country STRING NOT NULL,
  tax_id STRING,
  tax_id_country STRING,
  pan STRING,
  contact_email STRING,
  contact_phone STRING,
  bank_name STRING,
  bank_branch STRING,
  bank_account_number STRING,
  bank_ifsc STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- doc_sequences (3 columns) ----
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.doc_sequences` (
  tenant_id STRING NOT NULL,
  prefix STRING NOT NULL,
  current_value INT64 NOT NULL
)
CLUSTER BY tenant_id, prefix;

-- ---- documents (17 columns) ----
-- dropped CheckConstraint 'documents_scan_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'documents_storage_key_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'documents_kind_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'documents_storage_backend_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'documents_template_idx' - BigQuery has no indexes
-- dropped Index 'documents_related_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.documents` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  kind STRING NOT NULL,
  template STRING,
  filename STRING NOT NULL,
  content_type STRING NOT NULL,
  bytes INT64 NOT NULL,
  checksum STRING,
  storage_backend STRING NOT NULL,
  storage_key STRING NOT NULL,
  related_type STRING,
  related_id STRING,
  render_data JSON,
  scan_status STRING NOT NULL,
  scan_detail STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- email_configs (21 columns) ----
-- dropped UniqueConstraint 'email_configs_tenant_purpose_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'email_configs_security_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'email_configs_port_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.email_configs` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  purpose_key STRING NOT NULL,
  send_enabled BOOL NOT NULL,
  enabled BOOL NOT NULL,
  smtp_host STRING NOT NULL,
  smtp_port INT64 NOT NULL,
  security STRING NOT NULL,
  smtp_user STRING NOT NULL,
  smtp_password_sealed STRING,
  from_name STRING NOT NULL,
  from_email STRING NOT NULL,
  reply_to STRING,
  cc JSON NOT NULL,
  bcc JSON NOT NULL,
  last_test_at TIMESTAMP,
  last_test_ok BOOL,
  last_test_error STRING,
  updated_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- factories (16 columns) ----
-- dropped CheckConstraint 'factories_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'factories_tenant_code_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.factories` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  name STRING NOT NULL,
  status STRING NOT NULL,
  address_line1 STRING,
  address_line2 STRING,
  city STRING,
  state_code STRING,
  postal_code STRING,
  country STRING NOT NULL,
  contact_email STRING,
  contact_phone STRING,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- idempotency_keys (8 columns) ----
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.idempotency_keys` (
  tenant_id STRING NOT NULL,
  `key` STRING NOT NULL,
  method STRING NOT NULL,
  route STRING NOT NULL,
  request_hash STRING NOT NULL,
  response_status INT64 NOT NULL,
  response_body JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id;

-- ---- login_attempts (7 columns) ----
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.login_attempts` (
  id INT64 NOT NULL,
  tenant_id STRING,
  email STRING NOT NULL,
  ip STRING,
  successful BOOL NOT NULL,
  reason STRING,
  attempted_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- notification_templates (14 columns) ----
-- dropped CheckConstraint 'notification_templates_channel_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'notification_templates_key_version_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'notification_templates_key_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.notification_templates` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  `key` STRING NOT NULL,
  channel STRING NOT NULL,
  version INT64 NOT NULL,
  subject STRING,
  body_text STRING NOT NULL,
  body_html STRING,
  description STRING,
  active BOOL NOT NULL,
  is_builtin BOOL NOT NULL,
  builtin_hash STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- notifications (25 columns) ----
-- dropped CheckConstraint 'notifications_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'notifications_channel_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'notifications_pending_idx' - BigQuery has no indexes
-- dropped Index 'notifications_related_idx' - BigQuery has no indexes
-- dropped Index 'notifications_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.notifications` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  template_key STRING NOT NULL,
  template_version INT64,
  channel STRING NOT NULL,
  recipients ARRAY<STRING>,
  cc ARRAY<STRING>,
  bcc ARRAY<STRING>,
  subject STRING,
  body_text STRING NOT NULL,
  body_html STRING,
  data JSON NOT NULL,
  attachments JSON NOT NULL,
  related_type STRING,
  related_id STRING,
  status STRING NOT NULL,
  attempts INT64 NOT NULL,
  next_attempt_at TIMESTAMP NOT NULL,
  last_error STRING,
  provider STRING,
  provider_message_id STRING,
  sent_at TIMESTAMP,
  correlation_id STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- parties (26 columns) ----
-- dropped CheckConstraint 'parties_credit_used_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'parties_tax_country_ck' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'parties_risk_flag_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'parties_credit_limit_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'parties_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'parties_tenant_code_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'parties_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'parties_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.parties` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  legal_name STRING NOT NULL,
  display_name STRING NOT NULL,
  type STRING NOT NULL,
  subtype STRING,
  status STRING NOT NULL,
  tax_id STRING,
  tax_id_country STRING,
  registration_no STRING,
  payment_terms STRING,
  credit_limit NUMERIC NOT NULL,
  credit_used NUMERIC NOT NULL,
  currency STRING,
  risk_flag STRING NOT NULL,
  industry STRING,
  website STRING,
  notes STRING,
  blocked_reason STRING,
  blocked_at TIMESTAMP,
  blocked_by STRING,
  activated_at TIMESTAMP,
  version INT64 NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- party_types (6 columns) ----
-- dropped CheckConstraint 'party_types_base_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.party_types` (
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  label STRING NOT NULL,
  base_type STRING NOT NULL,
  status STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, code;

-- ---- product_categories (12 columns) ----
-- dropped UniqueConstraint 'product_categories_tenant_code_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'product_categories_parent_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.product_categories` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  product_category STRING NOT NULL,
  parent_id STRING,
  product_types ARRAY<STRING>,
  requires_batch BOOL NOT NULL,
  requires_expiry BOOL NOT NULL,
  default_tax_code STRING,
  status STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- public_request_throttle (4 columns) ----
-- dropped CheckConstraint 'public_request_throttle_scope_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.public_request_throttle` (
  scope STRING NOT NULL,
  identity STRING NOT NULL,
  hour_bucket TIMESTAMP NOT NULL,
  count INT64 NOT NULL
)
CLUSTER BY scope, identity, hour_bucket;

-- ---- rejection_codes (6 columns) ----
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.rejection_codes` (
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  description STRING,
  active BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, code;

-- ---- sticker_sizes (19 columns) ----
-- dropped CheckConstraint 'sticker_sizes_page_size_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'sticker_sizes_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'sticker_sizes_columns_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'sticker_sizes_tenant_name_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'sticker_sizes_rows_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'sticker_sizes_tenant_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.sticker_sizes` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  name STRING NOT NULL,
  page_size STRING NOT NULL,
  page_width_mm NUMERIC NOT NULL,
  page_height_mm NUMERIC NOT NULL,
  sticker_width_mm NUMERIC NOT NULL,
  sticker_height_mm NUMERIC NOT NULL,
  columns INT64 NOT NULL,
  `rows` INT64 NOT NULL,
  margin_left_mm NUMERIC NOT NULL,
  margin_right_mm NUMERIC NOT NULL,
  margin_top_mm NUMERIC NOT NULL,
  margin_bottom_mm NUMERIC NOT NULL,
  gap_horizontal_mm NUMERIC NOT NULL,
  gap_vertical_mm NUMERIC NOT NULL,
  status STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- suppressions (5 columns) ----
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.suppressions` (
  tenant_id STRING NOT NULL,
  address STRING NOT NULL,
  reason STRING NOT NULL,
  source STRING,
  suppressed_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id;

-- ---- tenants (10 columns) ----
-- dropped UniqueConstraint 'UniqueConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'UniqueConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'tenants_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.tenants` (
  id STRING NOT NULL,
  name STRING NOT NULL,
  slug STRING NOT NULL,
  country STRING NOT NULL,
  base_currency STRING NOT NULL,
  status STRING NOT NULL,
  settings JSON NOT NULL,
  zitadel_org_id STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY id;

-- ---- auth_policies (12 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.auth_policies` (
  tenant_id STRING NOT NULL,
  password_min_length INT64 NOT NULL,
  password_require_symbol BOOL NOT NULL,
  password_require_number BOOL NOT NULL,
  password_require_mixed_case BOOL NOT NULL,
  password_max_age_days INT64 NOT NULL,
  password_history INT64 NOT NULL,
  mfa_required BOOL NOT NULL,
  max_failed_attempts INT64 NOT NULL,
  lockout_minutes INT64 NOT NULL,
  session_idle_minutes INT64 NOT NULL,
  inactive_user_days INT64 NOT NULL
)
CLUSTER BY tenant_id;

-- ---- delivery_log (9 columns) ----
-- dropped CheckConstraint 'delivery_log_outcome_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'delivery_log_notification_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.delivery_log` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  notification_id STRING NOT NULL,
  attempt INT64 NOT NULL,
  outcome STRING NOT NULL,
  provider STRING,
  provider_message_id STRING,
  detail STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- party_addresses (14 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'party_addresses_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'party_addresses_default_uniq' - BigQuery has no indexes
-- dropped Index 'party_addresses_party_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.party_addresses` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  party_id STRING NOT NULL,
  type STRING NOT NULL,
  label STRING,
  line1 STRING NOT NULL,
  line2 STRING,
  city STRING NOT NULL,
  state_code STRING,
  postal_code STRING,
  country STRING NOT NULL,
  is_default BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- party_bank_accounts (18 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'party_bank_accounts_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'party_bank_accounts_party_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.party_bank_accounts` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  party_id STRING NOT NULL,
  account_name STRING NOT NULL,
  account_number_encrypted STRING NOT NULL,
  account_number_last4 STRING NOT NULL,
  ifsc STRING,
  swift STRING,
  bank_name STRING NOT NULL,
  branch STRING,
  status STRING NOT NULL,
  approved_by STRING,
  approved_at TIMESTAMP,
  rejected_reason STRING,
  created_by STRING,
  supersedes_id STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- party_contacts (10 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'party_contacts_party_idx' - BigQuery has no indexes
-- dropped Index 'party_contacts_primary_uniq' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.party_contacts` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  party_id STRING NOT NULL,
  name STRING NOT NULL,
  role STRING,
  email STRING,
  phone STRING,
  is_primary BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- party_versions (11 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'party_versions_party_version_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'party_versions_party_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.party_versions` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  party_id STRING NOT NULL,
  version INT64 NOT NULL,
  change_type STRING NOT NULL,
  snapshot JSON NOT NULL,
  reason STRING,
  changed_by STRING NOT NULL,
  changed_by_email STRING,
  correlation_id STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- payments (25 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'payments_direction_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'payments_method_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'payments_gateway_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'payments_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'payments_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'payments_exchange_rate_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'payments_tenant_party_date_idx' - BigQuery has no indexes
-- dropped Index 'payments_tenant_direction_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.payments` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  direction STRING NOT NULL,
  party_id STRING NOT NULL,
  party_name STRING NOT NULL,
  payment_date DATE NOT NULL,
  period STRING NOT NULL,
  method STRING NOT NULL,
  reference STRING,
  currency STRING NOT NULL,
  exchange_rate NUMERIC NOT NULL,
  amount NUMERIC NOT NULL,
  unallocated NUMERIC NOT NULL,
  status STRING NOT NULL,
  approved_by STRING,
  approved_at TIMESTAMP,
  reverses_id STRING,
  reversal_reason STRING,
  bank_account_last4 STRING,
  gateway_provider STRING,
  gateway_payment_id STRING,
  notes STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- products (31 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'products_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'products_tenant_sku_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'products_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'products_category_idx' - BigQuery has no indexes
-- dropped Index 'products_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.products` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  sku STRING NOT NULL,
  name STRING NOT NULL,
  make STRING,
  model_number STRING,
  description STRING,
  type STRING NOT NULL,
  category_id STRING,
  uom STRING NOT NULL,
  alternate_uoms ARRAY<STRING>,
  hsn_code STRING,
  status STRING NOT NULL,
  batch_tracked BOOL NOT NULL,
  expiry_tracked BOOL NOT NULL,
  storage_conditions STRING,
  reorder_point NUMERIC,
  reorder_qty NUMERIC,
  lead_time_days INT64,
  currency STRING NOT NULL,
  purchasable BOOL NOT NULL,
  sellable BOOL NOT NULL,
  weight_kg NUMERIC,
  volume_m3 NUMERIC,
  published_at TIMESTAMP,
  deprecated_at TIMESTAMP,
  deprecated_reason STRING,
  first_transaction_at TIMESTAMP,
  first_transaction_ref STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- roles (9 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'roles_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'roles_tenant_name_key' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.roles` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  name STRING NOT NULL,
  description STRING,
  business_unit STRING,
  is_system BOOL NOT NULL,
  status STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- users (20 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'users_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'users_tenant_email_key' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'users_external_identity_key' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.users` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  email STRING NOT NULL,
  display_name STRING NOT NULL,
  password_hash STRING,
  status STRING NOT NULL,
  business_unit STRING,
  manager_id STRING,
  phone STRING,
  mfa_secret STRING,
  mfa_enabled BOOL NOT NULL,
  failed_attempts INT64 NOT NULL,
  locked_until TIMESTAMP,
  last_login_at TIMESTAMP,
  password_changed_at TIMESTAMP,
  must_change_password BOOL NOT NULL,
  external_idp STRING,
  external_subject STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- warehouses (19 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'warehouses_tenant_code_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'warehouses_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'warehouses_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.warehouses` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  code STRING NOT NULL,
  name STRING NOT NULL,
  status STRING NOT NULL,
  factory_id STRING,
  allowed_product_types ARRAY<STRING>,
  address_line1 STRING,
  address_line2 STRING,
  city STRING,
  state_code STRING,
  postal_code STRING,
  country STRING NOT NULL,
  contact_email STRING,
  contact_phone STRING,
  capacity_units NUMERIC,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- boms (8 columns) ----
-- dropped UniqueConstraint 'boms_tenant_product_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'boms_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'boms_tenant_sku_idx' - BigQuery has no indexes
-- dropped Index 'boms_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.boms` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  product_id STRING NOT NULL,
  product_sku STRING NOT NULL,
  status STRING NOT NULL,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- orders (46 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_exchange_rate_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_packing_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_dates_ck' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'orders_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_logistics_cost_borne_by_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'orders_logistics_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'orders_tenant_customer_idx' - BigQuery has no indexes
-- dropped Index 'orders_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.orders` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  customer_id STRING NOT NULL,
  customer_name STRING NOT NULL,
  customer_ref STRING,
  status STRING NOT NULL,
  packing_status STRING NOT NULL,
  order_date DATE NOT NULL,
  promised_date DATE NOT NULL,
  warehouse_id STRING,
  warehouse_code STRING,
  currency STRING NOT NULL,
  exchange_rate NUMERIC NOT NULL,
  subtotal NUMERIC NOT NULL,
  tax_total NUMERIC NOT NULL,
  charges NUMERIC NOT NULL,
  total NUMERIC NOT NULL,
  paid_amount NUMERIC NOT NULL,
  fully_paid BOOL NOT NULL,
  payment_terms STRING,
  delivery_line1 STRING,
  delivery_line2 STRING,
  delivery_city STRING,
  delivery_state_code STRING,
  delivery_postal_code STRING,
  delivery_country STRING NOT NULL,
  notes STRING,
  inverter_details STRING,
  accessories_required STRING,
  branding STRING,
  logistics_cost_borne_by STRING,
  logistics_state STRING NOT NULL,
  logistics_request_id STRING,
  logistics_override_by STRING,
  logistics_override_reason STRING,
  logistics_raised_at TIMESTAMP,
  invoice_id STRING,
  invoice_number STRING,
  cancelled_reason STRING,
  cancelled_at TIMESTAMP,
  shipped_at TIMESTAMP,
  closed_at TIMESTAMP,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- password_history (3 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.password_history` (
  user_id STRING NOT NULL,
  password_hash STRING NOT NULL,
  changed_at TIMESTAMP NOT NULL
)
CLUSTER BY user_id, changed_at;

-- ---- purchase_orders (47 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_ack_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_receipt_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_exchange_rate_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_dates_ck' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_email_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_orders_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_orders_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'purchase_orders_tenant_status_idx' - BigQuery has no indexes
-- dropped Index 'purchase_orders_vendor_idx' - BigQuery has no indexes
-- dropped Index 'purchase_orders_warehouse_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_orders` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  revision INT64 NOT NULL,
  supersedes_id STRING,
  vendor_id STRING NOT NULL,
  vendor_name STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  warehouse_code STRING NOT NULL,
  business_entity_id STRING,
  status STRING NOT NULL,
  po_date DATE NOT NULL,
  expected_date DATE NOT NULL,
  currency STRING NOT NULL,
  exchange_rate NUMERIC NOT NULL,
  subtotal NUMERIC NOT NULL,
  tax_total NUMERIC NOT NULL,
  cgst NUMERIC NOT NULL,
  sgst NUMERIC NOT NULL,
  igst NUMERIC NOT NULL,
  charges NUMERIC NOT NULL,
  total NUMERIC NOT NULL,
  payment_terms STRING,
  payment_mode STRING,
  incoterms STRING,
  notes STRING,
  approval_tier INT64 NOT NULL,
  approved_by STRING,
  approved_at TIMESTAMP,
  issued_at TIMESTAMP,
  email_state STRING NOT NULL,
  email_sent_at TIMESTAMP,
  email_error STRING,
  pdf_document_id STRING,
  ack_status STRING NOT NULL,
  ack_date DATE,
  ack_ref STRING,
  ack_confirmed_date DATE,
  ack_notes STRING,
  ack_recorded_by STRING,
  ack_recorded_at TIMESTAMP,
  receipt_status STRING NOT NULL,
  cancelled_reason STRING,
  cancelled_at TIMESTAMP,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- role_permissions (4 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.role_permissions` (
  role_id STRING NOT NULL,
  permission STRING NOT NULL,
  granted_at TIMESTAMP NOT NULL,
  granted_by STRING
)
CLUSTER BY role_id, permission;

-- ---- sessions (10 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'UniqueConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'sessions_user_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.sessions` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  user_id STRING NOT NULL,
  refresh_token_hash STRING NOT NULL,
  issued_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP,
  rotated_to STRING,
  ip STRING,
  user_agent STRING
)
CLUSTER BY tenant_id, id;

-- ---- user_roles (7 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'user_roles_effective_range_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.user_roles` (
  user_id STRING NOT NULL,
  role_id STRING NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE,
  scopes ARRAY<STRING>,
  assigned_by STRING,
  assigned_at TIMESTAMP NOT NULL
)
CLUSTER BY user_id, role_id;

-- ---- bom_versions (19 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'bom_versions_range_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'bom_versions_yield_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'bom_versions_bom_version_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'bom_versions_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'bom_versions_bom_state_idx' - BigQuery has no indexes
-- dropped Index 'bom_versions_tenant_state_range_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.bom_versions` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  bom_id STRING NOT NULL,
  version INT64 NOT NULL,
  state STRING NOT NULL,
  yield_percent NUMERIC NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE,
  notes STRING,
  routing_notes STRING,
  approved_by STRING,
  approved_at TIMESTAMP,
  rejected_reason STRING,
  cost_rollup NUMERIC,
  currency STRING NOT NULL,
  revised_from_id STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- grns (28 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'grns_tenant_vendor_invoice_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grns_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'grns_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'grns_tenant_status_received_idx' - BigQuery has no indexes
-- dropped Index 'grns_tenant_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.grns` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  po_id STRING NOT NULL,
  po_number STRING,
  vendor_id STRING,
  vendor_name STRING,
  warehouse_id STRING NOT NULL,
  warehouse_code STRING,
  status STRING NOT NULL,
  received_date DATE NOT NULL,
  vehicle_number STRING,
  delivery_note STRING,
  gate_entry_no STRING,
  invoice_number STRING,
  sticker_size_id STRING,
  sticker_size_name STRING,
  has_vendor_qr BOOL NOT NULL,
  inspected_by STRING,
  posted_by STRING,
  inspected_at TIMESTAMP,
  posted_at TIMESTAMP,
  rejection_reason STRING,
  cancellation_reason STRING,
  notes STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- invoices (24 columns) ----
-- dropped CheckConstraint 'invoices_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'invoices_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'invoices_email_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'invoices_tenant_customer_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.invoices` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  order_id STRING NOT NULL,
  customer_id STRING NOT NULL,
  customer_name STRING NOT NULL,
  business_entity_id STRING,
  invoice_date DATE NOT NULL,
  due_date DATE NOT NULL,
  currency STRING NOT NULL,
  subtotal NUMERIC NOT NULL,
  tax_total NUMERIC NOT NULL,
  charges NUMERIC NOT NULL,
  total NUMERIC NOT NULL,
  cgst NUMERIC NOT NULL,
  sgst NUMERIC NOT NULL,
  igst NUMERIC NOT NULL,
  place_of_supply STRING,
  status STRING NOT NULL,
  document_id STRING,
  email_state STRING NOT NULL,
  email_error STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- po_dispatches (29 columns) ----
-- dropped UniqueConstraint 'po_dispatches_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_dispatches_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'po_dispatches_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.po_dispatches` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  po_id STRING NOT NULL,
  number STRING NOT NULL,
  status STRING NOT NULL,
  dispatch_date DATE NOT NULL,
  expected_arrival DATE,
  transporter STRING,
  vehicle_no STRING,
  lr_no STRING,
  driver_name STRING,
  driver_phone STRING,
  packages INT64,
  gross_weight_kg NUMERIC,
  invoice_no STRING,
  invoice_date DATE,
  invoice_value NUMERIC,
  packing_list_no STRING,
  delivery_challan_no STRING,
  delivery_challan_date DATE,
  eway_bill_no STRING,
  eway_bill_valid_until DATE,
  notes STRING,
  delivered_at TIMESTAMP,
  auto_delivered BOOL NOT NULL,
  cancelled_reason STRING,
  recorded_by_name STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- po_lines (20 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'po_lines_line_no_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_discount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_received_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_rejected_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_lines_unit_price_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'po_lines_product_idx' - BigQuery has no indexes
-- dropped Index 'po_lines_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.po_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  po_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  description STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  unit_price NUMERIC NOT NULL,
  discount NUMERIC NOT NULL,
  tax_code STRING NOT NULL,
  tax_rate NUMERIC NOT NULL,
  net_amount NUMERIC NOT NULL,
  tax_amount NUMERIC NOT NULL,
  gross_amount NUMERIC NOT NULL,
  expected_date DATE,
  received_qty NUMERIC NOT NULL,
  rejected_qty NUMERIC NOT NULL,
  status STRING NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- purchase_requisitions (29 columns) ----
-- dropped CheckConstraint 'purchase_requisitions_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_requisitions_priority_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_requisitions_rejected_stage_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_requisitions_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'purchase_requisitions_requester_idx' - BigQuery has no indexes
-- dropped Index 'purchase_requisitions_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_requisitions` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  status STRING NOT NULL,
  priority STRING NOT NULL,
  requester_id STRING NOT NULL,
  requester_name STRING NOT NULL,
  requester_email STRING,
  department STRING,
  warehouse_id STRING,
  warehouse_code STRING,
  required_by DATE,
  justification STRING,
  manager_id STRING,
  manager_name STRING,
  manager_decided_at TIMESTAMP,
  manager_note STRING,
  rejected_stage STRING,
  submitted_at TIMESTAMP,
  reviewed_by_id STRING,
  reviewed_by_name STRING,
  reviewed_at TIMESTAMP,
  review_note STRING,
  purchase_order_id STRING,
  purchase_order_number STRING,
  cancelled_reason STRING,
  cancelled_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- reservations (23 columns) ----
-- dropped CheckConstraint 'reservations_issued_qty_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'reservations_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'reservations_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'reservations_order_idx' - BigQuery has no indexes
-- dropped Index 'reservations_open_idx' - BigQuery has no indexes
-- dropped Index 'reservations_order_line_uniq' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.reservations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  batch_no STRING,
  location_id STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  allocation_legs JSON,
  issued_qty NUMERIC NOT NULL,
  status STRING NOT NULL,
  order_id STRING,
  order_line_id STRING,
  reference_type STRING NOT NULL,
  reference_no STRING,
  expires_at TIMESTAMP,
  released_at TIMESTAMP,
  released_reason STRING,
  issued_at TIMESTAMP,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- stock_balances (13 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'stock_balances_key_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'stock_balances_expiry_idx' - BigQuery has no indexes
-- dropped Index 'stock_balances_product_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.stock_balances` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  location_key STRING NOT NULL,
  location_id STRING,
  batch_no STRING NOT NULL,
  expiry_date DATE,
  bucket STRING NOT NULL,
  uom STRING NOT NULL,
  quantity NUMERIC NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- stock_ledger (23 columns) ----
-- seq: Postgres IDENTITY column - value must be app-assigned (app.services.sequences) instead of DB auto-increment
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'stock_ledger_bucket_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'stock_ledger_movement_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'stock_ledger_batch_idx' - BigQuery has no indexes
-- dropped Index 'stock_ledger_reference_idx' - BigQuery has no indexes
-- dropped Index 'stock_ledger_idempotency_idx' - BigQuery has no indexes
-- dropped Index 'stock_ledger_balance_idx' - BigQuery has no indexes
-- dropped Index 'stock_ledger_seq_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.stock_ledger` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  seq INT64 NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  location_id STRING,
  batch_no STRING,
  expiry_date DATE,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  bucket STRING NOT NULL,
  movement_type STRING NOT NULL,
  reference_type STRING NOT NULL,
  reference_id STRING NOT NULL,
  reference_no STRING,
  unit_cost NUMERIC,
  currency STRING,
  reason STRING,
  reverses_id STRING,
  actor_id STRING,
  correlation_id STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- transfers (19 columns) ----
-- dropped CheckConstraint 'transfers_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'transfers_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'transfers_distinct_ck' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'transfers_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'transfers_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.transfers` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  batch_no STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  source_warehouse_id STRING NOT NULL,
  source_location_id STRING,
  dest_warehouse_id STRING NOT NULL,
  dest_location_id STRING,
  status STRING NOT NULL,
  dispatched_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  cancelled_reason STRING,
  reason STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- transport_requests (38 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'transport_requests_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'transport_requests_source_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'transport_requests_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'transport_requests_service_level_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'transport_requests_tenant_order_idx' - BigQuery has no indexes
-- dropped Index 'transport_requests_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.transport_requests` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  source STRING NOT NULL,
  order_id STRING,
  order_number STRING,
  customer_id STRING,
  customer_name STRING,
  status STRING NOT NULL,
  source_warehouse_id STRING,
  source_warehouse_code STRING,
  origin_line1 STRING,
  origin_city STRING,
  origin_state_code STRING,
  origin_postal_code STRING,
  origin_country STRING NOT NULL,
  dest_line1 STRING NOT NULL,
  dest_city STRING NOT NULL,
  dest_state_code STRING,
  dest_postal_code STRING,
  dest_country STRING NOT NULL,
  goods JSON NOT NULL,
  weight_kg NUMERIC,
  volume_m3 NUMERIC,
  package_count INT64,
  target_date DATE,
  service_level STRING NOT NULL,
  insurance_required BOOL NOT NULL,
  insured_value NUMERIC,
  special_instructions STRING,
  `trigger` STRING,
  override_reason STRING,
  raised_by STRING,
  requester_email STRING,
  requester_ip STRING,
  cancelled_reason STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- user_role_factories (3 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.user_role_factories` (
  user_id STRING NOT NULL,
  role_id STRING NOT NULL,
  factory_id STRING NOT NULL
)
CLUSTER BY user_id, role_id, factory_id;

-- ---- user_role_warehouses (3 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.user_role_warehouses` (
  user_id STRING NOT NULL,
  role_id STRING NOT NULL,
  warehouse_id STRING NOT NULL
)
CLUSTER BY user_id, role_id, warehouse_id;

-- ---- ap_invoices (30 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_match_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_paid_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_exchange_rate_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'ap_invoices_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_source_type_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ap_invoices_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'ap_invoices_vendor_invoice_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'ap_invoices_tenant_vendor_idx' - BigQuery has no indexes
-- dropped Index 'ap_invoices_tenant_status_due_idx' - BigQuery has no indexes
-- dropped Index 'ap_invoices_tenant_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.ap_invoices` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  source_type STRING NOT NULL,
  source_id STRING,
  vendor_invoice_no STRING,
  po_id STRING,
  po_number STRING,
  grn_id STRING,
  vendor_id STRING NOT NULL,
  vendor_name STRING NOT NULL,
  invoice_date DATE NOT NULL,
  due_date DATE NOT NULL,
  period STRING NOT NULL,
  currency STRING NOT NULL,
  exchange_rate NUMERIC NOT NULL,
  amount NUMERIC NOT NULL,
  tax_amount NUMERIC NOT NULL,
  paid_amount NUMERIC NOT NULL,
  status STRING NOT NULL,
  match_status STRING NOT NULL,
  match_variance NUMERIC,
  match_note STRING,
  approved_by STRING,
  approved_at TIMESTAMP,
  dispute_reason STRING,
  notes STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- ar_invoices (29 columns) ----
-- dropped CheckConstraint 'ar_invoices_credit_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ar_invoices_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'ar_invoices_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ar_invoices_exchange_rate_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ar_invoices_einvoice_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ar_invoices_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'ar_invoices_paid_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'ar_invoices_tenant_customer_idx' - BigQuery has no indexes
-- dropped Index 'ar_invoices_irn_uniq' - BigQuery has no indexes
-- dropped Index 'ar_invoices_einvoice_idx' - BigQuery has no indexes
-- dropped Index 'ar_invoices_tenant_status_due_idx' - BigQuery has no indexes
-- dropped Index 'ar_invoices_tenant_order_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.ar_invoices` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  order_id STRING,
  order_number STRING,
  invoice_id STRING,
  customer_id STRING NOT NULL,
  customer_name STRING NOT NULL,
  invoice_date DATE NOT NULL,
  due_date DATE NOT NULL,
  period STRING NOT NULL,
  currency STRING NOT NULL,
  exchange_rate NUMERIC NOT NULL,
  amount NUMERIC NOT NULL,
  tax_amount NUMERIC NOT NULL,
  paid_amount NUMERIC NOT NULL,
  credit_amount NUMERIC NOT NULL,
  status STRING NOT NULL,
  written_off_by STRING,
  written_off_reason STRING,
  irn STRING,
  ack_no STRING,
  ack_date TIMESTAMP,
  signed_qr STRING,
  einvoice_status STRING NOT NULL,
  einvoice_error STRING,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- bom_approvals (8 columns) ----
-- dropped CheckConstraint 'bom_approvals_decision_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'bom_approvals_version_at_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.bom_approvals` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  version_id STRING NOT NULL,
  actor STRING NOT NULL,
  actor_email STRING,
  decision STRING NOT NULL,
  reason STRING,
  `at` TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- bom_components (13 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'bom_components_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'bom_components_version_line_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'bom_components_scrap_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'bom_components_version_line_idx' - BigQuery has no indexes
-- dropped Index 'bom_components_tenant_product_idx' - BigQuery has no indexes
-- dropped Index 'bom_components_primary_uniq' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.bom_components` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  bom_version_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  component_product_id STRING NOT NULL,
  component_sku STRING NOT NULL,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  scrap_percent NUMERIC NOT NULL,
  is_alternate BOOL NOT NULL,
  alternate_for_line INT64,
  notes STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- grn_lines (22 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grn_lines_rejected_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grn_lines_accept_reject_le_received_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grn_lines_received_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grn_lines_quality_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'grn_lines_grn_line_no_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'grn_lines_accepted_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'grn_lines_tenant_po_line_idx' - BigQuery has no indexes
-- dropped Index 'grn_lines_grn_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.grn_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  grn_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  po_line_id STRING,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  ordered_qty NUMERIC,
  received_qty NUMERIC NOT NULL,
  accepted_qty NUMERIC NOT NULL,
  rejected_qty NUMERIC NOT NULL,
  uom STRING NOT NULL,
  batch_no STRING,
  expiry_date DATE,
  manufacture_date DATE,
  location_id STRING,
  location_code STRING,
  quality_status STRING NOT NULL,
  rejection_code STRING,
  rejection_note STRING,
  unit_price NUMERIC NOT NULL,
  deleted_at TIMESTAMP
)
CLUSTER BY tenant_id, id;

-- ---- order_lines (21 columns) ----
-- dropped CheckConstraint 'order_lines_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_allocated_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'order_lines_line_no_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_unit_price_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_shipped_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_packed_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'order_lines_discount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'order_lines_order_idx' - BigQuery has no indexes
-- dropped Index 'order_lines_tenant_product_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.order_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  order_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  description STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  unit_price NUMERIC NOT NULL,
  discount NUMERIC NOT NULL,
  tax_code STRING NOT NULL,
  tax_rate NUMERIC NOT NULL,
  net_amount NUMERIC NOT NULL,
  tax_amount NUMERIC NOT NULL,
  gross_amount NUMERIC NOT NULL,
  reservation_id STRING,
  allocated_qty NUMERIC NOT NULL,
  packed_qty NUMERIC NOT NULL,
  shipped_qty NUMERIC NOT NULL,
  status STRING NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- po_dispatch_lines (5 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'po_dispatch_lines_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'po_dispatch_lines_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.po_dispatch_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  dispatch_id STRING NOT NULL,
  po_line_id STRING NOT NULL,
  quantity NUMERIC NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- po_documents (14 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'po_documents_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.po_documents` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  po_id STRING NOT NULL,
  dispatch_id STRING,
  document_id STRING NOT NULL,
  doc_type STRING NOT NULL,
  reference_no STRING,
  description STRING,
  filename STRING NOT NULL,
  content_type STRING NOT NULL,
  bytes INT64 NOT NULL,
  uploaded_by STRING,
  uploaded_by_name STRING,
  uploaded_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- po_receipts (8 columns) ----
-- dropped UniqueConstraint 'po_receipts_grn_line_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'po_receipts_po_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.po_receipts` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  po_id STRING NOT NULL,
  po_line_id STRING NOT NULL,
  grn_id STRING NOT NULL,
  accepted_qty NUMERIC NOT NULL,
  rejected_qty NUMERIC NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- production_runs (34 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'production_runs_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'production_runs_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'production_runs_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'production_runs_product_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.production_runs` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  bom_version_id STRING,
  bom_version INT64,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  location_id STRING,
  batch_no STRING,
  expiry_date DATE,
  status STRING NOT NULL,
  reversed_by STRING,
  notes STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL,
  production_date DATE,
  pack_id STRING,
  shift STRING,
  bms_make_model STRING,
  screen_type STRING,
  bms_id STRING,
  bluetooth_id STRING,
  iot_id STRING,
  cells_name STRING,
  cells_quantity INT64,
  series_count INT64,
  parallel_count INT64,
  enclosure_name STRING,
  charge_capacity STRING,
  discharge_capacity STRING,
  branding_details STRING
)
CLUSTER BY tenant_id, id;

-- ---- purchase_requisition_lines (10 columns) ----
-- dropped UniqueConstraint 'purchase_requisition_lines_line_no_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_requisition_lines_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'purchase_requisition_lines_req_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_requisition_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  requisition_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  product_id STRING,
  sku STRING,
  item_name STRING NOT NULL,
  notes STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- purchase_rfqs (21 columns) ----
-- dropped UniqueConstraint 'purchase_rfqs_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_rfqs_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'purchase_rfqs_tenant_status_idx' - BigQuery has no indexes
-- dropped Index 'purchase_rfqs_requisition_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_rfqs` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  status STRING NOT NULL,
  requisition_id STRING,
  requisition_number STRING,
  warehouse_id STRING,
  warehouse_code STRING,
  due_date DATE,
  required_by DATE,
  currency STRING NOT NULL,
  terms STRING,
  notes STRING,
  created_by STRING,
  created_by_name STRING,
  awarded_by_name STRING,
  awarded_at TIMESTAMP,
  cancelled_reason STRING,
  cancelled_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- rfqs (10 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'rfqs_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'rfqs_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'rfqs_transport_request_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.rfqs` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  transport_request_id STRING NOT NULL,
  status STRING NOT NULL,
  due_at TIMESTAMP NOT NULL,
  awarded_quote_id STRING,
  cancelled_reason STRING,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- ap_invoice_lines (13 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'ap_invoice_lines_invoice_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.ap_invoice_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  ap_invoice_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  po_line_id STRING,
  sku STRING,
  description STRING NOT NULL,
  quantity NUMERIC,
  uom STRING,
  unit_price NUMERIC,
  amount NUMERIC NOT NULL,
  tax_code STRING,
  tax_amount NUMERIC NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- credit_notes (17 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'credit_notes_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'credit_notes_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'credit_notes_direction_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'credit_notes_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.credit_notes` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  direction STRING NOT NULL,
  party_id STRING NOT NULL,
  party_name STRING NOT NULL,
  ar_invoice_id STRING,
  ap_invoice_id STRING,
  amount NUMERIC NOT NULL,
  currency STRING NOT NULL,
  period STRING NOT NULL,
  reason STRING NOT NULL,
  approved_by STRING,
  approved_at TIMESTAMP,
  status STRING NOT NULL,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- inventory_items (35 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'inventory_items_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'inventory_items_kind_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'inventory_items_bucket_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'inventory_items_tenant_inventory_id_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'inventory_items_tenant_rejected_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_tenant_status_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_tenant_run_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_transfer_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_grn_line_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_bucket_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_tenant_written_off_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_grn_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_tenant_accepted_idx' - BigQuery has no indexes
-- dropped Index 'inventory_items_fifo_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.inventory_items` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  inventory_id STRING NOT NULL,
  grn_id STRING NOT NULL,
  grn_line_id STRING NOT NULL,
  po_id STRING,
  po_number STRING,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  status STRING NOT NULL,
  kind STRING NOT NULL,
  quantity NUMERIC NOT NULL,
  uom STRING,
  received_date DATE,
  accepted_qty NUMERIC NOT NULL,
  rejected_qty NUMERIC NOT NULL,
  consumed_qty NUMERIC NOT NULL,
  consumed_run_id STRING,
  consumed_run_number STRING,
  batch_no STRING,
  qc_by STRING,
  qc_at TIMESTAMP,
  rejection_code STRING,
  rejection_note STRING,
  location_id STRING,
  location_code STRING,
  transfer_id STRING,
  bucket STRING NOT NULL,
  written_off_qty NUMERIC NOT NULL,
  vendor_qr_enabled BOOL NOT NULL,
  vendor_inventory_id STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  deleted_at TIMESTAMP
)
CLUSTER BY tenant_id, id;

-- ---- invoice_lines (15 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'invoice_lines_invoice_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.invoice_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  invoice_id STRING NOT NULL,
  order_line_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  sku STRING NOT NULL,
  description STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  unit_price NUMERIC NOT NULL,
  tax_code STRING NOT NULL,
  tax_rate NUMERIC NOT NULL,
  net_amount NUMERIC NOT NULL,
  tax_amount NUMERIC NOT NULL,
  gross_amount NUMERIC NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- payment_allocations (7 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'payment_allocations_exactly_one_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'payment_allocations_ar_invoice_idx' - BigQuery has no indexes
-- dropped Index 'payment_allocations_payment_idx' - BigQuery has no indexes
-- dropped Index 'payment_allocations_ap_invoice_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.payment_allocations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  payment_id STRING NOT NULL,
  ap_invoice_id STRING,
  ar_invoice_id STRING,
  amount NUMERIC NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- production_consumption (10 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'production_consumption_run_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.production_consumption` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  production_run_id STRING NOT NULL,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  batch_no STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  unit_cost NUMERIC,
  is_additional BOOL NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- production_run_stages (8 columns) ----
-- dropped CheckConstraint 'production_run_stages_stage_key_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'production_run_stages_run_stage_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'production_run_stages_run_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.production_run_stages` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  production_run_id STRING NOT NULL,
  stage_key STRING NOT NULL,
  sequence INT64 NOT NULL,
  associate_name STRING,
  completed_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- purchase_quotations (15 columns) ----
-- dropped CheckConstraint 'purchase_quotations_charges_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_quotations_rfq_vendor_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_quotations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  rfq_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  vendor_name STRING NOT NULL,
  quote_ref STRING,
  quote_date DATE,
  valid_until DATE,
  payment_terms STRING,
  delivery_days INT64,
  charges NUMERIC NOT NULL,
  notes STRING,
  recorded_by_name STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- purchase_rfq_lines (15 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_rfq_lines_quantity_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_rfq_lines_line_no_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'purchase_rfq_lines_rfq_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_rfq_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  rfq_id STRING NOT NULL,
  line_no INT64 NOT NULL,
  requisition_line_id STRING,
  product_id STRING,
  sku STRING,
  item_name STRING NOT NULL,
  notes STRING,
  quantity NUMERIC NOT NULL,
  uom STRING NOT NULL,
  awarded_vendor_id STRING,
  award_reason STRING,
  purchase_order_id STRING,
  purchase_order_number STRING
)
CLUSTER BY tenant_id, id;

-- ---- purchase_rfq_vendors (10 columns) ----
-- dropped CheckConstraint 'purchase_rfq_vendors_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'purchase_rfq_vendors_email_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_rfq_vendors_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_rfq_vendors` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  rfq_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  vendor_name STRING NOT NULL,
  vendor_email STRING,
  status STRING NOT NULL,
  email_state STRING NOT NULL,
  email_error STRING,
  invited_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- quotations (17 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'quotations_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'quotations_rfq_carrier_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'quotations_amount_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'quotations_rfq_amount_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.quotations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  rfq_id STRING NOT NULL,
  carrier_id STRING NOT NULL,
  carrier_name STRING NOT NULL,
  amount NUMERIC NOT NULL,
  currency STRING NOT NULL,
  transit_days INT64,
  valid_until DATE,
  service_level STRING,
  inclusions STRING,
  status STRING NOT NULL,
  approved_by STRING,
  approved_at TIMESTAMP,
  rejected_reason STRING,
  recorded_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- rfq_invitations (9 columns) ----
-- dropped UniqueConstraint 'rfq_invitations_rfq_carrier_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'rfq_invitations_email_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.rfq_invitations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  rfq_id STRING NOT NULL,
  carrier_id STRING NOT NULL,
  carrier_name STRING NOT NULL,
  carrier_email STRING,
  email_state STRING NOT NULL,
  email_error STRING,
  invited_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- dispatches (23 columns) ----
-- dropped UniqueConstraint 'dispatches_tenant_number_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'dispatches_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'dispatches_warehouse_notify_state_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'dispatches_transport_request_idx' - BigQuery has no indexes
-- dropped Index 'dispatches_tenant_status_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.dispatches` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  number STRING NOT NULL,
  transport_request_id STRING NOT NULL,
  quotation_id STRING,
  carrier_id STRING NOT NULL,
  carrier_name STRING NOT NULL,
  awb_number STRING,
  vehicle_number STRING,
  driver_name STRING,
  driver_phone STRING,
  status STRING NOT NULL,
  dispatched_at TIMESTAMP NOT NULL,
  eta DATE,
  delivered_at TIMESTAMP,
  pod_document_id STRING,
  pod_url STRING,
  pod_received_by STRING,
  failure_reason STRING,
  warehouse_notified_at TIMESTAMP,
  warehouse_notify_state STRING NOT NULL,
  created_by STRING,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- finished_good_items (22 columns) ----
-- dropped UniqueConstraint 'finished_good_items_tenant_inventory_id_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'finished_good_items_status_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'finished_good_items_kind_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'finished_good_items_shipped_qty_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped CheckConstraint 'finished_good_items_origin_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'finished_good_items_source_item_idx' - BigQuery has no indexes
-- dropped Index 'finished_good_items_run_idx' - BigQuery has no indexes
-- dropped Index 'finished_good_items_tenant_status_idx' - BigQuery has no indexes
-- dropped Index 'finished_good_items_tenant_order_idx' - BigQuery has no indexes
-- dropped Index 'finished_good_items_fifo_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.finished_good_items` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  inventory_id STRING NOT NULL,
  production_run_id STRING,
  source_inventory_item_id STRING,
  product_id STRING NOT NULL,
  sku STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  status STRING NOT NULL,
  kind STRING NOT NULL,
  quantity NUMERIC NOT NULL,
  uom STRING,
  received_date DATE,
  batch_no STRING,
  allocated_qty NUMERIC NOT NULL,
  shipped_qty NUMERIC NOT NULL,
  allocated_order_id STRING,
  allocated_order_number STRING,
  location_id STRING,
  location_code STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- production_consumption_items (6 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'production_consumption_items_consumption_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.production_consumption_items` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  production_consumption_id STRING NOT NULL,
  inventory_item_id STRING,
  quantity NUMERIC NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;

-- ---- purchase_quotation_lines (8 columns) ----
-- dropped CheckConstraint 'purchase_quotation_lines_price_check' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped UniqueConstraint 'purchase_quotation_lines_uniq' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.purchase_quotation_lines` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  quotation_id STRING NOT NULL,
  rfq_line_id STRING NOT NULL,
  unit_price NUMERIC,
  tax_code STRING NOT NULL,
  lead_time_days INT64,
  notes STRING
)
CLUSTER BY tenant_id, id;

-- ---- finished_good_allocations (6 columns) ----
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped ForeignKeyConstraint 'ForeignKeyConstraint' - not enforced by BigQuery, needs app-level check if it was the only guard
-- dropped Index 'finished_good_allocations_reservation_idx' - BigQuery has no indexes
CREATE TABLE IF NOT EXISTS `REPLACE_WITH_GCP_PROJECT_ID.simple_erp_dev.finished_good_allocations` (
  id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  reservation_id STRING NOT NULL,
  finished_good_item_id STRING,
  quantity NUMERIC NOT NULL,
  created_at TIMESTAMP NOT NULL
)
CLUSTER BY tenant_id, id;
