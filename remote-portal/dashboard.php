<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';
$user = require_login();
$videos = (int) db()->query('SELECT COUNT(*) FROM videos')->fetchColumn();
$photos = (int) db()->query('SELECT COUNT(*) FROM photos')->fetchColumn();

render_header('Dashboard', $user);
echo '<section class="grid">';
echo '<div class="card"><div class="muted">Video pausa</div><div class="stat">' . $videos . '</div><a class="btn" href="/videos.php">Gestisci video</a></div>';
echo '<div class="card"><div class="muted">Foto atleti</div><div class="stat">' . $photos . '</div><a class="btn" href="/photos.php">Gestisci foto</a></div>';
echo '<div class="card"><div class="muted">Manifest Raspberry</div><p><code>/api/pause-videos/manifest.php?token=...</code></p><p><code>/api/athlete-photos/manifest.php?token=...</code></p></div>';
echo '</section>';
render_footer();
