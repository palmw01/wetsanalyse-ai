/** Eén filterchip (spoor K): dezelfde vorm in de drie overzichten, op de tab Bronnen, bij de artefacten en in de
 *  bronverkenner. Een keuze is iets wat je aanklikt, dus de vorm van een knop – een kleine rechthoek, geen pil (een pil
 *  is een label; besluit 5 nov 2026) –, gekozen in lintblauw. Met `rol="tab"` hoort hij in een
 *  `tablist` (`aria-selected`), anders is het een schakelaar (`aria-pressed`). */
export function FilterChip({ gekozen, onKies, rol, children, ...rest }: {
  gekozen: boolean;
  onKies: () => void;
  rol?: "tab";
  children: React.ReactNode;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "role">) {
  return (
    <button type="button" onClick={onKies} {...(rol === "tab" ? { role: "tab", "aria-selected": gekozen } : { "aria-pressed": gekozen })}
      className={`focus-ring inline-flex min-h-[28px] items-center rounded-knop-xs border px-3 text-xs font-medium transition coarse:min-h-[44px] ${
        gekozen ? "border-lint bg-lint text-paper" : "border-line bg-paper text-muted hover:border-lint/40 hover:text-lint hover:shadow-zacht"}`}
      {...rest}>
      {children}
    </button>
  );
}
