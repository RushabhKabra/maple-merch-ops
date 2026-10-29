/* Dependency-free DOM contract driver. It does not render pixels or emulate a browser. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const base=process.argv[2];
if(!base)throw Error('Pass the running local server URL.');
function harness(file){
 const elements=new Map(),listeners={},storage=new Map();
 function element(selector){
  if(!elements.has(selector))elements.set(selector,{innerHTML:'',textContent:'',hidden:false,disabled:false,value:'',style:{},dataset:{},classList:{toggle(){}},setAttribute(){},removeAttribute(){},focus(){},setSelectionRange(){},showModal(){this.open=true;},close(){this.open=false;}});
  return elements.get(selector);
 }
 const context=vm.createContext({console,URL,URLSearchParams,Blob,crypto:webcrypto,setTimeout:()=>0,clearTimeout(){},
  location:{hash:''},window:{addEventListener(){}},document:{querySelector:element,querySelectorAll:()=>[],addEventListener:(name,cb)=>{(listeners[name]??=[]).push(cb);},createElement:()=>({click(){}})},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
  fetch:(url,options)=>fetch(new URL(url,base),options),FormData:class{constructor(source){this.source=source;}get(k){return this.source[k];}}
 });
 const done=vm.runInContext(fs.readFileSync(path.join(__dirname,'../web',file),'utf8'),context,{filename:file});
 return {context,done,elements,listeners,element,run:code=>vm.runInContext(code,context)};
}
(async()=>{
 const app=harness('app.js');await app.done;
 assert.equal(app.element('#content').hidden,false);
 assert.match(app.element('#content').innerHTML,/Net merchandise sales/);
 assert.match(app.element('#content').innerHTML,/36,246\.60/);
 for(const view of ['catalog','inventory','launches','assets','crm','reports','overview']){
  app.run(`nav('${view}')`);
  assert.ok(app.element('#content').innerHTML.length>100,view+' should contain content');
 }
 // Exercise the actual click handler, dialog save callback, API write and following render.
 const click=app.listeners.click[0];
 await click({target:{closest:selector=>selector==='[data-view]'?null:{dataset:{action:'edit-product',id:'MUG-001'}}}});
 assert.equal(app.element('#modal').open,true);
 await app.run(`saveModal({get: name => ({title:'Updated everyday mug',description:'A useful original description for coffee lovers. Hand wash and check care instructions.',alt:'Updated mug on cream',price:'18.95',compare:'0',expected:'18.95'})[name]})`);
 await app.run('refresh()');app.run("nav('catalog')");
 assert.match(app.element('#content').innerHTML,/Updated everyday mug/);
 const before=(await (await fetch(base+'/api/summary')).json()).metrics;
 const shop=harness('shop.js');await shop.done;
 assert.match(shop.element('#store-products').innerHTML,/Updated everyday mug/);
 await shop.listeners.click[0]({target:{closest:selector=>selector==='[data-add]'?{dataset:{add:'MUG-001'}}:null}});
 assert.equal(Number(shop.element('#cart-count').textContent),1);
 await shop.element('#open-cart').onclick();assert.equal(shop.element('#cart-dialog').open,true);
 shop.element('#promo').value='MAPLE10';
 await shop.element('#checkout-form').onsubmit({preventDefault(){}});
 assert.equal(shop.element('#cart-dialog').open,false);
 assert.match(shop.element('#toast').textContent,/No payment charged/);
 const after=(await (await fetch(base+'/api/summary')).json()).metrics;
 assert.equal(after.orders,before.orders+1);assert.equal(after.net_cents,before.net_cents+1705);
 console.log(JSON.stringify({status:'passed',dashboard_views:7,listing_edit:'UI handler → API → SQLite → refreshed UI',checkout:'UI handler → API → order + stock + analytics',limitation:'DOM contract driver only. No browser layout, CSP, keyboard or visual rendering verification.'},null,2));
})().catch(err=>{console.error(err);process.exit(1)});
