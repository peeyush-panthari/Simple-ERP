import { Shell } from "@/components/erp/shell";
import { EmptyState, PageHeader } from "@/components/erp/ui";

/** Catch-all for addresses that match no page. */
export default function NotFound() {
  return (
    <Shell>
      <PageHeader eyebrow={null} title="Page not found" />
      <div className="panel">
        <EmptyState title="Nothing here" hint="Check the address, or use the navigation." />
      </div>
    </Shell>
  );
}
