# Strategic Operating Model v1.8 Validation

## Correction

- 2026 Growth Engine cells no longer remain blank after actuals refresh.
- Ecommerce, Concierge, Wellington and Cavali seed 2026 from current connected actuals.
- Seeding only fills blank/uninitialized cells; values explicitly edited and saved by the user remain unchanged.
- Cavali 2026 members seed from Smartrr current active members.
- A new storage namespace prevents stale v1.7 browser data from restoring blank 2026 values.

## Checks executed

- `node --check assets/js/app.js`
- `node --check assets/js/dataService.js`
- `node tests-model.mjs`
- `node tests-integration-static.mjs`
- JSON validation for `data/assumptions.json`
