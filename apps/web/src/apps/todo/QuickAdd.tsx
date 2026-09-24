import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { todoApi } from "./api";
import { parseTodoNL } from "./todo-nl";

/**
 * 一句话快速添加。
 * - 支持语法糖 @自然语言日期 / !高|中|低 / #标签（服务端解析，原文透传）；
 * - TX-TODO-NL-01 增量：前端离线解析「更自然的表达」（明天下午3点/下周一/月底…），
 *   命中则结构化提交（带时刻 due_at），未命中原文走服务端语法糖兜底；
 * - 纯本地规则、零网络（隐私边界：不上云）。
 */
export default function QuickAdd() {
  const [text, setText] = useState("");
  const qc = useQueryClient();

  // 实时预览：输入时本地解析（纯函数，无副作用）
  const preview = useMemo(() => {
    const r = parseTodoNL(text);
    if (!r.matched) return null;
    const when = r.dueAt
      ? new Date(r.dueAt).toLocaleString("zh-CN", {
          month: "numeric",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
      : "";
    return { text: r.text, when, matched: r.matched };
  }, [text]);

  const mut = useMutation({
    mutationFn: async () => {
      const r = parseTodoNL(text);
      // 命中自然语言 → 结构化（文本剥离日期时间，due_at 带时刻）；未命中 → 原文服务端语法糖兜底
      if (r.matched && r.dueAt) {
        return todoApi.createStructured({ text: r.text, due_at: r.dueAt });
      }
      return todoApi.create(text);
    },
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["todo"] });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = parseTodoNL(text);
    // 纯日期短语（无正文）不允许提交
    if (!text.trim() || mut.isPending || (r.matched && !r.text)) return;
    mut.mutate();
  };

  const canSubmit = !!text.trim() && !mut.isPending && !(preview && !preview.text);

  // H4（令56）：离线/失败不再静默——错误可见、输入保留、可重试。
  const submitError = mut.isError
    ? mut.error instanceof Error
      ? mut.error.message
      : "未知错误"
    : null;

  return (
    <form className="todo-quick" onSubmit={submit}>
      <input
        className="todo-quick__input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="快速添加：明天下午3点交房租 / 写周报 @周五 !高 #副业"
        aria-label="快速添加待办"
      />
      {preview && (
        <div className="todo-quick__preview" data-testid="todo-nl-preview">
          {preview.text ? (
            <>
              待办：<strong>{preview.text}</strong> · 截止 <strong>{preview.when}</strong>
            </>
          ) : (
            <>
              已识别截止时间：<strong>{preview.when}</strong>（补一句待办正文）
            </>
          )}
        </div>
      )}
      {submitError && (
        <div className="todo-quick__error" role="alert" data-testid="todo-quick-error">
          保存失败：{submitError}。输入已保留，可稍后重试。
        </div>
      )}
      <button className="btn btn--primary" type="submit" disabled={!canSubmit}>
        {mut.isPending ? "添加中…" : "添加"}
      </button>
    </form>
  );
}
