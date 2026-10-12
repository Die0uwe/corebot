<?php
declare(strict_types=1);

/**
 * Eenmalige installer voor corebot.info. Maakt config.php en de tabellen in een EIGEN database
 * (niet die van SBWebUI). Het databasewachtwoord typ je hier op de server in; het staat nergens anders.
 * Beveiligd met de installatiecode uit LEES-MIJ.txt. Verwijder dit bestand na gebruik.
 */
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/schema.php';

security_headers();
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
start_session();

function h(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

function page(string $title, string $inner): never
{
    echo '<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<title>' . h($title) . '</title><link rel="stylesheet" href="assets/app.css"></head>'
        . '<body class="plain"><main class="install"><h1>' . h($title) . '</h1>' . $inner . '</main></body></html>';
    exit;
}

$codeFile = __DIR__ . '/inc/install_code.php';
if (is_installed()) {
    $done = false;
    try { $done = (int)q('select count(*) from settings')->fetchColumn() > 0; } catch (Throwable) { $done = false; }
    if ($done) { http_response_code(403); page('Al geïnstalleerd', '<p>CoreBot is al geïnstalleerd. <strong>Verwijder install.php van de server.</strong></p>'); }
}
$expected = is_file($codeFile) ? (string)(require $codeFile) : '';
if ($expected === '') { http_response_code(403); page('Installatiecode ontbreekt', '<p>Het bestand <code>inc/install_code.php</code> ontbreekt of is leeg. Upload de map opnieuw uit de zip.</p>'); }

$checks = [
    ['PHP 8.0 of hoger (nu ' . PHP_VERSION . ')', version_compare(PHP_VERSION, '8.0.0', '>=')],
    ['PDO MySQL', extension_loaded('pdo_mysql')],
    ['cURL (nodig voor Discord)', extension_loaded('curl')],
    ['mbstring', extension_loaded('mbstring')],
    ['Map is beschrijfbaar (voor config.php)', is_writable(CB_ROOT)],
];
$allOk = !in_array(false, array_column($checks, 1), true);

$err = '';
$vals = ['db_host' => '', 'db_port' => '3306', 'db_name' => '', 'db_user' => '', 'discord_client_id' => '', 'admin_discord_id' => '', 'contact_email' => '', 'hosts' => ''];
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    foreach (array_keys($vals) as $k) $vals[$k] = trim((string)($_POST[$k] ?? ''));
    $dbPass = (string)($_POST['db_pass'] ?? '');
    $secret = trim((string)($_POST['discord_client_secret'] ?? ''));
    try {
        if (!hash_equals(csrf_token(), (string)($_POST['csrf'] ?? ''))) throw new RuntimeException('Sessie verlopen. Ververs de pagina.');
        if (!$allOk) throw new RuntimeException('De systeemcheck hierboven moet eerst volledig groen zijn.');
        if (!hash_equals($expected, trim((string)($_POST['code'] ?? '')))) { sleep(2); throw new RuntimeException('De installatiecode klopt niet (zie LEES-MIJ.txt).'); }
        if ($vals['db_name'] === '' || $vals['db_user'] === '' || $vals['db_host'] === '') throw new RuntimeException('Vul de databasegegevens in.');
        if (preg_match('/^\d{15,22}$/', $vals['discord_client_id']) !== 1) throw new RuntimeException('De Discord Application ID klopt niet (alleen cijfers).');
        if (strlen($secret) < 16) throw new RuntimeException('De Discord Client Secret ontbreekt of is te kort.');
        if (preg_match('/^\d{15,22}$/', $vals['admin_discord_id']) !== 1) throw new RuntimeException('Jouw Discord-ID klopt niet (alleen cijfers). Zet in Discord ontwikkelaarsmodus aan, klik rechts op jezelf en kies ID kopiëren.');
        if ($vals['contact_email'] !== '' && !filter_var($vals['contact_email'], FILTER_VALIDATE_EMAIL)) throw new RuntimeException('Het contactadres klopt niet.');
        $hosts = [];
        foreach (explode(',', strtolower($vals['hosts'])) as $h) {
            $h = trim($h);
            if ($h === '') continue;
            if (preg_match('/^[a-z0-9]([a-z0-9.-]{0,60}[a-z0-9])?$/', $h) !== 1 || !str_contains($h, '.')) throw new RuntimeException("Het domein \"$h\" klopt niet (alleen de naam, zonder https://).");
            $hosts[] = $h;
        }
        if (!$hosts) throw new RuntimeException('Vul minstens één domein in, bijvoorbeeld corebot.scriptspace.nl.');
        try {
            $pdo = new PDO("mysql:host={$vals['db_host']};port=" . (int)$vals['db_port'] . ";dbname={$vals['db_name']};charset=utf8mb4", $vals['db_user'], $dbPass,
                [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 8]);
        } catch (PDOException $e) {
            throw new RuntimeException('Geen verbinding met de database: ' . $e->getMessage());
        }
        install_schema($pdo);
        $pdo->prepare('insert into settings (k, v) values (?, ?) on duplicate key update v = values(v)')->execute(['schema_version', CB_SCHEMA]);
        $hubSecret = bin2hex(random_bytes(32));
        $config = [
            'db_host' => $vals['db_host'], 'db_port' => (int)$vals['db_port'], 'db_name' => $vals['db_name'], 'db_user' => $vals['db_user'], 'db_pass' => $dbPass,
            'app_key' => 'base64:' . base64_encode(random_bytes(32)), 'hub_secret' => $hubSecret,
            'discord_client_id' => $vals['discord_client_id'], 'discord_client_secret' => $secret,
            'admin_discord_ids' => [$vals['admin_discord_id']], 'contact_email' => $vals['contact_email'],
            'allowed_hosts' => $hosts, 'canonical_host' => '', 'base_url' => '', 'debug' => false,
        ];
        $php = "<?php\n// Gemaakt door install.php op " . date('Y-m-d H:i') . ". Deel dit bestand nooit.\nreturn " . var_export($config, true) . ";\n";
        $tmp = CB_ROOT . '/config.php.tmp';
        if (file_put_contents($tmp, $php, LOCK_EX) === false || !rename($tmp, CB_ROOT . '/config.php')) throw new RuntimeException('config.php kon niet geschreven worden. Controleer de schrijfrechten van de map.');
        @chmod(CB_ROOT . '/config.php', 0640);
        @unlink($codeFile);
        $deleted = @unlink(__FILE__);
        $redirects = implode('', array_map(static fn ($h) => '<li><code>https://' . h($h) . '/callback.php</code></li>', $hosts));
        page('Installatie klaar', '<p class="ok">CoreBot is geïnstalleerd.</p><ol>'
            . '<li>Zet in het <a href="https://discord.com/developers/applications" rel="noreferrer">Discord Developer Portal</a> bij OAuth2 > Redirects al deze adressen:<ul>' . $redirects . '</ul></li>'
            . '<li>Zet de bot-sleutel in het <code>.env</code>-bestand van de bot op je pc als <code>COREBOT_SECRET=</code>. Je ziet hem later onder Platform > Bot-verbinding (alleen voor jou).</li>'
            . '<li>Log in met Discord. Jouw account is de beheerder van CoreBot.</li></ol>'
            . ($deleted ? '<p class="ok">install.php is automatisch verwijderd.</p>' : '<p class="warn"><strong>Verwijder nu zelf install.php</strong> via FTP of de bestandsbeheerder van Strato.</p>')
            . '<p><a class="btn" href="./">Naar CoreBot</a></p>');
    } catch (RuntimeException $e) {
        $err = $e->getMessage();
    }
}

$rows = '';
foreach ($checks as [$label, $ok]) $rows .= '<li class="' . ($ok ? 'ok' : 'bad') . '">' . ($ok ? 'OK' : 'FOUT') . ' — ' . h($label) . '</li>';
$field = static fn (string $n, string $l, string $t = 'text', string $v = '', string $x = '', bool $req = true) => '<label>' . h($l) . '<input name="' . h($n) . '" type="' . h($t) . '" value="' . h($v) . '" ' . $x . ($req ? ' required' : '') . '></label>';

page('CoreBot installeren',
    '<p class="muted">Eenmalig. Gebruik een eigen, lege database voor corebot.info, niet die van SBWebUI.</p><ul class="checks">' . $rows . '</ul>'
    . ($err !== '' ? '<p class="bad">' . h($err) . '</p>' : '')
    . '<form method="post" autocomplete="off"><input type="hidden" name="csrf" value="' . h(csrf_token()) . '">'
    . $field('code', 'Installatiecode (uit LEES-MIJ.txt)')
    . '<h2>Database (Strato)</h2>'
    . $field('db_host', 'Databaseserver', 'text', $vals['db_host'])
    . $field('db_port', 'Poort', 'text', $vals['db_port'])
    . $field('db_name', 'Databasenaam', 'text', $vals['db_name'])
    . $field('db_user', 'Gebruiker', 'text', $vals['db_user'])
    . $field('db_pass', 'Wachtwoord van de database', 'password', '', '', false)
    . '<h2>Domeinen</h2>'
    . $field('hosts', 'Domeinen van deze site, kommagescheiden (nu corebot.scriptspace.nl; voeg corebot.info toe zodra die klaar is)', 'text', $vals['hosts'] !== '' ? $vals['hosts'] : (string)($_SERVER['HTTP_HOST'] ?? ''))
    . '<h2>Discord</h2>'
    . $field('discord_client_id', 'Application ID (Developer Portal > General Information)', 'text', $vals['discord_client_id'])
    . $field('discord_client_secret', 'Client Secret (Developer Portal > OAuth2)', 'password')
    . $field('admin_discord_id', 'Jouw Discord-ID (beheerder van CoreBot)', 'text', $vals['admin_discord_id'])
    . $field('contact_email', 'Contactadres voor privacyvragen (wordt op de privacypagina getoond)', 'email', $vals['contact_email'], '', false)
    . '<button class="btn primary" type="submit"' . ($allOk ? '' : ' disabled') . '>Installeren</button></form>');
