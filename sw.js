// 사진은 한 번 받으면 폰에 저장해 두고 바로 보여줌 (다음부터 인터넷 없어도 보임)
const C="trip-img-v1";
self.addEventListener("install",e=>self.skipWaiting());
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;
  const u=new URL(r.url);if(u.origin!==location.origin||!/\/img\//.test(u.pathname)||/list\.json$/.test(u.pathname))return;
  e.respondWith(caches.open(C).then(c=>c.match(r,{ignoreSearch:true}).then(hit=>hit||fetch(r).then(n=>{if(n.ok)c.put(r,n.clone());return n}))));
});
self.addEventListener("message",e=>{
  const l=e.data&&e.data.pre;if(!l)return;
  e.waitUntil(caches.open(C).then(async c=>{let i=0;const next=async()=>{while(i<l.length){const u=new URL(l[i++],self.registration.scope).href;try{if(!(await c.match(u))){const n=await fetch(u);if(n.ok)await c.put(u,n)}}catch(x){}}};await Promise.all([next(),next(),next(),next()])}));
});
