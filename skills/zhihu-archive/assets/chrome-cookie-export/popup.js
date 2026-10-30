'use strict';
document.getElementById('export').addEventListener('click', async () => {
  const button = document.getElementById('export'), status = document.getElementById('status');
  button.disabled = true;
  try {
    const cookies = (await chrome.cookies.getAll({domain: 'zhihu.com'})).filter(c => c.domain.replace(/^\./, '') === 'zhihu.com' || c.domain.endsWith('.zhihu.com'));
    if (!cookies.some(c => c.name === 'z_c0' && c.value)) {
      status.textContent = '未检测到知乎登录 Cookie，请先在当前 Chrome 中登录。';
      return;
    }
    const url = URL.createObjectURL(new Blob([JSON.stringify({cookies}, null, 2)], {type: 'application/json'}));
    try {
      await chrome.downloads.download({url, filename: 'zhihu-cookies.json', saveAs: true});
      status.textContent = '已开始保存。请将文件路径提供给归档工具。';
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (error) {
      URL.revokeObjectURL(url);
      throw error;
    }
  } catch (error) {
    status.textContent = '未导出：请确认扩展拥有知乎 Cookie 权限，或重新打开弹窗。';
  } finally {
    button.disabled = false;
  }
});
