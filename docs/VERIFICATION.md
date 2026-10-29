# My verification record

I prepared the original verification record on October 26, 2026, and reran the executable project checks while preparing my GitHub repository on October 28, 2026. I use synthetic data for all executed checks; I have not accessed an employer or production account for this project.

## Story

An operator edits a product, a shopper places a synthetic order, and the project carries those actions through HTTP handlers into SQLite, canonical financial views, inventory, analytics, exports, and the refreshed JavaScript UI.

| Boundary | Executed result | Evidence and limit |
| --- | --- | --- |
| Core rules and API contracts | Passed | `python -m unittest discover -s tests -v`: **50 tests**, all passed |
| Static page/asset and report routes | Passed | HTTP 200 responses for the shop, workspace, scripts, CSS, data endpoints and the four Excel refresh inputs |
| Product edit to refreshed interface | Passed in a DOM contract driver | Actual JavaScript click handler and save callback → HTTP PATCH → SQLite → refreshed catalog HTML |
| Shop to order, stock and report | Passed in a DOM contract driver | Actual shop handlers → events/checkout API → unique order → stock reduction → dashboard sales increase by CAD $17.05 |
| All workspace views | Passed in a DOM contract driver | Seven views generated their content with real API data |
| Native XLSX structure | Passed | Six sheets, five Excel Tables, two editable charts, native formulas, validation and conditional formatting retained in the saved file |
| Workbook calculations | Passed in the authoring calculation engine | Headline metrics matched SQL; changing a source price changed report revenue; the restored file had no cached formula errors and a CAD $0.00 SQL control difference |
| Workbook visual review | Passed for rendered ranges | Each of the six sheets was rendered and visually inspected; the full source history remains in the file |
| Integration adapter behavior | Passed with mocked API responses | Pagination, metric naming, staged extracts, draft exports, suppression and restricted destination hosts tested without credentials |
| Actual browser rendering, CSP, keyboard and mobile behavior | **Not verified** | JavaScript syntax and DOM/API contracts were checked, but a usable browser engine was unavailable for a full rendered browser run |
| Microsoft Excel application behavior | **Not verified** | File opened through an XLSX reader, not Microsoft Excel. Native PivotTable creation and refresh must be checked in Excel |
| Shopify, GA4, Klaviyo account integration | **Not verified** | No store/property/account credentials or real API calls were used |

The DOM contract driver is a small test harness, not a browser emulator. It does not verify pixels, browser-enforced policy, file dialogs, focus, real downloads, or responsive layout. Those remaining checks are explicit below.

## Representative tested failures

- Two concurrent buyers cannot both purchase the final unit.
- Retrying checkout does not create another order or reduce stock again.
- A failed cart line rolls back the whole order.
- Draft and out-of-stock items are blocked from checkout.
- Invalid promotion codes and non-whole quantities are rejected.
- Stale product edits cannot overwrite newer stock changes.
- Invalid, duplicate-SKU, NaN, and unknown-SKU CSV imports do not partially commit.
- Launch tasks cannot skip their dependencies; task completion alone cannot clear unapproved creative.
- Sample/rights approval is required before a replacement becomes primary.
- Unconsented profiles stay suppressed regardless of spend.
- Cancelled orders stay out of financial reports; order counts do not multiply with line items.
- Date cutoffs, rounding, unique-order grain, and CAD-versus-cents refresh fields reconcile.

## Reproduce the executed checks

```bash
python -m unittest discover -s tests -v
python scripts/check_ui.py
```

The second command additionally requires Node 18+ and uses only Node built-ins. It runs a temporary local database and does not change your working database. The core application itself does not need Node.

## Before an interview demonstration

1. Open the workspace and shop in a real browser. Check desktop and narrow/mobile widths, all navigation, date filters and error states.
2. Tab through navigation and a dialog; confirm labels, close behavior and focus. Test a catalog file import and the supplied reshoot SVG upload.
3. Run the complete walkthrough. Download a CSV and the Excel pack, and verify the files open.
4. In Excel, test a changed date, a changed buffer, a refresh with a new demo order, and the native PivotTable exercise. Confirm the default baseline total first.
5. Complete any desired real-platform exercises in your own development accounts and record actual evidence separately.

I keep these checks open until I have performed them and recorded their results.
