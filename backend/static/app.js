/* app.js - Frontend Logik.

Beinhaltet das Polling der Daten, Tab-Wechsel, UI-Updates und Distanzberechnungen.
*/

const POLL_INTERVAL_MS = 1000;
const PLACEHOLDER_IMG = "/static/aircraft-placeholder.svg";

// --- In-Memory-Zustand ---
let selectedHex = null;
let selectedMeta = null;
let systemPosition = null;

// --- DOM-Elemente ---
/**
 * Holt ein DOM-Element anhand seiner ID und wirft einen Fehler, falls es nicht existiert.
 */
function $(id) {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Missing element: #${id}`);
  }
  return el;
}

/**
 * Prüft, ob der Browser auf reduzierte Animationen (z.B. für Barrierefreiheit) eingestellt ist.
 */
function prefersReducedMotion() {
  return Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
}

/**
 * Scrollt die Ansicht nach der Auswahl eines Flugzeugs nach ganz oben,
 * um die Details sofort sichtbar zu machen.
 */
function scrollToTopAfterSelection() {
  const behavior = prefersReducedMotion() ? "auto" : "smooth";
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: 0, left: 0, behavior });
  });
}

/**
 * Formatiert eine Zahl sicher als String, optional mit angehängter Einheit.
 */
function formatNumber(value, unit) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return unit ? `${value} ${unit}` : String(value);
}

/**
 * Formatiert GPS-Koordinaten auf 4 Nachkommastellen genau.
 */
function formatCoord(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (typeof value === "number") return value.toFixed(4);
  const parsed = Number(value);
  if (Number.isFinite(parsed)) return parsed.toFixed(4);
  return "—";
}

/**
 * Berechnet die Distanz zwischen zwei GPS-Punkten in Kilometern mittels Haversine-Formel.
 */
function haversineKm(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Normalisiert eine Flugnummer/Callsign (entfernt Leerzeichen).
 */
function normalizeFlight(value) {
  const text = (value || "").trim();
  return text.length > 0 ? text : null;
}

/**
 * Gibt die formatierte Flugnummer zurück oder einen Platzhalterstrich, falls keine vorhanden ist.
 */
function displayFlight(value) {
  const flight = normalizeFlight(value);
  return flight ? flight : "—";
}

/**
 * Liefert den Sortierschlüssel für die Flugzeugliste (bevorzugt Flugnummer, ansonsten Hex).
 */
function sortKeyForAircraft(a) {
  const flight = normalizeFlight(a && a.flight);
  if (flight) return flight;
  return String((a && a.hex) || "");
}

/**
 * Normalisiert eine Hex-Adresse in einen sauberen, kleingeschriebenen String.
 */
function normalizeHex(hex) {
  return String(hex || "").trim().toLowerCase();
}

/**
 * Sendet einen API-Call, um das aktuell verfolgte Flugzeug abzuwählen.
 */
async function unselectAircraft() {
  const response = await fetch("/api/unselect", {
    method: "POST",
    headers: { "content-type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Unselect failed: HTTP ${response.status}`);
  }
}

/**
 * Hebt die Auswahl im Frontend auf, leert die Detailansicht und aktualisiert das Backend.
 */
async function clearSelection() {
  try {
    await unselectAircraft();
  } finally {
    selectedHex = null;
    selectedMeta = null;
    renderDetails(null, null);
  }
}

/**
 * Zeigt eine temporäre Toast-Benachrichtigung an (z.B. für Erfolg oder Fehler).
 */
function showToast(message, kind) {
  const toast = $("toast");
  toast.textContent = message;
  toast.style.borderColor = kind === "error" ? "rgba(255,107,107,0.35)" : "rgba(98,246,184,0.28)";
  toast.style.background = kind === "error" ? "rgba(40, 14, 16, 0.92)" : "rgba(10, 32, 24, 0.92)";
  toast.classList.add("show");
  window.clearTimeout(showToast._t);
  showToast._t = window.setTimeout(() => toast.classList.remove("show"), 2400);
}

/**
 * Pollt die aktuellsten Flugzeugdaten vom Backend.
 */
async function fetchAircraft() {
  const response = await fetch("/api/aircraft", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return await response.json();
}

/**
 * Wählt ein Flugzeug aus und fordert das Backend auf, die Metadaten/Globe-Integration zu starten.
 */
async function selectAircraft(hex) {
  const response = await fetch("/api/select", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ hex }),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail ? String(data.detail) : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

/**
 * Rendert die Detailansicht eines ausgewählten Flugzeugs (Bild, Koordinaten, Distanz).
 */
function renderDetails(selected, meta) {
  const details = $("details");
  if (!selected) {
    details.replaceChildren();
    return;
  }

  const hex = String(selected.hex || "").toUpperCase();
  const flight = displayFlight(selected.flight);

  const imageUrl = meta && meta.image_url ? String(meta.image_url) : PLACEHOLDER_IMG;
  const type = meta && meta.type ? String(meta.type) : "Unknown type";
  const airline = meta && meta.airline ? String(meta.airline) : "Unknown airline";

  let distanceText = "—";
  if (
    systemPosition &&
    typeof systemPosition.lat === "number" &&
    typeof systemPosition.lon === "number" &&
    typeof selected.lat === "number" &&
    typeof selected.lon === "number"
  ) {
    const km = haversineKm(systemPosition.lat, systemPosition.lon, selected.lat, selected.lon);
    if (Number.isFinite(km)) distanceText = `${km.toFixed(1)} km`;
  }

  const card = document.createElement("div");
  card.className = "detailsCard";

  const img = document.createElement("img");
  img.className = "detailsImg";
  img.alt = `${flight} ${hex}`;
  img.src = imageUrl;
  img.addEventListener("error", () => {
    img.src = PLACEHOLDER_IMG;
  });

  const info = document.createElement("div");

  const header = document.createElement("div");
  header.className = "detailsHeader";

  const title = document.createElement("div");
  title.className = "detailsTitle";
  title.textContent = `${flight} • ${hex}`;

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "detailsClose";
  closeBtn.setAttribute("aria-label", "Unselect aircraft");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    void clearSelection();
  });

  header.appendChild(title);
  header.appendChild(closeBtn);

  const row = document.createElement("div");
  row.className = "detailsRow";

  const kvPos = document.createElement("div");
  kvPos.className = "kv";
  kvPos.innerHTML = `<div class="k">Position</div><div class="v">${formatCoord(selected.lat)}, ${formatCoord(selected.lon)}</div>`;

  const kvType = document.createElement("div");
  kvType.className = "kv";
  kvType.innerHTML = `<div class="k">Type</div><div class="v">${type}</div>`;

  const kvAirline = document.createElement("div");
  kvAirline.className = "kv";
  kvAirline.innerHTML = `<div class="k">Airline</div><div class="v">${airline}</div>`;

  const kvDistance = document.createElement("div");
  kvDistance.className = "kv";
  kvDistance.innerHTML = `<div class="k">Distance</div><div class="v">${distanceText}</div>`;

  row.appendChild(kvPos);
  row.appendChild(kvType);
  row.appendChild(kvAirline);
  row.appendChild(kvDistance);

  info.appendChild(header);
  info.appendChild(row);

  card.appendChild(img);
  card.appendChild(info);

  details.replaceChildren(card);
}

/**
 * Rendert die Liste/Grid aller aktuell getrackten Flugzeuge.
 */
function render(state) {
  const statusEl = $("status");
  const grid = $("grid");

  systemPosition = state && state.system_position ? state.system_position : null;

  const ok = Boolean(state.ok);
  const count = Array.isArray(state.aircraft) ? state.aircraft.length : 0;
  const pollText =
    typeof state.polled_at_unix_s === "number"
      ? `polled ${(Date.now() / 1000 - state.polled_at_unix_s).toFixed(1)}s ago`
      : "not polled yet";

  statusEl.textContent = ok ? `${count} aircraft • ${pollText}` : `dump1090 offline • ${String(state.error || "unknown error")}`;
  statusEl.style.color = ok ? "rgba(154,166,178,0.95)" : "rgba(255,107,107,0.95)";

  const list = Array.isArray(state.aircraft) ? state.aircraft.slice() : [];
  list.sort((a, b) => sortKeyForAircraft(a).localeCompare(sortKeyForAircraft(b)));

  const fragment = document.createDocumentFragment();
  for (const a of list) {
    const hasPos = a.lat !== null && a.lat !== undefined && a.lon !== null && a.lon !== undefined;

    const card = document.createElement("div");
    card.className = "card";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-disabled", String(!hasPos));

    const header = document.createElement("div");
    header.className = "cardHeader";

    const flight = document.createElement("div");
    flight.className = "flight";
    flight.textContent = displayFlight(a.flight);

    const hex = document.createElement("div");
    hex.className = "hex";
    hex.textContent = a.hex.toUpperCase();

    header.appendChild(flight);
    header.appendChild(hex);

    const meta = document.createElement("div");
    meta.className = "meta";

    const alt = document.createElement("div");
    alt.className = "kv";
    alt.innerHTML = `<div class="k">Altitude</div><div class="v">${formatNumber(a.altitude, "")}</div>`;

    const spd = document.createElement("div");
    spd.className = "kv";
    spd.innerHTML = `<div class="k">Speed</div><div class="v">${formatNumber(a.speed, "")}</div>`;

    meta.appendChild(alt);
    meta.appendChild(spd);

    const ctaRow = document.createElement("div");
    ctaRow.className = "ctaRow";
    const btn = document.createElement("button");
    btn.className = "button";
    btn.type = "button";
    btn.disabled = !hasPos;
    btn.textContent = hasPos ? "Select on Globe" : "No Position Yet";

    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await onSelect(a.hex);
    });

    ctaRow.appendChild(btn);

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(ctaRow);

    const onKey = async (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (hasPos) {
          await onSelect(a.hex);
        } else {
          showToast("No lat/lon available for this aircraft yet.", "error");
        }
      }
    };
    card.addEventListener("keydown", onKey);
    card.addEventListener("click", async () => {
      if (hasPos) {
        await onSelect(a.hex);
      } else {
        showToast("No lat/lon available for this aircraft yet.", "error");
      }
    });

    fragment.appendChild(card);
  }

  grid.replaceChildren(fragment);
}

let isSelecting = false;
/**
 * Handler für das Anklicken/Auswählen eines Flugzeugs.
 */
async function onSelect(hex) {
  if (isSelecting) return;
  isSelecting = true;
  try {
    const result = await selectAircraft(hex);
    selectedHex = normalizeHex(hex);
    selectedMeta = result && result.meta ? result.meta : null;
    renderDetails(result && result.selected ? result.selected : null, selectedMeta);
    scrollToTopAfterSelection();
    const forward = result && result.forward ? result.forward : null;
    if (forward && forward.sent) {
      showToast(`Forwarded ${hex.toUpperCase()} via ${forward.mode}.`, "ok");
    } else {
      const detail = forward && forward.detail ? String(forward.detail) : "not sent";
      showToast(`Not forwarded: ${detail}`, "error");
    }
  } catch (err) {
    showToast(String(err && err.message ? err.message : err), "error");
  } finally {
    isSelecting = false;
  }
}

/**
 * Aktualisiert die Detailansicht live, falls sich Position, Höhe oder Geschwindigkeit
 * des aktuell ausgewählten Flugzeugs geändert haben.
 */
function refreshSelectedFromState(state) {
  if (!selectedHex || !state || !Array.isArray(state.aircraft)) return;
  const match = state.aircraft.find((a) => normalizeHex(a && a.hex) === selectedHex) || null;
  if (!match) return;
  renderDetails(match, selectedMeta);
}

/**
 * Die Haupt-Polling-Schleife. Wird jede Sekunde aufgerufen.
 */
async function loop() {
  try {
    const state = await fetchAircraft();
    render(state);
    refreshSelectedFromState(state);
  } catch (err) {
    $("status").textContent = `Backend offline • ${String(err && err.message ? err.message : err)}`;
    $("status").style.color = "rgba(255,107,107,0.95)";
  } finally {
    window.setTimeout(loop, POLL_INTERVAL_MS);
  }
}

// --- Tab Navigation ---
/**
 * Initialisiert die Klick-Event-Listener für das Umschalten der UI-Tabs.
 */
function setupTabs() {
  const tabAircrafts = $("tabAircrafts");
  const tabGlobeControl = $("tabGlobeControl");
  const viewAircrafts = $("viewAircrafts");
  const viewGlobeControl = $("viewGlobeControl");

  tabAircrafts.addEventListener("click", () => {
    tabAircrafts.classList.add("active");
    tabGlobeControl.classList.remove("active");
    viewAircrafts.classList.remove("hidden");
    viewGlobeControl.classList.add("hidden");
  });

  tabGlobeControl.addEventListener("click", () => {
    tabGlobeControl.classList.add("active");
    tabAircrafts.classList.remove("active");
    viewGlobeControl.classList.remove("hidden");
    viewAircrafts.classList.add("hidden");
  });
}

// --- Globe Control Logik ---
/**
 * Sendet einen Befehl an das Backend, um den Anzeigemodus des Holo-Globes zu ändern.
 */
async function setGlobeMode(mode, color = null) {
  try {
    const payload = { mode };
    if (color) {
      payload.color = color;
    }
    
    const response = await fetch("/api/globe/mode", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
    }

    showToast(`Display mode ${mode} set successfully.`, "ok");
  } catch (err) {
    showToast(String(err && err.message ? err.message : err), "error");
  }
}

/**
 * Generiert zufällige Koordinaten und sendet sie als neuen "set_points" Befehl an den Globe.
 */
async function setRandomPlane() {
  try {
    const lat = (Math.random() * 180) - 90;
    const lon = (Math.random() * 360) - 180;
    
    const payload = {
      points: [
        {
          id: "RND" + Math.floor(Math.random() * 1000),
          lat: lat,
          lon: lon,
          color: [255, 255, 255]
        }
      ]
    };
    
    const response = await fetch("/api/globe/points", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
    }

    showToast(`Random plane spot set successfully.`, "ok");
  } catch (err) {
    showToast(String(err && err.message ? err.message : err), "error");
  }
}

// --- Motor Control Logik ---
/**
 * Sendet einen Befehl an das Backend, um die Motorgeschwindigkeit (RPM) zu ändern.
 */
async function setMotorRpm(rpm) {
  try {
    const mode = rpm > 0 ? 1 : 0;
    const payload = { mode, rpm };

    const response = await fetch("/api/globe/motor", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
    }

    showToast(mode === 0 ? "Motor off." : `Motor set to ${rpm} rpm.`, "ok");
  } catch (err) {
    showToast(String(err && err.message ? err.message : err), "error");
  }
}

setupTabs();
loop();
