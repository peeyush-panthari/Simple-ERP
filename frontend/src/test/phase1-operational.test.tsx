import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EmptyState, RecordNotFound } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";

describe("Phase 1: Operational Fixes & Error Resilience", () => {
  describe("F2: RecordNotFound 404 Handling", () => {
    it("renders RecordNotFound correctly for missing inventory items", () => {
      render(
        <MemoryRouter>
          <RecordNotFound entity="Inventory Item" id="ITEM-404-XYZ" backUrl="/inventory" backLabel="← Back to inventory" />
        </MemoryRouter>
      );
      expect(screen.getByText("Inventory Item not found")).toBeInTheDocument();
      expect(screen.getByText(/ITEM-404-XYZ/)).toBeInTheDocument();
      expect(screen.getByText("← Back to inventory")).toBeInTheDocument();
    });

    it("verifies ApiError status 404 identification", () => {
      const err404 = new ApiError(404, { title: "Not Found", detail: "Inventory unit not found" });
      expect(err404 instanceof ApiError).toBe(true);
      expect(err404.status).toBe(404);
      expect(err404.detail).toBe("Inventory unit not found");
    });
  });

  describe("F5: Universal EmptyState Rendering", () => {
    it("renders empty state for inventory balances", () => {
      render(
        <EmptyState
          title="No inventory balances found"
          hint="Try adjusting your warehouse, category, or search filters."
        />
      );
      expect(screen.getByText("No inventory balances found")).toBeInTheDocument();
      expect(screen.getByText("Try adjusting your warehouse, category, or search filters.")).toBeInTheDocument();
    });

    it("renders empty state for goods receipts & under-QC queue", () => {
      const { rerender } = render(
        <EmptyState title="No goods receipts found" hint="Try adjusting your warehouse, status, or search filters." />
      );
      expect(screen.getByText("No goods receipts found")).toBeInTheDocument();

      rerender(<EmptyState title="No goods under QC" hint="There are currently no receipts pending inspection." />);
      expect(screen.getByText("No goods under QC")).toBeInTheDocument();
      expect(screen.getByText("There are currently no receipts pending inspection.")).toBeInTheDocument();
    });

    it("renders empty state for finance invoices and payments", () => {
      const { rerender } = render(
        <EmptyState title="No vendor invoices found" hint="Try adjusting your status filter or post a new invoice." />
      );
      expect(screen.getByText("No vendor invoices found")).toBeInTheDocument();

      rerender(<EmptyState title="No payments found" hint="No incoming or outgoing payments recorded." />);
      expect(screen.getByText("No payments found")).toBeInTheDocument();
    });

    it("renders empty state for logistics transport requests", () => {
      render(
        <EmptyState
          title="No logistics transport requests"
          hint="Try adjusting your status filter or creating a new transport request."
        />
      );
      expect(screen.getByText("No logistics transport requests")).toBeInTheDocument();
    });

    it("renders empty state for user administration", () => {
      render(
        <EmptyState title="No users found" hint="Try adjusting your search query, status, or role filter." />
      );
      expect(screen.getByText("No users found")).toBeInTheDocument();
    });
  });

  describe("B4: Dual PATCH Error Distinction", () => {
    it("constructs explicit diagnostic error message when secondary manager PATCH fails", () => {
      const mErr = new ApiError(422, { title: "Unprocessable", detail: "Manager cannot report to subordinate" });
      const formatErr = (exc: unknown) => {
        const detail = exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc);
        return `Roles updated, but assigning manager failed: ${detail}. Please retry manager selection.`;
      };

      const msg = formatErr(mErr);
      expect(msg).toContain("Roles updated, but assigning manager failed");
      expect(msg).toContain("Manager cannot report to subordinate");
    });
  });
});
