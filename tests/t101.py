"""t101: corebot.info in de browser — landing, login (nep-Discord), serverinstellingen, voorkeuren, platform, mobiel, CSP."""
import json, re, sys, time
import requests
from playwright.sync_api import sync_playwright
exec(open('t100.py').read().split('# ---------- inloggen ----------')[0])   # hulpfuncties: ok, sql, hub, srv, chans
errors = []
def attach(page):
    page.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    page.on('console', lambda m: errors.append('console: ' + m.text) if m.type == 'error' and 'ERR_TUNNEL' not in m.text else None)  # Discord-plaatjes zijn in de sandbox niet bereikbaar
def login_browser(page, who):
    r = page.context.request.get(B + 'login.php', max_redirects=0)
    state = re.search(r'state=([0-9a-f]+)', r.headers['location']).group(1)
    page.goto(f'{B}callback.php?code=u:{who}&state={state}')
    page.wait_for_selector('.who')

# eerst servers via de hub laten bestaan
hub({'servers': [srv(G1, 'Mijn server'), srv(G2, 'Beheerserver'), srv(G3, 'Gewone server')], 'app_id': '123456789012345678'})
with sync_playwright() as p:
    br = p.chromium.launch()
    # ---- landing, uitgelogd
    ctx = br.new_context(viewport={'width': 1280, 'height': 860}); a = ctx.new_page(); attach(a)
    a.goto(B); a.wait_for_selector('h1')
    ok('landing: titel en rings-diagram', 'per kanaal een eigen toon' in a.inner_text('h1') and a.locator('svg.rings').count() == 1)
    ok('landing: bot toevoegen-link naar Discord met permissies', 'permissions=274877991936' in a.get_by_role('link', name='Bot toevoegen aan Discord').get_attribute('href'))
    ok('landing: privacy- en voorwaardenlinks', a.get_by_role('link', name='Privacy', exact=True).count() == 1 and a.get_by_role('link', name='Voorwaarden', exact=True).count() == 1)
    a.screenshot(path='shots/c_landing_desktop.png', full_page=True)
    m = br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2); mp = m.new_page(); attach(mp)
    mp.goto(B); mp.wait_for_selector('h1')
    ok('landing mobiel: geen horizontale scroll', mp.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
    mp.screenshot(path='shots/c_landing_mobile.png', full_page=True)
    a.goto(B + '?auth_error=geweigerd'); a.wait_for_selector('.note.bad'); ok('landing: nette fout bij geweigerde toestemming', 'toestemming' in a.inner_text('.note.bad'))
    pr = a.goto(B + 'legal.php?p=privacy'); txt = a.inner_text('main')
    ok('privacypagina: bevat bewaarde gegevens en contactadres', 'Discord-ID' in txt and 'privacy@corebot.info' in txt and 'werkgeheugen' in txt)
    ok('voorwaarden bestaan', 'Gebruiksvoorwaarden' in requests.get(B + 'legal.php?p=voorwaarden').text)

    # ---- eigenaar: dashboard en instellingen
    o = ctx.new_page(); attach(o); login_browser(o, 'owner')
    o.wait_for_selector('.rows .row')
    names = o.locator('.rows .row .name').all_inner_texts()
    ok('dashboard: servers met beheerrechten', 'Mijn server' in names and 'Beheerserver' in names and 'Zonder bot' in names, names)
    ok('dashboard: server zonder bot heeft Bot toevoegen', o.locator('.row', has_text='Zonder bot').get_by_role('link', name='Bot toevoegen').count() == 1)
    ok('dashboard: lidserver apart genoemd', 'Servers waar je lid bent' in o.inner_text('main') and 'Gewone server' in o.inner_text('main'))
    o.screenshot(path='shots/c_dashboard.png', full_page=True)
    o.locator('.row', has_text='Mijn server').get_by_role('link', name='Instellen').click()
    o.wait_for_selector('.tabs'); ok('serverpagina: tabs en waarschuwing over kanalen', 'antwoordkanaal' in o.inner_text('.note') and o.locator('[role=tab]').count() == 4)
    ok('geen opslaanbalk zolang er niets gewijzigd is', o.locator('.save').is_hidden())
    o.select_option('select >> nth=0', 'zakelijk'); o.fill('input[maxlength="32"]', 'Core')
    o.fill('textarea', 'Verwijs voor regels naar #regels.')
    ok('opslaanbalk verschijnt bij wijziging', o.locator('.save').is_visible())
    ok('tekenteller werkt', '34 van 400' in o.inner_text('main') or '33 van 400' in o.inner_text('main'), o.inner_text('main')[:400])
    o.get_by_role('tab', name='Kanalen').click()
    o.wait_for_selector('.chan')
    ok('kanalenlijst uit de bot', o.locator('.chan').count() == 3 and '#kanaal-1' in o.inner_text('main'))
    o.get_by_label('Bot antwoordt in kanaal-1').check(); o.get_by_label('Bot antwoordt in kanaal-2').check()
    o.locator('.chan').nth(1).get_by_role('button', name='Eigen instellingen').click()
    ok('kanaalpaneel toont erfenis in de keuzelijst', 'Zoals de server (Zakelijk)' in o.locator('.chan').nth(1).inner_text())
    o.locator('.chan').nth(1).locator('select').nth(1).select_option('speels')
    o.locator('.chan').nth(1).locator('input[type=text]').first.fill('Kees')
    ok('samenvatting onder het kanaal', 'toon Speels' in o.locator('.chan').nth(1).inner_text() and 'naam Kees' in o.locator('.chan').nth(1).inner_text(), o.locator('.chan').nth(1).inner_text())
    o.screenshot(path='shots/c_kanalen.png', full_page=True)
    o.get_by_role('tab', name='Commando\'s').click(); o.get_by_role('button', name='Commando toevoegen').click()
    o.get_by_label('Naam van het commando').fill('!regels'); o.get_by_label('Antwoord').fill('Wees aardig.')
    o.get_by_role('button', name='Opslaan').click(); o.wait_for_selector('#toast:not([hidden])')
    ok('opslaan geeft melding en balk verdwijnt', 'Opgeslagen' in o.inner_text('#toast') and o.locator('.save').is_hidden())
    j = hub({'servers': [{'id': G1, 'name': 'Mijn server', 'n': 5}]})[1]['guilds'][G1]
    ok('bot krijgt wat in de browser is ingesteld', j['server']['tone'] == 'zakelijk' and j['server']['name'] == 'Core' and j['channels'] == [C1, C2] and j['channel_cfg'][C2]['tone'] == 'speels' and j['channel_cfg'][C2]['name'] == 'Kees' and j['server']['commands'][0]['name'] == 'regels', j)
    o.reload(); o.wait_for_selector('.tabs')
    ok('tabkeuze blijft na verversen', o.get_by_role('tab', name="Commando's").get_attribute('aria-selected') == 'true' and o.input_value('textarea') == 'Wees aardig.')
    o.get_by_role('tab', name='Algemeen').click()
    ok('na verversen staan de waarden er nog', o.input_value('select >> nth=0') == 'zakelijk' and o.input_value('input[maxlength="32"]') == 'Core')
    o.get_by_role('tab', name='Gebruik').click(); ok('gebruikstab', 'Antwoorden vandaag' in o.inner_text('main') and 'Laatste 7 dagen' in o.inner_text('main'))
    ok('geen beheertab voor gewone beheerder', o.get_by_role('tab', name='Beheer').count() == 0)
    o.get_by_role('tab', name='Algemeen').click(); o.select_option('select >> nth=0', 'kort')
    o.get_by_role('button', name='Terugzetten').click(); ok('terugzetten herstelt de opgeslagen waarde', o.input_value('select >> nth=0') == 'zakelijk' and o.locator('.save').is_hidden())
    o.goto(B + '#/platform'); o.wait_for_selector('.rows, .panel'); ok('platform niet zichtbaar voor gewone gebruiker', 'Bot-verbinding' not in o.inner_text('main'))
    ok('geen Platform-link voor gewone gebruiker', o.get_by_role('link', name='Platform').count() == 0)

    # ---- mobiel: dashboard en server
    mo = m.new_page(); attach(mo); login_browser(mo, 'owner'); mo.wait_for_selector('.rows .row')
    mo.screenshot(path='shots/c_dashboard_mobile.png', full_page=True)
    mo.goto(B + '#/server/' + G1); mo.wait_for_selector('.tabs'); mo.get_by_role('tab', name='Kanalen').click(); mo.wait_for_selector('.chan')
    mo.locator('.chan').nth(1).get_by_role('button', name='Eigen instellingen').click()
    ok('server op mobiel: geen horizontale scroll', mo.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), mo.evaluate('[document.documentElement.scrollWidth, window.innerWidth]'))
    mo.screenshot(path='shots/c_server_mobile.png', full_page=True)

    # ---- lid: voorkeuren en wissen
    l = br.new_context(viewport={'width': 1100, 'height': 800}).new_page(); attach(l); login_browser(l, 'member')
    l.wait_for_selector('.rows .row'); ok('lid ziet geen Instellen-knop', l.get_by_role('link', name='Instellen').count() == 0 and 'Alleen beheerders' in l.inner_text('main'))
    l.get_by_role('link', name='Voorkeuren').first.click(); l.wait_for_selector('input[maxlength="32"]')
    l.fill('input[maxlength="32"]', 'Kees'); l.select_option('select', 'speels'); l.get_by_label('De bot mag onthouden wat ik zeg').uncheck()
    l.get_by_role('button', name='Opslaan').click(); l.wait_for_selector('#toast:not([hidden])')
    ok('voorkeuren opgeslagen', json.loads(sql('select prefs from member_prefs where discord_id="222222222222222222"')) == {'nick': 'Kees', 'tone': 'speels', 'memory': False})
    l.screenshot(path='shots/c_voorkeuren.png', full_page=True)
    l.get_by_role('button', name='Verwijder mijn gegevens').click()
    ok('wissen vraagt eerst bevestiging', 'kan niet ongedaan' in l.inner_text('main'))
    l.get_by_role('button', name='Ja, wis alles').click(); l.wait_for_selector('h1:has-text("per kanaal")')
    ok('na wissen: uitgelogd en gegevens weg', sql('select count(*) from users where discord_id="222222222222222222"') == '0' and sql('select count(*) from member_prefs') == '0')

    # ---- beheerder: platform
    ad = br.new_context(viewport={'width': 1200, 'height': 900}).new_page(); attach(ad); login_browser(ad, 'admin')
    ad.get_by_role('link', name='Platform').click(); ad.wait_for_selector('.stats')
    ok('platform: cijfers, verbinding en servertabel', 'Bot online' in ad.inner_text('main') and 'Hub-adres' in ad.inner_text('main') and 'Mijn server' in ad.inner_text('table'), ad.inner_text('main')[:300])
    ad.get_by_role('button', name='Toon bot-sleutel').click(); ad.wait_for_selector('code:has-text("testhubsecret")')
    ok('platform: bot-sleutel op verzoek zichtbaar', True)
    ad.fill('input[placeholder^="qwen3"]', 'qwen3:4b, llama3.1:8b'); ad.get_by_role('button', name='Opslaan').click(); ad.wait_for_selector('#toast:not([hidden])')
    ok('platform: instellingen opgeslagen', sql('select v from settings where k="models_allowed"') == 'qwen3:4b,llama3.1:8b')
    ad.locator('tr', has_text='Mijn server').get_by_role('link', name='Openen').click(); ad.wait_for_selector('.tabs')
    ad.get_by_role('tab', name='Beheer').click(); ad.select_option('select', 'qwen3:4b'); ad.get_by_role('button', name='Opslaan').click(); ad.wait_for_selector('#toast:not([hidden])')
    ok('beheer: model aan server toegekend', sql(f'select model from guilds where guild_id="{G1}"') == 'qwen3:4b')
    ad.screenshot(path='shots/c_platform.png', full_page=True)
    ok('geen console- of CSP-fouten in de hele sessie', not errors, errors[:5])
    br.close()
print(f'\n{n - len(fails)}/{n} geslaagd'); sys.exit(1 if fails else 0)
