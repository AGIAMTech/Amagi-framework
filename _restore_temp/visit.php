<?php
/**
 * visit.php — логирование посещения (вызывается с frontend)
 * POST { path, lang, theme }
 * GET — returns 204 No Content (for crawlers, prevents GSC errors)
 */
require __DIR__ . '/config.php';

// GET requests: return 204 No Content (silent OK for crawlers)
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(204);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true);
if (!is_array($input)) $input = $_POST;

$path = parse_url($input['path'] ?? '/', PHP_URL_PATH);
$path = substr($path, 0, 500);

// Игнорируем запросы к assets и api
if (preg_match('#^/assets/#', $path)) {
    json_response(['ok' => true, 'skipped' => true]);
}

try {
    $pdo = db();
    $stmt = $pdo->prepare("INSERT INTO visits (path, ip, user_agent, referrer, lang, theme) VALUES (?, ?, ?, ?, ?, ?)");
    $stmt->execute([
        $path,
        client_ip(),
        substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 500),
        substr($_SERVER['HTTP_REFERER'] ?? '', 0, 500),
        substr($input['lang'] ?? '', 0, 10),
        substr($input['theme'] ?? '', 0, 10),
    ]);
    json_response(['ok' => true]);
} catch (Throwable $e) {
    @file_put_contents(LOG_FILE, date('c') . " VISIT ERROR: " . $e->getMessage() . "\n", FILE_APPEND);
    json_response(['ok' => false, 'error' => 'server'], 500);
}
