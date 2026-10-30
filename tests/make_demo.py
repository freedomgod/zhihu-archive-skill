"""Create conspicuously labelled artificial data for offline reader QA."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'zhihu-archive' / 'scripts'))
from archive import Archive

root = Path(__file__).resolve().parents[1]
author = {'name': '示例博主', 'url_token': 'reader-demo', 'id': 'demo', 'headline': '人工演示数据，用于验证归档网页；不是任何真实知乎博主的内容。'}
a = Archive(root / 'output' / 'demo', author)
titles = ['如何建立自己的阅读与思考习惯？', '把长期记录变成有用的知识', '为什么有些问题值得反复追问？', '读书时，怎样留下可重用的笔记？', '在复杂信息中寻找清晰的判断', '保持专注的一些小方法']
for n in range(26):
    a.save_item({'id': n + 1, 'author': {'id': 'demo'}, 'question': {'id': n + 100, 'title': titles[n % len(titles)]}, 'created_time': 1704067200 + n * 1800000, 'updated_time': 1724067200 + n * 1800000, 'voteup_count': 120 + n * 37, 'content': '<p>这是一段人工编写的演示文字，用于测试本地阅读页。</p><h2>从一个具体的问题开始</h2><p>把阅读时想到的问题写下来，比单纯收藏链接更容易再次找到思路。每一次记录都可以包含三个部分：问题、证据，以及还没有解决的疑问。</p><blockquote><p>好的笔记可以让下一次阅读少绕一点路。</p></blockquote><p>搜索可以匹配全文中的“专注”“证据”等关键词，也可以按回答、文章、年份和专栏筛选。正文在网页中完整保存，使用过程中不需要访问外部服务器。</p><h2>给下一次阅读留下线索</h2><ol><li>保留原文来源。</li><li>写下自己的理解。</li><li>记录需要核对的证据。</li></ol><p>本段文字仅为测试示例，不是真实知乎作品。</p>'}, 'answer')
a.save_column({'id': 'notes', 'title': '阅读笔记（测试专栏）', 'description': '人工演示专栏'})
for n in range(3):
    a.save_item({'id': 100 + n, 'author': {'id': 'demo'}, 'title': ['一份安静的阅读清单', '怎样整理一个博主的全部内容', '从文字到可查找的知识'][n], 'created': 1754067200 + n * 100000, 'voteup_count': 90 + n, 'content': '<h2>文章演示</h2><p>文章内容可以保存为 Markdown，同时在网页中按专栏筛选。</p><table><tr><th>形式</th><th>用途</th></tr><tr><td>Markdown</td><td>编辑、长期保存</td></tr><tr><td>静态网页</td><td>搜索、阅读</td></tr></table><pre><code>这是演示代码块\narchive → search → read</code></pre>'}, 'article', 'notes')
a.state['selected'] = ['answers', 'articles', 'columns']
a.state['streams'] = {s: {'status': 'complete', 'source': 'synthetic QA fixture'} for s in a.state['selected']}
a.finish()
print(a.root / 'index.html')
