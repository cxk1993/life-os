/// <reference types="vite/client" />

// Vite 配置文件以 Node ESM 运行，Node 20.11+ 提供 import.meta.dirname。
// 这里只做类型补丁，避免为仅类型用途引入 @types/node。
interface ImportMeta {
  readonly dirname: string;
}
