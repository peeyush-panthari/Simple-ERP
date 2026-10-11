import { describe, expect, it } from "vitest";
import { monthGrid, monthLabel, shiftMonth, shortDate, tagRange } from "@/lib/calendar";

describe("calendar helpers (ports of production_state.py)", () => {
  it("shifts months across year boundaries", () => {
    expect(shiftMonth("2026-09", 1)).toBe("2026-10");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-03", -14)).toBe("2025-01");
  });

  it("builds a Sunday-first grid of full weeks", () => {
    // September 2026 starts on a Tuesday and has 30 days -> 2 leading blanks, 30 days, 3 trailing blanks = 35.
    const cells = monthGrid("2026-09");
    expect(cells.length).toBe(35);
    expect(cells.slice(0, 2).every((c) => !c.inMonth)).toBe(true);
    expect(cells[2]).toMatchObject({ day: "1", iso: "2026-09-01", inMonth: true });
    expect(cells[31]).toMatchObject({ day: "30", iso: "2026-09-30" });
    expect(cells.slice(32).every((c) => !c.inMonth)).toBe(true);
    // February 2026 starts on a Sunday and has 28 days -> exactly 4 rows.
    expect(monthGrid("2026-02").length).toBe(28);
    // Leap year.
    expect(monthGrid("2028-02").filter((c) => c.inMonth).length).toBe(29);
  });

  it("labels months and dates", () => {
    expect(monthLabel("2026-09")).toBe("September 2026");
    expect(shortDate("2026-09-05")).toBe("Sep 5, 2026");
  });

  it("tags the selected range, in either click order", () => {
    const cells = monthGrid("2026-09");
    const tagged = tagRange(cells, "2026-09-10", "2026-09-14").filter((c) => c.inMonth);
    expect(tagged.filter((c) => c.isStart).map((c) => c.iso)).toEqual(["2026-09-10"]);
    expect(tagged.filter((c) => c.isEnd).map((c) => c.iso)).toEqual(["2026-09-14"]);
    expect(tagged.filter((c) => c.inRange).map((c) => c.iso)).toEqual(["2026-09-11", "2026-09-12", "2026-09-13"]);
    const reversed = tagRange(cells, "2026-09-14", "2026-09-10").filter((c) => c.inMonth);
    expect(reversed.filter((c) => c.inRange).length).toBe(3);
    // A half-picked range highlights only its start.
    const half = tagRange(cells, "2026-09-10", "").filter((c) => c.inMonth);
    expect(half.filter((c) => c.isStart).length).toBe(1);
    expect(half.filter((c) => c.inRange).length).toBe(0);
  });
});
