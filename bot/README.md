# SBWebUI Discord-bot

Beantwoordt vragen in **de kanalen die je in het beheerpaneel kiest** met je eigen Ollama. Start en stop hem met een tray-icoon, zonder terminal.

- **Gewone vragen en gesprekken:** de bot antwoordt zelf (via de Ollama-API), kort en in het Nederlands, met datum en tijd erbij.
- **HTML, CSS, code of een website laten maken:** de bot schrijft die niet, maar verwijst naar **https://scriptspace.nl**.
- **CMS-werk:** verwijzing naar **https://cms.scriptspace.nl**.
- Uitleg ("wat is HTML?") mag de bot wel geven, zonder code te schrijven.
- Negeert andere kanalen, DM's en andere bots. Cooldown per gebruiker (standaard 8 s) en een uurlimiet (20).
- Eigen `!commando's` met vast antwoord, en foutmeldingen in een apart kanaal dat alleen beheerders zien.
- Berichten van de bot pingen nooit iemand (`@everyone` en `@here` worden onschadelijk gemaakt).

De verwijsregel staat op twee plekken: `router.py` beslist vooraf zonder model (dus betrouwbaar), en de opdracht aan het model is het vangnet voor wat de router niet herkent.

## Waarom op je pc en niet op Strato
Om op gewone berichten te reageren moet de bot ingelogd blijven bij Discord. Dat vraagt een proces dat de hele tijd draait; dat kan niet op shared hosting. Op je pc staat Ollama al, dus daar werkt het zonder tunnel. De bot antwoordt alleen als de pc en het script aan staan.

## Instellen
Een uitgebreide stap-voor-stap-hulp met afvinklijst, `.env`-bouwer en probleemoplossing staat in [`SETUP-HELP.html`](SETUP-HELP.html) (open in je browser).

1. https://discord.com/developers/applications → **New Application** → tabblad **Bot** → **Reset Token** en bewaar het token.
2. Zelfde tabblad, **Privileged Gateway Intents**: zet **Message Content Intent** aan. Zonder dit ziet de bot geen berichttekst.
3. **OAuth2 → URL Generator**: scope `bot`; rechten: *View Channels*, *Send Messages*, *Read Message History*. Open de URL en voeg de bot toe aan je server.
4. **Privékanaal (zoals een admin-testroom)?** Voeg de bot daar ook zelf toe: Kanaal bewerken → Rechten → Rol of lid toevoegen → de bot, met die drie rechten op ✓. Dit is de meest voorkomende reden dat een bot "niks doet".
5. In het paneel (Beheer → Discord-bot) bij **Verbinding**: **Geheim maken**. Kopieer `.env.example` naar `.env`, vul `DISCORD_TOKEN`, `SBWEBUI_PING_URL` en `SBWEBUI_BOT_SECRET` in. `OLLAMA_MODEL` moet een model zijn dat je met `ollama list` ziet.
6. Dubbelklik **`start-tray.bat`**. De eerste keer maakt die een eigen Python-omgeving (Python 3.10+). Daarna verschijnt een icoon naast de klok; de bot start meteen.
7. Kies in het paneel bij "Waar antwoordt de bot?" je kanaal, sla op en druk op **Test**. Dat werkt binnen 30 seconden, zonder herstart.

Liever zonder tray? `start-bot.bat` start de bot in een venster. Zet je dan `DISCORD_CHANNEL_ID` in `.env`, dan werkt hij ook zonder paneel.

Het token staat alleen in `.env` en komt nooit in git. Lekt het ooit, druk dan op Reset Token.

## Tray-starter (start/stop zonder terminal)
`tray.py` (via `start-tray.bat`) is een klein venster in de kleuren van de site met Start, Stop, Herstart, een logboek en een icoon in het systeemvak. Het kruisje en minimaliseren sturen het naar het systeemvak; **Afsluiten** in het icoonmenu stopt ook de bot. Opties: bot starten zodra de starter start, en starten met Windows (verborgen, via `start-tray-hidden.vbs`). Crasht de bot, dan herstart de starter hem; na 3 crashes in 5 minuten blijft hij gestopt en staat de reden in het logboek (`bot.log`).
De bot draait als apart proces zonder consolevenster. Een slot op een lokale poort voorkomt dat `start-bot.bat` en de tray-starter allebei een bot starten (dan zou elke vraag dubbel beantwoord worden).

## Beheerpaneel (Beheer → Discord-bot in SBWebUI)
De bot meldt zich elke 30 seconden op de site (`bot_ping.php`, ondertekend met een geheim); de tray-starter doet dat apart. In het paneel:
- **Status** met Start, Stop, Herstart (via de tray-starter) en Pauzeren.
- **Kanalen** kiezen met een vinkje per kanaal, met per kanaal of de bot mag zien, schrijven en lezen, en een Test-knop. Het paneel zegt het als de bot een kanaal niet ziet.
- **Foutmeldingen in een apart kanaal**: alleen naar een kanaal dat niet voor @everyone zichtbaar is.
- Instellingen (naam, model, wachttijd, limieten, geheugen, adressen, extra instructie), eigen commando's, activiteit, statistiek en deze documentatie.
- Wijzigingen werken binnen 30 seconden, zonder herstart.
De hartslag bevat geen berichten of gebruikersnamen. Laat je `SBWEBUI_PING_URL` en `SBWEBUI_BOT_SECRET` leeg, dan werkt de bot zonder paneel (met `DISCORD_CHANNEL_ID`).

## Tests
- `python test_bot.py`: 92 controles zonder Discord (router, limieten, instellingen van het paneel, commando's, alarmkanaal, rechten van kanalen, testopdrachten, de volledige berichtstroom met nepberichten).
- `python test_v05.py`: 69 controles voor de hub-koppeling, publieke grenzen, ledenvoorkeuren, vergeten, de terugvallaag en de noodrem.
- `python test_manager.py`: 29 controles van het starten, stoppen, crashbewaking en de afstandsbediening tegen een nepsite.
- `xvfb-run -a python test_tray.py` (Linux) of `python test_tray.py` (met scherm): hulpfuncties en een rooktest van het venster.
**Niet getest:** echt inloggen bij Discord, een echt Ollama-model, de tray op Windows (alleen onder Linux/Xvfb), de Windows-autostart (registry) en `pythonw` zonder venster. Probeer na het opstarten: "welke dag is het?", "wat is HTML?", "maak een html pagina met een knop" en "bouw een plugin voor mijn cms".

## v0.5: corebot.info en terugval
- `COREBOT_HUB_URL` en `COREBOT_HUB_SECRET` in `.env` (zie `.env.example`) koppelen de bot aan corebot.info. Elke minuut meldt de bot zijn servers, tellers en AI-status en haalt hij instellingen, FAQ en ledenvoorkeuren op (`hub.py`).
- Zonder paneel én zonder `DISCORD_CHANNEL_ID` start de bot ook als alleen de hub is ingesteld.
- Terugvalmodule: `fallback.py` (FAQ, antwoordgeheugen, vaste zinnen, noodrem). Tests: `python test_v05.py`.

## Bekende grenzen
- Het antwoordgeheugen van de terugval staat alleen in het werkgeheugen (24 uur, max. 200 per server) en is weg na een herstart.
- Het geheugen is kort (6 berichten per gebruiker, in het werkgeheugen) en weg na een herstart.
- De router werkt op Nederlandse trefwoorden; een vraag in nette zinnen zonder die woorden kan erdoor komen. Dan houdt het model zich aan de regel, maar dat is minder streng dan de router.
- Een klein model als qwen3:4b kan zich vergissen; de verwijzing zelf komt altijd van de router.
