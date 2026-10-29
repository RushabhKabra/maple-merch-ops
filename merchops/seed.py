"""Deterministic synthetic retail data. No customer or employer data."""
import csv
import random
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from .db import ROOT, DEFAULT_DB, connect, initialize, transaction

AS_OF = date(2026, 10, 26)
CHANNELS = ["Organic Search", "Paid Social", "Email", "Direct"]

def records():
    rng = random.Random(4483176791)
    specs = [
        ("MUG-001","Everyday ceramic mug","Drinkware",1895,650,82),
        ("MUG-002","Campfire enamel mug","Drinkware",2295,850,0),
        ("TUM-001","Maple travel tumbler","Drinkware",3295,1200,6),
        ("TUM-002","Cold brew glass cup","Drinkware",2495,900,71),
        ("BOT-001","Trail water bottle","Drinkware",3495,1350,48),
        ("APP-001","Everyday crewneck","Apparel",5495,2200,92),
        ("APP-002","Weekend hoodie","Apparel",6995,2800,32),
        ("APP-003","Coffee club tee","Apparel",2995,1000,4),
        ("HAT-001","Classic canvas cap","Accessories",2495,850,62),
        ("TOTE-001","Market canvas tote","Accessories",1995,600,120),
        ("PIN-001","Coffee enamel pin","Accessories",995,250,130),
        ("KEY-001","Maple keyring","Accessories",1295,350,88),
        ("GFT-001","Morning ritual gift set","Gifts",5995,2400,21),
        ("GFT-002","Cozy weekend gift box","Gifts",7995,3200,10),
        ("HOL-001","Winter ceramic mug","Drinkware",2495,900,90),
        ("HOL-002","Winter knit beanie","Apparel",2795,1050,65),
    ]
    products, assets = [], []
    for i,(sku,title,category,price,cost,stock) in enumerate(specs):
        draft = sku.startswith("HOL")
        image = f"/assets/{sku}.svg"
        description = f"{title} for slow mornings and everyday adventures. Designed for our independent Canadian coffee merchandise demo. See care instructions before use."
        products.append(dict(sku=sku,handle=title.lower().replace(" ","-"),title=title,
          description="" if sku=="APP-003" else description,
          collection="Winter Collection" if draft else ("Gift Edit" if category=="Gifts" else "Everyday Collection"),
          category=category,price_cents=price+300 if sku=="TUM-001" else price,
          compare_at_cents=price-100 if sku=="GFT-002" else 0,expected_price_cents=price,
          cost_cents=cost,status="draft" if draft else "active",inventory=stock,
          lead_days=14 if category=="Apparel" else 10,image=image,
          alt="" if sku=="HAT-001" else title+" on a cream background",version=1))
        assets.append(dict(id=f"AST-{i+1:03}",sku=sku,filename=image,width=600 if sku=="TUM-002" else 1200,
          height=600 if sku=="TUM-002" else 1200,approved=0 if sku=="HOL-002" else 1,
          rights="pending" if sku=="HOL-002" else "Original demo illustration",
          owner="Creative & Storytelling",sample_status="In transit" if sku=="HOL-002" else "Received",
          shoot_date="2026-10-28" if sku=="HOL-002" else "2026-10-15"))
    customers=[dict(id=f"CUS-{i:03}",email=f"shopper{i:03}@example.com",first_name=f"Demo {i}",
       email_consent=int(i%4!=0),consent_at="2026-08-15T12:00:00+00:00" if i%4 else None) for i in range(1,181)]
    orders,lines=[],[]
    counts=Counter()
    active=products[:14]
    oid=1000
    for day_index in range(60):
        day=AS_OF-timedelta(days=59-day_index)
        for _ in range(rng.randint(10,23)+(7 if day_index>44 else 0)):
            oid+=1
            channel=rng.choices(CHANNELS,[36,24,23,17])[0]
            cancelled=rng.random()<0.035
            fulfillment="delivered" if day_index<54 else rng.choices(["open","hold","shipped"],[5,1,5])[0]
            if cancelled: fulfillment="open"
            placed=f"{day}T{rng.randint(8,20):02}:00:00+00:00"
            orders.append(dict(id=f"MM-{oid}",placed_at=placed,customer_id=rng.choice(customers)["id"],
              channel=channel,status="cancelled" if cancelled else "paid",fulfillment=fulfillment,
              shipping_cents=0 if rng.random()<.5 else 795,tax_cents=0,
              fulfilled_at=f"{day+timedelta(days=1)}T16:00:00+00:00" if fulfillment in ("shipped","delivered") else None,
              session_id=None,idempotency_key=None))
            if not cancelled: counts[(str(day),channel)]+=1
            for j,p in enumerate(rng.sample(active,rng.choices([1,2,3],[6,3,1])[0])):
                qty=rng.choices([1,2,3],[8,2,1])[0]
                discount=(p["expected_price_cents"]*qty//10) if channel=="Email" or rng.random()<.12 else 0
                returned=1 if day_index<50 and rng.random()<.045 else 0
                lines.append(dict(id=f"MM-{oid}-{j}",order_id=f"MM-{oid}",sku=p["sku"],quantity=qty,
                  returned=returned,unit_price_cents=p["expected_price_cents"],discount_cents=discount,unit_cost_cents=p["cost_cents"]))
    traffic=[]
    for day_index in range(60):
        day=str(AS_OF-timedelta(days=59-day_index))
        for channel in CHANNELS:
            buys=counts[(day,channel)]
            rate={"Email":.055,"Organic Search":.038,"Paid Social":.023,"Direct":.034}[channel]
            visits=max(buys,int((buys+2)/rate*rng.uniform(.85,1.15)))
            checkouts=max(buys,int(visits*.095))
            carts=max(checkouts,int(visits*.17))
            traffic.append(dict(date=day,channel=channel,sessions=visits,cart_sessions=carts,checkout_sessions=checkouts,purchase_sessions=buys))
    launches=[dict(id="LCH-001",title="Winter Collection",collection="Winter Collection",target_date="2026-10-30",owner="E-Commerce Manager",status="planning"),
              dict(id="LCH-002",title="Everyday Gift Edit",collection="Gift Edit",target_date="2026-11-06",owner="Category",status="planning")]
    launch_products=[dict(launch_id="LCH-001",sku=sku) for sku in ("HOL-001","HOL-002")]+[dict(launch_id="LCH-002",sku=sku) for sku in ("GFT-001","GFT-002")]
    task_specs=[("T01","LCH-001","Confirm product data and prices","Category","2026-10-23","done",None),
      ("T02","LCH-001","Receive and log beanie sample","Planning & Inventory","2026-10-24","in_progress",None),
      ("T03","LCH-001","Complete photography and rights approval","Creative & Storytelling","2026-10-27","todo","T02"),
      ("T04","LCH-001","Review collection page and mobile checkout","E-Commerce","2026-10-29","todo","T03"),
      ("T05","LCH-001","Approve launch email preview","CRM","2026-10-29","todo","T04"),
      ("T06","LCH-002","Review gift pricing and promotion","Category","2026-11-02","in_progress",None),
      ("T07","LCH-002","Confirm gift inventory allocation","Planning & Inventory","2026-11-03","todo",None)]
    tasks=[dict(zip(["id","launch_id","title","owner","due_date","status","depends_on"],t)) for t in task_specs]
    carts=[dict(id=f"CRT-{i:03}",customer_id=c["id"],sku=active[i%14]["sku"],created_at=f"2026-10-{24 if i%3 else 25}T12:00:00+00:00",converted=int(i%5==0)) for i,c in enumerate(customers[:65],1)]
    promotions=[dict(code="MAPLE10",percent=10,start_date="2026-10-01",end_date="2026-11-15",collection="Everyday Collection")]
    return dict(products=products,assets=assets,customers=customers,orders=orders,order_lines=lines,
      traffic=traffic,launches=launches,launch_products=launch_products,tasks=tasks,carts=carts,promotions=promotions)

def generate_assets(data):
    palette={"Drinkware":"#a45b42","Apparel":"#566b59","Accessories":"#b89562","Gifts":"#765e73"}
    for p in data["products"]:
        color=palette[p["category"]]
        if p["category"]=="Drinkware":
            shape=f'<rect x="365" y="340" width="390" height="470" rx="55" fill="{color}"/><path d="M755 420h95q120 130 0 250h-95" fill="none" stroke="{color}" stroke-width="55"/>'
        elif p["category"]=="Apparel":
            shape=f'<path d="M420 320l-180 130 120 170 80-50v300h340V570l80 50 120-170-180-130-100 60-100-60z" fill="{color}"/>'
        elif p["category"]=="Gifts":
            shape=f'<rect x="300" y="430" width="600" height="400" rx="12" fill="{color}"/><rect x="270" y="380" width="660" height="90" rx="12" fill="{color}"/><path d="M600 380v450M330 625h540" stroke="#f2dfbf" stroke-width="55"/>'
        else:
            shape=f'<rect x="350" y="420" width="500" height="430" rx="35" fill="{color}"/><path d="M455 435v-75a145 145 0 0 1 290 0v75" fill="none" stroke="{color}" stroke-width="35"/>'
        size=600 if p["sku"]=="TUM-002" else 1200
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 1200 1200"><rect width="1200" height="1200" fill="#f3eee4"/><ellipse cx="600" cy="935" rx="320" ry="35" fill="#e5dccd"/>{shape}<text x="600" y="625" text-anchor="middle" fill="#fff8ed" font-family="Arial,sans-serif" font-size="36" letter-spacing="7">MAPLE</text><text x="600" y="1090" text-anchor="middle" fill="#796d5e" font-family="Arial,sans-serif" font-size="22">ORIGINAL DEMO ILLUSTRATION</text></svg>'
        (ROOT/"web"/"assets"/f'{p["sku"]}.svg').write_text(svg)
        if p["sku"]=="TUM-002":
            examples=ROOT/"examples";examples.mkdir(exist_ok=True)
            (examples/"TUM-002-reshoot.svg").write_text(svg.replace('width="600" height="600"','width="1200" height="1200"'))

def seed(path=DEFAULT_DB, reset=False):
    path=Path(path)
    if path.exists():
        with connect(path) as conn:
            try:
                if conn.execute("SELECT count(*) FROM products").fetchone()[0] and not reset:
                    return False
            except Exception:
                pass
        if reset: path.unlink()
    initialize(path)
    data=records()
    raw=ROOT/"data"/"raw"
    raw.mkdir(parents=True,exist_ok=True)
    with transaction(path) as conn:
        conn.executemany("INSERT OR REPLACE INTO settings VALUES(?,?)",[("as_of",str(AS_OF)),("source","Synthetic portfolio dataset; seed 4483176791"),("schema_version","1")])
        for table,items in data.items():
            columns=list(items[0])
            sql=f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})'
            conn.executemany(sql,[[item[c] for c in columns] for item in items])
            with (raw/f"{table}.csv").open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(items)
    generate_assets(data)
    return True
