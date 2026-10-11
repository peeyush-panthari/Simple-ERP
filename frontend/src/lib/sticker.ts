/**
 * Live client-side mirror of the backend's sticker-size layout check
 * (_assert_layout_fits): recomputed on every keystroke so a layout that won't
 * fit is flagged before Save, naming whichever of the page's width or height
 * is the actual problem. The backend re-checks authoritatively on submit, so
 * this is advisory, not a gate.
 */

/** Standard sheet dimensions in mm - matches the backend's PAGE_SIZE_MM. */
export const PAGE_SIZE_MM: Record<string, [number, number]> = { A4: [210, 297], A5: [148, 210], Letter: [215.9, 279.4] };
export const STICKER_PAGE_SIZES = ["A4", "A5", "Letter", "Custom"];

const mm = (value: string): number => {
  const n = Number(value?.trim());
  return value && value.trim() && Number.isFinite(n) ? n : 0;
};
/** Python's `:g` - up to 6 significant digits, no trailing zeros. */
const g = (n: number) => String(Number(n.toPrecision(6)));
const wholeNumber = (s: string) => (/^\d+$/.test(s.trim()) ? Number(s.trim()) : 0);

export interface StickerLayout {
  pageSize: string;
  pageWidthMm: string;
  pageHeightMm: string;
  stickerWidthMm: string;
  stickerHeightMm: string;
  columns: string;
  rows: string;
  marginLeftMm: string;
  marginRightMm: string;
  marginTopMm: string;
  marginBottomMm: string;
  gapHorizontalMm: string;
  gapVerticalMm: string;
}

export function stickerTotal(columns: string, rows: string): string {
  const c = /^-?\d+$/.test(columns.trim()) ? Number(columns) : columns.trim() ? NaN : 0;
  const r = /^-?\d+$/.test(rows.trim()) ? Number(rows) : rows.trim() ? NaN : 0;
  if (Number.isNaN(c) || Number.isNaN(r)) return "—";
  return c && r ? String(c * r) : "—";
}

export function stickerFitIssue(l: StickerLayout): string {
  const columns = wholeNumber(l.columns);
  const rows = wholeNumber(l.rows);
  const stickerW = mm(l.stickerWidthMm);
  const stickerH = mm(l.stickerHeightMm);
  if (!(columns > 0 && rows > 0 && stickerW > 0 && stickerH > 0)) return ""; // not enough entered yet

  let pageW: number;
  let pageH: number;
  if (l.pageSize === "Custom") {
    pageW = mm(l.pageWidthMm);
    pageH = mm(l.pageHeightMm);
    if (pageW <= 0 || pageH <= 0) return "";
  } else {
    [pageW, pageH] = PAGE_SIZE_MM[l.pageSize] ?? [0, 0];
  }
  const neededW = stickerW * columns + mm(l.gapHorizontalMm) * (columns - 1) + mm(l.marginLeftMm) + mm(l.marginRightMm);
  const neededH = stickerH * rows + mm(l.gapVerticalMm) * (rows - 1) + mm(l.marginTopMm) + mm(l.marginBottomMm);
  if (neededW > pageW + 1e-9) {
    return `Doesn't fit the page width: ${columns} column(s) of ${g(stickerW)}mm stickers with margins and gaps need ${g(neededW)}mm, but the page is only ${g(pageW)}mm wide.`;
  }
  if (neededH > pageH + 1e-9) {
    return `Doesn't fit the page height: ${rows} row(s) of ${g(stickerH)}mm stickers with margins and gaps need ${g(neededH)}mm, but the page is only ${g(pageH)}mm tall.`;
  }
  return "";
}
