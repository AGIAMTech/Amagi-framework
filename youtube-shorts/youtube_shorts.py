#!/usr/bin/env python3
"""
youtube_shorts.py v3.0 — production-ready automated YouTube Shorts generator

Pipeline:
1. Fetch 20 fresh news from althea-tech.ru API
2. LLM filter via SambaNova Meta-Llama-3.3-70B:
   - Score each news: relevance + YouTube appeal
   - LLM also writes the narration script (intelligently, not just title+summary)
   - Pick top-1 most interesting for Shorts
3. Generate DYNAMIC branded frame 1080x1920 (Pillow):
   - Photo background with Ken Burns zoom (if image_url available)
   - Animated gradient + pulsing nodes (fallback for no-photo news)
   - Category-colored elements
   - Progress bar at bottom (synced with audio)
4. TTS via edge-tts with prosody tuned per category:
   - AMAGI: serious, slower (-5% rate)
   - ALTHEA: neutral
   - Scio: mysterious, slightly slower
   - CTC: warm, neutral
   - Industry: energetic (+5% rate)
5. Background music (royalty-free, Kevin MacLeod CC BY 4.0):
   - Mixed at -24dB (subtle, doesn't compete with TTS)
   - Track selected by category
6. Assemble MP4 via FFmpeg (H.264 + AAC, 1080x1920, 30fps)
7. Upload to YouTube (if YOUTUBE_REFRESH_TOKEN configured)
8. Auto-cleanup: delete videos older than 24h from output/

Runs in GitHub Actions (Ubuntu runner) — no load on Reg.ru server.
Cron: every 4 hours via .github/workflows/shorts.yml

LIMITS AWARENESS:
- YouTube Data API v3: 10,000 units/day, 1,600 per upload = max 6/day
- SambaNova free tier: 10 RPM, ~1-2s per call
- GitHub Actions: 2,000 min/month (private), unlimited (public)
- edge-tts: free, no key, ~1 req/sec safe
- Cron every 4h = 6 runs/day = within YouTube quota (tight)

Author: Alexey M. Burlai (AGIAMTech)
License: S-APL v2.0 / CC BY-NC 4.0
"""
import os
import sys
import subprocess
import asyncio
import json
import urllib.request
import urllib.error
import time
import math
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', SCRIPT_DIR / 'output'))
MUSIC_DIR = SCRIPT_DIR / 'assets' / 'music'
LOG_FILE = os.environ.get('LOG_FILE', '/tmp/youtube_shorts.log')
STATE_FILE = OUTPUT_DIR / '.processed_ids.json'

# News API
ALTHEA_API_URL = os.environ.get('ALTHEA_API_URL',
    'https://althea-tech.ru/assets/api/content.php?action=news&limit=20')

# YouTube config
YOUTUBE_ENABLED = bool(os.environ.get('YOUTUBE_REFRESH_TOKEN'))
YOUTUBE_CHANNEL_HANDLE = '@ALTHEAResearchBrief'
YOUTUBE_CHANNEL_URL = 'https://www.youtube.com/@ALTHEAResearchBrief'

# TTS config — voice per category for variety
TTS_VOICES = {
    'amagi':       {'voice': 'ru-RU-DmitryNeural',   'rate': '-5%',  'pitch': '-2Hz'},  # serious
    'althea':      {'voice': 'ru-RU-SvetlanaNeural',  'rate': '+0%',  'pitch': '+0Hz'},  # warm female
    'scio':        {'voice': 'ru-RU-DmitryNeural',    'rate': '-8%',  'pitch': '-3Hz'},  # mysterious
    'ctc':         {'voice': 'ru-RU-SvetlanaNeural',  'rate': '+0%',  'pitch': '+0Hz'},  # neutral female
    'industry':    {'voice': 'ru-RU-DmitryNeural',    'rate': '+5%',  'pitch': '+2Hz'},  # energetic
    'publication': {'voice': 'ru-RU-DmitryNeural',    'rate': '+0%',  'pitch': '+0Hz'},  # neutral
}
DEFAULT_TTS = TTS_VOICES['industry']

# Music per category (royalty-free, Kevin MacLeod CC BY 4.0)
MUSIC_MAP = {
    'amagi':       'tech_amagi.m4a',
    'althea':      'calm_althea.m4a',
    'scio':        'mystery_scio.m4a',
    'ctc':         'calm_althea.m4a',      # reuse calm for medical
    'industry':    'tech_amagi.m4a',       # reuse tech for industry
    'publication': 'mystery_scio.m4a',     # reuse mystery for science
}
MUSIC_VOLUME = 0.06  # -24dB — subtle, doesn't compete with TTS

# FFmpeg
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')

# Cleanup: delete videos older than this
MAX_VIDEO_AGE_HOURS = 24

# Site branding
SITE_URL = 'https://althea-tech.ru'
NEWS_URL = 'https://althea-tech.ru/news.html'
BOT_URL = 'https://t.me/ALTHEA_Research_Briefbot'
SLOGAN = 'АЛТЕЯ — Инженерия доверия'

# Brand colors (RGB)
BG = (11, 20, 36)
BG2 = (15, 23, 42)
FOOT_BG = (21, 35, 63)
TEXT_W = (233, 238, 248)
MUTED = (168, 184, 212)
FAINT = (110, 130, 165)
AMBER = (245, 166, 35)
SCIO_BLUE = (76, 195, 232)
ALTHEA_GREEN = (45, 212, 167)
CTC_PURPLE = (192, 132, 252)
LINE = (30, 41, 70)

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
# STATE MANAGEMENT
# ============================================================

def load_processed_ids():
    try:
        with open(STATE_FILE, 'r') as f:
            return set(json.load(f).get('ids', []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_id(news_id):
    ids = load_processed_ids()
    ids.add(str(news_id))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump({'ids': sorted(ids), 'updated': datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)


# ============================================================
# AUTO-CLEANUP: delete videos older than MAX_VIDEO_AGE_HOURS
# ============================================================

def cleanup_old_videos():
    """Delete .mp4 files in OUTPUT_DIR older than MAX_VIDEO_AGE_HOURS."""
    if not OUTPUT_DIR.exists():
        return 0
    cutoff = datetime.now() - timedelta(hours=MAX_VIDEO_AGE_HOURS)
    deleted = 0
    for f in OUTPUT_DIR.glob('*.mp4'):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
                log(f'Cleanup: deleted {f.name} (age: {(datetime.now() - mtime).total_seconds()/3600:.1f}h)')
        except Exception as e:
            log(f'Cleanup error for {f.name}: {e}')
    if deleted:
        log(f'Cleanup: removed {deleted} old videos')
    return deleted


# ============================================================
# NEWS FETCHING + LLM FILTERING
# ============================================================

def fetch_news_raw(limit=20):
    """Fetch latest news list from API."""
    api_url = ALTHEA_API_URL
    import re
    if 'limit=' in api_url:
        api_url = re.sub(r'limit=\d+', f'limit={limit}', api_url)
    elif '?' in api_url:
        api_url = api_url + f'&limit={limit}'
    else:
        api_url = api_url + f'?limit={limit}'

    log(f'Fetching news: {api_url}')
    try:
        req = urllib.request.Request(api_url,
            headers={'User-Agent': 'AmagiShorts/3.0 (github.com/AGIAMTech/Amagi-framework)'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        return data.get('data', []) if data.get('ok') else []
    except Exception as e:
        log(f'API error: {e}')
        return []


def fetch_news():
    """Fetch news, run LLM filter, return best item or None."""
    news_list = fetch_news_raw(limit=10)  # 10 instead of 20 — faster LLM, fits context
    if not news_list:
        log('No news fetched')
        return None

    processed = load_processed_ids()
    fresh = [n for n in news_list if str(n.get('id', '')) not in processed]
    if not fresh:
        log('All available news already processed')
        return None

    log(f'Got {len(news_list)} news, {len(fresh)} fresh')

    samba_key = os.environ.get('OPENROUTER_KEY', '')
    if samba_key:
        try:
            from llm_filter import filter_best_news
            log('Running LLM filter via OpenRouter...')
            best = filter_best_news(fresh, min_relevance=5, min_appeal=5)
            if best:
                log(f'LLM selected: [{best.get("id")}] {best.get("title", "")[:80]}')
                log(f'  Score: rel={best.get("llm_relevance", "?")}/10 appeal={best.get("llm_appeal", "?")}/10')
                log(f'  Reason: {best.get("llm_reason", "")}')
                return best
            log('LLM filter: no suitable news, will retry next run')
            return None  # Don't fall back — better skip than waste YouTube quota
        except Exception as e:
            log(f'LLM filter error: {e}')
            # Fallback to first fresh if LLM fails (better than nothing)
            log('Falling back to first fresh news')
            return fresh[0]

    log('No OPENROUTER_KEY — using first fresh news')
    return fresh[0]


# ============================================================
# LLM NARRATION: generate TTS script (not just title+summary)
# ============================================================

def generate_narration_script(news):
    """
    Use LLM to write a natural narration script from news.
    Returns Russian text optimized for TTS (~30-45 sec when read).
    """
    openrouter_key = os.environ.get('OPENROUTER_KEY', '')
    if not openrouter_key:
        # Fallback: simple concatenation
        return _fallback_narration(news)

    try:
        from llm_filter import generate_narration
        narration = generate_narration(news)
        if narration:
            return narration
        log('LLM narration: empty response, using fallback')
        return _fallback_narration(news)
    except Exception as e:
        log(f'LLM narration error: {e}, using fallback')
        return _fallback_narration(news)


def _fallback_narration(news):
    """Simple narration if LLM unavailable."""
    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])
    parts = [cc['l'] + '.']
    title = (news.get('title') or '').strip()
    if title:
        parts.append(title + '.')
    summary = (news.get('summary') or '').strip()
    if summary and len(summary) > 30:
        parts.append(summary[:300] + '.')
    parts.append('Подробнее на althea-tech.ru.')
    text = ' '.join(parts)[:500]
    log(f'Fallback narration ({len(text)} chars)')
    return text


# ============================================================
# TTS — edge-tts with category-specific prosody
# ============================================================

async def _tts_async(text, out_path, voice, rate, pitch):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def make_tts(text, out_path, category='industry'):
    """Generate TTS audio with category-specific voice prosody."""
    cfg = TTS_VOICES.get(category, DEFAULT_TTS)
    try:
        asyncio.run(_tts_async(text, out_path, cfg['voice'], cfg['rate'], cfg['pitch']))
        size = os.path.getsize(out_path)
        log(f'TTS: {out_path} ({size} bytes, voice={cfg["voice"]} rate={cfg["rate"]})')
        return True
    except Exception as e:
        log(f'TTS error: {e}')
        return False


# ============================================================
# FRAME GENERATION — dynamic background
# ============================================================

def load_fonts():
    from PIL import ImageFont
    paths_bold = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                  '/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf']
    paths_reg = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf']
    bold = next((p for p in paths_bold if os.path.exists(p)), paths_bold[0])
    reg = next((p for p in paths_reg if os.path.exists(p)), paths_reg[0])
    try:
        return {
            'title': ImageFont.truetype(bold, 52),
            'body': ImageFont.truetype(reg, 36),
            'small': ImageFont.truetype(reg, 28),
            'header': ImageFont.truetype(bold, 40),
            'slogan': ImageFont.truetype(bold, 56),
        }
    except:
        f = ImageFont.load_default()
        return {'title': f, 'body': f, 'small': f, 'header': f, 'slogan': f}


def wrap_text(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(' '.join(cur))
            cur = [w]
    if cur:
        lines.append(' '.join(cur))
    return lines


def download_image(url, out_path):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Referer': 'https://althea-tech.ru/'
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            with open(out_path, 'wb') as f:
                f.write(r.read())
        return True
    except Exception as e:
        log(f'Image download error: {e}')
        return False


def make_frame(news, photo_path, out_path):
    """Generate dynamic 1080x1920 frame. Uses photo if available, else animated bg."""
    from PIL import Image, ImageDraw, ImageFilter
    import random

    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    fonts = load_fonts()

    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])

    # === BACKGROUND ===
    if photo_path and os.path.exists(photo_path):
        try:
            photo = Image.open(photo_path).convert('RGB')
            pr = photo.width / photo.height
            tr = W / H
            if pr > tr:
                new_h = H
                new_w = int(H * pr)
            else:
                new_w = W
                new_h = int(W / pr)
            photo = photo.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - W) // 2
            top = (new_h - H) // 2
            photo = photo.crop((left, top, left + W, top + H))
            photo = photo.filter(ImageFilter.GaussianBlur(radius=2))
            overlay = Image.new('RGB', (W, H), BG)
            tint = Image.new('RGB', (W, H), cc['c'])
            blended = Image.blend(photo, overlay, 0.65)
            blended = Image.blend(blended, tint, 0.15)
            img = blended
            d = ImageDraw.Draw(img)
        except Exception as e:
            log(f'Photo error: {e}, using animated bg')
            photo_path = None

    if not photo_path or not os.path.exists(photo_path):
        # === ANIMATED BG: radial gradient + pulsing nodes ===
        cx, cy = W // 2, H // 3
        max_r = int(math.sqrt(W**2 + H**2) / 2)
        for r in range(max_r, 0, -10):
            t = r / max_r
            col = (
                int(BG[0] * (1-t*0.3) + cc['c'][0] * t*0.3),
                int(BG[1] * (1-t*0.3) + cc['c'][1] * t*0.3),
                int(BG[2] * (1-t*0.3) + cc['c'][2] * t*0.3),
            )
            d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col)

        # Grid lines (faint)
        for x in range(0, W, 80):
            d.line([(x, 100), (x, H-350)], fill=(20, 30, 50), width=1)
        for y in range(100, H-350, 80):
            d.line([(0, y), (W, y)], fill=(20, 30, 50), width=1)

        # Network nodes (AMAGI-style)
        random.seed(42)
        nodes = [
            (200, 400, AMBER), (880, 500, SCIO_BLUE),
            (540, 700, ALTHEA_GREEN), (180, 1000, CTC_PURPLE),
            (900, 1100, AMBER), (540, 1300, SCIO_BLUE),
        ]
        for nx, ny, nc in nodes:
            for r, alpha in [(40, 20), (28, 40), (18, 80)]:
                glow = Image.new('RGBA', (r*2, r*2), nc + (alpha,))
                img.paste(glow, (nx-r, ny-r), glow)
            d.ellipse([nx-6, ny-6, nx+6, ny+6], fill=nc)
        d = ImageDraw.Draw(img)
        for i, (x1, y1, _) in enumerate(nodes):
            for j, (x2, y2, _) in enumerate(nodes):
                if i < j and abs(i-j) <= 2:
                    d.line([(x1, y1), (x2, y2)], fill=(40, 60, 100), width=1)

    # === HEADER ===
    d.rectangle([0, 0, W, 100], fill=cc['c'])
    d.text((40, 25), 'ALTHEA Research Brief', fill=BG, font=fonts['header'])
    d.text((W - 80, 30), cc['e'], fill=BG, font=fonts['header'])

    # Slogan + category
    d.text((40, 130), SLOGAN, fill=cc['c'], font=fonts['slogan'])
    d.text((40, 210), cc['l'], fill=cc['c'], font=fonts['header'])

    # === TITLE ===
    y = 290
    title = (news.get('title') or '')[:200]
    for line in wrap_text(title, fonts['title'], W - 80, d)[:5]:
        for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['title'])
        d.text((40, y), line, fill=TEXT_W, font=fonts['title'])
        y += 65

    # === SUMMARY ===
    y += 30
    summary = (news.get('summary') or '')[:400]
    if summary:
        for line in wrap_text(summary, fonts['body'], W - 80, d)[:6]:
            for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['body'])
            d.text((40, y), line, fill=MUTED, font=fonts['body'])
            y += 45

    # Source
    y += 20
    source = (news.get('source') or '')[:50]
    if source:
        d.text((40, y), 'Источник: ' + source, fill=SCIO_BLUE, font=fonts['small'])

    # === FOOTER ===
    foot_y = H - 350
    d.rectangle([0, foot_y, W, H], fill=FOOT_BG)
    d.rectangle([0, foot_y, W, foot_y + 2], fill=cc['c'])
    y = foot_y + 30
    d.text((40, y), NEWS_URL.replace('https://', ''), fill=SCIO_BLUE, font=fonts['body'])
    y += 50
    d.text((40, y), '@ALTHEA_Research_Briefbot', fill=TEXT_W, font=fonts['body'])
    y += 50
    d.text((40, y), ' '.join(cc['tag'].split(' ')[:4]), fill=MUTED, font=fonts['small'])
    y += 40
    pub_date = (news.get('published_at') or '')[:10]
    if pub_date:
        d.text((40, y), pub_date, fill=FAINT, font=fonts['small'])

    img.save(out_path, 'PNG')
    log(f'Frame: {out_path} (cat={cat})')


# ============================================================
# VIDEO ASSEMBLY — Ken Burns + progress bar + music
# ============================================================

def get_audio_duration(audio_path):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_format', '-of', 'json', audio_path],
            capture_output=True, text=True, timeout=15)
        return float(json.loads(r.stdout)['format']['duration'])
    except:
        return 30.0


def make_video(img_path, audio_path, out_path, music_path, category='industry'):
    """Assemble MP4: Ken Burns zoom + progress bar + ambient music."""
    duration = get_audio_duration(audio_path)
    # YouTube Shorts limit: 60s. We target max 50s to be safe.
    if duration > 50:
        log(f'Audio too long ({duration:.1f}s), truncating to 50s for Shorts limit')
        # Truncate audio using ffmpeg
        truncated_audio = str(audio_path) + '.trunc.mp3'
        subprocess.run([FFMPEG, '-y', '-i', audio_path, '-t', '50',
                        '-c', 'copy', truncated_audio],
                       capture_output=True, timeout=30)
        audio_path = truncated_audio
        duration = 50
    total_duration = duration + 1.0  # 1s tail
    log(f'Video: dur={duration:.2f}s, total={total_duration:.2f}s')

    fps = 30
    total_frames = int(total_duration * fps)
    cc = CATS.get(category, CATS['industry'])
    cat_color_hex = f'0x{cc["c"][0]:02x}{cc["c"][1]:02x}{cc["c"][2]:02x}'

    # Video filter: scale → Ken Burns → progress bar
    zoom_expr = f"1+0.15*on/{total_frames}"
    vf = (
        f"scale=2160:3840:flags=lanczos,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:s=1080x1920:fps={fps},"
        f"format=yuv420p,"
        f"drawbox=x=40:y=1850:w=1000:h=8:color=black@0.5:t=fill,"
        f"drawbox=x=40:y=1850:w='1000*t/{total_duration}':h=8:color={cat_color_hex}@0.9:t=fill"
    )

    # Audio: TTS + ambient music
    if music_path and os.path.exists(music_path):
        fc = (
            f"[0:v]{vf}[v];"
            f"[1:a]volume=1.0[voice];"
            f"[2:a]volume={MUSIC_VOLUME},afade=t=in:st=0:d=1,"
            f"afade=t=out:st={max(0, duration-1):.2f}:d=1[music];"
            f"[voice][music]amix=inputs=2:duration=first[a]"
        )
        cmd = [FFMPEG, '-y',
            '-loop', '1', '-i', img_path,
            '-i', audio_path,
            '-i', music_path,
            '-filter_complex', fc,
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
            '-t', str(total_duration), '-movflags', '+faststart', out_path]
    else:
        cmd = [FFMPEG, '-y',
            '-loop', '1', '-i', img_path,
            '-i', audio_path,
            '-vf', vf,
            '-map', '0:v', '-map', '1:a',
            '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
            '-t', str(total_duration), '-shortest', '-movflags', '+faststart', out_path]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            log(f'Video OK: {out_path} ({os.path.getsize(out_path)} bytes, {total_duration:.1f}s)')
            return True
        log(f'FFmpeg error: {r.stderr[-400:]}')
        return False
    except Exception as e:
        log(f'FFmpeg exception: {e}')
        return False


# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def upload_to_youtube(video_path, title, description, tags):
    """Upload to YouTube via Data API v3. Returns (video_id, video_url) or (None, None)."""
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

    try:
        creds = Credentials(
            token=None,
            refresh_token=os.environ.get('YOUTUBE_REFRESH_TOKEN'),
            client_id=os.environ.get('YOUTUBE_CLIENT_ID'),
            client_secret=os.environ.get('YOUTUBE_CLIENT_SECRET'),
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

        media = MediaFileUpload(video_path, mimetype='video/mp4',
                                resumable=True, chunksize=8*1024*1024)
        request = yt.videos().insert(part='snippet,status', body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log(f'Upload progress: {int(status.progress() * 100)}%')

        video_id = response.get('id')
        video_url = f'https://www.youtube.com/watch?v={video_id}' if video_id else None
        log(f'YouTube upload OK: {video_url}')
        return video_id, video_url
    except Exception as e:
        log(f'YouTube upload error: {e}')
        return None, None


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    log('=' * 60)
    log('YouTube Shorts v3.0 started')
    log(f'YouTube enabled: {YOUTUBE_ENABLED}, channel: {YOUTUBE_CHANNEL_HANDLE}')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 0. Cleanup old videos (older than 24h)
    cleanup_old_videos()

    # 1. Fetch + LLM filter news
    news = fetch_news()
    if not news:
        log('No suitable news. Exiting.')
        return 0

    nid = news.get('id', 'unknown')
    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])
    log(f'News: [{nid}] {news.get("title", "")[:80]} (cat={cat})')

    # 2. Generate narration script via LLM (or fallback)
    narration = generate_narration_script(news)

    # 3. Generate frame (with photo if available)
    frame_path = OUTPUT_DIR / f'frame_{nid}.png'
    photo_path = OUTPUT_DIR / f'photo_{nid}.jpg'
    if news.get('image_url'):
        if not download_image(news['image_url'], str(photo_path)):
            photo_path = None
    else:
        photo_path = None
    try:
        make_frame(news, photo_path, str(frame_path))
    except Exception as e:
        log(f'Frame error: {e}')
        save_processed_id(nid)
        return 1

    # 4. Generate TTS with category-specific prosody
    audio_path = OUTPUT_DIR / f'audio_{nid}.mp3'
    if not make_tts(narration, str(audio_path), category=cat):
        save_processed_id(nid)
        return 1

    # 5. Select music track
    music_file = MUSIC_MAP.get(cat, 'tech_amagi.m4a')
    music_path = MUSIC_DIR / music_file
    if not music_path.exists():
        log(f'Music file not found: {music_path}')
        music_path = None

    # 6. Assemble video
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    video_path = OUTPUT_DIR / f'shorts_{nid}_{ts}.mp4'
    if not make_video(str(frame_path), str(audio_path), str(video_path),
                      str(music_path) if music_path else None, category=cat):
        save_processed_id(nid)
        return 1

    # 7. YouTube metadata
    title = f'{cc["l"]}: {news.get("title", "")[:70]}'
    music_attribution = ''
    if music_path:
        track_name = {
            'tech_amagi.m4a': '"Decisions"',
            'calm_althea.m4a': '"Cool Vibes"',
            'mystery_scio.m4a': '"Investigations"',
        }.get(music_file, '')
        if track_name:
            music_attribution = f'\n\nMusic: {track_name} by Kevin MacLeod (incompetech.com)\nLicensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/'

    description = (
        f'{news.get("summary", "")}\n\n'
        f'🔗 Источник: {news.get("url", "")}\n'
        f'📰 Все новости: {NEWS_URL}\n'
        f'🤖 Telegram-бот: {BOT_URL}\n'
        f'🏢 Сайт: {SITE_URL}\n'
        f'📺 YouTube канал: {YOUTUBE_CHANNEL_URL}{music_attribution}'
    )
    tags = cc['tag'].split(' ') + ['ALTHEA', 'DeepTech', 'Research', 'АЛТЕЯ']

    # 8. Upload to YouTube
    yt_id, yt_url = None, None
    if YOUTUBE_ENABLED:
        yt_id, yt_url = upload_to_youtube(str(video_path), title, description, tags)

    # 9. Save state
    save_processed_id(nid)

    # 10. Cleanup temp files
    for tmp in [frame_path, audio_path, photo_path]:
        try:
            if tmp and tmp.exists():
                tmp.unlink()
        except:
            pass

    log('=' * 60)
    log(f'DONE: {video_path}')
    if yt_url:
        log(f'YouTube: {yt_url}')
    log(f'Title: {title}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
