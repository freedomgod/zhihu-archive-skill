"""Headless integration verification of the generated file:// reader."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
file = next((root / 'output' / 'demo').glob('*/index.html'))
out = root / 'output' / 'playwright'
out.mkdir(parents=True, exist_ok=True)
checks, errors = [], []
with sync_playwright() as p:
    channel = os.environ.get('ZHIHU_TEST_BROWSER', 'chrome')
    browser = p.chromium.launch(headless=True, **({} if channel == 'chromium' else {'channel': channel}))
    context = browser.new_context(viewport={'width': 1440, 'height': 1100})
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    context.route('http://**/*', lambda r: r.abort())
    context.route('https://**/*', lambda r: r.abort())
    page.goto(file.as_uri())
    page.wait_for_function("document.querySelectorAll('.entry').length===20")
    assert page.get_by_role('button', name='我的收藏').count() == 0
    assert page.get_by_role('button', name='收藏文章', exact=True).count() == 0
    assert page.locator('.brand').inner_text() == '知乎博主归档'
    assert not page.locator('#reader').is_visible()
    assert '29 篇' in page.locator('#count').inner_text()
    checks.append('local file opens without server or remote requests')
    page.screenshot(path=str(out / 'reader-desktop.png'))
    page.locator('[data-kind=article]').click()
    assert page.locator('.entry').count() == 3
    page.locator('#column').select_option('notes')
    assert page.locator('.entry').count() == 3
    checks.append('article and column filters')
    page.locator('#column').select_option('')
    page.locator('[data-kind=all]').click()
    page.locator('#query').fill('证据')
    page.wait_for_function("document.querySelector('#count').textContent.startsWith('26 篇')")
    checks.append('full text search')
    page.locator('#query').fill('不存在的词条')
    page.wait_for_function("document.querySelectorAll('.entry').length===0")
    assert '没有匹配' in page.locator('#list').inner_text()
    checks.append('empty search state')
    page.locator('#query').fill('')
    page.wait_for_function("document.querySelectorAll('.entry').length===20")
    page.locator('#sort').select_option('votes')
    assert page.locator('.entry').first.get_attribute('data-key') == 'answer:26'
    page.locator('#next').click()
    assert page.locator('.entry').count() == 9
    page.locator('#prev').click()
    checks.append('sorting and pagination')
    page.locator('.entry').first.click()
    assert page.locator('#reader .body').inner_text().find('证据') >= 0
    assert page.locator('#reader a[download]').get_attribute('href') == 'answers/26.md'
    assert page.locator('#reader').is_visible()
    assert page.locator('#reading-dialog').get_attribute('open') is not None
    page.screenshot(path=str(out / 'reader-desktop-article.png'))
    page.keyboard.press('Escape')
    assert not page.locator('#reader').is_visible()
    checks.append('article dialog, Markdown link, keyboard close; no favorites interface')
    page.locator('#theme').click()
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.screenshot(path=str(out / 'reader-dark.png'))
    page.locator('#theme').click()
    page.locator('[data-kind=all]').click()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out / 'reader-mobile-list.png'))
    page.locator('.entry').first.click()
    assert page.locator('#reader').is_visible()
    page.screenshot(path=str(out / 'reader-mobile-article.png'))
    page.locator('.back').click()
    assert page.locator('.list-panel').is_visible()
    checks.append('dark theme and mobile list/article navigation without overflow')
    assert not errors, errors
    browser.close()
(out / 'ui-report.json').write_text(json.dumps({'checks': checks, 'browser_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'checks': checks, 'browser_errors': errors}, ensure_ascii=False))
