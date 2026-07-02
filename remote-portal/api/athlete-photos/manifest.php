<?php
declare(strict_types=1);
require __DIR__ . '/../../inc/bootstrap.php';
check_asset_token();
header('Content-Type: application/json; charset=utf-8');
$stmt = db()->query('SELECT filename, athlete_name FROM photos ORDER BY athlete_name ASC');
$photos = [];
foreach ($stmt->fetchAll() as $row) {
    $photos[] = [
        'filename' => $row['filename'],
        'athleteName' => $row['athlete_name'],
        'url' => public_asset_url('photo', $row['filename']),
    ];
}
echo json_encode(['photos' => $photos], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
