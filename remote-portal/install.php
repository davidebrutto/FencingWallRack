<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';

db()->exec("
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'admin',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS videos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  filename VARCHAR(255) NOT NULL UNIQUE,
  original_name VARCHAR(255) NOT NULL,
  size_bytes BIGINT NOT NULL DEFAULT 0,
  mime VARCHAR(120) NOT NULL DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  uploaded_by INT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS photos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  filename VARCHAR(255) NOT NULL UNIQUE,
  athlete_name VARCHAR(120) NOT NULL,
  normalized_name VARCHAR(120) NOT NULL,
  size_bytes BIGINT NOT NULL DEFAULT 0,
  mime VARCHAR(120) NOT NULL DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT NULL,
  uploaded_by INT NULL,
  INDEX(normalized_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
");

$count = (int) db()->query('SELECT COUNT(*) FROM users')->fetchColumn();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $count === 0) {
    $username = trim((string) ($_POST['username'] ?? ''));
    $password = (string) ($_POST['password'] ?? '');
    if ($username === '' || strlen($password) < 8) {
        $error = 'Inserisci username e password di almeno 8 caratteri.';
    } else {
        $stmt = db()->prepare('INSERT INTO users (username, password_hash, role) VALUES (?, ?, "admin")');
        $stmt->execute([$username, password_hash($password, PASSWORD_DEFAULT)]);
        redirect_to('/login.php');
    }
}

render_header('Installazione');
echo '<section class="card">';
echo '<h1>Installazione FenceWall Media</h1>';
if ($error) {
    flash($error, 'error');
}
if ($count > 0) {
    echo '<p>Database pronto e utente già presente.</p>';
    echo '<p><strong>Per sicurezza elimina install.php dal server.</strong></p>';
    echo '<p><a class="btn" href="/login.php">Vai al login</a></p>';
} else {
    echo '<form method="post">';
    echo '<label>Username admin</label><input name="username" required>';
    echo '<label style="margin-top:12px">Password admin</label><input name="password" type="password" minlength="8" required>';
    echo '<button class="btn btn-ok" style="margin-top:16px" type="submit">Crea admin</button>';
    echo '</form>';
}
echo '</section>';
render_footer();
