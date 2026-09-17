import { describe, it, expect } from "vitest";
import { replaceRoot, removeRoot } from "./cache";
import type { CalendarEvent } from "../api";

function ev(id: string, children: CalendarEvent[] = []): CalendarEvent {
  return {
    id,
    title: id,
    color: "var(--accent)",
    start_at: "2026-09-15T08:00:00+08:00",
    end_at: "2026-09-15T09:00:00+08:00",
    all_day: false,
    span_days: 1,
    source: "manual",
    parent_id: null,
    sort: 0,
    location: null,
    note: null,
    children,
  };
}

describe("replaceRoot", () => {
  it("存在则按 id 替换", () => {
    const list = [ev("a"), ev("b")];
    const next = { ...ev("a"), title: "改了" };
    const out = replaceRoot(list, next);
    expect(out).toHaveLength(2);
    expect(out[0].title).toBe("改了");
  });
  it("不存在则追加", () => {
    const list = [ev("a")];
    const out = replaceRoot(list, ev("c"));
    expect(out.map((e) => e.id)).toEqual(["a", "c"]);
  });
  it("SSE created 增量合并子树（含子块）", () => {
    const withChild = ev("a", [ev("a1")]);
    const out = replaceRoot([], withChild);
    expect(out[0].children[0].id).toBe("a1");
  });
});

describe("removeRoot", () => {
  it("按 id 删除根（连同子树下整棵移除）", () => {
    const list = [ev("a", [ev("a1")]), ev("b")];
    const out = removeRoot(list, "a");
    expect(out.map((e) => e.id)).toEqual(["b"]);
  });
});
