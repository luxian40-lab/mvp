"""Respuestas de Graph para pruebas. No llama a Meta."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def cuerpo_graph(modo: str) -> tuple[int, dict]:
    if modo == 'ok':
        return 200, {'messages': [{'id': 'wamid.fake'}]}
    if modo == '131056':
        return 400, {'error': {'code': 131056, 'message': 'pair rate'}}
    if modo == '131047':
        return 400, {'error': {'code': 131047, 'message': 'window'}}
    if modo == '190':
        return 401, {'error': {'code': 190, 'message': 'token'}}
    if modo == 'timeout':
        return 0, {'error': {'code': 'TIMEOUT', 'message': 'Timeout'}}
    return 500, {'error': {'code': 1, 'message': modo}}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        status, data = cuerpo_graph(getattr(self.server, 'modo', 'ok'))
        raw = json.dumps(data).encode()
        if status == 0:
            return
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        return


class GraphFake:
    """Servidor en 127.0.0.1. modo: ok, 131056, 131047, 190, timeout."""

    def __init__(self, modo: str = 'ok'):
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        self.httpd.modo = modo
        self.url = 'http://%s:%s' % self.httpd.server_address

    def servir(self):
        self.httpd.serve_forever()

    def cerrar(self):
        self.httpd.server_close()
