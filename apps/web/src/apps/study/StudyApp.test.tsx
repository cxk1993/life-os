/**
 * 学业页前端测试（★ 2026-09-28 · 云昔 · 因主人报"点勾没效果"而立此存照）。
 *
 * ── 事故复现 ──────────────────────────────────────────────────
 * 学业页的 queryKey 曾是 `["study", "list"]`，而**共用的** `ItemRow` 只操作
 * `["todo"]` 前缀的缓存 ⇒ 在学业页点勾：
 *   · 请求**成功**（服务端 200，数据真的改了）
 *   · 乐观更新写进 `["todo"]` 缓存，学业页读的是 `["study","list"]` ⇒ **纹丝不动**
 *   · 失效刷新也只刷 `["todo"]` ⇒ 学业页**永不重新取数**
 * ⇒ **画面毫无变化** → 主人以为没生效，又点一次 → **两次互相抵消，作业白勾了**。
 *
 * ── 本用例守什么 ──────────────────────────────────────────────
 * **学业页的 key 必须挂在 `TODO_KEY_ROOT` 之下**：点勾后，
 * 学业页自己那条 query 的缓存必须真的被翻转（而不是只翻别人家的缓存）。
 * 若有人再把它改成另起一个根，这条会立刻变红。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import StudyApp from "./StudyApp";
import { TODO_KEY_ROOT } from "../todo/keys";
import type { TodoItem } from "../todo/api";

const sample: TodoItem = {
  id: "t1",
  text: "高数第四周作业",
  done: false,
  done_at: null,
  due_at: "2026-09-29T23:59:00+08:00",
  priority: "high",
  recur_rule: null,
  tags: ["学业", "学业/高数"],
  source_path: null,
  source_line: null,
  sort: 0,
  series_id: "t1",
  instance_no: 0,
  created_at: "2026-09-17T00:00:00+00:00",
  updated_at: "2026-09-17T00:00:00+00:00",
};

vi.mock("../todo/api", () => ({
  todoApi: {
    // 下面在 beforeEach 里按"**有状态的假服务器**"实现 ——
    // ★ 关键：toggle 之后，list 必须返回**已翻转**的状态。
    //   否则 onSettled 的失效重取会用旧值把乐观翻转盖回去，
    //   测试就会因为"mock 不像真服务器"而误红（本席第一版就是这么红的）。
    list: vi.fn(),
    toggle: vi.fn(),
    update: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
  },
}));

// eslint-disable-next-line import/first
import { todoApi } from "../todo/api";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

describe("StudyApp（学业页）", () => {
  // 假服务器状态：toggle 会真的翻转它，list 读它 —— 逼近真实后端的行为
  let serverDone = false;

  beforeEach(() => {
    serverDone = false;
    vi.mocked(todoApi.toggle).mockClear();
    vi.mocked(todoApi.list).mockImplementation(async () => ({
      items: [{ ...sample, done: serverDone, done_at: serverDone ? "2026-09-28T16:00:00+08:00" : null }],
      next_cursor: null,
    }));
    vi.mocked(todoApi.toggle).mockImplementation(async () => {
      serverDone = !serverDone;
      return { ...sample, done: serverDone, done_at: serverDone ? "now" : null };
    });
  });

  it("渲染出学业条目（含课程徽标）", async () => {
    const client = makeClient();
    render(
      <QueryClientProvider client={client}>
        <StudyApp />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("高数第四周作业")).toBeTruthy();
    expect(await screen.findByText("高数")).toBeTruthy(); // 从 学业/高数 取出的课程徽标
  });

  it("★ 点勾后学业页自己的缓存必须真翻转（回归：曾因 key 不在 todo 根下而毫无反应）", async () => {
    const client = makeClient();
    render(
      <QueryClientProvider client={client}>
        <StudyApp />
      </QueryClientProvider>,
    );
    const box = await screen.findByRole("button", { name: "标记为完成" });
    fireEvent.click(box);

    await waitFor(() => {
      const cached = client.getQueryData<{ items: TodoItem[] }>([
        TODO_KEY_ROOT,
        "study",
        "list",
      ]);
      // 修前：这个 key 下**根本取不到数据**（学业页当年用的是另一个根），断言必红。
      expect(cached?.items?.[0]?.done).toBe(true);
    });
  });


  it("★ 缓存里存在**非列表形状**的 todo 域缓存时，点勾仍必须发出请求", async () => {
    // ── 事故复现（2026-09-28，主人报"点勾没反应"的真正根因）──────────
    // ["todo"] 命名空间下不只住列表：
    //   · ["todo","tags"]           → TodoTag[]（**数组**）
    //   · ["todo","summary"]        → { today, overdue, week_done }（**没有 items**）
    // 而 ItemRow 的乐观更新曾直接 `old.items.map(...)` ⇒ 撞上就抛 TypeError ✗
    // 更要命的是 onMutate **先于** mutationFn 执行 ⇒ 请求**根本没发出去**
    // ⇒ 服务端只见 GET（onSettled 的刷新）、不见 POST ⇒ 界面纹丝不动。
    // 修前：本用例必红（toggle 从未被调用）。
    const client = makeClient();
    client.setQueryData(["todo", "tags"], [{ tag: "学业", todo: 1, done: 0, total: 1 }]);
    client.setQueryData(["todo", "summary"], { today: 0, overdue: 0, week_done: 0 });
    client.setQueryData(["todo", "today-summary"], { title: "今日日程", items: [], count: 0 });

    render(
      <QueryClientProvider client={client}>
        <StudyApp />
      </QueryClientProvider>,
    );
    const box = await screen.findByRole("button", { name: "标记为完成" });
    fireEvent.click(box);

    // ① 请求必须真的发出去（修前这一步就断了）
    await waitFor(() => expect(vi.mocked(todoApi.toggle)).toHaveBeenCalledWith("t1"));
    // ② 非列表缓存不能被破坏
    expect(client.getQueryData(["todo", "tags"])).toEqual([
      { tag: "学业", todo: 1, done: 0, total: 1 },
    ]);
    // ③ 列表缓存要真的翻转
    await waitFor(() => {
      const cached = client.getQueryData<{ items: TodoItem[] }>([
        TODO_KEY_ROOT,
        "study",
        "list",
      ]);
      expect(cached?.items?.[0]?.done).toBe(true);
    });
  });
});
