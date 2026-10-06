/** Kleine inline-iconen die tekstkleur en -grootte volgen.
 *
 *  Waarom dit bestaat: de UI gebruikte losse tekens – `▾` voor een uitklapper, `⚠` bij een
 *  waarschuwing, `✓` bij een afgevinkt item, `◇` bij twijfel, `←` voor terug. Die staan geen van
 *  alle in de latin-subset van Fira Sans (`app/fonts.ts`), dus de browser viel terug op het
 *  systeemfont: San Francisco op iOS, Roboto op Android, Segoe op Windows. Andere breedte, ander
 *  gewicht, andere optische grootte – vandaar dat dezelfde kaart op een telefoon net iets anders
 *  oogde dan op een desktop.
 *
 *  Een SVG kent dat probleem niet. Deze zijn `1em` bij `1em` en tekenen met `currentColor`, dus ze
 *  schalen mee met de tekst eromheen en nemen zijn kleur over – precies wat een tekstteken deed,
 *  maar dan overal hetzelfde.
 *
 *  Ze zijn `aria-hidden`: het zijn versieringen bij tekst die de betekenis al draagt. Staat een
 *  icoon alleen (zonder woord ernaast), geef de knop of het element dan zelf een `aria-label`.
 */

interface IcoonProps {
  className?: string;
}

/** Gedeelde vorm: 1em-vierkant, lijntekening in de tekstkleur. */
function svg(pad: React.ReactNode, className = "", extra?: { fill?: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`inline-block h-[1em] w-[1em] shrink-0 ${className}`}
      fill={extra?.fill ? "currentColor" : "none"}
      stroke={extra?.fill ? "none" : "currentColor"}
      strokeWidth={extra?.fill ? undefined : 1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {pad}
    </svg>
  );
}

/** Uitklapper of dropdown. Draai hem met een `rotate-*`-klasse: `-rotate-90` wijst naar links
 *  (terug), `-rotate-180` naar boven (ingeklapt). */
export function ChevronOmlaag({ className = "" }: IcoonProps) {
  return svg(<path d="M4 6l4 4 4-4" />, className);
}

/** Let op – bij een zwevende markering of een teller die aandacht vraagt. */
export function Waarschuwing({ className = "" }: IcoonProps) {
  return svg(
    <>
      <path d="M8 2.5 14.5 13.5h-13L8 2.5Z" />
      <path d="M8 6.5v3.2" />
      <path d="M8 11.8v.01" />
    </>,
    className,
  );
}

/** Afgehandeld, aanwezig, gelukt. */
export function Vinkje({ className = "" }: IcoonProps) {
  return svg(<path d="M3 8.5 6.5 12 13 4.5" />, className);
}

/** Neutraal, onbepaald – er valt niets te melden of niets te controleren. */
export function Cirkel({ className = "" }: IcoonProps) {
  return svg(<circle cx="8" cy="8" r="5.2" />, className);
}

/** Twijfel tussen klassen: de annoteerder zag twee plausibele opties. Bewust een open ruit en geen
 *  uitroepteken – twijfel is geen bezwaar. */
export function Ruit({ className = "" }: IcoonProps) {
  return svg(<path d="M8 2.5 13.5 8 8 13.5 2.5 8Z" />, className);
}

/** Zoeken (vergrootglas). */
export function Zoek({ className = "" }: IcoonProps) {
  return svg(<><circle cx="7" cy="7" r="4.2" /><path d="m10.2 10.2 3.3 3.3" /></>, className);
}

/** Lagen: gestapelde vlakken, voor wat er in beeld staat. */
export function Lagen({ className = "" }: IcoonProps) {
  return svg(<><path d="M8 2.5 14 5.5 8 8.5 2 5.5Z" /><path d="m2 8.5 6 3 6-3" /><path d="m2 11 6 3 6-3" /></>, className);
}

/** Alles in beeld: vier hoeken naar buiten. */
export function Passend({ className = "" }: IcoonProps) {
  return svg(<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" />, className);
}

/** Inzoomen. */
export function Plus({ className = "" }: IcoonProps) {
  return svg(<path d="M8 3v10M3 8h10" />, className);
}

/** Nieuw gesprek: een vel met een pen erop – je begint iets te schrijven. Het vel staat open waar
 *  de pen het raakt, zodat beide vormen leesbaar blijven op 16px. */
export function Opstellen({ className = "" }: IcoonProps) {
  return svg(
    <>
      <path d="M7.5 2.5H4A1.5 1.5 0 0 0 2.5 4v8A1.5 1.5 0 0 0 4 13.5h8a1.5 1.5 0 0 0 1.5-1.5V8.5" />
      <path d="M12.1 1.9a1.3 1.3 0 0 1 1.9 1.9L8.6 9.2 6.2 9.8l.6-2.4z" />
    </>,
    className,
  );
}

/** Uitzoomen. */
export function Min({ className = "" }: IcoonProps) {
  return svg(<path d="M3 8h10" />, className);
}

/** Centreren: vizier. */
export function Richten({ className = "" }: IcoonProps) {
  return svg(<><circle cx="8" cy="8" r="4.5" /><circle cx="8" cy="8" r="1" /><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2" /></>, className);
}

/** Sluiten of wissen (klein kruis, voor in een regel). */
export function Kruis({ className = "" }: IcoonProps) {
  return svg(<path d="m4 4 8 8M12 4l-8 8" />, className);
}
