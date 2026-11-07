/** Eén filterchip (spoor K): dezelfde vorm in de drie overzichten, op de tab Bronnen, bij de artefacten en in de
 *  bronverkenner. Een keuze is iets wat je aanklikt, dus de vorm van een knop – een kleine rechthoek, geen pil (een pil
 *  is een label; besluit 5 nov 2026) –, gekozen in lintblauw. Met `rol="tab"` hoort hij in een
 *  `tablist` (`aria-selected`), anders is het een schakelaar (`aria-pressed`). Hij staat altijd in een `KeuzeRij`. */
export function FilterChip({ gekozen, onKies, rol, children, ...rest }: {
  gekozen: boolean;
  onKies: () => void;
  rol?: "tab";
  children: React.ReactNode;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "role">) {
  return (
    <button type="button" onClick={onKies} {...(rol === "tab" ? { role: "tab", "aria-selected": gekozen } : { "aria-pressed": gekozen })}
      className={`focus-ring inline-flex min-h-[28px] shrink-0 items-center whitespace-nowrap rounded-knop-xs border px-3 text-xs font-medium transition coarse:min-h-[44px] ${
        gekozen ? "border-lint bg-lint text-paper" : "border-line bg-paper text-muted hover:border-lint/40 hover:text-lint hover:shadow-zacht"}`}
      {...rest}>
      {children}
    </button>
  );
}

/** De ene rij filterchips (7 nov 2026, melding van de gebruiker: op een iPhone stond *Afgerond* alleen op een tweede
 *  regel). Eén regel, nooit wrappen: past hij niet, dan scrolt hij horizontaal, net als de tabs (`TABRIJ`); een chip die
 *  half uit beeld valt zegt dat er meer is. `p-1 -m-1` geeft de focusrand (4 px buiten de chip) ruimte, want `overflow`
 *  knipt alles wat uitsteekt. `min-w-0` laat de rij in een flexrij krimpen in plaats van de pagina te verbreden. */
export const KEUZERIJ =
  "-m-1 flex min-w-0 max-w-[calc(100%+0.5rem)] gap-1.5 overflow-x-auto overflow-y-hidden overscroll-x-contain p-1";

export function KeuzeRij({ label, rol, className = "", children }: {
  label: string;
  rol?: "tablist";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role={rol ?? "group"} aria-label={label} data-keuzerij className={`${KEUZERIJ} ${className}`}>
      {children}
    </div>
  );
}
