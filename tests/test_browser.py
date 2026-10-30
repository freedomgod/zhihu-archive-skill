import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts'))


def test_initial_state_resolves_entity_references():
    from browser import hydrate
    entities = {'users': {'u': {'id': 'u', 'urlToken': 'person'}}, 'questions': {'q': {'id': 7, 'title': '问题'}}}
    item = hydrate({'id': 1, 'author': 'u', 'question': 'q'}, entities)
    assert item['author']['url_token'] == 'person'
    assert item['question']['title'] == '问题'


def test_missing_author_is_reported_incomplete(tmp_path):
    from archive import Archive
    from zhihu_archive import collect
    class C:
        def items(self, token, stream):
            yield {'id': 1, 'content': '<p>没有作者证明的正文</p>'}
    a = Archive(tmp_path, {'name': '测试', 'url_token': 'test'})
    result = collect(C(), a, ['answers'])
    assert not result['complete']
    assert result['streams']['answers']['status'] == 'unverified_author'


def test_browser_state_paid_and_visibility_flags_are_normalized():
    from browser import normalize
    item = normalize({'paidInfo': {'isPaidContent': True, 'isPurchased': True}, 'isPublic': False, 'isFull': False})
    assert item['paid_info']['is_paid_content']
    assert item['is_public'] is False and item['is_full'] is False
