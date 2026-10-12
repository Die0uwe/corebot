<?php
declare(strict_types=1);
// Sync met de Discord-bot (draait op de pc van de beheerder). POST met JSON en X-Bot-Signature.
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/guilds.php';
require __DIR__ . '/inc/hub.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
if (!is_installed()) { http_response_code(503); echo '{"ok":false}'; exit; }
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') { http_response_code(405); echo '{"ok":false}'; exit; }
try {
    setting('schema_version'); // zorgt dat het schema bestaat (eerste start of herstel)
    $subject = ip_hash();
    if (rate_count('hub', $subject, 60) >= 120) { http_response_code(429); echo '{"ok":false,"error":"te vaak"}'; exit; }
    rate_hit('hub', $subject);
    $raw = (string)file_get_contents('php://input', false, null, 0, HUB_MAX_BODY + 1);
    [$d, $err, $code] = hub_verify($raw, (string)($_SERVER['HTTP_X_BOT_SIGNATURE'] ?? ''), time());
    if ($d === null) { http_response_code($code); echo json_encode(['ok' => false, 'error' => $err], JSON_UNESCAPED_UNICODE); exit; }
    echo json_encode(hub_sync($d, time()), JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) {
    cb_log('hub: ' . get_class($e) . ': ' . $e->getMessage());
    http_response_code(500); echo '{"ok":false}';
}
