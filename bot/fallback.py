"""Terugvallaag voor als de AI niet bereikbaar is (CoreBot v0.5).

Volgorde: FAQ van de server -> recent antwoord op dezelfde vraag (alleen werkgeheugen, 24 uur) -> vaste antwoorden op simpele zinnen
-> een eerlijk bericht. Niets hiervan gebruikt een model; het zijn woordvergelijkingen en vaste teksten in de toon van de laag.
Geen netwerk en geen bestanden: alles is testbaar zonder Discord."""
import difflib
import re
import time
import unicodedata
from collections import OrderedDict

# Vraagwoorden (wanneer, waar, hoe, wie) blijven bewust staan: ze onderscheiden "wanneer is de raid" van "waar is de raid".
STOP = frozenset(
    'de het een en of ik je jij jou jouw u uw we wij jullie zij ze hij mijn me mij dat dit die deze er ook maar met aan bij om naar niet wel '
    'nog hier daar te van in op voor als dan zo nu toch even eens hoor is zijn was ben bent kan kun kunt mag moet gaat gaan heb heeft hebben '
    'zou zouden wil willen iemand weet weten graag alvast bedankt'.split())
THRESHOLD_FAQ = 0.62
THRESHOLD_CACHE = 0.85
MARGIN = 0.08
CACHE_TTL = 86400
CACHE_PER_GUILD = 200
# woorden die verwijzen naar eerder in het gesprek: zo'n antwoord is los van de geschiedenis niet bruikbaar voor iemand anders
REFERENTIAL = frozenset('dat dit die deze daar hij zij hem haar ervan daarvan dan daarom'.split())


def words(text: str) -> list[str]:
    """Kleine letters, zonder accenten en leestekens."""
    t = unicodedata.normalize('NFKD', text.lower())
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', t).split()


def stem(t: str) -> str:
    if len(t) > 4 and t.endswith('en'):
        return t[:-2]
    if len(t) > 3 and t.endswith('s'):
        return t[:-1]
    return t


def tokens(text: str) -> list[str]:
    return [stem(w) for w in words(text) if w not in STOP and (len(w) > 1 or w.isdigit())]


def _same(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if min(len(a), len(b)) < 4:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return r if r >= 0.8 else 0.0  # typefouten: "rad" voor "raid" telt, "pizza" voor "regels" niet


def score(want: list[str], have: list[str]) -> tuple[float, int]:
    """Hoe goed dekt `have` (het bericht) de woorden van `want` (de FAQ-vraag)? Geeft (score 0-1, aantal gevonden woorden)."""
    if not want or not have:
        return 0.0, 0
    used: set[int] = set()
    got, n = 0.0, 0
    for t in want:
        best, bi = 0.0, -1
        for i, u in enumerate(have):
            if i in used:
                continue
            w = _same(t, u)
            if w > best:
                best, bi = w, i
        if bi >= 0:
            used.add(bi)
            got += best
            n += 1
    return 0.7 * got / len(want) + 0.3 * min(1.0, got / len(have)), n


def faq_match(text: str, faq: list[dict]) -> str | None:
    """Antwoord uit de FAQ als er duidelijk één vraag bij past, anders None (liever niets dan een verkeerd antwoord)."""
    have = tokens(text)
    if not have or not faq:
        return None
    scored: list[tuple[float, int, str]] = []
    for it in faq:
        want = tokens(str(it.get('q', '')))
        s, n = score(want, have)
        if want and n >= min(2, len(want)):
            scored.append((s, n, str(it.get('a', ''))))
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < THRESHOLD_FAQ:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < MARGIN and scored[0][2] != scored[1][2]:
        return None
    return scored[0][2]


class AnswerCache:
    """Recent AI-antwoorden per server, alleen in het werkgeheugen. Verdwijnt bij een herstart; er gaat niets naar schijf of database."""

    def __init__(self, ttl: float = CACHE_TTL, per_guild: int = CACHE_PER_GUILD):
        self.ttl, self.per_guild = ttl, per_guild
        self.data: dict[int, OrderedDict[tuple, tuple[float, str, str]]] = {}

    @staticmethod
    def cacheable(question: str, answer: str) -> bool:
        raw = words(question)
        if len(question) > 200 or len(answer) > 1500 or '@' in question or re.search(r'\d{6,}', question):
            return False  # geen namen/nummers van mensen in het geheugen
        if REFERENTIAL & set(raw):
            return False
        return len(tokens(question)) >= 3

    def put(self, gid: int, question: str, answer: str, now: float | None = None) -> bool:
        if not self.cacheable(question, answer):
            return False
        now = time.time() if now is None else now
        d = self.data.setdefault(gid, OrderedDict())
        key = tuple(sorted(tokens(question)))
        d[key] = (now, ' '.join(tokens(question)), answer)
        d.move_to_end(key)
        while len(d) > self.per_guild:
            d.popitem(last=False)
        return True

    def get(self, gid: int, question: str, now: float | None = None) -> str | None:
        now = time.time() if now is None else now
        d = self.data.get(gid)
        have = tokens(question)
        if not d or len(have) < 3:
            return None
        for key in [k for k, (t, _, _) in d.items() if now - t > self.ttl]:
            del d[key]
        best, ans = 0.0, None
        for key, (_, _, a) in d.items():
            s = min(score(list(key), have)[0], score(have, list(key))[0])
            if s > best:
                best, ans = s, a
        return ans if best >= THRESHOLD_CACHE else None

    def clear(self) -> None:
        self.data.clear()


class Breaker:
    """Noodrem: na `threshold` mislukte AI-aanroepen probeert de bot een tijd niet meer (leden wachten dan niet op een time-out).
    Daarna mag één vraag als test door; lukt die, dan is de rem los. Het wachten loopt op: 30, 60, 120, 300 seconden."""

    def __init__(self, threshold: int = 3, steps: tuple = (30, 60, 120, 300)):
        self.threshold, self.steps = threshold, steps
        self.streak, self.opened, self.open_until = 0, 0, float('-inf')
        self.since = int(time.time())

    @property
    def up(self) -> bool:
        return self.streak < self.threshold

    def allow(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return self.up or now >= self.open_until

    def ok(self, wall: float | None = None) -> None:
        if not self.up:
            self.since = int(time.time() if wall is None else wall)
        self.streak, self.opened, self.open_until = 0, 0, float('-inf')

    def fail(self, now: float | None = None, wall: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        was_up = self.up
        self.streak += 1
        if self.streak >= self.threshold:
            self.open_until = now + self.steps[min(self.opened, len(self.steps) - 1)]
            self.opened += 1
            if was_up:
                self.since = int(time.time() if wall is None else wall)

    def recover(self, wall: float | None = None) -> None:
        """De AI antwoordt weer op een lichte controle: laat de volgende vraag door als test. Mislukt die, dan gaat de rem meteen weer dicht."""
        if not self.up:
            self.streak = self.threshold - 1
            self.open_until = float('-inf')
            self.since = int(time.time() if wall is None else wall)

    def status(self) -> dict:
        return {'up': self.up, 'since': self.since, 'fails': self.streak}


# ---------- vaste antwoorden ----------
GREET = frozenset('hoi hallo hey hee hi yo dag goedemorgen goedemiddag goedenavond goedennacht welkom moin hoihoi heyy hallo allemaal iedereen bot corebot daar'.split())
THANKS = frozenset('bedankt dank dankje dankjewel dankuwel thanks thx merci tnx top netjes lekker'.split())
BYE = frozenset('doei doeg tot ziens later ciao groetjes welterusten slaapwel dag'.split())
ALIVE = re.compile(r'\b(ben je er|ben je online|ben je wakker|werkt de bot|werkt (deze )?bot|doet de bot het|leef je|leeft de bot|bot kapot|hoor je me|is de bot er|ping)\b')
HELP = re.compile(r'\b(wat kun je|wat kan je|wat kunnen jullie|wat doe je|hoe werkt dit|hoe werkt de bot|help|hulp|commando|commandos)\b')

TEMPLATES: dict[str, dict[str, str]] = {
    'greeting': {
        'standaard': 'Hoi! Stel gerust je vraag. De AI is er nu even niet, dus ik kan alleen simpele dingen beantwoorden.',
        'vriendelijk': 'Hoi hoi! 😊 Leuk dat je er bent. De AI is er even niet, maar stel je vraag gerust.',
        'zakelijk': 'Goedendag. De AI is momenteel niet beschikbaar; eenvoudige vragen kan ik nog beantwoorden.',
        'speels': 'Hoi! 👋 Mijn AI-brein is even koffie halen, maar ik ben er nog.',
        'kort': 'Hoi! De AI is er even niet.',
        'uitleg': 'Hoi! Even uitleg: de AI is nu niet bereikbaar. Ik kan alleen vaste vragen en commando\'s beantwoorden.',
        'streng': 'Hallo. De AI is nu niet beschikbaar. Houd je aan de serverregels en probeer het later opnieuw.',
    },
    'thanks': {
        'standaard': 'Graag gedaan!', 'vriendelijk': 'Graag gedaan! 😊', 'zakelijk': 'Graag gedaan.', 'speels': 'Altijd! 🎉',
        'kort': 'Graag gedaan.', 'uitleg': 'Graag gedaan! Vraag gerust als iets nog niet duidelijk is.', 'streng': 'Geen dank.',
    },
    'bye': {
        'standaard': 'Doei! Tot de volgende keer.', 'vriendelijk': 'Doei, tot snel! 👋', 'zakelijk': 'Tot ziens.', 'speels': 'Tot later, houd de moed erin! 🚀',
        'kort': 'Doei!', 'uitleg': 'Tot ziens! Kom gerust terug als je meer wilt weten.', 'streng': 'Tot ziens.',
    },
    'alive': {
        'standaard': 'Ik ben er, maar de AI is nu niet bereikbaar. Commando\'s en veelgestelde vragen werken nog.',
        'vriendelijk': 'Ik ben er nog! 😊 Alleen de AI is even niet bereikbaar; commando\'s en veelgestelde vragen werken wel.',
        'zakelijk': 'De bot is actief. De AI is momenteel niet bereikbaar; commando\'s en veelgestelde vragen werken.',
        'speels': 'Nog springlevend! 🎈 Alleen mijn AI-brein is offline.',
        'kort': 'Ik ben er; de AI niet.',
        'uitleg': 'De bot draait, maar de AI is niet bereikbaar. Daardoor kan ik alleen vaste antwoorden en commando\'s geven.',
        'streng': 'De bot is actief. De AI is niet beschikbaar. Wacht tot die terug is.',
    },
    'help': {
        'standaard': 'Stel je vraag in dit kanaal. De AI is er nu even niet; {cmds}',
        'vriendelijk': 'Je kunt hier gewoon je vraag stellen! 😊 De AI is er nu even niet; {cmds}',
        'zakelijk': 'Stel uw vraag in dit kanaal. De AI is momenteel niet beschikbaar; {cmds}',
        'speels': 'Gooi je vraag maar in het kanaal! 🎯 Mijn AI is even weg; {cmds}',
        'kort': 'Stel je vraag hier. {cmds}',
        'uitleg': 'Zo werkt het: typ je vraag in dit kanaal, dan antwoordt de bot. De AI is nu niet bereikbaar; {cmds}',
        'streng': 'Stel je vraag in dit kanaal en houd je aan de regels. De AI is niet beschikbaar; {cmds}',
    },
}
HONEST = {
    'standaard': 'De AI is nu niet bereikbaar, dus ik kan hier geen antwoord op geven. Probeer het later nog eens.',
    'vriendelijk': 'Oei, de AI is nu niet bereikbaar, dus ik kan je hier niet mee helpen. 😊 Probeer het later nog eens!',
    'zakelijk': 'De AI is momenteel niet bereikbaar. Ik kan uw vraag nu niet beantwoorden. Probeer het later opnieuw.',
    'speels': 'Mijn AI-brein is niet bereikbaar. 🙈 Probeer het straks nog eens!',
    'kort': 'De AI is niet bereikbaar. Probeer het later.',
    'uitleg': 'De AI is op dit moment niet bereikbaar. Daardoor kan ik je vraag niet beantwoorden. Probeer het later opnieuw, of vraag het aan een beheerder.',
    'streng': 'De AI is niet bereikbaar. Ik kan nu niet antwoorden. Probeer het later opnieuw of vraag het een beheerder.',
}


def intent(text: str) -> str | None:
    """Alleen korte, duidelijke zinnen: "hoi, kun je mijn code fixen" is geen groet."""
    w = words(text)
    flat = ' '.join(w)
    if not w or len(w) > 7:
        return None
    if ALIVE.search(flat):
        return 'alive'
    if HELP.search(flat) and len(w) <= 6:
        return 'help'
    if len(w) <= 5 and set(w) & THANKS:
        return 'thanks'
    if len(w) <= 4 and set(w) <= GREET:
        return 'greeting'
    if len(w) <= 4 and (set(w) & {'doei', 'doeg', 'ciao', 'groetjes', 'welterusten', 'slaapwel'} or flat in ('tot ziens', 'tot later', 'tot morgen', 'tot straks')):
        return 'bye'
    return None


def commands_text(cmds: list[str]) -> str:
    return ('commando\'s die werken: ' + ', '.join('!' + c for c in cmds) + '.') if cmds else 'er zijn nog geen commando\'s.'


def template_answer(text: str, tone: str, cmds: list[str]) -> str | None:
    it = intent(text)
    if it is None:
        return None
    return TEMPLATES[it].get(tone, TEMPLATES[it]['standaard']).format(cmds=commands_text(cmds))


def honest_message(tone: str) -> str:
    return HONEST.get(tone, HONEST['standaard'])


def pick_fallback(text: str, tone: str, faq: list[dict], flags: dict, cache: AnswerCache | None, gid: int, cmds: list[str],
                  now: float | None = None) -> tuple[str, str] | None:
    """Eerste laag die iets vindt: ('faq' | 'cache' | 'template', tekst). None = niets passend; gebruik dan honest_message."""
    if flags.get('faq', True):
        a = faq_match(text, faq)
        if a:
            return 'faq', a
    if flags.get('cache', True) and cache is not None:
        a = cache.get(gid, text, now)
        if a:
            return 'cache', a
    if flags.get('templates', True):
        a = template_answer(text, tone, cmds)
        if a:
            return 'template', a
    return None
