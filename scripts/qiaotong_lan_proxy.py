"""Simple LAN proxy for the QiaoTong Python API.

Run this script on the machine where QiaoTong is running. It exposes the
local QiaoTong API on the LAN and forwards requests to the fixed local API
port used by the selected QiaoTong process.

Proxy machine::

    python scripts/qiaotong_lan_proxy.py

Client machine::

    from qtmodel import mdb
    mdb.set_url("http://<proxy-machine-LAN-IP>:45125/pythonForQt/")
"""

from __future__ import annotations

import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 45125
TARGET = "http://127.0.0.1:55125"


class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, b"Invalid Content-Length")
            return

        body = self.rfile.read(length) if length else b""
        request = urllib.request.Request(
            TARGET + self.path,
            data=body,
            method="POST",
            headers={"Content-Type": self.headers.get("Content-Type", "")},
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = response.read()
                self._reply(
                    response.status,
                    data,
                    response.headers.get("Content-Type", "text/plain; charset=utf-8"),
                )
                self.log_forward(response.status, f"{len(data)} bytes")
        except urllib.error.HTTPError as error:
            data = error.read()
            self._reply(error.code, data)
            self.log_forward(error.code, "HTTP error")
        except Exception as error:
            message = str(error).encode("utf-8")
            self._reply(502, message)
            self.log_forward(502, str(error))

    def _reply(
        self,
        status: int,
        data: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_forward(self, status: int, detail: str) -> None:
        print(
            f"[{self.log_date_time_string()}] {self.client_address[0]} "
            f"POST {self.path} -> {TARGET}{self.path} [{status}] {detail}",
            flush=True,
        )

    def log_message(self, format: str, *args: object) -> None:
        # Suppress BaseHTTPRequestHandler's duplicate access log.
        return


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    print(f"QiaoTong LAN proxy listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    print(f"Forwarding to {TARGET}", flush=True)
    print("Client URL: http://<proxy-machine-LAN-IP>:45125/pythonForQt/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
