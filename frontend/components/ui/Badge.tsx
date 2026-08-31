export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-field border border-line bg-surface px-2 py-0.5 font-mono text-xs text-muted">
      {children}
    </span>
  );
}
