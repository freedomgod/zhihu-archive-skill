'use strict';
const data=JSON.parse(document.getElementById('archive-data').textContent);
const $=id=>document.getElementById(id),PAGE_SIZE=20,dialog=$('reading-dialog');
let kind='all',page=0,theme='light',lastTrigger=null;
try{theme=localStorage.getItem('zhihu-archive:theme')||'light'}catch(e){}
document.documentElement.dataset.theme=theme;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const shortDate=value=>value?value.slice(0,10):'日期未记录';
const titleFor=id=>(data.column_list.find(c=>c.id===id)||{}).title||id;
const authorName=data.author.name||data.author.url_token;
const isDemo=Object.values(data.streams||{}).some(s=>s.source==='synthetic QA fixture');
$('author').textContent=authorName;
$('headline').textContent=data.author.headline||'回答、文章与专栏的本地归档。';
$('profile-link').href='https://www.zhihu.com/people/'+data.author.url_token;
$('answers').textContent=$('answer-count').textContent=data.saved.answer;
$('articles').textContent=$('article-count').textContent=data.saved.article;
$('columns').textContent=data.columns;
$('total-count').textContent=data.items.length;
$('archive-date').textContent='归档于 '+shortDate(data.saved_at);
$('status').textContent=data.complete?'所选可访问内容已保存':'抓取尚未完成';
if(data.complete)$('status').classList.add('complete');
if(isDemo){$('status').textContent='人工演示 · 非真实知乎内容';$('profile-link').hidden=true;}
const selectedLabels={answers:'回答',articles:'文章',columns:'专栏'};
$('scope-note').textContent='本次范围：'+(data.selected||[]).map(s=>selectedLabels[s]||s).join('、')+'。目录显示已保存的内容。';
const streamStates=Object.values(data.streams||{});
if(!data.complete&&!data.missing_bodies&&streamStates.length&&streamStates.every(s=>['complete','count_mismatch'].includes(s.status))){
  $('status').textContent='可访问列表已保存 · 主页存在计数差异';
  const notes=Object.entries(data.streams).filter(([,s])=>s.count_note).map(([name,s])=>(selectedLabels[name]||name)+'：'+s.count_note);
  $('scope-note').textContent+=' '+notes.join('。')+'。差异条目未在列表返回，原因尚未确认。';
}
if(data.skipped_count){$('skip-note').hidden=false;$('skip-note').textContent='已跳过 '+data.skipped_count+' 篇付费或非公开内容。'}
if(!data.items.length&&!data.complete){$('scope-note').textContent+=' 尚未取得正文；当前目录为空。'}
$('footnote').textContent=data.items.length+' 篇已保存内容 · 可离线浏览';
const colids=new Set(data.items.flatMap(i=>i.columns));data.column_list.forEach(c=>colids.add(c.id));
[...colids].forEach(id=>{const o=el('option',titleFor(id));o.value=id;$('column').append(o)});
if(!colids.size)$('column-label').hidden=true;
[...new Set(data.items.map(i=>(i.created||'').slice(0,4)).filter(Boolean))].sort().reverse().forEach(y=>{const o=el('option',y+' 年');o.value=y;$('year').append(o)});

function filtered(){
  const words=$('query').value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const items=data.items.filter(i=>(kind==='all'||kind===i.kind)&&(!$('column').value||i.columns.includes($('column').value))&&(!$('year').value||(i.created||'').startsWith($('year').value))&&words.every(w=>(i.title+' '+i.text+' '+i.excerpt).toLocaleLowerCase().includes(w)));
  const sort=$('sort').value;
  items.sort((a,b)=>sort==='votes'?Number(b.votes||0)-Number(a.votes||0):sort==='oldest'?(a.created||'').localeCompare(b.created||''):sort==='updated'?(b.updated||b.created||'').localeCompare(a.updated||a.created||''):(b.created||'').localeCompare(a.created||''));
  return items;
}

function render(){
  const items=filtered(),pages=Math.max(1,Math.ceil(items.length/PAGE_SIZE));
  page=Math.min(page,pages-1);
  $('catalog-title').textContent=kind==='answer'?'回答':kind==='article'?'文章':'全部内容';
  $('count').textContent=items.length+' 篇内容'+(data.missing_bodies?' · '+data.missing_bodies+' 篇正文待补齐':'');
  $('list').replaceChildren();
  if(!items.length)$('list').append(el('div',data.items.length?'没有匹配的内容。试试其他关键词或筛选条件。':'尚未取得正文。完成抓取后，回答和文章会显示在这里。','empty'));
  items.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE).forEach(i=>{
    const button=el('button',undefined,'entry');
    button.dataset.key=i.key;button.setAttribute('aria-label','阅读：'+i.title);button.setAttribute('aria-haspopup','dialog');
    const top=el('div',undefined,'entry-top');
    top.append(el('span',i.kind==='answer'?'回答':'文章','kind'+(i.kind==='article'?' article':'')),el('span',shortDate(i.created)));
    if(i.columns.length)top.append(el('span','专栏收录'));
    button.append(top,el('h3',i.title,'entry-title'),el('p',i.text.slice(0,130)||i.excerpt||'正文待补齐','entry-summary'));
    const foot=el('div',undefined,'entry-footer');
    foot.append(el('span',Number(i.votes||0).toLocaleString()+' 赞同'),el('span',i.body_status==='full'?'阅读全文 ↗':'查看已保存内容 ↗','entry-read'));
    button.append(foot);
    button.onclick=()=>{lastTrigger=button;history.pushState(null,'','#'+encodeURIComponent(i.key));show(i)};
    $('list').append(button);
  });
  $('page-number').textContent='第 '+(page+1)+' / '+pages+' 页';
  $('prev').disabled=page===0;$('next').disabled=page>=pages-1;
}

function show(i){
  const reader=$('reader');reader.replaceChildren();
  $('reading-author').textContent=authorName;
  const meta=el('div',undefined,'article-meta');
  meta.append(el('span',i.kind==='answer'?'回答':'文章','kind'),el('span',shortDate(i.created)),el('span',Number(i.votes||0).toLocaleString()+' 赞同'));
  const title=el('h2',i.title);title.id='reading-title';
  reader.append(meta,title);
  const tools=el('div',undefined,'reading-tools');
  const md=el('a','下载 Markdown');md.href=encodeURI(i.markdown);md.download=i.markdown.split('/').pop();
  const origin=el('a','查看知乎原文 ↗');origin.href=i.url;origin.target='_blank';origin.rel='noopener noreferrer';
  tools.append(md);tools.append(isDemo?el('span','人工演示内容'):origin);reader.append(tools);
  if(i.body_status!=='full')reader.append(el('div','正文尚未完整取得。以下为当前可用内容或摘要，可通过原文链接核对。','notice'));
  if(i.assets_missing.length)reader.append(el('div',i.assets_missing.length+' 张图片未能保存到本地，保留可用原链接。','notice'));
  const body=el('div',undefined,'body');
  if(i.html)body.innerHTML=i.html;else body.textContent=i.excerpt||'暂未取得正文。';
  reader.append(body);
  const end=el('div',undefined,'article-end');
  end.append(el('div','更新于 '+shortDate(i.updated||i.created)));
  if(i.columns.length)end.append(el('div','收录专栏：'+i.columns.map(titleFor).join('、')));
  end.append(el('div','归档副本可能与知乎最新版本不同，请以原文为准。'));
  reader.append(end);reader.scrollTop=0;
  if(!dialog.open)dialog.showModal();
  document.body.style.overflow='hidden';
}

function closeReader(){
  if(dialog.open)dialog.close();
  history.replaceState(null,'',location.pathname+location.search);
}
dialog.addEventListener('close',()=>{document.body.style.overflow='';if(lastTrigger&&lastTrigger.isConnected)lastTrigger.focus()});
dialog.addEventListener('cancel',event=>{event.preventDefault();closeReader()});
dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeReader()}});
$('close-reader').onclick=closeReader;
$('print-reader').onclick=()=>window.print();
document.querySelectorAll('[data-kind]').forEach(button=>button.onclick=()=>{
  kind=button.dataset.kind;page=0;
  document.querySelectorAll('[data-kind]').forEach(t=>t.setAttribute('aria-pressed',String(t===button)));
  render();
});
let timer;
$('query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{page=0;render()},140)};
['column','year','sort'].forEach(id=>$(id).onchange=()=>{page=0;render()});
$('prev').onclick=()=>{page--;render();$('workspace').scrollIntoView({block:'start'})};
$('next').onclick=()=>{page++;render();$('workspace').scrollIntoView({block:'start'})};
$('theme').onclick=()=>{theme=theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;try{localStorage.setItem('zhihu-archive:theme',theme)}catch(e){}};
function hashOpen(){
  try{const id=decodeURIComponent(location.hash.slice(1)),i=data.items.find(x=>x.key===id);if(i)show(i);else if(dialog.open)dialog.close()}catch(e){}
}
render();hashOpen();window.addEventListener('popstate',hashOpen);window.addEventListener('hashchange',hashOpen);
