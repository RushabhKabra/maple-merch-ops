"""Optional read-only external adapters. The demo never invokes these automatically.

All writes are local export files. Shopify catalog import and email campaign
activation are manual exercises in the user's own development accounts.
"""
import argparse
import csv
import html
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from .db import ROOT, DEFAULT_DB, connect, rows
from .seed import seed
from .services import Problem, require, crm, csv_safe

SHOPIFY_VERSION='2026-10'
KLAVIYO_REVISION='2026-10-15'

def request_json(url,headers=None,payload=None,opener=None):
    opener=opener or urllib.request.urlopen
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,
       headers={'Content-Type':'application/json','Accept':'application/json',**(headers or {})})
    for attempt in range(3):
        try:
            with opener(req,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (429,500,502,503,504) and attempt<2:
                retry=exc.headers.get('Retry-After','1')
                try:seconds=min(max(float(retry),.1),10)
                except ValueError:seconds=1
                time.sleep(seconds*(attempt+1));continue
            # Avoid printing request headers, token-bearing URLs or response bodies.
            raise Problem(f'External API returned HTTP {exc.code}. Check access scopes, version and account configuration.') from None
        except urllib.error.URLError:
            raise Problem('External API could not be reached. Check the network and retry.') from None

def shopify_products(domain,token,fetch=request_json):
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com',domain or ''),'Use your store-name.myshopify.com domain.')
    require(bool(token),'SHOPIFY_ACCESS_TOKEN is missing.')
    query='''query MerchProducts($cursor: String) {
      products(first: 100, after: $cursor) {
        nodes { id handle title description status productType
          variants(first: 100) { nodes { id sku price compareAtPrice inventoryQuantity }
            pageInfo { hasNextPage } }
          featuredMedia { ... on MediaImage { image { url altText width height } } }
        }
        pageInfo { hasNextPage endCursor }
      }
    }'''
    result=[];cursor=None;seen=set()
    while True:
        response=fetch(f'https://{domain}/admin/api/{SHOPIFY_VERSION}/graphql.json',
          {'X-Shopify-Access-Token':token},{'query':query,'variables':{'cursor':cursor}})
        require(not response.get('errors'),'Shopify returned a GraphQL error. Check read_products and read_inventory scopes.')
        page=response['data']['products']
        for product in page['nodes']:
            require(not product['variants']['pageInfo']['hasNextPage'],'A product has over 100 variants. This portfolio adapter refuses a partial export; extend variant pagination for that store.')
            result.append(product)
        if not page['pageInfo']['hasNextPage']:break
        cursor=page['pageInfo']['endCursor']
        require(cursor and cursor not in seen,'Shopify pagination did not advance.')
        seen.add(cursor)
        require(len(seen)<1000,'Pagination limit exceeded. Use a bulk export for this store.')
    return {'source':'Shopify GraphQL Admin API','api_version':SHOPIFY_VERSION,'products':result,
      'scope':'Read-only staged extract. Not loaded into the synthetic dashboard.'}

def ga4_report(property_id,access_token,start,end,fetch=request_json):
    require(bool(re.fullmatch(r'\d+',property_id or '')),'GA4_PROPERTY_ID must be numeric.')
    require(bool(access_token),'GA4_ACCESS_TOKEN is missing.')
    require(date.fromisoformat(start)<=date.fromisoformat(end),'Invalid report date range.')
    offset=0;all_rows=[];headers=None;currency=None
    while True:
        body={'dateRanges':[{'startDate':start,'endDate':end}],
          'dimensions':[{'name':'date'},{'name':'sessionDefaultChannelGroup'}],
          'metrics':[{'name':'sessions'},{'name':'ecommercePurchases'},{'name':'purchaseRevenue'}],
          'limit':10000,'offset':offset,'keepEmptyRows':False,'currencyCode':'CAD'}
        response=fetch(f'https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport',{'Authorization':'Bearer '+access_token},body)
        headers={'dimensions':response.get('dimensionHeaders',[]),'metrics':response.get('metricHeaders',[])}
        currency=response.get('metadata',{}).get('currencyCode','CAD')
        page=response.get('rows',[]);all_rows.extend(page);offset+=len(page)
        if offset>=int(response.get('rowCount',0)):break
        require(bool(page),'GA4 returned an incomplete page.')
    normalized=[]
    for row in all_rows:
        raw_date=row['dimensionValues'][0]['value']
        revenue=Decimal(row['metricValues'][2]['value'])
        normalized.append(dict(date=f'{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}',
          channel=row['dimensionValues'][1]['value'],sessions=int(row['metricValues'][0]['value']),
          ecommerce_purchase_events=int(row['metricValues'][1]['value']),
          purchase_revenue_cents=int((revenue*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))))
    return {'source':'GA4 Data API','currency':currency,'start':start,'end':end,'headers':headers,'rows':normalized,
      'note':'ecommercePurchases counts purchase events, not distinct purchasing sessions. Do not substitute it for the dashboard conversion numerator. This staged report does not overwrite demo data.'}

def klaviyo_profiles(token,revision=KLAVIYO_REVISION,fetch=request_json):
    require(bool(token),'KLAVIYO_PRIVATE_API_KEY is missing.')
    require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',revision)),'Use a YYYY-MM-DD Klaviyo revision.')
    url='https://a.klaviyo.com/api/profiles/?'+urllib.parse.urlencode({'additional-fields[profile]':'subscriptions'})
    result=[];seen=set()
    while url:
        parsed=urllib.parse.urlparse(url)
        require(parsed.scheme=='https' and parsed.hostname=='a.klaviyo.com' and parsed.path.startswith('/api/profiles'),'Unexpected Klaviyo pagination URL.')
        require(url not in seen,'Klaviyo pagination did not advance.');seen.add(url)
        response=fetch(url,{'Authorization':'Klaviyo-API-Key '+token,'revision':revision})
        result.extend(response.get('data',[]));url=response.get('links',{}).get('next')
        require(len(seen)<=1000,'Pagination limit exceeded.')
    return {'source':'Klaviyo Profiles API','revision':revision,'profiles':result,'scope':'Read-only extract. Contains account data; keep private. No profile is subscribed or emailed.'}

def klaviyo_plan(conn):
    # A profile's properties are not legal consent and do not subscribe it.
    profiles=[]
    for p in crm(conn):
        if p['segment']=='Suppressed':continue
        profiles.append({'data':{'type':'profile','attributes':{'email':p['email'],'first_name':p['first_name'],
          'properties':{'portfolio_segment':p['segment'],'synthetic_demo':True}}}})
    return {'destination':'Local JSON preview only','endpoint_reference':'POST /api/profile-import',
      'revision':KLAVIYO_REVISION,'payloads':profiles,'sends_email':False,'subscribes_profiles':False,
      'note':'Use example.com synthetic profiles for inspection only. Importing a profile is not subscribing it. Sending or subscribing is outside this project adapter.'}

def shopify_csv(conn):
    # Current Shopify column names; all products are exported as draft for a new dev-store import.
    headers=['Title','URL handle','Description','Vendor','Type','Tags','Status','SKU','Option1 name','Option1 value','Price','Compare-at price','Inventory tracker','Continue selling when out of stock','Fulfillment service','Product image URL','Image alt text']
    out=io.StringIO();writer=csv.writer(out,lineterminator='\n');writer.writerow(headers)
    for p in rows(conn,'SELECT * FROM products ORDER BY sku'):
        # Use the approved price and omit invalid compare-at values from the intentionally faulty source.
        compare=p['compare_at_cents'] if p['compare_at_cents']>p['expected_price_cents'] else 0
        writer.writerow([csv_safe(p['title']),p['handle'],csv_safe(p['description']),'Maple Merch Demo',p['category'],p['collection'],'draft',p['sku'],'Title','Default Title',
          f"{p['expected_price_cents']/100:.2f}",f'{compare/100:.2f}' if compare else '', 'shopify','deny','manual','',csv_safe(p['alt'])])
    return out.getvalue()

def main():
    parser=argparse.ArgumentParser(description='Optional read-only platform extracts and local import previews')
    parser.add_argument('source',choices=['shopify-csv','shopify-read','ga4-read','klaviyo-read','klaviyo-plan'])
    parser.add_argument('--db',type=Path,default=DEFAULT_DB)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',default='2026-09-27');parser.add_argument('--end',default='2026-10-26')
    args=parser.parse_args();seed(args.db)
    if args.source=='shopify-csv':
        with connect(args.db) as conn:data=shopify_csv(conn)
    elif args.source=='klaviyo-plan':
        with connect(args.db) as conn:data=klaviyo_plan(conn)
    elif args.source=='shopify-read':data=shopify_products(os.getenv('SHOPIFY_STORE_DOMAIN'),os.getenv('SHOPIFY_ACCESS_TOKEN'))
    elif args.source=='ga4-read':data=ga4_report(os.getenv('GA4_PROPERTY_ID'),os.getenv('GA4_ACCESS_TOKEN'),args.start,args.end)
    else:data=klaviyo_profiles(os.getenv('KLAVIYO_PRIVATE_API_KEY'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(data if isinstance(data,str) else json.dumps(data,indent=2),encoding='utf-8')
    print(f'Local export saved: {args.output}')

if __name__=='__main__':
    try:main()
    except (Problem,ValueError) as exc:raise SystemExit(str(exc))
