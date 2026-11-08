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
    activeTab: 'today', // 'today', 'gps', 'roster', 'profile', 'sync'
    currentZone: 'CAMP',
    currentWorksiteId: null,
    workerLocation: { lat: 25.15825, lng: 55.41225 }, // Warsan Camp default
    eventsQueue: [],
    networkTraffic: [],
    map: null,
    workerMarker: null,
    routePolyline: null,
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
    },
  };

  // Known fallback boundaries (Warsan Camp and Dubai Silicon Oasis, ~4.1 km commute)
  const DEFAULT_CAMP_POLYGON = [
    [55.4100, 25.1560],
    [55.4145, 25.1560],
    [55.4145, 25.1605],
    [55.4100, 25.1605],
    [55.4100, 25.1560],
  ];

  const DEFAULT_WORKSITE_POLYGON = [
    [55.3800, 25.1280],
    [55.3880, 25.1280],
    [55.3880, 25.1340],
    [55.3800, 25.1340],
    [55.3800, 25.1280],
  ];

  // Preset Route Definitions
  const PRESET_ROUTES = {
    standard: {
      name: 'Standard Clean Workday (06:02 - 15:31)',
      waypoints: [
        { time: '05:00:00', lat: 25.15825, lng: 55.41225, label: 'Warsan Staff Camp' },
        { time: '05:35:00', lat: 25.15300, lng: 55.40700, label: 'Leaving Camp Perimeter' },
        { time: '05:48:00', lat: 25.14200, lng: 55.39500, label: 'Transit (Manama St)' },
        { time: '05:58:00', lat: 25.13350, lng: 55.38850, label: 'Approaching Geofence Buffer (300m)' },
        { time: '06:02:00', lat: 25.13100, lng: 55.38400, label: 'Worksite Entry (Silicon Oasis)' },
        { time: '06:07:00', lat: 25.13120, lng: 55.38420, label: 'In-Site Confirmation Ping' },
        { time: '09:00:00', lat: 25.13150, lng: 55.38450, label: 'Mid-Morning Landscape Work' },
        { time: '12:00:00', lat: 25.13050, lng: 55.38350, label: 'Midday Rest on Site' },
        { time: '14:00:00', lat: 25.13110, lng: 55.38380, label: 'Afternoon Landscape Work' },
        { time: '15:31:00', lat: 25.12650, lng: 55.37800, label: 'Worksite Exit' },
        { time: '15:45:00', lat: 25.14500, lng: 55.39800, label: 'Return Commute Transit' },
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

  // Network Inspector Logger
  function logNetwork(method, path, status, latencyMs, reqBody, resBody) {
    const el = document.getElementById('networkLogList');
    const line = document.createElement('div');
    const time = new Date().toISOString().split('T')[1].slice(0, 8);
    const isSuccess = status >= 200 && status < 300;
    const badgeColor = isSuccess
      ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
      : 'bg-rose-950 text-rose-400 border-rose-800';

    // Store in memory for JSON export
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

  // API Client with Timing & Error Handling
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

  // Point in Polygon Math
  function isPointInPolygon(point, polygonCoordinates) {
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

  // Seconds parsing helper
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

  // Ground Truth Analytics Calculation
  function calculateGroundTruthMetrics(waypoints) {
    if (!waypoints || waypoints.length < 2) return;

    let workedSecs = 0;
    let transitSecs = 0;
    let campSecs = 0;
    let pings = 0;

    // Use active synced polygon or fallback polygon
    const campPoly = state.synced.accommodation?.boundary?.coordinates?.[0] || DEFAULT_CAMP_POLYGON;
    const worksitePolys = state.synced.jobs.length > 0 && state.synced.jobs[0].boundary?.coordinates?.[0]
      ? [state.synced.jobs[0].boundary.coordinates[0]]
      : [DEFAULT_WORKSITE_POLYGON];

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
        pings += Math.max(1, Math.floor(duration / 300));
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

    document.getElementById('gtWorkedTime').innerText = `${workedH}h ${String(workedM).padStart(2, '0')}m (${workedMin}m)`;
    document.getElementById('gtTransitTime').innerText = `${transitH}h ${String(transitM).padStart(2, '0')}m (${transitMin}m)`;
    document.getElementById('gtEventsCount').innerText = `1 ENTRY • 4 PING • 1 EXIT`;
  }

  // Initialize Map Viewport
  function initMap() {
    state.map = L.map('map', { zoomControl: false }).setView([25.145, 55.398], 13);
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

    state.map.on('click', function (e) {
      state.workerMarker.setLatLng(e.latlng);
      updateWorkerPosition(e.latlng.lat, e.latlng.lng);
    });

    // Render initial fallback layers
    updateMapLayers();
  }

  // Render Map Features from Synced or Default Data
  function updateMapLayers() {
    state.layers.worksites.forEach((l) => state.map.removeLayer(l));
    state.layers.geofences.forEach((l) => state.map.removeLayer(l));
    if (state.layers.accommodation) state.map.removeLayer(state.layers.accommodation);
    state.layers.worksites = [];
    state.layers.geofences = [];

    // 1. Accommodation Polygon (Warsan Camp)
    const campCoords = state.synced.accommodation?.boundary?.coordinates?.[0] || DEFAULT_CAMP_POLYGON;
    if (campCoords) {
      const latlngs = campCoords.map((pt) => [pt[1], pt[0]]);
      state.layers.accommodation = L.polygon(latlngs, {
        color: '#059669',
        fillColor: '#10b981',
        fillOpacity: 0.25,
        weight: 2,
      }).addTo(state.map);
      const campTitle = state.synced.accommodation?.name || 'Warsan Staff Accommodation Camp';
      state.layers.accommodation.bindTooltip(`🏠 ${campTitle}`, { permanent: true, direction: 'center' });
    }

    // 2. Worksite Polygons and Geofence Perimeter
    const jobList = state.synced.jobs.length > 0
      ? state.synced.jobs
      : [
          {
            job_name: 'Dubai Silicon Oasis Landscape Maintenance',
            boundary: { coordinates: [DEFAULT_WORKSITE_POLYGON] },
            geofence_circle: { center: { lat: 25.1310, lng: 55.3840 }, radius_m: 300 },
          },
        ];

    jobList.forEach((job) => {
      if (job.boundary?.coordinates?.[0]) {
        const latlngs = job.boundary.coordinates[0].map((pt) => [pt[1], pt[0]]);
        const poly = L.polygon(latlngs, {
          color: '#2563eb',
          fillColor: '#3b82f6',
          fillOpacity: 0.3,
          weight: 2,
        }).addTo(state.map);
        poly.bindTooltip(`📍 ${job.job_name}`, { permanent: true, direction: 'center' });
        state.layers.worksites.push(poly);
      }

      if (job.geofence_circle?.center) {
        const circle = L.circle([job.geofence_circle.center.lat, job.geofence_circle.center.lng], {
          radius: job.geofence_circle.radius_m,
          color: '#6366f1',
          fillColor: '#818cf8',
          fillOpacity: 0.08,
          weight: 1.5,
          dashArray: '4, 4',
        }).addTo(state.map);
        state.layers.geofences.push(circle);
      }
    });

    // Update Route Polyline
    renderRoutePolyline();
  }

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
    const campCoords = state.synced.accommodation?.boundary?.coordinates?.[0] || DEFAULT_CAMP_POLYGON;
    if (campCoords && isPointInPolygon({ lat, lng }, campCoords)) {
      detectedZone = 'CAMP';
      zoneTitle = 'CAMP (WARSAN)';
      badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    }

    // Check Worksites & Geofence
    const jobList = state.synced.jobs.length > 0
      ? state.synced.jobs
      : [
          {
            job_id: null,
            boundary: { coordinates: [DEFAULT_WORKSITE_POLYGON] },
            geofence_circle: { center: { lat: 25.1310, lng: 55.3840 }, radius_m: 300 },
          },
        ];

    jobList.forEach((job) => {
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

    // Calculate Distance to Camp
    const campLat = Number(state.synced.accommodation?.rep_latitude || 25.15825);
    const campLng = Number(state.synced.accommodation?.rep_longitude || 55.41225);
    const distM = Math.round(haversineMeters(lat, lng, campLat, campLng));
    document.getElementById('campDistance').innerText = distM < 1000 ? `${distM} m away` : `${(distM / 1000).toFixed(1)} km away`;

    // Automatic Transition Event Generator (Matches Phase 07 Contract)
    if (detectedZone !== state.currentZone) {
      if (detectedZone === 'WORKSITE_POLYGON') {
        queueEvent('ENTRY', activeWorksiteId, simulatedTime);
      } else if (state.currentZone === 'WORKSITE_POLYGON' && detectedZone !== 'WORKSITE_POLYGON') {
        queueEvent('EXIT', state.currentWorksiteId, simulatedTime);
      } else if (detectedZone === 'GEOFENCE_BUFFER') {
        queueEvent('PING', activeWorksiteId, simulatedTime);
      }
    }

    state.currentZone = detectedZone;
    state.currentWorksiteId = activeWorksiteId;
  }

  // Queue Event (Conforming to EventBatchRequest & MobileEventItem schemas)
  function queueEvent(type, worksiteId = null, recordedAt = null) {
    const evt = {
      event_id: crypto.randomUUID(),
      event_type: type,
      event_timestamp_utc: recordedAt || new Date().toISOString(),
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
          <span class="text-slate-500 font-mono">${e.event_timestamp_utc.split('T')[1].slice(0, 8)}</span>
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

    // Find current waypoint segment
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
    const simulatedIso = `${new Date().toISOString().split('T')[0]}T${timeStr}Z`;
    updateWorkerPosition(currentLat, currentLng, simulatedIso);
  }

  function loadRoute(waypoints) {
    state.route.waypoints = waypoints;
    state.route.progress = 0;
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
  }

  // Render Full Synced State into UI
  function applySyncedSnapshot(snapshot) {
    state.cursor = snapshot.cursor;
    document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;

    state.synced.jobs = [];
    state.synced.dayPlans = [];
    state.synced.scheduleItems = [];

    // Parse all entities (supporting either payload or data key)
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

    // 1. Settings card
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

      if (p.supervisor) {
        document.getElementById('spvName').innerText = p.supervisor.name;
        document.getElementById('spvPhone').innerText = p.supervisor.phone || '+971 50 123 4567';
        document.getElementById('spvCallLink').href = `tel:${p.supervisor.phone || '+971501234567'}`;
        document.getElementById('profSpv').innerText = p.supervisor.name;
      }
    }

    // 3. Accommodation Card
    if (state.synced.accommodation) {
      document.getElementById('campName').innerText = state.synced.accommodation.name;
      document.getElementById('profCamp').innerText = state.synced.accommodation.name;
    }

    // 4. Assigned Worksite Card
    if (state.synced.jobs.length > 0) {
      const j = state.synced.jobs[0];
      document.getElementById('shiftJobName').innerText = j.job_name;
      document.getElementById('shiftJobNumber').innerText = `${j.job_number} • Commercial Maintenance`;
    }

    // 5. Today's Day Plan Resolution
    const todayStr = new Date().toISOString().split('T')[0];
    const todayPlan = state.synced.dayPlans.find((dp) => dp.work_date === todayStr) || state.synced.dayPlans[0];

    if (todayPlan) {
      const isWorking = todayPlan.status === 'WORKING';
      const badge = document.getElementById('shiftStatusBadge');
      badge.innerText = todayPlan.status;
      badge.className = isWorking
        ? 'text-3xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300'
        : 'text-3xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300';

      if (todayPlan.planned) {
        document.getElementById('plannedCampStart').innerText = `${todayPlan.planned.accommodation_start} AM`;
        document.getElementById('shiftSiteHours').innerText = `${todayPlan.planned.first_site_start} - ${todayPlan.planned.last_site_end}`;
        document.getElementById('shiftBreak').innerText = `${todayPlan.planned.break_minutes} min midday`;
      }
      if (todayPlan.alarm_time) {
        document.getElementById('alarmDisplayTime').innerText = `${todayPlan.alarm_time} AM`;
      }
    }

    // 6. Roster Tab (30-day forward view)
    const workingDaysCount = state.synced.dayPlans.filter((dp) => dp.status === 'WORKING').length;
    document.getElementById('schedCount').innerText = `${workingDaysCount} working days`;

    const schedEl = document.getElementById('phoneScheduleList');
    schedEl.innerHTML = state.synced.dayPlans
      .map((p) => {
        const isToday = p.work_date === todayStr;
        const isWork = p.status === 'WORKING';
        const badgeColor = isWork ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200';
        const jobName = state.synced.jobs[0]?.job_name || 'Landscape Maintenance';

        return `
          <div class="p-2.5 bg-white rounded-xl border ${isToday ? 'border-indigo-400 shadow-xs' : 'border-slate-200'} text-3xs space-y-1">
            <div class="flex justify-between items-center font-bold">
              <span class="text-slate-900 font-mono flex items-center gap-1">
                ${p.work_date}
                ${isToday ? '<span class="bg-indigo-600 text-white px-1.5 py-0.2 rounded text-3xs font-semibold">TODAY</span>' : ''}
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

    // Update map features & refresh ground truth
    updateMapLayers();
    calculateGroundTruthMetrics(state.route.waypoints);
  }

  // Setup Event Listeners
  function setupEvents() {
    // Phone Tab Navigation
    document.getElementById('navBtnToday').addEventListener('click', () => switchTab('today'));
    document.getElementById('navBtnGps').addEventListener('click', () => switchTab('gps'));
    document.getElementById('navBtnRoster').addEventListener('click', () => switchTab('roster'));
    document.getElementById('navBtnProfile').addEventListener('click', () => switchTab('profile'));
    document.getElementById('navBtnSync').addEventListener('click', () => switchTab('sync'));

    // Test Alarm Audio Chime
    document.getElementById('btnTestAlarm').addEventListener('click', () => {
      playAlarmChime();
      alert('⏰ BEEP BEEP! Shift Alarm ringing locally at 04:30 AM (30 min lead before camp departure).');
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
      const preset = PRESET_ROUTES[e.target.value];
      if (preset) loadRoute(preset.waypoints);
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
            alert(`Loaded custom route: ${waypoints.length} waypoints.`);
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

    // Sign In Action
    document.getElementById('phoneBtnLogin').addEventListener('click', async () => {
      const tally_id = document.getElementById('phoneInputTally').value;
      const password = document.getElementById('phoneInputPwd').value;

      try {
        const res = await api('/mobile/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            tally_id,
            password,
            device: {
              device_identifier: state.device.identifier,
              platform: state.device.platform,
              device_model: state.device.model,
              app_version: state.device.app_version,
              os_version: state.device.os_version,
            },
          }),
        });

        state.token = res.access_token;
        state.worker = res.employee;
        localStorage.setItem('fwt_mobile_token', state.token);

        setAuthenticatedState(true, res.employee);

        // Immediately pull full snapshot
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
      try {
        const res = await api('/mobile/sync/snapshot');
        applySyncedSnapshot(res);
      } catch (err) {
        alert(`Snapshot pull failed: ${err.message}`);
      }
    }

    document.getElementById('phoneBtnPullSnapshot').addEventListener('click', pullSnapshot);

    // Pull Delta Sync
    document.getElementById('phoneBtnPullDelta').addEventListener('click', async () => {
      try {
        const res = await api(`/mobile/sync/changes?cursor=${state.cursor}`);
        if (res.resync_required) {
          alert('Server signaled resync_required=true. Pulling fresh snapshot.');
          return pullSnapshot();
        }
        state.cursor = res.cursor;
        document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;
        alert(`Delta sync complete: ${res.changes.length} changes applied. Cursor: ${res.cursor}`);
      } catch (err) {
        alert(`Delta sync failed: ${err.message}`);
      }
    });

    // Ack Cursor
    document.getElementById('phoneBtnAck').addEventListener('click', async () => {
      try {
        await api('/mobile/sync/ack', {
          method: 'POST',
          body: JSON.stringify({ cursor: state.cursor }),
        });
        alert(`Cursor ${state.cursor} acknowledged successfully with server.`);
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
        alert(`Batch sent! Accepted: ${accepted}, Rejected: ${rejected}. Cursor: ${res.latest_cursor}`);
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

  // Application Startup
  window.addEventListener('DOMContentLoaded', async () => {
    initMap();
    setupEvents();
    loadRoute(PRESET_ROUTES.standard.waypoints);
    updateWorkerPosition(state.workerLocation.lat, state.workerLocation.lng);

    // If existing valid token is stored, attempt auto-restore
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