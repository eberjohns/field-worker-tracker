// FWT Mobile Tester Proxy & GPS Route Player
// Phase 07 Mobile Contract & Android Studio Style Simulator

(function () {
  // Global Application State
  const state = {
    apiUrl: 'http://localhost:8000/api/v1',
    token: localStorage.getItem('fwt_mobile_token') || null,
    worker: null,
    device: {
      identifier: 'DEV_SIM_1193_A',
      platform: 'ANDROID',
      model: 'Pixel 8 Pro (Sim)',
      app_version: '1.0.0-phase07',
      os_version: 'Android 14',
    },
    cursor: 0,
    synced: {
      profile: null,
      settings: null,
      jobs: [],
      accommodation: null,
      dayPlans: [],
      scheduleItems: [],
    },
    simulatedDate: new Date().toISOString().split('T')[0], // Active simulation work date (constrained to past 1-7 days)
    activeTab: 'today', // 'today', 'gps', 'roster', 'profile', 'sync'
    currentZone: 'UNKNOWN',
    currentWorksiteId: null,
    workerLocation: { lat: 25.14, lng: 55.40 }, // Default map center
    eventsQueue: [],
    networkTraffic: [],
    map: null,
    workerMarker: null,
    routePolyline: null,
    drawnPolyline: null,
    drawnMarkers: [],
    isDrawingMode: false,
    drawnWaypoints: [],
    // Custom Polygon Drawing Engine
    isPolyDrawing: false,
    polyPoints: [],
    polyMarkers: [],
    polyLinePreview: null,
    customPolygonLayer: null,
    pastedPolygonLayer: null,
    pastedPolygonMarker: null,
    layers: {
      worksites: [],
      geofences: [],
      accommodation: null,
    },
    // Route Playback Engine
    route: {
      isPlaying: false,
      speed: 10,
      progress: 0, // 0.0 to 1.0
      currentTimeStr: '05:00:00',
      waypoints: [],
      lastTimestamp: null,
      animId: null,
      lastPingSimSecs: 0,
    },
  };

  // Preset Route Definitions (Matching Real UAE Placement)
  const PRESET_ROUTES = {
    standard: {
      name: 'Standard Workday (06:02 Site Entry - 15:31 Exit)',
      waypoints: [
        { time: '05:00:00', lat: 25.15825, lng: 55.41225, label: 'Warsan Staff Camp' },
        { time: '05:35:00', lat: 25.15300, lng: 55.40700, label: 'Leaving Camp Perimeter' },
        { time: '05:48:00', lat: 25.14200, lng: 55.39500, label: 'Transit (Manama St)' },
        { time: '05:58:00', lat: 25.13350, lng: 55.38850, label: 'Geofence Buffer Approach (300m)' },
        { time: '06:02:00', lat: 25.13100, lng: 55.38400, label: 'Worksite Entry (Silicon Oasis)' },
        { time: '09:00:00', lat: 25.13150, lng: 55.38450, label: 'Mid-Morning Landscape Work' },
        { time: '12:00:00', lat: 25.13050, lng: 55.38350, label: 'Midday Rest on Site' },
        { time: '14:00:00', lat: 25.13110, lng: 55.38380, label: 'Afternoon Landscape Work' },
        { time: '15:31:00', lat: 25.12650, lng: 55.37800, label: 'Worksite Exit' },
        { time: '15:45:00', lat: 25.14500, lng: 55.39800, label: 'Return Transit' },
        { time: '16:00:00', lat: 25.15825, lng: 55.41225, label: 'Back at Warsan Staff Camp' },
      ],
    },
    late: {
      name: 'Late Arrival Shift (Arrives 08:30)',
      waypoints: [
        { time: '07:30:00', lat: 25.15825, lng: 55.41225, label: 'Late Departure Camp' },
        { time: '08:00:00', lat: 25.14200, lng: 55.39500, label: 'Commute Transit' },
        { time: '08:28:00', lat: 25.13350, lng: 55.38850, label: 'Geofence Buffer' },
        { time: '08:30:00', lat: 25.13100, lng: 55.38400, label: 'Late Worksite Entry' },
        { time: '12:00:00', lat: 25.13050, lng: 55.38350, label: 'Midday Work' },
        { time: '15:31:00', lat: 25.12650, lng: 55.37800, label: 'Worksite Exit' },
        { time: '16:00:00', lat: 25.15825, lng: 55.41225, label: 'Back at Camp' },
      ],
    },
    midday_gap: {
      name: 'Midday Gap (Leaves 11:30, Returns 13:00)',
      waypoints: [
        { time: '05:00:00', lat: 25.15825, lng: 55.41225, label: 'Inside Camp' },
        { time: '06:02:00', lat: 25.13100, lng: 55.38400, label: 'Worksite Entry' },
        { time: '11:30:00', lat: 25.12400, lng: 55.37000, label: 'Unauthorized Exit' },
        { time: '12:15:00', lat: 25.11500, lng: 55.36000, label: 'Offsite Roaming' },
        { time: '13:00:00', lat: 25.13100, lng: 55.38400, label: 'Re-entry to Worksite' },
        { time: '15:31:00', lat: 25.12650, lng: 55.37800, label: 'Final Exit' },
        { time: '16:00:00', lat: 25.15825, lng: 55.41225, label: 'Back at Camp' },
      ],
    },
  };

  // Toast Notification Helper
  function showToast(text) {
    const toast = document.getElementById('mapToast');
    const toastText = document.getElementById('mapToastText');
    if (!toast || !toastText) return;
    toastText.innerText = text;
    toast.classList.remove('hidden');
    setTimeout(() => {
      toast.classList.add('hidden');
    }, 2800);
  }

  // Network Inspector Logger
  function logNetwork(method, path, status, latencyMs, reqBody, resBody) {
    const el = document.getElementById('networkLogList');
    const line = document.createElement('div');
    const time = new Date().toISOString().split('T')[1].slice(0, 8);
    const isSuccess = status >= 200 && status < 300;
    const badgeColor = isSuccess
      ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
      : 'bg-rose-950 text-rose-400 border-rose-800';

    state.networkTraffic.push({
      timestamp: new Date().toISOString(),
      method,
      path,
      status,
      latency_ms: latencyMs,
      request_payload: reqBody,
      response_payload: resBody,
    });

    line.className = 'p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-850 cursor-pointer text-3xs font-mono transition';
    line.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="text-slate-500">[${time}]</span>
          <span class="font-bold text-sky-400">${method}</span>
          <span class="text-slate-300">${path}</span>
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-slate-500">${latencyMs}ms</span>
          <span class="px-1.5 py-0.2 rounded border font-bold ${badgeColor}">${status}</span>
        </div>
      </div>
      <div class="hidden payload-details mt-1 pt-1 border-t border-slate-800 text-slate-400">
        <div><strong>Request:</strong> <pre class="text-3xs text-slate-300 overflow-x-auto">${reqBody ? JSON.stringify(reqBody, null, 2) : 'null'}</pre></div>
        <div class="mt-1"><strong>Response:</strong> <pre class="text-3xs text-emerald-300 overflow-x-auto">${resBody ? JSON.stringify(resBody, null, 2) : 'null'}</pre></div>
      </div>
    `;

    line.addEventListener('click', () => {
      const details = line.querySelector('.payload-details');
      details.classList.toggle('hidden');
    });

    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  }

  // API Client with Timing & Auto-logout on 401
  async function api(path, options = {}) {
    const baseUrl = document.getElementById('apiUrl').value.replace(/\/+$/, '');
    const url = `${baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {}),
    };

    const startTime = performance.now();
    let reqBody = null;
    if (options.body) {
      try { reqBody = JSON.parse(options.body); } catch { reqBody = options.body; }
    }

    try {
      const res = await fetch(url, { ...options, headers });
      const latencyMs = Math.round(performance.now() - startTime);
      const data = await res.json().catch(() => null);

      logNetwork(options.method || 'GET', path, res.status, latencyMs, reqBody, data);

      if (res.status === 401) {
        // Token invalid or user deleted on backend
        state.token = null;
        localStorage.removeItem('fwt_mobile_token');
        setAuthenticatedState(false);
        throw new Error(data?.detail || data?.message || 'Session expired. Please sign in again.');
      }

      if (!res.ok) {
        throw new Error(data?.detail || data?.message || `HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      if (!err.message.includes('HTTP')) {
        logNetwork(options.method || 'GET', path, 0, Math.round(performance.now() - startTime), reqBody, { error: err.message });
      }
      throw err;
    }
  }

  // Geo Math & Geometry Formatters
  function isPointInPolygon(point, polygonCoordinates) {
    if (!polygonCoordinates || polygonCoordinates.length < 3) return false;
    const x = point.lng;
    const y = point.lat;
    let inside = false;
    for (let i = 0, j = polygonCoordinates.length - 1; i < polygonCoordinates.length; j = i++) {
      const xi = polygonCoordinates[i][0], yi = polygonCoordinates[i][1];
      const xj = polygonCoordinates[j][0], yj = polygonCoordinates[j][1];
      const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function haversineMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function toWktPolygon(coords) {
    if (!coords || coords.length === 0) return '';
    let ring = coords;
    // Check if coords is 3D (e.g. [[[lng, lat], ...]])
    if (Array.isArray(coords[0]) && Array.isArray(coords[0][0])) {
      ring = coords[0];
    } else if (Array.isArray(coords[0]) && typeof coords[0][0] === 'number') {
      // 2D: [[lng, lat], [lng, lat], ...]
      ring = coords;
    }
    const validPts = ring.filter(
      (pt) => Array.isArray(pt) && pt.length >= 2 && !isNaN(Number(pt[0])) && !isNaN(Number(pt[1]))
    );
    if (validPts.length === 0) return '';
    const pts = validPts
      .map((pt) => `${Number(pt[0]).toFixed(6)} ${Number(pt[1]).toFixed(6)}`)
      .join(', ');
    return `POLYGON((${pts}))`;
  }

  function getPolygonCentroid(coords) {
    if (!coords || coords.length === 0) return null;
    let ring = coords;
    if (Array.isArray(coords[0]) && Array.isArray(coords[0][0])) {
      ring = coords[0];
    }
    let sumLat = 0;
    let sumLng = 0;
    let count = 0;
    ring.forEach((pt) => {
      if (Array.isArray(pt) && pt.length >= 2 && !isNaN(Number(pt[0])) && !isNaN(Number(pt[1]))) {
        sumLng += Number(pt[0]);
        sumLat += Number(pt[1]);
        count++;
      }
    });
    return count > 0 ? { lat: sumLat / count, lng: sumLng / count } : null;
  }

  function copyToClipboard(text, entityName, format) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(`✓ Copied ${format} for "${entityName}" to clipboard!`);
    }).catch(() => {
      prompt(`Copy ${format} manually:`, text);
    });
  }

  // Time conversion helpers
  function timeStrToSeconds(str) {
    const parts = str.split(':').map(Number);
    return parts[0] * 3600 + parts[1] * 60 + (parts[2] || 0);
  }

  function secondsToTimeStr(secs) {
    const h = Math.floor(secs / 3600) % 24;
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function formatTimeAmPm(secs) {
    let h = Math.floor(secs / 3600) % 24;
    const m = Math.floor((secs % 3600) / 60);
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} ${ampm}`;
  }

  // Calculate Ground Truth Metrics (Calculates ONLY on REAL Server Boundaries)
  function calculateGroundTruthMetrics(waypoints) {
    if (!waypoints || waypoints.length < 2) return;

    let workedSecs = 0;
    let transitSecs = 0;
    let campSecs = 0;

    const campPoly = state.synced.accommodation?.boundary?.coordinates?.[0] || null;
    const worksitePolys = state.synced.jobs
      .filter((j) => j.boundary?.coordinates?.[0])
      .map((j) => j.boundary.coordinates[0]);

    // If server has no worksite boundary, display clean warning
    if (worksitePolys.length === 0) {
      document.getElementById('gtWorkedTime').innerText = '0h 00m (No Site Polygon)';
      document.getElementById('gtTransitTime').innerText = '--';
      document.getElementById('gtEventsCount').innerText = '0 ENTRY • 0 PING • 0 EXIT';
      return;
    }

    for (let i = 0; i < waypoints.length - 1; i++) {
      const p1 = waypoints[i];
      const p2 = waypoints[i + 1];
      const duration = timeStrToSeconds(p2.time) - timeStrToSeconds(p1.time);
      if (duration <= 0) continue;

      const midPt = { lat: (p1.lat + p2.lat) / 2, lng: (p1.lng + p2.lng) / 2 };
      let insideSite = false;
      let insideCamp = false;

      if (campPoly && isPointInPolygon(midPt, campPoly)) {
        insideCamp = true;
      }
      worksitePolys.forEach((poly) => {
        if (poly && isPointInPolygon(midPt, poly)) {
          insideSite = true;
        }
      });

      if (insideSite) {
        workedSecs += duration;
      } else if (insideCamp) {
        campSecs += duration;
      } else {
        transitSecs += duration;
      }
    }

    const workedMin = Math.round(workedSecs / 60);
    const workedH = Math.floor(workedMin / 60);
    const workedM = workedMin % 60;

    const transitMin = Math.round(transitSecs / 60);
    const transitH = Math.floor(transitMin / 60);
    const transitM = transitMin % 60;

    // Approximate confirmation ping count based on configured interval
    const confInterval = state.synced.settings?.confirmation_polling_interval_s || 300;
    const estPings = Math.max(1, Math.floor(workedSecs / confInterval));

    document.getElementById('gtWorkedTime').innerText = `${workedH}h ${String(workedM).padStart(2, '0')}m (${workedMin}m)`;
    document.getElementById('gtTransitTime').innerText = `${transitH}h ${String(transitM).padStart(2, '0')}m (${transitMin}m)`;
    document.getElementById('gtEventsCount').innerText = `1 ENTRY • ${estPings} PING • 1 EXIT`;
  }

  // Initialize Map Viewport
  function initMap() {
    state.map = L.map('map', { zoomControl: false }).setView([25.14, 55.40], 13);
    L.control.zoom({ position: 'topright' }).addTo(state.map);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(state.map);

    // Draggable Worker Marker
    const workerIcon = L.divIcon({
      className: 'custom-worker-pin',
      html: `
        <div class="relative flex items-center justify-center">
          <div class="w-8 h-8 bg-indigo-600 rounded-full border-2 border-white shadow-xl flex items-center justify-center text-white text-sm pulse-marker">
            👷
          </div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    state.workerMarker = L.marker([state.workerLocation.lat, state.workerLocation.lng], {
      draggable: true,
      icon: workerIcon,
    }).addTo(state.map);

    state.workerMarker.on('dragend', function (e) {
      const pos = e.target.getLatLng();
      updateWorkerPosition(pos.lat, pos.lng);
    });

    // Map Click Handler: Supports standard pin move, Manual Route Drawing, or Custom Polygon Tracing
    state.map.on('click', function (e) {
      if (state.isPolyDrawing) {
        addPolyVertex(e.latlng.lat, e.latlng.lng);
      } else if (state.isDrawingMode) {
        addDrawnWaypoint(e.latlng.lat, e.latlng.lng);
      } else {
        state.workerMarker.setLatLng(e.latlng);
        updateWorkerPosition(e.latlng.lat, e.latlng.lng);
      }
    });

    // Update map with no hardcoded fallback
    updateMapLayers();
  }

  // Add Waypoint in Manual Route Drawing Mode
  function addDrawnWaypoint(lat, lng) {
    const idx = state.drawnWaypoints.length;
    let nextSecs = 5 * 3600; // 05:00:00 start
    const stepMins = parseInt(document.getElementById('drawStepMinutes')?.value || '15', 10);
    if (idx > 0) {
      const lastSecs = timeStrToSeconds(state.drawnWaypoints[idx - 1].time);
      nextSecs = lastSecs + stepMins * 60; // Auto-increment by chosen interval
    }
    const timeStr = secondsToTimeStr(nextSecs);
    const label = idx === 0 ? 'Start Waypoint' : `Waypoint #${idx + 1} (+${stepMins}m)`;

    const wp = { time: timeStr, lat, lng, label };
    state.drawnWaypoints.push(wp);

    // Add visual waypoint marker pin on map
    const wpIcon = L.divIcon({
      className: 'waypoint-pin-wrap',
      html: `<div class="waypoint-pin w-6 h-6">${idx + 1}</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
    const marker = L.marker([lat, lng], { icon: wpIcon }).addTo(state.map);
    marker.bindTooltip(`<b>${timeStr}</b>: ${label}`, { permanent: false, direction: 'top' });
    state.drawnMarkers.push(marker);

    // Update drawn polyline
    renderDrawnPolyline();
    showToast(`Added point #${idx + 1} at ${timeStr} (+${stepMins}m)`);

    if (state.drawnWaypoints.length >= 2) {
      loadRoute(state.drawnWaypoints);
      document.getElementById('routePresetSelect').value = 'custom';
    }
  }

  function renderDrawnPolyline() {
    if (state.drawnPolyline) {
      state.map.removeLayer(state.drawnPolyline);
    }
    if (state.drawnWaypoints.length > 1) {
      const latlngs = state.drawnWaypoints.map((wp) => [wp.lat, wp.lng]);
      state.drawnPolyline = L.polyline(latlngs, {
        color: '#f59e0b',
        dashArray: '4, 4',
        weight: 3,
        opacity: 0.9,
      }).addTo(state.map);
    }
  }

  function clearDrawnRoute() {
    state.drawnWaypoints = [];
    state.drawnMarkers.forEach((m) => state.map.removeLayer(m));
    state.drawnMarkers = [];
    if (state.drawnPolyline) {
      state.map.removeLayer(state.drawnPolyline);
      state.drawnPolyline = null;
    }
    showToast('Cleared manual route points.');
  }

  // Custom Boundary Polygon Tracing Tools
  function togglePolyDrawMode(enable) {
    state.isPolyDrawing = enable !== undefined ? enable : !state.isPolyDrawing;
    if (state.isPolyDrawing && state.isDrawingMode) {
      document.getElementById('btnToggleDrawMode').click();
    }
    const btn = document.getElementById('btnTogglePolygonDraw');
    const controls = document.getElementById('polyDrawControls');
    const text = document.getElementById('polyDrawText');
    if (state.isPolyDrawing) {
      btn.className = 'bg-cyan-900 border border-cyan-500 text-cyan-200 px-3 py-1.5 rounded text-2xs font-bold flex items-center gap-1.5 animate-pulse';
      controls.classList.remove('hidden');
      text.textContent = 'Tracing Boundary...';
      state.map.getContainer().style.cursor = 'crosshair';
      showToast('Click corners on map to trace polygon boundary.');
    } else {
      btn.className = 'bg-slate-800 hover:bg-cyan-950 hover:text-cyan-300 border border-slate-700 text-cyan-400 px-3 py-1.5 rounded text-2xs font-semibold flex items-center gap-1.5';
      controls.classList.add('hidden');
      text.textContent = 'Draw Custom Polygon';
      state.map.getContainer().style.cursor = '';
    }
  }

  function addPolyVertex(lat, lng) {
    state.polyPoints.push([lng, lat]); // GeoJSON order: [lng, lat]
    const count = state.polyPoints.length;
    document.getElementById('polyVertexCount').textContent = `${count} pts`;

    const marker = L.circleMarker([lat, lng], {
      radius: 6,
      fillColor: count === 1 ? '#10b981' : '#06b6d4',
      color: '#ffffff',
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(state.map);

    if (count === 1) {
      marker.bindTooltip('Click to close & finish polygon', { permanent: false });
      marker.on('click', () => {
        if (state.polyPoints.length >= 3) {
          completeCustomPolygon();
        }
      });
    }

    state.polyMarkers.push(marker);

    // Update polyline preview
    if (state.polyLinePreview) {
      state.map.removeLayer(state.polyLinePreview);
    }
    const latlngs = state.polyPoints.map((p) => [p[1], p[0]]);
    state.polyLinePreview = L.polyline(latlngs, {
      color: '#06b6d4',
      weight: 3,
      dashArray: '4, 4',
    }).addTo(state.map);
  }

  function completeCustomPolygon() {
    if (state.polyPoints.length < 3) {
      return alert('A polygon requires at least 3 points.');
    }

    // Ensure ring is closed
    const first = state.polyPoints[0];
    const last = state.polyPoints[state.polyPoints.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      state.polyPoints.push([first[0], first[1]]);
    }

    // Remove temp markers & line
    state.polyMarkers.forEach((m) => state.map.removeLayer(m));
    state.polyMarkers = [];
    if (state.polyLinePreview) {
      state.map.removeLayer(state.polyLinePreview);
      state.polyLinePreview = null;
    }

    if (state.customPolygonLayer) {
      state.map.removeLayer(state.customPolygonLayer);
    }

    const latlngs = state.polyPoints.map((p) => [p[1], p[0]]);
    state.customPolygonLayer = L.polygon(latlngs, {
      color: '#06b6d4',
      weight: 3,
      fillColor: '#0891b2',
      fillOpacity: 0.35,
    }).addTo(state.map);

    // Calculate approximate area
    let areaSqM = 0;
    for (let i = 0; i < state.polyPoints.length - 1; i++) {
      const p1 = state.polyPoints[i];
      const p2 = state.polyPoints[i + 1];
      const latMid = (((p1[1] + p2[1]) / 2) * Math.PI) / 180;
      const mPerDegLat = 111132.954 - 559.822 * Math.cos(2 * latMid) + 1.175 * Math.cos(4 * latMid);
      const mPerDegLon = 111412.84 * Math.cos(latMid) - 93.5 * Math.cos(3 * latMid);
      areaSqM += (p2[0] - p1[0]) * mPerDegLon * (((p2[1] + p1[1]) / 2) * mPerDegLat);
    }
    areaSqM = Math.abs(areaSqM);
    const ha = (areaSqM / 10000).toFixed(2);

    const geoJsonObject = {
      type: 'Polygon',
      coordinates: [state.polyPoints],
    };
    const geoJsonStr = JSON.stringify(geoJsonObject, null, 2);
    const wktStr = toWktPolygon(state.polyPoints);

    state.customPolygonLayer.bindPopup(`
      <div class="font-sans text-xs space-y-2 p-1">
        <div class="font-bold text-cyan-700 flex items-center gap-1">📐 Custom Drawn Polygon</div>
        <div class="text-slate-500 font-mono text-3xs">Area: ${Math.round(areaSqM).toLocaleString()} m² (${ha} ha)</div>
        <div class="flex items-center gap-1.5 pt-1">
          <button class="px-2 py-1 bg-indigo-600 text-white rounded text-3xs font-bold" onclick="window.__fwtCopy('${btoa(geoJsonStr)}', 'Custom Polygon', 'GeoJSON')">📋 Copy GeoJSON</button>
          <button class="px-2 py-1 bg-cyan-600 text-white rounded text-3xs font-bold" onclick="window.__fwtCopy('${btoa(wktStr)}', 'Custom Polygon', 'WKT')">📋 Copy WKT</button>
        </div>
      </div>
    `);

    // Populate and open custom polygon modal
    document.getElementById('customPolyVertCount').textContent = `${state.polyPoints.length - 1} corners`;
    document.getElementById('customPolyArea').textContent = `${Math.round(areaSqM).toLocaleString()} m² (${ha} ha)`;
    document.getElementById('customPolyGeoJson').textContent = geoJsonStr;
    document.getElementById('customPolyWkt').textContent = wktStr;

    // Attach copy button listeners for this modal
    document.getElementById('btnCopyCustomGeoJson').onclick = () => {
      copyToClipboard(geoJsonStr, 'Custom Polygon', 'GeoJSON');
    };
    document.getElementById('btnCopyCustomWkt').onclick = () => {
      copyToClipboard(wktStr, 'Custom Polygon', 'WKT');
    };

    document.getElementById('customPolygonModal').classList.remove('hidden');
    togglePolyDrawMode(false);
  }

  function cancelCustomPolygon() {
    state.polyMarkers.forEach((m) => state.map.removeLayer(m));
    state.polyMarkers = [];
    if (state.polyLinePreview) {
      state.map.removeLayer(state.polyLinePreview);
      state.polyLinePreview = null;
    }
    state.polyPoints = [];
    document.getElementById('polyVertexCount').textContent = '0 pts';
    togglePolyDrawMode(false);
    showToast('Cancelled polygon drawing.');
  }

  // Paste Polygon Tool
  function openPastePolygonModal() {
    document.getElementById('pastePolygonInput').value = '';
    document.getElementById('pastedPolyName').value = '';
    document.getElementById('pastePolyError').classList.add('hidden');
    document.getElementById('pastePolygonModal').classList.remove('hidden');
    document.getElementById('pastePolygonInput').focus();
  }

  function closePastePolygonModal() {
    document.getElementById('pastePolygonModal').classList.add('hidden');
  }

  function parsePolygonCoordinates(rawStr) {
    const s = (rawStr || '').trim();
    if (!s) throw new Error('Polygon input string is empty.');

    // 1. Try GeoJSON
    if (s.startsWith('{')) {
      try {
        const obj = JSON.parse(s);
        let coords = null;
        if (obj.type === 'Feature' && obj.geometry) {
          coords = obj.geometry.coordinates;
        } else if (obj.type === 'Polygon') {
          coords = obj.coordinates;
        } else if (obj.type === 'MultiPolygon') {
          coords = obj.coordinates?.[0];
        }
        if (coords && coords[0] && Array.isArray(coords[0])) {
          // Convert GeoJSON [lng, lat] to Leaflet [lat, lng]
          const ring = coords[0];
          return ring.map((pt) => [Number(pt[1]), Number(pt[0])]);
        }
      } catch (e) {
        throw new Error(`Invalid JSON syntax: ${e.message}`);
      }
    }

    // 2. Try WKT: POLYGON((lng lat, lng lat, ...))
    const match = s.match(/POLYGON\s*\(\(\s*(.*?)\s*\)\)/i);
    if (match && match[1]) {
      const pts = match[1].split(',');
      const ring = [];
      for (const p of pts) {
        const parts = p.trim().split(/\s+/);
        if (parts.length >= 2) {
          const lng = parseFloat(parts[0]);
          const lat = parseFloat(parts[1]);
          if (!isNaN(lat) && !isNaN(lng)) {
            ring.push([lat, lng]);
          }
        }
      }
      if (ring.length >= 3) {
        return ring;
      }
    }

    throw new Error('Could not parse as GeoJSON or WKT. Expected GeoJSON {"type":"Polygon",...} or WKT POLYGON((lng lat, ...))');
  }

  function applyPastedPolygon() {
    const raw = document.getElementById('pastePolygonInput').value;
    const errEl = document.getElementById('pastePolyError');
    errEl.classList.add('hidden');

    try {
      const latlngs = parsePolygonCoordinates(raw);
      if (latlngs.length < 3) {
        throw new Error('A polygon requires at least 3 coordinate points.');
      }

      // Ensure ring is closed
      const first = latlngs[0];
      const last = latlngs[latlngs.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) {
        latlngs.push([first[0], first[1]]);
      }

      const roleInput = document.querySelector('input[name="pastedPolyType"]:checked');
      const role = roleInput ? roleInput.value : 'WORKSITE';
      const customName = document.getElementById('pastedPolyName').value.trim() ||
        (role === 'WORKSITE' ? 'Pasted Worksite' : role === 'ACCOMMODATION' ? 'Pasted Camp' : 'Custom Pasted Boundary');

      let color = '#3b82f6';
      let icon = '🏢';
      if (role === 'ACCOMMODATION') {
        color = '#10b981';
        icon = '🏠';
      } else if (role === 'CUSTOM') {
        color = '#06b6d4';
        icon = '📐';
      }

      // Remove previous pasted polygon layer if present
      if (state.pastedPolygonLayer) {
        state.map.removeLayer(state.pastedPolygonLayer);
        state.pastedPolygonLayer = null;
      }
      if (state.pastedPolygonMarker) {
        state.map.removeLayer(state.pastedPolygonMarker);
        state.pastedPolygonMarker = null;
      }

      state.pastedPolygonLayer = L.polygon(latlngs, {
        color: color,
        weight: 3,
        fillColor: color,
        fillOpacity: 0.25,
      }).addTo(state.map);

      // Add centroid pin
      const bounds = state.pastedPolygonLayer.getBounds();
      const centroid = bounds.getCenter();

      state.pastedPolygonMarker = L.circleMarker(centroid, {
        radius: 6,
        color: '#ffffff',
        fillColor: color,
        fillOpacity: 1,
        weight: 2,
      }).addTo(state.map);

      state.pastedPolygonMarker.bindTooltip(`${icon} ${customName}`, { permanent: true, direction: 'top', className: 'text-3xs font-bold' });

      // GeoJSON & WKT strings for popup copy
      const geoJsonPoints = latlngs.map((pt) => [pt[1], pt[0]]);
      const geoJsonStr = JSON.stringify({ type: 'Polygon', coordinates: [geoJsonPoints] }, null, 2);
      const wktStr = toWktPolygon(geoJsonPoints);

      state.pastedPolygonLayer.bindPopup(`
        <div class="font-sans text-xs space-y-2 p-1">
          <div class="font-bold flex items-center gap-1" style="color: ${color};">${icon} ${customName}</div>
          <div class="text-slate-500 font-mono text-3xs">Center: ${centroid.lat.toFixed(5)}, ${centroid.lng.toFixed(5)}</div>
          <div class="flex items-center gap-1.5 pt-1">
            <button class="px-2 py-1 bg-indigo-600 text-white rounded text-3xs font-bold" onclick="window.__fwtCopy('${btoa(geoJsonStr)}', '${customName}', 'GeoJSON')">📋 Copy GeoJSON</button>
            <button class="px-2 py-1 bg-cyan-600 text-white rounded text-3xs font-bold" onclick="window.__fwtCopy('${btoa(wktStr)}', '${customName}', 'WKT')">📋 Copy WKT</button>
          </div>
        </div>
      `);

      // Zoom to polygon
      state.map.fitBounds(bounds, { padding: [40, 40] });

      closePastePolygonModal();
      showToast(`Pasted polygon applied: ${customName}`);
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    }
  }

  // Clear Map Canvas & Reset Custom Layers
  function clearEntireMap() {
    stopRoutePlayback();

    // 1. Remove custom drawn polygon & tracing markers
    if (state.customPolygonLayer) {
      state.map.removeLayer(state.customPolygonLayer);
      state.customPolygonLayer = null;
    }
    if (state.pastedPolygonLayer) {
      state.map.removeLayer(state.pastedPolygonLayer);
      state.pastedPolygonLayer = null;
    }
    if (state.pastedPolygonMarker) {
      state.map.removeLayer(state.pastedPolygonMarker);
      state.pastedPolygonMarker = null;
    }
    state.polyMarkers.forEach((m) => state.map.removeLayer(m));
    state.polyMarkers = [];
    if (state.polyLinePreview) {
      state.map.removeLayer(state.polyLinePreview);
      state.polyLinePreview = null;
    }
    state.polyPoints = [];
    document.getElementById('polyVertexCount').textContent = '0 pts';
    togglePolyDrawMode(false);

    // 2. Clear drawn route waypoints & polyline
    state.drawnWaypoints = [];
    state.drawnMarkers.forEach((m) => state.map.removeLayer(m));
    state.drawnMarkers = [];
    if (state.drawnPolyline) {
      state.map.removeLayer(state.drawnPolyline);
      state.drawnPolyline = null;
    }
    if (state.isDrawingMode) {
      document.getElementById('btnToggleDrawMode').click();
    }

    // 3. Hide all modals
    document.getElementById('customPolygonModal').classList.add('hidden');
    document.getElementById('boundaryModal').classList.add('hidden');

    // 4. Reset timeline slider & analytics
    state.route.progress = 0;
    const slider = document.getElementById('routeTimelineSlider');
    if (slider) slider.value = '0';
    applyRouteProgress(0);

    // 5. Reset route to standard preset
    document.getElementById('routePresetSelect').value = 'standard';
    loadRoute(PRESET_ROUTES.standard.waypoints);

    // 6. Refresh server layers
    updateMapLayers();

    showToast('✓ Map canvas cleared & reset.');
  }

  // Render Map Features ONLY from Synced Server Data (NO Hardcoded Fallback)
  function updateMapLayers() {
    state.layers.worksites.forEach((l) => state.map.removeLayer(l));
    state.layers.geofences.forEach((l) => state.map.removeLayer(l));
    if (state.layers.accommodation) state.map.removeLayer(state.layers.accommodation);
    state.layers.worksites = [];
    state.layers.geofences = [];

    const alertEl = document.getElementById('mapBoundaryAlert');
    const alertText = document.getElementById('mapBoundaryAlertText');
    const legendCamp = document.getElementById('legendCamp');
    const legendWorksite = document.getElementById('legendWorksite');

    let hasAnyWorksiteBoundary = false;
    let hasCampBoundary = false;

    // 1. Accommodation Polygon from Server Snapshot
    if (state.synced.accommodation?.boundary?.coordinates?.[0]) {
      hasCampBoundary = true;
      const coords = state.synced.accommodation.boundary.coordinates[0];
      const latlngs = coords.map((pt) => [pt[1], pt[0]]);
      const campName = state.synced.accommodation.name || 'Living Camp';

      const poly = L.polygon(latlngs, {
        color: '#059669',
        fillColor: '#10b981',
        fillOpacity: 0.25,
        weight: 2,
      }).addTo(state.map);

      // Click to Copy Popup
      const geojsonStr = JSON.stringify(state.synced.accommodation.boundary, null, 2);
      const wktStr = toWktPolygon(coords);
      poly.bindPopup(`
        <div class="p-2 space-y-2 text-xs font-sans">
          <div class="font-bold text-emerald-800 text-sm">🏠 ${campName}</div>
          <div class="text-3xs text-slate-500">${state.synced.accommodation.address || 'Living Quarters'}</div>
          <div class="pt-1 flex gap-1.5">
            <button onclick="window.__fwtCopy('${btoa(geojsonStr)}', '${campName}', 'GeoJSON')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2 py-1 rounded text-3xs">
              📋 Copy GeoJSON
            </button>
            <button onclick="window.__fwtCopy('${btoa(wktStr)}', '${campName}', 'WKT')" class="bg-slate-800 hover:bg-slate-900 text-white font-bold px-2 py-1 rounded text-3xs">
              📋 Copy WKT
            </button>
          </div>
        </div>
      `);
      poly.bindTooltip(`🏠 ${campName} (Click to copy)`, { permanent: false, direction: 'center' });
      state.layers.accommodation = poly;
      legendCamp.innerText = `${campName} (Click to copy)`;
    } else {
      legendCamp.innerText = 'No Camp Boundary on Server';
    }

    // 2. Worksite Polygons and Geofences from Server Snapshot
    state.synced.jobs.forEach((job) => {
      if (job.boundary?.coordinates?.[0]) {
        hasAnyWorksiteBoundary = true;
        const coords = job.boundary.coordinates[0];
        const latlngs = coords.map((pt) => [pt[1], pt[0]]);
        const jobName = job.job_name || 'Assigned Worksite';

        const poly = L.polygon(latlngs, {
          color: '#2563eb',
          fillColor: '#3b82f6',
          fillOpacity: 0.3,
          weight: 2,
        }).addTo(state.map);

        const geojsonStr = JSON.stringify(job.boundary, null, 2);
        const wktStr = toWktPolygon(coords);
        poly.bindPopup(`
          <div class="p-2 space-y-2 text-xs font-sans">
            <div class="font-bold text-blue-800 text-sm">📍 ${jobName}</div>
            <div class="text-3xs text-slate-500">${job.job_number || ''} • Contract Worksite</div>
            <div class="pt-1 flex gap-1.5">
              <button onclick="window.__fwtCopy('${btoa(geojsonStr)}', '${jobName}', 'GeoJSON')" class="bg-blue-600 hover:bg-blue-700 text-white font-bold px-2 py-1 rounded text-3xs">
                📋 Copy GeoJSON
              </button>
              <button onclick="window.__fwtCopy('${btoa(wktStr)}', '${jobName}', 'WKT')" class="bg-slate-800 hover:bg-slate-900 text-white font-bold px-2 py-1 rounded text-3xs">
                📋 Copy WKT
              </button>
            </div>
          </div>
        `);
        poly.bindTooltip(`📍 ${jobName} (Click to copy)`, { permanent: false, direction: 'center' });
        state.layers.worksites.push(poly);
        legendWorksite.innerText = `${jobName} (Click to copy)`;
      }

      if (job.geofence_circle?.center) {
        const circle = L.circle([job.geofence_circle.center.lat, job.geofence_circle.center.lng], {
          radius: job.geofence_circle.radius_m || 300,
          color: '#6366f1',
          fillColor: '#818cf8',
          fillOpacity: 0.08,
          weight: 1.5,
          dashArray: '4, 4',
        }).addTo(state.map);
        state.layers.geofences.push(circle);
      }
    });

    // Check boundary warning banner
    if (state.token) {
      if (!hasAnyWorksiteBoundary && !hasCampBoundary) {
        alertEl.classList.remove('hidden');
        alertText.innerText = 'No assigned worksite or camp boundaries configured on server for this worker.';
      } else if (!hasAnyWorksiteBoundary) {
        alertEl.classList.remove('hidden');
        if (state.synced.jobs.length === 0) {
          alertText.innerText = 'Worker has no active shift scheduled today (Day Plan: FREE). Living camp loaded.';
        } else {
          alertText.innerText = 'Assigned worksite has no polygon boundary set on server.';
        }
      } else {
        alertEl.classList.add('hidden');
      }
    } else {
      alertEl.classList.remove('hidden');
      alertText.innerText = 'Sign in with a worker account to sync server boundaries and shifts.';
    }

    // Auto-fit viewport to show accommodation and worksites
    const allLayers = [...state.layers.worksites];
    if (state.layers.accommodation) allLayers.push(state.layers.accommodation);
    if (allLayers.length > 0 && state.map) {
      const group = L.featureGroup(allLayers);
      const bounds = group.getBounds();
      if (bounds.isValid()) {
        state.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
      }
    }

    // Dynamic Auto-Route between Camp and Worksite
    if (state.synced.accommodation?.boundary?.coordinates && state.synced.jobs[0]?.boundary?.coordinates) {
      const campPt = getPolygonCentroid(state.synced.accommodation.boundary.coordinates);
      const sitePt = getPolygonCentroid(state.synced.jobs[0].boundary.coordinates);
      if (campPt && sitePt) {
        const campName = state.synced.accommodation.name || 'Living Camp';
        const jobName = state.synced.jobs[0].job_name || 'Assigned Worksite';
        const midPt = { lat: (campPt.lat + sitePt.lat) / 2, lng: (campPt.lng + sitePt.lng) / 2 };

        PRESET_ROUTES.auto_synced = {
          name: `Auto: ${campName} ➔ ${jobName}`,
          waypoints: [
            { time: '05:00:00', lat: campPt.lat, lng: campPt.lng, label: `${campName} (At Camp)` },
            { time: '05:35:00', lat: campPt.lat * 0.9 + midPt.lat * 0.1, lng: campPt.lng * 0.9 + midPt.lng * 0.1, label: 'Departing Camp' },
            { time: '05:48:00', lat: midPt.lat, lng: midPt.lng, label: 'Transit Commute' },
            { time: '05:58:00', lat: sitePt.lat * 0.9 + midPt.lat * 0.1, lng: sitePt.lng * 0.9 + midPt.lng * 0.1, label: 'Geofence Buffer Approach' },
            { time: '06:02:00', lat: sitePt.lat, lng: sitePt.lng, label: `${jobName} Entry` },
            { time: '09:00:00', lat: sitePt.lat, lng: sitePt.lng, label: 'Mid-Morning Work' },
            { time: '12:00:00', lat: sitePt.lat, lng: sitePt.lng, label: 'Midday Rest on Site' },
            { time: '14:00:00', lat: sitePt.lat, lng: sitePt.lng, label: 'Afternoon Work' },
            { time: '15:31:00', lat: sitePt.lat * 0.9 + midPt.lat * 0.1, lng: sitePt.lng * 0.9 + midPt.lng * 0.1, label: 'Worksite Exit' },
            { time: '15:45:00', lat: midPt.lat, lng: midPt.lng, label: 'Return Transit' },
            { time: '16:00:00', lat: campPt.lat, lng: campPt.lng, label: `Back at ${campName}` },
          ],
        };

        const optAuto = document.getElementById('optAutoSynced');
        if (optAuto) {
          optAuto.classList.remove('hidden');
          optAuto.innerText = `Auto: ${campName} ➔ ${jobName}`;
        }
      }
    }

    renderRoutePolyline();
  }

  // Expose global copy bridge for Leaflet popup buttons
  window.__fwtCopy = function (b64, name, format) {
    try {
      const text = atob(b64);
      copyToClipboard(text, name, format);
    } catch (e) {
      console.error(e);
    }
  };

  // Draw Route Polyline
  function renderRoutePolyline() {
    if (state.routePolyline) {
      state.map.removeLayer(state.routePolyline);
    }
    if (state.route.waypoints.length > 1) {
      const latlngs = state.route.waypoints.map((wp) => [wp.lat, wp.lng]);
      state.routePolyline = L.polyline(latlngs, {
        color: '#f59e0b',
        dashArray: '6, 6',
        weight: 3,
        opacity: 0.8,
      }).addTo(state.map);
    }
  }

  // Update Worker Position & Zone Containment
  function updateWorkerPosition(lat, lng, simulatedTime = null) {
    state.workerLocation = { lat, lng };
    document.getElementById('phoneLat').innerText = lat.toFixed(6);
    document.getElementById('phoneLng').innerText = lng.toFixed(6);

    let detectedZone = 'TRANSIT';
    let zoneTitle = 'TRANSIT (HIGHWAY)';
    let badgeClass = 'bg-amber-100 text-amber-800 border-amber-300';
    let activeWorksiteId = null;

    // Check Accommodation (Camp)
    const campCoords = state.synced.accommodation?.boundary?.coordinates?.[0] || null;
    if (campCoords && isPointInPolygon({ lat, lng }, campCoords)) {
      detectedZone = 'CAMP';
      zoneTitle = 'CAMP (WARSAN)';
      badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    }

    // Check Worksites & Geofence (REAL Server boundaries only)
    state.synced.jobs.forEach((job) => {
      if (job.boundary?.coordinates?.[0]) {
        if (isPointInPolygon({ lat, lng }, job.boundary.coordinates[0])) {
          detectedZone = 'WORKSITE_POLYGON';
          zoneTitle = 'INSIDE WORKSITE';
          badgeClass = 'bg-blue-100 text-blue-800 border-blue-300';
          activeWorksiteId = job.job_id;
        } else if (job.geofence_circle?.center) {
          const dist = haversineMeters(lat, lng, job.geofence_circle.center.lat, job.geofence_circle.center.lng);
          if (dist <= job.geofence_circle.radius_m && detectedZone !== 'WORKSITE_POLYGON') {
            detectedZone = 'GEOFENCE_BUFFER';
            zoneTitle = 'PERIMETER (GEOFENCE)';
            badgeClass = 'bg-purple-100 text-purple-800 border-purple-300';
            activeWorksiteId = job.job_id;
          }
        }
      }
    });

    const badge = document.getElementById('phoneZoneBadge');
    badge.innerText = zoneTitle;
    badge.className = `text-2xs font-bold px-2 py-0.5 rounded-full border ${badgeClass}`;

    // Distance to Camp
    if (state.synced.accommodation?.rep_latitude) {
      const campLat = Number(state.synced.accommodation.rep_latitude);
      const campLng = Number(state.synced.accommodation.rep_longitude);
      const distM = Math.round(haversineMeters(lat, lng, campLat, campLng));
      document.getElementById('campDistance').innerText = distM < 1000 ? `${distM} m away` : `${(distM / 1000).toFixed(1)} km away`;
    } else {
      document.getElementById('campDistance').innerText = '--';
    }

    // Automatic Transition & Periodic Ping Generator (Simulating Real Mobile App)
    const currentSimSecs = simulatedTime ? timeStrToSeconds(simulatedTime.split('T')[1].slice(0, 8)) : 0;
    const confInterval = state.synced.settings?.confirmation_polling_interval_s || 300;

    if (detectedZone !== state.currentZone) {
      if (detectedZone === 'WORKSITE_POLYGON') {
        queueEvent('ENTRY', activeWorksiteId, simulatedTime);
        state.route.lastPingSimSecs = currentSimSecs;
      } else if (state.currentZone === 'WORKSITE_POLYGON' && detectedZone !== 'WORKSITE_POLYGON') {
        queueEvent('EXIT', state.currentWorksiteId, simulatedTime);
      }
    } else if (detectedZone === 'WORKSITE_POLYGON') {
      // Periodic ping inside worksite
      if (currentSimSecs > 0 && currentSimSecs - state.route.lastPingSimSecs >= confInterval) {
        queueEvent('PING', activeWorksiteId, simulatedTime);
        state.route.lastPingSimSecs = currentSimSecs;
      }
    }

    state.currentZone = detectedZone;
    state.currentWorksiteId = activeWorksiteId;
  }

  // Get active timestamp for simulation conforming to selected simulatedDate (or real now)
  function getSimulatedTimestamp(timeOverride = null) {
    const baseDate = state.simulatedDate || new Date().toISOString().split('T')[0];
    if (timeOverride) {
      if (timeOverride.includes('T')) {
        const timePart = timeOverride.split('T')[1];
        return `${baseDate}T${timePart}`;
      }
      return `${baseDate}T${timeOverride}Z`;
    }
    const nowIso = new Date().toISOString();
    const today = nowIso.split('T')[0];
    if (baseDate === today) {
      return nowIso;
    }
    const timePart = state.route.currentTimeStr || nowIso.split('T')[1].slice(0, 8);
    return `${baseDate}T${timePart}Z`;
  }

  // Queue Event (Conforming strictly to EventBatchRequest & MobileEventItem schemas)
  function queueEvent(type, worksiteId = null, recordedAt = null) {
    const timestamp = getSimulatedTimestamp(recordedAt);
    const evt = {
      event_id: crypto.randomUUID(),
      event_type: type,
      event_timestamp_utc: timestamp,
      latitude: Number(state.workerLocation.lat.toFixed(6)),
      longitude: Number(state.workerLocation.lng.toFixed(6)),
      accuracy_meters: 4.5,
      is_mock_location: false,
      job_id: worksiteId || state.currentWorksiteId || (state.synced.jobs[0]?.job_id || null),
      accommodation_id: state.synced.accommodation?.accommodation_id || null,
    };

    state.eventsQueue.push(evt);
    renderQueue();
  }

  function renderQueue() {
    const el = document.getElementById('phoneQueueList');
    const badge = document.getElementById('phoneQueueCount');
    badge.innerText = `${state.eventsQueue.length} events`;

    if (state.eventsQueue.length === 0) {
      el.innerHTML = '<div class="text-slate-400 text-center py-2">Buffer is empty</div>';
      return;
    }

    el.innerHTML = state.eventsQueue
      .map(
        (e) => `
        <div class="p-1.5 bg-white rounded border border-slate-200 flex justify-between items-center text-3xs">
          <span class="font-bold ${
            e.event_type === 'ENTRY' ? 'text-emerald-700' : e.event_type === 'EXIT' ? 'text-rose-700' : 'text-indigo-700'
          }">${e.event_type}</span>
          <span class="text-slate-500 font-mono">${e.event_timestamp_utc.split('T')[0].slice(5)} ${e.event_timestamp_utc.split('T')[1].slice(0, 8)}</span>
        </div>
      `
      )
      .join('');
  }

  // Audio Alarm Synth Chime
  function playAlarmChime() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.6);
    } catch {}
  }

  // Route Player Animation Loop
  function startRoutePlayback() {
    if (state.route.isPlaying) return;
    state.route.isPlaying = true;
    document.getElementById('playIcon').innerText = '⏸';
    document.getElementById('playText').innerText = 'Pause';
    state.route.lastTimestamp = performance.now();

    function step(now) {
      if (!state.route.isPlaying) return;
      const deltaSec = (now - state.route.lastTimestamp) / 1000;
      state.route.lastTimestamp = now;

      const totalRouteSecs =
        timeStrToSeconds(state.route.waypoints[state.route.waypoints.length - 1].time) -
        timeStrToSeconds(state.route.waypoints[0].time);

      if (totalRouteSecs > 0) {
        state.route.progress += (deltaSec * state.route.speed) / totalRouteSecs;
        if (state.route.progress >= 1.0) {
          state.route.progress = 1.0;
          stopRoutePlayback();
        }
        applyRouteProgress(state.route.progress);
      }

      if (state.route.isPlaying) {
        state.route.animId = requestAnimationFrame(step);
      }
    }

    state.route.animId = requestAnimationFrame(step);
  }

  function stopRoutePlayback() {
    state.route.isPlaying = false;
    document.getElementById('playIcon').innerText = '▶';
    document.getElementById('playText').innerText = 'Play Route';
    if (state.route.animId) cancelAnimationFrame(state.route.animId);
  }

  function applyRouteProgress(progress) {
    const wps = state.route.waypoints;
    if (wps.length < 2) return;

    const startSecs = timeStrToSeconds(wps[0].time);
    const endSecs = timeStrToSeconds(wps[wps.length - 1].time);
    const currentSecs = startSecs + progress * (endSecs - startSecs);

    document.getElementById('routeTimelineSlider').value = Math.round(progress * 1000);
    const timeStr = secondsToTimeStr(currentSecs);
    state.route.currentTimeStr = timeStr;
    document.getElementById('routeCurrentTime').innerText = timeStr;
    document.getElementById('phoneClock').innerText = formatTimeAmPm(currentSecs);

    let segIdx = 0;
    for (let i = 0; i < wps.length - 1; i++) {
      if (currentSecs >= timeStrToSeconds(wps[i].time)) {
        segIdx = i;
      }
    }

    const p1 = wps[segIdx];
    const p2 = wps[segIdx + 1] || p1;
    const t1 = timeStrToSeconds(p1.time);
    const t2 = timeStrToSeconds(p2.time);
    const segT = t2 > t1 ? (currentSecs - t1) / (t2 - t1) : 0;

    const currentLat = p1.lat + (p2.lat - p1.lat) * segT;
    const currentLng = p1.lng + (p2.lng - p1.lng) * segT;

    state.workerMarker.setLatLng([currentLat, currentLng]);
    const baseDate = state.simulatedDate || new Date().toISOString().split('T')[0];
    const simulatedIso = `${baseDate}T${timeStr}Z`;
    updateWorkerPosition(currentLat, currentLng, simulatedIso);
  }

  function loadRoute(waypoints) {
    state.route.waypoints = waypoints;
    state.route.progress = 0;
    state.route.lastPingSimSecs = 0;
    document.getElementById('routeStartTime').innerText = waypoints[0]?.time || '05:00:00';
    document.getElementById('routeEndTime').innerText = waypoints[waypoints.length - 1]?.time || '16:00:00';
    renderRoutePolyline();
    calculateGroundTruthMetrics(waypoints);
    applyRouteProgress(0);
  }

  // Switch Mobile Phone Screen Tabs (Only active when authenticated)
  function switchTab(tabId) {
    state.activeTab = tabId;
    ['Today', 'Gps', 'Roster', 'Profile', 'Sync'].forEach((t) => {
      const content = document.getElementById(`tabContent${t}`);
      const btn = document.getElementById(`navBtn${t}`);
      if (t.toLowerCase() === tabId.toLowerCase()) {
        content.classList.remove('hidden');
        btn.className = 'flex flex-col items-center text-indigo-600 font-bold text-3xs space-y-0.5';
      } else {
        content.classList.add('hidden');
        btn.className = 'flex flex-col items-center text-slate-400 hover:text-slate-700 font-medium text-3xs space-y-0.5';
      }
    });
  }

  // Update authenticated UI state
  function setAuthenticatedState(isAuthed, employee = null) {
    const loginView = document.getElementById('phoneLoginView');
    const authContainer = document.getElementById('phoneAuthContainer');
    const bottomNav = document.getElementById('phoneBottomNav');
    const userTag = document.getElementById('phoneUserTag');
    const connBadge = document.getElementById('connBadge');

    if (isAuthed) {
      loginView.classList.add('hidden');
      authContainer.classList.remove('hidden');
      bottomNav.classList.remove('hidden');
      userTag.innerText = employee?.name || 'Online';
      connBadge.className = 'flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-emerald-950 border border-emerald-800 text-emerald-400';
      connBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span><span>Connected</span>';
      switchTab('today');
    } else {
      loginView.classList.remove('hidden');
      authContainer.classList.add('hidden');
      bottomNav.classList.add('hidden');
      userTag.innerText = 'Offline';
      connBadge.className = 'flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-red-950 border border-red-800 text-red-400';
      connBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span><span>Unauthenticated</span>';
    }
    updateMapLayers();
  }

  // Render Full Synced State into UI
  function applySyncedSnapshot(snapshot) {
    state.cursor = snapshot.cursor || 0;
    document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;

    state.synced.jobs = [];
    state.synced.dayPlans = [];
    state.synced.scheduleItems = [];

    // Parse all entities
    snapshot.entities.forEach((item) => {
      const data = item.payload || item.data;
      if (!data) return;

      if (item.entity_type === 'PROFILE') state.synced.profile = data;
      if (item.entity_type === 'SETTINGS') state.synced.settings = data;
      if (item.entity_type === 'ACCOMMODATION') state.synced.accommodation = data;
      if (item.entity_type === 'JOB') state.synced.jobs.push(data);
      if (item.entity_type === 'DAY_PLAN') state.synced.dayPlans.push(data);
      if (item.entity_type === 'SCHEDULE_ITEM') state.synced.scheduleItems.push(data);
    });

    // 1. Settings Card
    if (state.synced.settings) {
      document.getElementById('cfgRadius').innerText = `${state.synced.settings.geofence_circle_radius_m} m`;
      document.getElementById('cfgApproach').innerText = `${state.synced.settings.approach_polling_interval_s} s`;
      document.getElementById('cfgConfirm').innerText = `${state.synced.settings.confirmation_polling_interval_s} s`;
      document.getElementById('cfgAlarmLead').innerText = `${state.synced.settings.alarm_lead_minutes} min`;
      document.getElementById('alarmLeadTag').innerText = `${state.synced.settings.alarm_lead_minutes}m lead`;
    }

    // 2. Profile Screen
    if (state.synced.profile) {
      const p = state.synced.profile;
      document.getElementById('profName').innerText = p.name;
      document.getElementById('profGrade').innerText = p.staff_grade_description || 'Field Worker';
      document.getElementById('profTally').innerText = `Tally ID: ${p.tally_id}`;
      document.getElementById('profWeeklyOff').innerText = p.weekly_off_day || 'Friday';
      document.getElementById('profPhone').innerText = p.phone || '--';

      if (p.supervisor) {
        document.getElementById('spvName').innerText = p.supervisor.name;
        document.getElementById('spvPhone').innerText = p.supervisor.phone || '--';
        document.getElementById('spvCallLink').href = `tel:${p.supervisor.phone || ''}`;
        document.getElementById('profSpv').innerText = p.supervisor.name;
      } else {
        document.getElementById('spvName').innerText = 'None Assigned';
        document.getElementById('spvPhone').innerText = '--';
        document.getElementById('profSpv').innerText = 'None Assigned';
      }
    }

    // 3. Accommodation Card
    if (state.synced.accommodation) {
      document.getElementById('campName').innerText = state.synced.accommodation.name;
      document.getElementById('campAddress').innerText = state.synced.accommodation.address || 'Living Quarters';
      document.getElementById('profCamp').innerText = state.synced.accommodation.name;
    } else {
      document.getElementById('campName').innerText = 'No Camp Configured on Server';
      document.getElementById('campAddress').innerText = '--';
      document.getElementById('profCamp').innerText = 'None Assigned';
    }

    // 4. Assigned Worksite Card
    if (state.synced.jobs.length > 0) {
      const j = state.synced.jobs[0];
      document.getElementById('shiftJobName').innerText = j.job_name;
      document.getElementById('shiftJobNumber').innerText = `${j.job_number} • Contract Worksite`;
    } else {
      document.getElementById('shiftJobName').innerText = 'No Worksite Assigned';
      document.getElementById('shiftJobNumber').innerText = '--';
    }

    // 5. Today's Day Plan Resolution
    const activeDateStr = state.simulatedDate || new Date().toISOString().split('T')[0];
    const todayStr = new Date().toISOString().split('T')[0];
    const todayPlan = state.synced.dayPlans.find((dp) => dp.work_date === activeDateStr) || state.synced.dayPlans[0];

    const simBadge = document.getElementById('phoneSimDateBadge');
    if (simBadge) simBadge.innerText = activeDateStr;

    if (todayPlan) {
      const isWorking = todayPlan.status === 'WORKING';
      const badge = document.getElementById('shiftStatusBadge');
      badge.innerText = todayPlan.status === 'OFF' ? 'REST DAY' : todayPlan.status;
      badge.className = isWorking
        ? 'text-3xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300'
        : 'text-3xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300';

      if (todayPlan.planned) {
        document.getElementById('plannedCampStart').innerText = `${todayPlan.planned.accommodation_start} AM`;
        document.getElementById('shiftSiteHours').innerText = `${todayPlan.planned.first_site_start} - ${todayPlan.planned.last_site_end}`;
        document.getElementById('shiftBreak').innerText = `${todayPlan.planned.break_minutes} min midday`;
      } else {
        document.getElementById('plannedCampStart').innerText = '--:--';
        document.getElementById('shiftSiteHours').innerText = '--';
        document.getElementById('shiftBreak').innerText = '--';
      }
      if (todayPlan.alarm_time) {
        document.getElementById('alarmDisplayTime').innerText = `${todayPlan.alarm_time} AM`;
      } else {
        document.getElementById('alarmDisplayTime').innerText = '--:--';
      }
    }

    // 6. Roster Tab
    const workingDaysCount = state.synced.dayPlans.filter((dp) => dp.status === 'WORKING').length;
    document.getElementById('schedCount').innerText = `${workingDaysCount} working days`;

    const schedEl = document.getElementById('phoneScheduleList');
    schedEl.innerHTML = state.synced.dayPlans
      .map((p) => {
        const isSimDate = p.work_date === activeDateStr;
        const isRealToday = p.work_date === todayStr;
        const isWork = p.status === 'WORKING';
        const badgeColor = isWork ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200';
        const jobName = state.synced.jobs[0]?.job_name || 'Landscape Maintenance';

        return `
          <div class="p-2.5 bg-white rounded-xl border ${isSimDate ? 'border-indigo-500 ring-1 ring-indigo-500 shadow-xs' : 'border-slate-200'} text-3xs space-y-1 cursor-pointer hover:border-indigo-300 transition-colors" data-roster-date="${p.work_date}" title="Click to set simulation date">
            <div class="flex justify-between items-center font-bold">
              <span class="text-slate-900 font-mono flex items-center gap-1">
                ${p.work_date}
                ${isRealToday ? '<span class="bg-slate-700 text-white px-1.5 py-0.2 rounded text-3xs font-semibold">TODAY</span>' : ''}
                ${isSimDate ? '<span class="bg-indigo-600 text-white px-1.5 py-0.2 rounded text-3xs font-semibold">SIMULATING</span>' : ''}
              </span>
              <span class="px-2 py-0.5 rounded-full border text-3xs font-semibold ${badgeColor}">
                ${p.status === 'OFF' ? 'REST DAY' : p.status}
              </span>
            </div>
            ${
              isWork
                ? `
              <div class="text-slate-700 font-medium">${jobName}</div>
              <div class="flex justify-between text-slate-500 pt-0.5 border-t border-slate-100">
                <span>Shift: <strong class="text-slate-800">${p.planned?.first_site_start || '06:00'} - ${p.planned?.last_site_end || '15:30'}</strong></span>
                <span>Alarm: <strong class="text-slate-800">${p.alarm_time || '04:30'}</strong></span>
              </div>
            `
                : `
              <div class="text-slate-400 italic">Weekly Off / Scheduled Rest Day</div>
            `
            }
          </div>
        `;
      })
      .join('');

    // Attach click handlers to roster items to quickly switch simulated date
    const sevenDaysAgoStr = new Date(Date.now() - 7 * 86400 * 1000).toISOString().split('T')[0];
    schedEl.querySelectorAll('[data-roster-date]').forEach((card) => {
      card.addEventListener('click', () => {
        const targetDate = card.getAttribute('data-roster-date');
        if (!targetDate) return;
        if (targetDate > todayStr) {
          alert(`Cannot simulate future date (${targetDate}): Backend rejects events >5 minutes in the future with TIMESTAMP_IN_FUTURE.`);
          return;
        }
        if (targetDate < sevenDaysAgoStr) {
          alert(`Date ${targetDate} is older than 7 days: Backend rejects events with TIMESTAMP_TOO_OLD.`);
          return;
        }
        state.simulatedDate = targetDate;
        const picker = document.getElementById('simulatedDatePicker');
        if (picker) picker.value = targetDate;
        renderSyncedState();
        showToast(`📅 Simulated date switched to ${targetDate}`);
      });
    });

    // Update map features & refresh ground truth
    updateMapLayers();
    calculateGroundTruthMetrics(state.route.waypoints);
  }

  // Setup Event Listeners
  function setupEvents() {
    // Tab Navigation
    document.getElementById('navBtnToday').addEventListener('click', () => switchTab('today'));
    document.getElementById('navBtnGps').addEventListener('click', () => switchTab('gps'));
    document.getElementById('navBtnRoster').addEventListener('click', () => switchTab('roster'));
    document.getElementById('navBtnProfile').addEventListener('click', () => switchTab('profile'));
    document.getElementById('navBtnSync').addEventListener('click', () => switchTab('sync'));

    // Test Alarm Audio Chime
    document.getElementById('btnTestAlarm').addEventListener('click', () => {
      playAlarmChime();
      alert('⏰ BEEP BEEP! Shift Alarm ringing locally (lead time before camp departure).');
    });

    // Route Playback Controls
    document.getElementById('btnPlayRoute').addEventListener('click', () => {
      if (state.route.isPlaying) stopRoutePlayback();
      else startRoutePlayback();
    });

    document.getElementById('btnResetRoute').addEventListener('click', () => {
      stopRoutePlayback();
      state.route.progress = 0;
      applyRouteProgress(0);
    });

    // Speed Selector Buttons
    document.querySelectorAll('.speed-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.speed-btn').forEach((b) => {
          b.className = 'speed-btn px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono';
        });
        e.target.className = 'speed-btn px-2 py-1 rounded bg-indigo-600 text-white font-mono font-bold';
        state.route.speed = Number(e.target.dataset.speed);
      });
    });

    // Route Presets Selector
    document.getElementById('routePresetSelect').addEventListener('change', (e) => {
      stopRoutePlayback();
      const val = e.target.value;
      if (val === 'custom') {
        if (state.drawnWaypoints.length >= 2) loadRoute(state.drawnWaypoints);
        else alert('No custom route recorded yet. Click "Record / Draw Route" and click points on the map.');
      } else {
        const preset = PRESET_ROUTES[val];
        if (preset) loadRoute(preset.waypoints);
      }
    });

    // Simulated Work Date Picker (Enforcing 1-7 Day Backend Window)
    const datePicker = document.getElementById('simulatedDatePicker');
    const todayStr = new Date().toISOString().split('T')[0];
    const sevenDaysAgoStr = new Date(Date.now() - 7 * 86400 * 1000).toISOString().split('T')[0];

    if (datePicker) {
      datePicker.value = state.simulatedDate || todayStr;
      datePicker.max = todayStr;
      datePicker.min = sevenDaysAgoStr;

      datePicker.addEventListener('change', (e) => {
        const chosen = e.target.value;
        if (!chosen) return;
        if (chosen > todayStr) {
          alert('Cannot select future dates: The backend rejects events >5 minutes ahead of server clock with TIMESTAMP_IN_FUTURE.');
          e.target.value = state.simulatedDate;
          return;
        }
        if (chosen < sevenDaysAgoStr) {
          alert('Date exceeds 7-day ingestion limit: The backend rejects events older than 7 days with TIMESTAMP_TOO_OLD.');
          e.target.value = state.simulatedDate;
          return;
        }
        state.simulatedDate = chosen;
        const badge = document.getElementById('phoneSimDateBadge');
        if (badge) badge.innerText = state.simulatedDate;
        renderSyncedState();
        showToast(`📅 Simulated work date set to ${state.simulatedDate}. Any generated events will use this date.`);
      });
    }

    // Manual Route Drawing Toggle
    const btnDrawMode = document.getElementById('btnToggleDrawMode');
    const drawModeText = document.getElementById('drawModeText');
    const drawingBanner = document.getElementById('drawingBanner');
    const btnClearDrawn = document.getElementById('btnClearDrawnPoints');
    const drawStepContainer = document.getElementById('drawStepContainer');

    btnDrawMode.addEventListener('click', () => {
      state.isDrawingMode = !state.isDrawingMode;
      if (state.isDrawingMode) {
        if (state.isPolyDrawing) togglePolyDrawMode(false);
        btnDrawMode.className = 'bg-amber-600 text-white px-3 py-1.5 rounded text-2xs font-bold flex items-center gap-1.5 animate-pulse';
        drawModeText.innerText = 'Stop Drawing';
        drawingBanner.classList.remove('hidden');
        btnClearDrawn.classList.remove('hidden');
        if (drawStepContainer) drawStepContainer.classList.remove('hidden');
        showToast('Draw mode ON: Click anywhere on map to add route waypoints.');
      } else {
        btnDrawMode.className = 'bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 px-3 py-1.5 rounded text-2xs font-semibold flex items-center gap-1.5';
        drawModeText.innerText = 'Record / Draw Route';
        drawingBanner.classList.add('hidden');
        if (drawStepContainer) drawStepContainer.classList.add('hidden');
      }
    });

    btnClearDrawn.addEventListener('click', clearDrawnRoute);

    // Custom Polygon Tracing Controls
    document.getElementById('btnTogglePolygonDraw')?.addEventListener('click', () => togglePolyDrawMode());
    document.getElementById('btnCompletePolygon')?.addEventListener('click', completeCustomPolygon);
    document.getElementById('btnCancelPolygon')?.addEventListener('click', cancelCustomPolygon);
    document.getElementById('btnCloseCustomPolyModal')?.addEventListener('click', () => {
      document.getElementById('customPolygonModal').classList.add('hidden');
    });
    document.getElementById('btnDoneCustomPoly')?.addEventListener('click', () => {
      document.getElementById('customPolygonModal').classList.add('hidden');
    });
    document.getElementById('btnClearCustomPoly')?.addEventListener('click', () => {
      if (state.customPolygonLayer) {
        state.map.removeLayer(state.customPolygonLayer);
        state.customPolygonLayer = null;
      }
      state.polyPoints = [];
      document.getElementById('customPolygonModal').classList.add('hidden');
      showToast('Custom polygon removed from map.');
    });

    // Paste Polygon Boundary Controls
    document.getElementById('btnOpenPastePolyModal')?.addEventListener('click', openPastePolygonModal);
    document.getElementById('btnClosePastePolyModal')?.addEventListener('click', closePastePolygonModal);
    document.getElementById('btnCancelPastePoly')?.addEventListener('click', closePastePolygonModal);
    document.getElementById('btnApplyPastedPoly')?.addEventListener('click', applyPastedPolygon);

    // Quick Fill Account Buttons
    document.querySelectorAll('.btn-quick-fill').forEach((btn) => {
      btn.addEventListener('click', () => {
        const tally = btn.getAttribute('data-tally');
        document.getElementById('phoneInputTally').value = tally;
        document.getElementById('phoneInputPwd').value = 'Welcome123!';
        showToast(`Selected worker ${tally}.`);
      });
    });

    // Route Timeline Slider Scrubber
    document.getElementById('routeTimelineSlider').addEventListener('input', (e) => {
      stopRoutePlayback();
      state.route.progress = Number(e.target.value) / 1000;
      applyRouteProgress(state.route.progress);
    });

    // Route JSON Import
    document.getElementById('btnImportJson').addEventListener('click', () => {
      document.getElementById('routeJsonInput').click();
    });

    document.getElementById('routeJsonInput').addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        try {
          const json = JSON.parse(evt.target.result);
          const waypoints = json.waypoints || json;
          if (Array.isArray(waypoints) && waypoints.length >= 2) {
            loadRoute(waypoints);
            showToast(`Loaded route with ${waypoints.length} waypoints.`);
          } else {
            alert('Invalid route JSON: must contain an array of waypoints with {time, lat, lng}.');
          }
        } catch (err) {
          alert(`Failed to parse route JSON: ${err.message}`);
        }
      };
      reader.readAsText(file);
    });

    // Route JSON Export
    document.getElementById('btnExportJson').addEventListener('click', () => {
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify({ name: 'Exported Route', waypoints: state.route.waypoints }, null, 2));
      const a = document.createElement('a');
      a.setAttribute('href', dataStr);
      a.setAttribute('download', 'fwt_simulated_route.json');
      document.body.appendChild(a);
      a.click();
      a.remove();
    });

    // Clear Entire Map Canvas & Reset
    document.getElementById('btnClearMapAll')?.addEventListener('click', clearEntireMap);

    // Export Network Log (JSON)
    document.getElementById('btnExportNetworkLog').addEventListener('click', () => {
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(state.networkTraffic, null, 2));
      const a = document.createElement('a');
      a.setAttribute('href', dataStr);
      a.setAttribute('download', 'fwt_network_traffic.json');
      document.body.appendChild(a);
      a.click();
      a.remove();
    });

    // Boundary Modal & Copy Tools
    const boundaryModal = document.getElementById('boundaryModal');
    document.getElementById('btnOpenBoundaryModal').addEventListener('click', () => {
      renderBoundaryModalList();
      boundaryModal.classList.remove('hidden');
    });

    document.getElementById('btnCloseBoundaryModal').addEventListener('click', () => {
      boundaryModal.classList.add('hidden');
    });

    // Sign In Action (Handles First-Time Password Change Gracefully)
    document.getElementById('phoneBtnLogin').addEventListener('click', async () => {
      const tally_id = document.getElementById('phoneInputTally').value.trim();
      const password = document.getElementById('phoneInputPwd').value.trim();

      if (!tally_id || !password) {
        return alert('Please enter both Tally ID and password.');
      }

      try {
        let res;
        let activePwd = password;
        try {
          res = await api('/mobile/auth/login', {
            method: 'POST',
            body: JSON.stringify({
              tally_id,
              password: activePwd,
              device: {
                device_identifier: state.device.identifier,
                platform: state.device.platform,
                device_model: state.device.model,
                app_version: state.device.app_version,
                os_version: state.device.os_version,
              },
            }),
          });
        } catch (loginErr) {
          // If the worker was already enrolled on a previous run, fallback to permanent password
          if (password === 'Welcome123!') {
            try {
              res = await api('/mobile/auth/login', {
                method: 'POST',
                body: JSON.stringify({
                  tally_id,
                  password: 'WorkerPermanent123!',
                  device: {
                    device_identifier: state.device.identifier,
                    platform: state.device.platform,
                    device_model: state.device.model,
                    app_version: state.device.app_version,
                    os_version: state.device.os_version,
                  },
                }),
              });
              activePwd = 'WorkerPermanent123!';
              showToast('✓ Signed in with enrolled permanent password.');
            } catch {
              throw loginErr;
            }
          } else {
            throw loginErr;
          }
        }

        state.token = res.access_token;
        state.worker = res.employee;
        localStorage.setItem('fwt_mobile_token', state.token);

        // If user must change password on first login, automatically complete it to unblock sync
        if (res.must_change_password) {
          try {
            await api('/mobile/auth/change-password', {
              method: 'POST',
              body: JSON.stringify({
                old_password: activePwd,
                new_password: 'WorkerPermanent123!',
              }),
            });
            // Re-login to get clean non-pending token
            const relogin = await api('/mobile/auth/login', {
              method: 'POST',
              body: JSON.stringify({
                tally_id,
                password: 'WorkerPermanent123!',
                device: {
                  device_identifier: state.device.identifier,
                  platform: state.device.platform,
                  device_model: state.device.model,
                  app_version: state.device.app_version,
                  os_version: state.device.os_version,
                },
              }),
            });
            state.token = relogin.access_token;
            localStorage.setItem('fwt_mobile_token', state.token);
            showToast('✓ Permanent password enrolled for new worker.');
          } catch (pwdErr) {
            console.warn('Password change skipped or failed:', pwdErr);
          }
        }

        setAuthenticatedState(true, res.employee);

        // Immediately pull full snapshot from server
        await pullSnapshot();
      } catch (err) {
        alert(`Login failed: ${err.message}`);
      }
    });

    // Logout Action
    document.getElementById('phoneBtnLogout').addEventListener('click', async () => {
      try {
        await api('/mobile/auth/logout', { method: 'POST' });
      } catch {}
      state.token = null;
      state.worker = null;
      localStorage.removeItem('fwt_mobile_token');
      setAuthenticatedState(false);
    });

    // Pull Snapshot Function
    async function pullSnapshot() {
      if (!state.token) {
        showToast('Please sign in first.');
        return;
      }
      try {
        const res = await api('/mobile/sync/snapshot');
        applySyncedSnapshot(res);
      } catch (err) {
        alert(`Snapshot pull failed: ${err.message}`);
      }
    }

    document.getElementById('phoneBtnPullSnapshot').addEventListener('click', pullSnapshot);

    // Pull Delta Sync (Fixing next_cursor so cursor is never undefined)
    document.getElementById('phoneBtnPullDelta').addEventListener('click', async () => {
      if (!state.token) {
        showToast('Please sign in first.');
        return;
      }
      const cur = state.cursor || 0;
      try {
        const res = await api(`/mobile/sync/changes?cursor=${cur}`);
        if (res.resync_required) {
          showToast('Server signaled resync_required=true. Pulling fresh snapshot.');
          return pullSnapshot();
        }
        // Correctly update to next_cursor
        state.cursor = res.next_cursor !== undefined ? res.next_cursor : (res.cursor !== undefined ? res.cursor : cur);
        document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;

        // Apply changes to local state
        if (res.changes && res.changes.length > 0) {
          res.changes.forEach((c) => {
            if (c.entity_type === 'PROFILE' && c.payload) {
              state.synced.profile = c.payload;
            }
            if (c.entity_type === 'ACCOMMODATION' && c.payload) {
              state.synced.accommodation = c.payload;
            }
            if (c.entity_type === 'JOB' && c.payload) {
              const idx = state.synced.jobs.findIndex((j) => j.job_id === c.payload.job_id);
              if (idx >= 0) state.synced.jobs[idx] = c.payload;
              else state.synced.jobs.push(c.payload);
            }
            if (c.entity_type === 'DAY_PLAN' && c.payload) {
              const idx = state.synced.dayPlans.findIndex((dp) => dp.work_date === c.payload.work_date);
              if (idx >= 0) state.synced.dayPlans[idx] = c.payload;
              else state.synced.dayPlans.push(c.payload);
            }
          });
          // Re-render UI
          applySyncedSnapshot({
            cursor: state.cursor,
            entities: [
              ...(state.synced.profile ? [{ entity_type: 'PROFILE', payload: state.synced.profile }] : []),
              ...(state.synced.settings ? [{ entity_type: 'SETTINGS', payload: state.synced.settings }] : []),
              ...(state.synced.accommodation ? [{ entity_type: 'ACCOMMODATION', payload: state.synced.accommodation }] : []),
              ...state.synced.jobs.map((j) => ({ entity_type: 'JOB', payload: j })),
              ...state.synced.dayPlans.map((dp) => ({ entity_type: 'DAY_PLAN', payload: dp })),
            ],
          });
        }
        showToast(`Delta sync: ${res.changes.length} changes applied. Next cursor: ${state.cursor}`);
      } catch (err) {
        alert(`Delta sync failed: ${err.message}`);
      }
    });

    // Ack Cursor
    document.getElementById('phoneBtnAck').addEventListener('click', async () => {
      if (!state.token) {
        showToast('Please sign in first.');
        return;
      }
      try {
        await api('/mobile/sync/ack', {
          method: 'POST',
          body: JSON.stringify({ cursor: state.cursor || 0 }),
        });
        showToast(`Cursor ${state.cursor} acknowledged with server.`);
      } catch (err) {
        alert(`Ack failed: ${err.message}`);
      }
    });

    // Manual Event Buttons
    document.getElementById('phoneBtnEntry').addEventListener('click', () => queueEvent('ENTRY'));
    document.getElementById('phoneBtnPing').addEventListener('click', () => queueEvent('PING'));
    document.getElementById('phoneBtnExit').addEventListener('click', () => queueEvent('EXIT'));
    document.getElementById('phoneBtnLocOff').addEventListener('click', () => queueEvent('LOCATION_DISABLED'));
    document.getElementById('phoneBtnLocOn').addEventListener('click', () => queueEvent('LOCATION_ENABLED'));

    // Flush Batch (POST /api/v1/mobile/events/batch)
    document.getElementById('phoneBtnFlushBatch').addEventListener('click', async () => {
      if (!state.token) {
        alert('Please sign in first.');
        return;
      }
      if (state.eventsQueue.length === 0) return alert('Event buffer is empty.');
      const batchItems = [...state.eventsQueue];

      try {
        const res = await api('/mobile/events/batch', {
          method: 'POST',
          body: JSON.stringify({
            batch_id: crypto.randomUUID(),
            device_clock_utc: new Date().toISOString(),
            events: batchItems.map((e) => ({
              event_id: e.event_id,
              event_type: e.event_type,
              event_timestamp_utc: e.event_timestamp_utc,
              latitude: e.latitude,
              longitude: e.longitude,
              accuracy_meters: e.accuracy_meters,
              is_mock_location: false,
              job_id: e.job_id,
              accommodation_id: e.accommodation_id,
            })),
          }),
        });

        const accepted = res.results.filter((r) => r.status === 'ACCEPTED').length;
        const rejected = res.results.filter((r) => r.status === 'REJECTED').length;
        state.eventsQueue = [];
        renderQueue();
        let toastMsg = `Batch sent! Accepted: ${accepted}, Rejected: ${rejected}. Cursor: ${res.latest_cursor}`;
        if (rejected > 0) {
          const reasons = [...new Set(res.results.filter((r) => r.reason).map((r) => r.reason))].join(', ');
          toastMsg += ` (Reason: ${reasons})`;
        }
        showToast(toastMsg);
      } catch (err) {
        alert(`Batch failed: ${err.message}`);
      }
    });

    // Clear Network Log
    document.getElementById('btnClearNetworkLog').addEventListener('click', () => {
      document.getElementById('networkLogList').innerHTML = '';
      state.networkTraffic = [];
    });
  }

  // Render Boundary Copy Modal Items
  function renderBoundaryModalList() {
    const list = document.getElementById('boundaryModalList');
    if (!list) return;

    const items = [];
    if (state.synced.accommodation) {
      items.push({
        type: 'Accommodation Camp',
        name: state.synced.accommodation.name,
        code: state.synced.accommodation.accommodation_id,
        boundary: state.synced.accommodation.boundary,
      });
    }
    state.synced.jobs.forEach((job) => {
      items.push({
        type: 'Worksite',
        name: job.job_name,
        code: job.job_number,
        boundary: job.boundary,
      });
    });

    if (items.length === 0) {
      list.innerHTML = '<div class="text-slate-400 text-center py-6">No synced boundary data available. Please sign in to fetch boundaries.</div>';
      return;
    }

    list.innerHTML = items
      .map((item) => {
        const hasBoundary = Boolean(item.boundary?.coordinates?.[0]);
        const geojsonStr = hasBoundary ? JSON.stringify(item.boundary, null, 2) : '';
        const wktStr = hasBoundary ? toWktPolygon(item.boundary.coordinates[0]) : '';

        return `
          <div class="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
            <div class="flex justify-between items-start">
              <div>
                <span class="text-3xs uppercase font-bold text-indigo-400 block">${item.type}</span>
                <h4 class="font-bold text-xs text-white">${item.name}</h4>
                <div class="text-3xs text-slate-500 font-mono">${item.code || ''}</div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-3xs font-semibold ${
                hasBoundary ? 'bg-emerald-950 border border-emerald-800 text-emerald-400' : 'bg-amber-950 border border-amber-800 text-amber-400'
              }">${hasBoundary ? 'Boundary Set' : 'No Boundary'}</span>
            </div>
            ${
              hasBoundary
                ? `
              <div class="flex gap-2 pt-1">
                <button onclick="window.__fwtCopy('${btoa(geojsonStr)}', '${item.name}', 'GeoJSON')" class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-1.5 rounded text-2xs transition">
                  📋 Copy GeoJSON
                </button>
                <button onclick="window.__fwtCopy('${btoa(wktStr)}', '${item.name}', 'WKT')" class="flex-1 bg-slate-800 hover:bg-slate-700 text-white font-bold py-1.5 rounded text-2xs transition">
                  📋 Copy WKT
                </button>
              </div>
            `
                : `<div class="text-3xs text-slate-500 italic">No boundary polygon assigned on server.</div>`
            }
          </div>
        `;
      })
      .join('');
  }

  // Application Startup
  window.addEventListener('DOMContentLoaded', async () => {
    initMap();
    setupEvents();
    loadRoute(PRESET_ROUTES.standard.waypoints);

    // If existing token stored, verify and auto-restore
    if (state.token) {
      try {
        const snap = await api('/mobile/sync/snapshot');
        setAuthenticatedState(true);
        applySyncedSnapshot(snap);
      } catch {
        state.token = null;
        localStorage.removeItem('fwt_mobile_token');
        setAuthenticatedState(false);
      }
    } else {
      setAuthenticatedState(false);
    }
  });
})();