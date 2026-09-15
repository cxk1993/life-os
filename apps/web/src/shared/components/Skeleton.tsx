interface Props {
  width?: string | number;
  height?: number;
  rounded?: boolean;
}

export function Skeleton({ width = "100%", height = 12, rounded = false }: Props) {
  return (
    <div
      className={`skeleton${rounded ? " skeleton--round" : ""}`}
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height: `${height}px`,
      }}
      aria-hidden="true"
    />
  );
}
