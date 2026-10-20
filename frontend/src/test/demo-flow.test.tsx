import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent, renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  DEMO_FLOW_STEPS,
  DEMO_CASE_STUDY,
  ERP_JOURNEYS,
  ENTERPRISE_PHASES,
  ENTERPRISE_STREAMS,
  PROCURE_TO_PAY_STAGES,
} from "@/lib/demo-flow-data";
import { DemoFlowProvider, useDemoTour } from "@/lib/demo-flow-context";
import { GuidedTourDock } from "@/components/erp/guided-tour-dock";
import DemoFlowPage from "@/routes/demo-flow";
import { AuthProvider } from "@/lib/auth";

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

beforeEach(() => {
  localStorage.clear();
});

describe("Demo Flow Data Integrity", () => {
  it("defines the 6 Core Self-Guided Enterprise Journeys", () => {
    expect(ERP_JOURNEYS.length).toBe(6);

    const journeyIds = ERP_JOURNEYS.map((j) => j.id);
    expect(journeyIds).toEqual([
      "administration",
      "plan-to-order",
      "procure-to-pay",
      "plan-to-production",
      "order-to-cash",
      "inventory-management",
    ]);

    // Journey 1 is Administration of ERP and is marked as recommended starting point
    const adminJourney = ERP_JOURNEYS[0];
    expect(adminJourney.id).toBe("administration");
    expect(adminJourney.recommendedStart).toBe(true);
    expect(adminJourney.steps[0].route).toBe("/users");
    expect(adminJourney.steps[0].navGroup).toBe("Administration");
    expect(adminJourney.steps[1].route).toBe("/factory-warehouse");
    expect(adminJourney.steps[2].route).toBe("/products");
    expect(adminJourney.steps[3].route).toBe("/configuration");

    // Verify all steps across all 6 journeys have complete self-guided fields
    ERP_JOURNEYS.forEach((j) => {
      expect(j.title).toBeTruthy();
      expect(j.persona).toBeTruthy();
      expect(j.steps.length).toBeGreaterThanOrEqual(4);

      j.steps.forEach((step, idx) => {
        expect(step.stepNumber).toBe(idx + 1);
        expect(step.route.startsWith("/")).toBe(true);
        expect(step.navGroup).toBeTruthy();
        expect(step.actorRole).toBeTruthy();
        expect(step.actionPrompt).toBeTruthy();
        expect(step.sampleAction.buttonText).toBeTruthy();
        expect(step.sampleAction.successMessage).toBeTruthy();
        expect(step.keyTakeaway).toBeTruthy();
      });
    });
  });

  it("defines all 19 enterprise modules with Day-0 Administration as Step 1", () => {
    expect(DEMO_FLOW_STEPS.length).toBe(19);

    // Step 1 MUST be Users & Roles in Administration
    expect(DEMO_FLOW_STEPS[0].id).toBe("users-security");
    expect(DEMO_FLOW_STEPS[0].route).toBe("/users");
    expect(DEMO_FLOW_STEPS[0].navGroup).toBe("Administration");

    // Step 2 MUST be Factory & Warehouse in Administration
    expect(DEMO_FLOW_STEPS[1].id).toBe("facilities-warehouses");
    expect(DEMO_FLOW_STEPS[1].route).toBe("/factory-warehouse");
    expect(DEMO_FLOW_STEPS[1].navGroup).toBe("Administration");

    // Step 3 MUST be Products & BOM in Administration
    expect(DEMO_FLOW_STEPS[2].id).toBe("products-bom-catalog");
    expect(DEMO_FLOW_STEPS[2].route).toBe("/products");
    expect(DEMO_FLOW_STEPS[2].navGroup).toBe("Administration");

    DEMO_FLOW_STEPS.forEach((step, idx) => {
      expect(step.stepNumber).toBe(idx + 1);
      expect(step.id).toBeTruthy();
      expect(step.title).toBeTruthy();
      expect(step.route.startsWith("/")).toBe(true);
      expect(step.navGroup).toBeTruthy();
      expect(step.workflows.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("defines complete 9-stage Procure-to-Pay (P2P) end-to-end flow", () => {
    expect(PROCURE_TO_PAY_STAGES.length).toBe(9);

    PROCURE_TO_PAY_STAGES.forEach((stage, idx) => {
      expect(stage.stageNumber).toBe(idx + 1);
      expect(stage.id).toBeTruthy();
      expect(stage.title).toBeTruthy();
      expect(stage.role).toBeTruthy();
      expect(stage.department).toBeTruthy();
      expect(stage.formFields.length).toBeGreaterThanOrEqual(1);
      expect(stage.submitButtonText).toBeTruthy();
      expect(stage.successTitle).toBeTruthy();
      expect(stage.ledgerEffect).toBeTruthy();
      expect(stage.executionLogs.length).toBeGreaterThanOrEqual(1);
    });

    const stageTitles = PROCURE_TO_PAY_STAGES.map((s) => s.shortTitle);
    expect(stageTitles).toContain("1. Raise PR");
    expect(stageTitles).toContain("2. Float RFQ");
    expect(stageTitles).toContain("3. Create PO");
    expect(stageTitles).toContain("4. Tier-2 Approval");
    expect(stageTitles).toContain("5. ASN & Gate-In");
    expect(stageTitles).toContain("6. Dock GRN & QR");
    expect(stageTitles).toContain("7. QC Lot Testing");
    expect(stageTitles).toContain("8. WMS Putaway");
    expect(stageTitles).toContain("9. 3-Way Match & Pay");
  });

  it("covers all 6 enterprise business phases", () => {
    const phasesPresent = new Set(DEMO_FLOW_STEPS.map((s) => s.phase));
    Object.keys(ENTERPRISE_PHASES).forEach((phaseKey) => {
      expect(phasesPresent.has(phaseKey as any)).toBe(true);
    });
  });

  it("covers all 6 enterprise streams across the modules", () => {
    const streamsPresent = new Set(DEMO_FLOW_STEPS.map((s) => s.stream));
    Object.keys(ENTERPRISE_STREAMS).forEach((streamKey) => {
      expect(streamsPresent.has(streamKey as any)).toBe(true);
    });
  });

  it("contains the complete 19-stage order lifecycle case study", () => {
    expect(DEMO_CASE_STUDY.stages.length).toBe(19);
    expect(DEMO_CASE_STUDY.title).toContain("SKU-MOT-500");
  });
});

describe("DemoFlowContext and Tour Stepper Logic", () => {
  it("provides initial state and progresses through 6 Journeys and 19 steps", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter>
        <DemoFlowProvider>{children}</DemoFlowProvider>
      </MemoryRouter>
    );

    const { result } = renderHook(() => useDemoTour(), { wrapper });

    expect(result.current.totalSteps).toBe(19);
    expect(result.current.activeJourneyId).toBe("administration");
    expect(result.current.activeJourney.title).toContain("Administration of ERP");
    expect(result.current.activeStep.id).toBe("users-security");

    // Start tour
    act(() => {
      result.current.startTour(0);
    });
    expect(result.current.isTourActive).toBe(true);
    expect(result.current.completedStepIds).toContain("users-security");

    // Next step progresses to facilities-warehouses
    act(() => {
      result.current.nextStep();
    });
    expect(result.current.currentStepIndex).toBe(1);
    expect(result.current.activeStep.id).toBe("facilities-warehouses");
    expect(result.current.completedStepIds).toContain("facilities-warehouses");

    // Previous step
    act(() => {
      result.current.prevStep();
    });
    expect(result.current.currentStepIndex).toBe(0);

    // Switch to Plan to Order journey
    act(() => {
      result.current.switchJourney("plan-to-order", false);
    });
    expect(result.current.activeJourneyId).toBe("plan-to-order");
    expect(result.current.activeJourneyStep.route).toBe("/forecasting");

    // Toggle minimize
    expect(result.current.isDockMinimized).toBe(false);
    act(() => {
      result.current.toggleMinimize();
    });
    expect(result.current.isDockMinimized).toBe(true);

    // End tour
    act(() => {
      result.current.endTour();
    });
    expect(result.current.isTourActive).toBe(false);

    // Reset progress
    act(() => {
      result.current.resetProgress();
    });
    expect(result.current.completedStepIds).toEqual([]);
  });
});

describe("GuidedTourDock Component", () => {
  it("does not render when tour is inactive, and renders compact clean guide when active", () => {
    const TestComponent = () => {
      const { startTour } = useDemoTour();
      return (
        <div>
          <button onClick={() => startTour(0)}>Launch Tour</button>
          <GuidedTourDock />
        </div>
      );
    };

    render(
      <MemoryRouter>
        <DemoFlowProvider>
          <TestComponent />
        </DemoFlowProvider>
      </MemoryRouter>
    );

    // When inactive, GuidedTourDock is not visible
    expect(screen.queryByText(/Step 1\//i)).toBeNull();

    // Click launch
    fireEvent.click(screen.getByText("Launch Tour"));

    // Now it renders clean, uncluttered guide starting with Administration
    expect(screen.getByText("1. Administration of ERP")).toBeDefined();
    expect(screen.getByText("Users, Roles & Site Access Governance")).toBeDefined();
    expect(screen.queryByText(/Hands-On Action on this Screen:/i)).toBeNull();
    expect(screen.getByText(/Show Business Context & Key Takeaway/i)).toBeDefined();

    // Test expanding technical details
    fireEvent.click(screen.getByText(/Show Business Context & Key Takeaway/i));
    expect(screen.getByText(/Hide Business Context & Key Takeaway/i)).toBeDefined();
    expect(screen.getByText(/Why this matters:/i)).toBeDefined();
  });
});

describe("DemoFlowPage Route", () => {
  it("renders only the 6 Flows for which we have guided tours with Start and Reset buttons", () => {
    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/demo-flow"]}>
          <AuthProvider>
            <DemoFlowProvider>
              <DemoFlowPage />
            </DemoFlowProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Verify page header
    expect(screen.getByText("System Demo Flows")).toBeDefined();
    expect(screen.getByText("Reset All Tours")).toBeDefined();

    // Verify all 6 flows are rendered
    expect(screen.getByText("1. Administration of ERP")).toBeDefined();
    expect(screen.getByText("2. Plan to Order")).toBeDefined();
    expect(screen.getByText("3. Procurement to Pay (P2P)")).toBeDefined();
    expect(screen.getByText("4. Plan to Production")).toBeDefined();
    expect(screen.getByText("5. Order to Cash (O2C)")).toBeDefined();
    expect(screen.getByText("6. Inventory Management")).toBeDefined();

    // Verify "Start Here" badge on recommended flow
    expect(screen.getByText("Start Here")).toBeDefined();

    // Verify each flow has a Start Tour button and Reset Tour button
    const startButtons = screen.getAllByRole("button", { name: /Start Tour|Resume Tour|Continue Tour/i });
    expect(startButtons.length).toBe(6);

    const resetButtons = screen.getAllByRole("button", { name: /Reset Tour/i });
    expect(resetButtons.length).toBe(6);
  });

  it("launches guided tour when Start Tour is clicked", () => {
    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/demo-flow"]}>
          <AuthProvider>
            <DemoFlowProvider>
              <DemoFlowPage />
            </DemoFlowProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const startButtons = screen.getAllByRole("button", { name: /Start Tour/i });
    expect(startButtons.length).toBeGreaterThan(0);

    // Click Start Tour on the first journey (Administration)
    fireEvent.click(startButtons[0]);

    // Tour is now active for Administration
    expect(screen.getByText("Active Now")).toBeDefined();
  });

  it("resets tour progress when Reset Tour is clicked", () => {
    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/demo-flow"]}>
          <AuthProvider>
            <DemoFlowProvider>
              <DemoFlowPage />
            </DemoFlowProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Start tour first to create progress
    const startButtons = screen.getAllByRole("button", { name: /Start Tour/i });
    fireEvent.click(startButtons[0]);

    // Active Now indicator is visible
    expect(screen.getByText("Active Now")).toBeDefined();

    // Click Reset Tour on the first journey
    const resetButtons = screen.getAllByRole("button", { name: /Reset Tour/i });
    fireEvent.click(resetButtons[0]);

    // Active Now indicator is removed
    expect(screen.queryByText("Active Now")).toBeNull();
  });
});
