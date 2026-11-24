import React, { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { Button, Modal, TextArea, TextField, ensureOk, useToast } from "../../ui";
import { AttendanceRecord } from "./types";
import { toHhMm, validateManualTimes, type ManualTimesForm } from "./manualTimes";

interface ManualTimesModalProps {
  open: boolean;
  record: AttendanceRecord;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Enter the times for a day the phone did not record (owner decision 25 Nov 2026). The day gets
 * a new calculation version flagged "Manual times" and stays in review; earlier versions are kept.
 */
export const ManualTimesModal: React.FC<ManualTimesModalProps> = ({ open, record, onClose, onSaved }) => {
  const { token } = useAuth();
  const toast = useToast();
  const calc = record.current_calculation;
  const initial = (): ManualTimesForm => ({
    firstSiteEntry: toHhMm(calc?.planned_first_site_start),
    lastSiteExit: toHhMm(calc?.planned_last_site_end),
    accommodationDeparture: "",
    accommodationReturn: "",
    reason: "",
  });
  const [form, setForm] = useState<ManualTimesForm>(initial);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(initial());
      setTouched(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, record.id]);

  const errors = touched ? validateManualTimes(form) : {};
  const set = (key: keyof ManualTimesForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async () => {
    setTouched(true);
    if (Object.keys(validateManualTimes(form)).length > 0) return;
    setSaving(true);
    try {
      const res = await fetch("/api/v1/attendance/manual-times", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          employee_id: record.employee_id,
          work_date: record.work_date,
          first_site_entry: form.firstSiteEntry,
          last_site_exit: form.lastSiteExit,
          accommodation_departure: form.accommodationDeparture || null,
          accommodation_return: form.accommodationReturn || null,
          reason: form.reason.trim(),
        }),
      });
      await ensureOk(res, "Could not save the times.");
      toast.success("Times saved", "The day was recalculated and is waiting for review.");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      dismissible={!saving}
      title="Enter times for the day"
      description={`${record.employee_name} (${record.tally_id}), ${record.work_date}. Site-local times. Use this when the phone recorded nothing, e.g. a dead phone.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={save} loading={saving}>
            Save and recalculate
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <TextField
          type="time"
          label="First site entry"
          required
          value={form.firstSiteEntry}
          onChange={set("firstSiteEntry")}
          error={errors.firstSiteEntry}
        />
        <TextField
          type="time"
          label="Last site exit"
          required
          value={form.lastSiteExit}
          onChange={set("lastSiteExit")}
          error={errors.lastSiteExit}
        />
        <TextField
          type="time"
          label="Accommodation departure"
          hint="Optional (drivers need both)"
          value={form.accommodationDeparture}
          onChange={set("accommodationDeparture")}
          error={errors.accommodationDeparture}
        />
        <TextField
          type="time"
          label="Accommodation return"
          hint="Optional"
          value={form.accommodationReturn}
          onChange={set("accommodationReturn")}
          error={errors.accommodationReturn}
        />
      </div>
      <TextArea
        fieldClassName="mt-3"
        label="Reason"
        required
        rows={3}
        placeholder="Why the phone has no record, and how the times were confirmed"
        value={form.reason}
        onChange={set("reason")}
        error={errors.reason}
      />
      <p className="mt-3 text-fw-xs text-fw-text-muted">
        The usual break applies. The time is spread across the day's assigned sites. The previous
        calculation is kept in Versions, and the change is audited.
      </p>
    </Modal>
  );
};
