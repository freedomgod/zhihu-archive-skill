import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts'))


def test_paid_and_deleted_articles_are_skipped_without_marking_api_failure_complete(tmp_path):
    from archive import Archive
    from client import CrawlError
    from zhihu_archive import collect
    class C:
        def items(self, token, stream):
            yield {'id': 50, 'author': {'id': 'u'}, 'paid_info': {'is_paid_content': True}, 'content': '<p>付费预览</p>'}
            yield {'id': 51, 'author': {'id': 'u'}, 'excerpt': '已删除'}
            yield {'id': 52, 'author': {'id': 'u'}, 'content': '<p>可见文章</p>'}
        def detail(self, item, kind):
            assert item['id'] == 51
            raise CrawlError('HTTP 404：接口访问失败')
    a = Archive(tmp_path, {'name': '测试', 'url_token': 'test', 'id': 'u', 'articles_count': 3})
    r = collect(C(), a, ['articles'])
    assert r['complete']
    assert r['saved']['article'] == 1
    assert r['skipped_count'] == 2
    assert not (a.root / 'articles' / '50.md').exists()


@pytest.mark.parametrize('restriction', [{'is_public': False}, {'is_paid': True}, {'paid_info': {'is_paid_content': True, 'is_purchased': True}}])
def test_detail_restrictions_are_skipped_even_if_purchased(tmp_path, restriction):
    from archive import Archive
    from zhihu_archive import collect
    class C:
        def items(self, token, stream):
            yield {'id': 60, 'author': {'id': 'u'}, 'excerpt': '摘要'}
        def detail(self, item, kind):
            return dict(item, content='<p>付费或私密内容</p>', **restriction)
    a = Archive(tmp_path, {'name': '测试', 'url_token': 'test', 'id': 'u'})
    r = collect(C(), a, ['articles'])
    assert r['complete'] and r['skipped_count'] == 1
    assert r['saved']['article'] == 0
    assert not (a.root / 'articles' / '60.md').exists()


@pytest.mark.parametrize('detail', ['404', 'paid'])
def test_refresh_removes_previously_public_content_now_skipped(tmp_path, detail):
    from archive import Archive
    from client import CrawlError
    from zhihu_archive import collect
    a = Archive(tmp_path, {'name': '测试', 'url_token': 'test', 'id': 'u'})
    a.save_item({'id': 70, 'author': {'id': 'u'}, 'content': '<p>旧正文</p>'}, 'article')
    class C:
        def items(self, token, stream):
            yield {'id': 70, 'author': {'id': 'u'}, 'excerpt': '摘要'}
        def detail(self, item, kind):
            if detail == '404':
                raise CrawlError('HTTP 404')
            return dict(item, content='<p>旧正文</p>', paid_info={'is_paid_content': True})
    result = collect(C(), a, ['articles'], refresh=True)
    assert result['skipped_count'] == 1 and result['saved']['article'] == 0
    assert not (a.root / 'articles' / '70.md').exists()
    assert '旧正文' not in (a.root / 'index.html').read_text(encoding='utf-8')
