"""Test voor manager.py en control.py: proces starten/stoppen, crashbewaking, afstandsbediening tegen een nep-site.
Draait zonder Discord en zonder GUI:  python test_manager.py"""
import hashlib, hmac, http.server, json, os, sys, tempfile, threading, time

import control
from manager import BotManager, EXIT_ALREADY_RUNNING, rotate_log, tail

res = []
def ok(n, c, e=''):
    res.append(bool(c)); print(('PASS' if c else 'FAIL'), n, e)

tmp = tempfile.mkdtemp()
def script(name, body):
    p = os.path.join(tmp, name); open(p, 'w').write(body); return [sys.executable, p]

LONG = script('long.py', 'import time,sys\nprint("hallo",flush=True)\nwhile True: time.sleep(0.2)\n')
CRASH = script('crash.py', 'import sys\nprint("kapot",flush=True)\nsys.exit(1)\n')
DOUBLE = script('double.py', 'import sys\nsys.exit(3)\n')
BAD = [os.path.join(tmp, 'bestaat-niet.exe')]
def mgr(cmd, **kw):
    return BotManager(command=cmd, cwd=tmp, log_path=os.path.join(tmp, 'bot-%d.log' % time.time_ns()), restart_delay=0.05, **kw)

# ---- start en stop
m = mgr(LONG)
ok('niet gestart: running False', not m.running and m.pid == 0)
r = m.start(); time.sleep(0.5)
ok('start: proces draait met pid', r[0] and m.running and m.pid > 0, str(r))
ok('start nogmaals: geen tweede proces', m.start() == (True, 'De bot draait al.') and m.status()['running'])
ok('logboek bevat uitvoer van de bot', 'hallo' in m.log_tail())
r = m.stop()
ok('stop: proces is weg', r[0] and not m.running and m.pid == 0, str(r))
ok('stop nogmaals: geen fout', m.stop()[0])
m.restart(); time.sleep(0.4); first = m.pid
m.restart(); time.sleep(0.4)
ok('herstart geeft een nieuw proces', m.running and m.pid != first)
m.shutdown()
ok('shutdown stopt de bot', not m.running)

# ---- crashbewaking
m = mgr(CRASH)
m.start()
for _ in range(60):
    time.sleep(0.1); m.check()
    if m.gave_up: break
ok('crashlus: geeft op na 3 crashes', m.gave_up and not m.running and m.crash_total >= 3, str(m.status()))
ok('crashlus: melding noemt het logboek', 'logboek' in m.message)
ok('crashlus: handmatig Start probeert opnieuw', m.start()[0] and m.gave_up is False)
m.shutdown()

m = mgr(DOUBLE)
m.start(); time.sleep(0.5); m.check()
ok('al een bot actief (code 3): niet herstarten, duidelijke melding', not m.running and not m.gave_up and 'al een bot' in m.message and m.crash_total == 0, m.message)
m.shutdown()

m = mgr(BAD)
r = m.start()
ok('onbestaand programma: nette fout, geen exception', r[0] is False and 'mislukt' in r[1], str(r))

m = mgr(CRASH, auto_restart=False)
m.start(); time.sleep(0.5); m.check()
ok('auto_restart uit: blijft gestopt', not m.running and m.crash_total == 1)
m.shutdown()

# ---- logboek roteren
p = os.path.join(tmp, 'rot.log'); open(p, 'wb').write(b'x' * 2000)
rotate_log(p, max_bytes=1000)
ok('log roteert bij te groot', os.path.isfile(p + '.1') and not os.path.isfile(p))
ok('tail van ontbrekend bestand is leeg', tail(os.path.join(tmp, 'geen.log')) == '')

# ---- afstandsbediening tegen nepsite
SECRET = 'geheim-voor-test'
state = {'run': None, 'got': [], 'status': 200, 'ts_off': 0}
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length']))
        good = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest() == self.headers.get('X-Bot-Signature')
        if state['status'] != 200 or not good:
            self.send_response(state['status'] if state['status'] != 200 else 401); self.end_headers(); self.wfile.write(b'{"ok":false}'); return
        d = json.loads(raw); state['got'].append(d)
        if d.get('run_result') and state['run'] and d['run_result']['id'] == state['run']['id']: state['run'] = None
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({'ok': True, 'run': state['run']}).encode())
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
url = 'http://127.0.0.1:%d/bot_ping.php' % srv.server_address[1]

m = mgr(LONG)
c = control.Control(m, url, SECRET, interval=0.1, timeout=3)
ok('hartslag: verbinding en payload', c.beat_once() and c.connected and state['got'][-1]['role'] == 'tray' and state['got'][-1]['tray']['running'] is False
   and 'ts' in state['got'][-1] and 'run_result' not in state['got'][-1], str(state['got'][-1:]))
state['run'] = {'id': 'abc123', 'cmd': 'start'}
c.beat_once()
ok('opdracht start: proces draait', m.running)
ok('uitkomst wordt bewaard tot de volgende hartslag', c._result and c._result['id'] == 'abc123' and c._result['ok'])
c.beat_once()
ok('volgende hartslag meldt de uitkomst en wist hem', state['got'][-1].get('run_result', {}).get('ok') is True and c._result is None and state['run'] is None)
ok('hartslag meldt dat de bot draait', state['got'][-1]['tray']['running'] is True and state['got'][-1]['tray']['pid'] == m.pid)
# dubbele aflevering van dezelfde opdracht wordt niet nog eens uitgevoerd
pid = m.pid; state['run'] = {'id': 'abc123', 'cmd': 'restart'}; c.beat_once()
ok('zelfde opdracht-id wordt niet twee keer uitgevoerd', m.pid == pid and c._result is None)
state['run'] = {'id': 'def456', 'cmd': 'stop'}; c.beat_once(); c.beat_once()
ok('opdracht stop: bot gestopt, uitkomst gemeld', not m.running and state['run'] is None)
state['run'] = {'id': 'ggg', 'cmd': 'format-c'}; c.beat_once(); c.beat_once()
ok('onbekende opdracht wordt geweigerd en gemeld', state['got'][-1].get('run_result') == {'id': 'ggg', 'ok': False, 'note': 'onbekende opdracht'} and not m.running)
state['run'] = None
state['status'] = 503; ok('fout 503: nette melding, geen exception', c.beat_once() is False and not c.connected and 'nog geen bot' in c.last_error, c.last_error); state['status'] = 200
bad = control.Control(m, url, 'ander-geheim', timeout=3); ok('fout geheim: melding noemt geheim/klok', bad.beat_once() is False and 'Geheim' in bad.last_error, bad.last_error)
dead = control.Control(m, 'http://127.0.0.1:9/x', SECRET, timeout=1); ok('site onbereikbaar: nette melding', dead.beat_once() is False and 'niet bereikbaar' in dead.last_error, dead.last_error)
ok('zonder url/geheim: niet geconfigureerd', not control.Control(m, '', '').configured)

# thread: voert opdracht uit zonder handmatige beat
state['run'] = {'id': 'thr1', 'cmd': 'start'}
c.start(); time.sleep(1.5); c.stop()
ok('achtergrondlus voert opdracht uit en meldt uitkomst', m.running and state['run'] is None)
m.shutdown(); srv.shutdown()

print('\n%d/%d PASS' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
