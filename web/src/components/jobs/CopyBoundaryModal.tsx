import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { Copy, Search } from "lucide-react";
import { AlertBanner, Button, Modal, ScrollArea, describeError, ensureOk, type FieldError } from "../../ui";

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
  boundaryGeojson?: any;
  mode: "COPY_FROM" | "COPY_TO";
  onSuccess: () => void;
}

function toWktPolygon(geojson: any): string {
  if (!geojson) return "";
  let coords = geojson.coordinates;
  if (geojson.type === "Feature" && geojson.geometry) {
    coords = geojson.geometry.coordinates;
  }
  if (!coords || !coords[0]) return "";
  const ring = coords[0];
  const pts = ring.map((pt: number[]) => `${pt[0]} ${pt[1]}`).join(", ");
  return `POLYGON((${pts}))`;
}

export const CopyBoundaryModal: React.FC<CopyBoundaryModalProps> = ({
  isOpen,
  onClose,
  worksiteId,
  worksiteJobNumber,
  boundaryGeojson,
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
  const [errorFields, setErrorFields] = useState<FieldError[]>([]);
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);

  const handleCopyGeoJson = () => {
    if (!boundaryGeojson) return;
    navigator.clipboard.writeText(JSON.stringify(boundaryGeojson, null, 2));
    setCopiedFormat("GeoJSON");
    setTimeout(() => setCopiedFormat(null), 2500);
  };

  const handleCopyWkt = () => {
    if (!boundaryGeojson) return;
    const wkt = toWktPolygon(boundaryGeojson);
    navigator.clipboard.writeText(wkt);
    setCopiedFormat("WKT");
    setTimeout(() => setCopiedFormat(null), 2500);
  };

  useEffect(() => {
    if (!isOpen) return;

    const fetchCandidates = async () => {
      setFetching(true);
      setErrorMsg("");
      try {
        const res = await fetch("/api/v1/worksites?limit=200", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        await ensureOk(res, "Failed to load candidate worksites.");
        const all: WorksiteOption[] = await res.json();
        // Filter out current worksite
        setWorksites(all.filter((w) => w.id !== worksiteId));
      } catch (err: unknown) {
        setErrorMsg(describeError(err, "Failed to load candidate worksites.").message);
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
    setErrorFields([]);

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

      await ensureOk(res, "Failed to copy boundary.");

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const info = describeError(err, "Failed to copy boundary.");
      setErrorMsg(info.message);
      setErrorFields(info.fields);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      dismissible={!loading}
      size="md"
      title={mode === "COPY_FROM" ? "Copy Boundary From Worksite" : "Copy Boundary To Worksites"}
      description={`Worksite ${worksiteJobNumber} \u2022 Shared boundary assignment`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" form="copy-boundary-form" loading={loading}>
            {mode === "COPY_FROM" ? "Copy to This Worksite" : `Copy to ${selectedTargetIds.length} Worksite(s)`}
          </Button>
        </>
      }
    >
        <form id="copy-boundary-form" onSubmit={handleSubmit} className="space-y-4 text-xs">
          {errorMsg && (
            <AlertBanner tone="error" fields={errorFields}>
              {errorMsg}
            </AlertBanner>
          )}

          {/* Format Copy Section */}
          {mode === "COPY_TO" && boundaryGeojson && (
            <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-lg space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                  <Copy className="h-3.5 w-3.5 text-indigo-600" />
                  Copy to Clipboard (GIS / Mobile Proxy)
                </span>
                {copiedFormat && (
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                    ✓ Copied {copiedFormat}!
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 leading-tight">
                Copy this worksite's boundary coordinates directly to your clipboard for testing in the mobile simulator or GIS tools.
              </p>
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleCopyGeoJson}
                  className="px-3 py-1 bg-white hover:bg-slate-50 border border-indigo-300 rounded text-xs font-semibold text-indigo-700 flex items-center gap-1.5 shadow-2xs transition-colors"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy GeoJSON
                </button>
                <button
                  type="button"
                  onClick={handleCopyWkt}
                  className="px-3 py-1 bg-white hover:bg-slate-50 border border-cyan-300 rounded text-xs font-semibold text-cyan-800 flex items-center gap-1.5 shadow-2xs transition-colors"
                >
                  <Copy className="h-3.5 w-3.5 text-cyan-600" />
                  Copy WKT
                </button>
              </div>
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
            <ScrollArea maxHeight={240} className="space-y-1.5 border border-slate-200 rounded-lg p-2">
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
            </ScrollArea>
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

              <ScrollArea maxHeight={240} className="space-y-1.5 border border-slate-200 rounded-lg p-2">
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
              </ScrollArea>
            </div>
          )}
        </form>
    </Modal>
  );
};
