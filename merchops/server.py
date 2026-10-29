"""Loopback-only, dependency-free demonstration server. Not production hosting."""
import json
import mimetypes
import secrets
import sqlite3
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from .db import ROOT, as_of, connect, rows
from . import services as s
from .reporting import export_data, manager_brief, report_csv

def make_server(path,port=8765):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):
            print(f"{self.command} {self.path.split('?')[0]} {args[1] if len(args)>1 else ''}",flush=True)

        def reply(self,body,status=200,mime="application/json",filename=None):
            if mime=="application/json": body=json.dumps(body,allow_nan=False).encode()
            elif isinstance(body,str): body=body.encode()
            self.send_response(status)
            self.send_header("Content-Type",mime+("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Content-Length",str(len(body)))
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Referrer-Policy","same-origin")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            if filename: self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
            self.end_headers();self.wfile.write(body)

        def host_ok(self):
            host=self.headers.get("Host","")
            return host in (f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}")

        def do_GET(self):
            try:
                s.require(self.host_ok(),"Use the local 127.0.0.1 URL.",403)
                parsed=urlparse(self.path);route=parsed.path;q={k:v[0] for k,v in parse_qs(parsed.query).items()}
                if route.startswith("/api/"):
                    with connect(path) as conn:
                        if route=="/api/bootstrap": return self.reply(dict(token=token,as_of=as_of(conn),mode="Synthetic demo",version="1.0.0"))
                        if route=="/api/summary": return self.reply(s.summary(conn,q.get("start"),q.get("end"),q.get("channel")))
                        if route=="/api/products": return self.reply(rows(conn,"SELECT * FROM products ORDER BY sku"))
                        if route=="/api/performance": return self.reply(s.product_performance(conn,q.get("start"),q.get("end")))
                        if route=="/api/operations": return self.reply(dict(inventory=s.inventory(conn),findings=s.audits(conn),fulfillment=s.fulfillment(conn),launches=s.launches(conn),assets=rows(conn,"SELECT a.*,p.title FROM assets a JOIN products p ON p.sku=a.sku ORDER BY approved,sku"),issues=rows(conn,"SELECT * FROM issues ORDER BY id DESC")))
                        if route=="/api/crm": return self.reply(s.crm(conn))
                        if route=="/api/audit": return self.reply(rows(conn,"SELECT * FROM audit_log ORDER BY id DESC LIMIT 200"))
                        if route=="/api/catalog.csv": return self.reply(s.catalog_csv(conn),mime="text/csv",filename="catalog.csv")
                        if route=="/api/report.csv":
                            kind=q.get("kind","sales");s.require(kind in ("sales","lines","products","inventory","issues","segments","excel-lines","excel-orders","excel-traffic","excel-products"),"Unknown report.")
                            return self.reply(report_csv(conn,kind,q.get("start"),q.get("end")),mime="text/csv",filename=f"{kind}.csv")
                        if route=="/api/export.json": return self.reply(export_data(conn),filename="report_data.json")
                        if route=="/api/brief.md": return self.reply(manager_brief(conn),mime="text/markdown",filename="manager_brief.md")
                        raise s.Problem("Endpoint not found.",404)
                if route=="/": filename=ROOT/"web"/"index.html"
                elif route=="/shop": filename=ROOT/"web"/"shop.html"
                elif route=="/reports/Maple_Merch_Reporting.xlsx": filename=ROOT/"reports"/"Maple_Merch_Reporting.xlsx"
                else:
                    filename=(ROOT/"web"/unquote(route).lstrip("/")).resolve()
                    s.require(filename.is_relative_to((ROOT/"web").resolve()),"Not found.",404)
                s.require(filename.is_file(),"File not found.",404)
                self.reply(filename.read_bytes(),mime=mimetypes.guess_type(filename)[0] or "application/octet-stream")
            except s.Problem as exc:self.reply({"error":str(exc)},exc.status)
            except (ValueError,TypeError):self.reply({"error":"Invalid request parameters."},400)
            except Exception as exc:
                print(f"Server error: {type(exc).__name__}: {exc}",flush=True)
                self.reply({"error":"Unexpected local server error. See the terminal."},500)

        def do_POST(self):
            self.mutate()

        def do_PATCH(self):
            self.mutate()

        def mutate(self):
            try:
                s.require(self.host_ok(),"Use the local 127.0.0.1 URL.",403)
                origin=self.headers.get("Origin")
                s.require(not origin or origin in (f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"),"Cross-origin request denied.",403)
                s.require(secrets.compare_digest(self.headers.get("X-Merch-Token",""),token),"Missing local session token. Refresh the page.",403)
                s.require(self.headers.get("Content-Type","").split(";")[0]=="application/json","Use application/json.",415)
                try: size=int(self.headers.get("Content-Length","0"))
                except ValueError: raise s.Problem("Invalid body length.")
                s.require(0<size<=1_100_000,"Request body must be under 1.1 MB.",413)
                try: payload=json.loads(self.rfile.read(size))
                except (json.JSONDecodeError,UnicodeDecodeError): raise s.Problem("Body is not valid JSON.")
                s.require(isinstance(payload,dict),"Body must be a JSON object.")
                route=urlparse(self.path).path;parts=route.strip("/").split("/")
                result=None
                if self.command=="PATCH" and len(parts)==3 and parts[:2]==["api","products"]: result=s.change_product(path,parts[2],payload)
                elif self.command=="PATCH" and len(parts)==3 and parts[:2]==["api","tasks"]: result=s.update_task(path,parts[2],payload.get("status"))
                elif self.command=="PATCH" and len(parts)==3 and parts[:2]==["api","assets"]: result=s.update_asset(path,parts[2],payload)
                elif self.command=="POST" and route=="/api/checkout": result=s.checkout(path,payload)
                elif self.command=="POST" and route=="/api/events": result=s.session_event(path,payload)
                elif self.command=="POST" and route=="/api/import": result=s.import_catalog(path,payload.get("csv"))
                elif self.command=="POST" and route=="/api/receive": result=s.receive_stock(path,payload.get("sku"),payload.get("quantity"),payload.get("note"))
                elif self.command=="POST" and route=="/api/issues": result=s.assign_issue(path,payload)
                elif self.command=="POST" and route=="/api/assets/upload": result=s.upload_asset(path,payload)
                elif self.command=="POST" and len(parts)==4 and parts[:2]==["api","assets"] and parts[3]=="select": result=s.select_asset(path,parts[2])
                elif self.command=="POST" and len(parts)==4 and parts[:2]==["api","launches"] and parts[3]=="publish": result=s.publish_launch(path,parts[2])
                elif self.command=="POST" and len(parts)==4 and parts[:2]==["api","orders"] and parts[3]=="fulfill": result=s.fulfill_order(path,parts[2])
                else: raise s.Problem("Endpoint not found.",404)
                self.reply(result)
            except s.Problem as exc:self.reply({"error":str(exc)},exc.status)
            except (TypeError,ValueError,KeyError):self.reply({"error":"Invalid input fields."},400)
            except sqlite3.IntegrityError:self.reply({"error":"Data constraint failed. No changes were committed."},409)
            except Exception as exc:
                print(f"Server error: {type(exc).__name__}: {exc}",flush=True)
                self.reply({"error":"Unexpected local server error. See the terminal."},500)
    return ThreadingHTTPServer(("127.0.0.1",port),Handler)
