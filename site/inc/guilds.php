<?php
declare(strict_types=1);

/**
 * Instellingen per server en kanaal. Zelfde overervingsmodel als de bot (standaard < server < kanaal):
 * een profiel bevat alleen wat afwijkt; leeg betekent "erven van de laag erboven".
 * Publieke gebruikers kiezen nooit een model en schrijven geen vrije toontekst: de toon is een sleutel, de tekst staat in de bot.
 */

/** sleutel => [label, uitleg]. De instructietekst per toon staat in bot.py. */
const CB_TONES = [
    'standaard' => ['Standaard', 'Neutraal, vriendelijk en kort.'],
    'vriendelijk' => ['Vriendelijk', 'Warm en persoonlijk, af en toe een emoji.'],
    'zakelijk' => ['Zakelijk', 'Beknopt, zonder emoji en uitroeptekens.'],
    'speels' => ['Speels', 'Luchtig en grappig, maar behulpzaam.'],
    'kort' => ['Kort', 'Maximaal drie zinnen per antwoord.'],
    'uitleg' => ['Uitleggend', 'Stap voor stap, in eenvoudige taal.'],
    'streng' => ['Duidelijk en streng', 'Direct, wijst op de serverregels.'],
];
const CB_MODES = ['chat', 'commands'];
const CB_MAX_CHANNELS = 25;
const CB_MAX_CHAN_PROFILES = 50;
const CB_MAX_COMMANDS = 20;
const CB_MAX_FAQ = 30;
const CB_FALLBACK_KEYS = ['faq', 'cache', 'templates'];
/** [laagste, hoogste, label] — strenger dan bij de eigen bot van de beheerder. */
const CB_RANGES = [
    'cooldown' => [3, 600, 'Wachttijd'],
    'per_hour' => [1, 120, 'Berichten per uur'],
    'max_input' => [100, 2000, 'Maximale lengte vraag'],
    'memory' => [0, 10, 'Geheugen'],
];
const CB_PERM_MANAGE_GUILD = 0x20;
const CB_PERM_ADMIN = 0x8;
// kijken + schrijven + embeds + geschiedenis lezen + schrijven in threads
const CB_BOT_PERMISSIONS = '274877991936';

function cb_is_snowflake(mixed $v): bool
{
    return is_string($v) && preg_match('/^\d{15,22}$/', $v) === 1;
}

function cb_commands_clean(mixed $raw, string $where): array
{
    $cmds = []; $seen = [];
    foreach ((array)$raw as $x) {
        if (!is_array($x)) continue;
        $nm = ltrim(strtolower(trim((string)($x['name'] ?? ''))), '!');
        $rp = trim(str_replace(['<', '>'], '', (string)($x['reply'] ?? '')));
        if ($nm === '' && $rp === '') continue;
        if (preg_match('/^[a-z0-9_-]{1,20}$/', $nm) !== 1) return [null, "Commando \"$nm\"$where: gebruik 1 tot 20 kleine letters, cijfers, - of _."];
        if ($nm === 'help') return [null, 'Het commando !help bestaat al en geeft de lijst van commando\'s.'];
        if (isset($seen[$nm])) return [null, "Commando !$nm$where staat er dubbel in."];
        if ($rp === '' || mb_strlen($rp) > 800) return [null, "Commando !$nm$where: het antwoord moet tussen 1 en 800 tekens zijn."];
        $seen[$nm] = 1;
        $cmds[] = ['name' => $nm, 'reply' => $rp, 'on' => !empty($x['on'])];
    }
    if (count($cmds) > CB_MAX_COMMANDS) return [null, 'Maximaal ' . CB_MAX_COMMANDS . " commando's$where."];
    return [$cmds, ''];
}

/** Kleine letters, zonder leestekens en dubbele spaties: voor het opsporen van dubbele vragen. */
function cb_faq_norm(string $q): string
{
    return trim((string)preg_replace('/[^\p{L}\p{N}]+/u', ' ', mb_strtolower($q)));
}

/** FAQ van een server: lijst van {q, a, on}. Geeft [lijst, ''] of [null, melding]. */
function cb_faq_clean(mixed $raw): array
{
    $out = []; $seen = [];
    foreach (is_array($raw) ? $raw : [] as $x) {
        if (!is_array($x)) continue;
        $q = trim((string)preg_replace('/\s+/u', ' ', str_replace(['<', '>'], '', (string)($x['q'] ?? ''))));
        $a = trim(str_replace(['<', '>'], '', (string)($x['a'] ?? '')));
        if ($q === '' && $a === '') continue;
        $lbl = '"' . mb_substr($q, 0, 40) . (mb_strlen($q) > 40 ? '…' : '') . '"';
        if ($q === '' || mb_strlen($q) > 120) return [null, 'Veelgestelde vragen: een vraag moet tussen 1 en 120 tekens zijn' . ($q === '' ? '.' : " ($lbl).")];
        if ($a === '' || mb_strlen($a) > 600) return [null, "Veelgestelde vragen: het antwoord bij $lbl moet tussen 1 en 600 tekens zijn."];
        $n = cb_faq_norm($q);
        if ($n === '') return [null, "Veelgestelde vragen: $lbl bevat geen woorden."];
        if (isset($seen[$n])) return [null, "Veelgestelde vragen: de vraag $lbl staat er dubbel in."];
        $seen[$n] = 1;
        $out[] = ['q' => $q, 'a' => $a, 'on' => !empty($x['on'])];
    }
    if (count($out) > CB_MAX_FAQ) return [null, 'Maximaal ' . CB_MAX_FAQ . ' veelgestelde vragen.'];
    return [$out, ''];
}

/** Schakelaars voor de terugvallagen; ontbrekend betekent aan. */
function cb_fallback_get(mixed $raw): array
{
    $raw = is_array($raw) ? $raw : [];
    $o = [];
    foreach (CB_FALLBACK_KEYS as $k) $o[$k] = !array_key_exists($k, $raw) || (bool)$raw[$k];
    return $o;
}

/** Eén profiel (server of kanaal). Geeft [profiel, ''] of [null, melding]. */
function cb_profile_clean(array $in, bool $server, string $label): array
{
    $p = [];
    $w = " ($label)";
    if ($server && array_key_exists('enabled', $in) && !$in['enabled']) $p['enabled'] = false;
    $tone = trim((string)($in['tone'] ?? ''));
    if ($tone !== '') {
        if (!isset(CB_TONES[$tone])) return [null, "De toon klopt niet$w."];
        $p['tone'] = $tone;
    }
    $name = trim(str_replace(['<', '>'], '', (string)($in['name'] ?? '')));
    if (mb_strlen($name) > 32) return [null, "De naam van de bot mag maximaal 32 tekens zijn$w."];
    if ($name !== '') $p['name'] = $name;
    $extra = trim(str_replace(['<', '>'], '', (string)($in['extra_prompt'] ?? '')));
    if (mb_strlen($extra) > 400) return [null, "De extra instructie mag maximaal 400 tekens zijn$w."];
    if ($extra !== '') $p['extra_prompt'] = $extra;
    foreach (CB_RANGES as $k => [$lo, $hi, $nm]) {
        $v = $in[$k] ?? '';
        if ($v === '' || $v === null) continue;
        if (!is_numeric($v) || (int)$v < $lo || (int)$v > $hi) return [null, "$nm moet tussen $lo en $hi liggen$w."];
        $p[$k] = (int)$v;
    }
    if (!empty($in['commands'])) {
        [$cmds, $err] = cb_commands_clean($in['commands'], $w);
        if ($cmds === null) return [null, $err];
        if ($cmds) $p['commands'] = $cmds;
    }
    if (!$server) {
        $mode = (string)($in['mode'] ?? 'chat');
        if (!in_array($mode, CB_MODES, true)) return [null, "De modus klopt niet$w."];
        if ($mode !== 'chat') $p['mode'] = $mode;
    }
    return [$p, ''];
}

function cb_config_default(): array
{
    return ['server' => new stdClass(), 'channels' => [], 'channel_cfg' => new stdClass(), 'allow_member_tone' => true, 'faq' => [], 'fallback' => cb_fallback_get(null)];
}

/** Bewaarde configuratie van een serverrij, aangevuld met standaardwaarden. Lege kaarten blijven objecten ({}). */
function cb_config_get(?array $row): array
{
    $j = json_decode((string)($row['config'] ?? ''), true);
    $j = is_array($j) ? $j : [];
    return [
        'server' => (is_array($j['server'] ?? null) && $j['server']) ? $j['server'] : new stdClass(),
        'channels' => array_values(array_filter((array)($j['channels'] ?? []), 'cb_is_snowflake')),
        'channel_cfg' => (is_array($j['channel_cfg'] ?? null) && $j['channel_cfg']) ? $j['channel_cfg'] : new stdClass(),
        'allow_member_tone' => !isset($j['allow_member_tone']) || (bool)$j['allow_member_tone'],
        'faq' => cb_faq_clean($j['faq'] ?? [])[0] ?? [],
        'fallback' => cb_fallback_get($j['fallback'] ?? null),
    ];
}

/**
 * Controleert invoer uit het paneel. $known = kanaal-ID's die de bot doorgaf (leeg = nog niet bekend).
 * Geeft [config, ''] of [null, melding].
 */
function cb_config_clean(array $in, array $known, array $names = []): array
{
    $ids = [];
    foreach ((array)($in['channels'] ?? []) as $x) {
        $x = trim((string)$x);
        if (!cb_is_snowflake($x)) return [null, 'Een kanaal-ID klopt niet.'];
        if ($known && !in_array($x, $known, true)) return [null, 'CoreBot kent dit kanaal niet. Kies een kanaal uit de lijst; de bot geeft de kanalen door zodra hij in de server zit.'];
        if (!in_array($x, $ids, true)) $ids[] = $x;
    }
    if (count($ids) > CB_MAX_CHANNELS) return [null, 'Maximaal ' . CB_MAX_CHANNELS . ' kanalen.'];
    [$server, $err] = cb_profile_clean((array)($in['server'] ?? []), true, 'server');
    if ($server === null) return [null, $err];
    $cc = [];
    foreach ((array)($in['channel_cfg'] ?? []) as $id => $prof) {
        $id = (string)$id;
        if (!cb_is_snowflake($id) || !is_array($prof)) return [null, 'Een kanaal-ID klopt niet.'];
        if ($known && !in_array($id, $known, true)) return [null, 'CoreBot kent een van de kanalen met eigen instellingen niet.'];
        [$pp, $err] = cb_profile_clean($prof, false, 'kanaal ' . ($names[$id] ?? $id));
        if ($pp === null) return [null, $err];
        if ($pp) $cc[$id] = $pp;
    }
    if (count($cc) > CB_MAX_CHAN_PROFILES) return [null, 'Maximaal ' . CB_MAX_CHAN_PROFILES . ' kanalen met eigen instellingen.'];
    [$faq, $err] = cb_faq_clean($in['faq'] ?? []);
    if ($faq === null) return [null, $err];
    return [[
        'server' => $server ?: new stdClass(),
        'channels' => $ids,
        'channel_cfg' => $cc ?: new stdClass(),
        'allow_member_tone' => !isset($in['allow_member_tone']) || (bool)$in['allow_member_tone'],
        'faq' => $faq,
        'fallback' => cb_fallback_get($in['fallback'] ?? null),
    ], ''];
}

function cb_guild_row(string $gid): ?array
{
    $r = q('select * from guilds where guild_id = ?', [$gid])->fetch();
    return $r ?: null;
}

/** Mag deze gebruiker de serverinstellingen zien en wijzigen? Beheerder van CoreBot altijd. */
function cb_can_manage(array $user, string $gid): bool
{
    if ($user['admin']) return true;
    return (int)q('select can_manage from user_guilds where user_id = ? and guild_id = ?', [$user['id'], $gid])->fetchColumn() === 1;
}

function cb_known_channels(string $gid): array
{
    return q('select channel_id from guild_channels where guild_id = ?', [$gid])->fetchAll(PDO::FETCH_COLUMN);
}

function cb_usage_today(string $gid): array
{
    $r = q('select answered, limited, errors, fallback from usage_daily where day = curdate() and guild_id = ?', [$gid])->fetch();
    return $r ? array_map('intval', $r) : ['answered' => 0, 'limited' => 0, 'errors' => 0, 'fallback' => 0];
}

function cb_cap(array $row): int
{
    return $row['daily_cap'] !== null ? (int)$row['daily_cap'] : max(0, (int)setting('default_cap'));
}

/** Wat de bot voor deze server moet doen. Dit is het hele contract met de bot, zonder iets over modellen of sleutels. */
function cb_effective(array $row): array
{
    $conf = cb_config_get($row);
    $server = (array)$conf['server'];
    $use = cb_usage_today($row['guild_id']);
    $cap = cb_cap($row);
    $reason = '';
    if ((int)$row['suspended'] === 1) $reason = 'geschorst';
    elseif (array_key_exists('enabled', $server) && !$server['enabled']) $reason = 'uitgezet';
    elseif ($cap > 0 && $use['answered'] >= $cap) $reason = 'daglimiet';
    unset($server['enabled']);
    return [
        'enabled' => $reason === '',
        'reason' => $reason,
        'model' => (string)$row['model'],
        'server' => $server ?: new stdClass(),
        'channels' => $conf['channels'],
        'channel_cfg' => $conf['channel_cfg'],
        'allow_member_tone' => $conf['allow_member_tone'],
        'faq' => array_values(array_map(static fn ($f) => ['q' => $f['q'], 'a' => $f['a']], array_filter($conf['faq'], static fn ($f) => $f['on']))),
        'fallback' => $conf['fallback'],
    ];
}

function cb_invite_url(string $guildId = ''): string
{
    $q = ['client_id' => (string)cfg('discord_client_id', ''), 'scope' => 'bot', 'permissions' => CB_BOT_PERMISSIONS];
    if ($guildId !== '') { $q['guild_id'] = $guildId; $q['disable_guild_select'] = 'true'; }
    return 'https://discord.com/oauth2/authorize?' . http_build_query($q, '', '&', PHP_QUERY_RFC3986);
}

/** Waarschuwingen voor het paneel, in gewone taal. */
function cb_warnings(array $row, array $eff): array
{
    $w = [];
    if ((int)$row['bot_present'] !== 1) { $w[] = 'De bot zit niet (meer) in deze server. Voeg hem opnieuw toe.'; return $w; }
    if ($row['bot_seen'] === null || strtotime((string)$row['bot_seen']) < time() - 900) $w[] = 'De bot heeft zich al even niet gemeld. Instellingen gelden zodra hij weer online is.';
    if (!$eff['channels']) $w[] = 'Nog geen antwoordkanaal gekozen: de bot antwoordt nergens.';
    if ($eff['reason'] === 'daglimiet') $w[] = 'De daglimiet van deze server is bereikt. Morgen antwoordt de bot weer.';
    if ($eff['reason'] === 'geschorst') $w[] = 'Deze server is door de beheerder van CoreBot geschorst.';
    return $w;
}
