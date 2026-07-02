<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
check_asset_token();

$type = (string) ($_GET['type'] ?? '');
$file = basename((string) ($_GET['file'] ?? ''));
$dir = null;
$allowed = [];
if ($type === 'video') {
    $dir = VIDEO_DIR;
    $allowed = allowed_video_ext();
} elseif ($type === 'photo') {
    $dir = PHOTO_DIR;
    $allowed = allowed_photo_ext();
}

$ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
if (!$dir || $file === '' || !in_array($ext, $allowed, true)) {
    http_response_code(404);
    exit;
}

$path = realpath($dir . '/' . $file);
$root = realpath($dir);
if (!$path || !$root || !str_starts_with($path, $root . DIRECTORY_SEPARATOR)) {
    http_response_code(404);
    exit;
}

$mime = match ($ext) {
    'mp4', 'm4v' => 'video/mp4',
    'webm' => 'video/webm',
    'ogg' => 'video/ogg',
    'mov' => 'video/quicktime',
    'jpg', 'jpeg' => 'image/jpeg',
    'png' => 'image/png',
    'webp' => 'image/webp',
    default => 'application/octet-stream',
};
header('Content-Type: ' . $mime);
header('Content-Length: ' . filesize($path));
header('Cache-Control: public, max-age=3600');
readfile($path);
