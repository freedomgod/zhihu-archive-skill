# 知乎博主归档 Skill

将指定知乎博主可访问的**回答、文章、专栏**保存为 Markdown、本地图片和可搜索的静态阅读页。阅读页可直接双击打开，支持全文搜索、分类、年份筛选和长文阅读；也可打包 ZIP。

这是遵循 [Agent Skills 格式](https://agentskills.io/specification)的技能，附带 Python 脚本，可在支持本地脚本执行的 Codex、Claude Code 等工具中使用，也可以直接运行命令行。

## 安装

### 通过 npx 安装（推荐）

需要 Node.js 22.20+、npm 和 Git。在需要使用技能的项目目录运行：

```bash
npx skills add freedomgod/zhihu-archive-skill --skill zhihu-archive
```

按提示选择使用的 AI 工具。指定安装到 Codex 并对所有项目生效：

```bash
npx skills add freedomgod/zhihu-archive-skill --skill zhihu-archive --agent codex --global
```

Windows 若不方便使用符号链接，可追加 `--copy`；PowerShell 若拦截 `npx.ps1`，改用 `npx.cmd`。完整参数见 [Skills CLI 官方文档](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)。

`skills` 是通用安装器，它从本 GitHub 仓库安装技能；**npx 不会安装 Python 或 Python 依赖，也不会自动获得知乎登录状态**。本项目不需要另行发布 npm 包。

### 下载 ZIP 或手动安装

- [下载独立技能 ZIP](https://github.com/freedomgod/zhihu-archive-skill/raw/refs/heads/main/dist/zhihu-archive.zip) · [SHA-256 校验值](dist/SHA256SUMS)
- 解压后将整个 `zhihu-archive` 文件夹放到 `~/.agents/skills/`（Codex 全局）或项目的 `.agents/skills/`。Windows 的 `~` 指用户目录，例如 `C:/Users/你的用户名`。
- 正确结构为 `.agents/skills/zhihu-archive/SKILL.md`。只复制 `SKILL.md` 会缺少脚本、阅读页和参考文档。
- 也可让 Codex 的 `$skill-installer` 安装本仓库中的 `skills/zhihu-archive`。技能未显示时重启 Codex；避免在多个扫描目录重复安装同名技能。

路径依据：[Codex 技能文档](https://learn.chatgpt.com/docs/build-skills)。

## 第一次使用

向 AI 工具提供作者主页、内容范围、输出目录和 **Cookie 文件的本地路径**：

```text
使用 $zhihu-archive，归档 https://www.zhihu.com/people/作者标识 的文章。
Cookie 文件在 D:/private/zhihu-cookie.txt，输出到 D:/archives。
先测试 3 篇，确认正文可读后继续全量归档，并生成 ZIP。
```

技能需要 Python 3.10+。让 AI 按技能中的 [环境准备说明](skills/zhihu-archive/references/setup.md)安装依赖并运行；macOS/Linux 通常使用 `python3`。Cookie 文件必须存在于**执行脚本的那台电脑**，云端环境不能直接读取你电脑上的路径。

### 如何提供 cookies

1. 在你平常使用的 Chrome/Edge 中登录知乎。
2. 按 F12 → **Network / 网络**，刷新知乎页面，选中发往 `https://www.zhihu.com/` 的请求。
3. 在 **Headers → Request Headers → Cookie** 中复制完整的 Cookie 值。
4. 保存为本地 UTF-8 文本文件，例如 `D:/private/zhihu-cookie.txt` 或 `~/.config/zhihu-archive/zhihu-cookie.txt`，只把文件路径告诉 AI。

文件内容形如 `name=value; another=value`，也接受 `Cookie:` 前缀。不要复制整个 cURL 命令、全部请求头或响应的 `Set-Cookie`。Cookie 相当于登录凭据，**不要贴进聊天、Issue、README 或提交到 GitHub**。每位使用者提供自己的登录状态，仓库和下载包不含作者的 cookies。

失效时在正常浏览器重新登录并更新本地文件。支持请求头文本、Netscape、JSON；详细步骤、专用浏览器登录和可选本地导出扩展见 [登录说明](skills/zhihu-archive/references/authentication.md)。不需要常规用户安装扩展。

## 不通过 AI，直接运行

克隆仓库并进入仓库目录后，以下命令适用于已安装依赖的 Python。建议先按 [环境准备说明](skills/zhihu-archive/references/setup.md)创建虚拟环境。

```bash
git clone https://github.com/freedomgod/zhihu-archive-skill.git
cd zhihu-archive-skill
python -m pip install -r skills/zhihu-archive/scripts/requirements.txt
python -X utf8 skills/zhihu-archive/scripts/zhihu_archive.py crawl --user "https://www.zhihu.com/people/作者标识" --types articles --cookie-file "/你的私有目录/zhihu-cookie.txt" --output "./archives" --max-items 3
```

将示例主页和 Cookie 路径替换为自己的值。所有平台后续命令均应使用所创建虚拟环境的解释器（Windows 为 `.venv/Scripts/python.exe`，macOS/Linux 为 `.venv/bin/python`）；未使用虚拟环境时，macOS/Linux 通常使用 `python3`。样本核对后移除 `--max-items 3`，追加 `--zip` 即可继续；重复运行会复用已有归档。因样本上限截断、仍有后续内容时，退出码 `2` 是“尚未完整”的预期结果。

| 内容范围 | 参数 |
| --- | --- |
| 仅文章 | `--types articles` |
| 仅回答 | `--types answers` |
| 仅专栏及该作者的专栏文章 | `--types columns` |
| 全部 | `--types all` |

只传 `--cookie-file` 走 HTTP 模式，无需安装浏览器。加入 `--browser` 可使用专用 Chrome/Edge 会话；使用 Playwright 自带 Chromium 时，需额外运行 `python -m playwright install chromium`，并传 `--channel chromium`。

## 结果与限制

每位博主一个目录，包含 `answers/`、`articles/`、`columns/`、`assets/`、`index.html`、`manifest.json` 和 `report.json`。双击 `index.html` 阅读；分享时保留整个目录，或使用生成的 ZIP，避免本地图片丢失。

- 支持断点补缺、ID 去重、`--refresh` 更新正文、重建阅读页及单独打包。
- `crawl` 退出码 `0` 表示所选可访问内容完整，`2` 表示尚未完整，`130` 表示中断。`rebuild` / `pack` 成功并不证明原抓取完整。
- 主页计数与接口可见数量不符时保留 `count_mismatch`；不会将未返回的条目编造成正文或断言为付费内容。
- 401/403/429 会停止后续分类；明确付费、非公开、404/410 条目会跳过并报告。支持正常登录和用户手动验证，不提供绕过访问限制的功能。
- 正文完整性与图片离线完整性分开报告。视频保留链接，复杂公式/表格需通过原文核对。
- 知乎内部接口会变化，登录状态也会过期，不能保证任何作者在任意时间都可全量抓取。

更多参数与排错见 [操作说明](skills/zhihu-archive/references/operation.md)。

## 项目结构与开发

```text
skills/zhihu-archive/
  SKILL.md                 # 标准 YAML 元数据与技能入口
  agents/openai.yaml       # Codex 显示信息（UTF-8）
  scripts/                 # Python 抓取及归档脚本
  references/              # 环境、登录与操作说明
  assets/                  # 阅读页和可选 Cookie 导出扩展
  LICENSE.txt
scripts/package_skill.py   # 按明确文件清单生成独立 ZIP
tests/                     # 离线自动化测试与人工阅读页样本
dist/                      # 独立技能 ZIP 和校验值
```

测试和构建步骤见 [验证说明](docs/testing.md)。运行产生的 cookies、浏览器资料、归档内容、缓存及本地诊断记录不属于公开源码。

## 许可

技能与代码采用 [MIT License](LICENSE)。归档内容的权利仍属于原作者，代码许可不授予他人内容的转载权。请仅归档自己有权访问的内容，遵守网站规则并控制请求频率（默认间隔两秒）。
