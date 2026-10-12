"""Nep-Discord voor tests van corebot.info: token, @me en guilds. Code 'u:<naam>' geeft token 'tok-<naam>'."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
USERS = {
    'owner': {'id': '111111111111111111', 'username': 'owner', 'global_name': 'Eigenaar', 'avatar': 'abc123'},
    'member': {'id': '222222222222222222', 'username': 'lid', 'global_name': 'Lid', 'avatar': None},
    'admin': {'id': '999999999999999999', 'username': 'bigboss', 'global_name': 'BigBoss', 'avatar': None},
    'stranger': {'id': '333333333333333333', 'username': 'vreemd', 'global_name': None, 'avatar': None},
}
G = lambda i, n, perm, owner=False: {'id': '77700000000000000' + str(i), 'name': n, 'icon': 'ic' + str(i), 'owner': owner, 'permissions': str(perm)}
GUILDS = {
    'owner': [G(1, 'Mijn server', 8, True), G(2, 'Beheerserver', 32), G(3, 'Gewone server', 0), G(4, 'Zonder bot', 0x20)],
    'member': [G(1, 'Mijn server', 0), G(3, 'Gewone server', 0)],
    'admin': [G(1, 'Mijn server', 0)],
    'stranger': [G(5, 'Andere server', 8, True)],
}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0); f = parse_qs(self.rfile.read(n).decode())
        code = (f.get('code') or [''])[0]
        if not code.startswith('u:') or code[2:] not in USERS or not f.get('client_secret'): return self.send(400, {'error': 'invalid_grant'})
        self.send(200, {'access_token': 'tok-' + code[2:], 'expires_in': 604800, 'token_type': 'Bearer'})
    def do_GET(self):
        a = self.headers.get('Authorization', ''); who = a[11:] if a.startswith('Bearer tok-') else ''
        if who not in USERS: return self.send(401, {'message': '401: Unauthorized'})
        if self.path.endswith('/@me'): return self.send(200, USERS[who])
        if self.path.endswith('/guilds'): return self.send(200, GUILDS[who])
        self.send(404, {})
HTTPServer(('127.0.0.1', 8097), H).serve_forever()
