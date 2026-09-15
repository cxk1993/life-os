/**
 * 空壳页面。
 *
 * T01 只负责"能跑起来"，所以这里没有任何业务、没有任何颜色。
 * 窗口系统接管本文件是 T02 的活：它会用 Desktop + Dock + WindowManager 替换掉这里。
 * 刻意不写死任何色值，避免干扰 T02 的设计令牌体系。
 */
export default function App() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-medium">Life-OS</h1>
      <p className="mt-3 text-sm">工程骨架已就绪。窗口系统与各模块将在后续任务块接入。</p>
      <p className="mt-6 text-xs">前端 5173 · 后端 8000 · 健康检查 /healthz</p>
    </main>
  );
}
