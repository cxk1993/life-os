import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import pkg from "./package.json";

// ★ 2026-09-27（主人「正式版 1.0.0」）：把版本号 + **构建时刻**注入前端。
//   构建时刻是关键 —— 它能一眼区分「跑的是新版还是被 PWA 缓存的旧版」。
const BUILD_AT = new Date().toISOString().slice(0, 16).replace("T", " ");

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __BUILD_AT__: JSON.stringify(BUILD_AT),
  },
  resolve: {
    alias: {
      "@": import.meta.dirname + "/src",
    },
  },
  server: {
    port: 5173,
    // 端口被占时直接报错，不要偷偷换端口 —— 否则主人按文档访问会打不开
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // ★ 必须开 globals：@testing-library/react 的自动 cleanup 依赖全局 afterEach，
    //   关掉的话测试之间不会 unmount，上一个测试的 DOM 会残留，
    //   表现为 "Found multiple elements with ..." 这类假失败。
    globals: true,
  },
});
