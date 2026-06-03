# Voz Classifier Pipeline — Design Spec

**Date**: 2026-06-03
**Status**: Draft
**Replaces**: VOZ Macro Scanner userscript v0.3

## Overview

Port toàn bộ pipeline scan → score → classify → extract content từ userscript JS sang Python backend. Userscript bỏ hẳn. Config toàn bộ classification constants ra JSON file.

## Motivation

- Userscript phụ thuộc browser, không schedule được, không reusable.
- Python backend (`scrapers/voz.py`) hiện chỉ scrape listing metadata — thiếu scoring, classification, content extraction.
- Logic phân loại hiện nằm rải rác trong userscript, khó maintain, không test được.

## Architecture

```
n8n workflow
    │
    ▼ POST {url: "https://voz.vn/f/diem-bao.33/"}
POST /scrape/voz/scan
    │
    ├─ 1. Goto listing page → extract thread list (reuse _INJECT_JS)
    ├─ 2. Score + classify từng thread (config-driven)
    ├─ 3. Select top 4 hot + 3 curated = 7 threads
    ├─ 4. Fetch page 1 + last page từng thread (delay 1.2-2.2s)
    ├─ 5. Extract original post + comments (filter, truncate)
    └─ 6. Return structured JSON
```

Monolithic — tất cả trong `scrapers/voz.py`, không tách module riêng.

## Endpoint

### `POST /scrape/voz/scan`

**Input**:

```json
{
  "url": "https://voz.vn/f/diem-bao.33/"
}
```

**Output**:

```json
{
  "scanned_at": "2026-06-03T14:30:00+07:00",
  "source": "voz_f33",
  "threads": [
    {
      "thread_id": "1234567",
      "title": "Fed giữ nguyên lãi suất...",
      "url": "https://voz.vn/t/thread-title.1234567/",
      "source": "voz_f33",
      "topic": "macro_finance",
      "replies": 156,
      "views": 12345,
      "score": 2.8471,
      "original_post": "Nội dung bài gốc (tối đa 500 ký tự)...",
      "comments": [
        "Comment 1 (tối đa 300 ký tự)...",
        "Comment 2..."
      ]
    }
  ]
}
```

- Field naming: `snake_case` (Python convention).
- `thread_id` extracted from URL via `_extract_thread_id()`.
- `topic` là 1 trong: `macro_finance`, `tech_career`, `energy`, `policy_infra`, `general`.
- Threads sắp xếp giảm dần theo `score`.

## Config File

**Path**: `scrapers/voz_classifier_config.json`

Gom toàn bộ magic numbers, keywords, weights vào 1 file JSON. Sửa config không cần đụng code.

### Structure

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

**Note về encoding**: Keywords trong config viết không dấu để tránh vấn đề Unicode. Hàm `_detect_topic()` và `_topic_bonus()` sẽ normalize input title về không dấu trước khi match.

### Loading

```python
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "voz_classifier_config.json"

def _load_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

_CONFIG = _load_config()  # module-level, loaded once
```

## Code Structure

Tất cả trong `scrapers/voz.py`. File mở rộng từ 146 dòng hiện tại.

### Giữ nguyên (không sửa)
- `_parse_number(s)` — parse "1.2K" → 1200
- `_parse_timestamp(s)` — relative time → ISO 8601
- `_extract_thread_id(url)` — extract numeric ID
- `scrape_listing(url)` — public API hiện tại

### Sửa nhẹ
- `_INJECT_JS` — Mở rộng thêm field `page_jump` (đếm `.structItem-pageJump a`) để có proxy page count lúc scoring, tránh phải fetch thread mới biết.

### Thêm mới

#### Classification helpers
| Function | Input | Output | Note |
|----------|-------|--------|------|
| `_load_config()` | — | `dict` | Đọc JSON config |
| `_detect_source(url)` | URL string | `"voz_f33"` \| `"voz_cntt"` \| `"voz_ktl"` \| `None` | Match path pattern |
| `_normalize_vi(text)` | string | string không dấu (ASCII) | Strip Vietnamese diacritics bằng mapping table: á→a, đ→d, ơ→o, etc. Dùng để match keyword trong config. |
| `_is_garbage_title(title)` | string | `bool` | Check blacklist (không dấu) |
| `_topic_bonus(title)` | string | `float` (0, 0.5, 1.0, 1.5) | strong=+1, medium=+0.5 |
| `_detect_topic(title)` | string | `"macro_finance"` \| ... \| `"general"` | Match keyword → category |
| `_source_bonus(source)` | string | `float` | Lookup config |

#### Scoring
| Function | Input | Output |
|----------|-------|--------|
| `_calc_score(thread, source)` | thread dict + source string | `float` |
| `_select_threads(threads)` | list of scored threads | list of selected |

Scoring formula:
```
score = log10(replies+1) * 0.38
      + log10(views+1)   * 0.20
      + log10(pages+1)   * 0.12
      + freshness         * 0.15
      + topic_bonus       * 0.10
      + source_bonus      * 0.05
```

`freshness`: Tính từ `last_activity_at` (đã có từ `scrape_listing`) → chênh lệch giờ so với now → normalize về [0, 1] với decay window 72h. Công thức: `freshness = max(0, 1 - hours_since_last_activity / 72)`. Thread mới nhất = 1.0, thread 3 ngày tuổi = 0.0.

`pages`: Giá trị `page_jump` từ listing page (đếm `.structItem-pageJump a` trong `_INJECT_JS`). Đây là proxy — real page count chỉ lấy được sau khi fetch thread, dùng trong response data chứ không dùng để score. Khác userscript về cách lấy (DOM listing vs fetch page 1) nhưng cùng logic.

#### Content extraction
| Function | Input | Output |
|----------|-------|--------|
| `_clean_html(html)` | HTML string | plain text |
| `_parse_posts(html)` | HTML string | `{original_post, comments[]}` |
| `_get_page_count(html)` | HTML string | `int` |
| `_fetch_thread_content(url)` | URL string | `{page_count, original_post, comments[]}` |

`_clean_html()`:
1. Parse HTML
2. Remove `blockquote`, `img`, `script`, `style`
3. Replace `<a>` with text content
4. Normalize whitespace

`_parse_posts()`:
1. Query `.message-body .bbWrapper`
2. Post đầu tiên → `original_post` (truncate 500 chars)
3. Các post còn lại → `comments[]` (filter < 5 words, truncate 300 chars)

`_fetch_thread_content()`:
1. Goto page 1 → extract posts + đếm total pages
2. Nếu `total_pages > 1` AND `replies >= 30` → goto last page → extract thêm posts
3. Return combined

#### Public API
| Function | Input | Output |
|----------|-------|--------|
| `scan_and_classify(url)` | URL string | `dict` (full response) |

Orchestrator — gọi tuần tự các bước trên.

## Server Route

Thêm vào `server.py`:

```python
from scrapers.voz import scan_and_classify

@app.route('/scrape/voz/scan', methods=['POST'])
def scrape_voz_scan():
    url = request.json.get('url', 'https://voz.vn/f/diem-bao.33/')
    try:
        return jsonify(scan_and_classify(url))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

`/scrape/voz/listing` giữ nguyên — không breaking change.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| URL không phải Voz subforum | Return `{"error": "unsupported_url"}` 400 |
| Thread fetch fail (timeout, block) | Skip thread đó, continue với thread khác. Log warning. |
| 0 thread sau filter | Return `{"threads": []}` — không lỗi |
| Config file missing | Raise runtime error khi import module |

## Dependencies

- `cloakbrowser` — headless browser (đã có)
- `json`, `pathlib`, `re`, `math`, `random`, `time` — stdlib
- Không thêm dependency mới

## What Stays Unchanged

- Browser pool (vẫn chưa dùng)
- `/scrape/voz/listing` endpoint
- `/scrape`, `/scrape/md`, `/scrape/batch` endpoints
- Docker setup

## What Gets Deleted

- Userscript `VOZ Macro Scanner v0.3` — bỏ hẳn (không nằm trong repo này, nhưng ngừng sử dụng)

## Risks

1. **Cloakbrowser auth stability** — Nếu Voz thay đổi anti-bot, headless browser có thể bị chặn. Accepted risk (user confirmed).
2. **Performance** — Fetch 7 threads tuần tự với delay 1.2-2.2s = ~12-25s tổng thời gian response. n8n webhook timeout cần > 30s.
3. **Config drift** — Keywords cần update định kỳ theo trend. Giải pháp: JSON config dễ sửa, không cần deploy code.
