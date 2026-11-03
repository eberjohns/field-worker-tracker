import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  Clock,
  Building2,
  Calendar,
  Users,
  ShieldCheck,
  KeyRound,
  History,
  Plus,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Sparkles,
  Info,
} from "lucide-react";

interface SettingItem {
  id: string;
  setting_key: string;
  country: string | null;
  value: any;
  unit: string | null;
  effective_from: string;
  effective_to: string | null;
}

interface TimeRuleItem {
  id: string;
  name: string;
  country: string | null;
  scope_type: string;
  scope_employee_id: string | null;
  applies_to: string;
  start_date: string;
  end_date: string | null;
  accommodation_start: string | null;
  first_site_start: string | null;
  break_minutes: number | null;
  last_site_end: string | null;
  accommodation_end: string | null;
  standard_hours_change_minutes: number | null;
  notes: string | null;
  is_active: boolean;
  version: number;
}

interface PublicHolidayItem {
  id: string;
  holiday_date: string;
  name: string;
  country: string;
}

interface ConsentPolicyItem {
  id: string;
  version: number;
  language: string;
  title: string;
  body: string;
  published_at: string;
}

interface EmployeeItem {
  id: string;
  tally_id: string;
  name: string;
  role: string;
  country: string;
  is_driver: boolean;
}

interface ResolvedSchedule {
  employee_id: string;
  date: string;
  is_outdoor: boolean | null;
  accommodation_start: string | null;
  first_site_start: string | null;
  break_minutes: number;
  last_site_end: string | null;
  accommodation_end: string | null;
  planned_total_minutes: number;
  planned_worked_minutes: number;
  standard_hours_change_minutes: number;
  has_accommodation: boolean;
  winning_rule_id: string | null;
  winning_rule_name: string | null;
  winning_sources: Record<
    string,
    {
      rule_id: string;
      rule_name: string;
      scope_type: string;
      field_name: string;
      value: any;
    }
  >;
  matched_rules: Array<{
    rule_id: string;
    rule_name: string;
    scope_type: string;
    applies_to: string;
    priority_score: number;
    is_match: boolean;
    status: string;
    reasons: string[];
  }>;
}

export const Settings: React.FC = () => {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<
    "company" | "timerules" | "checktool" | "holidays" | "budget" | "password" | "consent"
  >("company");

  const [countryFilter, setCountryFilter] = useState<string>("ALL");
  const [asOfDate, setAsOfDate] = useState<string>(new Date().toISOString().split("T")[0]);

  // Data states
  const [settings, setSettings] = useState<SettingItem[]>([]);
  const [timeRules, setTimeRules] = useState<TimeRuleItem[]>([]);
  const [holidays, setHolidays] = useState<PublicHolidayItem[]>([]);
  const [consentPolicies, setConsentPolicies] = useState<ConsentPolicyItem[]>([]);
  const [employees, setEmployees] = useState<EmployeeItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Status/Alerts
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal states
  const [editSettingModal, setEditSettingModal] = useState<SettingItem | null>(null);
  const [settingNewValue, setSettingNewValue] = useState<string>("");
  const [settingEffectiveFrom, setSettingEffectiveFrom] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [historyKey, setHistoryKey] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<SettingItem[]>([]);

  // Time Rule Modal
  const [showNewRuleModal, setShowNewRuleModal] = useState(false);
  const [newRuleForm, setNewRuleForm] = useState({
    name: "",
    country: "AE",
    scope_type: user?.role === "ENGINEER" ? "TEAM" : "COMPANY",
    scope_employee_id: "",
    applies_to: "ALL",
    start_date: new Date().toISOString().split("T")[0],
    end_date: "",
    accommodation_start: "05:00",
    first_site_start: "06:00",
    break_minutes: 30,
    last_site_end: "15:30",
    accommodation_end: "17:00",
    standard_hours_change_minutes: 0,
    notes: "",
  });

  // Check Tool State
  const [checkEmployeeId, setCheckEmployeeId] = useState<string>("");
  const [checkDate, setCheckDate] = useState<string>(new Date().toISOString().split("T")[0]);
  const [checkIsOutdoor, setCheckIsOutdoor] = useState<boolean>(true);
  const [resolvedResult, setResolvedResult] = useState<ResolvedSchedule | null>(null);

  // Holiday Modal
  const [showHolidayModal, setShowHolidayModal] = useState(false);
  const [newHoliday, setNewHoliday] = useState({
    holiday_date: new Date().toISOString().split("T")[0],
    name: "",
    country: "AE",
  });

  // Consent Policy Modal
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [newConsentPolicy, setNewConsentPolicy] = useState({
    version: 1,
    language: "en",
    title: "",
    body: "",
  });

  // Loaders
  const fetchSettings = async () => {
    setLoading(true);
    try {
      const countryParam = countryFilter !== "ALL" ? `&country=${countryFilter}` : "";
      const res = await fetch(`/api/v1/settings?as_of=${asOfDate}${countryParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setSettings(await res.json());
    } catch {
      setErrorMessage("Failed to load company settings.");
    } finally {
      setLoading(false);
    }
  };

  const fetchTimeRules = async () => {
    setLoading(true);
    try {
      const countryParam = countryFilter !== "ALL" ? `?country=${countryFilter}` : "";
      const res = await fetch(`/api/v1/time-rules${countryParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setTimeRules(await res.json());
    } catch {
      setErrorMessage("Failed to load time rules.");
    } finally {
      setLoading(false);
    }
  };

  const fetchHolidays = async () => {
    setLoading(true);
    try {
      const countryParam = countryFilter !== "ALL" ? `?country=${countryFilter}` : "";
      const res = await fetch(`/api/v1/public-holidays${countryParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setHolidays(await res.json());
    } catch {
      setErrorMessage("Failed to load public holidays.");
    } finally {
      setLoading(false);
    }
  };

  const fetchConsentPolicies = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/consent-policies", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setConsentPolicies(await res.json());
    } catch {
      setErrorMessage("Failed to load consent policies.");
    } finally {
      setLoading(false);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await fetch("/api/v1/employees?limit=200", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEmployees(data);
        if (data.length > 0 && !checkEmployeeId) {
          setCheckEmployeeId(data[0].id);
        }
      }
    } catch {
      // silent
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  useEffect(() => {
    setStatusMessage(null);
    setErrorMessage(null);
    if (activeTab === "company" || activeTab === "budget" || activeTab === "password") {
      fetchSettings();
    } else if (activeTab === "timerules") {
      fetchTimeRules();
    } else if (activeTab === "holidays") {
      fetchHolidays();
    } else if (activeTab === "consent") {
      fetchConsentPolicies();
    }
  }, [activeTab, countryFilter, asOfDate]);

  // Handlers
  const handleOpenEditSetting = (item: SettingItem) => {
    setEditSettingModal(item);
    setSettingNewValue(
      typeof item.value === "object" ? JSON.stringify(item.value) : String(item.value)
    );
    setSettingEffectiveFrom(new Date().toISOString().split("T")[0]);
  };

  const handleSaveSetting = async () => {
    if (!editSettingModal) return;
    setStatusMessage(null);
    setErrorMessage(null);

    let parsedValue: any = settingNewValue;
    try {
      parsedValue = JSON.parse(settingNewValue);
    } catch {
      // fallback to number or string
      if (!isNaN(Number(settingNewValue)) && settingNewValue.trim() !== "") {
        parsedValue = Number(settingNewValue);
      }
    }

    try {
      const res = await fetch(`/api/v1/settings/${editSettingModal.setting_key}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          value: parsedValue,
          country: editSettingModal.country,
          effective_from: settingEffectiveFrom,
          unit: editSettingModal.unit,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to update setting.");
      }

      setStatusMessage(
        `Setting '${editSettingModal.setting_key}' updated effective from ${settingEffectiveFrom}. Earlier dates remain unchanged.`
      );
      setEditSettingModal(null);
      fetchSettings();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleOpenHistory = async (key: string, country: string | null) => {
    setHistoryKey(key);
    try {
      const countryParam = country ? `?country=${country}` : "";
      const res = await fetch(`/api/v1/settings/${key}/history${countryParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setHistoryItems(await res.json());
    } catch {
      setErrorMessage("Failed to load setting history.");
    }
  };

  const handleCreateTimeRule = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const payload = {
        name: newRuleForm.name,
        country: newRuleForm.country || null,
        scope_type: newRuleForm.scope_type,
        scope_employee_id: newRuleForm.scope_employee_id || null,
        applies_to: newRuleForm.applies_to,
        start_date: newRuleForm.start_date,
        end_date: newRuleForm.end_date || null,
        accommodation_start: newRuleForm.accommodation_start || null,
        first_site_start: newRuleForm.first_site_start || null,
        break_minutes: Number(newRuleForm.break_minutes),
        last_site_end: newRuleForm.last_site_end || null,
        accommodation_end: newRuleForm.accommodation_end || null,
        standard_hours_change_minutes: Number(newRuleForm.standard_hours_change_minutes),
        notes: newRuleForm.notes || null,
      };

      const res = await fetch("/api/v1/time-rules", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to create time rule.");
      }

      setStatusMessage(`Time rule '${newRuleForm.name}' created successfully.`);
      setShowNewRuleModal(false);
      fetchTimeRules();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleDeleteTimeRule = async (id: string, name: string) => {
    if (!window.confirm(`Deactivate time rule '${name}'?`)) return;
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch(`/api/v1/time-rules/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to deactivate time rule.");
      }
      setStatusMessage(`Time rule '${name}' deactivated.`);
      fetchTimeRules();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleResolveSchedule = async () => {
    if (!checkEmployeeId) return;
    setLoading(true);
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch(
        `/api/v1/time-rules/resolve?employee_id=${checkEmployeeId}&date=${checkDate}&is_outdoor=${checkIsOutdoor}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to resolve schedule.");
      }
      const data = await res.json();
      setResolvedResult(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateHoliday = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch("/api/v1/public-holidays", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newHoliday),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to add public holiday.");
      }

      setStatusMessage(`Public holiday '${newHoliday.name}' added.`);
      setShowHolidayModal(false);
      fetchHolidays();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleDeleteHoliday = async (id: string, name: string) => {
    if (!window.confirm(`Delete holiday '${name}'?`)) return;
    try {
      const res = await fetch(`/api/v1/public-holidays/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setStatusMessage(`Holiday '${name}' deleted.`);
        fetchHolidays();
      }
    } catch {
      setErrorMessage("Failed to delete holiday.");
    }
  };

  const handleCreateConsentPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch("/api/v1/consent-policies", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newConsentPolicy),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to publish consent policy.");
      }

      setStatusMessage(`Consent notice version ${newConsentPolicy.version} published.`);
      setShowConsentModal(false);
      fetchConsentPolicies();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleToggleBudgetRole = async (roleName: string) => {
    const budgetSetting = settings.find((s) => s.setting_key === "budget_only_staff_types");
    const currentList: string[] = Array.isArray(budgetSetting?.value) ? budgetSetting.value : [];
    const nextList = currentList.includes(roleName)
      ? currentList.filter((r) => r !== roleName)
      : [...currentList, roleName];

    try {
      const res = await fetch("/api/v1/settings/budget_only_staff_types", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          value: nextList,
          country: null,
          effective_from: new Date().toISOString().split("T")[0],
          unit: "list",
        }),
      });
      if (res.ok) {
        setStatusMessage("Budget-only staff types updated.");
        fetchSettings();
      }
    } catch {
      setErrorMessage("Failed to update budget-only roles.");
    }
  };

  const formatMinutes = (m: number) => {
    const hrs = Math.floor(m / 60);
    const mins = m % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            System Configuration & Time Rules
          </h1>
          <p className="text-sm text-slate-500">
            Effective-dated company settings, seasonal rules, planned schedule resolution, and
            calendars.
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg p-1 text-xs">
            <span className="px-2 font-medium text-slate-500">Country:</span>
            {["ALL", "AE", "SA"].map((c) => (
              <button
                key={c}
                onClick={() => setCountryFilter(c)}
                className={`px-2.5 py-1 rounded font-semibold transition ${
                  countryFilter === c
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {c}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg p-1 text-xs">
            <span className="px-2 font-medium text-slate-500">As Of:</span>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="px-2 py-1 border border-slate-200 rounded text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex border-b border-slate-200 bg-white px-3 rounded-t-xl overflow-x-auto">
        {[
          { id: "company", label: "Company Settings", icon: Building2 },
          { id: "timerules", label: "Time Rules", icon: Clock },
          { id: "checktool", label: "Resolver Check Tool", icon: Sparkles },
          { id: "holidays", label: "Public Holidays", icon: Calendar },
          { id: "budget", label: "Budget-Only Roles", icon: Users },
          { id: "password", label: "Default Password", icon: KeyRound },
          { id: "consent", label: "Consent Notice", icon: ShieldCheck },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 py-3 px-4 text-sm font-medium border-b-2 whitespace-nowrap transition ${
                isActive
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Status & Error Alerts */}
      {statusMessage && (
        <div className="flex items-center gap-2.5 p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm shadow-sm animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600" />
          <span>{statusMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="flex items-center gap-2.5 p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-sm shadow-sm animate-in fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* TAB 1: Company Settings */}
      {activeTab === "company" && (
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5 text-xs text-amber-800 flex items-start gap-2.5">
            <Info className="w-4 h-4 flex-shrink-0 text-amber-600 mt-0.5" />
            <div>
              <span className="font-semibold">Effective-Dated Governance (BR-ST-04):</span> All
              settings are resolved as of the selected date. Changing a setting inserts a new dated
              version; earlier dates and finalized records remain intact and defensible.
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-slate-700 font-semibold text-xs uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Setting Key</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4">Effective Value</th>
                  <th className="py-3 px-4">Unit</th>
                  <th className="py-3 px-4">In Force From</th>
                  <th className="py-3 px-4">In Force To</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {settings.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-400">
                      No settings resolved for this country and date.
                    </td>
                  </tr>
                ) : (
                  settings.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900">
                        {item.setting_key}
                      </td>
                      <td className="py-3 px-4">
                        {item.country ? (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                            {item.country}
                          </span>
                        ) : (
                          <span className="text-slate-400 text-xs italic">Global</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-900">
                        {typeof item.value === "object"
                          ? JSON.stringify(item.value)
                          : String(item.value)}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-500">{item.unit || "-"}</td>
                      <td className="py-3 px-4 text-xs text-slate-700 font-medium">
                        {item.effective_from}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-500">
                        {item.effective_to ? item.effective_to : "Current (open)"}
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        {user?.role === "ADMIN" && (
                          <button
                            onClick={() => handleOpenEditSetting(item)}
                            className="px-2.5 py-1 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-800 rounded transition"
                          >
                            Update
                          </button>
                        )}
                        <button
                          onClick={() => handleOpenHistory(item.setting_key, item.country)}
                          className="px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded transition inline-flex items-center gap-1"
                        >
                          <History className="w-3.5 h-3.5" />
                          History
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Time Rules */}
      {activeTab === "timerules" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Precedence: <strong className="text-slate-700">Employee &gt; Team &gt; Drivers &gt; Company</strong>.
              Outdoor-only rules win over general rules on outdoor worksites.
            </p>
            {(user?.role === "ADMIN" || user?.role === "ENGINEER") && (
              <button
                onClick={() => setShowNewRuleModal(true)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                New Time Rule
              </button>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-slate-700 font-semibold text-xs uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Scope</th>
                  <th className="py-3 px-4">Applies To</th>
                  <th className="py-3 px-4">Valid Range</th>
                  <th className="py-3 px-4">Acc. Start</th>
                  <th className="py-3 px-4">1st Site</th>
                  <th className="py-3 px-4">Break</th>
                  <th className="py-3 px-4">Last Site</th>
                  <th className="py-3 px-4">Acc. End</th>
                  <th className="py-3 px-4">Std Change</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {timeRules.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="py-8 text-center text-slate-400">
                      No time rules found.
                    </td>
                  </tr>
                ) : (
                  timeRules.map((rule) => (
                    <tr key={rule.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-medium text-slate-900">
                        {rule.name}
                        {rule.country && (
                          <span className="ml-1.5 text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                            {rule.country}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                            rule.scope_type === "COMPANY"
                              ? "bg-blue-100 text-blue-700"
                              : rule.scope_type === "TEAM"
                              ? "bg-purple-100 text-purple-700"
                              : rule.scope_type === "DRIVERS"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {rule.scope_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs font-medium">
                        {rule.applies_to === "OUTDOOR_ONLY" ? (
                          <span className="text-amber-700 font-semibold">Outdoor Only</span>
                        ) : rule.applies_to === "INDOOR_ONLY" ? (
                          <span className="text-cyan-700 font-semibold">Indoor Only</span>
                        ) : (
                          <span className="text-slate-500">All Jobs</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-600 whitespace-nowrap">
                        {rule.start_date}
                        {rule.end_date ? ` to ${rule.end_date}` : " onwards"}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs">{rule.accommodation_start || "-"}</td>
                      <td className="py-3 px-4 font-mono text-xs">{rule.first_site_start || "-"}</td>
                      <td className="py-3 px-4 text-xs">
                        {rule.break_minutes !== null ? `${rule.break_minutes}m` : "-"}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs">{rule.last_site_end || "-"}</td>
                      <td className="py-3 px-4 font-mono text-xs">{rule.accommodation_end || "-"}</td>
                      <td className="py-3 px-4 text-xs font-semibold">
                        {rule.standard_hours_change_minutes ? (
                          <span className="text-rose-600">
                            {rule.standard_hours_change_minutes} min
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {(user?.role === "ADMIN" ||
                          (user?.role === "ENGINEER" &&
                            rule.scope_type !== "COMPANY" &&
                            rule.scope_type !== "DRIVERS")) && (
                          <button
                            onClick={() => handleDeleteTimeRule(rule.id, rule.name)}
                            className="px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 rounded transition"
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Resolver Check Tool */}
      {activeTab === "checktool" && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-indigo-600" />
              Schedule Explainer & Verification Tool
            </h2>
            <p className="text-xs text-slate-500">
              Simulate effective planned hours and break times for any worker on any date. Shows
              which rule won and how missing fields were inherited.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Worker (Tally / Name)
                </label>
                <select
                  value={checkEmployeeId}
                  onChange={(e) => setCheckEmployeeId(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500"
                >
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.tally_id} - {emp.name} ({emp.role}
                      {emp.is_driver ? ", Driver" : ""})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Work Date</label>
                <input
                  type="date"
                  value={checkDate}
                  onChange={(e) => setCheckDate(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Job Setting</label>
                <div className="flex items-center gap-3 pt-2">
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="outdoorToggle"
                      checked={checkIsOutdoor}
                      onChange={() => setCheckIsOutdoor(true)}
                    />
                    Outdoor Worksite
                  </label>
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="outdoorToggle"
                      checked={!checkIsOutdoor}
                      onChange={() => setCheckIsOutdoor(false)}
                    />
                    Indoor Worksite
                  </label>
                </div>
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleResolveSchedule}
                  disabled={loading}
                  className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium shadow-sm transition flex items-center justify-center gap-1.5"
                >
                  {loading ? "Resolving..." : "Resolve Schedule"}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {resolvedResult && (
            <div className="space-y-4 animate-in fade-in">
              {/* Client example card layout */}
              <div className="bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-xl p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-indigo-800 pb-3">
                  <div>
                    <span className="text-xs font-mono text-indigo-300">
                      RESOLVED SCHEDULE AS OF {resolvedResult.date}
                    </span>
                    <h3 className="text-lg font-bold">
                      Winning Primary Rule: {resolvedResult.winning_rule_name || "None"}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-indigo-300">Company Accommodation:</span>
                    <div className="text-xs font-semibold">
                      {resolvedResult.has_accommodation ? "Company Provided" : "None (n/a times)"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                  <div className="bg-indigo-900/40 p-2.5 rounded-lg border border-indigo-700/50">
                    <div className="text-[11px] text-indigo-300 uppercase">Acc. Departure</div>
                    <div className="text-base font-bold font-mono">
                      {resolvedResult.accommodation_start || "n/a"}
                    </div>
                  </div>
                  <div className="bg-indigo-900/40 p-2.5 rounded-lg border border-indigo-700/50">
                    <div className="text-[11px] text-indigo-300 uppercase">1st Site Entry</div>
                    <div className="text-base font-bold font-mono">
                      {resolvedResult.first_site_start || "-"}
                    </div>
                  </div>
                  <div className="bg-indigo-900/40 p-2.5 rounded-lg border border-indigo-700/50">
                    <div className="text-[11px] text-indigo-300 uppercase">Planned Break</div>
                    <div className="text-base font-bold font-mono">
                      {resolvedResult.break_minutes} min
                    </div>
                  </div>
                  <div className="bg-indigo-900/40 p-2.5 rounded-lg border border-indigo-700/50">
                    <div className="text-[11px] text-indigo-300 uppercase">Last Site Exit</div>
                    <div className="text-base font-bold font-mono">
                      {resolvedResult.last_site_end || "-"}
                    </div>
                  </div>
                  <div className="bg-indigo-900/40 p-2.5 rounded-lg border border-indigo-700/50">
                    <div className="text-[11px] text-indigo-300 uppercase">Acc. Return</div>
                    <div className="text-base font-bold font-mono">
                      {resolvedResult.accommodation_end || "n/a"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-indigo-800">
                  <div className="bg-white/10 p-3 rounded-lg text-center">
                    <div className="text-xs text-indigo-200">Planned Total Span</div>
                    <div className="text-xl font-bold font-mono">
                      {formatMinutes(resolvedResult.planned_total_minutes)}
                      <span className="text-xs font-normal text-indigo-300 ml-1">
                        ({resolvedResult.planned_total_minutes}m)
                      </span>
                    </div>
                  </div>
                  <div className="bg-white/10 p-3 rounded-lg text-center">
                    <div className="text-xs text-indigo-200">Planned Worked Time</div>
                    <div className="text-xl font-bold font-mono text-emerald-300">
                      {formatMinutes(resolvedResult.planned_worked_minutes)}
                      <span className="text-xs font-normal text-emerald-200 ml-1">
                        ({resolvedResult.planned_worked_minutes}m)
                      </span>
                    </div>
                  </div>
                  <div className="bg-white/10 p-3 rounded-lg text-center">
                    <div className="text-xs text-indigo-200">Standard Hours Shift</div>
                    <div className="text-xl font-bold font-mono text-amber-300">
                      {resolvedResult.standard_hours_change_minutes} min
                    </div>
                  </div>
                </div>
              </div>

              {/* Explainer breakdown */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
                  <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                    Field-Level Sources (Inheritance Breakdown)
                  </h4>
                  <div className="divide-y divide-slate-100 text-xs">
                    {Object.entries(resolvedResult.winning_sources).map(([field, src]) => (
                      <div key={field} className="py-2 flex justify-between items-center">
                        <span className="font-mono text-slate-600">{field}:</span>
                        <div className="text-right">
                          <span className="font-semibold text-slate-800">{src.rule_name}</span>
                          <span className="ml-1 text-[10px] bg-slate-100 text-slate-600 px-1 py-0.5 rounded">
                            {src.scope_type}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
                  <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                    Candidate Evaluation Trace
                  </h4>
                  <div className="space-y-2 text-xs">
                    {resolvedResult.matched_rules.map((rule) => (
                      <div
                        key={rule.rule_id}
                        className={`p-2 rounded border ${
                          rule.status === "WON"
                            ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                            : rule.status === "PARTIAL_INHERITED"
                            ? "bg-purple-50 border-purple-200 text-purple-900"
                            : "bg-slate-50 border-slate-200 text-slate-500"
                        }`}
                      >
                        <div className="flex justify-between items-center font-medium">
                          <span>{rule.rule_name}</span>
                          <span className="text-[10px] font-bold uppercase">{rule.status}</span>
                        </div>
                        {rule.reasons.length > 0 && (
                          <div className="text-[10px] text-slate-400 mt-1">
                            {rule.reasons.join(", ")}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Public Holidays */}
      {activeTab === "holidays" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Statutory holidays are country-wide (AE and SA). Work scheduled on a public holiday is
              treated as OT2 (1.5x) per DEC-01.
            </p>
            {user?.role === "ADMIN" && (
              <button
                onClick={() => setShowHolidayModal(true)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                Add Holiday
              </button>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-slate-700 font-semibold text-xs uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Holiday Name</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {holidays.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-400">
                      No public holidays found for this selection.
                    </td>
                  </tr>
                ) : (
                  holidays.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900">
                        {h.holiday_date}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-900">{h.name}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {h.country}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {user?.role === "ADMIN" && (
                          <button
                            onClick={() => handleDeleteHoliday(h.id, h.name)}
                            className="px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 rounded transition"
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: Budget-Only Roles */}
      {activeTab === "budget" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Budget-Only Staff Types</h3>
            <p className="text-xs text-slate-500">
              Per DEC-09 and BR-JB-07: Roles selected below are included strictly for contract
              budgeting; they are never scheduled and never tracked on phones.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
            {[
              "Project Manager",
              "HSE Engineer",
              "QA/QC Engineer",
              "Irrigation Engineer",
              "Landscape Architect",
              "Surveyor",
              "Safety Officer",
            ].map((role) => {
              const budgetSetting = settings.find((s) => s.setting_key === "budget_only_staff_types");
              const currentList: string[] = Array.isArray(budgetSetting?.value)
                ? budgetSetting.value
                : [];
              const isChecked = currentList.includes(role);

              return (
                <label
                  key={role}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition ${
                    isChecked
                      ? "bg-indigo-50 border-indigo-200 text-indigo-900"
                      : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    disabled={user?.role !== "ADMIN"}
                    onChange={() => handleToggleBudgetRole(role)}
                    className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
                  />
                  <span className="text-xs font-medium">{role}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 6: Default Password */}
      {activeTab === "password" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4 max-w-2xl">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Worker Password Policy</h3>
            <p className="text-xs text-slate-500">
              Per DEC-53: All workers start with the company default password, are forced to change
              it on first login, and are locked out after `default_password_max_days`.
            </p>
          </div>

          <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 space-y-3 text-xs">
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-600 font-medium">Default Password Expiration:</span>
              <span className="font-semibold text-slate-900">
                {settings.find((s) => s.setting_key === "default_password_max_days")?.value || 7} days
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-600 font-medium">Reset Authority:</span>
              <span className="font-semibold text-emerald-700">Admin Only (manual action)</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-600 font-medium">Device Binding:</span>
              <span className="font-semibold text-slate-900">Locked to first registered phone</span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 7: Consent Notice */}
      {activeTab === "consent" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Per DEC-56 and ADR-008: Published location consent notice versions. The mobile app
              prompts workers when a newer policy version is published.
            </p>
            {user?.role === "ADMIN" && (
              <button
                onClick={() => setShowConsentModal(true)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                Publish Policy
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4">
            {consentPolicies.map((p) => (
              <div
                key={p.id}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-700">
                      v{p.version}
                    </span>
                    <span className="text-xs font-mono uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                      {p.language}
                    </span>
                    <h3 className="text-sm font-semibold text-slate-900">{p.title}</h3>
                  </div>
                  <span className="text-xs text-slate-400">
                    Published: {new Date(p.published_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-xs text-slate-600 whitespace-pre-line leading-relaxed">
                  {p.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MODAL: Edit Setting */}
      {editSettingModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">
                Update Setting: {editSettingModal.setting_key}
              </h3>
              <p className="text-xs text-slate-500">
                Country: {editSettingModal.country || "Global"}
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">New Value</label>
                <input
                  type="text"
                  value={settingNewValue}
                  onChange={(e) => setSettingNewValue(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg p-2 font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Effective From Date</label>
                <input
                  type="date"
                  value={settingEffectiveFrom}
                  onChange={(e) => setSettingEffectiveFrom(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg p-2 text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Requirement: Prominent banner on every change */}
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-[11px] leading-relaxed">
                <strong>Governance Rule:</strong> Affects dates from{" "}
                <span className="underline font-bold">{settingEffectiveFrom}</span>; earlier days
                and approved payroll remain unchanged.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setEditSettingModal(null)}
                className="px-3 py-1.5 border border-slate-200 text-slate-600 rounded-lg text-xs hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveSetting}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium shadow-sm"
              >
                Save Effective Row
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Setting History */}
      {historyKey && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="border-b border-slate-100 pb-3 flex justify-between items-center">
              <div>
                <h3 className="text-base font-bold text-slate-900">Audit History: {historyKey}</h3>
                <p className="text-xs text-slate-500">Chronological effective-dated record versions</p>
              </div>
              <button
                onClick={() => setHistoryKey(null)}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Close
              </button>
            </div>

            <div className="overflow-y-auto space-y-2 flex-1 pr-1">
              {historyItems.map((h, i) => (
                <div
                  key={h.id}
                  className={`p-3 rounded-lg border text-xs space-y-1 ${
                    i === 0
                      ? "bg-indigo-50 border-indigo-200 text-indigo-900"
                      : "bg-slate-50 border-slate-200 text-slate-600"
                  }`}
                >
                  <div className="flex justify-between font-medium">
                    <span>
                      Range: <strong>{h.effective_from}</strong> to{" "}
                      <strong>{h.effective_to || "Current"}</strong>
                    </span>
                    <span className="font-mono">
                      {h.country ? `[${h.country}]` : "[Global]"}
                    </span>
                  </div>
                  <div className="font-mono font-bold text-slate-900">
                    Value: {typeof h.value === "object" ? JSON.stringify(h.value) : String(h.value)}{" "}
                    {h.unit || ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* MODAL: New Time Rule */}
      {showNewRuleModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4 my-8">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Create Time Rule</h3>
              <p className="text-xs text-slate-500">
                Define 5-point planned hours, break, and standard hours adjustment.
              </p>
            </div>

            <form onSubmit={handleCreateTimeRule} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Rule Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramadan 2027, Summer Outdoor, Dawood Team"
                  value={newRuleForm.name}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, name: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg p-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Scope Level</label>
                  <select
                    value={newRuleForm.scope_type}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, scope_type: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2"
                  >
                    {user?.role === "ADMIN" && <option value="COMPANY">COMPANY (All)</option>}
                    {user?.role === "ADMIN" && <option value="DRIVERS">DRIVERS</option>}
                    <option value="TEAM">TEAM (Manager linked)</option>
                    <option value="EMPLOYEE">EMPLOYEE (Individual)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">Applies To</label>
                  <select
                    value={newRuleForm.applies_to}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, applies_to: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2"
                  >
                    <option value="ALL">All Jobs</option>
                    <option value="OUTDOOR_ONLY">Outdoor Only</option>
                    <option value="INDOOR_ONLY">Indoor Only</option>
                  </select>
                </div>
              </div>

              {(newRuleForm.scope_type === "TEAM" || newRuleForm.scope_type === "EMPLOYEE") && (
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    {newRuleForm.scope_type === "TEAM" ? "Team Manager" : "Target Employee"}
                  </label>
                  <select
                    required
                    value={newRuleForm.scope_employee_id}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, scope_employee_id: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2"
                  >
                    <option value="">-- Select Person --</option>
                    {employees.map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.tally_id} - {emp.name} ({emp.role})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Start Date</label>
                  <input
                    type="date"
                    required
                    value={newRuleForm.start_date}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, start_date: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">End Date (optional)</label>
                  <input
                    type="date"
                    value={newRuleForm.end_date}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, end_date: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2"
                  />
                </div>
              </div>

              {/* 5-point schedule */}
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-100">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Acc. Start</label>
                  <input
                    type="time"
                    value={newRuleForm.accommodation_start}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, accommodation_start: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">1st Site</label>
                  <input
                    type="time"
                    value={newRuleForm.first_site_start}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, first_site_start: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Break (min)</label>
                  <input
                    type="number"
                    value={newRuleForm.break_minutes}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, break_minutes: Number(e.target.value) })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Last Site</label>
                  <input
                    type="time"
                    value={newRuleForm.last_site_end}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, last_site_end: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Acc. End</label>
                  <input
                    type="time"
                    value={newRuleForm.accommodation_end}
                    onChange={(e) =>
                      setNewRuleForm({ ...newRuleForm, accommodation_end: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Std Change (m)</label>
                  <input
                    type="number"
                    placeholder="e.g. -120"
                    value={newRuleForm.standard_hours_change_minutes}
                    onChange={(e) =>
                      setNewRuleForm({
                        ...newRuleForm,
                        standard_hours_change_minutes: Number(e.target.value),
                      })
                    }
                    className="w-full border border-slate-200 rounded p-1.5 font-mono text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewRuleModal(false)}
                  className="px-3 py-1.5 border border-slate-200 text-slate-600 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg font-medium shadow-sm"
                >
                  Create Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Holiday */}
      {showHolidayModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">Add Public Holiday</h3>
            <form onSubmit={handleCreateHoliday} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Holiday Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Eid Al Fitr, National Day"
                  value={newHoliday.name}
                  onChange={(e) => setNewHoliday({ ...newHoliday, name: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Date</label>
                <input
                  type="date"
                  required
                  value={newHoliday.holiday_date}
                  onChange={(e) => setNewHoliday({ ...newHoliday, holiday_date: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Country</label>
                <select
                  value={newHoliday.country}
                  onChange={(e) => setNewHoliday({ ...newHoliday, country: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg p-2"
                >
                  <option value="AE">United Arab Emirates (AE)</option>
                  <option value="SA">Saudi Arabia (SA)</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowHolidayModal(false)}
                  className="px-3 py-1.5 border border-slate-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg font-medium"
                >
                  Save Holiday
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Consent Policy */}
      {showConsentModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">Publish Consent Notice Version</h3>
            <form onSubmit={handleCreateConsentPolicy} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Version Number</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={newConsentPolicy.version}
                    onChange={(e) =>
                      setNewConsentPolicy({ ...newConsentPolicy, version: Number(e.target.value) })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Language</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. en, ar"
                    value={newConsentPolicy.language}
                    onChange={(e) =>
                      setNewConsentPolicy({ ...newConsentPolicy, language: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded-lg p-2 font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Notice Title</label>
                <input
                  type="text"
                  required
                  value={newConsentPolicy.title}
                  onChange={(e) =>
                    setNewConsentPolicy({ ...newConsentPolicy, title: e.target.value })
                  }
                  className="w-full border border-slate-200 rounded-lg p-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Policy Body Text</label>
                <textarea
                  rows={4}
                  required
                  value={newConsentPolicy.body}
                  onChange={(e) =>
                    setNewConsentPolicy({ ...newConsentPolicy, body: e.target.value })
                  }
                  className="w-full border border-slate-200 rounded-lg p-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowConsentModal(false)}
                  className="px-3 py-1.5 border border-slate-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg font-medium"
                >
                  Publish Notice
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
