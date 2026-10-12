<?php
declare(strict_types=1);

/**
 * CoreBot (corebot.info) — gedeelde kern: config, database, sessie, CSRF, rate limits.
 * Aparte code en database van SBWebUI. Geen AI-sleutels of modelgegevens van de beheerder in dit systeem:
 * de AI zit verborgen achter de bot op de eigen pc van de beheerder.
 */

define('CB_ROOT', dirname(__DIR__));
const CB_VERSION = '0.1.1';
const CB_SCHEMA = '1';

function cfg(string $key, mixed $default = null): mixed
{
    static $c = false;
    if ($c === false) {
        $file = CB_ROOT . '/config.php';
        $c = is_file($file) ? (require $file) : [];
        if (!is_array($c)) $c = [];
    }
    return $c[$key] ?? $default;
}

/**
 * Domein van dit verzoek. Met allowed_hosts in config.php (bijvoorbeeld corebot.scriptspace.nl én corebot.info) werkt de site
 * op alle genoemde domeinen uit dezelfde map; een onbekende Host-header valt terug op het eerste domein.
 */
function site_host(): string
{
    $raw = strtolower(trim((string)($_SERVER['HTTP_HOST'] ?? '')));
    $allowed = array_values(array_filter(array_map(static fn ($h) => strtolower(trim((string)$h)), (array)cfg('allowed_hosts', []))));
    if (!$allowed) return $raw !== '' ? $raw : 'localhost';
    $bare = preg_replace('/:\d+$/', '', $raw);
    return in_array($raw, $allowed, true) || in_array($bare, $allowed, true) ? $raw : $allowed[0];
}

function site_base(): string
{
    return (is_https() ? 'https' : 'http') . '://' . site_host();
}

/** Alle redirect-adressen die in het Discord Developer Portal moeten staan. */
function redirect_uris(): array
{
    $hosts = array_values(array_filter(array_map(static fn ($h) => strtolower(trim((string)$h)), (array)cfg('allowed_hosts', []))));
    if (!$hosts) return [site_base() . '/callback.php'];
    return array_map(static fn ($h) => 'https://' . $h . '/callback.php', $hosts);
}

/** Na de verhuizing: canonical_host in config.php zetten stuurt alle andere domeinen met een 301 door (alleen GET). */
function canonical_redirect(): void
{
    $c = strtolower(trim((string)cfg('canonical_host', '')));
    if ($c === '' || ($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') return;
    $host = strtolower((string)preg_replace('/:\d+$/', '', (string)($_SERVER['HTTP_HOST'] ?? '')));
    if ($host === $c || $host === '') return;
    header('Location: https://' . $c . (string)($_SERVER['REQUEST_URI'] ?? '/'), true, 301);
    exit;
}

function is_installed(): bool
{
    return cfg('db_name') !== null && cfg('app_key') !== null && cfg('hub_secret') !== null;
}

function json_out(mixed $data, int $status = 200): never
{
    if (!headers_sent()) {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
    }
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}

function fail(string $message, int $status = 400, array $extra = []): never
{
    json_out(['error' => $message] + $extra, $status);
}

function cb_log(string $message): void
{
    error_log('[corebot] ' . $message);
}

set_exception_handler(static function (Throwable $e): void {
    cb_log(get_class($e) . ': ' . $e->getMessage() . ' @ ' . basename($e->getFile()) . ':' . $e->getLine());
    $msg = cfg('debug', false) ? $e->getMessage() : 'Er ging iets mis op de server.';
    if (!headers_sent()) {
        http_response_code(500);
        header('Content-Type: application/json; charset=utf-8');
    }
    echo json_encode(['error' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
});

/* ---------- database ---------- */

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) return $pdo;
    $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', (string)cfg('db_host', 'localhost'), (int)cfg('db_port', 3306), (string)cfg('db_name', ''));
    $pdo = new PDO($dsn, (string)cfg('db_user', ''), (string)cfg('db_pass', ''), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
        PDO::ATTR_TIMEOUT => 8,
    ]);
    $pdo->exec('SET NAMES utf8mb4');
    return $pdo;
}

function q(string $sql, array $params = []): PDOStatement
{
    $st = db()->prepare($sql);
    $st->execute($params);
    return $st;
}

function new_id(): string
{
    return bin2hex(random_bytes(12));
}

/* ---------- instellingen (platform, door de beheerder) ---------- */

const SETTING_DEFAULTS = [
    'schema_version' => '',
    'models_allowed' => '',   // kommagescheiden: modellen die de beheerder per server mag toekennen (leeg = alleen het standaardmodel van de bot)
    'default_cap' => '300',   // antwoorden per server per dag, tenzij de server een eigen limiet heeft
    'max_servers_per_user' => '25',
    'sbwebui_url' => '',      // alleen voor de knop in het platformscherm
    'hub_last' => '',         // JSON: laatste sync van de bot
    'signups' => '1',         // 1 = nieuwe servers mogen de bot toevoegen
];

function settings_all(?string $patchKey = null, string $patchValue = ''): array
{
    static $cache = null;
    if ($patchKey !== null) { settings_all(); $cache[$patchKey] = $patchValue; return $cache; }
    if ($cache !== null) return $cache;
    $out = SETTING_DEFAULTS;
    try {
        $rows = q('select k, v from settings')->fetchAll();
    } catch (PDOException $e) {
        if ($e->getCode() !== '42S02') throw $e; // tabel ontbreekt: schema aanmaken (eerste start of herstel)
        require_once __DIR__ . '/schema.php';
        install_schema(db());
        $rows = [];
    }
    foreach ($rows as $r) $out[$r['k']] = (string)$r['v'];
    if ($out['schema_version'] !== CB_SCHEMA) {
        require_once __DIR__ . '/schema.php';
        install_schema(db());
        set_setting('schema_version', CB_SCHEMA);
        $cache = null;
        return settings_all();
    }
    return $cache = $out;
}

function setting(string $key): string
{
    return settings_all()[$key] ?? (SETTING_DEFAULTS[$key] ?? '');
}

function set_setting(string $key, string $value): void
{
    q('insert into settings (k, v) values (?, ?) on duplicate key update v = values(v)', [$key, $value]);
    settings_all($key, $value);
}

/* ---------- sessie en CSRF ---------- */

function is_https(): bool
{
    return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || strtolower((string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https'
        || (int)($_SERVER['SERVER_PORT'] ?? 0) === 443;
}

function start_session(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) return;
    session_name('cbsid');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'secure' => is_https(), 'httponly' => true, 'samesite' => 'Lax']);
    ini_set('session.use_strict_mode', '1');
    ini_set('session.gc_maxlifetime', '604800');
    session_start();
}

function csrf_token(): string
{
    start_session();
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(24));
    return (string)$_SESSION['csrf'];
}

function csrf_check(): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') fail('Alleen POST.', 405);
    $sent = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    if ($sent === '' || !hash_equals(csrf_token(), $sent)) fail('Sessie verlopen. Ververs de pagina.', 403);
    $origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
    if ($origin !== '') {
        $oh = parse_url($origin, PHP_URL_HOST);
        $hh = parse_url('//' . ($_SERVER['HTTP_HOST'] ?? ''), PHP_URL_HOST);
        if (!$oh || !$hh || strtolower((string)$oh) !== strtolower((string)$hh)) fail('Verzoek van een ander adres geweigerd.', 403);
    }
}

function body(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') return [];
    if (strlen($raw) > 200000) fail('Bericht is te groot.', 413);
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

/* ---------- gebruiker en rechten ---------- */

/** Ingelogde gebruiker of null. Een gebruiker is alleen een Discord-identiteit; er zijn geen wachtwoorden. */
function me(): ?array
{
    static $user = false;
    if ($user !== false) return $user;
    start_session();
    $id = (string)($_SESSION['uid'] ?? '');
    $user = null;
    if ($id !== '') {
        $row = q('select id, discord_id, name, avatar from users where id = ?', [$id])->fetch();
        if ($row) {
            $row['admin'] = in_array((string)$row['discord_id'], array_map('strval', (array)cfg('admin_discord_ids', [])), true);
            $user = $row;
        } else {
            unset($_SESSION['uid']);
        }
    }
    return $user;
}

function require_login(): array
{
    $u = me();
    if (!$u) fail('Log eerst in met Discord.', 401);
    return $u;
}

function require_admin(): array
{
    $u = require_login();
    if (!$u['admin']) fail('Alleen voor de beheerder van CoreBot.', 403);
    return $u;
}

/* ---------- rate limits en logboek ---------- */

function ip_hash(): string
{
    return hash('sha256', (string)($_SERVER['REMOTE_ADDR'] ?? '') . '|' . (string)cfg('app_key', ''));
}

function rate_hit(string $kind, string $subject): void
{
    q('insert into rate_events (kind, subject) values (?, ?)', [$kind, $subject]);
    if (random_int(1, 50) === 1) q('delete from rate_events where created_at < (now() - interval 2 day)');
}

function rate_count(string $kind, string $subject, int $seconds): int
{
    return (int)q('select count(*) from rate_events where kind = ? and subject = ? and created_at > (now() - interval ' . (int)$seconds . ' second)', [$kind, $subject])->fetchColumn();
}

function audit(string $action, string $detail = '', ?string $guild = null): void
{
    $u = me();
    q('insert into audit_log (user_id, guild_id, action, detail) values (?, ?, ?, ?)', [$u['id'] ?? null, $guild, $action, mb_substr($detail, 0, 500)]);
}

function security_headers(): void
{
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: same-origin');
    header("Content-Security-Policy: default-src 'self'; img-src 'self' https://cdn.discordapp.com data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self' https://discord.com");
    if (is_https()) header('Strict-Transport-Security: max-age=31536000');
}
