import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  Radio,
  Search,
  ExternalLink,
  ChevronRight,
  RefreshCw,
  X,
  Navigation,
} from "lucide-react";
import { MapContainer } from "../features/map";
import { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";

interface TodayAssignment {
  worksite_id?: string;
  worksite_name?: string;
  assigned_hours?: number;
  group_id?: string;
  group_name?: string;
  zone_name?: string;
}

interface LiveWorker {
  employee_id: string;
  tally_id: string;
  name: string;
  role: string;
  supervisor_id?: string | null;
  supervisor_name?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  zone_id?: string | null;
  zone_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  accuracy_meters?: number | null;
  event_type: string;
  event_timestamp_utc: string;
  received_at_utc: string;
  last_contact_at: string;
  age_seconds: number;
  contact_age_seconds: number;
  tracking_enabled: boolean;
  server_verdict?: string | null;
  server_site_id?: string | null;
  server_site_name?: string | null;
  live_state: "ACTIVE" | "NO_RECENT_SIGNAL" | "LOCATION_DISABLED" | "NOT_SCHEDULED";
  has_schedule_today: boolean;
  today_assignments: TodayAssignment[];
}

interface TrailPoint {
  event_id: string;
  event_type: string;
  latitude: number;
  longitude: number;
  event_timestamp_utc: string;
  server_verdict?: string | null;
  server_site_name?: string | null;
}

function formatAge(seconds: number): string {
  if (seconds < 0) return "Never";
  if (seconds < 60) return `${seconds}s ago`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hours}h ${remMins}m ago`;
}

export const LiveMap: React.FC = () => {
  const { token } = useAuth();
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);

  const [workers, setWorkers] = useState<LiveWorker[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionMode, setConnectionMode] = useState<"LIVE" | "POLLING">("LIVE");
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [trailPoints, setTrailPoints] = useState<TrailPoint[]>([]);
  const [loadingTrail, setLoadingTrail] = useState(false);
  const [trailDate, setTrailDate] = useState<string>(new Date().toISOString().split("T")[0]);
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [replaySpeed, setReplaySpeed] = useState<number>(5);

  // Filters
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [supervisorFilter, setSupervisorFilter] = useState<string>("ALL");

  // Summary counts
  const [summary, setSummary] = useState({
    total: 0,
    active: 0,
    no_recent_signal: 0,
    location_disabled: 0,
    not_scheduled: 0,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Fetch initial live positions via REST
  const fetchPositions = useCallback(async () => {
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch("/api/v1/live/positions", { headers });
      if (res.ok) {
        const data = await res.json();
        setWorkers(data.items || []);
        if (data.summary) {
          setSummary({
            total: data.summary.total || 0,
            active: data.summary.active || 0,
            no_recent_signal: data.summary.no_recent_signal || 0,
            location_disabled: data.summary.location_disabled || 0,
            not_scheduled: data.summary.not_scheduled || 0,
          });
        }
      }
    } catch (err) {
      console.error("Failed to fetch live positions:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // 2. Setup SSE stream with 30s polling fallback
  useEffect(() => {
    let isCancelled = false;

    const setupStream = async () => {
      try {
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const ticketRes = await fetch("/api/v1/live/stream-ticket", {
          method: "POST",
          headers,
        });

        if (!ticketRes.ok) {
          throw new Error("Could not acquire stream ticket");
        }

        const { ticket } = await ticketRes.json();
        if (isCancelled) return;

        const es = new EventSource(`/api/v1/live/stream?ticket=${ticket}`);
        eventSourceRef.current = es;

        es.onopen = () => {
          if (!isCancelled) setConnectionMode("LIVE");
        };

        es.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.type === "UPDATE" && payload.data) {
              const updatedItem: LiveWorker = payload.data;
              setWorkers((prev) => {
                const idx = prev.findIndex((w) => w.employee_id === updatedItem.employee_id);
                if (idx >= 0) {
                  const next = [...prev];
                  next[idx] = { ...next[idx], ...updatedItem };
                  return next;
                }
                return [updatedItem, ...prev];
              });
            }
          } catch (e) {
            console.error("Failed to parse SSE payload", e);
          }
        };

        es.onerror = () => {
          console.warn("SSE connection error, falling back to 30s polling");
          es.close();
          eventSourceRef.current = null;
          if (!isCancelled) {
            setConnectionMode("POLLING");
            startPollingFallback();
          }
        };
      } catch (err) {
        console.warn("Could not establish SSE stream, using polling fallback:", err);
        if (!isCancelled) {
          setConnectionMode("POLLING");
          startPollingFallback();
        }
      }
    };

    const startPollingFallback = () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(() => {
        fetchPositions();
      }, 30000);
    };

    fetchPositions();
    setupStream();

    return () => {
      isCancelled = true;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [fetchPositions, token]);

  // 3. Load Boundaries (Worksites & Accommodations) onto Map
  useEffect(() => {
    if (!mapInstance) return;

    let isMounted = true;
    const loadBoundaries = async () => {
      try {
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch("/api/v1/boundary-queue?limit=200", { headers });
        if (!res.ok) return;
        const data = await res.json();
        if (!isMounted || !mapInstance) return;

        const siteFeatures: GeoJSON.Feature[] = [];
        const accFeatures: GeoJSON.Feature[] = [];

        (data.items || []).forEach((item: any) => {
          if (item.boundary_geojson) {
            const feat: GeoJSON.Feature = {
              type: "Feature",
              properties: {
                id: item.id,
                code: item.code,
                name: item.name,
                type: item.entity_type,
              },
              geometry: item.boundary_geojson,
            };
            if (item.entity_type === "WORKSITE") {
              siteFeatures.push(feat);
            } else {
              accFeatures.push(feat);
            }
          }
        });

        // Add or update Worksites Source & Layers
        if (!mapInstance.getSource("worksites-polygons")) {
          mapInstance.addSource("worksites-polygons", {
            type: "geojson",
            data: { type: "FeatureCollection", features: siteFeatures },
          });

          mapInstance.addLayer({
            id: "worksites-fill",
            type: "fill",
            source: "worksites-polygons",
            paint: {
              "fill-color": "#3b82f6",
              "fill-opacity": 0.15,
            },
          });

          mapInstance.addLayer({
            id: "worksites-outline",
            type: "line",
            source: "worksites-polygons",
            paint: {
              "line-color": "#2563eb",
              "line-width": 2,
            },
          });
        } else {
          (mapInstance.getSource("worksites-polygons") as GeoJSONSource).setData({
            type: "FeatureCollection",
            features: siteFeatures,
          });
        }

        // Add or update Accommodations Source & Layers
        if (!mapInstance.getSource("accommodations-polygons")) {
          mapInstance.addSource("accommodations-polygons", {
            type: "geojson",
            data: { type: "FeatureCollection", features: accFeatures },
          });

          mapInstance.addLayer({
            id: "accommodations-fill",
            type: "fill",
            source: "accommodations-polygons",
            paint: {
              "fill-color": "#a855f7",
              "fill-opacity": 0.15,
            },
          });

          mapInstance.addLayer({
            id: "accommodations-outline",
            type: "line",
            source: "accommodations-polygons",
            paint: {
              "line-color": "#9333ea",
              "line-width": 2,
              "line-dasharray": [2, 2],
            },
          });
        } else {
          (mapInstance.getSource("accommodations-polygons") as GeoJSONSource).setData({
            type: "FeatureCollection",
            features: accFeatures,
          });
        }
      } catch (e) {
        console.error("Failed to load map boundaries", e);
      }
    };

    if (mapInstance.isStyleLoaded()) {
      loadBoundaries();
    } else {
      mapInstance.once("load", loadBoundaries);
    }

    return () => {
      isMounted = false;
    };
  }, [mapInstance, token]);

  // 4. Update Worker GeoJSON Source & Clusters on Map
  useEffect(() => {
    if (!mapInstance) return;

    const workerFeatures: GeoJSON.Feature[] = workers
      .filter((w) => w.latitude !== null && w.longitude !== null && w.latitude !== undefined && w.longitude !== undefined)
      .map((w) => ({
        type: "Feature",
        properties: {
          employee_id: w.employee_id,
          name: w.name,
          tally_id: w.tally_id,
          live_state: w.live_state,
          event_type: w.event_type,
          server_verdict: w.server_verdict || "UNKNOWN",
        },
        geometry: {
          type: "Point",
          coordinates: [Number(w.longitude), Number(w.latitude)],
        },
      }));

    const updateWorkerLayers = () => {
      if (!mapInstance) return;

      if (!mapInstance.getSource("worker-positions")) {
        mapInstance.addSource("worker-positions", {
          type: "geojson",
          data: { type: "FeatureCollection", features: workerFeatures },
          cluster: true,
          clusterMaxZoom: 13,
          clusterRadius: 40,
        });

        // Cluster circle
        mapInstance.addLayer({
          id: "worker-clusters",
          type: "circle",
          source: "worker-positions",
          filter: ["has", "point_count"],
          paint: {
            "circle-color": [
              "step",
              ["get", "point_count"],
              "#3b82f6",
              10,
              "#f59e0b",
              30,
              "#ef4444",
            ],
            "circle-radius": [
              "step",
              ["get", "point_count"],
              18,
              10,
              24,
              30,
              30,
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Cluster count text
        mapInstance.addLayer({
          id: "worker-cluster-count",
          type: "symbol",
          source: "worker-positions",
          filter: ["has", "point_count"],
          layout: {
            "text-field": "{point_count_abbreviated}",
            "text-size": 12,
          },
          paint: {
            "text-color": "#ffffff",
          },
        });

        // Unclustered worker points
        mapInstance.addLayer({
          id: "worker-unclustered",
          type: "circle",
          source: "worker-positions",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": [
              "match",
              ["get", "live_state"],
              "ACTIVE",
              "#10b981",
              "LOCATION_DISABLED",
              "#f97316",
              "NO_RECENT_SIGNAL",
              "#eab308",
              "#64748b", // NOT_SCHEDULED
            ],
            "circle-radius": 8,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Click on cluster zooms in
        mapInstance.on("click", "worker-clusters", (e) => {
          const features = mapInstance.queryRenderedFeatures(e.point, {
            layers: ["worker-clusters"],
          });
          const clusterId = features[0]?.properties?.cluster_id;
          const source = mapInstance.getSource("worker-positions") as GeoJSONSource;
          if (clusterId && source && typeof (source as any).getClusterExpansionZoom === "function") {
            (source as any).getClusterExpansionZoom(clusterId, (err: any, zoom: number) => {
              if (err) return;
              const coords = (features[0].geometry as GeoJSON.Point).coordinates;
              mapInstance.easeTo({
                center: [coords[0], coords[1]],
                zoom,
              });
            });
          }
        });

        // Click on individual worker
        mapInstance.on("click", "worker-unclustered", (e) => {
          const feature = e.features?.[0];
          if (feature && feature.properties?.employee_id) {
            setSelectedWorkerId(feature.properties.employee_id);
          }
        });

        // Cursor pointer styling
        mapInstance.on("mouseenter", "worker-clusters", () => {
          mapInstance.getCanvas().style.cursor = "pointer";
        });
        mapInstance.on("mouseleave", "worker-clusters", () => {
          mapInstance.getCanvas().style.cursor = "";
        });
        mapInstance.on("mouseenter", "worker-unclustered", () => {
          mapInstance.getCanvas().style.cursor = "pointer";
        });
        mapInstance.on("mouseleave", "worker-unclustered", () => {
          mapInstance.getCanvas().style.cursor = "";
        });
      } else {
        const source = mapInstance.getSource("worker-positions") as GeoJSONSource;
        source.setData({
          type: "FeatureCollection",
          features: workerFeatures,
        });
      }
    };

    if (mapInstance.isStyleLoaded()) {
      updateWorkerLayers();
    } else {
      mapInstance.once("load", updateWorkerLayers);
    }
  }, [mapInstance, workers]);

  // 5. Fetch Trail points when worker or trailDate changes
  useEffect(() => {
    if (!selectedWorkerId) {
      setTrailPoints([]);
      setIsReplaying(false);
      setReplayIndex(0);
      if (mapInstance && mapInstance.getSource("worker-trail")) {
        (mapInstance.getSource("worker-trail") as GeoJSONSource).setData({
          type: "FeatureCollection",
          features: [],
        });
      }
      if (mapInstance && mapInstance.getSource("replay-marker")) {
        (mapInstance.getSource("replay-marker") as GeoJSONSource).setData({
          type: "FeatureCollection",
          features: [],
        });
      }
      return;
    }

    let isMounted = true;
    setIsReplaying(false);
    setReplayIndex(0);

    const fetchTrail = async () => {
      setLoadingTrail(true);
      try {
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(`/api/v1/live/trail/${selectedWorkerId}?date=${trailDate}`, { headers });
        if (res.ok) {
          const data = await res.json();
          if (!isMounted) return;
          const points: TrailPoint[] = Array.isArray(data) ? data : (data.points || []);
          setTrailPoints(points);

          // Update Trail Layer on Map
          if (mapInstance) {
            const coordinates = points.map((p) => [p.longitude, p.latitude]);
            const trailGeoJSON: GeoJSON.FeatureCollection = {
              type: "FeatureCollection",
              features: coordinates.length > 1
                ? [
                    {
                      type: "Feature",
                      properties: {},
                      geometry: {
                        type: "LineString",
                        coordinates,
                      },
                    },
                  ]
                : [],
            };

            if (!mapInstance.getSource("worker-trail")) {
              mapInstance.addSource("worker-trail", {
                type: "geojson",
                data: trailGeoJSON,
              });

              mapInstance.addLayer({
                id: "worker-trail-line",
                type: "line",
                source: "worker-trail",
                layout: {
                  "line-join": "round",
                  "line-cap": "round",
                },
                paint: {
                  "line-color": "#3b82f6",
                  "line-width": 3,
                  "line-dasharray": [1, 1],
                },
              });
            } else {
              (mapInstance.getSource("worker-trail") as GeoJSONSource).setData(trailGeoJSON);
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch trail:", err);
      } finally {
        if (isMounted) setLoadingTrail(false);
      }
    };

    fetchTrail();

    return () => {
      isMounted = false;
    };
  }, [selectedWorkerId, trailDate, mapInstance, token]);

  // 6. Animate replay ticker
  useEffect(() => {
    if (!isReplaying || trailPoints.length === 0) return;
    const intervalMs = Math.max(80, Math.round(1000 / replaySpeed));
    const timer = setInterval(() => {
      setReplayIndex((prev) => {
        if (prev >= trailPoints.length - 1) {
          setIsReplaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, intervalMs);
    return () => clearInterval(timer);
  }, [isReplaying, trailPoints.length, replaySpeed]);

  // 7. Update replay marker on map when replayIndex changes
  useEffect(() => {
    if (!mapInstance) return;
    if (!selectedWorkerId || trailPoints.length === 0) {
      if (mapInstance.getSource("replay-marker")) {
        (mapInstance.getSource("replay-marker") as GeoJSONSource).setData({
          type: "FeatureCollection",
          features: [],
        });
      }
      return;
    }

    const currentPt = trailPoints[replayIndex];
    if (!currentPt) return;

    const replayGeoJSON: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {
            event_type: currentPt.event_type,
            timestamp: currentPt.event_timestamp_utc,
          },
          geometry: {
            type: "Point",
            coordinates: [currentPt.longitude, currentPt.latitude],
          },
        },
      ],
    };

    if (!mapInstance.getSource("replay-marker")) {
      mapInstance.addSource("replay-marker", {
        type: "geojson",
        data: replayGeoJSON,
      });

      mapInstance.addLayer({
        id: "replay-marker-glow",
        type: "circle",
        source: "replay-marker",
        paint: {
          "circle-color": "#f59e0b",
          "circle-radius": 14,
          "circle-opacity": 0.45,
        },
      });

      mapInstance.addLayer({
        id: "replay-marker-core",
        type: "circle",
        source: "replay-marker",
        paint: {
          "circle-color": "#d97706",
          "circle-radius": 7,
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#ffffff",
        },
      });
    } else {
      (mapInstance.getSource("replay-marker") as GeoJSONSource).setData(replayGeoJSON);
    }

    // Auto-pan if replaying
    if (isReplaying) {
      mapInstance.easeTo({
        center: [currentPt.longitude, currentPt.latitude],
        duration: 250,
      });
    }
  }, [mapInstance, replayIndex, trailPoints, selectedWorkerId, isReplaying]);

  // Filtered workers for side panel
  const filteredWorkers = workers.filter((w) => {
    if (stateFilter !== "ALL" && w.live_state !== stateFilter) return false;
    if (supervisorFilter !== "ALL" && w.supervisor_id !== supervisorFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        w.name.toLowerCase().includes(q) ||
        w.tally_id.toLowerCase().includes(q) ||
        (w.supervisor_name && w.supervisor_name.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const selectedWorker = workers.find((w) => w.employee_id === selectedWorkerId);

  // Focus map on worker
  const handleSelectWorker = (worker: LiveWorker) => {
    setSelectedWorkerId(worker.employee_id);
    if (mapInstance && worker.latitude && worker.longitude) {
      mapInstance.easeTo({
        center: [Number(worker.longitude), Number(worker.latitude)],
        zoom: 16,
      });
    }
  };

  // Distinct supervisors for dropdown
  const supervisors = Array.from(
    new Map(
      workers
        .filter((w) => w.supervisor_id && w.supervisor_name)
        .map((w) => [w.supervisor_id as string, w.supervisor_name as string])
    ).entries()
  );

  return (
    <div className="flex flex-col h-full w-full bg-slate-50 overflow-hidden">
      {/* Top Banner / Summary Counters */}
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
            <Radio className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Live Workforce Map</h1>
            <p className="text-xs text-slate-500">Real-time GPS fixes and device connectivity</p>
          </div>
        </div>

        {/* Stats badges */}
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-ping" />
            Active: {summary.active}
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            No Recent Signal: {summary.no_recent_signal}
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
            Location Disabled: {summary.location_disabled}
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            Not Scheduled: {summary.not_scheduled}
          </span>
        </div>

        {/* Connection status indicator */}
        <div className="flex items-center gap-2">
          {connectionMode === "LIVE" ? (
            <span className="flex items-center text-xs font-medium text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-500 mr-1.5" />
              Live Stream (SSE)
            </span>
          ) : (
            <span className="flex items-center text-xs font-medium text-amber-600 bg-amber-50 px-2.5 py-1 rounded-md border border-amber-200">
              <RefreshCw className="h-3 w-3 mr-1.5 animate-spin" />
              Refreshing every 30s
            </span>
          )}
          <button
            onClick={() => fetchPositions()}
            className="p-1.5 text-slate-500 hover:text-slate-800 rounded hover:bg-slate-100 transition-colors"
            title="Manual refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Main Content Area: Map + Side Panel */}
      <div className="flex-1 flex overflow-hidden relative min-h-0">
        {/* Map Container */}
        <div className="flex-1 h-full w-full relative">
          <MapContainer
            className="w-full h-full rounded-none border-0"
            initialZoom={12}
            onMapReady={(map) => setMapInstance(map)}
            onMapUnmount={() => setMapInstance(null)}
          />
        </div>

        {/* Side Panel for Worker List & Details */}
        <div className="w-96 bg-white border-l border-slate-200 flex flex-col z-10 shadow-lg min-h-0 overflow-hidden">
          {/* Search & Filters */}
          <div className="p-4 border-b border-slate-200 space-y-3 bg-white">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search worker or tally ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex gap-2">
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="flex-1 text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ALL">All States ({workers.length})</option>
                <option value="ACTIVE">Active ({summary.active})</option>
                <option value="NO_RECENT_SIGNAL">No Recent Signal ({summary.no_recent_signal})</option>
                <option value="LOCATION_DISABLED">Location Disabled ({summary.location_disabled})</option>
                <option value="NOT_SCHEDULED">Not Scheduled ({summary.not_scheduled})</option>
              </select>

              {supervisors.length > 0 && (
                <select
                  value={supervisorFilter}
                  onChange={(e) => setSupervisorFilter(e.target.value)}
                  className="flex-1 text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ALL">All Supervisors</option>
                  {supervisors.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Worker List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loading ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading workers...</div>
            ) : filteredWorkers.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No workers found matching filters.</div>
            ) : (
              filteredWorkers.map((worker) => {
                const isSelected = worker.employee_id === selectedWorkerId;
                const stateColor =
                  worker.live_state === "ACTIVE"
                    ? "bg-emerald-500"
                    : worker.live_state === "LOCATION_DISABLED"
                    ? "bg-orange-500"
                    : worker.live_state === "NO_RECENT_SIGNAL"
                    ? "bg-amber-400"
                    : "bg-slate-400";

                const stateText =
                  worker.live_state === "ACTIVE"
                    ? "Active"
                    : worker.live_state === "LOCATION_DISABLED"
                    ? "Location Disabled"
                    : worker.live_state === "NO_RECENT_SIGNAL"
                    ? "No Recent Signal"
                    : "Not Scheduled";

                return (
                  <div
                    key={worker.employee_id}
                    onClick={() => handleSelectWorker(worker)}
                    className={`p-3.5 cursor-pointer transition-colors hover:bg-slate-50 flex items-start justify-between ${
                      isSelected ? "bg-blue-50/70 border-l-4 border-blue-600" : ""
                    }`}
                  >
                    <div className="space-y-1 pr-2 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2.5 h-2.5 rounded-full ${stateColor} shrink-0`} />
                        <span className="font-semibold text-sm text-slate-900 truncate">{worker.name}</span>
                        <span className="text-xs text-slate-400 shrink-0">({worker.tally_id})</span>
                      </div>

                      <div className="text-xs text-slate-500 flex items-center gap-1.5">
                        <span className="font-medium text-slate-600">{stateText}</span>
                        <span>•</span>
                        <span>{worker.role}</span>
                      </div>

                      {/* Two Ages: Fix Age and Contact Age */}
                      <div className="text-[11px] text-slate-400 flex flex-wrap items-center gap-x-2">
                        <span>GPS: {formatAge(worker.age_seconds)}</span>
                        <span>•</span>
                        <span>Contact: {formatAge(worker.contact_age_seconds)}</span>
                      </div>

                      {worker.today_assignments && worker.today_assignments.length > 0 && (
                        <div className="text-xs text-blue-700 bg-blue-50/80 px-2 py-0.5 rounded border border-blue-100 truncate inline-block max-w-full">
                          📍 {worker.today_assignments[0].worksite_name}
                        </div>
                      )}
                    </div>

                    <ChevronRight className="h-4 w-4 text-slate-300 shrink-0 mt-1" />
                  </div>
                );
              })
            )}
          </div>

          {/* Selected Worker Detail Drawer/Card at Bottom of Side Panel */}
          {selectedWorker && (
            <div className="border-t-2 border-slate-200 bg-white p-4 shadow-inner space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">{selectedWorker.name}</h3>
                  <p className="text-xs text-slate-500">{selectedWorker.tally_id} • {selectedWorker.role}</p>
                </div>
                <button
                  onClick={() => setSelectedWorkerId(null)}
                  className="text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Two Ages breakdown */}
              <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Position Age</span>
                  <span className="font-semibold text-slate-800">{formatAge(selectedWorker.age_seconds)}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Device Contact</span>
                  <span className="font-semibold text-slate-800">{formatAge(selectedWorker.contact_age_seconds)}</span>
                </div>
                <div className="col-span-2 pt-1 border-t border-slate-200/60 flex items-center justify-between">
                  <span className="text-slate-500">Verdict:</span>
                  <span className="font-medium text-slate-800">{selectedWorker.server_verdict || "UNKNOWN"}</span>
                </div>
                {selectedWorker.supervisor_name && (
                  <div className="col-span-2 flex items-center justify-between">
                    <span className="text-slate-500">Supervisor:</span>
                    <span className="font-medium text-slate-800">{selectedWorker.supervisor_name}</span>
                  </div>
                )}
              </div>

              {/* Day Trail & Journey Replay Section */}
              <div className="space-y-2 pt-1 border-t border-slate-200">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700">Journey Trail:</span>
                  <input
                    type="date"
                    value={trailDate}
                    onChange={(e) => setTrailDate(e.target.value)}
                    className="border border-slate-300 rounded px-2 py-0.5 text-xs text-slate-700 font-mono bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                {loadingTrail ? (
                  <div className="text-xs text-blue-600 animate-pulse text-center py-2 bg-blue-50/50 rounded">
                    Loading trail points...
                  </div>
                ) : trailPoints.length > 0 ? (
                  <div className="bg-slate-900 text-white p-3 rounded-xl space-y-2 border border-slate-700 shadow-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                        <span>▶️</span> Journey Replay
                      </span>
                      <span className="text-[11px] font-mono text-slate-300">
                        {new Date(trailPoints[replayIndex]?.event_timestamp_utc || "").toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </span>
                    </div>

                    {/* Timeline Slider / Scrubber */}
                    <div className="space-y-1">
                      <input
                        type="range"
                        min={0}
                        max={trailPoints.length - 1}
                        value={replayIndex}
                        onChange={(e) => {
                          setReplayIndex(Number(e.target.value));
                          if (isReplaying) setIsReplaying(false);
                        }}
                        className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                        <span>{new Date(trailPoints[0].event_timestamp_utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        <span className="text-amber-300 font-bold">
                          Step {replayIndex + 1}/{trailPoints.length} ({trailPoints[replayIndex]?.event_type})
                        </span>
                        <span>{new Date(trailPoints[trailPoints.length - 1].event_timestamp_utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                      </div>
                    </div>

                    {/* Controls & Speed Selector */}
                    <div className="flex items-center justify-between pt-1">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => setIsReplaying(!isReplaying)}
                          className="px-3 py-1 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded text-xs flex items-center gap-1 transition"
                        >
                          {isReplaying ? "⏸ Pause" : "▶ Replay"}
                        </button>
                        <button
                          onClick={() => {
                            setIsReplaying(false);
                            setReplayIndex(0);
                          }}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition"
                          title="Reset to beginning"
                        >
                          ↺
                        </button>
                      </div>

                      <div className="flex items-center gap-1 text-[10px] font-mono">
                        {[1, 5, 10, 30].map((s) => (
                          <button
                            key={s}
                            onClick={() => setReplaySpeed(s)}
                            className={`px-1.5 py-0.5 rounded transition ${
                              replaySpeed === s ? "bg-amber-500 text-slate-950 font-bold" : "bg-slate-800 text-slate-400 hover:text-white"
                            }`}
                          >
                            {s}x
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-400 text-center py-2 bg-slate-50 rounded border border-slate-200">
                    No trail recorded for {trailDate}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-1">
                <Link
                  to="/attendance"
                  search={{ employee_id: selectedWorker.employee_id } as any}
                  className="flex-1 py-1.5 px-3 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  View Timeline
                </Link>
                {selectedWorker.latitude && selectedWorker.longitude && (
                  <button
                    onClick={() => {
                      if (mapInstance) {
                        mapInstance.easeTo({
                          center: [Number(selectedWorker.longitude), Number(selectedWorker.latitude)],
                          zoom: 16,
                        });
                      }
                    }}
                    className="p-1.5 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50"
                    title="Center on map"
                  >
                    <Navigation className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
