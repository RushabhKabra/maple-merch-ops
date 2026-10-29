'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=c=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD'}).format(c/100);
let token='',products=[],collection='all';
let sid=sessionStorage.getItem('maple-session')||crypto.randomUUID();sessionStorage.setItem('maple-session',sid);
let cart;try{cart=JSON.parse(localStorage.getItem('maple-cart')||'{}');if(!cart||Array.isArray(cart)||typeof cart!=='object')cart={};}catch{cart={};}
let requestKey=localStorage.getItem('maple-checkout-key')||crypto.randomUUID();
async function api(url,body){const r=await fetch(url,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Merch-Token':token},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed.');return d;}
let toastTimer;
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,7000);}
function persist(){localStorage.setItem('maple-cart',JSON.stringify(cart));localStorage.setItem('maple-checkout-key',requestKey);$('#cart-count').textContent=Object.values(cart).reduce((a,b)=>a+Number(b),0);}
function render(){
 const active=products.filter(p=>p.status==='active');
 const collections=[...new Set(active.map(p=>p.collection))];
 $('#collections').innerHTML=['all',...collections].map(c=>`<button class="button ${collection===c?'active':''}" data-collection="${esc(c)}">${c==='all'?'Shop all':esc(c)}</button>`).join('');
 $('#store-products').innerHTML=active.filter(p=>collection==='all'||p.collection===collection).map(p=>`<article class="store-product"><img src="${esc(p.image)}" alt="${esc(p.alt||p.title)}">${p.inventory<10?`<span class="stock-label">${p.inventory===0?'Out of stock':'Only '+p.inventory+' left'}</span>`:''}<h2>${esc(p.title)}</h2><p class="price">${money(p.price_cents)}${p.compare_at_cents>p.price_cents?` <del>${money(p.compare_at_cents)}</del>`:''}</p><p class="desc">${esc(p.description?p.description.slice(0,108)+'…':'Product details are being updated.')}</p><button class="button" data-add="${esc(p.sku)}" ${p.inventory===0?'disabled':''}>${p.inventory===0?'Sold out':'Add to bag'}</button></article>`).join('');persist();
}
function drawCart(){
 const entries=Object.entries(cart).filter(([sku,q])=>products.some(p=>p.sku===sku)&&Number.isInteger(q)&&q>0);
 $('#cart-items').innerHTML=entries.map(([sku,q])=>{const p=products.find(p=>p.sku===sku);return `<div class="cart-line"><div>${esc(p.title)}<small class="live-note">${q} × ${money(p.price_cents)}</small></div><span>${money(q*p.price_cents)}</span><button class="button small" type="button" data-remove="${esc(sku)}" aria-label="Remove ${esc(p.title)}">Remove</button></div>`;}).join('')||'<p>Your bag is empty.</p>';
 $('#cart-total').textContent=money(entries.reduce((a,[sku,q])=>a+q*products.find(p=>p.sku===sku).price_cents,0));
 $('#place-order').disabled=!entries.length;$('#checkout-error').textContent='';
}
document.addEventListener('click',async e=>{
 const c=e.target.closest('[data-collection]');if(c){collection=c.dataset.collection;render();return;}
 const a=e.target.closest('[data-add]');if(a){const p=products.find(x=>x.sku===a.dataset.add);const q=cart[p.sku]||0;if(q>=p.inventory||q>=20){toast('The available quantity is already in your bag.');return;}cart[p.sku]=q+1;requestKey=crypto.randomUUID();persist();toast('Added to your bag.');try{await api('/api/events',{session_id:sid,event:'add_to_cart'});}catch(err){toast(err.message);}return;}
 const r=e.target.closest('[data-remove]');if(r){delete cart[r.dataset.remove];requestKey=crypto.randomUUID();persist();drawCart();}
});
$('#open-cart').onclick=async()=>{drawCart();$('#cart-dialog').showModal();try{await api('/api/events',{session_id:sid,event:'begin_checkout'});}catch(err){toast(err.message);}};
$('#close-cart').onclick=()=>$('#cart-dialog').close();
$('#checkout-form').onsubmit=async e=>{e.preventDefault();$('#place-order').disabled=true;try{
 const result=await api('/api/checkout',{items:Object.entries(cart).map(([sku,quantity])=>({sku,quantity})),session_id:sid,idempotency_key:requestKey,promo_code:$('#promo').value});
 cart={};requestKey=crypto.randomUUID();persist();$('#cart-dialog').close();products=await api('/api/products');render();toast(`Order ${result.order_id} created${result.net_cents!==undefined?' · '+money(result.net_cents):''}. No payment charged. Open the operations workspace to see the update.`);
 }catch(err){$('#checkout-error').textContent=err.message;}finally{$('#place-order').disabled=false;}};
(async()=>{try{const b=await api('/api/bootstrap');token=b.token;products=await api('/api/products');cart=Object.fromEntries(Object.entries(cart).filter(([sku,q])=>products.some(p=>p.sku===sku)&&Number.isInteger(q)&&q>0&&q<=20));render();await api('/api/events',{session_id:sid,event:'view_item'});}catch(err){$('#store-products').textContent='Could not load the shop: '+err.message;}})();
