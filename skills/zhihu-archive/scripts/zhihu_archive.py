#!/usr/bin/env python3
"""CLI: login, crawl, rebuild and pack. Exit 2 means an incomplete archive."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from archive import Archive, TZ, atomic_text
from auth import default_profile, load_cookies, login
from client import APIClient, CrawlError, user_token


def auth_failure(error):
    return bool(re.search(r'401|403|429|登录|验证|限流', str(error)))


def restricted(item):
    paid = item.get('paid_info') or {}
    return bool((isinstance(paid, dict) and (paid.get('is_paid_content') or paid.get('is_paid')))
                or item.get('is_paid') or item.get('is_public') is False)


def collect(client, archive, selected, max_items=None, refresh=False):
    archive.state['selected'] = selected
    archive.state['complete'] = False
    archive.state.setdefault('skipped', {})
    for stream in selected:
        archive.state['streams'][stream] = {'status': 'pending'}
    archive.checkpoint()
    token, halted = archive.state['author']['url_token'], False
    unverified = 0

    def skip(item, kind, reason):
        item_id = str(item.get('id', ''))
        if not re.fullmatch(r'\d+', item_id):
            raise CrawlError('内容缺少有效数字 ID，停止处理')
        skip_key = kind + ':' + item_id
        archive.state['skipped'][skip_key] = {'kind': kind, 'id': item_id, 'reason': reason, 'stream': current_stream}
        archive.state['items'].pop(skip_key, None)
        old_path = archive.root / ('answers' if kind == 'answer' else 'articles') / (item_id + '.md')
        if old_path.exists() and old_path.resolve().is_relative_to(archive.root.resolve()):
            old_path.unlink()
        archive.checkpoint()
        return False

    def save(item, kind, column=None):
        nonlocal unverified
        if not archive.is_owner(item):
            if not item.get('author'):
                unverified += 1
            return False
        skip_key = kind + ':' + str(item.get('id'))
        if restricted(item):
            return skip(item, kind, '付费或明确非公开')
        prior = archive.state['items'].get(kind + ':' + str(item.get('id')), {})
        if not refresh and prior.get('body_status') == 'full':
            return archive.save_item(dict(item, content=''), kind, column)
        if not item.get('content') or item.get('is_full') is False:
            try:
                detail = client.detail(item, kind)
                item = dict(item, **detail)
            except CrawlError as error:
                if re.search(r'HTTP (404|410)', str(error)):
                    return skip(item, kind, '已删除或详情不可公开访问')
                archive.save_item(item, kind, column)
                if auth_failure(error):
                    raise
                archive.state['warnings'].append(f'{kind}:{item.get("id")}：{error}')
        if restricted(item):
            return skip(item, kind, '详情为付费或非公开内容')
        archive.state['skipped'].pop(skip_key, None)
        return archive.save_item(item, kind, column)

    for stream in selected:
        current_stream = stream
        if halted:
            archive.state['streams'][stream] = {'status': 'paused', 'reason': '前一分类需登录或验证，停止后续请求'}
            continue
        if stream == 'columns' and archive.state['author'].get('columns_count') == 0:
            archive.state['streams'][stream] = {'status': 'complete', 'seen': 0, 'skipped': 0, 'note': '作者主页确认没有自有专栏'}
            archive.checkpoint()
            continue
        count = 0
        unverified = 0
        archive.state['streams'][stream] = {'status': 'running', 'seen': 0}
        archive.checkpoint()
        print(f'正在抓取 {stream}…', flush=True)
        try:
            for item in client.items(token, stream):
                if max_items is not None and count >= max_items:
                    raise CrawlError('达到本次测试数量上限；未证明全部抓取完毕')
                if stream == 'columns':
                    slug = archive.save_column(item)
                    if not slug:
                        raise CrawlError('专栏缺少有效标识')
                    column_count = 0
                    for article in client.column_items(slug):
                        if max_items is not None and column_count >= max_items:
                            raise CrawlError('达到专栏文章测试数量上限，归档尚未完整')
                        if save(article, 'article', slug):
                            column_count += 1
                    count += 1
                else:
                    if save(item, 'answer' if stream == 'answers' else 'article'):
                        count += 1
                archive.state['streams'][stream]['seen'] = count
                archive.checkpoint()
            archive.state['streams'][stream] = {'status': 'complete', 'seen': count}
            if unverified:
                archive.state['streams'][stream].update(status='unverified_author', reason=f'{unverified} 个条目缺少可核对作者，未保存这些正文')
            expected = archive.state['author'].get({'answers': 'answer_count', 'articles': 'articles_count', 'columns': 'columns_count'}[stream])
            skipped = sum(x.get('stream') == stream for x in archive.state['skipped'].values())
            archive.state['streams'][stream]['skipped'] = skipped
            if isinstance(expected, int) and count + skipped != expected:
                archive.state['streams'][stream]['count_note'] = f'主页计数 {expected}，保存 {count}、跳过 {skipped}；可能存在隐藏内容或抓取期间更新'
                if count + skipped < expected:
                    archive.state['streams'][stream]['status'] = 'count_mismatch'
        except CrawlError as error:
            archive.state['streams'][stream] = {'status': 'blocked', 'seen': count, 'reason': str(error)}
            halted = auth_failure(error)
            print(f'{stream} 暂停：{error}', flush=True)
        except KeyboardInterrupt:
            archive.state['streams'][stream] = {'status': 'interrupted', 'seen': count, 'reason': '用户中断'}
            archive.finish()
            raise
        finally:
            archive.checkpoint()
    return archive.finish()


def parser():
    p = argparse.ArgumentParser(description='知乎博主本地归档：Markdown、静态阅读页、可选 ZIP')
    sub = p.add_subparsers(dest='command', required=True)
    auth = sub.add_parser('login', help='弹出独立浏览器，由本人登录')
    auth.add_argument('--profile', type=Path, default=default_profile())
    auth.add_argument('--channel', choices=['chrome', 'msedge', 'chromium'], default='chrome')
    auth.add_argument('--timeout', type=int, default=600)
    crawl = sub.add_parser('crawl', help='抓取指定博主')
    crawl.add_argument('--user', required=True, help='知乎主页链接或 url_token')
    crawl.add_argument('--expect-name', help='核对作者昵称，防止目标错误')
    crawl.add_argument('--types', nargs='+', choices=['answers', 'articles', 'columns', 'all'], default=['all'])
    crawl.add_argument('--cookie-file', type=Path)
    crawl.add_argument('--browser', action='store_true', help='读取正常浏览器页面加载的数据；也可导入 Cookie 到专用浏览器')
    crawl.add_argument('--profile', type=Path, default=default_profile())
    crawl.add_argument('--channel', choices=['chrome', 'msedge', 'chromium'], default='chrome')
    crawl.add_argument('--output', type=Path, default=Path('archives'))
    crawl.add_argument('--images', choices=['local', 'remote'], default='local')
    crawl.add_argument('--delay', type=float, default=2)
    crawl.add_argument('--max-items', type=int, help='每类测试上限，不代表完整抓取')
    crawl.add_argument('--max-scrolls', type=int, default=2000)
    crawl.add_argument('--refresh', action='store_true', help='重新取得已保存正文；默认只补缺')
    crawl.add_argument('--zip', action='store_true')
    for name in ('rebuild', 'pack'):
        command = sub.add_parser(name, help='从已有归档重新生成网页' if name == 'rebuild' else '生成不含登录资料的 ZIP')
        command.add_argument('folder', type=Path)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == 'login':
        return 0 if login(args.profile, args.channel, args.timeout) else 2
    if args.command in ('rebuild', 'pack'):
        state = json.loads((args.folder / 'manifest.json').read_text(encoding='utf-8'))
        store = Archive(args.folder.resolve().parent, state['author'])
        # Rebuilds must not upgrade prior resource completeness.
        store.images = 'local' if state.get('offline_complete') else 'remote'
        store.finish()
        print(store.pack() if args.command == 'pack' else store.root / 'index.html')
        return 0
    token = user_token(args.user)
    if args.max_items is not None and args.max_items < 1:
        raise CrawlError('--max-items 必须大于零')
    if args.delay < 0 or args.max_scrolls < 1:
        raise CrawlError('延迟不能为负，滚动上限必须大于零')
    selected = ['answers', 'articles', 'columns'] if 'all' in args.types else list(dict.fromkeys(args.types))
    store, client = None, None
    try:
        if args.cookie_file and not args.browser:
            client = APIClient(load_cookies(args.cookie_file), args.delay)
        else:
            from browser import BrowserClient
            client = BrowserClient(args.profile, args.channel, args.delay, args.max_scrolls)
            if args.cookie_file:
                client.context.add_cookies([{'name': k, 'value': v, 'domain': '.zhihu.com', 'path': '/', 'secure': True}
                                            for k, v in load_cookies(args.cookie_file).items()])
        profile = client.profile(token)
        if profile.get('url_token') != token:
            raise CrawlError('返回的作者标识与目标主页不一致')
        if args.expect_name and profile.get('name') != args.expect_name:
            raise CrawlError('返回的作者昵称与预期不符，停止抓取')
        store = Archive(args.output, profile, args.images, args.delay)
        # The authentication profile must never share an artifact directory.
        if args.profile.resolve().is_relative_to(store.root):
            raise CrawlError('登录资料目录必须放在博主归档目录之外')
        result = collect(client, store, selected, args.max_items, args.refresh)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f'阅读页：{store.root / "index.html"}')
        if args.zip:
            print(f'压缩包：{store.pack()}')
        return 0 if result['complete'] else 2
    except CrawlError as error:
        if store:
            store.finish()
        else:
            diagnostic = {'user_token': token, 'expected_name': args.expect_name, 'complete': False, 'saved': 0, 'reason': str(error), 'tested_at': datetime.now(TZ).isoformat(timespec='seconds')}
            atomic_text(args.output / f'{token}__failed-run.json', json.dumps(diagnostic, ensure_ascii=False, indent=2))
        raise
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('已中断，已保存内容可继续抓取。', file=sys.stderr)
        sys.exit(130)
    except (CrawlError, ValueError, OSError) as error:
        print(f'未完整完成：{error}', file=sys.stderr)
        sys.exit(2)
    except Exception:
        # Browser internals may contain request data; don't print raw traces.
        print('运行失败。请检查浏览器是否安装、资料目录是否被占用以及依赖是否齐全；已有内容保留。', file=sys.stderr)
        sys.exit(2)
