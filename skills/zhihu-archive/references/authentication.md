# 本地登录状态

## 推荐：复制请求头到本地文本文件

用户已经在正常 Chrome 登录知乎时，直接复用现有会话，不要求安装扩展或换用自动化浏览器登录。

1. 打开正常知乎页面，按 F12，选择 Network／网络，再刷新页面。
2. 选择发送到 `https://www.zhihu.com/` 的页面或接口请求。可在筛选框输入 `domain:www.zhihu.com`，排除图片、广告和其他网站。
3. 在 Headers／标头 → Request Headers／请求标头中找到 `Cookie`，复制完整值。例如本地文件格式为 `name=value; other=value`。`Cookie:` 前缀可保留，但不要复制整个请求标头区、响应的 `Set-Cookie` 或整个 cURL 命令。
4. 将它粘贴到 `.auth/zhihu-cookie.txt` 等私有本地文件并以 UTF-8 保存，向 AI 工具提供路径。文件必须在执行脚本的同一台电脑上；可先创建空文件并在编辑器中打开，方便用户粘贴，保留已有文件以免覆盖凭据。
5. 将路径传给 `--cookie-file <path>`，先确认作者与少量正文。只输出凭据是否可用和数量，不输出值，也不把文件内容读取到聊天上下文。

Cookie 代表账户登录状态。每位使用者提供自己的文件；不要向维护者发送 Cookie，不要贴到聊天、GitHub Issue、提交记录、截图或共享网盘。归档输出目录与凭据目录分开。仓库 `.gitignore` 只保护匹配的文件名和目录；文件保存在任意其他位置时仍需自行保护。更新 Cookie 后重跑原命令即可，无需重新安装技能；不再使用时可自行删除文件并在知乎管理登录会话。

应使用真正发送的请求，不使用只有 `Provisional headers are shown` 的失败请求。找不到 Cookie 时，确认选中了知乎请求且日常浏览器已经登录。用户自行复制的是浏览器发出的 Cookie 值，包含这个请求使用的 HttpOnly Cookie；`document.cookie` 无法读取全部 HttpOnly Cookie，因此不把在 Console 执行它作为完整 Cookie 的导出办法。[Chrome 官方 Cookie 调试说明](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/skills/cookie-debugging/SKILL.md)、[Network 请求标头](https://developer.chrome.com/docs/devtools/network/reference)。

## 其他已有输入

请求头文本、Netscape 文件、Cookie JSON 数组、`{"cookies":[...]}` 均可。JSON 必须含 name/value，domain 如提供则只接受知乎域名。JSON 只是兼容输入格式，手动复制流程不需要生成它。

用户主动希望弹窗登录时，可使用 `login --channel chrome --profile <private-dir>`。若出现 10001，停止重复自动化登录，改用上述请求头复制方式。资料目录与 `archives` 分离。

随附的 `assets/chrome-cookie-export` 仅供用户明确选择扩展导出时使用，不作为默认鉴权步骤。它只申请知乎 Cookie 与本地下载权限。用户手动加载并点击导出，不上传数据。

## 数据库与浏览器限制

Windows 常见数据库路径是 `%LOCALAPPDATA%/Google/Chrome/User Data/Default/Network/Cookies`，其他 Chrome 配置可能在 Profile 1 等目录。它是 SQLite 数据库，可能被浏览器锁定，其中值可能受 DPAPI 或应用绑定加密保护。保持浏览器的加密与安全设置，使用正常导出接口；不要为了抓取要求管理员解密、禁用加密或修改用户的日常配置。

依据：[Chrome 应用绑定加密](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)、[Chrome cookies API 与域权限](https://developer.chrome.com/docs/extensions/reference/api/cookies)、[Chrome 136 起默认资料目录的远程调试限制](https://developer.chrome.com/blog/remote-debugging-port)。这些限制说明单纯知道数据库路径、或给正在运行的默认 Chrome 加调试参数，不是可靠导出方案。
