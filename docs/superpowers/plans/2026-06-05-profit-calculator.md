# Profit Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a database-backed Amazon profit calculator page.

**Architecture:** Calculation rules live in a pure Python service, API routes save input/result snapshots to a dedicated table, and the Vanilla JS SPA calls the API and renders the returned calculation. Trial calculations remain separate from `profit_daily`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vanilla JS, CSS.

---

## File Structure

- Create `app/analysis/profit_calculator.py`: pure calculation logic and validation-friendly helper functions.
- Modify `app/db/models.py`: add `ProfitCalculation` table.
- Modify `app/routes/analysis.py`: add Pydantic request models and `/api/profit/*` endpoints.
- Modify `app/static/index.html`: add navigation entry and profit calculator page markup.
- Modify `app/static/app.js`: add endpoint, page title, initialization, submit handler, and render helpers.
- Modify `app/static/styles.css`: add profit calculator layout and responsive rules.
- Modify `tests/test_api.py`: add API and frontend presence tests.

---

### Task 1: Backend API And Persistence

**Files:**
- Create: `app/analysis/profit_calculator.py`
- Modify: `app/db/models.py`
- Modify: `app/routes/analysis.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests for successful calculation save, invalid input rejection, and recent calculation listing.

- [ ] **Step 2: Run failing API tests**

Run: `pytest tests/test_api.py::test_profit_calculation_endpoint_saves_snapshot tests/test_api.py::test_profit_calculation_endpoint_rejects_invalid_payload tests/test_api.py::test_profit_calculations_endpoint_lists_recent_snapshots -q`

Expected: fail because the endpoints do not exist.

- [ ] **Step 3: Implement model and calculator**

Add `ProfitCalculation` with `product_name`, `sku`, `marketplace`, `input_data`, `result_data`, and `created_at`. Add a calculator that returns unit profit, margin, ROI, monthly profit, break-even units, FBA tier, cost breakdown, health, and advice.

- [ ] **Step 4: Implement routes**

Add `/api/profit/calculate` to validate, calculate, save, and return a snapshot. Add `/api/profit/calculations` to return recent snapshots.

- [ ] **Step 5: Run API tests**

Run the same pytest command and expect PASS.

---

### Task 2: Frontend Page

**Files:**
- Modify: `tests/test_api.py`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`

- [ ] **Step 1: Write failing frontend presence test**

Assert the dashboard contains `page-profit-calculator`, `利润核算`, `profit-product-name`, and `保存核算`.

- [ ] **Step 2: Run failing frontend test**

Run: `pytest tests/test_api.py::test_frontend_dashboard_contains_profit_calculator_entry -q`

Expected: fail because the page is missing.

- [ ] **Step 3: Add markup and JS**

Add sidebar entry, page markup, endpoint wiring, input serialization, submit handling, and result rendering.

- [ ] **Step 4: Add CSS**

Add responsive calculator layout, input cards, result cards, breakdown list, and history list.

- [ ] **Step 5: Run frontend test**

Run the same pytest command and expect PASS.

---

### Task 3: Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

Run: `pytest tests/test_api.py -q`

Expected: PASS.

- [ ] **Step 2: Run broader tests if feasible**

Run: `pytest -q`

Expected: PASS or report any unrelated pre-existing failure.

- [ ] **Step 3: Browser check**

Start the FastAPI app on an available local port and verify the profit calculator page visually in the in-app browser.
