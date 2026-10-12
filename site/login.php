<?php
declare(strict_types=1);
// Start van het inloggen met Discord: stuurt door naar Discord.
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/guilds.php';
require __DIR__ . '/inc/discord.php';
if (!is_installed()) { http_response_code(503); exit; }
canonical_redirect();
header('Cache-Control: no-store');
setting('schema_version');
$subject = ip_hash();
if (rate_count('login', $subject, 600) >= 30) { http_response_code(429); echo 'Te vaak geprobeerd. Wacht even.'; exit; }
rate_hit('login', $subject);
try {
    $url = discord_login_url();
} catch (Throwable $e) {
    cb_log('login: ' . $e->getMessage());
    http_response_code(500); echo 'Inloggen is nog niet ingesteld.'; exit;
}
session_write_close();
header('Location: ' . $url, true, 303);
