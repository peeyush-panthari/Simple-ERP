import { describe, expect, it } from "vitest";
import { groupedNav, mobileTabItems, permits, visibleNav } from "@/lib/nav";

describe("permission-filtered navigation", () => {
  it("wildcards", () => {
    expect(permits(["*"], "anything:read")).toBe(true);
    expect(permits(["order:*"], "order:ship")).toBe(true);
    expect(permits(["order:read"], "order:ship")).toBe(false);
  });

  it("shows only what the role can read, grouped in the fixed group order", () => {
    const groups = groupedNav(["order:read", "analytics:read", "audit:read"]);
    expect(groups.map((g) => g.group)).toEqual(["Overview", "Sales & Orders", "Administration"]);
    expect(groups[0].items.map((i) => i.path)).toEqual(["/", "/architecture"]);
  });

  it("Email Config sits under Administration and needs its own permission", () => {
    expect(visibleNav(["party:read"]).map((i) => i.path)).not.toContain("/email-config");
    const item = groupedNav(["email_config:read"]).find((g) => g.group === "Administration")?.items[0];
    expect(item).toMatchObject({ label: "Email Config", path: "/email-config" });
    expect(visibleNav(["*"]).map((i) => i.label)).toContain("Email Config");
  });

  it("Training Module sits under Administration and opens with training:read or user:read", () => {
    expect(visibleNav(["party:read"]).map((i) => i.path)).not.toContain("/training");
    const itemTraining = groupedNav(["training:read"]).find((g) => g.group === "Administration")?.items[0];
    expect(itemTraining).toMatchObject({ label: "Training Module", path: "/training" });
    expect(visibleNav(["user:read"]).map((i) => i.path)).toContain("/training");
    expect(visibleNav(["*"]).map((i) => i.label)).toContain("Training Module");
  });

  it("Procurement also opens for an employee who can only raise purchase requisitions", () => {
    expect(visibleNav(["pr:read", "pr:write"]).map((i) => i.path)).toEqual(["/procurement"]);
    expect(visibleNav(["pr:approve"]).map((i) => i.path)).toEqual(["/procurement"]);
    expect(visibleNav(["pr:team_approve"]).map((i) => i.path)).toEqual(["/procurement"]);
    expect(visibleNav(["sourcing:read"]).map((i) => i.path)).toEqual(["/procurement"]);
    expect(visibleNav(["po:read"]).map((i) => i.path)).toEqual(["/procurement"]);
    expect(visibleNav(["party:read"]).map((i) => i.path)).not.toContain("/procurement");
  });

  it("a user with no permissions sees no nav", () => {
    expect(visibleNav([])).toEqual([]);
  });

  it("mobile bottom bar keeps the four fixed modules in order", () => {
    expect(mobileTabItems(["*"]).map((i) => i.path)).toEqual(["/", "/warehouse", "/production", "/orders"]);
    expect(mobileTabItems(["order:read"]).map((i) => i.path)).toEqual(["/orders"]);
  });
});
