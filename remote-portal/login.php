<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';

$error = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim((string) ($_POST['username'] ?? ''));
    $password = (string) ($_POST['password'] ?? '');
    $stmt = db()->prepare('SELECT id, username, password_hash FROM users WHERE username = ? LIMIT 1');
    $stmt->execute([$username]);
    $user = $stmt->fetch();
    if ($user && password_verify($password, $user['password_hash'])) {
        session_regenerate_id(true);
        $_SESSION['user_id'] = (int) $user['id'];
        redirect_to('/dashboard.php');
    }
    $error = 'Credenziali non valide.';
}

render_header('Login');
echo '<section class="card" style="max-width:440px;margin:40px auto">';
echo '<h1>Login</h1>';
flash($error, 'error');
echo '<form method="post">';
echo '<label>Username</label><input name="username" autocomplete="username" required>';
echo '<label style="margin-top:12px">Password</label><input type="password" name="password" autocomplete="current-password" required>';
echo '<button class="btn" style="margin-top:16px;width:100%" type="submit">Entra</button>';
echo '</form></section>';
render_footer();
