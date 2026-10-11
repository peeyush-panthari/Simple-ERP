/** Inventory-ID pickers used by production (BOM picks and additional materials) - popover checklist and removable chips. */
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, X } from "lucide-react";
import { CheckRow } from "@/components/erp/extras";

export interface AvailableItem {
  id: string;
  inventoryId: string;
  availableQty: string;
  [k: string]: unknown;
}

/** UNIT-tracked stock: each Inventory ID is one whole piece, so several can be ticked on one line. */
export function ItemMultiSelect({ items, selected, onToggle }: { items: AvailableItem[]; selected: string[]; onToggle: (id: string) => void }) {
  const label = items.length === 0 ? "No stock at this warehouse" : selected.length === 0 ? "Select Inventory IDs" : `${selected.length} selected`;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" disabled={items.length === 0} className="filter-select flex w-full items-center justify-between gap-2">
          <span>{label}</span>
          <ChevronDown size={14} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="popover-content" style={{ width: "18rem" }} align="start" sideOffset={4}>
          <div className="check-list" style={{ maxHeight: "10rem", overflowY: "auto", width: "100%" }}>
            {items.map((it) => (
              <CheckRow key={it.id} label={`${it.inventoryId} (${it.availableQty} avail)`} checked={selected.includes(it.id)} onChange={() => onToggle(it.id)} />
            ))}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="chip">
      <span>{label}</span>
      <button type="button" className="chip-remove" onClick={onRemove} aria-label={`Remove ${label}`}>
        <X size={12} />
      </button>
    </span>
  );
}
