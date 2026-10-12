"""Beheert de bot als los proces: starten, stoppen, herstarten, logboek en crash-bewaking.

Geen GUI en alleen standaardbibliotheek, zodat dit los te testen is. De tray-starter (tray.py) en de
afstandsbediening vanuit het paneel (control.py) gebruiken dit.

Waarom een apart proces en geen thread (zoals CurseBot)? Een proces kun je schoon stoppen en bij een crash
opnieuw starten zonder dat een hangende verbinding de starter meeneemt."""
import os
import subprocess
import sys
import threading
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(HERE, 'bot.log')
LOG_MAX_BYTES = 1_000_000
EXIT_ALREADY_RUNNING = 3  # bot.py: er draait al een bot op deze pc
CRASH_WINDOW_S = 300
CRASH_LIMIT = 3
STOP_GRACE_S = 8


def default_command() -> list[str]:
    """Python zonder consolevenster (pythonw) als dat bestaat, anders de gewone interpreter."""
    exe = sys.executable
    if os.name == 'nt':
        w = os.path.join(os.path.dirname(exe), 'pythonw.exe')
        if os.path.isfile(w):
            exe = w
    return [exe, os.path.join(HERE, 'bot.py')]


def rotate_log(path: str = LOG_FILE, max_bytes: int = LOG_MAX_BYTES) -> None:
    try:
        if os.path.isfile(path) and os.path.getsize(path) > max_bytes:
            old = path + '.1'
            if os.path.isfile(old):
                os.remove(old)
            os.replace(path, old)
    except OSError:
        pass


def tail(path: str = LOG_FILE, lines: int = 200) -> str:
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64_000))
            data = f.read().decode('utf-8', 'replace')
        return '\n'.join(data.splitlines()[-lines:])
    except OSError:
        return ''


class BotManager:
    """Start en stopt de bot. Thread-veilig. Herstart automatisch bij een crash, maar geeft op na CRASH_LIMIT
    crashes binnen CRASH_WINDOW_S (anders blijft een kapotte .env eindeloos herstarten)."""

    def __init__(self, command: list[str] | None = None, cwd: str = HERE, log_path: str = LOG_FILE,
                 auto_restart: bool = True, restart_delay: float = 3.0, clock=time.monotonic) -> None:
        self.command = command or default_command()
        self.cwd = cwd
        self.log_path = log_path
        self.auto_restart = auto_restart
        self.restart_delay = restart_delay
        self.clock = clock
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._log = None
        self._wanted = False          # de gebruiker wil dat de bot draait
        self._crashes: deque[float] = deque()
        self.crash_total = 0
        self.gave_up = False
        self.last_exit: int | None = None
        self.started_at: float | None = None
        self.message = ''
        self._watch: threading.Thread | None = None
        self._stop_watch = threading.Event()

    # ---- staat
    @property
    def running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self) -> int:
        with self._lock:
            return self._proc.pid if self.running and self._proc else 0

    def uptime_s(self) -> int:
        return int(self.clock() - self.started_at) if self.running and self.started_at is not None else 0

    def status(self) -> dict:
        return {'running': self.running, 'pid': self.pid, 'crashes': self.crash_total, 'gave_up': self.gave_up,
                'last_exit': self.last_exit, 'uptime_s': self.uptime_s(), 'message': self.message}

    # ---- starten en stoppen
    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self.running:
                return True, 'De bot draait al.'
            self._wanted = True
            self.gave_up = False
            self._crashes.clear()
            return self._spawn()

    def _spawn(self) -> tuple[bool, str]:
        rotate_log(self.log_path)
        try:
            self._log = open(self.log_path, 'ab')
            kwargs: dict = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
            self._proc = subprocess.Popen(self.command, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=self._log,
                                          stderr=subprocess.STDOUT, env=env, **kwargs)
        except OSError as e:
            self._proc = None
            self.message = f'Starten mislukt: {e}'
            return False, self.message
        self.started_at = self.clock()
        self.message = 'Bot gestart.'
        self._ensure_watch()
        return True, self.message

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            self._wanted = False
            proc = self._proc
            if proc is None or proc.poll() is not None:
                self._close_log()
                return True, 'De bot stond al uit.'
            proc.terminate()
        try:
            proc.wait(timeout=STOP_GRACE_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False, 'De bot reageert niet op stoppen.'
        with self._lock:
            self.last_exit = proc.returncode
            self.message = 'Bot gestopt.'
            self._close_log()
        return True, self.message

    def restart(self) -> tuple[bool, str]:
        ok, msg = self.stop()
        if not ok:
            return False, msg
        return self.start()

    def shutdown(self) -> None:
        """Bij afsluiten van de starter: bot stoppen en bewaking beëindigen."""
        self._stop_watch.set()
        self.stop()

    # ---- bewaking
    def _ensure_watch(self) -> None:
        if self._watch is not None and self._watch.is_alive():
            return
        self._stop_watch.clear()
        self._watch = threading.Thread(target=self._watch_loop, name='bot-watch', daemon=True)
        self._watch.start()

    def _watch_loop(self) -> None:
        while not self._stop_watch.wait(1.0):
            self.check()

    def check(self) -> None:
        """Eén bewakingsronde (los aanroepbaar voor tests): herkent een crash en herstart eventueel."""
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is None or not self._wanted:
                return
            code = proc.returncode
            self.last_exit = code
            self._proc = None
            self._close_log()
            if code == EXIT_ALREADY_RUNNING:
                self._wanted = False
                self.message = 'Er draait al een bot op deze pc (start-bot.bat of een ander venster). Sluit die eerst af.'
                return
            now = self.clock()
            self._crashes.append(now)
            self.crash_total += 1
            while self._crashes and now - self._crashes[0] > CRASH_WINDOW_S:
                self._crashes.popleft()
            if not self.auto_restart:
                self._wanted = False
                self.message = f'Bot gestopt (code {code}).'
                return
            if len(self._crashes) >= CRASH_LIMIT:
                self._wanted = False
                self.gave_up = True
                self.message = f'De bot crashte {CRASH_LIMIT} keer in {CRASH_WINDOW_S // 60} minuten en blijft gestopt. Kijk in het logboek.'
                return
            self.message = f'Bot crashte (code {code}), herstart over {self.restart_delay:.0f} s.'
        if self._stop_watch.wait(self.restart_delay):
            return
        with self._lock:
            if self._wanted and not self.running:
                self._spawn()

    def _close_log(self) -> None:
        if self._log is not None:
            try:
                self._log.close()
            except OSError:
                pass
            self._log = None

    def log_tail(self, lines: int = 200) -> str:
        return tail(self.log_path, lines)
