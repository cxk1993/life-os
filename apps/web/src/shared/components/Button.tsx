import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "ghost", className = "", ...rest }: Props) {
  return <button className={`btn btn--${variant} ${className}`} {...rest} />;
}
