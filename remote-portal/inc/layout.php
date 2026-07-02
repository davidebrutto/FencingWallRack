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
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/dashboard.php">{$app}</a>
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
    echo '</main></body></html>';
}

function flash(?string $message, string $kind = 'info'): void
{
    if ($message) {
        echo '<div class="alert alert-' . e($kind) . '">' . e($message) . '</div>';
    }
}
