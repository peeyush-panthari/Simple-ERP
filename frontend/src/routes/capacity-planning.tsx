import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRightLeft,
  Calendar,
  Clock,
  Plus,
  RefreshCw,
} from "lucide-react";
import { Shell } from "@/components/erp/shell";
import {
  ActionButton,
  DataTable,
  Field,
  Modal,
  PageHeader,
  Panel,
  Pill,
  StatCard,
  TableRow,
  TextInput,
} from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { date as formatDate, money } from "@/lib/format";

interface WorkCenterItem {
  id: string;
  code: string;
  name: string;
  department: string;
  warehouse_id: string | null;
  warehouse_name: string;
  daily_capacity_hours: number;
  efficiency_factor: number;
  hourly_machine_rate: number;
  hourly_labor_rate: number;
  status: string;
  weekly_effective_capacity: number;
  weekly_booked_hours: number;
  utilization_pct: number;
  is_overloaded: boolean;
  notes: string | null;
}

interface ScheduleItem {
  id: string;
  work_center_id: string;
  work_center_code: string;
  work_center_name: string;
  department: string;
  production_run_id: string | null;
  production_run_number: string | null;
  task_name: string;
  schedule_date: string;
  shift: string;
  required_hours: number;
  status: string;
  is_overloaded: boolean;
  daily_booked_hours: number;
  daily_capacity_hours: number;
  notes: string | null;
}

interface RccpWeek {
  week_num: number;
  start_date: string;
  end_date: string;
  capacity_hours: number;
  load_hours: number;
  load_percentage: number;
  is_overloaded: boolean;
}

interface RccpStation {
  work_center_id: string;
  code: string;
  name: string;
  department: string;
  weekly_capacity_hours: number;
  weeks: RccpWeek[];
}

export default function CapacityPlanningPage() {
  const { api } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"work_centers" | "schedule" | "rccp">("work_centers");
  const [selectedWcId, setSelectedWcId] = useState<string>("all");

  // Modals
  const [showCreateWcModal, setShowCreateWcModal] = useState(false);
  const [showScheduleJobModal, setShowScheduleJobModal] = useState(false);
  const [reassignScheduleId, setReassignScheduleId] = useState<string | null>(null);

  // Form states - Create Work Center
  const [wcCode, setWcCode] = useState("");
  const [wcName, setWcName] = useState("");
  const [wcDepartment, setWcDepartment] = useState("Assembly & Pack");
  const [dailyCapacityHours, setDailyCapacityHours] = useState<string>("16");
  const [efficiencyFactor, setEfficiencyFactor] = useState<string>("0.85");
  const [hourlyMachineRate, setHourlyMachineRate] = useState<string>("750");
  const [hourlyLaborRate, setHourlyLaborRate] = useState<string>("350");
  const [isSubmittingWc, setIsSubmittingWc] = useState(false);

  // Form states - Schedule Job
  const [schedWcId, setSchedWcId] = useState("");
  const [schedTaskName, setSchedTaskName] = useState("");
  const [schedDate, setSchedDate] = useState(new Date().toISOString().slice(0, 10));
  const [schedShift, setSchedShift] = useState("day");
  const [schedRequiredHours, setSchedRequiredHours] = useState<string>("4");
  const [schedNotes, setSchedNotes] = useState("");
  const [isSubmittingSched, setIsSubmittingSched] = useState(false);

  // Form states - Reassign Job
  const [targetWcId, setTargetWcId] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [targetShift, setTargetShift] = useState("day");
  const [isSubmittingReassign, setIsSubmittingReassign] = useState(false);

  // 1. Fetch Work Centers
  const { data: wcData, isLoading: wcLoading, refetch: refetchWc } = useQuery<{ work_centers: WorkCenterItem[] }>({
    queryKey: ["capacity-work-centers"],
    queryFn: async () => {
      return await api<{ work_centers: WorkCenterItem[] }>("GET", "/api/v1/capacity-planning/work-centers");
    },
  });

  // 2. Fetch Job Schedules
  const { data: schedData, isLoading: schedLoading, refetch: refetchSched } = useQuery<{ schedules: ScheduleItem[] }>({
    queryKey: ["capacity-schedules", selectedWcId],
    queryFn: async () => {
      const qs = selectedWcId !== "all" ? `?work_center_id=${selectedWcId}` : "";
      return await api<{ schedules: ScheduleItem[] }>("GET", `/api/v1/capacity-planning/schedule${qs}`);
    },
  });

  // 3. Fetch RCCP 4-Week Radar
  const { data: rccpData, isLoading: rccpLoading, refetch: refetchRccp } = useQuery<{ rccp_matrix: RccpStation[] }>({
    queryKey: ["capacity-rccp-summary"],
    queryFn: async () => {
      return await api<{ rccp_matrix: RccpStation[] }>("GET", "/api/v1/capacity-planning/rccp-summary");
    },
  });

  const workCenters = wcData?.work_centers || [];
  const schedules = schedData?.schedules || [];
  const rccpStations = rccpData?.rccp_matrix || [];

  // Metrics
  const activeWcCount = workCenters.filter((w) => w.status === "active").length;
  const totalWeeklyCap = workCenters.reduce((sum, w) => sum + w.weekly_effective_capacity, 0);
  const overloadedCount = workCenters.filter((w) => w.is_overloaded).length;
  const avgEfficiency = workCenters.length
    ? Math.round((workCenters.reduce((sum, w) => sum + w.efficiency_factor, 0) / workCenters.length) * 100)
    : 85;

  // Actions
  const handleCreateWorkCenter = async () => {
    if (!wcCode.trim() || !wcName.trim()) {
      alert("Please enter work center code and name.");
      return;
    }
    setIsSubmittingWc(true);
    try {
      await api("POST", "/api/v1/capacity-planning/work-centers", {
        json: {
          code: wcCode.trim(),
          name: wcName.trim(),
          department: wcDepartment,
          daily_capacity_hours: parseFloat(dailyCapacityHours) || 16.0,
          efficiency_factor: parseFloat(efficiencyFactor) || 0.85,
          hourly_machine_rate: parseFloat(hourlyMachineRate) || 750.0,
          hourly_labor_rate: parseFloat(hourlyLaborRate) || 350.0,
          status: "active",
        },
      });
      setShowCreateWcModal(false);
      setWcCode("");
      setWcName("");
      qc.invalidateQueries({ queryKey: ["capacity-work-centers"] });
      qc.invalidateQueries({ queryKey: ["capacity-rccp-summary"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to register work center.";
      alert(message);
    } finally {
      setIsSubmittingWc(false);
    }
  };

  const handleScheduleJob = async () => {
    if (!schedWcId || !schedTaskName.trim() || !schedRequiredHours) {
      alert("Please select a work center, task name, and required hours.");
      return;
    }
    setIsSubmittingSched(true);
    try {
      await api("POST", "/api/v1/capacity-planning/schedule", {
        json: {
          work_center_id: schedWcId,
          task_name: schedTaskName.trim(),
          schedule_date: schedDate,
          shift: schedShift,
          required_hours: parseFloat(schedRequiredHours) || 4.0,
          notes: schedNotes || null,
        },
      });
      setShowScheduleJobModal(false);
      setSchedTaskName("");
      setSchedNotes("");
      qc.invalidateQueries({ queryKey: ["capacity-schedules"] });
      qc.invalidateQueries({ queryKey: ["capacity-work-centers"] });
      qc.invalidateQueries({ queryKey: ["capacity-rccp-summary"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to schedule job.";
      alert(message);
    } finally {
      setIsSubmittingSched(false);
    }
  };

  const handleReassignJob = async () => {
    if (!reassignScheduleId || !targetWcId) {
      alert("Please select target alternate work center.");
      return;
    }
    setIsSubmittingReassign(true);
    try {
      await api("POST", `/api/v1/capacity-planning/schedule/${reassignScheduleId}/reassign`, {
        json: {
          target_work_center_id: targetWcId,
          target_date: targetDate || null,
          target_shift: targetShift || null,
        },
      });
      setReassignScheduleId(null);
      setTargetWcId("");
      qc.invalidateQueries({ queryKey: ["capacity-schedules"] });
      qc.invalidateQueries({ queryKey: ["capacity-work-centers"] });
      qc.invalidateQueries({ queryKey: ["capacity-rccp-summary"] });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to reassign job.";
      alert(message);
    } finally {
      setIsSubmittingReassign(false);
    }
  };

  return (
    <Shell>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Work Center Finite Capacity Planning & RCCP"
          description="Machine and assembly cell finite capacity scheduling, rough-cut bottleneck overload radar, and shift balancing"
          actions={
            <div className="flex items-center gap-2">
              <ActionButton
                tone="ghost"
                onClick={() => {
                  refetchWc();
                  refetchSched();
                  refetchRccp();
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </ActionButton>
              {activeTab === "work_centers" && (
                <ActionButton tone="primary" onClick={() => setShowCreateWcModal(true)}>
                  <Plus className="mr-1 h-4 w-4" /> Register Work Center
                </ActionButton>
              )}
              {activeTab === "schedule" && (
                <ActionButton tone="primary" onClick={() => setShowScheduleJobModal(true)}>
                  <Plus className="mr-1 h-4 w-4" /> Schedule Job
                </ActionButton>
              )}
            </div>
          }
        />

        {/* Top KPIs */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Active Work Centers"
            value={activeWcCount.toString()}
            hint="Production cells across assembly floors"
          />
          <StatCard
            label="Weekly Network Capacity"
            value={`${Math.round(totalWeeklyCap)} hrs`}
            hint="Effective net hours (factoring efficiency)"
          />
          <StatCard
            label="Overloaded Bottlenecks"
            value={overloadedCount.toString()}
            hint={overloadedCount > 0 ? "Requires load leveling / subcontracting" : "All stations within capacity limits"}
          />
          <StatCard
            label="Plant Operational Efficiency"
            value={`${avgEfficiency}%`}
            hint="Average machine & labor OEE factor"
          />
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)]">
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "work_centers"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("work_centers")}
          >
            Work Center Capacity Matrix
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "schedule"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("schedule")}
          >
            Job Schedules & Bottleneck Resolution
          </button>
          <button
            type="button"
            className={`border-b-2 px-4 py-2 font-medium text-sm transition-colors ${
              activeTab === "rccp"
                ? "border-blue-700 text-blue-700 dark:border-blue-400 dark:text-blue-300 font-semibold"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
            onClick={() => setActiveTab("rccp")}
          >
            Rough-Cut Capacity Planning (RCCP) 4-Week Radar
          </button>
        </div>

        {/* TAB 1: Work Center Capacity Matrix */}
        {activeTab === "work_centers" && (
          <Panel
            title="Manufacturing Work Centers & Stations"
            aside={
              <ActionButton tone="primary" onClick={() => setShowCreateWcModal(true)}>
                <Plus className="mr-1 h-4 w-4" /> Add Work Center
              </ActionButton>
            }
          >
            {wcLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading work centers...</div>
            ) : workCenters.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">
                No work centers configured yet. Add manufacturing machines and lines.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Station Code & Name",
                  "Department / Floor",
                  "Daily Capacity",
                  "Efficiency (OEE)",
                  "Hourly Rates (Machine / Labor)",
                  "Current Week Load",
                  "Status",
                ]}
              >
                {workCenters.map((wc) => (
                  <TableRow
                    key={wc.id}
                    cells={[
                      <div>
                        <div className="font-semibold text-sm">{wc.name}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{wc.code}</div>
                      </div>,
                      <div>
                        <div className="font-medium text-sm">{wc.department}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">{wc.warehouse_name}</div>
                      </div>,
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-4 w-4 text-[var(--muted-foreground)]" />
                        <span className="font-medium text-sm">{wc.daily_capacity_hours} hrs/day</span>
                      </div>,
                      <div>
                        <span className="font-semibold">{Math.round(wc.efficiency_factor * 100)}%</span>
                        <div className="text-xs text-[var(--muted-foreground)]">Rated Factor</div>
                      </div>,
                      <div>
                        <div className="text-sm">
                          {money(wc.hourly_machine_rate)} <span className="text-xs text-[var(--muted-foreground)]">/ machine-hr</span>
                        </div>
                        <div className="text-xs text-[var(--muted-foreground)]">
                          {money(wc.hourly_labor_rate)} / labor-hr
                        </div>
                      </div>,
                      <div className="w-48">
                        <div className="flex justify-between text-xs mb-1">
                          <span>{wc.weekly_booked_hours}h booked</span>
                          <span
                            className={
                              wc.is_overloaded ? "font-bold text-red-500" : "font-semibold text-[var(--foreground)]"
                            }
                          >
                            {wc.utilization_pct}%
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                          <div
                            className={`h-full ${
                              wc.is_overloaded
                                ? "bg-red-500"
                                : wc.utilization_pct >= 85
                                ? "bg-amber-500"
                                : "bg-green-500"
                            }`}
                            style={{ width: `${Math.min(wc.utilization_pct, 100)}%` }}
                          />
                        </div>
                      </div>,
                      <Pill tone={wc.is_overloaded ? "destructive" : wc.status === "active" ? "success" : "muted"}>
                        {wc.is_overloaded ? "OVERLOADED" : wc.status.toUpperCase()}
                      </Pill>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 2: Job Schedules & Bottlenecks */}
        {activeTab === "schedule" && (
          <Panel
            title="Scheduled Operations & Shift Sequence"
            aside={
              <div className="flex items-center gap-3">
                <select
                  value={selectedWcId}
                  onChange={(e) => setSelectedWcId(e.target.value)}
                  className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm"
                >
                  <option value="all">All Work Centers</option>
                  {workCenters.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} - {w.name}
                    </option>
                  ))}
                </select>
                <ActionButton tone="primary" onClick={() => setShowScheduleJobModal(true)}>
                  <Plus className="mr-1 h-4 w-4" /> Schedule Job
                </ActionButton>
              </div>
            }
          >
            {schedLoading ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">Loading job schedules...</div>
            ) : schedules.length === 0 ? (
              <div className="p-8 text-center text-[var(--muted-foreground)]">
                No jobs scheduled on selected station. Schedule a work order operation.
              </div>
            ) : (
              <DataTable
                columns={[
                  "Task / Operation",
                  "Station",
                  "Schedule Date & Shift",
                  "Duration",
                  "Daily Station Load",
                  "Status",
                  "Actions",
                ]}
              >
                {schedules.map((s) => (
                  <TableRow
                    key={s.id}
                    cells={[
                      <div>
                        <div className="font-semibold text-sm">{s.task_name}</div>
                        {s.production_run_number && (
                          <div className="font-mono text-xs text-[var(--muted-foreground)]">
                            Run: {s.production_run_number}
                          </div>
                        )}
                      </div>,
                      <div>
                        <div className="font-medium text-sm">{s.work_center_name}</div>
                        <div className="font-mono text-xs text-[var(--muted-foreground)]">{s.work_center_code}</div>
                      </div>,
                      <div>
                        <div className="flex items-center gap-1.5 font-medium text-sm">
                          <Calendar className="h-4 w-4 text-blue-500" />
                          <span>{formatDate(s.schedule_date)}</span>
                        </div>
                        <div className="text-xs capitalize text-[var(--muted-foreground)]">{s.shift} Shift</div>
                      </div>,
                      <div className="font-semibold">{s.required_hours} hrs</div>,
                      <div>
                        <div className="text-xs">
                          {s.daily_booked_hours}h / {s.daily_capacity_hours}h limit
                        </div>
                        {s.is_overloaded && (
                          <div className="flex items-center gap-1 text-xs font-semibold text-red-500">
                            <AlertTriangle className="h-3 w-3" />
                            <span>Bottleneck Overload</span>
                          </div>
                        )}
                      </div>,
                      <Pill tone={s.is_overloaded ? "destructive" : "success"}>
                        {s.is_overloaded ? "OVERLOADED" : s.status.toUpperCase()}
                      </Pill>,
                      <div>
                        <ActionButton
                          size="sm"
                          tone={s.is_overloaded ? "danger" : "ghost"}
                          onClick={() => {
                            setReassignScheduleId(s.id);
                            setTargetWcId(s.work_center_id);
                            setTargetDate(s.schedule_date);
                            setTargetShift(s.shift);
                          }}
                        >
                          <ArrowRightLeft className="mr-1 h-3.5 w-3.5" /> Reassign Station
                        </ActionButton>
                      </div>,
                    ]}
                  />
                ))}
              </DataTable>
            )}
          </Panel>
        )}

        {/* TAB 3: RCCP 4-Week Radar */}
        {activeTab === "rccp" && (
          <Panel title="Rough-Cut Capacity Planning (RCCP) Multi-Week Loading Radar">
            <div className="flex flex-col gap-6">
              <p className="text-sm text-[var(--muted-foreground)]">
                Rough-Cut Capacity Planning aggregates total manufacturing load across 4 consecutive planning weeks,
                detecting machine over-utilization prior to MRP run release.
              </p>

              {rccpLoading ? (
                <div className="p-8 text-center text-[var(--muted-foreground)]">Evaluating RCCP matrix...</div>
              ) : rccpStations.length === 0 ? (
                <div className="p-8 text-center text-[var(--muted-foreground)]">No active work centers to evaluate.</div>
              ) : (
                <div className="flex flex-col gap-4">
                  {rccpStations.map((station) => (
                    <div
                      key={station.work_center_id}
                      className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
                        <div>
                          <span className="font-bold text-base">{station.name}</span>
                          <span className="ml-2 font-mono text-xs text-[var(--muted-foreground)]">({station.code})</span>
                          <div className="text-xs text-[var(--muted-foreground)]">{station.department}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-[var(--muted-foreground)]">Net Capacity</div>
                          <div className="font-bold text-sm">{station.weekly_capacity_hours} hrs/week</div>
                        </div>
                      </div>

                      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {station.weeks.map((wk) => (
                          <div
                            key={wk.week_num}
                            className={`rounded-md border p-3 ${
                              wk.is_overloaded
                                ? "border-red-300 bg-red-50/50 dark:border-red-900/60 dark:bg-red-950/20"
                                : wk.load_percentage >= 80
                                ? "border-amber-300 bg-amber-50/50 dark:border-amber-900/60 dark:bg-amber-950/20"
                                : "border-[var(--border)] bg-[var(--background)]"
                            }`}
                          >
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-semibold">Week {wk.week_num}</span>
                              <span
                                className={`font-bold font-mono ${
                                  wk.is_overloaded
                                    ? "text-red-600 dark:text-red-400"
                                    : wk.load_percentage >= 80
                                    ? "text-amber-600 dark:text-amber-400"
                                    : "text-green-600 dark:text-green-400"
                                }`}
                              >
                                {wk.load_percentage}%
                              </span>
                            </div>
                            <div className="mt-1 text-xs text-[var(--muted-foreground)]">
                              {wk.load_hours}h booked / {wk.capacity_hours}h cap
                            </div>
                            <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                              <div
                                className={`h-full ${
                                  wk.is_overloaded
                                    ? "bg-red-500"
                                    : wk.load_percentage >= 80
                                    ? "bg-amber-500"
                                    : "bg-green-500"
                                }`}
                                style={{ width: `${Math.min(wk.load_percentage, 100)}%` }}
                              />
                            </div>
                            {wk.is_overloaded && (
                              <div className="mt-2 flex items-center gap-1 text-[11px] font-semibold text-red-600 dark:text-red-400">
                                <AlertTriangle className="h-3 w-3" />
                                <span>Bottleneck: Exceeds Capacity</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Panel>
        )}

        {/* Modal: Create Work Center */}
        {showCreateWcModal && (
          <Modal open={showCreateWcModal} title="Register Manufacturing Work Center" onClose={() => setShowCreateWcModal(false)}>
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Work Center Code *">
                  <TextInput
                    value={wcCode}
                    onChange={(e) => setWcCode(e.target.value)}
                    placeholder="e.g. WC-WELD-01"
                  />
                </Field>
                <Field label="Station Name *">
                  <TextInput
                    value={wcName}
                    onChange={(e) => setWcName(e.target.value)}
                    placeholder="e.g. Ultrasonic Pack Welder"
                  />
                </Field>
              </div>

              <Field label="Department / Process Area">
                <TextInput
                  value={wcDepartment}
                  onChange={(e) => setWcDepartment(e.target.value)}
                  placeholder="e.g. Battery Cell Module Assembly"
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Daily Capacity (Hours/Day) *">
                  <TextInput
                    type="number"
                    value={dailyCapacityHours}
                    onChange={(e) => setDailyCapacityHours(e.target.value)}
                  />
                </Field>
                <Field label="Efficiency Factor (0.10 - 1.00) *">
                  <TextInput
                    type="number"
                    step="0.05"
                    value={efficiencyFactor}
                    onChange={(e) => setEfficiencyFactor(e.target.value)}
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Hourly Machine Rate (₹)">
                  <TextInput
                    type="number"
                    value={hourlyMachineRate}
                    onChange={(e) => setHourlyMachineRate(e.target.value)}
                  />
                </Field>
                <Field label="Hourly Labor Rate (₹)">
                  <TextInput
                    type="number"
                    value={hourlyLaborRate}
                    onChange={(e) => setHourlyLaborRate(e.target.value)}
                  />
                </Field>
              </div>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setShowCreateWcModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleCreateWorkCenter} disabled={isSubmittingWc}>
                  {isSubmittingWc ? "Registering..." : "Create Work Center"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}

        {/* Modal: Schedule Job */}
        {showScheduleJobModal && (
          <Modal open={showScheduleJobModal} title="Schedule Work Order Job Operation" onClose={() => setShowScheduleJobModal(false)}>
            <div className="flex flex-col gap-4">
              <Field label="Work Center Machine *">
                <select
                  value={schedWcId}
                  onChange={(e) => setSchedWcId(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">-- Select Work Center --</option>
                  {workCenters.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} - {w.name}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Operation / Task Name *">
                <TextInput
                  value={schedTaskName}
                  onChange={(e) => setSchedTaskName(e.target.value)}
                  placeholder="e.g. SMT Surface Mount Soldering Run 42"
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Schedule Date *">
                  <TextInput type="date" value={schedDate} onChange={(e) => setSchedDate(e.target.value)} />
                </Field>
                <Field label="Assigned Shift *">
                  <select
                    value={schedShift}
                    onChange={(e) => setSchedShift(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="day">Day Shift (08:00 - 16:30)</option>
                    <option value="evening">Evening Shift (16:30 - 01:00)</option>
                    <option value="night">Night Shift (01:00 - 08:00)</option>
                  </select>
                </Field>
              </div>

              <Field label="Required Machine Hours *">
                <TextInput
                  type="number"
                  step="0.5"
                  value={schedRequiredHours}
                  onChange={(e) => setSchedRequiredHours(e.target.value)}
                  placeholder="e.g. 4.5"
                />
              </Field>

              <Field label="Scheduling Notes">
                <TextInput
                  value={schedNotes}
                  onChange={(e) => setSchedNotes(e.target.value)}
                  placeholder="e.g. Priority dispatch for OEM EV client batch"
                />
              </Field>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setShowScheduleJobModal(false)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleScheduleJob} disabled={isSubmittingSched}>
                  {isSubmittingSched ? "Scheduling..." : "Schedule Job"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}

        {/* Modal: Reassign Bottleneck Job */}
        {reassignScheduleId && (
          <Modal open={!!reassignScheduleId} title="Reassign Job to Alternate Work Center" onClose={() => setReassignScheduleId(null)}>
            <div className="flex flex-col gap-4">
              <p className="text-sm text-[var(--muted-foreground)]">
                Level machine load and eliminate station bottlenecks by routing this operation to an alternate
                work center line or shifting to an adjacent production day.
              </p>

              <Field label="Target Alternate Work Center *">
                <select
                  value={targetWcId}
                  onChange={(e) => setTargetWcId(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">-- Select Alternate Station --</option>
                  {workCenters.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} - {w.name} ({w.weekly_booked_hours}h booked)
                    </option>
                  ))}
                </select>
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Rescheduled Date (Optional)">
                  <TextInput type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
                </Field>
                <Field label="Shift (Optional)">
                  <select
                    value={targetShift}
                    onChange={(e) => setTargetShift(e.target.value)}
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                  >
                    <option value="day">Day Shift</option>
                    <option value="evening">Evening Shift</option>
                    <option value="night">Night Shift</option>
                  </select>
                </Field>
              </div>

              <div className="mt-4 flex justify-end gap-2">
                <ActionButton tone="ghost" onClick={() => setReassignScheduleId(null)}>
                  Cancel
                </ActionButton>
                <ActionButton tone="primary" onClick={handleReassignJob} disabled={isSubmittingReassign}>
                  {isSubmittingReassign ? "Reassigning..." : "Reassign & Rebalance Load"}
                </ActionButton>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </Shell>
  );
}
