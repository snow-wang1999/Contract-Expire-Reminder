const {chromium}=require('playwright');const path=require('path'),fs=require('fs');
(async()=>{
  const [oldHtml,newHtml,dir]=process.argv.slice(2);const b=await chromium.launch();
  const run=async(html,fn)=>{const p=await b.newPage();await p.goto('file://'+path.resolve(html));await p.evaluate(()=>{const i=document.createElement('input');i.type='file';i.id='tst';document.body.appendChild(i)});const out={};
    for(const f of fs.readdirSync(dir)){await p.setInputFiles('#tst',path.join(dir,f));out[f]=await p.evaluate(fn)}await p.close();return out};
  const oldR=await run(oldHtml,async()=>{const f=document.getElementById('tst').files[0];try{return JSON.stringify(await u_readRows(f,null))}catch(e){return 'ERR '+e.message}});
  const newR=await run(newHtml,async()=>{const f=document.getElementById('tst').files[0];const csv=/\.csv$/i.test(f.name);try{const w=JSON.stringify(await u_readRows(f,null));let m=await u_parseOnMain(f,csv,null);if(!csv)m[0]=m[0].map(h=>String(h).trim());m=JSON.stringify(m);return w===m?w:'WORKER/MAIN MISMATCH '+w+' vs '+m}catch(e){return 'ERR '+e.message}});
  for(const f of Object.keys(newR)){const same=oldR[f]===newR[f];console.log((same?'SAME ':'DIFF ')+f);if(!same){console.log('  old:',String(oldR[f]).slice(0,600));console.log('  new:',String(newR[f]).slice(0,600))}else console.log('  ',newR[f].replace(/长{20,}/,'长…').slice(0,400))}
  await b.close();})();
