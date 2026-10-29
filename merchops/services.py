from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from .db import ROOT, DEFAULT_DB, as_of, connect, log, rows, transaction

class Problem(ValueError):
    def __init__(self,message,status=400):
        super().__init__(message);self.status=status

def require(condition,message,status=400):
    if not condition: raise Problem(message,status)

def integer(value,name,minimum=0,maximum=10_000_000):
    require(isinstance(value,int) and not isinstance(value,bool) and minimum<=value<=maximum,
            f"{name} must be a whole number between {minimum} and {maximum}.")
    return value

def window(conn,start=None,end=None):
    end=end or as_of(conn)
    start=start or (date.fromisoformat(end)-timedelta(days=29)).isoformat()
    try: a,b=date.fromisoformat(start),date.fromisoformat(end)
    except (ValueError,TypeError): raise Problem("Use dates in YYYY-MM-DD format.")
    require(a<=b,"Start date must be on or before end date.")
    require((b-a).days<=366,"Choose at most 367 days.")
    require(b<=date.fromisoformat(as_of(conn)),"End date exceeds the dataset's as-of date.")
    return start,end

def summary(conn,start=None,end=None,channel=None):
    start,end=window(conn,start,end)
    channels={r[0] for r in conn.execute("SELECT DISTINCT channel FROM orders UNION SELECT DISTINCT channel FROM traffic")}
    if channel: require(channel in channels,"Unknown acquisition channel.")
    clause=" AND channel=?" if channel else ""
    params=[start,end]+([channel] if channel else [])
    sums=dict(conn.execute("SELECT COUNT(*) orders,COALESCE(SUM(gross_cents),0) gross_cents,COALESCE(SUM(discount_cents),0) discount_cents,COALESCE(SUM(refund_cents),0) refund_cents,COALESCE(SUM(net_cents),0) net_cents,COALESCE(SUM(cogs_cents),0) cogs_cents,COALESCE(SUM(units),0) units,COALESCE(SUM(returns),0) returns FROM order_sales WHERE date BETWEEN ? AND ?"+clause,params).fetchone())
    traffic=rows(conn,"SELECT date,channel,SUM(sessions) sessions,SUM(cart_sessions) carts,SUM(checkout_sessions) checkouts,SUM(purchase_sessions) purchases FROM (SELECT date,channel,sessions,cart_sessions,checkout_sessions,purchase_sessions FROM traffic UNION ALL SELECT substr(started_at,1,10),channel,1,cart,checkout,purchased FROM sessions) WHERE date BETWEEN ? AND ?"+clause+" GROUP BY date,channel",params)
    funnel={k:sum(t[k] for t in traffic) for k in ("sessions","carts","checkouts","purchases")}
    sums.update(funnel)
    sums["aov_cents"]=round(sums["net_cents"]/sums["orders"]) if sums["orders"] else None
    sums["conversion"]=sums["purchases"]/sums["sessions"] if sums["sessions"] else None
    sums["gross_profit_cents"]=sums["net_cents"]-sums["cogs_cents"]
    sums["margin"]=sums["gross_profit_cents"]/sums["net_cents"] if sums["net_cents"] else None
    daily={r["date"]:r for r in rows(conn,"SELECT date,COUNT(*) orders,SUM(net_cents) net_cents FROM order_sales WHERE date BETWEEN ? AND ?"+clause+" GROUP BY date ORDER BY date",params)}
    trend=[]
    day=date.fromisoformat(start)
    while day<=date.fromisoformat(end):
        key=str(day);trend.append(daily.get(key,dict(date=key,orders=0,net_cents=0)));day+=timedelta(days=1)
    channel_sales=rows(conn,"SELECT channel,COUNT(*) orders,SUM(net_cents) net_cents FROM order_sales WHERE date BETWEEN ? AND ?"+clause+" GROUP BY channel ORDER BY net_cents DESC",params)
    for item in channel_sales:
        item["sessions"]=sum(t["sessions"] for t in traffic if t["channel"]==item["channel"])
        purchases=sum(t["purchases"] for t in traffic if t["channel"]==item["channel"])
        item["conversion"]=purchases/item["sessions"] if item["sessions"] else None
    n=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
    prev_end=date.fromisoformat(start)-timedelta(days=1)
    prev_start=prev_end-timedelta(days=n-1)
    earliest=conn.execute("SELECT MIN(date) FROM traffic").fetchone()[0]
    complete_previous=bool(earliest and earliest<=str(prev_start))
    prev=conn.execute("SELECT SUM(net_cents) FROM order_sales WHERE date BETWEEN ? AND ?"+clause,[str(prev_start),str(prev_end)]+([channel] if channel else [])).fetchone()[0]
    growth=(sums["net_cents"]-prev)/prev if complete_previous and prev else None
    return dict(start=start,end=end,channel=channel,as_of=as_of(conn),metrics=sums,trend=trend,channels=channel_sales,
      growth=growth,previous_period_complete=complete_previous,source="Synthetic demo + local test orders")

def product_performance(conn,start=None,end=None):
    start,end=window(conn,start,end)
    return rows(conn,"""SELECT p.sku,p.title,p.category,p.collection,p.status,p.price_cents,p.inventory,
      COALESCE(SUM(s.quantity),0) units,COALESCE(SUM(s.returned),0) returns,
      COALESCE(SUM(s.net_cents),0) net_cents,COALESCE(SUM(s.net_cents-s.cogs_cents),0) gross_profit_cents
      FROM products p LEFT JOIN line_sales s ON s.sku=p.sku AND s.date BETWEEN ? AND ?
      GROUP BY p.sku ORDER BY net_cents DESC""",(start,end))

def inventory(conn):
    end=as_of(conn);start=str(date.fromisoformat(end)-timedelta(days=6))
    result=rows(conn,"""SELECT p.*,COALESCE(SUM(s.quantity),0) units_7d FROM products p
      LEFT JOIN line_sales s ON s.sku=p.sku AND s.date BETWEEN ? AND ? GROUP BY p.sku""",(start,end))
    for p in result:
        avg=p["units_7d"]/7
        p["daily_demand"]=round(avg,2)
        p["days_cover"]=round(p["inventory"]/avg,1) if avg else None
        p["suggested_order"]=max(0,math.ceil(avg*(p["lead_days"]+7))-p["inventory"])
        p["risk"]="Draft" if p["status"]=="draft" else "Stockout" if p["inventory"]==0 else "Reorder" if avg and p["inventory"]<=avg*(p["lead_days"]+7) else "Healthy"
    return sorted(result,key=lambda x:({"Stockout":0,"Reorder":1,"Healthy":2,"Draft":3}[x["risk"]],x["sku"]))

def audits(conn,sku=None):
    findings=[]
    products=rows(conn,"SELECT * FROM products"+(" WHERE sku=?" if sku else ""),[sku] if sku else [])
    def add(p,kind,message,owner="E-Commerce",severity="warning"):
        findings.append(dict(sku=p["sku"],title=p["title"],kind=kind,message=message,owner=owner,severity=severity))
    for p in products:
        if len(p["description"].strip())<40: add(p,"description","Add a useful description of at least 40 characters.")
        if not p["alt"].strip(): add(p,"alt","Add descriptive image alt text.","Creative & Storytelling")
        if p["price_cents"]!=p["expected_price_cents"]: add(p,"price","Listing price differs from the approved merchandising price.","Category","critical")
        if p["compare_at_cents"] and p["compare_at_cents"]<=p["price_cents"]: add(p,"compare_at","Compare-at price must be above the selling price.","Category","critical")
        asset=conn.execute("SELECT * FROM assets WHERE sku=? AND filename=?",(p["sku"],p["image"])).fetchone()
        path=ROOT/"web"/p["image"].lstrip("/")
        if not re.fullmatch(r"/assets/[A-Za-z0-9_-]+\.svg",p["image"]) or not path.is_file(): add(p,"image","Product image is missing.","Creative & Storytelling","critical")
        if not asset: add(p,"asset","No matching asset-library record.","Creative & Storytelling","critical")
        else:
            if min(asset["width"],asset["height"])<800: add(p,"resolution","Replace the primary image with an asset at least 800 × 800.","Creative & Storytelling")
            if not asset["approved"] or asset["rights"] in ("","pending"): add(p,"approval","Creative approval or usage rights are pending.","Creative & Storytelling","critical")
            if asset["sample_status"]!="Received": add(p,"sample","Confirm that the product sample was received.","Planning & Inventory")
    return findings

def fulfillment(conn):
    end=datetime.fromisoformat(as_of(conn)+"T23:59:59+00:00")
    result=rows(conn,"SELECT o.id,o.placed_at,o.fulfillment,o.customer_id,SUM(s.net_cents) net_cents FROM orders o JOIN line_sales s ON s.order_id=o.id WHERE o.status='paid' AND o.fulfillment IN('open','hold') GROUP BY o.id ORDER BY o.placed_at")
    for o in result:
        o["age_hours"]=round((end-datetime.fromisoformat(o["placed_at"])).total_seconds()/3600,1)
        o["issue"]="On hold" if o["fulfillment"]=="hold" else "Over 48h" if o["age_hours"]>48 else "Within SLA"
    return result

def launches(conn):
    result=rows(conn,"SELECT * FROM launches ORDER BY target_date")
    for launch in result:
        tasks=rows(conn,"SELECT * FROM tasks WHERE launch_id=? ORDER BY due_date,id",(launch["id"],))
        for task in tasks:
            task["overdue"]=task["status"]!="done" and task["due_date"]<as_of(conn)
            parent=next((t for t in tasks if t["id"]==task["depends_on"]),None)
            task["blocked"]=bool(parent and parent["status"]!="done")
        skus=[r[0] for r in conn.execute("SELECT sku FROM launch_products WHERE launch_id=?",(launch["id"],))]
        blockers=[f'Task {t["id"]}: {t["title"]}' for t in tasks if t["status"]!="done"]
        for sku in skus:
            blockers.extend(f'{sku}: {a["message"]}' for a in audits(conn,sku))
            if conn.execute("SELECT inventory FROM products WHERE sku=?",(sku,)).fetchone()[0]<=0: blockers.append(f"{sku}: no available inventory")
        launch.update(tasks=tasks,skus=skus,blockers=blockers,ready=not blockers,
          completion=round(sum(t["status"]=="done" for t in tasks)/len(tasks)*100) if tasks else 0)
    return result

def crm(conn):
    cutoff=date.fromisoformat(as_of(conn))-timedelta(days=30)
    profiles=rows(conn,"""SELECT c.*,COALESCE(SUM(s.net_cents),0) lifetime_net_cents,COUNT(s.order_id) orders,
      MAX(s.date) last_order FROM customers c LEFT JOIN order_sales s ON s.customer_id=c.id GROUP BY c.id""")
    abandoned={r[0] for r in conn.execute("SELECT DISTINCT customer_id FROM carts WHERE converted=0 AND substr(created_at,1,10)<=?",(as_of(conn),))}
    for p in profiles:
        p["segment"]="Suppressed" if not p["email_consent"] or not p["consent_at"] else "VIP" if p["lifetime_net_cents"]>=50000 else "Win-back" if p["last_order"] and p["last_order"]<str(cutoff) else "Repeat" if p["orders"]>=2 else "Welcome"
        p["abandoned_cart"]=p["id"] in abandoned
        # Demo cart reminders require explicit opt-in and a 24-hour wait, and no later order.
        cart=conn.execute("SELECT MAX(created_at) FROM carts WHERE customer_id=? AND converted=0",(p["id"],)).fetchone()[0]
        last=conn.execute("SELECT MAX(placed_at) FROM orders WHERE customer_id=? AND status='paid'",(p["id"],)).fetchone()[0]
        p["reminder_eligible"]=bool(p["segment"]!="Suppressed" and cart and cart[:10]<as_of(conn) and (not last or last<cart))
    return profiles

def change_product(path,sku,payload):
    allowed={"title","description","alt","price_cents","compare_at_cents","expected_price_cents"}
    require(set(payload)<=allowed|{"version"},"Unsupported product field.")
    with transaction(path) as conn:
        old=conn.execute("SELECT * FROM products WHERE sku=?",(sku,)).fetchone()
        require(old is not None,"Product not found.",404)
        old=dict(old);require(payload.get("version")==old["version"],"This product changed. Refresh before saving.",409)
        new={**old,**{k:v for k,v in payload.items() if k in allowed}}
        for key in ("title","description","alt"):
            require(isinstance(new[key],str) and len(new[key])<=4000,f"Invalid {key}.")
        require(1<=len(new["title"].strip())<=120,"Product title must contain 1–120 characters.")
        for key in ("price_cents","expected_price_cents"): integer(new[key],key,1,1_000_000)
        integer(new["compare_at_cents"],"compare_at_cents",0,1_000_000)
        require(not new["compare_at_cents"] or new["compare_at_cents"]>new["price_cents"],"Compare-at price must be zero or above the selling price.")
        new["version"]+=1
        keys=sorted(allowed)+["version"]
        conn.execute(f'UPDATE products SET {",".join(k+"=?" for k in keys)} WHERE sku=?',[new[k] for k in keys]+[sku])
        log(conn,"product.updated",sku,old,new)
        return new

def update_task(path,task_id,status):
    require(status in ("todo","in_progress","done"),"Invalid task status.")
    with transaction(path) as conn:
        task=conn.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        require(task is not None,"Task not found.",404)
        launch=conn.execute("SELECT status FROM launches WHERE id=?",(task["launch_id"],)).fetchone()
        require(launch[0]!="live","A live launch checklist is locked.",409)
        if status=="done" and task["depends_on"]:
            require(conn.execute("SELECT status FROM tasks WHERE id=?",(task["depends_on"],)).fetchone()[0]=="done","Complete the prerequisite task first.",409)
        if status!="done":
            require(not conn.execute("SELECT id FROM tasks WHERE depends_on=? AND status='done'",(task_id,)).fetchone(),"Reopen the completed dependent task first.",409)
        conn.execute("UPDATE tasks SET status=? WHERE id=?",(status,task_id));log(conn,"task.updated",task_id,dict(task),{"status":status})
        return {"id":task_id,"status":status}

def publish_launch(path,launch_id):
    with transaction(path) as conn:
        launch=next((l for l in launches(conn) if l["id"]==launch_id),None)
        require(launch is not None,"Launch not found.",404)
        require(launch["status"]!="live","Launch is already live.",409)
        require(launch["ready"],"Launch blocked: "+"; ".join(launch["blockers"][:4]),409)
        conn.executemany("UPDATE products SET status='active',version=version+1 WHERE sku=?",[(s,) for s in launch["skus"]])
        conn.execute("UPDATE launches SET status='live' WHERE id=?",(launch_id,))
        log(conn,"launch.published",launch_id,after={"skus":launch["skus"],"scope":"local demo shop"})
        return {"status":"live","scope":"Local demo shop only"}

def update_asset(path,asset_id,payload):
    require(set(payload)<={"approved","rights","sample_status","shoot_date"},"Unsupported asset field.")
    with transaction(path) as conn:
        asset=conn.execute("SELECT * FROM assets WHERE id=?",(asset_id,)).fetchone()
        require(asset is not None,"Asset not found.",404)
        new={**dict(asset),**payload}
        integer(new["approved"],"approved",0,1)
        require(new["sample_status"] in ("Requested","In transit","Received"),"Invalid sample status.")
        require(isinstance(new["rights"],str) and len(new["rights"])<=200,"Invalid rights note.")
        try: date.fromisoformat(new["shoot_date"])
        except (ValueError,TypeError): raise Problem("Invalid shoot date.")
        require(not new["approved"] or new["rights"] not in ("","pending"),"Record usage rights before approving.")
        require(not new["approved"] or new["sample_status"]=="Received","Receive the sample before approving.")
        keys=["approved","rights","sample_status","shoot_date"]
        conn.execute("UPDATE assets SET approved=?,rights=?,sample_status=?,shoot_date=? WHERE id=?",[new[k] for k in keys]+[asset_id])
        log(conn,"asset.updated",asset_id,dict(asset),new)
        return new

def upload_asset(path,payload):
    sku=payload.get("sku");source=payload.get("svg")
    require(isinstance(sku,str) and isinstance(source,str) and 0<len(source)<=100_000,"Provide a SKU and an SVG smaller than 100 KB.")
    require(not re.search(r"<!DOCTYPE|<!ENTITY",source,re.I),"SVG declarations are not allowed.")
    try: tree=ET.fromstring(source)
    except ET.ParseError: raise Problem("Invalid SVG file.")
    allowed_tags={"svg","g","rect","path","circle","ellipse","line","polyline","polygon","text","title","desc"}
    allowed_attrs={"width","height","viewBox","x","y","cx","cy","r","rx","ry","d","points","fill","stroke","stroke-width","x1","x2","y1","y2","transform","opacity","font-family","font-size","font-weight","text-anchor","letter-spacing"}
    require(tree.tag.split("}")[-1]=="svg","An SVG root element is required.")
    for node in tree.iter():
        require(node.tag.split("}")[-1] in allowed_tags,"SVG contains an unsupported element.")
        for name,value in node.attrib.items():
            require(name in allowed_attrs and not re.search(r"url\s*\(|javascript:|https?:|data:",value,re.I),"SVG contains an unsupported attribute.")
    try: width=int(tree.attrib["width"]);height=int(tree.attrib["height"])
    except (KeyError,ValueError): raise Problem("SVG needs integer width and height.")
    require(800<=width<=6000 and 800<=height<=6000,"Upload an SVG between 800 and 6000 pixels in each dimension.")
    digest=hashlib.sha256(source.encode()).hexdigest()[:20]
    filename=f"/assets/upload-{digest}.svg";asset_id=f"UP-{digest}"
    with transaction(path) as conn:
        require(conn.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone(),"SKU not found.",404)
        previous=conn.execute("SELECT sku FROM assets WHERE id=?",(asset_id,)).fetchone()
        require(not previous or previous[0]==sku,"This file is already registered to another SKU.",409)
        (ROOT/"web"/filename.lstrip("/")).write_text(source,encoding="utf-8")
        conn.execute("INSERT OR IGNORE INTO assets VALUES(?,?,?,?,?,0,'pending','Creative & Storytelling','Received',?)",(asset_id,sku,filename,width,height,as_of(conn)))
        log(conn,"asset.uploaded",asset_id,after={"sku":sku,"filename":filename})
    return {"id":asset_id,"filename":filename,"message":"Uploaded. Record usage rights and approve before selecting as primary."}

def select_asset(path,asset_id):
    with transaction(path) as conn:
        a=conn.execute("SELECT * FROM assets WHERE id=?",(asset_id,)).fetchone()
        require(a is not None,"Asset not found.",404)
        require(a["approved"] and a["rights"] not in ("","pending") and a["sample_status"]=="Received","Approve creative rights and sample receipt first.",409)
        require(min(a["width"],a["height"])>=800,"Primary imagery must be at least 800 × 800.",409)
        conn.execute("UPDATE products SET image=?,version=version+1 WHERE sku=?",(a["filename"],a["sku"]))
        log(conn,"asset.selected",asset_id,after={"sku":a["sku"],"filename":a["filename"]})
    return {"sku":a["sku"],"primary_asset":asset_id}

def receive_stock(path,sku,quantity,note):
    integer(quantity,"quantity",1,10000)
    require(isinstance(note,str) and 3<=len(note)<=300,"Add a receipt reference or note (3–300 characters).")
    with transaction(path) as conn:
        p=conn.execute("SELECT inventory FROM products WHERE sku=?",(sku,)).fetchone()
        require(p is not None,"Product not found.",404)
        conn.execute("UPDATE products SET inventory=inventory+?,version=version+1 WHERE sku=?",(quantity,sku))
        log(conn,"inventory.received",sku,{"inventory":p[0]},{"quantity":quantity,"note":note,"inventory":p[0]+quantity})
        return {"sku":sku,"inventory":p[0]+quantity}

def fulfill_order(path,order_id):
    with transaction(path) as conn:
        o=conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
        require(o is not None,"Order not found.",404)
        require(o["status"]=="paid" and o["fulfillment"] in ("open","hold"),"Order cannot be fulfilled from its current state.",409)
        conn.execute("UPDATE orders SET fulfillment='shipped',fulfilled_at=? WHERE id=?",(as_of(conn)+"T23:59:00+00:00",order_id))
        log(conn,"order.fulfilled",order_id,dict(o),{"fulfillment":"shipped","scope":"Local demo"})
        return {"id":order_id,"fulfillment":"shipped"}

def assign_issue(path,payload):
    require(set(payload)=={"kind","reference","owner","note"},"Provide kind, reference, owner and note.")
    require(payload["kind"] in ("inventory","fulfillment","listing"),"Invalid issue kind.")
    for key in ("reference","owner","note"):
        require(isinstance(payload[key],str) and 1<=len(payload[key])<=300,f"Invalid {key}.")
    with transaction(path) as conn:
        table="orders" if payload["kind"]=="fulfillment" else "products"
        key="id" if table=="orders" else "sku"
        require(conn.execute(f"SELECT 1 FROM {table} WHERE {key}=?",(payload["reference"],)).fetchone(),"Issue reference not found.",404)
        conn.execute("INSERT INTO issues(kind,reference,owner,note) VALUES(?,?,?,?) ON CONFLICT(kind,reference) DO UPDATE SET owner=excluded.owner,note=excluded.note",tuple(payload[k] for k in ("kind","reference","owner","note")))
        log(conn,"issue.assigned",payload["reference"],after=payload)
        return payload

def session_event(path,payload):
    sid=payload.get("session_id","");event=payload.get("event","")
    require(isinstance(sid,str) and re.fullmatch(r"[a-zA-Z0-9-]{10,80}",sid),"Invalid session ID.")
    require(event in ("view_item","add_to_cart","begin_checkout"),"Unsupported event.")
    with transaction(path) as conn:
        conn.execute("INSERT OR IGNORE INTO sessions(id,started_at,channel) VALUES(?,?,'Direct')",(sid,as_of(conn)+"T18:00:00+00:00"))
        if event=="add_to_cart": conn.execute("UPDATE sessions SET cart=1 WHERE id=?",(sid,))
        if event=="begin_checkout": conn.execute("UPDATE sessions SET cart=1,checkout=1 WHERE id=?",(sid,))
    return {"recorded":event,"destination":"Local SQLite event store"}

def checkout(path,payload):
    require(set(payload)<={"items","session_id","idempotency_key","promo_code"},"Unknown checkout field.")
    key=payload.get("idempotency_key","");sid=payload.get("session_id","")
    require(isinstance(key,str) and re.fullmatch(r"[a-zA-Z0-9-]{10,80}",key),"Invalid checkout request key.")
    require(isinstance(sid,str) and re.fullmatch(r"[a-zA-Z0-9-]{10,80}",sid),"Invalid session ID.")
    items=payload.get("items")
    require(isinstance(items,list) and 1<=len(items)<=20,"Provide 1–20 cart lines.")
    cart={}
    for item in items:
        require(isinstance(item,dict) and set(item)=={"sku","quantity"},"Each line needs sku and quantity.")
        require(isinstance(item["sku"],str),"Invalid SKU.")
        integer(item["quantity"],"quantity",1,20)
        cart[item["sku"]]=cart.get(item["sku"],0)+item["quantity"]
        integer(cart[item["sku"]],"quantity per SKU",1,20)
    with transaction(path) as conn:
        previous=conn.execute("SELECT id FROM orders WHERE idempotency_key=?",(key,)).fetchone()
        if previous:
            return {"order_id":previous[0],"replayed":True}
        code=payload.get("promo_code","").strip().upper()
        require(len(code)<=30,"Invalid promo code.")
        promo=conn.execute("SELECT * FROM promotions WHERE code=? AND start_date<=? AND end_date>=?",(code,as_of(conn),as_of(conn))).fetchone() if code else None
        if code: require(promo is not None,"Promotion is invalid or expired.")
        products=[]
        for sku,qty in cart.items():
            p=conn.execute("SELECT * FROM products WHERE sku=? AND status='active'",(sku,)).fetchone()
            require(p is not None,f"{sku} is unavailable.",409)
            require(p["inventory"]>=qty,f"Only {p['inventory']} units of {sku} are available.",409)
            products.append((p,qty))
        if promo: require(any(p["collection"]==promo["collection"] for p,q in products),"This promotion does not apply to the cart.")
        oid="DEMO-"+uuid.uuid4().hex[:10].upper()
        cid="LOCAL-DEMO"
        conn.execute("INSERT OR IGNORE INTO customers VALUES(?,?,'Demo buyer',0,NULL)",(cid,"local-buyer@example.com"))
        conn.execute("INSERT OR IGNORE INTO sessions(id,started_at,channel) VALUES(?,?,'Direct')",(sid,as_of(conn)+"T18:00:00+00:00"))
        conn.execute("UPDATE sessions SET cart=1,checkout=1,purchased=1 WHERE id=?",(sid,))
        conn.execute("INSERT INTO orders(id,placed_at,customer_id,channel,status,fulfillment,session_id,idempotency_key) VALUES(?,?,?,'Direct','paid','open',?,?)",(oid,as_of(conn)+"T18:30:00+00:00",cid,sid,key))
        total=0
        for i,(p,qty) in enumerate(products):
            gross=qty*p["price_cents"]
            discount=int((Decimal(gross)*Decimal(promo["percent"])/100).quantize(Decimal("1"),rounding=ROUND_HALF_UP)) if promo and p["collection"]==promo["collection"] else 0
            conn.execute("INSERT INTO order_lines VALUES(?,?,?,?,?,?,?,?)",(f"{oid}-{i}",oid,p["sku"],qty,0,p["price_cents"],discount,p["cost_cents"]))
            conn.execute("UPDATE products SET inventory=inventory-?,version=version+1 WHERE sku=?",(qty,p["sku"]))
            total+=gross-discount
        log(conn,"checkout.completed",oid,after={"net_cents":total,"scope":"Synthetic local order. No payment charged."})
        return {"order_id":oid,"net_cents":total,"replayed":False,"message":"Local demo order created. No payment charged."}

def import_catalog(path,csv_text):
    require(isinstance(csv_text,str) and len(csv_text)<=1_000_000,"CSV must be under 1 MB.")
    required={"sku","title","description","price","compare_at_price","alt"}
    reader=csv.DictReader(io.StringIO(csv_text))
    require(reader.fieldnames is not None and set(reader.fieldnames)==required and len(reader.fieldnames)==len(required),"CSV headers must be sku,title,description,price,compare_at_price,alt (in any order).")
    items=list(reader);require(0<len(items)<=500,"Import 1–500 existing product rows.")
    digest=hashlib.sha256(csv_text.encode()).hexdigest()
    seen=set();prepared=[];errors=[]
    for index,item in enumerate(items,2):
        try:
            require(None not in item and all(isinstance(v,str) for v in item.values()),"Unexpected or missing fields.")
            require(item["sku"] not in seen,"Duplicate SKU in file.");seen.add(item["sku"])
            price=Decimal(item["price"]);compare=Decimal(item["compare_at_price"] or "0")
            require(price.is_finite() and compare.is_finite(),"Prices must be finite.")
            require(price*100==(price*100).to_integral_value() and compare*100==(compare*100).to_integral_value(),"Prices need at most two decimal places.")
            pc=int(price*100);cc=int(compare*100)
            integer(pc,"price",1,1_000_000);integer(cc,"compare_at_price",0,1_000_000)
            require(cc==0 or cc>pc,"Compare-at price must exceed selling price.")
            require(1<=len(item["title"].strip())<=120 and len(item["description"])<=4000 and len(item["alt"])<=4000,"Invalid text length.")
            prepared.append((item["title"],item["description"],pc,cc,item["alt"],item["sku"]))
        except (ValueError,ArithmeticError,TypeError) as exc: errors.append(f"Row {index}: {exc}")
    require(not errors,"Import rejected; no rows changed. "+" ".join(errors[:5]))
    with transaction(path) as conn:
        if conn.execute("SELECT 1 FROM imports WHERE digest=?",(digest,)).fetchone(): return {"rows":0,"already_imported":True}
        missing=[p[-1] for p in prepared if not conn.execute("SELECT 1 FROM products WHERE sku=?",(p[-1],)).fetchone()]
        require(not missing,"Unknown SKU(s): "+", ".join(missing)+". No rows changed.")
        for row in prepared:
            conn.execute("UPDATE products SET title=?,description=?,price_cents=?,compare_at_cents=?,alt=?,version=version+1 WHERE sku=?",row)
        conn.execute("INSERT INTO imports VALUES(?,?,?,?)",(digest,"catalog.csv",len(prepared),as_of(conn)))
        log(conn,"catalog.imported",digest,after={"rows":len(prepared)})
    return {"rows":len(prepared),"already_imported":False}

def csv_safe(value):
    # Prevent spreadsheet formula execution from untrusted imported labels.
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")): return "'"+value
    return value

def catalog_csv(conn):
    out=io.StringIO();w=csv.writer(out);w.writerow(["sku","title","description","price","compare_at_price","alt"])
    for p in rows(conn,"SELECT * FROM products ORDER BY sku"):
        w.writerow([csv_safe(p["sku"]),csv_safe(p["title"]),csv_safe(p["description"]),f'{p["price_cents"]/100:.2f}',f'{p["compare_at_cents"]/100:.2f}',csv_safe(p["alt"])])
    return out.getvalue()
