from flask import Flask, request, jsonify
from cloakbrowser import launch

app = Flask(__name__)

@app.route('/debug', methods=['POST'])
def debug():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'url required'}), 400
    try:
        with launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
            page = browser.new_page()
            page.goto(url, wait_until='load', timeout=30000)
            
            # Get raw HTML of first structItem to inspect structure
            items = page.query_selector_all('.structItem')
            
            result = {
                'found_structItem': len(items),
                'first_item_classes': [],
                'first_item_html': ''
            }
            
            if items:
                first = items[0]
                # Get all classes from first structItem
                classes = first.get_attribute('class').split() if first.get_attribute('class') else []
                result['first_item_classes'] = classes
                
                # Get inner HTML
                result['first_item_html'] = first.inner_html()[:2000]
                
                # Try different selectors on first item
                selectors = [
                    '.structItem-title',
                    '.structItem-name',
                    '.structItem-meta',
                    '.structItem-excerpt',
                    '.structItem-participant',
                    '.structItem-container',
                    '[data-template]',
                    '.structItem-row',
                    '.structItem-major',
                    '.structItem-minor',
                    'h3', 'h4',
                    '.node-stats',
                    '.lastPostInfo'
                ]
                
                result['selector_results'] = {}
                for sel in selectors:
                    el = first.query_selector(sel)
                    if el:
                        result['selector_results'][sel] = {
                            'text': el.inner_text()[:200],
                            'html': el.inner_html()[:300]
                        }
            
            page.close()
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8899)