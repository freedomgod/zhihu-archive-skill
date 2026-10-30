# 环境准备

技能目录指包含 `SKILL.md` 的 `zhihu-archive` 文件夹。从已加载的技能路径定位它；不要假定安装在某台电脑的固定位置。脚本、`assets/` 和 `references/` 必须一起保留。

## 依赖与解释器

需要 Python 3.10+ 及访问知乎的网络。Node.js 仅供 `npx skills` 安装技能，抓取本身由 Python 执行。安装技能后，检查依赖是否存在；首次使用时在用户工作目录创建虚拟环境。

Windows PowerShell（将路径替换为实际技能目录）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r "C:/实际路径/zhihu-archive/scripts/requirements.txt"
.\.venv\Scripts\python.exe -X utf8 "C:/实际路径/zhihu-archive/scripts/zhihu_archive.py" --help
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r "/实际路径/zhihu-archive/scripts/requirements.txt"
.venv/bin/python -X utf8 "/实际路径/zhihu-archive/scripts/zhihu_archive.py" --help
```

后续命令使用同一个虚拟环境的解释器；无需执行环境激活脚本，也无需修改 PowerShell 执行策略。中文终端/日志建议使用 `-X utf8`。仅 HTTP Cookie 模式不需要下载浏览器。

## 浏览器模式（按需）

系统已有 Chrome 时可用默认 `--channel chrome`；Edge 使用 `--channel msedge`。没有这两种浏览器时安装 Playwright Chromium：

```bash
python -m playwright install chromium
```

此处 `python` 代表上一步的虚拟环境解释器；运行技能时加入 `--channel chromium`。Linux 如缺系统库，按 Playwright 的错误提示处理依赖。浏览器模式需要可用桌面和用户完成登录/验证；无桌面的环境优先使用 Cookie HTTP 模式。

## 首次运行

确认作者 URL、所选范围、输出父目录，以及 Cookie 文件路径或已有专用浏览器会话。没有登录资料时，先按 [authentication.md](authentication.md)让用户在本地保存 Cookie，再进行少量测试。提供路径已经足够，避免把文件内容读入聊天或工具输出。

`--max-items 3` 在仍有后续内容时返回退出码 `2`，表示样本未覆盖全部内容。读取 `report.json` 区分样本限制、登录失败、缺正文和计数差异；核对样本后移除上限继续。只有用户已经要求全量时才继续全量抓取。
