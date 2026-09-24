/** export 数据请求层。 */
import { api } from "@/shared/api/client";

export interface ProfileItem {
  id: string;
  title: string;
}

export interface ProfileList {
  items: ProfileItem[];
}

export interface PreviewOut {
  [k: string]: unknown;
}

const BASE = "/api/v1/export";

export const exportApi = {
  profiles: () => api.get<ProfileList>(`${BASE}/profiles`),
  preview: (profile: string) => api.get<PreviewOut>(`${BASE}/preview/${profile}`),
};
