import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { todoApi } from "./api";

/**
 * 一句话快速添加：支持语法糖 @自然语言日期 / !高|中|低 / #标签。
 * 实际解析在服务端完成，前端只把原始文本 POST 出去。
 */
export default function QuickAdd() {
  const [text, setText] = useState("");
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: () => todoApi.create(text),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["todo"] });
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || mut.isPending) return;
    mut.mutate();
  };

  return (
    <form className="todo-quick" onSubmit={submit}>
      <input
        className="todo-quick__input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="快速添加：写周报 @周五 !高 #副业"
        aria-label="快速添加待办"
      />
      <button
        className="btn btn--primary"
        type="submit"
        disabled={mut.isPending || !text.trim()}
      >
        添加
      </button>
    </form>
  );
}
