# ALTHEA YouTube Shorts Generator

Automated pipeline for generating branded YouTube Shorts from ALTHEA Research Brief news.

**Channel**: [@ALTHEAResearchBrief](https://www.youtube.com/@ALTHEAResearchBrief)
**Schedule**: every 4 hours via GitHub Actions
**Cost**: $0 (edge-tts free, GitHub Actions free tier, YouTube Data API free quota, SambaNova LLM free tier)

---

## Architecture

```
GitHub Actions (Ubuntu runner, cron every 4h)
    ↓
1. Fetch fresh news from althea-tech.ru API (20 latest)
2. LLM filter via SambaNova Meta-Llama-3.3-70B:
   - Score each news: relevance + YouTube appeal
   - Pick top-1 most interesting for Shorts
3. Generate branded PNG frame (1080x1920) via Pillow
4. Text-to-speech via edge-tts (Microsoft Neural, ru-RU-DmitryNeural)
5. Assemble MP4 via FFmpeg (libx264 + AAC, Ken Burns + progress bar)
6. Upload to YouTube (if YOUTUBE_REFRESH_TOKEN configured)
7. Mark news as processed (state file)
```

**No load on the production server** — all work happens in GitHub Actions runner.

---

## Files

| File | Purpose |
|---|---|
| `youtube_shorts.py` | Main pipeline script |
| `requirements.txt` | Python dependencies |
| `.github/workflows/shorts.yml` | GitHub Actions cron job |
| `output/` | Generated videos (gitignored) |
| `.processed_ids.json` | State: which news IDs already processed |

---

## Local Testing

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Make sure ffmpeg is installed
#    Debian/Ubuntu: sudo apt install ffmpeg
#    macOS: brew install ffmpeg

# 3. Run
python youtube_shorts.py
```

The script will:
1. Fetch the latest news from `https://althea-tech.ru/assets/api/content.php`
2. Generate `output/shorts_<id>_<timestamp>.mp4`
3. Skip if YouTube credentials are not set (local mode)

---

## YouTube Upload Setup (Optional)

To enable automatic YouTube uploads, set these repository secrets:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `YOUTUBE_CLIENT_ID` | From Google Cloud Console OAuth client |
| `YOUTUBE_CLIENT_SECRET` | From Google Cloud Console OAuth client |
| `YOUTUBE_REFRESH_TOKEN` | Obtained via one-time OAuth flow |

### Getting `YOUTUBE_REFRESH_TOKEN`

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3**
3. Create OAuth 2.0 Client ID (Desktop app type)
4. Download `client_secret.json`
5. Run this one-time script:
   ```bash
   pip install google-auth-oauthlib
   python -c "
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_secrets_file('client_secret.json',
       scopes=['https://www.googleapis.com/auth/youtube.upload'])
   creds = flow.run_console()
   print('REFRESH_TOKEN:', creds.refresh_token)
   "
   ```
6. Copy the refresh token to GitHub secrets

---

## Branding

Each video includes:
- **Top header bar** — colored by category (AMAGI amber, ALTHEA green, Scio blue, CTC purple)
- **Slogan** — "АЛТЕЯ — Инженерия доверия"
- **Title + summary** — wrapped, Cyrillic-aware
- **Source attribution** — link to original
- **Footer** — site URL + Telegram bot + hashtags + date
- **Progress bar track** — at bottom (synced with audio duration)

---

## License

S-APL v2.0 / CC BY-NC 4.0 — see [LICENSE.md](../LICENSE.md) in repo root.

## Author

**Alexey M. Burlai** — [ORCID](https://orcid.org/0009-0001-4679-5967)
AGIAM Technologies Ltd / LLC "Althea"
