import { CheckCircle2, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WalkthroughFieldItem {
  id?: string;
  key?: string;
  label: string;
  shortLabel?: string;
  stepNumber?: number;
  useCase: string;
  guideline?: string;
  guidelines?: string;
  restriction?: string;
  sampleValueText?: string;
  sampleValue?: string;
  required?: boolean;
  isFilled?: boolean;
  onFill?: () => void;
  onAutofill?: () => void;
}

export interface GuidedFieldWalkthroughProps {
  dialogTitle?: string;
  fields: WalkthroughFieldItem[];
  activeFieldId?: string;
  activeKey?: string;
  activeStepKey?: string;
  onSelectField?: (id: string) => void;
  onSelectKey?: (id: string) => void;
  onStepChange?: (id: string) => void;
  onFillAll?: () => void;
  onAutofillAll?: () => void;
  allFilled?: boolean;
  submitButtonLabel?: string;
  stepBadgeNumber?: number; // e.g. 2 for field steps
  nextStepBadgeNumber?: number; // e.g. 3 for submit button
  values?: Record<string, unknown>;
}

export function GuidedFieldWalkthrough({
  dialogTitle = "Field Guide",
  fields,
  activeFieldId,
  activeKey,
  activeStepKey,
  onSelectField,
  onSelectKey,
  onStepChange,
  onFillAll,
  onAutofillAll,
  allFilled: propAllFilled,
  submitButtonLabel = "Submit",
  stepBadgeNumber = 2,
  nextStepBadgeNumber = 3,
  values,
}: GuidedFieldWalkthroughProps) {
  const currentActiveId = activeFieldId || activeKey || activeStepKey || (fields[0]?.id || fields[0]?.key || "");
  const selectField = (id: string) => {
    onSelectField?.(id);
    onSelectKey?.(id);
    onStepChange?.(id);
  };
  const fillAll = () => {
    onFillAll?.();
    onAutofillAll?.();
  };

  const normalizedFields = fields.map((f, idx) => {
    const id = f.id || f.key || `field-${idx}`;
    const isFilled = f.isFilled !== undefined ? f.isFilled : Boolean(values ? values[id] : false);
    const sampleValueText = f.sampleValueText || f.sampleValue || "";
    const guideline = f.guideline || f.guidelines || "";
    const onFill = f.onFill || f.onAutofill || (() => {});
    return {
      ...f,
      id,
      isFilled,
      sampleValueText,
      guideline,
      onFill,
    };
  });

  const currentIndex = Math.max(
    0,
    normalizedFields.findIndex((f) => f.id === currentActiveId)
  );
  const activeField = normalizedFields[currentIndex] || normalizedFields[0];
  const allFilled = propAllFilled !== undefined ? propAllFilled : normalizedFields.every((f) => f.isFilled);

  const handleFillActive = () => {
    activeField.onFill();
    // Advance to next unfilled field or next field
    const nextUnfilled = normalizedFields.findIndex((f, idx) => idx > currentIndex && !f.isFilled);
    if (nextUnfilled !== -1) {
      selectField(normalizedFields[nextUnfilled].id);
    } else if (currentIndex < normalizedFields.length - 1) {
      selectField(normalizedFields[currentIndex + 1].id);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      selectField(normalizedFields[currentIndex - 1].id);
    }
  };

  const handleNext = () => {
    if (currentIndex < normalizedFields.length - 1) {
      selectField(normalizedFields[currentIndex + 1].id);
    }
  };

  return (
    <div className="rounded-xl border border-teal-500/40 bg-teal-500/5 p-3 space-y-2.5 text-xs text-[var(--foreground)] animate-in fade-in duration-200">
      {/* Top Bar: Step Title and Fill All shortcut */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-500/20 pb-2">
        <div className="flex items-center gap-1.5">
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-teal-500 text-[10px] font-bold text-white shadow-xs">
            {stepBadgeNumber}
          </div>
          <span className="font-bold text-teal-900 dark:text-teal-200 text-xs flex items-center gap-1">
            <Sparkles size={13} className="text-teal-600 dark:text-teal-400" />
            <span>{dialogTitle}: Field Guide ({currentIndex + 1} of {normalizedFields.length})</span>
          </span>
        </div>

        <button
          type="button"
          onClick={fillAll}
          className="text-[11px] font-semibold text-teal-700 dark:text-teal-300 hover:text-teal-800 dark:hover:text-teal-100 hover:underline inline-flex items-center gap-1 transition-colors"
        >
          <span>⚡ Autofill All Fields</span>
        </button>
      </div>

      {/* Field Pills Stepper */}
      <div className="flex items-center gap-1 overflow-x-auto pb-0.5 scrollbar-none">
        {normalizedFields.map((field, idx) => {
          const isActive = field.id === activeField.id;
          return (
            <button
              key={field.id}
              type="button"
              onClick={() => selectField(field.id)}
              className={cn(
                "shrink-0 rounded-md px-2 py-0.5 text-[10px] font-medium transition-all flex items-center gap-1 border",
                isActive
                  ? "bg-teal-600 text-white border-teal-600 font-bold shadow-xs"
                  : field.isFilled
                  ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200 border-emerald-500/30 hover:bg-emerald-500/20"
                  : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)] hover:bg-[var(--muted)]"
              )}
            >
              <span>{idx + 1}. {field.shortLabel || field.label}</span>
              {field.isFilled && <CheckCircle2 size={10} className="text-emerald-600 dark:text-emerald-400 shrink-0" />}
            </button>
          );
        })}
      </div>

      {/* Active Field Detail Card */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-2.5 space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-bold text-[11px] text-[var(--foreground)] flex items-center gap-1">
            <span className="text-teal-600 dark:text-teal-400 font-extrabold">{currentIndex + 1}.</span>
            <span>{activeField.label}</span>
          </span>

          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={currentIndex === 0}
              onClick={handlePrev}
              className="p-1 rounded text-[var(--muted-foreground)] hover:bg-[var(--muted)] disabled:opacity-30"
              title="Previous field"
            >
              <ChevronLeft size={13} />
            </button>
            <span className="text-[10px] text-[var(--muted-foreground)] font-mono">
              {currentIndex + 1}/{normalizedFields.length}
            </span>
            <button
              type="button"
              disabled={currentIndex === normalizedFields.length - 1}
              onClick={handleNext}
              className="p-1 rounded text-[var(--muted-foreground)] hover:bg-[var(--muted)] disabled:opacity-30"
              title="Next field"
            >
              <ChevronRight size={13} />
            </button>
          </div>
        </div>

        {/* Use Case & Guidelines */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] leading-relaxed">
          <div className="bg-teal-500/5 rounded p-2 border border-teal-500/15">
            <span className="font-semibold text-teal-800 dark:text-teal-300 block text-[10px] uppercase tracking-wider mb-0.5">
              📌 Enterprise Use Case:
            </span>
            <span className="text-[var(--foreground)]">{activeField.useCase}</span>
          </div>

          <div className="bg-amber-500/5 rounded p-2 border border-amber-500/15">
            <span className="font-semibold text-amber-800 dark:text-amber-300 block text-[10px] uppercase tracking-wider mb-0.5">
              ⚖️ Guidelines & Restrictions:
            </span>
            <span className="text-[var(--foreground)]">
              {activeField.guideline}
              {activeField.restriction && (
                <span className="block mt-0.5 font-medium text-amber-900 dark:text-amber-200">
                  Rule: {activeField.restriction}
                </span>
              )}
            </span>
          </div>
        </div>

        {/* Action Button for this field with Step Badge */}
        <div className="flex items-center justify-between pt-1 border-t border-[var(--border)]">
          <div className="text-[11px] text-[var(--muted-foreground)] truncate max-w-[200px]">
            <span className="font-semibold text-[var(--foreground)]">Sample: </span>
            <span className="font-mono text-teal-700 dark:text-teal-300">{activeField.sampleValueText}</span>
          </div>

          <div className="relative inline-flex">
            <span className="absolute -top-2 -right-2 flex h-4 w-4 z-10 pointer-events-none">
              <span className="relative inline-flex rounded-full h-4 w-4 bg-teal-500 text-[9px] font-bold text-white items-center justify-center shadow-xs">
                {stepBadgeNumber}
              </span>
            </span>
            <button
              type="button"
              onClick={handleFillActive}
              className="inline-flex items-center gap-1 rounded-md bg-teal-600 hover:bg-teal-700 px-2.5 py-1 text-xs font-semibold text-white shadow-xs transition-colors"
            >
              <Sparkles size={12} />
              <span>{activeField.isFilled ? "✓ Re-fill Sample" : "Fill Sample Value"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Completion prompt indicating Step 3 */}
      {allFilled && (
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-2 text-[11px] text-emerald-900 dark:text-emerald-200 flex items-center justify-between gap-2 animate-in fade-in duration-200">
          <div className="flex items-center gap-1.5 font-medium">
            <CheckCircle2 size={13} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>All fields configured! Click <strong>"{submitButtonLabel}"</strong> (Step {nextStepBadgeNumber}) below to commit.</span>
          </div>
        </div>
      )}
    </div>
  );
}
