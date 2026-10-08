"""Local dashboard server. All analysis runs against the saved dataset."""

from __future__ import annotations

import json
import mimetypes
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .analysis import analyze, backtest, generate_sets
from .data import DEFAULT_DATA, DEFAULT_SOURCES, ROOT, draws_csv, load_draws

DISCLAIMER = "Historical patterns do not predict future draws. Every six-number set has a 1 in 8,145,060 first-prize chance in a fair draw."


def integer(query, name, default, minimum, maximum):
    try:
        value = int(query.get(name, [default])[0])
    except (ValueError, TypeError, IndexError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


class Application:
    def __init__(self, data_path=DEFAULT_DATA, sources_path=DEFAULT_SOURCES):
        self.draws = load_draws(data_path)
        self.sources_path = Path(sources_path)
        self.first = self.draws[0]["round"]
        self.last = self.draws[-1]["round"]

    @lru_cache(maxsize=12)
    def analysis(self, start, end, window):
        selected = [d for d in self.draws if start <= d["round"] <= end]
        result = analyze(selected, window=window)
        # Full combination counts are available in the exported analysis report.
        for name in ("pairs", "triples"):
            result[name] = {k: v for k, v in result[name].items() if k != "counts"}
        return result

    @lru_cache(maxsize=8)
    def evaluation(self, start, end, window):
        selected = [d for d in self.draws if d["round"] <= end]
        return backtest(selected, window=window, start_round=start)

    def api(self, path, query):
        if path == "/api/sources":
            if not self.sources_path.exists():
                return {"sources": [], "coverage_note": "Source manifest is missing. Run sync to restore provenance."}
            return json.loads(self.sources_path.read_text(encoding="utf-8-sig"))
        start = integer(query, "start", self.first, self.first, self.last)
        end = integer(query, "end", self.last, self.first, self.last)
        if start > end:
            raise ValueError("start must be less than or equal to end.")
        window = integer(query, "window", 50, 1, 10000)
        selected = [d for d in self.draws if start <= d["round"] <= end]
        if path == "/api/draws":
            return selected
        if path == "/api/analysis":
            return self.analysis(start, end, window)
        if path == "/api/generate":
            count = integer(query, "count", 5, 1, 100)
            seed = integer(query, "seed", 645, 0, 2**32 - 1)
            strategy = query.get("strategy", ["uniform"])[0]
            return {"sets": generate_sets(selected, count=count, strategy=strategy, seed=seed, window=window),
                    "strategy": strategy, "seed": seed, "through_round": end, "note": DISCLAIMER}
        if path == "/api/backtest":
            return self.evaluation(start, end, window)
        if path == "/api/export.csv":
            return draws_csv(selected)
        raise KeyError(path)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            try:
                if parsed.path.startswith("/api/"):
                    result = app.api(parsed.path, parse_qs(parsed.query, keep_blank_values=True))
                    if isinstance(result, str):
                        self.send_body(200, result.encode("utf-8-sig"), "text/csv; charset=utf-8")
                    else:
                        body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
                        self.send_body(200, body, "application/json; charset=utf-8")
                    return
                assets = {"/": "index.html", "/index.html": "index.html", "/styles.css": "styles.css", "/app.js": "app.js"}
                filename = assets.get(parsed.path)
                if not filename:
                    raise KeyError(parsed.path)
                asset = ROOT / "web" / filename
                if not asset.is_file():
                    raise KeyError(parsed.path)
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                self.send_body(200, asset.read_bytes(), content_type + "; charset=utf-8")
            except (OSError, json.JSONDecodeError):
                self.send_body(500, b'{"error":"Could not read local data. Check the dataset and source manifest."}', "application/json")
            except ValueError as exc:
                self.send_body(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            except KeyError:
                self.send_body(404, b'{"error":"Not found"}', "application/json")

    return Handler


def serve(host="127.0.0.1", port=6450, data_path=DEFAULT_DATA):
    app = Application(data_path, Path(data_path).with_name("sources.json"))
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"Lotto 6/45 Lab: http://{host}:{server.server_port}", flush=True)
    print(f"Loaded {len(app.draws):,} draws ({app.first}-{app.last}). Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
