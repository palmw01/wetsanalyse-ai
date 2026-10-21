import { useId } from "react";

/** De lijststijl van de werkgebieden (F3a): rijen met een scheidingslijn, zoals de vraagkaart van Lex,
 *  in plaats van een omrande box per deelvraag, bron of kandidaat. Een box per rij maakt van elke lijst
 *  een stapel kaarten; een lijn ertussen laat de inhoud spreken.
 *
 *  - `Sectie` – een kop met telling, toelichting en acties, zonder rand eromheen;
 *  - `Lijst` + `LijstRij` – de rijen: titel, meta, status rechts, acties eronder;
 *  - `Voorstel` – een rij die een voorstel van Lex is: een gele rand links, met tekst erbij;
 *  - `StatusLabel` – een pil met tekst; kleur alleen als hij een oordeel draagt;
 *  - `Regels` + `Regel` – naam en waarde, zoals de samenvatting van de vraagkaart.
 *
 *  Elk onderdeel geeft overige attributen (`data-*`, `aria-*`) door aan zijn element. */

type Attrs = Omit<React.HTMLAttributes<HTMLElement>, "title">;

export function Sectie({ titel, telling, toelichting, acties, niveau = 2, children, className = "", ...rest }: {
  titel: React.ReactNode;
  telling?: number;
  toelichting?: React.ReactNode;
  /** Knoppen rechts van de kop; mobiel eronder, op volle breedte. */
  acties?: React.ReactNode;
  niveau?: 2 | 3;
  children?: React.ReactNode;
  className?: string;
} & Attrs) {
  const id = useId();
  const Kop = niveau === 3 ? "h3" : "h2";
  return (
    <section aria-labelledby={id} className={className} {...rest}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <Kop id={id} className="font-display text-sm font-semibold text-ink">
            {titel}
            {telling !== undefined && <span className="ml-1.5 font-normal tabular-nums text-muted">{telling}</span>}
          </Kop>
          {toelichting && <p className="mt-0.5 text-xs text-muted">{toelichting}</p>}
        </div>
        {acties && <div className="flex shrink-0 flex-col gap-2 sm:flex-row">{acties}</div>}
      </div>
      {children !== undefined && <div className="mt-2 space-y-3">{children}</div>}
    </section>
  );
}

export function Lijst({ genummerd = false, label, children, className = "", ref, ...rest }: {
  genummerd?: boolean;
  label: string;
  children: React.ReactNode;
  className?: string;
  ref?: React.Ref<HTMLUListElement & HTMLOListElement>;
} & Attrs) {
  const Tag = genummerd ? "ol" : "ul";
  return (
    <Tag ref={ref} aria-label={label} className={`divide-y divide-line ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

export function LijstRij({ voor, titel, meta, status, acties, actief = false, children, className = "", ...rest }: {
  /** Vóór de titel: een nummer of een vinkje. */
  voor?: React.ReactNode;
  titel: React.ReactNode;
  meta?: React.ReactNode;
  /** Rechts van de titel, bovenaan uitgelijnd: een `StatusLabel`. */
  status?: React.ReactNode;
  /** Onder de titel, mobiel gestapeld. */
  acties?: React.ReactNode;
  /** De rij onder de cursor van het toetsenbord. */
  actief?: boolean;
  /** Onder de acties: een formulier dat openklapt. */
  children?: React.ReactNode;
  className?: string;
} & Omit<React.LiHTMLAttributes<HTMLLIElement>, "title">) {
  return (
    // De tint van de actieve rij loopt met een ring buiten de rij door: een negatieve marge zou de
    // scheidingslijn buiten de kolom laten lopen.
    <li className={`rounded-sm py-3 ${actief ? "bg-lint/[0.06] ring-[6px] ring-lint/[0.06]" : ""} ${className}`} {...rest}>
      <div className="flex items-start gap-3">
        {voor !== undefined && <span className="shrink-0 pt-px text-sm tabular-nums text-muted">{voor}</span>}
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
            {/* `overflow-wrap: anywhere` en niet `break-words`: een bron-IRI is één lang woord, en alleen
                `anywhere` telt mee in de minimale breedte – anders duwt hij de rij uit beeld (Safari). */}
            <div className="min-w-0 text-sm text-ink [overflow-wrap:anywhere]">{titel}</div>
            {status && <div className="flex shrink-0 flex-wrap gap-1.5">{status}</div>}
          </div>
          {meta && <div className="mt-0.5 text-xs text-muted [overflow-wrap:anywhere]">{meta}</div>}
          {acties && <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap">{acties}</div>}
          {children}
        </div>
      </div>
    </li>
  );
}

/** Een voorstel van Lex in een lijst: geel, want het is een voorstel – met tekst, zodat het niet alleen
 *  aan kleur hangt. */
export function Voorstel({ titel, acties, children, className = "", ...rest }: {
  titel: React.ReactNode;
  acties?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
} & Omit<React.LiHTMLAttributes<HTMLLIElement>, "title">) {
  return (
    <li className={`border-l-2 !border-l-aandacht-geel-rand bg-aandacht-geel-bg/40 py-3 pl-3 pr-2 ${className}`} {...rest}>
      <p className="text-xs font-medium text-aandacht-geel-tekst">Voorstel van Lex</p>
      <div className="mt-0.5 break-words text-sm text-ink">{titel}</div>
      {acties && <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap">{acties}</div>}
      {children}
    </li>
  );
}

export type StatusToon = "groen" | "geel" | "neutraal";

const TOON: Record<StatusToon, string> = {
  groen: "border-aandacht-groen-rand bg-aandacht-groen-bg text-aandacht-groen-tekst",
  geel: "border-aandacht-geel-rand bg-aandacht-geel-bg text-aandacht-geel-tekst",
  neutraal: "border-line bg-surface text-muted",
};

export function StatusLabel({ toon = "neutraal", uitleg, children, className = "", ...rest }: {
  toon?: StatusToon;
  /** Wat de stand betekent, als tooltip. */
  uitleg?: string;
  children: React.ReactNode;
  className?: string;
} & Attrs) {
  return (
    <span title={uitleg}
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${TOON[toon]} ${className}`}
      {...rest}>
      {children}
    </span>
  );
}

export function Regels({ children, className = "", ...rest }: { children: React.ReactNode; className?: string } & Attrs) {
  return <dl className={`divide-y divide-line ${className}`} {...rest}>{children}</dl>;
}

export function Regel({ naam, children, ...rest }: { naam: React.ReactNode; children: React.ReactNode } & Attrs) {
  return (
    <div className="grid gap-0.5 py-2.5 sm:grid-cols-[8rem_1fr] sm:gap-3" {...rest}>
      <dt className="text-sm text-muted">{naam}</dt>
      <dd className="min-w-0 break-words text-ink">{children}</dd>
    </div>
  );
}
