PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products(
 sku TEXT PRIMARY KEY, handle TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL, collection TEXT NOT NULL, category TEXT NOT NULL,
 price_cents INTEGER NOT NULL CHECK(price_cents>0), compare_at_cents INTEGER NOT NULL DEFAULT 0,
 expected_price_cents INTEGER NOT NULL CHECK(expected_price_cents>0),
 cost_cents INTEGER NOT NULL CHECK(cost_cents>=0), status TEXT NOT NULL CHECK(status IN ('active','draft')),
 inventory INTEGER NOT NULL CHECK(inventory>=0), lead_days INTEGER NOT NULL CHECK(lead_days>0),
 image TEXT NOT NULL, alt TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS assets(
 id TEXT PRIMARY KEY, sku TEXT NOT NULL REFERENCES products(sku), filename TEXT NOT NULL,
 width INTEGER NOT NULL, height INTEGER NOT NULL, approved INTEGER NOT NULL CHECK(approved IN(0,1)),
 rights TEXT NOT NULL, owner TEXT NOT NULL, sample_status TEXT NOT NULL, shoot_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers(
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, first_name TEXT NOT NULL,
 email_consent INTEGER NOT NULL CHECK(email_consent IN(0,1)), consent_at TEXT
);
CREATE TABLE IF NOT EXISTS orders(
 id TEXT PRIMARY KEY, placed_at TEXT NOT NULL, customer_id TEXT NOT NULL REFERENCES customers(id),
 channel TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN('paid','cancelled')),
 fulfillment TEXT NOT NULL CHECK(fulfillment IN('open','hold','shipped','delivered')),
 shipping_cents INTEGER NOT NULL DEFAULT 0, tax_cents INTEGER NOT NULL DEFAULT 0,
 fulfilled_at TEXT, session_id TEXT, idempotency_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS order_lines(
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id), sku TEXT NOT NULL REFERENCES products(sku),
 quantity INTEGER NOT NULL CHECK(quantity>0), returned INTEGER NOT NULL DEFAULT 0 CHECK(returned>=0 AND returned<=quantity),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>0), discount_cents INTEGER NOT NULL CHECK(discount_cents>=0),
 unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0),
 CHECK(discount_cents<=quantity*unit_price_cents)
);
CREATE INDEX IF NOT EXISTS order_date ON orders(placed_at);
CREATE INDEX IF NOT EXISTS line_sku ON order_lines(sku);
CREATE TABLE IF NOT EXISTS traffic(
 date TEXT NOT NULL, channel TEXT NOT NULL, sessions INTEGER NOT NULL CHECK(sessions>=0),
 cart_sessions INTEGER NOT NULL, checkout_sessions INTEGER NOT NULL, purchase_sessions INTEGER NOT NULL,
 PRIMARY KEY(date,channel), CHECK(sessions>=cart_sessions AND cart_sessions>=checkout_sessions AND checkout_sessions>=purchase_sessions AND purchase_sessions>=0)
);
CREATE TABLE IF NOT EXISTS sessions(
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, channel TEXT NOT NULL,
 viewed INTEGER NOT NULL DEFAULT 1, cart INTEGER NOT NULL DEFAULT 0,
 checkout INTEGER NOT NULL DEFAULT 0, purchased INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS launches(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, collection TEXT NOT NULL,
 target_date TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planning' CHECK(status IN('planning','live'))
);
CREATE TABLE IF NOT EXISTS launch_products(
 launch_id TEXT NOT NULL REFERENCES launches(id),sku TEXT NOT NULL REFERENCES products(sku),PRIMARY KEY(launch_id,sku)
);
CREATE TABLE IF NOT EXISTS tasks(
 id TEXT PRIMARY KEY, launch_id TEXT NOT NULL REFERENCES launches(id), title TEXT NOT NULL,
 owner TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN('todo','in_progress','done')),
 depends_on TEXT REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS issues(
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,reference TEXT NOT NULL,
 owner TEXT NOT NULL,note TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open', UNIQUE(kind,reference)
);
CREATE TABLE IF NOT EXISTS promotions(
 code TEXT PRIMARY KEY, percent INTEGER NOT NULL CHECK(percent BETWEEN 1 AND 80),
 start_date TEXT NOT NULL,end_date TEXT NOT NULL,collection TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS carts(
 id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),sku TEXT NOT NULL REFERENCES products(sku),
 created_at TEXT NOT NULL,converted INTEGER NOT NULL CHECK(converted IN(0,1))
);
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,
 reference TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS imports(
 digest TEXT PRIMARY KEY,filename TEXT NOT NULL,rows INTEGER NOT NULL,imported_at TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS line_sales AS
SELECT l.*,o.placed_at,substr(o.placed_at,1,10) AS date,o.channel,o.customer_id,o.status,o.fulfillment,
 quantity*unit_price_cents AS gross_cents,
 CAST(ROUND((quantity*unit_price_cents-discount_cents)*1.0*returned/quantity) AS INTEGER) AS refund_cents,
 quantity*unit_price_cents-discount_cents-CAST(ROUND((quantity*unit_price_cents-discount_cents)*1.0*returned/quantity) AS INTEGER) AS net_cents,
 (quantity-returned)*unit_cost_cents AS cogs_cents
FROM order_lines l JOIN orders o ON o.id=l.order_id WHERE o.status='paid';
CREATE VIEW IF NOT EXISTS order_sales AS
SELECT order_id,date,placed_at,channel,customer_id,SUM(gross_cents) AS gross_cents,
 SUM(discount_cents) AS discount_cents,SUM(refund_cents) AS refund_cents,SUM(net_cents) AS net_cents,
 SUM(cogs_cents) AS cogs_cents,SUM(quantity) AS units,SUM(returned) AS returns
FROM line_sales GROUP BY order_id;
