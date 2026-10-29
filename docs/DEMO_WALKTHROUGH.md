# My demonstration walkthrough

I use the following sequence to demonstrate my project from the trading review through a synthetic order, launch approval, asset replacement, and CRM review.

Run `python app.py`, open http://127.0.0.1:8765, and keep the demo shop in another tab. Start from a fresh database for the expected baseline. This walkthrough uses synthetic data throughout.

## 1. Explain the trading picture (one minute)

Use Overview with September 27 through October 26, 2026 selected. The baseline reports:

| Metric | Baseline |
| --- | --- |
| Net merchandise sales | CAD $36,246.60 |
| Paid orders | 538 |
| Sessions | 22,555 |
| Purchasing sessions | 538 |
| Session conversion | 2.3853% |
| Gross profit before operating costs | CAD $22,199.60 |

The dashboard rounds its display. State that this is a synthetic case. Do not describe the figures as Tim Hortons results or personal business achievements.

Show channel and daily trends. Explain why an observed conversion difference is a question to investigate, rather than proof that one channel caused better performance.

## 2. Correct merchandising errors (one minute)

Open Product catalog:

1. Edit **TUM-001**. Set selling price to **32.95**, matching its approved merchandising price. Save. Its price finding disappears.
2. Edit **APP-003**. Add a useful description such as: `A comfortable cotton tee for everyday coffee runs. Wash cold with similar colours and hang to dry. Check the size guide before ordering.` Save.
3. Edit **HAT-001**. Add `Canvas coffee club cap shown from the front on a cream background` as alt text.
4. Edit **GFT-002**. Set compare-at price to **0.00**, or set it above its CAD $79.95 selling price if that comparison is justified in your scenario. Use 0.00 for this demo.

Show that the storefront receives saved values. The system refuses an invalid comparison price and protects against stale edits.

## 3. Resolve a stockout and hand it to the right owner (one minute)

Open Inventory & orders. **MUG-002** is out of stock.

1. Use Assign, choose Supply Chain, and record `Confirm the replenishment ETA and warehouse receipt for MUG-002.`
2. Use Receive. Enter **40** units and reference `DEMO-PO-1001 received and counted`.
3. Its availability updates and the stockout disappears. A Reorder status can remain if the seven-day demand and lead-time rule still calls for more units. Receiving stock does not automatically make a SKU healthy.
4. Mark one overdue synthetic order shipped. Show that it leaves the open fulfillment queue and appears in Change history.

## 4. Place a shop order and trace it through the system (one minute)

1. Open `/shop` and add **Everyday ceramic mug (MUG-001)** to your bag.
2. Open the bag and enter **MAPLE10**.
3. Place the demo order. One mug costs CAD $18.95 before promotion. A 10% discount rounds to CAD $1.90; net merchandise sales are CAD $17.05. No payment is charged.
4. Refresh the operations browser tab. Paid orders rise by one, sales rise by CAD $17.05, MUG-001 stock falls by one, and a local checkout appears in Change history.
5. The exported CSV now contains the order's `DEMO-...` ID. The included baseline XLSX stays unchanged until you follow the Excel refresh steps.

## 5. Prepare and publish the Winter Collection (two minutes)

1. Open Launch calendar and expand Winter Collection's prerequisites.
2. Mark **T02** complete. **T03** was dependent on it; complete T03, then T04, then T05 in order. T01 is already complete.
3. Publishing is still blocked because the beanie's asset has not been approved. This demonstrates that task completion alone does not clear asset requirements.
4. Open Creative assets and review **HOL-002**, asset **AST-016**. Set sample status to **Received**, rights to **Original demo illustration**, and creative approval to **Approved**. Save.
5. Return to Launch calendar and publish the collection to the **local demo shop**. Both Winter products change from draft to active. Refresh the shop and show the new collection.

## 6. Complete the asset replacement workflow (one minute)

The Cold brew glass cup, **TUM-002**, has a deliberately small primary image.

1. In Creative assets, choose Upload replacement SVG.
2. Select TUM-002 and open `examples/TUM-002-reshoot.svg` from the extracted project.
3. Review the newly uploaded item. Record `Original demo illustration` as rights and approve it. The upload defaults its synthetic sample status to Received.
4. Choose Use as primary. The low-resolution listing finding disappears. The old record stays in the library.

## 7. Show Excel and CRM evidence (one minute)

Open `reports/Maple_Merch_Reporting.xlsx`. Trace Review to Lines for revenue and to Orders for unique paid-order counts. Show VLOOKUP, SUMIFS, COUNTIFS, ROUND and inventory rules. Complete the native PivotTable exercise before presenting it as completed Excel evidence.

Open Customer & CRM. Show that profiles without consent are Suppressed even if they have high spend. Preview or download the local draft. No email is sent.

Finish by downloading the current manager review. Explain the issue, evidence, owner, next action, and remaining uncertainty for one recommendation.
