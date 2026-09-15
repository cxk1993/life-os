import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../App";

describe("空壳可渲染", () => {
  it("渲染出 Life-OS 标题", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Life-OS" })).toBeTruthy();
  });
});
