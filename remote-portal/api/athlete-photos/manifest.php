<?php
declare(strict_types=1);
require __DIR__ . '/../../inc/bootstrap.php';
check_asset_token();
header('Content-Type: application/json; charset=utf-8');
ensure_photo_flag_override_column();
$stmt = db()->query('SELECT filename, athlete_name, flag_override FROM photos ORDER BY athlete_name ASC');
$photos = [];
foreach ($stmt->fetchAll() as $row) {
    $item = [
        'filename' => $row['filename'],
        'athleteName' => $row['athlete_name'],
        'url' => public_asset_url('photo', $row['filename']),
    ];
    if (!empty($row['flag_override'])) {
        $item['flagOverride'] = $row['flag_override'];
    }
    $photos[] = $item;
}
echo json_encode(['photos' => $photos], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
