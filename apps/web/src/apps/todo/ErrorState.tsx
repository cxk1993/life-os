interface Props {
  error: unknown;
  onRetry: () => void;
}

/**
 * 统一的错误态（断网 / 上游挂 / 4xx-5xx）。
 * 只渲染明确提示 + 重试按钮，不无限转圈（边界测试 #4 要求）。
 * 不处理空态，空态交给 EmptyState。
 */
export default function ErrorState({ error, onRetry }: Props) {
  const msg = error instanceof Error ? error.message : "请求失败，请稍后重试";
  return (
    <div className="todo-error" role="alert">
      <div className="todo-error__title">加载失败</div>
      <div className="todo-error__msg">{msg}</div>
      <button className="btn btn--primary todo-error__retry" onClick={onRetry}>
        重试
      </button>
    </div>
  );
}
