"""Voz.vn forum scraper — chuyên biệt cho diễn đàn Voz.

Chỉ tập trung scrape F33 ("Điểm báo") và các subforum Voz.
Tách riêng khỏi server.py để dễ maintain, test, và mở rộng.
"""

import re
from datetime import datetime, timezone, timedelta
from cloakbrowser import launch


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
            threads.push({
                title: gt(a),
                url: a ? a.href : '',
                replies: matches[0] || '',
                views: matches[1] || '',
                last_activity: gt(lastActivity),
                author: gt(author),
                is_pinned: item.querySelector('.structItem--pinned') != null,
                is_hot: item.querySelector('.structItem--hot') != null,
                tags: []
            });
        }
        return { threads: threads, forum_title: gt(document.querySelector('.p-title-value')) };
    }
"""


# --- Public API ---

def scrape_f33(url: str = 'https://voz.vn/f/diem-bao.33/') -> dict:
    """Scrape Voz F33 forum listing.

    Args:
        url: Voz subforum URL (default: F33 "Điểm báo").

    Returns:
        {
            'scanned_at': '...',
            'source': 'voz_f33',
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
        'source': 'voz_f33',
        'threads': threads_out,
    }
