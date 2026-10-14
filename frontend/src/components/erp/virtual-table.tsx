import { useState, useRef, useEffect, useMemo, type ReactNode, type UIEvent } from "react";
import { cn } from "@/lib/utils";

export interface VirtualDataTableProps<T> {
  columns: ReactNode[];
  items: T[];
  renderRow: (item: T, index: number) => ReactNode;
  rowHeight?: number;
  maxHeight?: number | string;
  overscan?: number;
  minWidth?: number;
  fit?: boolean;
  className?: string;
  emptyState?: ReactNode;
}

/**
 * Lightweight, zero-dependency virtualized table component for dense datasets (>100 rows).
 * Keeps DOM node count bounded (<50 rows) regardless of dataset size, maintaining 60 FPS
 * scrolling on mobile and low-spec devices while preserving DataTable styling and column headers.
 */
export function VirtualDataTable<T>({
  columns,
  items,
  renderRow,
  rowHeight = 44,
  maxHeight = 480,
  overscan = 5,
  minWidth = 720,
  fit = false,
  className,
  emptyState,
}: VirtualDataTableProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(
    typeof maxHeight === "number" ? maxHeight : 480
  );

  useEffect(() => {
    if (containerRef.current) {
      setViewportHeight(containerRef.current.clientHeight || 480);
    }
  }, [maxHeight]);

  const onScroll = (e: UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  const totalCount = items.length;

  const { topPadding, bottomPadding, visibleItems } = useMemo(() => {
    if (totalCount === 0) {
      return { topPadding: 0, bottomPadding: 0, visibleItems: [] };
    }

    const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const visibleCount = Math.ceil(viewportHeight / rowHeight) + overscan * 2;
    const end = Math.min(totalCount, start + visibleCount);

    const top = start * rowHeight;
    const bottom = Math.max(0, (totalCount - end) * rowHeight);

    return {
      topPadding: top,
      bottomPadding: bottom,
      visibleItems: items.slice(start, end).map((item, idx) => ({
        item,
        index: start + idx,
      })),
    };
  }, [totalCount, scrollTop, rowHeight, overscan, viewportHeight, items]);

  if (totalCount === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      className={cn("data-table-wrap overflow-y-auto", className)}
      style={{ maxHeight, height: maxHeight }}
      tabIndex={0}
      aria-label="Virtualized data table"
    >
      <table className={cn("data-table", fit && "data-table-fit")} style={fit ? undefined : { minWidth }}>
        <thead className="sticky top-0 z-10 bg-[var(--card)] shadow-xs">
          <tr>
            {columns.map((c, i) => {
              const isEmpty = c === "" || c === null || c === undefined || (typeof c === "string" && c.trim() === "");
              return (
                <th key={i} scope="col">
                  {isEmpty ? <span className="sr-only">Row Actions</span> : c}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {topPadding > 0 && (
            <tr style={{ height: topPadding }} aria-hidden="true">
              <td colSpan={columns.length} style={{ height: topPadding, padding: 0, border: 0 }} />
            </tr>
          )}
          {visibleItems.map(({ item, index }) => renderRow(item, index))}
          {bottomPadding > 0 && (
            <tr style={{ height: bottomPadding }} aria-hidden="true">
              <td colSpan={columns.length} style={{ height: bottomPadding, padding: 0, border: 0 }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
