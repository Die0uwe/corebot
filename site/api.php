<?php
declare(strict_types=1);

require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/guilds.php';
require __DIR__ . '/inc/discord.php';
require __DIR__ . '/inc/hub.php';

if (!is_installed()) fail('CoreBot is nog niet geïnstalleerd.', 503);
security_headers();
start_session();

const TONE_KEYS = ['standaard', 'vriendelijk', 'zakelijk', 'speels', 'kort', 'uitleg', 'streng'];

function tones_public(): array
{
    $o = [];
    foreach (CB_TONES as $k => [$label, $hint]) $o[] = ['key' => $k, 'label' => $label, 'hint' => $hint];
    return $o;
}

function avatar_url(array $u): ?string
{
    return $u['avatar'] ? 'https://cdn.discordapp.com/avatars/' . $u['discord_id'] . '/' . $u['avatar'] . '.png?size=64' : null;
}

function icon_url(string $gid, ?string $icon): ?string
{
    return $icon ? 'https://cdn.discordapp.com/icons/' . $gid . '/' . $icon . '.png?size=64' : null;
}

function user_public(array $u): array
{
    return ['name' => $u['name'], 'avatar' => avatar_url($u), 'admin' => $u['admin']];
}

function write_limit(array $u): void
{
    if (rate_count('apiw', (string)$u['id'], 60) >= 40) fail('Te veel wijzigingen vlak achter elkaar. Wacht een minuut.', 429);
    rate_hit('apiw', (string)$u['id']);
}

function prefs_clean(array $in): array
{
    $p = [];
    $nick = trim(preg_replace('/\s+/u', ' ', str_replace(['<', '>', '@'], '', (string)($in['nick'] ?? ''))) ?? '');
    if (mb_strlen($nick) > 32) fail('De bijnaam mag maximaal 32 tekens zijn.');
    if ($nick !== '') $p['nick'] = $nick;
    $tone = trim((string)($in['tone'] ?? ''));
    if ($tone !== '') {
        if (!isset(CB_TONES[$tone])) fail('De toon klopt niet.');
        $p['tone'] = $tone;
    }
    if (array_key_exists('memory', $in) && !$in['memory']) $p['memory'] = false;
    return $p;
}

function guild_payload(array $row, array $user): array
{
    $gid = $row['guild_id'];
    $conf = cb_config_get($row);
    $eff = cb_effective($row);
    $week = q('select day, answered from usage_daily where guild_id = ? and day >= (curdate() - interval 6 day) order by day', [$gid])->fetchAll();
    $channels = q('select channel_id as id, name, type, position from guild_channels where guild_id = ? order by position, name', [$gid])->fetchAll();
    $out = [
        'id' => $gid, 'name' => $row['name'], 'icon' => icon_url($gid, $row['icon']), 'members' => (int)$row['members'],
        'bot_present' => (int)$row['bot_present'] === 1, 'config' => $conf, 'rev' => md5((string)json_encode($conf)),
        'channels' => $channels, 'warnings' => cb_warnings($row, $eff),
        'usage' => ['today' => cb_usage_today($gid)['answered'], 'fallback_today' => cb_usage_today($gid)['fallback'], 'cap' => cb_cap($row), 'week' => $week],
        'invite_url' => cb_invite_url($gid),
        'limits' => array_map(static fn ($r) => ['min' => $r[0], 'max' => $r[1], 'label' => $r[2]], CB_RANGES),
    ];
    if ($user['admin']) {
        $out['admin'] = ['model' => $row['model'], 'suspended' => (int)$row['suspended'] === 1, 'daily_cap' => $row['daily_cap'] === null ? null : (int)$row['daily_cap'], 'models_allowed' => hub_models_allowed()];
    }
    return $out;
}

$action = (string)($_GET['a'] ?? '');

try {
    switch ($action) {
        case 'me': {
            $u = me();
            $base = ['version' => CB_VERSION, 'csrf' => csrf_token(), 'invite_url' => cb_invite_url(), 'tones' => tones_public(),
                'limits' => array_map(static fn ($r) => ['min' => $r[0], 'max' => $r[1], 'label' => $r[2]], CB_RANGES), 'contact' => (string)cfg('contact_email', ''),
                'signups' => setting('signups') === '1'];
            if (!$u) json_out($base + ['user' => null]);
            $servers = [];
            $rows = q('select ug.guild_id, ug.name, ug.icon, ug.is_owner, ug.can_manage, g.bot_present, g.suspended from user_guilds ug left join guilds g on g.guild_id = ug.guild_id
                       where ug.user_id = ? and (ug.can_manage = 1 or g.bot_present = 1) order by ug.can_manage desc, g.bot_present desc, ug.name', [$u['id']])->fetchAll();
            foreach ($rows as $r) {
                $servers[] = ['id' => $r['guild_id'], 'name' => $r['name'], 'icon' => icon_url($r['guild_id'], $r['icon']), 'owner' => (int)$r['is_owner'] === 1,
                    'can_manage' => (int)$r['can_manage'] === 1, 'bot_present' => (int)($r['bot_present'] ?? 0) === 1, 'suspended' => (int)($r['suspended'] ?? 0) === 1,
                    'invite_url' => cb_invite_url($r['guild_id'])];
            }
            $t = $_SESSION['dtoken'] ?? null;
            json_out($base + ['user' => user_public($u), 'servers' => $servers, 'can_refresh' => is_array($t) && (int)$t['exp'] > time()]);
        }

        case 'guild': {
            $u = require_login();
            $gid = (string)($_GET['id'] ?? '');
            if (!cb_is_snowflake($gid) || !cb_can_manage($u, $gid)) fail('Geen toegang tot deze server.', 403);
            $row = cb_guild_row($gid);
            if (!$row) fail('De bot zit nog niet in deze server. Voeg hem eerst toe.', 404, ['invite_url' => cb_invite_url($gid)]);
            json_out(guild_payload($row, $u));
        }

        case 'prefs': {
            $u = require_login();
            $r = q('select prefs from member_prefs where discord_id = ?', [$u['discord_id']])->fetchColumn();
            $p = $r ? json_decode((string)$r, true) : [];
            json_out(['prefs' => is_array($p) && $p ? $p : new stdClass()]);
        }

        case 'admin': {
            $u = require_admin();
            $stats = [
                'servers' => (int)q('select count(*) from guilds')->fetchColumn(),
                'present' => (int)q('select count(*) from guilds where bot_present = 1')->fetchColumn(),
                'users' => (int)q('select count(*) from users')->fetchColumn(),
                'today' => (int)q('select coalesce(sum(answered),0) from usage_daily where day = curdate()')->fetchColumn(),
                'week' => (int)q('select coalesce(sum(answered),0) from usage_daily where day >= (curdate() - interval 6 day)')->fetchColumn(),
            ];
            $guilds = q('select g.guild_id as id, g.name, g.members, g.bot_present, g.bot_seen, g.suspended, g.model, g.daily_cap,
                         coalesce(d.answered,0) as today, coalesce(d.fallback,0) as fallback from guilds g left join usage_daily d on d.guild_id = g.guild_id and d.day = curdate()
                         order by g.bot_present desc, g.bot_seen desc limit 200')->fetchAll();
            foreach ($guilds as &$g) { $g['bot_present'] = (int)$g['bot_present'] === 1; $g['suspended'] = (int)$g['suspended'] === 1; $g['members'] = (int)$g['members']; $g['today'] = (int)$g['today']; $g['fallback'] = (int)$g['fallback']; $g['daily_cap'] = $g['daily_cap'] === null ? null : (int)$g['daily_cap']; }
            unset($g);
            $last = json_decode(setting('hub_last'), true);
            json_out(['stats' => $stats, 'guilds' => $guilds, 'hub_last' => is_array($last) ? $last : null,
                'settings' => ['models_allowed' => setting('models_allowed'), 'default_cap' => (int)setting('default_cap'), 'signups' => setting('signups') === '1', 'sbwebui_url' => setting('sbwebui_url')],
                'redirect_uri' => discord_redirect_uri(), 'redirect_uris' => redirect_uris(), 'hub_url' => site_base() . '/hub.php', 'hosts' => array_values((array)cfg('allowed_hosts', [])), 'canonical_host' => (string)cfg('canonical_host', '')]);
        }

        /* ---------- schrijven (POST + CSRF) ---------- */
        case 'logout': {
            csrf_check();
            $_SESSION = [];
            session_destroy();
            json_out(['ok' => true]);
        }

        case 'refresh': {
            csrf_check();
            $u = require_login();
            write_limit($u);
            if (!discord_refresh_guilds((string)$u['id'])) fail('Je Discord-sessie is verlopen. Log opnieuw in om je servers te vernieuwen.', 401, ['relogin' => true]);
            json_out(['ok' => true]);
        }

        case 'guild_save': {
            csrf_check();
            $u = require_login();
            write_limit($u);
            $in = body();
            $gid = (string)($in['id'] ?? '');
            if (!cb_is_snowflake($gid) || !cb_can_manage($u, $gid)) fail('Geen toegang tot deze server.', 403);
            $row = cb_guild_row($gid);
            if (!$row) fail('De bot zit nog niet in deze server.', 404);
            $cur = cb_config_get($row);
            if (!hash_equals(md5((string)json_encode($cur)), (string)($in['rev'] ?? ''))) fail('Iemand anders heeft deze server net gewijzigd. Ververs de pagina en probeer opnieuw.', 409);
            $known = cb_known_channels($gid);
            $names = q('select channel_id, name from guild_channels where guild_id = ?', [$gid])->fetchAll(PDO::FETCH_KEY_PAIR);
            [$conf, $err] = cb_config_clean((array)($in['config'] ?? []), $known, $names);
            if ($conf === null) fail($err);
            q('update guilds set config = ? where guild_id = ?', [json_encode($conf, JSON_UNESCAPED_UNICODE), $gid]);
            audit('guild_save', 'kanalen ' . count($conf['channels']) . ', eigen kanaalinstellingen ' . count((array)$conf['channel_cfg']), $gid);
            json_out(['ok' => true, 'guild' => guild_payload(cb_guild_row($gid), $u)]);
        }

        case 'prefs_save': {
            csrf_check();
            $u = require_login();
            write_limit($u);
            $p = prefs_clean((array)(body()['prefs'] ?? []));
            if ($p) q('insert into member_prefs (discord_id, prefs) values (?, ?) on duplicate key update prefs = values(prefs)', [$u['discord_id'], json_encode($p, JSON_UNESCAPED_UNICODE)]);
            else q('delete from member_prefs where discord_id = ?', [$u['discord_id']]);
            json_out(['ok' => true, 'prefs' => $p ?: new stdClass()]);
        }

        case 'forget_me': {
            csrf_check();
            $u = require_login();
            $pdo = db();
            $pdo->beginTransaction();
            try {
                q('delete from user_guilds where user_id = ?', [$u['id']]);
                q('delete from member_prefs where discord_id = ?', [$u['discord_id']]);
                q('update audit_log set user_id = null where user_id = ?', [$u['id']]);
                q('delete from users where id = ?', [$u['id']]);
                q('insert into forget_queue (discord_id) values (?) on duplicate key update created_at = now()', [$u['discord_id']]);
                $pdo->commit();
            } catch (Throwable $e) {
                $pdo->rollBack();
                throw $e;
            }
            $_SESSION = [];
            session_destroy();
            json_out(['ok' => true]);
        }

        case 'admin_guild': {
            csrf_check();
            $u = require_admin();
            $in = body();
            $gid = (string)($in['id'] ?? '');
            $row = cb_is_snowflake($gid) ? cb_guild_row($gid) : null;
            if (!$row) fail('Server niet gevonden.', 404);
            $model = trim((string)($in['model'] ?? ''));
            if ($model !== '' && !in_array($model, hub_models_allowed(), true)) fail('Dit model staat niet in de toegestane lijst (Platform > Instellingen).');
            $cap = $in['daily_cap'] ?? null;
            if ($cap === '' || $cap === null) $cap = null;
            elseif (!is_numeric($cap) || (int)$cap < 0 || (int)$cap > 100000) fail('Daglimiet moet tussen 0 en 100000 liggen (0 = geen limiet).');
            else $cap = (int)$cap;
            q('update guilds set model = ?, suspended = ?, daily_cap = ? where guild_id = ?', [$model, !empty($in['suspended']) ? 1 : 0, $cap, $gid]);
            audit('admin_guild', 'model ' . ($model ?: '-') . ', geschorst ' . (!empty($in['suspended']) ? 'ja' : 'nee'), $gid);
            json_out(['ok' => true, 'guild' => guild_payload(cb_guild_row($gid), $u)]);
        }

        case 'admin_settings': {
            csrf_check();
            $u = require_admin();
            $in = body();
            $models = [];
            foreach (explode(',', (string)($in['models_allowed'] ?? '')) as $m) {
                $m = trim($m);
                if ($m === '') continue;
                if (preg_match('/^[A-Za-z0-9._:\/-]{1,80}$/', $m) !== 1) fail("Modelnaam \"$m\" bevat ongeldige tekens.");
                $models[] = $m;
            }
            $cap = $in['default_cap'] ?? 300;
            if (!is_numeric($cap) || (int)$cap < 0 || (int)$cap > 100000) fail('Standaard daglimiet moet tussen 0 en 100000 liggen.');
            $url = trim((string)($in['sbwebui_url'] ?? ''));
            if ($url !== '' && (strlen($url) > 200 || !filter_var($url, FILTER_VALIDATE_URL) || !str_starts_with($url, 'https://'))) fail('Het SBWebUI-adres moet met https:// beginnen.');
            set_setting('models_allowed', implode(',', array_values(array_unique($models))));
            set_setting('default_cap', (string)(int)$cap);
            set_setting('signups', !empty($in['signups']) ? '1' : '0');
            set_setting('sbwebui_url', $url);
            audit('admin_settings', 'modellen ' . count($models) . ', daglimiet ' . (int)$cap);
            json_out(['ok' => true]);
        }

        case 'admin_secret': {
            csrf_check();
            require_admin();
            json_out(['hub_secret' => (string)cfg('hub_secret', '')]);
        }

        default:
            fail('Onbekende actie.', 404);
    }
} catch (PDOException $e) {
    cb_log('api ' . $action . ': ' . $e->getMessage());
    fail('De database gaf een fout. Probeer het zo nog eens.', 500);
}
