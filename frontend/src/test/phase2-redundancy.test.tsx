import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as format from "@/lib/format";
import { errMsg, errText } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  UOMS,
  GST_LABELS,
  gstLabel,
  INDIAN_STATE_SELECT_OPTIONS,
  indianStateSelectOptions,
  ACTIVE_STATUS_OPTIONS,
} from "@/lib/reference";
import { usePagination } from "@/lib/hooks";

describe("Phase 2 - Redundancy Cleanup & Shared Utilities", () => {
  describe("format.lineDisplayName (RX4)", () => {
    it("prefers productName if present", () => {
      expect(format.lineDisplayName({ productName: "Steel Rod 10mm", name: "Steel", sku: "SR-10" })).toBe("Steel Rod 10mm");
    });

    it("falls back to name if productName is absent", () => {
      expect(format.lineDisplayName({ name: "Copper Wire", sku: "CW-01" })).toBe("Copper Wire");
      expect(format.lineDisplayName({ productName: null, name: "Copper Wire", sku: "CW-01" })).toBe("Copper Wire");
    });

    it("falls back to itemName if productName and name are absent", () => {
      expect(format.lineDisplayName({ itemName: "Aluminium Sheet", sku: "AL-50" })).toBe("Aluminium Sheet");
    });

    it("falls back to sku if name and productName are absent", () => {
      expect(format.lineDisplayName({ sku: "SKU-999" })).toBe("SKU-999");
    });

    it("returns dash for null, undefined, or empty object", () => {
      expect(format.lineDisplayName(null)).toBe("—");
      expect(format.lineDisplayName(undefined)).toBe("—");
      expect(format.lineDisplayName({})).toBe("—");
      expect(format.lineDisplayName({ productName: "" })).toBe("—");
    });

    it("lineName alias behaves identically", () => {
      expect(format.lineName({ productName: "Item A" })).toBe("Item A");
      expect(format.lineName(null)).toBe("—");
    });
  });

  describe("errMsg / errText helper (RX5)", () => {
    it("extracts detail from ApiError", () => {
      const err = new ApiError(400, { detail: "SKU already exists", code: "DUPLICATE_SKU" });
      expect(errMsg(err)).toBe("SKU already exists");
      expect(errText(err)).toBe("SKU already exists");
    });

    it("extracts message from standard Error", () => {
      const err = new Error("Network timeout");
      expect(errMsg(err)).toBe("Network timeout");
      expect(errText(err)).toBe("Network timeout");
    });

    it("extracts string representation from primitive errors", () => {
      expect(errMsg("Custom raw error")).toBe("Custom raw error");
      expect(errMsg(12345)).toBe("12345");
    });

    it("returns friendly fallback on empty/null/undefined error", () => {
      expect(errMsg(null)).toBe("An unexpected error occurred");
      expect(errMsg("")).toBe("An unexpected error occurred");
    });
  });

  describe("Reference constants & helpers (RX2, RX3, RX7, RX8)", () => {
    it("centralized UOMS includes essential ERP unit values", () => {
      expect(UOMS).toContain("UNIT");
      expect(UOMS).toContain("KG");
      expect(UOMS).toContain("L");
      expect(UOMS).toContain("M");
    });

    it("gstLabel returns clean label for known GST codes and falls back to code", () => {
      expect(gstLabel("GST18")).toBe(GST_LABELS["GST18"]);
      expect(GST_LABELS["GST18"]).toBe("18%");
      expect(gstLabel("GST0")).toBe("0%");
      expect(gstLabel("UNKNOWN_CODE")).toBe("UNKNOWN_CODE");
    });

    it("indianStateSelectOptions returns select options with 36 states/UTs", () => {
      expect(INDIAN_STATE_SELECT_OPTIONS.length).toBeGreaterThanOrEqual(36);
      expect(INDIAN_STATE_SELECT_OPTIONS[0]).toHaveProperty("value");
      expect(INDIAN_STATE_SELECT_OPTIONS[0]).toHaveProperty("label");
      expect(indianStateSelectOptions()).toEqual(INDIAN_STATE_SELECT_OPTIONS);
    });

    it("ACTIVE_STATUS_OPTIONS contains active and suspended options", () => {
      expect(ACTIVE_STATUS_OPTIONS).toEqual([
        { value: "active", label: "Active" },
        { value: "suspended", label: "Suspended" },
      ]);
    });
  });

  describe("usePagination hook (RX6, RX9)", () => {
    it("initializes with page 1 by default and supports both tuple and object destructuring", () => {
      const { result } = renderHook(() => usePagination());

      // Array tuple access
      const [pageTuple, setPageTuple, resetPageTuple] = result.current;
      expect(pageTuple).toBe(1);
      expect(typeof setPageTuple).toBe("function");
      expect(typeof resetPageTuple).toBe("function");

      // Object property access
      expect(result.current.page).toBe(1);
      expect(result.current.setPage).toBe(setPageTuple);
      expect(result.current.resetPage).toBe(resetPageTuple);
    });

    it("initializes with custom initial page", () => {
      const { result } = renderHook(() => usePagination(5));
      expect(result.current.page).toBe(5);
      expect(result.current[0]).toBe(5);
    });

    it("setPage updates the page state and resetPage resets to 1", () => {
      const { result } = renderHook(() => usePagination(1));

      act(() => {
        result.current.setPage(4);
      });
      expect(result.current.page).toBe(4);
      expect(result.current[0]).toBe(4);

      act(() => {
        result.current.resetPage();
      });
      expect(result.current.page).toBe(1);
      expect(result.current[0]).toBe(1);
    });
  });
});
