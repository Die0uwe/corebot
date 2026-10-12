<?php
declare(strict_types=1);
// Terugkeeradres van Discord. Stuurt altijd terug naar de eigen site, nooit naar een adres uit het verzoek.
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/guilds.php';
require __DIR__ . '/inc/discord.php';
if (!is_installed()) { http_response_code(503); exit; }
header('Cache-Control: no-store');
header('Referrer-Policy: no-referrer');
try {
    $query = discord_handle_callback();
} catch (Throwable $e) {
    cb_log('callback: ' . get_class($e) . ': ' . $e->getMessage());
    $query = 'auth_error=fout';
}
session_write_close();
header('Location: ./' . ($query !== '' ? '?' . $query : '') . '#/', true, 303);
