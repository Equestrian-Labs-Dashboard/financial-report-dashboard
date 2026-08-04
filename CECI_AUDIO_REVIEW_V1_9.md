# Ceci audio review — v1.9

## Implemented in the model

- 2026 ecommerce closing forecast uses actual Shopify YTD plus the remaining months multiplied by the editable monthly run rate.
- Organic Growth is zero in the 2026 revenue build and starts affecting 2027.
- Current CAC reads from Stats as Spend / Purchases. Forecast CAC is an editable assumption seeded from the latest actual instead of being recalculated with total forecast orders.
- Current Returning Customers % and Revenue Carryover % remain separate: customers vs revenue.
- Carryover affects the next-year ecommerce base once.
- Ecommerce, Concierge, Wellington and Cavali GM1 use channel-specific actuals. Forecast GM1 starts from each channel's actual GM1 and remains editable.
- Concierge and Wellington forecasts no longer start with obviously unrealistic values such as 12 orders/clients when the current channel is already materially larger.
- Cavali current members, boxes/year, prices, orders and GM1 feed from connected actuals; forecasts remain editable and save by scenario.
- Markup 2026 seeds from the actual product/sku calculation.
- Inventory Turns 2026 seeds from SKU Savvy actuals; later years remain editable targets.
- Embroidery launch is calculated as Funding Date + 3 months.
- Private Label launch is calculated as Funding Date + 15 months.
- Sales & Marketing remains flat at $210k / $300k / $300k / $300k; Advertising is not duplicated inside S&M.
- G&A remains a fixed operating assumption and does not grow automatically with revenue.
- Every editable cell is saved in the active scenario and recalculates Tabs 1–4.
- Refresh Actuals updates baseline/current values and does not overwrite saved forecast inputs.

## Still pending external sources or management confirmation

- Shipping cost actuals: ShipStation or QuickBooks.
- Packaging actuals: QuickBooks or a manual operating source.
- Shipping revenue actuals: Shopify mapping confirmation.
- Opening cash actual: QuickBooks/bank source. The current value remains editable.
- Booking Amount and Booking Discount actuals.
- Final management targets for Embroidery, Private Label and future Cavali members/boxes.
- QuickBooks integration and account mapping from Phase 3.
- Purchase Operating System and Payables dashboard are separate next-step projects and are not part of Tabs 1–4.
