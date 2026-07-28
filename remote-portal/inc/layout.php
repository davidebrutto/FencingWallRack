<?php
declare(strict_types=1);

function render_header(string $title, ?array $user = null): void
{
    $app = e((string) app_config('app_name', 'FenceWall Media'));
    $titleEsc = e($title);
    echo <<<HTML
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{$titleEsc} - {$app}</title>
  <meta name="theme-color" content="#101418">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="{$app}">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="icon" type="image/png" sizes="192x192" href="/assets/app-icon-192.png">
  <link rel="icon" type="image/png" sizes="512x512" href="/assets/app-icon.png">
  <link rel="apple-touch-icon" href="/assets/app-icon.png">
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/dashboard.php"><img class="brand-logo brand-logo-secondary" src="/assets/logo-secondary.png" alt=""><img class="brand-logo" src="/assets/logo.png" alt="{$app}"></a>
HTML;
    if ($user) {
        echo '<nav class="nav">';
        echo '<a href="/dashboard.php">Home</a>';
        echo '<a href="/videos.php">Video</a>';
        echo '<a href="/photos.php">Foto</a>';
        if (is_admin($user)) {
            echo '<a href="/users.php">Utenti</a>';
        }
        echo '<a href="/logout.php">Logout</a>';
        echo '</nav>';
    }
    echo '</header><main class="page">';
}

function render_footer(): void
{
    echo <<<'HTML'
</main>
<script>
if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js').catch(() => undefined);
  });
}
</script>
</body></html>
HTML;
}

function flash(?string $message, string $kind = 'info'): void
{
    if ($message) {
        echo '<div class="alert alert-' . e($kind) . '">' . e($message) . '</div>';
    }
}
