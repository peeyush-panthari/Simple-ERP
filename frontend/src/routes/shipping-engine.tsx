import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  Printer,
  RefreshCw,
  Sparkles,
  Truck,
  Zap,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  Field,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { date as formatDate, money } from "@/lib/format";

interface RateQuote {
  carrier_code: string;
  carrier_name: string;
  service_type: string;
  sla_days: number;
  estimated_delivery_date: string;
  base_freight: number;
  fuel_surcharge: number;
  gst_tax: number;
  total_freight: number;
  chargeable_weight_kg: number;
}

interface RateShopResult {
  chargeable_weight_kg: number;
  destination_pincode: string;
  quotes: RateQuote[];
  recommended_carrier: RateQuote | null;
}

interface ShipmentItem {
  id: string;
  shipment_number: string;
  order_id: string | null;
  order_number: string;
  carrier_code: string;
  service_type: string;
  awb_number: string;
  package_weight_kg: number;
  freight_charge: number;
  recipient_name: string;
  destination_city: string;
  destination_pincode: string;
  current_status: string;
  estimated_delivery_date: string | null;
  delivered_at: string | null;
  events_count: number;
  created_at: string;
}

interface RateCardItem {
  id: string;
  carrier_code: string;
  carrier_name: string;
  service_type: string;
  base_rate: number;
  per_kg_rate: number;
  cod_fee_pct: number;
  sla_days: number;
  is_active: boolean;
}

interface ThermalLabelData {
  shipment_number: string;
  awb_number: string;
  carrier_code: string;
  routing_barcode: string;
  service_type: string;
  consignor: {
    name: string;
    address: string;
    city: string;
    gstin: string;
  };
  consignee: {
    name: string;
    address: string;
    city: string;
    pincode: string;
  };
  package_details: {
    weight: string;
    dimensions: string;
    date: string;
    sort_code: string;
  };
}

export default function ShippingEnginePage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"rate_shop" | "shipments" | "rate_cards">("rate_shop");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Rate shop calculator inputs
  const [calcWeight, setCalcWeight] = useState<string>("2.5");
  const [calcLength, setCalcLength] = useState<string>("30");
  const [calcWidth, setCalcWidth] = useState<string>("20");
  const [calcHeight, setCalcHeight] = useState<string>("15");
  const [calcPincode, setCalcPincode] = useState<string>("560001");
  const [recipientName, setRecipientName] = useState<string>("Titan Energy Labs Ltd");
  const [destinationCity, setDestinationCity] = useState<string>("Bengaluru");
  const [rateResults, setRateResults] = useState<RateShopResult | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isBooking, setIsBooking] = useState(false);

  // Modals
  const [selectedLabelShipmentId, setSelectedLabelShipmentId] = useState<string | null>(null);
  const [updateStatusShipmentId, setUpdateStatusShipmentId] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState<string>("in_transit");
  const [milestoneLocation, setMilestoneLocation] = useState<string>("Bengaluru Hub Facility");
  const [milestoneRemarks, setMilestoneRemarks] = useState<string>("");
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // 1. Fetch Shipments
  const { data: shipmentsData, isLoading: shipmentsLoading, refetch: refetchShipments } = useQuery<{ shipments: ShipmentItem[] }>({
    queryKey: ["shipping-shipments", statusFilter],
    queryFn: async () => {
      const qs = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      return await api<{ shipments: ShipmentItem[] }>("GET", `/api/v1/shipping-engine/shipments${qs}`);
    },
  });

  // 2. Fetch Rate Cards
  const { data: cardsData, isLoading: cardsLoading, refetch: refetchCards } = useQuery<{ rate_cards: RateCardItem[] }>({
    queryKey: ["shipping-rate-cards"],
    queryFn: async () => {
      return await api<{ rate_cards: RateCardItem[] }>("GET", "/api/v1/shipping-engine/rate-cards");
    },
  });

  // 3. Fetch Thermal Label Detail when opened
  const { data: thermalLabel } = useQuery<ThermalLabelData>({
    queryKey: ["shipping-thermal-label", selectedLabelShipmentId],
    queryFn: async () => {
      if (!selectedLabelShipmentId) return null as unknown as ThermalLabelData;
      return await api<ThermalLabelData>("GET", `/api/v1/shipping-engine/shipments/${selectedLabelShipmentId}/thermal-label`);
    },
    enabled: !!selectedLabelShipmentId,
  });

  const shipments = shipmentsData?.shipments || [];
  const rateCards = cardsData?.rate_cards || [];

  // Metrics
  const bookedCount = shipments.filter((s) => s.current_status === "booked" || s.current_status === "pickup_scheduled").length;
  const inTransitCount = shipments.filter((s) => s.current_status === "in_transit" || s.current_status === "out_for_delivery").length;
  const deliveredCount = shipments.filter((s) => s.current_status === "delivered").length;
  const activeCarriersCount = new Set(rateCards.map((c) => c.carrier_code)).size;

  // Actions
  const handleCalculateRates = async () => {
    if (!calcWeight || !calcPincode || calcPincode.length !== 6) {
      alert("Please provide package weight and a valid 6-digit destination pincode.");
      return;
    }
    setIsCalculating(true);
    try {
      const res = await api<RateShopResult>("POST", "/api/v1/shipping-engine/rate-shop", {
        json: {
          weight_kg: parseFloat(calcWeight),
          length_cm: parseFloat(calcLength) || 30,
          width_cm: parseFloat(calcWidth) || 20,
          height_cm: parseFloat(calcHeight) || 15,
          destination_pincode: calcPincode,
        },
      });
      setRateResults(res);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to calculate carrier rates.";
      alert(message);
    } finally {
      setIsCalculating(false);
    }
  };

  const handleBookShipment = async (quote: RateQuote) => {
    if (!recipientName.trim() || !destinationCity.trim()) {
      alert("Please enter recipient company name and destination city.");
      return;
    }
    setIsBooking(true);
    try {
      const res = await api<{ id: string; awb_number: string; message: string }>(
        "POST",
        "/api/v1/shipping-engine/shipments/generate-awb",
        {
          json: {
            carrier_code: quote.carrier_code,
            service_type: quote.service_type,
            package_weight_kg: quote.chargeable_weight_kg,
            length_cm: parseFloat(calcLength) || 30,
            width_cm: parseFloat(calcWidth) || 20,
            height_cm: parseFloat(calcHeight) || 15,
            freight_charge: quote.total_freight,
            recipient_name: recipientName,
            destination_city: destinationCity,
            destination_pincode: calcPincode,
          },
        }
      );
      alert(res.message);
      qc.invalidateQueries({ queryKey: ["shipping-shipments"] });
      setActiveTab("shipments");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to generate AWB.";
      alert(message);
    } finally {
      setIsBooking(false);
    }
  };

  const handleUpdateMilestone = async () => {
    if (!updateStatusShipmentId) return;
    setIsUpdatingStatus(true);
    try {
      await api("POST", `/api/v1/shipping-engine/shipments/${updateStatusShipmentId}/update-status`, {
        json: {
          status: newStatus,
          location: milestoneLocation || "Hub Sorting Center",
          remarks: milestoneRemarks || null,
        },
      });
      setUpdateStatusShipmentId(null);
      qc.invalidateQueries({ queryKey: ["shipping-shipments"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to update shipment status.";
      alert(message);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  return (
    <Shell>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Multi-Carrier Shipping Engine & Live AWB Radar"
          description="Algorithmic freight rate shopping across national carriers (Delhivery, Blue Dart, FedEx, Shiprocket), 1-click AWB assignment, and 4x6 thermal label printing"
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                onClick={() => {
                  refetchShipments();
                  refetchCards();
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </ActionButton>
              {activeTab !== "rate_shop" && (
                <ActionButton tone="primary" onClick={() => setActiveTab("rate_shop")}>
                  <Zap className="mr-1 h-4 w-4" /> Rate Shop & Book
                </ActionButton>
              )}
            </div>
          }
        />

        {/* Top KPIs */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Active Carrier Partners"
            value={activeCarriersCount.toString()}
            hint="Integrated courier networks & express 3PLs"
          />
          <StatCard
            label="Booked & Ready for Pickup"
            value={bookedCount.toString()}
            hint="AWB generated, pending dock dispatch"
          />
          <StatCard
            label="Parcels In Transit"
            value={inTransitCount.toString()}
            hint="En route to regional customer destinations"
          />
          <StatCard
            label="Delivered Shipments"
            value={deliveredCount.toString()}
            hint="Successfully received with digital POD"
          />
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)]">
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "rate_shop"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("rate_shop")}
          >
            Algorithmic Rate Shopping & Booking
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "shipments"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("shipments")}
          >
            Parcel Shipments Registry & Live Tracking
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "rate_cards"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("rate_cards")}
          >
            Carrier Rate Cards & SLAs
          </button>
        </div>

        {/* TAB 1: Rate Shopping & Booking */}
        {activeTab === "rate_shop" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left: Dimension & Destination Calculator */}
            <div className="lg:col-span-1">
              <Panel title="Package Parameters & Destination">
                <div className="flex flex-col gap-4">
                  <Field label="Actual Dead Weight (KG) *">
                    <TextInput
                      type="number"
                      step="0.1"
                      value={calcWeight}
                      onChange={(e) => setCalcWeight(e.target.value)}
                    />
                  </Field>

                  <div className="grid grid-cols-3 gap-2">
                    <Field label="L (cm)">
                      <TextInput
                        type="number"
                        value={calcLength}
                        onChange={(e) => setCalcLength(e.target.value)}
                      />
                    </Field>
                    <Field label="W (cm)">
                      <TextInput
                        type="number"
                        value={calcWidth}
                        onChange={(e) => setCalcWidth(e.target.value)}
                      />
                    </Field>
                    <Field label="H (cm)">
                      <TextInput
                        type="number"
                        value={calcHeight}
                        onChange={(e) => setCalcHeight(e.target.value)}
                      />
                    </Field>
                  </div>

                  <Field label="Destination PIN Code (6-Digits) *">
                    <TextInput
                      value={calcPincode}
                      onChange={(e) => setCalcPincode(e.target.value)}
                      placeholder="e.g. 560001"
                    />
                  </Field>

                  <Field label="Recipient / Client Company *">
                    <TextInput
                      value={recipientName}
                      onChange={(e) => setRecipientName(e.target.value)}
                      placeholder="e.g. Titan Energy Systems"
                    />
                  </Field>

                  <Field label="Destination City *">
                    <TextInput
                      value={destinationCity}
                      onChange={(e) => setDestinationCity(e.target.value)}
                      placeholder="e.g. Bengaluru"
                    />
                  </Field>

                  <div className="mt-2">
                    <ActionButton tone="primary" onClick={handleCalculateRates} disabled={isCalculating} className="w-full">
                      <Zap className="mr-1.5 h-4 w-4" />
                      {isCalculating ? "Calculating Optimal Carriers..." : "Compare Carrier Rates"}
                    </ActionButton>
                  </div>
                </div>
              </Panel>
            </div>

            {/* Right: Rate Shopping Results */}
            <div className="lg:col-span-2">
              <Panel
                title="Live Carrier Quotes & Transit SLAs"
                aside={
                  rateResults && (
                    <span className="text-xs text-[var(--muted-foreground)]">
                      Chargeable: <strong>{rateResults.chargeable_weight_kg} kg</strong>
                    </span>
                  )
                }
              >
                {!rateResults ? (
                  <div className="flex flex-col items-center justify-center p-12 text-center text-[var(--muted-foreground)]">
                    <Truck className="h-12 w-12 stroke-[1.2] text-blue-500 mb-3 opacity-60" />
                    <h3 className="font-semibold text-base text-[var(--foreground)]">Run Carrier Rate Shopping</h3>
                    <p className="mt-1 max-w-sm text-sm">
                      Enter package weight, box dimensions, and destination pincode to compare live quotes across Delhivery,
                      Blue Dart, FedEx, Shiprocket, and DTDC.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {/* Recommended Best Value Card */}
                    {rateResults.recommended_carrier && (
                      <div className="rounded-lg border border-green-200 bg-green-50/70 p-4 dark:border-green-900/60 dark:bg-green-950/20">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Sparkles className="h-5 w-5 text-green-600 dark:text-green-400" />
                            <span className="font-bold text-sm text-green-900 dark:text-green-300">
                              RECOMMENDED BEST VALUE CARRIER
                            </span>
                          </div>
                          <Pill tone="success">Lowest Cost Option</Pill>
                        </div>
                        <div className="mt-2 flex items-center justify-between">
                          <div>
                            <div className="font-bold text-base">{rateResults.recommended_carrier.carrier_name}</div>
                            <div className="text-xs text-[var(--muted-foreground)]">
                              Transit SLA: {rateResults.recommended_carrier.sla_days} Days (Estimated Delivery: {rateResults.recommended_carrier.estimated_delivery_date})
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-xl text-green-700 dark:text-green-400">
                              {money(rateResults.recommended_carrier.total_freight)}
                            </div>
                            <div className="text-[11px] text-[var(--muted-foreground)]">All-inclusive incl. GST & Fuel</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* All Carrier Comparison Table */}
                    <DataTable
                      columns={[
                        "Carrier & Service",
                        "Transit SLA",
                        "Base Freight",
                        "Fuel + GST",
                        "Total Freight",
                        "Action",
                      ]}
                    >
                      {rateResults.quotes.map((q) => (
                        <TableRow
                          key={q.carrier_code}
                          cells={[
                            <div>
                              <div className="font-bold text-sm">{q.carrier_name}</div>
                              <div className="text-xs text-[var(--muted-foreground)] capitalize">
                                {q.service_type.replace(/_/g, " ")}
                              </div>
                            </div>,
                            <div className="flex items-center gap-1.5 font-medium">
                              <Clock className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                              <span>{q.sla_days} Days</span>
                            </div>,
                            <div>{money(q.base_freight)}</div>,
                            <div className="text-xs text-[var(--muted-foreground)]">
                              +{money(q.fuel_surcharge + q.gst_tax)}
                            </div>,
                            <div className="font-bold text-sm text-blue-600 dark:text-blue-400">
                              {money(q.total_freight)}
                            </div>,
                            <div>
                              <ActionButton
                                size="sm"
                                tone="primary"
                                onClick={() => handleBookShipment(q)}
                                disabled={isBooking}
                              >
                                Book & Generate AWB
                              </ActionButton>
                            </div>,
                          ]}
                        />
                      ))}
                    </DataTable>
                  </div>
                )}
              </Panel>
            </div>
          </div>
        )}

        {/* TAB 2: Parcel Shipments Registry */}
        {activeTab === "shipments" && (
          <Panel
            title="Generated Parcel Consignments & Tracking Registry"
            aside={
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm"
              >
                <option value="all">All Delivery Statuses</option>
                <option value="booked">Booked</option>
                <option value="in_transit">In Transit</option>
                <option value="out_for_delivery">Out for Delivery</option>
                <option value="delivered">Delivered</option>
                <option value="rto">RTO (Returned)</option>
              </select>
            }
          >
            {shipmentsLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading parcel shipments...</div>
            ) : shipments.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">
                No shipments logged yet. Use the Rate Shopping tab to book a parcel consignment.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Shipment & AWB #",
                  "Carrier",
                  "Consignee & Destination",
                  "Weight & Freight",
                  "Estimated Delivery",
                  "Status",
                  "Actions",
                ]}
              >
                {shipments.map((s) => (
                  <TableRow
                    key={s.id}
                    cells={[
                      <div>
                        <div className="font-mono font-bold text-sm text-blue-600 dark:text-blue-400">{s.awb_number}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{s.shipment_number}</div>
                      </div>,
                      <div>
                        <div className="font-semibold text-sm">{s.carrier_code}</div>
                        <div className="text-xs text-[var(--muted-foreground)] capitalize">
                          {s.service_type.replace(/_/g, " ")}
                        </div>
                      </div>,
                      <div>
                        <div className="font-medium text-sm">{s.recipient_name}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">
                          {s.destination_city} ({s.destination_pincode})
                        </div>
                      </div>,
                      <div>
                        <div className="text-sm">{s.package_weight_kg} kg</div>
                        <div className="font-semibold text-xs text-[var(--muted-foreground)]">
                          {money(s.freight_charge)}
                        </div>
                      </div>,
                      <div>
                        {s.delivered_at ? (
                          <div className="text-xs text-green-600 dark:text-green-400 font-medium">
                            Delivered {formatDate(s.delivered_at)}
                          </div>
                        ) : s.estimated_delivery_date ? (
                          <div>{formatDate(s.estimated_delivery_date)}</div>
                        ) : (
                          <span className="text-xs text-[var(--muted-foreground)]">TBD</span>
                        )}
                      </div>,
                      <Pill
                        tone={
                          s.current_status === "delivered"
                            ? "success"
                            : s.current_status === "in_transit" || s.current_status === "out_for_delivery"
                            ? "info"
                            : s.current_status === "rto"
                            ? "destructive"
                            : "warning"
                        }
                      >
                        {s.current_status.toUpperCase().replace(/_/g, " ")}
                      </Pill>,
                      <div className="flex items-center gap-1.5">
                        <ActionButton
                          size="sm"
                          tone="ghost"
                          onClick={() => setSelectedLabelShipmentId(s.id)}
                        >
                          <Printer className="mr-1 h-3.5 w-3.5" /> Thermal Label
                        </ActionButton>
                        <ActionButton
                          size="sm"
                          tone="ghost"
                          onClick={() => {
                            setUpdateStatusShipmentId(s.id);
                            setNewStatus(s.current_status === "booked" ? "in_transit" : "delivered");
                          }}
                        >
                          Update Milestone
                        </ActionButton>
                      </div>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 3: Carrier Rate Cards */}
        {activeTab === "rate_cards" && (
          <Panel title="Configured National Carrier Rate Cards & SLAs">
            {cardsLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading carrier rate cards...</div>
            ) : rateCards.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">No carrier rate cards active.</div>
            ) : (
              <DataTable
                columns={[
                  "Carrier Name",
                  "Carrier Code",
                  "Service Category",
                  "Base Rate (First 500g)",
                  "Additional / KG",
                  "COD Surcharge",
                  "Transit SLA",
                  "Status",
                ]}
              >
                {rateCards.map((c) => (
                  <TableRow
                    key={c.id}
                    cells={[
                      <span className="font-semibold text-sm">{c.carrier_name}</span>,
                      <span className="font-mono text-xs">{c.carrier_code}</span>,
                      <span className="capitalize">{c.service_type.replace(/_/g, " ")}</span>,
                      <div>{money(c.base_rate)}</div>,
                      <div>{money(c.per_kg_rate)} / kg</div>,
                      <div>{Math.round(c.cod_fee_pct * 100)}%</div>,
                      <div className="font-medium">{c.sla_days} Days</div>,
                      <Pill tone={c.is_active ? "success" : "muted"}>
                        {c.is_active ? "ACTIVE" : "DISABLED"}
                      </Pill>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* Modal: 4x6 Inch Thermal Label Print */}
        {selectedLabelShipmentId && (
          <Modal
            open={!!selectedLabelShipmentId}
            title="Official 4x6 Inch Thermal Shipping Label"
            onClose={() => setSelectedLabelShipmentId(null)}
          >
            {thermalLabel ? (
              <div className="flex flex-col gap-4">
                {/* 4x6 Thermal Label Container */}
                <div className="mx-auto w-[360px] rounded-lg border-2 border-black bg-white p-4 font-sans text-black shadow-md">
                  {/* Top Bar: Carrier & Service */}
                  <div className="flex items-center justify-between border-b-2 border-black pb-2">
                    <div className="font-black text-2xl tracking-wider">{thermalLabel.carrier_code}</div>
                    <div className="rounded bg-black px-2 py-0.5 font-bold text-xs text-white">
                      {thermalLabel.service_type}
                    </div>
                  </div>

                  {/* Routing Barcode & AWB */}
                  <div className="my-3 text-center">
                    <div className="font-mono tracking-widest text-3xl font-bold py-1">
                      ||||| | ||||| ||| |||| |
                    </div>
                    <div className="font-mono font-bold text-lg">{thermalLabel.awb_number}</div>
                    <div className="text-[10px] text-gray-500">Airway Bill Routing Identifier</div>
                  </div>

                  {/* Consignor (Shipper) */}
                  <div className="border-t border-dashed border-gray-400 py-2 text-xs">
                    <div className="font-bold text-[11px] text-gray-600">SHIP FROM:</div>
                    <div className="font-semibold">{thermalLabel.consignor.name}</div>
                    <div>{thermalLabel.consignor.address}</div>
                    <div>{thermalLabel.consignor.city}</div>
                    <div className="text-[10px]">GSTIN: {thermalLabel.consignor.gstin}</div>
                  </div>

                  {/* Consignee (Recipient) */}
                  <div className="border-t-2 border-black py-2.5">
                    <div className="font-bold text-xs text-gray-600">SHIP TO (DELIVER TO):</div>
                    <div className="font-bold text-sm">{thermalLabel.consignee.name}</div>
                    <div className="text-xs">{thermalLabel.consignee.address}</div>
                    <div className="font-bold text-sm mt-0.5">
                      {thermalLabel.consignee.city} - {thermalLabel.consignee.pincode}
                    </div>
                  </div>

                  {/* Bottom Strip: Sort Code & Package Meta */}
                  <div className="mt-2 flex items-center justify-between border-t-2 border-black pt-2 text-[11px]">
                    <div>
                      <div>Weight: <strong>{thermalLabel.package_details.weight}</strong></div>
                      <div>Dims: {thermalLabel.package_details.dimensions}</div>
                    </div>
                    <div className="text-right">
                      <div className="rounded border border-black px-2 py-0.5 font-mono font-black text-sm">
                        {thermalLabel.package_details.sort_code}
                      </div>
                      <div className="text-[10px]">{thermalLabel.package_details.date}</div>
                    </div>
                  </div>
                </div>

                <div className="mt-2 flex justify-end gap-2">
                  <ActionButton tone="ghost" onClick={() => setSelectedLabelShipmentId(null)}>
                    Close
                  </ActionButton>
                  <ActionButton
                    tone="primary"
                    onClick={() => {
                      window.print();
                    }}
                  >
                    <Printer className="mr-1 h-4 w-4" /> Print Label
                  </ActionButton>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center">Loading label data...</div>
            )}
          </Modal>
        )}

        {/* Modal: Update Delivery Milestone */}
        {updateStatusShipmentId && (
          <Modal
            open={!!updateStatusShipmentId}
            title="Advance Carrier Tracking Milestone"
            onClose={() => setUpdateStatusShipmentId(null)}
          >
            <div className="flex flex-col gap-4">
              <Field label="New Delivery Status *">
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="pickup_scheduled">Pickup Scheduled</option>
                  <option value="in_transit">In Transit (Hub Sorting)</option>
                  <option value="out_for_delivery">Out for Delivery</option>
                  <option value="delivered">Delivered (Digital POD)</option>
                  <option value="rto">RTO (Return to Origin)</option>
                </select>
              </Field>

              <Field label="Current Hub / Checkpoint Location">
                <TextInput
                  value={milestoneLocation}
                  onChange={(e) => setMilestoneLocation(e.target.value)}
                  placeholder="e.g. Hyderabad Transit Hub"
                />
              </Field>

              <Field label="Milestone Remarks">
                <TextInput
                  value={milestoneRemarks}
                  onChange={(e) => setMilestoneRemarks(e.target.value)}
                  placeholder="e.g. Arrived on feeder vehicle KA-01-EA-4921"
                />
              </Field>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setUpdateStatusShipmentId(null)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleUpdateMilestone} disabled={isUpdatingStatus}>
                  {isUpdatingStatus ? "Updating..." : "Update Milestone"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
