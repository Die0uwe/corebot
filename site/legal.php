<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
if (!is_installed()) { http_response_code(503); exit; }
canonical_redirect();
security_headers();
header('Content-Type: text/html; charset=utf-8');
function h(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
$p = (string)($_GET['p'] ?? 'privacy');
$mail = (string)cfg('contact_email', '');
$contact = $mail !== '' ? '<a href="mailto:' . h($mail) . '">' . h($mail) . '</a>' : 'het contactadres dat de beheerder van deze site opgeeft';
$v = rawurlencode(CB_VERSION);

if ($p === 'voorwaarden') {
    $title = 'Gebruiksvoorwaarden';
    $body = <<<HTML
<p>CoreBot is een gratis Discord-bot met een eigen paneel. Door de bot aan een server toe te voegen of in te loggen ga je akkoord met deze voorwaarden.</p>
<h2>Wat je mag</h2>
<ul>
<li>Je mag de bot toevoegen aan servers waarvan je beheerder bent en de instellingen aanpassen.</li>
<li>Je blijft zelf verantwoordelijk voor wat er in je server gebeurt en voor de regels die je er instelt.</li>
</ul>
<h2>Wat je niet mag</h2>
<ul>
<li>De bot gebruiken om te pesten, te bedreigen, illegale inhoud te verspreiden of de limieten te omzeilen.</li>
<li>Extra instructies schrijven om de basisregels van de bot te omzeilen. Die instructies kunnen de basisregels niet overschrijven.</li>
</ul>
<h2>Beschikbaarheid</h2>
<ul>
<li>De bot draait op een eigen computer van de beheerder en kan zonder aankondiging offline zijn. Er is geen garantie op beschikbaarheid of op de inhoud van antwoorden.</li>
<li>Antwoorden komen van een AI-model en kunnen onjuist zijn. Gebruik ze niet voor medische, juridische of financiële beslissingen.</li>
<li>Elke server heeft een daglimiet aan antwoorden. De beheerder kan een server schorsen, bijvoorbeeld bij misbruik.</li>
</ul>
<h2>Stoppen</h2>
<p>Je kunt de bot op elk moment uit je server zetten via Discord. Leden kunnen hun gegevens wissen via het paneel (Voorkeuren > Verwijder mijn gegevens).</p>
<p>Vragen? Neem contact op via $contact.</p>
HTML;
} else {
    $title = 'Privacyverklaring';
    $body = <<<HTML
<p>Hier staat wat CoreBot over jou en je server bewaart, waarom, en hoe je het laat wissen. Verantwoordelijke is de beheerder van deze site; contact: $contact.</p>
<h2>Wat we bewaren</h2>
<ul>
<li><strong>Als je inlogt met Discord:</strong> je Discord-ID, je weergavenaam, de code van je avatar en de lijst van servers waar je lid van bent (naam, icoon en of je er beheerder bent). We vragen geen e-mailadres en bewaren geen Discord-toegangssleutel in de database.</li>
<li><strong>Servers met de bot:</strong> naam, icoon, aantal leden, de kanalen (naam en ID) en de instellingen die een beheerder kiest: toon, botnaam, extra instructie, limieten, commando's en kanalen.</li>
<li><strong>Voorkeuren van leden (alleen als je ze zelf instelt):</strong> bijnaam, toon en of de bot onthoudt wat je zegt.</li>
<li><strong>Tellers:</strong> per server per dag hoeveel antwoorden, afgeremde berichten en fouten. Alleen aantallen, geen berichten.</li>
<li><strong>Logboek van wijzigingen:</strong> wie wanneer instellingen opsloeg, zonder de inhoud van je tekst. Bij het wissen van je gegevens wordt je koppeling met deze regels verbroken.</li>
</ul>
<h2>Wat de bot met berichten doet</h2>
<ul>
<li>De bot leest alleen berichten in kanalen die een serverbeheerder heeft gekozen. In andere kanalen reageert hij niet.</li>
<li>Een vraag in zo'n kanaal gaat samen met de instellingen van de server naar het AI-model dat op de eigen computer van de beheerder draait. Er gaat niets naar een externe AI-aanbieder, tenzij de beheerder dat zelf heeft ingesteld; dat staat dan hier vermeld.</li>
<li>Berichten worden niet in een database of bestand opgeslagen. De laatste berichten per lid en kanaal staan alleen in het werkgeheugen van de bot (standaard maximaal 6 en nooit meer dan 10) en verdwijnen bij een herstart of als je ze laat wissen. Heb je geheugen uitgezet, dan onthoudt de bot niets van jou.</li>
</ul>
<h2>Jouw rechten</h2>
<ul>
<li><strong>Inzien en aanpassen:</strong> alles wat we van jou hebben zie je onder Voorkeuren en Servers.</li>
<li><strong>Wissen:</strong> onder Voorkeuren > Verwijder mijn gegevens wis je je account, je serverlijst en je voorkeuren. De bot krijgt de opdracht ook zijn geheugen over jou te wissen.</li>
<li><strong>Bezwaar of vraag:</strong> mail naar $contact.</li>
</ul>
<h2>Bewaartermijn en beveiliging</h2>
<ul>
<li>Servergegevens blijven bewaard zolang de bot in de server zit of de beheerder ze niet laat wissen. Dagtellers worden na 90 dagen verwijderd en het wijzigingslogboek na 180 dagen.</li>
<li>Het paneel gebruikt een beveiligde verbinding en een sessiecookie die nodig is om in te loggen. We gebruiken geen advertentie- of volgcookies.</li>
</ul>
<p class="muted">Deze tekst beschrijft de werking van CoreBot per versie {$v}. Hij is geen juridisch advies.</p>
HTML;
}
?><!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($title) ?> | CoreBot</title>
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/app.css?v=<?= $v ?>">
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="./"><img src="assets/logo.svg" alt="" width="30" height="30">CoreBot</a>
<nav class="nav" aria-label="Pagina's"><a href="legal.php?p=privacy"<?= $p !== 'voorwaarden' ? ' aria-current="page"' : '' ?>>Privacy</a><a href="legal.php?p=voorwaarden"<?= $p === 'voorwaarden' ? ' aria-current="page"' : '' ?>>Voorwaarden</a><a href="./">Naar het paneel</a></nav></div></header>
<main class="wrap legal"><h1><?= h($title) ?></h1><?= $body ?></main>
</body>
</html>
