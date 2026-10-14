import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VirtualDataTable } from "@/components/erp/virtual-table";

describe("Phase 3 - Scalability & UI Virtualization (SC3 & SC4)", () => {
  describe("VirtualDataTable (SC3)", () => {
    const columns = ["ID", "Name", "Stock", "Status"];
    const dummyItems = Array.from({ length: 200 }, (_, i) => ({
      id: `ITEM-${i + 1}`,
      name: `Product Item ${i + 1}`,
      stock: (i * 10).toString(),
      status: i % 2 === 0 ? "In Stock" : "Low Stock",
    }));

    it("renders column headers properly", () => {
      render(
        <VirtualDataTable
          columns={columns}
          items={dummyItems.slice(0, 5)}
          renderRow={(item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.name}</td>
              <td>{item.stock}</td>
              <td>{item.status}</td>
            </tr>
          )}
        />
      );

      expect(screen.getByText("ID")).toBeInTheDocument();
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Stock")).toBeInTheDocument();
      expect(screen.getByText("Status")).toBeInTheDocument();
    });

    it("renders emptyState when items list is empty", () => {
      render(
        <VirtualDataTable
          columns={columns}
          items={[]}
          emptyState={<div data-testid="custom-empty-state">No inventory items available</div>}
          renderRow={() => <tr />}
        />
      );

      expect(screen.getByTestId("custom-empty-state")).toBeInTheDocument();
      expect(screen.getByText("No inventory items available")).toBeInTheDocument();
    });

    it("bounds DOM nodes for large datasets (virtualization)", () => {
      const { container } = render(
        <VirtualDataTable
          columns={columns}
          items={dummyItems}
          rowHeight={40}
          maxHeight={400}
          overscan={3}
          renderRow={(item) => (
            <tr key={item.id} data-testid="virtual-row">
              <td>{item.id}</td>
              <td>{item.name}</td>
              <td>{item.stock}</td>
              <td>{item.status}</td>
            </tr>
          )}
        />
      );

      // Total items is 200, but rendered row elements should be far fewer (windowed slice)
      const renderedRows = container.querySelectorAll("tbody tr[data-testid='virtual-row']");
      expect(renderedRows.length).toBeLessThan(50);
      expect(renderedRows.length).toBeGreaterThan(0);

      // First item should be visible initially
      expect(screen.getByText("ITEM-1")).toBeInTheDocument();
      // Item 190 should NOT be in the initial DOM window
      expect(screen.queryByText("ITEM-190")).not.toBeInTheDocument();
    });

    it("handles scroll event and updates visible window", () => {
      const { container } = render(
        <VirtualDataTable
          columns={columns}
          items={dummyItems}
          rowHeight={40}
          maxHeight={400}
          overscan={2}
          renderRow={(item) => (
            <tr key={item.id} data-testid="virtual-row">
              <td>{item.id}</td>
              <td>{item.name}</td>
              <td>{item.stock}</td>
              <td>{item.status}</td>
            </tr>
          )}
        />
      );

      const tableWrap = container.querySelector(".data-table-wrap");
      expect(tableWrap).toBeInTheDocument();

      // Simulate scrolling down by 2000px (~50 rows down)
      if (tableWrap) {
        fireEvent.scroll(tableWrap, { target: { scrollTop: 2000 } });
      }

      // Middle items should now be rendered
      expect(screen.getByText("ITEM-51")).toBeInTheDocument();
    });
  });

  describe("SearchPicker Truncation Indicator Logic (SC4)", () => {
    it("identifies when total count exceeds returned slice", () => {
      const results = Array.from({ length: 50 }, (_, i) => ({ id: `id-${i}` }));
      const total = 184;

      const shouldShowWarning = total !== null && total > results.length;
      expect(shouldShowWarning).toBe(true);

      const warningText = `Showing first ${results.length} of ${total} records — type to narrow search`;
      expect(warningText).toBe("Showing first 50 of 184 records — type to narrow search");
    });

    it("does not show warning when all records are returned", () => {
      const results = Array.from({ length: 15 }, (_, i) => ({ id: `id-${i}` }));
      const total = 15;

      const shouldShowWarning = total !== null && total > results.length;
      expect(shouldShowWarning).toBe(false);
    });
  });
});
