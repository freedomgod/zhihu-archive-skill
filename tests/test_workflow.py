import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts'))


def workflow():
    p = Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts' / 'zhihu_archive.py'
    assert p.exists(), 'crawl workflow is not implemented'
    import zhihu_archive
    return zhihu_archive


class Client:
    def items(self, token, stream):
        if stream == 'answers':
            yield {'id': 10, 'author': {'id': 'owner'}, 'content': '<p>回答正文</p>', 'question': {'id': 1, 'title': '测试问题'}}
            from client import CrawlError
            raise CrawlError('HTTP 403：受阻')
        raise AssertionError('403 后不能继续发送其他分类请求')


def test_workflow_retains_data_and_stops_all_streams_on_auth_error(tmp_path):
    w = workflow()
    from archive import Archive
    archive = Archive(tmp_path, {'name': '测试', 'id': 'owner', 'url_token': 'owner'})
    result = w.collect(Client(), archive, ['answers', 'articles', 'columns'])
    assert result['saved']['answer'] == 1
    assert not result['complete']
    assert result['streams']['answers']['status'] == 'blocked'
    assert result['streams']['articles']['status'] == 'paused'


def test_column_only_collects_owner_and_avoids_duplicate_body(tmp_path):
    w = workflow()
    from archive import Archive
    archive = Archive(tmp_path, {'name': '测试', 'id': 'owner', 'url_token': 'owner'})
    class C:
        def items(self, token, stream):
            assert stream == 'columns'
            yield {'id': 'invest', 'title': '测试专栏'}
        def column_items(self, column):
            yield {'id': 30, 'author': {'id': 'owner'}, 'title': '本人文章', 'content': '<p>正文</p>'}
            yield {'id': 31, 'author': {'id': 'other'}, 'title': '共同作者', 'content': '<p>别人的正文</p>'}
    result = w.collect(C(), archive, ['columns'])
    assert result['complete']
    assert result['saved']['article'] == 1
    assert archive.state['items']['article:30']['columns'] == ['invest']


def test_missing_body_cannot_be_reported_complete(tmp_path):
    w = workflow()
    from archive import Archive
    archive = Archive(tmp_path, {'name': '测试', 'id': 'owner', 'url_token': 'owner'})
    class C:
        def items(self, token, stream):
            yield {'id': 33, 'author': {'id': 'owner'}, 'title': '仅摘要', 'excerpt': '摘要'}
        def detail(self, item, kind):
            return item
    result = w.collect(C(), archive, ['articles'])
    assert not result['complete']
    assert result['missing_bodies'] == 1


def test_author_rename_reuses_directory(tmp_path):
    from archive import Archive
    a = Archive(tmp_path, {'name': '旧名字', 'url_token': 'owner'})
    a.checkpoint()
    b = Archive(tmp_path, {'name': '新名字', 'url_token': 'owner'})
    assert a.root == b.root


def test_verified_zero_columns_does_not_call_nonexistent_list(tmp_path):
    w = workflow()
    from archive import Archive
    a = Archive(tmp_path, {'name': '测试', 'id': 'owner', 'url_token': 'owner', 'columns_count': 0})
    class C:
        def items(self, token, stream):
            raise AssertionError('明确零个自有专栏时不应调用列表接口')
    result = w.collect(C(), a, ['columns'])
    assert result['complete'] and result['columns'] == 0
    assert result['streams']['columns']['status'] == 'complete'
