import React, { useState, useId } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Building,
  CheckCircle2,
  Clock,
  Flame,
  GitBranch,
  Layers,
  LineChart,
  Network,
  QrCode,
  Receipt,
  Send,
  ShieldAlert,
  Ship,
  Sparkles,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Shell } from "@/components/erp/shell";
import { ActionButton, TextInput } from "@/components/erp/ui";
import { ROADMAP_MODULES, type RoadmapModuleData } from "@/lib/roadmap-data";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  Receipt,
  Workflow,
  Layers,
  Network,
  LineChart,
  QrCode,
  Ship,
  Building,
  GitBranch,
  Boxes,
};

export function RoadmapModuleView({ moduleId }: { moduleId: string }) {
  const data = ROADMAP_MODULES[moduleId];
  const [activeTab, setActiveTab] = useState<"overview" | "workflow" | "schema" | "prototype">("overview");
  const [feedbackEmail, setFeedbackEmail] = useState("");
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [upvoted, setUpvoted] = useState(false);
  const [upvoteCount, setUpvoteCount] = useState(data?.stage === "medium_term" ? 42 : 28);
  const emailInputId = useId();
  const feedbackInputId = useId();

  if (!data) {
    return (
      <Shell>
        <div className="p-8 max-w-4xl mx-auto text-center">
          <h2 className="text-xl font-bold">Module Roadmap Not Found</h2>
          <p className="text-[var(--muted-foreground)] mt-2">The requested roadmap module was not found.</p>
          <Link to="/" className="mt-4 inline-block text-blue-600 hover:underline">Return to Control Tower</Link>
        </div>
      </Shell>
    );
  }

  const Icon = ICONS[data.iconName] || Sparkles;

  const handleUpvote = () => {
    if (!upvoted) {
      setUpvoted(true);
      setUpvoteCount((prev) => prev + 1);
    } else {
      setUpvoted(false);
      setUpvoteCount((prev) => prev - 1);
    }
  };

  const handleFeedback = (e: React.FormEvent) => {
    e.preventDefault();
    if (feedbackEmail.trim()) {
      setFeedbackSubmitted(true);
    }
  };

  return (
    <Shell>
      <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
        {/* Breadcrumb / Top Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Link to="/" className="hover:text-[var(--foreground)]">ERP</Link>
            <span>/</span>
            <span className="font-medium text-[var(--foreground)]">{data.department}</span>
            <span>/</span>
            <span className="text-[var(--foreground)] truncate">{data.title}</span>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider",
                data.stage === "medium_term"
                  ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                  : "bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"
              )}
            >
              <Clock size={13} />
              {data.stage === "medium_term" ? "Medium-Term Roadmap" : "Long-Term Roadmap"} &bull; {data.targetRelease}
            </span>

            <ActionButton
              tone={upvoted ? "primary" : "ghost"}
              size="sm"
              onClick={handleUpvote}
              className="gap-1.5"
            >
              <Flame size={14} className={upvoted ? "fill-current text-amber-500" : ""} />
              <span>{upvoted ? "Prioritized!" : "Vote for Early Delivery"}</span>
              <span className="ml-1 px-1.5 py-0.2 bg-black/10 dark:bg-white/10 rounded-full text-xs font-mono">
                {upvoteCount}
              </span>
            </ActionButton>
          </div>
        </div>

        {/* Hero Header */}
        <div className="rounded-2xl border border-[var(--border)] bg-gradient-to-br from-[var(--card)] to-[var(--muted)]/40 p-6 md:p-8 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="p-3.5 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 shrink-0">
                <Icon size={32} />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{data.title}</h1>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 font-mono">Planned</span>
                </div>
                <p className="text-[var(--muted-foreground)] text-sm md:text-base font-normal max-w-2xl">
                  {data.subtitle}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start md:self-auto">
              <button
                type="button"
                onClick={() => setActiveTab("prototype")}
                className="px-4 py-2 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium hover:opacity-90 transition flex items-center gap-2 shadow-sm"
              >
                <Sparkles size={15} />
                Try Interactive Prototype
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-[var(--border)]">
            {data.kpis.map((kpi, idx) => (
              <div key={idx} className="bg-[var(--card)]/80 backdrop-blur rounded-xl p-4 border border-[var(--border)]">
                <div className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                  {kpi.metric}
                </div>
                <div className="text-2xl font-bold text-[var(--primary)] mt-1 font-mono">
                  {kpi.target}
                </div>
                <div className="text-xs text-[var(--muted-foreground)] mt-0.5">
                  {kpi.description}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)] gap-2 overflow-x-auto">
          {[
            { id: "overview", label: "Executive Overview & Problem Statement" },
            { id: "workflow", label: "Architecture & Workflow Lifecycle" },
            { id: "schema", label: "Data Schema & Entities" },
            { id: "prototype", label: "Interactive Prototype Simulator" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium border-b-2 transition whitespace-nowrap",
                activeTab === tab.id
                  ? "border-[var(--primary)] text-[var(--primary)] font-semibold"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4">
                <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-semibold text-sm">
                  <AlertTriangle size={18} />
                  <span>The Strategic Problem Today</span>
                </div>
                <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
                  {data.strategicProblem}
                </p>
              </div>

              <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4">
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-semibold text-sm">
                  <CheckCircle2 size={18} />
                  <span>The Solution &amp; Enterprise Impact</span>
                </div>
                <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
                  {data.solutionImpact}
                </p>
              </div>
            </div>

            <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4">
              <h3 className="text-base font-semibold">Planned Feature Capabilities</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.keyCapabilities.map((cap, i) => (
                  <div key={i} className="p-4 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)] space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-sm">{cap.title}</h4>
                      <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-[var(--card)] border border-[var(--border)]">
                        {cap.tag}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                      {cap.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Early Access / Requirements Feedback Form */}
            <div className="p-6 rounded-xl border border-[var(--border)] bg-gradient-to-r from-blue-500/5 via-[var(--card)] to-purple-500/5 space-y-4">
              <div className="flex items-center gap-3">
                <Sparkles className="text-blue-500" size={20} />
                <div>
                  <h3 className="font-semibold text-sm">Have specific requirements for this module?</h3>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Share your team's workflow constraints to influence our product engineering design.
                  </p>
                </div>
              </div>

              {feedbackSubmitted ? (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm flex items-center gap-2">
                  <CheckCircle2 size={16} />
                  <span>Thank you! Your feedback has been logged with the Supply Chain Product Group.</span>
                </div>
              ) : (
                <form onSubmit={handleFeedback} className="space-y-3 pt-2">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={emailInputId} className="block text-xs font-medium text-[var(--muted-foreground)] mb-1">
                        Work Email
                      </label>
                      <TextInput
                        id={emailInputId}
                        type="email"
                        placeholder="planner@company.com"
                        value={feedbackEmail}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFeedbackEmail(e.target.value)}
                        required
                      />
                    </div>
                    <div>
                      <label htmlFor={feedbackInputId} className="block text-xs font-medium text-[var(--muted-foreground)] mb-1">
                        Specific Requirements / Existing ERP Pain
                      </label>
                      <TextInput
                        id={feedbackInputId}
                        placeholder="e.g. Need support for multi-currency customs tariffs..."
                        value={feedbackNote}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFeedbackNote(e.target.value)}
                      />
                    </div>
                  </div>
                  <ActionButton type="submit" size="sm" tone="primary" className="gap-2">
                    <Send size={13} />
                    Submit Product Feedback
                  </ActionButton>
                </form>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: WORKFLOW */}
        {activeTab === "workflow" && (
          <div className="space-y-6">
            <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-6">
              <div>
                <h3 className="text-base font-semibold">End-to-End Execution Sequence</h3>
                <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                  Detailed transactional lifecycle mapping actors, inputs, and system audit outputs.
                </p>
              </div>

              <div className="relative pl-6 space-y-8 before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-[var(--border)]">
                {data.workflowSteps.map((step) => (
                  <div key={step.stepNumber} className="relative group">
                    <div className="absolute -left-6 top-0 flex items-center justify-center w-6 h-6 rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-bold ring-4 ring-[var(--card)]">
                      {step.stepNumber}
                    </div>
                    <div className="p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="font-semibold text-sm">{step.title}</h4>
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 font-medium">
                          Actor: {step.actor}
                        </span>
                      </div>
                      <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                        {step.action}
                      </p>
                      <div className="pt-2 border-t border-[var(--border)]/60 flex items-center gap-2 text-[11px] text-[var(--muted-foreground)]">
                        <span className="font-medium text-[var(--foreground)]">System Output:</span>
                        <code className="px-1.5 py-0.5 rounded bg-[var(--card)] border border-[var(--border)] font-mono text-[10px]">
                          {step.output}
                        </code>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: SCHEMA */}
        {activeTab === "schema" && (
          <div className="space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">Planned PostgreSQL Entity Models</h3>
                <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                  Relational tables, foreign key constraints, and field definitions designed for scalable execution.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-6">
                {data.schemaTables.map((table) => (
                  <div key={table.tableName} className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
                    <div className="bg-[var(--muted)]/60 px-5 py-3 border-b border-[var(--border)] flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[var(--primary)]">{table.tableName}</span>
                        <span className="text-xs text-[var(--muted-foreground)]">&mdash; {table.description}</span>
                      </div>
                      <span className="text-[10px] font-mono bg-blue-500/10 text-blue-600 px-2 py-0.5 rounded">
                        SQL Table
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-[var(--muted)]/20 border-b border-[var(--border)] text-[var(--muted-foreground)] font-semibold uppercase">
                          <tr>
                            <th className="py-2.5 px-4">Column Name</th>
                            <th className="py-2.5 px-4">Data Type</th>
                            <th className="py-2.5 px-4">Description</th>
                            <th className="py-2.5 px-4 text-right">Key Constraint</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]/60 font-mono">
                          {table.fields.map((field) => (
                            <tr key={field.name} className="hover:bg-[var(--muted)]/20 transition">
                              <td className="py-2.5 px-4 font-semibold text-[var(--foreground)]">{field.name}</td>
                              <td className="py-2.5 px-4 text-blue-600 dark:text-blue-400">{field.type}</td>
                              <td className="py-2.5 px-4 text-[var(--muted-foreground)] font-sans">{field.description}</td>
                              <td className="py-2.5 px-4 text-right">
                                {field.isKey ? (
                                  <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 border border-amber-500/20 text-[10px]">
                                    PK / KEY
                                  </span>
                                ) : (
                                  <span className="text-[var(--muted-foreground)]/40">&mdash;</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: INTERACTIVE PROTOTYPE */}
        {activeTab === "prototype" && (
          <div className="space-y-6">
            <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4 shadow-sm">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
                <div>
                  <h3 className="text-base font-semibold flex items-center gap-2">
                    <Sparkles size={18} className="text-amber-500" />
                    Interactive Feature Prototype Preview
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                    Test the simulated workflow algorithms and user interactions planned for this module.
                  </p>
                </div>
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  Live Sandbox
                </span>
              </div>

              {renderInteractiveSimulator(data.interactiveType)}
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}

/** Render domain-specific interactive prototype based on module type */
function renderInteractiveSimulator(type: RoadmapModuleData["interactiveType"]) {
  switch (type) {
    case "landed_cost_calc":
      return <LandedCostSimulator />;
    case "subcontract_reconcile":
      return <SubcontractSimulator />;
    case "bin_visualizer":
      return <BinVisualizerSimulator />;
    case "drp_network":
      return <DrpNetworkSimulator />;
    case "forecast_modeler":
      return <ForecastModelerSimulator />;
    case "traceability_tree":
      return <TraceabilitySimulator />;
    case "container_stuffing":
      return <ContainerStuffingSimulator />;
    case "vendor_portal_asn":
      return <VendorPortalSimulator />;
    default:
      return <div>Prototype under development.</div>;
  }
}

// 1. LANDED COST SIMULATOR
function LandedCostSimulator() {
  const [apportionBy, setApportionBy] = useState<"value" | "weight">("value");
  const [freightAmount, setFreightAmount] = useState<number>(1500);
  const [customsAmount, setCustomsAmount] = useState<number>(1000);

  const totalCharges = freightAmount + customsAmount;

  // 2 Sample items
  const itemA = { name: "High-Precision CNC Motor", qty: 10, unitBase: 1000, totalBase: 10000, weightKg: 20 };
  const itemB = { name: "Steel Mounting Assemblies", qty: 50, unitBase: 40, totalBase: 2000, weightKg: 180 };

  const totalBaseValue = itemA.totalBase + itemB.totalBase; // 12000
  const totalWeight = itemA.weightKg + itemB.weightKg; // 200

  const shareA = apportionBy === "value" ? itemA.totalBase / totalBaseValue : itemA.weightKg / totalWeight;
  const shareB = apportionBy === "value" ? itemB.totalBase / totalBaseValue : itemB.weightKg / totalWeight;

  const allocatedA = totalCharges * shareA;
  const allocatedB = totalCharges * shareB;

  const landedUnitA = (itemA.totalBase + allocatedA) / itemA.qty;
  const landedUnitB = (itemB.totalBase + allocatedB) / itemB.qty;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">
            Freight &amp; Shipping Charges ($)
          </label>
          <input
            type="number"
            className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs"
            value={freightAmount}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFreightAmount(Number(e.target.value) || 0)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">
            Customs &amp; Port Duties ($)
          </label>
          <input
            type="number"
            className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs"
            value={customsAmount}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCustomsAmount(Number(e.target.value) || 0)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">
            Apportionment Method
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setApportionBy("value")}
              className={cn(
                "flex-1 px-3 py-1.5 rounded-lg text-xs font-medium transition",
                apportionBy === "value" ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              )}
            >
              By Item Value
            </button>
            <button
              type="button"
              onClick={() => setApportionBy("weight")}
              className={cn(
                "flex-1 px-3 py-1.5 rounded-lg text-xs font-medium transition",
                apportionBy === "weight" ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              )}
            >
              By Gross Weight
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] overflow-hidden">
        <table className="w-full text-xs text-left">
          <thead className="bg-[var(--muted)]/40 font-semibold border-b border-[var(--border)]">
            <tr>
              <th className="py-2.5 px-3">Item Description</th>
              <th className="py-2.5 px-3">Qty</th>
              <th className="py-2.5 px-3">PO Unit Price</th>
              <th className="py-2.5 px-3">Weight (kg)</th>
              <th className="py-2.5 px-3 text-right">Allocated Expense</th>
              <th className="py-2.5 px-3 text-right font-bold text-[var(--primary)]">True Landed Cost/Unit</th>
              <th className="py-2.5 px-3 text-right">Cost Variance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            <tr>
              <td className="py-3 px-3 font-medium">{itemA.name}</td>
              <td className="py-3 px-3">{itemA.qty}</td>
              <td className="py-3 px-3 font-mono">${itemA.unitBase.toFixed(2)}</td>
              <td className="py-3 px-3">{itemA.weightKg} kg</td>
              <td className="py-3 px-3 text-right font-mono">${allocatedA.toFixed(2)}</td>
              <td className="py-3 px-3 text-right font-mono font-bold text-blue-600 dark:text-blue-400">
                ${landedUnitA.toFixed(2)}
              </td>
              <td className="py-3 px-3 text-right font-mono text-emerald-600">
                +{(((landedUnitA - itemA.unitBase) / itemA.unitBase) * 100).toFixed(1)}%
              </td>
            </tr>
            <tr>
              <td className="py-3 px-3 font-medium">{itemB.name}</td>
              <td className="py-3 px-3">{itemB.qty}</td>
              <td className="py-3 px-3 font-mono">${itemB.unitBase.toFixed(2)}</td>
              <td className="py-3 px-3">{itemB.weightKg} kg</td>
              <td className="py-3 px-3 text-right font-mono">${allocatedB.toFixed(2)}</td>
              <td className="py-3 px-3 text-right font-mono font-bold text-blue-600 dark:text-blue-400">
                ${landedUnitB.toFixed(2)}
              </td>
              <td className="py-3 px-3 text-right font-mono text-emerald-600">
                +{(((landedUnitB - itemB.unitBase) / itemB.unitBase) * 100).toFixed(1)}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs flex items-center justify-between">
        <span>
          <strong>Total Apportioned:</strong> ${totalCharges.toLocaleString()} allocated across 2 items via{" "}
          <strong>{apportionBy === "value" ? "Ad Valorem (Value Ratio)" : "Gross Weight (Kg Ratio)"}</strong>.
        </span>
        <span className="font-mono text-blue-600 font-bold">IAS 2 Compliant</span>
      </div>
    </div>
  );
}

// 2. SUBCONTRACT SIMULATOR
function SubcontractSimulator() {
  const [goodQty, setGoodQty] = useState(98);
  const [scrapKg, setScrapKg] = useState(4.5);

  const rawDispatchedKg = 100;
  const allowableScrapPct = 3.0; // 3%
  const actualScrapPct = (scrapKg / rawDispatchedKg) * 100;
  const isVarianceExceeded = actualScrapPct > allowableScrapPct;

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Order Ref</div>
          <div className="font-mono text-sm font-bold">SPO-2026-9041 (External Powder Coating)</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Vendor</div>
          <div className="text-sm">Supreme Surface Finishers Ltd.</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Raw Material Dispatched</div>
          <div className="font-mono text-sm font-bold">100.0 kg (Alloy Sheet Plates)</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Allowable Scrap Tolerance</div>
          <div className="font-mono text-sm font-bold text-amber-500">3.0% Max</div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">
            Finished Assemblies Received Back (Target: 100)
          </label>
          <input
            type="number"
            className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs"
            value={goodQty}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGoodQty(Number(e.target.value) || 0)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">
            Vendor Scrap / Rejection Returned (kg)
          </label>
          <input
            type="number"
            step="0.1"
            className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-xs"
            value={scrapKg}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setScrapKg(Number(e.target.value) || 0)}
          />
        </div>
      </div>

      <div className={cn(
        "p-4 rounded-xl border flex items-center justify-between text-xs",
        isVarianceExceeded
          ? "bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-400"
          : "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
      )}>
        <div className="flex items-center gap-2">
          {isVarianceExceeded ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
          <span>
            <strong>Scrap Ratio: {actualScrapPct.toFixed(1)}%</strong> &mdash;{" "}
            {isVarianceExceeded
              ? "Exceeds contractual tolerance! System will auto-hold vendor invoice until debit note approved."
              : "Within acceptable 3.0% threshold. Authorized for standard service billing."}
          </span>
        </div>
        <span className="font-mono font-bold uppercase">{isVarianceExceeded ? "Variance Alert" : "Approved"}</span>
      </div>
    </div>
  );
}

// 3. WAREHOUSE BINS SIMULATOR
function BinVisualizerSimulator() {
  const [selectedBin, setSelectedBin] = useState<string>("B-02");
  const bins = [
    { id: "B-01", util: 45, sku: "MOTOR-PUMP-01", weight: "120/500kg", velocity: "Fast (Class A)" },
    { id: "B-02", util: 88, sku: "VALVE-BRASS-90", weight: "440/500kg", velocity: "Fast (Class A)" },
    { id: "B-03", util: 15, sku: "O-RING-PACK-100", weight: "15/500kg", velocity: "Medium (Class B)" },
    { id: "B-04", util: 92, sku: "FLANGE-STEEL-4IN", weight: "460/500kg", velocity: "Slow (Class C)" },
    { id: "B-05", util: 0, sku: "EMPTY (Available)", weight: "0/500kg", velocity: "Unassigned" },
    { id: "B-06", util: 60, sku: "GASKET-NEOPRENE", weight: "180/500kg", velocity: "Medium (Class B)" },
  ];

  const active = bins.find((b) => b.id === selectedBin) || bins[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--muted-foreground)]">
          Rack Coordinate: <strong>Zone 1 &bull; Aisle 3 &bull; Rack 2</strong> (Click a cell to inspect)
        </span>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-emerald-500" /> &lt;60% Full</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-amber-500" /> 60-85% Full</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-rose-500" /> &gt;85% Full</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {bins.map((b) => {
          const color = b.util === 0 ? "border-dashed border-gray-400 bg-transparent" : b.util > 85 ? "bg-rose-500/15 border-rose-500/40 text-rose-700 dark:text-rose-300" : b.util > 55 ? "bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-300" : "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300";
          return (
            <button
              key={b.id}
              type="button"
              onClick={() => setSelectedBin(b.id)}
              className={cn(
                "p-4 rounded-xl border text-left transition relative cursor-pointer",
                color,
                selectedBin === b.id && "ring-2 ring-[var(--primary)] ring-offset-2"
              )}
            >
              <div className="font-mono text-xs font-bold">{b.id}</div>
              <div className="text-xs truncate mt-1 font-medium">{b.sku}</div>
              <div className="text-[11px] opacity-80 mt-1">{b.util}% Volume</div>
            </button>
          );
        })}
      </div>

      <div className="p-4 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)] flex items-center justify-between text-xs">
        <div>
          <span className="font-semibold text-sm">Selected Cell: {active.id}</span>
          <p className="text-[var(--muted-foreground)] mt-0.5">Stored SKU: {active.sku} &bull; Weight Rating: {active.weight}</p>
        </div>
        <div className="text-right">
          <span className="font-mono px-2 py-1 rounded bg-[var(--card)] border border-[var(--border)] font-semibold">
            {active.velocity}
          </span>
        </div>
      </div>
    </div>
  );
}

// 4. DRP NETWORK SIMULATOR
function DrpNetworkSimulator() {
  const [spikePct, setSpikePct] = useState(25);

  const baseOrder = 200;
  const recommendedTransfer = Math.round(baseOrder * (1 + spikePct / 100));

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold">Simulate Regional Demand Surge in North DC (Delhi)</span>
          <span className="font-mono font-bold text-xs text-blue-600">+{spikePct}% Forecast Spike</span>
        </div>
        <input
          type="range"
          min="0"
          max="80"
          value={spikePct}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSpikePct(Number(e.target.value))}
          className="w-full accent-blue-600 cursor-pointer"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-1">
          <div className="text-[var(--muted-foreground)] font-semibold uppercase text-[10px]">Supply Source</div>
          <div className="font-bold text-sm">Central Mother Hub (Pune)</div>
          <div className="text-emerald-600 font-mono">On-Hand: 1,840 Units Available</div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] bg-blue-500/5 space-y-1">
          <div className="text-blue-600 font-semibold uppercase text-[10px]">Transit Lane</div>
          <div className="font-bold text-sm">Pune &rarr; Delhi North DC</div>
          <div className="text-[var(--muted-foreground)]">Transit Lead Time: 3 Days (Roadways)</div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-1">
          <div className="text-[var(--muted-foreground)] font-semibold uppercase text-[10px]">Destination Hub</div>
          <div className="font-bold text-sm">North DC (Delhi)</div>
          <div className="text-rose-600 font-mono font-bold">Buffer Penetration: In 4 Days</div>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs flex items-center justify-between">
        <div>
          <strong>DRP Engine Recommendation:</strong> Release Planned Transfer Order (PTO) of{" "}
          <strong className="text-emerald-600 text-sm font-mono">{recommendedTransfer} units</strong> from Pune to Delhi.
        </div>
        <ActionButton size="sm" tone="primary" className="text-xs">
          Simulate Auto-Release Transfer
        </ActionButton>
      </div>
    </div>
  );
}

// 5. FORECAST MODELER SIMULATOR
function ForecastModelerSimulator() {
  const [model, setModel] = useState<"holt_winters" | "arima" | "moving_avg">("holt_winters");
  const [promoUplift, setPromoUplift] = useState<number>(15);

  const baseValues = [120, 135, 142, 130, 155, 168]; // Past 6 months
  const projectedValues = {
    holt_winters: [175, 188, 210, 195],
    arima: [172, 180, 189, 192],
    moving_avg: [160, 162, 165, 167],
  }[model].map((v) => Math.round(v * (1 + promoUplift / 100)));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--muted-foreground)]">Algorithm:</span>
          {(["holt_winters", "arima", "moving_avg"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setModel(m)}
              className={cn(
                "px-3 py-1 rounded-lg text-xs font-medium transition",
                model === m ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              )}
            >
              {m === "holt_winters" ? "Holt-Winters Seasonal" : m === "arima" ? "ARIMA (1,1,1)" : "3M Moving Avg"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-[var(--muted-foreground)]">Promotional Uplift:</span>
          <span className="font-mono font-bold text-blue-600">+{promoUplift}%</span>
          <input
            type="range"
            min="0"
            max="40"
            value={promoUplift}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPromoUplift(Number(e.target.value))}
            className="w-24 accent-blue-600 cursor-pointer"
          />
        </div>
      </div>

      {/* Simulated Time-Series Bar */}
      <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--muted)]/20 space-y-3">
        <div className="text-xs font-semibold text-[var(--muted-foreground)]">Time-Series Forecast Trajectory (Units)</div>
        <div className="grid grid-cols-10 gap-2 items-end h-28 pt-4">
          {baseValues.map((val, i) => (
            <div key={`hist-${i}`} className="flex flex-col items-center gap-1 group">
              <span className="text-[9px] font-mono opacity-0 group-hover:opacity-100 transition">{val}</span>
              <div
                style={{ height: `${(val / 250) * 100}%` }}
                className="w-full bg-slate-400 dark:bg-slate-600 rounded-t transition-all"
              />
              <span className="text-[9px] text-[var(--muted-foreground)]">M-{6 - i}</span>
            </div>
          ))}
          {projectedValues.map((val, i) => (
            <div key={`proj-${i}`} className="flex flex-col items-center gap-1 group">
              <span className="text-[9px] font-mono font-bold text-blue-600 opacity-0 group-hover:opacity-100 transition">{val}</span>
              <div
                style={{ height: `${(val / 250) * 100}%` }}
                className="w-full bg-blue-500 rounded-t transition-all shadow-sm shadow-blue-500/50"
              />
              <span className="text-[9px] font-bold text-blue-600">+M{i + 1}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)] pt-2 border-t border-[var(--border)]">
          <span>&bull; Grey: Actual Past Shipments</span>
          <span className="text-blue-600 font-medium">&bull; Blue: Algorithmic S&amp;OP Projection</span>
          <span className="font-mono">Tested MAPE: <strong>8.7%</strong></span>
        </div>
      </div>
    </div>
  );
}

// 6. TRACEABILITY SIMULATOR
function TraceabilitySimulator() {
  const [quarantined, setQuarantined] = useState(false);

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Suspect Input Lot</div>
          <div className="font-mono text-sm font-bold text-rose-600">LOT-RAW-ALUM-892 (Raw Bauxite Ingot)</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Vendor Origin</div>
          <div className="text-sm">National Alloys Corp (PO-2026-118)</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Incident Reason</div>
          <div className="text-sm text-rose-600 font-medium">Yield Strength Below Spec (520 vs 680 MPa)</div>
        </div>
      </div>

      {/* Visual Genealogy Graph */}
      <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4">
        <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
          Forward Consumption Genealogy Graph
        </div>

        <div className="flex flex-col md:flex-row items-center gap-4 text-xs">
          <div className="p-3 rounded-lg border border-rose-500/40 bg-rose-500/10 text-center w-full md:w-48">
            <span className="font-mono font-bold block text-rose-700 dark:text-rose-300">LOT-RAW-ALUM-892</span>
            <span className="text-[10px] text-[var(--muted-foreground)]">500 kg Received</span>
          </div>

          <ArrowRight className="text-[var(--muted-foreground)] shrink-0 hidden md:block" size={16} />

          <div className="p-3 rounded-lg border border-blue-500/40 bg-blue-500/10 text-center w-full md:w-56">
            <span className="font-mono font-bold block text-blue-700 dark:text-blue-300">WO-2026-0419</span>
            <span className="text-[10px] text-[var(--muted-foreground)]">Machined Crankcase (40 Pcs)</span>
          </div>

          <ArrowRight className="text-[var(--muted-foreground)] shrink-0 hidden md:block" size={16} />

          <div className="flex-1 w-full space-y-2">
            <div className="p-2.5 rounded bg-[var(--muted)]/50 border border-[var(--border)] flex justify-between items-center">
              <span><strong>SO-1094:</strong> Shipped to Apex Motors (15 Pcs)</span>
              <span className="text-[10px] font-mono text-rose-600 font-bold">Needs Advisory</span>
            </div>
            <div className="p-2.5 rounded bg-[var(--muted)]/50 border border-[var(--border)] flex justify-between items-center">
              <span><strong>Hub A Warehouse:</strong> 25 Pcs on Shelf (Rack 4)</span>
              <span className="text-[10px] font-mono text-amber-600 font-bold">
                {quarantined ? "LOCKED & QUARANTINED" : "Available to Ship"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <ActionButton
          tone={quarantined ? "ghost" : "danger"}
          size="sm"
          onClick={() => setQuarantined(!quarantined)}
          className="gap-2"
        >
          <ShieldAlert size={15} />
          {quarantined ? "Release Simulated Quarantine Hold" : "Simulate One-Click Digital Quarantine"}
        </ActionButton>
        <span className="text-xs text-[var(--muted-foreground)]">
          Audit Log ID: <code className="font-mono">RECALL-2026-004</code>
        </span>
      </div>
    </div>
  );
}

// 7. CONTAINER STUFFING SIMULATOR
function ContainerStuffingSimulator() {
  const [containerType, setContainerType] = useState<"20GP" | "40HC">("40HC");

  const capacity = containerType === "20GP" ? { cbm: 33.2, maxWeight: 21770 } : { cbm: 76.2, maxWeight: 26580 };
  const loadedCbm = containerType === "20GP" ? 28.5 : 67.8;
  const loadedWeight = containerType === "20GP" ? 17400 : 22800;

  const utilPct = Math.round((loadedCbm / capacity.cbm) * 100);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--muted-foreground)]">Container Specification:</span>
          {(["20GP", "40HC"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setContainerType(t)}
              className={cn(
                "px-3 py-1 rounded text-xs font-medium transition",
                containerType === t ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              )}
            >
              {t === "20GP" ? "20ft Standard (33 CBM)" : "40ft High Cube (76 CBM)"}
            </button>
          ))}
        </div>
        <span className="text-xs font-mono font-bold text-emerald-600">3D Volumetric Fill: {utilPct}%</span>
      </div>

      <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span>Cubic Volume Utilization ({loadedCbm} / {capacity.cbm} CBM)</span>
            <span className="font-mono font-bold">{utilPct}%</span>
          </div>
          <div className="w-full bg-[var(--muted)] h-3 rounded-full overflow-hidden">
            <div style={{ width: `${utilPct}%` }} className="bg-blue-600 h-full rounded-full transition-all" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs pt-2">
          <div className="p-3 rounded-lg bg-[var(--muted)]/40 border border-[var(--border)]">
            <div className="text-[var(--muted-foreground)]">Gross Weight</div>
            <div className="font-mono text-sm font-bold mt-0.5">{loadedWeight.toLocaleString()} kg</div>
            <div className="text-[10px] text-emerald-600 mt-0.5">Payload Safe (Max {capacity.maxWeight.toLocaleString()} kg)</div>
          </div>
          <div className="p-3 rounded-lg bg-[var(--muted)]/40 border border-[var(--border)]">
            <div className="text-[var(--muted-foreground)]">Consolidated Invoices</div>
            <div className="font-mono text-sm font-bold mt-0.5">4 Orders Pooled</div>
            <div className="text-[10px] text-blue-600 mt-0.5">Est. Freight Saving: $1,420</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 8. VENDOR PORTAL SIMULATOR
function VendorPortalSimulator() {
  const [asnGenerated, setAsnGenerated] = useState(false);
  const [poAcknowledged, setPoAcknowledged] = useState(false);

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Supplier Collaboration Order</div>
          <div className="font-mono text-sm font-bold">PO-3004 (Industrial Hydraulic Hoses)</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Supplier Name</div>
          <div className="text-sm">FlexiFlow Tubing Ltd.</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-[var(--muted-foreground)]">Order Value</div>
          <div className="font-mono text-sm font-bold">$18,450.00</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border border-[var(--border)] space-y-3">
          <h4 className="font-semibold text-xs text-[var(--primary)] uppercase tracking-wider">
            1. Supplier PO Confirmation
          </h4>
          <p className="text-xs text-[var(--muted-foreground)]">
            Vendor confirms receipt and commits to ship date without phone calls.
          </p>
          <ActionButton
            size="sm"
            tone={poAcknowledged ? "ghost" : "primary"}
            onClick={() => setPoAcknowledged(true)}
            className="w-full text-xs"
          >
            {poAcknowledged ? "✓ PO Acknowledged by Vendor" : "Click to Acknowledge PO"}
          </ActionButton>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] space-y-3">
          <h4 className="font-semibold text-xs text-[var(--primary)] uppercase tracking-wider">
            2. Advance Shipping Notice (ASN)
          </h4>
          <p className="text-xs text-[var(--muted-foreground)]">
            Generates pre-arrival shipping manifest with GS1-128 pallet barcodes.
          </p>
          <ActionButton
            size="sm"
            tone={asnGenerated ? "ghost" : "primary"}
            disabled={!poAcknowledged}
            onClick={() => setAsnGenerated(true)}
            className="w-full text-xs"
          >
            {asnGenerated ? "✓ ASN-9841 Dispatched (Barcode Ready)" : "Generate & Dispatch ASN"}
          </ActionButton>
        </div>
      </div>

      {asnGenerated && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs flex items-center justify-between">
          <span>
            <strong>ASN Active:</strong> Inbound goods receipt pre-scheduled at Factory Dock. Barcode scanning enables 10-second receipt.
          </span>
          <span className="font-mono font-bold text-emerald-600">ASN-9841</span>
        </div>
      )}
    </div>
  );
}
