<?php
header('Cache-Control: no-cache, must-revalidate');
/**
 * stats.php — публичная статистика для отображения на сайте
 * GET — возвращает суммарные метрики
 */
require __DIR__ . '/config.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

try {
    $pdo = db();

    // Общее число посещений
    $total = (int)$pdo->query("SELECT COUNT(*) FROM visits")->fetchColumn();

    // Уникальные IP
    $unique = (int)$pdo->query("SELECT COUNT(DISTINCT ip) FROM visits")->fetchColumn();

    // Посещения за сегодня
    $today = (int)$pdo->query("SELECT COUNT(*) FROM visits WHERE created_at > datetime('now', '-1 day')")->fetchColumn();

    // Топ страниц
    $stmt = $pdo->query("SELECT path, COUNT(*) as cnt FROM visits GROUP BY path ORDER BY cnt DESC LIMIT 10");
    $topPages = $stmt->fetchAll();

    // Активность за последние 7 дней (по дням)
    $stmt = $pdo->query("SELECT date(created_at) as d, COUNT(*) as cnt FROM visits WHERE created_at > datetime('now', '-7 days') GROUP BY d ORDER BY d");
    $last7 = $stmt->fetchAll();

    // Тема dark/light
    $stmt = $pdo->query("SELECT theme, COUNT(*) as cnt FROM visits WHERE theme != '' GROUP BY theme");
    $themes = $stmt->fetchAll();

    // Языки
    $stmt = $pdo->query("SELECT lang, COUNT(*) as cnt FROM visits WHERE lang != '' GROUP BY lang ORDER BY cnt DESC LIMIT 5");
    $langs = $stmt->fetchAll();

    json_response([
        'ok' => true,
        'total_visits' => $total,
        'unique_visitors' => $unique,
        'today_visits' => $today,
        'top_pages' => $topPages,
        'last_7_days' => $last7,
        'themes' => $themes,
        'languages' => $langs,
        'updated' => date('c'),
    ]);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => 'server'], 500);
}
