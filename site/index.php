<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
if (!is_installed()) { header('Location: install.php', true, 302); exit; }
canonical_redirect();
security_headers();
header('Content-Type: text/html; charset=utf-8');
$v = rawurlencode(CB_VERSION);
?><!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CoreBot: Discord-bot met eigen toon per kanaal</title>
<meta name="description" content="Gratis Nederlandse Discord-bot met AI-antwoorden. Stel toon, kanalen en commando's in per server en per kanaal.">
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/app.css?v=<?= $v ?>">
</head>
<body>
<div id="top"></div>
<main class="wrap" id="app" tabindex="-1"><noscript>CoreBot heeft JavaScript nodig om het paneel te tonen.</noscript></main>
<div id="foot"></div>
<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>
<script src="assets/app.js?v=<?= $v ?>"></script>
</body>
</html>
