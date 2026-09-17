/** todo —— 内置插件的前端入口（T14 的加载器按 manifest.entry 加载它）。 */
export function Component() {
  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold">todo</h2>
      <p className="text-sm opacity-70">由 create_plugin.py 生成，请把界面写在这里。</p>
    </div>
  );
}

export default { Component };
