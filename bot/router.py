"""Beslist vooraf, zonder model, of een vraag naar ScriptSpace moet.

Doorverwijzen: iemand vraagt om iets te MAKEN of te SCHRIJVEN in HTML/CSS/JS/code of een website
(-> scriptspace.nl), of vraagt om CMS-werk (-> cms.scriptspace.nl).
Uitleg-vragen ("wat is HTML?") blijven gewoon bij de bot. Wat hier niet matcht gaat naar het model,
dat dezelfde regel in zijn opdracht heeft staan als vangnet."""
import re

WEB_URL = 'https://scriptspace.nl'
CMS_URL = 'https://cms.scriptspace.nl'

_MAKE = r'(maak|maken|bouw|bouwen|schrijf|schrijven|genereer|genereren|programmeer|programmeren|codeer|coder|ontwerp|ontwerpen|creëer|creeer|creëren|geef\s+(me|mij)|kun\s+je\s+.*\bmaken|kan\s+je\s+.*\bmaken|laat\s+.*\bzien)'
_WEB = r'(html|css|javascript|typescript|\bjs\b|php|react|vue|svelte|tailwind|bootstrap|\bcode\b|\bscript\b|\bscripts\b|website|webpagina|web\s*pagina|webshop|landingpage|landing\s*page|homepage|navigatiebalk)'
_CMS = r'(\bcms\b|content\s*management|wordpress|joomla|drupal|\bblog\b|\bbeheerpagina|\bthema\b|\btheme\b|\bplugin\b|\bblokken\b|\bwebsite\s*beheren)'


def classify(text: str) -> str:
    """'cms', 'web' of 'chat'."""
    t = text.lower()
    if '```' in text and re.search(r'(<\w+[^>]*>|\{[^}]*:[^}]*\}|function\s|const\s|def\s)', text):
        return 'web' if not re.search(_CMS, t) else 'cms'
    has_make = re.search(_MAKE, t) is not None
    if re.search(_CMS, t) and has_make:
        return 'cms'
    if has_make and re.search(_WEB, t):
        return 'cms' if re.search(_CMS, t) else 'web'
    return 'chat'


WEB_REPLY = ('Voor het maken van HTML, CSS, code en websites ga je naar **ScriptSpace**: {web}\n'
             'Daar bouw je het met hulp van de AI en zie je het resultaat meteen. Hier in Discord beantwoord ik alleen vragen en gewone gesprekken.')
CMS_REPLY = ('Voor alles rond het CMS ga je naar **CMS ScriptSpace**: {cms}\n'
             'Hier in Discord beantwoord ik alleen vragen en gewone gesprekken.')


def referral(kind: str, web: str = WEB_URL, cms: str = CMS_URL) -> str:
    return (CMS_REPLY if kind == 'cms' else WEB_REPLY).format(web=web, cms=cms)
