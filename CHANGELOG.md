# Changelog

## site 0.1.1 (2026-10-12)
- Meerdere domeinen uit één map: `allowed_hosts`, `canonical_host`, redirect-adressen per domein, installer vraagt de domeinen.
- Schema wordt aangemaakt bij de eerste aanroep van `hub.php` en `login.php`.

## site 0.1.0 (2026-10-12)
- Eerste versie: Discord-login (identify + guilds), serverlijst, instellingen per server en kanaal, ledenvoorkeuren, wissen van gegevens, platformscherm, `hub.php` voor de bot, privacy- en voorwaardenpagina.
- Tests: 106 (API/hub) en 36 (browser) tegen een nep-Discord.

## bot 0.4.0
- Meerdere servers, profielen per server en kanaal, tonen, commando's. 150 tests. Overgenomen uit Die0uwe/SBwebui (`tools/discord-bot`).

## Volgende
- Bot 0.5: tweede bron `hub` (corebot.info) naast SBWebUI, ledenvoorkeuren, vergeet-opdracht, gebruik terugmelden, beperkte serverinstructie tegen prompt-injectie.
- C-006: AI-aanroepen via SBWebUI (zie `docs/besluiten.md`).
