<?php
declare(strict_types=1);

const BASE_DIR = __DIR__ . '/..';
const STORAGE_DIR = BASE_DIR . '/storage';
const VIDEO_DIR = STORAGE_DIR . '/pause-videos';
const PHOTO_DIR = STORAGE_DIR . '/athlete-photos';
const FLAG_DIR = STORAGE_DIR . '/flags';

$configFile = BASE_DIR . '/config.php';
if (!is_file($configFile)) {
    http_response_code(500);
    echo 'config.php mancante. Copia config.example.php in config.php e compila i dati.';
    exit;
}

$config = require $configFile;
if (!is_array($config)) {
    http_response_code(500);
    echo 'config.php non valido.';
    exit;
}

if (session_status() !== PHP_SESSION_ACTIVE) {
    session_name('FENCEWALLMEDIA');
    session_start();
}

foreach ([STORAGE_DIR, VIDEO_DIR, PHOTO_DIR, FLAG_DIR] as $dir) {
    if (!is_dir($dir)) {
        mkdir($dir, 0755, true);
    }
}

function app_config(?string $key = null, mixed $default = null): mixed
{
    global $config;
    if ($key === null) {
        return $config;
    }
    return $config[$key] ?? $default;
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $db = app_config('db', []);
    $charset = $db['charset'] ?? 'utf8mb4';
    $dsn = sprintf('mysql:host=%s;dbname=%s;charset=%s', $db['host'] ?? 'localhost', $db['name'] ?? '', $charset);
    $pdo = new PDO($dsn, $db['user'] ?? '', $db['pass'] ?? '', [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    return $pdo;
}

function e(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function redirect_to(string $path): never
{
    header('Location: ' . $path);
    exit;
}

function current_user(): ?array
{
    if (empty($_SESSION['user_id'])) {
        return null;
    }
    $stmt = db()->prepare('SELECT id, username, role FROM users WHERE id = ? LIMIT 1');
    $stmt->execute([$_SESSION['user_id']]);
    $user = $stmt->fetch();
    return $user ?: null;
}

function require_login(): array
{
    $user = current_user();
    if (!$user) {
        redirect_to('/login.php');
    }
    return $user;
}

function is_admin(?array $user = null): bool
{
    $user = $user ?: current_user();
    return $user && ($user['role'] ?? '') === 'admin';
}

function require_admin(): array
{
    $user = require_login();
    if (!is_admin($user)) {
        http_response_code(403);
        echo 'Accesso negato.';
        exit;
    }
    return $user;
}

function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function verify_csrf(): void
{
    $sent = $_POST['csrf'] ?? '';
    if (!is_string($sent) || !hash_equals($_SESSION['csrf'] ?? '', $sent)) {
        http_response_code(419);
        echo 'Sessione scaduta. Ricarica la pagina.';
        exit;
    }
}

function normalize_athlete_name(string $name): string
{
    $value = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $name);
    $value = strtoupper($value ?: $name);
    $value = preg_replace('/[^A-Z0-9]+/', ' ', $value);
    $value = trim((string) $value);
    return preg_replace('/\s+/', ' ', $value) ?: '';
}

function safe_base_name(string $name, string $fallback = 'file'): string
{
    $value = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $name);
    $value = $value ?: $name;
    $value = preg_replace('/[^a-zA-Z0-9 ._-]+/', '_', $value);
    $value = trim((string) preg_replace('/\s+/', ' ', (string) $value));
    return mb_substr($value !== '' ? $value : $fallback, 0, 90);
}

function unique_filename(string $dir, string $base, string $ext, ?string $current = null): string
{
    $candidate = $base . $ext;
    $i = 1;
    while ($candidate !== $current && file_exists($dir . '/' . $candidate)) {
        $candidate = $base . '_' . $i . $ext;
        $i++;
    }
    return $candidate;
}

function public_asset_url(string $type, string $filename): string
{
    $base = rtrim((string) app_config('base_url', ''), '/');
    $token = rawurlencode((string) app_config('asset_token', ''));
    return $base . '/asset.php?type=' . rawurlencode($type) . '&file=' . rawurlencode($filename) . '&token=' . $token;
}

function check_asset_token(): void
{
    $expected = (string) app_config('asset_token', '');
    $sent = (string) ($_GET['token'] ?? '');
    if ($expected === '' || !hash_equals($expected, $sent)) {
        http_response_code(403);
        echo 'Forbidden';
        exit;
    }
}

function allowed_video_ext(): array
{
    return ['mp4', 'webm', 'mov', 'm4v', 'ogg'];
}

function allowed_photo_ext(): array
{
    return ['jpg', 'jpeg', 'png', 'webp'];
}

function allowed_flag_ext(): array
{
    return ['svg'];
}

function normalize_flag_override(string $value): string
{
    $value = basename(trim($value));
    $value = preg_replace('/\.svg$/i', '', $value);
    $value = preg_replace('/[^a-zA-Z0-9_-]+/', '', (string) $value);
    if ($value === '') {
        return '';
    }
    return is_file(FLAG_DIR . '/' . $value . '.svg') ? $value : '';
}

function list_flags(): array
{
    if (!is_dir(FLAG_DIR)) {
        return [];
    }
    $items = [];
    foreach (scandir(FLAG_DIR) ?: [] as $file) {
        if ($file === '.' || $file === '..') {
            continue;
        }
        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        if (!in_array($ext, allowed_flag_ext(), true)) {
            continue;
        }
        $code = pathinfo($file, PATHINFO_FILENAME);
        $items[] = [
            'filename' => $file,
            'code' => $code,
            'url' => public_asset_url('flag', $file),
        ];
    }
    usort($items, static fn(array $a, array $b): int => strnatcasecmp($a['code'], $b['code']));
    return $items;
}

function ensure_photo_flag_override_column(): void
{
    static $done = false;
    if ($done) {
        return;
    }
    $done = true;
    try {
        $stmt = db()->query("SHOW COLUMNS FROM photos LIKE 'flag_override'");
        if (!$stmt || !$stmt->fetch()) {
            db()->exec("ALTER TABLE photos ADD COLUMN flag_override VARCHAR(120) NULL DEFAULT NULL AFTER normalized_name");
        }
    } catch (Throwable) {
        // The table may not exist before install.php has run.
    }
}

function ensure_photo_placeholder_column(): void
{
    static $done = false;
    if ($done) {
        return;
    }
    $done = true;
    try {
        $stmt = db()->query("SHOW COLUMNS FROM photos LIKE 'is_placeholder'");
        if (!$stmt || !$stmt->fetch()) {
            db()->exec("ALTER TABLE photos ADD COLUMN is_placeholder TINYINT(1) NOT NULL DEFAULT 0 AFTER flag_override");
        }
        mark_existing_placeholder_photos();
    } catch (Throwable) {
        // The table may not exist before install.php has run.
    }
}

function mark_existing_placeholder_photos(): void
{
    $source = BASE_DIR . '/assets/athlete-placeholder-import.png';
    if (!is_file($source)) {
        return;
    }
    $size = filesize($source);
    $hash = hash_file('sha256', $source);
    if ($size === false || $hash === false) {
        return;
    }

    $stmt = db()->prepare("SELECT id, filename FROM photos WHERE is_placeholder = 0 AND mime = 'image/png' AND size_bytes = ?");
    $stmt->execute([(int) $size]);
    $update = db()->prepare('UPDATE photos SET is_placeholder = 1 WHERE id = ?');
    foreach ($stmt->fetchAll() as $row) {
        $path = PHOTO_DIR . '/' . basename((string) $row['filename']);
        if (is_file($path) && hash_equals($hash, (string) hash_file('sha256', $path))) {
            $update->execute([(int) $row['id']]);
        }
    }
}

function upload_error_message(int $code): string
{
    return match ($code) {
        UPLOAD_ERR_INI_SIZE, UPLOAD_ERR_FORM_SIZE => 'File troppo grande.',
        UPLOAD_ERR_PARTIAL => 'Upload incompleto.',
        UPLOAD_ERR_NO_FILE => 'Nessun file selezionato.',
        default => 'Errore upload.',
    };
}
