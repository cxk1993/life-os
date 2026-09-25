/**
 * MultitabFrame 判据测试 · 对应豆包 V6 预研 §3.3 四条：
 * 渲染 N 页签 / 切页内容切换 / 切回状态保持（keep-alive）/ 懒挂载只挂当前页。
 * 另加键盘可达（role=tab + aria-selected）与空 pages 兜底两条。
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useState } from "react";

import MultitabFrame, { type MultitabPage } from "./MultitabFrame";

function pages(): MultitabPage[] {
  return [
    { key: "catalog", label: "能力目录", content: <div>目录内容</div> },
    { key: "mcp", label: "MCP", content: <div>MCP内容</div> },
    { key: "push", label: "推送", content: <div>推送内容</div> },
  ];
}

describe("MultitabFrame（V6 一窗多页容器）", () => {
  it("渲染全部一级页签，当前页 aria-selected", () => {
    render(<MultitabFrame pages={pages()} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(tabs[1].getAttribute("aria-selected")).toBe("false");
  });

  it("切页内容切换：点 MCP 页签后其面板成为当前", () => {
    render(<MultitabFrame pages={pages()} />);
    fireEvent.click(screen.getByTestId("mtab-tab-mcp"));
    expect(screen.getByTestId("mtab-tab-mcp").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("mtab-panel-mcp").hidden).toBe(false);
    expect(screen.getByTestId("mtab-panel-catalog").hidden).toBe(true);
  });

  it("懒挂载：未点过的页不挂载（DOM 中不存在面板）", () => {
    render(<MultitabFrame pages={pages()} />);
    expect(screen.queryByTestId("mtab-panel-mcp")).toBeNull();
    expect(screen.queryByTestId("mtab-panel-push")).toBeNull();
    expect(screen.getByTestId("mtab-panel-catalog")).toBeTruthy();
  });

  it("keep-alive：切回后状态保持（输入不丢）", () => {
    function KeepAliveProbe() {
      const [value, setValue] = useState("");
      return (
        <MultitabFrame
          pages={[
            {
              key: "a",
              label: "A",
              content: <input aria-label="输入" value={value} onChange={(e) => setValue(e.target.value)} />,
            },
            { key: "b", label: "B", content: <div>B页</div> },
          ]}
        />
      );
    }
    render(<KeepAliveProbe />);
    fireEvent.change(screen.getByLabelText("输入"), { target: { value: "主人的话" } });
    fireEvent.click(screen.getByTestId("mtab-tab-b"));
    fireEvent.click(screen.getByTestId("mtab-tab-a"));
    expect((screen.getByLabelText("输入") as HTMLInputElement).value).toBe("主人的话");
  });

  it("空 pages 返回 null 不崩", () => {
    const { container } = render(<MultitabFrame pages={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
