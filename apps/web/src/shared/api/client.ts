/**
 * 通用 API 客户端（内核提供，任何模块共用）。
 *
 * 职责（总纲 §1.4）：
 *   - 自动注入 `Authorization: Bearer <jwt>`（token 来源可插拔，鉴权由内核统一处理）。
 *   - 失败响应解析 RFC7807 `application/problem+json` → 抛结构化 ApiError。
 *   - 透传后端 `X-Trace-Id`，便于前后端串日志。
 *   - 后端未就绪 / 断网时，抛结构化错误而不是让调用方白屏。
 *
 * 这是通用封装，**不写任何模块专用请求**（那属于各模块的 api.ts）。
 */

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  trace_id?: string;
}

export class ApiError extends Error {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail?: string;
  readonly traceId?: string;

  constructor(p: Problem) {
    super(p.title);
    this.name = "ApiError";
    this.type = p.type;
    this.title = p.title;
    this.status = p.status;
    this.detail = p.detail;
    this.traceId = p.trace_id;
  }
}

let tokenGetter: () => string | null = () => {
  try {
    return localStorage.getItem("lifeos.token");
  } catch {
    return null;
  }
};

/** 由鉴权内核注入取 token 的方式（T03 会接这里）。 */
export function setTokenGetter(fn: () => string | null): void {
  tokenGetter = fn;
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem("lifeos.token", token);
    else localStorage.removeItem("lifeos.token");
  } catch {
    /* 忽略存储异常 */
  }
}

const JSON_ACCEPT = "application/json";
const PROBLEM_TYPE = "application/problem+json";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers = new Headers({ Accept: JSON_ACCEPT });
  const tok = tokenGetter();
  if (tok) headers.set("Authorization", `Bearer ${tok}`);
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    headers.set("Content-Type", JSON_ACCEPT);
    payload = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch (e) {
    throw new ApiError({
      type: "https://lifeos/network-error",
      title: "网络不可用",
      status: 0,
      detail: e instanceof Error ? e.message : String(e),
    });
  }

  const traceId = res.headers.get("X-Trace-Id") ?? undefined;
  const ct = res.headers.get("content-type") ?? "";
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      /* 非 JSON 响应体 */
    }
  }

  if (!res.ok) {
    if (ct.includes(PROBLEM_TYPE) && data && typeof data === "object") {
      const p = data as Record<string, unknown>;
      throw new ApiError({
        type: typeof p.type === "string" ? p.type : "about:blank",
        title: typeof p.title === "string" ? p.title : "请求失败",
        status: typeof p.status === "number" ? p.status : res.status,
        detail: typeof p.detail === "string" ? p.detail : text || res.statusText,
        trace_id: (p.trace_id as string | undefined) ?? traceId,
      });
    }
    throw new ApiError({
      type: "about:blank",
      title: `HTTP ${res.status}`,
      status: res.status,
      detail: text || res.statusText,
      trace_id: traceId,
    });
  }

  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
