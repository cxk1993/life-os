/**
 * 日程事件数据层：TanStack Query 拉取 + SSE 增量合并 + 乐观更新/回滚。
 *
 * 设计要点（对齐总纲 §1.4 / 验收清单）：
 * - SSE 推送只做「增量合并」（按 id 替换/删除根），不整表重拉。
 * - 拖动/缩放松手立即本地生效（乐观），后台 PATCH；失败回滚 + toast。
 * - 写请求自带 Idempotency-Key（见 api.ts），断网重试由内核去重。
 */

import { useCallback, useRef } from "react";
import { useMutation, useQuery, useQueryClient, keepPreviousData, type QueryKey } from "@tanstack/react-query";
import { usePluginEvent } from "@/shared/api/events";
import { calendarApi, type CalendarEvent, type EventPatch, type EventCreate } from "../api";
import { replaceRoot, removeRoot } from "../lib/cache";
import { shiftTree } from "../lib/time";
import { toast } from "../state";

export interface Range {
  from: string;
  to: string;
}

/** 乐观移动：start_at 变化则整棵子树同 delta 平移（父块移动/缩放子块跟随）。 */
export function applyOptimisticMove(
  list: CalendarEvent[],
  id: string,
  patch: EventPatch,
): CalendarEvent[] {
  const root = list.find((e) => e.id === id);
  if (!root) return list;
  if (patch.start_at) {
    const delta = new Date(patch.start_at).getTime() - new Date(root.start_at).getTime();
    return replaceRoot(list, shiftTree(root, delta));
  }
  return replaceRoot(list, { ...root, ...patch } as CalendarEvent);
}

export function useCalendarEvents(range: Range) {
  const qc = useQueryClient();
  const queryKey: QueryKey = ["calendar", "events", range.from, range.to];
  // 用 ref 持有最新 key，SSE 回调不会被旧 key 锁死。
  const keyRef = useRef<QueryKey>(queryKey);
  keyRef.current = queryKey;

  const query = useQuery({
    queryKey,
    queryFn: () => calendarApi.listRange(range.from, range.to),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const onCreated = useCallback(
    (payload: unknown) =>
      qc.setQueryData<CalendarEvent[]>(keyRef.current, (old = []) =>
        replaceRoot(old, payload as CalendarEvent),
      ),
    [qc],
  );
  const onUpdated = useCallback(
    (payload: unknown) =>
      qc.setQueryData<CalendarEvent[]>(keyRef.current, (old = []) =>
        replaceRoot(old, payload as CalendarEvent),
      ),
    [qc],
  );
  const onDeleted = useCallback(
    (payload: unknown) => {
      const id = (payload as { id?: string })?.id;
      if (id) qc.setQueryData<CalendarEvent[]>(keyRef.current, (old = []) => removeRoot(old, id));
    },
    [qc],
  );

  usePluginEvent("calendar.event.created", onCreated);
  usePluginEvent("calendar.event.updated", onUpdated);
  usePluginEvent("calendar.event.deleted", onDeleted);

  const updateEvent = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: EventPatch }) => calendarApi.update(id, patch),
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey });
      const prev = qc.getQueryData<CalendarEvent[]>(queryKey) ?? [];
      qc.setQueryData(queryKey, applyOptimisticMove(prev, id, patch));
      return { prev };
    },
    onError: (err, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKey, ctx.prev);
      toast(`更新失败，已回滚：${(err as Error).message}`, "err");
    },
    onSuccess: (data) =>
      qc.setQueryData<CalendarEvent[]>(queryKey, (old = []) => replaceRoot(old, data)),
  });

  const createEvent = useMutation({
    mutationFn: (input: EventCreate) => calendarApi.create(input),
    onSuccess: (data) =>
      qc.setQueryData<CalendarEvent[]>(queryKey, (old = []) => replaceRoot(old, data)),
    onError: (err) => toast(`新建失败：${(err as Error).message}`, "err"),
  });

  const deleteEvent = useMutation({
    mutationFn: (id: string) => calendarApi.remove(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey });
      const prev = qc.getQueryData<CalendarEvent[]>(queryKey) ?? [];
      qc.setQueryData(queryKey, removeRoot(prev, id));
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKey, ctx.prev);
      toast("删除失败，已回滚", "err");
    },
  });

  const addChild = useMutation({
    mutationFn: ({ parentId, input }: { parentId: string; input: EventCreate }) =>
      calendarApi.addChild(parentId, input),
    onSuccess: (data) =>
      qc.setQueryData<CalendarEvent[]>(queryKey, (old = []) => replaceRoot(old, data)),
    onError: (err) => toast(`新建子块失败：${(err as Error).message}`, "err"),
  });

  const updateChild = useMutation({
    mutationFn: ({
      parentId,
      childId,
      patch,
    }: {
      parentId: string;
      childId: string;
      patch: EventPatch;
    }) => calendarApi.updateChild(parentId, childId, patch),
    onSuccess: (data) =>
      qc.setQueryData<CalendarEvent[]>(queryKey, (old = []) => replaceRoot(old, data)),
    onError: (err) => toast(`更新子块失败：${(err as Error).message}`, "err"),
  });

  const deleteChild = useMutation({
    mutationFn: ({ parentId, childId }: { parentId: string; childId: string }) =>
      calendarApi.removeChild(parentId, childId),
    // DELETE 返回空体：无新状态可合并，直接失效本查询让服务端真值回流。
    onSuccess: () => qc.invalidateQueries({ queryKey }),
    onError: (err) => toast(`删除子块失败：${(err as Error).message}`, "err"),
  });

  return {
    events: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    updateEvent,
    createEvent,
    deleteEvent,
    addChild,
    updateChild,
    deleteChild,
  };
}
