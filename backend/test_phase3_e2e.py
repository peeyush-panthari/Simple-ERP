"""End-to-end test suite for Phase 3 Supply Chain Advanced Intelligence modules:
1. Work Center Finite Capacity Planning & RCCP
2. Multi-Carrier Shipping Engine & Live AWB Tracking
3. Supply Chain Control Tower Dashboard
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
from app.models.phase3_modules import (
    WorkCenter, WorkCenterSchedule, CarrierRateCard, CarrierShipment, ScKpiSnapshot
)
from app.domains.operations.capacity_planning_router import (
    list_work_centers, create_work_center, list_schedule, schedule_job, reassign_job,
    get_rccp_summary, CreateWorkCenterRequest, ScheduleJobRequest, ReassignJobRequest
)
from app.domains.logistics.shipping_engine_router import (
    list_rate_cards, rate_shop, generate_awb, list_shipments, get_thermal_label,
    update_shipment_status, RateShopRequest, GenerateAwbRequest, UpdateStatusRequest
)
from app.domains.planning.control_tower_router import (
    get_macro_kpis, get_stockout_radar, get_lead_time_volatility, get_geographic_velocity,
    record_daily_snapshot
)

def run_phase3_verification():
    print("==================================================================")
    print("STARTING PHASE 3 E2E VERIFICATION TEST SUITE")
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

    # ---------------------------------------------------------
    # TEST 1: Work Center Finite Capacity Planning & RCCP
    # ---------------------------------------------------------
    print("\n--- [1/3] Testing Work Center Finite Capacity Planning & RCCP ---")
    # Register Station 1 (Primary Welder)
    wc1_req = CreateWorkCenterRequest(
        code=f"WC-E2E-WELD-{uuid.uuid4().hex[:4].upper()}",
        name="Ultrasonic Wire Bonder Station 1",
        department="Battery Module Cell Assembly",
        daily_capacity_hours=16.0,
        efficiency_factor=0.85,
        hourly_machine_rate=800.0,
        hourly_labor_rate=400.0,
        status="active"
    )
    wc1_resp = create_work_center(wc1_req, actor)
    wc1_id = uuid.UUID(wc1_resp["id"])
    print(f"Created Work Center 1: {wc1_resp['code']} (ID: {wc1_id})")

    # Register Station 2 (Alternate Backup Welder)
    wc2_req = CreateWorkCenterRequest(
        code=f"WC-E2E-WELD2-{uuid.uuid4().hex[:4].upper()}",
        name="Backup Laser Cell Welder Station 2",
        department="Battery Module Cell Assembly",
        daily_capacity_hours=16.0,
        efficiency_factor=0.90,
        hourly_machine_rate=850.0,
        hourly_labor_rate=400.0,
        status="active"
    )
    wc2_resp = create_work_center(wc2_req, actor)
    wc2_id = uuid.UUID(wc2_resp["id"])
    print(f"Created Alternate Work Center 2: {wc2_resp['code']} (ID: {wc2_id})")

    # List Work Centers
    wc_list = list_work_centers(actor)
    assert any(w["id"] == str(wc1_id) for w in wc_list["work_centers"]), "Work center 1 must be listed"
    print(f"Listed {len(wc_list['work_centers'])} work centers in network.")

    # Schedule a heavy job on Station 1
    today = date.today()
    sched_req = ScheduleJobRequest(
        work_center_id=wc1_id,
        task_name="Continuous Pack Welding Run 101",
        schedule_date=today,
        shift="day",
        required_hours=18.0,  # Exceeds 16h * 0.85 = 13.6h effective capacity -> triggers overload!
        notes="High Priority OEM Battery Pack"
    )
    sched_resp = schedule_job(sched_req, actor)
    sched_id = uuid.UUID(sched_resp["id"])
    print(f"Scheduled Job: {sched_resp['task_name']} on {sched_resp['work_center_code']} (ID: {sched_id})")

    # Inspect schedule for bottleneck overload detection
    sched_list = list_schedule(actor, work_center_id=wc1_id)
    target_sched = next(s for s in sched_list["schedules"] if s["id"] == str(sched_id))
    print(f"Schedule Inspection: required={target_sched['required_hours']}h, daily_limit={target_sched['daily_capacity_hours']}h, status={target_sched['status']}, overloaded={target_sched['is_overloaded']}")
    assert target_sched["is_overloaded"] is True, "Heavy job must trigger overload condition"
    assert target_sched["status"] == "overloaded", "Status must be tagged overloaded"

    # Reassign job to alternate Station 2 to eliminate bottleneck
    reassign_req = ReassignJobRequest(
        target_work_center_id=wc2_id,
        target_date=today + timedelta(days=1),
        target_shift="evening"
    )
    reassign_resp = reassign_job(sched_id, reassign_req, actor)
    print(f"Reassign Result: {reassign_resp['message']}")

    # Verify RCCP Summary 4-Week Radar
    rccp_resp = get_rccp_summary(actor)
    assert len(rccp_resp["rccp_matrix"]) >= 2, "RCCP matrix must include both stations"
    print(f"Rough-Cut Capacity Planning Matrix evaluated for {len(rccp_resp['rccp_matrix'])} stations over 4 weeks.")
    print("✓ WORK CENTER FINITE CAPACITY & RCCP: ALL TESTS PASSED.")

    # ---------------------------------------------------------
    # TEST 2: Multi-Carrier Shipping Engine & Live AWB Tracking
    # ---------------------------------------------------------
    print("\n--- [2/3] Testing Multi-Carrier Shipping Engine & Live AWB Radar ---")
    # List rate cards
    cards_resp = list_rate_cards(actor)
    assert len(cards_resp["rate_cards"]) >= 5, "Must have rate cards for Delhivery, Blue Dart, FedEx, Shiprocket, DTDC"
    print(f"Active Carrier Rate Cards verified: {[c['carrier_code'] for c in cards_resp['rate_cards']]}")

    # Algorithmic Rate Shop
    shop_req = RateShopRequest(
        weight_kg=3.5,
        length_cm=35.0,
        width_cm=25.0,
        height_cm=18.0,
        destination_pincode="560001",
        declared_value=8500.0
    )
    shop_resp = rate_shop(shop_req, actor)
    assert len(shop_resp["quotes"]) >= 5, "Must return quotes from all active carriers"
    assert shop_resp["recommended_carrier"] is not None, "Must calculate recommended lowest-cost carrier"
    rec = shop_resp["recommended_carrier"]
    print(f"Rate Shop Results: Chargeable Weight={shop_resp['chargeable_weight_kg']} kg, Recommended={rec['carrier_name']} ({rec['service_type']}) at {rec['total_freight']} INR (SLA: {rec['sla_days']} days)")

    # Book Shipment & Generate Live AWB
    awb_req = GenerateAwbRequest(
        carrier_code=rec["carrier_code"],
        service_type=rec["service_type"],
        package_weight_kg=shop_resp["chargeable_weight_kg"],
        length_cm=35.0,
        width_cm=25.0,
        height_cm=18.0,
        freight_charge=rec["total_freight"],
        recipient_name="Tata Power Renewables Ltd",
        destination_city="Bengaluru",
        destination_pincode="560001"
    )
    awb_resp = generate_awb(awb_req, actor)
    shipment_id = uuid.UUID(awb_resp["id"])
    print(f"Generated Live AWB: {awb_resp['awb_number']} ({awb_resp['carrier_code']}), Shipment: {awb_resp['shipment_number']}")
    assert awb_resp["status"] == "booked", "Initial status should be booked"

    # List Shipments
    ship_list = list_shipments(actor)
    assert any(s["id"] == str(shipment_id) for s in ship_list["shipments"]), "Shipment must be in shipments list"

    # Thermal Label 4x6 Generation
    label_resp = get_thermal_label(shipment_id, actor)
    assert label_resp["awb_number"] == awb_resp["awb_number"], "Label AWB must match"
    assert "consignor" in label_resp and "consignee" in label_resp, "Label must have consignor and consignee details"
    print(f"Generated 4x6 Thermal Shipping Label: Barcode={label_resp['routing_barcode']}, Consignee={label_resp['consignee']['name']}")

    # Advance Delivery Milestones
    update_resp1 = update_shipment_status(
        shipment_id,
        UpdateStatusRequest(status="in_transit", location="Nelamangala Hub Sort Facility", remarks="Scanned onto feeder vehicle"),
        actor
    )
    print(f"Milestone 1: {update_resp1['message']}")
    assert update_resp1["status"] == "in_transit", "Status must advance to in_transit"

    update_resp2 = update_shipment_status(
        shipment_id,
        UpdateStatusRequest(status="delivered", location="Electronic City Client Facility", remarks="Received and signed by Security"),
        actor
    )
    print(f"Milestone 2: {update_resp2['message']}")
    assert update_resp2["status"] == "delivered", "Status must advance to delivered"
    print("✓ MULTI-CARRIER SHIPPING ENGINE & LIVE AWB RADAR: ALL TESTS PASSED.")

    # ---------------------------------------------------------
    # TEST 3: Supply Chain Control Tower Dashboard
    # ---------------------------------------------------------
    print("\n--- [3/3] Testing Supply Chain Control Tower Dashboard ---")
    # Live Macro KPIs
    macro_resp = get_macro_kpis(actor)
    print(f"Macro KPIs: OTIF={macro_resp['otif']['value']}% (Target {macro_resp['otif']['target']}%), DOH={macro_resp['doh']['value']} Days, Cash-to-Cash={macro_resp['cash_to_cash']['value']} Days, Valuation={macro_resp['inventory_valuation']['value']} INR")
    assert macro_resp["otif"]["value"] > 0, "OTIF must be a valid positive rate"
    assert macro_resp["doh"]["value"] > 0, "DOH must be a positive day count"
    assert isinstance(macro_resp["cash_to_cash"]["value"], (int, float)), "Cash-to-cash must be a valid number"

    # Predictive Stockout Risk Radar
    radar_resp = get_stockout_radar(actor)
    assert radar_resp["total_monitored"] > 0, "Must monitor active SKUs"
    print(f"Stockout Risk Radar: {radar_resp['total_monitored']} items monitored, {radar_resp['critical_count']} in critical runout window.")

    # Supplier Lead Time Volatility Heatmap
    vol_resp = get_lead_time_volatility(actor)
    assert len(vol_resp["supplier_lead_times"]) > 0, "Must calculate supplier lead times"
    print(f"Supplier Volatility: {len(vol_resp['supplier_lead_times'])} suppliers tracked against delivery targets.")

    # Geographical Order Velocity
    geo_resp = get_geographic_velocity(actor)
    assert len(geo_resp["geographic_velocity"]) >= 4, "Must cover main Indian regional zones"
    print(f"Geographic Velocity: Corridors={[z['zone'] for z in geo_resp['geographic_velocity']]}")

    # Capture Executive Snapshot
    snap_resp = record_daily_snapshot(actor)
    print(f"Snapshot Result: {snap_resp['message']} (Date: {snap_resp['snapshot_date']}, OTIF: {snap_resp['otif']}%)")
    print("✓ SUPPLY CHAIN CONTROL TOWER DASHBOARD: ALL TESTS PASSED.")

    print("\n==================================================================")
    print("ALL 3 PHASE 3 SUPPLY CHAIN ERP MODULES VERIFIED SUCCESSFULLY (100% PASS)")
    print("==================================================================")

if __name__ == "__main__":
    run_phase3_verification()
