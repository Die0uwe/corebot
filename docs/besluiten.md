# Besluiten CoreBot

| ID | Besluit | Status | Datum |
|---|---|---|---|
| C-001 | corebot.info is de publieke kant; eigen Strato-database, los van SBWebUI | Gegeven (Ouwe) | 2026-10-12 |
| C-002 | Eén Discord-login. Gebruikers worden nooit beheerder of lid van SBWebUI; SBWebUI blijft admin-only | Gegeven (Ouwe) | 2026-10-12 |
| C-003 | Gebruikers kiezen geen model en zien geen modelnamen; de beheerder kent modellen per server toe | Gegeven door ontwerp | 2026-10-12 |
| C-004 | De bot belt de site (HMAC-ondertekend); de site belt nooit de pc | Gegeven door ontwerp (Strato-database niet extern bereikbaar) | 2026-10-12 |
| C-005 | De site werkt op meerdere domeinen uit één map (corebot.scriptspace.nl nu, corebot.info straks) | Gebouwd v0.1.1 | 2026-10-12 |
| C-006 | **De AI van de bot loopt altijd via SBWebUI.** Of het een gratis (lokale) of betaalde aanbieder is, bepaalt de beheerder in SBWebUI; de andere opties blijven daar beschikbaar. corebot.info bewaart geen AI-sleutels | Gegeven (Ouwe); **nog niet gebouwd**: de bot praat nu rechtstreeks met Ollama | 2026-10-12 |

## Open voor C-006

- SBWebUI heeft nog geen endpoint voor de bot. Voorstel: een ondertekend `bot_ai.php` (zelfde HMAC-patroon als de hartslag) dat de bestaande modelkeuze en terugvaloptie van SBWebUI gebruikt, met streaming. De bot stuurt alleen de vraag, de systeemprompt van de laag (server/kanaal) en het gekozen model; SBWebUI beslist de aanbieder.
- Privacytekst (`site/legal.php`) moet dan melden dat een vraag naar een externe aanbieder kan gaan als de beheerder een betaalde aanbieder aanzet. De tekst staat daar nu al voorwaardelijk.
- Daglimieten en limieten per lid blijven in de bot en de hub; SBWebUI telt eigen verbruik apart.
