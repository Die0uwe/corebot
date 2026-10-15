# Bot v0.3.2 (en bijbehorende site-wijzigingen)

## Nieuw
- Beheer > Discord-bot > kaart "Rechten per kanaal": per kanaal ✓/✗ voor Kanaal bekijken, Berichten sturen, Berichtgeschiedenis lezen, Links insluiten en Berichten sturen in threads.
- Gekozen antwoordkanalen (bij "Waar antwoordt de bot?"): ontbrekend Bekijken/Sturen/Geschiedenis = rood; ontbrekend Links/Threads = geel (optioneel). Een gekozen kanaal dat de bot niet ziet staat er ook in (rood).
- Overige privékanalen: aparte tabel, alleen informatie (grijs, nooit een fout). Openbare kanalen waar de bot niet antwoordt worden alleen geteld.
- Bij een ontbrekend recht een Nederlandse oplossingstekst ("Geef de rol van de bot in dit kanaal Berichtgeschiedenis lezen: Kanaal bewerken > Rechten > Geavanceerde rechten"). De handleiding wordt alleen in tekst genoemd.
- Knop "Opnieuw controleren": zet via het bestaande mechanisme (bot_test / bot_action) een opdracht `recheck` klaar. De bot meldt na die opdracht direct een extra hartslag (binnen ca. 1 s) met verse rechten en de uitkomst. Naast de knop: "Laatst gecontroleerd om hh:mm:ss".
- Hartslag: per kanaal twee vlaggen erbij (`l`, `t`) en een tijdstip `perm_at`. Alleen ids, namen en vlaggen; geen berichtinhoud.

## Gefixt
- Pauzemelding kwam niet bij een pc die korter dan 5 minuten aan stond (`notice_at` begon op 0.0 en `time.monotonic()` is dan < 300). Deze fout zat al in v0.3.1 en veroorzaakte de enige falende test van de vorige 102 (nu terug naar groen). Het kan zich in het echt voordoen bij autostart direct na het aanzetten van de pc.
- Melding bij ontbrekende geschiedenisrechten bovenaan het paneel is nu rood (was geel) en verwijst naar de nieuwe kaart.

## Site (SB_VERSION en schema ongewijzigd)
- `inc/social.php`: bot_action_create kent type `recheck`; bot_record bewaart `l`, `t`, `perm_at` (onbekend = null bij bot < 0.3.2; perm_at begrensd op nu); nieuwe `bot_perm_report`, `BOT_PERMS`, `bot_perm_fix`; `bot_overview` levert `perms`.
- `assets/app.js`: alleen in `adminBot` (kaart, `renderPerms`, knop, een regel in `actionLine`, `refresh`, `box.append`).
- `api.php` en `bot_ping.php`: niet gewijzigd (`bot_test` vangt de nieuwe opdracht al op; admin-only, CSRF, 400 bij onbekend type).

## Getest (lokaal, geen echte Discord)
- test_bot.py: 113/113 (was 102; +11: vlaggen l/t, ontbrekend recht per kanaal, recheck-actie, zelfde id geen tweede hartslag, echte hartslaglus met nepserver: tweede hartslag binnen enkele seconden met uitkomst, pauzemelding-regressie).
- t084 29/29, t085 30/30 (schema 12), t086 47/47, t087_bot 45/45 (Playwright, hartslag nagebootst via een ondertekende POST naar bot_ping.php).
- t087 controleert o.a.: ✓/✗ per kanaal, ingesteld rood/geel versus informatie grijs, oplossingstekst, knop zet opdracht klaar en toont uitkomst, tweede klik tijdens wachten geweigerd, onbekend type 400, zonder CSRF 403, lid 403, gast 401, oudere bot zonder l/t ("–"), geschoonde kanaalnamen, mobiel zonder horizontale paginascroll, geen JS-fouten.

## Niet getest
- Echte Discord: of `permissions_for(...).embed_links` en `.send_messages_in_threads` in jouw discord.py-versie bestaan en kloppen. In de tests zijn het nepobjecten. Verwacht ze in discord.py 2.x, maar niet gezien.
- Rechten komen uit de cache van de bot; een rechtenwijziging in Discord kan zijn gateway-event net iets later krijgen dan de knop. De knop dwingt een verse hartslag af, geen nieuwe ophaalactie bij Discord.
- Privékanalen, overschrijvingen per rol/lid, Strato, Windows-tray, de bot met de tray (stop/herstart tijdens een recheck).
- Een bot v0.3.1 met de nieuwe site: alleen nagebootst (geen l/t, recheck geeft "onbekende opdracht" en de UI toont de hint om te updaten).
- Gelijktijdige edits door de andere ontwikkelaar in app.js: geen conflict gezien, maar niet specifiek getest.
