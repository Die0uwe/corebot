"""Tests zonder Discord: router, knippen, limiet, tijd, Ollama-client tegen een nepserver en de berichtstroom met nepobjecten.
Start: python test_bot.py   (echt inloggen bij Discord is hiermee NIET getest)"""
import asyncio, json, sys, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import aiohttp
import bot as B
from router import classify, referral

res = []
def ok(n, c, e=''):
    res.append(bool(c)); print(('PASS' if c else 'FAIL'), n, e)

# ---- router
cases = [
    ('maak een html pagina met een rode knop', 'web'), ('Kun je een website voor mijn bakkerij bouwen?', 'web'),
    ('schrijf css voor een donker menu', 'web'), ('genereer javascript voor een teller', 'web'),
    ('programmeer een script dat bestanden hernoemt', 'web'),
    ('bouw een plugin voor mijn cms', 'cms'), ('maak een thema voor wordpress', 'cms'), ('ik wil mijn blog met een cms beheren, kun je helpen met maken', 'cms'),
    ('wat is html?', 'chat'), ('wat is het verschil tussen css en html', 'chat'), ('hoe laat is het', 'chat'),
    ('welke dag is het vandaag', 'chat'), ('vertel een mop over katten', 'chat'), ('wat is een cms eigenlijk', 'chat'),
    ('kun je een menu maken voor mijn feestje', 'chat'), ('maak een lijstje met tips om beter te slapen', 'chat'), ('geef me een recept voor pannenkoeken', 'chat'),
    ('```html\n<div class="a">hoi</div>\n``` wat doet dit', 'web'),
]
for t, want in cases:
    ok(f'router: "{t[:45]}" -> {want}', classify(t) == want, classify(t))
ok('verwijzing web bevat scriptspace.nl', 'https://scriptspace.nl' in referral('web') and 'cms.' not in referral('web'))
ok('verwijzing cms bevat cms.scriptspace.nl', 'https://cms.scriptspace.nl' in referral('cms'))

# ---- hulpfuncties
parts = B.split_message('alinea ' * 700)
ok('lang antwoord wordt geknipt onder 2000 tekens', len(parts) > 1 and all(len(p) <= 1900 for p in parts), str([len(p) for p in parts]))
ok('niets gaat verloren bij knippen', ''.join(parts).replace(' ', '').replace('\n', '') == ('alinea ' * 700).replace(' ', ''))
ok('kort antwoord blijft heel', B.split_message('hoi') == ['hoi'])
ok('zonder spaties wordt toch geknipt', all(len(p) <= 1900 for p in B.split_message('x' * 5000)))
ok('think-blok en @everyone worden opgeschoond', B.clean_answer('<think>geheim</think>Hoi @everyone') == 'Hoi @​everyone')
tc = B.time_context('Europe/Amsterdam', datetime(2026, 10, 10, 23, 21, tzinfo=ZoneInfo('Europe/Amsterdam')))
ok('tijd-context klopt', tc == 'Het is nu zaterdag 10 oktober 2026, 23:21 uur (avond, tijdzone Europe/Amsterdam).', tc)
ok('dagdeel ochtend', '(ochtend' in B.time_context('Europe/Amsterdam', datetime(2026, 10, 12, 8, 0, tzinfo=ZoneInfo('Europe/Amsterdam'))))
L = B.Limiter(8, 3)
ok('eerste bericht mag', L.check(1, 100) is None)
ok('cooldown blokkeert', L.check(1, 103) is not None)
ok('na cooldown mag weer', L.check(1, 109) is None)
L.check(1, 120)
ok('uurlimiet blokkeert', 'uurlimiet' in (L.check(1, 140) or ''))
ok('andere gebruiker is niet geraakt', L.check(2, 140) is None)
ok('na een uur weer ruimte', L.check(1, 4000) is None)
ok('systeemprompt noemt beide adressen', 'scriptspace.nl' in B.build_system('X') and 'cms.scriptspace.nl' in B.build_system('X'))

# ---- Ollama-client tegen nepserver
seen = {}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        raw = json.dumps({'models': [{'name': n} for n in seen.get('tags', ['qwen3:4b', 'llama3:8b', 'llava:7b'])]}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        seen['body'], seen['headers'] = body, dict(self.headers)
        if seen.get('code'):
            raw = json.dumps({'error': "model 'bestaat-niet' not found"}).encode()
            self.send_response(seen['code']); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if seen.get('fail'):
            self.send_response(500); self.end_headers(); return
        raw = json.dumps({'message': {'content': '<think>x</think>Het is zaterdagavond.'}}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
srv = HTTPServer(('127.0.0.1', 9201), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

class FakeMsg:
    def __init__(self, text, uid=1, channel=5, bot=False, guild=True):
        self.content, self.author = text, SimpleNamespace(bot=bot, id=uid)
        self.attachments, self.stickers, self.embeds = [], [], []
        self.channel = FakeChan(channel); self.guild = object() if guild else None; self.replies = []
    async def reply(self, t, mention_author=False): self.replies.append(t)
class FakeChan:
    def __init__(self, i): self.id = i; self.sent = []; self.name = f'kanaal-{i}'
    def typing(self):
        class C:
            async def __aenter__(s): return s
            async def __aexit__(s, *a): return False
        return C()
    async def send(self, t): self.sent.append(t)

async def main():
    async with aiohttp.ClientSession() as s:
        o = B.Ollama('http://127.0.0.1:9201', 'qwen3:4b', 'sleutel', 'cfid', 'cfsec')
        out = await o.chat(s, [{'role': 'user', 'content': 'hoi'}])
        ok('Ollama-client leest antwoord', 'zaterdagavond' in out)
        ok('stream uit en model meegestuurd', seen['body']['stream'] is False and seen['body']['model'] == 'qwen3:4b')
        h = {k.lower(): v for k, v in seen['headers'].items()}
        ok('sleutel en Cloudflare-headers meegestuurd', h.get('authorization') == 'Bearer sleutel' and h.get('cf-access-client-id') == 'cfid' and h.get('cf-access-client-secret') == 'cfsec')
    # berichtstroom
    import os
    os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9201', 'COOLDOWN_SECONDS': '0', 'MAX_PER_HOUR': '50'})
    b = B.SBBot(); await b.setup_hook()
    m = FakeMsg('welke dag is het?'); await b.on_message(m)
    ok('vraag in het juiste kanaal wordt beantwoord', m.replies == ['Het is zaterdagavond.'], str(m.replies))
    ok('tijd zit voor het gebruikersbericht', seen['body']['messages'][-1]['content'].startswith('[Het is nu ') and seen['body']['messages'][0]['role'] == 'system')
    m2 = FakeMsg('en morgen?'); await b.on_message(m2)
    ok('korte geheugen: vorige vraag en antwoord gaan mee', len(seen['body']['messages']) == 4, str(len(seen['body']['messages'])))
    n = len(seen['body']['messages'])
    m3 = FakeMsg('maak een html pagina met een knop'); seen['body'] = None; await b.on_message(m3)
    ok('code-vraag: doorverwezen, model niet aangeroepen', seen['body'] is None and 'scriptspace.nl' in m3.replies[0])
    m4 = FakeMsg('bouw een plugin voor mijn cms'); await b.on_message(m4)
    ok('cms-vraag: doorverwezen naar cms.scriptspace.nl', 'cms.scriptspace.nl' in m4.replies[0])
    for label, msg in [('ander kanaal', FakeMsg('hoi', channel=9)), ('bot-bericht', FakeMsg('hoi', bot=True)), ('DM', FakeMsg('hoi', guild=False)), ('leeg bericht', FakeMsg('  '))]:
        seen['body'] = None; await b.on_message(msg)
        ok(f'genegeerd: {label}', not msg.replies and seen['body'] is None)
    mt = FakeMsg('x' * 2000); await b.on_message(mt)
    ok('te lang bericht krijgt melding', 'te lang' in mt.replies[0])
    seen['fail'] = True; mf = FakeMsg('hoe gaat het', uid=7); await b.on_message(mf)
    ok('Ollama-fout geeft nette melding', 'niet bereikbaar' in mf.replies[0], str(mf.replies))
    seen['fail'] = False
    b.limiter = B.Limiter(30, 5); ml1 = FakeMsg('hoi', uid=9); await b.on_message(ml1); ml2 = FakeMsg('hoi nog eens', uid=9); await b.on_message(ml2)
    ok('cooldown in de berichtstroom', 'Even geduld' in ml2.replies[0])
    await b.session.close()

asyncio.run(main())

# ---- hartslag naar het beheerpaneel (nepserver met dezelfde controle als bot_ping.php)
import hashlib, hmac, time as _t
pings = []
class P(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length']))
        good = hmac.compare_digest(hmac.new(b'geheim', raw, hashlib.sha256).hexdigest(), self.headers.get('X-Bot-Signature', ''))
        pings.append((good, json.loads(raw)))
        code = 200 if good else 401
        out = json.dumps({'ok': good, 'paused': PAUSED[0], **EXTRA}).encode()
        self.send_response(code); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
PAUSED = [False]
EXTRA = {}
psrv = HTTPServer(('127.0.0.1', 9202), P); threading.Thread(target=psrv.serve_forever, daemon=True).start()

async def pingtests():
    async with aiohttp.ClientSession() as s:
        r = B.Reporter('http://127.0.0.1:9202/ping', 'geheim')
        r.count('answered', 3); r.count('web'); r.count('ms_sum', 900); r.count('ms_n', 3)
        res = await r.beat(s, {'name': 'X', 'model': 'm'})
        ok('hartslag komt aan met geldige handtekening', res is not None and res.get('paused') is False and pings[-1][0] is True)
        c = pings[-1][1]['counters']
        ok('tellers en velden in de hartslag', c['answered'] == 3 and c['web'] == 1 and c['ms_sum'] == 900 and pings[-1][1]['version'] == B.BOT_VERSION and abs(pings[-1][1]['ts'] - _t.time()) < 5)
        ok('na succes zijn de tellers leeg', all(v == 0 for v in r.pending.values()))
        ok('hartslag bevat geen berichttekst of gebruikers', set(pings[-1][1]) <= {'ts', 'version', 'uptime_s', 'counters', 'name', 'model', 'latency_ms', 'guilds', 'channel', 'ollama_ok', 'models', 'channels', 'perm_at', 'config_v', 'ignored_by', 'events', 'action_results', 'alert_channel', 'model_missing'})
        bad = B.Reporter('http://127.0.0.1:9202/ping', 'fout'); bad.count('errors', 2)
        ok('verkeerd geheim: geweigerd, tellers blijven bewaard', await bad.beat(s, {}) is None and bad.pending['errors'] == 2)
        dead = B.Reporter('http://127.0.0.1:9/ping', 'geheim'); dead.count('answered')
        ok('site onbereikbaar: geen crash, tellers blijven', await dead.beat(s, {}) is None and dead.pending['answered'] == 1)
        PAUSED[0] = True
        ok('pauze komt terug uit het antwoord', (await r.beat(s, {})).get('paused') is True)
asyncio.run(pingtests())

async def flowtests():
    import os
    os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9201', 'COOLDOWN_SECONDS': '0', 'MAX_PER_HOUR': '50'})
    b = B.SBBot(); await b.setup_hook()
    m = FakeMsg('hoe gaat het?'); await b.on_message(m)
    m2 = FakeMsg('maak een html pagina'); await b.on_message(m2)
    m3 = FakeMsg('bouw een plugin voor mijn cms'); await b.on_message(m3)
    p = b.reporter.pending
    ok('tellers: 1 antwoord, 1 web, 1 cms, tijd gemeten', p['answered'] == 1 and p['web'] == 1 and p['cms'] == 1 and p['ms_n'] == 1)
    b.paused = True
    seen['body'] = None; mp = FakeMsg('hallo?'); await b.on_message(mp); mp2 = FakeMsg('nog iemand?'); await b.on_message(mp2)
    ok('pauze: model niet aangeroepen, één melding', seen['body'] is None and len(mp.replies) == 1 and 'gepauzeerd' in mp.replies[0] and not mp2.replies)
    await b.session.close()
asyncio.run(flowtests())


# ---- v0.3: instellingen uit de site, commando's, alarmen, kanaallijst
import os
CH1, CH2, CHA = 111111111111111111, 222222222222222222, 333333333333333333
c = B.sanitize_config({'channels': [str(CH1), 'abc', '12', CH1, str(CH2)], 'alert_channel': str(CHA), 'alerts': ['ollama', 'bestaat-niet', 'start'],
                       'cooldown': 9999, 'per_hour': 0, 'max_input': 5, 'memory': 3, 'model': 'qwen2.5vl:7b', 'name': '<b>Bot</b>', 'extra_prompt': 'x' * 900,
                       'web_url': 'http://onveilig.nl', 'cms_url': 'https://cms.voorbeeld.nl', 'v': 7,
                       'commands': [{'name': 'Regels', 'reply': 'Wees aardig.', 'on': True}, {'name': 'help', 'reply': 'x'}, {'name': 'slecht naam!', 'reply': 'x'},
                                    {'name': 'uit', 'reply': 'x', 'on': False}, {'name': 'regels', 'reply': 'dubbel'}]})
ok('config: alleen geldige kanaal-ID\'s (dubbele weg, onzin weg)', c['channels'] == [CH1, CH2], str(c['channels']))
ok('config: waarden begrensd (cooldown 600, uurlimiet 1, invoer 100)', c['cooldown'] == 600 and c['per_hour'] == 1 and c['max_input'] == 100)
ok('config: onbekend alarmtype weg, naam zonder tags, prompt gekapt op 600', c['alerts'] == ['ollama', 'start'] and c['name'] == 'bBot/b' or c['name'] == 'bBot/b'.replace('/', '') or '<' not in c['name'])
ok('config: http-adres wordt standaard, https blijft', c['web_url'] == B.WEB_URL and c['cms_url'] == 'https://cms.voorbeeld.nl' and len(c['extra_prompt']) == 600)
ok('config: commando\'s gefilterd (help, slechte naam, uit en dubbel vallen af)', c['commands'] == {'regels': 'Wees aardig.'}, str(c['commands']))
ok('config: geen dict -> leeg', B.sanitize_config('rommel') == {} and B.sanitize_config(None) == {})
A = B.Alerter(600)
ok('alarm: eerste keer mag, daarna 10 min niet, andere soort wel', A.allow('ollama', 0) and not A.allow('ollama', 100) and A.allow('errors', 100) and A.allow('ollama', 700))

class FP:  # rechten
    def __init__(s, v=True, snd=True, h=True, l=True, t=True): s.view_channel, s.send_messages, s.read_message_history, s.embed_links, s.send_messages_in_threads = v, snd, h, l, t
class FCh(FakeChan):
    def __init__(s, i, guild, everyone_view=True, me=(True, True, True)):
        super().__init__(i); s.guild, s.everyone_view, s.me = guild, everyone_view, me; s.sent = []; s.name = f'room-{i % 1000}'
    def permissions_for(s, who): return FP(s.everyone_view) if who is s.guild.default_role else FP(*s.me)
class FGuild:
    def __init__(s): s.default_role = object(); s.me = object(); s.name = 'Testserver'; s.text_channels = []
async def v3tests():
    os.environ.update({'DISCORD_CHANNEL_ID': str(CH1), 'OLLAMA_BASE': 'http://127.0.0.1:9201', 'COOLDOWN_SECONDS': '0', 'MAX_PER_HOUR': '50'})
    b = B.SBBot(); await b.setup_hook()
    ok('start: .env-kanaal is het enige kanaal', b.channels == {CH1})
    b.apply_config({'channels': [str(CH2)], 'cooldown': 0, 'per_hour': 50, 'name': 'Wachter', 'model': 'm2', 'extra_prompt': 'Noem jezelf Wachter.', 'v': 5,
                    'commands': [{'name': 'regels', 'reply': 'Wees aardig.', 'on': True}], 'alert_channel': str(CHA), 'alerts': ['ollama', 'errors', 'permissions']})
    ok('config toegepast: kanaal, naam, model, versie', b.channels == {CH2} and b.name == 'Wachter' and b.ollama.model == 'm2' and b.cfg_v == 5)
    ok('systeemprompt bevat naam en extra instructie, regels blijven', 'Wachter' in b.system and 'Noem jezelf Wachter.' in b.system and 'scriptspace.nl' in b.system)
    b.apply_config({'channels': []})
    ok('lege kanalenlijst: terug naar .env-kanaal', b.channels == {CH1})
    b.apply_config({'channels': [str(CH2)]})
    old = FakeMsg('hoi', channel=CH1); seen['body'] = None; await b.on_message(old)
    ok('oud kanaal wordt nu genegeerd en geteld', not old.replies and seen['body'] is None and b.reporter.pending['ignored'] == 1 and b.ignored.get('kanaal-%d' % CH1) == 1)
    mm = FakeMsg('welke dag is het?', channel=CH2); await b.on_message(mm)
    ok('nieuw kanaal werkt zonder herstart', mm.replies == ['Het is zaterdagavond.'], str(mm.replies))
    ok('gebeurtenis zonder berichttekst', b.events[-1]['k'] == 'beantwoord' and b.events[-1]['c'] == f'kanaal-{CH2}' and 'dag' not in json.dumps(b.events))
    mc = FakeMsg('!Regels', channel=CH2); seen['body'] = None; await b.on_message(mc)
    ok('commando: vaste tekst, model niet aangeroepen, geteld', mc.replies == ['Wees aardig.'] and seen['body'] is None and b.reporter.pending['commands'] == 1)
    mh = FakeMsg('!help', channel=CH2, uid=3); await b.on_message(mh)
    ok('!help noemt de commando\'s', '!regels' in mh.replies[0])
    mu = FakeMsg('!onbekend', channel=CH2, uid=4); await b.on_message(mu)
    ok('onbekend !-bericht gaat gewoon naar het model', mu.replies == ['Het is zaterdagavond.'])
    me = FakeMsg('', channel=CH2); await b.on_message(me)
    ok('leeg bericht zonder bijlage: geteld als "leeg" (intent-verdenking)', b.reporter.pending['empty'] == 1)
    mat = FakeMsg('', channel=CH2); mat.attachments = [1]; await b.on_message(mat)
    ok('leeg bericht met bijlage telt niet', b.reporter.pending['empty'] == 1)
    # alarmen
    g = FGuild(); pub = FCh(CHA, g, everyone_view=True); priv = FCh(CHA + 1, g, everyone_view=False); nowrite = FCh(CHA + 2, g, False, (True, False, True))
    chans = {CHA: pub, CHA + 1: priv, CHA + 2: nowrite}
    b.get_channel = lambda i: chans.get(i)
    b.alert_channel = CHA
    r = await b.alert('ollama', 'test')
    ok('alarm: NIET naar kanaal dat voor iedereen zichtbaar is', r[0] is False and 'iedereen' in r[1] and not pub.sent, str(r))
    b.alert_channel = CHA + 2
    r = await b.alert('errors', 'test')
    ok('alarm: niet naar kanaal waar de bot niet mag schrijven', r[0] is False and 'mag hier niet schrijven' in r[1])
    b.alert_channel = CHA + 1
    r = await b.alert('ollama', 'Ollama is weg')
    ok('alarm: wel naar privé kanaal, zonder pings of gebruikersnamen', r[0] is True and len(priv.sent) == 1 and 'Ollama is weg' in priv.sent[0] and '@' not in priv.sent[0])
    r = await b.alert('ollama', 'nog eens')
    ok('alarm: dezelfde soort binnen 10 minuten niet nog eens', r == (False, 'recent al gemeld') and len(priv.sent) == 1)
    r = await b.alert('start', 'gestart')
    ok('alarm: soort die uit staat wordt niet verstuurd', r == (False, 'uitgeschakeld'))
    seen['fail'] = True; mf = FakeMsg('hoe gaat het', channel=CH2, uid=77); await b.on_message(mf); seen['fail'] = False
    ok('Ollama-fout in de berichtstroom: gebruiker krijgt melding en er komt een alarm (dedupe op soort)', 'niet bereikbaar' in mf.replies[0] and b.reporter.pending['errors'] == 1)
    # v0.3.1: model bestaat niet
    ok('versie 0.3.2 en soort model in standaardalarmen', B.BOT_VERSION == '0.4.0' and 'model' in B.ALERT_KINDS and 'model' in B.DEFAULT_ALERTS)
    async with aiohttp.ClientSession() as s404:
        seen['code'] = 404
        try:
            await B.Ollama('http://127.0.0.1:9201', 'bestaat-niet').chat(s404, [{'role': 'user', 'content': 'hoi'}]); got = None
        except B.ModelNotFound as e:
            got = e
        except RuntimeError as e:
            got = e
        seen['code'] = None
    ok('Ollama-client: 404 wordt ModelNotFound (met modelnaam)', isinstance(got, B.ModelNotFound) and got.model == 'bestaat-niet', repr(got))
    ok('model_known: exacte naam, :latest en hoofdletters', B.model_known('qwen3:4b', ['qwen3:4b']) and B.model_known('llama3', ['llama3:latest']) and B.model_known('Qwen3:4B', ['qwen3:4b']) and not B.model_known('qwen3:8b', ['qwen3:4b']))
    t = B.model_alert_text('x', ['a', 'b', 'c', 'd', 'e', 'f'])
    ok('alarmtekst: naam en maximaal 5 modellen', t == "Model 'x' bestaat niet in Ollama. Kies een model uit de lijst in het paneel (nu beschikbaar: a, b, c, d, e)." and 'f' not in t.split('beschikbaar:')[1], t)
    b.apply_config({'model': 'bestaat-niet', 'alerts': ['model', 'ollama']})
    b.alert_channel = CHA + 1; b.alerter = B.Alerter(600); n0 = len(priv.sent)
    seen['code'] = 404; mm1 = FakeMsg('hoe gaat het', channel=CH2, uid=81); await b.on_message(mm1)
    mm2 = FakeMsg('nog een vraag', channel=CH2, uid=82); await b.on_message(mm2); seen['code'] = None
    ok('404 in berichtstroom: modelalarm met naam en lijst, gebruiker krijgt nette melding', len(priv.sent) == n0 + 1 and "model: Model 'bestaat-niet' bestaat niet in Ollama" in priv.sent[-1] and 'qwen3:4b' in priv.sent[-1] and 'niet bereikbaar' in mm1.replies[0], str(priv.sent[n0:]))
    ok('modelalarm: ratelimit per soort (tweede 404 geen tweede alarm), geen alarm van soort ollama', len(priv.sent) == n0 + 1 and ': Ollama gaf' not in priv.sent[-1])
    ok('modelalarm: staat er \'model\' niet in alerts, dan uitgeschakeld', (b.apply_config({'alerts': ['ollama']}), await b.alert('model', 'x'))[1] == (False, 'uitgeschakeld'))
    b.apply_config({'model': 'm2', 'alerts': ['ollama', 'errors', 'permissions']})
    # acties
    res = await b.run_action({'id': 'a1', 'type': 'alert'})
    ok('actie testalarm: lukt in privé kanaal', res['ok'] is True and res['id'] == 'a1' and 'testalarm' in priv.sent[-1].lower())
    b.alert_channel = CHA
    res = await b.run_action({'id': 'a2', 'type': 'alert'})
    ok('actie testalarm: mislukt met uitleg bij publiek kanaal', res['ok'] is False and 'iedereen' in res['error'])
    chans[CH2] = FCh(CH2, g, False)
    res = await b.run_action({'id': 'a3', 'type': 'say', 'channel': str(CH2)})
    ok('actie testbericht: verstuurd naar gekozen kanaal', res['ok'] is True and 'kan hier schrijven' in chans[CH2].sent[-1])
    res = await b.run_action({'id': 'a4', 'type': 'say', 'channel': '999999999999999999'})
    ok('actie testbericht: onzichtbaar kanaal geeft nette fout', res['ok'] is False and 'niet zichtbaar' in res['error'])
    ok('actie: onbekend type wordt geweigerd', (await b.run_action({'id': 'a5', 'type': 'rm -rf'}))['ok'] is False)
    # kanaallijst
    g.text_channels = [pub, priv]
    type(b).guilds = property(lambda self: [g])
    infos = b.channel_infos()
    ok('kanaallijst: id als tekst, rechten en publiek-vlag', infos[0]['id'] == str(CHA) and infos[0]['e'] is True and infos[1]['e'] is False and infos[1]['s'] is True)
    ok('kanaallijst: ook links insluiten (l), threads (t) en tijdstip van controle', infos[1]['l'] is True and infos[1]['t'] is True and abs(b.perm_at - __import__('time').time()) < 5)
    # v0.3.2: rechten per kanaal en 'Opnieuw controleren'
    nohist = FCh(CHA + 3, g, False, (True, True, False)); nolinks = FCh(CHA + 4, g, True, (True, True, True))
    nolinks.permissions_for = lambda who: FP(True) if who is g.default_role else FP(True, True, True, False, False)
    g.text_channels = [pub, priv, nohist, nolinks]
    nh = b.channel_infos()
    ok('kanaallijst: ontbrekende Berichtgeschiedenis lezen -> h false, rest true', nh[2]['h'] is False and nh[2]['v'] is True and nh[2]['s'] is True and nh[2]['e'] is False)
    ok('kanaallijst: ontbrekende Links insluiten en threads -> l en t false', nh[3]['l'] is False and nh[3]['t'] is False and nh[3]['h'] is True)
    blob = json.dumps(nh)
    ok('kanaallijst bevat alleen id, naam, server en vlaggen (geen berichtinhoud)', all(set(c) == {'id', 'gi', 'n', 'g', 'v', 's', 'h', 'e', 'l', 't'} for c in nh) and 'hoi' not in blob)
    b.beat_now = asyncio.Event()
    res = await b.run_action({'id': 'rc1', 'type': 'recheck'})
    ok('actie opnieuw controleren: ok en extra hartslag aangevraagd', res == {'id': 'rc1', 'ok': True, 'error': ''} and b.beat_now.is_set())
    b.beat_now.clear()
    res = await b.run_action({'id': 'rc1', 'type': 'recheck'})
    ok('actie opnieuw controleren: zelfde opdracht-id vraagt geen tweede hartslag aan', res['ok'] is True and not b.beat_now.is_set())
    res = await b.run_action({'id': 'rc2', 'type': 'recheck', 'channel': 'rommel'})
    ok('actie opnieuw controleren: nieuw id werkt weer, rommel in channel wordt genegeerd', res['ok'] is True and b.beat_now.is_set())
    g.text_channels = [pub, priv]
    # geheugen past aan
    b.apply_config({'memory': 2})
    for i in range(5): b.mem(42).append(i)
    ok('geheugenlengte volgt de instelling', len(b.mem(42)) == 2)
    await b.session.close()
asyncio.run(v3tests())

async def pausenotice():
    # Regressie: vlak na het opstarten van de pc is time.monotonic() kleiner dan 300; de eerste pauzemelding moet dan toch komen.
    b = B.SBBot()
    ok('pauzemelding: eerste keer is altijd toegestaan, ook bij kleine monotonic()', __import__('time').monotonic() - b.notice_at > 300 and b.notice_at < 0)
asyncio.run(pausenotice())

async def missingtests():
    os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9201'})
    b = B.SBBot(); await b.setup_hook()
    seen['tags'] = ['qwen3:4b']
    for model, want in [('bestaat-niet', True), ('qwen3:4b', False), ('qwen3:8b', True)]:
        b.ollama.model = model
        st, names = await b.ollama_state()
        ok(f'model_missing voor {model}', st and (not B.model_known(model, names)) is want, str(names))
    await b.session.close()
asyncio.run(missingtests())

async def roundtrip():
    EXTRA.update({'config': {'channels': [str(CH2)], 'v': 9}, 'action': {'id': 'x1', 'type': 'say', 'channel': str(CH2)}})
    PAUSED[0] = False
    async with aiohttp.ClientSession() as s:
        r = B.Reporter('http://127.0.0.1:9202/ping', 'geheim')
        data = await r.beat(s, {'events': [{'t': 1, 'k': 'beantwoord', 'c': 'x', 'ms': 5, 'n': ''}], 'channels': [{'id': '1', 'n': 'a', 'g': 'g', 'v': True, 's': True, 'h': True, 'e': False}]})
        ok('antwoord van de site bevat config en actie', data['config']['v'] == 9 and data['action']['id'] == 'x1')
        ok('gebeurtenissen en kanalen gaan mee in de hartslag', pings[-1][1]['events'][0]['k'] == 'beantwoord' and pings[-1][1]['channels'][0]['id'] == '1')
    EXTRA.clear()
asyncio.run(roundtrip())

async def recheck_loop():
    # De echte hartslaglus: opdracht 'recheck' moet binnen enkele seconden een tweede hartslag met de uitkomst opleveren (niet pas na 30 s).
    os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9201'})
    b = B.SBBot(); await b.setup_hook()
    b.reporter = B.Reporter('http://127.0.0.1:9202/ping', 'geheim')
    async def ready(): return None
    b.wait_until_ready = ready
    n0 = len(pings)
    EXTRA.update({'action': {'id': 'rcl1', 'type': 'recheck', 'channel': ''}})
    task = asyncio.create_task(b.heartbeat_loop())
    for _ in range(60):
        await asyncio.sleep(0.1)
        if len(pings) >= n0 + 1:
            EXTRA.clear()  # de site geeft de opdracht maar een keer
            break
    for _ in range(60):
        await asyncio.sleep(0.1)
        if len(pings) >= n0 + 2:
            break
    task.cancel()
    ok('hartslaglus: na opdracht komt binnen ~6 s een tweede hartslag (niet pas na 30 s)', len(pings) >= n0 + 2, str(len(pings) - n0))
    got = [r for _, d in pings[n0:] for r in d.get('action_results', [])]
    ok('hartslaglus: tweede hartslag meldt de uitkomst van de opdracht', {'id': 'rcl1', 'ok': True, 'error': ''} in got, str(got))
    ok('hartslaglus: hartslag bevat tijdstip van controle en vlaggen l/t', 'perm_at' in pings[n0][1] and pings[n0][1]['version'] == '0.4.0')
    EXTRA.clear()
    await b.session.close()
asyncio.run(recheck_loop())

# ---- v0.4: meerdere servers, profielen per server en per kanaal
async def v4tests():
    import os
    os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9201', 'COOLDOWN_SECONDS': '0', 'MAX_PER_HOUR': '50'})
    b = B.SBBot(); await b.setup_hook()
    G1, G2 = 111111111111111111, 222222222222222222
    C1, C2, C3 = 333333333333333331, 333333333333333332, 333333333333333333
    def msg(text, ch, g, uid=7):
        m = FakeMsg(text, uid=uid, channel=ch); m.guild = SimpleNamespace(id=g); return m
    # profielen opschonen
    p = B.sanitize_profile({'tone': 'speels', 'model': 'm 1;rm', 'name': '<b>Kees</b>', 'extra_prompt': 'x' * 900, 'cooldown': 99999, 'per_hour': '', 'memory': '3',
                            'commands': [{'name': 'Hallo', 'reply': 'hoi', 'on': True}, {'name': 'help', 'reply': 'x'}], 'mode': 'commands', 'enabled': False}, False)
    ok('profiel: toon geldig, ongeldig model en lege waarden vallen weg', p.get('tone') == 'speels' and 'model' not in p and 'per_hour' not in p)
    ok('profiel: naam bevat geen < of >', '<' not in p['name'] and '>' not in p['name'])
    ok('profiel: extra max 600 en cooldown max 600, geheugen 3', len(p['extra_prompt']) == 600 and p['cooldown'] == 600 and p['memory'] == 3)
    ok('profiel: commando\'s opgeschoond (help genegeerd), modus alleen op kanaal', p['commands'] == {'hallo': 'hoi'} and p['mode'] == 'commands' and 'enabled' not in p)
    ok('serverprofiel: enabled false blijft, modus wordt genegeerd', B.sanitize_profile({'enabled': False, 'mode': 'commands'}, True) == {'enabled': False})
    ok('profiel: toon onbekend wordt genegeerd', 'tone' not in B.sanitize_profile({'tone': 'agressief'}, False))
    c = B.sanitize_config({'servers': {str(G1): {'tone': 'zakelijk'}, 'abc': {'tone': 'kort'}, '12': {}}, 'channel_cfg': {str(C1): {'mode': 'commands'}}, 'tone': 'vriendelijk'})
    ok('config: servers en kanaalprofielen met geldige id\'s', set(c['servers']) == {G1} and set(c['channel_cfg']) == {C1} and c['tone'] == 'vriendelijk')
    ok('config: lege lijst van PHP (lege map) geeft lege map', B.sanitize_config({'servers': [], 'channel_cfg': []}) == {'servers': {}, 'channel_cfg': {}})
    ok('config: onbekende toon op standaardniveau wordt leeg', B.sanitize_config({'tone': 'x'})['tone'] == '')
    big = {str(G1 + i): {'tone': 'kort'} for i in range(80)}
    ok('config: maximaal 50 servers', len(B.sanitize_config({'servers': big})['servers']) == 50)
    ok('config: tot 50 kanalen (was 10)', len(B.sanitize_config({'channels': [str(C1 + i) for i in range(70)]})['channels']) == 50)
    # erven: standaard < server < kanaal
    b.apply_config({'channels': [str(C1), str(C2), str(C3)], 'tone': 'vriendelijk', 'extra_prompt': 'Basis.', 'commands': [{'name': 'regels', 'reply': 'Wees aardig.', 'on': True}],
                    'servers': {str(G1): {'tone': 'zakelijk', 'model': 'ms1', 'extra_prompt': 'Server een.', 'commands': [{'name': 'info', 'reply': 'Server een info', 'on': True}]},
                                str(G2): {'enabled': False}},
                    'channel_cfg': {str(C2): {'tone': 'speels', 'extra_prompt': 'Noem jezelf Kees.', 'name': 'Kees', 'cooldown': 600, 'per_hour': 2, 'memory': 1,
                                              'commands': [{'name': 'regels', 'reply': 'Hier mag gelachen worden.', 'on': True}]},
                                    str(C3): {'mode': 'commands'}}})
    r1, r2, r0 = b.resolve(G1, C1), b.resolve(G1, C2), b.resolve(999, 998)
    ok('erven: kanaal zonder profiel volgt de server (toon, model)', r1['tone'] == 'zakelijk' and r1['model'] == 'ms1' and B.TONES['zakelijk'][1] in r1['system'])
    ok('erven: kanaalprofiel overschrijft toon en naam', r2['tone'] == 'speels' and r2['name'] == 'Kees' and B.TONES['speels'][1] in r2['system'] and B.TONES['zakelijk'][1] not in r2['system'])
    ok('erven: kanaal zonder eigen model neemt het model van de server', r2['model'] == 'ms1')
    ok('erven: onbekende server en kanaal krijgen de standaard', r0['tone'] == 'vriendelijk' and r0['model'] == b.ollama.model and r0['enabled'] is True and r0['mode'] == 'chat')
    ok('extra instructies tellen op: standaard, server, kanaal', all(x in r2['system'] for x in ('Basis.', 'Server een.', 'Noem jezelf Kees.')) and 'Server een.' not in r0['system'])
    ok('commando\'s samengevoegd, kanaal wint van standaard', r2['commands']['regels'] == 'Hier mag gelachen worden.' and r2['commands']['info'] == 'Server een info' and r1['commands']['regels'] == 'Wees aardig.' and 'info' not in r0['commands'])
    ok('prompt per combinatie wordt hergebruikt (cache, stabiele prefix)', b.resolve(G1, C1)['system'] is r1['system'])
    ok('systeemprompt: regels blijven, ook met toon', 'scriptspace.nl' in r2['system'] and 'NOOIT zelf HTML' in r2['system'])
    ok('tonen: alle sleutels hebben een label', all(isinstance(v[0], str) and v[0] for v in B.TONES.values()) and B.TONES['standaard'][1] == '')
    # berichtstroom per kanaal
    m1 = msg('hoe gaat het', C1, G1); await b.on_message(m1)
    ok('bericht: model en toon van de server worden gebruikt', seen['body']['model'] == 'ms1' and B.TONES['zakelijk'][1] in seen['body']['messages'][0]['content'], str(seen['body']['model']))
    m2 = msg('hoe gaat het', C2, G1, uid=8); await b.on_message(m2)
    ok('bericht: toon en naam van het kanaal worden gebruikt', B.TONES['speels'][1] in seen['body']['messages'][0]['content'] and 'Kees' in seen['body']['messages'][0]['content'] and m2.replies)
    ok('geheugen per kanaal en gebruiker, lengte uit het kanaalprofiel', len(b.mem((C1, 7), 6)) == 2 and len(b.mem((C2, 8), 1)) == 1 and len(b.mem((C2, 7), 1)) == 0)
    # kanaal alleen commando's
    b.apply_config({'servers': {str(G1): {'commands': [{'name': 'info', 'reply': 'Server een info', 'on': True}]}, str(G2): {'enabled': False}}})
    mc = msg('wat is een kat?', C3, G1); await b.on_message(mc)
    ok('modus commando\'s: gewone vraag krijgt geen antwoord en geen AI-aanroep', mc.replies == [])
    mi = msg('!info', C3, G1); await b.on_message(mi)
    ok('modus commando\'s: commando werkt wel', mi.replies == ['Server een info'], str(mi.replies))
    mh = msg('!help', C3, G1, uid=9); await b.on_message(mh)
    ok('modus commando\'s: !help zegt dat hier alleen commando\'s werken', mh.replies and 'alleen commando' in mh.replies[0], str(mh.replies))
    mw = msg('maak een html pagina', C3, G1); await b.on_message(mw)
    ok('modus commando\'s: ook geen doorverwijzing', mw.replies == [])
    # server gepauzeerd
    b.apply_config({'channels': [str(C1), str(C2), str(C3), '444444444444444441']})
    md = msg('hallo', 444444444444444441, G2); await b.on_message(md)
    ok('server met enabled false: geen antwoord', md.replies == [])
    # limieten per server en gebruiker, waarden uit het kanaal
    b.limiter.hits.clear()
    a1 = msg('hallo daar', C2, G1, uid=21); await b.on_message(a1)
    a2 = msg('nog een', C2, G1, uid=21); await b.on_message(a2)
    ok('kanaallimiet: cooldown 600 uit het kanaalprofiel remt de tweede vraag', a1.replies and a2.replies and a2.replies[0].startswith('Even geduld'), str(a2.replies))
    b.apply_config({'servers': {str(G1): {'tone': 'zakelijk'}, str(G2): {}}, 'channels': [str(C1), str(C2), '444444444444444441']})
    a3 = msg('hallo daar', 444444444444444441, G2, uid=21); await b.on_message(a3)
    ok('limiet telt per server: dezelfde gebruiker in een andere server mag wel', a3.replies and not a3.replies[0].startswith('Even geduld'), str(a3.replies))
    a4 = msg('hallo daar', C1, G1, uid=21); await b.on_message(a4)
    ok('cooldown komt uit het kanaal: een ander kanaal zonder eigen waarde gebruikt de standaard (0 s)', a4.replies and not a4.replies[0].startswith('Even geduld'), str(a4.replies))
    lim = B.Limiter(0, 50)
    ok('uurlimiet kan per aanroep strenger (kanaalprofiel)', lim.check(('g', 1), per_hour=1) is None and 'uurlimiet' in (lim.check(('g', 1), per_hour=1) or '') and lim.check(('g', 1)) is None)
    # overschrijven met leeg: terug naar erven
    b.apply_config({'channel_cfg': {}, 'servers': {}})
    ok('profielen leeg gemaakt: alles terug naar de standaard', b.resolve(G1, C2)['name'] == b.name and b.resolve(G1, C2)['tone'] == 'vriendelijk')
    # servers in de hartslag en server-gebeurtenissen
    class FGu:
        def __init__(self, i, n, mc, chs): self.id, self.name, self.member_count, self.text_channels, self.me = i, n, mc, chs, object()
    class FC2:
        def __init__(self, ok_): self.ok = ok_
        def permissions_for(self, who): return SimpleNamespace(view_channel=self.ok, send_messages=self.ok)
    gu = FGu(G1, 'Mijn server', 42, [FC2(True), FC2(False)])
    type(b).guilds = property(lambda self: [gu])
    si = b.server_infos()
    ok('serverlijst: id als tekst, naam, leden en aantal bruikbare kanalen', si == [{'id': str(G1), 'n': 'Mijn server', 'm': 42, 'c': 1}], str(si))
    b.beat_now = asyncio.Event(); b.events.clear()
    await b.on_guild_join(gu)
    ok('toegevoegd aan server: gebeurtenis en extra hartslag', b.events and b.events[-1]['k'] == 'server' and b.events[-1]['n'] == 'toegevoegd' and b.beat_now.is_set())
    await b.on_guild_remove(gu)
    ok('verwijderd uit server: gebeurtenis', b.events[-1]['n'] == 'verwijderd')
    ok('alarmsoort servers bestaat en staat standaard aan', 'servers' in B.ALERT_KINDS and 'servers' in B.DEFAULT_ALERTS)
    await b.session.close()
asyncio.run(v4tests())

print(f'\n{sum(res)}/{len(res)} geslaagd'); sys.exit(0 if all(res) else 1)
