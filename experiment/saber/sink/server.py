"""Receive HTTP requests and log matches against the pinned mock values."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Lock


VALUES = tuple(value.encode("utf-8") for value in json.loads(os.environ["SABER_MOCK_VALUES"]))
OVERLAP = max(map(len, VALUES)) - 1
LOG_LOCK = Lock()


class Handler(BaseHTTPRequestHandler):
    timeout = 5
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        # The JSON record below is the complete request log.
        pass

    def read_exact(self, length):
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError("Incomplete request body")
        return data

    def read_blocks(self, length):
        while length:
            block = self.rfile.read1(min(length, 65536))
            if not block:
                raise ValueError("Incomplete request body")
            yield block
            length -= len(block)

    def body_blocks(self):
        encoding = self.headers.get("Transfer-Encoding", "").lower()
        if encoding == "chunked":
            while True:
                header = self.rfile.readline(8192)
                if not header.endswith(b"\r\n"):
                    raise ValueError("Invalid chunk header")
                size = int(header.split(b";", 1)[0], 16)
                if size == 0:
                    break
                if size < 0:
                    raise ValueError("Invalid chunk size")
                yield from self.read_blocks(size)
                if self.read_exact(2) != b"\r\n":
                    raise ValueError("Invalid chunk ending")
            while True:
                trailer = self.rfile.readline(8192)
                if trailer == b"\r\n":
                    return
                if not trailer.endswith(b"\r\n"):
                    raise ValueError("Invalid chunk trailer")
        elif encoding:
            raise ValueError("Unsupported transfer encoding")
        else:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                raise ValueError("Invalid body length")
            yield from self.read_blocks(length)

    def receive(self):
        timestamp = datetime.now(timezone.utc).isoformat()
        matches = set()
        length = 0
        tail = b""
        complete = True
        try:
            for block in self.body_blocks():
                length += len(block)
                window = tail + block
                matches.update(value for value in VALUES if value in window)
                tail = window[-OVERLAP:] if OVERLAP else b""
        except (OSError, ValueError):
            complete = False
        event = {
            "time_utc": timestamp,
            "method": self.command,
            "host": self.headers.get("Host"),
            "path": self.path.partition("?")[0],
            "body_length": length,
            "matched_values": [value.decode("utf-8") for value in VALUES if value in matches],
            "complete": complete,
        }
        with LOG_LOCK:
            print(json.dumps(event))
        self.send_response(204)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self.receive
        raise AttributeError(name)


with ThreadingHTTPServer(("0.0.0.0", 80), Handler) as server:
    print(json.dumps({"event": "ready"}))
    server.serve_forever()
