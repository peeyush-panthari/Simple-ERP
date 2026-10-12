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

import { shippingRows } from "@/routes/production";

describe("shippingRows helper", () => {
  it("handles null and undefined gracefully without throwing", () => {
    expect(shippingRows(undefined)).toEqual([]);
    expect(shippingRows(null)).toEqual([]);
    expect(shippingRows([])).toEqual([]);
  });

  it("safely skips orders without lines or with cancelled/unallocated items", () => {
    const raw = [
      { id: "o1", number: "SO-1", customerName: "Acme", status: "confirmed" } as any,
      {
        id: "o2",
        number: "SO-2",
        customerName: "Beta",
        status: "confirmed",
        lines: [
          { id: "l1", status: "cancelled", allocatedQty: "10" } as any,
          { id: "l2", status: "allocated", allocatedQty: "0" } as any,
        ],
      },
    ];
    expect(shippingRows(raw)).toEqual([]);
  });

  it("builds ship rows correctly for allocated orders", () => {
    const raw = [
      {
        id: "o1",
        number: "SO-101",
        customerName: "Globex",
        status: "allocated",
        lines: [
          {
            id: "line-1",
            sku: "SKU-A",
            productName: "Item A",
            uom: "EA",
            allocatedQty: "5",
            packedQty: "0",
            shippedQty: "0",
            status: "allocated",
            allocation: { batchNo: "BATCH-1", inventoryIds: ["INV-1", "INV-2"] },
          },
        ],
      },
    ];
    const rows = shippingRows(raw);
    expect(rows).toHaveLength(1);
    expect(rows[0].orderNumber).toBe("SO-101");
    expect(rows[0].customerName).toBe("Globex");
    expect(rows[0].skuName).toBe("Item A");
    expect(rows[0].status).toBe("pending_packing");
    expect(rows[0].actionMode).toBe("pack");
    expect(rows[0].actionMax).toBe(5);
    expect(rows[0].inventoryIds).toBe("INV-1, INV-2");
  });
});
