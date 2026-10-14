/**
 * Design-system kit - a 1:1 port of the Reflex app's components/ui_kit.py
 * (which ported the original components/erp/ui.tsx). Every page builds its
 * visual furniture from here so the "stat-card row -> filter -> table ->
 * dialog" look stays consistent. Styling comes from the recipe classes in
 * styles/theme.css; interaction primitives (dialog, tabs) are Radix, the same
 * primitives shadcn/ui is built on.
 */

import * as Dialog from "@radix-ui/react-dialog";
import { Clock, Inbox, Info, ShieldAlert, TriangleAlert, X } from "lucide-react";
import { cloneElement, forwardRef, isValidElement, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type MouseEvent, type InputHTMLAttributes, type ReactElement, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { useActiveReads, useActiveRequests } from "@/lib/activity";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toneFor, type Tone } from "@/lib/status";

// ---- status pill ---------------------------------------------------------------

const PILL_CLASS: Record<Tone, string> = {
  success: "pill pill-success",
  warning: "pill pill-warning",
  info: "pill pill-info",
  destructive: "pill pill-destructive",
  muted: "pill pill-muted",
};

/** Status badge. `tone` overrides auto-detection (e.g. priority `urgent` -> destructive). */
export function Pill({ children, tone }: { children: ReactNode; tone?: Tone }) {
  const resolved = tone ?? (typeof children === "string" ? toneFor(children) : "muted");
  return <span className={PILL_CLASS[resolved]}>{children}</span>;
}

/** Radix Themes soft <Badge> (what the Reflex architecture and notification pages use instead of the pill). */
export function Badge({ children, color = "gray" }: { children: ReactNode; color?: "green" | "red" | "gray" | "amber" }) {
  return <span className={`rx-badge rx-badge-${color}`}>{children}</span>;
}

// ---- page furniture -------------------------------------------------------------

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  titleSuffix,
  fit = false,
}: {
  /** Shrink the header (and its underline) to its content, as the Reflex pages that sit in an align-start stack do. */
  fit?: boolean;
  eyebrow?: string | null;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  titleSuffix?: ReactNode;
}) {
  return (
    <div className={cn("page-header", fit && "w-fit")}>
      <div className="min-w-0">
        {eyebrow ? <p className="page-header-eyebrow">{eyebrow}</p> : null}
        {titleSuffix ? (
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="page-header-title">{title}</h1>
            {titleSuffix}
          </div>
        ) : (
          <h1 className="page-header-title">{title}</h1>
        )}
        {description ? <p className="page-header-description">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

type ActionTone = "primary" | "ghost" | "danger";
// Every button wears the same colour; `tone` is kept so call sites still say what a button is for.
const ACTION_TONE: Record<ActionTone, string> = { primary: "action-btn-primary", ghost: "action-btn-primary", danger: "action-btn-primary" };

/** A small rotating ring in the current text colour. */
export function Spinner({ size = 14, className }: { size?: number; className?: string }) {
  return <span role="status" aria-label="Loading" className={cn("spinner", className)} style={{ width: size, height: size }} />;
}

/** Big spinner in the middle of the screen, for a page that is still loading. */
export function PageSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="page-spinner" role="status" aria-live="polite">
      <Spinner size={44} className="spinner-lg" />
      <span>{label}</span>
    </div>
  );
}

/** Same spinner, centred over whatever page is showing, while data is being read (after half a second, so quick loads stay quiet). */
export function LoadingOverlay() {
  const reading = useActiveReads();
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setShow(reading > 0), reading > 0 ? 500 : 150);
    return () => window.clearTimeout(t);
  }, [reading]);
  if (!show) return null;
  return (
    <div className="loading-overlay">
      <Spinner size={44} className="spinner-lg" />
    </div>
  );
}

/**
 * The one button. While `loading` - or while an async `onClick` is still running - it shows a spinner, ignores further clicks
 * and says so to assistive tech, so nobody double-submits and there is always a reaction to a click.
 */
export const ActionButton = forwardRef<HTMLButtonElement, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & { tone?: ActionTone; size?: "default" | "sm"; loading?: boolean; onClick?: (e: MouseEvent<HTMLButtonElement>) => unknown }>(function ActionButton(
  { tone = "primary", size = "default", type = "button", className, loading = false, onClick, disabled, children, ...props },
  ref,
) {
  const [pending, setPending] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const busy = loading || pending;
  const handle = (e: MouseEvent<HTMLButtonElement>) => {
    if (busy) return e.preventDefault();
    const result = onClick?.(e);
    if (result && typeof (result as Promise<unknown>).then === "function") {
      setPending(true);
      const done = () => mounted.current && setPending(false);
      (result as Promise<unknown>).then(done, done);
    }
  };
  return (
    <button
      ref={ref}
      type={type}
      className={cn("action-btn", ACTION_TONE[tone], size === "sm" && "action-btn-sm", busy && "action-btn-loading", className)}
      disabled={disabled}
      aria-busy={busy || undefined}
      // `aria-disabled` rather than `disabled` while busy keeps focus (and the layout) where the user left it.
      aria-disabled={busy || undefined}
      onClick={handle}
      {...props}
    >
      {busy && <Spinner size={size === "sm" ? 11 : 14} />}
      {children}
    </button>
  );
});

/** Thin bar across the top of the window while any request is in flight (shown only if it takes more than a blink). */
export function TopProgress() {
  const active = useActiveRequests();
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (active === 0) {
      const t = window.setTimeout(() => setShow(false), 200);
      return () => window.clearTimeout(t);
    }
    const t = window.setTimeout(() => setShow(true), 150);
    return () => window.clearTimeout(t);
  }, [active]);
  if (!show) return null;
  return (
    <div className="top-progress" role="progressbar" aria-label="Loading" aria-busy>
      <div className="top-progress-bar" />
    </div>
  );
}

export function Panel({
  children,
  title,
  subtitle,
  aside,
  className,
}: {
  children?: ReactNode;
  title?: string;
  subtitle?: ReactNode;
  aside?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel", className)}>
      {title !== undefined && (
        <header className="panel-header">
          <div className="min-w-0">
            <h2 className="panel-header-title">{title}</h2>
            {subtitle ? <p className="panel-header-subtitle">{subtitle}</p> : null}
          </div>
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, delta, hint, tone = "muted", loading = false }: { label: string; value: ReactNode; delta?: ReactNode; hint?: ReactNode; tone?: Tone; loading?: boolean }) {
  return (
    <div className="panel stat-card">
      <p className="stat-card-label">{label}</p>
      {loading ? <div className="mt-1 h-5 w-24 animate-pulse rounded bg-[var(--muted)]" /> : <p className="stat-card-value numeric">{value}</p>}
      {(delta !== undefined || hint !== undefined) && (
        <div className="mt-1 flex items-center gap-2">
          {delta !== undefined && <Pill tone={tone}>{delta}</Pill>}
          {hint !== undefined && <span className="stat-card-hint">{hint}</span>}
        </div>
      )}
    </div>
  );
}

// ---- tables ----------------------------------------------------------------------

/** `fit` sizes the table to its content and scrolls sideways instead of wrapping cells (the old native-table look). */
export function DataTable({ columns, children, minWidth = 720, fit = false }: { columns: ReactNode[]; children: ReactNode; minWidth?: number; fit?: boolean }) {
  return (
    <div className="data-table-wrap">
      <table className={cn("data-table", fit && "data-table-fit")} style={fit ? undefined : { minWidth }}>
        <thead>
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
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function TableRow({ cells, onClick, selected = false }: { cells: ReactNode[]; onClick?: () => void; selected?: boolean }) {
  return (
    <tr className={selected ? "selected" : onClick ? "clickable" : undefined} onClick={onClick}>
      {cells.map((c, i) => (
        <td key={i}>{c}</td>
      ))}
    </tr>
  );
}

export interface PageMeta {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export function Pagination({ meta, onPage }: { meta: PageMeta | undefined; onPage: (page: number) => void }) {
  if (!meta || meta.pages <= 1) return null;
  return (
    <div className="pagination-bar">
      <span className="numeric">
        {(meta.page - 1) * meta.limit + 1}–{Math.min(meta.page * meta.limit, meta.total)} of {meta.total}
      </span>
      <div className="flex gap-1.5">
        <ActionButton tone="ghost" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>
          Previous
        </ActionButton>
        <ActionButton tone="ghost" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>
          Next
        </ActionButton>
      </div>
    </div>
  );
}

/** Renders only above the lg breakpoint - pair with MobileOnly for the stacked-card counterpart (plain @media in theme.css). */
export function DesktopOnly({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("desktop-only", className)}>{children}</div>;
}

export function MobileOnly({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mobile-only", className)}>{children}</div>;
}

export function MobileRecordCard({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mobile-record-card">
      <div className="mobile-record-card-rows">{children}</div>
      {actions ? <div className="mobile-record-card-actions">{actions}</div> : null}
    </div>
  );
}

export function MobileRecordRow({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="mobile-record-row">
      <span className="mobile-record-label">{label}</span>
      <span className="mobile-record-value">{value}</span>
    </div>
  );
}

// ---- filter controls ---------------------------------------------------------------

export function SearchInput({ value, onChange, placeholder = "Search…", id: explicitId }: { value: string; onChange: (v: string) => void; placeholder?: string; id?: string }) {
  const generatedId = useId();
  const inputId = explicitId || generatedId;
  return (
    <>
      <label htmlFor={inputId} className="sr-only">{placeholder}</label>
      <input id={inputId} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="search-input" />
    </>
  );
}

export interface Option {
  value: string;
  label: string;
}

export function FilterSelect({
  value,
  onChange,
  options,
  label,
  showLabel = false,
  id: explicitId,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  label: string;
  showLabel?: boolean;
  id?: string;
  className?: string;
}) {
  const generatedId = useId();
  const selectId = explicitId || generatedId;

  const selectNode = (
    <select
      id={selectId}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn("filter-select", className)}
      aria-label={label}
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );

  if (!showLabel) {
    return (
      <>
        <label htmlFor={selectId} className="sr-only">{label}</label>
        {selectNode}
      </>
    );
  }

  return (
    <div className="filter-group">
      <label htmlFor={selectId} className="filter-group-label">
        {label}:
      </label>
      {selectNode}
    </div>
  );
}

// ---- dialog ------------------------------------------------------------------------

/** Radix Dialog with the app's modal recipe; full-screen takeover below lg (see theme.css). */
export function Modal({
  open,
  onClose,
  title,
  description,
  footer,
  wide = false,
  maxWidth,
  descriptionSize = "1",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  maxWidth?: string;
  /** Reflex used `rx.text` size 1 (12px gray) for most dialog captions, size 2 for a few, and the Radix Description (16px) in configuration and factory dialogs. */
  descriptionSize?: "1" | "2" | "radix";
  children?: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className={cn("dialog-content", wide && "dialog-content-wide")} style={maxWidth ? { maxWidth } : undefined}>
          <header className="modal-header">
            <div>
              <Dialog.Title className="modal-title">{title}</Dialog.Title>
              {description ? <Dialog.Description className={cn("modal-description", `modal-description-${descriptionSize}`)}>{description}</Dialog.Description> : null}
            </div>
            <Dialog.Close className="modal-close" aria-label="Close">
              <X size={16} />
            </Dialog.Close>
          </header>
          <div className="modal-body">{children}</div>
          {footer ? <footer className="modal-footer">{footer}</footer> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---- form primitives -----------------------------------------------------------------

export function Field({
  label,
  children,
  hint,
  error,
  required = false,
  htmlFor,
}: {
  label: string;
  children: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  htmlFor?: string;
}) {
  const generatedId = useId();
  const childId = isValidElement(children) && (children.props as any)?.id ? (children.props as any).id : undefined;
  const fieldId = htmlFor || childId || generatedId;
  const errorId = error ? `${fieldId}-error` : undefined;

  const renderedChild = isValidElement(children)
    ? cloneElement(children as ReactElement<any>, {
        id: (children.props as any)?.id || fieldId,
        ...(error
          ? {
              "aria-describedby": errorId,
              "aria-invalid": true,
            }
          : {}),
      })
    : children;

  return (
    <div>
      <label htmlFor={fieldId} className="flex items-baseline justify-between gap-2">
        <span className="field-label">
          {label}
          {required ? <span className="field-required">*</span> : null}
        </span>
        {hint ? <span className="field-hint">{hint}</span> : null}
      </label>
      <div>{renderedChild}</div>
      {error ? (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextInput({ className, ...props }, ref) {
  // size=17 gives the ~150px intrinsic width of a Radix TextField (matters where the input sizes a shrink-wrapped panel).
  return <input ref={ref} size={17} className={cn("ui-input", className)} {...props} />;
});

export const NumberInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function NumberInput({ className, ...props }, ref) {
  return <input ref={ref} inputMode="decimal" className={cn("ui-input numeric", className)} {...props} />;
});

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextArea({ className, rows = 2, ...props }, ref) {
  return <textarea ref={ref} rows={rows} className={cn("ui-textarea", className)} {...props} />;
});

export function SelectInput({ options, placeholder, className, "aria-label": ariaLabel, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { options: Option[]; placeholder?: string }) {
  const fallbackLabel = ariaLabel || placeholder || (options[0]?.label ? `${options[0].label} selector` : "Selection");
  return (
    <select className={cn("ui-select", className)} aria-label={fallbackLabel} {...props}>
      {placeholder ? <option value="" data-placeholder>{placeholder}</option> : null}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

// ---- notes / errors / empty states ------------------------------------------------------

export function InfoTooltip({ content, label }: { content: string; label?: string }) {
  return (
    <span className="relative inline-flex items-center group cursor-help ml-1 align-middle">
      <button
        type="button"
        aria-label={label || `Info: ${content}`}
        className="inline-flex items-center justify-center p-0.5 rounded text-[var(--muted-foreground)] hover:text-[var(--foreground)] focus:outline-hidden"
      >
        <Info size={13} className="shrink-0" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:flex group-focus-within:flex z-50 w-max max-w-xs rounded-md bg-[var(--popover)] text-[var(--popover-foreground)] px-2.5 py-1.5 text-xs shadow-md border border-[var(--border)] leading-normal text-left font-normal"
      >
        {content}
      </span>
    </span>
  );
}

export function Note({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" }) {
  return (
    <div className={cn("note", tone === "info" ? "note-info" : "note-warning")}>
      <Info size={17} className="mt-0.5 shrink-0 opacity-70" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function InlineError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <div className="inline-error" role="alert">
      <TriangleAlert size={17} className="mt-0.5 shrink-0" />
      <p>{message}</p>
    </div>
  );
}

export function EmptyState({ title, hint, description }: { title: string; hint?: string; description?: string }) {
  const subtext = hint || description;
  return (
    <div className="empty-state">
      <Inbox size={28} className="opacity-40" />
      <p className="empty-state-title">{title}</p>
      {subtext ? <p className="empty-state-hint">{subtext}</p> : null}
    </div>
  );
}

export function RecordNotFound({ entity, id, backUrl, backLabel }: { entity: string; id?: string; backUrl: string; backLabel?: string }) {
  return (
    <div className="flex w-full flex-col items-center justify-center gap-3 py-16 text-center">
      <TriangleAlert size={36} className="text-[var(--destructive)] opacity-80" />
      <h1 className="text-xl font-bold">{entity} not found</h1>
      <p className="max-w-md text-sm text-[var(--muted-foreground)]">
        {id ? `No ${entity.toLowerCase()} exists with identifier "${id}", or it may have been deleted or archived.` : `The requested ${entity.toLowerCase()} could not be found.`}
      </p>
      <Link to={backUrl} className="mt-2">
        <ActionButton size="sm">{backLabel || `← Back to ${entity.toLowerCase()} list`}</ActionButton>
      </Link>
    </div>
  );
}

/**
 * Rendered wherever a page's own permission gate fails. That gate also goes
 * false when the session quietly expired mid-visit, so the two are told apart:
 * an expired session offers the one action that fixes it (sign in again),
 * instead of sending people to ask an admin for a permission they already have.
 */
export function Forbidden({ permission }: { permission: string }) {
  const { status } = useAuth();
  if (status === "authenticated") {
    return (
      <div className="panel forbidden-panel">
        <ShieldAlert size={28} className="mx-auto opacity-40" />
        <p className="mt-2 text-sm font-medium">You do not have access to this module</p>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          It needs the <code className="numeric rounded bg-[var(--muted)] px-1 py-0.5">{permission}</code> permission. Ask an administrator to add it to your role.
        </p>
      </div>
    );
  }
  return (
    <div className="panel forbidden-panel">
      <Clock size={28} className="mx-auto opacity-40" />
      <p className="mt-2 text-sm font-medium">Your session has expired</p>
      <p className="mt-1 text-xs text-[var(--muted-foreground)]">For your security, you've been signed out after a period of inactivity.</p>
      <div className="mt-3">
        <Link to="/login" className="action-btn action-btn-primary">
          Sign in again
        </Link>
      </div>
    </div>
  );
}


/** Segmented toggle (Count / Cost style). */
export function Segmented({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: Option[] }) {
  return (
    <div className="segmented" role="group">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export { VirtualDataTable, type VirtualDataTableProps } from "@/components/erp/virtual-table";
