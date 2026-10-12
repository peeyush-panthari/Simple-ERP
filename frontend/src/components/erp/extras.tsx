/**
 * Interaction pieces the page kit doesn't cover: toasts, a confirm dialog
 * (Radix AlertDialog), a searchable checkbox multi-select popover and a
 * checkbox row. Same Radix primitives shadcn/ui wraps, styled with the app's
 * recipes in theme.css.
 */
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { ActionButton, InlineError, SearchInput } from "@/components/erp/ui";
import { cn } from "@/lib/utils";

// ---- toasts ------------------------------------------------------------------------

interface ToastItem {
  id: string;
  kind: "success" | "error";
  message: string;
}
interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const push = useCallback((kind: ToastItem["kind"], message: string) => {
    const id = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${++toastCounter}`;
    setToasts((t) => [...t, { id, kind, message }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  const api = useMemo<ToastApi>(() => ({ success: (m) => push("success", m), error: (m) => push("error", m) }), [push]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cn("toast", t.kind === "success" ? "toast-success" : "toast-error")}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

// ---- confirm dialog ------------------------------------------------------------------

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Delete",
  error,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  error?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog.Root open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="dialog-overlay" />
        <AlertDialog.Content className="dialog-content" style={{ maxWidth: "28rem", padding: "1.25rem" }}>
          <AlertDialog.Title className="dialog-title">{title}</AlertDialog.Title>
          <AlertDialog.Description className="dialog-description" style={{ marginTop: "0.5rem" }}>
            {description}
          </AlertDialog.Description>
          <div className="mt-3">
            <InlineError message={error} />
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <ActionButton tone="ghost">Cancel</ActionButton>
            </AlertDialog.Cancel>
            <ActionButton tone="danger" onClick={onConfirm}>
              {confirmLabel}
            </ActionButton>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

// ---- checkboxes / multi-select ---------------------------------------------------------

export function CheckRow({ label, checked, onChange, disabled }: { label: ReactNode; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return (
    <label className="check-row">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

/** A button that opens a popover of checkboxes (optionally searchable) - roles / warehouses / factories pickers. */
export function MultiSelect<T>({
  items,
  selected,
  onToggle,
  getId,
  getLabel,
  placeholder,
  countLabel = (n: number) => `${n} selected`,
  searchable = false,
  searchPlaceholder = "Search…",
  width = "20rem",
}: {
  items: T[];
  selected: string[];
  onToggle: (id: string) => void;
  getId: (item: T) => string;
  getLabel: (item: T) => string;
  placeholder: string;
  countLabel?: (n: number) => string;
  searchable?: boolean;
  searchPlaceholder?: string;
  width?: string;
}) {
  const [query, setQuery] = useState("");
  const shown = query.trim() ? items.filter((i) => getLabel(i).toLowerCase().includes(query.trim().toLowerCase())) : items;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" className="filter-select flex w-full items-center justify-between gap-2">
          <span>{selected.length === 0 ? placeholder : countLabel(selected.length)}</span>
          <ChevronDown size={14} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="popover-content" style={{ width }} align="start" sideOffset={4}>
          <div className="flex w-full flex-col gap-2">
            {searchable && <SearchInput value={query} onChange={setQuery} placeholder={searchPlaceholder} />}
            <div className="check-list">
              {shown.map((item) => (
                <CheckRow key={getId(item)} label={getLabel(item)} checked={selected.includes(getId(item))} onChange={() => onToggle(getId(item))} />
              ))}
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function toggleIn(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export { X as CloseIcon };
