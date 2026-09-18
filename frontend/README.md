# GridWise Demonstration Dashboard (Frontend)

An interactive, responsive demonstration dashboard for the **GridWise** smart campus energy management system.

> [!NOTE]
> **Architecture & Judging Boundary:**
> This frontend is an optional demonstration dashboard designed for presentations, rehearsals, and video recordings. It is **never** required by the organizer evaluation harness or on the judged API path (`GET /health` and `POST /optimize-energy`). The browser never interprets operator notes or calculates schedules; all optimization, guardrail validation, and replay verification are executed strictly by the backend HTTP service.

---

## 1. Features

- **Dynamic Backend Base URL Configuration:** Easily switch between `http://127.0.0.1:8000`, remote deployments, or staging environments.
- **Readiness Health Probe Indicator:** Real-time polling and status display (`Online`, `Offline`, `Checking`).
- **Official Public Sample Loader:** Load any of the 10 official public sample scenarios directly from `docs/BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`.
- **Interactive Scenario & Constraint Inputs:**
  - Dynamic 1–3 operator note inputs with add/remove controls.
  - Complete battery parameter controls (capacity, initial energy, reserve, charge/discharge rates).
  - 24-hour tabular editor for hourly demand, solar generation, and tariffs.
- **Rich Visualization & Diagnostics:**
  - **KPI Cards:** Total cost (BDT), total grid import (kWh), and peak feeder load (kWh).
  - **Directive Cards:** Displays interpreted note index, applicability (`APPLIES` vs `NO-OP`), directive type, and structured adjustments.
  - **Dual Synchronized Charts:**
    - Stacked energy supply (Solar + Grid + Battery Discharge) vs. Demand line.
    - Battery stored energy progression vs. Time-of-use tariff.
  - **Emitted Plan Table:** Complete 24-hour breakdown with color-coded actions (`charge`, `discharge`, `idle`).
- **Raw JSON Inspector:** Complete request and response inspector with syntax formatting, one-click copy, and file download controls.
- **Safe Error Presentation:** Surfaces structured backend error envelopes (`400`, `422`, `500`) and network issues gracefully without crashing.

---

## 2. Technology Stack

- **HTML5 & Vanilla Modern JavaScript (ES6+):** Zero compilation steps, maximum portability, lightweight and fast.
- **Responsive Modern CSS:** CSS grid/flexbox, custom properties (CSS variables), dark-mode palette.
- **Chart.js (v4.4.1):** High-performance canvas-based multi-axis charting.

---

## 3. Quick Start & Serving

You can serve the frontend using any static web server or Python's built-in HTTP server:

```bash
# From the project root:
cd frontend
python3 -m http.server 3000
```

Then open your browser at:
```text
http://localhost:3000
```

Ensure the GridWise backend is running at `http://127.0.0.1:8000`:
```bash
# Start backend service
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 4. Verification & Testing

To verify the dashboard offline against simulated backend responses or live against the local backend:
1. Open the dashboard in a browser.
2. Click **Check Health** to verify backend connectivity (status indicator will turn green).
3. Select **SAMPLE-01** from the sample selector dropdown and click **Load**.
4. Click **Run Energy Optimization**.
5. Observe the KPIs (`38,365.00 BDT`), charts, directive cards, and hourly plan matching the official public test suite.

