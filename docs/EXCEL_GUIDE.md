# My Excel reporting exercise

I use this workbook to demonstrate traceable calculations, source controls, operational planning, and a separate native PivotTable exercise.

Open `reports/Maple_Merch_Reporting.xlsx` in Excel. The six sheets contain the original synthetic snapshot. The workbook was calculated and rendered during creation, its headline results reconciled with SQL, and a changed source price was verified to flow into the report. It was not opened in Microsoft Excel in this environment.

## What to demonstrate

| Sheet | What it demonstrates |
| --- | --- |
| Review | Date controls, SUMIFS, COUNTIFS, net AOV, session conversion, margins, two editable charts, and an independent SQL control |
| Inventory | VLOOKUP, seven-day demand, supplier lead time, an editable buffer, ROUNDUP/MAX, IF, and conditional risk formatting |
| Lines | Original numeric sales inputs plus editable gross/refund/net/COGS calculations and product lookups |
| Orders | Unique paid-order records and SQL financial control totals; cancellations are excluded |
| Traffic | Session counts at a consistent date/channel grain |
| Products | SKU master, catalog prices, lead times, statuses, and current stock |

Change Review B4 and D4 to change the selected reporting period. The daily chart always shows the **30 days ending on D4**, as labelled, even if you choose a different summary start date. Keep the controls inside the sample coverage, August 28 through October 26, 2026. Inventory's stock snapshot is fixed as of October 26; it uses its own as-of cell B4.

The amber Inventory D4 cell controls the planning buffer. Changing it updates order suggestions and risk statuses. A resizable Excel Table supplies each recurring source range.

## Create the native PivotTable

The delivered workbook contains a native Excel Table named **SalesLines**, but it does **not** already contain a PivotTable. Complete this step before claiming that part of the project is finished.

1. Click anywhere inside the data on Lines.
2. Choose **Insert → PivotTable → From Table/Range**. Confirm the source is `SalesLines` and use a new worksheet.
3. Put **Category** in Rows, **Channel** in Columns, and **Net sales** in Values.
4. In Value Field Settings choose **Sum** and set a CAD currency number format with two decimals.
5. Put **Report period** in Filters and select **Selected**. This is important: SalesLines contains 60 days, while the default Review selects 30 days.
6. Rename the worksheet **Channel Pivot**. The grand total should be **CAD $36,246.60** for the original default period.
7. Change the Review date controls, recalculate, and **Refresh** the PivotTable. Confirm its total agrees with Review B8.

If your Excel account exposes **Automate → New Script**, paste `scripts/create_excel_pivot.ts` and run it instead of the manual creation steps. Office Scripts availability depends on your Excel account; it is optional. The script has not been executed here and does not require enabling VBA macros.

## Trace a calculation

1. Select one paid line and trace Quantity × Unit price → Gross sales → Discount and Refund → Net sales.
2. Explain why returned units have the original allocated discount applied to the refund.
3. Trace net sales into Review's SUMIFS result. Paid-order counts come from the unique Orders table, so an order with three products is counted once.
4. Review B17 compares Excel line calculations with the independently exported SQL total. It should be **CAD $0.00** in the baseline. This is a terminal check, not a control used to alter results.
5. If you deliberately change an input, a nonzero control difference is expected until the source controls are refreshed. Restore your test edits before presenting the baseline.

## Refresh from current local data

The app does not silently change an open XLSX. Use **Reports & handoff → Excel refresh inputs**, or run `python app.py export`. The generated files are `excel_lines.csv`, `excel_orders.csv`, `excel_traffic.csv`, and `excel_products.csv` in `reports/`.

These four refresh files contain the **full current history**, not only the selected 30-day sales report, and currency values are in CAD dollars. Other operational CSV exports use integer cents and are not direct replacements for these workbook inputs.

Work in a copy of the workbook:

1. Open/import each refresh CSV in Excel. Parse its Date column as a real date. `=ISNUMBER(A2)` should return TRUE for a CSV's imported date. If it is text, use **Data → Text to Columns**, choose Date/YMD, and finish. Do not paste date strings into the report and assume the date filters will work.
2. On each target sheet, use **Table Design → Resize Table** to include exactly the new data rows, starting at row 6 for the header. If there are N records, the last row is N + 6. Keep the table's existing name. Clear obsolete source values if the new extract is shorter.
3. On **Lines**, paste values from the refresh file's **A:D** into A7 onward and **G:K** into G7 onward. Keep the workbook's formulas in E:F and L:R. Fill those formula columns down through every newly added row, using their existing first data-row formulas as the pattern. Product names and categories come from the Products lookup.
4. On **Orders**, replace data values in A:L. On **Traffic**, replace A:F. On **Products**, replace A:I. All three files match the workbook's column order. Keep their header row and table names. The local app has a fixed 16-SKU master; adding new SKUs would also require expanding product lookup ranges and the Inventory schedule.
5. Recalculate with **F9**, then refresh the PivotTable. The summary formulas use table column references so resized Lines, Orders, and Traffic tables flow through to the report.
6. Compare Review B8 with the app's matching period, paid orders with the dashboard count, and B17 with zero. Spot-check the new `DEMO-...` order and a product's received stock.

Keep raw source inputs and formula columns separate. Import into a new workbook or sheet first if you are unsure; do not overwrite the report's calculations with a flat CSV.
