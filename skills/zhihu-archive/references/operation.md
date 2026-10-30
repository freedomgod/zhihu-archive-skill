# 操作与可访问内容边界

## 内容类型

| 用户选择 | 参数 |
|---|---|
| 仅回答 | `--types answers` |
| 仅文章 | `--types articles` |
| 仅专栏及作者本人专栏文章 | `--types columns` |
| 回答和文章 | `--types answers articles` |
| 全部 | `--types all` |

选择文章不会自动扫描专栏；选择专栏会取得专栏内该作者的文章，不包含其他共同作者。只选一种类型时，输出是本次所选范围；复用已有归档仍保留早先保存的其他类型。

## 输出

```text
<output>/作者昵称__url_token/
  answers/数字ID.md
  articles/数字ID.md
  columns/专栏ID.md
  assets/内容地址哈希.图片扩展名
  manifest.json
  report.json
  index.html
```

正文保留原链接、创建/更新时间（Asia/Shanghai）、赞同数。HTML 阅读副本会清理可执行标签和事件属性；保留段落、列表、引用、代码、表格、图片、公式替代文字。Markdown 中公式取 `data-tex`/alt；复杂合并表格会平展，复杂内容通过原链接核对。

ZIP 按清单与受控资源文件列表建立，不递归压缩作者目录；Cookie、浏览器资料和其他用户文件不会加入压缩包。内容仍归原作者所有。

## 运行模式与分页

HTTP 模式使用以下只读接口：
- `GET /api/v4/members/{token}` 确认作者。
- `GET /api/v4/members/{token}/answers|articles` 枚举回答与文章列表。
- `GET /api/v4/members/{token}/column-contributions` 枚举专栏贡献，提取返回条目的 `column` 对象；主页确认 `columns_count=0` 时，无自有专栏可枚举。
- `GET /api/v4/answers/{id}`、`/articles/{id}` 补正文。
- `GET /api/v4/columns/{slug}/items` 枚举专栏。

这些是网站内部接口，并非稳定的正式公开 API。脚本使用 `data`/`paging.next`/`paging.is_end`；知乎返回的旧 HTTP 下一页链接先转换为 HTTPS 再请求，登录凭据始终通过 HTTPS 发送。API 地址必须保持知乎域名及接口路径，分页循环、空页无结束标记和格式变化均是失败。可见数量低于主页计数时保留计数差异提示，不承诺不可见内容完整。

浏览器模式读取真实页面网络响应，解析 `js-initialData` 中实体引用，并滚动回答、文章或专栏页。缺正文时新开详情标签，避免破坏列表位置。连续五次没有新条目或响应但没有收到 `is_end`，标记部分完成；`--max-scrolls` 达上限同样不完整。网站 UI/响应结构变化时需要有证据地调整适配器。

默认请求间隔两秒，无并行请求；网络和 5xx 最多三次尝试。401、403、429 停止后续分类，保留当前文件。详情 404/410 跳过并记录。明确付费或 `is_public=false` 内容跳过；没有明确限制却缺正文的条目标记缺失，不能借此把解析失败当成非公开。

`--max-items` 是每类/每个专栏的测试上限；在枚举中达到限制不意味着全部取得。完整列表的最后一项刚好等于限制时允许正常完成。

## 资源

默认本地下载图片，最多 20MB/张，只接收常见栅格图片 MIME。知乎 CDN 下载不携带登录 Cookie；其他域名资源保留原链接。图像没有在线链接但含 base64 栅格数据时写本地文件。图片失败记录 `assets_missing`；`offline_complete` 与 `complete` 独立，远程图片模式不会宣称完整离线。

## 调试

- 登录 10001：停止自动化登录重复尝试，在正常 Chrome 的 Network 请求标头复制完整 Cookie 到本地 `.txt`；无需安装扩展或创建 JSON。
- Cookie 模式 403：检查会话是否过期；可使用 `--browser --cookie-file ...` 读取浏览器正常页面流程。浏览器仍 403 时请用户正常验证，保存失败结论。
- 浏览器资料被占用：关闭技能开的专用窗口再运行，勿关闭用户所有日常浏览器。
- `complete=false`：查看 report 中每类 `status`/`reason`、缺正文数与计数差异；按同一作者与输出目录重跑。
- 想同步更新正文：加 `--refresh`。默认补缺不会刷新以前已保存的赞同数与正文。

实际抓取依赖作者主页可访问、登录状态和网站当前接口。独立浏览器首次登录以及 Cookie 模式都需要实测；测试受阻时交付可运行工具并明确未完成全量抓取。
