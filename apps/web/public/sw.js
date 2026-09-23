/* Life-OS service worker
 * 职责一：离线壳（ADR-0003 §2.5 的 PWA 落地，红线：/api/ 绝不缓存——单用户系统数据必须实时）：
 *  - /api/*、/healthz        → 直连网络（bypass）
 *  - /assets/*（hash 文件名） → cache-first（hash 变即新资源，天然安全）
 *  - 页面导航 / 壳资源        → network-first，离线回退缓存（装得上、断网能开壳）
 * 职责二：Web Push 接收端（push 插件）——push 事件 → showNotification，
 *         notificationclick → 聚焦/新开窗口。详见文件末两段。
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

/* ── Web Push（push 插件）：浏览器 / PWA 推送通道 ──────────────────────────
 * ★ 没有下面这段，后端发得出去、浏览器也不会弹 —— 这就是 Web Push 的最后一公里。
 * payload 形状与后端 modules/push/sender.py 对齐：{title, body, url, tag}。
 */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Life-OS", {
      body: data.body || "",
      tag: data.tag || "lifeos",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: data.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          if ("navigate" in client) client.navigate(url).catch(() => {});
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
