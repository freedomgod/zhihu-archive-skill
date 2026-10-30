---
name: zhihu-archive
description: "Archive a Zhihu author's answers, articles or columns into Markdown and a searchable local reader. Use when users ask to back up or crawl a 知乎博主, select content types, use local login cookies, or update an existing local Zhihu archive."
license: MIT
metadata:
  author: freedomgod
  version: "1.0.0"
---

# 知乎博主归档

使用随附脚本归档目标作者可公开访问的回答、文章、专栏。每位作者一个文件夹，含 Markdown、本地图片、可双击打开的静态阅读页与完整性报告；可生成 ZIP。

## 选择范围与作者

- 按用户选择传入 `--types answers`、`articles`、`columns` 或任意组合；未指定时使用 `all`。
- 从主页 URL 取得 `url_token`。只有昵称时先搜索主页，再用知乎返回的 `name` 和 `url_token` 核对；不要仅凭搜索摘要宣布作者已确认。支持 `--expect-name` 检查。
- 专栏默认归档目录、简介及该博主本人的文章。同一文章按 ID 去重，可对应多个专栏；共同作者的正文不进入此作者归档。
- 跳过明确付费、非公开、404/410 的条目，报告 `skipped_count` 和原因。401/403/429 可能表示整个会话失效或限流，不能当成单篇非公开而跳过。

## 准备运行

从已加载的 `SKILL.md` 路径定位技能目录，使用 Python 3.10+。首次安装、缺依赖或跨平台运行时，先读 [references/setup.md](references/setup.md)，优先在用户工作目录使用虚拟环境。`npx skills add` 只安装技能文件，Python 依赖仍需安装。

```powershell
python -m pip install -r "<skill-dir>/scripts/requirements.txt"
python -X utf8 "<skill-dir>/scripts/zhihu_archive.py" --help
```

浏览器模式可使用已安装 Chrome/Edge；仅使用 bundled Chromium 时需要 `python -m playwright install chromium`。读取用户指定的本地 Cookie 文件，或复用技能专用浏览器登录目录。登录资料目录必须位于归档文件夹之外；不将凭据写入聊天、日志、报告或 ZIP。

## 登录与抓取

首次使用需要用户提供自己的本地 Cookie 文件路径，或已有的技能专用浏览器会话；技能不会自动读取日常浏览器的登录数据库。优先指导用户通过 F12 → Network → Headers 复制知乎请求的完整 `Cookie` 请求头值，保存为本地 UTF-8 `.txt` 文件；无需安装扩展或创建 JSON。获取或更新登录资料时读取 [references/authentication.md](references/authentication.md)。将路径传给脚本即可，避免通过 `cat`、`Get-Content` 或日志输出凭据正文；不要求将凭据贴入聊天。

用户需要重新登录时，可以弹出独立 Chrome，让用户自行登录：

```powershell
python "<skill-dir>/scripts/zhihu_archive.py" login --channel chrome --profile "<private-dir>/zhihu-browser"
```

检测到登录 Cookie 只说明会话已保存；随后访问作者主页才能验证实际可用性。遇到 `10001:请求参数异常，请升级客户端后重试`，停止反复尝试自动化登录，改用正常 Chrome 中复制的 Cookie 请求头。用户提供的 `Network/Cookies` 是加密数据库，不能直接传给 `--cookie-file`。

命令示例（替换作者和路径，先取得登录状态，再核对作者）：

```powershell
python -X utf8 "<skill-dir>/scripts/zhihu_archive.py" crawl --user "https://www.zhihu.com/people/<url_token>" --expect-name "<作者昵称>" --types answers articles columns --cookie-file "<private-dir>/zhihu-cookie.txt" --output "<output-dir>" --images local --zip
```

仅传 `--cookie-file` 使用只读 HTTP API；加入 `--browser` 将知乎 Cookie 导入专用浏览器，并读取页面正常加载的响应与详情正文。已有专用浏览器会话可省略 Cookie 参数。直接 API 被 403 阻断时，浏览器模式是可选的后续访问方式；不会伪造签名或解答验证码。需要人工验证时让用户在浏览器中完成。

参数和排错细节见 [references/operation.md](references/operation.md)。首次测试可用 `--max-items 3`，数量限制产生的结果必须明确是测试样本。

## 进度与阅读

- 每个条目落盘后更新 `manifest.json`。再次用相同作者和输出父目录运行，会复用原目录、补齐缺失正文；`--refresh` 重取已保存正文。作者改名仍按 `url_token` 找到原目录。
- 每次从第一页重新枚举，按 ID 去重，避免上次抓取后发布新内容导致旧 offset 漏项。只有明确分页结束才认为列表完整；页面不再加载也可能是失败。
- 摘要、没有作者证明的条目和缺失正文不算完整正文。详情仍不可得时记录缺失；不能用搜索缓存、转载或编造文本冒充原文。
- `report.json` 区分完整、失败、缺失和已跳过内容。页面与最终答复说明已保存数量、跳过数量、受阻原因；不能把离线测试数据说成真实抓取结果。
- `index.html` 内嵌数据、没有 CDN 依赖；双击打开即可搜索正文、按回答/文章/专栏/年份筛选和排序。左侧展示目标博主信息与筛选条件，右侧是内容目录；点击条目打开长文阅读视图。字体使用系统中文字体。页面是该博主所选内容的归档，不设置个人文库或收藏功能。
- `--images local` 尝试本地保存知乎图片及内嵌栅格图片；失败保留原地址并记录。视频只保留可用链接，不承诺完整离线视频。正文完整性与资源离线完整性分别记录。

已有归档可独立重建阅读页或压缩：

```powershell
python "<skill-dir>/scripts/zhihu_archive.py" rebuild "<author-folder>"
python "<skill-dir>/scripts/zhihu_archive.py" pack "<author-folder>"
```

交付本地阅读页链接、作者文件夹或 ZIP，报告真实测试结论。`crawl` 退出码 `0` 表示所选可访问内容抓取完整（允许报告中的明确跳过），`2` 表示未完整完成，`130` 表示用户中断。`rebuild` / `pack` 的 `0` 只表示本地重建/压缩成功，原抓取完整性仍以 `report.json` 为准。
