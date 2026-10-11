"""End-to-end test suite for Phase 2 Supply Chain ERP Modules.
Tests:
1. Wave & Batch Picking Optimization Engine
2. Customer B2B Self-Service Portal
3. In-Process Quality Control (IPQC) & Certificate of Analysis (CoA)
4. Approved Vendor List (AVL) Governance & PO Eligibility Gate
"""
import sys
import uuid
from decimal import Decimal
from datetime import date, timedelta
from app.core.db import session
from app.models.tenant import Tenant
from app.models.user import User
from app.models.party import Party
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.production_run import ProductionRun
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.phase2_modules import (
    PickWave, PickWaveOrder, PickWaveLine,
    CustomerPortalUser, CustomerRmaTicket,
    IpqcInspection, CertificateOfAnalysis,
    ApprovedVendor, VendorComplianceCert
)
from app.domains.warehouse.wave_picking_router import (
    create_wave, list_waves, get_wave_detail, confirm_line_pick, complete_wave,
    CreateWaveRequest, ConfirmPickRequest
)
from app.domains.sales.customer_portal_router import (
    get_customer_orders, get_customer_invoices, get_customer_rmas, submit_rma_ticket,
    get_customer_summary, CreateRmaRequest
)
from app.domains.quality.ipqc_router import (
    list_ipqc_inspections, record_ipqc_inspection, list_certificates_of_analysis,
    generate_certificate_of_analysis, get_coa_print_slip,
    RecordIpqcRequest, ParameterCheck, GenerateCoaRequest, CoaParameterItem
)
from app.domains.procurement.avl_router import (
    list_approved_vendors, qualify_vendor, update_vendor_status,
    list_vendor_certs, register_vendor_cert, check_po_eligibility,
    QualifyVendorRequest, RegisterCertRequest
)

def run_phase2_verification():
    print("==================================================================")
    print("STARTING PHASE 2 E2E VERIFICATION TEST SUITE")
    print("==================================================================")

    # 1. Resolve tenant and admin actor
    tenant = session.query(Tenant).first()
    if not tenant:
        print("ERROR: No tenant found in DB.")
        sys.exit(1)
    admin_user = session.query(User).filter_by(tenant_id=tenant.id).first()
    if not admin_user:
        print("ERROR: No admin user found.")
        sys.exit(1)

    actor = {
        "tenant_id": tenant.id,
        "user_id": admin_user.id,
        "email": admin_user.email,
        "permissions": ["*"],
    }
    print(f"Testing with Tenant ID: {tenant.id}, User: {admin_user.email}")

    # Ensure test fixtures exist
    test_wh = session.query(Warehouse).filter_by(tenant_id=tenant.id).first()
    if not test_wh:
        test_wh = Warehouse(tenant_id=tenant.id, code="WH-E2E", name="E2E Central Warehouse", type="warehouse", status="active")
        session.add(test_wh)
        session.commit()

    test_product = session.query(Product).filter_by(tenant_id=tenant.id).first()
    if not test_product:
        test_product = Product(tenant_id=tenant.id, sku="E2E-PH2-SKU", name="E2E Phase 2 Product", uom="PCS", type="finished_good", status="active")
        session.add(test_product)
        session.commit()

    test_vendor = session.query(Party).filter_by(tenant_id=tenant.id, type="vendor").first()
    if not test_vendor:
        test_vendor = Party(tenant_id=tenant.id, code="V-E2E", name="E2E Precision Supplier", display_name="E2E Supplier Inc", type="vendor", status="active")
        session.add(test_vendor)
        session.commit()

    test_customer = session.query(Party).filter_by(tenant_id=tenant.id, type="customer").first()
    if not test_customer:
        test_customer = Party(tenant_id=tenant.id, code="C-E2E", name="E2E Global Client", display_name="E2E Client Corp", type="customer", status="active")
        session.add(test_customer)
        session.commit()

    print(f"Fixtures verified: WH={test_wh.code}, Prod={test_product.sku}, Vendor={test_vendor.code}, Customer={test_customer.code}")

    # ---------------------------------------------------------
    # TEST 1: Wave & Batch Picking Optimization Engine
    # ---------------------------------------------------------
    print("\n--- [1/4] Testing Wave & Batch Picking Engine ---")
    today = date.today()
    so = Order(
        tenant_id=tenant.id,
        number=f"SO-WAVE-{uuid.uuid4().hex[:6].upper()}",
        customer_id=test_customer.id,
        customer_name=test_customer.display_name or test_customer.name or "E2E Customer",
        status="confirmed",
        order_date=today,
        promised_date=today,
        currency="INR",
        exchange_rate=Decimal("1.0"),
        subtotal=Decimal("15000.00"),
        tax_total=Decimal("2700.00"),
        total=Decimal("17700.00")
    )
    session.add(so)
    session.flush()

    so_line = OrderLine(
        tenant_id=tenant.id,
        order_id=so.id,
        line_no=1,
        product_id=test_product.id,
        sku=test_product.sku,
        quantity=Decimal("50"),
        uom=test_product.uom or "PCS",
        unit_price=Decimal("300.00"),
        tax_code="GST18",
        tax_rate=Decimal("0.18"),
        tax_amount=Decimal("2700.00"),
        net_amount=Decimal("15000.00"),
        gross_amount=Decimal("17700.00")
    )
    session.add(so_line)
    session.commit()

    # Create Wave
    wave_req = CreateWaveRequest(
        warehouse_id=test_wh.id,
        wave_type="batch_order",
        carrier_cutoff="18:00 Standard Express",
        max_orders=10,
        order_ids=[so.id],
        notes="Automated E2E Wave Picking Run"
    )
    wave_resp = create_wave(wave_req, actor)
    wave_id = uuid.UUID(wave_resp["id"])
    print(f"Created Wave: {wave_resp['wave_number']} (ID: {wave_id}), Lines: {wave_resp['total_lines']}")
    assert wave_resp["total_lines"] >= 1, "Wave lines should be generated"

    # List Waves
    waves_list = list_waves(actor)
    assert len(waves_list["waves"]) > 0, "Wave list should contain newly created wave"
    print(f"Listed {len(waves_list['waves'])} waves in system.")

    # Get Wave Detail
    wave_detail = get_wave_detail(wave_id, actor)
    assert wave_detail["wave"]["id"] == str(wave_id), "Wave detail id must match"
    assert len(wave_detail["lines"]) >= 1, "Wave detail lines must not be empty"
    target_line_id = uuid.UUID(wave_detail["lines"][0]["id"])
    print(f"Inspected Wave: Serpentine Pick Path with {len(wave_detail['lines'])} lines.")

    # Pick Line
    pick_resp = confirm_line_pick(wave_id, ConfirmPickRequest(line_id=target_line_id, picked_qty=50.0), actor)
    print(f"Line Pick Result: picked_qty={pick_resp['picked_qty']}, wave_status={pick_resp['wave_status']}")
    assert pick_resp["picked_qty"] == 50.0, "Line should be picked"

    # Complete Wave
    comp_resp = complete_wave(wave_id, actor)
    print(f"Completed Wave Result: {comp_resp['message']}")
    print("✓ WAVE & BATCH PICKING ENGINE: ALL TESTS PASSED.")

    # ---------------------------------------------------------
    # TEST 2: Customer B2B Self-Service Portal
    # ---------------------------------------------------------
    print("\n--- [2/4] Testing Customer B2B Self-Service Portal ---")
    summary_resp = get_customer_summary(actor, customer_party_id=test_customer.id)
    print(f"Customer Summary: open_orders={summary_resp['open_orders_count']}, customer={summary_resp['customer_name']}")

    orders_resp = get_customer_orders(actor, customer_party_id=test_customer.id)
    print(f"Customer Orders retrieved: {len(orders_resp['orders'])}")
    assert len(orders_resp["orders"]) >= 1, "Should find at least 1 customer order"

    invoices_resp = get_customer_invoices(actor, customer_party_id=test_customer.id)
    print(f"Customer Invoices retrieved: {len(invoices_resp['invoices'])}")

    # Submit RMA Ticket
    ticket_req = CreateRmaRequest(
        customer_party_id=test_customer.id,
        order_id=so.id,
        order_number=so.number,
        product_id=test_product.id,
        sku=test_product.sku,
        return_qty=5.0,
        uom="PCS",
        reason_category="damaged_in_transit",
        customer_notes="Outer packaging damaged during transit. Requesting replacement authorization.",
        carrier_name="FedEx Ground"
    )
    ticket_resp = submit_rma_ticket(ticket_req, actor)
    print(f"Created Ticket: {ticket_resp['ticket_number']} (Status: {ticket_resp['status']})")
    assert ticket_resp["status"] == "submitted", "Ticket should default to submitted status"

    # List RMA Tickets
    rmas_list = get_customer_rmas(actor, customer_party_id=test_customer.id)
    assert any(r["ticket_number"] == ticket_resp["ticket_number"] for r in rmas_list["rmas"]), "Ticket must be in RMA list"
    print(f"Listed {len(rmas_list['rmas'])} customer tickets successfully.")
    print("✓ CUSTOMER B2B PORTAL: ALL TESTS PASSED.")

    # ---------------------------------------------------------
    # TEST 3: In-Process Quality Control (IPQC) & CoA
    # ---------------------------------------------------------
    print("\n--- [3/4] Testing Quality IPQC & Certificate of Analysis ---")
    pr = session.query(ProductionRun).filter_by(tenant_id=tenant.id).first()
    if not pr:
        pr = ProductionRun(
            tenant_id=tenant.id,
            number=f"PR-E2E-{uuid.uuid4().hex[:6].upper()}",
            product_id=test_product.id,
            sku=test_product.sku,
            quantity=Decimal("100"),
            uom=test_product.uom or "PCS",
            warehouse_id=test_wh.id,
            status="planned"
        )
        session.add(pr)
        session.commit()

    ipqc_req = RecordIpqcRequest(
        production_run_id=pr.id,
        stage_name="Stage-2 Soldering & Surface Mount",
        sample_size=10,
        inspected_qty=10.0,
        passed_qty=10.0,
        failed_qty=0.0,
        status="passed",
        parameters=[
            ParameterCheck(parameter="Solder Joint Fillet", specification="IPC-A-610 Class 3", measured_value="Passed 100% IPC X-Ray", decision="PASS"),
            ParameterCheck(parameter="Operating Voltage", specification="3.3V +/- 0.05V", measured_value="3.31V", decision="PASS"),
            ParameterCheck(parameter="Torque Fastener", specification="2.5 Nm +/- 0.2", measured_value="2.54 Nm", decision="PASS"),
        ],
        corrective_action_required=False
    )
    ipqc_resp = record_ipqc_inspection(ipqc_req, actor)
    print(f"Recorded IPQC: {ipqc_resp['inspection_number']} (Status: {ipqc_resp['status']})")
    assert ipqc_resp["status"] == "passed", "IPQC status should be passed"

    ipqc_list = list_ipqc_inspections(actor)
    assert len(ipqc_list["inspections"]) >= 1, "IPQC list must not be empty"

    coa_req = GenerateCoaRequest(
        product_id=test_product.id,
        production_run_id=pr.id,
        batch_no=f"BATCH-E2E-{uuid.uuid4().hex[:6].upper()}",
        mfg_date=today,
        expiry_date=today + timedelta(days=730),
        lot_size_qty=100.0,
        uom="PCS",
        test_standards="ISO 9001:2015, RoHS 3 (EU 2015/863), REACH",
        specifications=[
            CoaParameterItem(test_name="Dielectric Withstand", method="IEC 60601-1", specification="1500 VAC / 60s", result="Pass (No Breakdown)", decision="PASS"),
            CoaParameterItem(test_name="Heavy Metals Content (Pb, Cd, Hg)", method="EPA 3052", specification="< 100 ppm", result="< 5 ppm (RoHS Compliant)", decision="PASS")
        ]
    )
    coa_resp = generate_certificate_of_analysis(coa_req, actor)
    coa_id = uuid.UUID(coa_resp["id"])
    print(f"Created CoA: {coa_resp['coa_number']}")

    # List CoAs
    coa_list = list_certificates_of_analysis(actor)
    assert any(c["id"] == str(coa_id) for c in coa_list["coas"]), "CoA must appear in coas list"

    # Retrieve Printable CoA Slip
    slip_resp = get_coa_print_slip(coa_id, actor)
    assert slip_resp["coa_number"] == coa_resp["coa_number"], "CoA slip number match"
    assert len(slip_resp["specifications"]) == 2, "CoA slip should have 2 parametric tests"
    print(f"Generated Official CoA Document Slip for {slip_resp['product_name']}.")
    print("✓ QUALITY IPQC & CERTIFICATE OF ANALYSIS: ALL TESTS PASSED.")

    # ---------------------------------------------------------
    # TEST 4: Approved Vendor List (AVL) Governance
    # ---------------------------------------------------------
    print("\n--- [4/4] Testing Approved Vendor List (AVL) & PO Clearance Gate ---")
    qual_req = QualifyVendorRequest(
        vendor_party_id=test_vendor.id,
        product_id=test_product.id,
        category="Semiconductors & Sensors",
        status="approved",
        audit_score=94,
        max_po_limit=750000.0,
        notes="E2E Plant Audit Passed with distinction"
    )
    qual_resp = qualify_vendor(qual_req, actor)
    avl_id = uuid.UUID(qual_resp["id"])
    print(f"Vendor Qualified on AVL: ID={avl_id}, Status={qual_resp['status']}")

    avl_list = list_approved_vendors(actor)
    assert any(v["id"] == str(avl_id) for v in avl_list["vendors"]), "Vendor must appear in AVL list"
    print(f"Listed {len(avl_list['vendors'])} approved suppliers.")

    status_update_resp = update_vendor_status(avl_id, actor, status="conditional_trial")
    print(f"Status update result: {status_update_resp['message']}")
    assert status_update_resp["status"] == "conditional_trial", "Status should be conditional_trial"

    cert_req = RegisterCertRequest(
        vendor_party_id=test_vendor.id,
        cert_type="ISO_9001",
        certificate_number=f"ISO9001-E2E-{uuid.uuid4().hex[:6].upper()}",
        issuing_body="TÜV SÜD Asia Pacific",
        issue_date=date.today() - timedelta(days=60),
        expiry_date=date.today() + timedelta(days=305),
        document_url="https://acme-erp.internal/certs/iso9001.pdf"
    )
    cert_resp = register_vendor_cert(cert_req, actor)
    print(f"Registered Certificate: {cert_resp['message']}")

    certs_list = list_vendor_certs(actor, vendor_party_id=test_vendor.id)
    assert len(certs_list["certificates"]) >= 1, "Should list compliance cert"
    print(f"Compliance radar: {certs_list['certificates'][0]['cert_type']} expires in {certs_list['certificates'][0]['days_to_expiry']} days (Status: {certs_list['certificates'][0]['status']})")

    # PO clearance checks
    gate_ok = check_po_eligibility(vendor_party_id=test_vendor.id, actor=actor, product_id=test_product.id, order_amount=250000.0)
    print(f"Gate check (Order ₹2,50,000): Eligible={gate_ok['eligible']}, Reason={gate_ok['reason']}")
    assert gate_ok["eligible"] is True, "Should be eligible under PO ceiling"

    gate_blocked = check_po_eligibility(vendor_party_id=test_vendor.id, actor=actor, product_id=test_product.id, order_amount=1500000.0)
    print(f"Gate check (Order ₹15,00,000): Eligible={gate_blocked['eligible']}, Reason={gate_blocked['reason']}")
    assert gate_blocked["eligible"] is False, "Should be blocked exceeding ₹7,50,000 ceiling"
    assert gate_blocked["status"] == "limit_exceeded", "Status must be limit_exceeded"

    print("✓ APPROVED VENDOR LIST & PO CLEARANCE GATE: ALL TESTS PASSED.")

    print("\n==================================================================")
    print("ALL 4 PHASE 2 SUPPLY CHAIN ERP MODULES VERIFIED SUCCESSFULLY (100% PASS)")
    print("==================================================================")

if __name__ == "__main__":
    run_phase2_verification()
