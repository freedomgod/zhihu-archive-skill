# 验证与发布

## 本地自动化检查

从仓库根目录运行（macOS/Linux 可用 `python3`）：

```bash
python -m pip install -r requirements-dev.txt
python -X utf8 -m pytest tests -q
node tests/test_exporter.cjs
python -X utf8 tests/make_demo.py
python -X utf8 tests/check_reader.py
python -X utf8 scripts/package_skill.py
```

阅读页检查默认使用已安装的 Chrome；设置 `ZHIHU_TEST_BROWSER=chromium` 后可以改用 Playwright Chromium，先运行 `python -m playwright install chromium`。所有常规测试均使用人工数据，不读取真实 cookies，也不请求知乎。测试生成物位于 `output/`，不提交。

测试覆盖 Cookie 格式与域隔离、分页、会话错误停止、正文与摘要区分、续抓、专栏作者过滤、付费/非公开条目跳过、HTML 清理、资源离线完整性与归档 ZIP 凭据隔离。发布检查额外验证 UTF-8 技能元数据，以及向技能源目录注入假凭据后，发布 ZIP 仍排除这些文件且解压后的命令行可运行。

## 真实使用证据与边界

2026-10-12 的本地真实验证归档了同一作者的 238 个回答、20 篇文章及 9 张图片；两种排序返回相同 ID 集合。主页计数比可见列表各多一条，结果保留 `complete=false` / `count_mismatch`，没有把不可见条目推断为付费或私密。

这是历史验证记录，不是对当前接口或所有作者的保证。本次发布不需要重新抓取，也不公开该作者正文、用户 Cookie 或个人浏览器资料。

## 构建与发布文件

`scripts/package_skill.py` 只读取列出的技能源文件，输出 `dist/zhihu-archive.zip` 与 `dist/SHA256SUMS`。ZIP 内包含完整 `zhihu-archive/` 文件夹，保留许可证；元数据使用 UTF-8，压缩包可重复构建。添加新的运行依赖文件时同步更新打包清单。

`.gitignore` 排除 `.auth/`、`archives/`、`output/`、`local-notes/`、虚拟环境和常见凭据文件。发布前仍需检查 `git diff --cached --name-only`，只提交技能、测试、文档和受控发布包。

检查安装器发现技能：

```bash
npx skills add . --list
```

用临时项目目录验证安装，避免覆盖日常使用的技能：

```bash
npx skills add freedomgod/zhihu-archive-skill --skill zhihu-archive --agent codex --copy --yes
```

这里不传 `--global`，安装范围就是临时项目。安装成功后，确认 `SKILL.md`、脚本、模板和参考文档齐全，并运行脚本的 `crawl --help`。
