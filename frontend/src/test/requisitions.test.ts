import { describe, expect, it } from "vitest";
import { trimDecimal } from "@/components/erp/requisitions";

describe("requisition quantities", () => {
  it("trims the API's fixed-scale decimals for editing", () => {
    expect(trimDecimal("25.000000")).toBe("25");
    expect(trimDecimal("2.500000")).toBe("2.5");
    expect(trimDecimal("0.125000")).toBe("0.125");
    expect(trimDecimal("100")).toBe("100");
  });
});
