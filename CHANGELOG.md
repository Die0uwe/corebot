# Changelog

## bot 0.5.1 / site 0.2.1 (2026-10-12)
- Naam per server: de bot zet de naam die de beheerder op corebot.info koos als bijnaam in die server (recht Bijnaam wijzigen; uitnodiging vraagt het nu mee). Geen naam gekozen = naam van de applicatie. Weigert Discord het, dan probeert de bot niet elke minuut opnieuw.
- Standaardnaam is CoreBot (was SB AI). `bot/UPGRADE.txt`: oude SBWebUI-bot omzetten naar CoreBot via de hub.
- Login zonder `prompt=none` (eerste keer inloggen faalde).

## bot 0.5.0 (2026-10-12)
- Tweede bron: de hub (corebot.info). Publieke servers hebben eigen kanalen, toon, naam, commando's en limieten (binnen strengere grenzen dan het eigen paneel), geen eigen model. Eigen kanalen uit het SBWebUI-paneel gaan voor.
- Ledenvoorkeuren (bijnaam, toon als de server dat toestaat, geen gespreksgeheugen), vergeet-opdracht (geheugen weg, bevestiging bij de volgende sync), gebruik per server terugmelden (`a`, `l`, `e`, `fb`), vertrokken servers melden.
- Serverinstructie van een derde is een stijlvoorkeur die de basisregels nooit opheft (prompt-injectie).
- Terugvallaag (`bot/fallback.py`): als de AI niet antwoordt komt er een antwoord uit de FAQ van de server, een recent antwoord op bijna dezelfde vraag (werkgeheugen, 24 uur, alleen veilige vragen), een vaste zin per toon (groet, bedankt, doei, ben je er, help) of een eerlijk bericht (per lid max. eens per 10 minuten, daarna een ⏳).
- Noodrem: na 3 mislukte AI-aanroepen probeert de bot 30 s niet meer (daarna 60/120/300 s), een lichte controle van Ollama laat een testvraag door. Status (`up`, `since`, `fails`) gaat mee in de sync.
- Tests: 150 (ongewijzigd) + 69 (`test_v05.py`) + 29 integratie met de echte site (`tests/t102.py`).

## site 0.2.0 (2026-10-12)
- AI-terugval, site-kant: FAQ per server (tabblad Veelgestelde vragen, max. 30), schakelaars `fallback` (faq/cache/templates), `faq` en `fallback` in de hub-config per server.
- Hub: optioneel `ai` {up, since, fails} in het sync-verzoek, `fb` per server in `usage`; Platform toont AI-status en "Via terugval". Schema 2: kolom `usage_daily.fallback` (migratie via information_schema).
- Privacytekst uitgebreid over de terugval en het werkgeheugen van de bot.

## site 0.1.1 (2026-10-12)
- Meerdere domeinen uit één map: `allowed_hosts`, `canonical_host`, redirect-adressen per domein, installer vraagt de domeinen.
- Schema wordt aangemaakt bij de eerste aanroep van `hub.php` en `login.php`.

## site 0.1.0 (2026-10-12)
- Eerste versie: Discord-login (identify + guilds), serverlijst, instellingen per server en kanaal, ledenvoorkeuren, wissen van gegevens, platformscherm, `hub.php` voor de bot, privacy- en voorwaardenpagina.
- Tests: 106 (API/hub) en 36 (browser) tegen een nep-Discord.

## bot 0.4.0
- Meerdere servers, profielen per server en kanaal, tonen, commando's. 150 tests. Overgenomen uit Die0uwe/SBwebui (`tools/discord-bot`).

## Volgende
- C-006: AI-aanroepen via SBWebUI (zie `docs/besluiten.md`).
