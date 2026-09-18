/**
 * GridWise Executive Operations Interface - Dashboard Application
 * Complies strictly with the organizer HTTP API contract:
 * - Direct HTTP calls to GET /health and POST /optimize-energy
 * - Zero client-side heuristic scheduling or directive interpretation
 * - Pure presentation and accessible interaction
 */

// Application State
let publicSamples = [];
let currentScenario = {
  scenario_id: "CAMPUS-MICROGRID-01",
  operator_notes: ["The battery charging circuit will be disconnected between 2 PM and 4 PM."],
  hours: generateCampusProfile(),
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
let activeTab = "response";

// DOM References
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
const presetFlatBtn = document.getElementById("presetFlatBtn");
const presetPeakBtn = document.getElementById("presetPeakBtn");
const presetZeroBtn = document.getElementById("presetZeroBtn");
const worstCaseBtn = document.getElementById("worstCaseBtn");

const optimizeBtn = document.getElementById("optimizeBtn");
const errorAlert = document.getElementById("errorAlert");
const errorTitle = document.getElementById("errorTitle");
const errorMessage = document.getElementById("errorMessage");
const errorActions = document.getElementById("errorActions");
const quickSwitchOfflineBtn = document.getElementById("quickSwitchOfflineBtn");
const errorOpenSettingsBtn = document.getElementById("errorOpenSettingsBtn");

const kpiCost = document.getElementById("kpiCost");
const kpiGrid = document.getElementById("kpiGrid");
const kpiPeak = document.getElementById("kpiPeak");
const planSummaryText = document.getElementById("planSummaryText");
const directivesList = document.getElementById("directivesList");
const resultsTableBody = document.getElementById("resultsTableBody");

const tabResponse = document.getElementById("tabResponse");
const tabRequest = document.getElementById("tabRequest");
const copyJsonBtn = document.getElementById("copyJsonBtn");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");
const jsonInspector = document.getElementById("jsonInspector");

// Mobile Segmented Tab References
const tabNavScenario = document.getElementById("tabNavScenario");
const tabNavResults = document.getElementById("tabNavResults");
const scenarioView = document.getElementById("scenarioView");
const resultsView = document.getElementById("resultsView");

// Authentication & Portal DOM References
const loginView = document.getElementById("loginView");
const loginForm = document.getElementById("loginForm");
const loginEmail = document.getElementById("loginEmail");
const loginPassword = document.getElementById("loginPassword");
const loginRole = document.getElementById("loginRole");
const toggleLoginPasswordBtn = document.getElementById("toggleLoginPasswordBtn");
const loginErrorMsg = document.getElementById("loginErrorMsg");
const quickJudgeLoginBtn = document.getElementById("quickJudgeLoginBtn");
const appHeader = document.getElementById("appHeader");
const mobileNavTabs = document.getElementById("mobileNavTabs");
const mainContent = document.getElementById("mainContent");
const userProfileBadge = document.getElementById("userProfileBadge");
const userRoleDisplay = document.getElementById("userRoleDisplay");
const logoutBtn = document.getElementById("logoutBtn");

function getAuthUser() {
  try {
    const session = sessionStorage.getItem("gridwise_auth_user") || localStorage.getItem("gridwise_auth_user");
    if (session) return JSON.parse(session);
  } catch (e) {}
  return null;
}

function setAuthUser(user) {
  try {
    sessionStorage.setItem("gridwise_auth_user", JSON.stringify(user));
  } catch (e) {}
}

function clearAuthUser() {
  try {
    sessionStorage.removeItem("gridwise_auth_user");
    localStorage.removeItem("gridwise_auth_user");
  } catch (e) {}
}

function applyAuthState() {
  const user = getAuthUser();
  if (user) {
    if (loginView) loginView.style.display = "none";
    if (appHeader) appHeader.style.display = "flex";
    if (mobileNavTabs) mobileNavTabs.style.display = "";
    if (mainContent) mainContent.style.display = "";
    if (userProfileBadge) userProfileBadge.style.display = "flex";
    if (userRoleDisplay) userRoleDisplay.textContent = user.roleShort || "Judge";
  } else {
    if (loginView) loginView.style.display = "flex";
    if (appHeader) appHeader.style.display = "none";
    if (mobileNavTabs) mobileNavTabs.style.display = "none";
    if (mainContent) mainContent.style.display = "none";
    if (userProfileBadge) userProfileBadge.style.display = "none";
  }
}

function handleLogin(email, password, role) {
  if (!email || !password) {
    if (loginErrorMsg) {
      loginErrorMsg.textContent = "Please enter both operator email and passcode.";
      loginErrorMsg.style.display = "block";
    }
    return false;
  }

  const roleText = role || "Lead Hackathon Judge";
  const shortRole = roleText.includes("Judge") ? "Judge" : roleText.includes("Chief") ? "Chief" : "Auditor";
  const userObj = {
    email: email.trim(),
    role: roleText,
    roleShort: shortRole,
    loginTime: new Date().toISOString()
  };

  setAuthUser(userObj);
  if (loginErrorMsg) loginErrorMsg.style.display = "none";
  applyAuthState();
  checkHealth();
  return true;
}

// Theme Toggle Management
const themeToggleBtn = document.getElementById("themeToggleBtn");
const themeIcon = document.getElementById("themeIcon");
const themeLabel = document.getElementById("themeLabel");

function initTheme() {
  const savedTheme = localStorage.getItem("gridwise_theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const currentTheme = savedTheme || (prefersDark ? "dark" : "light");
  applyTheme(currentTheme, false);
}

function applyTheme(theme, redrawCharts = true) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("gridwise_theme", theme);
  if (themeIcon) themeIcon.textContent = theme === "dark" ? "🌙" : "☀️";
  if (themeLabel) themeLabel.textContent = theme === "dark" ? "Dark" : "Light";
  if (redrawCharts && (energyChart || batteryChart) && lastResponse && lastRequest) {
    renderCharts(lastResponse, lastRequest);
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const target = current === "dark" ? "light" : "dark";
  applyTheme(target, true);
}

// Settings Modal References & State
const settingsModal = document.getElementById("settingsModal");
const settingsToggleBtn = document.getElementById("settingsToggleBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const cfgLlmProvider = document.getElementById("cfgLlmProvider");
const cfgGeminiKey = document.getElementById("cfgGeminiKey");
const toggleKeyVisibilityBtn = document.getElementById("toggleKeyVisibilityBtn");
const cfgGeminiModel = document.getElementById("cfgGeminiModel");
const cfgSolverTimeout = document.getElementById("cfgSolverTimeout");
const cfgRequestTimeout = document.getElementById("cfgRequestTimeout");
const cfgCurrency = document.getElementById("cfgCurrency");
const cfgThemeSelect = document.getElementById("cfgThemeSelect");
const cfgServerEndpoint = document.getElementById("cfgServerEndpoint");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const resetSettingsBtn = document.getElementById("resetSettingsBtn");
const settingsStatusMsg = document.getElementById("settingsStatusMsg");

const DEFAULT_SETTINGS = {
  llm_provider: "gemini",
  gemini_key: "",
  gemini_model: "gemini-2.5-flash",
  solver_timeout: 5.0,
  request_timeout: 30.0,
  currency: "BDT",
  theme: "dark"
};

function getStoredSettings() {
  try {
    const saved = localStorage.getItem("gridwise_config");
    if (saved) return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
  } catch (e) {}
  return { ...DEFAULT_SETTINGS };
}

function saveStoredSettings(cfg) {
  localStorage.setItem("gridwise_config", JSON.stringify(cfg));
}

function openSettingsModal() {
  const cfg = getStoredSettings();
  if (cfgLlmProvider) cfgLlmProvider.value = cfg.llm_provider;
  if (cfgGeminiKey) cfgGeminiKey.value = cfg.gemini_key;
  if (cfgGeminiModel) cfgGeminiModel.value = cfg.gemini_model;
  if (cfgSolverTimeout) cfgSolverTimeout.value = cfg.solver_timeout;
  if (cfgRequestTimeout) cfgRequestTimeout.value = cfg.request_timeout;
  if (cfgCurrency) cfgCurrency.value = cfg.currency;
  if (cfgThemeSelect) cfgThemeSelect.value = document.documentElement.getAttribute("data-theme") || cfg.theme;
  if (cfgServerEndpoint) cfgServerEndpoint.value = apiBaseInput ? apiBaseInput.value : "";
  if (settingsModal) settingsModal.style.display = "flex";
}

function closeSettingsModal() {
  if (settingsModal) settingsModal.style.display = "none";
}

function switchMobileView(viewName) {
  if (viewName === "scenarioView") {
    if (tabNavScenario) tabNavScenario.classList.add("active");
    if (tabNavResults) tabNavResults.classList.remove("active");
    if (scenarioView) scenarioView.classList.add("view-active");
    if (resultsView) resultsView.classList.remove("view-active");
  } else {
    if (tabNavResults) tabNavResults.classList.add("active");
    if (tabNavScenario) tabNavScenario.classList.remove("active");
    if (resultsView) resultsView.classList.add("view-active");
    if (scenarioView) scenarioView.classList.remove("view-active");
    // Ensure charts resize accurately when switching to results tab
    requestAnimationFrame(() => {
      if (energyChart) energyChart.resize();
      if (batteryChart) batteryChart.resize();
    });
  }
}

// Helpers for Profiles
function generateCampusProfile() {
  return Array.from({ length: 24 }, (_, h) => {
    // Normal campus load curve
    const demand = (40 + (h >= 8 && h <= 18 ? 80 + Math.sin((h - 8) / 10 * Math.PI) * 60 : 15)).toFixed(1) * 1;
    // Solar peak around midday
    const solar = (h >= 7 && h <= 17 ? Math.sin((h - 7) / 10 * Math.PI) * 75 : 0).toFixed(1) * 1;
    // Time-of-use tariff structure
    const tariff = (h < 6 || h >= 22 ? 8.0 : (h >= 17 && h <= 21 ? 18.0 : 12.0));
    return { hour: h, demand_kwh: demand, solar_kwh: solar, tariff_bdt_per_kwh: tariff };
  });
}

function generateFlatProfile() {
  return Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    demand_kwh: 60.0,
    solar_kwh: (h >= 8 && h <= 16 ? 40.0 : 0.0),
    tariff_bdt_per_kwh: 12.0
  }));
}

function generateZeroProfile() {
  return Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    demand_kwh: 0.0,
    solar_kwh: 0.0,
    tariff_bdt_per_kwh: 10.0
  }));
}

function generateWorstCaseProfile() {
  return Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    demand_kwh: 350.0, // High demand
    solar_kwh: 0.0,   // Zero generation (cloudy/night)
    tariff_bdt_per_kwh: (h >= 17 && h <= 22 ? 22.0 : 14.0)
  }));
}

// Lifecycle Init
async function init() {
  initTheme();
  applyAuthState();
  if (apiBaseInput && window.location.protocol.startsWith("http")) {
    if (window.location.port !== "3000") {
      apiBaseInput.value = window.location.origin;
    }
  }
  await loadPublicSamples();
  renderInputs();
  if (getAuthUser()) {
    checkHealth();
  }
  setupEventListeners();
}

// Data Fetching
async function loadPublicSamples() {
  try {
    const res = await fetch("sample_cases.json");
    if (res.ok) {
      publicSamples = await res.json();
      sampleSelect.innerHTML = `<option value="">-- Load Reference Scenario --</option>`;
      publicSamples.forEach((sample, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${sample.id}: ${sample.label}`;
        sampleSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn("Could not load sample_cases.json:", err);
  }
}

function getApiBase() {
  let url = apiBaseInput ? apiBaseInput.value.trim() : "";
  if (!url && window.location.protocol.startsWith("http")) {
    url = window.location.origin;
  }
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
      statusText.textContent = `Status ${res.status}`;
    }
  } catch (err) {
    statusDot.className = "status-dot offline";
    statusText.textContent = "Offline / Connection Refused";
  }
}

// UI Rendering
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
      <span class="note-index-pill" aria-label="Note index ${idx}">#${idx}</span>
      <input type="text" class="form-control note-input" data-index="${idx}" value="${escapeHtml(note)}" placeholder="Enter operator directive or constraint..." aria-label="Operator note text" />
      <button class="btn-icon delete-note-btn" data-index="${idx}" aria-label="Remove note" ${currentScenario.operator_notes.length <= 1 ? "disabled" : ""}>✕</button>
    `;
    notesContainer.appendChild(row);
  });

  addNoteBtn.disabled = currentScenario.operator_notes.length >= 3;
}

function renderHoursTable() {
  hoursTableBody.innerHTML = "";
  currentScenario.hours.forEach((h) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="text-align:center; font-weight:600; color:var(--text-secondary);">${h.hour}</td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-demand" data-hour="${h.hour}" value="${h.demand_kwh}" aria-label="Hour ${h.hour} demand" /></td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-solar" data-hour="${h.hour}" value="${h.solar_kwh}" aria-label="Hour ${h.hour} solar" /></td>
      <td><input type="number" step="0.1" min="0" class="table-input hr-tariff" data-hour="${h.hour}" value="${h.tariff_bdt_per_kwh}" aria-label="Hour ${h.hour} tariff" /></td>
    `;
    hoursTableBody.appendChild(tr);
  });
}

// Request Payload Construction
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
    scenario_id: scenarioIdInput.value.trim() || "SCENARIO-01",
    operator_notes: notes,
    hours: hours,
    battery: battery
  };
}

// Submit Optimization
async function runOptimization() {
  hideError();
  const base = getApiBase();
  const payload = buildRequestPayload();
  lastRequest = payload;

  if (activeTab === "request") {
    renderJsonInspector();
  }

  optimizeBtn.disabled = true;
  optimizeBtn.innerHTML = `<span class="inline-spinner"></span> Computing...`;

  try {
    const cfg = getStoredSettings();
    const reqHeaders = { "Content-Type": "application/json" };
    if (cfg.gemini_key && cfg.llm_provider === "gemini") {
      reqHeaders["X-Gemini-API-Key"] = cfg.gemini_key;
    }
    if (cfg.llm_provider) {
      reqHeaders["X-LLM-Provider"] = cfg.llm_provider;
    }
    if (cfg.gemini_model) {
      reqHeaders["X-Gemini-Model"] = cfg.gemini_model;
    }

    const res = await fetch(`${base}/optimize-energy`, {
      method: "POST",
      headers: reqHeaders,
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    lastResponse = data;

    if (!res.ok) {
      showError(
        `Backend Error HTTP ${res.status}: ${data?.error?.code || "DISPATCH_ERROR"}`,
        data?.error?.message || JSON.stringify(data)
      );
      renderJsonInspector();
      return;
    }

    renderResults(data);
  } catch (err) {
    showError("Network / Server Unavailable", `Failed to communicate with ${base}/optimize-energy: ${err.message}`);
    lastResponse = { error: { code: "NETWORK_ERROR", message: err.message } };
  } finally {
    optimizeBtn.disabled = false;
    optimizeBtn.innerHTML = `Compute Optimal Dispatch`;
    renderJsonInspector();
  }
}

// Results Presentation
function renderResults(data) {
  // Auto-switch to results view on mobile/webview
  switchMobileView("resultsView");

  // KPIs
  kpiCost.textContent = Number(data.total_cost_bdt).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  kpiGrid.textContent = Number(data.total_grid_kwh).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  kpiPeak.textContent = Number(data.peak_grid_kwh).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  planSummaryText.textContent = data.plan_summary || "24-hour cost-optimal schedule computed and replayed successfully.";

  // Directives
  directivesList.innerHTML = "";
  if (data.directive_interpretation && data.directive_interpretation.length > 0) {
    data.directive_interpretation.forEach(d => {
      const tile = document.createElement("div");
      tile.className = `directive-tile ${d.applies ? "" : "noop"}`;
      tile.innerHTML = `
        <div class="directive-meta">
          <span class="directive-name">[Note #${d.note_index}] ${d.directive_type}</span>
          <span class="badge-tag ${d.applies ? "badge-applies" : "badge-noop"}">${d.applies ? "ACTIVE" : "NO-OP"}</span>
        </div>
        <div class="directive-body">${escapeHtml(d.explanation || "")}</div>
        ${d.structured_adjustment ? `<div class="directive-spec">${escapeHtml(JSON.stringify(d.structured_adjustment))}</div>` : ""}
      `;
      directivesList.appendChild(tile);
    });
  } else {
    directivesList.innerHTML = `<div style="color:var(--text-tertiary); font-size:0.75rem;">No directives interpreted.</div>`;
  }

  // Hourly plan table
  resultsTableBody.innerHTML = "";
  if (data.hourly_plan) {
    data.hourly_plan.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="text-align:center; font-weight:600; color:var(--text-secondary);">${item.hour}</td>
        <td>${Number(item.grid_kwh).toFixed(2)}</td>
        <td>${Number(item.solar_used_kwh).toFixed(2)}</td>
        <td><span class="action-pill ${item.battery_action}">${item.battery_action}</span></td>
        <td>${Number(item.battery_kwh).toFixed(2)}</td>
        <td>${Number(item.battery_energy_after_kwh).toFixed(2)}</td>
      `;
      resultsTableBody.appendChild(tr);
    });
  }

  // Visual Multi-Axis Charts
  renderCharts(data, lastRequest);
}

// Chart Visualization
function renderCharts(response, request) {
  const hours = response.hourly_plan.map(p => `H${p.hour}`);
  const gridData = response.hourly_plan.map(p => p.grid_kwh);
  const solarUsedData = response.hourly_plan.map(p => p.solar_used_kwh);
  const batteryFlow = response.hourly_plan.map(p => (p.battery_action === "discharge" ? p.battery_kwh : 0));
  const demandData = request.hours.map(h => h.demand_kwh);
  const batteryEnergy = response.hourly_plan.map(p => p.battery_energy_after_kwh);
  const tariffData = request.hours.map(h => h.tariff_bdt_per_kwh);

  const compStyle = getComputedStyle(document.documentElement);
  const gridColor = compStyle.getPropertyValue("--chart-grid").trim() || "rgba(31, 41, 61, 0.5)";
  const tickColor = compStyle.getPropertyValue("--chart-tick").trim() || "#64748b";

  if (energyChart) energyChart.destroy();
  if (batteryChart) batteryChart.destroy();

  const ctxEnergy = document.getElementById("energyChart").getContext("2d");
  energyChart = new Chart(ctxEnergy, {
    type: "bar",
    data: {
      labels: hours,
      datasets: [
        {
          label: "Solar Used",
          data: solarUsedData,
          backgroundColor: "rgba(6, 182, 212, 0.8)",
          stack: "Supply"
        },
        {
          label: "Grid Import",
          data: gridData,
          backgroundColor: "rgba(59, 130, 246, 0.8)",
          stack: "Supply"
        },
        {
          label: "Battery Discharge",
          data: batteryFlow,
          backgroundColor: "rgba(245, 158, 11, 0.8)",
          stack: "Supply"
        },
        {
          label: "Demand",
          data: demandData,
          type: "line",
          borderColor: "#ef4444",
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
        x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 } } },
        y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 } }, title: { display: true, text: "kWh", color: tickColor, font: { size: 10 } } }
      },
      plugins: { legend: { display: false } }
    }
  });

  const ctxBattery = document.getElementById("batteryChart").getContext("2d");
  batteryChart = new Chart(ctxBattery, {
    type: "line",
    data: {
      labels: hours,
      datasets: [
        {
          label: "Battery Energy",
          data: batteryEnergy,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          borderWidth: 2,
          fill: true,
          pointRadius: 2.5,
          yAxisID: "y"
        },
        {
          label: "Tariff",
          data: tariffData,
          borderColor: "#8b5cf6",
          borderWidth: 1.5,
          borderDash: [3, 3],
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
        x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 } } },
        y: {
          grid: { color: gridColor },
          ticks: { color: "#10b981", font: { size: 10 } },
          title: { display: true, text: "Battery kWh", color: "#10b981", font: { size: 10 } }
        },
        y1: {
          position: "right",
          grid: { display: false },
          ticks: { color: "#8b5cf6", font: { size: 10 } },
          title: { display: true, text: "BDT/kWh", color: "#8b5cf6", font: { size: 10 } }
        }
      },
      plugins: { legend: { display: false } }
    }
  });
}

// JSON Inspector & Diagnostics
function renderJsonInspector() {
  const content = activeTab === "response" ? lastResponse : lastRequest;
  jsonInspector.textContent = content ? JSON.stringify(content, null, 2) : "// Awaiting scenario execution...";
}

function showError(title, msg) {
  errorTitle.textContent = title;
  errorMessage.textContent = msg;
  errorAlert.style.display = "flex";
  
  const isLlmIssue = /MODEL_INTERPRETATION_ERROR|Gemini|API connection|nodename nor servname|timed out|TimeoutError|404|429|LLM/i.test(title + " " + msg);
  if (errorActions) {
    errorActions.style.display = isLlmIssue ? "flex" : "none";
  }

  switchMobileView("scenarioView");
  errorAlert.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideError() {
  errorAlert.style.display = "none";
  if (errorActions) {
    errorActions.style.display = "none";
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Event Bindings
function setupEventListeners() {
  if (tabNavScenario) {
    tabNavScenario.addEventListener("click", () => switchMobileView("scenarioView"));
  }
  if (tabNavResults) {
    tabNavResults.addEventListener("click", () => switchMobileView("resultsView"));
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", toggleTheme);
  }

  if (checkHealthBtn) {
    checkHealthBtn.addEventListener("click", checkHealth);
  }

  loadSampleBtn.addEventListener("click", () => {
    const idx = sampleSelect.value;
    if (idx === "" || !publicSamples[idx]) return;
    const sample = publicSamples[idx];
    currentScenario = JSON.parse(JSON.stringify(sample.input));
    renderInputs();
    hideError();
  });

  presetFlatBtn.addEventListener("click", () => {
    currentScenario.hours = generateFlatProfile();
    renderHoursTable();
  });

  presetPeakBtn.addEventListener("click", () => {
    currentScenario.hours = generateCampusProfile();
    renderHoursTable();
  });

  presetZeroBtn.addEventListener("click", () => {
    currentScenario.hours = generateZeroProfile();
    renderHoursTable();
  });

  worstCaseBtn.addEventListener("click", () => {
    currentScenario.hours = generateWorstCaseProfile();
    currentScenario.operator_notes = [
      "The charging circuit will be unavailable from 2 PM until 6 PM.",
      "The feeder is operating under a 200 kWh transformer limit from 6 PM to 10 PM."
    ];
    currentScenario.battery.max_charge_kwh_per_hour = 30.0;
    currentScenario.battery.max_discharge_kwh_per_hour = 30.0;
    renderInputs();
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
    tabResponse.setAttribute("aria-selected", "true");
    tabRequest.classList.remove("active");
    tabRequest.setAttribute("aria-selected", "false");
    renderJsonInspector();
  });

  tabRequest.addEventListener("click", () => {
    activeTab = "request";
    tabRequest.classList.add("active");
    tabRequest.setAttribute("aria-selected", "true");
    tabResponse.classList.remove("active");
    tabResponse.setAttribute("aria-selected", "false");
    renderJsonInspector();
  });

  copyJsonBtn.addEventListener("click", () => {
    const text = jsonInspector.textContent;
    navigator.clipboard.writeText(text).then(() => {
      copyJsonBtn.textContent = "Copied!";
      setTimeout(() => (copyJsonBtn.textContent = "Copy"), 2000);
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

  // Settings Modal Listeners
  if (settingsToggleBtn) settingsToggleBtn.addEventListener("click", openSettingsModal);
  if (closeSettingsBtn) closeSettingsBtn.addEventListener("click", closeSettingsModal);
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) closeSettingsModal();
    });
  }

  if (toggleKeyVisibilityBtn && cfgGeminiKey) {
    toggleKeyVisibilityBtn.addEventListener("click", () => {
      const isPassword = cfgGeminiKey.type === "password";
      cfgGeminiKey.type = isPassword ? "text" : "password";
      toggleKeyVisibilityBtn.textContent = isPassword ? "Hide" : "Show";
    });
  }

  // Modal tab switching
  document.querySelectorAll(".modal-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      document.querySelectorAll(".modal-tab-btn").forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".modal-tab-pane").forEach(pane => {
        pane.style.display = "none";
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.style.display = "flex";
    });
  });

  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener("click", () => {
      const newCfg = {
        llm_provider: cfgLlmProvider ? cfgLlmProvider.value : "gemini",
        gemini_key: cfgGeminiKey ? cfgGeminiKey.value.trim() : "",
        gemini_model: cfgGeminiModel ? cfgGeminiModel.value : "gemini-2.5-flash",
        solver_timeout: parseFloat(cfgSolverTimeout ? cfgSolverTimeout.value : 5.0) || 5.0,
        request_timeout: parseFloat(cfgRequestTimeout ? cfgRequestTimeout.value : 30.0) || 30.0,
        currency: cfgCurrency ? cfgCurrency.value : "BDT",
        theme: cfgThemeSelect ? cfgThemeSelect.value : "dark"
      };
      saveStoredSettings(newCfg);
      if (cfgThemeSelect) applyTheme(newCfg.theme, true);
      if (cfgServerEndpoint && cfgServerEndpoint.value.trim() && apiBaseInput) {
        apiBaseInput.value = cfgServerEndpoint.value.trim();
        checkHealth();
      }
      if (settingsStatusMsg) {
        settingsStatusMsg.textContent = "Saved!";
        settingsStatusMsg.style.display = "inline";
        setTimeout(() => { settingsStatusMsg.style.display = "none"; }, 2000);
      }
    });
  }

  if (resetSettingsBtn) {
    resetSettingsBtn.addEventListener("click", () => {
      localStorage.removeItem("gridwise_config");
      openSettingsModal();
      if (settingsStatusMsg) {
        settingsStatusMsg.textContent = "Reset to defaults";
        settingsStatusMsg.style.display = "inline";
        setTimeout(() => {
          settingsStatusMsg.style.display = "none";
          settingsStatusMsg.textContent = "Saved!";
        }, 2000);
      }
    });
  }

  // Quick actions from error alert
  if (quickSwitchOfflineBtn) {
    quickSwitchOfflineBtn.addEventListener("click", () => {
      const cfg = getStoredSettings();
      cfg.llm_provider = "fake";
      saveStoredSettings(cfg);
      if (cfgLlmProvider) cfgLlmProvider.value = "fake";
      hideError();
      runOptimization();
    });
  }

  if (errorOpenSettingsBtn) {
    errorOpenSettingsBtn.addEventListener("click", () => {
      openSettingsModal();
    });
  }

  // Authentication Event Bindings
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      handleLogin(loginEmail.value, loginPassword.value);
    });
  }

  if (quickJudgeLoginBtn) {
    quickJudgeLoginBtn.addEventListener("click", () => {
      if (loginEmail) loginEmail.value = "judge@bup.edu.bd";
      if (loginPassword) loginPassword.value = "gridwise2026";
      handleLogin("judge@bup.edu.bd", "gridwise2026");
    });
  }

  if (toggleLoginPasswordBtn && loginPassword) {
    toggleLoginPasswordBtn.addEventListener("click", () => {
      const isPass = loginPassword.type === "password";
      loginPassword.type = isPass ? "text" : "password";
      toggleLoginPasswordBtn.textContent = isPass ? "Hide" : "Show";
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearAuthUser();
      applyAuthState();
    });
  }

  // Auto-load reference scenario when selected from dropdown
  if (sampleSelect) {
    sampleSelect.addEventListener("change", () => {
      const idx = sampleSelect.value;
      if (idx !== "" && publicSamples[idx]) {
        currentScenario = JSON.parse(JSON.stringify(publicSamples[idx].input));
        renderInputs();
        hideError();
      }
    });
  }
}

window.addEventListener("DOMContentLoaded", init);
