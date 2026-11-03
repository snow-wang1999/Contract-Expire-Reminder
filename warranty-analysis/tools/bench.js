// usage: node bench.js <html> <datadir> [outjson]
const {chromium}=require('playwright');
const path=require('path'),fs=require('fs');
(async()=>{
  const [html,dir,out]=process.argv.slice(2);
  const files=fs.readdirSync(dir);
  const pick=re=>path.join(dir,files.find(f=>re.test(f)));
  const map={inQuote:pick(/serviceLine/i),inRenew:pick(/RenewalSNList/i),inBl:pick(/Barcode/i),inSub:pick(/SublineList/i)};
  const b=await chromium.launch({args:['--js-flags=--max-old-space-size=8192']});
  const p=await b.newPage({viewport:{width:1400,height:900}});
  const logs=[];p.on('console',m=>logs.push(m.text()));p.on('pageerror',e=>logs.push('PAGEERR '+e.message));
  await p.addInitScript(()=>{window.__lt=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lt.push(e.duration)}).observe({type:'longtask',buffered:true})}catch(e){}});
  if(process.env.NOWORKER)await p.addInitScript(()=>{delete window.Worker});
  await p.goto('file://'+path.resolve(html));
  const res={};
  const fiOf={inQuote:'fiQuote',inRenew:'fiRenew',inBl:'fiBl',inSub:'fiSub'};
  for(const [inp,f] of Object.entries(map)){
    const t0=Date.now();
    await p.evaluate(()=>{window.__lt=[]});
    await p.setInputFiles('#'+inp,f);
    await p.waitForFunction(id=>{const e=document.getElementById(id);return e&&e.style.display!=='none'&&/^(📎|⚠️)/.test(e.textContent)},fiOf[inp],{timeout:900000,polling:200});
    const lt=await p.evaluate(()=>window.__lt);
    res[inp]={ms:Date.now()-t0,file:path.basename(f),mb:+(fs.statSync(f).size/1e6).toFixed(1),info:await p.textContent('#'+fiOf[inp]),maxLongTask:Math.round(Math.max(0,...lt)),sumLongTask:Math.round(lt.reduce((a,c)=>a+c,0))};
    console.error(inp,JSON.stringify(res[inp]));
  }
  await p.evaluate(()=>{window.__lt=[]});
  const t0=Date.now();
  await p.click('#btnRun');
  await p.waitForFunction(()=>{const e=document.getElementById('btnExpX');const er=document.getElementById('errBox');return (e&&e.style.display!=='none')||(er&&er.style.display==='block')},null,{timeout:900000,polling:200});
  const lt=await p.evaluate(()=>window.__lt);
  res.run={ms:Date.now()-t0,maxLongTask:Math.round(Math.max(0,...lt)),err:await p.evaluate(()=>{const e=document.getElementById('errBox');return e.style.display==='block'?e.textContent:''})};
  res.domNodes=await p.evaluate(()=>document.getElementsByTagName('*').length);
  res.heapMB=await p.evaluate(()=>performance.memory?Math.round(performance.memory.usedJSHeapSize/1e6):null);
  res.stat=await p.evaluate(()=>document.getElementById('statBox').innerText);
  console.error('run',JSON.stringify(res.run),'dom',res.domNodes,'heap',res.heapMB);
  // tab switch timing
  const tabs=await p.$$eval('#tabNav button',bs=>bs.map(b=>b.textContent));
  res.tabs=[];
  for(let i=0;i<tabs.length;i++){const t=Date.now();await p.click(`#tabNav button >> nth=${i}`);await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>setTimeout(r,0))));res.tabs.push([tabs[i],Date.now()-t]);}
  // export xlsx timing
  const t1=Date.now();
  const dl=p.waitForEvent('download',{timeout:900000}).catch(e=>null);
  await p.click('#btnExpX');const d=await dl;res.exportMs=Date.now()-t1;
  if(d&&out){await d.saveAs(out.replace(/\.json$/,'.xlsx'))}
  // snapshot result for regression
  res.snapshot=await p.evaluate(()=>{const r=window.u_result||(typeof u_result!=='undefined'?u_result:null);try{return JSON.stringify(u_exportSheets().map(s=>({name:s.name,n:s.rows.length,h:s.rows.slice(0,3)})))}catch(e){return 'ERR '+e.message}});
  res.logs=logs.filter(l=>!/^\[上传\]/.test(l)).slice(-20);
  if(out)fs.writeFileSync(out,JSON.stringify(res,null,1));
  console.log(JSON.stringify({...res,snapshot:undefined,logs:res.logs},null,1));
  await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
