import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../App";
import { setToken } from "@/shared/api/client";

describe("桌面可渲染", () => {
  it("渲染出 Life-OS 品牌与顶栏/坞骨架", () => {
    // ★ T30：桌面壳有鉴权门 —— 该用例测的是"登录后的桌面"，先种一个 token
    setToken("test-token");
    render(<App />);
    // 顶栏品牌（span，非 heading）
    expect(screen.getByText("Life-OS")).toBeTruthy();
    // 顶栏搜索入口
    expect(screen.getByLabelText("打开全局搜索")).toBeTruthy();
    // 模块坞容器
    expect(screen.getByRole("toolbar", { name: "模块坞" })).toBeTruthy();
  });
});
