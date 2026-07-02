<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';
$user = require_admin();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';
    if ($action === 'create') {
        $username = trim((string) ($_POST['username'] ?? ''));
        $password = (string) ($_POST['password'] ?? '');
        $role = $_POST['role'] === 'admin' ? 'admin' : 'editor';
        if ($username === '' || strlen($password) < 8) {
            $error = 'Username richiesto e password minima 8 caratteri.';
        } else {
            try {
                db()->prepare('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)')
                    ->execute([$username, password_hash($password, PASSWORD_DEFAULT), $role]);
                redirect_to('/users.php');
            } catch (Throwable) {
                $error = 'Utente già esistente o non valido.';
            }
        }
    }
    if ($action === 'delete') {
        $id = (int) ($_POST['id'] ?? 0);
        if ($id !== (int) $user['id']) {
            db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
        }
        redirect_to('/users.php');
    }
}

$users = db()->query('SELECT id, username, role, created_at FROM users ORDER BY username')->fetchAll();
render_header('Utenti', $user);
echo '<section class="card"><h1>Utenti</h1>';
flash($error, 'error');
echo '<form method="post" class="inline-form"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="create">';
echo '<input name="username" placeholder="username" required><input name="password" type="password" placeholder="password" required>';
echo '<select name="role"><option value="editor">Editor</option><option value="admin">Admin</option></select><button class="btn">Crea</button></form></section>';
echo '<section class="card"><div class="media-list">';
foreach ($users as $row) {
    echo '<div class="media-row" style="grid-template-columns:1fr auto"><div><strong>' . e($row['username']) . '</strong><br><span class="muted">' . e($row['role']) . '</span></div>';
    if ((int) $row['id'] !== (int) $user['id']) {
        echo '<form method="post" onsubmit="return confirm(\'Eliminare utente?\')"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="' . (int) $row['id'] . '"><button class="btn btn-danger">Elimina</button></form>';
    } else {
        echo '<span class="muted">utente corrente</span>';
    }
    echo '</div>';
}
echo '</div></section>';
render_footer();
