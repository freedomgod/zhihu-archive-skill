"""Read data produced by actual Zhihu page navigation, without forging signatures."""
import json
import re
from urllib.parse import urlparse

from auth import launch_context
from client import CrawlError


def normalize(value):
    if isinstance(value, list):
        return [normalize(x) for x in value]
    if isinstance(value, dict):
        aliases = {'urlToken': 'url_token', 'voteupCount': 'voteup_count', 'commentCount': 'comment_count',
                   'createdTime': 'created_time', 'updatedTime': 'updated_time', 'answerCount': 'answer_count',
                   'articlesCount': 'articles_count', 'columnsCount': 'columns_count', 'paidInfo': 'paid_info',
                   'isPaid': 'is_paid', 'isPaidContent': 'is_paid_content', 'isPurchased': 'is_purchased',
                   'isPublic': 'is_public', 'isFull': 'is_full'}
        return {aliases.get(k, k): normalize(v) for k, v in value.items()}
    return value


def hydrate(item, entities):
    item = normalize(item)
    for field, group in (('author', 'users'), ('question', 'questions'), ('column', 'columns')):
        value = item.get(field)
        if isinstance(value, (str, int)):
            resolved = entities.get(group, {}).get(str(value))
            if isinstance(resolved, dict):
                item[field] = normalize(resolved)
    return item


class BrowserClient:
    def __init__(self, profile, channel='msedge', delay=2, max_scrolls=2000):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        try:
            self.context = launch_context(self.pw, profile, channel)
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.set_default_timeout(10000)
        except Exception:
            self.pw.stop()
            raise
        self.delay = max(1, delay)
        self.max_scrolls = max_scrolls
        self.wanted_path = ''
        self.responses = []
        self.blocked = None
        self.page.on('response', self._response)

    def _response(self, response):
        path = urlparse(response.url).path
        if path != self.wanted_path:
            return
        if response.status in (401, 403, 429):
            self.blocked = f'HTTP {response.status}：请在浏览器中完成登录或验证'
            return
        if response.status == 200:
            try:
                value = response.json()
                if isinstance(value, dict):
                    self.responses.append(normalize(value))
            except Exception:
                pass

    def _goto(self, url):
        try:
            response = self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            if response and response.status in (401, 403, 429):
                raise CrawlError(f'页面 HTTP {response.status}：请在浏览器中完成验证')
            self.page.wait_for_timeout(self.delay * 1000)
        except CrawlError:
            raise
        except Exception:
            raise CrawlError('浏览器页面加载失败或窗口已关闭；已保留进度') from None
        if '/signin' in self.page.url or '/account/unhuman' in self.page.url:
            raise CrawlError('页面要求登录或人工验证，请先运行 login')

    def _state(self):
        scripts = self.page.locator('script#js-initialData, script#__NEXT_DATA__')
        for i in range(scripts.count()):
            try:
                data = normalize(json.loads(scripts.nth(i).text_content()))
                return data.get('initialState', data)
            except (ValueError, TypeError):
                continue
        return {}

    def profile(self, token):
        self._goto(f'https://www.zhihu.com/people/{token}')
        state = self._state()
        users = state.get('entities', {}).get('users', {})
        for u in users.values():
            if isinstance(u, dict) and u.get('url_token') == token:
                return u
        name = self.page.locator('.ProfileHeader-name')
        if name.count():
            return {'url_token': token, 'name': name.first.inner_text()}
        raise CrawlError('无法从知乎主页确认作者；请检查链接和登录状态')

    def _list(self, url, path, entity):
        self.wanted_path, self.responses, self.blocked = path, [], None
        seen, idle, ended = set(), 0, False
        try:
            self._goto(url)
            entities = self._state().get('entities', {})
            initial = entities.get(entity, {})
            initial_items = [hydrate(v, entities) for v in initial.values() if isinstance(v, dict)] if isinstance(initial, dict) else []
            for step in range(self.max_scrolls):
                batches, self.responses = self.responses, []
                items = initial_items if step == 0 else []
                for batch in batches:
                    if not isinstance(batch.get('data'), list):
                        raise CrawlError('浏览器列表响应缺少 data 数组')
                    for entry in batch['data']:
                        value = entry.get('column', entry) if entity == 'columns' else entry.get('target', entry)
                        items.append(hydrate(value, entities))
                    if batch.get('paging', {}).get('is_end') is True:
                        ended = True
                new = 0
                for item in items:
                    key = str(item.get('id') or item.get('slug') or item.get('url_token') or '')
                    if key and key not in seen:
                        seen.add(key)
                        new += 1
                        yield item
                if self.blocked:
                    raise CrawlError(self.blocked)
                if ended:
                    return
                idle = 0 if new or batches else idle + 1
                if idle >= 5:
                    raise CrawlError('列表停止加载且未收到结束标记，已保存可见条目；本次归档不完整')
                self.page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
                self.page.wait_for_timeout(self.delay * 1000)
            raise CrawlError('达到浏览器滚动上限，归档不完整')
        finally:
            self.wanted_path = ''

    def items(self, token, stream):
        endpoint = 'column-contributions' if stream == 'columns' else stream
        return self._list(f'https://www.zhihu.com/people/{token}/{stream}',
                          f'/api/v4/members/{token}/{endpoint}', stream)

    def column_items(self, slug):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', slug):
            raise CrawlError('专栏标识格式无效')
        return self._list(f'https://www.zhihu.com/column/{slug}', f'/api/v4/columns/{slug}/items', 'articles')

    def detail(self, item, kind):
        # Separate tab: visiting a detail page must not reset the list scroll state.
        list_page = self.page
        self.page = self.context.new_page()
        try:
            if kind == 'article':
                url = f'https://zhuanlan.zhihu.com/p/{item["id"]}'
            else:
                qid = item.get('question', {}).get('id')
                if not qid:
                    raise CrawlError('回答缺少问题 ID，无法打开详情页')
                url = f'https://www.zhihu.com/question/{qid}/answer/{item["id"]}'
            self._goto(url)
            entities = self._state().get('entities', {})
            entity = hydrate(entities.get(kind + 's', {}).get(str(item['id']), {}), entities)
            if entity.get('content'):
                return entity
            selector = '.Post-RichText' if kind == 'article' else '.AnswerItem .RichContent-inner'
            body = self.page.locator(selector)
            # A collapsed answer is an excerpt; expand before extraction.
            expand = self.page.get_by_role('button', name=re.compile('阅读全文|展开阅读全文'))
            if expand.count():
                expand.first.click()
                self.page.wait_for_timeout(self.delay * 1000)
            if body.count():
                return dict(item, content=body.first.inner_html(), body_source='detail_dom')
            raise CrawlError('详情页没有可用正文，保留摘要并标注缺失')
        finally:
            self.page.close()
            self.page = list_page

    def close(self):
        self.context.close()
        self.pw.stop()
