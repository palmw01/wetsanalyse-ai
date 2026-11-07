export function Card({
  children,
  className = "",
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-kaart border border-line bg-surface ${className}`} {...rest}>{children}</div>
  );
}

