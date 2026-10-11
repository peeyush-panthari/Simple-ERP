/** Status vocabulary - port of ui_kit.py's tone_for / humanise / bucket_label / raw_item_status_label. */

export type Tone = "success" | "warning" | "info" | "destructive" | "muted";

const TONE_WORDS: [Tone, string[]][] = [
  ["success", ["approved", "accept", "active", "posted", "settled", "fulfilled", "healthy", "on track", "resolved", "dispatched", "delivered", "sent", "auto-raised", "issued", "closed", "met", "low", "passed", "full", "shipped", "available", "packed"]],
  ["warning", ["pending", "under_qc", "at risk", "draft", "under production", "partial", "rfq sent", "0-30", "not sent", "medium", "constrained", "degraded", "queued", "reopened", "quotation", "planned"]],
  ["destructive", ["breach", "blocked", "on hold", "suspended", "high", "urgent", "reject", "cancel", "31-60", "60+", "90+", "down", "failed", "infected", "variance", "overdue", "damaged", "expired"]],
  ["info", ["received", "ready", "current", "new", "in transit", "in_transit", "allocated", "confirmed", "picked", "open", "reserved", "consumed"]],
];

/** Acronyms humanise() keeps upper-cased ("under_qc" -> "Under QC", not "Under Qc"). */
const ACRONYMS = new Set(["qc", "grn", "po", "sku", "fg", "rm", "bom", "id"]);

export function toneFor(value: string | null | undefined): Tone {
  const v = (value ?? "").toLowerCase().replaceAll("_", " ");
  // "inactive" contains "active": decide it first, or an inactive record would read green.
  if (/\b(inactive|deactivated|disabled)\b/.test(v)) return "destructive";
  for (const [tone, words] of TONE_WORDS) {
    if (words.some((w) => v.includes(w.replaceAll("_", " ")))) return tone;
  }
  return "muted";
}

export function humanise(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .split(" ")
    .map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

/** The one allowed set of user-pickable stock buckets - "quarantine" reads "Rejected in QC" everywhere. */
export const BUCKET_OPTIONS: { value: string; label: string }[] = [
  { value: "available", label: "Available" },
  { value: "quarantine", label: "Rejected in QC" },
  { value: "damaged", label: "Damaged" },
  { value: "expired", label: "Expired" },
];

const BUCKET_LABELS = Object.fromEntries(BUCKET_OPTIONS.map((o) => [o.value, o.label]));

export function bucketLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return BUCKET_LABELS[value] ?? humanise(value);
}

const RAW_ITEM_STATUS_LABELS: Record<string, string> = { returned_to_vendor: "Returned to Vendor", discarded: "Discarded" };

interface RawItem {
  status?: string | null;
  transferId?: string | null;
  acceptedQty?: string | number | null;
  consumedQty?: string | number | null;
  writtenOffQty?: string | number | null;
  bucket?: string | null;
}

/** One canonical, mutually-exclusive display status for a raw-material InventoryItem. */
export function rawItemStatusLabel(item: RawItem): string {
  const status = (item.status ?? "").toLowerCase();
  if (status === "accepted") {
    if (item.transferId) return "In Transit";
    const accepted = Number(item.acceptedQty ?? 0);
    const consumed = Number(item.consumedQty ?? 0);
    const writtenOff = Number(item.writtenOffQty ?? 0);
    if (accepted - consumed - writtenOff <= 1e-9) {
      if (writtenOff > 0) return "Written Off";
      if (consumed > 0) return "Consumed";
    }
    const bucket = item.bucket ?? "available";
    if (bucket !== "available") return bucketLabel(bucket);
    return "Available";
  }
  if (status in RAW_ITEM_STATUS_LABELS) return RAW_ITEM_STATUS_LABELS[status];
  return humanise(status);
}
