<?php
header('Content-Type: text/plain; charset=utf-8');
$logs = ['/tmp/tg_bot.log','/tmp/research_post.log','/tmp/news_images.log','/tmp/tg_groups_poster.log','/tmp/news_cron.log','/tmp/site_watchdog.log','/tmp/bot_watchdog.log','/tmp/daily_stats.log','/tmp/dashboard.log','/tmp/seo_audit.log','/tmp/broken_links.log','/tmp/auto_promote.log','/tmp/yw_monitor.log','/tmp/sitemap_cron.log'];
foreach ($logs as $log) {
    echo "\n=== $log ===\n";
    if (file_exists($log)) {
        $content = file_get_contents($log);
        $lines = explode("\n", $content);
        $total = count($lines);
        echo "Lines: $total\n---\n";
        $start = max(0, $total - 15);
        for ($i = $start; $i < $total; $i++) echo $lines[$i]."\n";
        echo "---\n";
    } else echo "NOT FOUND\n";
}
?>