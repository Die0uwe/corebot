"""Koppeling met corebot.info (de hub): de bot roept de site aan, nooit andersom.
Elk verzoek is ondertekend (HMAC-SHA256 over de body, header X-Bot-Signature). Geen berichten of gebruikersnamen in de body:
alleen servers (id, naam, icoon, ledental, kanalen), tellers en de AI-status. Zie site/inc/hub.php voor de andere kant."""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict

import aiohttp

log = logging.getLogger('sbbot.hub')
MAX_BODY = 120_000          # de site weigert > 140000; marge voor de koppen
MAX_SERVERS_PER_CALL = 25
USAGE_KEYS = ('a', 'l', 'e', 'fb')


class HubClient:
    def __init__(self, url: str, secret: str, version: str):
        self.url, self.secret, self.version = url, secret, version
        self.usage: dict[int, dict[str, int]] = defaultdict(lambda: {k: 0 for k in USAGE_KEYS})
        self.ack: set[int] = set()
        self.left: set[int] = set()
        self.ok_at = 0.0
        self.fails = 0

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.secret)

    def count(self, gid: int, key: str, n: int = 1) -> None:
        if gid and key in USAGE_KEYS:
            u = self.usage[gid]
            u[key] = min(u[key] + n, 100_000)

    def sign(self, raw: str) -> str:
        return hmac.new(self.secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

    def bodies(self, servers: list[dict], ai: dict, app_id: str = '', now: float | None = None) -> list[tuple[str, dict]]:
        """Verdeelt de servers over één of meer verzoeken (max. 25 servers en ~120 kB per verzoek). Het eerste verzoek draagt tellers,
        vertrokken servers, vergeetbevestigingen en AI-status. Geeft (body, wat-erin-zat) terug zodat alleen aangekomen tellers verdwijnen."""
        ts = int(time.time() if now is None else now)
        usage = {str(g): dict(u) for g, u in self.usage.items() if any(u.values())}
        head = {'ts': ts, 'version': self.version, 'app_id': app_id, 'usage': usage, 'left': [str(g) for g in sorted(self.left)][:100],
                'ack_forget': [str(i) for i in sorted(self.ack)][:200], 'ai': ai}
        groups: list[list[dict]] = [[]]
        size = 0
        for s in servers:
            n = len(json.dumps(s, separators=(',', ':'), ensure_ascii=False))
            if groups[-1] and (len(groups[-1]) >= MAX_SERVERS_PER_CALL or size + n > MAX_BODY - 4000):
                groups.append([])
                size = 0
            groups[-1].append(s)
            size += n
        out = []
        for i, g in enumerate(groups):
            d = {'ts': ts, 'version': self.version, 'app_id': app_id, 'servers': g}
            sent: dict = {'usage': {}, 'left': [], 'ack': []}
            if i == 0:
                d.update({k: head[k] for k in ('usage', 'left', 'ack_forget', 'ai')})
                sent = {'usage': {int(g_): dict(u) for g_, u in usage.items()}, 'left': sorted(self.left)[:100], 'ack': sorted(self.ack)[:200]}
            out.append((json.dumps(d, separators=(',', ':'), ensure_ascii=False), sent))
        return out

    def settle(self, sent: dict) -> None:
        for g, u in sent['usage'].items():
            cur = self.usage.get(g)
            if cur:
                for k in USAGE_KEYS:
                    cur[k] = max(0, cur[k] - u.get(k, 0))
        self.left -= set(sent['left'])
        self.ack -= set(sent['ack'])

    async def sync(self, session: aiohttp.ClientSession, servers: list[dict], ai: dict, app_id: str = '') -> dict | None:
        """Geeft het samengevoegde antwoord {'guilds','members','forget','global'} of None als niets aankwam."""
        merged: dict = {'guilds': {}, 'members': {}, 'forget': [], 'global': {}, 'complete': True}
        got = False
        for raw, sent in self.bodies(servers, ai, app_id):
            try:
                async with session.post(self.url, data=raw.encode(), headers={'Content-Type': 'application/json', 'X-Bot-Signature': self.sign(raw)},
                                        timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status != 200:
                        log.warning('Hub weigert de sync: status %s', r.status)
                        merged['complete'] = False
                        continue
                    data = await r.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                log.warning('Hub-sync mislukt: %s', e)
                merged['complete'] = False
                continue
            if not isinstance(data, dict) or data.get('ok') is not True:
                merged['complete'] = False
                continue
            got = True
            self.settle(sent)
            for k in ('guilds', 'members'):
                if isinstance(data.get(k), dict):
                    merged[k].update(data[k])
            if isinstance(data.get('forget'), list):
                merged['forget'] = list({str(x) for x in merged['forget'] + data['forget']})
            if isinstance(data.get('global'), dict):
                merged['global'] = data['global']
        if got:
            self.ok_at, self.fails = time.monotonic(), 0
            return merged
        self.fails += 1
        return None
