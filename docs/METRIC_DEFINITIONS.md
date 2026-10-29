# My data and metric definitions

I define the measures below explicitly so I can explain how my dashboard, SQL calculations, and Excel report reconcile.

All currency calculations in SQLite use integer Canadian cents. XLSX inputs use numeric Canadian dollars and round refunds to cents. The fixed sample date is October 26, 2026.

| Metric | Definition |
| --- | --- |
| Gross merchandise sales | Ordered quantity × original unit selling price, for paid orders |
| Discounts | Line-level merchandise reductions allocated at purchase |
| Merchandise refunds | (Gross − discount) × returned units / ordered units, rounded to cents per line |
| Net merchandise sales | Gross − discounts − merchandise refunds |
| Net AOV | Net merchandise sales / distinct paid orders, including orders later partially returned |
| COGS | (Ordered − returned units) × original unit cost; assumes returns are resalable |
| Gross profit | Net merchandise sales − COGS |
| Gross margin | Gross profit / net merchandise sales; unavailable when the denominator is zero |
| Conversion | Purchasing sessions / sessions, using session-start cohorts |
| Cart/checkout funnel | Distinct sessions reaching each step; repeated clicks do not create additional sessions |
| Replenishment | Max(0, ceiling(seven-day gross unit demand / 7 × (supplier lead days + 7 buffer days)) − available stock) |
| Days cover | Current available stock / daily seven-day demand; unavailable with zero observed demand |
| Fulfillment exception | Paid, unshipped order on hold or older than 48 hours at the fixed demo clock |
| VIP | Consented profile with at least CAD $500 lifetime net merchandise sales |
| Win-back | Consented, non-VIP profile whose last paid order is more than 30 days old |
| Repeat | Consented profile with at least two paid orders, after higher-priority segments |
| Welcome | Remaining consented profiles |
| Suppressed | No affirmative email consent or no consent timestamp; overrides all spend/recency segments |

Tax and shipping are stored separately and excluded from merchandise metrics. Seeded tax is zero and is not a Canadian tax model. The local checkout omits tax/shipping entirely. No card information is collected.

Cancelled orders do not enter any sales view, demand calculation, or customer order count. Draft products appear in operations but cannot be purchased. Stock is an as-of snapshot; the project does not reconstruct historical inventory or claim an inventory-turnover measure.

Refunds are attributed to the original purchase date. This is an order-cohort trading analysis, not an accounting close or a report of refunds by the cash transaction date. An operating-cost or paid-media table would be required for net profit or ROAS; neither is inferred from the existing records.

The GA4 adapter deliberately names `ecommerce_purchase_events`. GA4's ecommercePurchases metric counts purchase events. It is not substituted for distinct purchasing sessions. Real GA4 and commerce exports can differ because of consent, ad blockers, timezone, attribution, refunds, and tagging. Stage and reconcile them before merging.

The inventory rule is a transparent heuristic. Seven days of demand can be distorted by promotions, new launches, returns, or previous stockouts. Incoming POs, safety-stock variability, minimum order quantities and warehouse reservations are outside the model.

Cart reminders require affirmative consent, a prior-day cart, no conversion on that cart, and no later paid order. This is a demonstration of suppression logic; it does not send a campaign or replace platform subscription status. The example timestamps make the baseline wait exceed 24 hours.
