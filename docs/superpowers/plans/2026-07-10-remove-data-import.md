# Remove Data Import Module Implementation Plan

> **For agentic workers:** Execute inline in this session. Do not create commits unless the user explicitly requests one.

**Goal:** Remove the data import UI and `/imports/*` API surface without deleting historical data or the parser used by demo loading.

**Architecture:** Remove the import router from application composition and delete its isolated route module. Remove the corresponding SPA page and its upload-only behavior, then adapt API tests to seed data through repositories instead of deleted HTTP endpoints.

**Tech Stack:** FastAPI, SQLAlchemy, Vanilla JavaScript, pytest.

## Global Constraints

- Preserve `app/importers/tabular.py`, sample-data loading, database tables, and existing records.
- Do not modify `.env`, delete databases, or commit Git changes.
- The removed `/imports/*` paths must return 404.

---

### Task 1: Remove the public import surface

**Files:**
- Modify: `app/main.py`
- Delete: `app/routes/imports.py`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`

**Interfaces:**
- Removes FastAPI route prefix `/imports`.
- Removes the SPA route target `page-imports` and nav item `data-page="imports"`.

- [ ] Add a failing API assertion that `POST /imports/sku` returns 404.
- [ ] Run the assertion and verify it fails while the router is registered.
- [ ] Remove the router import and `include_router` call; delete `app/routes/imports.py`.
- [ ] Remove only upload-page markup, upload-only JavaScript functions/event binding, and upload-only CSS selectors.
- [ ] Run the API assertion and verify it passes.

### Task 2: Preserve test data setup without import endpoints

**Files:**
- Modify: `tests/test_api.py`
- Keep: `tests/test_importers.py`

**Interfaces:**
- Test fixtures use `upsert_sku_rows` and `upsert_daily_rows` with the existing SQLAlchemy session factory.
- `app.importers.tabular.parse_tabular_upload` remains covered by `tests/test_importers.py`.

- [ ] Replace each deleted import-endpoint call used as setup with direct repository writes using the existing session factory.
- [ ] Run the affected daily-analysis and sales-monitor tests.
- [ ] Run the complete `tests/test_importers.py` and relevant `tests/test_api.py` subset.

### Verification

- [ ] Confirm no `page-imports`, `data-page="imports"`, `/imports/`, `uploadFile`, or `initDragAndDrop` production references remain.
- [ ] Start the app and verify `/imports/sku` returns 404 while `/` returns 200.
