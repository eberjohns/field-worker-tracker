import React, { useState, useEffect } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  User as UserIcon,
  GitFork,
  FileText,
  Smartphone,
  History,
  ArrowLeft,
  KeyRound,
  Trash2,
  Plus,
  AlertCircle,
  CheckCircle,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Download,
  ShieldAlert,
  Pencil,
  PowerOff,
  RotateCcw,
  Eye,
  EyeOff,
  AlertTriangle,
  X,
  Loader2,
} from "lucide-react";

export const EmployeeDetail: React.FC = () => {
  const { employeeId } = useParams({ strict: false }) as { employeeId: string };
  const { token, user } = useAuth();

  const [employee, setEmployee] = useState<any>(null);
  const [accommodations, setAccommodations] = useState<any[]>([]);
  const [reportingLines, setReportingLines] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [salaryHistory, setSalaryHistory] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"profile" | "salary" | "hierarchy" | "documents" | "device" | "history">("profile");
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Profile edit state
  const [editWeeklyOff, setEditWeeklyOff] = useState("");
  const [editBreakOverride, setEditBreakOverride] = useState<number | "">("");
  const [editPhone, setEditPhone] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editAccommodationId, setEditAccommodationId] = useState("");

  // Add document state
  const [newDocType, setNewDocType] = useState("VISA");
  const [newDocExpiry, setNewDocExpiry] = useState("");

  // Hierarchy editing state (Admin only)
  const [allManagers, setAllManagers] = useState<any[]>([]);
  const [newRelType, setNewRelType] = useState<"SUPERVISOR" | "SUPERINTENDENT" | "ENGINEER">("SUPERVISOR");
  const [newManagerId, setNewManagerId] = useState("");
  const [savingHierarchy, setSavingHierarchy] = useState(false);

  // Batch 4: Hierarchy Violations Modal (Admin only)
  const [violationsModalOpen, setViolationsModalOpen] = useState(false);
  const [hierarchyViolations, setHierarchyViolations] = useState<any[]>([]);
  const [loadingViolations, setLoadingViolations] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Phase 13 DSAR and Consent actions
  const [exportingDsar, setExportingDsar] = useState(false);
  const [withdrawingConsent, setWithdrawingConsent] = useState(false);

  // Batch 3: Change Tally ID (Admin only)
  const [tallyModalOpen, setTallyModalOpen] = useState(false);
  const [newTallyId, setNewTallyId] = useState("");
  const [tallyReason, setTallyReason] = useState("");
  const [tallyCheck, setTallyCheck] = useState<any | null>(null);
  const [checkingTally, setCheckingTally] = useState(false);
  const [confirmReuse, setConfirmReuse] = useState(false);
  const [submittingTally, setSubmittingTally] = useState(false);
  const [tallyModalError, setTallyModalError] = useState<string | null>(null);

  // Batch 3: Deactivate / Reactivate Employee (Admin only)
  const [deactivateModalOpen, setDeactivateModalOpen] = useState(false);
  const [deactivateEffectiveDate, setDeactivateEffectiveDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [deactivateReason, setDeactivateReason] = useState("");
  const [deactivateConfirmText, setDeactivateConfirmText] = useState("");
  const [deactivatePassword, setDeactivatePassword] = useState("");
  const [showDeactivatePassword, setShowDeactivatePassword] = useState(false);
  const [deactivateImpact, setDeactivateImpact] = useState<any | null>(null);
  const [loadingImpact, setLoadingImpact] = useState(false);
  const [submittingDeactivate, setSubmittingDeactivate] = useState(false);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  const [reactivateModalOpen, setReactivateModalOpen] = useState(false);
  const [reactivateReason, setReactivateReason] = useState("");
  const [reactivateConfirmText, setReactivateConfirmText] = useState("");
  const [reactivatePassword, setReactivatePassword] = useState("");
  const [showReactivatePassword, setShowReactivatePassword] = useState(false);
  const [submittingReactivate, setSubmittingReactivate] = useState(false);
  const [reactivateError, setReactivateError] = useState<string | null>(null);

  // Live check new tally_id when modal is open
  useEffect(() => {
    if (!tallyModalOpen || !newTallyId.trim() || !token) {
      setTallyCheck(null);
      return;
    }
    const timer = setTimeout(async () => {
      setCheckingTally(true);
      try {
        const res = await fetch(
          `/api/v1/employees/check-tally-id?tally_id=${encodeURIComponent(
            newTallyId.trim()
          )}&exclude_employee_id=${encodeURIComponent(employeeId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.ok) {
          setTallyCheck(await res.json());
        }
      } catch {
        setTallyCheck(null);
      } finally {
        setCheckingTally(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [tallyModalOpen, newTallyId, token, employeeId]);

  // Live fetch deactivation impact whenever modal opens or effective date changes
  useEffect(() => {
    if (!deactivateModalOpen || !token || !employeeId) return;
    let active = true;
    const loadImpact = async () => {
      setLoadingImpact(true);
      try {
        const qs = deactivateEffectiveDate
          ? `?effective_date=${encodeURIComponent(deactivateEffectiveDate)}`
          : "";
        const res = await fetch(`/api/v1/employees/${employeeId}/deactivation-impact${qs}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && active) {
          setDeactivateImpact(await res.json());
        }
      } catch {
        if (active) setDeactivateImpact(null);
      } finally {
        if (active) setLoadingImpact(false);
      }
    };
    loadImpact();
    return () => {
      active = false;
    };
  }, [deactivateModalOpen, deactivateEffectiveDate, token, employeeId]);

  const handleChangeTallyId = async (e: React.FormEvent) => {
    e.preventDefault();
    setTallyModalError(null);
    setSubmittingTally(true);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/change-tally-id`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          new_tally_id: newTallyId.trim(),
          reason: tallyReason.trim() || "Temp to permanent Tally ID update",
          confirm_reuse: confirmReuse,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || "Failed to change Tally ID");
      }
      setTallyModalOpen(false);
      setNewTallyId("");
      setTallyReason("");
      setConfirmReuse(false);
      setStatusMessage(
        `Tally ID updated to ${data.tally_id}. Employee login username has been updated automatically; please inform the worker to sign in with the new Tally ID on their next login.`
      );
      await fetchData();
    } catch (err: any) {
      setTallyModalError(err.message || "Failed to update Tally ID");
    } finally {
      setSubmittingTally(false);
    }
  };

  const handleDeactivateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeactivateError(null);
    setSubmittingDeactivate(true);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/deactivate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          reason: deactivateReason.trim(),
          effective_date: deactivateEffectiveDate || null,
          confirmation_text: deactivateConfirmText.trim(),
          admin_password: deactivatePassword,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || "Failed to deactivate employee");
      }
      setDeactivateModalOpen(false);
      setDeactivateReason("");
      setDeactivateConfirmText("");
      setDeactivatePassword("");
      setStatusMessage(data.message || "Employee deactivated cleanly.");
      await fetchData();
    } catch (err: any) {
      setDeactivateError(err.message || "Deactivation failed");
    } finally {
      setSubmittingDeactivate(false);
    }
  };

  const handleReactivateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setReactivateError(null);
    setSubmittingReactivate(true);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/reactivate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          reason: reactivateReason.trim(),
          confirmation_text: reactivateConfirmText.trim(),
          admin_password: reactivatePassword,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || "Failed to reactivate employee");
      }
      setReactivateModalOpen(false);
      setReactivateReason("");
      setReactivateConfirmText("");
      setReactivatePassword("");
      setStatusMessage(data.message || "Employee reactivated cleanly (Option A — no past shifts restored).");
      await fetchData();
    } catch (err: any) {
      setReactivateError(err.message || "Reactivation failed");
    } finally {
      setSubmittingReactivate(false);
    }
  };

  const handleExportDsar = async () => {
    setExportingDsar(true);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/export-dsar`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Failed to export employee DSAR");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dsar_${employee?.tally_id || employeeId}_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setStatusMessage("DSAR package exported successfully.");
    } catch (err: any) {
      setErrorMessage(err.message || "DSAR export failed");
    } finally {
      setExportingDsar(false);
    }
  };

  const handleWithdrawConsent = async () => {
    const reason = window.prompt("Enter reason for consent withdrawal (e.g. Employee request, Contract review):");
    if (!reason) return;
    setWithdrawingConsent(true);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/withdraw-consent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ reason }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to withdraw consent");
      }
      setStatusMessage("Consent withdrawn successfully. Mobile tracking events will now be rejected with HTTP 403.");
      fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to record consent withdrawal");
    } finally {
      setWithdrawingConsent(false);
    }
  };

  const fetchData = async () => {
    if (!employeeId) return;
    setLoading(true);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      // 1. Employee
      const empRes = await fetch(`/api/v1/employees/${employeeId}`, { headers });
      if (empRes.ok) {
        const empData = await empRes.json();
        setEmployee(empData);
        setEditWeeklyOff(empData.weekly_off_day || "");
        setEditBreakOverride(empData.break_override_minutes ?? "");
        setEditPhone(empData.phone || "");
        setEditEmail(empData.email || "");
        setEditAccommodationId(empData.accommodation_id || "");
        if (empData.role === "SUPERVISOR") {
          setNewRelType("SUPERINTENDENT");
        } else {
          setNewRelType("SUPERVISOR");
        }
      }

      // Accommodations list
      const accRes = await fetch(`/api/v1/accommodations`, { headers });
      if (accRes.ok) {
        setAccommodations(await accRes.json());
      }

      // 2. Reporting lines
      const repRes = await fetch(`/api/v1/employees/${employeeId}/reporting-lines`, { headers });
      if (repRes.ok) setReportingLines(await repRes.json());

      // 3. Documents
      const docRes = await fetch(`/api/v1/employees/${employeeId}/documents`, { headers });
      if (docRes.ok) setDocuments(await docRes.json());

      // 4. Salary history
      const salRes = await fetch(`/api/v1/employees/${employeeId}/salary`, { headers });
      if (salRes.ok) setSalaryHistory(await salRes.json());

      // 5. Devices, Audit Logs & Candidate Managers (Admin only)
      if (user?.role === "ADMIN") {
        const devRes = await fetch(`/api/v1/employees/${employeeId}/devices`, { headers });
        if (devRes.ok) setDevices(await devRes.json());

        const auditRes = await fetch(`/api/v1/audit-logs?entity_type=employee&entity_id=${employeeId}`, { headers });
        if (auditRes.ok) setAuditLogs(await auditRes.json());

        const mgrsRes = await fetch(`/api/v1/employees?is_active=true&limit=1000`, { headers });
        if (mgrsRes.ok) {
          const allEmps = await mgrsRes.json();
          setAllManagers(
            allEmps.filter(
              (m: any) => m.id !== employeeId && m.role !== "ADMIN" && m.tally_id !== "ADMIN001"
            )
          );
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [employeeId, user]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const payload: any = {
        version: employee.version,
        weekly_off_day: editWeeklyOff || null,
        break_override_minutes: editBreakOverride !== "" ? Number(editBreakOverride) : null,
        accommodation_id: editAccommodationId || null,
        phone: editPhone || null,
        email: editEmail || null,
      };

      const res = await fetch(`/api/v1/employees/${employeeId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Save failed");
      }

      const updated = await res.json();
      setEmployee(updated);
      setStatusMessage("Profile updated successfully!");
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleResetPassword = async () => {
    if (!window.confirm("Reset this worker's password to company default?")) return;
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch(`/api/v1/employees/${employee.id}/reset-password`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || data.detail || "Failed to reset password");

      setStatusMessage(data.message || "Password reset to company default successfully.");
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    if (!window.confirm("Revoke this device binding?")) return;
    try {
      const res = await fetch(`/api/v1/devices/${deviceId}/revoke`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchData();
        setStatusMessage("Device binding revoked.");
      }
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleAddReportingLine = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newManagerId) return;
    setSavingHierarchy(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      };

      // If assigning a SUPERVISOR and a direct supervisor already exists, replace it atomically
      if (newRelType === "SUPERVISOR") {
        const existingSup = reportingLines.find(
          (l) => l.is_direct && l.relationship === "SUPERVISOR"
        );
        if (existingSup) {
          if (existingSup.manager_id === newManagerId) {
            setErrorMessage("This supervisor is already assigned.");
            return;
          }
          const delRes = await fetch(
            `/api/v1/employees/${employeeId}/reporting-lines/${existingSup.id}`,
            { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
          );
          if (!delRes.ok) {
            const err = await delRes.json().catch(() => ({}));
            throw new Error(err.detail || err.message || "Failed to replace existing supervisor.");
          }
        }
      }

      const res = await fetch(`/api/v1/employees/${employeeId}/reporting-lines`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          manager_id: newManagerId,
          relationship: newRelType,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Failed to assign reporting line.");
      }

      setNewManagerId("");
      setStatusMessage("Reporting line updated successfully.");
      await fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to update hierarchy.");
    } finally {
      setSavingHierarchy(false);
    }
  };

  const handleRemoveReportingLine = async (lineId: string, managerLabel: string) => {
    if (!window.confirm(`Remove direct reporting line to ${managerLabel}?`)) return;
    setSavingHierarchy(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/reporting-lines/${lineId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Failed to remove reporting line.");
      }
      setStatusMessage("Reporting line removed.");
      await fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to remove reporting line.");
    } finally {
      setSavingHierarchy(false);
    }
  };

  const fetchHierarchyViolations = async () => {
    setLoadingViolations(true);
    try {
      const res = await fetch("/api/v1/employees/hierarchy-violations", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setHierarchyViolations(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingViolations(false);
    }
  };

  const handleDeactivateViolation = async (lineId: string) => {
    if (!window.confirm("Are you sure you want to deactivate this reporting line?")) return;
    setActionInProgress(lineId);
    try {
      const res = await fetch(`/api/v1/employees/hierarchy-violations/${lineId}/deactivate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Failed to deactivate line");
      }
      setStatusMessage("Reporting line deactivated.");
      await fetchHierarchyViolations();
      await fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to deactivate line.");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleMoveViolationToSupervisor = async (lineId: string) => {
    if (!window.confirm("Move this leadership link to the worker's supervisor and deactivate the worker's direct link?")) return;
    setActionInProgress(lineId);
    try {
      const res = await fetch(`/api/v1/employees/hierarchy-violations/${lineId}/move-to-supervisor`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Failed to move line");
      }
      setStatusMessage("Reporting line moved to supervisor.");
      await fetchHierarchyViolations();
      await fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to move line.");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleExportViolationsExcel = async () => {
    try {
      const res = await fetch("/api/v1/employees/hierarchy-violations/export", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "hierarchy_violations.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to export Excel");
    }
  };

  const handleAddDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDocExpiry) return;
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/documents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          document_type: newDocType,
          expiry_date: newDocExpiry,
        }),
      });
      if (res.ok) {
        setNewDocExpiry("");
        fetchData();
        setStatusMessage("Document added/updated.");
      }
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  if (loading || !employee) {
    return <div className="p-12 text-center text-slate-500">Loading employee details...</div>;
  }

  const renderDiff = (diff: Record<string, any>, labels: Record<string, string> = {}) => {
    const entries = Object.entries(diff || {});
    if (entries.length === 0) return <span className="text-slate-400 text-xs">—</span>;

    return (
      <div className="space-y-1 text-xs">
        {entries.map(([key, val]) => {
          const friendlyLabel = labels[key];
          const displayKey = key
            .replace(/_/g, " ")
            .replace(/\bid\b/i, "ID")
            .replace(/\b\w/g, (c) => c.toUpperCase());

          return (
            <div key={key} className="flex flex-col sm:flex-row sm:items-baseline gap-1 text-[11px] leading-tight">
              <span className="font-semibold text-slate-600 shrink-0">{displayKey}:</span>
              {friendlyLabel ? (
                <span
                  className="font-medium text-indigo-800 bg-indigo-50/90 px-1.5 py-0.5 rounded border border-indigo-200/80 break-words"
                  title={String(val)}
                >
                  {friendlyLabel}
                </span>
              ) : (
                <span className="font-mono text-slate-800 break-words">
                  {typeof val === "object" ? JSON.stringify(val) : String(val)}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Back button and header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/employees"
            className="p-2 border border-slate-200 rounded-lg hover:bg-white text-slate-600 transition"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">{employee.name}</h2>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 font-semibold text-slate-700">
                {employee.tally_id}
              </span>
              {user?.role === "ADMIN" && (
                <button
                  type="button"
                  onClick={() => {
                    setNewTallyId("");
                    setTallyReason("");
                    setTallyCheck(null);
                    setConfirmReuse(false);
                    setTallyModalError(null);
                    setTallyModalOpen(true);
                  }}
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition cursor-pointer"
                  title="Update temporary or permanent Tally ID"
                >
                  <Pencil className="h-3 w-3" /> Change Tally ID
                </button>
              )}
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                {employee.role}
              </span>
              {employee.is_active === false && (
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                  DEACTIVATED
                </span>
              )}
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                  employee.consent_status === "WITHDRAWN"
                    ? "bg-rose-100 text-rose-800 border border-rose-200"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                }`}
              >
                Consent: {employee.consent_status || "ACCEPTED"}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {employee.staff_grade_description || "Field Worker"} • {employee.country} Operations
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleExportDsar}
            disabled={exportingDsar}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 rounded-lg text-xs font-medium hover:bg-slate-50 transition shadow-xs disabled:opacity-50"
            title="Export full Data Subject Access Request (DSAR) Excel package"
          >
            <Download className="h-3.5 w-3.5 text-slate-500" />
            {exportingDsar ? "Exporting DSAR..." : "Export DSAR (.xlsx)"}
          </button>

          {user?.role === "ADMIN" && employee.consent_status !== "WITHDRAWN" && (
            <button
              onClick={handleWithdrawConsent}
              disabled={withdrawingConsent}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-rose-200 bg-rose-50 text-rose-700 rounded-lg text-xs font-medium hover:bg-rose-100 transition shadow-xs disabled:opacity-50"
              title="Record consent withdrawal for tracking events"
            >
              <ShieldAlert className="h-3.5 w-3.5 text-rose-600" />
              {withdrawingConsent ? "Withdrawing..." : "Withdraw Consent"}
            </button>
          )}

          {user?.role === "ADMIN" && employee.is_active !== false && employee.role !== "ADMIN" && (
            <button
              type="button"
              onClick={() => {
                setDeactivateEffectiveDate(new Date().toISOString().slice(0, 10));
                setDeactivateReason("");
                setDeactivateConfirmText("");
                setDeactivatePassword("");
                setDeactivateError(null);
                setDeactivateModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-rose-300 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700 transition shadow-xs cursor-pointer"
              title="Deactivate employee, disable login, and cancel future shifts"
            >
              <PowerOff className="h-3.5 w-3.5" />
              Deactivate
            </button>
          )}

          {user?.role === "ADMIN" && employee.is_active === false && (
            <button
              type="button"
              onClick={() => {
                setReactivateReason("");
                setReactivateConfirmText("");
                setReactivatePassword("");
                setReactivateError(null);
                setReactivateModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-emerald-300 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition shadow-xs cursor-pointer"
              title="Reactivate employee cleanly without restoring cancelled shifts"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reactivate
            </button>
          )}
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle className="h-4 w-4" />
          {statusMessage}
        </div>
      )}
      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {errorMessage}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6">
        <button
          onClick={() => setActiveTab("profile")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "profile"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <UserIcon className="h-4 w-4" /> Profile
        </button>

        <button
          onClick={() => setActiveTab("salary")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "salary"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <DollarSign className="h-4 w-4" /> Salary Structure
        </button>

        <button
          onClick={() => setActiveTab("hierarchy")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "hierarchy"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <GitFork className="h-4 w-4" /> Hierarchy
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "documents"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <FileText className="h-4 w-4" /> Documents ({documents.length})
        </button>

        {user?.role === "ADMIN" && (
          <>
            <button
              onClick={() => setActiveTab("device")}
              className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
                activeTab === "device"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Smartphone className="h-4 w-4" /> Devices & Security
            </button>

            <button
              onClick={() => setActiveTab("history")}
              className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
                activeTab === "history"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <History className="h-4 w-4" /> Audit History
            </button>
          </>
        )}
      </div>

      {/* Tab Panels */}
      {activeTab === "profile" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl">
          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Tally ID</label>
                <input
                  type="text"
                  disabled
                  value={employee.tally_id}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm text-slate-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  disabled
                  value={employee.name}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm text-slate-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Weekly Off Day</label>
                <select
                  value={editWeeklyOff}
                  onChange={(e) => setEditWeeklyOff(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                >
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
                <label className="block text-xs font-medium text-slate-700 mb-1">Break Override (Minutes)</label>
                <input
                  type="number"
                  value={editBreakOverride}
                  onChange={(e) => setEditBreakOverride(e.target.value ? Number(e.target.value) : "")}
                  placeholder="e.g. 60"
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Living Camp / Accommodation</label>
                <select
                  value={editAccommodationId}
                  onChange={(e) => setEditAccommodationId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800"
                >
                  <option value="">-- No Camp Assigned --</option>
                  {accommodations.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.name} ({acc.accommodation_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Phone Number</label>
                <input
                  type="text"
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  placeholder="e.g. +971501234567"
                  disabled={!["ADMIN", "ENGINEER"].includes(user?.role || "")}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  placeholder="e.g. worker@example.com"
                  disabled={!["ADMIN", "ENGINEER"].includes(user?.role || "")}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400">Record Version: {employee.version}</span>
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      )}

      {activeTab === "salary" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-6">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Worker Salary Structure</h3>
              <p className="text-xs text-slate-500">
                Effective-dated salary portions and historical revisions.
              </p>
            </div>
            {salaryHistory?.current_salary?.change_source === "CREW_BREAK" ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Last change:</span>
                <span className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full bg-blue-100 text-blue-800">
                  Break change
                </span>
              </div>
            ) : salaryHistory?.last_change_difference !== null && salaryHistory?.last_change_difference !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Last change:</span>
                <span
                  className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full ${
                    salaryHistory.last_change_difference > 0
                      ? "bg-emerald-100 text-emerald-800"
                      : salaryHistory.last_change_difference < 0
                      ? "bg-red-100 text-red-800"
                      : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {salaryHistory.last_change_difference > 0 && <TrendingUp className="h-3.5 w-3.5" />}
                  {salaryHistory.last_change_difference < 0 && <TrendingDown className="h-3.5 w-3.5" />}
                  {salaryHistory.last_change_difference > 0
                    ? `+${salaryHistory.last_change_difference}`
                    : salaryHistory.last_change_difference}
                </span>
              </div>
            )}
          </div>

          {/* Current Active Structure Card */}
          {salaryHistory?.current_salary ? (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-indigo-900 uppercase tracking-wider">
                  Active Structure (as of {salaryHistory.current_salary.effective_from})
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Standard Hours: {salaryHistory.current_salary.standard_hours} hrs/day
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Basic Salary</span>
                  <span className="text-base font-bold text-slate-900">
                    {Number(salaryHistory.current_salary.basic_salary).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Special Allowance</span>
                  <span className="text-base font-bold text-slate-900">
                    {Number(salaryHistory.current_salary.special_allowance).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Other Allowances</span>
                  <span className="text-base font-bold text-slate-900">
                    {(
                      Number(salaryHistory.current_salary.fixed_ot_amount) +
                      Number(salaryHistory.current_salary.bonus) +
                      Number(salaryHistory.current_salary.telephone_allowance) +
                      Number(salaryHistory.current_salary.housing_transport_allowance)
                    ).toFixed(2)}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-200">
                  <span className="text-xs text-indigo-700 block mb-1 font-semibold">Total Fixed Portion</span>
                  <span className="text-base font-extrabold text-indigo-600">
                    {Number(salaryHistory.current_salary.salary_portion).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400 rounded-lg border border-dashed border-slate-200">
              No active salary structure found for this worker. Upload the template or record a salary revision.
            </div>
          )}

          {/* Revisions History */}
          <div className="space-y-3 pt-2">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Revision History ({salaryHistory?.history?.length ?? 0})
            </h4>

            {salaryHistory?.history && salaryHistory.history.length > 0 ? (
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden text-xs">
                {salaryHistory.history.map((rev: any) => (
                  <div key={rev.id} className="p-3 flex items-center justify-between hover:bg-slate-50">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">
                          Effective {rev.effective_from}
                        </span>
                        {rev.change_source === "CREW_BREAK" && (
                          <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-bold">
                            Break change
                          </span>
                        )}
                      </div>
                      <div className="text-slate-400 text-[11px]">
                        Basic: {rev.basic_salary} • Standard: {rev.standard_hours} hrs
                        {rev.break_minutes ? ` • Break: ${rev.break_minutes}m` : ""}
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="font-bold text-slate-800 text-sm">
                        {rev.salary_portion}
                      </span>
                      {rev.change_source === "CREW_BREAK" ? (
                        <span className="text-slate-400 text-xs">-</span>
                      ) : rev.difference !== 0 ? (
                        <span
                          className={`px-2 py-0.5 rounded font-semibold ${
                            rev.difference > 0 ? "text-emerald-700 bg-emerald-50" : "text-red-700 bg-red-50"
                          }`}
                        >
                          {rev.difference > 0 ? `+${rev.difference}` : rev.difference}
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {activeTab === "hierarchy" && (() => {
        const canEditHierarchy =
          user?.role === "ADMIN" && employee?.role !== "ADMIN" && employee?.tally_id !== "ADMIN001";
        const isWorker = employee?.role === "WORKER";
        const isSupervisor = employee?.role === "SUPERVISOR";
        const isLeadership = employee?.role === "SUPERINTENDENT" || employee?.role === "ENGINEER";

        const existingDirectSup = reportingLines.find(
          (l) => l.is_direct && l.relationship === "SUPERVISOR"
        );
        const existingDirectIdsForType = new Set(
          reportingLines
            .filter((l) => l.is_direct && l.relationship === newRelType)
            .map((l) => l.manager_id)
        );

        // Strict role matching candidates per fixed crew structure (DEC-10)
        const matchingRoleCandidates = allManagers.filter(
          (m) => m.role === newRelType && !existingDirectIdsForType.has(m.id)
        );

        return (
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl space-y-6">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Management Reporting Chain</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {isWorker && "Workers have exactly 1 direct Supervisor. Leadership (Superintendents & Engineers) is inherited transitively."}
                    {isSupervisor && "Supervisors lead crews and attach to Superintendents and Engineers."}
                    {isLeadership && "Superintendents and Engineers manage Supervisors directly."}
                  </p>
                </div>
                {user?.role === "ADMIN" && (
                  <button
                    type="button"
                    onClick={() => {
                      setViolationsModalOpen(true);
                      fetchHierarchyViolations();
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg text-xs font-semibold hover:bg-amber-100 transition shadow-xs"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                    Hierarchy Audit & Violations
                  </button>
                )}
              </div>

              {employee?.role === "ADMIN" || employee?.tally_id === "ADMIN001" ? (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600">
                  Admin accounts are system superusers and do not belong to the employee reporting hierarchy.
                </div>
              ) : reportingLines.length === 0 ? (
                <p className="text-xs text-slate-500">No managers assigned.</p>
              ) : (
                <div className="space-y-2.5">
                  {reportingLines.map((line) => {
                    const relBadgeClass =
                      line.relationship === "SUPERVISOR"
                        ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                        : line.relationship === "SUPERINTENDENT"
                        ? "bg-purple-100 text-purple-700 border-purple-200"
                        : "bg-sky-100 text-sky-700 border-sky-200";

                    // In fixed crew structure: direct supt/eng on a worker is non-conforming or inherited
                    const isInherited = !line.is_direct || (isWorker && line.relationship !== "SUPERVISOR");

                    return (
                      <div
                        key={`${line.id}-${line.manager_id}`}
                        className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 text-sm hover:bg-slate-50 transition"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Link
                              to="/employees/$employeeId"
                              params={{ employeeId: line.manager_id }}
                              className="font-semibold text-slate-900 hover:text-indigo-600 hover:underline"
                            >
                              {line.manager_name || `Manager ID: ${line.manager_id}`}
                            </Link>
                            {line.manager_tally_id && (
                              <span className="text-xs text-slate-500 font-mono bg-slate-200/60 px-1.5 py-0.5 rounded">
                                Tally: {line.manager_tally_id}
                              </span>
                            )}
                            <span className={`px-2 py-0.5 rounded text-xs font-mono font-medium border ${relBadgeClass}`}>
                              {line.relationship}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            {isInherited ? (
                              <span className="px-2 py-0.5 rounded-full text-2xs font-semibold bg-slate-200 text-slate-700 border border-slate-300">
                                {line.via_name ? `Inherited via ${line.via_name}` : "Inherited Leadership"}
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-2xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                Direct {line.relationship}
                              </span>
                            )}
                            {canEditHierarchy && line.is_direct && (!isWorker || line.relationship === "SUPERVISOR") && (
                              <button
                                type="button"
                                disabled={savingHierarchy}
                                onClick={() =>
                                  handleRemoveReportingLine(
                                    line.id,
                                    line.manager_name || line.manager_id
                                  )
                                }
                                title="Remove / Deactivate direct reporting line"
                                className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition disabled:opacity-40"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                        {!line.is_direct && line.via_name && (
                          <div className="mt-1.5 text-xs text-slate-500 flex items-center gap-1.5">
                            <span className="text-slate-400">↳ Reports via:</span>
                            <span className="font-medium text-slate-700">{line.via_name}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Admin-Only Edit Hierarchy Form */}
            {canEditHierarchy && !isLeadership && (
              <form
                onSubmit={handleAddReportingLine}
                className="pt-5 border-t border-slate-200 space-y-3"
              >
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  {isWorker ? "Assign Supervisor (Admin Only)" : "Assign Leadership Manager (Admin Only)"}
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Relationship
                    </label>
                    <select
                      value={newRelType}
                      onChange={(e) => {
                        setNewRelType(e.target.value as "SUPERVISOR" | "SUPERINTENDENT" | "ENGINEER");
                        setNewManagerId("");
                      }}
                      className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {isWorker ? (
                        <option value="SUPERVISOR">Supervisor (Max 1)</option>
                      ) : (
                        <>
                          <option value="SUPERINTENDENT">Superintendent (Multiple allowed)</option>
                          <option value="ENGINEER">Engineer (Multiple allowed)</option>
                        </>
                      )}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Select Manager
                    </label>
                    <select
                      required
                      value={newManagerId}
                      onChange={(e) => setNewManagerId(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg p-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">-- Choose {newRelType.toLowerCase()} --</option>
                      {matchingRoleCandidates.length > 0 ? (
                        matchingRoleCandidates.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name} ({m.tally_id})
                          </option>
                        ))
                      ) : (
                        <option disabled value="">No available {newRelType.toLowerCase()}s</option>
                      )}
                    </select>
                  </div>
                </div>

                {newRelType === "SUPERVISOR" && existingDirectSup && (
                  <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    This employee already reports to Supervisor{" "}
                    <strong>{existingDirectSup.manager_name}</strong>. Saving will replace the current direct supervisor.
                  </p>
                )}

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!newManagerId || savingHierarchy}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 disabled:opacity-40 transition"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    {savingHierarchy
                      ? "Saving..."
                      : newRelType === "SUPERVISOR" && existingDirectSup
                      ? "Replace Supervisor"
                      : `Add ${newRelType.charAt(0) + newRelType.slice(1).toLowerCase()}`}
                  </button>
                </div>
              </form>
            )}

            {isLeadership && (
              <div className="pt-3 border-t border-slate-200 text-xs text-slate-500 bg-slate-50 p-3 rounded-lg">
                Superintendents and Engineers attach directly to Supervisors. Field workers inherit their leadership chain transitively.
              </div>
            )}
          </div>
        );
      })()}

      {activeTab === "documents" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Official Document Validity</h3>
          </div>

          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-3">Document Type</th>
                <th className="p-3">Expiry Date</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((doc) => {
                const daysLeft = Math.ceil(
                  (new Date(doc.expiry_date).getTime() - new Date().getTime()) / (1000 * 86400)
                );
                const isExpiring = daysLeft <= 30 && daysLeft > 0;
                const isExpired = daysLeft <= 0;

                return (
                  <tr key={doc.id}>
                    <td className="p-3 font-semibold text-slate-800">{doc.document_type}</td>
                    <td className="p-3 font-mono text-xs">{doc.expiry_date}</td>
                    <td className="p-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          isExpired
                            ? "bg-red-50 text-red-700"
                            : isExpiring
                            ? "bg-amber-50 text-amber-700"
                            : "bg-emerald-50 text-emerald-700"
                        }`}
                      >
                        {isExpired
                          ? "Expired"
                          : isExpiring
                          ? `Expiring soon (${daysLeft}d)`
                          : `Valid (${daysLeft}d left)`}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {user?.role === "ADMIN" && (
            <form onSubmit={handleAddDocument} className="pt-4 border-t border-slate-100 flex gap-4 items-end">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Document Type</label>
                <select
                  value={newDocType}
                  onChange={(e) => setNewDocType(e.target.value)}
                  className="border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="VISA">Visa</option>
                  <option value="PASSPORT">Passport</option>
                  <option value="EMIRATES_ID">Emirates ID</option>
                  <option value="LABOUR_CARD">Labour Card</option>
                  <option value="DRIVING_LICENCE">Driving Licence</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Expiry Date</label>
                <input
                  type="date"
                  required
                  value={newDocExpiry}
                  onChange={(e) => setNewDocExpiry(e.target.value)}
                  className="border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 flex items-center gap-2"
              >
                <Plus className="h-4 w-4" /> Save Document
              </button>
            </form>
          )}
        </div>
      )}

      {activeTab === "device" && user?.role === "ADMIN" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Security & Credentials</h3>
            <button
              onClick={handleResetPassword}
              className="px-3.5 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 flex items-center gap-2 transition"
            >
              <KeyRound className="h-4 w-4" /> Reset Password to Default
            </button>
          </div>

          <div className="pt-4 border-t border-slate-100">
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
              Bound Registered Devices (1 device limit)
            </h4>

            {devices.length === 0 ? (
              <p className="text-xs text-slate-500">No active device bound to this worker.</p>
            ) : (
              <div className="space-y-3">
                {devices.map((dev) => (
                  <div
                    key={dev.id}
                    className="p-4 border border-slate-200 rounded-lg flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800 text-sm">
                          {dev.device_model || dev.platform}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            dev.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {dev.is_active ? "ACTIVE BINDING" : "REVOKED"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        OS: {dev.os_version || "—"} • App Version: {dev.app_version || "—"}
                      </p>
                    </div>

                    {dev.is_active && (
                      <button
                        onClick={() => handleRevokeDevice(dev.id)}
                        className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 border border-red-200 rounded-lg flex items-center gap-1.5 transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Revoke Binding
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "history" && user?.role === "ADMIN" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Audit Trail for Employee</h3>
          {auditLogs.length === 0 ? (
            <p className="text-xs text-slate-500">No audit records found.</p>
          ) : (
            <div className="space-y-3">
              {auditLogs.map((log) => (
                <div key={log.id} className="p-3 border border-slate-200 rounded-lg bg-slate-50/50 text-xs space-y-2">
                  <div className="flex items-center justify-between text-slate-500 pb-1 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-800 bg-white px-2 py-0.5 rounded border border-slate-200">{log.action}</span>
                      {log.actor_name && (
                        <span className="text-slate-600">by <strong className="text-slate-800">{log.actor_name}</strong></span>
                      )}
                    </div>
                    <span>{new Date(log.created_at).toLocaleString()}</span>
                  </div>
                  {log.entity_label && (
                    <div className="text-[11px] text-indigo-700 font-medium">
                      Target: {log.entity_label}
                    </div>
                  )}
                  <div className="p-2 bg-white rounded border border-slate-200">
                    {renderDiff(log.diff, log.diff_labels || {})}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Change Tally ID Modal (Admin Only) */}
      {tallyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Pencil className="h-4 w-4 text-indigo-600" />
                  Change Tally ID
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Current Tally ID: <span className="font-mono font-bold text-slate-800">{employee.tally_id}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTallyModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleChangeTallyId} className="p-6 space-y-4">
              <div className="p-3 rounded-lg bg-indigo-50/70 border border-indigo-200 text-xs text-indigo-900 space-y-1">
                <div className="font-semibold">How Tally ID changes work:</div>
                <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                  <li>All historical shifts, attendance, payroll, and GPS records remain linked automatically via internal UUID.</li>
                  <li>The linked login username updates to the new Tally ID immediately; the employee will use it on their next login.</li>
                  <li>The previous Tally ID is preserved in the Audit Trail only.</li>
                </ul>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  New Tally ID <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newTallyId}
                  onChange={(e) => {
                    setNewTallyId(e.target.value);
                    setConfirmReuse(false);
                  }}
                  placeholder="e.g. PERM-1042"
                  className="w-full px-3 py-2 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                {checkingTally && (
                  <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" /> Checking Tally ID history...
                  </p>
                )}
              </div>

              {tallyCheck && !tallyCheck.available && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <strong>Already in use</strong> by {tallyCheck.in_use_by_name || "another employee"}. Choose a different Tally ID.
                  </div>
                </div>
              )}

              {tallyCheck && tallyCheck.available && tallyCheck.previously_used && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 text-xs text-amber-900 space-y-2">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <strong>Previously Used Tally ID Guardrail:</strong> This Tally ID was previously assigned to:
                      <ul className="list-disc pl-4 mt-1 space-y-0.5 text-[11px]">
                        {(tallyCheck.previous_uses || []).map((h: any, idx: number) => (
                          <li key={idx}>
                            <strong>{h.employee_name || h.employee_id}</strong> (changed to{" "}
                            <span className="font-mono">{h.new_tally_id || "another ID"}</span>
                            {h.changed_at ? ` on ${new Date(h.changed_at).toLocaleDateString()}` : ""})
                          </li>
                        ))}
                      </ul>
                      <p className="text-[11px] mt-1">
                        System data stays separated by UUID, but reusing a retired Tally ID may confuse external Tally/Excel exports.
                      </p>
                    </div>
                  </div>
                  <label className="flex items-center gap-2 pt-1 font-semibold cursor-pointer">
                    <input
                      type="checkbox"
                      checked={confirmReuse}
                      onChange={(e) => setConfirmReuse(e.target.checked)}
                      className="rounded border-amber-400 text-amber-600 focus:ring-amber-500"
                    />
                    <span>I understand this Tally ID was previously used and confirm reuse</span>
                  </label>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Reason for Change <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={tallyReason}
                  onChange={(e) => setTallyReason(e.target.value)}
                  placeholder="e.g. Probation completed — assigned permanent Tally ID"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              {tallyModalError && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                  {tallyModalError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setTallyModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    submittingTally ||
                    !newTallyId.trim() ||
                    !tallyReason.trim() ||
                    (tallyCheck !== null && !tallyCheck.available) ||
                    (Boolean(tallyCheck?.previously_used) && !confirmReuse)
                  }
                  className="px-4 py-2 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white flex items-center gap-1.5 cursor-pointer"
                >
                  {submittingTally && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Update Tally ID
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deactivate Employee Modal (Admin Only) */}
      {deactivateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-rose-200 w-full max-w-lg max-h-[92vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-rose-200 bg-rose-50 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-rose-900 flex items-center gap-2">
                  <PowerOff className="h-5 w-5 text-rose-600" />
                  Deactivate Employee
                </h3>
                <p className="text-xs text-rose-700 mt-0.5">
                  {employee.name} ({employee.tally_id}) · {employee.role}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDeactivateModalOpen(false)}
                className="p-1.5 rounded-lg text-rose-400 hover:text-rose-700 hover:bg-rose-100 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleDeactivateEmployee} className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Effective Date (Optional — defaults to Today)
                </label>
                <input
                  type="date"
                  value={deactivateEffectiveDate}
                  onChange={(e) => setDeactivateEffectiveDate(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Only schedules on or after this date will be cancelled and marked as <strong>Needs Cover</strong>. Past attendance and payroll stay untouched.
                </p>
              </div>

              {/* Impact Preview */}
              <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs space-y-2">
                <div className="font-bold text-amber-950 flex items-center justify-between">
                  <span>Deactivation Impact Preview</span>
                  {loadingImpact && <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-700" />}
                </div>
                {deactivateImpact ? (
                  <ul className="space-y-1 text-[11px] text-amber-900">
                    <li>
                      • <strong>Login Access:</strong> Web &amp; mobile account (if linked) will be disabled immediately and all active sessions revoked.
                    </li>
                    <li>
                      • <strong>Base Roster Slots:</strong> {deactivateImpact.base_roster_slots ?? 0} recurring slot(s) removed (future days flagged Needs Cover).
                    </li>
                    <li>
                      • <strong>Scheduled Shifts (≥ {deactivateImpact.effective_date}):</strong> {deactivateImpact.future_active_shifts ?? 0} shift(s) cancelled &amp; flagged Needs Cover.
                    </li>
                    <li>
                      • <strong>Standing Assignments:</strong> {deactivateImpact.active_standing_assignments ?? 0} active assignment(s) ended.
                    </li>
                    <li>
                      • <strong>Pending Requests:</strong> {deactivateImpact.pending_leave_requests ?? 0} leave(s) and {deactivateImpact.pending_reassignment_requests ?? 0} reassignment(s) cancelled.
                    </li>
                    {(deactivateImpact.active_direct_reports ?? 0) > 0 && (
                      <li className="text-rose-800 font-semibold">
                        • Direct Reports: {deactivateImpact.active_direct_reports} employee(s) report to this manager — remember to reassign their supervisor.
                      </li>
                    )}
                  </ul>
                ) : (
                  <p className="text-[11px] text-amber-700">Calculating impact...</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Reason for Deactivation <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={deactivateReason}
                  onChange={(e) => setDeactivateReason(e.target.value)}
                  placeholder="e.g. Resigned / Contract ended / Transferred"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Type <span className="font-mono font-bold text-rose-700">DEACTIVATE</span> to confirm <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={deactivateConfirmText}
                    onChange={(e) => setDeactivateConfirmText(e.target.value)}
                    placeholder="DEACTIVATE"
                    className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Admin Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type={showDeactivatePassword ? "text" : "password"}
                      required
                      value={deactivatePassword}
                      onChange={(e) => setDeactivatePassword(e.target.value)}
                      placeholder="Enter your password"
                      className="w-full px-3 py-2 pr-9 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowDeactivatePassword((p) => !p)}
                      className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      {showDeactivatePassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              </div>

              {deactivateError && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                  {deactivateError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setDeactivateModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    submittingDeactivate ||
                    deactivateConfirmText.trim() !== "DEACTIVATE" ||
                    !deactivateReason.trim() ||
                    !deactivatePassword
                  }
                  className="px-4 py-2 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white flex items-center gap-1.5 cursor-pointer"
                >
                  {submittingDeactivate && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Confirm Deactivation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reactivate Employee Modal (Option A — Clean, Admin Only) */}
      {reactivateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-emerald-200 w-full max-w-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-emerald-200 bg-emerald-50 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-emerald-900 flex items-center gap-2">
                  <RotateCcw className="h-5 w-5 text-emerald-600" />
                  Reactivate Employee (Clean)
                </h3>
                <p className="text-xs text-emerald-700 mt-0.5">
                  {employee.name} ({employee.tally_id})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReactivateModalOpen(false)}
                className="p-1.5 rounded-lg text-emerald-500 hover:text-emerald-700 hover:bg-emerald-100 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleReactivateEmployee} className="p-6 space-y-4">
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 space-y-1">
                <div className="font-bold">Clean Reactivation (Option A):</div>
                <p className="text-[11px]">
                  This restores the employee&apos;s active status, visibility across pages, and login access. <strong>No previously cancelled schedules or base roster slots are restored</strong>, preventing any double-booking with cover workers. Assign new shifts manually in the Base or Operational Planner.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Reason for Reactivation <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={reactivateReason}
                  onChange={(e) => setReactivateReason(e.target.value)}
                  placeholder="e.g. Rehired / Returned from extended absence"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Type <span className="font-mono font-bold text-emerald-700">REACTIVATE</span> <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={reactivateConfirmText}
                    onChange={(e) => setReactivateConfirmText(e.target.value)}
                    placeholder="REACTIVATE"
                    className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Admin Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type={showReactivatePassword ? "text" : "password"}
                      required
                      value={reactivatePassword}
                      onChange={(e) => setReactivatePassword(e.target.value)}
                      placeholder="Enter your password"
                      className="w-full px-3 py-2 pr-9 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowReactivatePassword((p) => !p)}
                      className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      {showReactivatePassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              </div>

              {reactivateError && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                  {reactivateError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setReactivateModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    submittingReactivate ||
                    reactivateConfirmText.trim() !== "REACTIVATE" ||
                    !reactivateReason.trim() ||
                    !reactivatePassword
                  }
                  className="px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white flex items-center gap-1.5 cursor-pointer"
                >
                  {submittingReactivate && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Confirm Reactivation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Batch 4: Hierarchy Violations Modal (Admin only) */}
      {violationsModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-xl border border-slate-200 space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  Hierarchy Violations Audit (DEC-10)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Active reporting lines that violate the fixed crew hierarchy (worker direct supt/eng links or non-supervisor managers).
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleExportViolationsExcel}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition"
                  title="Export violations to Excel"
                >
                  <Download className="h-3.5 w-3.5" />
                  Export Excel (.xlsx)
                </button>
                <button
                  type="button"
                  onClick={() => setViolationsModalOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingViolations ? (
                <div className="flex items-center justify-center py-12 text-slate-500 text-xs gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                  Scanning active reporting lines...
                </div>
              ) : hierarchyViolations.length === 0 ? (
                <div className="p-8 text-center bg-emerald-50/50 border border-emerald-100 rounded-xl space-y-2">
                  <CheckCircle className="h-8 w-8 text-emerald-600 mx-auto" />
                  <p className="text-sm font-semibold text-emerald-900">
                    No Hierarchy Violations Found
                  </p>
                  <p className="text-xs text-emerald-700">
                    All active reporting lines cleanly adhere to the fixed crew hierarchy structure.
                  </p>
                </div>
              ) : (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="p-3">Employee (Subordinate)</th>
                        <th className="p-3">Direct Manager</th>
                        <th className="p-3">Relationship</th>
                        <th className="p-3">Violation Details</th>
                        <th className="p-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {hierarchyViolations.map((v) => (
                        <tr key={v.reporting_line_id} className="hover:bg-slate-50/80 transition">
                          <td className="p-3">
                            <div className="font-semibold text-slate-900">{v.employee_name}</div>
                            <div className="text-2xs text-slate-500 font-mono">Tally: {v.employee_tally_id} ({v.employee_role})</div>
                          </td>
                          <td className="p-3">
                            <div className="font-semibold text-slate-900">{v.manager_name}</div>
                            <div className="text-2xs text-slate-500 font-mono">Tally: {v.manager_tally_id} ({v.manager_role})</div>
                          </td>
                          <td className="p-3">
                            <span className="px-2 py-0.5 rounded text-2xs font-mono font-medium border bg-amber-50 text-amber-700 border-amber-200">
                              {v.relationship}
                            </span>
                          </td>
                          <td className="p-3 text-slate-600 max-w-xs">
                            <div className="font-medium text-amber-900">{v.violation_code}</div>
                            <div className="text-2xs mt-0.5">{v.violation_message}</div>
                            {v.supervisor_name && (
                              <div className="text-2xs text-slate-500 mt-1">
                                Worker's Supervisor: <span className="font-medium text-slate-700">{v.supervisor_name} ({v.supervisor_tally_id})</span>
                                {v.supervisor_already_has_manager && " (Already linked)"}
                              </div>
                            )}
                          </td>
                          <td className="p-3 text-right space-x-1.5 whitespace-nowrap">
                            {v.can_move_to_supervisor && (
                              <button
                                type="button"
                                disabled={actionInProgress === v.reporting_line_id}
                                onClick={() => handleMoveViolationToSupervisor(v.reporting_line_id)}
                                className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-2xs font-semibold disabled:opacity-40 transition"
                                title="Add link to supervisor and deactivate direct link on worker"
                              >
                                {actionInProgress === v.reporting_line_id ? "Moving..." : "Move to Supervisor"}
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={actionInProgress === v.reporting_line_id}
                              onClick={() => handleDeactivateViolation(v.reporting_line_id)}
                              className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-lg text-2xs font-semibold disabled:opacity-40 transition"
                              title="Deactivate non-conforming reporting line"
                            >
                              {actionInProgress === v.reporting_line_id ? "Deactivating..." : "Deactivate"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setViolationsModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
