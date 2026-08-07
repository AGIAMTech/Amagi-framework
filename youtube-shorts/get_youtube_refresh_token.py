#!/usr/bin/env python3
"""
get_youtube_refresh_token.py — one-time OAuth flow to get YOUTUBE_REFRESH_TOKEN

Run this script LOCALLY (not in GitHub Actions). It will:
1. Start a local HTTP server on port 8085
2. Open your browser to Google OAuth consent screen
3. You log in with your Google account (the one that owns @ALTHEAResearchBrief)
4. Google redirects back with an authorization code
5. Script exchanges code for refresh_token + access_token
6. Prints the refresh_token — copy it to GitHub Secrets as YOUTUBE_REFRESH_TOKEN

Prerequisites:
  pip install google-auth-oauthlib

Usage:
  python get_youtube_refresh_token.py

After getting the token:
  1. Copy the refresh_token (starts with "1//")
  2. Go to: https://github.com/AGIAMTech/Amagi-framework/settings/secrets/actions
  3. Add new secret: YOUTUBE_REFRESH_TOKEN = <paste token>
"""
import os
import json
import sys
import http.server
import threading
import urllib.parse
import webbrowser

# ============================================================
# CONFIG — read from environment variables (DO NOT hardcode secrets!)
# ============================================================

# Get credentials from env vars OR from client_secret.json file
CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET', '')
PROJECT_ID = os.environ.get('YOUTUBE_PROJECT_ID', 'quantum-ratio-504711-r9')

# If not in env, try reading from client_secret.json (local file, gitignored)
if not CLIENT_ID or not CLIENT_SECRET:
    client_secret_path = os.environ.get('CLIENT_SECRET_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_secret.json'))
    if os.path.exists(client_secret_path):
        with open(client_secret_path, 'r') as f:
            data = json.load(f)
        # Handle both "web" and "installed" (desktop) formats
        cred_type = 'web' if 'web' in data else 'installed'
        CLIENT_ID = data[cred_type]['client_id']
        CLIENT_SECRET = data[cred_type]['client_secret']
        PROJECT_ID = data[cred_type].get('project_id', PROJECT_ID)
        print(f'✅ Loaded credentials from {client_secret_path} (type: {cred_type})')

# OAuth scopes — YouTube upload permission
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Redirect URI — must match what's configured in Google Cloud Console
# For "Desktop" app type, use: http://localhost:PORT
# For "Web" app type, add http://localhost:8085 to authorized redirect URIs
REDIRECT_PORT = 8085
REDIRECT_URI = f'http://localhost:{REDIRECT_PORT}'

# State for CSRF protection
import secrets
STATE = secrets.token_urlsafe(16)


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    """Handle OAuth callback from Google."""
    auth_code = None
    error = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if 'error' in params:
            OAuthHandler.error = params['error'][0]
            self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f'<h1>❌ OAuth Error</h1><p>{OAuthHandler.error}</p>'.encode())
        elif 'code' in params:
            OAuthHandler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>OAuth Success</title>
<style>body{font-family:system-ui;background:#0b1424;color:#e9eef8;text-align:center;padding:60px}
h1{color:#f5a623;font-size:48px}p{font-size:20px;color:#a8b8d4}
.ok{color:#2dd4a7;font-size:120px}</style></head>
<body><div class="ok">✓</div><h1>Авторизация успешна!</h1>
<p>Вы можете закрыть эту вкладку.<br>Вернитесь к терминалу — там будет refresh_token.</p>
</body></html>''')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # Suppress default logging


def exchange_code_for_tokens(auth_code):
    """Exchange authorization code for refresh_token + access_token."""
    import urllib.request

    data = urllib.parse.urlencode({
        'code': auth_code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code',
    }).encode()

    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'❌ Token exchange failed: HTTP {e.code}')
        print(f'Response: {body}')
        return None
    except Exception as e:
        print(f'❌ Error: {e}')
        return None


def main():
    print('=' * 60)
    print('YouTube OAuth Flow — get refresh_token')
    print('=' * 60)
    print()

    if not CLIENT_ID or not CLIENT_SECRET:
        print('❌ No YouTube OAuth credentials found!')
        print()
        print('To fix, do ONE of:')
        print('  1. Set env vars:')
        print('     export YOUTUBE_CLIENT_ID="your-client-id"')
        print('     export YOUTUBE_CLIENT_SECRET="your-secret"')
        print()
        print('  2. Place client_secret.json next to this script')
        print('     (download from Google Cloud Console)')
        print()
        print('  3. Use CLIENT_SECRET_PATH env var:')
        print('     export CLIENT_SECRET_PATH="/path/to/client_secret.json"')
        return 1

    print(f'Project: {PROJECT_ID}')
    print(f'Client ID: {CLIENT_ID[:20]}...{CLIENT_ID[-10:]}')
    print(f'Redirect URI: {REDIRECT_URI}')
    print()

    # Check if google-auth-oauthlib is available (optional, for verification)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        print('✅ google-auth-oauthlib available')
    except ImportError:
        print('ℹ google-auth-oauthlib not installed (using stdlib HTTP server instead)')

    # Build OAuth URL
    auth_url = (
        'https://accounts.google.com/o/oauth2/auth'
        f'?response_type=code'
        f'&client_id={CLIENT_ID}'
        f'&redirect_uri={urllib.parse.quote(REDIRECT_URI)}'
        f'&scope={urllib.parse.quote(" ".join(SCOPES))}'
        f'&access_type=offline'  # CRITICAL: returns refresh_token
        f'&prompt=consent'        # Force consent to get new refresh_token
        f'&state={STATE}'
    )

    print()
    print('📋 Instructions:')
    print('  1. Browser will open to Google sign-in page')
    print('  2. Sign in with the Google account that owns @ALTHEAResearchBrief')
    print('  3. Consent to "Upload videos to your YouTube channel"')
    print('  4. You will be redirected back to localhost')
    print('  5. Refresh_token will appear here')
    print()
    print('⚠️  If browser does not open automatically, copy this URL:')
    print()
    print(auth_url)
    print()
    input('Press Enter to open browser...')

    # Try to open browser
    try:
        webbrowser.open(auth_url)
        print('✅ Browser opened')
    except:
        print('⚠️ Could not open browser automatically. Copy the URL above manually.')

    # Start local HTTP server to receive callback
    print(f'\nStarting local server on port {REDIRECT_PORT}...')
    server = http.server.HTTPServer(('localhost', REDIRECT_PORT), OAuthHandler)
    server.timeout = 300  # 5 min timeout

    print(f'Waiting for OAuth callback (up to 5 minutes)...')
    print()

    # Handle requests until we get the auth code
    while OAuthHandler.auth_code is None and OAuthHandler.error is None:
        server.handle_request()

    server.server_close()

    if OAuthHandler.error:
        print(f'\n❌ OAuth error: {OAuthHandler.error}')
        return 1

    if not OAuthHandler.auth_code:
        print('\n❌ No authorization code received (timeout)')
        return 1

    print('\n✅ Authorization code received!')
    print('Exchanging for refresh_token...')

    tokens = exchange_code_for_tokens(OAuthHandler.auth_code)
    if not tokens:
        return 1

    refresh_token = tokens.get('refresh_token')
    access_token = tokens.get('access_token')
    expires_in = tokens.get('expires_in')

    print()
    print('=' * 60)
    print('🎉 SUCCESS! Tokens received:')
    print('=' * 60)
    print()
    print(f'access_token: {access_token[:50]}...' if access_token else 'access_token: (none)')
    print(f'expires_in: {expires_in} seconds')
    print()
    if refresh_token:
        print('━' * 60)
        print('📋 YOUR REFRESH TOKEN (copy this):')
        print('━' * 60)
        print()
        print(refresh_token)
        print()
        print('━' * 60)
        print()
        print('NEXT STEPS:')
        print('1. Copy the refresh_token above (starts with "1//")')
        print('2. Go to: https://github.com/AGIAMTech/Amagi-framework/settings/secrets/actions')
        print('3. Click "New repository secret"')
        print('4. Name: YOUTUBE_REFRESH_TOKEN')
        print('5. Value: paste the refresh_token')
        print('6. Click "Add secret"')
        print()
        print('After this, GitHub Actions will auto-upload Shorts to @ALTHEAResearchBrief')
    else:
        print('⚠️  No refresh_token in response!')
        print('This happens if you already authorized this app before.')
        print('Solution: go to https://myaccount.google.com/permissions')
        print('Remove "AMAGI Shorts" (or whatever name) from authorized apps,')
        print('then run this script again — fresh consent will give new refresh_token.')
        print()
        print('Full response:')
        print(json.dumps(tokens, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
