"""Local authentication; credentials never enter an archive."""
import json
import os
import time
from pathlib import Path


def zhihu_domain(domain):
    domain = str(domain).lstrip('.').lower()
    return domain == 'zhihu.com' or domain.endswith('.zhihu.com')


def load_cookies(path):
    text = Path(path).read_text(encoding='utf-8-sig').strip()
    if text.startswith(('[', '{')):
        data = json.loads(text)
        rows = data.get('cookies', []) if isinstance(data, dict) else data
        return {c['name']: c['value'] for c in rows
                if zhihu_domain(c.get('domain', 'zhihu.com')) and c.get('name')}
    if '\t' in text:
        result = {}
        for line in text.splitlines():
            if line.startswith('#HttpOnly_'):
                line = line[len('#HttpOnly_'):]
            elif line.startswith('#'):
                continue
            fields = line.split('\t')
            if len(fields) == 7 and zhihu_domain(fields[0]):
                result[fields[5]] = fields[6]
        return result
    text = text.removeprefix('Cookie:').removeprefix('cookie:').strip()
    if '\n' in text or '\r' in text:
        raise ValueError('Cookie 请求头应为单行，或使用 JSON/Netscape 文件')
    result = {}
    for piece in text.split(';'):
        key, sep, value = piece.strip().partition('=')
        if sep and key:
            result[key] = value
    if not result:
        raise ValueError('没有可用的知乎 Cookie')
    return result


def default_profile():
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share')))
    return base / 'zhihu-archive' / 'browser-profile'


def launch_context(playwright, profile, channel='chrome', headless=False):
    profile = Path(profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    options = dict(user_data_dir=str(profile), headless=headless,
                   viewport={'width': 1280, 'height': 900}, locale='zh-CN')
    if channel != 'chromium':
        options['channel'] = channel
    return playwright.chromium.launch_persistent_context(**options)


def login(profile, channel='chrome', timeout=600):
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    with sync_playwright() as p:
        context = launch_context(p, profile, channel)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto('https://www.zhihu.com/signin', wait_until='domcontentloaded', timeout=60000)
            print('浏览器已打开。请在窗口中自行登录知乎；程序不会读取密码或验证码。', flush=True)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not context.pages:
                    return False
                if any(c['name'] == 'z_c0' and c['value'] for c in context.cookies('https://www.zhihu.com')):
                    print('已检测到登录 Cookie，登录资料已保存在专用本地目录。实际访问是否成功由抓取验证。', flush=True)
                    return True
                context.pages[0].wait_for_timeout(1500)
            print('等待登录超时；再次运行 login 即可继续。', flush=True)
            return False
        except PlaywrightError:
            print('登录窗口已关闭或加载失败；可重新运行或改用已导出的 Cookie 文件。', flush=True)
            return False
        finally:
            context.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='打开独立知乎登录窗口')
    parser.add_argument('--profile', type=Path, default=default_profile())
    parser.add_argument('--channel', choices=['msedge', 'chrome', 'chromium'], default='chrome')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    try:
        raise SystemExit(0 if login(args.profile, args.channel, args.timeout) else 2)
    except KeyboardInterrupt:
        print('登录已取消，已保存的本地浏览器资料仍可复用。')
        raise SystemExit(130)
