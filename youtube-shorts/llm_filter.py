#!/usr/bin/env python3
"""
llm_filter.py — LLM-powered news filter for ALTHEA YouTube Shorts

Uses SambaNova Meta-Llama-3.3-70B-Instruct (free, RF-friendly) to:
1. Score each news item for relevance to ALTHEA deep-tech topics
2. Score YouTube Shorts appeal (general audience interest)
3. Pick the single most engaging news for video generation

Why LLM filtering:
- Site API returns ~30 news items per fetch
- Many are technical details or version releases (boring for Shorts)
- LLM selects the most "story-worthy" item — improves retention

Cost: $0 (SambaNova free tier, 10 RPM, ~1 call per filter batch)
Latency: ~1-2s per news item, parallelizable
"""
import os
import json
import urllib.request
import urllib.error
import time
from typing import List, Dict, Optional

# ============================================================
# CONFIG
# ============================================================

SAMBA_KEY = os.environ.get('SAMBA_KEY', '')
SAMBA_URL = 'https://api.sambanova.ai/v1/chat/completions'
SAMBA_MODEL = 'Meta-Llama-3.3-70B-Instruct'

# Categories that match site convention
VALID_CATEGORIES = ['amagi', 'althea', 'scio', 'ctc', 'industry', 'publication']

# Topics ALTHEA cares about (for relevance scoring)
ALTHEA_TOPICS = [
    'AI safety / AI alignment / AI reliability',
    'Hardware security / FPGA / ASIC / TEE',
    'CRISPR / bioengineering / precision oncology',
    'Deepfake detection / media forensics',
    'AI therapy coordination / clinical decision support',
    'EU AI Act / NIST AI RMF / AI regulation',
    'Functional safety (IEC 61508, ISO 26262)',
    'LLM / large language models / foundation models',
    'Quantum computing / cryptography',
    'Robotics / autonomous systems / safety-critical',
]


# ============================================================
# LOGGING
# ============================================================

def log(msg):
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = '[%s] [LLM] %s' % (ts, msg)
    print(line, flush=True)


# ============================================================
# SAMBANOVA API CALL
# ============================================================

def call_sambanova(system_prompt: str, user_prompt: str, max_tokens: int = 300, temperature: float = 0.2) -> Optional[str]:
    """Call SambaNova chat completions API with retry on 429. Returns text response or None."""
    if not SAMBA_KEY:
        log('No SAMBA_KEY env var — LLM filter disabled')
        return None

    payload = {
        'model': SAMBA_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'max_tokens': max_tokens,
        'temperature': temperature,
        'top_p': 0.9
    }

    # Retry with exponential backoff for 429 (rate limit)
    max_retries = 3
    base_delay = 6  # seconds — SambaNova rate limit window is ~1 min

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                SAMBA_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': 'Bearer ' + SAMBA_KEY,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode('utf-8'))
            return data['choices'][0]['message']['content'].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                delay = base_delay * (attempt + 1)
                log(f'SambaNova 429 rate limit — retry {attempt+1}/{max_retries} after {delay}s')
                time.sleep(delay)
                continue
            body = e.read().decode('utf-8')[:200] if e.fp else ''
            log(f'SambaNova HTTP {e.code}: {body}')
            return None
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (attempt + 1)
                log(f'SambaNova error ({e}) — retry {attempt+1}/{max_retries} after {delay}s')
                time.sleep(delay)
                continue
            log(f'SambaNova error: {e}')
            return None

    return None


# ============================================================
# SCORE SINGLE NEWS ITEM
# ============================================================

SCORE_SYSTEM_PROMPT = """You are an editorial AI for ALTHEA Research Brief — a deep-tech YouTube Shorts channel.

Your task: evaluate ONE news item for two criteria:
1. RELEVANCE (1-10): How closely does this match ALTHEA topics?
   - 10: Direct match (AI safety, CRISPR, deepfake, hardware security, AI regulation)
   - 7-9: Adjacent (LLM advances, bioinformatics, cybersecurity, functional safety)
   - 4-6: General tech with deep-tech angle (cloud, devops, ML ops)
   - 1-3: Unrelated (lifestyle, politics, sports, entertainment)

2. YOUTUBE APPEAL (1-10): How interesting for general tech audience?
   - 10: Breakthrough / controversy / "wow" factor
   - 7-9: Concrete product/release with broad impact
   - 4-6: Useful but niche
   - 1-3: Minor version bump, dry technical detail

ALTHEA topics:
- AI safety, alignment, reliability
- Hardware security (FPGA, ASIC, TEE)
- CRISPR, bioengineering, precision oncology
- Deepfake detection, media forensics
- AI therapy coordination
- EU AI Act, NIST AI RMF, AI regulation
- Functional safety (IEC 61508, ISO 26262)
- LLM, foundation models
- Quantum computing, cryptography
- Robotics, autonomous systems

Respond in STRICT JSON format only:
{
  "relevance": <int 1-10>,
  "appeal": <int 1-10>,
  "category": "<amagi|althea|scio|ctc|industry|publication>",
  "reason": "<one short sentence in Russian explaining why this is/isn't good for Shorts>"
}

Categories:
- amagi: AI safety / hardware security
- althea: bioengineering / CRISPR
- scio: deepfake detection / media forensics
- ctc: AI therapy coordination / medical AI
- industry: general deep-tech industry news
- publication: research paper / scientific publication"""


def score_news(news: Dict) -> Optional[Dict]:
    """Score single news item. Returns dict with relevance/appeal/category/reason or None."""
    title = (news.get('title') or '')[:200]
    summary = (news.get('summary') or '')[:400]
    source = news.get('source', '')
    current_cat = news.get('category', 'industry')

    user_prompt = f"""Evaluate this news item for ALTHEA YouTube Shorts:

Title: {title}
Summary: {summary}
Source: {source}
Current category: {current_cat}

Return JSON only."""

    response = call_sambanova(SCORE_SYSTEM_PROMPT, user_prompt, max_tokens=200, temperature=0.1)
    if not response:
        return None

    # Parse JSON from response (LLM may add markdown fences)
    text = response.strip()
    if text.startswith('```'):
        # Remove ```json or ``` fences
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

    try:
        result = json.loads(text)
        # Validate
        if not all(k in result for k in ['relevance', 'appeal', 'category', 'reason']):
            log(f'LLM response missing fields: {result}')
            return None
        # Clamp scores to 1-10
        result['relevance'] = max(1, min(10, int(result['relevance'])))
        result['appeal'] = max(1, min(10, int(result['appeal'])))
        # Validate category
        if result['category'] not in VALID_CATEGORIES:
            result['category'] = current_cat or 'industry'
        return result
    except json.JSONDecodeError as e:
        log(f'LLM JSON parse error: {e}, response: {response[:200]}')
        return None
    except Exception as e:
        log(f'LLM parse exception: {e}')
        return None


# ============================================================
# FILTER: pick best news from list
# ============================================================

def filter_best_news(news_list: List[Dict], min_relevance: int = 5, min_appeal: int = 5) -> Optional[Dict]:
    """
    Score all news items in a SINGLE LLM call (batch mode) and return the best one.
    This avoids hitting SambaNova rate limits (10 RPM free tier).

    Uses one LLM call to score all news at once, then picks the top-scored.
    """
    if not news_list:
        log('Empty news list')
        return None

    if not SAMBA_KEY:
        log('No SAMBA_KEY — returning first news item (no LLM filter)')
        return news_list[0]

    # === BATCH MODE: single LLM call for all news ===
    log(f'Batch-scoring {len(news_list)} news items via SambaNova (single call)...')

    # Build compact news list for LLM
    news_for_llm = []
    for i, n in enumerate(news_list):
        news_for_llm.append({
            'i': i,
            't': (n.get('title') or '')[:120],
            's': (n.get('summary') or '')[:200],
            'c': n.get('category', 'industry'),
        })

    system_prompt = """Ты — редактор YouTube Shorts канала ALTHEA Research Brief (deep-tech: AI safety, биоинженерия, deepfake-детекция, регуляторика).

Задача: оценить КАЖДУЮ новость по двум критериям:
1. RELEVANCE (1-10): соответствие deep-tech темам ALTHEA
   - 10: AI safety, CRISPR, deepfake, hardware security, AI regulation
   - 7-9: LLM advances, bioinformatics, cybersecurity, functional safety
   - 4-6: General tech with deep-tech angle
   - 1-3: Lifestyle, politics, sports, entertainment

2. APPEAL (1-10): интересность для YouTube Shorts (широкая техническая аудитория)
   - 10: прорыв / конфликт / "wow" фактор
   - 7-9: конкретный продукт с широким impact
   - 4-6: полезно, но niche
   - 1-3: minor version bump, dry technical detail

Категории ALTHEA:
- amagi: AI safety / hardware security / FPGA / ASIC
- althea: bioengineering / CRISPR / precision oncology
- scio: deepfake detection / media forensics
- ctc: AI therapy coordination / medical AI
- industry: general deep-tech industry news
- publication: research paper / scientific publication

Верни СТРОГО JSON массив (без markdown fences), каждый элемент:
{"i": <индекс>, "r": <relevance 1-10>, "a": <appeal 1-10>, "c": "<category>", "reason": "<одно предложение на русском>"}

Пример: [{"i":0,"r":8,"a":7,"c":"amagi","reason":"..."},{"i":1,"r":3,"a":2,"c":"industry","reason":"..."}]"""

    user_prompt = "Оцени все новости:\n\n" + json.dumps(news_for_llm, ensure_ascii=False, indent=2)

    response = call_sambanova(system_prompt, user_prompt, max_tokens=2000, temperature=0.2)
    if not response:
        log('LLM batch call failed — no response')
        return None

    # Parse JSON from response
    text = response.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

    try:
        results = json.loads(text)
    except json.JSONDecodeError as e:
        log(f'LLM JSON parse error: {e}')
        log(f'Response (first 500): {response[:500]}')
        return None

    if not isinstance(results, list):
        log(f'LLM returned non-list: {type(results)}')
        return None

    # Map back to news items
    scored = []
    for r in results:
        try:
            idx = int(r['i'])
            if idx < 0 or idx >= len(news_list):
                continue
            rel = max(1, min(10, int(r['r'])))
            app = max(1, min(10, int(r['a'])))
            cat = r.get('c', news_list[idx].get('category', 'industry'))
            if cat not in VALID_CATEGORIES:
                cat = news_list[idx].get('category', 'industry')
            total = rel + app
            log(f'  [{idx+1}] rel={rel}/10 app={app}/10 total={total} cat={cat} — {news_list[idx].get("title", "")[:50]}')
            if rel < min_relevance or app < min_appeal:
                log(f'      → below threshold, skipping')
                continue
            news_copy = dict(news_list[idx])
            news_copy['llm_score'] = total
            news_copy['llm_relevance'] = rel
            news_copy['llm_appeal'] = app
            news_copy['llm_category'] = cat
            news_copy['llm_reason'] = r.get('reason', '')
            news_copy['category'] = cat
            scored.append(news_copy)
        except (KeyError, ValueError, TypeError) as e:
            log(f'  Skip malformed entry: {e}')
            continue

    if not scored:
        log('No news passed LLM filter')
        return None

    scored.sort(key=lambda n: n['llm_score'], reverse=True)
    best = scored[0]
    log(f'✅ Best: score={best["llm_score"]} cat={best["llm_category"]}')
    log(f'   Title: {best.get("title", "")[:80]}')
    log(f'   Reason: {best.get("llm_reason", "")}')

    if len(scored) > 1:
        log('   Top-3:')
        for i, n in enumerate(scored[:3]):
            log(f'     {i+1}. [{n["llm_score"]}] {n.get("title", "")[:60]}')

    return best


# ============================================================
# MAIN (for testing)
# ============================================================

if __name__ == '__main__':
    import sys

    # Test: fetch 5 latest news from API and score them
    print('=== LLM Filter Test ===')
    if not SAMBA_KEY:
        # For local testing, allow passing key as arg
        if len(sys.argv) > 1:
            os.environ['SAMBA_KEY'] = sys.argv[1]
            SAMBA_KEY = sys.argv[1]
        else:
            print('Usage: python llm_filter.py [SAMBA_KEY]')
            print('  or set SAMBA_KEY env var')
            sys.exit(1)

    # Fetch news
    API_URL = 'https://althea-tech.ru/assets/api/content.php?action=news&limit=10'
    print(f'Fetching news from {API_URL}...')
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'AmagiLLMFilter/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        news_list = data.get('data', [])
        print(f'Got {len(news_list)} news items')
    except Exception as e:
        print(f'API error: {e}')
        sys.exit(1)

    # Filter
    best = filter_best_news(news_list, min_relevance=4, min_appeal=4)
    if best:
        print()
        print('=== WINNER ===')
        print(f'ID: {best.get("id")}')
        print(f'Title: {best.get("title")}')
        print(f'Category (LLM): {best.get("llm_category")}')
        print(f'Score: rel={best.get("llm_relevance")}/10 appeal={best.get("llm_appeal")}/10 total={best.get("llm_score")}/20')
        print(f'Reason: {best.get("llm_reason")}')
    else:
        print('No suitable news found')
