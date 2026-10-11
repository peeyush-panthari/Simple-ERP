import { describe, expect, it } from "vitest";
import { autoPick, gFormat, isCovered, pickedQty } from "@/lib/production";

const stock = [
  { id: "a", inventoryId: "INV-1", availableQty: "3" },
  { id: "b", inventoryId: "INV-2", availableQty: "10" },
  { id: "c", inventoryId: "INV-3", availableQty: "0" },
];

describe("production picker maths (ports of production_state.py)", () => {
  it("auto-picks greedily in list order and stops at the requirement", () => {
    const picks = autoPick("5", [], stock);
    expect(picks.map((p) => [p.inventoryId, p.quantity])).toEqual([["INV-1", "3"], ["INV-2", "2"]]);
    expect(isCovered("5", picks)).toBe(true);
  });

  it("skips units already picked and zero-availability units, and is a no-op once covered", () => {
    const first = autoPick("4", [{ itemId: "a", inventoryId: "INV-1", quantity: "1" }], stock);
    expect(first.map((p) => [p.itemId, p.quantity])).toEqual([["a", "1"], ["b", "3"]]);
    expect(autoPick("4", first, stock)).toBe(first);
    expect(autoPick("100", [], [stock[2]])).toEqual([]);
  });

  it("treats a shortfall as not covered but tolerates float dust", () => {
    expect(isCovered("5", [{ itemId: "a", inventoryId: "x", quantity: "4" }])).toBe(false);
    expect(isCovered("0.3", [{ itemId: "a", inventoryId: "x", quantity: String(0.1 + 0.2) }])).toBe(true);
    expect(pickedQty(undefined)).toBe(0);
  });

  it("formats prefilled quantities like Python's :g", () => {
    expect(gFormat("5.000000")).toBe("5");
    expect(gFormat("1.500000")).toBe("1.5");
  });
});
