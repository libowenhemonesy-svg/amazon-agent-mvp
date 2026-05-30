# Sample Upload Files

Upload these files in this order through `http://127.0.0.1:8000/docs`:

1. `sku.csv` -> `POST /imports/sku`
2. `sales.csv` -> `POST /imports/sales`
3. `ads.csv` -> `POST /imports/ads`
4. `inventory.csv` -> `POST /imports/inventory`

Then run:

```text
POST /jobs/daily-run?run_date=2026-01-07
```

Check:

```text
GET /alerts?date=2026-01-07
GET /reports/daily?date=2026-01-07
GET /metrics/daily?date=2026-01-07
```
