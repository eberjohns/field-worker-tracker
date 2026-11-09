import React, { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  Search,
  Filter,
  Layers,
  CheckSquare,
  Square,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Shield,
  UserPlus,
  Home,
  X,
} from "lucide-react";

interface Employee {
  id: string;
  tally_id: string;
  name: string;
  role: string;
  staff_grade_description: string | null;
  grade_code: string | null;
  weekly_off_day: string | null;
  is_driver: boolean;
  country: string;
  accommodation_id?: string | null;
  is_active: boolean;
  version: number;
}

interface SupervisorGroup {
  supervisor: Employee;
  superintendents: Employee[];
  engineers: Employee[];
  members: Employee[];
}

interface LeaderWithStats {
  employee: Employee;
  crewsCount: number;
  workersCount: number;
}

interface HierarchyNode {
  employee: Employee;
  relationship?: string | null;
  subordinates?: HierarchyNode[];
}

export const Employees: React.FC = () => {
  const { token, user } = useAuth();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [accommodationFilter, setAccommodationFilter] = useState<string>("");
  const [groupBySupervisor, setGroupBySupervisor] = useState(true);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Hierarchy grouping state
  const [supervisorGroups, setSupervisorGroups] = useState<SupervisorGroup[]>([]);
  const [allSupervisors, setAllSupervisors] = useState<Employee[]>([]);
  const [superintendentsList, setSuperintendentsList] = useState<LeaderWithStats[]>([]);
  const [engineersList, setEngineersList] = useState<LeaderWithStats[]>([]);
  const [directMembers, setDirectMembers] = useState<Employee[]>([]);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
    unassigned: true, // Direct staff collapsed by default to keep page focused
  });

  // Focus & filter by leader
  const [focusedLeaderId, setFocusedLeaderId] = useState<string | null>(null);
  const [filterLeaderId, setFilterLeaderId] = useState<string | null>(null);

  // Bulk update dialog state
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [bulkWeeklyOff, setBulkWeeklyOff] = useState("");
  const [bulkBreak, setBulkBreak] = useState<number | "">("");
  const [bulkLoading, setBulkLoading] = useState(false);

  // Create employee dialog state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [accommodations, setAccommodations] = useState<
    Array<{ id: string; name: string; code: string }>
  >([]);
  const [createFormData, setCreateFormData] = useState({
    tally_id: "",
    name: "",
    role: "WORKER",
    country: "AE",
    staff_grade_description: "Landscape Gardener",
    grade_code: "",
    weekly_off_day: "FRIDAY",
    is_driver: false,
    break_override_minutes: "" as number | "",
    phone: "",
    email: "",
    accommodation_id: "",
    join_date: "",
    supervisor_id: "",
    superintendent_id: "",
    engineer_id: "",
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  const fetchEmployees = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "1000");
      if (search) params.set("q", search);
      if (roleFilter) params.set("role", roleFilter);
      if (accommodationFilter === "assigned") params.set("has_accommodation", "true");
      else if (accommodationFilter === "unassigned") params.set("has_accommodation", "false");
      else if (accommodationFilter) params.set("accommodation_id", accommodationFilter);

      const res = await fetch(`/api/v1/employees?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        // Exclude system bootstrap ADMIN001 from operational employee views
        const filtered = data.filter((e: any) => e.tally_id !== "ADMIN001" && e.role !== "ADMIN");
        setEmployees(filtered);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHierarchy = async () => {
    try {
      const res = await fetch("/api/v1/employees/hierarchy", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const tree: HierarchyNode[] = await res.json();

        const allEmps = new Map<string, Employee>();
        const supsMap = new Map<
          string,
          {
            emp: Employee;
            supts: Map<string, Employee>;
            engs: Map<string, Employee>;
            members: Map<string, Employee>;
          }
        >();
        const allSuptsMap = new Map<string, Employee>();
        const allEngsMap = new Map<string, Employee>();
        const assignedWorkerIds = new Set<string>();

        const processNode = (node: HierarchyNode, parent?: Employee, rel?: string | null) => {
          const emp = node.employee;
          if (!emp || emp.tally_id === "ADMIN001" || emp.role === "ADMIN") return;
          allEmps.set(emp.id, emp);

          if (emp.role === "ENGINEER") {
            allEngsMap.set(emp.id, emp);
          } else if (emp.role === "SUPERINTENDENT") {
            allSuptsMap.set(emp.id, emp);
          } else if (emp.role === "SUPERVISOR") {
            if (!supsMap.has(emp.id)) {
              supsMap.set(emp.id, {
                emp,
                supts: new Map(),
                engs: new Map(),
                members: new Map(),
              });
            }
          }

          if (parent && rel) {
            if (rel === "ENGINEER" && parent.role === "ENGINEER") {
              if (emp.role === "SUPERVISOR") {
                if (!supsMap.has(emp.id)) {
                  supsMap.set(emp.id, {
                    emp,
                    supts: new Map(),
                    engs: new Map(),
                    members: new Map(),
                  });
                }
                supsMap.get(emp.id)!.engs.set(parent.id, parent);
              }
            } else if (rel === "SUPERINTENDENT" && parent.role === "SUPERINTENDENT") {
              if (emp.role === "SUPERVISOR") {
                if (!supsMap.has(emp.id)) {
                  supsMap.set(emp.id, {
                    emp,
                    supts: new Map(),
                    engs: new Map(),
                    members: new Map(),
                  });
                }
                supsMap.get(emp.id)!.supts.set(parent.id, parent);
              }
            } else if (rel === "SUPERVISOR") {
              const pId = parent.id;
              if (!supsMap.has(pId)) {
                supsMap.set(pId, {
                  emp: parent,
                  supts: new Map(),
                  engs: new Map(),
                  members: new Map(),
                });
              }
              supsMap.get(pId)!.members.set(emp.id, emp);
              assignedWorkerIds.add(emp.id);
            }
          }

          if (node.subordinates && node.subordinates.length > 0) {
            for (const child of node.subordinates) {
              processNode(child, emp, child.relationship);
            }
          }
        };

        for (const root of tree) {
          processNode(root);
        }

        // Build groups array
        const groups: SupervisorGroup[] = [];
        for (const [_, supData] of supsMap) {
          groups.push({
            supervisor: supData.emp,
            superintendents: Array.from(supData.supts.values()),
            engineers: Array.from(supData.engs.values()),
            members: Array.from(supData.members.values()),
          });
        }

        // Sort groups by supervisor name
        groups.sort((a, b) => a.supervisor.name.localeCompare(b.supervisor.name));
        setSupervisorGroups(groups);
        setAllSupervisors(groups.map((g) => g.supervisor));

        // Collect leadership with stats
        const suptsWithStats: LeaderWithStats[] = Array.from(allSuptsMap.values()).map((supt) => {
          let crews = 0;
          let workers = 0;
          for (const g of groups) {
            if (g.superintendents.some((s) => s.id === supt.id)) {
              crews++;
              workers += g.members.length;
            }
          }
          return { employee: supt, crewsCount: crews, workersCount: workers };
        });
        suptsWithStats.sort((a, b) => a.employee.name.localeCompare(b.employee.name));
        setSuperintendentsList(suptsWithStats);

        const engsWithStats: LeaderWithStats[] = Array.from(allEngsMap.values()).map((eng) => {
          let crews = 0;
          let workers = 0;
          for (const g of groups) {
            if (g.engineers.some((e) => e.id === eng.id)) {
              crews++;
              workers += g.members.length;
            }
          }
          return { employee: eng, crewsCount: crews, workersCount: workers };
        });
        engsWithStats.sort((a, b) => a.employee.name.localeCompare(b.employee.name));
        setEngineersList(engsWithStats);

        // Direct / unassigned staff
        const direct: Employee[] = [];
        for (const [eId, emp] of allEmps) {
          if (
            !assignedWorkerIds.has(eId) &&
            !supsMap.has(eId) &&
            !allSuptsMap.has(eId) &&
            !allEngsMap.has(eId)
          ) {
            direct.push(emp);
          }
        }
        direct.sort((a, b) => a.name.localeCompare(b.name));
        setDirectMembers(direct);
      }
    } catch (err) {
      console.error("Failed to load hierarchy:", err);
    }
  };

  const fetchAccommodations = async () => {
    try {
      const res = await fetch("/api/v1/accommodations", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setAccommodations(await res.json());
    } catch (err) {
      console.error("Failed to load accommodations:", err);
    }
  };

  useEffect(() => {
    fetchEmployees();
    fetchHierarchy();
    fetchAccommodations();
  }, [search, roleFilter, accommodationFilter]);

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError(null);

    const trimmedTallyId = createFormData.tally_id.trim();
    const trimmedName = createFormData.name.trim();

    if (!trimmedTallyId || !trimmedName) {
      setCreateError("Tally ID and Full Name are required.");
      setCreateLoading(false);
      return;
    }

    try {
      const payload: any = {
        tally_id: trimmedTallyId,
        name: trimmedName,
        role: createFormData.role,
        country: createFormData.country,
        staff_grade_description: createFormData.staff_grade_description.trim() || null,
        grade_code: createFormData.grade_code.trim() || null,
        weekly_off_day: createFormData.weekly_off_day || null,
        is_driver: createFormData.is_driver,
        phone: createFormData.phone.trim() || null,
        email: createFormData.email.trim() || null,
        accommodation_id: createFormData.accommodation_id || null,
        break_override_minutes:
          createFormData.break_override_minutes !== ""
            ? Number(createFormData.break_override_minutes)
            : null,
        join_date: createFormData.join_date || null,
      };

      const res = await fetch("/api/v1/employees", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.message || `Creation failed (${res.status})`);
      }

      const created = await res.json();

      // Assign reporting lines if selected
      const reportingPromises = [];
      if (createFormData.supervisor_id && createFormData.role === "WORKER") {
        reportingPromises.push(
          fetch(`/api/v1/employees/${created.id}/reporting-lines`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              manager_id: createFormData.supervisor_id,
              relationship: "SUPERVISOR",
            }),
          })
        );
      }
      if (createFormData.superintendent_id) {
        reportingPromises.push(
          fetch(`/api/v1/employees/${created.id}/reporting-lines`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              manager_id: createFormData.superintendent_id,
              relationship: "SUPERINTENDENT",
            }),
          })
        );
      }
      if (createFormData.engineer_id) {
        reportingPromises.push(
          fetch(`/api/v1/employees/${created.id}/reporting-lines`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              manager_id: createFormData.engineer_id,
              relationship: "ENGINEER",
            }),
          })
        );
      }
      if (reportingPromises.length > 0) {
        await Promise.all(reportingPromises);
      }

      setCreateModalOpen(false);
      setSuccessToast(`Employee ${created.name} (${created.tally_id}) created successfully!`);
      setTimeout(() => setSuccessToast(null), 5000);

      // Reset form
      setCreateFormData({
        tally_id: "",
        name: "",
        role: "WORKER",
        country: "AE",
        staff_grade_description: "Landscape Gardener",
        grade_code: "",
        weekly_off_day: "FRIDAY",
        is_driver: false,
        break_override_minutes: "",
        phone: "",
        email: "",
        accommodation_id: "",
        join_date: "",
        supervisor_id: "",
        superintendent_id: "",
        engineer_id: "",
      });

      await fetchEmployees();
      await fetchHierarchy();
    } catch (err: any) {
      setCreateError(err.message || "Failed to create employee.");
    } finally {
      setCreateLoading(false);
    }
  };

  const toggleGroupCollapse = (managerId: string) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [managerId]: !prev[managerId],
    }));
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const scrollToLeader = (leaderId: string) => {
    setFocusedLeaderId(leaderId);
    const el = document.getElementById(`mgmt-${leaderId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    // Highlight for 3.5 seconds
    setTimeout(() => {
      setFocusedLeaderId((prev) => (prev === leaderId ? null : prev));
    }, 3500);
  };

  const handleBulkUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBulkLoading(true);
    try {
      const res = await fetch("/api/v1/employees/bulk-update", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          employee_ids: selectedIds,
          changes: {
            weekly_off_day: bulkWeeklyOff || null,
            break_override_minutes: bulkBreak !== "" ? Number(bulkBreak) : null,
          },
        }),
      });
      if (res.ok) {
        setBulkModalOpen(false);
        setSelectedIds([]);
        fetchEmployees();
        fetchHierarchy();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setBulkLoading(false);
    }
  };

  // Filtered supervisor groups based on active leader filter
  const visibleSupervisorGroups = supervisorGroups.filter((g) => {
    if (!filterLeaderId) return true;
    return (
      g.superintendents.some((s) => s.id === filterLeaderId) ||
      g.engineers.some((e) => e.id === filterLeaderId)
    );
  });

  const activeLeader =
    filterLeaderId &&
    [...superintendentsList, ...engineersList].find((l) => l.employee.id === filterLeaderId);

  // Overall metric counts
  const totalEmployeesCount = employees.length;
  const suptsCount = employees.filter((e) => e.role === "SUPERINTENDENT").length;
  const engsCount = employees.filter((e) => e.role === "ENGINEER").length;
  const supsCount = employees.filter((e) => e.role === "SUPERVISOR").length;
  const workersCount = employees.filter((e) => e.role === "WORKER").length;

  const accMap = new Map(accommodations.map((a) => [a.id, a]));
  const availableSupervisors =
    allSupervisors.length > 0 ? allSupervisors : employees.filter((e) => e.role === "SUPERVISOR");
  const availableSuperintendents =
    superintendentsList.length > 0
      ? superintendentsList.map((s) => s.employee)
      : employees.filter((e) => e.role === "SUPERINTENDENT");
  const availableEngineers =
    engineersList.length > 0
      ? engineersList.map((e) => e.employee)
      : employees.filter((e) => e.role === "ENGINEER");
  const withAccommodationCount = employees.filter((e) => !!e.accommodation_id).length;
  const withoutAccommodationCount = employees.filter((e) => !e.accommodation_id).length;

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Employees & People</h2>
          <p className="text-sm text-slate-500 mt-1">
            Supervisor crews, leadership oversight, and operational staff profiles
          </p>
        </div>

        <div className="flex items-center gap-3">
          {selectedIds.length > 0 && (user?.role === "ADMIN" || user?.role === "ENGINEER") && (
            <button
              onClick={() => setBulkModalOpen(true)}
              className="px-3.5 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 transition shadow-xs"
            >
              Bulk Update ({selectedIds.length})
            </button>
          )}

          {(user?.role === "ADMIN" || !user?.role) && (
            <button
              onClick={() => {
                setCreateError(null);
                setCreateModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition shadow-xs"
            >
              <UserPlus className="h-4 w-4" />
              Add Employee
            </button>
          )}

          <button
            onClick={() => setGroupBySupervisor(!groupBySupervisor)}
            className={`flex items-center gap-2 px-3 py-2 border rounded-lg text-sm font-medium transition shadow-xs ${
              groupBySupervisor
                ? "bg-indigo-50 border-indigo-200 text-indigo-700 font-semibold"
                : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
          >
            <Layers className="h-4 w-4" />
            {groupBySupervisor ? "Grouped by Supervisor" : "Flat Table"}
          </button>
        </div>
      </div>

      {/* Success Toast */}
      {successToast && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl flex items-center justify-between shadow-xs">
          <span className="font-medium">{successToast}</span>
          <button
            onClick={() => setSuccessToast(null)}
            className="text-emerald-600 hover:text-emerald-800 p-1"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* High-Level Organization Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Total Staff
          </span>
          <p className="text-2xl font-bold text-slate-900 mt-0.5">{totalEmployeesCount}</p>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-purple-700 uppercase tracking-wider">
            Superintendents
          </span>
          <p className="text-2xl font-bold text-purple-900 mt-0.5">{suptsCount}</p>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-blue-700 uppercase tracking-wider">
            Engineers
          </span>
          <p className="text-2xl font-bold text-blue-900 mt-0.5">{engsCount}</p>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">
            Supervisors
          </span>
          <p className="text-2xl font-bold text-amber-900 mt-0.5">{supsCount}</p>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">
            Field Workers
          </span>
          <p className="text-2xl font-bold text-emerald-900 mt-0.5">{workersCount}</p>
        </div>
      </div>

      {/* Leadership & Oversight Section (Superintendents & Engineers shown singly above) */}
      {groupBySupervisor && (superintendentsList.length > 0 || engineersList.length > 0) && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-indigo-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Leadership & Field Oversight (Superintendents & Engineers)
              </h3>
            </div>
            <span className="text-xs text-slate-400">
              Click a card to filter groups below · Click chips in supervisor rows to focus here
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {/* Superintendents */}
            {superintendentsList.map(({ employee: supt, crewsCount, workersCount }) => {
              const isFocused = focusedLeaderId === supt.id;
              const isFiltering = filterLeaderId === supt.id;
              return (
                <div
                  key={supt.id}
                  id={`mgmt-${supt.id}`}
                  onClick={() => setFilterLeaderId(isFiltering ? null : supt.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isFocused
                      ? "ring-2 ring-indigo-500 bg-indigo-50/80 border-indigo-300 scale-[1.01]"
                      : isFiltering
                      ? "bg-purple-50/80 border-purple-400 ring-2 ring-purple-300"
                      : "bg-slate-50/70 border-slate-200 hover:bg-slate-100/70"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <Link
                          to="/employees/$employeeId"
                          params={{ employeeId: supt.id }}
                          onClick={(e) => e.stopPropagation()}
                          className="font-bold text-sm text-slate-900 hover:text-indigo-600 hover:underline"
                        >
                          {supt.name}
                        </Link>
                        <span className="text-xs font-mono text-slate-500">({supt.tally_id})</span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 uppercase">
                          Superintendent
                        </span>
                        {supt.grade_code && (
                          <span className="text-[11px] font-mono px-1 py-0.5 bg-slate-200/80 rounded text-slate-700">
                            {supt.grade_code}
                          </span>
                        )}
                        {supt.staff_grade_description && (
                          <span className="text-[11px] text-slate-500">
                            • {supt.staff_grade_description}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-white border border-slate-200 text-slate-700 shadow-2xs">
                        {crewsCount} crew{crewsCount === 1 ? "" : "s"} · {workersCount} wkr
                        {workersCount === 1 ? "" : "s"}
                      </span>
                      {isFiltering && (
                        <p className="text-[10px] font-bold text-purple-700 mt-1">
                          ✓ Filtering below
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Engineers */}
            {engineersList.map(({ employee: eng, crewsCount, workersCount }) => {
              const isFocused = focusedLeaderId === eng.id;
              const isFiltering = filterLeaderId === eng.id;
              return (
                <div
                  key={eng.id}
                  id={`mgmt-${eng.id}`}
                  onClick={() => setFilterLeaderId(isFiltering ? null : eng.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isFocused
                      ? "ring-2 ring-indigo-500 bg-indigo-50/80 border-indigo-300 scale-[1.01]"
                      : isFiltering
                      ? "bg-blue-50/80 border-blue-400 ring-2 ring-blue-300"
                      : "bg-slate-50/70 border-slate-200 hover:bg-slate-100/70"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <Link
                          to="/employees/$employeeId"
                          params={{ employeeId: eng.id }}
                          onClick={(e) => e.stopPropagation()}
                          className="font-bold text-sm text-slate-900 hover:text-indigo-600 hover:underline"
                        >
                          {eng.name}
                        </Link>
                        <span className="text-xs font-mono text-slate-500">({eng.tally_id})</span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 uppercase">
                          Engineer
                        </span>
                        {eng.grade_code && (
                          <span className="text-[11px] font-mono px-1 py-0.5 bg-slate-200/80 rounded text-slate-700">
                            {eng.grade_code}
                          </span>
                        )}
                        {eng.staff_grade_description && (
                          <span className="text-[11px] text-slate-500">
                            • {eng.staff_grade_description}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-white border border-slate-200 text-slate-700 shadow-2xs">
                        {crewsCount} crew{crewsCount === 1 ? "" : "s"} · {workersCount} wkr
                        {workersCount === 1 ? "" : "s"}
                      </span>
                      {isFiltering && (
                        <p className="text-[10px] font-bold text-blue-700 mt-1">
                          ✓ Filtering below
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Active Filter Banner */}
      {filterLeaderId && activeLeader && (
        <div className="flex items-center justify-between bg-indigo-50 border border-indigo-200 px-4 py-2.5 rounded-lg text-sm text-indigo-900">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-indigo-600" />
            <span>
              Showing supervisor groups overseen by{" "}
              <strong>
                {activeLeader.employee.name} ({activeLeader.employee.role})
              </strong>
            </span>
          </div>
          <button
            onClick={() => setFilterLeaderId(null)}
            className="flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:text-indigo-900 bg-white px-2.5 py-1 rounded border border-indigo-200 hover:bg-indigo-100 transition"
          >
            <X className="h-3.5 w-3.5" />
            Clear Filter
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="relative flex-1">
          <Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name or Tally ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="border border-slate-200 rounded-lg text-sm px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Roles</option>
            <option value="ADMIN">Admin</option>
            <option value="ENGINEER">Engineer</option>
            <option value="SUPERINTENDENT">Superintendent</option>
            <option value="SUPERVISOR">Supervisor</option>
            <option value="WORKER">Worker</option>
          </select>
        </div>

        {/* Accommodation Filter */}
        <div className="flex items-center gap-2">
          <Home className="h-4 w-4 text-slate-400" />
          <select
            value={accommodationFilter}
            onChange={(e) => setAccommodationFilter(e.target.value)}
            className="border border-slate-200 rounded-lg text-sm px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Accommodations ({employees.length})</option>
            <option value="assigned">With Camp ({withAccommodationCount})</option>
            <option value="unassigned">Without Camp / Self ({withoutAccommodationCount})</option>
            {accommodations.length > 0 && (
              <optgroup label="Specific Camps">
                {accommodations.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({acc.code})
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>

        <button
          onClick={() => {
            fetchEmployees();
            fetchHierarchy();
          }}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600 transition"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading employees...</div>
        ) : employees.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">No employees found.</div>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-4 w-12">
                  <span className="sr-only">Select</span>
                </th>
                <th className="p-4">Tally ID</th>
                <th className="p-4">Name</th>
                <th className="p-4">Role</th>
                <th className="p-4">Staff Grade (SGD)</th>
                <th className="p-4">Grade Code</th>
                <th className="p-4">Weekly Off</th>
                <th className="p-4">Accommodation</th>
                <th className="p-4">Country</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {groupBySupervisor ? (
                <>
                  {/* Supervisor Groups */}
                  {visibleSupervisorGroups.map((group) => {
                    const isCollapsed = collapsedGroups[group.supervisor.id];
                    const filteredMembers = group.members.filter((m) => {
                      if (search) {
                        const q = search.toLowerCase();
                        if (!m.name.toLowerCase().includes(q) && !m.tally_id.toLowerCase().includes(q)) {
                          return false;
                        }
                      }
                      if (roleFilter && m.role !== roleFilter) return false;
                      if (accommodationFilter === "assigned" && !m.accommodation_id) return false;
                      if (accommodationFilter === "unassigned" && m.accommodation_id) return false;
                      if (
                        accommodationFilter &&
                        accommodationFilter !== "assigned" &&
                        accommodationFilter !== "unassigned" &&
                        m.accommodation_id !== accommodationFilter
                      ) {
                        return false;
                      }
                      return true;
                    });

                    return (
                      <React.Fragment key={group.supervisor.id}>
                        {/* Group Header: Grouped by Supervisor */}
                        <tr
                          onClick={() => toggleGroupCollapse(group.supervisor.id)}
                          className="bg-slate-100/90 hover:bg-slate-200/80 cursor-pointer font-semibold text-xs text-slate-800 transition select-none"
                        >
                          <td colSpan={10} className="px-4 py-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              {/* Left: Supervisor Information */}
                              <div className="flex items-center gap-2.5">
                                {isCollapsed ? (
                                  <ChevronRight className="h-4 w-4 text-slate-500 flex-shrink-0" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-slate-500 flex-shrink-0" />
                                )}
                                <div className="flex items-center gap-2 flex-wrap">
                                  <Link
                                    to="/employees/$employeeId"
                                    params={{ employeeId: group.supervisor.id }}
                                    onClick={(e) => e.stopPropagation()}
                                    className="font-bold text-slate-900 text-sm hover:text-indigo-600 hover:underline"
                                  >
                                    {group.supervisor.name}
                                  </Link>
                                  <span className="font-mono text-xs text-slate-500">
                                    ({group.supervisor.tally_id})
                                  </span>
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">
                                    Supervisor
                                  </span>
                                  {group.supervisor.grade_code && (
                                    <span className="font-mono text-[11px] px-1.5 py-0.5 bg-slate-200 rounded text-slate-700">
                                      {group.supervisor.grade_code}
                                    </span>
                                  )}
                                  {group.supervisor.staff_grade_description && (
                                    <span className="text-[11px] text-slate-600 italic">
                                      • {group.supervisor.staff_grade_description}
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Right: Site Superintendent, Engineer & Worker count */}
                              <div
                                className="flex items-center gap-2.5 flex-wrap"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {group.superintendents.length > 0 && (
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] font-semibold uppercase text-slate-400">
                                      Supt:
                                    </span>
                                    {group.superintendents.map((s) => (
                                      <button
                                        key={s.id}
                                        type="button"
                                        onClick={() => scrollToLeader(s.id)}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 transition shadow-2xs"
                                        title={`Click to focus on Superintendent ${s.name}`}
                                      >
                                        <span className="font-semibold">{s.name}</span>
                                        <span className="text-[10px] opacity-75 font-mono">
                                          ({s.tally_id})
                                        </span>
                                      </button>
                                    ))}
                                  </div>
                                )}

                                {group.engineers.length > 0 && (
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] font-semibold uppercase text-slate-400">
                                      Eng:
                                    </span>
                                    {group.engineers.map((eng) => (
                                      <button
                                        key={eng.id}
                                        type="button"
                                        onClick={() => scrollToLeader(eng.id)}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition shadow-2xs"
                                        title={`Click to focus on Engineer ${eng.name}`}
                                      >
                                        <span className="font-semibold">{eng.name}</span>
                                        <span className="text-[10px] opacity-75 font-mono">
                                          ({eng.tally_id})
                                        </span>
                                      </button>
                                    ))}
                                  </div>
                                )}

                                <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-white border border-slate-200 text-slate-700 shadow-2xs">
                                  {filteredMembers.length} team member
                                  {filteredMembers.length === 1 ? "" : "s"}
                                </span>
                              </div>
                            </div>
                          </td>
                        </tr>

                        {/* Members inside the supervisor group */}
                        {!isCollapsed &&
                          (filteredMembers.length === 0 ? (
                            <tr>
                              <td colSpan={10} className="px-8 py-3 text-xs text-slate-400 italic">
                                No matching team members in this supervisor group.
                              </td>
                            </tr>
                          ) : (
                            filteredMembers.map((m) => {
                              const isSelected = selectedIds.includes(m.id);
                              return (
                                <tr key={m.id} className="hover:bg-slate-50 transition">
                                  <td className="p-4">
                                    <button
                                      onClick={() => toggleSelect(m.id)}
                                      className="text-slate-400 hover:text-indigo-600"
                                    >
                                      {isSelected ? (
                                        <CheckSquare className="h-4 w-4 text-indigo-600" />
                                      ) : (
                                        <Square className="h-4 w-4" />
                                      )}
                                    </button>
                                  </td>
                                  <td className="p-4 font-mono font-medium text-slate-900">
                                    <div className="flex items-center gap-1.5 pl-4">
                                      <span className="text-slate-300 font-mono">└</span>
                                      <Link
                                        to="/employees/$employeeId"
                                        params={{ employeeId: m.id }}
                                        className="text-indigo-600 hover:underline"
                                      >
                                        {m.tally_id}
                                      </Link>
                                    </div>
                                  </td>
                                  <td className="p-4 font-medium text-slate-900">{m.name}</td>
                                  <td className="p-4">
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                      {m.role}
                                    </span>
                                  </td>
                                  <td className="p-4">{m.staff_grade_description || "—"}</td>
                                  <td className="p-4 font-mono text-xs">{m.grade_code || "—"}</td>
                                  <td className="p-4">{m.weekly_off_day || "SUNDAY"}</td>
                                  <td className="p-4 text-xs">
                                    {m.accommodation_id && accMap.has(m.accommodation_id) ? (
                                      <span className="inline-flex items-center gap-1 font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                        <Home className="h-3 w-3 text-emerald-600" />
                                        {accMap.get(m.accommodation_id)?.name}
                                      </span>
                                    ) : (
                                      <span className="text-slate-400 italic">Self / None</span>
                                    )}
                                  </td>
                                  <td className="p-4">
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100">
                                      {m.country}
                                    </span>
                                  </td>
                                  <td className="p-4">
                                    <span
                                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                        m.is_active
                                          ? "bg-emerald-50 text-emerald-700"
                                          : "bg-red-50 text-red-700"
                                      }`}
                                    >
                                      {m.is_active ? "Active" : "Inactive"}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })
                          ))}
                      </React.Fragment>
                    );
                  })}

                  {/* Direct / Independent Staff (unassigned to a supervisor) */}
                  {directMembers.length > 0 && !filterLeaderId && (
                    <React.Fragment key="unassigned">
                      <tr
                        onClick={() => toggleGroupCollapse("unassigned")}
                        className="bg-slate-50 hover:bg-slate-100 cursor-pointer font-semibold text-xs text-slate-700 transition select-none"
                      >
                        <td colSpan={10} className="px-4 py-2.5">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {collapsedGroups["unassigned"] ? (
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-slate-400" />
                              )}
                              <span className="font-bold text-slate-800">
                                Direct / Independent Staff
                              </span>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700 uppercase">
                                Unassigned
                              </span>
                            </div>
                            <span className="text-slate-500 font-normal">
                              {directMembers.length} staff member
                              {directMembers.length === 1 ? "" : "s"}
                            </span>
                          </div>
                        </td>
                      </tr>
                      {!collapsedGroups["unassigned"] &&
                        directMembers
                          .filter((m) => {
                            if (search) {
                              const q = search.toLowerCase();
                              if (!m.name.toLowerCase().includes(q) && !m.tally_id.toLowerCase().includes(q)) {
                                return false;
                              }
                            }
                            if (roleFilter && m.role !== roleFilter) return false;
                            if (accommodationFilter === "assigned" && !m.accommodation_id) return false;
                            if (accommodationFilter === "unassigned" && m.accommodation_id) return false;
                            if (
                              accommodationFilter &&
                              accommodationFilter !== "assigned" &&
                              accommodationFilter !== "unassigned" &&
                              m.accommodation_id !== accommodationFilter
                            ) {
                              return false;
                            }
                            return true;
                          })
                          .map((m) => {
                            const isSelected = selectedIds.includes(m.id);
                            return (
                              <tr key={m.id} className="hover:bg-slate-50 transition">
                                <td className="p-4">
                                  <button
                                    onClick={() => toggleSelect(m.id)}
                                    className="text-slate-400 hover:text-indigo-600"
                                  >
                                    {isSelected ? (
                                      <CheckSquare className="h-4 w-4 text-indigo-600" />
                                    ) : (
                                      <Square className="h-4 w-4" />
                                    )}
                                  </button>
                                </td>
                                <td className="p-4 font-mono font-medium text-slate-900">
                                  <div className="flex items-center gap-1.5 pl-4">
                                    <span className="text-slate-300 font-mono">└</span>
                                    <Link
                                      to="/employees/$employeeId"
                                      params={{ employeeId: m.id }}
                                      className="text-indigo-600 hover:underline"
                                    >
                                      {m.tally_id}
                                    </Link>
                                  </div>
                                </td>
                                <td className="p-4 font-medium text-slate-900">{m.name}</td>
                                <td className="p-4">
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                    {m.role}
                                  </span>
                                </td>
                                <td className="p-4">{m.staff_grade_description || "—"}</td>
                                <td className="p-4 font-mono text-xs">{m.grade_code || "—"}</td>
                                <td className="p-4">{m.weekly_off_day || "SUNDAY"}</td>
                                <td className="p-4 text-xs">
                                  {m.accommodation_id && accMap.has(m.accommodation_id) ? (
                                    <span className="inline-flex items-center gap-1 font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                      <Home className="h-3 w-3 text-emerald-600" />
                                      {accMap.get(m.accommodation_id)?.name}
                                    </span>
                                  ) : (
                                    <span className="text-slate-400 italic">Self / None</span>
                                  )}
                                </td>
                                <td className="p-4">
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100">
                                    {m.country}
                                  </span>
                                </td>
                                <td className="p-4">
                                  <span
                                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                      m.is_active
                                        ? "bg-emerald-50 text-emerald-700"
                                        : "bg-red-50 text-red-700"
                                    }`}
                                  >
                                    {m.is_active ? "Active" : "Inactive"}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                    </React.Fragment>
                  )}
                </>
              ) : (
                /* Flat Table */
                employees.map((emp) => {
                  const isSelected = selectedIds.includes(emp.id);
                  return (
                    <tr key={emp.id} className="hover:bg-slate-50 transition">
                      <td className="p-4">
                        <button
                          onClick={() => toggleSelect(emp.id)}
                          className="text-slate-400 hover:text-indigo-600"
                        >
                          {isSelected ? (
                            <CheckSquare className="h-4 w-4 text-indigo-600" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                        </button>
                      </td>
                      <td className="p-4 font-mono font-medium text-slate-900">
                        <Link
                          to="/employees/$employeeId"
                          params={{ employeeId: emp.id }}
                          className="text-indigo-600 hover:underline"
                        >
                          {emp.tally_id}
                        </Link>
                      </td>
                      <td className="p-4 font-medium text-slate-900">{emp.name}</td>
                      <td className="p-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                          {emp.role}
                        </span>
                      </td>
                      <td className="p-4">{emp.staff_grade_description || "—"}</td>
                      <td className="p-4 font-mono text-xs">{emp.grade_code || "—"}</td>
                      <td className="p-4">{emp.weekly_off_day || "SUNDAY"}</td>
                      <td className="p-4 text-xs">
                        {emp.accommodation_id && accMap.has(emp.accommodation_id) ? (
                          <span className="inline-flex items-center gap-1 font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            <Home className="h-3 w-3 text-emerald-600" />
                            {accMap.get(emp.accommodation_id)?.name}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Self / None</span>
                        )}
                      </td>
                      <td className="p-4">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100">
                          {emp.country}
                        </span>
                      </td>
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            emp.is_active
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-red-50 text-red-700"
                          }`}
                        >
                          {emp.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Bulk Update Modal */}
      {bulkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-lg border border-slate-200 max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Bulk Update {selectedIds.length} Employee(s)
            </h3>
            <p className="text-xs text-slate-500">
              Update accommodation, break override, or weekly off day for the selected workers.
            </p>

            <form onSubmit={handleBulkUpdate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Weekly Off Day</label>
                <select
                  value={bulkWeeklyOff}
                  onChange={(e) => setBulkWeeklyOff(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="">Leave Unchanged</option>
                  <option value="SUNDAY">Sunday</option>
                  <option value="MONDAY">Monday</option>
                  <option value="TUESDAY">Tuesday</option>
                  <option value="WEDNESDAY">Wednesday</option>
                  <option value="THURSDAY">Thursday</option>
                  <option value="FRIDAY">Friday</option>
                  <option value="SATURDAY">Saturday</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Break Override (Minutes)
                </label>
                <input
                  type="number"
                  placeholder="e.g. 60"
                  value={bulkBreak}
                  onChange={(e) => setBulkBreak(e.target.value ? Number(e.target.value) : "")}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setBulkModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={bulkLoading}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
                >
                  {bulkLoading ? "Saving..." : "Apply Updates"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Employee Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <UserPlus className="h-5 w-5 text-indigo-600" />
                  Add New Employee
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Creates employee profile and linked user account with default password.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCreateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {createError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateEmployee} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Tally / Employee ID <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 1205 or W_101"
                    value={createFormData.tally_id}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, tally_id: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Full Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Mohammad Ali"
                    value={createFormData.name}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, name: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Role</label>
                  <select
                    value={createFormData.role}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, role: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="WORKER">Field Worker (Mobile)</option>
                    <option value="SUPERVISOR">Supervisor</option>
                    <option value="SUPERINTENDENT">Superintendent</option>
                    <option value="ENGINEER">Engineer</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Country</label>
                  <select
                    value={createFormData.country}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, country: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="AE">United Arab Emirates (AE)</option>
                    <option value="SA">Saudi Arabia (SA)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Trade / Designation
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Landscape Gardener"
                    value={createFormData.staff_grade_description}
                    onChange={(e) =>
                      setCreateFormData({
                        ...createFormData,
                        staff_grade_description: e.target.value,
                      })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Grade Code</label>
                  <input
                    type="text"
                    placeholder="e.g. SGD_12"
                    value={createFormData.grade_code}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, grade_code: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Weekly Off Day
                  </label>
                  <select
                    value={createFormData.weekly_off_day}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, weekly_off_day: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="FRIDAY">Friday (Standard UAE)</option>
                    <option value="SATURDAY">Saturday</option>
                    <option value="SUNDAY">Sunday</option>
                    <option value="MONDAY">Monday</option>
                    <option value="TUESDAY">Tuesday</option>
                    <option value="WEDNESDAY">Wednesday</option>
                    <option value="THURSDAY">Thursday</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Assigned Accommodation
                  </label>
                  <select
                    value={createFormData.accommodation_id}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, accommodation_id: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">None / Self Accommodation</option>
                    {accommodations.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.name} ({acc.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Phone</label>
                  <input
                    type="tel"
                    placeholder="+971 50 123 4567"
                    value={createFormData.phone}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, phone: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Email</label>
                  <input
                    type="email"
                    placeholder="worker@company.com"
                    value={createFormData.email}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, email: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Join Date</label>
                  <input
                    type="date"
                    value={createFormData.join_date}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, join_date: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Break Override (Minutes)
                  </label>
                  <input
                    type="number"
                    placeholder="e.g. 60"
                    value={createFormData.break_override_minutes}
                    onChange={(e) =>
                      setCreateFormData({
                        ...createFormData,
                        break_override_minutes: e.target.value ? Number(e.target.value) : "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-lg p-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              {/* Reporting & Leadership Oversight Section */}
              <div className="border-t border-slate-100 pt-3 space-y-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                  <Shield className="h-4 w-4 text-indigo-600" />
                  <span>Reporting Lines & Leadership Oversight (Optional)</span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Assign reporting lines directly upon creation. These relationships can also be viewed and edited later in the employee profile.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {createFormData.role === "WORKER" && (
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">
                        Supervisor (Crew Lead)
                      </label>
                      <select
                        value={createFormData.supervisor_id}
                        onChange={(e) =>
                          setCreateFormData({ ...createFormData, supervisor_id: e.target.value })
                        }
                        className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">None / Direct</option>
                        {availableSupervisors.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name} ({s.tally_id})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {createFormData.role !== "ENGINEER" && (
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">
                        Superintendent
                      </label>
                      <select
                        value={createFormData.superintendent_id}
                        onChange={(e) =>
                          setCreateFormData({
                            ...createFormData,
                            superintendent_id: e.target.value,
                          })
                        }
                        className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">None</option>
                        {availableSuperintendents.map((supt) => (
                          <option key={supt.id} value={supt.id}>
                            {supt.name} ({supt.tally_id})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Project Engineer
                    </label>
                    <select
                      value={createFormData.engineer_id}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, engineer_id: e.target.value })
                      }
                      className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">None</option>
                      {availableEngineers.map((eng) => (
                        <option key={eng.id} value={eng.id}>
                          {eng.name} ({eng.tally_id})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="pt-1">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={createFormData.is_driver}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, is_driver: e.target.checked })
                    }
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Designated Driver (eligible for site transport runs)</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition shadow-xs"
                >
                  {createLoading ? "Creating Employee..." : "Create Employee"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
