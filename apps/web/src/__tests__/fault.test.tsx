import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModuleErrorBoundary } from "@/kernel/WindowFrame";
import { resolveLoader } from "@/kernel/ModuleRegistry";

function Boom(): null {
  throw new Error("boom");
}

describe("模块容错", () => {
  it("入口求值抛异常的模块：loader 拒绝（由错误边界兜底为占位）", async () => {
    await expect(resolveLoader("@mocks/broken")()).rejects.toThrow();
  });

  it("入口指向不存在文件的模块：loader 拒绝（缺失容错）", async () => {
    await expect(resolveLoader("@mocks/ghost")()).rejects.toThrow();
  });

  it("错误边界：子组件抛错时只渲染占位，不向上白屏", () => {
    const { container } = render(
      <ModuleErrorBoundary moduleId="mod-x">
        <Boom />
      </ModuleErrorBoundary>,
    );
    expect(container.textContent).toContain("该模块尚未接入");
  });
});
