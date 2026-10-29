#!/usr/bin/env python3
"""
d3 Studio - server locale.

Serve d3_studio.html e inoltra a Ollama solo le chiamate necessarie
(/v1/systemone, /api/tags, /api/version). Usa solo la libreria standard.

Per i PDF usa gli strumenti di poppler, se installati (nessun pacchetto Python):
  sudo apt install poppler-utils      # fornisce pdftotext e pdftoppm
  /pdf/extract  -> testo di ogni pagina      /pdf/render -> pagine come immagini PNG

Uso:
  python3 d3_studio.py                      # Ollama su http://localhost:11434
  python3 d3_studio.py --ollama http://OLLAMA_HOST:11434 --port 8765 --open

Poi apri http://127.0.0.1:8765

Usage (EN): serves the d3_studio.html UI on 127.0.0.1 and forwards only the calls it
needs to Ollama. Standard library only; poppler-utils is optional (PDF input).
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

__version__ = "1.0.0"
HERE = Path(__file__).resolve().parent
HTML = HERE / "d3_studio.html"
MAX_BODY = 64 * 1024 * 1024  # 64 MiB (Ollama accetta fino a 32 MiB con immagini)
ALLOWED_GET = {"/api/tags", "/api/version"}
ALLOWED_POST = {"/v1/systemone"}


MISSING_POPPLER = ("%s non trovato: installa poppler-utils (sudo apt install poppler-utils) "
                   "e riavvia il server.")


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def pdf_extract(data: bytes) -> list:
    """Testo di ogni pagina, in ordine di lettura."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", src, "-"], capture_output=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:300] or "pdftotext ha fallito")
    pages = r.stdout.decode("utf-8", "replace").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def pdf_render(data: bytes, first: int, last: int, dpi: int) -> list:
    """Pagine first..last come PNG in base64."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        r = subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(first), "-l", str(last), src, os.path.join(d, "pg")],
                           capture_output=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:300] or "pdftoppm ha fallito")
        out = []
        for fn in sorted(glob.glob(os.path.join(d, "pg-*.png")), key=lambda x: int(re.search(r"-(\d+)\.png$", x).group(1))):
            with open(fn, "rb") as f:
                out.append({"page": int(re.search(r"-(\d+)\.png$", fn).group(1)), "png": base64.b64encode(f.read()).decode()})
        return out


def qint(q: dict, key: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int((q.get(key) or [default])[0])
    except ValueError:
        v = default
    return max(lo, min(hi, v))


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Connessione chiusa dal browser: normale, niente traceback.
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    server_version = "d3studio/1.0"

    # --- sicurezza: accetta solo richieste dal browser locale -----------------
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost", "[::1]"):
            return False
        origin = self.headers.get("Origin")
        if origin:
            allowed = {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }
            if origin not in allowed:
                return False
        return True

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> bool:
        """Scrive la risposta al browser. False se il browser ha gia' chiuso la connessione."""
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
            return False

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def log_message(self, fmt, *args):  # log compatto
        sys.stderr.write("[d3studio] " + (fmt % args) + "\n")

    # --- inoltro a Ollama -----------------------------------------------------
    def _forward(self, method: str, path: str, body: bytes | None):
        url = self.server.ollama.rstrip("/") + path
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        # 1) chiama Ollama; 2) solo dopo risponde al browser. Un errore nella scrittura
        #    verso il browser (pagina chiusa, Stop, ricarica) non e' un errore di Ollama.
        try:
            with urllib.request.urlopen(req, timeout=self.server.timeout_s) as r:
                status, data = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, data = e.code, e.read() or json.dumps({"error": str(e)}).encode()
        except Exception as e:  # noqa: BLE001
            status = 502
            data = json.dumps({"error": f"Ollama non raggiungibile su {self.server.ollama}: {e}"}).encode()
        if not self._send(status, data):
            sys.stderr.write("[d3studio] il browser ha chiuso la connessione prima della risposta (ignorato)\n")

    # --- PDF (poppler) --------------------------------------------------------
    def _pdf(self, path: str, query: dict):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self._json(413, {"error": f"PDF vuoto o oltre {MAX_BODY // (1024 * 1024)} MiB"})
        data = self.rfile.read(n)
        if not data.lstrip()[:5] == b"%PDF-":
            return self._json(400, {"error": "il file non sembra un PDF"})
        tool = "pdftotext" if path == "/pdf/extract" else "pdftoppm"
        if not have(tool):
            return self._json(501, {"error": MISSING_POPPLER % tool})
        try:
            if path == "/pdf/extract":
                return self._json(200, {"pages": pdf_extract(data)})
            first = qint(query, "first", 1, 1, 100000)
            last = qint(query, "last", first, first, first + 49)  # al massimo 50 pagine per chiamata
            return self._json(200, {"pages": pdf_render(data, first, last, qint(query, "dpi", 96, 50, 200))})
        except subprocess.TimeoutExpired:
            return self._json(504, {"error": "tempo scaduto nell'elaborazione del PDF"})
        except Exception as e:  # noqa: BLE001
            return self._json(422, {"error": f"PDF non elaborabile: {e}"})

    # --- metodi ---------------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "host non consentito"})
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            if not HTML.exists():
                return self._json(500, {"error": "d3_studio.html non trovato accanto al server"})
            return self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        if path == "/config":
            return self._json(200, {"ollama": self.server.ollama,
                                    "tools": {"pdftotext": have("pdftotext"), "pdftoppm": have("pdftoppm")}})
        if path.startswith("/proxy/"):
            target = path[len("/proxy"):]
            if target in ALLOWED_GET:
                return self._forward("GET", target, None)
        self._json(404, {"error": "non trovato"})

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "host non consentito"})
        u = urlparse(self.path)
        path = u.path
        if path in ("/pdf/extract", "/pdf/render"):
            return self._pdf(path, parse_qs(u.query))
        if not path.startswith("/proxy/") or path[len("/proxy"):] not in ALLOWED_POST:
            return self._json(404, {"error": "non trovato"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self._json(413, {"error": f"corpo richiesta non valido o oltre {MAX_BODY // (1024 * 1024)} MiB"})
        body = self.rfile.read(n)
        self._forward("POST", path[len("/proxy"):], body)


def main():
    ap = argparse.ArgumentParser(description="d3 Studio: UI web locale per i decision model di Ollama")
    ap.add_argument("--ollama", default="http://localhost:11434", help="URL di Ollama")
    ap.add_argument("--host", default="127.0.0.1", help="indirizzo di ascolto (default solo locale)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--timeout", type=int, default=300, help="timeout per richiesta, in secondi")
    ap.add_argument("--open", action="store_true", help="apre il browser")
    ap.add_argument("--version", action="version", version="d3 Studio " + __version__)
    a = ap.parse_args()

    if a.host not in ("127.0.0.1", "localhost", "::1"):
        sys.stderr.write("Attenzione: d3 Studio accetta solo richieste con Host localhost/127.0.0.1 e non ha "
                         "autenticazione. Non esporlo su una rete: per l'uso da remoto usa un tunnel SSH.\n")
    try:
        srv = Server((a.host, a.port), Handler)
    except OSError as e:
        sys.exit(f"Impossibile ascoltare su {a.host}:{a.port} ({e.strerror or e}). "
                 "Porta gia' in uso? Prova con --port 8766.")
    srv.ollama = a.ollama
    srv.timeout_s = a.timeout
    url = f"http://127.0.0.1:{a.port}"
    print(f"d3 Studio su {url}  ->  Ollama: {a.ollama}")
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nchiuso")


if __name__ == "__main__":
    main()
