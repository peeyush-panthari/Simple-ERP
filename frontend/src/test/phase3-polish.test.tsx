import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import * as format from "@/lib/format";
import { EmptyState, RecordNotFound } from "@/components/erp/ui";

describe("Phase 3: Strict ISO Date Parsing & Validation", () => {
  it("formats valid ISO dates correctly", () => {
    expect(format.date("2026-08-19")).toBe("19 Aug 2026");
    expect(format.date("2026-01-05")).toBe("05 Jan 2026");
    expect(format.date("2026-12-31")).toBe("31 Dec 2026");
  });

  it("returns dash for out-of-range years (< 1900 or > 9999)", () => {
    expect(format.date("1899-12-31")).toBe("—");
    expect(format.date("10000-01-01")).toBe("—");
  });

  it("returns dash for out-of-range months (not between 1 and 12)", () => {
    expect(format.date("2026-00-15")).toBe("—");
    expect(format.date("2026-13-15")).toBe("—");
  });

  it("returns dash for out-of-range days (not between 1 and 31)", () => {
    expect(format.date("2026-08-00")).toBe("—");
    expect(format.date("2026-08-32")).toBe("—");
  });

  it("returns dash for empty, null, or garbage inputs", () => {
    expect(format.date("")).toBe("—");
    expect(format.date(null)).toBe("—");
    expect(format.date(undefined)).toBe("—");
    expect(format.date("invalid-date")).toBe("—");
  });
});

describe("Phase 3: Route-Level 404 & Empty State Components", () => {
  it("renders RecordNotFound with entity name, ID, and back navigation", () => {
    render(
      <MemoryRouter>
        <RecordNotFound entity="Production Run" id="RUN-999" backUrl="/production" />
      </MemoryRouter>
    );
    expect(screen.getByText("Production Run not found")).toBeInTheDocument();
    expect(screen.getByText(/RUN-999/)).toBeInTheDocument();
    expect(screen.getByText("← Back to production run list")).toBeInTheDocument();
  });

  it("renders EmptyState with title and hint", () => {
    render(<EmptyState title="No purchase orders found" hint="Adjust your status filters." />);
    expect(screen.getByText("No purchase orders found")).toBeInTheDocument();
    expect(screen.getByText("Adjust your status filters.")).toBeInTheDocument();
  });
});
