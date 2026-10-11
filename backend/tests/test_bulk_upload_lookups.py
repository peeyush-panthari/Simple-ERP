"""Guards the batched lookups the bulk-upload routes rely on.

Each CSV route used to resolve its SKUs, warehouse/vendor/entity codes and
location codes one row at a time; they are now resolved for the whole file up
front. The batched resolvers have to match their single-row counterparts
exactly - including the parts that are easy to get wrong:

  * find_by_sku is case-insensitive AND falls back to product aliases, with a
    direct SKU match beating another product's alias for the same string;
  * warehouse, party and location codes compare case-insensitively;
  * business-entity and category codes compare EXACTLY, so a case variant
    must still miss;
  * a location code is only unique within its warehouse.
"""

import uuid

import pytest

from tests.flaskcompat import db
from app.models.business_entity import BusinessEntity
from app.models.location import Location
from app.models.party import Party
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.warehouse import Warehouse
from app.services import org_repo, party_repo, product_repo, warehouse_repo


@pytest.fixture
def sample_products(app, default_tenant_id):
    with app.app_context():
        return [
            {"id": p.id, "sku": p.sku}
            for p in Product.query.filter_by(tenant_id=default_tenant_id).limit(5).all()
        ]


def test_find_by_skus_matches_find_by_sku(app, default_tenant_id, sample_products):
    """Same answers as the single-row lookup for hits, case variants and misses."""
    if not sample_products:
        pytest.skip("no products in this tenant")
    skus = [p["sku"] for p in sample_products]
    probes = skus + [s.lower() for s in skus] + [s.upper() for s in skus] + ["NO-SUCH-SKU-XYZ"]

    with app.app_context():
        batched = product_repo.find_by_skus(default_tenant_id, probes)
        for sku in probes:
            one = product_repo.find_by_sku(default_tenant_id, sku)
            many = batched.get(sku.upper())
            assert (one.id if one else None) == (many.id if many else None), sku


def test_find_by_skus_resolves_aliases_and_prefers_a_direct_match(app, default_tenant_id, sample_products):
    """An alias resolves to its product, but a string that is some other
    product's live SKU resolves to that product, not to the aliasing one."""
    if len(sample_products) < 3:
        pytest.skip("need three products")
    a, b, c = sample_products[0], sample_products[1], sample_products[2]
    retired = f"OLD-{uuid.uuid4().hex[:8].upper()}"
    created = []

    with app.app_context():
        try:
            for product_id, alias_sku in ((a["id"], retired), (b["id"], c["sku"])):
                row = ProductAlias(tenant_id=default_tenant_id, product_id=product_id, alias_sku=alias_sku, reason="test")
                db.session.add(row)
                db.session.flush()
                created.append(row.id)
            db.session.commit()

            batched = product_repo.find_by_skus(default_tenant_id, [retired, retired.lower(), c["sku"]])
            assert batched[retired].id == a["id"]
            assert batched[retired.lower().upper()].id == a["id"]
            # c's own SKU wins over b's alias of it, exactly as find_by_sku does
            assert batched[c["sku"].upper()].id == c["id"]
            assert product_repo.find_by_sku(default_tenant_id, c["sku"]).id == c["id"]
        finally:
            if created:
                ProductAlias.query.filter(ProductAlias.id.in_(created)).delete(synchronize_session=False)
                db.session.commit()


def test_find_warehouses_by_codes_is_case_insensitive(app, default_tenant_id):
    with app.app_context():
        codes = [w.code for w in Warehouse.query.filter_by(tenant_id=default_tenant_id).limit(5).all()]
        if not codes:
            pytest.skip("no warehouses in this tenant")
        probes = codes + [c.lower() for c in codes] + ["NO-SUCH-WH-XYZ"]
        batched = warehouse_repo.find_warehouses_by_codes(default_tenant_id, probes)
        for code in probes:
            one = warehouse_repo.find_warehouse_by_code(default_tenant_id, code)
            many = batched.get(code.upper())
            assert (one.id if one else None) == (many.id if many else None), code


def test_find_entities_by_codes_stays_case_sensitive(app, default_tenant_id):
    """find_entity_by_code compares exactly; the batched form must not quietly
    widen that to a case-insensitive match."""
    with app.app_context():
        entities = BusinessEntity.query.filter_by(tenant_id=default_tenant_id).limit(3).all()
        codes = [e.code for e in entities]
        if not codes:
            pytest.skip("no business entities in this tenant")
        probes = codes + [c.swapcase() for c in codes]
        batched = org_repo.find_entities_by_codes(default_tenant_id, probes)
        for code in probes:
            one = org_repo.find_entity_by_code(default_tenant_id, code)
            assert (one.id if one else None) == (batched[code].id if code in batched else None), code


def test_find_locations_by_codes_is_scoped_to_its_warehouse(app, default_tenant_id):
    """A location code is unique only within a warehouse, so the same code
    against a different warehouse must not resolve."""
    with app.app_context():
        rows = (
            Location.query.join(Warehouse, Warehouse.id == Location.warehouse_id)
            .filter(Warehouse.tenant_id == default_tenant_id)
            .limit(10)
            .all()
        )
        if len(rows) < 2:
            pytest.skip("need two locations")
        first, last = rows[0], rows[-1]
        pairs = [(l.warehouse_id, l.code) for l in rows] + [(l.warehouse_id, l.code.lower()) for l in rows]
        if first.warehouse_id != last.warehouse_id:
            pairs += [(first.warehouse_id, last.code), (last.warehouse_id, first.code)]

        batched = warehouse_repo.find_locations_by_codes(pairs)
        for warehouse_id, code in pairs:
            one = Location.query.filter(
                Location.warehouse_id == warehouse_id,
                db.func.upper(Location.code) == code.upper(),
            ).first()
            many = batched.get((warehouse_id, code.upper()))
            assert (one.id if one else None) == (many.id if many else None), (warehouse_id, code)


def test_find_parties_by_codes_is_case_insensitive(app, default_tenant_id):
    with app.app_context():
        codes = [p.code for p in Party.query.filter_by(tenant_id=default_tenant_id).limit(5).all()]
        if not codes:
            pytest.skip("no parties in this tenant")
        probes = codes + [c.lower() for c in codes] + ["NO-SUCH-PARTY-XYZ"]
        batched = party_repo.find_parties_by_codes(default_tenant_id, probes)
        for code in probes:
            one = party_repo.find_party_by_code(default_tenant_id, code)
            many = batched.get(code.upper())
            assert (one.id if one else None) == (many.id if many else None), code
