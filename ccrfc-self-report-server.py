#!/usr/bin/env python3
"""ccrfc-self-report-server.py — reference implementation for the CCF provider self-report.

Serves the provider's self-report JSON at /.well-known/ccrfc-report (one of the
"two doors" in CCRFC-003 / PROVIDER_README.md). Stdlib only, no dependencies.

Behavior:
  GET /.well-known/ccrfc-report -> 200 with the report JSON.
    The report's own `report_checksum` is sent back as the HTTP ETag, so
    clients get the checksum-match / mismatch-refetch dance for free:
    a matching If-None-Match header yields 304, anything else re-serves.
  POST /handshake -> 200 with the in-handshake declaration (second door).
    Body carries {"report_checksum": "<held>"} or {} on first contact.
    Match yields {"status": 304}; first contact or mismatch yields the
    full report. Both doors serve byte-identical payloads per CCRFC-003.
  Anything else -> 404, clean, no body sniffing.

On startup the server recomputes report_checksum over the canonical JSON
(sort_keys, separators (",", ":"), UTF-8, without report_checksum itself) and
refuses to start if the file's checksum does not match — a provider must never
serve a report whose checksum lies, because clients treat the checksum as the
downgrade detector.

The second door (the in-handshake declaration) is served here as POST
/handshake carrying the same report bytes. The flag wire encoding for
per-interaction flags remains an open question (CCRFC-003); the
checksum-match / mismatch-refetch dance below is fully implemented on
both doors today.

Usage:
  python3 ccrfc-self-report-server.py --report report.json [--port 8000]
"""

import argparse
import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

WELL_KNOWN_PATH = "/.well-known/ccrfc-report"


def canonical_bytes(report_without_checksum):
    return json.dumps(
        report_without_checksum, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def verify_report(report):
    """Return (ok, recomputed_checksum)."""
    claimed = report.get("report_checksum", "")
    body = {k: v for k, v in report.items() if k != "report_checksum"}
    recomputed = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return claimed == recomputed, recomputed


class Handler(BaseHTTPRequestHandler):
    report_text = b""
    etag = ""

    def log_message(self, fmt, *args):  # quieter than the default stderr chatter
        sys.stderr.write("ccrfc-report: " + fmt % args + "\n")

    def do_GET(self):
        if self.path != WELL_KNOWN_PATH:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.headers.get("If-None-Match") == self.etag:
            self.send_response(304)
            self.send_header("ETag", self.etag)
            self.end_headers()
            return
        payload = self.report_text
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("ETag", self.etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_HEAD(self):
        # Same headers as GET, no body — lets clients probe cheaply.
        if self.path != WELL_KNOWN_PATH:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(self.report_text)))
        self.send_header("ETag", self.etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_POST(self):
        # Second door: in-handshake declaration. Byte-identical report bytes.
        if self.path != "/handshake":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except Exception:
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        client_checksum = data.get("report_checksum")
        if client_checksum == self.etag.strip('"'):
            # checksum match: nothing changed
            body = json.dumps({"status": 304, "message": "still that",
                               "report_checksum": self.etag.strip('"')}).encode()
        else:
            # first contact (no checksum) or mismatch: full report
            body = self.report_text
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", self.etag)
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser(description="Serve a CCF self-report JSON.")
    ap.add_argument("--report", required=True, help="Path to the report JSON file.")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    with open(args.report, "r", encoding="utf-8") as f:
        report = json.load(f)

    ok, recomputed = verify_report(report)
    if not ok:
        sys.stderr.write(
            "REFUSING TO START: report_checksum mismatch.\n"
            "  claimed:     %s\n"
            "  recomputed:  %s\n"
            "Fix the file — clients treat this checksum as the downgrade detector.\n"
            % (report.get("report_checksum", ""), recomputed)
        )
        sys.exit(1)

    # Serve the file's own bytes (checksum included) verbatim.
    with open(args.report, "rb") as f:
        Handler.report_text = f.read()
    Handler.etag = '"%s"' % report["report_checksum"]

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    sys.stderr.write(
        "Serving CCF self-report at http://127.0.0.1:%d%s (checksum %s)\n"
        % (args.port, WELL_KNOWN_PATH, report["report_checksum"][:16])
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
