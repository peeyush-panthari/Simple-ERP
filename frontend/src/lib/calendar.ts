/** Calendar helpers for the date-range picker - port of production_state.py's _month_grid / _shift_month / _tag_range. */

const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export interface DayCell {
  day: string;
  iso: string;
  inMonth: boolean;
  isStart: boolean;
  isEnd: boolean;
  inRange: boolean;
}

/** "2026-09" + 1 -> "2026-10", wrapping the year at Dec/Jan. */
export function shiftMonth(anchor: string, delta: number): string {
  const [y, m] = anchor.split("-").map(Number);
  const total = y * 12 + (m - 1) + delta;
  const y2 = Math.floor(total / 12);
  const m2 = total - y2 * 12;
  return `${String(y2).padStart(4, "0")}-${String(m2 + 1).padStart(2, "0")}`;
}

/** Sunday-first grid for "YYYY-MM": blank (inMonth false) cells included so every week is a full row of 7. */
export function monthGrid(anchor: string): DayCell[] {
  const [y, m] = anchor.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay(); // 0 = Sunday
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const blank = (): DayCell => ({ day: "", iso: "", inMonth: false, isStart: false, isEnd: false, inRange: false });
  const cells: DayCell[] = Array.from({ length: first }, blank);
  for (let d = 1; d <= days; d++) {
    cells.push({ day: String(d), iso: `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`, inMonth: true, isStart: false, isEnd: false, inRange: false });
  }
  while (cells.length % 7 !== 0) cells.push(blank());
  return cells;
}

export function monthLabel(anchor: string): string {
  const [y, m] = anchor.split("-").map(Number);
  return `${FULL_MONTHS[m - 1]} ${y}`;
}

/** "2026-09-05" -> "Sep 5, 2026". */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${SHORT_MONTHS[m - 1]} ${d}, ${y}`;
}

export function tagRange(cells: DayCell[], start: string, end: string): DayCell[] {
  const both = !!start && !!end;
  const [lo, hi] = both ? (start <= end ? [start, end] : [end, start]) : ["", ""];
  return cells.map((c) => ({
    ...c,
    isStart: !!c.iso && c.iso === start,
    isEnd: !!c.iso && c.iso === end,
    inRange: !!c.iso && !!lo && !!hi && lo < c.iso && c.iso < hi,
  }));
}
