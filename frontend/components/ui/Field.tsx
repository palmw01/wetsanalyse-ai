interface FieldProps {
  label: string;
  hint?: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}

export function Field({ label, hint, required, error, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 flex items-baseline gap-1.5 text-sm font-medium text-ink">
        {label}
        {required && <span className="text-fout">*</span>}
        {hint && <span className="ml-auto text-xs font-normal text-faint">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs text-fout">{error}</span>}
    </label>
  );
}

// Rijkshuisstijl: formulierveld min. hoogte 48px, lichte radius, lintblauwe focus-ring.
// Geëxporteerd zodat samengestelde velden (zoals de Combobox) dezelfde veldstijl dragen.
export const inputBase =
  "w-full min-h-[40px] coarse:min-h-[48px] rounded-field border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-lint focus:outline-none focus:ring-2 focus:ring-lint/30";

// `ComponentProps<"input">` en niet `InputHTMLAttributes`: met React 19 is `ref` een gewone prop, en zo
// kan een aanroeper het veld focussen.
export function Input(props: React.ComponentProps<"input">) {
  return <input {...props} className={`${inputBase} ${props.className ?? ""}`} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${inputBase} resize-y ${props.className ?? ""}`} />;
}

/** Een keuzelijst met een eigen chevron (spoor I4): dezelfde hoogte, radius en focus als `Input`, en op elk
 *  platform hetzelfde pijltje in plaats van dat van het besturingssysteem. `className` gaat naar de schil, zodat
 *  een breedte (`sm:w-56`) ook het pijltje meeneemt. */
export function Select({ className = "", ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={`relative block ${className}`}>
      <select {...props} className={`${inputBase} cursor-pointer appearance-none pr-9`} />
      <svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.6}
        strokeLinecap="round" strokeLinejoin="round"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted">
        <path d="M4 6l4 4 4-4" />
      </svg>
    </span>
  );
}

/** De klassen van een keuzelijst, voor een `<select>` die geen `Select` kan zijn; zonder eigen chevron. */
export const SELECT_KLASSE = `${inputBase} cursor-pointer`;
