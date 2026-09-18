/**
 * GridWise Demonstration Dashboard - Frontend Application
 * Strictly consumes the backend HTTP API contract without client-side interpretation or solver heuristics.
 */

// Global State
let publicSamples = [];
let currentScenario = {
  scenario_id: "DEMO-SCENARIO-01",
  operator_notes: ["The battery charging circuit will be disconnected between 2 PM and 4 PM."],
  hours: Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    demand_kwh: (50 + Math.sin(h / 3) * 20).toFixed(1) * 1,
    solar_kwh: (h >= 6 && h <= 18 ? Math.sin((h - 6) / 12 * Math.PI) * 45 : 0).toFixed(1) * 1,
    tariff_bdt_per_kwh: (h < 6 || h >= 22 ? 8.0 : h >= 17 && h <= 21 ? 18.0 : 12.0)
  })),
  battery: {
    capacity_kwh: 200.0,
    initial_energy_kwh: 100.0,
    minimum_energy_kwh: 20.0,
    max_charge_kwh_per_hour: 50.0,
    max_discharge_kwh_per_hour: 50.0
  }
};

let lastResponse = null;
let lastRequest = null;
let energyChart = null;
let batteryChart = null;

// DOM Elements
const apiBaseInput = document.getElementById("apiBaseInput");
const checkHealthBtn = document.getElementById("checkHealthBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const sampleSelect = document.getElementById("sampleSelect");
const loadSampleBtn = document.getElementById("loadSampleBtn");

const scenarioIdInput = document.getElementById("scenarioIdInput");
const notesContainer = document.getElementById("notesContainer");
const addNoteBtn = document.getElementById("addNoteBtn");
const batteryCapacity = document.getElementById("batteryCapacity");
const batteryInitial = document.getElementById("batteryInitial");
const batteryMin = document.getElementById("batteryMin");
const batteryMaxCharge = document.getElementById("batteryMaxCharge");
const batteryMaxDischarge = document.getElementById("batteryMaxDischarge");
const hoursTableBody = document.getElementById("hoursTableBody");
const optimizeBtn = document.getElementById("optimizeBtn");
const errorAlert = document.getElementById("errorAlert");
const errorTitle = document.getElementById("errorTitle");
const errorMessage = document.getElementById("errorMessage");

const kpiCost = document.getElementById("kpiCost");
const kpiGrid = document.getElementById("kpiGrid");
const kpiPeak = document.getElementById("kpiPeak");
const planSummaryText = document.getElementById("planSummaryText");
const directivesList = document.getElementById("directivesList");
const resultsTableBody = document.getElementById("resultsTableBody");
const jsonInspector = document.getElementById("jsonInspector");
const tabResponse = document.getElementById("tabResponse");
const tabRequest = document.getElementById("tabRequest");
const copyJsonBtn = document.getElementById("copyJsonBtn");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");

let activeTab = "response";

// Initialization
async function init() {
  loadPublicSamples();
  renderInputs();
  checkHealth();
  setupEventListeners();
}

async function loadPublicSamples() {
  try {
    const res = await fetch("sample_cases.json");
    if (res.ok) {
      publicSamples = await res.json();
      sampleSelect.innerHTML = `<option value="">-- Choose a public sample case --</option>`;
      publicSamples.forEach((sample, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${sample.id} (${sample.label})`;
        sampleSelect.appendChild(opt);
      });
    }
  } catch (e) {
    console.warn("Could not load public samples:", e);
  }
}

function getApiBase() {
  let url = apiBaseInput.value.trim();
  if (url.endsWith("/")) url = url.slice(0, -1);
  return url;
}

// Health Check
async function checkHealth() {
  const base = getApiBase();
  statusDot.className = "status-dot checking";
  statusText.textContent = "Checking...";

  try {
    const res = await fetch(`${base}/health`, { method: "GET" });
    if (res.ok) {
      statusDot.className = "status-dot online";
      statusText.textContent = "Online (200 OK)";
    } else {
      statusDot.className = "status-dot offline";
      statusText.textContent = `Error ${res.status}`;
    }
  } catch (err) {
    statusDot.className = "status-dot offline";
    statusText.textContent = "Offline / Connection Refused";
  }
}

// Render Inputs
function renderInputs() {
  scenarioIdInput.value = currentScenario.scenario_id;
  batteryCapacity.value = currentScenario.battery.capacity_kwh;
  batteryInitial.value = currentScenario.battery.initial_energy_kwh;
  batteryMin.value = currentScenario.battery.minimum_energy_kwh;
  batteryMaxCharge.value = currentScenario.battery.max_charge_kwh_per_hour;
  batteryMaxDischarge.value = currentScenario.battery.max_discharge_kwh_per_hour;

  renderNotes();
  renderHoursTable();
}

function renderNotes() {
  notesContainer.innerHTML = "";
  currentScenario.operator_notes.forEach((note, idx) => {
    const row = document.createElement("div");
    row.className = "note-row";
    row.innerHTML = `
      <div class="note-badge">${idx}</div>
      <input type="text" class="form-control note-input" data-index="${idx}" value="${escapeHtml(note)}" placeholder="Operator note..." />
      <button class="btn-icon delete-note-btn" data-index="${idx}" title="Remove note" ${currentScenario.operator_notes.length <= 1 ? "disabled" : ""}>✕</button>
    `;
    notesContainer.appendChild(row);
  });

  addNoteBtn.disabled = currentScenario.operator_notes.length >= 3;
}

function renderHoursTable() {
  hoursTableBody.innerHTML = "";
  currentScenario.hours.forEach((h, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600; text-align:center;">${h.hour}</td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-demand" data-hour="${h.hour}" value="${h.demand_kwh}" /></td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-solar" data-hour="${h.hour}" value="${h.solar_kwh}" /></td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-tariff" data-hour="${h.hour}" value="${h.tariff_bdt_per_kwh}" /></td>
    `;
    hoursTableBody.appendChild(tr);
  });
}

// Build Request Payload from UI
function buildRequestPayload() {
  const notes = Array.from(document.querySelectorAll(".note-input"))
    .map(input => input.value.trim())
    .filter(n => n.length > 0);

  const hours = Array.from({ length: 24 }, (_, h) => {
    const dInput = document.querySelector(`.hr-demand[data-hour="${h}"]`);
    const sInput = document.querySelector(`.hr-solar[data-hour="${h}"]`);
    const tInput = document.querySelector(`.hr-tariff[data-hour="${h}"]`);
    return {
      hour: h,
      demand_kwh: parseFloat(dInput ? dInput.value : 0) || 0.0,
      solar_kwh: parseFloat(sInput ? sInput.value : 0) || 0.0,
      tariff_bdt_per_kwh: parseFloat(tInput ? tInput.value : 0) || 0.0
    };
  });

  const battery = {
    capacity_kwh: parseFloat(batteryCapacity.value) || 0.0,
    initial_energy_kwh: parseFloat(batteryInitial.value) || 0.0,
    minimum_energy_kwh: parseFloat(batteryMin.value) || 0.0,
    max_charge_kwh_per_hour: parseFloat(batteryMaxCharge.value) || 0.0,
    max_discharge_kwh_per_hour: parseFloat(batteryMaxDischarge.value) || 0.0
  };

  return {
    scenario_id: scenarioIdInput.value.trim() || "DEMO-SCENARIO",
    operator_notes: notes,
    hours: hours,
    battery: battery
  };
}

// Execute Optimization Call
async function runOptimization() {
  hideError();
  const base = getApiBase();
  const payload = buildRequestPayload();
  lastRequest = payload;

  if (activeTab === "request") {
    renderJsonInspector();
  }

  optimizeBtn.disabled = true;
  optimizeBtn.innerHTML = `<span class="loading-spinner"></span> Optimizing...`;

  try {
    const res = await fetch(`${base}/optimize-energy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    lastResponse = data;

    if (!res.ok) {
      showError(
        `Backend Error HTTP ${res.status}: ${data?.error?.code || "ERROR"}`,
        data?.error?.message || JSON.stringify(data)
      );
      renderJsonInspector();
      return;
    }

    renderResults(data);
  } catch (err) {
    showError("Network / Connection Failure", `Failed to contact ${base}/optimize-energy: ${err.message}`);
    lastResponse = { error: { code: "NETWORK_ERROR", message: err.message } };
  } finally {
    optimizeBtn.disabled = false;
    optimizeBtn.innerHTML = `<span>⚡</span> Run Energy Optimization`;
    renderJsonInspector();
  }
}

// Render Results
function renderResults(data) {
  // KPIs
  kpiCost.textContent = `${Number(data.total_cost_bdt).toFixed(2)} BDT`;
  kpiGrid.textContent = `${Number(data.total_grid_kwh).toFixed(2)} kWh`;
  kpiPeak.textContent = `${Number(data.peak_grid_kwh).toFixed(2)} kWh`;
  planSummaryText.textContent = data.plan_summary || "24-hour cost-optimal plan computed successfully.";

  // Directives
  directivesList.innerHTML = "";
  if (data.directive_interpretation && data.directive_interpretation.length > 0) {
    data.directive_interpretation.forEach(d => {
      const card = document.createElement("div");
      card.className = `directive-card ${d.applies ? "" : "noop"}`;
      card.innerHTML = `
        <div class="directive-header">
          <span class="directive-type">[Note #${d.note_index}] ${d.directive_type}</span>
          <span class="directive-applies ${d.applies ? "applies-true" : "applies-false"}">
            ${d.applies ? "APPLIES" : "NO-OP"}
          </span>
        </div>
        <div class="directive-explanation">${escapeHtml(d.explanation || "")}</div>
        ${d.structured_adjustment ? `<div class="directive-details">Adjustment: ${JSON.stringify(d.structured_adjustment)}</div>` : ""}
      `;
      directivesList.appendChild(card);
    });
  } else {
    directivesList.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem;">No directives interpreted.</div>`;
  }

  // Results Table
  resultsTableBody.innerHTML = "";
  if (data.hourly_plan) {
    data.hourly_plan.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:600; text-align:center;">${item.hour}</td>
        <td>${Number(item.grid_kwh).toFixed(2)}</td>
        <td>${Number(item.solar_used_kwh).toFixed(2)}</td>
        <td><span class="badge-action action-${item.battery_action}">${item.battery_action}</span></td>
        <td>${Number(item.battery_kwh).toFixed(2)}</td>
        <td>${Number(item.battery_energy_after_kwh).toFixed(2)}</td>
      `;
      resultsTableBody.appendChild(tr);
    });
  }

  // Render Visual Charts
  renderCharts(data, lastRequest);
}

// Charts
function renderCharts(response, request) {
  const hours = response.hourly_plan.map(p => `H${p.hour}`);
  const gridData = response.hourly_plan.map(p => p.grid_kwh);
  const solarUsedData = response.hourly_plan.map(p => p.solar_used_kwh);
  const batteryFlow = response.hourly_plan.map(p => (p.battery_action === "discharge" ? p.battery_kwh : 0));
  const batteryCharge = response.hourly_plan.map(p => (p.battery_action === "charge" ? p.battery_kwh : 0));
  const demandData = request.hours.map(h => h.demand_kwh);
  const batteryEnergy = response.hourly_plan.map(p => p.battery_energy_after_kwh);
  const tariffData = request.hours.map(h => h.tariff_bdt_per_kwh);

  // Destroy previous charts if existing
  if (energyChart) energyChart.destroy();
  if (batteryChart) batteryChart.destroy();

  const ctxEnergy = document.getElementById("energyChart").getContext("2d");
  energyChart = new Chart(ctxEnergy, {
    type: "bar",
    data: {
      labels: hours,
      datasets: [
        {
          label: "Solar Used (kWh)",
          data: solarUsedData,
          backgroundColor: "rgba(6, 182, 212, 0.75)",
          stack: "Supply"
        },
        {
          label: "Grid Import (kWh)",
          data: gridData,
          backgroundColor: "rgba(56, 189, 248, 0.75)",
          stack: "Supply"
        },
        {
          label: "Battery Discharge (kWh)",
          data: batteryFlow,
          backgroundColor: "rgba(245, 158, 11, 0.75)",
          stack: "Supply"
        },
        {
          label: "Demand (kWh)",
          data: demandData,
          type: "line",
          borderColor: "#f43f5e",
          borderWidth: 2,
          pointRadius: 2,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(51, 65, 85, 0.4)" }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(51, 65, 85, 0.4)" }, ticks: { color: "#94a3b8" }, title: { display: true, text: "kWh", color: "#94a3b8" } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });

  const ctxBattery = document.getElementById("batteryChart").getContext("2d");
  batteryChart = new Chart(ctxBattery, {
    type: "line",
    data: {
      labels: hours,
      datasets: [
        {
          label: "Battery Energy (kWh)",
          data: batteryEnergy,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          borderWidth: 2,
          fill: true,
          pointRadius: 3,
          yAxisID: "y"
        },
        {
          label: "Tariff (BDT/kWh)",
          data: tariffData,
          borderColor: "#a855f7",
          borderWidth: 1.5,
          borderDash: [4, 4],
          fill: false,
          pointRadius: 2,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(51, 65, 85, 0.4)" }, ticks: { color: "#94a3b8" } },
        y: {
          grid: { color: "rgba(51, 65, 85, 0.4)" },
          ticks: { color: "#10b981" },
          title: { display: true, text: "Battery (kWh)", color: "#10b981" }
        },
        y1: {
          position: "right",
          grid: { display: false },
          ticks: { color: "#a855f7" },
          title: { display: true, text: "BDT/kWh", color: "#a855f7" }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// JSON Inspector
function renderJsonInspector() {
  const content = activeTab === "response" ? lastResponse : lastRequest;
  jsonInspector.textContent = content ? JSON.stringify(content, null, 2) : "// No data yet. Run an optimization to inspect.";
}

function showError(title, msg) {
  errorTitle.textContent = title;
  errorMessage.textContent = msg;
  errorAlert.style.display = "flex";
}

function hideError() {
  errorAlert.style.display = "none";
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Event Listeners
function setupEventListeners() {
  checkHealthBtn.addEventListener("click", checkHealth);

  loadSampleBtn.addEventListener("click", () => {
    const idx = sampleSelect.value;
    if (idx === "" || !publicSamples[idx]) return;
    const sample = publicSamples[idx];
    currentScenario = JSON.parse(JSON.stringify(sample.input));
    renderInputs();
    hideError();
  });

  addNoteBtn.addEventListener("click", () => {
    if (currentScenario.operator_notes.length < 3) {
      currentScenario.operator_notes.push("");
      renderNotes();
    }
  });

  notesContainer.addEventListener("click", (e) => {
    if (e.target.classList.contains("delete-note-btn")) {
      const idx = parseInt(e.target.getAttribute("data-index"), 10);
      if (currentScenario.operator_notes.length > 1) {
        currentScenario.operator_notes.splice(idx, 1);
        renderNotes();
      }
    }
  });

  notesContainer.addEventListener("input", (e) => {
    if (e.target.classList.contains("note-input")) {
      const idx = parseInt(e.target.getAttribute("data-index"), 10);
      currentScenario.operator_notes[idx] = e.target.value;
    }
  });

  optimizeBtn.addEventListener("click", runOptimization);

  tabResponse.addEventListener("click", () => {
    activeTab = "response";
    tabResponse.classList.add("active");
    tabRequest.classList.remove("active");
    renderJsonInspector();
  });

  tabRequest.addEventListener("click", () => {
    activeTab = "request";
    tabRequest.classList.add("active");
    tabResponse.classList.remove("active");
    renderJsonInspector();
  });

  copyJsonBtn.addEventListener("click", () => {
    const text = jsonInspector.textContent;
    navigator.clipboard.writeText(text).then(() => {
      copyJsonBtn.textContent = "Copied!";
      setTimeout(() => (copyJsonBtn.textContent = "Copy JSON"), 2000);
    });
  });

  downloadJsonBtn.addEventListener("click", () => {
    const text = jsonInspector.textContent;
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gridwise_${activeTab}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

window.addEventListener("DOMContentLoaded", init);
