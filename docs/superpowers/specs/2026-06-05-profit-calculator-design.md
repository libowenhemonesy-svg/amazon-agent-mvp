# Profit Calculator Design

## Goal

Add a profit calculator page that matches the reference layout and saves each calculation as an independent database snapshot.

## Scope

The feature uses option one: create a dedicated `profit_calculations` table. It does not write trial calculations into `profit_daily`, so estimated calculator snapshots stay separate from daily operating data.

## User Experience

The sidebar gets a new `利润核算` entry under AI tools. The page has a two-column layout: inputs on the left and computed results on the right. Users enter product name, SKU, sale price, landed cost, first-leg freight, referral rate, weight, dimensions, ad ACoS, return rate, expected monthly units, fixed monthly fee, and whether Q4 peak season applies. Clicking `保存核算` calls the backend and renders the saved result.

## Calculation Rules

The backend computes:

- Amazon referral fee: `sale_price * referral_rate`
- FBA fulfillment fee: a local estimate based on weight and volume tier
- Storage fee: monthly fixed fee divided by expected monthly units
- Advertising cost: `sale_price * ad_acos`
- Return cost: `sale_price * return_rate * 0.3`
- Unit profit: sale price minus all unit costs
- Margin: unit profit divided by sale price
- ROI: unit profit divided by landed cost plus first-leg freight
- Monthly profit: unit profit times expected monthly units, with a 1.3 multiplier for Q4
- Break-even units: monthly fixed fee divided by unit profit

The backend returns cost breakdown, health status, ROI, FBA tier, and short improvement advice.

## Backend

Create `app/analysis/profit_calculator.py` for pure calculation logic. Add `ProfitCalculation` to `app/db/models.py` with JSON columns for input and result snapshots. Add `/api/profit/calculate` and `/api/profit/calculations` in `app/routes/analysis.py`.

## Frontend

Update `app/static/index.html`, `app/static/app.js`, and `app/static/styles.css`. The page follows existing Vanilla JS patterns and existing card/button styling while using a green-accent result area like the reference.

## Testing

Add failing tests first in `tests/test_api.py`:

- dashboard contains the profit calculator entry and controls
- `/api/profit/calculate` saves and returns calculated profit data
- endpoint rejects missing product name or invalid numeric values
- `/api/profit/calculations` lists saved snapshots
