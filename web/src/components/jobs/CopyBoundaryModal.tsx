import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { X, Copy, AlertCircle, Search } from "lucide-react";

interface WorksiteOption {
  id: string;
  job_number: string;
  job_name: string;
  has_boundary: boolean;
}

interface CopyBoundaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  worksiteId: string;
  worksiteJobNumber: string;
  mode: "COPY_FROM" | "COPY_TO";
  onSuccess: () => void;
}

export const CopyBoundaryModal: React.FC<CopyBoundaryModalProps> = ({
  isOpen,
  onClose,
  worksiteId,
  worksiteJobNumber,
  mode,
  onSuccess,
}) => {
  const { token } = useAuth();
  const [worksites, setWorksites] = useState<WorksiteOption[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!isOpen) return;

    const fetchCandidates = async () => {
      setFetching(true);
      setErrorMsg("");
      try {
        const res = await fetch("/api/v1/worksites?limit=200", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const all: WorksiteOption[] = await res.json();
          // Filter out current worksite
          setWorksites(all.filter((w) => w.id !== worksiteId));
        }
      } catch (err: any) {
        setErrorMsg("Failed to load candidate worksites.");
      } finally {
        setFetching(false);
      }
    };

    fetchCandidates();
    setSelectedSourceId("");
    setSelectedTargetIds([]);
    setSearch("");
  }, [isOpen, worksiteId, token]);

  if (!isOpen) return null;

  const filtered = worksites.filter(
    (w) =>
      w.job_number.toLowerCase().includes(search.toLowerCase()) ||
      w.job_name.toLowerCase().includes(search.toLowerCase())
  );

  const toggleTargetId = (id: string) => {
    if (selectedTargetIds.includes(id)) {
      setSelectedTargetIds(selectedTargetIds.filter((t) => t !== id));
    } else {
      setSelectedTargetIds([...selectedTargetIds, id]);
    }
  };

  const handleSelectAllTargets = () => {
    if (selectedTargetIds.length === filtered.length) {
      setSelectedTargetIds([]);
    } else {
      setSelectedTargetIds(filtered.map((w) => w.id));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (mode === "COPY_FROM" && !selectedSourceId) {
      setErrorMsg("Please select a source worksite to copy from.");
      return;
    }
    if (mode === "COPY_TO" && selectedTargetIds.length === 0) {
      setErrorMsg("Please select at least one target worksite to copy to.");
      return;
    }

    setLoading(true);
    try {
      let url = "";
      let body: any = {};

      if (mode === "COPY_FROM") {
        url = `/api/v1/worksites/${worksiteId}/copy-boundary`;
        body = { source_worksite_id: selectedSourceId };
      } else {
        url = `/api/v1/worksites/${worksiteId}/copy-boundary-to`;
        body = { target_worksite_ids: selectedTargetIds };
      }

      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to copy boundary.");
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Copy className="h-5 w-5 text-indigo-600" />
              {mode === "COPY_FROM" ? "Copy Boundary From Worksite" : "Copy Boundary To Worksites"}
            </h2>
            <p className="text-xs text-slate-500">
              Worksite {worksiteJobNumber} &bull; Shared boundary assignment
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
          {errorMsg && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Search */}
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by job number or name..."
              className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
          </div>

          {fetching ? (
            <div className="py-8 text-center text-slate-400">Loading worksites...</div>
          ) : mode === "COPY_FROM" ? (
            /* Radio list for source */
            <div className="space-y-1.5 max-h-60 overflow-y-auto border border-slate-200 rounded-lg p-2">
              {filtered
                .filter((w) => w.has_boundary)
                .map((w) => (
                  <label
                    key={w.id}
                    className={`flex items-center justify-between p-2 rounded cursor-pointer transition-colors ${
                      selectedSourceId === w.id
                        ? "bg-indigo-50 border border-indigo-200 text-indigo-900"
                        : "hover:bg-slate-50 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        type="radio"
                        name="source_worksite"
                        value={w.id}
                        checked={selectedSourceId === w.id}
                        onChange={() => setSelectedSourceId(w.id)}
                        className="text-indigo-600 focus:ring-indigo-500"
                      />
                      <div>
                        <span className="font-mono font-bold text-slate-900">{w.job_number}</span>
                        <span className="text-slate-600 ml-2">{w.job_name}</span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                      Has Boundary
                    </span>
                  </label>
                ))}
              {filtered.filter((w) => w.has_boundary).length === 0 && (
                <div className="py-6 text-center text-slate-400">
                  No other worksites with boundaries found.
                </div>
              )}
            </div>
          ) : (
            /* Checkbox list for targets */
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-medium text-[11px]">
                  Select target worksites ({selectedTargetIds.length} selected):
                </span>
                <button
                  type="button"
                  onClick={handleSelectAllTargets}
                  className="text-indigo-600 hover:text-indigo-800 font-semibold text-[11px]"
                >
                  {selectedTargetIds.length === filtered.length ? "Deselect All" : "Select All"}
                </button>
              </div>

              <div className="space-y-1.5 max-h-60 overflow-y-auto border border-slate-200 rounded-lg p-2">
                {filtered.map((w) => {
                  const isChecked = selectedTargetIds.includes(w.id);
                  return (
                    <label
                      key={w.id}
                      className={`flex items-center justify-between p-2 rounded cursor-pointer transition-colors ${
                        isChecked
                          ? "bg-indigo-50 border border-indigo-200 text-indigo-900"
                          : "hover:bg-slate-50 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleTargetId(w.id)}
                          className="rounded text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <span className="font-mono font-bold text-slate-900">{w.job_number}</span>
                          <span className="text-slate-600 ml-2">{w.job_name}</span>
                        </div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          w.has_boundary
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {w.has_boundary ? "Overwrite Existing" : "Unset"}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="pt-3 border-t border-slate-200 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-1.5 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {loading
                ? "Copying..."
                : mode === "COPY_FROM"
                ? "Copy to This Worksite"
                : `Copy to ${selectedTargetIds.length} Worksite(s)`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
