// FWT Mobile Tester Proxy Application Logic
// Phase 07 Mobile Contract & GPS Simulator

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
    currentZone: 'OUTSIDE',
    currentWorksiteId: null,
    workerLocation: { lat: 25.15825, lng: 55.41225 }, // Warsan start
    eventsQueue: [],
    map: null,
    workerMarker: null,
    layers: {
      worksites: [],
      geofences: [],
      accommodation: null,
    },
  };

  // Helper logging
  function log(msg, type = 'info') {
    const el = document.getElementById('consoleLog');
    const line = document.createElement('div');
    const time = new Date().toISOString().split('T')[1].slice(0, 8);
    let color = 'text-slate-300';
    if (type === 'success') color = 'text-emerald-400';
    if (type === 'error') color = 'text-rose-400 font-semibold';
    if (type === 'warn') color = 'text-amber-400';
    if (type === 'network') color = 'text-sky-300';

    line.className = color;
    line.innerHTML = `<span class="text-slate-500">[${time}]</span> ${msg}`;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  }

  // Point in Polygon (Ray-casting Algorithm)
  function isPointInPolygon(point, polygonCoordinates) {
    // polygonCoordinates: array of [lng, lat]
    const x = point.lng;
    const y = point.lat;
    let inside = false;

    for (let i = 0, j = polygonCoordinates.length - 1; i < polygonCoordinates.length; j = i++) {
      const xi = polygonCoordinates[i][0], yi = polygonCoordinates[i][1];
      const xj = polygonCoordinates[j][0], yj = polygonCoordinates[j][1];

      const intersect = ((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  // Haversine Distance (in meters)
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

  // Initialize Map
  function initMap() {
    state.map = L.map('map').setView([25.12, 55.28], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(state.map);

    // Draggable Worker Pin Icon
    const workerIcon = L.divIcon({
      className: 'custom-worker-pin',
      html: `
        <div class="relative flex items-center justify-center">
          <div class="w-6 h-6 bg-indigo-600 rounded-full border-2 border-white shadow-lg flex items-center justify-center text-white text-3xs font-bold pulse-marker">
            👷
          </div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    state.workerMarker = L.marker([state.workerLocation.lat, state.workerLocation.lng], {
      draggable: true,
      icon: workerIcon,
    }).addTo(state.map);

    state.workerMarker.bindPopup('<b>Worker: Shanto Miah</b><br>Drag me anywhere on map to test location!');

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
    // Clear old layers
    state.layers.worksites.forEach((l) => state.map.removeLayer(l));
    state.layers.geofences.forEach((l) => state.map.removeLayer(l));
    if (state.layers.accommodation) state.map.removeLayer(state.layers.accommodation);
    state.layers.worksites = [];
    state.layers.geofences = [];

    // Accommodation Polygon
    if (state.synced.accommodation && state.synced.accommodation.boundary) {
      const geo = state.synced.accommodation.boundary;
      if (geo.coordinates && geo.coordinates[0]) {
        const latlngs = geo.coordinates[0].map((pt) => [pt[1], pt[0]]);
        state.layers.accommodation = L.polygon(latlngs, {
          color: '#059669',
          fillColor: '#10b981',
          fillOpacity: 0.25,
          weight: 2,
        }).addTo(state.map);
        state.layers.accommodation.bindTooltip(`🏠 ${state.synced.accommodation.name}`, { permanent: true, direction: 'center' });
      }
    }

    // Worksite Polygons and Geofence Circles
    state.synced.jobs.forEach((job) => {
      if (job.boundary && job.boundary.coordinates && job.boundary.coordinates[0]) {
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

      if (job.geofence_circle && job.geofence_circle.center) {
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
  }

  // Detect Zone & Point Containment
  function updateWorkerPosition(lat, lng) {
    state.workerLocation = { lat, lng };
    document.getElementById('posLat').innerText = lat.toFixed(6);
    document.getElementById('posLng').innerText = lng.toFixed(6);

    let detectedZone = 'OUTSIDE';
    let zoneName = 'Transit / Offsite';
    let activeWorksiteId = null;

    // Check Accommodation
    if (state.synced.accommodation && state.synced.accommodation.boundary) {
      const coords = state.synced.accommodation.boundary.coordinates[0];
      if (isPointInPolygon({ lat, lng }, coords)) {
        detectedZone = 'ACCOMMODATION';
        zoneName = state.synced.accommodation.name;
      }
    }

    // Check Worksites & Geofence
    state.synced.jobs.forEach((job) => {
      if (job.boundary && job.boundary.coordinates) {
        if (isPointInPolygon({ lat, lng }, job.boundary.coordinates[0])) {
          detectedZone = 'WORKSITE_POLYGON';
          zoneName = `${job.job_name} (Inside)`;
          activeWorksiteId = job.worksite_id;
        } else if (job.geofence_circle) {
          const dist = haversineMeters(lat, lng, job.geofence_circle.center.lat, job.geofence_circle.center.lng);
          if (dist <= job.geofence_circle.radius_m && detectedZone === 'OUTSIDE') {
            detectedZone = 'GEOFENCE_BUFFER';
            zoneName = `${job.job_name} (Geofence Perimeter)`;
            activeWorksiteId = job.worksite_id;
          }
        }
      }
    });

    const badge = document.getElementById('zoneStatusBadge');
    badge.innerText = detectedZone;
    if (detectedZone === 'WORKSITE_POLYGON') {
      badge.className = 'text-2xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300';
    } else if (detectedZone === 'GEOFENCE_BUFFER') {
      badge.className = 'text-2xs font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 border border-indigo-300';
    } else if (detectedZone === 'ACCOMMODATION') {
      badge.className = 'text-2xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300';
    } else {
      badge.className = 'text-2xs font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-600';
    }

    document.getElementById('posZoneName').innerText = zoneName;

    // Auto-generate Event if transition occurred
    const autoGen = document.getElementById('autoGenEvents').checked;
    if (autoGen && detectedZone !== state.currentZone) {
      if (detectedZone === 'WORKSITE_POLYGON') {
        queueEvent('ENTRY', activeWorksiteId);
      } else if (state.currentZone === 'WORKSITE_POLYGON' && detectedZone !== 'WORKSITE_POLYGON') {
        queueEvent('EXIT', state.currentWorksiteId);
      } else if (detectedZone === 'GEOFENCE_BUFFER') {
        queueEvent('PING', activeWorksiteId);
      }
    }

    state.currentZone = detectedZone;
    state.currentWorksiteId = activeWorksiteId;
  }

  // Queue Event
  function queueEvent(type, worksiteId = null) {
    const evt = {
      event_id: crypto.randomUUID(),
      event_type: type,
      recorded_at: new Date().toISOString(),
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
    log(`Queued Event: [${type}] at (${evt.latitude.toFixed(4)}, ${evt.longitude.toFixed(4)})`, 'info');
  }

  function renderQueue() {
    const el = document.getElementById('queueList');
    const badge = document.getElementById('queueCount');
    badge.innerText = `${state.eventsQueue.length} events`;

    if (state.eventsQueue.length === 0) {
      el.innerHTML = '<div class="text-slate-400 text-center py-4">No events queued</div>';
      return;
    }

    el.innerHTML = state.eventsQueue
      .map(
        (e, idx) => `
        <div class="p-1.5 bg-slate-50 rounded border border-slate-200 flex justify-between items-center text-3xs">
          <div>
            <span class="font-bold ${
              e.event_type === 'ENTRY'
                ? 'text-emerald-700'
                : e.event_type === 'EXIT'
                ? 'text-rose-700'
                : 'text-indigo-700'
            }">${e.event_type}</span>
            <span class="text-slate-500">${e.recorded_at.split('T')[1].slice(0, 8)}</span>
          </div>
          <div class="text-slate-500">
            (${e.latitude.toFixed(3)}, ${e.longitude.toFixed(3)})
          </div>
        </div>
      `
      )
      .join('');
  }

  // API Requests wrapper
  async function api(path, options = {}) {
    const baseUrl = document.getElementById('apiUrl').value.replace(/\/+$/, '');
    const url = `${baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {}),
    };

    log(`--> ${options.method || 'GET'} ${path}`, 'network');
    try {
      const res = await fetch(url, { ...options, headers });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        log(`<-- ERROR ${res.status}: ${data?.detail || res.statusText}`, 'error');
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }

      log(`<-- OK ${res.status} (${JSON.stringify(data).slice(0, 100)}...)`, 'success');
      return data;
    } catch (err) {
      log(`API Failed: ${err.message}`, 'error');
      throw err;
    }
  }

  // Setup Event Listeners
  function setupEvents() {
    // 1. Login
    document.getElementById('btnLogin').addEventListener('click', async () => {
      const tally_id = document.getElementById('loginId').value;
      const password = document.getElementById('loginPwd').value;
      const device_id = document.getElementById('loginDevId').value;
      const platform = document.getElementById('loginPlatform').value;

      try {
        const res = await api('/mobile/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            tally_id,
            password,
            device_identifier: device_id,
            platform,
            device_model: state.device.model,
            app_version: state.device.app_version,
            os_version: state.device.os_version,
          }),
        });

        state.token = res.access_token;
        state.worker = res.employee;
        localStorage.setItem('fwt_mobile_token', state.token);

        document.getElementById('authBadge').innerText = 'Authenticated';
        document.getElementById('authBadge').className = 'text-2xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800';
        document.getElementById('connStatus').className = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-900 text-emerald-200';
        document.getElementById('connStatus').innerHTML = '<span class="w-1.5 h-1.5 mr-1.5 bg-emerald-400 rounded-full"></span>Connected';

        document.getElementById('profName').innerText = res.employee.name;
        document.getElementById('profRole').innerText = `Tally: ${res.employee.tally_id} • ${res.employee.staff_grade_description || 'Worker'}`;

        document.getElementById('loginForm').classList.add('hidden');
        document.getElementById('authProfile').classList.remove('hidden');

        if (res.must_change_password) {
          document.getElementById('pwdChangePrompt').classList.remove('hidden');
          log('⚠️ Server requires password change on first login.', 'warn');
        } else {
          document.getElementById('pwdChangePrompt').classList.add('hidden');
          // Automatically pull snapshot
          document.getElementById('btnSnapshot').click();
        }
      } catch (e) {
        alert(`Login failed: ${e.message}`);
      }
    });

    // Forced Password Change
    document.getElementById('btnSubmitNewPwd').addEventListener('click', async () => {
      const old_password = document.getElementById('loginPwd').value;
      const new_password = document.getElementById('newPwd').value;

      try {
        await api('/mobile/auth/change-password', {
          method: 'POST',
          body: JSON.stringify({ old_password, new_password }),
        });
        document.getElementById('pwdChangePrompt').classList.add('hidden');
        document.getElementById('loginPwd').value = new_password;
        log('Password changed successfully! Resuming operations.', 'success');
        document.getElementById('btnSnapshot').click();
      } catch (e) {
        alert(`Password change failed: ${e.message}`);
      }
    });

    // Logout
    document.getElementById('btnLogout').addEventListener('click', async () => {
      try {
        await api('/mobile/auth/logout', { method: 'POST' });
      } catch {}
      state.token = null;
      localStorage.removeItem('fwt_mobile_token');
      document.getElementById('loginForm').classList.remove('hidden');
      document.getElementById('authProfile').classList.add('hidden');
      document.getElementById('authBadge').innerText = 'Unauthenticated';
      document.getElementById('authBadge').className = 'text-2xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-600';
      document.getElementById('connStatus').className = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200';
      document.getElementById('connStatus').innerHTML = '<span class="w-1.5 h-1.5 mr-1.5 bg-red-400 rounded-full animate-pulse"></span>Disconnected';
    });

    // Accept Consent
    document.getElementById('btnAcceptConsent').addEventListener('click', async () => {
      try {
        await api('/mobile/auth/consent', {
          method: 'POST',
          body: JSON.stringify({
            policy_version: '1.0.0',
            accepted: true,
            language: 'en',
            app_version: state.device.app_version,
          }),
        });
        document.getElementById('consentBadge').innerText = 'Consent: Accepted (v1.0.0)';
        document.getElementById('consentBadge').className = 'px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium';
      } catch (e) {
        alert(`Consent recording failed: ${e.message}`);
      }
    });

    // Heartbeat
    document.getElementById('btnHeartbeat').addEventListener('click', async () => {
      try {
        const res = await api('/mobile/auth/heartbeat', {
          method: 'POST',
          body: JSON.stringify({
            device_identifier: document.getElementById('loginDevId').value,
            battery_pct: 85,
            location_permission_state: 'ALWAYS',
            app_version: state.device.app_version,
          }),
        });
        log(`Heartbeat ACK: resync_required=${res.resync_required}`, 'success');
      } catch (e) {
        alert(`Heartbeat failed: ${e.message}`);
      }
    });

    // 2. Sync Snapshot
    document.getElementById('btnSnapshot').addEventListener('click', async () => {
      try {
        const res = await api('/mobile/sync/snapshot');
        state.cursor = res.cursor;
        document.getElementById('cursorDisplay').innerText = `Cursor: ${state.cursor}`;

        // Parse entities
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

        document.getElementById('cntJobs').innerText = state.synced.jobs.length;
        document.getElementById('cntDays').innerText = state.synced.dayPlans.length;

        // Display Today's Plan
        const todayIso = new Date().toISOString().split('T')[0];
        const todayPlan = state.synced.dayPlans.find((p) => p.work_date === todayIso);
        if (todayPlan) {
          document.getElementById('todayPlanDetails').classList.remove('hidden');
          document.getElementById('todayDate').innerText = todayPlan.work_date;
          document.getElementById('todayTimes').innerText = `${todayPlan.planned_start_time || '07:00'} - ${todayPlan.planned_end_time || '16:00'} (Alarm: ${todayPlan.alarm_time || '06:30'})`;
          document.getElementById('todayMarkers').innerText = `Markers: ${(todayPlan.markers || []).join(', ') || 'SCHEDULED'}`;
        }

        updateMapLayers();
        log(`Snapshot synced! Loaded ${res.entities.length} entities. Cursor: ${state.cursor}`, 'success');
      } catch (e) {
        alert(`Snapshot sync failed: ${e.message}`);
      }
    });

    // Delta Sync
    document.getElementById('btnDelta').addEventListener('click', async () => {
      try {
        const res = await api(`/mobile/sync/changes?cursor=${state.cursor}`);
        if (res.resync_required) {
          log('⚠️ Server indicated resync_required=true (cursor below floor). Pulling fresh snapshot.', 'warn');
          return document.getElementById('btnSnapshot').click();
        }

        state.cursor = res.cursor;
        document.getElementById('cursorDisplay').innerText = `Cursor: ${state.cursor}`;
        log(`Delta sync OK: ${res.changes.length} changes received. New cursor: ${res.cursor}`, 'success');

        // Apply coalesced changes
        res.changes.forEach((c) => {
          log(`Applied Delta: [${c.entity_type}] ${c.entity_id} (${c.operation})`, 'info');
        });
      } catch (e) {
        alert(`Delta sync failed: ${e.message}`);
      }
    });

    // Ack Sync
    document.getElementById('btnAck').addEventListener('click', async () => {
      try {
        await api('/mobile/sync/ack', {
          method: 'POST',
          body: JSON.stringify({ cursor: state.cursor }),
        });
        log(`Acknowledged cursor ${state.cursor} with server.`, 'success');
      } catch (e) {
        alert(`Ack failed: ${e.message}`);
      }
    });

    // 3. Teleport Buttons
    document.getElementById('btnTeleportWorksite').addEventListener('click', () => {
      const lat = 25.08025;
      const lng = 55.14525;
      state.workerMarker.setLatLng([lat, lng]);
      state.map.setView([lat, lng], 16);
      updateWorkerPosition(lat, lng);
    });

    document.getElementById('btnTeleportBuffer').addEventListener('click', () => {
      // Near Marina edge
      const lat = 25.0782;
      const lng = 55.1435;
      state.workerMarker.setLatLng([lat, lng]);
      state.map.setView([lat, lng], 16);
      updateWorkerPosition(lat, lng);
    });

    document.getElementById('btnTeleportAccom').addEventListener('click', () => {
      const lat = 25.15825;
      const lng = 55.41225;
      state.workerMarker.setLatLng([lat, lng]);
      state.map.setView([lat, lng], 16);
      updateWorkerPosition(lat, lng);
    });

    document.getElementById('btnTeleportTransit').addEventListener('click', () => {
      const lat = 25.115;
      const lng = 55.23;
      state.workerMarker.setLatLng([lat, lng]);
      state.map.setView([lat, lng], 13);
      updateWorkerPosition(lat, lng);
    });

    // Manual Event Buttons
    document.getElementById('btnEvtEntry').addEventListener('click', () => queueEvent('ENTRY'));
    document.getElementById('btnEvtPing').addEventListener('click', () => queueEvent('PING'));
    document.getElementById('btnEvtExit').addEventListener('click', () => queueEvent('EXIT'));
    document.getElementById('btnClearQueue').addEventListener('click', () => {
      state.eventsQueue = [];
      renderQueue();
    });

    // Send Batch to Server
    document.getElementById('btnSendBatch').addEventListener('click', async () => {
      if (state.eventsQueue.length === 0) {
        return alert('No events in queue to send.');
      }

      const batch = [...state.eventsQueue];
      try {
        const res = await api('/mobile/events/batch', {
          method: 'POST',
          body: JSON.stringify({ events: batch }),
        });

        log(`Batch Sent: accepted=${res.accepted_count}, rejected=${res.rejected_count}`, 'success');
        if (res.results) {
          res.results.forEach((r) => {
            if (r.status === 'REJECTED') {
              log(`❌ Event ${r.event_id.slice(0, 8)} rejected: ${r.reason}`, 'error');
            }
          });
        }
        state.eventsQueue = [];
        renderQueue();
      } catch (e) {
        alert(`Event batch ingestion failed: ${e.message}`);
      }
    });

    // Auto Tour / Simulate Shift
    document.getElementById('btnSimulateShift').addEventListener('click', async () => {
      log('Starting automated workday tour simulation...', 'info');
      // Step 1: At Camp
      document.getElementById('btnTeleportAccom').click();
      await new Promise((r) => setTimeout(r, 1500));

      // Step 2: In Transit
      document.getElementById('btnTeleportTransit').click();
      await new Promise((r) => setTimeout(r, 1500));

      // Step 3: Enter Worksite
      document.getElementById('btnTeleportWorksite').click();
      await new Promise((r) => setTimeout(r, 1500));

      // Step 4: Dispatch Batch
      document.getElementById('btnSendBatch').click();
    });

    // Clear Console
    document.getElementById('btnClearLog').addEventListener('click', () => {
      document.getElementById('consoleLog').innerHTML = '';
    });
  }

  // Startup
  window.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupEvents();
    updateWorkerPosition(state.workerLocation.lat, state.workerLocation.lng);
  });
})();

