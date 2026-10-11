/**
 * Display formatting - a 1:1 port of the Reflex app's format.py (itself a port
 * of the original lib/format.ts). Every money value arriving from the backend
 * is an exact decimal *string*; these helpers accept strings/numbers and only
 * convert to a float at the last moment, for display - never for arithmetic.
 * Deterministic by construction (no locale APIs), so output never depends on
 * the viewer's browser.
 *
 * Python's round() is round-half-to-even on the exact binary value, unlike
 * JS's Math.round/toFixed (half-up); `pyRound` reproduces Python's behaviour
 * so a value like 2.5 or 12.25 renders identically to the Reflex app.
 */

export type Numeric = string | number | null | undefined;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Python-compatible round(x, digits): correctly rounded, ties to even. */
export function pyRound(x: number, digits = 0): number {
  if (!Number.isFinite(x)) return x;
  const negative = x < 0;
  const exact = Math.abs(x).toFixed(Math.min(100, digits + 40)); // exact decimal expansion of the double
  const dot = exact.indexOf(".");
  const intPart = exact.slice(0, dot);
  const frac = exact.slice(dot + 1);
  const kept = frac.slice(0, digits);
  const rest = frac.slice(digits);
  let digitsStr = intPart + kept;
  const firstDropped = rest.charCodeAt(0) - 48;
  const restIsZero = /^0*$/.test(rest.slice(1));
  const lastKept = digitsStr.length ? digitsStr.charCodeAt(digitsStr.length - 1) - 48 : 0;
  const roundUp = firstDropped > 5 || (firstDropped === 5 && (!restIsZero || lastKept % 2 === 1));
  let value = BigInt(digitsStr || "0");
  if (roundUp) value += 1n;
  digitsStr = value.toString().padStart(digits + 1, "0");
  const whole = digitsStr.slice(0, digitsStr.length - digits) || "0";
  const decimals = digits ? digitsStr.slice(digitsStr.length - digits) : "";
  const result = Number(decimals ? `${whole}.${decimals}` : whole);
  return negative ? -result : result;
}

/** Indian digit grouping: last 3 digits, then pairs - "1234567" -> "12,34,567". */
function groupIn(n: number): string {
  const s = String(Math.trunc(pyRound(Math.abs(n))));
  if (s.length <= 3) return s;
  const last3 = s.slice(-3);
  let rest = s.slice(0, -3);
  const grouped: string[] = [];
  while (rest.length > 2) {
    grouped.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) grouped.unshift(rest);
  return `${grouped.join(",")},${last3}`;
}

function toNumber(value: Numeric): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function symbolFor(currency: string): string {
  return currency === "INR" ? "₹" : `${currency} `;
}

/** Rounds to `maxDp` places and splits into [whole, frac]; frac is "" for a whole number. */
function splitDecimal(n: number, maxDp = 2): [string, string] {
  const rounded = pyRound(Math.abs(n), maxDp);
  if (rounded === Math.trunc(rounded)) return [String(Math.trunc(rounded)), ""];
  const [whole, frac] = rounded.toFixed(maxDp).split(".");
  return [whole, frac];
}

export function money(value: Numeric, currency = "INR"): string {
  const n = toNumber(value);
  const sign = n < 0 ? "-" : "";
  const [whole, frac] = splitDecimal(n);
  return `${symbolFor(currency)}${sign}${groupIn(Number(whole))}${frac ? `.${frac}` : ""}`;
}

/** Indian short scale - lakh and crore. */
export function compactMoney(value: Numeric, currency = "INR"): string {
  const n = toNumber(value);
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const symbol = symbolFor(currency);
  const fmt = (v: number, suffix: string) => {
    const r = pyRound(v * 10) / 10;
    const rStr = r === Math.trunc(r) ? r.toFixed(0) : r.toFixed(1);
    return `${symbol}${sign}${rStr}${suffix}`;
  };
  if (abs >= 1e7) return fmt(abs / 1e7, "Cr");
  if (abs >= 1e5) return fmt(abs / 1e5, "L");
  if (abs >= 1e3) return fmt(abs / 1e3, "K");
  return `${symbol}${sign}${groupIn(abs)}`;
}

/** No decimal point for a whole number; otherwise 2 places. Indian grouping on the integer part. */
export function qty(value: Numeric, uom?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return uom ? `${value} ${uom}` : String(value);
  const sign = n < 0 ? "-" : "";
  const [whole, frac] = splitDecimal(n);
  const s = `${sign}${groupIn(Number(whole))}${frac ? `.${frac}` : ""}`;
  return uom ? `${s} ${uom}` : s;
}

export function percent(value: Numeric): string {
  const n = toNumber(value);
  const sign = n < 0 ? "-" : "";
  const [whole, frac] = splitDecimal(n);
  return `${sign}${whole}${frac ? `.${frac}` : ""}%`;
}

/** "2026-08-19" -> "19 Aug 2026". Parsed as plain date parts so it never shifts a day for a timezone reason. */
export function date(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const iso = typeof value === "string" ? value : value.toISOString();
  const parts = iso.slice(0, 10).split("-").map(Number);
  if (parts.length !== 3 || parts.some((p) => !Number.isInteger(p) || !p)) return "—";
  const [y, m, d] = parts;
  return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]} ${y}`;
}

export function dateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const iso = typeof value === "string" ? value : value.toISOString();
  return `${date(iso)} ${iso.slice(11, 16)}`;
}

export function timeOnly(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const iso = typeof value === "string" ? value : value.toISOString();
  return iso.slice(11, 16);
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
