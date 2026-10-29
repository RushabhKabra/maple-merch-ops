/**
 * Optional Office Script for a native Excel PivotTable.
 * Paste into Excel > Automate > New Script, if Office Scripts is available.
 * Manual Insert > PivotTable works without this script; see docs/EXCEL_GUIDE.md.
 * Reviewed against Microsoft's documented API; not executed in Excel here.
 */
function main(workbook: ExcelScript.Workbook) {
  const source = workbook.getTable("SalesLines");
  if (!source) throw new Error("SalesLines table is missing. Open Maple_Merch_Reporting.xlsx.");
  const existing = workbook.getWorksheet("Channel Pivot");
  if (existing) throw new Error("Channel Pivot already exists. Delete it deliberately before recreating.");
  const sheet = workbook.addWorksheet("Channel Pivot");
  sheet.getRange("A2").setValue("Category and channel sales (CAD)");
  const pivot = sheet.addPivotTable("CategoryChannelSales", source, "A5");
  pivot.addRowHierarchy(pivot.getHierarchy("Category"));
  pivot.addColumnHierarchy(pivot.getHierarchy("Channel"));
  const net = pivot.addDataHierarchy(pivot.getHierarchy("Net sales"));
  net.setSummarizeBy(ExcelScript.AggregationFunction.sum);
  net.setName("Net merchandise sales (CAD)");
  const filter = pivot.addFilterHierarchy(pivot.getHierarchy("Report period"));
  filter.getFields()[0].applyFilter({manualFilter: {selectedItems: ["Selected"]}});
  sheet.getUsedRange().getFormat().autofitColumns();
  sheet.activate();
}
