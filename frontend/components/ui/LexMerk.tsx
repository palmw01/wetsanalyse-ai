/** De rechthoeken van het merk op een raster van 32 (x, y, breedte, hoogte), gelijk aan `merk/lex-merk.svg`.
 *  Even maten, zodat het merk op 16 en 32 px op hele pixels valt. `app/iconen.test.ts` vergelijkt ze met
 *  de bron, dus wijzig ze daar en hier samen (en draai `npm run iconen`). */
export const LEX_MERK_REGELS: readonly (readonly [number, number, number, number])[] = [
  [6, 6, 20, 4],
  [6, 14, 6, 4],
  [6, 22, 14, 4],
];
export const LEX_MERK_MARKERING = [16, 14, 10, 4] as const;
export const LEX_MERK_RADIUS = 7;

/** Het beeldmerk van Lex: drie regels wettekst, in de middelste één fragment gemarkeerd. De kleuren komen uit
 *  de merktokens (`--merk-*` in `app/globals.css`), dus de donkere modus van later zet alleen die om.
 *
 *  Decoratief (`aria-hidden`): de naam "Lex" staat ernaast of in het `aria-label` van de link eromheen.
 *  `tegel={false}` laat het vlak weg, voor een donkere of eigen achtergrond. */
export function LexMerk({ className = "", tegel = true }: { className?: string; tegel?: boolean }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false" className={className} data-lex-merk="">
      {tegel && (
        <rect
          width="32"
          height="32"
          rx={LEX_MERK_RADIUS}
          style={{ fill: "rgb(var(--merk-vlak))", fillOpacity: "var(--merk-vlak-dekking)" }}
        />
      )}
      <g style={{ fill: "rgb(var(--merk-vorm))" }}>
        {LEX_MERK_REGELS.map(([x, y, w, h]) => (
          <rect key={`${x}-${y}`} x={x} y={y} width={w} height={h} />
        ))}
      </g>
      <rect
        x={LEX_MERK_MARKERING[0]}
        y={LEX_MERK_MARKERING[1]}
        width={LEX_MERK_MARKERING[2]}
        height={LEX_MERK_MARKERING[3]}
        style={{ fill: "rgb(var(--merk-markering))" }}
      />
    </svg>
  );
}

/** Het logo van de applicatie: het beeldmerk met de naam en wat Lex doet. Het staat op elke plek waar de app
 *  zich voorstelt: bovenin de sidebar (`compact`) en boven de kaart van het inlogscherm en de andere schermen
 *  buiten de schil (`groot`, gecentreerd). De naam is gewone tekst in de app-letter, dus leesbaar voor een
 *  schermlezer; het merk zelf is decoratief.
 *
 *  Maten op het raster van het merk (32 en 48 px), zodat de regels op hele pixels vallen. */
export function LexLogo({ variant = "compact", className = "" }: { variant?: "compact" | "groot"; className?: string }) {
  const groot = variant === "groot";
  return (
    <span
      className={`flex items-center leading-tight ${groot ? "flex-col gap-3 text-center" : "gap-2.5"} ${className}`}
      data-lex-logo={variant}
    >
      <LexMerk className={`shrink-0 ${groot ? "h-12 w-12" : "h-8 w-8"}`} />
      <span className="block">
        <span className={`block font-display font-semibold text-lint ${groot ? "text-2xl" : "text-lg"}`}>Lex</span>
        <span className={`block text-muted ${groot ? "text-sm" : "text-xs"}`}>Juridische analyse met AI</span>
      </span>
    </span>
  );
}
