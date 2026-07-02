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
        $file = $_FILES['photo'] ?? null;
        $athlete = trim((string) ($_POST['athlete_name'] ?? ''));
        if (!$file || $file['error'] !== UPLOAD_ERR_OK) {
            $error = upload_error_message((int) ($file['error'] ?? UPLOAD_ERR_NO_FILE));
        } elseif ($athlete === '') {
            $error = 'Inserisci il nome atleta.';
        } else {
            $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
            if (!in_array($ext, allowed_photo_ext(), true)) {
                $error = 'Formato foto non supportato.';
            } else {
                $base = safe_base_name($athlete, 'atleta');
                $filename = unique_filename(PHOTO_DIR, $base, '.' . $ext);
                if (move_uploaded_file($file['tmp_name'], PHOTO_DIR . '/' . $filename)) {
                    $stmt = db()->prepare('INSERT INTO photos (filename, athlete_name, normalized_name, size_bytes, mime, uploaded_by) VALUES (?, ?, ?, ?, ?, ?)');
                    $stmt->execute([$filename, $athlete, normalize_athlete_name($athlete), (int) $file['size'], (string) $file['type'], (int) $user['id']]);
                    redirect_to('/photos.php');
                }
                $error = 'Impossibile salvare la foto.';
            }
        }
    }
    if ($action === 'rename') {
        $id = (int) ($_POST['id'] ?? 0);
        $athlete = trim((string) ($_POST['athlete_name'] ?? ''));
        $stmt = db()->prepare('SELECT * FROM photos WHERE id = ?');
        $stmt->execute([$id]);
        $photo = $stmt->fetch();
        if ($photo && $athlete !== '') {
            $ext = strtolower(pathinfo($photo['filename'], PATHINFO_EXTENSION));
            $base = safe_base_name($athlete, 'atleta');
            $newFilename = unique_filename(PHOTO_DIR, $base, '.' . $ext, $photo['filename']);
            if ($newFilename !== $photo['filename']) {
                rename(PHOTO_DIR . '/' . $photo['filename'], PHOTO_DIR . '/' . $newFilename);
            }
            db()->prepare('UPDATE photos SET filename = ?, athlete_name = ?, normalized_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?')
                ->execute([$newFilename, $athlete, normalize_athlete_name($athlete), $id]);
        }
        redirect_to('/photos.php');
    }
    if ($action === 'delete') {
        $id = (int) ($_POST['id'] ?? 0);
        $stmt = db()->prepare('SELECT filename FROM photos WHERE id = ?');
        $stmt->execute([$id]);
        $photo = $stmt->fetch();
        if ($photo) {
            @unlink(PHOTO_DIR . '/' . $photo['filename']);
            db()->prepare('DELETE FROM photos WHERE id = ?')->execute([$id]);
        }
        redirect_to('/photos.php');
    }
}

$photos = db()->query('SELECT * FROM photos ORDER BY athlete_name ASC, id DESC')->fetchAll();
render_header('Foto atleti', $user);
echo '<section class="card"><h1>Foto atleti</h1>';
flash($error, 'error');
echo '<form method="post" enctype="multipart/form-data">';
echo '<input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="upload">';
echo '<label>Nome atleta come da seriale</label><input name="athlete_name" placeholder="BRUTTO D." required>';
echo '<label style="margin-top:12px">Foto</label><input type="file" name="photo" accept=".jpg,.jpeg,.png,.webp" required>';
echo '<button class="btn" style="margin-top:12px" type="submit">Upload</button></form></section>';
echo '<section class="card"><h2>Foto caricate</h2><div class="media-list">';
foreach ($photos as $photo) {
    $url = public_asset_url('photo', $photo['filename']);
    echo '<div class="media-row">';
    echo '<img class="photo-preview" src="' . e($url) . '" alt="' . e($photo['athlete_name']) . '">';
    echo '<div><strong>' . e($photo['athlete_name']) . '</strong><br><span class="muted">Chiave: ' . e($photo['normalized_name']) . '</span><br><code>' . e($photo['filename']) . '</code></div>';
    echo '<div class="actions">';
    echo '<form class="inline-form" method="post"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="rename"><input type="hidden" name="id" value="' . (int) $photo['id'] . '"><input type="text" name="athlete_name" value="' . e($photo['athlete_name']) . '"><button class="btn">Rinomina</button></form>';
    echo '<form method="post" onsubmit="return confirm(\'Eliminare questa foto?\')"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="' . (int) $photo['id'] . '"><button class="btn btn-danger">Elimina</button></form>';
    echo '</div></div>';
}
if (!$photos) {
    echo '<p>Nessuna foto caricata.</p>';
}
echo '</div></section>';
render_footer();
