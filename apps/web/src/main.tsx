import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "@/shared/styles/tokens.css";
import "@/shared/styles/components.css";
import "@/kernel/desktop.css";
import "./index.css";
import { initTheme } from "@/shared/styles/theme";

// 在首次渲染前确定主题并写到 <html>，避免闪烁。
initTheme();

// 服务端状态统一由 TanStack Query 管；窗口/UI 状态由 Zustand 管（内核 store）。
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("找不到 #root 挂载点，检查 index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);

// PWA：生产环境注册 service worker（dev 下不注册，避免 HMR 被缓存层干扰）。
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // 注册失败不影响使用，静默即可（例如通过 IP 直连的非安全上下文）
    });
  });
}
