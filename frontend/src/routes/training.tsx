import React, { useState, useMemo } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Boxes,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  ExternalLink,
  Factory,
  GraduationCap,
  HelpCircle,
  Layers,
  Network,
  Printer,
  Receipt,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Sparkles,
  Truck,
  Warehouse,
  type LucideIcon,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import { ActionButton, Badge, DataTable, Forbidden, PageHeader, Panel, Pill } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import {
  ENTERPRISE_MASTER_FLOWCHART,
  STREAM_METADATA,
  getNodeById,
  type EnterpriseStream,
  type EnterpriseWorkflowNode,
} from "@/lib/enterprise-flowchart-data";
import {
  TRAINING_MODULES,
  type ModuleTrainingContent,
  type TrainingWorkflowStep,
} from "@/lib/training-data";
import { cn } from "@/lib/utils";

const MODULE_ICONS: Record<string, LucideIcon> = {
  ShoppingCart,
  Warehouse,
  Boxes,
  Factory,
  ClipboardList,
  Receipt,
  Truck,
  SlidersHorizontal,
  ShieldCheck,
};

const STAGE_TITLES: Record<number, { title: string; subtitle: string }> = {
  1: { title: "Stage 1: Demand, Forecasting & BOM", subtitle: "Strategic demand modeling and engineering specs" },
  2: { title: "Stage 2: Requirements & Demand Initiation", subtitle: "MRP explosion, internal requisitions & sales orders" },
  3: { title: "Stage 3: Sourcing, Quoting & Work Orders", subtitle: "Vendor RFQs, PO tier approvals & shop-floor runs" },
  4: { title: "Stage 4: Inbound Logistics & Order Allocation", subtitle: "Vendor dispatch ASNs, material issue & wave picking" },
  5: { title: "Stage 5: Receiving, QC, Assembly & Billing", subtitle: "Dock GRNs, quality tests, FG conversion & customer invoices" },
  6: { title: "Stage 6: Settlement, Delivery POD & Valuation", subtitle: "3-Way matching, bank payouts, landed cost & audit" },
};

export default function TrainingPage() {
  const { can } = useAuth();

  // Top-level View Mode: Master Flowchart vs Module Deep-Dive
  const [viewMode, setViewMode] = useState<"master_flowchart" | "module_training">("master_flowchart");

  // Master Flowchart states
  const [selectedStream, setSelectedStream] = useState<EnterpriseStream | "All">("All");
  const [selectedMasterNodeId, setSelectedMasterNodeId] = useState<string>("PO_ISSUE");

  // Module Deep-Dive states
  const [selectedModuleId, setSelectedModuleId] = useState<string>("procurement");
  const [activeTab, setActiveTab] = useState<"flowchart" | "manual" | "validations" | "troubleshooting" | "quiz">("flowchart");
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(0);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>("All");
  const [expandedFaqIndex, setExpandedFaqIndex] = useState<number | null>(0);
  const [expandedTroubleIndex, setExpandedTroubleIndex] = useState<number | null>(0);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState<boolean>(false);

  // Universal Search
  const [searchQuery, setSearchQuery] = useState<string>("");

  const hasAccess =
    can("training:read") ||
    can("user:read") ||
    can("audit:read") ||
    can("analytics:read") ||
    can("product:read") ||
    can("*");

  if (!hasAccess) {
    return (
      <Shell>
        <Forbidden permission="training:read" />
      </Shell>
    );
  }

  const activeModule: ModuleTrainingContent = TRAINING_MODULES[selectedModuleId] || TRAINING_MODULES.procurement;
  const ActiveIcon = MODULE_ICONS[activeModule.iconName] || BookOpen;

  const activeMasterNode: EnterpriseWorkflowNode =
    getNodeById(selectedMasterNodeId) || ENTERPRISE_MASTER_FLOWCHART[0];

  // Filtered Master Flowchart nodes
  const filteredMasterNodes = useMemo(() => {
    if (selectedStream === "All") return ENTERPRISE_MASTER_FLOWCHART;
    return ENTERPRISE_MASTER_FLOWCHART.filter((n) => n.stream === selectedStream);
  }, [selectedStream]);

  // Group nodes by stage (Stage 1 to 6)
  const nodesByStage = useMemo(() => {
    const map: Record<number, EnterpriseWorkflowNode[]> = { 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] };
    filteredMasterNodes.forEach((node) => {
      if (map[node.stageOrder]) {
        map[node.stageOrder].push(node);
      }
    });
    return map;
  }, [filteredMasterNodes]);

  // Global search filtering
  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return null;

    const matches: {
      id: string;
      title: string;
      context: string;
      snippet: string;
      type: "master_node" | "module_content";
      targetId: string;
    }[] = [];

    // Search master flowchart nodes
    ENTERPRISE_MASTER_FLOWCHART.forEach((node) => {
      if (
        node.title.toLowerCase().includes(q) ||
        node.code.toLowerCase().includes(q) ||
        node.summary.toLowerCase().includes(q) ||
        node.keyValidations.some((v) => v.name.toLowerCase().includes(q) || (v.errorCode && v.errorCode.toLowerCase().includes(q)))
      ) {
        matches.push({
          id: node.id,
          title: `[${node.code}] ${node.title}`,
          context: `Enterprise Flowchart • ${node.module}`,
          snippet: node.summary,
          type: "master_node",
          targetId: node.id,
        });
      }
    });

    // Search module deep-dive training
    Object.values(TRAINING_MODULES).forEach((mod) => {
      if (mod.title.toLowerCase().includes(q) || mod.summary.toLowerCase().includes(q)) {
        matches.push({
          id: mod.id,
          title: mod.title,
          context: `Module Training • ${mod.group}`,
          snippet: mod.summary,
          type: "module_content",
          targetId: mod.id,
        });
      }

      mod.troubleshooting.forEach((t) => {
        if (t.issue.toLowerCase().includes(q) || (t.errorCode && t.errorCode.toLowerCase().includes(q)) || t.rootCause.toLowerCase().includes(q)) {
          matches.push({
            id: `${mod.id}-${t.issue}`,
            title: `Issue: ${t.issue}`,
            context: `${mod.title} • Troubleshooting`,
            snippet: `${t.errorCode ? `[${t.errorCode}] ` : ""}${t.rootCause}`,
            type: "module_content",
            targetId: mod.id,
          });
        }
      });
    });

    return matches;
  }, [searchQuery]);

  const handleSelectModule = (id: string) => {
    setSelectedModuleId(id);
    setSelectedStepIndex(0);
    setQuizAnswers({});
    setQuizSubmitted(false);
  };

  const handleJumpToModuleFromMaster = (modId: string) => {
    setSelectedModuleId(modId);
    setViewMode("module_training");
    setActiveTab("flowchart");
    setSelectedStepIndex(0);
  };

  const activeStep: TrainingWorkflowStep | undefined =
    selectedStepIndex !== null ? activeModule.workflowSteps[selectedStepIndex] : activeModule.workflowSteps[0];

  const totalValidationsCount = useMemo(() => {
    return activeModule.workflowSteps.reduce((acc, s) => acc + s.validations.length, 0);
  }, [activeModule]);

  const filteredValidations = useMemo(() => {
    const all = activeModule.workflowSteps.flatMap((s) =>
      s.validations.map((v) => ({ ...v, stepNumber: s.stepNumber, stepTitle: s.title }))
    );
    if (selectedCategoryFilter === "All") return all;
    return all.filter((v) => v.category === selectedCategoryFilter);
  }, [activeModule, selectedCategoryFilter]);

  const calculateQuizScore = () => {
    let score = 0;
    activeModule.quiz.forEach((q, idx) => {
      if (quizAnswers[idx] === q.correctIndex) {
        score++;
      }
    });
    return score;
  };

  return (
    <Shell fullWidth>
      <div className="p-4 md:p-6 lg:p-8 max-w-[1600px] mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[var(--border)] pb-5">
          <div>
            <PageHeader
              eyebrow="Administration / Knowledge Base"
              title={
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20 shadow-sm">
                    <GraduationCap size={26} />
                  </span>
                  <div>
                    <span className="text-xl md:text-2xl font-bold tracking-tight text-[var(--foreground)]">
                      ERP Training & Enterprise Workflow Academy
                    </span>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                      Visual flowcharts depicting all module workflows with upperline & downline connections, validation checks, operational SOPs, and troubleshooting guides.
                    </p>
                  </div>
                </div>
              }
            />
          </div>

          {/* Primary View Mode Switcher */}
          <div className="flex items-center gap-2 bg-[var(--muted)] p-1 rounded-xl border border-[var(--border)] shrink-0">
            <button
              type="button"
              onClick={() => setViewMode("master_flowchart")}
              className={cn(
                "px-3.5 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2",
                viewMode === "master_flowchart"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              <Network size={16} />
              <span>Complete Enterprise Flowchart</span>
              <span className="text-[10px] px-1.5 py-0.2 bg-teal-800/40 rounded text-teal-100 font-mono">
                {ENTERPRISE_MASTER_FLOWCHART.length} Nodes
              </span>
            </button>

            <button
              type="button"
              onClick={() => setViewMode("module_training")}
              className={cn(
                "px-3.5 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2",
                viewMode === "module_training"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              <BookOpen size={16} />
              <span>Module Deep-Dive & SOPs</span>
              <span className="text-[10px] px-1.5 py-0.2 bg-teal-800/40 rounded text-teal-100 font-mono">
                9 Modules
              </span>
            </button>
          </div>
        </div>

        {/* Global Universal Search Bar */}
        <div className="relative">
          <div className="relative flex items-center">
            <Search size={18} className="absolute left-3.5 text-[var(--muted-foreground)] pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search across all workflows, checks, error codes (e.g. '3-way match', 'credit limit', 'over-tolerance', 'rejection', 'e-way bill', 'row-lock')..."
              className="w-full pl-10 pr-24 py-2.5 bg-[var(--card)] border border-[var(--border)] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 text-[var(--foreground)] shadow-sm"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] bg-[var(--muted)] px-2 py-1 rounded"
              >
                Clear
              </button>
            )}
          </div>

          {/* Search Results Dropdown */}
          {searchResults && (
            <div className="absolute z-40 left-0 right-0 mt-2 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl max-h-96 overflow-y-auto p-2 space-y-1">
              <div className="p-2 text-xs font-semibold text-[var(--muted-foreground)] border-b border-[var(--border)] flex justify-between">
                <span>Search Results ({searchResults.length} matches)</span>
                <span>Click to jump</span>
              </div>
              {searchResults.length === 0 ? (
                <div className="p-4 text-center text-sm text-[var(--muted-foreground)]">
                  No matching workflows, validations, or error codes found for "{searchQuery}".
                </div>
              ) : (
                searchResults.map((res, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      if (res.type === "master_node") {
                        setViewMode("master_flowchart");
                        setSelectedMasterNodeId(res.targetId);
                      } else {
                        setViewMode("module_training");
                        handleSelectModule(res.targetId);
                      }
                      setSearchQuery("");
                    }}
                    className="w-full text-left p-2.5 rounded-lg hover:bg-[var(--accent)] transition-colors flex flex-col gap-1"
                  >
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-semibold text-teal-600 dark:text-teal-400">{res.title}</span>
                      <span className="text-[var(--muted-foreground)]">•</span>
                      <span className="font-medium text-[var(--foreground)]">{res.context}</span>
                    </div>
                    <p className="text-xs text-[var(--muted-foreground)] line-clamp-1">{res.snippet}</p>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* SECTION 1: COMPLETE ENTERPRISE MASTER FLOWCHART & DEPENDENCY NETWORK */}
        {/* ========================================================================= */}
        {viewMode === "master_flowchart" && (
          <div className="space-y-6">
            {/* Stream Filter Pills & Legend */}
            <div className="p-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] space-y-3 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Filter Enterprise Stream:
                  </span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {(["All", "Procure-to-Pay", "Plan-to-Produce", "Order-to-Cash", "Warehouse & WMS", "Finance & Accounting", "Governance"] as const).map(
                      (stream) => {
                        const isSelected = selectedStream === stream;
                        return (
                          <button
                            key={stream}
                            type="button"
                            onClick={() => setSelectedStream(stream)}
                            className={cn(
                              "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                              isSelected
                                ? "bg-teal-600 text-white shadow-sm"
                                : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                            )}
                          >
                            {stream === "All" ? "All Streams (36 Nodes)" : stream}
                          </button>
                        );
                      }
                    )}
                  </div>
                </div>

                {/* Legend */}
                <div className="flex items-center gap-3 text-[11px] text-[var(--muted-foreground)] flex-wrap">
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-teal-500" /> Upperline: Inputs & Predecessors
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-blue-500" /> Downline: Outputs & Triggers
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-red-500" /> Hard Blocker Dependency
                  </span>
                </div>
              </div>
            </div>

            {/* Master Pipeline Flowchart Grid (Stages 1 through 6) */}
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {[1, 2, 3, 4, 5, 6].map((stageNum) => {
                  const stageNodes = nodesByStage[stageNum] || [];
                  const stageInfo = STAGE_TITLES[stageNum];
                  if (stageNodes.length === 0) return null;

                  return (
                    <div
                      key={stageNum}
                      className="flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm space-y-3"
                    >
                      {/* Stage Header */}
                      <div className="border-b border-[var(--border)] pb-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-teal-500/10 text-teal-700 dark:text-teal-300">
                            Pipeline Phase {stageNum}
                          </span>
                          <span className="text-[11px] font-mono text-[var(--muted-foreground)]">
                            {stageNodes.length} Workflows
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-[var(--foreground)] mt-1">{stageInfo.title}</h3>
                        <p className="text-[11px] text-[var(--muted-foreground)]">{stageInfo.subtitle}</p>
                      </div>

                      {/* Stage Workflow Nodes */}
                      <div className="space-y-3 flex-1">
                        {stageNodes.map((node) => {
                          const isSelected = selectedMasterNodeId === node.id;
                          const streamMeta = STREAM_METADATA[node.stream];

                          return (
                            <div
                              key={node.id}
                              onClick={() => setSelectedMasterNodeId(node.id)}
                              className={cn(
                                "p-3.5 rounded-xl border text-left cursor-pointer transition-all relative group",
                                isSelected
                                  ? "border-teal-500 bg-teal-500/10 shadow-md ring-2 ring-teal-500/50"
                                  : "border-[var(--border)] bg-[var(--card)] hover:border-teal-500/40 hover:bg-[var(--accent)]"
                              )}
                            >
                              {/* Node Top Row */}
                              <div className="flex items-center justify-between gap-2 mb-1.5">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--foreground)]">
                                    {node.code}
                                  </span>
                                  <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full", streamMeta.badgeClass)}>
                                    {node.stream}
                                  </span>
                                </div>
                                <span className="text-[10px] text-[var(--muted-foreground)] font-mono">
                                  🛡️ {node.keyValidations.length}
                                </span>
                              </div>

                              <h4 className="text-xs font-bold text-[var(--foreground)] group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors">
                                {node.title}
                              </h4>
                              <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-2 mt-1">
                                {node.summary}
                              </p>

                              {/* Connects Counters Badges */}
                              <div className="mt-2.5 pt-2 border-t border-[var(--border)] flex items-center justify-between text-[10px]">
                                <span className="flex items-center gap-1 text-teal-600 dark:text-teal-400 font-medium">
                                  <ArrowUp size={12} />
                                  <span>{node.upperlineConnects.length} Upperline</span>
                                </span>
                                <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium">
                                  <ArrowDown size={12} />
                                  <span>{node.downlineConnects.length} Downline</span>
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Master Node Deep-Dive Inspector (Upperline, Downline, Validations & Ledger) */}
            {activeMasterNode && (
              <Panel
                title={`[${activeMasterNode.code}] ${activeMasterNode.title} — Complete Connection & Dependency Inspector`}
                subtitle={`Module: ${activeMasterNode.module} • Lifecycle Stream: ${activeMasterNode.stream} • Actor: ${activeMasterNode.actor} (${activeMasterNode.actorRole})`}
                aside={
                  <button
                    type="button"
                    onClick={() => handleJumpToModuleFromMaster(activeMasterNode.moduleId)}
                    className="action-btn text-xs font-semibold px-3 py-1.5 rounded-lg border border-teal-500 bg-teal-500/10 text-teal-700 dark:text-teal-300 hover:bg-teal-500/20 flex items-center gap-1.5"
                  >
                    <span>Open {activeMasterNode.module} Training Package</span>
                    <ExternalLink size={14} />
                  </button>
                }
                className="border-teal-500/40 bg-gradient-to-br from-teal-500/[0.02] to-blue-500/[0.02] shadow-md"
              >
                <div className="p-5 space-y-6">
                  {/* Summary & Actor Bar */}
                  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-2">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-[var(--border)] pb-2 text-xs">
                      <div>
                        <span className="font-semibold text-[var(--foreground)]">Primary Actor & Permission: </span>
                        <code className="font-mono bg-[var(--muted)] px-2 py-0.5 rounded text-teal-700 dark:text-teal-300">
                          {activeMasterNode.actor} ({activeMasterNode.actorRole})
                        </code>
                      </div>
                      <div>
                        <span className="font-semibold text-[var(--foreground)]">Pipeline Phase: </span>
                        <span className="text-[var(--muted-foreground)]">Stage {activeMasterNode.stageOrder}</span>
                      </div>
                    </div>
                    <p className="text-xs text-[var(--foreground)] leading-relaxed">{activeMasterNode.summary}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 text-[11px] text-[var(--muted-foreground)]">
                      <div>
                        <span className="font-semibold text-[var(--foreground)]">Input Documents: </span>
                        <span>{activeMasterNode.inputDocuments.join(", ")}</span>
                      </div>
                      <div>
                        <span className="font-semibold text-[var(--foreground)]">Output Documents: </span>
                        <span>{activeMasterNode.outputDocuments.join(", ")}</span>
                      </div>
                    </div>
                  </div>

                  {/* Upperline vs Downline Connections Two-Column Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {/* Upperline Connects (Upstream Predecessors) */}
                    <div className="p-4 rounded-xl border border-teal-500/30 bg-[var(--card)] space-y-3">
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                        <div className="flex items-center gap-2">
                          <span className="p-1 rounded bg-teal-500/10 text-teal-600">
                            <ArrowUp size={16} />
                          </span>
                          <h4 className="text-sm font-bold text-[var(--foreground)]">
                            Upperline Connects ({activeMasterNode.upperlineConnects.length} Upstream Inputs)
                          </h4>
                        </div>
                        <span className="text-[10px] text-[var(--muted-foreground)]">What feeds into this step</span>
                      </div>

                      {activeMasterNode.upperlineConnects.length === 0 ? (
                        <p className="text-xs text-[var(--muted-foreground)] italic py-2">
                          Initial entry point; no preceding workflow requirements.
                        </p>
                      ) : (
                        <div className="space-y-2.5">
                          {activeMasterNode.upperlineConnects.map((conn, idx) => (
                            <div
                              key={idx}
                              onClick={() => setSelectedMasterNodeId(conn.nodeId)}
                              className="p-3 rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 hover:border-teal-500/50 hover:bg-teal-500/5 cursor-pointer transition-all space-y-1 text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-teal-600 dark:text-teal-400">
                                  ← {conn.label} ({conn.sourceModule})
                                </span>
                                {conn.isHardDependency && (
                                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/10 text-red-600 border border-red-500/20 font-semibold">
                                    Hard Blocker
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-[var(--muted-foreground)]">
                                <span className="font-medium text-[var(--foreground)]">Data Received: </span>
                                {conn.dataPassed}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Downline Connects (Downstream Successors) */}
                    <div className="p-4 rounded-xl border border-blue-500/30 bg-[var(--card)] space-y-3">
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                        <div className="flex items-center gap-2">
                          <span className="p-1 rounded bg-blue-500/10 text-blue-600">
                            <ArrowDown size={16} />
                          </span>
                          <h4 className="text-sm font-bold text-[var(--foreground)]">
                            Downline Connects ({activeMasterNode.downlineConnects.length} Downstream Outputs)
                          </h4>
                        </div>
                        <span className="text-[10px] text-[var(--muted-foreground)]">What this step triggers</span>
                      </div>

                      {activeMasterNode.downlineConnects.length === 0 ? (
                        <p className="text-xs text-[var(--muted-foreground)] italic py-2">
                          Final terminal milestone in current stream.
                        </p>
                      ) : (
                        <div className="space-y-2.5">
                          {activeMasterNode.downlineConnects.map((conn, idx) => (
                            <div
                              key={idx}
                              onClick={() => setSelectedMasterNodeId(conn.nodeId)}
                              className="p-3 rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 hover:border-blue-500/50 hover:bg-blue-500/5 cursor-pointer transition-all space-y-1 text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-blue-600 dark:text-blue-400">
                                  → {conn.label} ({conn.targetModule})
                                </span>
                                {conn.isTrigger && (
                                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 font-semibold">
                                    Auto-Trigger
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-[var(--muted-foreground)]">
                                <span className="font-medium text-[var(--foreground)]">Data Handed Off: </span>
                                {conn.dataPassed}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Validations Enforced & Checks */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                      <ShieldCheck size={16} className="text-teal-600" />
                      <span>Critical Validations & Guard Conditions Enforced at this Node:</span>
                    </h4>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {activeMasterNode.keyValidations.map((val, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-1.5 text-xs"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-bold text-[var(--foreground)]">{val.name}</span>
                            <Badge
                              color={
                                val.severity.includes("Blocker")
                                  ? "red"
                                  : val.severity.includes("Escalation")
                                  ? "amber"
                                  : "gray"
                              }
                            >
                              {val.severity}
                            </Badge>
                          </div>
                          <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">{val.rule}</p>
                          {val.errorCode && (
                            <code className="text-[10px] font-mono bg-[var(--muted)] px-1.5 py-0.5 rounded text-red-600 dark:text-red-400 font-semibold inline-block mt-1">
                              {val.errorCode}
                            </code>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Financial Ledger & Failure Impact Bar */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div className="p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] space-y-1 text-xs">
                      <span className="font-bold text-emerald-700 dark:text-emerald-300 block flex items-center gap-1.5">
                        <Receipt size={14} />
                        <span>Financial & Stock Ledger Accounting Impact:</span>
                      </span>
                      <p className="text-[var(--foreground)] font-mono text-[11px] leading-relaxed">
                        {activeMasterNode.ledgerImpact}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.03] space-y-1 text-xs">
                      <span className="font-bold text-rose-700 dark:text-rose-300 block flex items-center gap-1.5">
                        <AlertTriangle size={14} />
                        <span>Failure & Exception Consequence:</span>
                      </span>
                      <p className="text-[var(--muted-foreground)] text-[11px] leading-relaxed">
                        {activeMasterNode.failureImpact}
                      </p>
                    </div>
                  </div>
                </div>
              </Panel>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* SECTION 2: MODULE DEEP-DIVE TRAINING & SOP ACADEMY */}
        {/* ========================================================================= */}
        {viewMode === "module_training" && (
          <div className="space-y-6">
            {/* Module Switcher Buttons (9 Modules) */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                Select ERP Module to Train On:
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-9 gap-2">
                {Object.values(TRAINING_MODULES).map((mod) => {
                  const Icon = MODULE_ICONS[mod.iconName] || BookOpen;
                  const isSelected = mod.id === selectedModuleId;
                  return (
                    <button
                      key={mod.id}
                      type="button"
                      onClick={() => handleSelectModule(mod.id)}
                      className={cn(
                        "flex flex-col items-start p-3 rounded-xl border text-left transition-all relative overflow-hidden group",
                        isSelected
                          ? "border-teal-500 bg-teal-500/10 text-teal-900 dark:text-teal-100 shadow-sm ring-1 ring-teal-500"
                          : "border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-[var(--foreground)]"
                      )}
                    >
                      <div className="flex items-center justify-between w-full mb-2">
                        <span
                          className={cn(
                            "p-1.5 rounded-lg",
                            isSelected
                              ? "bg-teal-500 text-white"
                              : "bg-[var(--muted)] text-[var(--muted-foreground)] group-hover:text-[var(--foreground)]"
                          )}
                        >
                          <Icon size={16} />
                        </span>
                        <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]">
                          {mod.group.split(" ")[0]}
                        </span>
                      </div>
                      <span className="text-xs font-semibold leading-tight line-clamp-1">{mod.title}</span>
                      <span className="text-[10px] text-[var(--muted-foreground)] line-clamp-1 mt-0.5">{mod.badge}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Active Module Banner */}
            <div className="p-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                    <ActiveIcon size={26} />
                  </span>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-xl font-bold text-[var(--foreground)]">{activeModule.title}</h2>
                      <Badge color="green">{activeModule.badge}</Badge>
                      <span className="text-xs text-[var(--muted-foreground)]">• Section: {activeModule.group}</span>
                    </div>
                    <p className="text-xs text-[var(--muted-foreground)] mt-1 max-w-3xl">{activeModule.summary}</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="text-left bg-[var(--muted)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
                    <span className="text-[10px] uppercase text-[var(--muted-foreground)] font-semibold block">Workflow Steps</span>
                    <span className="text-sm font-bold text-[var(--foreground)]">{activeModule.workflowSteps.length} Steps</span>
                  </div>
                  <div className="text-left bg-[var(--muted)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
                    <span className="text-[10px] uppercase text-[var(--muted-foreground)] font-semibold block">Checks & Rules</span>
                    <span className="text-sm font-bold text-teal-600 dark:text-teal-400">{totalValidationsCount} Validations</span>
                  </div>
                  <div className="text-left bg-[var(--muted)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
                    <span className="text-[10px] uppercase text-[var(--muted-foreground)] font-semibold block">Troubleshooting</span>
                    <span className="text-sm font-bold text-[var(--foreground)]">{activeModule.troubleshooting.length} Scenarios</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="action-btn text-xs font-medium px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-[var(--foreground)] flex items-center gap-1.5"
                    title="Print standard operating procedures"
                  >
                    <Printer size={15} />
                    <span>Print SOP</span>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-[var(--border)] text-xs">
                <div>
                  <span className="font-semibold text-[var(--foreground)]">Primary User Personas: </span>
                  <span className="text-[var(--muted-foreground)]">{activeModule.primaryUsers.join(" • ")}</span>
                </div>
                <div>
                  <span className="font-semibold text-[var(--foreground)]">Key Business Documents: </span>
                  <span className="text-[var(--muted-foreground)]">{activeModule.keyDocuments.join(" • ")}</span>
                </div>
              </div>
            </div>

            {/* View Mode Tabs */}
            <div className="flex items-center gap-2 border-b border-[var(--border)] overflow-x-auto pb-1">
              <button
                type="button"
                onClick={() => setActiveTab("flowchart")}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors border-b-2 flex items-center gap-2 whitespace-nowrap",
                  activeTab === "flowchart"
                    ? "border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-500/5"
                    : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                <Network size={16} />
                <span>1. Workflow Flowchart & Interconnections</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("manual")}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors border-b-2 flex items-center gap-2 whitespace-nowrap",
                  activeTab === "manual"
                    ? "border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-500/5"
                    : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                <BookOpen size={16} />
                <span>2. Operations Manual & SOP</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("validations")}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors border-b-2 flex items-center gap-2 whitespace-nowrap",
                  activeTab === "validations"
                    ? "border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-500/5"
                    : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                <ShieldCheck size={16} />
                <span>3. Checks & Validations Matrix ({totalValidationsCount})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("troubleshooting")}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors border-b-2 flex items-center gap-2 whitespace-nowrap",
                  activeTab === "troubleshooting"
                    ? "border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-500/5"
                    : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
              >
                <HelpCircle size={16} />
                <span>4. Troubleshooting & FAQs ({activeModule.troubleshooting.length + activeModule.faqs.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("quiz")}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors border-b-2 flex items-center gap-2 whitespace-nowrap",
                  activeTab === "quiz"
                ? "border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-500/5"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            )}
          >
            <Sparkles size={16} />
            <span>5. Knowledge Check & Quiz</span>
          </button>
        </div>

        {/* Tab 1: Workflow Flowchart & Interconnections */}
        {activeTab === "flowchart" && (
          <div className="space-y-6">
            <Panel
              title={`${activeModule.title} — Step-by-Step Workflow Flowchart`}
              subtitle="Click any workflow step to inspect its specific upstream inputs, downstream outputs, and validation checks"
            >
              <div className="p-4 space-y-6">
                {/* Horizontal Step Ribbon */}
                <div className="overflow-x-auto pb-4">
                  <div className="flex items-center gap-3 min-w-[850px] py-2">
                    {activeModule.workflowSteps.map((step, idx) => {
                      const isSelected = selectedStepIndex === idx;
                      return (
                        <React.Fragment key={step.stepNumber}>
                          <div
                            onClick={() => setSelectedStepIndex(idx)}
                            className={cn(
                              "flex-1 min-w-[200px] p-3.5 rounded-xl border cursor-pointer transition-all relative group",
                              isSelected
                                ? "border-teal-600 bg-teal-500/10 shadow-md ring-2 ring-teal-500/50"
                                : "border-[var(--border)] bg-[var(--card)] hover:border-teal-500/40 hover:bg-[var(--accent)]"
                            )}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span
                                className={cn(
                                  "text-[10px] font-bold px-2 py-0.5 rounded-full",
                                  isSelected ? "bg-teal-600 text-white" : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                                )}
                              >
                                Step {step.stepNumber}
                              </span>
                              <span className="text-[10px] font-mono text-[var(--muted-foreground)]">
                                {step.validations.length} checks
                              </span>
                            </div>

                            <h4 className="text-xs font-bold text-[var(--foreground)] line-clamp-1 mb-1">
                              {step.title}
                            </h4>
                            <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-2 mb-2">
                              {step.action}
                            </p>

                            <div className="pt-2 border-t border-[var(--border)] flex flex-col gap-1 text-[10px]">
                              <span className="font-semibold text-teal-600 dark:text-teal-400 truncate">
                                👤 {step.actor}
                              </span>
                              {step.interconnection.upstreamModule && (
                                <span className="text-[9px] text-[var(--muted-foreground)] truncate flex items-center gap-1">
                                  <ArrowUp size={10} className="text-teal-600" />
                                  <span>From: {step.interconnection.upstreamModule}</span>
                                </span>
                              )}
                              {step.interconnection.downstreamModule && (
                                <span className="text-[9px] text-[var(--muted-foreground)] truncate flex items-center gap-1">
                                  <ArrowDown size={10} className="text-blue-600" />
                                  <span>To: {step.interconnection.downstreamModule}</span>
                                </span>
                              )}
                            </div>
                          </div>

                          {idx < activeModule.workflowSteps.length - 1 && (
                            <ArrowRight size={20} className="shrink-0 text-[var(--muted-foreground)] opacity-50" />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>

                {/* Selected Step Inspector Box */}
                {activeStep && (
                  <div className="p-5 rounded-xl border border-teal-500/30 bg-teal-500/[0.02] space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-teal-600 text-white">
                            Step {activeStep.stepNumber} Inspector
                          </span>
                          <h3 className="text-base font-bold text-[var(--foreground)]">{activeStep.title}</h3>
                        </div>
                        <p className="text-xs text-[var(--muted-foreground)] mt-1">{activeStep.action}</p>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--muted-foreground)]">Actor / Role:</span>
                        <code className="text-xs font-mono font-semibold bg-[var(--muted)] px-2 py-1 rounded text-teal-700 dark:text-teal-300">
                          {activeStep.actorRole}
                        </code>
                      </div>
                    </div>

                    {/* Step Upperline vs Downline Connects */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-lg border border-teal-500/20 bg-[var(--card)] space-y-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400 block flex items-center gap-1">
                          <ArrowUp size={12} />
                          <span>Upperline Connect (Input Prerequisites & Triggers)</span>
                        </span>
                        <div className="text-xs font-semibold text-[var(--foreground)]">
                          {activeStep.interconnection.upstreamModule || "None (Initial Step)"}
                        </div>
                        <p className="text-xs text-[var(--muted-foreground)]">
                          {activeStep.interconnection.upstreamEvent || "Manual user initiation"}
                        </p>
                      </div>

                      <div className="p-3.5 rounded-lg border border-blue-500/20 bg-[var(--card)] space-y-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 block flex items-center gap-1">
                          <ArrowDown size={12} />
                          <span>Downline Connect (Output Deliverables & Handoffs)</span>
                        </span>
                        <div className="text-xs font-semibold text-[var(--foreground)]">
                          {activeStep.interconnection.downstreamModule || "Workflow Terminal"}
                        </div>
                        <p className="text-xs text-[var(--muted-foreground)]">
                          {activeStep.interconnection.downstreamEvent || "Completes current operation"}
                        </p>
                      </div>
                    </div>

                    {/* Step Checks & Validations */}
                    <div className="space-y-2">
                      <span className="text-xs font-bold text-[var(--foreground)] flex items-center gap-2">
                        <ShieldCheck size={16} className="text-teal-600" />
                        <span>Checks & Validations Enforced at Step {activeStep.stepNumber}:</span>
                      </span>

                      <div className="grid grid-cols-1 gap-2.5">
                        {activeStep.validations.map((val, vIdx) => (
                          <div
                            key={vIdx}
                            className="p-3 rounded-lg border border-[var(--border)] bg-[var(--card)] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span
                                  className={cn(
                                    "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                                    val.category === "Pre-Condition" && "bg-blue-500/10 text-blue-600 border border-blue-500/20",
                                    val.category === "Business Logic" && "bg-amber-500/10 text-amber-600 border border-amber-500/20",
                                    val.category === "Data Integrity" && "bg-purple-500/10 text-purple-600 border border-purple-500/20",
                                    val.category === "Authorization" && "bg-rose-500/10 text-rose-600 border border-rose-500/20"
                                  )}
                                >
                                  {val.category}
                                </span>
                                <span className="font-semibold text-[var(--foreground)]">{val.check}</span>
                                {val.errorCode && (
                                  <code className="text-[10px] bg-[var(--muted)] px-1 py-0.5 rounded font-mono text-red-600 dark:text-red-400">
                                    {val.errorCode}
                                  </code>
                                )}
                              </div>
                              <p className="text-[var(--muted-foreground)] text-xs">{val.rule}</p>
                            </div>

                            <div className="shrink-0 text-left md:text-right">
                              <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400 block">
                                If Failed:
                              </span>
                              <span className="text-[11px] text-[var(--muted-foreground)]">{val.onFailure}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Cross-Module Integration Matrix Table */}
                <div className="space-y-3 pt-4 border-t border-[var(--border)]">
                  <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                    <Network size={16} className="text-teal-600" />
                    <span>Cross-Module Integration & Ledger Matrix</span>
                  </h3>

                  <div className="overflow-x-auto">
                    <DataTable
                      columns={["Connected Module", "Direction", "Trigger Event", "Data Exchanged", "Ledger / Financial Effect"]}
                    >
                      {activeModule.crossModuleInterconnections.map((link, idx) => (
                        <tr key={idx}>
                          <td className="font-semibold text-teal-600 dark:text-teal-400">{link.targetModule}</td>
                          <td>
                            <Badge color={link.direction === "Inbound" ? "amber" : "green"}>
                              {link.direction}
                            </Badge>
                          </td>
                          <td className="font-medium">{link.trigger}</td>
                          <td className="text-xs text-[var(--muted-foreground)]">{link.dataExchanged}</td>
                          <td className="text-xs font-mono">{link.ledgerEffect || "Data Sync"}</td>
                        </tr>
                      ))}
                    </DataTable>
                  </div>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* Tab 2: Operations Manual & SOP */}
        {activeTab === "manual" && (
          <div className="space-y-6">
            <Panel
              title={`${activeModule.title} — Standard Operating Procedures (SOP)`}
              subtitle="Detailed user walkthrough for day-to-day operations and state machine transition rules"
            >
              <div className="p-4 space-y-6">
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--muted)]/50 text-xs leading-relaxed text-[var(--foreground)]">
                  <div className="flex items-center gap-2 text-sm font-bold mb-1 text-teal-600 dark:text-teal-400">
                    <BookOpen size={16} />
                    <span>Operational Purpose & Policy Guidelines</span>
                  </div>
                  {activeModule.trainingManual.overview}
                </div>

                <div className="space-y-4">
                  <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                    <ClipboardList size={16} className="text-teal-600" />
                    <span>Step-by-Step Execution Guide</span>
                  </h3>

                  <div className="space-y-3">
                    {activeModule.trainingManual.sopWalkthrough.map((sop, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-2 hover:border-teal-500/30 transition-all"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border)] pb-2">
                          <h4 className="text-sm font-bold text-[var(--foreground)]">{sop.step}</h4>
                          <span className="text-xs font-mono bg-teal-500/10 text-teal-700 dark:text-teal-300 px-2.5 py-1 rounded-md border border-teal-500/20">
                            Path: {sop.uiPath}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">{sop.instructions}</p>
                        {sop.proTips && (
                          <div className="flex items-start gap-2 pt-1 text-[11px] text-amber-600 dark:text-amber-400">
                            <Sparkles size={14} className="shrink-0 mt-0.5" />
                            <span>Pro-Tip: {sop.proTips}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-3 pt-4 border-t border-[var(--border)]">
                  <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                    <Layers size={16} className="text-teal-600" />
                    <span>Lifecycle State Machine & Transition Guards</span>
                  </h3>

                  <DataTable columns={["Current Status", "Target Status", "Trigger Action", "Authorized Roles", "Guard Conditions"]}>
                    {activeModule.trainingManual.stateMachine.map((sm, idx) => (
                      <tr key={idx}>
                        <td>
                          <Pill>{sm.fromState}</Pill>
                        </td>
                        <td>
                          <Pill tone="success">{sm.toState}</Pill>
                        </td>
                        <td className="font-semibold text-xs">{sm.action}</td>
                        <td className="text-xs font-mono">{sm.allowedRoles.join(", ")}</td>
                        <td className="text-xs text-[var(--muted-foreground)]">{sm.guardConditions}</td>
                      </tr>
                    ))}
                  </DataTable>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* Tab 3: Checks & Validations Catalog */}
        {activeTab === "validations" && (
          <div className="space-y-6">
            <Panel
              title={`${activeModule.title} — System Checks & Business Rules Catalog`}
              subtitle="All automated validation rules, constraint checks, and database concurrency protections enforced by the ERP"
            >
              <div className="p-4 space-y-6">
                <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
                  <span className="font-semibold text-[var(--muted-foreground)] mr-1">Filter Category:</span>
                  {["All", "Pre-Condition", "Business Logic", "Data Integrity", "Authorization"].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedCategoryFilter(cat)}
                      className={cn(
                        "px-3 py-1.5 rounded-lg font-medium transition-all",
                        selectedCategoryFilter === cat
                          ? "bg-teal-600 text-white"
                          : "bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                      )}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredValidations.map((val, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-3 flex flex-col justify-between"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={cn(
                              "text-[10px] font-semibold px-2 py-0.5 rounded",
                              val.category === "Pre-Condition" && "bg-blue-500/10 text-blue-600 border border-blue-500/20",
                              val.category === "Business Logic" && "bg-amber-500/10 text-amber-600 border border-amber-500/20",
                              val.category === "Data Integrity" && "bg-purple-500/10 text-purple-600 border border-purple-500/20",
                              val.category === "Authorization" && "bg-rose-500/10 text-rose-600 border border-rose-500/20"
                            )}
                          >
                            {val.category}
                          </span>
                          <span className="text-[10px] font-mono text-[var(--muted-foreground)]">
                            Enforced at Step {val.stepNumber}
                          </span>
                        </div>

                        <h4 className="text-sm font-bold text-[var(--foreground)]">{val.check}</h4>
                        <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">{val.rule}</p>
                      </div>

                      <div className="pt-3 border-t border-[var(--border)] flex items-center justify-between text-[11px]">
                        <div>
                          {val.errorCode ? (
                            <code className="bg-[var(--muted)] px-1.5 py-0.5 rounded font-mono text-red-600 dark:text-red-400 font-semibold">
                              {val.errorCode}
                            </code>
                          ) : (
                            <span className="text-[var(--muted-foreground)] font-mono">System Guard</span>
                          )}
                        </div>
                        <span className="text-rose-600 dark:text-rose-400 font-medium text-right truncate max-w-[200px]">
                          {val.onFailure}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-3 pt-4 border-t border-[var(--border)]">
                  <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                    <ShieldAlert size={16} className="text-teal-600" />
                    <span>Security & Policy Enforcement Matrix</span>
                  </h3>

                  <DataTable columns={["Policy Name", "Scope", "Rule Expression / Guard Logic", "Enforcement Severity"]}>
                    {activeModule.trainingManual.validationMatrix.map((mat, idx) => (
                      <tr key={idx}>
                        <td className="font-semibold text-xs">{mat.ruleName}</td>
                        <td className="text-xs text-[var(--muted-foreground)]">{mat.scope}</td>
                        <td className="text-xs font-mono">{mat.validationLogic}</td>
                        <td>
                          <Badge
                            color={
                              mat.enforcementLevel.includes("Hard Block")
                                ? "red"
                                : mat.enforcementLevel.includes("Escalation")
                                ? "amber"
                                : "gray"
                            }
                          >
                            {mat.enforcementLevel}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </DataTable>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* Tab 4: Troubleshooting & FAQs */}
        {activeTab === "troubleshooting" && (
          <div className="space-y-6">
            <Panel
              title={`${activeModule.title} — Common Issues & Troubleshooting Guide`}
              subtitle="Step-by-step diagnostic procedures, error codes, and resolution guides for frontline users"
            >
              <div className="p-4 space-y-4">
                {activeModule.troubleshooting.map((trouble, idx) => {
                  const isExpanded = expandedTroubleIndex === idx;
                  return (
                    <div
                      key={idx}
                      className="border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--card)] transition-all"
                    >
                      <button
                        type="button"
                        onClick={() => setExpandedTroubleIndex(isExpanded ? null : idx)}
                        className="w-full p-4 text-left flex items-start justify-between gap-4 hover:bg-[var(--accent)] transition-colors"
                      >
                        <div className="flex items-start gap-3">
                          <span className="p-1 rounded bg-red-500/10 text-red-600 border border-red-500/20 mt-0.5">
                            <AlertTriangle size={16} />
                          </span>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="text-sm font-bold text-[var(--foreground)]">{trouble.issue}</h4>
                              {trouble.errorCode && (
                                <code className="text-xs font-mono bg-[var(--muted)] text-red-600 dark:text-red-400 px-1.5 py-0.5 rounded font-semibold">
                                  {trouble.errorCode}
                                </code>
                              )}
                            </div>
                            <p className="text-xs text-[var(--muted-foreground)] mt-1">{trouble.symptom}</p>
                          </div>
                        </div>

                        <span className="text-[var(--muted-foreground)]">
                          {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        </span>
                      </button>

                      {isExpanded && (
                        <div className="p-4 pt-2 border-t border-[var(--border)] bg-[var(--muted)]/20 space-y-4 text-xs">
                          <div className="p-3 rounded-lg bg-[var(--muted)]/50 border border-[var(--border)]">
                            <span className="font-semibold text-[var(--foreground)] block mb-1">
                              Root Cause Analysis:
                            </span>
                            <p className="text-[var(--muted-foreground)] leading-relaxed">{trouble.rootCause}</p>
                          </div>

                          <div className="space-y-2">
                            <span className="font-semibold text-teal-600 dark:text-teal-400 block">
                              Step-by-Step Resolution:
                            </span>
                            <ol className="list-decimal list-inside space-y-1.5 text-[var(--foreground)] pl-1">
                              {trouble.stepByStepFix.map((step, sIdx) => (
                                <li key={sIdx} className="leading-relaxed">
                                  {step}
                                </li>
                              ))}
                            </ol>
                          </div>

                          <div className="pt-2 border-t border-[var(--border)] flex items-start gap-2 text-[11px] text-amber-600 dark:text-amber-400">
                            <ShieldCheck size={15} className="shrink-0 mt-0.5" />
                            <span>Proactive Prevention Tip: {trouble.preventionTip}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Panel>

            <Panel
              title={`${activeModule.title} — Frequently Asked Questions (FAQs)`}
              subtitle="Direct answers to frequent operational, compliance, and procedural questions"
            >
              <div className="p-4 space-y-3">
                {activeModule.faqs.map((faq, idx) => {
                  const isExpanded = expandedFaqIndex === idx;
                  return (
                    <div
                      key={idx}
                      className="border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--card)]"
                    >
                      <button
                        type="button"
                        onClick={() => setExpandedFaqIndex(isExpanded ? null : idx)}
                        className="w-full p-4 text-left flex items-center justify-between gap-4 hover:bg-[var(--accent)] transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <HelpCircle size={16} className="text-teal-600 shrink-0" />
                          <span className="text-xs font-bold text-[var(--foreground)]">{faq.question}</span>
                        </div>
                        <span className="text-[var(--muted-foreground)]">
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </span>
                      </button>

                      {isExpanded && (
                        <div className="p-4 pt-1 border-t border-[var(--border)] bg-[var(--muted)]/20 text-xs text-[var(--muted-foreground)] leading-relaxed">
                          {faq.answer}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>
        )}

        {/* Tab 5: Knowledge Check & Quiz */}
        {activeTab === "quiz" && (
          <div className="space-y-6">
            <Panel
              title={`${activeModule.title} — Knowledge Check & Certification Quiz`}
              subtitle="Interactive evaluation to test operational mastery for trainees and new hires"
            >
              <div className="p-4 space-y-6">
                {activeModule.quiz.map((q, qIdx) => {
                  const selectedOpt = quizAnswers[qIdx];
                  const isAnswered = selectedOpt !== undefined;
                  const isCorrect = isAnswered && selectedOpt === q.correctIndex;

                  return (
                    <div
                      key={qIdx}
                      className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <h4 className="text-sm font-bold text-[var(--foreground)]">
                          Question {qIdx + 1}: {q.question}
                        </h4>
                        {quizSubmitted && (
                          <span>
                            {isCorrect ? (
                              <Badge color="green">Correct</Badge>
                            ) : (
                              <Badge color="red">Incorrect</Badge>
                            )}
                          </span>
                        )}
                      </div>

                      <div className="space-y-2">
                        {q.options.map((opt, optIdx) => {
                          const isOptSelected = selectedOpt === optIdx;
                          return (
                            <label
                              key={optIdx}
                              onClick={() => {
                                if (quizSubmitted) return;
                                setQuizAnswers((prev) => ({ ...prev, [qIdx]: optIdx }));
                              }}
                              className={cn(
                                "flex items-center gap-3 p-3 rounded-lg border text-xs cursor-pointer transition-all",
                                isOptSelected
                                  ? "border-teal-500 bg-teal-500/10 text-teal-900 dark:text-teal-100 font-medium"
                                  : "border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] text-[var(--foreground)]"
                              )}
                            >
                              <input
                                type="radio"
                                name={`quiz-${qIdx}`}
                                checked={isOptSelected}
                                onChange={() => {}}
                                className="accent-teal-600"
                              />
                              <span>{opt}</span>
                            </label>
                          );
                        })}
                      </div>

                      {quizSubmitted && (
                        <div
                          className={cn(
                            "p-3 rounded-lg text-xs border leading-relaxed",
                            isCorrect
                              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-200"
                              : "bg-red-500/10 border-red-500/30 text-red-800 dark:text-red-200"
                          )}
                        >
                          <span className="font-bold block mb-1">
                            {isCorrect ? "✓ Well Done!" : "✕ Explanation:"}
                          </span>
                          {q.explanation}
                        </div>
                      )}
                    </div>
                  );
                })}

                <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                  <div>
                    {quizSubmitted && (
                      <div className="text-sm font-bold text-teal-600 dark:text-teal-400">
                        Score: {calculateQuizScore()} of {activeModule.quiz.length} Correct (
                        {Math.round((calculateQuizScore() / activeModule.quiz.length) * 100)}%)
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    {quizSubmitted ? (
                      <ActionButton
                        onClick={() => {
                          setQuizAnswers({});
                          setQuizSubmitted(false);
                        }}
                      >
                        Retake Quiz
                      </ActionButton>
                    ) : (
                      <ActionButton
                        disabled={Object.keys(quizAnswers).length < activeModule.quiz.length}
                        onClick={() => setQuizSubmitted(true)}
                      >
                        Submit & Check Answers
                      </ActionButton>
                    )}
                  </div>
                </div>
              </div>
            </Panel>
          </div>
        )}
      </div>
    )}
  </div>
</Shell>
  );
}
