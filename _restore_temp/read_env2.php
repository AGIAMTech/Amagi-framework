<?php
header('Content-Type: text/plain; charset=utf-8');
$paths = [
    '/var/www/u3590665/data/.env',
    '/var/www/u3590665/data/.althea_secrets.env',
    '/var/www/u3590665/data/www/althea-tech.ru/.env',
    '/var/www/u3590665/data/www/althea-tech.ru/.althea_secrets.env',
];
foreach ($paths as $p) {
    echo "=== $p ===\n";
    if (file_exists($p)) {
        $content = file_get_contents($p);
        $lines = explode("\n", $content);
        echo "Total lines: " . count($lines) . "\n";
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line && !preg_match('/^#/', $line)) {
                // Show all non-comment lines
                echo $line . "\n";
            }
        }
    } else {
        echo "NOT FOUND\n";
    }
    echo "\n";
}
?>