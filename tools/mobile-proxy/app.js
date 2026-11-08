// FWT Mobile Tester Proxy & GPS Route Player
// Phase 07 Mobile Contract & Android Studio Style Simulator

(function () {
  // Global State
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
    activeTab: 'shift', // 'shift', 'gps', 'schedule', 'settings'
    currentZone: 'ACCOMMODATION',
    currentWorksiteId: null,
    workerLocation: { lat: 25.15825, lng: 55.41225 }, // Warsan default
    eventsQueue: [],
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

  // Preset Routes
  const PRESET_ROUTES = {
    standard: {
      name: 'Standard Clean Workday (06:02 - 15:31)',
      waypoints: [
        { time: '05:00:00', lat: 25.15825, lng: 55.41225, label: 'Warsan Staff Camp' },
        { time: '05:20:00', lat: 25.18300, lng: 55.35000, label: 'Ras Al Khor Transit' },
        { time: '05:40:00', lat: 25.13000, lng: 55.24000, label: 'Al Khail Road Transit' },
        { time: '05:58:00', lat: 25.07820, lng: 55.14350, label: 'Marina Geofence Perimeter' },
        { time: '06:02:00', lat: 25.08025, lng: 55.14525, label: 'Site Entry (Marina Towers)' },
        { time: '09:00:00', lat: 25.08080, lng: 55.14580, label: 'Mid-Morning Site Work' },
        { time: '12:00:00', lat: 25.08010, lng: 55.14480, label: 'Midday Break on Site' },
        { time: '14:00:00', lat: 25.08050, lng: 55.14540, label: 'Afternoon Site Work' },
        { time: '15:31:00', lat: 25.07750, lng: 55.14200, label: 'Site Exit' },
        { time: '16:05:00', lat: 25.14000, lng: 55.28000, label: 'Return Commute Transit' },
        { time: '16:30:00', lat: 25.15825, lng: 55.41225, label: 'Return to Warsan Camp' },
      ],
    },
    late: {
      name: 'Late Arrival Shift (Arrives 08:30)',
      waypoints: [
        { time: '07:00:00', lat: 25.15825, lng: 55.41225, label: 'Late Departure Camp' },
        { time: '07:45:00', lat: 25.13000, lng: 55.24000, label: 'Transit Al Khail' },
        { time: '08:28:00', lat: 25.07820, lng: 55.14350, label: 'Marina Perimeter' },
        { time: '08:30:00', lat: 25.08025, lng: 55.14525, label: 'Late Site Entry' },
        { time: '12:00:00', lat: 25.08050, lng: 55.14540, label: 'Midday Work' },
        { time: '15:31:00', lat: 25.07750, lng: 55.14200, label: 'Site Exit' },
        { time: '16:30:00', lat: 25.15825, lng: 55.41225, label: 'Back at Camp' },
      ],
    },
    midday_gap: {
      name: 'Midday Gap (Leaves 11:30, Returns 13:00)',
      waypoints: [
        { time: '05:00:00', lat: 25.15825, lng: 55.41225, label: 'Camp' },
        { time: '06:02:00', lat: 25.08025, lng: 55.14525, label: 'Site Entry' },
        { time: '11:30:00', lat: 25.07500, lng: 55.13500, label: 'Unauthorized Exit' },
        { time: '12:15:00', lat: 25.06000, lng: 55.12000, label: 'Offsite Roaming' },
        { time: '13:00:00', lat: 25.08025, lng: 55.14525, label: 'Re-entry to Site' },
        { time: '15:31:00', lat: 25.07750, lng: 55.14200, label: 'Final Exit' },
        { time: '16:30:00', lat: 25.15825, lng: 55.41225, label: 'Camp' },
      ],
    },
  };

  // Network Inspector Logger
  function logNetwork(method, path, status, latencyMs, reqBody, resBody) {
    const el = document.getElementById('networkLogList');
    const line = document.createElement('div');
    const time = new Date().toISOString().split('T')[1].slice(0, 8);
    const isSuccess = status >= 200 && status < 300;
    const badgeColor = isSuccess ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-rose-950 text-rose-400 border-rose-800';

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
    let entries = 0;
    let pings = 0;
    let exits = 0;

    for (let i = 0; i < waypoints.length - 1; i++) {
      const p1 = waypoints[i];
      const p2 = waypoints[i + 1];
      const duration = timeStrToSeconds(p2.time) - timeStrToSeconds(p1.time);
      if (duration <= 0) continue;

      const midPt = { lat: (p1.lat + p2.lat) / 2, lng: (p1.lng + p2.lng) / 2 };
      let insideSite = false;
      let insideCamp = false;

      if (state.synced.accommodation?.boundary?.coordinates) {
        insideCamp = isPointInPolygon(midPt, state.synced.accommodation.boundary.coordinates[0]);
      }
      state.synced.jobs.forEach((j) => {
        if (j.boundary?.coordinates && isPointInPolygon(midPt, j.boundary.coordinates[0])) {
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

    // Always 1 ENTRY and 1 EXIT for clean day
    entries = 1;
    exits = 1;

    const workedMin = Math.round(workedSecs / 60);
    const workedH = Math.floor(workedMin / 60);
    const workedM = workedMin % 60;

    const transitMin = Math.round(transitSecs / 60);
    const transitH = Math.floor(transitMin / 60);
    const transitM = transitMin % 60;

    document.getElementById('gtWorkedTime').innerText = `${workedH}h ${String(workedM).padStart(2, '0')}m (${workedMin}m)`;
    document.getElementById('gtTransitTime').innerText = `${transitH}h ${String(transitM).padStart(2, '0')}m`;
    document.getElementById('gtEventsCount').innerText = `${entries} ENTRY • ${pings} PING • ${exits} EXIT`;
  }

  // Initialize Map
  function initMap() {
    state.map = L.map('map', { zoomControl: false }).setView([25.12, 55.28], 11);
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
          <div class="w-7 h-7 bg-indigo-600 rounded-full border-2 border-white shadow-xl flex items-center justify-center text-white text-xs pulse-marker">
            👷
          </div>
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
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
  }

  // Render Map Features from Synced Data
  function updateMapLayers() {
    state.layers.worksites.forEach((l) => state.map.removeLayer(l));
    state.layers.geofences.forEach((l) => state.map.removeLayer(l));
    if (state.layers.accommodation) state.map.removeLayer(state.layers.accommodation);
    state.layers.worksites = [];
    state.layers.geofences = [];

    // Accommodation Polygon
    if (state.synced.accommodation?.boundary?.coordinates?.[0]) {
      const latlngs = state.synced.accommodation.boundary.coordinates[0].map((pt) => [pt[1], pt[0]]);
      state.layers.accommodation = L.polygon(latlngs, {
        color: '#059669',
        fillColor: '#10b981',
        fillOpacity: 0.25,
        weight: 2,
      }).addTo(state.map);
      state.layers.accommodation.bindTooltip(`🏠 ${state.synced.accommodation.name}`, { permanent: true, direction: 'center' });
    }

    // Worksite Polygons and Geofence Circles
    state.synced.jobs.forEach((job) => {
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
          weight: 1,
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

    // Check Accommodation
    if (state.synced.accommodation?.boundary?.coordinates) {
      if (isPointInPolygon({ lat, lng }, state.synced.accommodation.boundary.coordinates[0])) {
        detectedZone = 'ACCOMMODATION';
        zoneTitle = 'CAMP (WARSAN)';
        badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300';
      }
    }

    // Check Worksites & Geofence
    state.synced.jobs.forEach((job) => {
      if (job.boundary?.coordinates) {
        if (isPointInPolygon({ lat, lng }, job.boundary.coordinates[0])) {
          detectedZone = 'WORKSITE_POLYGON';
          zoneTitle = 'INSIDE WORKSITE';
          badgeClass = 'bg-blue-100 text-blue-800 border-blue-300';
          activeWorksiteId = job.worksite_id;
        } else if (job.geofence_circle) {
          const dist = haversineMeters(lat, lng, job.geofence_circle.center.lat, job.geofence_circle.center.lng);
          if (dist <= job.geofence_circle.radius_m && detectedZone !== 'WORKSITE_POLYGON') {
            detectedZone = 'GEOFENCE_BUFFER';
            zoneTitle = 'PERIMETER (GEOFENCE)';
            badgeClass = 'bg-purple-100 text-purple-800 border-purple-300';
            activeWorksiteId = job.worksite_id;
          }
        }
      }
    });

    const badge = document.getElementById('phoneZoneBadge');
    badge.innerText = zoneTitle;
    badge.className = `text-2xs font-bold px-2 py-0.5 rounded-full border ${badgeClass}`;

    // Calculate Distance to Camp
    if (state.synced.accommodation?.rep_latitude) {
      const distM = Math.round(haversineMeters(lat, lng, Number(state.synced.accommodation.rep_latitude), Number(state.synced.accommodation.rep_longitude)));
      document.getElementById('campDistance').innerText = distM < 1000 ? `${distM} m away` : `${(distM / 1000).toFixed(1)} km away`;
    }

    // Transition Event Generator
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

  // Queue Event
  function queueEvent(type, worksiteId = null, recordedAt = null) {
    const evt = {
      event_id: crypto.randomUUID(),
      event_type: type,
      recorded_at: recordedAt || new Date().toISOString(),
      latitude: state.workerLocation.lat,
      longitude: state.workerLocation.lng,
      accuracy_m: 4.5,
      speed_mps: 0.0,
      battery_pct: 88,
      worksite_id: worksiteId || state.currentWorksiteId,
      is_mock: false,
    };

    state.eventsQueue.push(evt);
    renderQueue();
  }

  function renderQueue() {
    const el = document.getElementById('phoneQueueList');
    const badge = document.getElementById('phoneQueueCount');
    badge.innerText = `${state.eventsQueue.length} events`;

    if (state.eventsQueue.length === 0) {
      el.innerHTML = '<div class="text-slate-400 text-center py-2">Queue is empty</div>';
      return;
    }

    el.innerHTML = state.eventsQueue
      .map(
        (e) => `
        <div class="p-1 bg-white rounded border border-slate-200 flex justify-between items-center text-3xs">
          <span class="font-bold ${
            e.event_type === 'ENTRY' ? 'text-emerald-700' : e.event_type === 'EXIT' ? 'text-rose-700' : 'text-indigo-700'
          }">${e.event_type}</span>
          <span class="text-slate-500">${e.recorded_at.split('T')[1].slice(0, 8)}</span>
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
    document.getElementById('routeEndTime').innerText = waypoints[waypoints.length - 1]?.time || '16:30:00';
    renderRoutePolyline();
    calculateGroundTruthMetrics(waypoints);
    applyRouteProgress(0);
  }

  // Switch Mobile Phone Screen Tabs
  function switchTab(tabId) {
    state.activeTab = tabId;
    ['Shift', 'Gps', 'Schedule', 'Settings'].forEach((t) => {
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

  // Wire up Event Listeners
  function setupEvents() {
    // Tab Navigation
    document.getElementById('navBtnShift').addEventListener('click', () => switchTab('shift'));
    document.getElementById('navBtnGps').addEventListener('click', () => switchTab('gps'));
    document.getElementById('navBtnSchedule').addEventListener('click', () => switchTab('schedule'));
    document.getElementById('navBtnSettings').addEventListener('click', () => switchTab('settings'));

    // Test Alarm Chime
    document.getElementById('btnTestAlarm').addEventListener('click', () => {
      playAlarmChime();
      alert('⏰ BEEP BEEP! Shift Alarm ringing locally at 04:30 AM (30 min before camp departure).');
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

    // Login Action
    document.getElementById('phoneBtnLogin').addEventListener('click', async () => {
      const tally_id = document.getElementById('phoneInputTally').value;
      const password = document.getElementById('phoneInputPwd').value;

      try {
        const res = await api('/mobile/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            tally_id,
            password,
            device_identifier: state.device.identifier,
            platform: state.device.platform,
            device_model: state.device.model,
            app_version: state.device.app_version,
            os_version: state.device.os_version,
          }),
        });

        state.token = res.access_token;
        state.worker = res.employee;
        localStorage.setItem('fwt_mobile_token', state.token);

        document.getElementById('phoneUserTag').innerText = res.employee.name;
        document.getElementById('connBadge').className = 'flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-emerald-950 border border-emerald-800 text-emerald-400';
        document.getElementById('connBadge').innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span><span>Connected</span>';

        document.getElementById('phoneAuthForm').classList.add('hidden');
        document.getElementById('phoneAuthProfile').classList.remove('hidden');
        document.getElementById('phoneAuthWorkerName').innerText = res.employee.name;
        document.getElementById('phoneAuthWorkerRole').innerText = `${res.employee.tally_id} • ${res.employee.staff_grade_description || 'Worker'}`;

        // Pull fresh snapshot automatically
        document.getElementById('phoneBtnPullSnapshot').click();
      } catch (err) {
        alert(`Login failed: ${err.message}`);
      }
    });

    // Logout Action
    document.getElementById('phoneBtnLogout').addEventListener('click', async () => {
      try { await api('/mobile/auth/logout', { method: 'POST' }); } catch {}
      state.token = null;
      localStorage.removeItem('fwt_mobile_token');
      document.getElementById('phoneUserTag').innerText = 'Offline';
      document.getElementById('connBadge').className = 'flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-red-950 border border-red-800 text-red-400';
      document.getElementById('connBadge').innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span><span>Disconnected</span>';
      document.getElementById('phoneAuthForm').classList.remove('hidden');
      document.getElementById('phoneAuthProfile').classList.add('hidden');
    });

    // Pull Snapshot Action
    document.getElementById('phoneBtnPullSnapshot').addEventListener('click', async () => {
      try {
        const res = await api('/mobile/sync/snapshot');
        state.cursor = res.cursor;
        document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;

        state.synced.jobs = [];
        state.synced.dayPlans = [];
        state.synced.scheduleItems = [];

        res.entities.forEach((item) => {
          if (item.entity_type === 'PROFILE') state.synced.profile = item.data;
          if (item.entity_type === 'SETTINGS') state.synced.settings = item.data;
          if (item.entity_type === 'ACCOMMODATION') state.synced.accommodation = item.data;
          if (item.entity_type === 'JOB') state.synced.jobs.push(item.data);
          if (item.entity_type === 'DAY_PLAN') state.synced.dayPlans.push(item.data);
          if (item.entity_type === 'SCHEDULE_ITEM') state.synced.scheduleItems.push(item.data);
        });

        // Update UI Cards
        if (state.synced.settings) {
          document.getElementById('cfgRadius').innerText = `${state.synced.settings.geofence_circle_radius_m} m`;
          document.getElementById('cfgApproach').innerText = `${state.synced.settings.approach_polling_interval_s} s`;
          document.getElementById('cfgConfirm').innerText = `${state.synced.settings.confirmation_polling_interval_s} s`;
          document.getElementById('cfgAlarmLead').innerText = `${state.synced.settings.alarm_lead_minutes} min`;
          document.getElementById('alarmLeadTag').innerText = `${state.synced.settings.alarm_lead_minutes}m lead`;
        }

        if (state.synced.profile) {
          if (state.synced.profile.supervisor) {
            document.getElementById('spvName').innerText = state.synced.profile.supervisor.name;
            document.getElementById('spvPhone').innerText = state.synced.profile.supervisor.phone || '+971 50 123 4567';
          }
        }

        if (state.synced.accommodation) {
          document.getElementById('campName').innerText = state.synced.accommodation.name;
        }

        if (state.synced.jobs.length > 0) {
          document.getElementById('shiftJobName').innerText = state.synced.jobs[0].job_name;
          document.getElementById('shiftJobNumber').innerText = `${state.synced.jobs[0].job_number} • Commercial`;
        }

        // Render Schedule Tab
        document.getElementById('schedCount').innerText = `${state.synced.dayPlans.length} days`;
        const schedEl = document.getElementById('phoneScheduleList');
        schedEl.innerHTML = state.synced.dayPlans
          .map(
            (p) => `
            <div class="p-2 bg-white rounded-lg border border-slate-200 text-3xs space-y-1">
              <div class="flex justify-between items-center font-bold">
                <span class="text-slate-800 font-mono">${p.work_date}</span>
                <span class="px-1.5 py-0.2 rounded-full ${
                  p.status === 'WORKING' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'
                }">${p.status}</span>
              </div>
              <div class="flex justify-between text-slate-500">
                <span>Shift: ${p.planned_start_time || '06:00'} - ${p.planned_end_time || '15:30'}</span>
                <span>Alarm: ${p.alarm_time || '04:30'}</span>
              </div>
            </div>
          `
          )
          .join('');

        updateMapLayers();
      } catch (err) {
        alert(`Snapshot pull failed: ${err.message}`);
      }
    });

    // Pull Delta Sync
    document.getElementById('phoneBtnPullDelta').addEventListener('click', async () => {
      try {
        const res = await api(`/mobile/sync/changes?cursor=${state.cursor}`);
        if (res.resync_required) {
          alert('Server signaled resync_required=true. Pulling fresh snapshot.');
          return document.getElementById('phoneBtnPullSnapshot').click();
        }
        state.cursor = res.cursor;
        document.getElementById('phoneCursorBadge').innerText = `Cursor: ${state.cursor}`;
        alert(`Delta sync completed: ${res.changes.length} changes applied. Cursor: ${res.cursor}`);
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

    // Flush Batch
    document.getElementById('phoneBtnFlushBatch').addEventListener('click', async () => {
      if (state.eventsQueue.length === 0) return alert('Event queue is empty.');
      const batch = [...state.eventsQueue];
      try {
        const res = await api('/mobile/events/batch', {
          method: 'POST',
          body: JSON.stringify({ events: batch }),
        });
        state.eventsQueue = [];
        renderQueue();
        alert(`Batch sent! Accepted: ${res.accepted_count}, Rejected: ${res.rejected_count}`);
      } catch (err) {
        alert(`Batch failed: ${err.message}`);
      }
    });

    // Clear Network Log
    document.getElementById('btnClearNetworkLog').addEventListener('click', () => {
      document.getElementById('networkLogList').innerHTML = '';
    });
  }

  // Application Startup
  window.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupEvents();
    loadRoute(PRESET_ROUTES.standard.waypoints);
    updateWorkerPosition(state.workerLocation.lat, state.workerLocation.lng);

    // If already has token, attempt auto-login
    if (state.token) {
      document.getElementById('phoneBtnPullSnapshot').click();
    }
  });
})();
