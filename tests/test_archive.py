import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def module(name):
    assert (SCRIPTS / f'{name}.py').exists(), f'{name} capability is not implemented'
    return __import__(name)


def test_cookie_domain_isolation_and_formats(tmp_path):
    a = module('auth')
    f = tmp_path / 'cookies.json'
    f.write_text(json.dumps([{'name': 'z_c0', 'value': 'private', 'domain': '.zhihu.com'},
                             {'name': 'other', 'value': 'private', 'domain': '.example.org'}]))
    assert a.load_cookies(f) == {'z_c0': 'private'}
    f.write_text('Cookie: z_c0=private; d_c0=sample')
    assert a.load_cookies(f)['d_c0'] == 'sample'
    f.write_text('# Netscape HTTP Cookie File\n#HttpOnly_.zhihu.com\tTRUE\t/\tTRUE\t0\tz_c0\tprivate\n')
    assert a.load_cookies(f) == {'z_c0': 'private'}


def test_pagination_deduplicates_and_requires_terminal_page():
    c = module('client')
    pages = {'first': {'data': [{'id': 1}, {'id': 2}], 'paging': {'is_end': False, 'next': 'next'}},
             'next': {'data': [{'id': 2}, {'id': 3}], 'paging': {'is_end': True}}}
    assert [x['id'] for x in c.paginate(pages.__getitem__, 'first')] == [1, 2, 3]
    pages['next']['paging'] = {'is_end': False, 'next': 'first'}
    with pytest.raises(c.CrawlError):
        list(c.paginate(pages.__getitem__, 'first'))
    with pytest.raises(c.CrawlError):
        list(c.paginate(lambda _: {'data': [], 'paging': {'is_end': False}}, 'first'))


def test_sanitization_preserves_rich_content_without_active_code():
    a = module('archive')
    dirty = '<p>正文<script>alert(1)</script><img src="javascript:x" onerror="alert(1)"></p><a href="javascript:x">链接</a><h2>标题</h2><pre><code>x = 1</code></pre><table><tr><th>A</th></tr><tr><td>B</td></tr></table>'
    clean = a.clean_html(dirty)
    assert '<script' not in clean and 'onerror' not in clean and 'javascript:' not in clean
    md = a.html_markdown(clean)
    assert '## 标题' in md and '```' in md and '| A |' in md and '| B |' in md


def test_partial_archive_retains_existing_content_and_pack_excludes_credentials(tmp_path):
    a = module('archive')
    store = a.Archive(tmp_path, {'name': '测试作者', 'url_token': 'test', 'id': 'u1'})
    item = {'id': 1, 'type': 'answer', 'author': {'id': 'u1'}, 'question': {'id': 9, 'title': '</script><script>bad</script>'}, 'content': '<p>完整正文</p>', 'created_time': 1}
    store.save_item(item, 'answer')
    store.save_item(dict(item, content=''), 'answer')
    store.save_item({'id': 2, 'author': {'id': 'someone-else'}, 'content': '<p>别人的文章</p>'}, 'article')
    store.save_item({'id': 3, 'author': {'id': 'u1'}, 'excerpt': '只有摘要'}, 'article')
    store.state['streams']['answers'] = {'status': 'blocked', 'reason': 'HTTP 403'}
    store.finish()
    manifest = json.loads((store.root / 'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['items']) == 2
    assert manifest['items']['answer:1']['body_status'] == 'full'
    assert manifest['items']['article:3']['body_status'] == 'missing'
    assert not manifest['complete']
    html = (store.root / 'index.html').read_text(encoding='utf-8')
    assert '</script><script>bad' not in html
    assert '完整正文' in html
    (store.root / 'cookies.txt').write_text('SECRET')
    (store.root / '.auth').mkdir()
    (store.root / '.auth' / 'state.json').write_text('SECRET')
    import zipfile
    with zipfile.ZipFile(store.pack()) as z:
        assert not any('cookies' in n or '.auth' in n for n in z.namelist())
    resumed = a.Archive(tmp_path, store.state['author'])
    assert len(resumed.state['items']) == 2


def test_profile_input_and_http_errors_are_bounded():
    c = module('client')
    assert c.user_token('https://www.zhihu.com/people/example-author/answers') == 'example-author'
    with pytest.raises(c.CrawlError):
        c.user_token('https://evil.test/people/test')
    with pytest.raises(c.CrawlError):
        c.user_token('../test')


def test_http_403_stops_without_retries_or_secret_output():
    c = module('client')
    import requests
    class Session:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            r = requests.Response()
            r.status_code = 403
            r._content = b'private-cookie-value'
            return r
    api = c.APIClient({}, delay=0)
    api.session = Session()
    with pytest.raises(c.CrawlError) as error:
        api.json('https://www.zhihu.com/api/v4/members/test')
    assert api.session.calls == 1
    assert 'private' not in str(error.value)


def test_remote_images_do_not_claim_offline_completeness_on_resume(tmp_path):
    a = module('archive')
    author = {'name': '测试', 'url_token': 'test', 'id': 'u'}
    store = a.Archive(tmp_path, author, images='remote')
    store.save_item({'id': 9, 'author': {'id': 'u'}, 'content': '<p>正文</p><img src="https://external.example/image.png">'}, 'article')
    store.finish()
    resumed = a.Archive(tmp_path, author, images='local')
    resumed.finish()
    assert not resumed.state['offline_complete']


def test_legacy_http_next_link_is_requested_over_https():
    c = module('client')
    import requests
    urls = []
    class Session:
        def get(self, url, **kwargs):
            urls.append(url)
            r = requests.Response()
            r.status_code = 200
            r._content = b'{"data":[],"paging":{"is_end":true}}'
            return r
    api = c.APIClient({}, delay=0)
    api.session = Session()
    api.json('http://www.zhihu.com/api/v4/members/test/answers?offset=20')
    assert urls == ['https://www.zhihu.com/api/v4/members/test/answers?offset=20']
    with pytest.raises(c.CrawlError):
        api.json('http://evil.test/api/v4/answers')


def test_owned_column_contribution_response_is_unwrapped():
    c = module('client')
    urls = []
    api = c.APIClient({}, delay=0)
    def get(url):
        urls.append(url)
        return {'data': [{'column': {'id': 'invest', 'title': '投资笔记'}}], 'paging': {'is_end': True}}
    api.json = get
    rows = list(api.items('test', 'columns'))
    assert '/column-contributions?' in urls[0]
    assert rows == [{'id': 'invest', 'title': '投资笔记'}]
