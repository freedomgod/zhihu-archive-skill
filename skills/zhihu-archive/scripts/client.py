"""Read-only API access and strict pagination. Browser UI adapter is separate."""
import re
import time
from urllib.parse import urlencode, urlparse

import requests

BASE = 'https://www.zhihu.com/api/v4'


class CrawlError(RuntimeError):
    pass


def user_token(value):
    value = value.strip()
    if '://' in value:
        u = urlparse(value)
        if u.scheme != 'https' or u.hostname not in ('www.zhihu.com', 'zhihu.com'):
            raise CrawlError('请输入知乎 HTTPS 个人主页链接')
        match = re.match(r'^/people/([^/]+)', u.path)
        value = match.group(1) if match else ''
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', value):
        raise CrawlError('需要个人主页链接或 url_token；昵称请先通过浏览器搜索确定主页')
    return value


def paginate(get, first, max_pages=10000):
    next_url, seen_urls, seen_items = first, set(), set()
    for _ in range(max_pages):
        if next_url in seen_urls:
            raise CrawlError('分页链接循环，归档尚未完整')
        seen_urls.add(next_url)
        page = get(next_url)
        if not isinstance(page.get('data'), list):
            raise CrawlError('列表响应缺少 data 数组')
        for item in page['data']:
            key = str(item.get('id', item.get('url_token', item.get('slug', ''))))
            if not key:
                raise CrawlError('列表条目缺少唯一标识')
            if key not in seen_items:
                seen_items.add(key)
                yield item
        paging = page.get('paging', {})
        if paging.get('is_end') is True:
            return
        next_url = paging.get('next')
        if not next_url:
            raise CrawlError('未收到分页结束标记或下一页链接')
        if not page['data']:
            raise CrawlError('分页意外为空且尚未结束')
    raise CrawlError('达到分页上限，归档尚未完整')


def api_url(url):
    p = urlparse(url)
    if p.scheme == 'http' and p.hostname == 'www.zhihu.com' and p.path.startswith('/api/v4/') and not p.username and p.port in (None, 80):
        url = p._replace(scheme='https', netloc='www.zhihu.com').geturl()
        p = urlparse(url)
    if p.scheme != 'https' or p.hostname != 'www.zhihu.com' or not p.path.startswith('/api/v4/') or p.username or p.port not in (None, 443):
        raise CrawlError('拒绝非知乎 API 分页地址')
    return url


class APIClient:
    def __init__(self, cookies, delay=2, timeout=30):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36',
                                     'Referer': 'https://www.zhihu.com/', 'Accept': 'application/json'})
        for k, v in cookies.items():
            self.session.cookies.set(k, v, domain='.zhihu.com', path='/')
        self.delay, self.timeout = delay, timeout

    def json(self, url):
        url = api_url(url)
        for attempt in range(3):
            time.sleep(self.delay + (2 ** attempt if attempt else 0))
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
            except requests.RequestException:
                if attempt < 2:
                    continue
                raise CrawlError('网络请求失败；已保留进度，可稍后重试') from None
            if response.status_code in (401, 403, 429):
                raise CrawlError(f'HTTP {response.status_code}：需检查登录、验证或限流；已停止请求')
            if response.status_code >= 500 and attempt < 2:
                continue
            if response.status_code != 200:
                raise CrawlError(f'HTTP {response.status_code}：接口访问失败')
            try:
                value = response.json()
            except ValueError:
                raise CrawlError('接口返回非 JSON，可能需要在浏览器中验证') from None
            if not isinstance(value, dict) or 'error' in value:
                raise CrawlError('接口返回错误或未知格式')
            return value
        raise CrawlError('请求失败')

    def profile(self, token):
        return self.json(f'{BASE}/members/{token}?include=answer_count,articles_count,columns_count')

    def items(self, token, stream):
        fields = 'content,excerpt,voteup_count,comment_count,created_time,updated_time,created,updated,author,question,column,paid_info,is_paid,is_public'
        endpoint = 'column-contributions' if stream == 'columns' else stream
        if stream == 'columns':
            fields = 'column.title,intro,description,articles_count,followers'
        query = urlencode({'limit': 20, 'offset': 0, 'sort_by': 'created', 'include': 'data[*].' + fields})
        def get_page(url):
            value = self.json(url)
            if stream == 'columns' and isinstance(value.get('data'), list):
                value = dict(value, data=[row.get('column', row) for row in value['data']])
            return value
        return paginate(get_page, f'{BASE}/members/{token}/{endpoint}?{query}')

    def column_items(self, column):
        query = urlencode({'limit': 20, 'offset': 0, 'include': 'data[*].content,author,column'})
        return paginate(self.json, f'{BASE}/columns/{column}/items?{query}')

    def detail(self, item, kind):
        return self.json(f'{BASE}/{kind}s/{item["id"]}?include=content,author,question,column,paid_info')

    def close(self):
        self.session.close()
