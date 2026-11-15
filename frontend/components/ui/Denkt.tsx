/** Lex is bezig (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §9): drie stippen
 *  die na elkaar oplichten, alleen als de gebruiker beweging toestaat. Bij een antwoord zonder tekst en bij een vraagkaart
 *  die nadenkt; de ene stip van een lopend denkproces is een stand, geen wachten. `app/eenDenkproces.test.ts` bewaakt
 *  dat er geen tweede vorm naast komt. */
export function Denkt({ label = "Bezig" }: { label?: string }) {
  return (
    <span className="inline-flex gap-1" role="status" aria-label={label} data-denkt>
      {[0, 1, 2].map((i) => (
        <span key={i} className="inline-block h-1.5 w-1.5 rounded-full bg-accent-soft motion-safe:animate-pulse"
          style={{ animationDelay: `${i * 150}ms` }} aria-hidden />
      ))}
    </span>
  );
}
