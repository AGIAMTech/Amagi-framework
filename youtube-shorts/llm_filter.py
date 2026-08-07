#!/usr/bin/env python3
"""
llm_filter.py v2.0 — LLM-powered news filter for ALTHEA YouTube Shorts

Uses OpenRouter free tier (NVIDIA Nemotron 3 Super 120B or similar) to:
1. Score each news item for relevance to ALTHEA deep-tech topics
2. Score YouTube Shorts appeal (general audience interest)
3. Pick the single most engaging news for video generation

Cost: $0 (OpenRouter free tier, 20 requests/day, 1 RPM)
Latency: ~10-15s per call (Nemotron is large but free)

Strategy:
- Batch mode: 1 LLM call for all 20 news (saves rate limit budget)
- Fallback chain: Nemotron → Gemma → gpt-oss → keyword filter (no LLM)
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

OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Model fallback chain (try in order — first that works wins)
# All are FREE on OpenRouter
LLM_MODELS = [
    'nvidia/nemotron-3-super-120b-a12b:free',  # 120B params, best quality
    'openai/gpt-oss-20b:free',                  # 20B, OpenAI quality
    'google/gemma-4-31b-it:free',               # 31B, Google quality
    'nvidia/nemotron-3-nano-30b-a3b:free',      # 30B, smaller/faster
]

# Categories that match site convention
VALID_CATEGORIES = ['amagi', 'althea', 'scio', 'ctc', 'industry', 'publication']


def log(msg):
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] [LLM] {msg}', flush=True)


# ============================================================
# OPENROUTER API CALL (with model fallback)
# ============================================================

def call_llm(system_prompt: str, user_prompt: str,
             max_tokens: int = 2000, temperature: float = 0.2) -> Optional[str]:
    """
    Call OpenRouter API with model fallback chain.
    Tries each model in LLM_MODELS until one succeeds.
    Returns text response or None.
    """
    if not OPENROUTER_KEY:
        log('No OPENROUTER_KEY env var — LLM filter disabled')
        return None

    payload = {
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'max_tokens': max_tokens,
        'temperature': temperature,
        'top_p': 0.9
    }

    last_error = None
    for model in LLM_MODELS:
        payload['model'] = model
        log(f'Trying model: {model}')

        # Single retry per model (not exponential — free tier limits)
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    OPENROUTER_URL,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Authorization': 'Bearer ' + OPENROUTER_KEY,
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://github.com/AGIAMTech/Amagi-framework',
                        'X-Title': 'ALTHEA YouTube Shorts'
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = json.loads(r.read().decode('utf-8'))

                if 'choices' in data and data['choices']:
                    content = data['choices'][0]['message']['content'].strip()
                    if content:
                        usage = data.get('usage', {})
                        log(f'  ✅ {model}: {len(content)} chars, '
                            f'tokens={usage.get("total_tokens", "?")}, '
                            f'cost=${usage.get("cost", 0)}')
                        return content
                    else:
                        log(f'  ⚠ {model}: empty response')
                        last_error = 'empty response'
                else:
                    log(f'  ⚠ {model}: no choices in response')
                    last_error = 'no choices'

            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8')[:300]
                if e.code == 429:
                    if attempt == 0:
                        log(f'  ⚠ {model}: rate limited, retrying in 5s...')
                        time.sleep(5)
                        continue
                    else:
                        log(f'  ⚠ {model}: rate limited after retry, trying next model')
                        last_error = f'429 {body[:100]}'
                        break  # try next model
                else:
                    log(f'  ❌ {model}: HTTP {e.code} {body[:200]}')
                    last_error = f'HTTP {e.code}'
                    break  # try next model
            except Exception as e:
                log(f'  ❌ {model}: {e}')
                last_error = str(e)
                break

    log(f'All models failed. Last error: {last_error}')
    return None


# ============================================================
# FILTER: pick best news from list (batch mode)
# ============================================================

def filter_best_news(news_list: List[Dict],
                     min_relevance: int = 5,
                     min_appeal: int = 5) -> Optional[Dict]:
    """
    Score all news items in a SINGLE LLM call (batch mode) and return the best one.
    Falls back to keyword filter if LLM unavailable.
    """
    if not news_list:
        log('Empty news list')
        return None

    if not OPENROUTER_KEY:
        log('No OPENROUTER_KEY — using keyword filter fallback')
        return keyword_filter_fallback(news_list)

    log(f'Batch-scoring {len(news_list)} news items via OpenRouter (single call)...')

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
1. RELEVANCE (r, 1-10): соответствие deep-tech темам ALTHEA
   - 10: AI safety, CRISPR, deepfake, hardware security, AI regulation
   - 7-9: LLM advances, bioinformatics, cybersecurity, functional safety
   - 4-6: General tech with deep-tech angle
   - 1-3: Lifestyle, politics, sports, entertainment

2. APPEAL (a, 1-10): интересность для YouTube Shorts (широкая техническая аудитория)
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

Верни СТРОГО JSON массив (без markdown fences, без пояснений), каждый элемент:
{"i": <индекс>, "r": <relevance 1-10>, "a": <appeal 1-10>, "c": "<category>", "reason": "<короткое предложение на русском>"}

ВАЖНО: верни массив для ВСЕХ новостей из входных данных."""

    user_prompt = "Оцени все новости:\n\n" + json.dumps(news_for_llm, ensure_ascii=False, indent=2)

    response = call_llm(system_prompt, user_prompt, max_tokens=3000, temperature=0.2)
    if not response:
        log('LLM batch call failed — using keyword filter fallback')
        return keyword_filter_fallback(news_list)

    # Parse JSON from response
    text = response.strip()
    # Remove markdown fences if present
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
    # Try to extract JSON array if there's extra text
    if not text.startswith('['):
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            text = text[start:end+1]

    try:
        results = json.loads(text)
    except json.JSONDecodeError as e:
        log(f'LLM JSON parse error: {e}')
        log(f'Response (first 500): {response[:500]}')
        return keyword_filter_fallback(news_list)

    if not isinstance(results, list):
        log(f'LLM returned non-list: {type(results)}')
        return keyword_filter_fallback(news_list)

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
# KEYWORD FILTER FALLBACK (no LLM, simple Python)
# ============================================================

# Keywords per category (same as site's fetch_news.php)
KEYWORDS = {
    'amagi': ['ии безопас', 'ai safety', 'hardware security', 'fpga', 'asic',
              'tee', 'trusted execution', 'ieck 61508', 'iso 26262',
              'safety-critical', 'формальн вериф', 'spin model'],
    'althea': ['crispr', 'биоинжен', 'gene therapy', 'онкол', 'fus',
               'gmp', 'ema atmp', 'fda cber', 'biomolec'],
    'scio': ['deepfake', 'медиа форензик', 'face detection', 'rppg',
             'voice clone', 'spectral analy', 'biometric'],
    'ctc': ['медицинск ии', 'medical ai', 'clinical decision', 'терапи ии',
            'ai therapy', 'диагност ии', 'федеративн обуч'],
    'publication': ['doi', 'zenodo', 'arxiv', 'ieee', 'frontiers',
                    'research paper', 'научн публика'],
    'industry': ['ии модел', 'технолог', 'ии-агент', 'llm', 'языков модел',
                 'machine learning', 'neural network', 'ai regulation',
                 'eu ai act', 'nist ai rmf', 'кибербез'],
}


def keyword_filter_fallback(news_list: List[Dict]) -> Optional[Dict]:
    """Simple keyword-based filter when LLM is unavailable."""
    log(f'Keyword filter on {len(news_list)} news')

    scored = []
    for n in news_list:
        text = ((n.get('title') or '') + ' ' + (n.get('summary') or '')).lower()
        best_cat = 'industry'
        best_score = 1  # default
        for cat, kws in KEYWORDS.items():
            score = sum(2 for kw in kws if kw in text)
            if score > best_score:
                best_score = score
                best_cat = cat
        if best_score >= 4:  # at least 2 keyword matches
            n_copy = dict(n)
            n_copy['llm_score'] = best_score
            n_copy['llm_relevance'] = min(10, best_score)
            n_copy['llm_appeal'] = 5  # default
            n_copy['llm_category'] = best_cat
            n_copy['llm_reason'] = 'Keyword filter (LLM unavailable)'
            n_copy['category'] = best_cat
            scored.append(n_copy)
            log(f'  [{n.get("id")}] score={best_score} cat={best_cat} — {n.get("title", "")[:50]}')

    if not scored:
        log('Keyword filter: no matches')
        return None

    scored.sort(key=lambda n: n['llm_score'], reverse=True)
    return scored[0]


# ============================================================
# LLM NARRATION: generate TTS script
# ============================================================

def generate_narration(news: Dict) -> Optional[str]:
    """Use LLM to write a natural narration script from news."""
    if not OPENROUTER_KEY:
        return None

    system_prompt = """Ты — редактор YouTube Shorts канала ALTHEA Research Brief.

ЗАДАЧА: написать текст для озвучки (narration) новости для Shorts.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1. Объём: СТРОГО 400-500 символов (это 30-40 секунд речи)
2. Русский язык, литературный стиль
3. НЕ используй английские слова, кроме: AI, CRISPR, deepfake, LLM, FPGA
4. НЕ пиши "Источник:", "Очки:", "URL:", "Подробнее:"
5. НЕ называй компании в первом предложении (звучит как реклама)
6. НЕ объясняй, что ты делаешь — просто верни готовый текст
7. НЕ используй markdown, кавычки, заголовки

СТРУКТУРА:
- 1-2 предложения: цепляющий факт или вопрос
- 2-3 предложения: техническая деталь
- 1 предложение: значимость
- Конец: "Подробнее на althea-tech.ru."

ПРИМЕР ХОРОШЕГО ОТВЕТА (не копируй, просто формат):
«Учёные доказали, что аппаратный заслон способен остановить неконтролируемое поведение ИИ. Шесть инвариантов архитектуры AMAGI проверены формальной верификацией SPIN на 25,9 миллиона состояний. Это означает, что критические системы от автопилота до медицинского оборудования теперь имеют математически доказанную защиту. Подробнее на althea-tech.ru.»

Верни ТОЛЬКО текст narration (без пояснений, без "Вот narration:", без markdown)."""

    title = (news.get('title') or '')[:200]
    summary = (news.get('summary') or '')[:500]
    source = news.get('source', '')
    cat = news.get('category', 'industry')

    user_prompt = f"""Категория: {cat}
Заголовок: {title}
Содержание: {summary}
Источник: {source}

Напиши narration (400-500 символов, на русском):"""

    response = call_llm(system_prompt, user_prompt, max_tokens=600, temperature=0.5)
    if not response:
        return None

    # Clean up
    text = response.strip()
    # Remove markdown fences
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
    # Strip common meta-prefixes LLMs add
    for prefix in ['Вот narration:', 'Narration:', 'Озвучка:', 'Текст:', 'Narration script:']:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    # Remove wrapping quotes
    text = text.strip('«»""\'')

    # If LLM ignored instructions (English meta-text), use fallback
    if any(phrase in text for phrase in ['need to produce', 'should write', 'rules:', 'rules =', 'I will', 'Let me']):
        log(f'LLM narration: meta-text detected, using fallback')
        return None

    # Ensure ends with site mention
    if 'althea-tech.ru' not in text:
        text += ' Подробнее на althea-tech.ru.'

    # Cap at 500 chars
    if len(text) > 500:
        text = text[:497] + '...'

    # Sanity check: if too short, LLM failed
    if len(text) < 100:
        log(f'LLM narration: too short ({len(text)} chars), using fallback')
        return None

    log(f'LLM narration ({len(text)} chars): {text[:100]}...')
    return text


# ============================================================
# MAIN (for testing)
# ============================================================

if __name__ == '__main__':
    import sys

    print('=== LLM Filter Test (OpenRouter) ===')
    if not OPENROUTER_KEY:
        if len(sys.argv) > 1:
            os.environ['OPENROUTER_KEY'] = sys.argv[1]
            OPENROUTER_KEY = sys.argv[1]
        else:
            print('Usage: python llm_filter.py [OPENROUTER_KEY]')
            print('  or set OPENROUTER_KEY env var')
            sys.exit(1)

    # Fetch news
    API_URL = 'https://althea-tech.ru/assets/api/content.php?action=news&limit=20'
    print(f'Fetching news from {API_URL}...')
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'AmagiLLMFilter/2.0'})
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

        # Test narration generation
        print()
        print('=== NARRATION ===')
        narration = generate_narration(best)
        if narration:
            print(narration)
    else:
        print('No suitable news found')
