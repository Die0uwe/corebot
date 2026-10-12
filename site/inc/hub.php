<?php
declare(strict_types=1);

/**
 * Verbinding met de bot (hub). De bot draait op de pc van de beheerder naast Ollama en roept deze site aan;
 * de site roept de pc nooit aan. Elk verzoek is ondertekend: X-Bot-Signature = HMAC-SHA256(body, hub_secret).
 */

const HUB_MAX_BODY = 140000;
const HUB_MAX_SERVERS_PER_CALL = 25;
const HUB_MAX_CHANNELS = 250;

/** Controleert handtekening en tijd. Geeft [body, '', 200] of [null, melding, status]. */
function hub_verify(string $raw, string $sig, int $now): array
{
    $secret = (string)cfg('hub_secret', '');
    if ($secret === '') return [null, 'hub nog niet ingesteld', 503];
    if (strlen($raw) > HUB_MAX_BODY) return [null, 'te groot', 413];
    if (!hash_equals(hash_hmac('sha256', $raw, $secret), strtolower($sig))) return [null, 'handtekening klopt niet', 401];
    $d = json_decode($raw, true);
    if (!is_array($d)) return [null, 'geen geldige JSON', 400];
    if (abs($now - (int)($d['ts'] ?? 0)) > 300) return [null, 'tijdstempel te oud (klok van de pc klopt niet?)', 401];
    return [$d, '', 200];
}

function hub_models_allowed(): array
{
    $out = [];
    foreach (explode(',', setting('models_allowed')) as $m) {
        $m = trim($m);
        if ($m !== '' && preg_match('/^[A-Za-z0-9._:\/-]{1,80}$/', $m) === 1) $out[] = $m;
    }
    return array_values(array_unique($out));
}

/** Verwerkt één sync van de bot en geeft het antwoord terug. */
function hub_sync(array $d, int $now): array
{
    $pdo = db();
    $wanted = [];
    $newOnes = 0;
    $signups = setting('signups') === '1';
    $pdo->beginTransaction();
    try {
        foreach (array_slice((array)($d['servers'] ?? []), 0, HUB_MAX_SERVERS_PER_CALL) as $s) {
            if (!is_array($s) || !cb_is_snowflake((string)($s['id'] ?? ''))) continue;
            $gid = (string)$s['id'];
            $name = mb_substr(trim(str_replace(['<', '>'], '', (string)($s['name'] ?? ''))), 0, 100);
            $icon = is_string($s['icon'] ?? null) && preg_match('/^[a-z0-9_]{1,64}$/i', $s['icon']) ? $s['icon'] : null;
            $members = max(0, min(100000000, (int)($s['n'] ?? 0)));
            $exists = q('select 1 from guilds where guild_id = ?', [$gid])->fetchColumn();
            if (!$exists) {
                $newOnes++;
                q('insert into guilds (guild_id, name, icon, members, bot_present, bot_seen, suspended) values (?, ?, ?, ?, 1, now(), ?)', [$gid, $name, $icon, $members, $signups ? 0 : 1]);
            } else {
                q('update guilds set name = ?, icon = ?, members = ?, bot_present = 1, bot_seen = now() where guild_id = ?', [$name, $icon, $members, $gid]);
            }
            if (array_key_exists('ch', $s) && is_array($s['ch'])) {
                q('delete from guild_channels where guild_id = ?', [$gid]);
                $ins = $pdo->prepare('insert ignore into guild_channels (guild_id, channel_id, name, type, position) values (?, ?, ?, ?, ?)');
                foreach (array_slice($s['ch'], 0, HUB_MAX_CHANNELS) as $c) {
                    if (!is_array($c) || !cb_is_snowflake((string)($c['id'] ?? ''))) continue;
                    $ins->execute([$gid, (string)$c['id'], mb_substr(trim(str_replace(['<', '>'], '', (string)($c['n'] ?? ''))), 0, 100), max(0, min(20, (int)($c['t'] ?? 0))), max(0, min(10000, (int)($c['p'] ?? 0)))]);
                }
            }
            $wanted[] = $gid;
        }
        $left = array_values(array_filter(array_slice((array)($d['left'] ?? []), 0, 100), 'cb_is_snowflake'));
        foreach ($left as $gid) q('update guilds set bot_present = 0 where guild_id = ?', [$gid]);
        foreach (array_slice((array)($d['usage'] ?? []), 0, 100, true) as $gid => $u) {
            $gid = (string)$gid;
            if (!cb_is_snowflake($gid) || !is_array($u)) continue;
            $a = max(0, min(100000, (int)($u['a'] ?? 0))); $l = max(0, min(100000, (int)($u['l'] ?? 0))); $e = max(0, min(100000, (int)($u['e'] ?? 0)));
            if ($a + $l + $e === 0) continue;
            q('insert into usage_daily (day, guild_id, answered, limited, errors) select curdate(), guild_id, ?, ?, ? from guilds where guild_id = ?
               on duplicate key update answered = answered + values(answered), limited = limited + values(limited), errors = errors + values(errors)', [$a, $l, $e, $gid]);
        }
        $ack = array_values(array_filter(array_slice((array)($d['ack_forget'] ?? []), 0, 200), 'cb_is_snowflake'));
        foreach ($ack as $id) q('delete from forget_queue where discord_id = ?', [$id]);
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }

    $guilds = [];
    foreach ($wanted as $gid) {
        $row = cb_guild_row($gid);
        if ($row) $guilds[$gid] = cb_effective($row);
    }
    $members = [];
    if ($wanted) {
        $in = implode(',', array_fill(0, count($wanted), '?'));
        $rows = q("select distinct p.discord_id, p.prefs from member_prefs p join users u on u.discord_id = p.discord_id join user_guilds ug on ug.user_id = u.id where ug.guild_id in ($in) limit 500", $wanted)->fetchAll();
        foreach ($rows as $r) {
            $p = json_decode((string)$r['prefs'], true);
            if (is_array($p) && $p) $members[(string)$r['discord_id']] = $p;
        }
    }
    if (random_int(1, 100) === 1) {
        q('delete from usage_daily where day < (curdate() - interval 90 day)');
        q('delete from audit_log where created_at < (now() - interval 180 day)');
    }
    $forget = q('select discord_id from forget_queue order by created_at limit 200')->fetchAll(PDO::FETCH_COLUMN);

    $prev = json_decode(setting('hub_last'), true);
    $appId = preg_match('/^\d{15,22}$/', (string)($d['app_id'] ?? '')) === 1 ? (string)$d['app_id'] : (string)($prev['app_id'] ?? '');
    set_setting('hub_last', json_encode(['at' => $now, 'version' => mb_substr((string)($d['version'] ?? ''), 0, 20), 'app_id' => $appId, 'new' => $newOnes], JSON_UNESCAPED_UNICODE));
    return [
        'ok' => true,
        'guilds' => $guilds ?: new stdClass(),
        'members' => $members ?: new stdClass(),
        'forget' => array_map('strval', $forget),
        'global' => ['models_allowed' => hub_models_allowed()],
    ];
}
