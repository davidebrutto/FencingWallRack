<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';
$user = require_login();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';
    if ($action === 'upload') {
        $file = $_FILES['video'] ?? null;
        if (!$file || $file['error'] !== UPLOAD_ERR_OK) {
            $error = upload_error_message((int) ($file['error'] ?? UPLOAD_ERR_NO_FILE));
        } else {
            $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
            if (!in_array($ext, allowed_video_ext(), true)) {
                $error = 'Formato video non supportato.';
            } else {
                $base = safe_base_name(pathinfo($file['name'], PATHINFO_FILENAME), 'video');
                $filename = unique_filename(VIDEO_DIR, $base, '.' . $ext);
                if (move_uploaded_file($file['tmp_name'], VIDEO_DIR . '/' . $filename)) {
                    $stmt = db()->prepare('INSERT INTO videos (filename, original_name, size_bytes, mime, uploaded_by) VALUES (?, ?, ?, ?, ?)');
                    $stmt->execute([$filename, $file['name'], (int) $file['size'], (string) $file['type'], (int) $user['id']]);
                    redirect_to('/videos.php');
                }
                $error = 'Impossibile salvare il file.';
            }
        }
    }
    if ($action === 'delete') {
        $id = (int) ($_POST['id'] ?? 0);
        $stmt = db()->prepare('SELECT filename FROM videos WHERE id = ?');
        $stmt->execute([$id]);
        $video = $stmt->fetch();
        if ($video) {
            @unlink(VIDEO_DIR . '/' . $video['filename']);
            db()->prepare('DELETE FROM videos WHERE id = ?')->execute([$id]);
        }
        redirect_to('/videos.php');
    }
}

$videos = db()->query('SELECT * FROM videos ORDER BY created_at DESC, id DESC')->fetchAll();
render_header('Video pausa', $user);
echo '<section class="card"><h1>Video pausa</h1>';
flash($error, 'error');
echo '<form method="post" enctype="multipart/form-data">';
echo '<input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="upload">';
echo '<label>Carica video</label><input type="file" name="video" accept=".mp4,.webm,.mov,.m4v,.ogg" required>';
echo '<button class="btn" style="margin-top:12px" type="submit">Upload</button></form></section>';
echo '<section class="card"><div class="section-title-row"><h2>File caricati</h2><span class="muted" id="videoSearchCount">' . count($videos) . ' file</span></div>';
echo '<div class="search-box"><label for="videoSearch">Cerca video</label><input id="videoSearch" type="search" placeholder="Cerca per nome file o URL"><span class="muted">La ricerca filtra mentre scrivi.</span></div>';
echo '<div class="media-list" id="videoList">';
foreach ($videos as $video) {
    $url = public_asset_url('video', $video['filename']);
    $searchText = implode(' ', [(string) $video['filename'], (string) ($video['original_name'] ?? ''), $url]);
    echo '<div class="media-row" data-filter-row data-search="' . e($searchText) . '">';
    echo '<video class="preview" src="' . e($url) . '" controls preload="metadata"></video>';
    echo '<div><strong>' . e($video['filename']) . '</strong><br><span class="muted">' . e((string) $video['size_bytes']) . ' byte</span><br><code>' . e($url) . '</code></div>';
    echo '<form method="post" onsubmit="return confirm(\'Eliminare questo video?\')"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="' . (int) $video['id'] . '"><button class="btn btn-danger">Elimina</button></form>';
    echo '</div>';
}
if (!$videos) {
    echo '<p>Nessun video caricato.</p>';
}
echo '<p class="empty-filter-message" id="videoSearchEmpty" hidden>Nessun video trovato con questa ricerca.</p>';
echo '</div></section>';
echo <<<'HTML'
<script>
(() => {
  const input = document.getElementById('videoSearch');
  const rows = Array.from(document.querySelectorAll('#videoList [data-filter-row]'));
  const empty = document.getElementById('videoSearchEmpty');
  const count = document.getElementById('videoSearchCount');
  const normalize = (value) => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  function applyFilter() {
    const query = normalize(input.value).trim();
    let visible = 0;
    for (const row of rows) {
      const text = normalize(row.dataset.search);
      const match = query === '' || text.includes(query);
      row.hidden = !match;
      if (match) visible += 1;
    }
    if (empty) empty.hidden = visible !== 0 || rows.length === 0;
    if (count) count.textContent = `${visible} di ${rows.length} file`;
  }

  if (input) {
    input.addEventListener('input', applyFilter);
    applyFilter();
  }
})();
</script>
HTML;
render_footer();
