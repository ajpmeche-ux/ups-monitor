from __future__ import annotations

import collections
import json
import platform
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Deque, Optional

from .logger import CSVLogger
from .models import UPSMetrics
from .parser import get_ups_metrics

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="5">
  <title>UPS Monitor</title>
  <style>
    body{{font-family:monospace;background:#111;color:#eee;padding:20px;margin:0}}
    h2{{margin-bottom:16px}}
    .badge{{display:inline-block;padding:5px 14px;border-radius:6px;font-weight:bold;background:{status_color}}}
    .metric{{margin:8px 0;font-size:1.1em}}
    .sub{{font-size:.85em;color:#888;margin-top:12px}}
    table{{border-collapse:collapse;width:100%;margin-top:20px;max-width:640px}}
    th,td{{border:1px solid #333;padding:5px 12px;text-align:right}}
    th{{background:#222;text-align:center}}
    tr:nth-child(even){{background:#1a1a1a}}
    a{{color:#8fc31f}}
  </style>
</head>
<body>
  <h2>UPS Monitor</h2>
  <p><span class="badge">{status_text}</span></p>
  <p class="metric">AC Input: <b>{voltage}</b> <span style="color:#888;font-size:.85em">(120 V = on AC, 0 V = on battery)</span></p>
  <p class="metric">UPS Load: <b>{load}</b> <span style="color:#888;font-size:.85em">(equipment draw as % of UPS capacity)</span></p>
  <p class="sub">Last update: {timestamp} &nbsp;|&nbsp; Auto-refreshes every 5&nbsp;s &nbsp;|&nbsp; <a href="/api/metrics">JSON API</a></p>
  <table>
    <tr><th>Timestamp</th><th>Voltage (V)</th><th>Load (%)</th></tr>
    {rows}
  </table>
</body>
</html>"""


class UPSDaemon:
    def __init__(
        self,
        poll_interval: float = 2.0,
        port: int = 8765,
        csv_file: str = "ups_metrics.csv",
        debug: bool = False,
    ) -> None:
        self._poll_interval = poll_interval
        self._port = port
        self._debug = debug
        self._samples: Deque[UPSMetrics] = collections.deque(maxlen=50)
        self._connected = False
        self._lock = threading.Lock()
        self._logger = CSVLogger(csv_file)
        self._stop_event = threading.Event()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                raw = get_ups_metrics(debug=self._debug)
                connected = bool(raw)
                with self._lock:
                    self._connected = connected
                    if raw:
                        m = UPSMetrics(
                            timestamp=datetime.now(),
                            voltage=float(raw["Voltage"]),
                            load=float(raw["Load"]),
                        )
                        self._samples.append(m)
                        self._logger.log(m)
            except Exception as exc:
                if self._debug:
                    print(f"[daemon] poll error: {exc}")

            elapsed = 0.0
            while not self._stop_event.is_set() and elapsed < self._poll_interval:
                time.sleep(0.1)
                elapsed += 0.1

    def _make_handler(self) -> type:
        daemon = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                path = self.path.split("?")[0]
                if path == "/api/metrics":
                    self._serve_json()
                elif path in ("/", "/index.html"):
                    self._serve_html()
                else:
                    self.send_response(404)
                    self.end_headers()

            def _current_state(self):
                with daemon._lock:
                    return daemon._connected, list(daemon._samples)

            def _serve_json(self) -> None:
                connected, samples = self._current_state()
                latest = samples[-1] if samples else None
                data = {
                    "connected": connected,
                    "latest": {
                        "timestamp": latest.timestamp.isoformat(),
                        "voltage": latest.voltage,
                        "load": latest.load,
                    } if latest else None,
                    "history": [
                        {
                            "timestamp": s.timestamp.isoformat(),
                            "voltage": s.voltage,
                            "load": s.load,
                        }
                        for s in samples
                    ],
                }
                body = json.dumps(data, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_html(self) -> None:
                connected, samples = self._current_state()
                latest = samples[-1] if samples else None
                rows = "".join(
                    f"<tr><td>{s.timestamp.strftime('%H:%M:%S')}</td>"
                    f"<td>{s.voltage:.2f}</td><td>{s.load:.2f}</td></tr>"
                    for s in reversed(samples)
                )
                html = _HTML_TEMPLATE.format(
                    status_color="#2e7d32" if connected else "#b71c1c",
                    status_text="Connected" if connected else "Disconnected",
                    voltage=f"{latest.voltage:.2f} V" if latest else "—",
                    load=f"{latest.load:.2f} %" if latest else "—",
                    timestamp=latest.timestamp.strftime("%Y-%m-%d %H:%M:%S") if latest else "—",
                    rows=rows or "<tr><td colspan=3>No data yet</td></tr>",
                )
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args) -> None:
                pass

        return _Handler

    def run(self) -> None:
        if platform.system() != "Darwin":
            raise RuntimeError("UPS polling requires macOS.")

        self._logger.start()
        poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        poll_thread.start()

        server = HTTPServer(("", self._port), self._make_handler())
        print(f"UPS Monitor daemon started.")
        print(f"  HTTP dashboard : http://0.0.0.0:{self._port}/")
        print(f"  JSON API       : http://0.0.0.0:{self._port}/api/metrics")
        print("Press Ctrl+C to stop.")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self._stop_event.set()
            poll_thread.join(timeout=5.0)
            self._logger.stop()
            server.server_close()
