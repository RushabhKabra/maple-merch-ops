import csv
import io
import tempfile
import unittest
from pathlib import Path
from merchops.db import connect
from merchops.seed import seed
from merchops.integrations import shopify_products,ga4_report,klaviyo_profiles,klaviyo_plan,shopify_csv
from merchops.services import Problem

class IntegrationContracts(unittest.TestCase):
    def test_shopify_uses_graphql_cursor_pagination(self):
        calls=[]
        def fetch(url,headers,payload):
            calls.append(payload['variables']['cursor'])
            return {'data':{'products':{'nodes':[{'id':str(len(calls)),'variants':{'pageInfo':{'hasNextPage':False}}}],
              'pageInfo':{'hasNextPage':len(calls)==1,'endCursor':'page-2'}}}}
        d=shopify_products('example-store.myshopify.com','not-a-real-token',fetch)
        self.assertEqual(calls,[None,'page-2']);self.assertEqual(len(d['products']),2)
    def test_shopify_rejects_graphql_errors_and_partial_variant_export(self):
        for response in [{'errors':[{'message':'Denied'}]},{'data':{'products':{'nodes':[{'variants':{'pageInfo':{'hasNextPage':True}}}],'pageInfo':{'hasNextPage':False}}}}]:
            with self.subTest(response=response),self.assertRaises(Problem):shopify_products('example-store.myshopify.com','test',lambda *a:response)
    def test_shopify_domain_cannot_redirect_tokens_to_an_arbitrary_host(self):
        for domain in ['attacker.example','store.myshopify.com.attacker.example','https://store.myshopify.com']:
            with self.subTest(domain=domain),self.assertRaises(Problem):shopify_products(domain,'test',lambda *a:None)
    def test_ga4_request_and_normalization_preserve_metric_scope(self):
        calls=[]
        def fetch(url,headers,body):
            calls.append(body)
            return {'rowCount':1,'metadata':{'currencyCode':'CAD'},'rows':[{'dimensionValues':[{'value':'20261026'},{'value':'Organic Search'}],
              'metricValues':[{'value':'100'},{'value':'3'},{'value':'100.25'}]}]}
        d=ga4_report('123','test','2026-10-01','2026-10-26',fetch)
        self.assertEqual(d['rows'][0]['purchase_revenue_cents'],10025)
        self.assertEqual(d['rows'][0]['ecommerce_purchase_events'],3)
        self.assertEqual(calls[0]['metrics'][1]['name'],'ecommercePurchases')
        self.assertIn('not distinct purchasing sessions',d['note'])
    def test_ga4_paginates_instead_of_silently_truncating(self):
        offsets=[]
        def fetch(url,headers,body):
            offsets.append(body['offset'])
            return {'rowCount':2,'rows':[{'dimensionValues':[{'value':'20261026'},{'value':'Direct'}],'metricValues':[{'value':'1'},{'value':'0'},{'value':'0'}]}]}
        d=ga4_report('123','test','2026-10-01','2026-10-26',fetch)
        self.assertEqual(offsets,[0,1]);self.assertEqual(len(d['rows']),2)
    def test_klaviyo_follows_only_expected_https_profile_urls(self):
        responses=[{'data':[{'id':'1'}],'links':{'next':'https://attacker.example/profiles'}}]
        with self.assertRaises(Problem):klaviyo_profiles('test',fetch=lambda *a:responses[0])
    def test_klaviyo_read_only_paginates(self):
        calls=[]
        def fetch(url,headers):
            calls.append(url);return {'data':[{'id':str(len(calls))}],'links':{'next':'https://a.klaviyo.com/api/profiles/?page=2' if len(calls)==1 else None}}
        self.assertEqual(len(klaviyo_profiles('test',fetch=fetch)['profiles']),2)
    def test_local_exports_are_drafts_and_do_not_subscribe_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.sqlite3';seed(db)
            with connect(db) as conn:
                products=list(csv.DictReader(io.StringIO(shopify_csv(conn))))
                self.assertEqual(len(products),16);self.assertEqual({p['Status'] for p in products},{'draft'})
                self.assertTrue(all(not p['Product image URL'] for p in products))
                plan=klaviyo_plan(conn)
                self.assertFalse(plan['sends_email']);self.assertFalse(plan['subscribes_profiles'])
                self.assertTrue(plan['payloads']);self.assertTrue(all(p['data']['attributes']['email'].endswith('@example.com') for p in plan['payloads']))

if __name__=='__main__':unittest.main()
