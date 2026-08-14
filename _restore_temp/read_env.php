<?php
header('Content-Type: text/plain; charset=utf-8');
$env_path = '/var/www/u3590665/data/.env';
if (file_exists($env_path)) {
    $content = file_get_contents($env_path);
    foreach (explode("\n", $content) as $line) {
        if (preg_match('/^(YOUTUBE_|GOOGLE_|CLIENT_)/i', $line)) {
            echo $line . "\n";
        }
    }
} else {
    echo "FILE NOT FOUND: $env_path\n";
    // Try alternative paths
    $paths = [
        '/var/www/u3590665/data/.althea_secrets.env',
        '/var/www/u3590665/data/www/althea-tech.ru/.env',
        '/var/www/u3590665/data/www/althea-tech.ru/.althea_secrets.env',
    ];
    foreach ($paths as $p) {
        if (file_exists($p)) {
            echo "\n=== Found: $p ===\n";
            $content = file_get_contents($p);
            foreach (explode("\n", $content) as $line) {
                if (preg_match('/^(YOUTUBE_|GOOGLE_|CLIENT_)/i', $line)) {
                    echo $line . "\n";
                }
            }
        }
    }
}
?>