# ⚡ GridWise LLM — Frontend

> **AI-Powered Smart Grid Energy Optimization Interface**

GridWise LLM is an intelligent energy optimization platform that transforms natural-language operator instructions into structured energy constraints and generates an optimized 24-hour energy schedule.

The frontend provides a professional dashboard for interacting with the GridWise optimization engine, visualizing energy flows, reviewing AI interpretations, inspecting constraints, and validating the final schedule.

> [!NOTE]
> **Architecture & Judging Boundary:**
> This frontend is an optional demonstration dashboard designed for presentations, rehearsals, and video recordings. It is **never** required by the organizer evaluation harness or on the judged API path (`GET /health` and `POST /optimize-energy`). The browser never interprets operator notes or calculates schedules; all optimization, guardrail validation, and replay verification are executed strictly by the backend HTTP service.

---

## 🚀 Overview

GridWise LLM connects **Natural Language → LLM Interpretation → Deterministic Guardrails → Optimization → Replay Validation** into a single interactive interface.

Operators can provide instructions such as:

* Reduce solar output during a specific time window
* Maintain a minimum battery reserve
* Prevent battery charging during a maintenance period
* Prevent battery discharge during a protection window
* Limit grid import during peak hours
* Ignore irrelevant operational notes

The frontend sends these instructions to the backend optimization API and presents the resulting schedule in an easy-to-understand dashboard.

---

## ✨ Key Features

### 🤖 Natural Language Energy Control

Operators can enter energy-related instructions using normal language instead of manually configuring complex parameters.

Example:

> "Battery charging is prohibited from 2 PM until 4 PM."

GridWise interprets the instruction and converts it into a structured directive.

---

### 🧠 AI Directive Interpretation

The interface displays how the operator's natural-language instructions were interpreted.

Supported directive types include:

| Directive                 | Description                                        |
| ------------------------- | -------------------------------------------------- |
| `solar_reduction`         | Reduces usable solar generation for selected hours |
| `minimum_battery_reserve` | Maintains a minimum battery energy level           |
| `no_charge_window`        | Prevents battery charging during selected hours    |
| `no_discharge_window`     | Prevents battery discharge during selected hours   |
| `max_grid_window`         | Limits grid import during selected hours           |
| `no_op`                   | Marks irrelevant instructions as non-operational   |

---

### ⚙️ 24-Hour Energy Optimization

The dashboard visualizes the optimized energy plan across all 24 hours.

The schedule includes:

* Solar generation
* Load demand
* Grid import
* Battery charging
* Battery discharging
* Battery energy / state
* Hourly energy flow
* Peak grid usage
* Total operating cost

---

### 📊 Interactive Energy Visualization

The dashboard provides visual representations of the optimized schedule so operators can quickly understand:

* Solar utilization
* Grid dependency
* Battery behavior
* Load demand
* Peak usage
* Energy flow throughout the day

---

### 🛡️ Schedule Validation

GridWise includes deterministic validation after optimization.

The frontend communicates the validation status clearly so users can distinguish between:

**Optimized Schedule**

and

**Verified Schedule**

The validation process checks the generated plan against the system's operational constraints and energy-balance requirements.

---

### 🔒 Constraint Visibility

Applied constraints are presented separately so users can understand exactly which operator instructions affected the optimization.

For example:

```text
Applied Constraints

✓ Solar reduced to 70%
  Hours: 13–14

✓ Minimum battery reserve: 80 kWh
  Hours: 19–20

✓ Charging disabled
  Hours: 14–15
```

---

### 🧪 Public Sample Cases

The frontend supports the official GridWise sample cases, allowing users to quickly load predefined scenarios and test the optimizer.

This makes the interface useful for:

* Demonstrations
* Testing
* Hackathon presentations
* Regression testing
* Evaluating optimization behavior

---

### 🔍 Raw JSON Inspector

For technical users and developers, the frontend provides access to the raw API response.

This makes it easier to inspect:

* Directive interpretations
* Optimization results
* Hourly schedules
* Validation information
* Backend response structure

---

## 🏗️ Architecture

```text
┌─────────────────────────────┐
│       Operator / User       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       GridWise Frontend     │
│                             │
│  • Operator Notes           │
│  • Sample Cases             │
│  • Energy Dashboard         │
│  • Charts                   │
│  • Schedule Table           │
│  • Validation Status        │
└──────────────┬──────────────┘
               │ HTTP API
               ▼
┌─────────────────────────────┐
│       GridWise Backend      │
│                             │
│     LLM Interpretation      │
│             ↓               │
│     Guardrail Validation    │
│             ↓               │
│        Compilation          │
│             ↓               │
│       Optimization          │
│             ↓               │
│       Replay Validation     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      Optimized 24h Plan     │
└─────────────────────────────┘
```

---

## 🔄 Optimization Pipeline

GridWise follows a structured processing pipeline:

```text
Operator Notes
      ↓
LLM Interpretation
      ↓
Structured Directives
      ↓
Deterministic Guardrails
      ↓
Directive Compilation
      ↓
Energy Optimization
      ↓
Replay Validation
      ↓
Verified 24-Hour Schedule
```

This architecture separates natural-language interpretation from deterministic energy optimization.

---

## 🖥️ Frontend Technology

The frontend is intentionally lightweight and does not require a large frontend framework.

### Core Technologies

* **HTML5**
* **CSS3**
* **JavaScript (ES6+)**
* **Fetch API**
* **Chart-based data visualization**
* **Responsive UI**
* **REST API integration**

The frontend is designed to remain simple, fast, and easy to deploy.

---

## 📁 Project Structure

```text
frontend/
│
├── index.html
├── app.js
├── styles.css
├── sample_cases.json
└── README.md
```

### File Responsibilities

#### `index.html`

Contains the main dashboard structure and UI components.

#### `styles.css`

Handles:

* Layout
* Responsive design
* Dashboard styling
* Cards
* Tables
* Charts
* Dark/light visual elements
* Status indicators
* Responsive behavior

#### `app.js`

Responsible for:

* API communication
* Form handling
* Input validation
* Sample case loading
* Directive rendering
* Optimization result rendering
* Chart updates
* Schedule visualization
* Validation status handling

#### `sample_cases.json`

Contains predefined GridWise sample scenarios used for testing and demonstration.

---

## 🔌 Backend API

The frontend communicates with the GridWise backend through REST APIs.

### Health Check

```http
GET /health
```

Used to verify that the backend service is available.

---

### Optimize Energy

```http
POST /optimize-energy
```

The frontend sends the energy scenario and operator instructions to the backend.

A typical workflow is:

```text
Frontend
   │
   │ POST /optimize-energy
   ▼
Backend
   │
   ├── Interpret operator notes
   ├── Validate directives
   ├── Compile constraints
   ├── Optimize energy schedule
   └── Replay / validate result
   │
   ▼
Frontend
   │
   ├── Display interpretation
   ├── Display constraints
   ├── Display KPIs
   ├── Display charts
   └── Display 24h schedule
```

---

## 📋 Supported Operator Directives

### ☀️ Solar Reduction

Reduces usable solar generation for a specified time window.

Example:

```text
Rooftop PV production will be cut by 30%
between 1 PM and 3 PM.
```

Interpretation:

```json
{
  "directive_type": "solar_reduction",
  "hours": [13, 14],
  "factor": 0.7
}
```

---

### 🔋 Minimum Battery Reserve

Maintains a minimum amount of energy in the battery.

Example:

```text
Keep no less than 120 kWh stored in the battery
from 6 PM until 9 PM.
```

---

### 🚫 No Charge Window

Prevents battery charging during a specified time window.

Example:

```text
Battery charging is prohibited from 2 PM until 4 PM.
```

---

### 🚫 No Discharge Window

Prevents battery discharge during a specified time window.

Example:

```text
Battery discharge is prohibited from 6 PM until 8 PM.
```

---

### ⚡ Maximum Grid Import

Limits grid import during a specified time window.

Example:

```text
The evening transformer can accept no more than
90 kWh of grid import from 7 PM until 9 PM.
```

---

### ➖ No Operation

Irrelevant operator instructions can be interpreted as:

```json
{
  "directive_type": "no_op",
  "applies": false
}
```

This allows the system to safely ignore unrelated notes.

---

## 📊 Dashboard Output

After optimization, the frontend presents several key metrics.

### Energy Metrics

* Total energy cost
* Total grid import
* Total solar utilization
* Peak grid usage
* Battery activity
* Optimization status

### Hourly Schedule

Each hour contains the relevant energy values and battery state.

```text
Hour | Load | Solar | Grid | Charge | Discharge | Battery
-----|------|-------|------|--------|-----------|--------
00   | ...  | ...   | ...  | ...    | ...       | ...
01   | ...  | ...   | ...  | ...    | ...       | ...
...
23   | ...  | ...   | ...  | ...    | ...       | ...
```

---

## 🛡️ Validation & Reliability

GridWise does not rely only on the LLM for correctness.

The architecture separates:

```text
LLM
 ↓
Interpretation
 ↓
Deterministic Validation
 ↓
Optimization
 ↓
Independent Replay Validation
```

This helps prevent natural-language interpretation errors from directly becoming invalid energy schedules.

The system validates important properties such as:

* 24 unique hourly entries
* Valid hour range `0–23`
* Non-negative energy values
* Battery capacity constraints
* Battery reserve constraints
* Charge/discharge rate limits
* Solar availability limits
* Grid limits
* Energy balance
* Initial/final battery consistency
* Hourly and total cost consistency

---

## 🧪 Testing

The frontend is part of a larger GridWise test environment.

From the project root:

```bash
python3 scripts/run_tests.py
```

The test suite covers areas including:

* API behavior
* Optimization
* Compiler behavior
* Replay validation
* Guardrails
* Schemas
* Provider contracts
* Concurrency
* Frontend assets
* LLM paraphrase handling
* Startup/configuration

Official public sample cases can be executed using:

```bash
python3 scripts/run_public_samples.py
```

---

## ▶️ Running the Frontend Locally

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd smart-grid-llm-optimizer-main
```

### 2. Start the backend

Follow the backend setup instructions in the root project README.

The backend should expose:

```text
/health
/optimize-energy
```

### 3. Open the frontend

The frontend can be served using a simple local HTTP server.

For example:

```bash
cd frontend
python3 -m http.server 8080
```

Then open:

```text
http://localhost:8080
```

---

## 🔧 Configuration

The frontend needs to communicate with the running backend API.

Make sure the API endpoint configured in `app.js` matches your backend environment.

For local development, it may look like:

```text
http://localhost:8000
```

Use the actual backend port configured in your project.

---

## 📱 Responsive Design

The interface is designed to work across:

* 💻 Desktop
* 🖥️ Large displays
* 📱 Mobile devices
* 📟 Tablet screens

The dashboard prioritizes readability of energy metrics, charts, constraints, and hourly schedules across different screen sizes.

---

## 🎯 Design Goals

The frontend focuses on five major principles:

### 1. Clarity

Complex optimization results should be understandable to non-technical operators.

### 2. Transparency

Users should be able to see how their natural-language instructions were interpreted.

### 3. Reliability

Optimization results should communicate whether the final schedule passed validation.

### 4. Usability

Common scenarios should be testable quickly through sample cases.

### 5. Technical Visibility

Developers and judges should be able to inspect structured JSON responses when needed.

---

## 🏆 Hackathon Demonstration Flow

A recommended demonstration flow is:

```text
1. Open GridWise Dashboard
        ↓
2. Select a sample energy scenario
        ↓
3. Enter operator instructions
        ↓
4. Run Optimization
        ↓
5. Show AI Directive Interpretation
        ↓
6. Show Applied Constraints
        ↓
7. Show Optimization KPIs
        ↓
8. Show Energy Flow Charts
        ↓
9. Show 24-Hour Schedule
        ↓
10. Show Replay Validation
```

This demonstrates the complete journey from **human instruction to verified energy schedule**.

---

## 🌐 Project Components

GridWise LLM consists of multiple components:

```text
GridWise LLM
│
├── Frontend
│   ├── Dashboard
│   ├── Operator Interface
│   ├── Charts
│   ├── Schedule Viewer
│   └── Validation UI
│
├── Backend
│   ├── API
│   ├── LLM Interpreter
│   ├── Guardrails
│   ├── Compiler
│   ├── Optimizer
│   └── Replay Validator
│
├── Tests
│   ├── Unit Tests
│   ├── API Tests
│   ├── Guardrail Tests
│   ├── Replay Tests
│   └── LLM Paraphrase Tests
│
└── Test Fixtures
    └── Public Sample Cases
```

---

## 👥 Team

**GridWise LLM**

Built for the **BUP CSE Fest 2026 Preliminary Round**.

---

## 📄 License

This project is developed as part of a hackathon/academic project.

Refer to the repository's root-level license and project documentation for applicable terms.

---

## ⚡ GridWise LLM

**Natural Language → Intelligent Constraints → Optimized Energy → Verified Schedule**

> Making smart-grid optimization more accessible through natural-language interaction and deterministic validation.

