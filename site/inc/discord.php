<?php
declare(strict_types=1);

/**
 * Inloggen met Discord (OAuth2, authorization-code). Scopes: identify en guilds — geen e-mail.
 * Het toegangstoken blijft alleen in de serversessie (om de serverlijst te vernieuwen) en gaat nooit in de database.
 */

function discord_base(): string
{
    // Alleen voor geautomatiseerde tests: CB_TEST_DISCORD (auto_prepend) wijst naar een nepserver op http.
    return defined('CB_TEST_DISCORD') ? CB_TEST_DISCORD : 'https://discord.com';
}

function discord_redirect_uri(): string
{
    $base = rtrim((string)cfg('base_url', ''), '/');
    return ($base !== '' ? $base : site_base()) . '/callback.php';
}

function discord_http(string $method, string $url, array $headers, ?array $form = null): array
{
    $ch = curl_init($url);
    $opts = [
        CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_CONNECTTIMEOUT => 8, CURLOPT_TIMEOUT => 15,
        CURLOPT_USERAGENT => 'CoreBot/' . CB_VERSION,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_PROTOCOLS => defined('CB_TEST_DISCORD') ? (CURLPROTO_HTTPS | CURLPROTO_HTTP) : CURLPROTO_HTTPS,
    ];
    if ($method === 'POST') {
        $opts[CURLOPT_POST] = true;
        $opts[CURLOPT_POSTFIELDS] = http_build_query($form ?? []);
    }
    curl_setopt_array($ch, $opts);
    $raw = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    if ($raw === false) throw new RuntimeException('Geen verbinding met Discord: ' . $err);
    $j = json_decode((string)$raw, true);
    return [$status, is_array($j) ? $j : []];
}

/** Adres waar de gebruiker Discord opent. De state staat in de sessie en is 10 minuten geldig. */
function discord_login_url(): string
{
    start_session();
    $id = (string)cfg('discord_client_id', '');
    if ($id === '') throw new RuntimeException('discord_client_id ontbreekt in config.php');
    $state = bin2hex(random_bytes(24));
    $_SESSION['oauth'] = ['state' => $state, 'exp' => time() + 600];
    return 'https://discord.com/oauth2/authorize?' . http_build_query([
        'client_id' => $id, 'redirect_uri' => discord_redirect_uri(), 'response_type' => 'code',
        'scope' => 'identify guilds', 'state' => $state,
    ], '', '&', PHP_QUERY_RFC3986);
}

/** Server van de gebruiker volgens Discord: [[id, naam, icon, owner, can_manage], ...]. */
function discord_fetch_guilds(string $access): array
{
    [$s, $list] = discord_http('GET', discord_base() . '/api/users/@me/guilds', ['Authorization: Bearer ' . $access, 'Accept: application/json']);
    if ($s >= 300) throw new RuntimeException('guilds');
    $out = [];
    foreach ($list as $g) {
        if (!is_array($g) || !cb_is_snowflake((string)($g['id'] ?? ''))) continue;
        $owner = ($g['owner'] ?? false) === true;
        $perm = (int)($g['permissions'] ?? 0);
        $out[] = [
            (string)$g['id'], mb_substr((string)($g['name'] ?? ''), 0, 100),
            is_string($g['icon'] ?? null) && preg_match('/^[a-z0-9_]{1,64}$/i', $g['icon']) ? $g['icon'] : null,
            $owner, $owner || ($perm & (CB_PERM_MANAGE_GUILD | CB_PERM_ADMIN)) !== 0,
        ];
        if (count($out) >= 200) break;
    }
    return $out;
}

function discord_store_guilds(string $userId, array $guilds): void
{
    $pdo = db();
    $pdo->beginTransaction();
    try {
        q('delete from user_guilds where user_id = ?', [$userId]);
        $st = $pdo->prepare('insert into user_guilds (user_id, guild_id, name, icon, is_owner, can_manage) values (?, ?, ?, ?, ?, ?)');
        foreach ($guilds as [$id, $name, $icon, $owner, $manage]) $st->execute([$userId, $id, $name, $icon, $owner ? 1 : 0, $manage ? 1 : 0]);
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }
}

/** Haalt de serverlijst opnieuw op met het token uit de sessie. Geeft false als het token verlopen is. */
function discord_refresh_guilds(string $userId): bool
{
    start_session();
    $t = $_SESSION['dtoken'] ?? null;
    if (!is_array($t) || (int)$t['exp'] < time()) return false;
    discord_store_guilds($userId, discord_fetch_guilds((string)$t['t']));
    return true;
}

/** Verwerkt de terugkeer van Discord. Geeft de query voor de redirect terug. */
function discord_handle_callback(): string
{
    start_session();
    $stored = $_SESSION['oauth'] ?? null;
    unset($_SESSION['oauth']); // eenmalig
    $state = is_string($_GET['state'] ?? null) ? $_GET['state'] : '';
    if (!is_array($stored) || $state === '' || !hash_equals((string)$stored['state'], $state) || (int)$stored['exp'] < time()) return 'auth_error=sessie';
    if (isset($_GET['error'])) return 'auth_error=geweigerd';
    $code = is_string($_GET['code'] ?? null) ? $_GET['code'] : '';
    if ($code === '' || strlen($code) > 2000) return 'auth_error=discord';

    [$st, $tok] = discord_http('POST', discord_base() . '/api/oauth2/token', ['Accept: application/json'], [
        'grant_type' => 'authorization_code', 'code' => $code, 'redirect_uri' => discord_redirect_uri(),
        'client_id' => (string)cfg('discord_client_id', ''), 'client_secret' => (string)cfg('discord_client_secret', ''),
    ]);
    $access = is_string($tok['access_token'] ?? null) ? $tok['access_token'] : '';
    if ($st >= 300 || $access === '') return 'auth_error=discord';
    [$s, $u] = discord_http('GET', discord_base() . '/api/users/@me', ['Authorization: Bearer ' . $access, 'Accept: application/json']);
    if ($s >= 300 || !cb_is_snowflake((string)($u['id'] ?? ''))) return 'auth_error=discord';
    $did = (string)$u['id'];
    $name = mb_substr((string)(($u['global_name'] ?? '') !== '' && $u['global_name'] !== null ? $u['global_name'] : ($u['username'] ?? 'Onbekend')), 0, 80);
    $avatar = is_string($u['avatar'] ?? null) && preg_match('/^[a-z0-9_]{1,64}$/i', $u['avatar']) ? $u['avatar'] : null;

    $row = q('select id from users where discord_id = ?', [$did])->fetch();
    if ($row) {
        $uid = (string)$row['id'];
        q('update users set name = ?, avatar = ?, last_login = now() where id = ?', [$name, $avatar, $uid]);
    } else {
        $uid = new_id();
        q('insert into users (id, discord_id, name, avatar, last_login) values (?, ?, ?, ?, now())', [$uid, $did, $name, $avatar]);
    }
    try { discord_store_guilds($uid, discord_fetch_guilds($access)); } catch (Throwable $e) { cb_log('guilds: ' . $e->getMessage()); }

    session_regenerate_id(true);
    $_SESSION['uid'] = $uid;
    $_SESSION['csrf'] = bin2hex(random_bytes(24));
    $_SESSION['dtoken'] = ['t' => $access, 'exp' => time() + max(60, min(604800, (int)($tok['expires_in'] ?? 3600)))];
    q('insert into audit_log (user_id, guild_id, action, detail) values (?, null, ?, ?)', [$uid, 'login', '']);
    return '';
}
