/** Een suggestie: een vraag of opdracht die Lex met één klik stuurt. De vorm van de voorbeeldvragen in de lege
 *  werkplek (5 nov 2026, het stijlblad): een afgeronde rechthoek met een lijn, een zachte schaduw en een kleine lift bij
 *  hover. `klein` is dezelfde vorm, compact, voor de suggesties boven het invoerveld. Het is een knop, dus nooit een pil
 *  (een pil is een label). */
export function suggestieKlasse(klein = false): string {
  const vorm = klein
    ? "min-h-[24px] rounded-knop px-2.5 py-1 text-xs text-muted hover:-translate-y-px hover:text-ink coarse:min-h-[44px]"
    : "rounded-bubbel px-4 py-2.5 text-sm text-lint hover:-translate-y-0.5";
  return `focus-ring inline-flex items-center border border-line bg-paper text-left shadow-zacht transition-all hover:border-lint/40 hover:shadow-kaart motion-reduce:hover:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:border-line disabled:hover:shadow-zacht ${vorm}`;
}

export function Suggestie({ klein = false, className = "", ...props }: { klein?: boolean }
  & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={`${suggestieKlasse(klein)} ${className}`} {...props} />;
}
