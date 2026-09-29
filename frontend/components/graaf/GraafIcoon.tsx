/** Het graaficoon van de tab en de chatknop: drie verbonden knopen. */
export function GraafIcoon({ className = "h-4 w-4" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
    <path d="m6 7 12 2M6 7l5 12m7-10-7 10" /><circle cx="6" cy="7" r="3" fill="currentColor" stroke="none" />
    <circle cx="18" cy="9" r="3" fill="currentColor" stroke="none" /><circle cx="11" cy="19" r="3" fill="currentColor" stroke="none" />
  </svg>;
}
