<?php
declare(strict_types=1);
require __DIR__ . '/../../inc/bootstrap.php';
check_asset_token();
header('Content-Type: application/json; charset=utf-8');
$stmt = db()->query('SELECT filename FROM videos ORDER BY filename ASC');
$videos = [];
foreach ($stmt->fetchAll() as $row) {
    $videos[] = [
        'filename' => $row['filename'],
        'url' => public_asset_url('video', $row['filename']),
    ];
}
echo json_encode(['videos' => $videos], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
