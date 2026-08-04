# Strategic Operating Model v2.1 — Cecilia Corrections

## Implemented

- Ecommerce 2027–2029 management forecast restored: Orders 1,600 / 2,500 / 3,000; AOV $210 / $230 / $250; GM1 32.5% / 35.5% / 38.5%.
- CAC current is calculated from Marketing Stats as Spend / Purchases, with New Customers used only as an identified fallback. Forecast CAC cells seed from the numeric current actual and remain editable.
- Added an English CAC source note below Acquisition Strategy instead of placing explanatory text inside numeric cells.
- Returning Customers % remains customer-based.
- Revenue Carryover % current is returning revenue / total customer revenue; 2026 seeds from that actual and carryover is applied once to the following-year base.
- Purchase Frequency current and 2026 seed from Shopify orders / unique customers.
- Added an English retention source/formula note below Retention Strategy.
- Smartrr Cavali member parsing now de-duplicates aggregate/detail rows by plan/variant and does not copy the largest value into every field.
- Cavali 2026 seeds from current actuals only. 2027–2029 stay editable and are never overwritten by Refresh Actuals.
- Refresh Actuals never replaces saved forecast inputs.
- Browser storage moved to som_assumptions_v210 to prevent old invalid text values such as "Actuals" and "Calculated from Stats" from returning in numeric cells.
- Visible model version updated to v2.1.

## Validation executed

- JavaScript syntax: PASS
- assumptions.json: PASS
- financial model test: PASS
- static integration and persistence checks: PASS
- fake placeholder check: PASS

## Data-source limitation

The bundled connected_actuals.json is only a deployment placeholder. Final live values are generated in GitHub Actions using the repository Secrets and private Shopify/Google Sheets/Smartrr sources.
