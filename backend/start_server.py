import os
import signal
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("start_server")

logger.info("Pre-importing application modules...")
from app.main import app

logger.info("Application modules loaded — killing health placeholder...")
pid_file = "/tmp/brainsuite_health.pid"
try:
    with open(pid_file) as f:
        pid = int(f.read().strip())
    os.kill(pid, signal.SIGTERM)
except (FileNotFoundError, ValueError, ProcessLookupError, OSError):
    pass
try:
    os.unlink(pid_file)
except OSError:
    pass

port = int(os.environ.get("BACKEND_PORT", "5000"))
import socket
for attempt in range(10):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", port))
        s.close()
        break
    except OSError:
        if attempt < 9:
            time.sleep(0.2)
        else:
            logger.warning("Port %s still occupied after retries, proceeding anyway", port)

logger.info("Starting uvicorn on port %s...", port)
import uvicorn
uvicorn.run(
    app,
    host="0.0.0.0",
    port=port,
    log_level="info",
    timeout_keep_alive=120,
    workers=1,
)
