#!/usr/bin/env python3
"""
youtube_shorts.py v2.0 — automated YouTube Shorts generator for ALTHEA Research Brief

Pipeline:
1. Fetch fresh news from althea-tech.ru API (or local SQLite fallback)
2. Generate branded frame 1080x1920 (Pillow):
   - Top header bar (AMAGI/ALTHEA/Scio/CTC color-coded)
   - Title + summary (wrapped, Cyrillic-aware)
   - Source attribution
   - Footer with site URL + Telegram bot + hashtags
   - Progress bar at bottom (synced with audio)
3. Text-to-speech via edge-tts (Microsoft Neural, ru-RU-DmitryNeural, free, no API key)
4. Assemble MP4 video with FFmpeg (libx264 + AAC)
5. Upload to YouTube (if YOUTUBE_REFRESH_TOKEN env var is set)
6. Log to video_log table (prevents re-processing same news)

Runs in GitHub Actions (Ubuntu runner) — no load on Reg.ru server.
Cron: every 4 hours via .github/workflows/shorts.yml

Author: Alexey M. Burlai (AGIAMTech)
License: S-APL v2.0 / CC BY-NC 4.0
"""
import os
import sys
import subprocess
import asyncio
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

# News source — try API first, fallback to local SQLite (for testing)
ALTHEA_API_URL = os.environ.get('ALTHEA_API_URL', 'https://althea-tech.ru/assets/api/content.php?action=news&limit=5')

# Output paths
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output'))
LOG_FILE = os.environ.get('LOG_FILE', '/tmp/youtube_shorts.log')
STATE_FILE = os.path.join(OUTPUT_DIR, '.processed_ids.json')

# YouTube config
YOUTUBE_ENABLED = bool(os.environ.get('YOUTUBE_REFRESH_TOKEN'))
YOUTUBE_CHANNEL_HANDLE = '@ALTHEAResearchBrief'
YOUTUBE_CHANNEL_URL = 'https://www.youtube.com/@ALTHEAResearchBrief'
YOUTUBE_CHANNEL_ID = 'UC_xxx'  # Set after first upload

# edge-tts config
TTS_VOICE = os.environ.get('TTS_VOICE', 'ru-RU-DmitryNeural')
TTS_RATE = os.environ.get('TTS_RATE', '+0%')  # +0% = normal speed

# FFmpeg path (in GitHub Actions it's pre-installed at /usr/bin/ffmpeg)
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')

# Site branding
SITE_URL = 'https://althea-tech.ru'
NEWS_URL = 'https://althea-tech.ru/news.html'
BOT_URL = 'https://t.me/ALTHEA_Research_Briefbot'
SLOGAN = 'АЛТЕЯ — Инженерия доверия'

# Brand colors (RGB) — match site palette
BG = (11, 20, 36)              # --bg #0b1424
BG2 = (15, 23, 42)             # --bg2
FOOT_BG = (21, 35, 63)         # --s1
TEXT_W = (233, 238, 248)       # --text
MUTED = (168, 184, 212)        # --muted
FAINT = (110, 130, 165)        # --faint
AMBER = (245, 166, 35)         # --amagi (AMAGI brand)
SCIO_BLUE = (76, 195, 232)     # --scio
ALTHEA_GREEN = (45, 212, 167)  # --althea
CTC_PURPLE = (192, 132, 252)   # --ctc
LINE = (30, 41, 70)            # --line

# Category config: color + label + emoji + hashtag
CATS = {
    'amagi':       {'c': AMBER,        'e': '🟡', 'l': 'AMAGI',       'tag': '#AMAGI #AISafety #HardwareSecurity'},
    'althea':      {'c': ALTHEA_GREEN, 'e': '🟢', 'l': 'ALTHEA',      'tag': '#ALTHEA #CRISPR #BioEngineering'},
    'scio':        {'c': SCIO_BLUE,    'e': '🔵', 'l': 'Scio',        'tag': '#Scio #Deepfake #Forensics'},
    'ctc':         {'c': CTC_PURPLE,   'e': '🟣', 'l': 'CTC',         'tag': '#CTC #AITherapy #MedAI'},
    'industry':    {'c': MUTED,        'e': '📰', 'l': 'Industry',    'tag': '#DeepTech #Industry'},
    'publication': {'c': MUTED,        'e': '📚', 'l': 'Publication', 'tag': '#Publication #Research'},
}


# ============================================================
# LOGGING
# ============================================================

def log(msg):
    """Log to stdout + file."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = '[%s] %s' % (ts, msg)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ============================================================
# STATE MANAGEMENT (track processed news IDs)
# ============================================================

def load_processed_ids():
    """Load set of already-processed news IDs from state file."""
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('ids', []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_processed_id(news_id):
    """Add news_id to state file (prevents re-processing)."""
    ids = load_processed_ids()
    ids.add(str(news_id))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump({'ids': sorted(ids), 'updated': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


# ============================================================
# NEWS FETCHING
# ============================================================

def fetch_news():
    """Fetch latest news from althea-tech.ru API. Returns one fresh news item dict or None."""
    log('Fetching news from: ' + ALTHEA_API_URL)
    try:
        req = urllib.request.Request(
            ALTHEA_API_URL,
            headers={'User-Agent': 'AmagiShorts/2.0 (github.com/AGIAMTech/Amagi-framework)'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.URLError as e:
        log('API error: ' + str(e))
        return None
    except Exception as e:
        log('API exception: ' + str(e))
        return None

    if not data.get('ok'):
        log('API returned not-ok: ' + str(data)[:200])
        return None

    news_list = data.get('data', [])
    if not news_list:
        log('No news in API response')
        return None

    processed = load_processed_ids()
    for item in news_list:
        if str(item.get('id', '')) in processed:
            continue
        return item

    log('All available news already processed (' + str(len(news_list)) + ' items)')
    return None


# ============================================================
# TTS — edge-tts (Microsoft Neural, free, no API key)
# ============================================================

async def _tts_async(text, out_path):
    """Generate TTS audio file via edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(out_path)


def make_tts(text, out_path):
    """Generate TTS audio. Returns True on success, False on error."""
    try:
        asyncio.run(_tts_async(text, out_path))
        size = os.path.getsize(out_path)
        log('TTS: ' + out_path + ' (' + str(size) + ' bytes, voice=' + TTS_VOICE + ')')
        return True
    except Exception as e:
        log('TTS error: ' + str(e))
        return False


def build_speech(news):
    """Build the speech text from news item. Russian, ~30-45 sec when read."""
    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])

    parts = []
    # Branded intro
    parts.append(cc['l'] + '. ')
    # Title (main content)
    title = news.get('title', '').strip()
    if title:
        parts.append(title + '. ')
    # Summary (if available and not too long)
    summary = news.get('summary', '').strip()
    if summary and len(summary) > 30:
        parts.append(summary[:300] + '. ')
    # Source attribution
    source = news.get('source', '').strip()
    if source:
        parts.append('Источник: ' + source + '. ')
    # Outro
    parts.append('Подробнее на althea-tech.ru.')

    speech = ''.join(parts)
    # Cap at 500 chars to keep video under 60s
    if len(speech) > 500:
        speech = speech[:497] + '...'
    return speech


# ============================================================
# FRAME GENERATION (Pillow, 1080x1920 portrait)
# ============================================================

def wrap_text(text, font, max_w, draw):
    """Word-wrap text respecting max width. Returns list of lines."""
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(' '.join(cur))
            cur = [w]
    if cur:
        lines.append(' '.join(cur))
    return lines


def load_fonts():
    """Load fonts (try Noto Sans / DejaVu Sans for Cyrillic support)."""
    from PIL import ImageFont
    font_paths = [
        # Noto Sans SC (best for Cyrillic + Latin)
        '/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        # DejaVu Sans (always available on Linux)
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    bold_path = None
    reg_path = None
    for p in font_paths:
        if 'Bold' in p and not bold_path and os.path.exists(p):
            bold_path = p
        elif 'Bold' not in p and not reg_path and os.path.exists(p):
            reg_path = p
    # Fallback
    if not bold_path:
        bold_path = reg_path or '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if not reg_path:
        reg_path = bold_path

    try:
        return {
            'title': ImageFont.truetype(bold_path, 52),
            'body': ImageFont.truetype(reg_path, 36),
            'small': ImageFont.truetype(reg_path, 28),
            'header': ImageFont.truetype(bold_path, 40),
            'mono': ImageFont.truetype(reg_path, 24),
            'slogan': ImageFont.truetype(bold_path, 56),
        }
    except Exception as e:
        log('Font load error: ' + str(e) + ', using default')
        default = ImageFont.load_default()
        return {'title': default, 'body': default, 'small': default,
                'header': default, 'mono': default, 'slogan': default}


def make_frame(news, out_path):
    """Generate branded 1080x1920 PNG frame."""
    from PIL import Image, ImageDraw

    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    fonts = load_fonts()

    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])

    # ===== TOP HEADER BAR (colored by category) =====
    d.rectangle([0, 0, W, 100], fill=cc['c'])
    d.text((40, 25), 'ALTHEA Research Brief', fill=BG, font=fonts['header'])
    # Right side: category emoji
    d.text((W - 80, 30), cc['e'], fill=BG, font=fonts['header'])

    # ===== LEFT COLOR STRIPE (category indicator) =====
    d.rectangle([0, 100, 8, H - 350], fill=cc['c'])

    # ===== SLOGAN (just below header) =====
    slogan_y = 130
    d.text((40, slogan_y), SLOGAN, fill=cc['c'], font=fonts['slogan'])

    # ===== CATEGORY LABEL =====
    y = 210
    d.text((40, y), cc['l'], fill=cc['c'], font=fonts['header'])

    # ===== TITLE (wrapped, white) =====
    y = 290
    title = news.get('title', '')[:200]
    title_lines = wrap_text(title, fonts['title'], W - 80, d)[:5]
    for line in title_lines:
        d.text((40, y), line, fill=TEXT_W, font=fonts['title'])
        y += 65

    # ===== SUMMARY (wrapped, muted) =====
    y += 30
    summary = news.get('summary', '')[:400]
    if summary:
        for line in wrap_text(summary, fonts['body'], W - 80, d)[:6]:
            d.text((40, y), line, fill=MUTED, font=fonts['body'])
            y += 45

    # ===== SOURCE (small, scio-blue) =====
    y += 20
    source = news.get('source', '')[:50]
    if source:
        d.text((40, y), 'Источник: ' + source, fill=SCIO_BLUE, font=fonts['small'])

    # ===== FOOTER =====
    foot_y = H - 350
    d.rectangle([0, foot_y, W, H], fill=FOOT_BG)
    # Top border line
    d.rectangle([0, foot_y, W, foot_y + 2], fill=cc['c'])

    y = foot_y + 30
    d.text((40, y), NEWS_URL.replace('https://', ''), fill=SCIO_BLUE, font=fonts['body'])
    y += 50
    d.text((40, y), '@ALTHEA_Research_Briefbot', fill=TEXT_W, font=fonts['body'])
    y += 50
    # Hashtags
    tags = cc['tag'].split(' ')[:4]
    d.text((40, y), ' '.join(tags), fill=MUTED, font=fonts['small'])
    y += 40
    # Date
    pub_date = (news.get('published_at', '') or '')[:10]
    if pub_date:
        d.text((40, y), pub_date, fill=FAINT, font=fonts['mono'])

    # ===== PROGRESS BAR TRACK (will be filled by FFmpeg) =====
    pb_y = H - 60
    pb_h = 6
    d.rectangle([40, pb_y, W - 40, pb_y + pb_h], fill=LINE)

    img.save(out_path, 'PNG')
    log('Frame: ' + out_path + ' (cat=' + cat + ')')


# ============================================================
# VIDEO ASSEMBLY (FFmpeg)
# ============================================================

def get_audio_duration(audio_path):
    """Get audio duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_format', '-show_streams',
             '-of', 'json', audio_path],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(r.stdout)
        return float(data['format']['duration'])
    except Exception as e:
        log('ffprobe error: ' + str(e))
        return 30.0  # default 30s


def make_video(img_path, audio_path, out_path):
    """Assemble MP4 video from PNG + MP3 using FFmpeg."""
    duration = get_audio_duration(audio_path)
    log('Audio duration: ' + str(round(duration, 2)) + 's')

    # Add 1s intro (slogan frame) + 0.5s outro
    total_duration = duration + 1.5

    cmd = [
        FFMPEG, '-y',
        '-loop', '1', '-i', img_path,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-tune', 'stillimage',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-vf', 'scale=1080:1920:flags=lanczos,fps=30',
        '-t', str(total_duration),
        '-shortest',
        '-movflags', '+faststart',
        out_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            size = os.path.getsize(out_path)
            log('Video: ' + out_path + ' (' + str(size) + ' bytes, ' + str(round(total_duration, 1)) + 's)')
            return True
        else:
            log('FFmpeg error: ' + r.stderr[-500:])
            return False
    except Exception as e:
        log('FFmpeg exception: ' + str(e))
        return False


# ============================================================
# YOUTUBE UPLOAD (optional)
# ============================================================

def upload_to_youtube(video_path, title, description, tags):
    """Upload video to YouTube via Data API v3. Requires YOUTUBE_REFRESH_TOKEN env var."""
    if not YOUTUBE_ENABLED:
        log('YouTube upload disabled (no YOUTUBE_REFRESH_TOKEN)')
        return None, None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        log('google-api-python-client not installed — skipping YouTube upload')
        return None, None

    client_id = os.environ.get('YOUTUBE_CLIENT_ID')
    client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET')
    refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        log('Missing YouTube OAuth env vars')
        return None, None

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri='https://oauth2.googleapis.com/token',
            scopes=['https://www.googleapis.com/auth/youtube.upload']
        )
        yt = build('youtube', 'v3', credentials=creds)

        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000],
                'tags': tags,
                'categoryId': '28'  # Science & Technology
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True, chunksize=8*1024*1024)
        request = yt.videos().insert(part='snippet,status', body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log('Upload progress: ' + str(int(status.progress() * 100)) + '%')

        video_id = response.get('id')
        video_url = 'https://www.youtube.com/watch?v=' + video_id if video_id else None
        log('YouTube upload OK: ' + str(video_url))
        return video_id, video_url

    except Exception as e:
        log('YouTube upload error: ' + str(e))
        return None, None


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    log('=' * 60)
    log('YouTube Shorts generator v2.0 started')
    log('Voice: ' + TTS_VOICE + ', YouTube enabled: ' + str(YOUTUBE_ENABLED))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Fetch fresh news
    news = fetch_news()
    if not news:
        log('No fresh news to process. Exiting.')
        return 0

    nid = news.get('id', 'unknown')
    log('News: [' + str(nid) + '] ' + news.get('title', '')[:80])

    # 2. Generate branded frame
    frame_path = os.path.join(OUTPUT_DIR, 'frame_%s.png' % nid)
    try:
        make_frame(news, frame_path)
    except Exception as e:
        log('Frame error: ' + str(e))
        save_processed_id(nid)  # Don't retry this news
        return 1

    # 3. Generate TTS audio
    audio_path = os.path.join(OUTPUT_DIR, 'audio_%s.mp3' % nid)
    speech = build_speech(news)
    log('Speech (' + str(len(speech)) + ' chars): ' + speech[:100] + '...')
    if not make_tts(speech, audio_path):
        save_processed_id(nid)
        return 1

    # 4. Assemble video
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    video_path = os.path.join(OUTPUT_DIR, 'shorts_%s_%s.mp4' % (nid, ts))
    if not make_video(frame_path, audio_path, video_path):
        save_processed_id(nid)
        return 1

    # 5. Build YouTube metadata
    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])
    title = cc['l'] + ': ' + news.get('title', '')[:80]
    description = (
        news.get('summary', '') + '\n\n'
        '🔗 Источник: ' + news.get('url', '') + '\n'
        '📰 Все новости: ' + NEWS_URL + '\n'
        '🤖 Telegram-бот: ' + BOT_URL + '\n'
        '🏢 Сайт: ' + SITE_URL + '\n\n'
        '#' + cc['l'] + ' #DeepTech #ALTHEA #AISafety #Research'
    )
    tags = cc['tag'].split(' ') + ['ALTHEA', 'DeepTech', 'Research', 'АЛТЕЯ']

    # 6. Upload to YouTube (optional)
    yt_id, yt_url = None, None
    if YOUTUBE_ENABLED:
        yt_id, yt_url = upload_to_youtube(video_path, title, description, tags)

    # 7. Save state (mark news as processed)
    save_processed_id(nid)

    # 8. Cleanup temp files (keep final video)
    for tmp in [frame_path, audio_path]:
        try:
            os.remove(tmp)
        except Exception:
            pass

    log('=' * 60)
    log('DONE: ' + video_path)
    if yt_url:
        log('YouTube: ' + yt_url)
    log('Title: ' + title)
    return 0


if __name__ == '__main__':
    sys.exit(main())
