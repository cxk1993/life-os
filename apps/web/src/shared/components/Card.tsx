import type { ReactNode } from "react";

interface Props {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, children, className = "" }: Props) {
  return (
    <div className={`card ${className}`}>
      {title ? <div className="card__title">{title}</div> : null}
      <div className="card__body">{children}</div>
    </div>
  );
}
