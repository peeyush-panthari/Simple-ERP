import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Compass,
  Factory,
  LineChart,
  Play,
  RotateCcw,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Warehouse,
  type LucideIcon,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import { useDemoTour } from "@/lib/demo-flow-context";
import { ERP_JOURNEYS, type ERPJourney } from "@/lib/demo-flow-data";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  ShieldCheck,
  LineChart,
  ShoppingCart,
  Factory,
  Truck,
  Warehouse,
  Compass,
};

export default function DemoFlowPage() {
  const {
    startJourney,
    resetJourneyProgress,
    completedJourneySteps,
    isTourActive,
    activeJourneyId,
    endTour,
  } = useDemoTour();

  const handleStartTour = (journeyId: string) => {
    startJourney(journeyId, 0, true);
  };

  const handleResetTour = (journeyId: string) => {
    resetJourneyProgress(journeyId);
    if (activeJourneyId === journeyId) {
      endTour();
    }
  };

  const handleResetAll = () => {
    resetJourneyProgress();
    endTour();
  };

  return (
    <Shell>
      <div className="space-y-2 pb-2 max-w-7xl mx-auto">
        {/* Compact Header with reduced whitespace and no eyebrow */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[var(--border)] pb-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-500/15 text-teal-700 dark:text-teal-300 shrink-0">
                <Compass size={16} />
              </div>
              <h1 className="text-base sm:text-lg font-bold text-[var(--foreground)] tracking-tight">
                System Demo Flows
              </h1>
            </div>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Interactive, step-by-step guided tours walking through end-to-end ERP workflows directly on live screens.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleResetAll}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              title="Reset progress across all tours"
            >
              <RotateCcw size={12} />
              <span>Reset All Tours</span>
            </button>
          </div>
        </div>

        {/* 6 Flows stretched wide: 3 rows on the left, action buttons on the right */}
        <div className="flex flex-col gap-2">
          {ERP_JOURNEYS.map((journey: ERPJourney) => {
            const Icon = ICONS[journey.iconName] || Compass;
            const completedSteps = completedJourneySteps[journey.id] || [];
            const totalSteps = journey.steps.length;
            const isCompleted = completedSteps.length >= totalSteps && totalSteps > 0;
            const isInProgress = completedSteps.length > 0 && !isCompleted;
            const isCurrentActive = isTourActive && activeJourneyId === journey.id;

            return (
              <div
                key={journey.id}
                className={cn(
                  "flex flex-col lg:flex-row lg:items-center justify-between gap-3 rounded-xl border bg-[var(--card)] px-3.5 py-2.5 transition-all shadow-xs",
                  isCurrentActive
                    ? "border-teal-500 ring-1 ring-teal-500/30 bg-teal-500/[0.02]"
                    : "border-[var(--border)] hover:border-[var(--border-strong,var(--border))]"
                )}
              >
                {/* Left Side: 3 Rows */}
                <div className="flex-1 min-w-0 space-y-1">
                  {/* Row-1: Name of flow with step counter and badges in front of it */}
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-teal-500/10 text-teal-700 dark:text-teal-300">
                      <Icon size={14} />
                    </div>
                    <h3 className="text-sm font-semibold text-[var(--foreground)] truncate">
                      {journey.title}
                    </h3>

                    {journey.recommendedStart && (
                      <span className="rounded bg-teal-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-teal-700 dark:text-teal-300 border border-teal-500/20 shrink-0">
                        Start Here
                      </span>
                    )}

                    <span className="text-xs text-[var(--muted-foreground)] shrink-0">
                      • {journey.persona}
                    </span>

                    <span className="inline-flex items-center gap-1 text-[11px] text-[var(--muted-foreground)] shrink-0">
                      <Clock size={11} />
                      <span>~{journey.estimatedMinutes}m ({totalSteps} steps)</span>
                    </span>

                    {/* Status Pill */}
                    <div className="shrink-0 ml-auto lg:ml-2">
                      {isCurrentActive ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span>Active Now</span>
                        </span>
                      ) : isCompleted ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-teal-500/15 px-2 py-0.5 text-[10px] font-semibold text-teal-700 dark:text-teal-300 border border-teal-500/30">
                          <CheckCircle2 size={11} />
                          <span>Completed</span>
                        </span>
                      ) : isInProgress ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-300 border border-amber-500/30">
                          <span>{completedSteps.length}/{totalSteps} Steps</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--muted)] px-2 py-0.5 text-[10px] font-medium text-[var(--muted-foreground)] border border-[var(--border)]">
                          <span>Not Started</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Row-2: Greyedout detailed written */}
                  <p
                    className="text-xs text-[var(--muted-foreground)] truncate"
                    title={journey.tagline || journey.description}
                  >
                    {journey.tagline || journey.description}
                  </p>

                  {/* Row-3: Step flow */}
                  <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 scrollbar-none">
                    <span className="text-[11px] font-medium text-[var(--muted-foreground)] shrink-0">
                      Flow:
                    </span>
                    {journey.steps.map((step, idx) => {
                      const isStepDone = completedSteps.includes(step.id);
                      return (
                        <div key={step.id} className="flex items-center gap-1.5 shrink-0">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors",
                              isStepDone
                                ? "bg-teal-500/15 text-teal-800 dark:text-teal-200 border border-teal-500/30"
                                : "bg-[var(--muted)]/60 text-[var(--foreground)] border border-[var(--border)]"
                            )}
                            title={`${step.title} (${step.route})`}
                          >
                            {isStepDone ? (
                              <CheckCircle2 size={11} className="text-teal-600 dark:text-teal-400 shrink-0" />
                            ) : (
                              <span className="text-[10px] text-[var(--muted-foreground)] font-mono shrink-0">
                                {idx + 1}
                              </span>
                            )}
                            <span>{step.shortTitle}</span>
                          </span>
                          {idx < journey.steps.length - 1 && (
                            <ArrowRight size={10} className="text-[var(--muted-foreground)]/50 shrink-0" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right Side: Reset Tour and Resume/Start Tour buttons in front of all 3 rows */}
                <div className="flex items-center gap-2 shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => handleResetTour(journey.id)}
                    disabled={completedSteps.length === 0 && !isCurrentActive}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] disabled:opacity-40 disabled:pointer-events-none transition-colors"
                  >
                    <RotateCcw size={12} />
                    <span>Reset Tour</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleStartTour(journey.id)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors"
                  >
                    <Play size={12} className="fill-current" />
                    <span>{isCurrentActive ? "Continue Tour" : isInProgress ? "Resume Tour" : "Start Tour"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Shell>
  );
}
