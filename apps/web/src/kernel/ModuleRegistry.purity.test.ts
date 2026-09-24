/**
 * 内核洁癖 · 入口解析：按目录约定加载业务插件，源码不得出现业务插件名。
 * 判据：新增 src/apps/<任意目录>/index.tsx 后，无需改 kernel 即可 resolveLoader。
 */
import { describe, it, expect } from "vitest";
import { resolveLoader } from "./ModuleRegistry";

describe("resolveLoader 目录约定", () => {
  it("能加载约定目录下的插件入口（不写死业务名）", async () => {
    // 任意存在的 apps 目录；测试只依赖「目录里有 index.tsx」这一约定
    const loader = resolveLoader("@/apps/dashboard");
    const mod = await loader();
    expect(mod.default).toBeTruthy();
  });

  it("生产实测修复：兼容后端清单的 @apps/ 简写（少一个斜杠）", async () => {
    // 部署批次实测：/api/v1/plugins 的 manifest.entry = "@apps/todo"，
    // 旧正则只认 @/apps/ 导致所有 slot 贡献注册失败（E5/D1/C′ 生产不可见）。
    const loader = resolveLoader("@apps/dashboard");
    const mod = await loader();
    expect(mod.default).toBeTruthy();
  });

  it("演示 mock 仍可加载", async () => {
    const mod = await resolveLoader("@mocks/alpha")();
    expect(mod.default).toBeTruthy();
  });

  it("未知 entry 拒绝而不是静默", async () => {
    await expect(resolveLoader("@/apps/not-exist-xyz")()).rejects.toThrow();
  });
});
