#!/usr/bin/env python3
"""Run with Python 3.10+. No third-party dependencies for the core project."""
import argparse
from pathlib import Path
from merchops.db import DEFAULT_DB
from merchops.seed import seed
from merchops.reporting import export_reports
from merchops.server import make_server

def main():
    parser=argparse.ArgumentParser(description="Maple Merch Ops — independent e-commerce portfolio demo")
    parser.add_argument("command",choices=["serve","seed","export"],nargs="?",default="serve")
    parser.add_argument("--db",type=Path,default=DEFAULT_DB)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--reset",action="store_true",help="Replace this project's local synthetic database")
    args=parser.parse_args()
    if args.reset and args.command!="seed": parser.error("--reset is supported only with the seed command.")
    seed(args.db,reset=args.reset)
    if args.command=="seed": print(f"Synthetic database ready: {args.db}");return
    if args.command=="export": print(f"Reports exported: {export_reports(args.db)}");return
    server=make_server(args.db,args.port)
    print(f"\nMaple Merch Ops\nOperations: http://127.0.0.1:{server.server_port}\nDemo shop:  http://127.0.0.1:{server.server_port}/shop\nData: synthetic. Checkout never charges a payment.\nPress Ctrl+C to stop.\n",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=="__main__": main()
