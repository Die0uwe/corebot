<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
if (!is_installed()) { http_response_code(503); echo '{"ok":false,"installed":false}'; exit; }
try { q('select 1'); echo json_encode(['ok' => true, 'version' => CB_VERSION]); }
catch (Throwable $e) { http_response_code(503); echo '{"ok":false}'; }
