# Voz Classifier Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port full scan→score→classify→extract pipeline from userscript JS to Python backend, config-driven via JSON.

**Architecture:** Monolithic — all new logic in `scrapers/voz.py`. Config in `scrapers/voz_classifier_config.json`. One new route `/scrape/voz/scan` in `server.py`. Pure functions (classification, scoring) are unit-testable. Browser-dependent functions (fetch, extract) tested via integration.

**Tech Stack:** Python 3, Flask, cloakbrowser, pytest

---

### Task 1: Create config file

**Files:**
- Create: `scrapers/voz_classifier_config.json`

- [ ] **Step 1: Write the config JSON**

```json
{
  "selection": {
    "top_hot": 4,
    "top_curated": 3,
    "min_words_per_comment": 5,
    "max_first_page_comments": 12,
    "max_last_page_comments": 10,
    "max_comment_length": 300,
    "original_post_max_length": 500,
    "min_replies_for_last_page": 30,
    "fetch_delay_min_ms": 1200,
    "fetch_delay_max_ms": 2200
  },
  "scoring_weights": {
    "replies": 0.38,
    "views": 0.20,
    "page_count": 0.12,
    "freshness": 0.15,
    "topic": 0.10,
    "source": 0.05
  },
  "source": {
    "patterns": {
      "/f/diem-bao.33": "voz_f33",
      "/f/lap-trinh-cntt.91": "voz_cntt",
      "/f/kinh-te-luat.92": "voz_ktl"
    },
    "bonus": {
      "voz_ktl": 1.0,
      "voz_cntt": 0.9,
      "voz_f33": 0.8
    }
  },
  "classification": {
    "blacklist_title": [
      "showbiz", "lo clip", "clip nong",
      "cuop", "giet", "hiep",
      "vo chong", "ngoai tinh", "danh ghen"
    ],
    "keyword_boost": {
      "strong": [
        "lai suat", "fed", "usd", "ty gia", "vang", "chung khoan", "etf",
        "ai", "tuyen dung", "layoff", "cloud", "dev", "backend", "frontend",
        "thue", "nghi dinh", "de xuat", "chi thi", "dien", "nang luong",
        "quy hoach", "ha tang", "xe dien"
      ],
      "medium": [
        "startup", "data", "iot", "smart grid", "pin",
        "bat dong san", "dau tu", "kinh te", "luat", "cong nghe"
      ]
    },
    "topics": {
      "macro_finance": ["lai suat", "fed", "usd", "ty gia", "vang", "chung khoan", "etf", "dau tu"],
      "tech_career": ["ai", "cloud", "dev", "backend", "frontend", "tuyen dung", "layoff", "data"],
      "energy": ["dien", "nang luong", "xe dien", "pin", "smart grid"],
      "policy_infra": ["quy hoach", "ha tang", "bat dong san", "de xuat", "nghi dinh", "thue"]
    },
    "default_topic": "general"
  }
}
```

- [ ] **Step 2: Validate JSON is well-formed**

Run: `python -c "import json; json.load(open('scrapers/voz_classifier_config.json', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scrapers/voz_classifier_config.json
git commit -m "feat: add voz classifier config JSON"
```

---

### Task 2: Add `_normalize_vi()` — strip Vietnamese diacritics

**Files:**
- Create: `tests/test_voz_classifier.py`
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for voz classifier — pure functions only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.voz import _normalize_vi


def test_normalize_vi_strips_diacritics():
    assert _normalize_vi("lãi suất") == "lai suat"
    assert _normalize_vi("điện") == "dien"
    assert _normalize_vi("Đề Xuất") == "de xuat"
    assert _normalize_vi("chứng khoán") == "chung khoan"


def test_normalize_vi_preserves_ascii():
    assert _normalize_vi("fed usd ai") == "fed usd ai"
    assert _normalize_vi("ETF 2024") == "etf 2024"


def test_normalize_vi_empty():
    assert _normalize_vi("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voz_classifier.py::test_normalize_vi_strips_diacritics -v`
Expected: `FAIL` — `ImportError` or `AttributeError: module 'scrapers.voz' has no attribute '_normalize_vi'`

- [ ] **Step 3: Implement `_normalize_vi()` and `_load_config()` in `scrapers/voz.py`**

Add these after existing imports (after line 10):

```python
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
```

- [ ] **Step 4: Run all normalize_vi tests to verify pass**

Run: `pytest tests/test_voz_classifier.py -v -k normalize`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/voz.py tests/test_voz_classifier.py
git commit -m "feat: add _normalize_vi() and _load_config()"
```

---

### Task 3: Add classification helpers

**Files:**
- Modify: `tests/test_voz_classifier.py`
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Write failing tests for all classification functions**

Append to `tests/test_voz_classifier.py`:

```python
from scrapers.voz import _detect_source, _is_garbage_title, _topic_bonus, _detect_topic, _source_bonus


class TestDetectSource:
    def test_detect_f33(self):
        assert _detect_source("https://voz.vn/f/diem-bao.33/page-2") == "voz_f33"

    def test_detect_cntt(self):
        assert _detect_source("https://voz.vn/f/lap-trinh-cntt.91/") == "voz_cntt"

    def test_detect_ktl(self):
        assert _detect_source("https://voz.vn/f/kinh-te-luat.92/") == "voz_ktl"

    def test_detect_unknown(self):
        assert _detect_source("https://voz.vn/f/random.99/") is None
        assert _detect_source("https://google.com") is None


class TestIsGarbageTitle:
    def test_garbage_detected(self):
        assert _is_garbage_title("Showbiz Việt: Lộ clip nóng") is True
        assert _is_garbage_title("Cướp ngân hàng ở SG") is True
        assert _is_garbage_title("Chuyện vợ chồng và ngoại tình") is True

    def test_clean_title_passes(self):
        assert _is_garbage_title("Fed giữ nguyên lãi suất") is False
        assert _is_garbage_title("Tuyển dụng dev backend") is False


class TestTopicBonus:
    def test_strong_keyword(self):
        assert _topic_bonus("Fed tăng lãi suất") == 1.0

    def test_medium_keyword(self):
        assert _topic_bonus("Startup Việt gọi vốn đầu tư") == 0.5

    def test_strong_and_medium(self):
        assert _topic_bonus("AI và data trong chứng khoán") == 1.5

    def test_no_match(self):
        assert _topic_bonus("Hôm nay trời đẹp") == 0.0


class TestDetectTopic:
    def test_macro_finance(self):
        assert _detect_topic("Fed giữ nguyên lãi suất, vàng tăng") == "macro_finance"

    def test_tech_career(self):
        assert _detect_topic("Tuyển dụng backend dev cho startup AI") == "tech_career"

    def test_energy(self):
        assert _detect_topic("Điện mặt trời và pin lưu trữ") == "energy"

    def test_policy_infra(self):
        assert _detect_topic("Nghị định mới về thuế bất động sản") == "policy_infra"

    def test_general(self):
        assert _detect_topic("Hôm nay ăn gì") == "general"


class TestSourceBonus:
    def test_ktl_max(self):
        assert _source_bonus("voz_ktl") == 1.0

    def test_cntt(self):
        assert _source_bonus("voz_cntt") == 0.9

    def test_f33(self):
        assert _source_bonus("voz_f33") == 0.8

    def test_unknown(self):
        assert _source_bonus("unknown") == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voz_classifier.py -v -k "TestDetectSource or TestIsGarbage or TestTopicBonus or TestDetectTopic or TestSourceBonus"`
Expected: All FAIL — functions not defined

- [ ] **Step 3: Implement classification functions in `scrapers/voz.py`**

Add after `_normalize_vi()`:

```python
def _detect_source(url):
    """Detect Voz subforum from URL path."""
    from urllib.parse import urlparse
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
        if bad in normalized:
            return True
    return False


def _topic_bonus(title):
    """Calculate keyword boost: strong=+1.0, medium=+0.5."""
    normalized = _normalize_vi(title)
    score = 0.0
    boost = _CONFIG["classification"]["keyword_boost"]
    for kw in boost["strong"]:
        if kw in normalized:
            score += 1.0
    for kw in boost["medium"]:
        if kw in normalized:
            score += 0.5
    return score


def _detect_topic(title):
    """Classify thread into a topic category based on keyword match count."""
    normalized = _normalize_vi(title)
    topics = _CONFIG["classification"]["topics"]
    best_topic = _CONFIG["classification"]["default_topic"]
    best_count = 0
    for topic, keywords in topics.items():
        count = sum(1 for kw in keywords if kw in normalized)
        if count > best_count:
            best_count = count
            best_topic = topic
    return best_topic


def _source_bonus(source):
    """Look up source bonus weight from config. Returns 0 for unknown."""
    return _CONFIG["source"]["bonus"].get(source, 0.0)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_voz_classifier.py -v -k "TestDetectSource or TestIsGarbage or TestTopicBonus or TestDetectTopic or TestSourceBonus"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/voz.py tests/test_voz_classifier.py
git commit -m "feat: add classification helpers — source, garbage, topic, bonus"
```

---

### Task 4: Add scoring functions

**Files:**
- Modify: `tests/test_voz_classifier.py`
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Write failing tests for `_calc_score` and `_select_threads`**

Append to `tests/test_voz_classifier.py`:

```python
from scrapers.voz import _calc_score, _select_threads


class TestCalcScore:
    def test_score_is_positive(self):
        thread = {
            "title": "Fed tăng lãi suất",
            "replies": 150,
            "views": 5000,
            "page_jump": 3,
            "last_activity_at": "2026-06-03T14:00:00+07:00",
        }
        score = _calc_score(thread, "voz_ktl")
        assert score > 0

    def test_higher_replies_higher_score(self):
        t1 = {"title": "A", "replies": 10, "views": 1000, "page_jump": 1,
              "last_activity_at": "2026-06-03T14:00:00+07:00"}
        t2 = {"title": "A", "replies": 100, "views": 1000, "page_jump": 1,
              "last_activity_at": "2026-06-03T14:00:00+07:00"}
        assert _calc_score(t2, "voz_f33") > _calc_score(t1, "voz_f33")

    def test_ktl_beats_f33_all_else_equal(self):
        thread = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                  "last_activity_at": "2026-06-03T14:00:00+07:00"}
        assert _calc_score(thread, "voz_ktl") > _calc_score(thread, "voz_f33")

    def test_old_thread_lower_freshness(self):
        t_new = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                 "last_activity_at": "2026-06-03T14:00:00+07:00"}
        t_old = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                 "last_activity_at": "2026-05-29T14:00:00+07:00"}  # 5 days ago
        assert _calc_score(t_new, "voz_f33") > _calc_score(t_old, "voz_f33")

    def test_missing_last_activity_defaults_to_zero_freshness(self):
        thread = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2}
        score = _calc_score(thread, "voz_f33")
        assert score > 0  # shouldn't crash


class TestSelectThreads:
    def test_selects_top_hot_and_curated(self):
        threads = [
            {"title": "Hot 1", "score": 5.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "Hot 2", "score": 4.0, "topic_bonus": 0.0, "url": "/t/2"},
            {"title": "Hot 3", "score": 3.0, "topic_bonus": 0.0, "url": "/t/3"},
            {"title": "Hot 4", "score": 2.0, "topic_bonus": 0.0, "url": "/t/4"},
            {"title": "Curated 1", "score": 1.5, "topic_bonus": 1.0, "url": "/t/5"},
            {"title": "Curated 2", "score": 1.0, "topic_bonus": 1.0, "url": "/t/6"},
            {"title": "Curated 3", "score": 0.8, "topic_bonus": 1.0, "url": "/t/7"},
            {"title": "Leftover", "score": 0.5, "topic_bonus": 1.0, "url": "/t/8"},
        ]
        result = _select_threads(threads)
        assert len(result) == 7
        urls = [t["url"] for t in result]
        assert "/t/1" in urls  # hot
        assert "/t/5" in urls  # curated
        assert "/t/8" not in urls  # left out

    def test_less_than_top_returns_all(self):
        threads = [
            {"title": "A", "score": 3.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "B", "score": 2.0, "topic_bonus": 1.0, "url": "/t/2"},
        ]
        result = _select_threads(threads)
        assert len(result) == 2

    def test_no_topic_bonus_returns_only_hot(self):
        threads = [
            {"title": "A", "score": 5.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "B", "score": 4.0, "topic_bonus": 0.0, "url": "/t/2"},
            {"title": "C", "score": 3.0, "topic_bonus": 0.0, "url": "/t/3"},
            {"title": "D", "score": 2.0, "topic_bonus": 0.0, "url": "/t/4"},
            {"title": "E", "score": 1.0, "topic_bonus": 0.0, "url": "/t/5"},
        ]
        result = _select_threads(threads)
        assert len(result) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voz_classifier.py -v -k "TestCalcScore or TestSelectThreads"`
Expected: All FAIL

- [ ] **Step 3: Implement `_calc_score` and `_select_threads` in `scrapers/voz.py`**

Add after classification functions:

```python
def _calc_score(thread, source):
    """Calculate priority score for a thread using config weights."""
    w = _CONFIG["scoring_weights"]
    cfg = _CONFIG["selection"]

    replies_score = math.log10((thread.get("replies", 0) or 0) + 1) * w["replies"]
    views_score = math.log10((thread.get("views", 0) or 0) + 1) * w["views"]
    page_score = math.log10((thread.get("page_jump", 0) or 0) + 1) * w["page_count"]

    # Freshness: normalize from last_activity_at, 72h decay window
    last_activity = thread.get("last_activity_at", "")
    if last_activity:
        try:
            from datetime import datetime, timezone, timedelta
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_voz_classifier.py -v -k "TestCalcScore or TestSelectThreads"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/voz.py tests/test_voz_classifier.py
git commit -m "feat: add scoring functions — _calc_score, _select_threads"
```

---

### Task 5: Extend `_INJECT_JS` with `page_jump`

**Files:**
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Replace `_INJECT_JS` to include `page_jump` field**

Replace the current `_INJECT_JS` (lines 73-100 in voz.py) with:

```python
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
```

The only change from current: added `const pageJumpLinks = item.querySelectorAll('.structItem-pageJump a');` and `page_jump: pageJumpLinks.length,` in the push object.

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `pytest tests/test_voz_classifier.py -v`
Expected: All existing tests still PASS

- [ ] **Step 3: Commit**

```bash
git add scrapers/voz.py
git commit -m "feat: extend _INJECT_JS with page_jump field"
```

---

### Task 6: Add content extraction functions

**Files:**
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Implement `_clean_html`, `_parse_posts`, `_get_page_count`**

Add after scoring functions in `scrapers/voz.py`:

```python
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
    import re
    text = re.sub(r'\{[^{}]*lightbox_[^{}]*\}', '', text, flags=re.IGNORECASE)
    return text.strip()


def _parse_posts(html, config=None):
    """Extract original post + comments from thread page HTML."""
    if config is None:
        config = _CONFIG
    sel = config["selection"]

    from html.parser import HTMLParser

    # Quick parse to find .bbWrapper content
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
                if tag in ("blockquote",):
                    pass  # skip blockquote content
                elif tag == "br":
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
    import re
    matches = re.findall(r'class="pageNav-page[^"]*"[^>]*>(\d+)<', html)
    if not matches:
        return 1
    return max(int(m) for m in matches)
```

- [ ] **Step 2: Verify import won't crash**

Run: `python -c "from scrapers.voz import _clean_html, _parse_posts, _get_page_count; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scrapers/voz.py
git commit -m "feat: add content extraction — _clean_html, _parse_posts, _get_page_count"
```

---

### Task 7: Add `_fetch_thread_content()` — browser-based

**Files:**
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Implement `_fetch_thread_content()`**

Add after `_get_page_count()`:

```python
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
```

- [ ] **Step 2: Verify import**

Run: `python -c "from scrapers.voz import _fetch_thread_content; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scrapers/voz.py
git commit -m "feat: add _fetch_thread_content() — headless browser thread fetch"
```

---

### Task 8: Add `scan_and_classify()` orchestrator

**Files:**
- Modify: `scrapers/voz.py`

- [ ] **Step 1: Implement `scan_and_classify()`**

Add after `_fetch_thread_content()` at end of `scrapers/voz.py`:

```python
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
    from datetime import datetime, timezone, timedelta

    source = _detect_source(url)
    if source is None:
        raise ValueError(f"Unsupported URL: {url}")

    config = _CONFIG
    sel = config["selection"]

    # Step 1: Scan listing page — reuse existing scrape_listing logic
    from cloakbrowser import launch
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
            # Skip failed threads, log warning
            import sys
            print(f"[VOZ] Failed to fetch {thread['url']}: {e}", file=sys.stderr)
            continue

    return {
        "scanned_at": datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S+07:00"),
        "source": source,
        "threads": results,
    }
```

- [ ] **Step 2: Verify import**

Run: `python -c "from scrapers.voz import scan_and_classify; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scrapers/voz.py
git commit -m "feat: add scan_and_classify() orchestrator"
```

---

### Task 9: Add route in server.py

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Update import at top of `server.py`**

Change line 3 from:
```python
from scrapers.voz import scrape_listing
```
to:
```python
from scrapers.voz import scrape_listing, scan_and_classify
```

- [ ] **Step 2: Add route after the existing `/scrape/voz/listing` route (after line 181)**

```python
# === Voz Scan & Classify ===
@app.route('/scrape/voz/scan', methods=['POST'])
def scrape_voz_scan():
    url = request.json.get('url', 'https://voz.vn/f/diem-bao.33/')
    try:
        return jsonify(scan_and_classify(url))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 3: Verify server starts without import errors**

Run: `python -c "from server import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server.py
git commit -m "feat: add /scrape/voz/scan endpoint"
```

---

### Task 10: Run full test suite and verify

**Files:**
- None (verification only)

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/test_voz_classifier.py -v`
Expected: All tests PASS

- [ ] **Step 2: Verify Python syntax of all changed files**

Run: `python -m py_compile scrapers/voz.py && python -m py_compile server.py && echo "OK"`
Expected: `OK`

- [ ] **Step 3: Verify config loads correctly**

Run: `python -c "from scrapers.voz import _CONFIG; print('Selection:', _CONFIG['selection']['top_hot']); print('Sources:', list(_CONFIG['source']['patterns'].keys())); print('Topics:', list(_CONFIG['classification']['topics'].keys()))"`
Expected:
```
Selection: 4
Sources: ['/f/diem-bao.33', '/f/lap-trinh-cntt.91', '/f/kinh-te-luat.92']
Topics: ['macro_finance', 'tech_career', 'energy', 'policy_infra']
```

- [ ] **Step 4: Final commit (if any changes from verification)**

```bash
git status
```
