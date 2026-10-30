// Test the user's explicit export action with a fake Chrome API. No real cookies.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('skills/zhihu-archive/assets/chrome-cookie-export/popup.js','utf8');
async function run(cookies){
 let callback, exported, file, upload=0;
 const button={disabled:false,addEventListener:(event,cb)=>{callback=cb}},status={textContent:''};
 const context={document:{getElementById:id=>id==='export'?button:status},
 chrome:{cookies:{getAll:async query=>{assert.equal(query.domain,'zhihu.com');return cookies}},downloads:{download:async options=>{file=options;return 1}}},
 Blob:class{constructor(parts){exported=parts.join('')}},URL:{createObjectURL:()=> 'blob:local',revokeObjectURL:()=>{}},setTimeout:()=>{},fetch:()=>{upload++;throw Error('No uploads allowed')}};
 vm.runInNewContext(source,context);await callback();return{status:status.textContent,exported,file,upload};
}
(async()=>{
 const result=await run([{name:'z_c0',value:'fake',domain:'.zhihu.com'},{name:'unrelated',value:'fake',domain:'.example.com'}]);
 assert.equal(JSON.parse(result.exported).cookies.length,1);assert.equal(result.file.saveAs,true);assert.equal(result.upload,0);
 const empty=await run([]);assert.equal(empty.file,undefined);assert(empty.status.includes('未检测到'));
 const manifest=JSON.parse(fs.readFileSync('skills/zhihu-archive/assets/chrome-cookie-export/manifest.json','utf8'));
 assert.deepEqual(manifest.host_permissions,['https://*.zhihu.com/*']);
 console.log('Cookie exporter: local save, domain scope, explicit click, and no-login handling passed.');
})().catch(e=>{console.error(e);process.exit(1)});
