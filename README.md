# Maple Merch Ops

I built Maple Merch Ops as my end-to-end retail e-commerce operations portfolio project. I wanted to connect my retail and inventory experience with practical analytics, merchandising, launch coordination, and customer workflows. I scoped the project against the **Analyst, Retail E-Commerce, Tim Hortons, Canada** role at Restaurant Brands International.

My scenario is a fictional Canadian coffee merchandise shop. I connected its shopping journey, catalog, inventory, fulfillment, launches, creative approvals, and reporting in one local application. I use synthetic data and original illustrative assets throughout. This is my independent portfolio project, with no affiliation to RBI or Tim Hortons.

## Run my project on Windows

1. Clone this repository or download and extract its ZIP.
2. Install Python 3.10 or newer if it is not already installed. Python is free: https://www.python.org/downloads/. Select **Add Python to PATH** during installation.
3. Double-click **start-windows.bat**. Leave its terminal window open.
4. Open **http://127.0.0.1:8765** in your browser.
5. Use **Open demo shop** or go to **http://127.0.0.1:8765/shop**.

There is no pip install, API key, credit card, or paid service required to run the core project. A modern browser and Python are enough. The Excel file can be inspected separately in an application that supports XLSX; native Excel features need Excel.

On macOS/Linux, open a terminal in this folder and run:

```bash
python3 app.py
```

If port 8765 is occupied, run `python app.py --port 8766` and use the port shown in the terminal. On Windows, `py -3 app.py --port 8766` also works.

## What I implemented

- **Shop → cart → checkout → orders → inventory → analytics.** I connected a synthetic checkout to SQLite, stock deduction, and current reports. I apply promotions on the server and do not collect or charge payment.
- **Catalog operations.** I added listing edits, approved-price checks, imagery and alt-text validation, atomic CSV imports, version checks, and change history.
- **Inventory and fulfillment.** I built stockout and replenishment views, stock receipts, an unshipped-order queue, and recorded team handoffs.
- **Launch coordination.** I implemented owners, due dates, dependency checks, sample receipt, creative approval, and gated publication to my local shop.
- **Creative library.** I included original illustrations and a workflow for samples, shoot dates, usage rights, approval, image replacement, and primary-asset selection.
- **Analytics.** I calculate sales, discounts, returns, paid orders, net AOV, gross profit, channel/product performance, and a session funnel with explicit denominators.
- **CRM preparation.** I added value/recency segments, consent suppression, cart-reminder eligibility, local email previews, and exports.
- **Reporting.** I included CSV/JSON exports, an operating-review generator, and a six-sheet Excel pack with editable formulas, tables, charts, and PivotTable setup instructions.

## What I still need to verify

My included XLSX has Excel Tables, formulas, and two editable charts. I still need to create and verify its native PivotTable in Excel using [my Excel guide](docs/EXCEL_GUIDE.md), or [my optional Office Script](scripts/create_excel_pivot.ts) if Office Scripts is available. I have not executed that script in Excel.

I have not connected a Shopify store, Google Analytics property, or Klaviyo account. I included read-only staged extract adapters, a Shopify draft product CSV, and a local CRM payload preview. I tested the adapter contracts with mocks; live account authentication, permissions, behavior, and email delivery remain unverified. I keep the account exercises in [my platform guide](docs/PLATFORM_GUIDE.md) and keep live extracts separate from my synthetic dashboard.

I run my server locally on 127.0.0.1. I have not added production authentication, real payment processing, carrier integration, or public hosting. Full rendered-browser, responsive-layout, keyboard, and browser-policy checks also remain outstanding; my JavaScript/API contract tests do not replace those checks.

## How I demonstrate the project

I follow [my demonstration walkthrough](docs/DEMO_WALKTHROUGH.md) to explain trading results, correct listings, receive stock, place a synthetic order, complete launch prerequisites, replace an asset, and review CRM consent. It records the exact products, tasks, fields, and expected changes.

I generated a baseline of **16 SKUs, 180 synthetic profiles, and 60 days of activity ending October 26, 2026**. I keep the demo clock fixed so exception ages and launch deadlines remain reproducible. Audit log timestamps use the actual UTC time. My default 30-day report contains CAD $36,246.60 in synthetic net merchandise sales across 538 paid orders; these are scenario values, not real company results or claimed business improvements.

## My project structure

| Location | Purpose |
| --- | --- |
| `app.py` | One-command local launcher and report export CLI |
| `merchops/seed.py` | Reproducible sample records, CSV extracts, and original SVG illustrations |
| `sql/schema.sql` | Database constraints, indexes, and financial calculation views |
| `merchops/services.py` | Operations, validation, analytics, and transactional checkout |
| `merchops/server.py` | Local HTTP endpoints and static UI |
| `web/` | Operations workspace and demo storefront |
| `merchops/integrations.py` | Optional Shopify, GA4, and Klaviyo read-only adapters |
| `reports/Maple_Merch_Reporting.xlsx` | Excel demonstration snapshot |
| `reports/` | Baseline exports and current report outputs |
| `examples/` | Shopify draft product import, creative reshoot, and CRM payload preview |
| `tests/` | Python workflow, API, and integration contract tests |
| `docs/` | Requirements mapping, definitions, demo, platform, Excel, and interview guides |

## Useful commands

Run from the extracted project folder:

```bash
python app.py
python -m unittest discover -s tests -v
python app.py export
python -m merchops.integrations shopify-csv --output examples/Shopify_Products.csv
python -m merchops.integrations klaviyo-plan --output examples/Klaviyo_Profile_Preview.json
```

`python app.py export` refreshes CSV, JSON, and the manager review. It does not rebuild the included XLSX. Its snapshot needs the Excel refresh workflow described in the Excel guide.

To deliberately discard your local edits and demo orders, stop the server and run:

```bash
python app.py seed --reset
```

Only the specified project's local database is replaced. Restart the app afterward. Raw baseline CSV files and generated original illustrations are recreated when seeding; put your own source files elsewhere.

## My validation

I included **50 automated Python workflow, HTTP, and integration-contract tests**, plus a dependency-free JavaScript/HTTP contract driver covering seven workspace views and the listing-edit and checkout flows. I document the executed checks and remaining browser, Excel, and account validation in [my verification record](docs/VERIFICATION.md).

I keep credentials, live account exports, local databases, and generated cache files out of Git. My repository includes the complete application source, synthetic source data, baseline reports, workbook, and original project assets.

## Job source

[LinkedIn posting 4483176791](https://www.linkedin.com/jobs/view/4483176791/), reviewed October 26, 2026. See [docs/JOB_ALIGNMENT.md](docs/JOB_ALIGNMENT.md) for the project-to-role mapping.
