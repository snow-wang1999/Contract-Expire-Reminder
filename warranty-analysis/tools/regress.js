// node regress.js <html> <datadir> <outprefix>
const {chromium}=require('playwright');const path=require('path'),fs=require('fs'),crypto=require('crypto');
(async()=>{
  const [html,dir,out]=process.argv.slice(2);const files=fs.readdirSync(dir);const pick=re=>path.join(dir,files.find(f=>re.test(f)));
  const b=await chromium.launch({args:['--js-flags=--max-old-space-size=8192']});
  const scen=[['real-renew',{inQuote:/serviceLine/i,inRenew:/RenewalSNList/i,inBl:/Barcode/i,inSub:/SublineList/i}],['real-new',{inQuote:/serviceLine/i,inBl:/Barcode/i,inSub:/SublineList/i}],['demo-new',null],['demo-renew',null]];
  const fi={inQuote:'fiQuote',inRenew:'fiRenew',inBl:'fiBl',inSub:'fiSub'};
  const res={};
  for(const [name,map] of scen){if(process.env.ONLY&&!process.env.ONLY.split(',').includes(name))continue;
    const p=await b.newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));
    if(process.env.NOWORKER)await p.addInitScript(()=>{delete window.Worker});
    await p.goto('file://'+path.resolve(html));
    if(map){for(const [inp,re] of Object.entries(map)){await p.setInputFiles('#'+inp,pick(re));await p.waitForFunction(id=>/^(📎|⚠️)/.test(document.getElementById(id).textContent),fi[inp],{timeout:900000,polling:200})}
      await p.evaluate(()=>{setTimeout(()=>u_run(),0)});}
    else await p.evaluate(n=>{setTimeout(()=>u_demo(n),0)},name==='demo-new'?'new':'renew');
    await p.waitForFunction(()=>{const e=document.getElementById('btnExpX');const er=document.getElementById('errBox');return (e.style.display!=='none'&&!document.getElementById('btnRun').disabled)||er.style.display==='block'},null,{timeout:900000,polling:200});
    const sheets=await p.evaluate(()=>{const s=u_exportSheets();s[0].rows=s[0].rows.filter(r=>r[0]!=='生成时间');return JSON.stringify(s)});
    const html1=await p.evaluate(()=>['statBox','issueStrip','tabATitle'].map(id=>document.getElementById(id).innerText).join('\n'));
    const parsed=JSON.parse(sheets);
    res[name]={hash:crypto.createHash('sha1').update(sheets).digest('hex'),sheets:parsed.map(s=>s.name+':'+s.rows.length),ui:crypto.createHash('sha1').update(html1).digest('hex'),errs,err:await p.evaluate(()=>document.getElementById('errBox').style.display==='block'?document.getElementById('errBox').textContent:'')};
    fs.writeFileSync(out+'-'+name+'.json',sheets);
    const dl=p.waitForEvent('download',{timeout:900000});await p.evaluate(()=>{setTimeout(()=>u_exportXlsx(),0)});await p.waitForTimeout(100);const d=await dl;await d.saveAs(out+'-'+name+'.xlsx');
    console.log(name,JSON.stringify(res[name]));
    await p.close();
  }
  await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
