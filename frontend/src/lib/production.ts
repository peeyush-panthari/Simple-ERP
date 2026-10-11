/** Shared bits of the production forms - picker maths and the pack/team field lists. */

export interface Requirement {
  productId: string;
  sku: string;
  quantity: string;
  uom: string;
}
export interface Pick {
  itemId: string;
  inventoryId: string;
  quantity: string;
}
export interface AdditionalLine {
  productId: string;
  sku: string;
  skuName: string;
  uom: string;
  quantity: string;
  items: { itemId: string; inventoryId: string; quantity: string }[];
}

export const pickedQty = (picks: Pick[] | undefined) => (picks ?? []).reduce((s, p) => s + Number(p.quantity), 0);
export const isCovered = (requiredQty: string, picks: Pick[] | undefined) => pickedQty(picks) >= Number(requiredQty) - 1e-9;

/** Auto-pick: greedy fill in list order from what is available, never re-picking an already picked unit. */
export function autoPick(requiredQty: string, picks: Pick[], available: { id: string; inventoryId: string; availableQty: string }[]): Pick[] {
  let remaining = Number(requiredQty) - pickedQty(picks);
  if (remaining <= 0) return picks;
  const next = [...picks];
  const taken = new Set(picks.map((p) => p.itemId));
  for (const item of available) {
    if (remaining <= 0) break;
    if (taken.has(item.id)) continue;
    const take = Math.min(remaining, Number(item.availableQty));
    if (take <= 0) continue;
    next.push({ itemId: item.id, inventoryId: item.inventoryId, quantity: String(take) });
    remaining -= take;
  }
  return next;
}

/** Python's f"{x:g}" for the quantities the picker prefills ("5", "1.5") - trims trailing zeros. */
export const gFormat = (v: string | number) => String(Number(v));

export const PACK_FIELDS: [key: string, label: string][] = [
  ["bmsMakeModel", "BMS Make/Model"],
  ["screenType", "Screen type"],
  ["bmsId", "BMS ID"],
  ["bluetoothId", "Bluetooth ID"],
  ["iotId", "IoT ID"],
  ["cellsName", "Cells name"],
  ["cellsQuantity", "Cells quantity"],
  ["seriesCount", "No's of series"],
  ["parallelCount", "No's of parallel"],
  ["enclosureName", "Enclosure name"],
  ["chargeCapacity", "Charge capacity"],
  ["dischargeCapacity", "Discharge capacity"],
];
export const INT_FIELDS = ["cellsQuantity", "seriesCount", "parallelCount"];

export const TEAM_FIELDS: [key: string, label: string][] = [
  ["moduleAssemblyBy", "Module Assembly"],
  ["cellAssemblyBy", "Cell Assembly"],
  ["frpCuttingBy", "FRP Cutting"],
  ["bmsSensingCableAssemblyBy", "BMS & Sensing Cable Assembly"],
  ["enclosureAssemblyBy", "Enclosure Assembly"],
  ["qcPdiBy", "QC & PDI"],
];

/** A file read as base64 for the API (test report / QR photo). */
export function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
