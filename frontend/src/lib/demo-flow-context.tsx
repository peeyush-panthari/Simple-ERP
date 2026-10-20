import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  DEMO_FLOW_STEPS,
  ERP_JOURNEYS,
  type DemoFlowStep,
  type ERPJourney,
  type ERPJourneyStep,
} from "./demo-flow-data";

export interface DemoFlowContextType {
  // Global tour active state
  isTourActive: boolean;
  isDockMinimized: boolean;
  toggleMinimize: () => void;
  endTour: () => void;

  // Active Journey state
  activeJourneyId: string;
  activeJourney: ERPJourney;
  currentJourneyStepIndex: number;
  activeJourneyStep: ERPJourneyStep;
  totalJourneySteps: number;
  completedJourneySteps: Record<string, string[]>;
  startJourney: (journeyId?: string, stepIndex?: number, autoNavigate?: boolean) => void;
  nextJourneyStep: (autoNavigate?: boolean) => void;
  prevJourneyStep: (autoNavigate?: boolean) => void;
  goToJourneyStep: (index: number, autoNavigate?: boolean) => void;
  switchJourney: (journeyId: string, autoNavigate?: boolean) => void;
  resetJourneyProgress: (journeyId?: string) => void;

  // Backwards-compatibility for 19-module stepper & tests
  currentStepIndex: number;
  activeStep: DemoFlowStep;
  completedStepIds: string[];
  totalSteps: number;
  progressPercentage: number;
  startTour: (stepIndex?: number) => void;
  nextStep: (autoNavigate?: boolean) => void;
  prevStep: (autoNavigate?: boolean) => void;
  goToStep: (index: number, autoNavigate?: boolean) => void;
  markStepCompleted: (stepId: string) => void;
  resetProgress: () => void;
}

const DemoFlowContext = createContext<DemoFlowContextType | null>(null);

const STORAGE_KEY_COMPLETED = "simple_erp_demo_flow_completed";
const STORAGE_KEY_ACTIVE = "simple_erp_demo_tour_active";
const STORAGE_KEY_CURRENT_STEP = "simple_erp_demo_tour_step";
const STORAGE_KEY_JOURNEY_ID = "simple_erp_demo_journey_id";
const STORAGE_KEY_JOURNEY_STEP = "simple_erp_demo_journey_step";
const STORAGE_KEY_JOURNEY_COMPLETED = "simple_erp_demo_journey_completed";

export function DemoFlowProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  // Load completed steps from localStorage
  const [completedStepIds, setCompletedStepIds] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_COMPLETED);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Tour active state
  const [isTourActive, setIsTourActive] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY_ACTIVE) === "true";
    } catch {
      return false;
    }
  });

  // Active Journey ID (defaults to 'administration')
  const [activeJourneyId, setActiveJourneyId] = useState<string>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_JOURNEY_ID);
      const exists = ERP_JOURNEYS.some((j) => j.id === stored);
      return exists && stored ? stored : "administration";
    } catch {
      return "administration";
    }
  });

  // Current Journey Step Index
  const [currentJourneyStepIndex, setCurrentJourneyStepIndex] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_JOURNEY_STEP);
      const parsed = stored ? parseInt(stored, 10) : 0;
      return parsed >= 0 ? parsed : 0;
    } catch {
      return 0;
    }
  });

  // Completed steps per journey
  const [completedJourneySteps, setCompletedJourneySteps] = useState<Record<string, string[]>>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_JOURNEY_COMPLETED);
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  });

  // Current step index (19-module legacy)
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_CURRENT_STEP);
      const parsed = stored ? parseInt(stored, 10) : 0;
      return parsed >= 0 && parsed < DEMO_FLOW_STEPS.length ? parsed : 0;
    } catch {
      return 0;
    }
  });

  const [isDockMinimized, setIsDockMinimized] = useState<boolean>(false);

  // Active Journey resolution
  const activeJourney = useMemo(() => {
    return ERP_JOURNEYS.find((j) => j.id === activeJourneyId) || ERP_JOURNEYS[0];
  }, [activeJourneyId]);

  const activeJourneyStep = useMemo(() => {
    const safeIdx = Math.max(0, Math.min(currentJourneyStepIndex, activeJourney.steps.length - 1));
    return activeJourney.steps[safeIdx] || activeJourney.steps[0];
  }, [activeJourney, currentJourneyStepIndex]);

  const totalJourneySteps = activeJourney.steps.length;

  const activeStep = useMemo(() => {
    return DEMO_FLOW_STEPS[currentStepIndex] || DEMO_FLOW_STEPS[0];
  }, [currentStepIndex]);

  // Sync state to storage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_COMPLETED, JSON.stringify(completedStepIds));
      localStorage.setItem(STORAGE_KEY_JOURNEY_COMPLETED, JSON.stringify(completedJourneySteps));
    } catch {
      // ignore
    }
  }, [completedStepIds, completedJourneySteps]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_ACTIVE, String(isTourActive));
      localStorage.setItem(STORAGE_KEY_CURRENT_STEP, String(currentStepIndex));
      localStorage.setItem(STORAGE_KEY_JOURNEY_ID, activeJourneyId);
      localStorage.setItem(STORAGE_KEY_JOURNEY_STEP, String(currentJourneyStepIndex));
    } catch {
      // ignore
    }
  }, [isTourActive, currentStepIndex, activeJourneyId, currentJourneyStepIndex]);

  const markStepCompleted = useCallback((stepId: string) => {
    setCompletedStepIds((prev) => {
      if (prev.includes(stepId)) return prev;
      return [...prev, stepId];
    });
  }, []);

  const markJourneyStepCompleted = useCallback((journeyId: string, stepId: string) => {
    setCompletedJourneySteps((prev) => {
      const currentList = prev[journeyId] || [];
      if (currentList.includes(stepId)) return prev;
      return {
        ...prev,
        [journeyId]: [...currentList, stepId],
      };
    });
  }, []);

  // Start specific journey
  const startJourney = useCallback(
    (journeyId = "administration", stepIndex = 0, autoNavigate = true) => {
      const targetJourney = ERP_JOURNEYS.find((j) => j.id === journeyId) || ERP_JOURNEYS[0];
      const safeIndex = Math.max(0, Math.min(stepIndex, targetJourney.steps.length - 1));

      setActiveJourneyId(targetJourney.id);
      setCurrentJourneyStepIndex(safeIndex);
      setIsTourActive(true);
      setIsDockMinimized(false);

      const targetStep = targetJourney.steps[safeIndex];
      markJourneyStepCompleted(targetJourney.id, targetStep.id);

      // Map to legacy step if available
      const legacyIdx = DEMO_FLOW_STEPS.findIndex((s) => s.route === targetStep.route);
      if (legacyIdx !== -1) {
        setCurrentStepIndex(legacyIdx);
        markStepCompleted(DEMO_FLOW_STEPS[legacyIdx].id);
      }

      if (autoNavigate && targetStep.route) {
        navigate(targetStep.route);
      }
    },
    [markJourneyStepCompleted, markStepCompleted, navigate]
  );

  const switchJourney = useCallback(
    (journeyId: string, autoNavigate = true) => {
      startJourney(journeyId, 0, autoNavigate);
    },
    [startJourney]
  );

  const nextJourneyStep = useCallback(
    (autoNavigate = true) => {
      if (currentJourneyStepIndex < activeJourney.steps.length - 1) {
        const nextIdx = currentJourneyStepIndex + 1;
        setCurrentJourneyStepIndex(nextIdx);
        const nextStepObj = activeJourney.steps[nextIdx];
        markJourneyStepCompleted(activeJourney.id, nextStepObj.id);

        const legacyIdx = DEMO_FLOW_STEPS.findIndex((s) => s.route === nextStepObj.route);
        if (legacyIdx !== -1) {
          setCurrentStepIndex(legacyIdx);
          markStepCompleted(DEMO_FLOW_STEPS[legacyIdx].id);
        }

        if (autoNavigate && nextStepObj.route) {
          navigate(nextStepObj.route);
        }
      }
    },
    [activeJourney, currentJourneyStepIndex, markJourneyStepCompleted, markStepCompleted, navigate]
  );

  const prevJourneyStep = useCallback(
    (autoNavigate = true) => {
      if (currentJourneyStepIndex > 0) {
        const prevIdx = currentJourneyStepIndex - 1;
        setCurrentJourneyStepIndex(prevIdx);
        const prevStepObj = activeJourney.steps[prevIdx];

        const legacyIdx = DEMO_FLOW_STEPS.findIndex((s) => s.route === prevStepObj.route);
        if (legacyIdx !== -1) {
          setCurrentStepIndex(legacyIdx);
        }

        if (autoNavigate && prevStepObj.route) {
          navigate(prevStepObj.route);
        }
      }
    },
    [activeJourney, currentJourneyStepIndex, navigate]
  );

  const goToJourneyStep = useCallback(
    (index: number, autoNavigate = true) => {
      const safeIndex = Math.max(0, Math.min(index, activeJourney.steps.length - 1));
      setCurrentJourneyStepIndex(safeIndex);
      const stepObj = activeJourney.steps[safeIndex];
      markJourneyStepCompleted(activeJourney.id, stepObj.id);

      const legacyIdx = DEMO_FLOW_STEPS.findIndex((s) => s.route === stepObj.route);
      if (legacyIdx !== -1) {
        setCurrentStepIndex(legacyIdx);
        markStepCompleted(DEMO_FLOW_STEPS[legacyIdx].id);
      }

      if (autoNavigate && stepObj.route) {
        navigate(stepObj.route);
      }
    },
    [activeJourney, markJourneyStepCompleted, markStepCompleted, navigate]
  );

  const resetJourneyProgress = useCallback((journeyId?: string) => {
    if (journeyId) {
      setCompletedJourneySteps((prev) => {
        const next = { ...prev };
        delete next[journeyId];
        return next;
      });
      if (activeJourneyId === journeyId) {
        setCurrentJourneyStepIndex(0);
        setIsTourActive(false);
      }
    } else {
      setCompletedJourneySteps({});
      setCurrentJourneyStepIndex(0);
      setIsTourActive(false);
    }
  }, [activeJourneyId]);

  // Backwards compatibility legacy tour methods
  const startTour = useCallback(
    (stepIndex = 0) => {
      const safeIndex = Math.max(0, Math.min(stepIndex, DEMO_FLOW_STEPS.length - 1));
      setCurrentStepIndex(safeIndex);
      setIsTourActive(true);
      setIsDockMinimized(false);
      markStepCompleted(DEMO_FLOW_STEPS[safeIndex].id);

      // Also align active journey to matching step route if possible
      const stepRoute = DEMO_FLOW_STEPS[safeIndex].route;
      const matchingJourney = ERP_JOURNEYS.find((j) => j.steps.some((s) => s.route === stepRoute));
      if (matchingJourney) {
        setActiveJourneyId(matchingJourney.id);
        const jStepIdx = matchingJourney.steps.findIndex((s) => s.route === stepRoute);
        if (jStepIdx !== -1) {
          setCurrentJourneyStepIndex(jStepIdx);
          markJourneyStepCompleted(matchingJourney.id, matchingJourney.steps[jStepIdx].id);
        }
      }
    },
    [markJourneyStepCompleted, markStepCompleted]
  );

  const endTour = useCallback(() => {
    setIsTourActive(false);
  }, []);

  const goToStep = useCallback(
    (index: number, autoNavigate = false) => {
      const safeIndex = Math.max(0, Math.min(index, DEMO_FLOW_STEPS.length - 1));
      setCurrentStepIndex(safeIndex);
      markStepCompleted(DEMO_FLOW_STEPS[safeIndex].id);
      if (autoNavigate) {
        navigate(DEMO_FLOW_STEPS[safeIndex].route);
      }
    },
    [markStepCompleted, navigate]
  );

  const nextStep = useCallback(
    (autoNavigate = false) => {
      if (currentStepIndex < DEMO_FLOW_STEPS.length - 1) {
        const nextIdx = currentStepIndex + 1;
        setCurrentStepIndex(nextIdx);
        markStepCompleted(DEMO_FLOW_STEPS[nextIdx].id);
        if (autoNavigate) {
          navigate(DEMO_FLOW_STEPS[nextIdx].route);
        }
      }
    },
    [currentStepIndex, markStepCompleted, navigate]
  );

  const prevStep = useCallback(
    (autoNavigate = false) => {
      if (currentStepIndex > 0) {
        const prevIdx = currentStepIndex - 1;
        setCurrentStepIndex(prevIdx);
        if (autoNavigate) {
          navigate(DEMO_FLOW_STEPS[prevIdx].route);
        }
      }
    },
    [currentStepIndex, navigate]
  );

  const toggleMinimize = useCallback(() => {
    setIsDockMinimized((prev) => !prev);
  }, []);

  const resetProgress = useCallback(() => {
    setCompletedStepIds([]);
    setCompletedJourneySteps({});
    setCurrentStepIndex(0);
    setCurrentJourneyStepIndex(0);
    try {
      localStorage.removeItem(STORAGE_KEY_COMPLETED);
      localStorage.removeItem(STORAGE_KEY_CURRENT_STEP);
      localStorage.removeItem(STORAGE_KEY_JOURNEY_STEP);
      localStorage.removeItem(STORAGE_KEY_JOURNEY_COMPLETED);
    } catch {
      // ignore
    }
  }, []);

  const totalSteps = DEMO_FLOW_STEPS.length;
  const progressPercentage = Math.round((completedStepIds.length / totalSteps) * 100);

  const value = useMemo(
    () => ({
      isTourActive,
      isDockMinimized,
      toggleMinimize,
      endTour,

      // Journey state
      activeJourneyId,
      activeJourney,
      currentJourneyStepIndex,
      activeJourneyStep,
      totalJourneySteps,
      completedJourneySteps,
      startJourney,
      nextJourneyStep,
      prevJourneyStep,
      goToJourneyStep,
      switchJourney,
      resetJourneyProgress,

      // Legacy support
      currentStepIndex,
      activeStep,
      completedStepIds,
      totalSteps,
      progressPercentage,
      startTour,
      nextStep,
      prevStep,
      goToStep,
      markStepCompleted,
      resetProgress,
    }),
    [
      isTourActive,
      isDockMinimized,
      toggleMinimize,
      endTour,
      activeJourneyId,
      activeJourney,
      currentJourneyStepIndex,
      activeJourneyStep,
      totalJourneySteps,
      completedJourneySteps,
      startJourney,
      nextJourneyStep,
      prevJourneyStep,
      goToJourneyStep,
      switchJourney,
      resetJourneyProgress,
      currentStepIndex,
      activeStep,
      completedStepIds,
      totalSteps,
      progressPercentage,
      startTour,
      nextStep,
      prevStep,
      goToStep,
      markStepCompleted,
      resetProgress,
    ]
  );

  return <DemoFlowContext.Provider value={value}>{children}</DemoFlowContext.Provider>;
}

export function useDemoTour(): DemoFlowContextType {
  const ctx = useContext(DemoFlowContext);
  if (!ctx) {
    throw new Error("useDemoTour must be used within a DemoFlowProvider");
  }
  return ctx;
}
