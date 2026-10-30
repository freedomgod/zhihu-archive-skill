"""Portable Markdown archive, sanitized reader, local images and controlled ZIP."""
import base64
import hashlib
import html
import json
import re
import time
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString

TZ = timezone(timedelta(hours=8))
TEMPLATE = Path(__file__).resolve().parent.parent / 'assets' / 'reader.html'
ALLOWED_TAGS = set('p br div span h1 h2 h3 h4 h5 h6 strong b em i u s del blockquote pre code ul ol li a img figure figcaption table thead tbody tr th td hr sup sub video source'.split())


def safe_url(value, image=False):
    value = str(value or '').strip()
    if value.startswith('//'):
        value = 'https:' + value
    if image and re.match(r'^data:image/(png|jpeg|gif|webp);base64,', value):
        return value
    scheme = urlparse(value).scheme.lower()
    if scheme in ('https', 'http'):
        return value
    if not scheme and not value.startswith(('\\', '//')) and not any(ord(c) < 32 for c in value):
        return value
    return ''


def clean_html(content):
    soup = BeautifulSoup(content or '', 'html.parser')
    for bad in soup.find_all(['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'svg', 'math']):
        bad.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        attrs = {}
        if tag.name == 'img':
            source = tag.get('data-original') or tag.get('data-actualsrc') or tag.get('src', '')
            attrs = {'src': safe_url(source, image=True), 'alt': str(tag.get('alt', '')), 'loading': 'lazy'}
            tex = tag.get('data-tex')
            if tex:
                attrs['alt'] = '$' + str(tex) + '$'
        elif tag.name == 'a':
            attrs = {'href': safe_url(tag.get('href')), 'rel': 'noopener noreferrer', 'target': '_blank'}
        elif tag.name in ('video', 'source'):
            attrs = {'src': safe_url(tag.get('src'))}
            if tag.name == 'video':
                attrs.update(controls='', preload='none')
        elif tag.name in ('td', 'th'):
            for key in ('colspan', 'rowspan'):
                if str(tag.get(key, '')).isdigit():
                    attrs[key] = str(min(100, int(tag[key])))
        tag.attrs = {k: v for k, v in attrs.items() if v or k == 'controls'}
    return str(soup)


def html_markdown(content):
    soup = BeautifulSoup(content, 'html.parser')

    def walk(node):
        if isinstance(node, NavigableString):
            return str(node)
        name = node.name
        if name == 'table':
            rows = [[c.get_text(' ', strip=True).replace('|', '\\|') for c in row.find_all(['td', 'th'])] for row in node.find_all('tr')]
            rows = [r for r in rows if r]
            if not rows:
                return ''
            width = max(map(len, rows))
            rows = [r + [''] * (width - len(r)) for r in rows]
            lines = ['| ' + ' | '.join(r) + ' |' for r in rows]
            lines.insert(1, '| ' + ' | '.join(['---'] * width) + ' |')
            return '\n\n' + '\n'.join(lines) + '\n\n'
        if name == 'pre':
            text = node.get_text().strip('\n')
            fence = '`' * max(3, max((len(x) + 1 for x in re.findall(r'`+', text)), default=3))
            return f'\n\n{fence}\n{text}\n{fence}\n\n'
        inner = ''.join(walk(c) for c in node.children)
        if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return '\n\n' + '#' * int(name[1]) + ' ' + inner.strip() + '\n\n'
        if name in ('p', 'div', 'figure'):
            return '\n\n' + inner.strip() + '\n\n'
        if name == 'br':
            return '  \n'
        if name == 'hr':
            return '\n\n---\n\n'
        if name in ('strong', 'b'):
            return '**' + inner + '**'
        if name in ('em', 'i'):
            return '*' + inner + '*'
        if name in ('s', 'del'):
            return '~~' + inner + '~~'
        if name == 'code':
            fence = '`' * max(1, max((len(x) + 1 for x in re.findall(r'`+', inner)), default=1))
            return fence + inner + fence
        if name == 'a':
            url = node.get('href', '').replace(')', '%29').replace(' ', '%20')
            return f'[{inner}](<{url}>)' if url else inner
        if name == 'img':
            alt, url = node.get('alt', '').replace(']', '\\]'), node.get('src', '')
            if alt.startswith('$') and alt.endswith('$'):
                return alt
            return f'![{alt}](<{url}>)' if url else f'[图片不可用：{alt}]'
        if name == 'blockquote':
            return '\n\n' + '\n'.join('> ' + line for line in inner.strip().splitlines()) + '\n\n'
        if name == 'li':
            marker = '1.' if node.parent.name == 'ol' else '-'
            return '\n' + marker + ' ' + inner.strip().replace('\n', '\n  ')
        if name in ('ul', 'ol'):
            return '\n' + inner + '\n\n'
        if name in ('video', 'source'):
            url = node.get('src', '')
            return f'\n[视频原链接](<{url}>)\n' if url else inner
        return inner

    return re.sub(r'\n{3,}', '\n\n', walk(soup)).strip() + '\n'


def safe_name(value, limit=60):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .')[:limit] or '未命名'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name):
        name = '_' + name
    return name


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def date_text(value):
    if not value:
        return ''
    try:
        return datetime.fromtimestamp(float(value), TZ).isoformat(timespec='seconds')
    except (ValueError, TypeError, OverflowError, OSError):
        return str(value)


class Archive:
    def __init__(self, output, author, images='remote', delay=2):
        output = Path(output).resolve()
        existing = [p for p in output.glob('*__' + author['url_token']) if (p / 'manifest.json').is_file()]
        if len(existing) > 1:
            raise ValueError('发现同一作者的多个归档目录，请指定一个输出目录整理后再运行')
        self.root = existing[0] if existing else output / (safe_name(author.get('name', author['url_token']), 36) + '__' + author['url_token'])
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = self.root / 'manifest.json'
        if manifest.exists():
            self.state = json.loads(manifest.read_text(encoding='utf-8'))
            if self.state['author']['url_token'] != author['url_token']:
                raise ValueError('目录内已有其他作者归档')
        else:
            self.state = {'schema': 1, 'author': {}, 'items': {}, 'columns': {}, 'streams': {}, 'complete': False, 'warnings': []}
        self.state['author'] = {k: author[k] for k in ('name', 'url_token', 'id', 'headline', 'answer_count', 'articles_count', 'columns_count') if k in author}
        self.images, self.delay = images, delay
        self.resources = requests.Session()  # Deliberately no cookies or auth headers.

    def is_owner(self, item):
        author = item.get('author') or {}
        if isinstance(author, str):
            return author in (self.state['author'].get('id'), self.state['author']['url_token'])
        return bool((author.get('url_token') and author['url_token'] == self.state['author']['url_token']) or
                    (author.get('urlToken') and author['urlToken'] == self.state['author']['url_token']) or
                    (author.get('id') and author['id'] == self.state['author'].get('id')))

    def local_image(self, url):
        digest = hashlib.sha256(url.encode()).hexdigest()[:24]
        existing = list((self.root / 'assets').glob(digest + '.*'))
        if existing:
            return existing[0].relative_to(self.root).as_posix()
        if url.startswith('data:'):
            header, encoded = url.split(',', 1)
            mime = header[5:].split(';')[0]
            data = base64.b64decode(encoded, validate=True)
        else:
            p = urlparse(url)
            host = p.hostname or ''
            if p.scheme not in ('http', 'https') or not (host == 'zhimg.com' or host.endswith('.zhimg.com') or host == 'zhihu.com' or host.endswith('.zhihu.com')):
                raise ValueError('图片域名不是知乎资源域名，保留原链接')
            time.sleep(self.delay)
            with self.resources.get(url, timeout=30, stream=True, allow_redirects=False) as r:
                if r.status_code != 200:
                    raise ValueError(f'图片 HTTP {r.status_code}')
                mime = r.headers.get('Content-Type', '').split(';')[0]
                chunks, size = [], 0
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > 20 * 1024 * 1024:
                        raise ValueError('图片大于 20MB')
                    chunks.append(chunk)
                data = b''.join(chunks)
        ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif', 'image/webp': '.webp', 'image/avif': '.avif'}.get(mime)
        if not ext or len(data) > 20 * 1024 * 1024:
            raise ValueError('不支持的图片格式或大小')
        target = self.root / 'assets' / (digest + ext)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
        return target.relative_to(self.root).as_posix()

    def save_item(self, item, kind, column=None):
        if not self.is_owner(item):
            return False
        item_id = str(item.get('id', ''))
        if not re.fullmatch(r'\d+', item_id):
            return False
        key = kind + ':' + item_id
        previous = self.state['items'].get(key, {})
        if previous.get('body_status') == 'full' and not item.get('content'):
            if column and column not in previous['columns']:
                previous['columns'].append(column)
            self.checkpoint()
            return True
        title = item.get('title') or item.get('question', {}).get('title') or f'{kind} {item_id}'
        content = clean_html(item.get('content', ''))
        has_body = bool(BeautifulSoup(content, 'html.parser').get_text(strip=True) or '<img' in content or '<video' in content)
        body_status = 'full' if has_body else 'missing'
        if item.get('body_status') in ('excerpt', 'restricted') or item.get('is_full') is False:
            body_status = item.get('body_status', 'excerpt')
        missing_assets = []
        soup = BeautifulSoup(content, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src:
                missing_assets.append('无图片地址')
                continue
            if self.images == 'local' or src.startswith('data:'):
                try:
                    img['src'] = self.local_image(src)
                except (ValueError, requests.RequestException, OSError):
                    missing_assets.append(src[:500] if not src.startswith('data:') else '内嵌图片保存失败')
        content = str(soup)
        markdown_soup = BeautifulSoup(content, 'html.parser')
        for tag in markdown_soup.find_all(['img', 'a']):
            attr = 'src' if tag.name == 'img' else 'href'
            value = tag.get(attr, '')
            if value.startswith('assets/'):
                tag[attr] = '../' + value
        folder = 'answers' if kind == 'answer' else 'articles'
        # Stable filenames make resuming and renamed titles safe.
        relative = f'{folder}/{item_id}.md'
        qid = item.get('question', {}).get('id')
        url = f'https://www.zhihu.com/question/{qid}/answer/{item_id}' if kind == 'answer' and qid else f'https://www.zhihu.com/answer/{item_id}' if kind == 'answer' else f'https://zhuanlan.zhihu.com/p/{item_id}'
        columns = list(previous.get('columns', []))
        c = item.get('column') or {}
        if isinstance(c, dict):
            slug = c.get('id') or c.get('slug') or c.get('url_token')
            if slug and str(slug) not in columns:
                columns.append(str(slug))
        if column and column not in columns:
            columns.append(column)
        record = {'id': item_id, 'key': key, 'kind': kind, 'title': str(title), 'url': url,
                  'created': date_text(item.get('created_time', item.get('created'))),
                  'updated': date_text(item.get('updated_time', item.get('updated'))),
                  'votes': item.get('voteup_count', 0), 'columns': columns,
                  'body_status': body_status, 'assets_missing': missing_assets,
                  'html': content, 'text': BeautifulSoup(content, 'html.parser').get_text(' ', strip=True),
                  'excerpt': str(item.get('excerpt', '')), 'markdown': relative}
        header = '# ' + str(title).replace('\n', ' ') + '\n\n' + f'作者：{self.state["author"].get("name", "")}  \n类型：{"回答" if kind == "answer" else "文章"}  \n来源：<{url}>  \n创建：{record["created"]}  \n更新：{record["updated"]}  \n赞同：{record["votes"]}\n\n'
        if body_status != 'full':
            header += '> 正文未完整取得。以下为可用内容或摘要，请通过原文链接核对。\n\n'
        md = html_markdown(str(markdown_soup)) if has_body else record['excerpt'] + '\n'
        atomic_text(self.root / relative, header + md)
        self.state['items'][key] = record
        self.checkpoint()
        return True

    def save_column(self, column):
        slug = str(column.get('id') or column.get('slug') or column.get('url_token') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', slug):
            return None
        record = {'id': slug, 'title': column.get('title', slug), 'description': BeautifulSoup(column.get('description', ''), 'html.parser').get_text(' ', strip=True),
                  'url': f'https://www.zhihu.com/column/{slug}'}
        self.state['columns'][slug] = record
        self.checkpoint()
        return slug

    def checkpoint(self):
        self.state['saved_at'] = datetime.now(TZ).isoformat(timespec='seconds')
        atomic_text(self.root / 'manifest.json', json.dumps(self.state, ensure_ascii=False, indent=2))

    def finish(self):
        selected = self.state.get('selected', ['answers', 'articles', 'columns'])
        relevant = [i for i in self.state['items'].values() if ('answers' if i['kind'] == 'answer' else 'articles') in selected or ('columns' in selected and i['columns'])]
        self.state['complete'] = bool(selected) and all(self.state['streams'].get(s, {}).get('status') == 'complete' for s in selected) and all(i['body_status'] == 'full' for i in relevant)
        def local_assets(item):
            images = BeautifulSoup(item.get('html', ''), 'html.parser').find_all('img')
            return not item['assets_missing'] and all(img.get('src', '').startswith('assets/') and (self.root / img['src']).is_file() for img in images)
        self.state['offline_complete'] = all(local_assets(i) for i in relevant) and self.images == 'local'
        self.checkpoint()
        for slug, c in self.state['columns'].items():
            entries = [i for i in self.state['items'].values() if slug in i['columns']]
            text = f'# {c["title"]}\n\n{c["description"]}\n\n原专栏：<{c["url"]}>\n\n这里只列出目标作者本人的文章。\n\n'
            text += '\n'.join(f'- [{i["title"].replace("[", "").replace("]", "")}](../{i["markdown"]})' for i in entries)
            atomic_text(self.root / 'columns' / f'{slug}.md', text + '\n')
        summary = {'author': self.state['author'], 'selected': selected, 'complete': self.state['complete'],
                   'saved': {k: sum(i['kind'] == k for i in self.state['items'].values()) for k in ('answer', 'article')},
                   'columns': len(self.state['columns']), 'skipped_count': len(self.state.get('skipped', {})), 'skipped': list(self.state.get('skipped', {}).values()), 'missing_bodies': sum(i['body_status'] != 'full' for i in relevant),
                   'missing_assets': sum(len(i['assets_missing']) for i in relevant), 'streams': self.state['streams'], 'saved_at': self.state['saved_at']}
        atomic_text(self.root / 'report.json', json.dumps(summary, ensure_ascii=False, indent=2))
        data = dict(summary, items=list(self.state['items'].values()), column_list=list(self.state['columns'].values()))
        embedded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        page = TEMPLATE.read_text(encoding='utf-8')
        page = page.replace('$$TITLE$$', html.escape(self.state['author'].get('name', '知乎博主')))
        page = page.replace('$$STYLES$$', (TEMPLATE.parent / 'reader.css').read_text(encoding='utf-8'))
        page = page.replace('$$SCRIPT$$', (TEMPLATE.parent / 'reader.js').read_text(encoding='utf-8'))
        page = page.replace('$$DATA$$', embedded)
        atomic_text(self.root / 'index.html', page)
        return summary

    def pack(self):
        # Include only artifact files explicitly tracked by this archive.
        paths = ['index.html', 'manifest.json', 'report.json']
        paths += [i['markdown'] for i in self.state['items'].values()]
        paths += [f'columns/{slug}.md' for slug in self.state['columns']]
        paths += [p.relative_to(self.root).as_posix() for p in (self.root / 'assets').glob('*') if re.fullmatch(r'[0-9a-f]{24}\.(png|jpg|gif|webp|avif)', p.name)]
        target = self.root.parent / (self.root.name + '.zip')
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(set(paths)):
                path = (self.root / name).resolve()
                if not path.is_relative_to(self.root) or not path.is_file():
                    continue
                archive.write(path, self.root.name + '/' + name)
        return target
