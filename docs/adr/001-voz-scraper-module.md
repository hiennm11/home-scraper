# ADR-001: Tách Voz scraper ra module riêng

**Date**: 2026-06-03  
**Status**: Accepted

## Context

`server.py` hiện là monolith 298 dòng, chứa tất cả logic: BrowserPool, html_to_md, do_scrape, 4 routes (scrape, scrape/md, scrape/batch, scrape/voz/f33), health check. Code Voz chiếm ~110 dòng (lines 172-284) với 3 helper functions (parse_number, parse_timestamp, extract_thread_id) và JS inject nội tuyến.

Khi thêm scraper mới (ví dụ batdongsan.com.vn, tinhte.vn), file sẽ phình to không kiểm soát được.

## Decision

**Tách mỗi scraper chuyên biệt thành module riêng trong package `scrapers/`.**

Cấu trúc:

```
scrapers/
├── __init__.py        # Package marker
└── voz.py             # Voz.vn forum scraper
    ├── _parse_number()
    ├── _parse_timestamp()
    ├── _extract_thread_id()
    ├── _INJECT_JS       # JS evaluate string (module-level constant)
    └── scrape_f33(url)  # Public API → returns dict
```

`server.py` chỉ giữ route handler mỏng:

```python
from scrapers.voz import scrape_f33

@app.route('/scrape/voz/f33', methods=['POST'])
def scrape_voz_f33():
    url = request.json.get('url', 'https://voz.vn/f/diem-bao.33/')
    try:
        return jsonify(scrape_f33(url))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## Rationale

1. **Single Responsibility** — mỗi module scraper chỉ lo 1 site. Dễ test, dễ debug, dễ thay thế.
2. **Không phá vỡ API contract** — endpoint `/scrape/voz/f33` giữ nguyên input/output JSON.
3. **Mở rộng tự nhiên** — thêm `scrapers/batdongsan.py`, `scrapers/tinhte.py` mà không đụng vào code cũ.
4. **Không cần Blueprint** — quy mô nhỏ, 1 endpoint/scraper, không cần Flask Blueprint phức tạp hóa.

## Consequences

- `server.py` giảm ~110 dòng.
- `scrapers/voz.py` là single source of truth cho mọi thứ Voz.
- Helper functions đổi thành private (`_parse_number`, ...) để tránh leak ra ngoài package.
- JS inject string tách thành module-level constant `_INJECT_JS` — dễ đọc hơn inline trong hàm.
