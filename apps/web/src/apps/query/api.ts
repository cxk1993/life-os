/** query 数据请求层。 */
import { api } from "@/shared/api/client";

export interface PresetItem {
  id: string;
  title: string;
}

export interface PresetList {
  items: PresetItem[];
}

export interface QueryRow {
  [k: string]: unknown;
}

export interface QueryResult {
  query: { id: string; empty_text?: string };
  rows: QueryRow[];
  row_count: number;
  empty: boolean;
  partial?: boolean;
  errors?: string[];
}

const BASE = "/api/v1/query";

export const queryApi = {
  presets: () => api.get<PresetList>(`${BASE}/presets`),
  run: (qid: string, days?: number) =>
    api.get<QueryResult>(
      `${BASE}/presets/${qid}${days && days > 0 ? `?days=${days}` : ""}`,
    ),
};
