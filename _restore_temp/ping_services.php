<?php
/**
 * ping_services.php — Notify RSS aggregators & blog search engines about new content
 *
 * Supports:
 *   - Weblogs.com (legacy ping)
 *   - Google Blog Search (deprecated, kept for compatibility)
 *   - Yandex Blog Search ping
 *   - Pingomatic (multi-ping service)
 *   - Feedburner (if you have a feed)
 *
 * Usage:
 *   - CLI:  php ping_services.php
 *   - Web:  https://althea-tech.ru/assets/api/ping_services.php?key=althea2026
 *
 * CRON: after fetch_news.php completes
 *   30 0,6,12,18 * * * /usr/bin/php /var/www/u3590665/data/www/althea-tech.ru/assets/api/ping_services.php >> /tmp/ping.log 2>&1
 */

declare(strict_types=1);

require_once __DIR__ . '/config.php';

$BASE = 'https://althea-tech.ru';
$RSS_URL = "$BASE/assets/api/rss.php";
$AUTH = 'althea2026';

if (php_sapi_name() !== 'cli' && ($_GET['key'] ?? '') !== $AUTH) {
    http_response_code(403);
    die('Forbidden');
}

$site_name = 'Althea Tech — DeepTech';
$site_url = $BASE . '/';
$rss_url = $RSS_URL;
$update_url = $BASE . '/';

$results = [];

// ---------------------------------------------------------------------------
// 1. Pingomatic (multi-service: forwards to Weblogs.com, Google Blog Search, etc.)
// ---------------------------------------------------------------------------
$results['pingomatic'] = xmlrpc_ping(
    'https://rpc.pingomatic.com/',
    $site_name, $site_url, $rss_url, $update_url
);

// ---------------------------------------------------------------------------
// 2. Twingly (blog search engine)
// ---------------------------------------------------------------------------
$results['twingly'] = http_get_ping(
    'http://rpc.twingly.com/',
    $site_name, $site_url, $rss_url
);

// ---------------------------------------------------------------------------
// 3. Yandex Webmaster sitemap ping (works 2024+)
// ---------------------------------------------------------------------------
$results['yandex_webmaster'] = http_get_ping(
    'https://webmaster.yandex.ru/ping?action=update-sitemap&url=' . urlencode($rss_url),
    $site_name, $site_url, $rss_url
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function xmlrpc_ping(string $endpoint, string $title, string $url, string $rss, string $upd): array {
    $xml = '<?xml version="1.0"?>' . "\n";
    $xml .= '<methodCall>';
    $xml .= '<methodName>weblogUpdates.extendedPing</methodName>';
    $xml .= '<params>';
    $xml .= '<param><value><string>' . htmlspecialchars($title) . '</string></value></param>';
    $xml .= '<param><value><string>' . htmlspecialchars($url) . '</string></value></param>';
    $xml .= '<param><value><string>' . htmlspecialchars($upd) . '</string></value></param>';
    $xml .= '<param><value><string>' . htmlspecialchars($rss) . '</string></value></param>';
    $xml .= '</params>';
    $xml .= '</methodCall>';

    $ch = curl_init($endpoint);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $xml,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_HTTPHEADER     => ['Content-Type: text/xml', 'User-Agent: Althea-Ping/1.0'],
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);

    return ['http_code' => $code, 'error' => $err, 'response' => substr((string)$resp, 0, 500)];
}

function http_get_ping(string $endpoint, string $title, string $url, string $rss): array {
    $sep = strpos($endpoint, '?') === false ? '?' : '&';
    $full = $endpoint . $sep . http_build_query(['title' => $title, 'url' => $url, 'rss' => $rss]);

    $ch = curl_init($full);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_USERAGENT      => 'Althea-Ping/1.0',
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_FOLLOWLOCATION => true,
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);

    return ['http_code' => $code, 'error' => $err, 'response' => substr((string)$resp, 0, 500)];
}

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------
if (php_sapi_name() === 'cli') {
    echo "Ping Services — " . date('Y-m-d H:i') . "\n";
    echo str_repeat('=', 60) . "\n";
    foreach ($results as $name => $r) {
        $ok = $r['http_code'] >= 200 && $r['http_code'] < 400;
        printf("%-15s %s HTTP %d %s\n",
            $name, $ok ? '✓' : '✗', $r['http_code'], $r['error'] ?: '');
    }
} else {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($results, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
}
