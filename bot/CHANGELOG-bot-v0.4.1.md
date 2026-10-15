# Bot v0.4.1
Bibliotheek als kennisbron: vóór elk antwoord vraagt de bot `bot_rag.php` om fragmenten (ondertekend met hetzelfde geheim als de hartslag, 4 s time-out). Fragmenten gaan vóór de vraag naar het model; onder het antwoord hooguit twee bronnen als link (zonder voorbeeldkaart). Onbereikbaar of leeg: gewoon antwoord. Uit te zetten met `LIBRARY=0` in `.env`.
Vereist site v0.9.8 voor `bot_rag.php`; met een oudere site werkt de bot zoals v0.4.0.
Tests: `test_bot.py` 159/159 (nagebootste Discord, Ollama en site). Niet getest met echte Discord.
