from flask import Flask, request, jsonify
from cloakbrowser import launch
from scrapers.voz import scrape_f33
import markdownify
import threading
import queue
import hashlib
from functools import lru_cache
from threading import Lock

app = Flask(__name__)

# === Browser Pool ===
class BrowserPool:
    def __init__(self, size=3):
        self._pool = queue.Queue(maxsize=size)
        self._args = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        self._size = size
        self._lock = Lock()

    def acquire(self):
        with self._lock:
            try:
                browser = self._pool.get_nowait()
                try:
                    _ = browser.pages  # Health check
                    return browser
                except:
                    pass
            except queue.Empty:
                pass

            return launch(headless=True, args=self._args)

    def release(self, browser):
        with self._lock:
            try:
                if self._pool.qsize() < self._size:
                    self._pool.put(browser, block=False)
            except:
                try:
                    browser.close()
                except:
                    pass

    def close_all(self):
        while not self._pool.empty():
            try:
                self._pool.get_nowait().close()
            except: pass

_browser_pool = BrowserPool(size=3)

# === Markdown Converter ===
def html_to_md(html: str) -> str:
    if not html:
        return ''

    md = markdownify.markdownify(
        html,
        heading_style="ATX",
        code_style="fenced",
        link_style="full",
        strip=['script', 'style', 'noscript', 'iframe']
    )

    import re
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'\s{2,}', ' ', md)
    return md.strip()

# === Scrape ===
def do_scrape(url):
    with launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']) as browser:
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)

        data = page.evaluate("""
            () => {
                const getText = (el) => el?.textContent?.trim() || '';
                const isThread = !!document.querySelector('.message--post .bbWrapper');
                const isForum = !!document.querySelector('.structItem');

                if (isThread) {
                    return {
                        type: 'thread',
                        title: getText(document.querySelector('.p-title-value')) || document.title,
                        posts: [...document.querySelectorAll('.message--post .bbWrapper')]
                            .map(el => el.innerHTML)
                    };
                }
                if (isForum) {
                    return {
                        type: 'forum',
                        title: getText(document.querySelector('.p-title-value')) || document.title,
                        threads: [...document.querySelectorAll('.structItem')].map(item => {
                            const cells = item.querySelectorAll('.structItem-cell');
                            const a = cells[1]?.querySelector('.structItem-title a');
                            return {
                                title: getText(a),
                                url: a?.href || '',
                                meta: getText(cells[2]),
                                latest: getText(cells[3])
                            };
                        })
                    };
                }
                return { type: 'raw', title: document.title };
            }
        """)
        page.close()
        return data

# === Routes ===
@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'url required'}), 400

    try:
        return jsonify(do_scrape(url))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/scrape/md', methods=['POST'])
def scrape_md():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'url required'}), 400

    try:
        data = do_scrape(url)
        content_type = data.get('type', 'unknown')

        if content_type == 'thread':
            md = '\n\n---\n\n'.join(html_to_md(p) for p in data['posts'])
        elif content_type == 'forum':
            lines = [f'# {data["title"]}', '']
            for t in data['threads']:
                lines += [
                    f'## {t["title"]}',
                    f'- meta: {t["meta"]}',
                    f'- last: {t["latest"]}',
                    f'- url: {t["url"]}', ''
                ]
            md = '\n'.join(lines)
        else:
            md = html_to_md(data.get('posts', [''])[0])

        return jsonify({
            'type': content_type,
            'title': data.get('title', ''),
            'markdown': md,
            'url': url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/scrape/batch', methods=['POST'])
def scrape_batch():
    urls = request.json.get('urls', [])[:50]

    results = []
    for url in urls:
        try:
            results.append({**do_scrape(url), 'url': url, 'status': 'ok'})
        except Exception as e:
            results.append({'url': url, 'status': 'error', 'error': str(e)})

    return jsonify({'results': results})

# === Voz F33 Forum Listing ===
@app.route('/scrape/voz/f33', methods=['POST'])
def scrape_voz_f33():
    url = request.json.get('url', 'https://voz.vn/f/diem-bao.33/')
    try:
        return jsonify(scrape_f33(url))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'pool_size': _browser_pool._pool.qsize(),
        'pool_max': _browser_pool._size
    })

@app.teardown_appcontext
def cleanup(exception=None):
    pass  # Pool stays alive

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8899)