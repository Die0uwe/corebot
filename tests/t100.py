"""t100: corebot.info backend — login met nep-Discord, serverlijst, hub-contract, instellingen, voorkeuren, vergeten, beheer."""
import hashlib, hmac, json, re, subprocess, sys, time
import requests
B = 'http://127.0.0.1:8098/'
SECRET = 'testhubsecret-0123456789abcdef0123456789abcdef'
G1, G2, G3, G4 = ['77700000000000000' + str(i) for i in (1, 2, 3, 4)]
C1, C2, C3 = '888000000000000001', '888000000000000002', '888000000000000003'
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
        r = self.s.get(B + 'login.php', allow_redirects=False)
        state = re.search(r'state=([0-9a-f]+)', r.headers['Location']).group(1)
        r2 = self.s.get(B + 'callback.php', params={'code': 'u:' + self.who, 'state': state}, allow_redirects=False)
        self.me(); return r, r2
    def me(self):
        j = self.s.get(B + 'api.php?a=me').json(); self.csrf = j.get('csrf', ''); return j
    def get(self, a, **p):
        r = self.s.get(B + 'api.php', params={'a': a, **p}); return r.status_code, r.json()
    def post(self, a, body=None, csrf=True):
        h = {'X-CSRF-Token': self.csrf} if csrf else {}
        r = self.s.post(B + 'api.php?a=' + a, json=body or {}, headers=h); return r.status_code, r.json()

def hub(body, secret=SECRET, ts=None, sig=None):
    body = {'ts': int(time.time()) if ts is None else ts, 'version': 'test', **body}
    raw = json.dumps(body, separators=(',', ':'))
    s = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest() if sig is None else sig
    r = requests.post(B + 'hub.php', data=raw, headers={'X-Bot-Signature': s, 'Content-Type': 'application/json'})
    try: return r.status_code, r.json()
    except Exception: return r.status_code, {}
def chans(*ids): return [{'id': c, 'n': 'kanaal-' + c[-1], 't': 0, 'p': i} for i, c in enumerate(ids)]
def srv(gid, name, ch=True): 
    d = {'id': gid, 'name': name, 'icon': 'ic' + gid[-1], 'n': 42}
    if ch: d['ch'] = chans(C1, C2, C3)
    return d

# ---------- inloggen ----------
anon = requests.Session()
j = anon.get(B + 'api.php?a=me').json()
ok('uitgelogd: user is null en csrf aanwezig', j.get('user') is None and len(j.get('csrf', '')) > 20)
ok('uitgelogd: uitnodigingslink met juiste permissies', 'client_id=123456789012345678' in j['invite_url'] and 'permissions=274877991936' in j['invite_url'] and 'scope=bot' in j['invite_url'])
ok('uitgelogd: geen geheimen in het antwoord', 'geheim-geheim' not in json.dumps(j) and SECRET not in json.dumps(j))
o = U('owner'); r, r2 = o.login()
ok('login stuurt naar Discord met scope identify guilds', 'discord.com/oauth2/authorize' in r.headers['Location'] and 'scope=identify%20guilds' in r.headers['Location'] and 'redirect_uri=http%3A%2F%2F127.0.0.1%3A8098%2Fcallback.php' in r.headers['Location'], r.headers['Location'])
ok('callback stuurt terug naar de eigen site zonder fout', r2.status_code == 303 and r2.headers['Location'].startswith('./') and 'auth_error' not in r2.headers['Location'], r2.headers.get('Location'))
bad = requests.Session(); bad.get(B + 'login.php', allow_redirects=False)
rr = bad.get(B + 'callback.php', params={'code': 'u:owner', 'state': 'verkeerd'}, allow_redirects=False)
ok('verkeerde state wordt geweigerd', 'auth_error=sessie' in rr.headers['Location'])
st = re.search(r'state=([0-9a-f]+)', bad.get(B + 'login.php', allow_redirects=False).headers['Location']).group(1)
bad.get(B + 'callback.php', params={'code': 'u:owner', 'state': st}, allow_redirects=False)
st2, _ = 0, 0
rr = bad.get(B + 'callback.php', params={'code': 'u:owner', 'state': st}, allow_redirects=False)
ok('dezelfde state kan geen tweede keer', 'auth_error=sessie' in rr.headers['Location'])
w = requests.Session(); s0 = re.search(r'state=([0-9a-f]+)', w.get(B + 'login.php', allow_redirects=False).headers['Location']).group(1)
rr = w.get(B + 'callback.php', params={'code': 'rommel', 'state': s0}, allow_redirects=False)
ok('ongeldige code geeft een nette foutmelding', 'auth_error=discord' in rr.headers['Location'])
rr = requests.Session(); rr.get(B + 'login.php', allow_redirects=False)
ok('callback zonder sessie wordt geweigerd', 'auth_error=sessie' in requests.get(B + 'callback.php', params={'code': 'u:owner', 'state': 'x'}, allow_redirects=False).headers['Location'])
m = o.me()
ok('ingelogd: naam en geen beheerder', m['user']['name'] == 'Eigenaar' and m['user']['admin'] is False and 'cdn.discordapp.com/avatars/111111111111111111/abc123' in m['user']['avatar'])
ok('gebruiker in de database: alleen id, naam, avatar', sql('select count(*) from users where discord_id="111111111111111111"') == '1')
ok('serverlijst vóór de bot: alleen servers met beheerrechten', {s['id'] for s in m['servers']} == {G1, G2, G4} and all(s['can_manage'] and not s['bot_present'] for s in m['servers']), m['servers'])
ok('per server een uitnodiging met guild_id', all('guild_id=' + s['id'] in s['invite_url'] and 'disable_guild_select=true' in s['invite_url'] for s in m['servers']))

# ---------- hub ----------
st, j = hub({'servers': [srv(G1, 'Mijn server')]}, sig='0' * 64); ok('hub: foute handtekening 401', st == 401)
st, j = hub({'servers': []}, ts=int(time.time()) - 1000); ok('hub: te oud tijdstempel 401', st == 401)
st, j = hub({'servers': []}, secret='anders'); ok('hub: ander geheim 401', st == 401)
ok('hub: GET niet toegestaan', requests.get(B + 'hub.php').status_code == 405)
st, j = hub({'servers': [srv(G1, 'Mijn server'), srv(G2, 'Beheerserver'), srv(G3, 'Gewone server')], 'app_id': '123456789012345678'})
ok('hub: sync geeft ok en config per server', st == 200 and j['ok'] and set(j['guilds']) == {G1, G2, G3}, j)
g = j['guilds'][G1]
ok('hub: nieuwe server staat aan, zonder kanalen, zonder model', g['enabled'] is True and g['channels'] == [] and g['model'] == '' and g['allow_member_tone'] is True and g['reason'] == '', g)
ok('hub: lege kaarten blijven {} in JSON (contract met bot)', '"server": {}' in json.dumps(g) or g['server'] == {}, g)
ok('hub: kanalen opgeslagen', sql(f'select count(*) from guild_channels where guild_id="{G1}"') == '3')
st, j2 = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]})
ok('hub: sync zonder ch laat kanalen staan', sql(f'select count(*) from guild_channels where guild_id="{G1}"') == '3' and sql(f'select members from guilds where guild_id="{G1}"') == '50')
st, j3 = hub({'servers': [{'id': 'abc', 'name': 'x'}, 'rommel', {'id': G1, 'name': '<b>Mijn server</b>', 'n': 50}]})
ok('hub: ongeldige servers worden overgeslagen, html uit naam', st == 200 and set(j3['guilds']) == {G1} and sql(f'select name from guilds where guild_id="{G1}"') == 'bMijn server/b', sql(f'select name from guilds where guild_id="{G1}"'))
hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]})
m = o.me()
ok('serverlijst na sync: G3 zichtbaar als lid (bot erin, geen beheer)', {s['id']: (s['can_manage'], s['bot_present']) for s in m['servers']} == {G1: (True, True), G2: (True, True), G3: (False, True), G4: (True, False)}, m['servers'])

# ---------- rechten op servers ----------
mem = U('member'); mem.login(); strg = U('stranger'); strg.login(); adm = U('admin'); adm.login()
st, j = o.get('guild', id=G1)
ok('beheerder van server ziet de serverinstellingen', st == 200 and j['name'] == 'Mijn server' and len(j['channels']) == 3 and 'admin' not in j, j)
ok('waarschuwing: nog geen antwoordkanaal', any('antwoordkanaal' in w for w in j['warnings']), j['warnings'])
for who, u in (('lid', mem), ('vreemde', strg)):
    st, j = u.get('guild', id=G1); ok(f'{who} heeft geen toegang tot server G1', st == 403, j)
st, j = o.get('guild', id=G3); ok('beheerrechten ontbreken in G3: geen toegang', st == 403)
st, j = o.get('guild', id=G4); ok('server zonder bot: 404 met uitnodiging', st == 404 and 'guild_id=' + G4 in j.get('invite_url', ''), j)
st, j = anon.get(B + 'api.php?a=guild&id=' + G1).status_code, 0; ok('uitgelogd: geen toegang tot server', st == 401)

# ---------- instellingen opslaan ----------
st, j = o.get('guild', id=G1); rev = j['rev']
base = {'server': {'tone': 'zakelijk', 'name': 'Core', 'extra_prompt': 'Dit is een <b>zakelijke</b> server.', 'cooldown': 10, 'per_hour': 30},
        'channels': [C1, C2], 'channel_cfg': {C2: {'tone': 'speels', 'mode': 'commands', 'commands': [{'name': '!Regels', 'reply': 'Wees aardig.', 'on': True}]}, C3: {}}, 'allow_member_tone': False}
st, j = o.post('guild_save', {'id': G1, 'rev': rev, 'config': base}, csrf=False); ok('opslaan zonder CSRF-token wordt geweigerd', st == 403, j)
st, j = o.post('guild_save', {'id': G1, 'rev': rev, 'config': base}); ok('opslaan lukt', st == 200 and j['ok'], j)
c = j['guild']['config']
ok('serverprofiel bewaard, html verwijderd', c['server']['tone'] == 'zakelijk' and c['server']['extra_prompt'] == 'Dit is een bzakelijke/b server.' and c['server']['cooldown'] == 10, c)
ok('kanaalprofiel: modus en commando genormaliseerd, leeg profiel weg', list(c['channel_cfg']) == [C2] and c['channel_cfg'][C2]['mode'] == 'commands' and c['channel_cfg'][C2]['commands'][0]['name'] == 'regels', c)
ok('allow_member_tone uit', c['allow_member_tone'] is False)
ok('nieuwe rev na opslaan', j['guild']['rev'] != rev)
st, j2 = o.post('guild_save', {'id': G1, 'rev': rev, 'config': base}); ok('verouderde rev geeft 409', st == 409, j2)
st, j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]})
e = j['guilds'][G1]
ok('hub geeft de effectieve config aan de bot', e['channels'] == [C1, C2] and e['server']['tone'] == 'zakelijk' and e['channel_cfg'][C2]['tone'] == 'speels' and e['allow_member_tone'] is False and e['model'] == '', e)
ok('waarschuwing verdwijnt als er kanalen zijn', not any('antwoordkanaal' in w for w in o.get('guild', id=G1)[1]['warnings']))
rev = o.get('guild', id=G1)[1]['rev']
def save_bad(name, change, frag, target='server', gid=G1):
    cfg = json.loads(json.dumps(base)); 
    if target == 'top': cfg.update(change)
    elif target == 'server': cfg['server'].update(change)
    else: cfg['channel_cfg'][C2].update(change)
    r = o.get('guild', id=gid)[1]['rev']
    st, j = o.post('guild_save', {'id': gid, 'rev': r, 'config': cfg}); ok(name, st == 400 and frag in json.dumps(j, ensure_ascii=False), f'{st} {j}')
save_bad('toon onbekend', {'tone': 'agressief'}, 'toon klopt niet')
save_bad('wachttijd te laag', {'cooldown': 1}, 'Wachttijd moet tussen 3')
save_bad('berichten per uur te hoog', {'per_hour': 500}, 'Berichten per uur')
save_bad('extra instructie te lang', {'extra_prompt': 'x' * 401}, 'maximaal 400')
save_bad('botnaam te lang', {'name': 'x' * 33}, 'maximaal 32')
save_bad('commando !help verboden', {'commands': [{'name': 'help', 'reply': 'x', 'on': True}]}, '!help')
save_bad('commando dubbel', {'commands': [{'name': 'a', 'reply': 'x'}, {'name': 'A', 'reply': 'y'}]}, 'dubbel')
save_bad('commando ongeldige naam', {'commands': [{'name': 'a b', 'reply': 'x'}]}, '1 tot 20')
save_bad('kanaalmodus onbekend', {'mode': 'spam'}, 'modus klopt niet', 'chan')
save_bad('onbekend kanaal wordt geweigerd', {'channels': ['999999999999999999']}, 'kent dit kanaal niet', 'top')
save_bad('kanaal-ID geen snowflake', {'channels': ['abc']}, 'kanaal-ID klopt niet', 'top')
st, j = o.post('guild_save', {'id': G1, 'rev': o.get('guild', id=G1)[1]['rev'], 'config': {**base, 'server': {'model': 'evil-model', 'tone': 'kort'}}})
ok('model in het profiel wordt genegeerd', st == 200 and 'model' not in j['guild']['config']['server'] and j['guild']['config']['server'] == {'tone': 'kort'}, j)
ok('niemand anders kan G1 opslaan', mem.post('guild_save', {'id': G1, 'rev': 'x', 'config': {}})[0] == 403 and strg.post('guild_save', {'id': G1, 'rev': 'x', 'config': {}})[0] == 403)
ok('audit: wijziging vastgelegd zonder inhoud van de instructie', 'Dit is een' not in sql('select group_concat(detail) from audit_log') and int(sql('select count(*) from audit_log where action="guild_save"')) >= 2)

# ---------- voorkeuren van leden ----------
st, j = mem.post('prefs_save', {'prefs': {'nick': ' Kees <b> ', 'tone': 'speels', 'memory': False}}); ok('lid bewaart voorkeuren', st == 200 and j['prefs'] == {'nick': 'Kees b', 'tone': 'speels', 'memory': False}, j)
ok('voorkeuren terug te lezen', mem.get('prefs')[1]['prefs']['tone'] == 'speels')
ok('voorkeur: toon onbekend', mem.post('prefs_save', {'prefs': {'tone': 'x'}})[0] == 400)
ok('voorkeur: bijnaam te lang', mem.post('prefs_save', {'prefs': {'nick': 'x' * 33}})[0] == 400)
st, j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]})
ok('hub geeft voorkeuren van leden in deze server', j['members'].get('222222222222222222', {}).get('nick') == 'Kees b' and j['members']['222222222222222222']['memory'] is False, j['members'])
ok('leden zonder voorkeuren komen niet in de lijst', '111111111111111111' not in j['members'])
G8 = '777000000000000008'
st, j = hub({'servers': [{'id': G8, 'name': 'Andere server', 'n': 1}]}); ok('voorkeuren van leden uit andere servers lekken niet', j['members'] == {}, j['members'])
ok('standaardvoorkeuren verwijderen de rij', mem.post('prefs_save', {'prefs': {'nick': '', 'tone': '', 'memory': True}})[1]['prefs'] == {} and sql('select count(*) from member_prefs') == '0')
mem.post('prefs_save', {'prefs': {'nick': 'Kees'}})

# ---------- gebruik, limieten, afmelden ----------
st, j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}], 'usage': {G1: {'a': 3, 'l': 1, 'e': 0}, G4: {'a': 5}, 'abc': {'a': 1}}})
ok('hub: gebruik opgeteld, onbekende server genegeerd', sql(f'select answered from usage_daily where guild_id="{G1}"') == '3' and sql('select count(*) from usage_daily') == '1' and sql(f'select count(*) from usage_daily where guild_id="{G4}"') == '0')
hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}], 'usage': {G1: {'a': 2}}})
ok('hub: gebruik telt op', sql(f'select answered from usage_daily where guild_id="{G1}"') == '5' and o.get('guild', id=G1)[1]['usage']['today'] == 5)
ok('standaard daglimiet 300 zichtbaar', o.get('guild', id=G1)[1]['usage']['cap'] == 300)

# ---------- beheerder ----------
for name, u in (('gebruiker', o), ('lid', mem), ('vreemde', strg)):
    ok(f'{name}: platformgegevens geweigerd', u.get('admin')[0] == 403 and u.post('admin_settings', {})[0] == 403 and u.post('admin_secret')[0] == 403 and u.post('admin_guild', {'id': G1})[0] == 403)
ok('uitgelogd: platform geweigerd', anon.get(B + 'api.php?a=admin').status_code == 401)
st, a = adm.get('admin')
ok('beheerder: overzicht met cijfers en hub-status', st == 200 and a['stats']['servers'] == 4 and a['stats']['present'] == 4 and a['stats']['today'] == 5 and a['hub_last']['app_id'] == '123456789012345678' and a['redirect_uri'].endswith('/callback.php'), a)
ok('beheerder ziet servers waar hij geen lid van is', {g['id'] for g in a['guilds']} == {G1, G2, G3, G8})
st, j = adm.get('guild', id=G2); ok('beheerder opent elke server, met admin-velden', st == 200 and j['admin']['model'] == '' and j['admin']['models_allowed'] == [], j)
st, j = adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b'}); ok('model buiten de toegestane lijst wordt geweigerd', st == 400, j)
st, j = adm.post('admin_settings', {'models_allowed': 'qwen3:4b, llama3.1:8b', 'default_cap': 300, 'signups': True, 'sbwebui_url': 'http://onveilig'}); ok('SBWebUI-adres moet https zijn', st == 400)
st, j = adm.post('admin_settings', {'models_allowed': 'qwen3:4b, llama3.1:8b', 'default_cap': 300, 'signups': True, 'sbwebui_url': 'https://sbwebui.scriptspace.nl'}); ok('platforminstellingen opgeslagen', st == 200, j)
ok('modelnaam met rare tekens geweigerd', adm.post('admin_settings', {'models_allowed': 'a b;c', 'default_cap': 1})[0] == 400)
st, j = adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b', 'suspended': False, 'daily_cap': ''}); ok('beheerder kent model toe', st == 200 and j['guild']['admin']['model'] == 'qwen3:4b', j)
st, j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]}); ok('hub geeft het toegekende model', j['guilds'][G1]['model'] == 'qwen3:4b' and 'models_allowed' in json.dumps(j['global']), j['guilds'][G1])
ok('gebruikers zien het model niet in hun eigen paneel', 'qwen3' not in json.dumps(o.get('guild', id=G1)[1]) and 'qwen3' not in json.dumps(o.me()))
st, j = adm.post('admin_guild', {'id': G1, 'model': 'qwen3:4b', 'suspended': True}); st, j = hub({'servers': [{'id': G1, 'name': 'x', 'n': 1}]})
ok('geschorste server: enabled false met reden', j['guilds'][G1]['enabled'] is False and j['guilds'][G1]['reason'] == 'geschorst', j['guilds'][G1])
ok('beheerder schorst; gebruiker ziet de waarschuwing', any('geschorst' in w for w in o.get('guild', id=G1)[1]['warnings']))
adm.post('admin_guild', {'id': G1, 'model': '', 'suspended': False, 'daily_cap': 5})
st, j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]}); ok('daglimiet bereikt: enabled false met reden', j['guilds'][G1]['enabled'] is False and j['guilds'][G1]['reason'] == 'daglimiet' and j['guilds'][G1]['model'] == '', j['guilds'][G1])
adm.post('admin_guild', {'id': G1, 'model': '', 'suspended': False, 'daily_cap': 0})
ok('daglimiet 0 betekent geen limiet', hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 50}]})[1]['guilds'][G1]['enabled'] is True)
ok('daglimiet buiten bereik geweigerd', adm.post('admin_guild', {'id': G1, 'daily_cap': -1})[0] == 400)
# server uitzetten door de beheerder van de server zelf
rv = o.get('guild', id=G1)[1]
st, j = o.post('guild_save', {'id': G1, 'rev': rv['rev'], 'config': {'server': {'enabled': False}, 'channels': [C1], 'channel_cfg': {}}})
ok('serverbeheerder zet de bot uit', st == 200 and hub({'servers': [{'id': G1, 'name': 'x', 'n': 1}]})[1]['guilds'][G1]['reason'] == 'uitgezet')
o.post('guild_save', {'id': G1, 'rev': o.get('guild', id=G1)[1]['rev'], 'config': {'server': {}, 'channels': [C1], 'channel_cfg': {}}})
ok('beheerder haalt hub-geheim op; anderen niet', adm.post('admin_secret')[1]['hub_secret'] == SECRET)
adm.post('admin_settings', {'models_allowed': '', 'default_cap': 300, 'signups': False, 'sbwebui_url': ''})
st, j = hub({'servers': [srv('777000000000000007', 'Nieuw')]}); ok('inschrijving dicht: nieuwe server start geschorst', j['guilds']['777000000000000007']['reason'] == 'geschorst', j)
adm.post('admin_settings', {'models_allowed': '', 'default_cap': 300, 'signups': True, 'sbwebui_url': ''})
st, j = hub({'servers': [{'id': G2, 'name': 'Beheerserver', 'n': 1}], 'left': [G2]})
ok('bot verlaat server: bot_present 0 en server verdwijnt voor leden', sql(f'select bot_present from guilds where guild_id="{G2}"') == '0')
st, j = hub({'servers': [], 'left': [G2]})
ok('left zet bot_present uit', sql(f'select bot_present from guilds where guild_id="{G2}"') == '0')
ok('na verlaten: waarschuwing met uitnodiging', any('opnieuw toe' in w for w in o.get('guild', id=G2)[1]['warnings']))

# ---------- vergeten ----------
st, j = mem.post('forget_me'); ok('lid wist zijn gegevens', st == 200 and j['ok'])
ok('gegevens weg uit de database', sql('select count(*) from users where discord_id="222222222222222222"') == '0' and sql('select count(*) from member_prefs') == '0' and sql('select count(*) from user_guilds where user_id not in (select id from users)') == '0')
ok('sessie is beëindigd na wissen', mem.get('admin')[0] == 401)
st, j = hub({'servers': [{'id': G1, 'name': 'x', 'n': 1}]}); ok('bot krijgt een vergeet-opdracht', '222222222222222222' in j['forget'], j['forget'])
st, j = hub({'servers': [], 'ack_forget': ['222222222222222222']}); ok('na bevestiging verdwijnt de opdracht', j['forget'] == [] and sql('select count(*) from forget_queue') == '0')
ok('auditregels zijn geanonimiseerd', sql('select count(*) from audit_log where user_id is not null and user_id not in (select id from users)') == '0')

# ---------- meerdere domeinen ----------
def login_url(host, proto='https'):
    r = requests.get(B + 'login.php', headers={'Host': host, 'X-Forwarded-Proto': proto}, allow_redirects=False)
    return r.headers['Location']
ok('domein corebot.scriptspace.nl: redirect-adres op dat domein', 'redirect_uri=https%3A%2F%2Fcorebot.scriptspace.nl%2Fcallback.php' in login_url('corebot.scriptspace.nl'), login_url('corebot.scriptspace.nl'))
ok('domein corebot.info: redirect-adres op dat domein', 'redirect_uri=https%3A%2F%2Fcorebot.info%2Fcallback.php' in login_url('corebot.info'))
ok('onbekende Host-header valt terug op het eerste domein', 'redirect_uri=http%3A%2F%2F127.0.0.1%3A8098%2Fcallback.php' in login_url('evil.example', 'http') or '127.0.0.1%3A8098' in login_url('evil.example', 'http'), login_url('evil.example', 'http'))
a2 = adm.get('admin')[1]
ok('platform toont alle redirect-adressen', a2['redirect_uris'] == ['https://127.0.0.1:8098/callback.php', 'https://corebot.scriptspace.nl/callback.php', 'https://corebot.info/callback.php'], a2['redirect_uris'])
ok('beide domeinen leveren de app uit (geen doorverwijzing zolang canonical_host leeg is)', requests.get(B, headers={'Host': 'corebot.info'}, allow_redirects=False).status_code == 200 and requests.get(B, headers={'Host': 'corebot.scriptspace.nl'}, allow_redirects=False).status_code == 200)

# ---------- afsluiten, beveiliging ----------
o2 = requests.Session(); r = o2.get(B + 'api.php?a=me'); h = r.headers
ok('beveiligingsheaders aanwezig', "default-src 'self'" in h.get('Content-Security-Policy', '') and h.get('X-Content-Type-Options') == 'nosniff' and h.get('X-Frame-Options') == 'DENY', h)
allj = json.dumps([o.me(), o.get('guild', id=G1)[1], o.get('prefs')[1]])
ok('geen geheimen in gebruikersantwoorden', SECRET not in allj and 'geheim-geheim' not in allj and 'cbpass' not in allj)
ok('config.php niet opvraagbaar via de webserver is Apache-werk: .htaccess blokkeert het', 'config\\.php' in open('../site/.htaccess').read())
st, j = o.post('logout'); ok('uitloggen', st == 200 and o.get('guild', id=G1)[0] == 401)
st, j = o.post('nietbestaand'); ok('onbekende actie 404', st == 404)
print(f'\n{n - len(fails)}/{n} geslaagd'); sys.exit(1 if fails else 0)
