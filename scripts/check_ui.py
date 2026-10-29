"""Optional JS/API contract smoke test. Requires Node 18+; no npm packages."""
import shutil
import subprocess
import tempfile
import threading
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from merchops.seed import seed
from merchops.server import make_server

def main():
    node=shutil.which('node')
    if not node:raise SystemExit('Install Node 18+ to run this optional JS contract check. The application itself only needs Python.')
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/'ui.sqlite3';seed(db)
        server=make_server(db,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=subprocess.run([node,str(Path(__file__).resolve().parents[1]/'tests'/'ui-smoke.cjs'),f'http://127.0.0.1:{server.server_port}'],timeout=60)
            if result.returncode:raise SystemExit(result.returncode)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
