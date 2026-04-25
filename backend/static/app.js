/*
  Touchscreen UI logic (vanilla JS).

  The frontend is intentionally lightweight for Raspberry Pi kiosk mode:
  - Polls the backend cache (/api/aircraft) every second
  - Renders aircraft cards with big tap targets
  - Sends a selection to /api/select to forward lat/lon to the globe integration
*/

const POLL_INTERVAL_MS = 1000;
const PLACEHOLDER_IMG = "/static/aircraft-placeholder.svg";

function $(id) {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Missing element: #${id}`);
  }
  return el;
}

function formatNumber(value, unit) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return unit ? `${value} ${unit}` : String(value);
}

function formatCoord(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (typeof value === "number") return value.toFixed(4);
  const parsed = Number(value);
  if (Number.isFinite(parsed)) return parsed.toFixed(4);
  return "—";
}

function normalizeFlight(value, hex) {
  const text = (value || "").trim();
  return text.length > 0 ? text : hex.toUpperCase();
}

function showToast(message, kind) {
  const toast = $("toast");
  toast.textContent = message;
  toast.style.borderColor = kind === "error" ? "rgba(255,107,107,0.35)" : "rgba(98,246,184,0.28)";
  toast.style.background = kind === "error" ? "rgba(40, 14, 16, 0.92)" : "rgba(10, 32, 24, 0.92)";
  toast.classList.add("show");
  window.clearTimeout(showToast._t);
  showToast._t = window.setTimeout(() => toast.classList.remove("show"), 2400);
}

async function fetchAircraft() {
  const response = await fetch("/api/aircraft", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return await response.json();
}

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

function renderDetails(selected, meta) {
  const details = $("details");
  if (!selected) {
    details.replaceChildren();
    return;
  }

  const hex = String(selected.hex || "").toUpperCase();
  const flight = normalizeFlight(selected.flight, selected.hex);

  const imageUrl = meta && meta.image_url ? String(meta.image_url) : PLACEHOLDER_IMG;
  const type = meta && meta.type ? String(meta.type) : "Unknown type";
  const airline = meta && meta.airline ? String(meta.airline) : "Unknown airline";

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

  const title = document.createElement("div");
  title.className = "detailsTitle";
  title.textContent = `${flight} • ${hex}`;

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

  row.appendChild(kvPos);
  row.appendChild(kvType);
  row.appendChild(kvAirline);

  info.appendChild(title);
  info.appendChild(row);

  card.appendChild(img);
  card.appendChild(info);

  details.replaceChildren(card);
}

function render(state) {
  const statusEl = $("status");
  const grid = $("grid");

  const ok = Boolean(state.ok);
  const count = Array.isArray(state.aircraft) ? state.aircraft.length : 0;
  const pollText =
    typeof state.polled_at_unix_s === "number"
      ? `polled ${(Date.now() / 1000 - state.polled_at_unix_s).toFixed(1)}s ago`
      : "not polled yet";

  statusEl.textContent = ok ? `${count} aircraft • ${pollText}` : `dump1090 offline • ${String(state.error || "unknown error")}`;
  statusEl.style.color = ok ? "rgba(154,166,178,0.95)" : "rgba(255,107,107,0.95)";

  const list = Array.isArray(state.aircraft) ? state.aircraft.slice() : [];
  list.sort((a, b) => normalizeFlight(a.flight, a.hex).localeCompare(normalizeFlight(b.flight, b.hex)));

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
    flight.textContent = normalizeFlight(a.flight, a.hex);

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
async function onSelect(hex) {
  if (isSelecting) return;
  isSelecting = true;
  try {
    const result = await selectAircraft(hex);
    renderDetails(result && result.selected ? result.selected : null, result && result.meta ? result.meta : null);
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

async function loop() {
  try {
    const state = await fetchAircraft();
    render(state);
  } catch (err) {
    $("status").textContent = `Backend offline • ${String(err && err.message ? err.message : err)}`;
    $("status").style.color = "rgba(255,107,107,0.95)";
  } finally {
    window.setTimeout(loop, POLL_INTERVAL_MS);
  }
}

loop();
