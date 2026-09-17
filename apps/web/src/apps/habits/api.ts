/** 习惯打卡数据请求层。鉴权 / RFC7807 由 @/shared/api/client 统一处理。 */
import { api } from "@/shared/api/client";

export type RuleType = "daily" | "weekly" | "custom";

export interface Rule {
  type: RuleType;
  times?: number | null;
  days?: number[] | null;
}

export interface Habit {
  id: string;
  name: string;
  target: string;
  rule: Rule;
  color: string;
  reminder_time: string;
  rest_weekdays: number[];
  archived: boolean;
  sort: number;
  today_status: "done" | "pending" | "rest";
  streak: number;
  created_at: string;
  updated_at: string;
}

export interface HabitCreate {
  name: string;
  target?: string;
  rule?: Rule;
  rest_weekdays?: number[];
}

export interface Summary {
  total: number;
  done: number;
  pending: number;
  rest: number;
  best_streak: number;
}

const BASE = "/api/v1/habits";

export const habitsApi = {
  list: () => api.get<Habit[]>(`${BASE}/habits`),
  create: (body: HabitCreate) => api.post<Habit>(`${BASE}/habits`, body),
  update: (id: string, body: Partial<Habit>) =>
    api.patch<Habit>(`${BASE}/habits/${id}`, body),
  remove: (id: string) => api.delete<void>(`${BASE}/habits/${id}`),
  checkin: (id: string, body: { value?: string; note?: string } = {}) =>
    api.post<Habit>(`${BASE}/habits/${id}/checkin`, body),
  uncheck: (id: string, day: string) =>
    api.delete<Habit>(`${BASE}/habits/${id}/checkin/${day}`),
  summary: () => api.get<Summary>(`${BASE}/summary`),
};
