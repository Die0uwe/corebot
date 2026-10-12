"""Test voor tray.py: hulpfuncties (zonder scherm) en een rooktest van het venster (alleen met scherm, bv. xvfb-run).
Draai:  python test_tray.py          of          xvfb-run -a python test_tray.py"""
import os, sys, tempfile, time

import tray

res = []
def ok(n, c, e=''):
    res.append(bool(c)); print(('PASS' if c else 'FAIL'), n, e)

tmp = tempfile.mkdtemp()
# ---- config
p = os.path.join(tmp, 'tray.json')
ok('config: standaardwaarden zonder bestand', tray.load_config(p) == {'autostart_bot': True, 'windows_autostart': False})
tray.save_config({'autostart_bot': False, 'windows_autostart': True}, p)
ok('config: opslaan en teruglezen', tray.load_config(p) == {'autostart_bot': False, 'windows_autostart': True})
open(p, 'w').write('{kapot'); ok('config: kapot bestand valt terug op standaard', tray.load_config(p)['autostart_bot'] is True)
open(p, 'w').write('{"autostart_bot": "ja", "x": 1}'); ok('config: verkeerd type en onbekende sleutel genegeerd', tray.load_config(p) == {'autostart_bot': True, 'windows_autostart': False})

# ---- .env
e = os.path.join(tmp, '.env'); open(e, 'w', encoding='utf-8').write('# c\nDISCORD_TOKEN="abc"\nSBWEBUI_PING_URL=https://x.nl/bot_ping.php\n\nrommel\nA=b=c\n')
env = tray.load_env(e)
ok('.env: waarden, quotes en = in waarde', env['DISCORD_TOKEN'] == 'abc' and env['SBWEBUI_PING_URL'].endswith('bot_ping.php') and env['A'] == 'b=c' and 'rommel' not in env)
ok('.env: ontbrekend bestand geeft leeg', tray.load_env(os.path.join(tmp, 'nee')) == {})

# ---- paneel-url
ok('paneel-url uit ping-url', tray.panel_url('https://sbwebui.scriptspace.nl/bot_ping.php') == 'https://sbwebui.scriptspace.nl/#/beheer/bot')
ok('paneel-url met submap', tray.panel_url('https://x.nl/beta/bot_ping.php') == 'https://x.nl/beta/#/beheer/bot')
ok('paneel-url: http op localhost mag', tray.panel_url('http://127.0.0.1:8099/bot_ping.php') == 'http://127.0.0.1:8099/#/beheer/bot')
ok('paneel-url: http op internet geweigerd', tray.panel_url('http://x.nl/bot_ping.php') == '')
ok('paneel-url: onzin en gevaarlijk schema geweigerd', tray.panel_url('') == '' and tray.panel_url('javascript:alert(1)') == '' and tray.panel_url('file:///c:/x') == '')

# ---- autostart-opdracht en icoon
cmd = tray.autostart_command(here='C:\\Bots\\sb bot')
ok('autostart: onzichtbaar via vbs, pad tussen aanhalingstekens', cmd.startswith('wscript.exe "') and cmd.endswith('start-tray-hidden.vbs"') and 'sb bot' in cmd, cmd)
ok('autostart buiten Windows: nette melding, geen crash', os.name == 'nt' or tray.set_windows_autostart(True)[0] is False)
try:
    imgs = {s: tray.make_icon(s) for s in ('running', 'stopped', 'busy')}
    px = {s: i.getpixel((int(64 * .75), int(64 * .75)))[:3] for s, i in imgs.items()}
    ok('icoon: 64x64 en statusstip heeft de juiste kleur', all(i.size == (64, 64) for i in imgs.values()) and px['running'] == (0x3d, 0xcc, 0x7a) and px['stopped'] == (0xef, 0x6b, 0x78) and px['busy'] == (0xf0, 0xb3, 0x4a), str(px))
except ImportError as ex:
    ok('icoon (Pillow ontbreekt)', False, str(ex))

# ---- enkele-instantie
a = tray.acquire_lock(47999); b = tray.acquire_lock(47999)
ok('tray: tweede instantie krijgt geen slot', a is not None and b is None); a and a.close()
import bot
x = bot.acquire_lock(47998); y = bot.acquire_lock(47998)
ok('bot: tweede bot krijgt geen slot (voorkomt dubbele antwoorden)', x is not None and y is None); x and x.close()

# ---- venster (alleen met scherm)
if os.environ.get('DISPLAY'):
    import manager as mg
    try:
        import customtkinter  # noqa: F401
        import pystray  # noqa: F401
    except ImportError as ex:
        ok('venster: customtkinter/pystray ontbreken', False, str(ex)); sys.exit(1)
    td = tempfile.mkdtemp()
    open(os.path.join(td, 'long.py'), 'w').write('import time\nprint("tray-test",flush=True)\nwhile True: time.sleep(.2)\n')
    tray.load_env = lambda *a, **k: {'DISCORD_TOKEN': 'x'}
    tray.CONFIG_FILE = os.path.join(td, 'tray.json')
    orig = mg.BotManager.__init__
    mg.BotManager.__init__ = lambda self, *a, **k: orig(self, command=[sys.executable, os.path.join(td, 'long.py')], cwd=td, log_path=os.path.join(td, 'b.log'), restart_delay=.05)
    tray.BotManager = mg.BotManager
    try:
        app = tray.App(minimized=False)
    except Exception as ex:  # noqa: BLE001
        ok('venster: App start zonder fout', False, repr(ex)); sys.exit(1)
    def pump(sec):
        end = time.time() + sec
        while time.time() < end:
            app.root.update(); time.sleep(0.05)
    pump(2.0)
    ok('venster: bot start automatisch (autostart_bot aan)', app.manager.running)
    ok('venster: toont "Bot draait" en Stop is actief', app.state_lbl.cget('text') == 'Bot draait' and str(app.b_stop.cget('state')) == 'normal' and str(app.b_start.cget('state')) == 'disabled')
    ok('venster: logboek toont uitvoer van de bot', 'tray-test' in app.log.get('1.0', 'end'))
    app.do_stop(); pump(1.0)
    ok('venster: Stop stopt de bot en zet knoppen om', not app.manager.running and app.state_lbl.cget('text') == 'Bot gestopt' and str(app.b_start.cget('state')) == 'normal')
    app.do_start(); pump(1.0); ok('venster: Start start opnieuw', app.manager.running)
    pid = app.manager.pid; app.do_restart(); pump(1.0); ok('venster: Herstart geeft nieuw proces', app.manager.running and app.manager.pid != pid)
    app.hide(); pump(.3); ok('venster: kruisje verbergt naar het systeemvak (bot blijft draaien)', app.root.state() == 'withdrawn' and app.manager.running)
    app.show(); pump(.3); ok('venster: tray-menu "Openen" toont het weer', app.root.state() == 'normal')
    ok('venster: kleuren van de site', app.root.cget('fg_color') == '#05060a')
    app.quit()
    ok('afsluiten stopt ook de bot', not app.manager.running)
else:
    print('SKIP venster-rooktest (geen DISPLAY; gebruik xvfb-run)')

print('\n%d/%d PASS' % (sum(res), len(res)))
sys.stdout.flush()
os._exit(0 if all(res) else 1)
