"""Voz.vn forum scraper — chuyên biệt cho diễn đàn Voz.

Chỉ tập trung scrape F33 ("Điểm báo") và các subforum Voz.
Tách riêng khỏi server.py để dễ maintain, test, và mở rộng.
"""

import re
from datetime import datetime, timezone, timedelta
from cloakbrowser import launch
from urllib.parse import urlparse

import json
import math
import random
import time
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "voz_classifier_config.json"

def _load_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

_CONFIG = _load_config()

# Vietnamese diacritics → ASCII mapping
_DIACRITIC_MAP = str.maketrans(
    "àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyydAAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD"
)

def _normalize_vi(text):
    """Strip Vietnamese diacritics, lowercase. For keyword matching."""
    if not text:
        return ""
    return text.translate(_DIACRITIC_MAP).lower()


def _word_match(kw, normalized_text):
    """Match keyword with proper word boundary handling.

    - Multi-word keywords (contain space): use substring match (kw in text)
    - Single-word keywords: split text into words and check exact match
    """
    if ' ' in kw:
        return kw in normalized_text
    return kw in normalized_text.split()


def _detect_source(url):
    """Detect Voz subforum from URL path."""
    path = urlparse(url).path
    patterns = _CONFIG["source"]["patterns"]
    for pattern, source_id in patterns.items():
        if pattern in path:
            return source_id
    return None


def _is_garbage_title(title):
    """Check if title matches blacklist keywords."""
    normalized = _normalize_vi(title)
    for bad in _CONFIG["classification"]["blacklist_title"]:
        if _word_match(bad, normalized):
            return True
    return False


def _topic_bonus(title):
    """Calculate keyword boost: strong=+1.0, medium=+0.5."""
    normalized = _normalize_vi(title)
    score = 0.0
    boost = _CONFIG["classification"]["keyword_boost"]
    if any(_word_match(kw, normalized) for kw in boost["strong"]):
        score += 1.0
    if any(_word_match(kw, normalized) for kw in boost["medium"]):
        score += 0.5
    return score


def _detect_topic(title):
    """Classify thread into a topic category based on keyword match count."""
    normalized = _normalize_vi(title)
    topics = _CONFIG["classification"]["topics"]
    best_topic = _CONFIG["classification"]["default_topic"]
    best_count = 0
    for topic, keywords in topics.items():
        count = sum(1 for kw in keywords if _word_match(kw, normalized))
        if count > best_count:
            best_count = count
            best_topic = topic
    return best_topic


def _source_bonus(source):
    """Look up source bonus weight from config. Returns 0 for unknown."""
    return _CONFIG["source"]["bonus"].get(source, 0.0)


def _calc_score(thread, source):
    """Calculate priority score using config weights. 6-component composite."""
    w = _CONFIG["scoring_weights"]

    replies_score = math.log10((thread.get("replies", 0) or 0) + 1) * w["replies"]
    views_score = math.log10((thread.get("views", 0) or 0) + 1) * w["views"]
    page_score = math.log10((thread.get("page_jump", 0) or 0) + 1) * w["page_count"]

    # Freshness: normalize from last_activity_at, 72h decay window
    last_activity = thread.get("last_activity_at", "")
    if last_activity:
        try:
            tz = timezone(timedelta(hours=7))
            parsed = datetime.fromisoformat(last_activity)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            now = datetime.now(tz)
            hours_ago = (now - parsed).total_seconds() / 3600
            freshness_score = max(0, 1 - hours_ago / 72) * w["freshness"]
        except (ValueError, TypeError):
            freshness_score = 0
    else:
        freshness_score = 0

    topic_score = _topic_bonus(thread.get("title", "")) * w["topic"]
    source_score = _source_bonus(source) * w["source"]

    return round(replies_score + views_score + page_score + freshness_score + topic_score + source_score, 4)


def _select_threads(threads):
    """Select top_hot + top_curated threads. Hot = top score. Curated = topic_bonus > 0, not in hot."""
    cfg = _CONFIG["selection"]
    sorted_by_score = sorted(threads, key=lambda t: t.get("score", 0), reverse=True)

    hot = sorted_by_score[:cfg["top_hot"]]
    hot_urls = {t.get("url") for t in hot}

    curated = [
        t for t in sorted_by_score
        if t.get("url") not in hot_urls and t.get("topic_bonus", 0) > 0
    ][:cfg["top_curated"]]

    merged = hot + curated
    return sorted(merged, key=lambda t: t.get("score", 0), reverse=True)


def _clean_html(html):
    """Strip blockquotes, images, scripts, links → plain text."""
    from html.parser import HTMLParser

    class Cleaner(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result = []
            self.skip_blockquote = 0
            self.skip_script_style = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.skip_script_style = True
            elif tag == "blockquote":
                self.skip_blockquote += 1
            elif tag == "img":
                pass  # skip images entirely

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                self.skip_script_style = False
            elif tag == "blockquote" and self.skip_blockquote > 0:
                self.skip_blockquote -= 1

        def handle_data(self, data):
            if self.skip_script_style or self.skip_blockquote > 0:
                return
            text = data.strip()
            if text:
                self.result.append(text)

    cleaner = Cleaner()
    cleaner.feed(html)
    text = " ".join(cleaner.result)
    # Normalize whitespace
    text = " ".join(text.split())
    # Remove lightbox placeholders
    text = re.sub(r'\{[^{}]*lightbox_[^{}]*\}', '', text, flags=re.IGNORECASE)
    return text.strip()


def _parse_posts(html, config=None):
    """Extract original post + comments from thread page HTML."""
    if config is None:
        config = _CONFIG
    sel = config["selection"]

    from html.parser import HTMLParser

    class BBExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.posts = []
            self._current_post = []
            self._in_target = False
            self._depth = 0
            self._tag_stack = []

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            cls = attrs_dict.get("class", "")
            self._tag_stack.append(tag)
            if "bbWrapper" in cls:
                self._in_target = True
                self._depth = len(self._tag_stack)
                self._current_post = []
            elif self._in_target:
                if tag == "br":
                    self._current_post.append(" ")

        def handle_endtag(self, tag):
            if self._tag_stack:
                self._tag_stack.pop()
            if self._in_target and len(self._tag_stack) < self._depth:
                self._in_target = False
                text = "".join(self._current_post).strip()
                text = " ".join(text.split())
                if text:
                    self.posts.append(text)

        def handle_data(self, data):
            if self._in_target:
                self._current_post.append(data)

    extractor = BBExtractor()
    extractor.feed(html)

    original_post = ""
    comments = []

    if extractor.posts:
        original_post = extractor.posts[0]
        if len(original_post) > sel["original_post_max_length"]:
            original_post = original_post[:sel["original_post_max_length"]].strip() + "..."

    for post in extractor.posts[1:]:
        if len(post.split()) < sel["min_words_per_comment"]:
            continue
        if len(post) > sel["max_comment_length"]:
            post = post[:sel["max_comment_length"]].strip() + "..."
        comments.append(post)

    return {"original_post": original_post, "comments": comments}


def _get_page_count(html):
    """Count pages from .pageNav-page links."""
    matches = re.findall(r'class="pageNav-page[^"]*"[^>]*>(\d+)<', html)
    if not matches:
        return 1
    return max(int(m) for m in matches)


def _fetch_thread_content(url):
    """Fetch page 1 + last page of a thread, extract posts."""
    from cloakbrowser import launch
    config = _CONFIG

    with launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    ) as browser:
        page = browser.new_page()

        # Page 1
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        html1 = page.content()
        max_page = _get_page_count(html1)
        parsed1 = _parse_posts(html1, config)

        # Last page (if applicable)
        parsed_last = {"original_post": "", "comments": []}
        if max_page > 1:
            last_url = url.rstrip('/') + '/page-' + str(max_page)
            page.goto(last_url, wait_until='domcontentloaded', timeout=30000)
            html_last = page.content()
            parsed_last = _parse_posts(html_last, config)

        page.close()

    # Merge: page 1 first N comments + last page last N comments
    sel = config["selection"]
    comments = (
        parsed1["comments"][:sel["max_first_page_comments"]] +
        parsed_last["comments"][-sel["max_last_page_comments"]:]
    )

    return {
        "page_count": max_page,
        "original_post": parsed1["original_post"] or parsed_last["original_post"],
        "comments": comments,
    }


# --- Helpers ---

def _parse_number(s: str) -> int:
    """Parse '1.2K', '3M', '456' → int."""
    if not s:
        return 0
    m = re.search(r'([\d.]+)\s*([KM])?', s, re.IGNORECASE)
    if not m:
        return 0
    num = float(m.group(1))
    suffix = m.group(2)
    if suffix:
        num = num * 1000 if suffix.upper() == 'K' else num * 1000000
    return int(num)


def _parse_timestamp(s: str) -> str:
    """Parse Voz relative/absolute time → ISO 8601 +07:00.

    Handles: '21 minutes ago', 'Yesterday at 6:48 PM', 'May 20, 2026'.
    """
    now = datetime.now(timezone(timedelta(hours=7)))
    s = s.strip()

    if 'ago' in s:
        num_match = re.search(r'\d+', s)
        num = int(num_match.group()) if num_match else 0
        if 'minute' in s:
            return (now - timedelta(minutes=num)).strftime('%Y-%m-%dT%H:%M:%S+07:00')
        if 'hour' in s:
            return (now - timedelta(hours=num)).strftime('%Y-%m-%dT%H:%M:%S+07:00')
        if 'day' in s:
            return (now - timedelta(days=num)).strftime('%Y-%m-%dT%H:%M:%S+07:00')

    if 'Yesterday' in s:
        parts = s.replace('Yesterday at ', '').strip()
        try:
            t = datetime.strptime(parts, '%I:%M %p')
            yesterday = now - timedelta(days=1)
            return yesterday.replace(hour=t.hour, minute=t.minute, second=0).strftime('%Y-%m-%dT%H:%M:%S+07:00')
        except ValueError:
            pass

    # 'May 20, 2026' format
    try:
        dt = datetime.strptime(s, '%b %d, %Y')
        return dt.replace(year=now.year, tzinfo=timezone(timedelta(hours=7))).strftime('%Y-%m-%dT%H:%M:%S+07:00')
    except ValueError:
        pass

    return now.strftime('%Y-%m-%dT%H:%M:%S+07:00')


def _extract_thread_id(url: str) -> str:
    """Extract numeric thread ID from Voz URL."""
    m = re.search(r'\.([0-9]+)/', url)
    return m.group(1) if m else ''


# --- JS inject đoạn extract DOM ---

_INJECT_JS = """
    () => {
        const gt = (el) => el ? el.textContent.trim() : '';
        const items = document.querySelectorAll('.structItem');
        const threads = [];
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            const cells = item.querySelectorAll('.structItem-cell');
            const a = cells[1] ? cells[1].querySelector('a') : null;
            const cell2Text = cells[2] ? cells[2].textContent : '';
            const matches = cell2Text.match(/([\\d.]+)\\s*([KM])?/gi) || [];
            const lastActivity = cells[3] ? cells[3].querySelector('.structItem-lastPostTime') : null;
            const author = cells[3] ? cells[3].querySelector('.username') : null;
            const pageJumpLinks = item.querySelectorAll('.structItem-pageJump a');
            threads.push({
                title: gt(a),
                url: a ? a.href : '',
                replies: matches[0] || '',
                views: matches[1] || '',
                last_activity: gt(lastActivity),
                author: gt(author),
                is_pinned: item.querySelector('.structItem--pinned') != null,
                is_hot: item.querySelector('.structItem--hot') != null,
                page_jump: pageJumpLinks.length,
                tags: []
            });
        }
        return { threads: threads, forum_title: gt(document.querySelector('.p-title-value')) };
    }
"""


# --- Public API ---

def scrape_listing(url: str = 'https://voz.vn/f/diem-bao.33/') -> dict:
    """Scrape Voz forum listing page.

    Args:
        url: Voz forum listing URL.

    Returns:
        {
            'scanned_at': '...',
'source': 'voz_listing',
            'threads': [{thread_id, title, url, author, replies, views, last_activity_at, is_pinned, is_hot, tags_detected}]
        }
    """
    with launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    ) as browser:
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        raw_data = page.evaluate(_INJECT_JS)
        page.close()

    threads_out = []
    for t in raw_data.get('threads', []):
        threads_out.append({
            'thread_id': _extract_thread_id(t['url']),
            'title': t['title'],
            'url': t['url'],
            'author': t['author'],
            'replies': _parse_number(t['replies']),
            'views': _parse_number(t['views']),
            'last_activity_at': _parse_timestamp(t['last_activity']),
            'is_pinned': t['is_pinned'],
            'is_hot': t['is_hot'],
            'tags_detected': t['tags'],
        })

    return {
        'scanned_at': datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%dT%H:%M:%S+07:00'),
        'source': 'voz_listing',
        'threads': threads_out,
    }


def scan_and_classify(url):
    """Full pipeline: scan listing → score → select → fetch content → classify.

    Args:
        url: Voz forum listing URL (e.g. https://voz.vn/f/diem-bao.33/)

    Returns:
        {
            'scanned_at': '...',
            'source': 'voz_f33',
            'threads': [{thread_id, title, url, source, topic, replies, views, score, original_post, comments}]
        }
    """
    source = _detect_source(url)
    if source is None:
        raise ValueError(f"Unsupported URL: {url}")

    config = _CONFIG
    sel = config["selection"]

    # Step 1: Scan listing page
    with launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    ) as browser:
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        raw_data = page.evaluate(_INJECT_JS)
        page.close()

    # Step 2: Enrich + classify + score
    enriched = []
    for t in raw_data.get("threads", []):
        title = t.get("title", "")
        if _is_garbage_title(title):
            continue

        thread = {
            "thread_id": _extract_thread_id(t.get("url", "")),
            "title": title,
            "url": t.get("url", ""),
            "source": source,
            "topic": _detect_topic(title),
            "replies": _parse_number(t.get("replies", "")),
            "views": _parse_number(t.get("views", "")),
            "page_jump": t.get("page_jump", 0),
            "last_activity_at": _parse_timestamp(t.get("last_activity", "")),
            "topic_bonus": _topic_bonus(title),
        }
        thread["score"] = _calc_score(thread, source)
        enriched.append(thread)

    # Step 3: Select top threads
    selected = _select_threads(enriched)

    # Step 4: Fetch content for each thread (with delay)
    results = []
    for thread in selected:
        delay = random.uniform(sel["fetch_delay_min_ms"], sel["fetch_delay_max_ms"]) / 1000
        time.sleep(delay)

        try:
            content = _fetch_thread_content(thread["url"])
            results.append({
                "thread_id": thread["thread_id"],
                "title": thread["title"],
                "url": thread["url"],
                "source": thread["source"],
                "topic": thread["topic"],
                "replies": thread["replies"],
                "views": thread["views"],
                "score": thread["score"],
                "original_post": content["original_post"],
                "comments": content["comments"],
            })
        except Exception as e:
            import sys
            print(f"[VOZ] Failed to fetch {thread['url']}: {e}", file=sys.stderr)
            continue

    return {
        "scanned_at": datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S+07:00"),
        "source": source,
        "threads": results,
    }
