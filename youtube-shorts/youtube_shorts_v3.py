#!/usr/bin/env python3
"""
youtube_shorts_v3.py — Demo: 3 visual variants for ALTHEA Shorts

Generates 3 versions of the same news item so user can compare:
  - Variant A: Ken Burns on photo + animated text + progress bar (no music)
  - Variant B: Variant A + ambient background music (-22dB)
  - Variant C: Pure animated background (CSS-like) — pulsing dots + gradient, no photo

All 3 use the same news, same TTS audio — only visuals differ.

Usage:
  python youtube_shorts_v3.py <news_id>
"""
import os
import sys
import subprocess
import asyncio
import json
import urllib.request
from datetime import datetime

# Reuse config from main script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_shorts import (
    log, fetch_news, make_tts, build_speech, load_fonts,
    BG, BG2, FOOT_BG, TEXT_W, MUTED, FAINT, AMBER, SCIO_BLUE, ALTHEA_GREEN, CTC_PURPLE, LINE,
    CATS, SITE_URL, NEWS_URL, BOT_URL, SLOGAN,
    TTS_VOICE, TTS_RATE, ALTHEA_API_URL, FFMPEG
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'demo3')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_specific_news(news_id):
    """Fetch a specific news item by ID via API."""
    log(f'Fetching news id={news_id} from API')
    try:
        req = urllib.request.Request(
            ALTHEA_API_URL,
            headers={'User-Agent': 'AmagiShorts/3.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        for n in data.get('data', []):
            if str(n.get('id')) == str(news_id):
                return n
        log(f'News id={news_id} not found in API response')
        return None
    except Exception as e:
        log(f'API error: {e}')
        return None


def download_image(url, out_path):
    """Download image from URL. Returns True on success."""
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


def wrap_text(text, font, max_w, draw):
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


def get_audio_duration(audio_path):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_format', '-of', 'json', audio_path],
            capture_output=True, text=True, timeout=15
        )
        return float(json.loads(r.stdout)['format']['duration'])
    except:
        return 30.0


# ============================================================
# FRAME GENERATION — Variant A (photo + dark overlay + text)
# ============================================================

def make_frame_a(news, photo_path, out_path):
    """Variant A: Photo background with dark overlay + branded text on top."""
    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    fonts = load_fonts()

    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])

    # Background = photo (cover-fit, blurred + darkened)
    if photo_path and os.path.exists(photo_path):
        try:
            photo = Image.open(photo_path).convert('RGB')
            # Cover-fit: resize and crop
            pr = photo.width / photo.height
            tr = W / H
            if pr > tr:
                new_h = H
                new_w = int(H * pr)
            else:
                new_w = W
                new_h = int(W / pr)
            photo = photo.resize((new_w, new_h), Image.LANCZOS)
            # Center crop
            left = (new_w - W) // 2
            top = (new_h - H) // 2
            photo = photo.crop((left, top, left + W, top + H))
            # Slight blur for depth
            photo = photo.filter(ImageFilter.GaussianBlur(radius=2))
            # Darken with category-tinted overlay
            overlay = Image.new('RGB', (W, H), BG)
            tint = Image.new('RGB', (W, H), cc['c'])
            # Blend: 70% dark + 20% tint + 10% photo
            blended = Image.blend(photo, overlay, 0.65)
            blended = Image.blend(blended, tint, 0.15)
            img = blended
            d = ImageDraw.Draw(img)
        except Exception as e:
            log(f'Photo processing error: {e}, using solid bg')

    # Top header bar (category-colored)
    d.rectangle([0, 0, W, 100], fill=cc['c'])
    d.text((40, 25), 'ALTHEA Research Brief', fill=BG, font=fonts['header'])
    d.text((W - 80, 30), cc['e'], fill=BG, font=fonts['header'])

    # Slogan
    d.text((40, 130), SLOGAN, fill=cc['c'], font=fonts['slogan'])

    # Category label
    d.text((40, 210), cc['l'], fill=cc['c'], font=fonts['header'])

    # Title (white, bold, on semi-transparent panel)
    y = 290
    # Draw a subtle dark panel behind text
    panel_top = y - 20
    panel_bottom = y + 350
    panel = Image.new('RGBA', (W, panel_bottom - panel_top), (0, 0, 0, 100))
    img.paste(panel, (0, panel_top), panel)
    d = ImageDraw.Draw(img)

    title = news.get('title', '')[:200]
    title_lines = wrap_text(title, fonts['title'], W - 80, d)[:5]
    for line in title_lines:
        # Outline for readability
        for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['title'])
        d.text((40, y), line, fill=TEXT_W, font=fonts['title'])
        y += 65

    # Summary
    y += 30
    summary = news.get('summary', '')[:400]
    if summary:
        for line in wrap_text(summary, fonts['body'], W - 80, d)[:6]:
            for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['body'])
            d.text((40, y), line, fill=MUTED, font=fonts['body'])
            y += 45

    # Source
    y += 20
    source = news.get('source', '')[:50]
    if source:
        d.text((40, y), 'Источник: ' + source, fill=SCIO_BLUE, font=fonts['small'])

    # Footer
    foot_y = H - 350
    d.rectangle([0, foot_y, W, H], fill=FOOT_BG)
    d.rectangle([0, foot_y, W, foot_y + 2], fill=cc['c'])
    y = foot_y + 30
    d.text((40, y), NEWS_URL.replace('https://', ''), fill=SCIO_BLUE, font=fonts['body'])
    y += 50
    d.text((40, y), '@ALTHEA_Research_Briefbot', fill=TEXT_W, font=fonts['body'])
    y += 50
    tags = cc['tag'].split(' ')[:4]
    d.text((40, y), ' '.join(tags), fill=MUTED, font=fonts['small'])
    y += 40
    pub_date = (news.get('published_at', '') or '')[:10]
    if pub_date:
        d.text((40, y), pub_date, fill=FAINT, font=fonts['mono'])

    img.save(out_path, 'PNG')
    log(f'Variant A frame: {out_path}')


# ============================================================
# FRAME GENERATION — Variant C (animated bg, no photo)
# ============================================================

def make_frame_c(news, out_path):
    """Variant C: Pure animated background — gradient + pulsing dots + grid."""
    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    fonts = load_fonts()

    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])

    # Radial gradient background (dark center → category color at edges)
    cx, cy = W // 2, H // 3
    max_r = int(math.sqrt(W**2 + H**2) / 2)
    for r in range(max_r, 0, -10):
        # Interpolate from category color (edge) to BG (center)
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

    # Pulsing dots (AMAGI-style network nodes)
    import random
    random.seed(42)  # Deterministic
    nodes = [
        (200, 400, AMBER),
        (880, 500, SCIO_BLUE),
        (540, 700, ALTHEA_GREEN),
        (180, 1000, CTC_PURPLE),
        (900, 1100, AMBER),
        (540, 1300, SCIO_BLUE),
    ]
    for nx, ny, nc in nodes:
        # Outer glow
        for r, alpha in [(40, 20), (28, 40), (18, 80)]:
            glow = Image.new('RGBA', (r*2, r*2), nc + (alpha,))
            img.paste(glow, (nx-r, ny-r), glow)
        # Core
        d.ellipse([nx-6, ny-6, nx+6, ny+6], fill=nc)
    d = ImageDraw.Draw(img)

    # Connecting lines
    for i, (x1, y1, _) in enumerate(nodes):
        for j, (x2, y2, _) in enumerate(nodes):
            if i < j and abs(i-j) <= 2:
                d.line([(x1, y1), (x2, y2)], fill=(40, 60, 100), width=1)

    # Header bar
    d.rectangle([0, 0, W, 100], fill=cc['c'])
    d.text((40, 25), 'ALTHEA Research Brief', fill=BG, font=fonts['header'])
    d.text((W - 80, 30), cc['e'], fill=BG, font=fonts['header'])

    # Slogan
    d.text((40, 130), SLOGAN, fill=cc['c'], font=fonts['slogan'])
    d.text((40, 210), cc['l'], fill=cc['c'], font=fonts['header'])

    # Title (white, on top of grid)
    y = 290
    title = news.get('title', '')[:200]
    title_lines = wrap_text(title, fonts['title'], W - 80, d)[:5]
    for line in title_lines:
        for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['title'])
        d.text((40, y), line, fill=TEXT_W, font=fonts['title'])
        y += 65

    # Summary
    y += 30
    summary = news.get('summary', '')[:400]
    if summary:
        for line in wrap_text(summary, fonts['body'], W - 80, d)[:6]:
            for ox, oy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                d.text((40+ox, y+oy), line, fill=(0,0,0), font=fonts['body'])
            d.text((40, y), line, fill=MUTED, font=fonts['body'])
            y += 45

    # Source
    y += 20
    source = news.get('source', '')[:50]
    if source:
        d.text((40, y), 'Источник: ' + source, fill=SCIO_BLUE, font=fonts['small'])

    # Footer
    foot_y = H - 350
    d.rectangle([0, foot_y, W, H], fill=FOOT_BG)
    d.rectangle([0, foot_y, W, foot_y + 2], fill=cc['c'])
    y = foot_y + 30
    d.text((40, y), NEWS_URL.replace('https://', ''), fill=SCIO_BLUE, font=fonts['body'])
    y += 50
    d.text((40, y), '@ALTHEA_Research_Briefbot', fill=TEXT_W, font=fonts['body'])
    y += 50
    tags = cc['tag'].split(' ')[:4]
    d.text((40, y), ' '.join(tags), fill=MUTED, font=fonts['small'])
    y += 40
    pub_date = (news.get('published_at', '') or '')[:10]
    if pub_date:
        d.text((40, y), pub_date, fill=FAINT, font=fonts['mono'])

    img.save(out_path, 'PNG')
    log(f'Variant C frame: {out_path}')


# ============================================================
# VIDEO ASSEMBLY with Ken Burns + animated progress bar
# ============================================================

def make_video_animated(img_path, audio_path, out_path, music_path=None, variant='A'):
    """
    Assemble MP4 with:
    - Ken Burns zoom effect on background image (1.0 → 1.15)
    - Animated progress bar (FFmpeg drawbox)
    - Optional background music mixed at -22dB
    """
    duration = get_audio_duration(audio_path)
    total_duration = duration + 1.0
    log(f'[{variant}] Audio: {duration:.2f}s, total: {total_duration:.2f}s')

    fps = 30
    total_frames = int(total_duration * fps)

    # Video filter chain: scale → zoompan (Ken Burns) → progress bar
    zoom_expr = f"1+0.15*on/{total_frames}"
    vf = (
        f"scale=2160:3840:flags=lanczos,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:s=1080x1920:fps={fps},"
        f"format=yuv420p,"
        f"drawbox=x=40:y=1850:w=1000:h=8:color=black@0.5:t=fill,"
        f"drawbox=x=40:y=1850:w='1000*t/{total_duration}':h=8:color=0x{AMBER[0]:02x}{AMBER[1]:02x}{AMBER[2]:02x}@0.9:t=fill"
    )

    # Verify music file is valid before using it
    use_music = music_path and os.path.exists(music_path) and os.path.getsize(music_path) > 1000

    if use_music:
        # Mix TTS with ambient music (music at 6% volume = -24dB)
        # Use filter_complex with labeled streams
        fc = (
            f"[0:v]{vf}[v];"  # video with Ken Burns + progress bar
            f"[1:a]volume=1.0[voice];"
            f"[2:a]volume=0.06,afade=t=in:st=0:d=1,afade=t=out:st={max(0, duration-1):.2f}:d=1[music];"
            f"[voice][music]amix=inputs=2:duration=first[a]"
        )
        cmd = [
            FFMPEG, '-y',
            '-loop', '1', '-i', img_path,
            '-i', audio_path,
            '-i', music_path,
            '-filter_complex', fc,
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-t', str(total_duration),
            '-movflags', '+faststart',
            out_path
        ]
    else:
        # No music — apply video filter directly, map TTS audio as-is
        cmd = [
            FFMPEG, '-y',
            '-loop', '1', '-i', img_path,
            '-i', audio_path,
            '-vf', vf,
            '-map', '0:v', '-map', '1:a',
            '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-t', str(total_duration),
            '-shortest', '-movflags', '+faststart',
            out_path
        ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            size = os.path.getsize(out_path)
            log(f'[{variant}] Video: {out_path} ({size} bytes, {total_duration:.1f}s)')
            return True
        else:
            log(f'[{variant}] FFmpeg error: {r.stderr[-400:]}')
            return False
    except Exception as e:
        log(f'[{variant}] FFmpeg exception: {e}')
        return False


# ============================================================
# Generate ambient music (synth, royalty-free)
# ============================================================

def generate_ambient_music(out_path, duration=35, cat_color=AMBER):
    """Generate a simple ambient pad via FFmpeg sine + filters. Output as .m4a (AAC)."""
    # Use .m4a extension for AAC
    if out_path.endswith('.mp3'):
        out_path = out_path[:-4] + '.m4a'
    base_freq = 110 + (cat_color[0] % 50)  # 110-160 Hz
    cmd = [
        FFMPEG, '-y',
        '-f', 'lavfi', '-i', f'sine=frequency={base_freq}:duration={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency={base_freq*1.5}:duration={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency={base_freq*2}:duration={duration}',
        '-filter_complex',
        f'[0:a]volume=0.5[a1];[1:a]volume=0.3[a2];[2:a]volume=0.2[a3];'
        f'[a1][a2][a3]amix=inputs=3,'
        f'lowpass=f=400,highpass=f=80,'
        f'afade=t=in:st=0:d=2,afade=t=out:st={max(0, duration-2)}:d=2,'
        f'aecho=0.8:0.7:60:0.4',
        '-c:a', 'aac', '-b:a', '96k',
        out_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            log(f'Music generated: {out_path}')
            return out_path  # Return possibly-renamed path
        log(f'Music gen error: {r.stderr[-300:]}')
        return None
    except Exception as e:
        log(f'Music gen exception: {e}')
        return None


# ============================================================
# MAIN
# ============================================================

def main():
    log('=' * 60)
    log('YouTube Shorts v3 — 3 variants demo')

    # Use specific news for fair comparison
    news_id = sys.argv[1] if len(sys.argv) > 1 else '267'
    news = fetch_specific_news(news_id)
    if not news:
        log(f'Cannot fetch news id={news_id}')
        return 1

    nid = news.get('id')
    log(f'News: [{nid}] {news.get("title", "")[:80]}')
    log(f'Category: {news.get("category")}, image: {news.get("image_url", "none")}')

    # Generate TTS (shared across all 3 variants)
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{nid}.mp3')
    speech = build_speech(news)
    if not make_tts(speech, audio_path):
        return 1

    # Download photo if available
    photo_path = os.path.join(OUTPUT_DIR, f'photo_{nid}.jpg')
    if news.get('image_url'):
        download_image(news['image_url'], photo_path)
    else:
        photo_path = None

    # Generate ambient music
    cat = news.get('category', 'industry')
    cc = CATS.get(cat, CATS['industry'])
    music_path = os.path.join(OUTPUT_DIR, f'music_{nid}.m4a')
    actual_music_path = generate_ambient_music(music_path, duration=40, cat_color=cc['c'])
    if actual_music_path:
        music_path = actual_music_path
    else:
        music_path = None

    # === VARIANT A: Photo + Ken Burns + animated text ===
    log('--- Generating Variant A (photo + Ken Burns) ---')
    frame_a = os.path.join(OUTPUT_DIR, f'frame_a_{nid}.png')
    make_frame_a(news, photo_path, frame_a)
    video_a = os.path.join(OUTPUT_DIR, f'variantA_{nid}.mp4')
    make_video_animated(frame_a, audio_path, video_a, music_path=None, variant='A')

    # === VARIANT B: Photo + Ken Burns + ambient music ===
    log('--- Generating Variant B (photo + Ken Burns + music) ---')
    video_b = os.path.join(OUTPUT_DIR, f'variantB_{nid}.mp4')
    make_video_animated(frame_a, audio_path, video_b, music_path=music_path, variant='B')

    # === VARIANT C: Animated bg (no photo) + Ken Burns + music ===
    log('--- Generating Variant C (animated bg + music) ---')
    frame_c = os.path.join(OUTPUT_DIR, f'frame_c_{nid}.png')
    make_frame_c(news, frame_c)
    video_c = os.path.join(OUTPUT_DIR, f'variantC_{nid}.mp4')
    make_video_animated(frame_c, audio_path, video_c, music_path=music_path, variant='C')

    log('=' * 60)
    log('DONE — 3 variants generated:')
    log(f'  A: {video_a}')
    log(f'  B: {video_b}')
    log(f'  C: {video_c}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
