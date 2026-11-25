import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { AlertBanner, Button, Modal } from "../../ui";
import { formatApiError, buildJobItemPayload } from "./jobItemUtils";
import {
  WORKING_WEEK,
  draftProblem,
  draftToPayload,
  emptyDraft,
  nextSubItemCode,
  type JobItemDraft,
} from "./jobItemUtils";
import { JobItemFields } from "./JobItemFields";
import { JobItemChecksPanel } from "./JobItemChecksPanel";

export interface JobItem {
  id: string;
  worksite_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string | null;
  start_date: string;
  end_date: string | null;
  frequency_unit: "WEEK" | "MONTH" | "QUARTER" | "YEAR";
  occurrences_per_period: number;
  period_interval: number;
  weekday_pattern: string[] | number[] | null;
  required_staff_count: number;
  hours_per_occurrence_per_staff: number | string;
  deployment_type: "PERMANENT" | "REMOTE";
  break_override_minutes: number | null;
  is_active: boolean;
  version: number;
}

export interface JobItemModalProps {
  isOpen: boolean;
  onClose: () => void;
  worksiteId: string;
  /** The worksite's country, for the eligible-employee check. */
  worksiteCountry: string;
  worksiteStartDate?: string | null;
  initialData?: JobItem | null;
  /** Codes already used on the worksite, to suggest the next one for a new item. */
  existingCodes?: string[];
  onSuccess: () => void;
}

export { formatApiError, buildJobItemPayload };

const INDEX_TO_CODE = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

const normalizeWeekdays = (pattern: unknown): string[] => {
  if (!Array.isArray(pattern)) return [];
  return pattern
    .map((item) =>
      typeof item === "number" && item >= 0 && item < INDEX_TO_CODE.length
        ? INDEX_TO_CODE[item]
        : String(item).toUpperCase(),
    )
    .filter((code) => INDEX_TO_CODE.includes(code));
};

function draftFromItem(item: JobItem, fallbackStart: string): JobItemDraft {
  const days = normalizeWeekdays(item.weekday_pattern);
  return {
    sub_item_code: item.sub_item_code,
    staff_grade_description: item.staff_grade_description || "",
    planned_grade_code: item.planned_grade_code || "",
    start_date: item.start_date ? String(item.start_date).substring(0, 10) : fallbackStart,
    end_date: item.end_date ? String(item.end_date).substring(0, 10) : "",
    frequency_unit: item.frequency_unit,
    occurrences_per_period: Number(item.occurrences_per_period),
    period_interval: item.period_interval,
    weekday_pattern:
      days.length > 0 ? days : Number(item.occurrences_per_period) === 1 ? ["MON"] : [...WORKING_WEEK],
    required_staff_count: item.required_staff_count,
    hours_per_occurrence_per_staff: item.hours_per_occurrence_per_staff,
    deployment_type: item.deployment_type,
    break_override_minutes: item.break_override_minutes ?? "",
  };
}

/** Add or edit one job item of a saved worksite. Same fields and checks as the wizard rows. */
export const JobItemModal: React.FC<JobItemModalProps> = ({
  isOpen,
  onClose,
  worksiteId,
  worksiteCountry,
  worksiteStartDate,
  initialData,
  existingCodes = [],
  onSuccess,
}) => {
  const { token } = useAuth();
  const [draft, setDraft] = useState<JobItemDraft>(() => emptyDraft("", ""));
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    const todayStr = new Date().toISOString().split("T")[0];
    const start = worksiteStartDate ? String(worksiteStartDate).substring(0, 10) : todayStr;
    setDraft(
      initialData ? draftFromItem(initialData, start) : emptyDraft(nextSubItemCode(existingCodes), start),
    );
    setErrorMsg("");
    // existingCodes is only read when the modal opens.
  }, [initialData, isOpen, worksiteStartDate]);

  if (!isOpen) return null;

  const patch = (p: Partial<JobItemDraft>) => setDraft((d) => ({ ...d, ...p }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = draftProblem(draft);
    if (problem) {
      setErrorMsg(`Add ${problem}.`);
      return;
    }
    const code = draft.sub_item_code.trim().toUpperCase();
    if (!initialData && existingCodes.some((c) => c.trim().toUpperCase() === code)) {
      setErrorMsg(`Job item ${code} already exists on this worksite.`);
      return;
    }
    setErrorMsg("");
    setLoading(true);
    try {
      const payload: Record<string, unknown> = draftToPayload(draft);
      if (initialData) payload.version = initialData.version;
      const res = await fetch(
        initialData ? `/api/v1/job-items/${initialData.id}` : `/api/v1/worksites/${worksiteId}/job-items`,
        {
          method: initialData ? "PATCH" : "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(payload),
        },
      );
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(formatApiError(errData));
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      dismissible={!loading}
      size="xl"
      title={initialData ? "Edit Job Item" : "Add Job Item"}
      description="Frequency, staffing, dates and hours. Occurrences are generated automatically."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" form="job-item-form" loading={loading}>
            {initialData ? "Save Changes" : "Create Job Item"}
          </Button>
        </>
      }
    >
      <form id="job-item-form" onSubmit={handleSubmit} className="space-y-5">
        {errorMsg && (
          <AlertBanner tone="error">
            <span className="whitespace-pre-line">{errorMsg}</span>
          </AlertBanner>
        )}

        <JobItemFields draft={draft} onChange={patch} breakMode="edit" idPrefix="modal" />
        <JobItemChecksPanel draft={draft} country={worksiteCountry} worksiteId={worksiteId} />
      </form>
    </Modal>
  );
};
