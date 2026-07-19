"""Shared test helpers: a Range-capable local HTTP server."""
import functools
import http.server
import threading
from pathlib import Path


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().do_GET()
        try:
            unit, span = rng.split("=")
            start_s, end_s = span.split("-")
            start = int(start_s)
        except ValueError:
            self.send_error(400)
            return
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)
        self.send_response(206)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            self.wfile.write(f.read(end - start + 1))

    def log_message(self, *a):
        pass


def serve(directory: Path):
    """Start a threading HTTP server on an ephemeral port. Returns (server, base_url)."""
    handler = functools.partial(RangeHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
