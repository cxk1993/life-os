/* Life-OS service worker
 * 策略（ADR-0003 §2.5 的 PWA 落地，红线：/api/ 绝不缓存——单用户系统数据必须实时）：
 *  - /api/*、/healthz        → 直连网络（bypass）
 *  - /assets/*（hash 文件名） → cache-first（hash 变即新资源，天然安全）
 *  - 页面导航 / 壳资源        → network-first，离线回退缓存（装得上、断网能开壳）
 */
const CACHE = "lifeos-shell-v1";
const SHELL = ["/", "/login.html", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/healthz") return; // 数据永远走网络

  if (url.pathname.startsWith("/assets/")) {
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const clone = res.clone();
              caches.open(CACHE).then((c) => c.put(req, clone));
            }
            return res;
          })
      )
    );
    return;
  }

  // 导航与其他静态：network-first，失败回退缓存，再失败回退壳
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok && (req.mode === "navigate" || url.pathname.startsWith("/icons/"))) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(req, clone));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then(
          (hit) => hit || (req.mode === "navigate" ? caches.match("/") : hit)
        )
      )
  );
});
