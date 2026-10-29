import csv
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from merchops.db import connect, ROOT
from merchops.seed import seed
from merchops import services as s
from merchops.reporting import export_reports, report_csv
from merchops.server import make_server

class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'test.sqlite3';seed(self.db)
    def tearDown(self):self.tmp.cleanup()
    def product(self,sku='MUG-001'):
        with connect(self.db) as c:return dict(c.execute('SELECT * FROM products WHERE sku=?',(sku,)).fetchone())
    def order(self,sku='MUG-001',q=1,key='test-checkout-0001',sid='test-session-0001',**extra):
        return s.checkout(self.db,dict(items=[dict(sku=sku,quantity=q)],session_id=sid,idempotency_key=key,**extra))

    def test_seed_is_repeatable_and_preserves_local_edits(self):
        before=self.product();s.receive_stock(self.db,'MUG-001',3,'PO-001');self.assertFalse(seed(self.db));self.assertEqual(self.product()['inventory'],before['inventory']+3)
    def test_foreign_keys_and_sales_reconcile(self):
        with connect(self.db) as c:
            self.assertEqual(list(c.execute('PRAGMA foreign_key_check')),[])
            m=s.summary(c)['metrics'];self.assertEqual(m['net_cents'],m['gross_cents']-m['discount_cents']-m['refund_cents'])
            self.assertEqual(m['gross_profit_cents'],m['net_cents']-m['cogs_cents'])
    def test_refunds_round_to_cents_and_reverse_resalable_cogs(self):
        with connect(self.db) as c:
            lines=list(c.execute('SELECT * FROM line_sales WHERE returned>0'))
            self.assertTrue(lines)
            for l in lines:
                expected=int((Decimal(l['gross_cents']-l['discount_cents'])*l['returned']/l['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                self.assertEqual(l['refund_cents'],expected)
                self.assertEqual(l['cogs_cents'],(l['quantity']-l['returned'])*l['unit_cost_cents'])
    def test_cancelled_orders_never_enter_sales(self):
        with connect(self.db) as c:
            self.assertGreater(c.execute("SELECT count(*) FROM orders WHERE status='cancelled'").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT count(*) FROM order_sales s JOIN orders o ON o.id=s.order_id WHERE o.status='cancelled'").fetchone()[0],0)
    def test_order_shop_inventory_and_dashboard_update_together(self):
        p=self.product()
        with connect(self.db) as c:before=s.summary(c)['metrics']
        order=self.order(q=2)
        self.assertFalse(order['replayed']);self.assertEqual(order['net_cents'],2*p['price_cents'])
        self.assertEqual(self.product()['inventory'],p['inventory']-2)
        with connect(self.db) as c:
            after=s.summary(c)['metrics']
            self.assertEqual(after['orders'],before['orders']+1)
            self.assertEqual(after['net_cents'],before['net_cents']+2*p['price_cents'])
            self.assertEqual(after['purchases'],before['purchases']+1)
            self.assertEqual(c.execute("SELECT count(*) FROM audit_log WHERE action='checkout.completed'").fetchone()[0],1)
    def test_retry_does_not_double_charge_or_reduce_stock_twice(self):
        p=self.product();a=self.order();b=self.order();self.assertEqual(a['order_id'],b['order_id']);self.assertTrue(b['replayed']);self.assertEqual(self.product()['inventory'],p['inventory']-1)
    def test_promotion_applies_only_to_eligible_collection(self):
        a=self.order(promo_code='MAPLE10')
        self.assertEqual(a['net_cents'],1705)
        with self.assertRaises(s.Problem):self.order(sku='GFT-001',key='other-checkout-0001',promo_code='MAPLE10')
    def test_invalid_promotion_rolls_back(self):
        p=self.product()
        with self.assertRaises(s.Problem):self.order(promo_code='INVALID')
        self.assertEqual(self.product()['inventory'],p['inventory'])
    def test_stockout_and_draft_products_cannot_be_purchased(self):
        for sku in ['MUG-002','HOL-001']:
            with self.subTest(sku=sku),self.assertRaises(s.Problem):self.order(sku=sku)
    def test_all_cart_lines_roll_back_if_one_is_unavailable(self):
        p=self.product()
        with self.assertRaises(s.Problem):s.checkout(self.db,dict(items=[dict(sku='MUG-001',quantity=2),dict(sku='MUG-002',quantity=1)],session_id='session-all-rollback',idempotency_key='key-all-rollback'))
        self.assertEqual(self.product()['inventory'],p['inventory'])
    def test_negative_fractional_boolean_quantities_are_rejected(self):
        for q in [-1,0,1.5,True,'2',21]:
            with self.subTest(q=q),self.assertRaises(s.Problem):self.order(q=q)
    def test_concurrent_buyers_cannot_oversell_last_unit(self):
        with connect(self.db) as c:c.execute("UPDATE products SET inventory=1 WHERE sku='MUG-001'")
        def buy(i):
            try:return self.order(key=f'concurrent-key-{i:04}',sid=f'concurrent-session-{i:04}')
            except s.Problem:return None
        with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(buy,range(4)))
        self.assertEqual(sum(x is not None for x in result),1);self.assertEqual(self.product()['inventory'],0)
    def test_events_count_sessions_not_repeated_clicks(self):
        for _ in range(3):s.session_event(self.db,dict(session_id='repeat-session-0001',event='add_to_cart'))
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT cart FROM sessions').fetchone()[0],1)
    def test_event_input_is_validated(self):
        for event in ['purchase','unknown','']:
            with self.assertRaises(s.Problem):s.session_event(self.db,dict(session_id='valid-session-0001',event=event))
    def test_date_boundaries_are_inclusive_and_trend_has_all_days(self):
        with connect(self.db) as c:
            result=s.summary(c,'2026-10-26','2026-10-26');self.assertEqual(len(result['trend']),1)
            expected=c.execute("SELECT count(*) FROM order_sales WHERE date='2026-10-26'").fetchone()[0]
            self.assertEqual(result['metrics']['orders'],expected)
    def test_invalid_dates_and_future_dates_rejected(self):
        for start,end in [('oops','2026-10-26'),('2026-10-27','2026-10-26'),('2026-10-01','2027-01-01')]:
            with connect(self.db) as c,self.subTest(start=start),self.assertRaises(s.Problem):s.summary(c,start,end)
    def test_missing_previous_period_is_not_reported_as_zero_growth(self):
        with connect(self.db) as c:self.assertIsNone(s.summary(c,'2026-08-28','2026-09-26')['growth'])
    def test_listing_edit_reduces_quality_findings_and_is_versioned(self):
        p=self.product('APP-003')
        with connect(self.db) as c:self.assertIn('description',[a['kind'] for a in s.audits(c,p['sku'])])
        updated=s.change_product(self.db,p['sku'],dict(version=p['version'],description='A detailed cotton tee for everyday coffee runs. Wash cold and hang to dry.'))
        self.assertEqual(updated['version'],p['version']+1)
        with connect(self.db) as c:self.assertNotIn('description',[a['kind'] for a in s.audits(c,p['sku'])])
    def test_stale_listing_edit_cannot_overwrite_new_stock(self):
        p=self.product();s.receive_stock(self.db,p['sku'],2,'Receipt 02')
        with self.assertRaises(s.Problem) as error:s.change_product(self.db,p['sku'],dict(version=p['version'],title='New title'))
        self.assertEqual(error.exception.status,409)
    def test_invalid_compare_at_price_does_not_save(self):
        p=self.product()
        with self.assertRaises(s.Problem):s.change_product(self.db,p['sku'],dict(version=p['version'],compare_at_cents=100))
        self.assertEqual(self.product()['version'],p['version'])
    def test_csv_import_is_atomic_idempotent_and_rejects_unknown_skus(self):
        with connect(self.db) as c:csv_text=s.catalog_csv(c)
        # Seed includes an intentionally invalid compare-at value. Fix in the incoming file.
        parsed=list(csv.DictReader(io.StringIO(csv_text)))
        for p in parsed:p['compare_at_price']='0'
        out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(parsed[0]));w.writeheader();w.writerows(parsed)
        clean=out.getvalue();r=s.import_catalog(self.db,clean);self.assertEqual(r['rows'],16)
        self.assertTrue(s.import_catalog(self.db,clean)['already_imported'])
        before=self.product()
        bad=clean.replace('MUG-001','UNKNOWN-SKU')
        with self.assertRaises(s.Problem):s.import_catalog(self.db,bad)
        self.assertEqual(self.product()['version'],before['version'])
    def test_csv_rejects_nan_duplicate_and_extra_precision(self):
        template='sku,title,description,price,compare_at_price,alt\nMUG-001,Test mug,Description,{price},0,Alt text\n'
        for value in ['NaN','Infinity','18.951']:
            with self.subTest(value=value),self.assertRaises(s.Problem):s.import_catalog(self.db,template.format(price=value))
        with self.assertRaises(s.Problem):s.import_catalog(self.db,template.format(price='18.95')+'MUG-001,Other mug,Description,18.95,0,Alt\n')
    def test_formula_injection_is_escaped_in_spreadsheet_exports(self):
        self.assertEqual(s.csv_safe('=HYPERLINK("x")'),'\'=HYPERLINK("x")')
        self.assertEqual(s.csv_safe(' +cmd'),'\' +cmd')
        self.assertEqual(s.csv_safe(-12),-12)
    def test_dependent_launch_task_cannot_skip_prerequisite(self):
        with self.assertRaises(s.Problem):s.update_task(self.db,'T03','done')
        s.update_task(self.db,'T02','done');s.update_task(self.db,'T03','done')
        with self.assertRaises(s.Problem):s.update_task(self.db,'T02','todo')
    def test_launch_cannot_publish_with_unapproved_creative(self):
        with self.assertRaises(s.Problem):s.publish_launch(self.db,'LCH-001')
        self.assertEqual(self.product('HOL-001')['status'],'draft')
    def test_approval_requires_rights_and_received_sample(self):
        with self.assertRaises(s.Problem):s.update_asset(self.db,'AST-016',dict(approved=1))
        with self.assertRaises(s.Problem):s.update_asset(self.db,'AST-016',dict(approved=1,rights='Original illustration'))
    def test_launch_becomes_visible_only_when_every_prerequisite_is_complete(self):
        for task in ['T02','T03','T04','T05']:s.update_task(self.db,task,'done')
        with self.assertRaises(s.Problem):s.publish_launch(self.db,'LCH-001')
        s.update_asset(self.db,'AST-016',dict(approved=1,rights='Original illustration',sample_status='Received'))
        s.publish_launch(self.db,'LCH-001');self.assertEqual(self.product('HOL-001')['status'],'active')
        with self.assertRaises(s.Problem):s.update_task(self.db,'T02','todo')
    def test_asset_upload_approval_and_selection_fix_resolution(self):
        source=(ROOT/'examples'/'TUM-002-reshoot.svg').read_text()
        a=s.upload_asset(self.db,dict(sku='TUM-002',svg=source))
        with self.assertRaises(s.Problem):s.select_asset(self.db,a['id'])
        s.update_asset(self.db,a['id'],dict(approved=1,rights='Original illustration'))
        s.select_asset(self.db,a['id'])
        with connect(self.db) as c:self.assertNotIn('resolution',[a['kind'] for a in s.audits(c,'TUM-002')])
    def test_unsafe_svg_is_rejected(self):
        for payload in ['<svg width="1200" height="1200"><script>alert(1)</script></svg>','<!DOCTYPE svg><svg/>','<svg width="1200" height="1200" onload="x"/>']:
            with self.subTest(payload=payload),self.assertRaises(s.Problem):s.upload_asset(self.db,dict(sku='MUG-001',svg=payload))
    def test_stock_receipt_clears_stockout_and_is_logged(self):
        s.receive_stock(self.db,'MUG-002',20,'PO-002 received')
        with connect(self.db) as c:
            p=next(p for p in s.inventory(c) if p['sku']=='MUG-002');self.assertNotEqual(p['risk'],'Stockout')
            self.assertEqual(c.execute("SELECT count(*) FROM audit_log WHERE action='inventory.received'").fetchone()[0],1)
    def test_shipped_order_leaves_exception_queue_and_cannot_ship_twice(self):
        with connect(self.db) as c:oid=s.fulfillment(c)[0]['id']
        s.fulfill_order(self.db,oid)
        with connect(self.db) as c:self.assertNotIn(oid,[o['id'] for o in s.fulfillment(c)])
        with self.assertRaises(s.Problem):s.fulfill_order(self.db,oid)
    def test_customer_suppression_overrides_value_segment(self):
        with connect(self.db) as c:
            profiles=s.crm(c)
            for p in profiles:
                if not p['email_consent']:self.assertEqual(p['segment'],'Suppressed');self.assertFalse(p['reminder_eligible'])
    def test_crm_uses_unique_orders_and_does_not_multiply_order_lines(self):
        with connect(self.db) as c:
            for p in s.crm(c)[:10]:
                expected=c.execute("SELECT count(*) FROM orders WHERE customer_id=? AND status='paid'",(p['id'],)).fetchone()[0]
                self.assertEqual(p['orders'],expected)
    def test_exports_are_complete_and_current(self):
        self.order();dest=export_reports(self.db,Path(self.tmp.name)/'out')
        data=json.loads((dest/'report_data.json').read_text());self.assertIn('DEMO-',(dest/'sales.csv').read_text());self.assertTrue(data['lines']);self.assertTrue((dest/'manager_brief.md').exists())
    def test_excel_refresh_exports_preserve_dollar_units_and_unique_order_grain(self):
        order=self.order(promo_code='MAPLE10')
        with connect(self.db) as c:
            lines=list(csv.DictReader(io.StringIO(report_csv(c,'excel-lines'))))
            paid=list(csv.DictReader(io.StringIO(report_csv(c,'excel-orders'))))
            traffic=list(csv.DictReader(io.StringIO(report_csv(c,'excel-traffic'))))
            self.assertEqual(len({r['Order ID'] for r in paid}),len(paid))
            row=next(r for r in paid if r['Order ID']==order['order_id'])
            self.assertEqual(Decimal(row['Net sales']),Decimal('17.05'))
            self.assertEqual(Decimal(next(r for r in lines if r['Order ID']==order['order_id'])['Unit price']),Decimal('18.95'))
            all_time=s.summary(c,'2026-08-28','2026-10-26')['metrics']
            self.assertEqual(sum(int(r['Purchasing sessions']) for r in traffic),all_time['purchases'])
    def test_assignment_keeps_one_current_handoff_per_reference(self):
        p=dict(kind='inventory',reference='MUG-002',owner='Supply Chain',note='Confirm ETA')
        s.assign_issue(self.db,p);s.assign_issue(self.db,{**p,'note':'New ETA received'})
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT count(*) FROM issues').fetchone()[0],1)

class HTTPFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'http.sqlite3';seed(cls.db)
        cls.server=make_server(cls.db,0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.token=cls.get('/api/bootstrap')['token']
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    @classmethod
    def get(cls,path):
        with urllib.request.urlopen(cls.url+path) as r:return json.load(r)
    def request(self,path,payload,token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Merch-Token']=self.token
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(payload).encode(),headers=headers,method='POST')
        with urllib.request.urlopen(req) as r:return json.load(r)
    def test_pages_and_all_read_endpoints_render_without_error(self):
        for path in ['/','/shop','/app.js','/shop.js','/styles.css','/api/summary','/api/products','/api/performance','/api/operations','/api/crm','/api/audit','/api/report.csv?kind=lines','/api/report.csv?kind=excel-lines','/api/report.csv?kind=excel-orders','/api/report.csv?kind=excel-traffic','/api/report.csv?kind=excel-products','/api/catalog.csv']:
            with self.subTest(path=path),urllib.request.urlopen(self.url+path) as r:self.assertEqual(r.status,200)
    def test_http_checkout_updates_following_dashboard_response(self):
        before=self.get('/api/summary')['metrics']['orders']
        self.request('/api/checkout',dict(items=[dict(sku='MUG-001',quantity=1)],session_id='http-session-0001',idempotency_key='http-checkout-0001'))
        self.assertEqual(self.get('/api/summary')['metrics']['orders'],before+1)
    def test_mutation_requires_local_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/events',dict(session_id='token-session-0001',event='view_item'),token=False)
        self.assertEqual(e.exception.code,403)
    def test_cross_origin_request_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/events',dict(session_id='origin-session-0001',event='view_item'),origin='https://untrusted.example')
        self.assertEqual(e.exception.code,403)
    def test_path_traversal_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.url+'/%2e%2e/sql/schema.sql')
        self.assertEqual(e.exception.code,404)
    def test_validation_returns_useful_json_error(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/checkout',{})
        self.assertIn('error',json.load(e.exception))

if __name__=='__main__':unittest.main()
