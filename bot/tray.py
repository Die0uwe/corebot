"""SB AI-bot: tray-starter. Start, stopt en bewaakt de Discord-bot zonder terminal, en luistert naar Start/Stop in het paneel.

Zoals CurseBot: het kruisje en minimaliseren sturen het venster naar het systeemvak; de bot blijft draaien.
Afsluiten doe je via het tray-menu (dat stopt ook de bot). Uiterlijk volgt de site: donker, Slayer-kleuren.

Start met:  pythonw tray.py            (venster)
            pythonw tray.py --minimized  (direct in het systeemvak, zo start Windows hem)"""
import json
import os
import socket
import sys
import webbrowser
from urllib.parse import urlsplit

from manager import HERE, BotManager

CONFIG_FILE = os.path.join(HERE, 'tray.json')
LOCK_PORT = 47832
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'SBAIBot'

# Kleuren van de site (assets/app.css)
BG, SURFACE, ELEVATED, LINE, LINE_STRONG = '#05060a', '#0a0c12', '#10131a', '#1a1e2a', '#262b3c'
FG, MUTED, ACCENT, GOOD, BAD, WARN = '#c8c6d4', '#8a8798', '#8f88b8', '#3dcc7a', '#ef6b78', '#f0b34a'


# ---- instellingen en hulpfuncties (zonder GUI, dus testbaar)
def load_config(path: str = CONFIG_FILE) -> dict:
    d = {'autostart_bot': True, 'windows_autostart': False}
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for k in d:
                if isinstance(raw.get(k), bool):
                    d[k] = raw[k]
    except (OSError, ValueError):
        pass
    return d


def save_config(cfg: dict, path: str = CONFIG_FILE) -> None:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def load_env(path: str = os.path.join(HERE, '.env')) -> dict:
    """Leest .env (zelfde regels als bot.py) zonder os.environ te vervuilen."""
    out: dict = {}
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def panel_url(ping_url: str) -> str:
    """Beheerpagina van de bot, afgeleid van SBWEBUI_PING_URL (alleen https of http op localhost)."""
    p = urlsplit(ping_url)
    if not p.netloc or p.scheme not in ('https', 'http'):
        return ''
    if p.scheme == 'http' and p.hostname not in ('localhost', '127.0.0.1'):
        return ''
    base = p.path.rsplit('/', 1)[0] if '/' in p.path else ''
    return f'{p.scheme}://{p.netloc}{base}/#/beheer/bot'


def autostart_command(python_exe: str | None = None, here: str = HERE) -> str:
    """Opdracht voor de Windows-autostart: onzichtbaar via het VBS-bestand."""
    return f'wscript.exe "{os.path.join(here, "start-tray-hidden.vbs")}"'


def set_windows_autostart(on: bool) -> tuple[bool, str]:
    if os.name != 'nt':
        return False, 'Autostart met Windows werkt alleen op Windows.'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True, ''
    except OSError as e:
        return False, f'Registry-fout: {e}'


def acquire_lock(port: int = LOCK_PORT) -> socket.socket | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', port))
        s.listen(1)
    except OSError:
        s.close()
        return None
    return s


def make_icon(state: str, size: int = 64):
    """Tray-icoon: donkere tegel, accentring en een statusstip (groen draait, rood gestopt, oranje wacht)."""
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 6
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=SURFACE, outline=ACCENT, width=max(2, size // 20))
    c = size // 2
    d.ellipse([c - size // 4, c - size // 4 - size // 12, c + size // 4, c + size // 4 - size // 12], outline=ACCENT, width=max(2, size // 16))
    dot = {'running': GOOD, 'stopped': BAD, 'busy': WARN}.get(state, MUTED)
    rr = size // 6
    cx, cy = size - size // 4, size - size // 4
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=dot, outline=BG, width=max(1, size // 32))
    return img


# ---- GUI
class App:
    def __init__(self, minimized: bool) -> None:
        import customtkinter as ctk
        import pystray
        self.ctk, self.pystray = ctk, pystray
        self.cfg = load_config()
        self.env = load_env()
        self.manager = BotManager()
        self.control = None
        url, secret = self.env.get('SBWEBUI_PING_URL', ''), self.env.get('SBWEBUI_BOT_SECRET', '')
        if url and secret:
            from control import Control
            self.control = Control(self.manager, url, secret)
        self.panel = panel_url(url)
        self.quitting = False
        self.last_state = ''

        ctk.set_appearance_mode('dark')
        self.root = ctk.CTk(fg_color=BG)
        self.root.title('SB AI-bot')
        self.root.geometry('760x560')
        self.root.minsize(620, 440)
        self.root.protocol('WM_DELETE_WINDOW', self.hide)
        self.root.bind('<Unmap>', self._on_unmap)
        self._build()
        self.icon = self.pystray.Icon('sbbot', make_icon('stopped'), 'SB AI-bot', self._menu())
        self.icon.run_detached()
        if self.control:
            self.control.start()
        if self.cfg['autostart_bot'] and self.env.get('DISCORD_TOKEN'):
            self.manager.start()
        self._tick()
        if minimized:
            self.root.after(200, self.hide)

    def _build(self) -> None:
        ctk = self.ctk
        font = ('Segoe UI', 13)
        head = ctk.CTkFrame(self.root, fg_color=SURFACE, border_color=LINE, border_width=1, corner_radius=10)
        head.pack(fill='x', padx=14, pady=(14, 8))
        self.dot = ctk.CTkLabel(head, text='●', text_color=BAD, font=('Segoe UI', 22))
        self.dot.pack(side='left', padx=(14, 6), pady=10)
        col = ctk.CTkFrame(head, fg_color='transparent')
        col.pack(side='left', fill='x', expand=True, pady=8)
        self.state_lbl = ctk.CTkLabel(col, text='Bot gestopt', text_color=FG, font=('Segoe UI', 16, 'bold'), anchor='w')
        self.state_lbl.pack(fill='x')
        self.sub_lbl = ctk.CTkLabel(col, text='', text_color=MUTED, font=font, anchor='w', justify='left', wraplength=520)
        self.sub_lbl.pack(fill='x')
        btns = ctk.CTkFrame(self.root, fg_color='transparent')
        btns.pack(fill='x', padx=14, pady=4)
        mk = lambda t, cmd, primary=False: ctk.CTkButton(btns, text=t, command=cmd, width=110, font=font,
                                                         fg_color=ACCENT if primary else ELEVATED, text_color=BG if primary else FG,
                                                         hover_color='#a39dc8' if primary else LINE_STRONG, border_color=LINE_STRONG, border_width=0 if primary else 1)
        self.b_start = mk('Start', self.do_start, True)
        self.b_stop = mk('Stop', self.do_stop)
        self.b_restart = mk('Herstart', self.do_restart)
        for b in (self.b_start, self.b_stop, self.b_restart):
            b.pack(side='left', padx=(0, 8))
        if self.panel:
            mk('Open paneel', lambda: webbrowser.open(self.panel)).pack(side='right')
        self.msg = ctk.CTkLabel(self.root, text='', text_color=WARN, font=font, anchor='w', justify='left', wraplength=700)
        self.msg.pack(fill='x', padx=16, pady=(4, 0))
        opts = ctk.CTkFrame(self.root, fg_color='transparent')
        opts.pack(fill='x', padx=14, pady=6)
        self.v_auto = ctk.BooleanVar(value=self.cfg['autostart_bot'])
        self.v_win = ctk.BooleanVar(value=self.cfg['windows_autostart'])
        ck = lambda t, v, cmd: ctk.CTkCheckBox(opts, text=t, variable=v, command=cmd, text_color=FG, fg_color=ACCENT, hover_color='#a39dc8', border_color=LINE_STRONG, font=font)
        ck('Bot starten zodra dit programma start', self.v_auto, self._opt_changed).pack(side='left', padx=(2, 18))
        ck('Starten met Windows (verborgen)', self.v_win, self._opt_changed).pack(side='left')
        ctk.CTkLabel(self.root, text='Logboek', text_color=MUTED, font=('Segoe UI', 12), anchor='w').pack(fill='x', padx=16, pady=(6, 0))
        self.log = ctk.CTkTextbox(self.root, fg_color=SURFACE, text_color=FG, border_color=LINE, border_width=1, corner_radius=8, font=('Consolas', 11), wrap='word')
        self.log.pack(fill='both', expand=True, padx=14, pady=(2, 14))
        self.log.configure(state='disabled')
        self._log_cache = ''

    # ---- acties (ook vanuit het tray-menu; daar via root.after zodat Tk in zijn eigen thread blijft)
    def do_start(self) -> None:
        self._say(*self.manager.start())

    def do_stop(self) -> None:
        self._say(*self.manager.stop())

    def do_restart(self) -> None:
        self._say(*self.manager.restart())

    def _say(self, ok: bool, text: str) -> None:
        self.msg.configure(text=text, text_color=GOOD if ok else BAD)
        self._refresh()

    def _opt_changed(self) -> None:
        self.cfg['autostart_bot'] = bool(self.v_auto.get())
        want = bool(self.v_win.get())
        if want != self.cfg['windows_autostart']:
            ok, err = set_windows_autostart(want)
            if ok:
                self.cfg['windows_autostart'] = want
            else:
                self.v_win.set(self.cfg['windows_autostart'])
                self.msg.configure(text=err, text_color=BAD)
        save_config(self.cfg)

    # ---- venster en tray
    def hide(self) -> None:
        self.root.withdraw()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_unmap(self, _e) -> None:
        # Minimaliseren stuurt het venster naar het systeemvak (zoals CurseBot), zodat er geen taakbalkknop overblijft.
        if self.root.state() == 'iconic':
            self.root.after(50, self.hide)

    def _menu(self):
        it, m = self.pystray.MenuItem, self.pystray.Menu
        post = lambda fn: (lambda *_: self.root.after(0, fn))
        return m(it('Openen', post(self.show), default=True), it('Start', post(self.do_start)), it('Stop', post(self.do_stop)),
                 it('Herstart', post(self.do_restart)), m.SEPARATOR, it('Afsluiten (stopt ook de bot)', post(self.quit)))

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        if self.control:
            self.control.stop()
        self.manager.shutdown()
        try:
            self.icon.stop()
        except Exception:  # noqa: BLE001 - afsluiten mag nooit blijven hangen
            pass
        self.root.destroy()

    # ---- ververs
    def _state(self) -> str:
        st = self.manager.status()
        if st['running']:
            return 'running'
        return 'stopped'

    def _refresh(self) -> None:
        st = self.manager.status()
        state = self._state()
        if st['running']:
            self.dot.configure(text_color=GOOD)
            m, s = divmod(st['uptime_s'], 60)
            h, m = divmod(m, 60)
            self.state_lbl.configure(text='Bot draait')
            sub = f'pid {st["pid"]}, draait {h} u {m} min'
        else:
            self.dot.configure(text_color=WARN if st['message'].startswith('Bot crashte') else BAD)
            self.state_lbl.configure(text='Bot gestopt')
            sub = st['message'] or 'Druk op Start.'
        if self.control:
            sub += '  |  site: ' + ('verbonden' if self.control.connected else (self.control.last_error or 'nog niet verbonden'))
        else:
            sub += '  |  geen koppeling met het paneel (zet SBWEBUI_PING_URL en SBWEBUI_BOT_SECRET in .env)'
        self.sub_lbl.configure(text=sub)
        self.b_start.configure(state='disabled' if st['running'] else 'normal')
        self.b_stop.configure(state='normal' if st['running'] else 'disabled')
        self.b_restart.configure(state='normal' if st['running'] else 'disabled')
        if st['gave_up']:
            self.msg.configure(text=st['message'], text_color=BAD)
        if state != self.last_state:
            self.last_state = state
            try:
                self.icon.icon = make_icon(state)
                self.icon.title = 'SB AI-bot: ' + ('draait' if state == 'running' else 'gestopt')
            except Exception:  # noqa: BLE001
                pass

    def _refresh_log(self) -> None:
        text = self.manager.log_tail(300)
        if text != self._log_cache:
            self._log_cache = text
            self.log.configure(state='normal')
            self.log.delete('1.0', 'end')
            self.log.insert('end', text)
            self.log.see('end')
            self.log.configure(state='disabled')

    def _tick(self) -> None:
        if self.quitting:
            return
        try:
            self._refresh()
            if self.root.state() != 'withdrawn':
                self._refresh_log()
        except Exception as e:  # noqa: BLE001 - de lus mag niet stoppen
            self.msg.configure(text=f'Interne fout: {e}', text_color=BAD)
        self.root.after(1500, self._tick)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    lock = acquire_lock()
    if lock is None:
        # Er draait al een tray-starter: niets doen (geen tweede icoon, geen tweede bot).
        return
    App('--minimized' in sys.argv).run()
    os._exit(0)  # de tray-thread van pystray kan het proces anders open houden; de bot is al gestopt


if __name__ == '__main__':
    main()
