import { describe, expect, it } from "vitest";
import { parseTodoNL } from "./todo-nl";

/** 本地时间 → 期望的 UTC ISO（与服务端 to_utc 语义一致）。 */
function atLocal(y: number, mo: number, d: number, h: number, mi: number): string {
  return new Date(y, mo - 1, d, h, mi, 0, 0).toISOString();
}
function todayBase(): { y: number; m: number; d: number; day: number } {
  const now = new Date();
  return { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate(), day: now.getDay() };
}
function addDaysLocal(y: number, m: number, d: number, n: number) {
  const dt = new Date(y, m - 1, d + n);
  return { y: dt.getFullYear(), m: dt.getMonth() + 1, d: dt.getDate() };
}

describe("· 待办自然语言解析（离线词典版）", () => {
  it("明天下午3点交房租 → 文本剥离 + due=明天15:00", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("明天下午3点交房租");
    expect(r.text).toBe("交房租");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 15, 0));
    expect(r.matched).toBe("明天下午3点");
  });

  it("明天交房租（无时刻）→ due=明天 09:00（默认上午）", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("明天交房租");
    expect(r.text).toBe("交房租");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 9, 0));
  });

  it("今天写周报 → due=今天 09:00", () => {
    const t = todayBase();
    const r = parseTodoNL("今天写周报");
    expect(r.text).toBe("写周报");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, t.d, 9, 0));
  });

  it("后天去医院 → due=+2 09:00", () => {
    const t = todayBase();
    const later = addDaysLocal(t.y, t.m, t.d, 2);
    const r = parseTodoNL("后天去医院");
    expect(r.text).toBe("去医院");
    expect(r.dueAt).toBe(atLocal(later.y, later.m, later.d, 9, 0));
  });

  it("大后天去旅游 → due=+3", () => {
    const t = todayBase();
    const later = addDaysLocal(t.y, t.m, t.d, 3);
    const r = parseTodoNL("大后天去旅游");
    expect(r.text).toBe("去旅游");
    expect(r.dueAt).toBe(atLocal(later.y, later.m, later.d, 9, 0));
  });

  it("周一下午开会 → nearest future 周一 15:00（下午默认；已过则下周）", () => {
    const t = todayBase();
    const target = 1; // 周一
    let delta = (target - t.day + 7) % 7;
    if (delta === 0) delta = 7;
    const want = addDaysLocal(t.y, t.m, t.d, delta);
    const r = parseTodoNL("周一下午开会");
    expect(r.text).toBe("开会");
    expect(r.dueAt).toBe(atLocal(want.y, want.m, want.d, 15, 0));
  });

  it("下周五聚餐 → 下周周五 09:00", () => {
    const t = todayBase();
    const target = 5; // 周五
    const delta = ((target - t.day + 7) % 7) + 7;
    const want = addDaysLocal(t.y, t.m, t.d, delta);
    const r = parseTodoNL("下周五聚餐");
    expect(r.text).toBe("聚餐");
    expect(r.dueAt).toBe(atLocal(want.y, want.m, want.d, 9, 0));
  });

  it("3天后提交报告 → +3 09:00", () => {
    const t = todayBase();
    const later = addDaysLocal(t.y, t.m, t.d, 3);
    const r = parseTodoNL("3天后提交报告");
    expect(r.text).toBe("提交报告");
    expect(r.dueAt).toBe(atLocal(later.y, later.m, later.d, 9, 0));
  });

  it("三天后提交报告（中文数字）→ +3", () => {
    const t = todayBase();
    const later = addDaysLocal(t.y, t.m, t.d, 3);
    const r = parseTodoNL("三天后提交报告");
    expect(r.text).toBe("提交报告");
    expect(r.dueAt).toBe(atLocal(later.y, later.m, later.d, 9, 0));
  });

  it("月底交水电费 → 本月最后一天 09:00", () => {
    const t = todayBase();
    const lastDay = new Date(t.y, t.m, 0).getDate(); // 下月0号=本月最后一天
    const r = parseTodoNL("月底交水电费");
    expect(r.text).toBe("交水电费");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, lastDay, 9, 0));
  });

  it("9月25日体检 → 今年9/25 09:00", () => {
    const t = todayBase();
    const r = parseTodoNL("9月25日体检");
    expect(r.text).toBe("体检");
    expect(r.dueAt).toBe(atLocal(t.y, 9, 25, 9, 0));
  });

  it("9月25号体检（号）→ 同 9/25", () => {
    const t = todayBase();
    const r = parseTodoNL("9月25号体检");
    expect(r.text).toBe("体检");
    expect(r.dueAt).toBe(atLocal(t.y, 9, 25, 9, 0));
  });

  it("9-25体检 → 9/25", () => {
    const t = todayBase();
    const r = parseTodoNL("9-25体检");
    expect(r.text).toBe("体检");
    expect(r.dueAt).toBe(atLocal(t.y, 9, 25, 9, 0));
  });

  it("晚上8点健身 → 今天 20:00", () => {
    const t = todayBase();
    const r = parseTodoNL("晚上8点健身");
    expect(r.text).toBe("健身");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, t.d, 20, 0));
  });

  it("早上7点跑步 → 今天 07:00", () => {
    const t = todayBase();
    const r = parseTodoNL("早上7点跑步");
    expect(r.text).toBe("跑步");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, t.d, 7, 0));
  });

  it("晚上8点半学习 → 今天 20:30", () => {
    const t = todayBase();
    const r = parseTodoNL("晚上8点半学习");
    expect(r.text).toBe("学习");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, t.d, 20, 30));
  });

  it("明天晚上9点45分看电影 → 明天 21:45", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("明天晚上9点45分看电影");
    expect(r.text).toBe("看电影");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 21, 45));
  });

  it("明天中午12点吃饭 → 12:00", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("明天中午12点吃饭");
    expect(r.text).toBe("吃饭");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 12, 0));
  });

  it("今天上午10点开会 → 10:00", () => {
    const t = todayBase();
    const r = parseTodoNL("今天上午10点开会");
    expect(r.text).toBe("开会");
    expect(r.dueAt).toBe(atLocal(t.y, t.m, t.d, 10, 0));
  });

  it("周天去爬山 → 周日 nearest future", () => {
    const t = todayBase();
    const target = 0; // 周日
    let delta = (target - t.day + 7) % 7;
    if (delta === 0) delta = 7;
    const want = addDaysLocal(t.y, t.m, t.d, delta);
    const r = parseTodoNL("周天去爬山");
    expect(r.text).toBe("去爬山");
    expect(r.dueAt).toBe(atLocal(want.y, want.m, want.d, 9, 0));
  });

  it("周五晚上看电影 → nearest future 周五 20:00", () => {
    const t = todayBase();
    const target = 5;
    let delta = (target - t.day + 7) % 7;
    if (delta === 0) delta = 7;
    const want = addDaysLocal(t.y, t.m, t.d, delta);
    const r = parseTodoNL("周五晚上看电影");
    expect(r.text).toBe("看电影");
    expect(r.dueAt).toBe(atLocal(want.y, want.m, want.d, 20, 0));
  });

  it("交房租（无日期）→ 原样透传 due=null", () => {
    const r = parseTodoNL("交房租");
    expect(r.text).toBe("交房租");
    expect(r.dueAt).toBeNull();
    expect(r.matched).toBe("");
  });

  it("只有日期短语 → 文本为空（合法，服务端会拒空文本由 UI 兜底）", () => {
    const r = parseTodoNL("明天下午3点");
    expect(r.matched).toBe("明天下午3点");
  });

  it("空输入 → 空结果", () => {
    const r = parseTodoNL("   ");
    expect(r.text).toBe("");
    expect(r.dueAt).toBeNull();
  });

  it("日期在句中（给老板写周报，明天下午交）→ 尾部日期剥离", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("给老板写周报，明天下午交");
    expect(r.text).toBe("给老板写周报，交");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 15, 0));
  });

  it("文本含既有语法糖（!高 #标签）不被破坏", () => {
    const t = todayBase();
    const tom = addDaysLocal(t.y, t.m, t.d, 1);
    const r = parseTodoNL("明天交房租 !高 #房贷");
    expect(r.text).toBe("交房租 !高 #房贷");
    expect(r.dueAt).toBe(atLocal(tom.y, tom.m, tom.d, 9, 0));
  });
});
