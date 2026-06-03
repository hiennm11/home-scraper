# CONTEXT — home-scraper

Web scraping microservice. Nhận URL forum → trả về structured data (JSON) hoặc Markdown.

## Stack

- **Runtime**: Python 3, Flask (port 8899)
- **Browser engine**: [cloakbrowser](https://github.com/cloakhq/cloakbrowser) — headless browser API giống Playwright/Puppeteer
- **Base image**: `cloakhq/cloakbrowser` (Docker)
- **Markdown**: `markdownify`

## Domain Vocabulary

| Term | Definition |
|------|-----------|
| **scrape** | Gọi URL thật bằng headless browser, extract dữ liệu từ DOM → structured data |
| **thread** | Trang bài viết — chứa các post (`.message--post .bbWrapper`). Scrape ra title + list post |
| **forum** | Trang danh sách thread — chứa các `.structItem`. Scrape ra title + list thread (title, url, meta, latest) |
| **raw** | Trang không khớp pattern thread/forum → trả về title |
| **Voz** | Diễn đàn voz.vn — có endpoint chuyên biệt `/scrape/voz/f33` |
| **F33** | Subforum "Điểm báo" của Voz — `/f/diem-bao.33/` |
| **markdownify** | Convert HTML → Markdown (ATX headings, fenced code, full links, strip script/style) |
| **browser pool** | Queue-based pool 3 browser instances. `acquire()` reuse hoặc launch mới, `release()` trả lại pool |

## Content Detection Logic

JS inject vào page để detect loại nội dung:

1. **thread** — có `.message--post .bbWrapper` → extract `{type, title, posts[]}`
2. **forum** — có `.structItem` → extract `{type, title, threads[{title, url, meta, latest}]}`
3. **raw** — fallback → `{type: 'raw', title}`

## API Endpoints

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/scrape` | POST | `{url}` | JSON structured data (thread/forum/raw) |
| `/scrape/md` | POST | `{url}` | `{type, title, markdown, url}` — HTML→MD |
| `/scrape/batch` | POST | `{urls[]}` (max 50) | `{results[{url, status, ...}]}` — sequential |
| `/scrape/voz/f33` | POST | `{url?}` (default F33) | `{scanned_at, source, threads[{thread_id, title, url, author, replies, views, last_activity_at, is_pinned, is_hot}]}` |
| `/health` | GET | — | `{pool_size, pool_max}` |

## Architectural Notes

- **Browser pool**: chỉ `BrowserPool` class tồn tại nhưng `do_scrape()` và `/scrape/voz/f33` hiện **không dùng pool** — launch browser mới mỗi lần gọi. Pool defined nhưng chưa integrated.
- **No concurrency**: batch endpoint xử lý tuần tự. Không dùng thread/async.
- **Timezone**: hardcoded UTC+7 (Việt Nam).
- **No auth**: endpoints public, không rate limit.
- **Timeout**: mỗi lần `page.goto` timeout 30s.
- **Docker network**: `homelab_net` (external) — chạy trong homelab setup.

## File Map

```
/
├── server.py           # Main app — all routes + do_scrape + BrowserPool + html_to_md
├── debug_server.py     # Dev debug endpoint /debug — inspect structItem DOM structure
├── Dockerfile          # Build từ cloakhq/cloakbrowser
├── docker-compose.yml  # Single service scraper:local, port 8899, homelab_net
├── CONTEXT.md          # This file
├── CLAUDE.md           # Agent skills config
└── docs/
    ├── adr/            # Architectural Decision Records
    └── agents/         # Agent skill configs (issue-tracker, triage-labels, domain)
```
