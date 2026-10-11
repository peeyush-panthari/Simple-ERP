import { describe, expect, it } from "vitest";
import { stickerFitIssue, stickerTotal, type StickerLayout } from "@/lib/sticker";

const base: StickerLayout = { pageSize: "A4", pageWidthMm: "", pageHeightMm: "", stickerWidthMm: "50", stickerHeightMm: "25", columns: "3", rows: "10", marginLeftMm: "5", marginRightMm: "5", marginTopMm: "5", marginBottomMm: "5", gapHorizontalMm: "2", gapVerticalMm: "2" };

describe("sticker layout fit check", () => {
  it("accepts a layout that fits an A4 sheet", () => {
    expect(stickerFitIssue(base)).toBe("");
  });
  it("names the width when columns overflow (message identical to the Reflex app's)", () => {
    expect(stickerFitIssue({ ...base, columns: "5" })).toBe("Doesn't fit the page width: 5 column(s) of 50mm stickers with margins and gaps need 268mm, but the page is only 210mm wide.");
  });
  it("names the height when rows overflow", () => {
    expect(stickerFitIssue({ ...base, rows: "13" })).toContain("Doesn't fit the page height: 13 row(s) of 25mm");
  });
  it("stays quiet until enough is entered, and for an incomplete Custom page", () => {
    expect(stickerFitIssue({ ...base, stickerWidthMm: "" })).toBe("");
    expect(stickerFitIssue({ ...base, pageSize: "Custom" })).toBe("");
    expect(stickerFitIssue({ ...base, pageSize: "Custom", pageWidthMm: "100", pageHeightMm: "400" })).toContain("page width");
  });
  it("total stickers per page", () => {
    expect(stickerTotal("3", "10")).toBe("30");
    expect(stickerTotal("", "10")).toBe("—");
    expect(stickerTotal("x", "10")).toBe("—");
  });
});
