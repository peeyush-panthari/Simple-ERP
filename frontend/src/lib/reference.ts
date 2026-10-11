/** Static reference lists shared across pages - country/state pickers, not fetched from the backend since these never change per tenant. Port of reference_data.py. */

import type { Option } from "@/components/erp/ui";

/** Matches the backend's tax_codes GST codes exactly (minus EXEMPT, which isn't a rate) - keep both in sync. */
export const GST_RATE_OPTIONS: Option[] = [
  { value: "GST0", label: "0%" },
  { value: "GST5", label: "5%" },
  { value: "GST12", label: "12%" },
  { value: "GST18", label: "18%" },
  { value: "GST28", label: "28%" },
];

export const COUNTRY_OPTIONS: Option[] = [
  { value: "IN", label: "India" },
  { value: "US", label: "United States" },
  { value: "GB", label: "United Kingdom" },
  { value: "AE", label: "United Arab Emirates" },
  { value: "SG", label: "Singapore" },
];

/** GST state/UT codes (matches the backend's party_tax_id GST_STATE_CODES). */
export const INDIAN_STATE_OPTIONS: Option[] = [
  { value: "01", label: "Jammu and Kashmir" },
  { value: "02", label: "Himachal Pradesh" },
  { value: "03", label: "Punjab" },
  { value: "04", label: "Chandigarh" },
  { value: "05", label: "Uttarakhand" },
  { value: "06", label: "Haryana" },
  { value: "07", label: "Delhi" },
  { value: "08", label: "Rajasthan" },
  { value: "09", label: "Uttar Pradesh" },
  { value: "10", label: "Bihar" },
  { value: "11", label: "Sikkim" },
  { value: "12", label: "Arunachal Pradesh" },
  { value: "13", label: "Nagaland" },
  { value: "14", label: "Manipur" },
  { value: "15", label: "Mizoram" },
  { value: "16", label: "Tripura" },
  { value: "17", label: "Meghalaya" },
  { value: "18", label: "Assam" },
  { value: "19", label: "West Bengal" },
  { value: "20", label: "Jharkhand" },
  { value: "21", label: "Odisha" },
  { value: "22", label: "Chhattisgarh" },
  { value: "23", label: "Madhya Pradesh" },
  { value: "24", label: "Gujarat" },
  { value: "25", label: "Daman and Diu" },
  { value: "26", label: "Dadra and Nagar Haveli" },
  { value: "27", label: "Maharashtra" },
  { value: "28", label: "Andhra Pradesh (Old)" },
  { value: "29", label: "Karnataka" },
  { value: "30", label: "Goa" },
  { value: "31", label: "Lakshadweep" },
  { value: "32", label: "Kerala" },
  { value: "33", label: "Tamil Nadu" },
  { value: "34", label: "Puducherry" },
  { value: "35", label: "Andaman and Nicobar Islands" },
  { value: "36", label: "Telangana" },
  { value: "37", label: "Andhra Pradesh" },
  { value: "38", label: "Ladakh" },
  { value: "97", label: "Other Territory" },
  { value: "99", label: "Centre Jurisdiction" },
];

export const INDIAN_STATE_NAMES: Record<string, string> = Object.fromEntries(INDIAN_STATE_OPTIONS.map((o) => [o.value, o.label]));

/** Units of measure a product can be created with; the stored code stays raw ("UNIT"), only the label differs. */
export const UOMS = ["KG", "G", "UNIT", "M", "MM", "L", "BOX"];
const UOM_LABELS: Record<string, string> = { UNIT: "Unit" };
export const uomLabel = (code: string | null | undefined): string => (code ? (UOM_LABELS[code] ?? code) : "");
export const UOM_OPTIONS: Option[] = UOMS.map((u) => ({ value: u, label: uomLabel(u) }));

export const PRODUCT_TYPES = ["raw_material", "finished_good", "consumable", "service"];
