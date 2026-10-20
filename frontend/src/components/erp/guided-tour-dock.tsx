import { useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Boxes,
  Building,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Compass,
  ExternalLink,
  Eye,
  Factory,
  GripHorizontal,
  Layers,
  LayoutDashboard,
  LineChart,
  Maximize2,
  Minimize2,
  Package,
  Receipt,
  RotateCcw,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Sparkles,
  Truck,
  Warehouse,
  X,
  type LucideIcon,
} from "lucide-react";
import { useDemoTour } from "@/lib/demo-flow-context";
import {
  ERP_JOURNEYS,
} from "@/lib/demo-flow-data";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  Boxes,
  Building,
  Building2,
  LineChart,
  SlidersHorizontal,
  ShoppingCart,
  Truck,
  Warehouse,
  ShieldCheck,
  Layers,
  Factory,
  ClipboardList: Package,
  Package,
  Receipt,
  RotateCcw,
  LayoutDashboard,
  Compass,
};

export function GuidedTourDock() {
  const {
    isTourActive,
    isDockMinimized,
    endTour,
    toggleMinimize,
    // Journey API
    activeJourneyId,
    activeJourney,
    currentJourneyStepIndex,
    activeJourneyStep,
    totalJourneySteps,
    nextJourneyStep,
    prevJourneyStep,
    switchJourney,
    activeStep,
  } = useDemoTour();

  const location = useLocation();
  const navigate = useNavigate();
  const autoNavigate = true;
  const [showJourneySwitcher, setShowJourneySwitcher] = useState<boolean>(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dockRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{
    pointerStartX: number;
    pointerStartY: number;
    boxStartX: number;
    boxStartY: number;
    boxWidth: number;
    boxHeight: number;
  } | null>(null);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (target.closest("button, a, input, select, textarea, [role='button']")) {
      return;
    }
    if (!dockRef.current) return;

    const rect = dockRef.current.getBoundingClientRect();
    dragStartRef.current = {
      pointerStartX: e.clientX,
      pointerStartY: e.clientY,
      boxStartX: rect.left,
      boxStartY: rect.top,
      boxWidth: rect.width,
      boxHeight: rect.height,
    };
    setIsDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStartRef.current) return;
    const { pointerStartX, pointerStartY, boxStartX, boxStartY, boxWidth, boxHeight } = dragStartRef.current;
    const dx = e.clientX - pointerStartX;
    const dy = e.clientY - pointerStartY;

    const minX = 8;
    const maxX = Math.max(8, window.innerWidth - boxWidth - 8);
    const minY = 8;
    const maxY = Math.max(8, window.innerHeight - boxHeight - 8);

    const newX = Math.min(Math.max(boxStartX + dx, minX), maxX);
    const newY = Math.min(Math.max(boxStartY + dy, minY), maxY);

    setPosition({ x: newX, y: newY });
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDragging) {
      setIsDragging(false);
      dragStartRef.current = null;
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    }
  };

  if (!isTourActive) return null;

  // Use Journey step by default, fallback to legacy
  const currentRoute = activeJourneyStep?.route || activeStep.route;
  const isOnCurrentScreen = location.pathname === currentRoute;
  const StepIcon = ICONS[activeJourney?.iconName || activeStep.iconName] || Compass;

  const handleNext = () => {
    nextJourneyStep(autoNavigate);
  };

  const handlePrev = () => {
    prevJourneyStep(autoNavigate);
  };

  // Minimized view: sleek floating pill at bottom right
  if (isDockMinimized) {
    return (
      <div className="fixed bottom-5 right-5 z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
        <div className="flex items-center gap-2 rounded-full border border-teal-500/40 bg-[var(--card)]/95 px-3.5 py-2 shadow-xl backdrop-blur-md">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-500/20 text-teal-600 dark:text-teal-300">
            <Sparkles size={13} className="animate-pulse" />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--foreground)]">
              <span className="text-teal-700 dark:text-teal-300 font-bold">
                {activeJourney.shortTitle}:
              </span>
              <span>
                Step {currentJourneyStepIndex + 1}/{totalJourneySteps}
              </span>
              <span className="text-[11px] text-[var(--muted-foreground)] font-medium truncate max-w-[120px]">
                {activeJourneyStep?.shortTitle}
              </span>
            </div>
          </div>
          <div className="ml-1 flex items-center gap-1">
            <button
              type="button"
              onClick={toggleMinimize}
              className="rounded-full p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              title="Expand tour guide"
              aria-label="Expand tour guide"
            >
              <Maximize2 size={13} />
            </button>
            <button
              type="button"
              onClick={endTour}
              className="rounded-full p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--destructive)]"
              title="End tour"
              aria-label="End tour"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={dockRef}
      className={cn(
        "fixed z-50 w-[96%] max-w-2xl transition-shadow",
        position === null && "bottom-4 left-1/2 -translate-x-1/2 animate-in fade-in slide-in-from-bottom-4 duration-300",
        isDragging ? "shadow-2xl ring-2 ring-teal-500 cursor-grabbing opacity-95 select-none" : "shadow-2xl"
      )}
      style={
        position !== null
          ? {
              left: `${position.x}px`,
              top: `${position.y}px`,
              bottom: "auto",
              transform: "none",
            }
          : undefined
      }
    >
      <div className="overflow-hidden rounded-2xl border border-teal-500/40 bg-[var(--card)]/98 backdrop-blur-md">
        {/* Progress bar across top */}
        <div className="h-1.5 w-full bg-[var(--muted)]">
          <div
            className="h-full bg-gradient-to-r from-teal-500 via-indigo-500 to-amber-500 transition-all duration-300"
            style={{ width: `${((currentJourneyStepIndex + 1) / totalJourneySteps) * 100}%` }}
          />
        </div>

        {/* Header Bar - Draggable Handle */}
        <div
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onDoubleClick={() => setPosition(null)}
          className={cn(
            "flex items-center justify-between border-b border-[var(--border)] px-3.5 py-2 bg-[var(--muted)]/40 cursor-grab select-none transition-colors",
            isDragging && "cursor-grabbing bg-teal-500/10"
          )}
          title="Click and drag to move dialog anywhere on the screen (Double-click to reset position)"
        >
          <div className="flex items-center gap-2 min-w-0">
            {/* Visual Drag Grip Handle */}
            <div
              className="flex items-center text-[var(--muted-foreground)] hover:text-teal-600 dark:hover:text-teal-400 cursor-grab active:cursor-grabbing p-0.5"
              title="Click and drag to move dialog"
            >
              <GripHorizontal size={14} className="opacity-70" />
            </div>

            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-teal-500/15 text-teal-700 dark:text-teal-300">
              <StepIcon size={16} />
            </div>

            {/* Journey selector popover button */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowJourneySwitcher((prev) => !prev)}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-0.5 text-xs font-bold text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
                title="Click to switch between 6 Core Business Journeys"
              >
                <span className="truncate max-w-[160px] sm:max-w-none">{activeJourney.title}</span>
                <ChevronDown size={12} className="text-[var(--muted-foreground)]" />
              </button>

              {/* Journey Switcher Menu */}
              {showJourneySwitcher && (
                <div className="absolute left-0 top-full mt-1.5 z-50 w-72 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1.5 shadow-xl animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Switch Core Journey
                  </div>
                  <div className="space-y-1">
                    {ERP_JOURNEYS.map((j) => (
                      <button
                        key={j.id}
                        type="button"
                        onClick={() => {
                          switchJourney(j.id, autoNavigate);
                          setShowJourneySwitcher(false);
                        }}
                        className={cn(
                          "w-full text-left rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all flex items-center justify-between",
                          j.id === activeJourneyId
                            ? "bg-teal-500/15 text-teal-900 dark:text-teal-100 font-bold border border-teal-500/30"
                            : "hover:bg-[var(--muted)] text-[var(--foreground)]"
                        )}
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="truncate">{j.title}</span>
                        </div>
                        <span className="text-[10px] text-[var(--muted-foreground)] shrink-0 ml-1">
                          {j.steps.length} steps
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <span className="text-[11px] font-bold text-teal-700 dark:text-teal-300 bg-teal-500/10 px-1.5 py-0.5 rounded border border-teal-500/20 shrink-0">
              Step {currentJourneyStepIndex + 1}/{totalJourneySteps}
            </span>
          </div>

          {/* Quick controls */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => navigate("/demo-flow")}
              className="text-[11px] font-medium text-teal-700 dark:text-teal-300 hover:underline px-2 py-0.5 rounded flex items-center gap-1"
              title="Open full demo & journey center"
            >
              <span>Journey Hub</span>
              <ExternalLink size={11} />
            </button>
            {position !== null && (
              <button
                type="button"
                onClick={() => setPosition(null)}
                className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-teal-600 dark:hover:text-teal-400"
                title="Reset position to bottom center"
                aria-label="Reset position to bottom center"
              >
                <RotateCcw size={13} />
              </button>
            )}
            <button
              type="button"
              onClick={toggleMinimize}
              className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              title="Minimize guide dock"
              aria-label="Minimize guide dock"
            >
              <Minimize2 size={14} />
            </button>
            <button
              type="button"
              onClick={endTour}
              className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--destructive)]"
              title="Exit guided tour"
              aria-label="Exit guided tour"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Current Step Content */}
        <div className="p-3.5 space-y-2.5">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-bold text-[var(--foreground)]">
                  {activeJourneyStep?.title}
                </h4>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]">
                  {activeJourneyStep?.navGroup} ➔ {activeJourneyStep?.route}
                </span>
              </div>
              <p className="text-xs text-[var(--muted-foreground)] mt-1 leading-relaxed">
                {activeJourneyStep?.description}
              </p>
            </div>
          </div>

          {/* Key Takeaway Collapsible */}
          <div className="pt-0.5">
            <button
              type="button"
              onClick={() => setShowTechnicalDetails((prev) => !prev)}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--muted-foreground)] hover:text-teal-700 dark:hover:text-teal-300 transition-colors"
            >
              {showTechnicalDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              <span>{showTechnicalDetails ? "Hide" : "Show"} Business Context & Key Takeaway</span>
            </button>

            {showTechnicalDetails && (
              <div className="mt-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] p-2 text-[11px] text-[var(--muted-foreground)] animate-in fade-in duration-150">
                <span className="font-semibold text-[var(--foreground)]">Why this matters: </span>
                {activeJourneyStep?.keyTakeaway}
              </div>
            )}
          </div>
        </div>

        {/* Footer Navigation Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] px-4 py-2.5 bg-[var(--muted)]/25 text-xs">
          <div className="flex items-center gap-2">
            {!isOnCurrentScreen ? (
              <button
                type="button"
                onClick={() => navigate(currentRoute)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300 hover:underline bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/25 transition-colors"
                title={`Navigate to ${currentRoute}`}
              >
                <Eye size={13} />
                <span>Jump to Screen ({currentRoute})</span>
              </button>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                <CheckCircle2 size={13} />
                <span>On Live Screen ({currentRoute})</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={currentJourneyStepIndex === 0}
              onClick={handlePrev}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs sm:text-sm font-semibold text-[var(--foreground)] disabled:opacity-35 hover:bg-[var(--muted)] transition-all shadow-2xs"
            >
              <ArrowLeft size={14} />
              <span>Back</span>
            </button>

            <button
              type="button"
              onClick={handleNext}
              className="inline-flex items-center gap-2 rounded-xl bg-teal-600 hover:bg-teal-700 active:scale-[0.98] text-white px-4 py-2 sm:px-5 sm:py-2.5 text-xs sm:text-sm font-bold shadow-md hover:shadow-lg transition-all ring-1 ring-teal-400/30"
            >
              <span>
                {currentJourneyStepIndex < totalJourneySteps - 1
                  ? `Next: ${activeJourney.steps[currentJourneyStepIndex + 1]?.shortTitle}`
                  : "Complete Journey ✓"}
              </span>
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

