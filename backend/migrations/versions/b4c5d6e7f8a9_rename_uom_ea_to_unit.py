"""data: rename the 'EA' unit-of-measure code to 'UNIT' everywhere it's stored

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-09 00:00:00.000000

app/services/uom.py's UOMS catalog no longer has an "EA" entry (renamed to
"UNIT" - see that file). Every table holding a uom/from_uom/to_uom value, plus
products.alternate_uoms (an array), needs its existing 'EA' rows updated so
they still pass UomCode validation (which checks membership against the
current catalog) and read consistently with newly-created rows.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None

# Every table with a plain `uom` column holding a UOM code.
_UOM_COLUMN_TABLES = [
    'production_consumption', 'reservations', 'bom_components', 'stock_ledger',
    'order_lines', 'invoice_lines', 'transfers', 'production_runs', 'po_lines',
    'products', 'inventory_items', 'ap_invoice_lines', 'grn_lines',
    'stock_balances', 'putaway_tasks',
]


def upgrade():
    for table in _UOM_COLUMN_TABLES:
        op.execute(f"UPDATE {table} SET uom = 'UNIT' WHERE uom = 'EA'")
    op.execute("UPDATE uom_conversions SET from_uom = 'UNIT' WHERE from_uom = 'EA'")
    op.execute("UPDATE uom_conversions SET to_uom = 'UNIT' WHERE to_uom = 'EA'")
    op.execute("UPDATE products SET alternate_uoms = array_replace(alternate_uoms, 'EA', 'UNIT') WHERE 'EA' = ANY(alternate_uoms)")


def downgrade():
    for table in _UOM_COLUMN_TABLES:
        op.execute(f"UPDATE {table} SET uom = 'EA' WHERE uom = 'UNIT'")
    op.execute("UPDATE uom_conversions SET from_uom = 'EA' WHERE from_uom = 'UNIT'")
    op.execute("UPDATE uom_conversions SET to_uom = 'EA' WHERE to_uom = 'UNIT'")
    op.execute("UPDATE products SET alternate_uoms = array_replace(alternate_uoms, 'UNIT', 'EA') WHERE 'UNIT' = ANY(alternate_uoms)")
