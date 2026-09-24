/**
 * TX-TODO-NL-01 · 待办自然语言解析（离线词典版）。
 *
 * 设计要点（与后端对齐，不重复造轮子）：
 * - 后端 parse_natural_date 已支持 今天/明天/后天/周X(nearest future)/10-01 且只到「日期」粒度；
 * - 本解析器在前端补「自然表达 + 时刻」两段增量，语义与后端一致（周X 已过→下周），
 *   解析成功走结构化 due_at（带时刻），失败原文透传给后端语法糖兜底；
 * - 纯本地规则、零网络、零依赖，隐私边界（采纳 astrbot 约束：不上云）。
 */

export interface TodoNLResult {
  /** 去掉日期时间短语后的待办文本（trim） */
  text: string;
  /** 解析出的截止时间（UTC ISO 完整串，给 createStructured 用）；无则 null */
  dueAt: string | null;
  /** 命中的日期时间短语（界面预览用） */
  matched: string;
  /** 命中但无法计算的短语（提示用），无则 null */
  unparsed: string | null;
}

const WEEKDAY: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  日: 0,
  天: 0,
};

const CN_NUM: Record<string, number> = {
  零: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
};

/** 中文数字（≤99）→ number；非数字返回 null。 */
function cnToNum(s: string): number | null {
  if (s in CN_NUM) return CN_NUM[s];
  if (s.startsWith("十")) {
    const tail = s.slice(1);
    return 10 + (tail ? (cnToNum(tail) ?? 0) : 0);
  }
  if (s.endsWith("十") && s.length === 2) {
    const head = cnToNum(s[0]);
    return head == null ? null : head * 10;
  }
  if (s.length === 2 && s[0] in CN_NUM && s[1] in CN_NUM) {
    const a = CN_NUM[s[0]];
    const b = CN_NUM[s[1]];
    if (a === 1 && s[1] === "十") return 10;
    return a * 10 + b;
  }
  return null;
}

/** 数字 token（阿拉伯 / 中文）→ number。 */
function numOf(tok: string): number | null {
  if (/^\d+$/.test(tok)) {
    const n = parseInt(tok, 10);
    return n >= 0 && n <= 99 ? n : null;
  }
  return cnToNum(tok);
}

interface Slot {
  start: number;
  end: number;
  match: string;
}

const TIME_TOKEN =
  "(凌晨|早上|上午|中午|下午|傍晚|晚上|夜里)?(\\d{1,2}|[一二两三四五六七八九十]{1,3})(点|時|:)(半|(\\d{1,2}|[一二两三四五六七八九十]{1,2})分?)?";
const PURE_PERIOD = "(凌晨|早上|上午|中午|下午|傍晚|晚上|夜里)";

/** 匹配日期短语后的时刻段：优先「时段+数字」，回退「纯时段词」（默认时刻）。返回长度+分钟。 */
function matchTimeAfter(after: string): { len: number; time: number } | null {
  const fullRe = new RegExp(`^${TIME_TOKEN}`);
  const fm = after.match(fullRe);
  if (fm && fm[2]) {
    const time = timeToMinutes(fm[1], fm[2], fm[4], fm[5]);
    if (time != null) return { len: fm[0].length, time };
  }
  const pp = after.match(new RegExp(`^${PURE_PERIOD}`));
  if (pp) {
    const time = PERIOD_DEFAULT[pp[1]];
    if (time != null) return { len: pp[0].length, time };
  }
  return null;
}

/** 时段词 → 默认时刻（分钟）；仅当「时段后无数字小时」时使用。 */
const PERIOD_DEFAULT: Record<string, number> = {
  凌晨: 2 * 60,
  早上: 8 * 60,
  上午: 10 * 60,
  中午: 12 * 60,
  下午: 15 * 60,
  傍晚: 18 * 60,
  晚上: 20 * 60,
  夜里: 22 * 60,
};

/** 时刻短语 → 分钟（当天 0-1439）。语义：有时段词按时段偏移；无时段词按字面；纯时段词（无数字）取时段默认。 */
function timeToMinutes(
  period: string | undefined,
  hourTok: string | undefined,
  half: string | undefined,
  minTok: string | undefined,
): number | null {
  if (hourTok == null) {
    return PERIOD_DEFAULT[period ?? ""] ?? null;
  }
  let h = numOf(hourTok);
  if (h == null || h > 24) return null;
  let m = 0;
  if (half === "半") m = 30;
  else if (minTok != null) {
    const mm = numOf(minTok);
    if (mm == null || mm > 59) return null;
    m = mm;
  }
  const p = period ?? "";
  if (p === "下午" || p === "傍晚" || p === "晚上" || p === "夜里") {
    if (h < 12) h += 12;
  } else if (p === "中午") {
    if (h < 11) h += 12; // 中午1点=13:00
  } else if (p === "早上" || p === "凌晨") {
    if (h === 12) h = 0; // 凌晨12点=00:00
  }
  if (h === 24) h = 0;
  return h * 60 + m;
}

/** 本地 Date → UTC ISO（完整串，服务端 to_utc 无歧义）。 */
function toUtcIso(d: Date): string {
  return d.toISOString();
}

/** 在文本中定位第一个命中时段/日期的短语，返回槽位。 */
function findDateTimeSlot(input: string): { slot: Slot | null; date?: Date; hasTime?: boolean } {
  const text = input.trim();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  function mk(d: Date): Date {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }
  function addDays(base: Date, n: number): Date {
    const d = mk(base);
    d.setDate(d.getDate() + n);
    return d;
  }

  // 1) 相对日 + 可选时刻：明天下午3点 / 后天晚上8点 / 大后天
  // 2) 周X + 可选时刻：周五下午 / 下周一晚上8点半 / 周日
  // 3) 绝对日期：9月25日 / 9月25号 / 9-25 / 9/25 / 月底 / 周末
  // 4) N天后：三天后 / 3天后 / 两个月后（暂只天）
  // 5) 纯时刻：下午3点 / 晚上8点（当天）

  // 组合扫描：按「起始位置最靠前、长度最长」的短语优先。
  const candidates: {
    start: number;
    end: number;
    match: string;
    date: Date | null;
    time?: number;
  }[] = [];

  function push(match: string, date: Date | null, time?: number) {
    const start = text.indexOf(match);
    if (start < 0) return;
    candidates.push({ start, end: start + match.length, match, date, time });
  }

  // 相对日 + 时刻
  const relDayRe = /(大后天|后天|明天|今天|今晚)/;
  const relM = relDayRe.exec(text);
  if (relM) {
    const relDay = relM[1];
    const base =
      relDay === "今天" || relDay === "今晚"
        ? today
        : relDay === "明天"
          ? addDays(today, 1)
          : relDay === "后天"
            ? addDays(today, 2)
            : addDays(today, 3);
    const after = text.slice(relM.index + relDay.length);
    const tm = matchTimeAfter(after);
    const matchLen = relDay.length + (tm?.len ?? 0);
    const full = text.slice(relM.index, relM.index + matchLen);
    push(full, base, tm?.time);
  }

  // 周X（nearest future，与后端一致：已过→下周）
  const weekRe = /(?:下|下个|这|这个)?周([一二三四五六日天])(?:日|天)?/;
  const weekM = weekRe.exec(text);
  if (weekM) {
    const wd = WEEKDAY[weekM[1]];
    const next = weekM[0].startsWith("下");
    let date: Date;
    if (next) {
      date = addDays(today, ((wd - today.getDay() + 7) % 7) + 7);
    } else {
      date = addDays(today, (wd - today.getDay() + 7) % 7 || 7);
    }
    const after = text.slice(weekM.index + weekM[0].length);
    const tm = matchTimeAfter(after);
    const matchLen = weekM[0].length + (tm?.len ?? 0);
    const full = text.slice(weekM.index, weekM.index + matchLen);
    push(full, date, tm?.time);
  }

  // 绝对日期：X月X日 / X月X号 / X-X / X/X / X号
  const absRe =
    /(\d{1,2}|[一二两三四五六七八九十]{1,3})月(\d{1,2}|[一二两三四五六七八九十]{1,3})(?:日|号)?|(\d{1,2})[-/](\d{1,2})|(\d{1,2}|[一二两三四五六七八九十]{1,3})号/;
  const absM = absRe.exec(text);
  if (absM) {
    let date: Date | null = null;
    if (absM[1]) {
      const mo = numOf(absM[1]);
      const da = numOf(absM[2]);
      if (mo != null && da != null && mo >= 1 && mo <= 12 && da >= 1 && da <= 31) {
        const d = new Date(today.getFullYear(), mo - 1, da);
        if (d.getMonth() === mo - 1) date = d;
      }
    } else if (absM[3]) {
      const mo = parseInt(absM[3], 10);
      const da = parseInt(absM[4], 10);
      if (mo >= 1 && mo <= 12 && da >= 1 && da <= 31) {
        const d = new Date(today.getFullYear(), mo - 1, da);
        if (d.getMonth() === mo - 1) date = d;
      }
    } else if (absM[5]) {
      const da = numOf(absM[5]);
      if (da != null && da >= 1 && da <= 31) {
        const d = new Date(today.getFullYear(), today.getMonth(), da);
        if (d.getMonth() === today.getMonth()) date = d;
      }
    }
    if (date) push(absM[0], date);
  }

  // 月底
  const endM = /月底/.exec(text);
  if (endM) {
    const d = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    push(endM[0], d);
  }

  // 周末（本周六，已过则下周六）
  const wkndM = /周末/.exec(text);
  if (wkndM) {
    const sat = addDays(today, (6 - today.getDay() + 7) % 7 || 7);
    push(wkndM[0], sat);
  }

  // N天后
  const daysRe = /(\d{1,2}|[一二两三四五六七八九十]{1,3})天(?:后|之后|以后)/;
  const daysM = daysRe.exec(text);
  if (daysM) {
    const n = numOf(daysM[1]);
    if (n != null && n >= 1 && n <= 99) push(daysM[0], addDays(today, n));
  }

  // 纯时刻（无日期前缀）：下午3点 / 晚上8点
  const pureTimeRe = new RegExp(
    `(^|\\s|，|,|：|:)(凌晨|早上|上午|中午|下午|傍晚|晚上|夜里)?(\\d{1,2}|[一二两三四五六七八九十]{1,2})(点|時|:)(半|(\\d{1,2}|[一二两三四五六七八九十]{1,2})分?)?`,
  );
  const ptM = pureTimeRe.exec(text);
  if (ptM && !relM && !weekM && !absM && !endM && !wkndM && !daysM) {
    const time = timeToMinutes(ptM[2], ptM[3], ptM[5], ptM[6]);
    if (time != null) {
      const d = new Date(today);
      d.setMinutes(time);
      const start = ptM.index + (ptM[1] === "：" || ptM[1] === ":" ? 1 : 0);
      const match = text.slice(start, ptM.index + ptM[0].length);
      candidates.push({ start, end: start + match.length, match, date: d, time });
    }
  }

  if (candidates.length === 0) return { slot: null };
  // 取最靠前；同起点取最长
  candidates.sort((a, b) => a.start - b.start || b.end - a.end);
  let best = candidates[0];
  // ★ @语法糖保护：@明天 是服务端领地，前端不抢（跳过紧邻 @ 的候选）
  while (best && best.start > 0 && text[best.start - 1] === "@") {
    candidates.shift();
    best = candidates[0];
  }
  if (!best) return { slot: null };
  const date = best.date;
  if (!date) return { slot: { start: best.start, end: best.end, match: best.match } };
  const d = new Date(date);
  if (best.time != null) {
    d.setHours(Math.floor(best.time / 60), best.time % 60, 0, 0);
  } else {
    d.setHours(9, 0, 0, 0); // 仅日期时默认上午 9 点
  }
  return {
    slot: { start: best.start, end: best.end, match: best.match },
    date: d,
    hasTime: best.time != null,
  };
}

/** 主入口：自然语言待办 → 结构化。 */
export function parseTodoNL(input: string): TodoNLResult {
  const text = input.trim();
  if (!text) return { text: "", dueAt: null, matched: "", unparsed: null };

  const found = findDateTimeSlot(text);
  if (!found.slot) return { text, dueAt: null, matched: "", unparsed: null };

  const { slot } = found;
  const head = text.slice(0, slot.start).trim();
  const tail = text.slice(slot.end).trim();
  // 中文标点后不加空格（，。！？、；：）
  const needSpace = head && tail && !/[，。！？、；：,.:]/.test(head.slice(-1));
  const cleaned = `${head}${head && tail ? (needSpace ? " " : "") : ""}${tail}`.trim();

  return {
    text: cleaned,
    dueAt: found.date ? toUtcIso(found.date) : null,
    matched: slot.match,
    unparsed: null,
  };
}
