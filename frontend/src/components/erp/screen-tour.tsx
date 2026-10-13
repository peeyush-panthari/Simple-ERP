import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, ChevronRight, ChevronLeft, X, ExternalLink, Compass } from "lucide-react";
import { ActionButton } from "./ui";

export interface TourStep {
  title: string;
  description: string;
  highlightTag?: string;
}

interface ScreenTourProps {
  screenTitle: string;
  steps: TourStep[];
  trainingModuleId?: string;
  className?: string;
}

export function ScreenTourButton({ screenTitle, steps, trainingModuleId, className = "" }: ScreenTourProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const navigate = useNavigate();

  const currentStep = steps[currentStepIndex];

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setCurrentStepIndex(0);
          setIsOpen(true);
        }}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-950 dark:bg-emerald-950/40 dark:text-emerald-100 hover:bg-emerald-100 dark:hover:bg-emerald-900/60 border border-emerald-300 dark:border-emerald-800 transition-all ${className}`}
        aria-label={`Take a 1-minute tour of ${screenTitle}`}
        title={`Take a 1-minute tour of ${screenTitle}`}
      >
        <Sparkles size={13} className="text-emerald-900 dark:text-emerald-200" />
        <span className="text-emerald-950 dark:text-emerald-100 font-semibold">1-Min Tour</span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in duration-200">
          <div 
            className="fixed inset-0" 
            onClick={() => setIsOpen(false)} 
            aria-hidden="true" 
          />

          <div 
            role="dialog"
            aria-label={`${screenTitle} Interactive Tour`}
            aria-modal="true"
            className="relative z-10 w-full max-w-lg bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-2xl shadow-2xl p-6 space-y-5 animate-in zoom-in-95 duration-200"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/10 text-teal-700 dark:text-teal-300">
                  <Compass size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--foreground)]">{screenTitle} — Interactive Tour</h2>
                  <p className="text-[11px] text-[var(--muted-foreground)]">Step {currentStepIndex + 1} of {steps.length}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close tour modal"
                className="p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              >
                <X size={18} />
              </button>
            </div>

            {/* Tour Step Body */}
            <div className="space-y-3 py-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-300">
                  {currentStep.highlightTag || "Key Operational Area"}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--muted)] text-[var(--muted-foreground)]">
                  {currentStepIndex + 1} / {steps.length}
                </span>
              </div>

              <h3 className="text-base font-bold text-[var(--foreground)]">{currentStep.title}</h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                {currentStep.description}
              </p>

              {/* Progress Bar Indicator */}
              <div className="w-full bg-[var(--muted)] h-1.5 rounded-full overflow-hidden mt-4">
                <div 
                  className="bg-teal-600 dark:bg-teal-400 h-full transition-all duration-300"
                  style={{ width: `${((currentStepIndex + 1) / steps.length) * 100}%` }}
                />
              </div>
            </div>

            {/* Modal Footer Controls */}
            <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
              {trainingModuleId ? (
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    navigate("/training");
                  }}
                  className="text-xs text-teal-700 dark:text-teal-300 hover:underline flex items-center gap-1 font-medium"
                >
                  <span>Full Training Module</span>
                  <ExternalLink size={12} />
                </button>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                {currentStepIndex > 0 && (
                  <ActionButton
                    tone="ghost"
                    size="sm"
                    onClick={() => setCurrentStepIndex((prev) => prev - 1)}
                  >
                    <ChevronLeft size={14} className="mr-1" />
                    Previous
                  </ActionButton>
                )}

                {currentStepIndex < steps.length - 1 ? (
                  <ActionButton
                    tone="primary"
                    size="sm"
                    onClick={() => setCurrentStepIndex((prev) => prev + 1)}
                  >
                    Next
                    <ChevronRight size={14} className="ml-1" />
                  </ActionButton>
                ) : (
                  <ActionButton
                    tone="primary"
                    size="sm"
                    onClick={() => setIsOpen(false)}
                  >
                    Complete Tour ✓
                  </ActionButton>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
