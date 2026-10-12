"""t102: contract bot <-> site. De echte bot (HubClient + SBBot) tegen de echte PHP-site met database en een nep-Ollama.
Start: tests/cb_up.sh  daarna  python3 tests/t102.py  (verse database nodig, net als t101)."""
import asyncio, json, os, re, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'bot'))
os.environ.update({'DISCORD_CHANNEL_ID': '5', 'OLLAMA_BASE': 'http://127.0.0.1:9205', 'COOLDOWN_SECONDS': '0', 'MAX_PER_HOUR': '50'})
import bot as B
from hub import HubClient

SITE = 'http://127.0.0.1:8098/'
SECRET = 'testhubsecret-0123456789abcdef0123456789abcdef'
G1 = '777000000000000001'
C1, C2 = '888000000000000001', '888000000000000002'
MEM_ID = 222222222222222222
fails = []; n = 0
def ok(name, cond, detail=''):
    global n; n += 1
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  -> ' + str(detail)[:300]))
    if not cond: fails.append(name)
def sql(q):
    return subprocess.run(['mariadb', '-uroot', '-N', 'corebot', '-e', q], capture_output=True, text=True).stdout.strip()

class U:
    def __init__(self, who):
        self.s = requests.Session(); self.who = who; self.csrf = ''
    def login(self):
        r = self.s.get(SITE + 'login.php', allow_redirects=False)
        state = re.search(r'state=([0-9a-f]+)', r.headers['Location']).group(1)
        self.s.get(SITE + 'callback.php', params={'code': 'u:' + self.who, 'state': state}, allow_redirects=False)
        self.csrf = self.s.get(SITE + 'api.php?a=me').json().get('csrf', '')
    def get(self, a, **p): return self.s.get(SITE + 'api.php', params={'a': a, **p}).json()
    def post(self, a, body=None):
        r = self.s.post(SITE + 'api.php?a=' + a, json=body or {}, headers={'X-CSRF-Token': self.csrf}); return r.status_code, r.json()

# nep-Ollama
O = {'mode': 'ok', 'calls': 0, 'body': None}
class OH(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        raw = json.dumps({'models': [{'name': 'qwen3:4b'}]}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        O['body'] = json.loads(self.rfile.read(int(self.headers['Content-Length']))); O['calls'] += 1
        if O['mode'] == 'fail':
            self.send_response(500); self.end_headers(); return
        raw = json.dumps({'message': {'content': 'Antwoord van de AI.'}}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
threading.Thread(target=HTTPServer(('127.0.0.1', 9205), OH).serve_forever, daemon=True).start()

class FakeChan:
    def __init__(self, i): self.id = i; self.name = f'kanaal-{i}'
    def typing(self):
        class C:
            async def __aenter__(s): return s
            async def __aexit__(s, *a): return False
        return C()
    async def send(self, t): pass
class FakeMsg:
    def __init__(self, text, ch, uid):
        self.content, self.author = text, SimpleNamespace(bot=False, id=uid)
        self.attachments, self.stickers, self.embeds = [], [], []
        self.channel = FakeChan(int(ch)); self.guild = SimpleNamespace(id=int(G1)); self.replies = []; self.reacts = []
    async def reply(self, t, mention_author=False): self.replies.append(t)
    async def add_reaction(self, e): self.reacts.append(e)

async def main():
    o, mem, adm = U('owner'), U('member'), U('admin')
    for u in (o, mem, adm): u.login()
    b = B.SBBot(); await b.setup_hook()
    b.hub = HubClient(SITE + 'hub.php', SECRET, B.BOT_VERSION)
    servers = [{'id': G1, 'name': 'Mijn server', 'icon': 'ic1', 'n': 42, 'ch': [{'id': C1, 'n': 'algemeen', 't': 0, 'p': 0}, {'id': C2, 'n': 'raid', 't': 0, 'p': 1}]}]
    async def sync():
        data = await b.hub.sync(b.session, servers, b.breaker.status(), '123456789012345678')
        if data is not None: b.apply_hub(data)
        return data
    async def ask(text, uid=7, ch=C1):
        b.limiter.hits.clear(); m = FakeMsg(text, ch, uid); await b.on_message(m); return m

    d = await sync()
    ok('eerste sync: site antwoordt, server is aangemaakt, nog geen kanalen gekozen', d is not None and d['complete'] and sql(f'select count(*) from guilds where guild_id="{G1}"') == '1' and b.hub_cfg[int(G1)]['channels'] == set())
    m = await ask('hoi')
    ok('nog geen antwoordkanaal: de bot negeert het kanaal', not m.replies)

    # platformbeheerder: toegestane modellen en model per server
    st, _ = adm.post('admin_settings', {'models_allowed': 'qwen3:4b', 'default_cap': 300, 'signups': True, 'sbwebui_url': ''}); ok('platform: toegestane modellen', st == 200)
    st, _ = adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b', 'suspended': False, 'daily_cap': ''}); ok('platform: model toegekend', st == 200)

    # servereigenaar stelt in
    rev = o.get('guild', id=G1)['rev']
    faq = [{'q': 'Wanneer is de raid?', 'a': 'Elke donderdag om 20:00.', 'on': True}]
    cfg = {'server': {'tone': 'vriendelijk', 'name': 'Gildebot', 'extra_prompt': 'Praat over WoW.', 'cooldown': 5, 'per_hour': 100, 'commands': [{'name': 'regels', 'reply': 'Wees aardig.', 'on': True}]},
           'channels': [C1], 'channel_cfg': {C1: {'tone': 'zakelijk'}}, 'allow_member_tone': True, 'faq': faq, 'fallback': {'faq': True, 'cache': True, 'templates': True}}
    st, j = o.post('guild_save', {'id': G1, 'rev': rev, 'config': {**cfg, 'server': {**cfg['server'], 'cooldown': 1}}}); ok('site weigert een wachttijd onder de publieke grens', st == 400, j)
    st, j = o.post('guild_save', {'id': G1, 'rev': rev, 'config': cfg}); ok('eigenaar slaat instellingen op', st == 200, j)
    await sync(); g = b.hub_cfg[int(G1)]
    ok('bot ziet kanalen, FAQ, naam, model en commando\'s', g['channels'] == {int(C1)} and g['faq'] == [{'q': 'Wanneer is de raid?', 'a': 'Elke donderdag om 20:00.'}] and g['model'] == 'qwen3:4b'
       and g['server']['name'] == 'Gildebot' and g['server']['commands'] == {'regels': 'Wees aardig.'}, str(g))
    ok('bot gebruikt de limieten van de server', b.resolve_hub(int(G1), int(C1))['per_hour'] == 100 and b.resolve_hub(int(G1), int(C1))['cooldown'] == 5)
    ok('kanaaltoon gaat voor servertoon', b.resolve_hub(int(G1), int(C1))['tone'] == 'zakelijk')

    # vraag via de hub
    m = await ask('hoe gaat het met je')
    ok('vraag in hubkanaal wordt beantwoord met het toegewezen model', m.replies == ['Antwoord van de AI.'] and O['body']['model'] == 'qwen3:4b' and O['body']['messages'][0]['content'].startswith('Je bent Gildebot'), str(O['body'])[:200])
    m = await ask('!regels')
    ok('server-commando werkt zonder AI', m.replies == ['Wees aardig.'])
    m = await ask('hoi', ch=C2)
    ok('kanaal dat de eigenaar niet koos wordt genegeerd', not m.replies)

    # ledenvoorkeuren uit het lidmaatschapsaccount
    st, j = mem.post('prefs_save', {'prefs': {'nick': 'Kees', 'tone': 'speels', 'memory': False}}); ok('lid bewaart voorkeuren op de site', st == 200)
    await sync()
    ok('bot krijgt de voorkeuren van het lid', b.members.get(MEM_ID) == {'nick': 'Kees', 'tone': 'speels', 'memory': False}, str(b.members))
    await ask('vertel iets leuks', uid=MEM_ID)
    ok('voorkeuren werken: bijnaam, toon en geen geheugen', 'de gebruiker heet Kees' in O['body']['messages'][-1]['content'] and 'luchtig en grappig' in O['body']['messages'][0]['content'] and len(O['body']['messages']) == 2)

    # tellers terug naar de site
    await sync()
    ok('tellers zijn bij de site aangekomen en bij de bot genuld', int(sql(f'select answered from usage_daily where guild_id="{G1}"') or 0) >= 2 and b.hub.usage[int(G1)]['a'] == 0)

    # AI valt weg
    O['mode'] = 'fail'
    m = await ask('wanneer is de raid eigenlijk', uid=9)
    ok('AI plat: FAQ-antwoord van de server', m.replies == ['Elke donderdag om 20:00.'])
    await ask('een heel andere vraag over iets obscuren', uid=10); await ask('en nog een heel andere vraag over bijzonders', uid=11)
    ok('drie fouten: noodrem open', not b.breaker.up)
    await sync()
    last = json.loads(sql("select v from settings where k='hub_last'"))
    ok('site weet dat de AI plat ligt (status in hub_last)', last.get('ai', {}).get('up') is False and last['ai']['fails'] >= 3 and last['version'] == B.BOT_VERSION, str(last))
    ok('terugval en fouten staan bij het gebruik van vandaag', int(sql(f'select fallback from usage_daily where guild_id="{G1}"')) >= 1 and int(sql(f'select errors from usage_daily where guild_id="{G1}"')) >= 3)
    pl = adm.get('admin')
    ok('platformpaneel toont de AI-status', json.dumps(pl, ensure_ascii=False).find('"up":false') >= 0 or json.dumps(pl).find('"up": false') >= 0 or 'ai' in json.dumps(pl).lower(), str(pl)[:200])
    O['mode'] = 'ok'; b.ai_watch(True, ['qwen3:4b']); await ask('hoe gaat het nu', uid=12); await sync()
    last = json.loads(sql("select v from settings where k='hub_last'"))
    ok('AI terug: status weer up op de site', last['ai']['up'] is True and last['ai']['fails'] == 0, str(last))

    # vergeten
    await ask('onthoud dit', uid=33)
    b.members[MEM_ID] = {'nick': 'Kees'}; b.memory[(int(C1), MEM_ID)] = b.mem((int(C1), MEM_ID))
    st, j = mem.post('forget_me'); ok('lid laat zijn gegevens wissen op de site', st == 200)
    d = await sync()
    ok('bot wist geheugen en voorkeuren van dat lid', MEM_ID not in b.members and (int(C1), MEM_ID) not in b.memory and MEM_ID in b.hub.ack, str(b.hub.ack))
    await sync()
    ok('bevestiging bereikt de site: vergeet-opdracht verdwijnt', sql('select count(*) from forget_queue') == '0' and not b.hub.ack)

    # geschorst
    adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b', 'suspended': True, 'daily_cap': ''}); await sync()
    O['calls'] = 0; m = await ask('hoi daar')
    ok('geschorste server: bot zwijgt', not m.replies and O['calls'] == 0)
    adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b', 'suspended': False, 'daily_cap': 1}); await sync()
    m = await ask('hoi daar')
    ok('daglimiet bereikt: één vriendelijk bericht', m.replies and 'daglimiet' in m.replies[0], str(m.replies))
    adm.post('admin_guild', {'id': G1, 'model': '', 'suspended': False, 'daily_cap': 0}); await sync()
    ok('limiet weg: bot antwoordt weer, model terug naar standaard', b.resolve_hub(int(G1), int(C1))['enabled'] and b.resolve_hub(int(G1), int(C1))['model'] == b.ollama.model)

    # bot verlaat server
    b.hub.left.add(int(G1)); await sync()
    ok('bot meldt vertrek', sql(f'select bot_present from guilds where guild_id="{G1}"') == '0')
    await b.session.close()

asyncio.run(main())
print(f'\n{n - len(fails)}/{n} geslaagd'); sys.exit(1 if fails else 0)
