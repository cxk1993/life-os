import type { ReactNode } from "react";

interface Props {
  icon?: ReactNode;
  text: string;
  hint?: string;
}

export function EmptyState({ icon, text, hint }: Props) {
  return (
    <div className="empty">
      <div className="empty__icon" aria-hidden="true">
        {icon ?? "∅"}
      </div>
      <div className="empty__text">{text}</div>
      {hint ? <div className="empty__hint">{hint}</div> : null}
    </div>
  );
}
