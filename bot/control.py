"""Afstandsbediening: meldt de tray-starter bij de site en voert Start/Stop/Herstart uit het paneel uit.

De bot zelf meldt zich ook (bot.py); deze hartslag is apart (role = tray) zodat het paneel ook weet of de
starter bereikbaar is terwijl de bot uit staat. Alleen standaardbibliotheek. Gesigneerd met hetzelfde geheim als de bot.
Er worden alleen drie vaste opdrachten uitgevoerd (start, stop, restart); nooit vrije commando's."""
import hashlib
import hmac
import json
import socket
import threading
import time
import urllib.error
import urllib.request

from manager import BotManager

TRAY_VERSION = '0.1.0'
INTERVAL_S = 15
ALLOWED = ('start', 'stop', 'restart')


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class Control:
    def __init__(self, manager: BotManager, url: str, secret: str, interval: float = INTERVAL_S, timeout: float = 10.0) -> None:
        self.manager = manager
        self.url = url
        self.secret = secret
        self.interval = interval
        self.timeout = timeout
        self.connected = False
        self.last_error = ''
        self.last_ok_at: float | None = None
        self._result: dict | None = None
        self._done_ids: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.host = socket.gethostname()[:40]

    @property
    def configured(self) -> bool:
        return bool(self.url and self.secret)

    def payload(self, now: int | None = None) -> dict:
        st = self.manager.status()
        body = {'ts': int(time.time()) if now is None else now, 'role': 'tray',
                'tray': {'running': st['running'], 'pid': st['pid'], 'version': TRAY_VERSION, 'crashes': st['crashes'],
                         'host': self.host, 'gave_up': st['gave_up']}}
        if self._result is not None:
            body['run_result'] = self._result
        return body

    def post(self, body: dict) -> dict:
        raw = json.dumps(body, separators=(',', ':')).encode()
        req = urllib.request.Request(self.url, data=raw, method='POST',
                                     headers={'Content-Type': 'application/json', 'X-Bot-Signature': sign(raw, self.secret)})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - https-adres uit eigen .env
            return json.loads(r.read(100_000).decode('utf-8'))

    def execute(self, run: dict) -> dict:
        """Voert één opdracht uit en geeft de uitkomst terug voor de volgende hartslag."""
        rid = str(run.get('id', ''))
        cmd = str(run.get('cmd', ''))
        if cmd not in ALLOWED:
            return {'id': rid, 'ok': False, 'note': 'onbekende opdracht'}
        ok, note = getattr(self.manager, cmd)()
        return {'id': rid, 'ok': bool(ok), 'note': note[:100]}

    def beat_once(self) -> bool:
        """Eén hartslag: melden, antwoord lezen, eventuele opdracht uitvoeren. Geeft True bij een geslaagde verbinding."""
        try:
            resp = self.post(self.payload())
        except urllib.error.HTTPError as e:
            self.connected = False
            self.last_error = {401: 'Geheim of klok klopt niet (SBWEBUI_BOT_SECRET, tijd van de pc).', 429: 'Te vaak gemeld.', 503: 'De site heeft nog geen bot ingesteld.'}.get(e.code, f'De site antwoordde met fout {e.code}.')
            return False
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            self.connected = False
            self.last_error = f'Site niet bereikbaar: {getattr(e, "reason", e)}'
            return False
        self.connected = bool(resp.get('ok'))
        self.last_error = '' if self.connected else 'Onverwacht antwoord van de site.'
        if self.connected:
            self.last_ok_at = time.time()
            # De uitkomst is afgeleverd: pas dan vergeten we hem.
            if self._result is not None:
                self._done_ids = (self._done_ids + [self._result['id']])[-20:]
                self._result = None
            run = resp.get('run')
            if isinstance(run, dict) and str(run.get('id', '')) not in self._done_ids:
                self._result = self.execute(run)
        return self.connected

    def start(self) -> None:
        if not self.configured or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name='tray-control', daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.beat_once()
            # Na een uitgevoerde opdracht meteen de uitkomst melden in plaats van een volle ronde te wachten.
            wait = 1.0 if self._result is not None else self.interval
            self._stop.wait(wait)

    def stop(self) -> None:
        self._stop.set()
