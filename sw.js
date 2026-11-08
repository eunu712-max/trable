// 사진은 한 번 받으면 폰에 저장해 두고 바로 보여줌 (다음부터 인터넷 없어도 보임)
// 앱 화면(html)도 열 때마다 최신본을 저장 → 비행기 모드·인터넷 없을 때는 저장본으로 열림
const C="trip-img-v1",P="trip-page-v3";
self.addEventListener("install",e=>{self.skipWaiting();e.waitUntil(caches.open(P).then(c=>Promise.all(["tokyo.html","tokyo-us.html","greece.html"].map(f=>{const u=new URL(f,self.registration.scope).href;return fetch(u,{cache:"no-store"}).then(n=>{if(n.ok)return c.put(u,n)}).catch(()=>{})}))))});
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;
  const u=new URL(r.url);if(u.origin!==location.origin)return;
  if(r.mode==="navigate"||/\.html$/.test(u.pathname)){
    const key=u.origin+u.pathname;
    // 인터넷 되면 항상 최신본 (브라우저 10분 캐시도 건너뜀) · 안 되면 저장본
    e.respondWith(caches.open(P).then(c=>fetch(new Request(u.origin+u.pathname,{cache:"no-store",credentials:"same-origin"})).then(n=>{if(n.ok)c.put(key,n.clone());return n}).catch(()=>c.match(key).then(h=>h||Response.error()))));
    return;
  }
  if(!/\/img\//.test(u.pathname)||/list\.json$/.test(u.pathname))return;
  e.respondWith(caches.open(C).then(c=>c.match(r,{ignoreSearch:true}).then(hit=>hit||fetch(r).then(n=>{if(n.ok)c.put(r,n.clone());return n}))));
});
self.addEventListener("message",e=>{
  const l=e.data&&e.data.pre;if(!l)return;
  e.waitUntil(caches.open(C).then(async c=>{let i=0;const next=async()=>{while(i<l.length){const u=new URL(l[i++],self.registration.scope).href;try{if(!(await c.match(u))){const n=await fetch(u);if(n.ok)await c.put(u,n)}}catch(x){}}};await Promise.all([next(),next(),next(),next()])}));
});
