import type { ReactNode } from "react";

interface Props {
  open: boolean;
  title?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({ open, title, onClose, children, footer }: Props) {
  if (!open) return null;
  return (
    <div className="modal__backdrop" onMouseDown={onClose} role="dialog" aria-modal="true">
      <div className="modal__panel" onMouseDown={(e) => e.stopPropagation()}>
        {title ? <div className="modal__title">{title}</div> : null}
        <div className="modal__body">{children}</div>
        {footer ? <div className="modal__foot">{footer}</div> : null}
      </div>
    </div>
  );
}
