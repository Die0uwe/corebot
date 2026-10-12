# CoreBot

Gratis Nederlandse Discord-bot met AI-antwoorden en een eigen webpaneel. Serverbeheerders voegen de bot toe aan hun eigen Discord en stellen toon, kanalen, limieten en commando's in per server en per kanaal. Leden kiezen eigen voorkeuren.

Twee delen in één repo:

| Map | Wat | Waar het draait |
|---|---|---|
| `site/` | corebot.info: PHP 8 + MariaDB, Discord-login, paneel, `hub.php` voor de bot | Strato (eigen database) |
| `bot/` | De Discord-bot (Python, discord.py) met tray-starter | Pc van de beheerder, naast de AI |
| `tests/` | API-, hub- en browsertests van de site met een nep-Discord | Ontwikkelomgeving |
| `docs/` | Architectuur en besluiten | |

## Hoe het samenhangt

```
Discord  <--->  bot (pc)  --ondertekend (HMAC)-->  site/hub.php  <---  paneel (leden en beheerders)
                  |                                   |
                  +-- AI-aanroepen via SBWebUI        +-- eigen database (servers, instellingen, voorkeuren, tellers)
```

- De bot belt de site; de site belt nooit de pc.
- Instellingen erven: standaard < server < kanaal. Alleen afwijkingen worden bewaard.
- Gebruikers kiezen nooit een model. Modellen, schorsing en daglimieten zijn alleen voor de beheerder (Platform).
- SBWebUI blijft los en alleen voor de beheerder. Eén Discord-identiteit, maar corebot-gebruikers krijgen daar nooit een account.

### Als de AI plat ligt

De bot antwoordt dan toch, zonder model: eerst de FAQ van de server, dan een recent antwoord op bijna dezelfde vraag (alleen in het werkgeheugen, 24 uur), dan een vaste zin per toon voor korte groeten en vragen als "ben je er nog?", en anders een eerlijk bericht dat de AI er niet is (per lid max. eens per 10 minuten, daarna een ⏳-reactie). Na 3 mislukte aanroepen gaat de noodrem dicht (30 s, dan 60/120/300 s) zodat leden niet op time-outs wachten. Elke server kan de drie lagen apart uitzetten. Het Platform-scherm toont of de AI aan staat.

Zie `docs/besluiten.md` voor de vastgelegde keuzes (waaronder: AI altijd via SBWebUI).

## Installeren (site)

1. Upload de inhoud van `site/` (of de release-zip) naar de map van het domein. Neem `.htaccess` en `inc/.htaccess` mee.
2. Zet in het Discord Developer Portal bij OAuth2 > Redirects `https://<domein>/callback.php` voor elk domein.
3. Open `install.php`, vul de installatiecode, de databasegegevens (eigen lege database), de Discord-gegevens, jouw Discord-ID en de domeinen in.
4. Controleer dat `install.php` en `inc/install_code.php` verdwenen zijn. `config.php` blijft op de server en staat in `.gitignore`.

Meer in `site/LEES-MIJ.txt`. Domein verhuizen: zet alle domeinen in `allowed_hosts`; `canonical_host` stuurt de rest door.

## Testen

```
cd tests && ./cb_up.sh && python3 t100.py     # API en hub (nep-Discord)
./cb_up.sh && python3 t101.py                 # browser (Playwright)
cd ../bot && python3 test_bot.py && python3 test_v05.py   # bot (oude + v0.5)
cd ../tests && ./cb_up.sh && python3 t102.py  # contract bot <-> echte site
```

Vereist: php 8 (pdo_mysql, curl), MariaDB, python3 met `requests` en `playwright`.

## Stand

Zie `CHANGELOG.md`. Niet getest met echte Discord, echte Strato of Windows.
