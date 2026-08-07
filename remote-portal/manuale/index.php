<?php
declare(strict_types=1);

$manualPath = __DIR__ . '/../assets/manuale-fencewall.pdf';
$manualUrl = '/assets/manuale-fencewall.pdf';

if (!is_file($manualPath)) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Manuale FENCEWALL non disponibile.';
    exit;
}

header('Location: ' . $manualUrl, true, 302);
exit;
