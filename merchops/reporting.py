"""CSV and JSON outputs share the same SQL definitions as the dashboard."""
import csv
import io
import json
from pathlib import Path
from .db import DEFAULT_DB, ROOT, as_of, connect, rows
from .services import summary, product_performance, inventory, audits, launches, crm, fulfillment, csv_safe

def export_data(conn):
    return dict(as_of=as_of(conn),summary=summary(conn),
      orders=rows(conn,"SELECT * FROM order_sales ORDER BY placed_at"),
      lines=rows(conn,"SELECT s.*,p.title,p.category,p.collection FROM line_sales s JOIN products p ON p.sku=s.sku ORDER BY s.placed_at,s.id"),
      products=rows(conn,"SELECT * FROM products ORDER BY sku"),
      traffic=rows(conn,"""SELECT date,channel,SUM(sessions) sessions,SUM(cart_sessions) cart_sessions,
        SUM(checkout_sessions) checkout_sessions,SUM(purchase_sessions) purchase_sessions
        FROM (SELECT * FROM traffic UNION ALL SELECT substr(started_at,1,10),channel,1,cart,checkout,purchased FROM sessions)
        GROUP BY date,channel ORDER BY date,channel"""),
      inventory=inventory(conn),findings=audits(conn),launches=launches(conn),fulfillment=fulfillment(conn))

def csv_text(records,columns=None):
    out=io.StringIO()
    if columns is None: columns=list(records[0]) if records else []
    writer=csv.writer(out);writer.writerow(columns)
    writer.writerows([[csv_safe(r.get(c,"")) for c in columns] for r in records])
    return out.getvalue()

def report_csv(conn,kind="sales",start=None,end=None):
    if kind=="excel-lines":
        source=rows(conn,"SELECT s.*,p.title,p.category FROM line_sales s JOIN products p ON p.sku=s.sku ORDER BY s.placed_at,s.id")
        return csv_text([dict(zip(['Date','Order ID','Channel','SKU','Product','Category','Quantity','Returned','Unit price','Discount','Unit cost'],
          [r['date'],r['order_id'],r['channel'],r['sku'],r['title'],r['category'],r['quantity'],r['returned'],r['unit_price_cents']/100,r['discount_cents']/100,r['unit_cost_cents']/100])) for r in source])
    if kind=="excel-orders":
        source=rows(conn,"SELECT * FROM order_sales ORDER BY placed_at")
        return csv_text([dict(zip(['Date','Order ID','Channel','Customer ID','Gross sales','Discounts','Refunds','Net sales','COGS','Gross profit','Units','Returned'],
          [r['date'],r['order_id'],r['channel'],r['customer_id'],r['gross_cents']/100,r['discount_cents']/100,r['refund_cents']/100,r['net_cents']/100,r['cogs_cents']/100,(r['net_cents']-r['cogs_cents'])/100,r['units'],r['returns']])) for r in source])
    if kind=="excel-traffic":
        source=rows(conn,"""SELECT date,channel,SUM(sessions) sessions,SUM(cart_sessions) cart_sessions,SUM(checkout_sessions) checkout_sessions,SUM(purchase_sessions) purchase_sessions
          FROM (SELECT * FROM traffic UNION ALL SELECT substr(started_at,1,10),channel,1,cart,checkout,purchased FROM sessions)
          GROUP BY date,channel ORDER BY date,channel""")
        return csv_text([dict(zip(['Date','Channel','Sessions','Cart sessions','Checkout sessions','Purchasing sessions'],
          [r['date'],r['channel'],r['sessions'],r['cart_sessions'],r['checkout_sessions'],r['purchase_sessions']])) for r in source])
    if kind=="excel-products":
        source=rows(conn,"SELECT * FROM products ORDER BY sku")
        return csv_text([dict(zip(['SKU','Product','Category','Approved price','Lead days','Available','Status','Selling price','Compare-at price'],
          [r['sku'],r['title'],r['category'],r['expected_price_cents']/100,r['lead_days'],r['inventory'],r['status'],r['price_cents']/100,r['compare_at_cents']/100])) for r in source])
    if kind=="sales":
        result=summary(conn,start,end)
        return csv_text(rows(conn,"SELECT * FROM order_sales WHERE date BETWEEN ? AND ? ORDER BY placed_at",(result["start"],result["end"])))
    if kind=="lines":
        result=summary(conn,start,end)
        return csv_text(rows(conn,"SELECT s.date,s.order_id,s.channel,s.sku,p.title,p.category,s.quantity,s.returned,s.gross_cents,s.discount_cents,s.refund_cents,s.net_cents,s.cogs_cents FROM line_sales s JOIN products p ON p.sku=s.sku WHERE s.date BETWEEN ? AND ? ORDER BY s.placed_at,s.id",(result["start"],result["end"])))
    if kind=="products": return csv_text(product_performance(conn,start,end))
    if kind=="inventory": return csv_text(inventory(conn))
    if kind=="issues": return csv_text(audits(conn),["sku","title","kind","message","owner","severity"])
    if kind=="segments": return csv_text(crm(conn),["id","email","first_name","email_consent","consent_at","segment","lifetime_net_cents","orders","last_order","reminder_eligible"])
    raise ValueError("Unknown report type.")

def export_reports(path=DEFAULT_DB,destination=None):
    destination=Path(destination or ROOT/"reports")
    destination.mkdir(parents=True,exist_ok=True)
    with connect(path) as conn:
        data=export_data(conn)
        (destination/"report_data.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
        for kind in ("sales","lines","products","inventory","issues","segments","excel-lines","excel-orders","excel-traffic","excel-products"):
            (destination/f"{kind.replace('-','_')}.csv").write_text(report_csv(conn,kind),encoding="utf-8")
        (destination/"manager_brief.md").write_text(manager_brief(conn),encoding="utf-8")
    return destination

def manager_brief(conn):
    s=summary(conn);m=s["metrics"];inv=inventory(conn);qa=audits(conn);late=[o for o in fulfillment(conn) if o["issue"]!="Within SLA"]
    channels=sorted(s["channels"],key=lambda c:c["conversion"] or 0,reverse=True)
    top=channels[0] if channels else None
    dollars=lambda c:f"CAD ${c/100:,.2f}"
    lines=["# Weekly operating review",f"\nIndependent synthetic portfolio scenario. Data as of {s['as_of']}.\n",f"Reporting period: {s['start']} through {s['end']}.",
      f"\nNet merchandise sales are {dollars(m['net_cents'])} across {m['orders']:,} paid orders. Discounts and merchandise refunds are deducted. Tax and shipping are excluded.",
      f"\nGross profit is {dollars(m['gross_profit_cents'])}. This model assumes returned merchandise is resalable and reverses its original COGS. It excludes advertising, fulfillment and fixed operating costs.","\n## Actions"]
    for p in inv:
        if p["risk"] in ("Stockout","Reorder"):
            lines.append(f"- Planning & Inventory: {p['sku']} has {p['inventory']} units, {p['units_7d']} units of demand over seven days, and a suggested replenishment of {p['suggested_order']}. Confirm supplier capacity before placing a purchase order.")
    lines += [f"- E-Commerce and Category: resolve {len(qa)} listing/asset findings before the next launch.",f"- Supply Chain: investigate {len(late)} open orders on hold or older than 48 hours."]
    if top: lines.append(f"- Analytics: {top['channel']} has the highest observed conversion rate at {top['conversion']:.1%}. Check audience and product differences before reallocating spend. This comparison does not establish causality.")
    lines += ["\n## Launch handoff"]
    for l in launches(conn):
        lines.append(f"- {l['title']} ({l['target_date']}): {l['completion']}% of tasks complete. {len(l['blockers'])} prerequisites remain. Owner: {l['owner']}.")
    lines += ["\n## Definitions", "- Conversion = purchasing sessions / sessions, using the session-start cohort. Seeded traffic and local demo sessions are combined.","- Net AOV = net merchandise sales / paid orders, including paid orders later partially returned.","- Refunds are attributed to the original order date. This is an order-cohort analysis, not a cash-refund or accounting close report.","- Replenishment uses seven-day gross unit demand, supplier lead time and a seven-day buffer. It is a heuristic, not a validated forecast.","- All findings and amounts are synthetic. No business results or revenue improvements are claimed."]
    return "\n".join(lines)+"\n"
