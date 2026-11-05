import { useId } from "react";
import { jasStyle, klasseLabel } from "@/lib/jas";

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
            {telling !== undefined && <> <span className="font-normal tabular-nums text-muted">{telling}</span></>}
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
                `anywhere` telt mee in de minimale breedte – anders duwt hij de rij uit beeld (Safari). `flex-1`: een
                titel die ter plekke een invoerveld wordt, neemt de breedte van de rij en niet die van de tekst. */}
            <div className="min-w-0 flex-1 text-sm text-ink [overflow-wrap:anywhere]">{titel}</div>
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

export type StatusToon = "groen" | "geel" | "rood" | "neutraal" | "lint";

export const TOON: Record<StatusToon, string> = {
  groen: "border-aandacht-groen-rand bg-aandacht-groen-bg text-aandacht-groen-tekst",
  geel: "border-aandacht-geel-rand bg-aandacht-geel-bg text-aandacht-geel-tekst",
  rood: "border-aandacht-rood-rand bg-aandacht-rood-bg text-aandacht-rood-tekst",
  neutraal: "border-line bg-surface text-muted",
  // Waar iets over gaat (het onderwerp van een vraag, een soort): lintblauw, zonder oordeel.
  lint: "border-lint/25 bg-lint/[0.06] text-lint",
};

/** Het ene label van Lex: een pil met een getint vlak. **Een pil is een label, een afgeronde rechthoek is een knop**
 *  (besluit 5 nov 2026): een label zegt iets en doet niets – geen hover, nooit een `button` of `Link`. Maak geen eigen
 *  label-pil; gebruik dit, met de toon die het oordeel draagt. De stijlgids staat in *Instellingen › Stijl*. */
export function StatusLabel({ toon = "neutraal", uitleg, klein = false, rekbaar = false, children, className = "", ...rest }: {
  toon?: StatusToon;
  /** Wat de stand betekent, als tooltip. */
  uitleg?: string;
  /** Midden in een regel tekst (een klasse vóór een fragment): dezelfde pil, kleiner. */
  klein?: boolean;
  /** Een lange inhoud die mag afkappen (het onderwerp boven het invoerveld): het label krimpt mee. */
  rekbaar?: boolean;
  children: React.ReactNode;
  className?: string;
} & Attrs) {
  return (
    <span title={uitleg}
      className={`inline-flex items-center rounded-full border ${rekbaar ? "min-w-0" : "shrink-0 whitespace-nowrap"} ${LABEL_MAAT[klein ? "klein" : "gewoon"]} ${TOON[toon]} ${className}`}
      {...rest}>
      {children}
    </span>
  );
}

const LABEL_MAAT = { gewoon: "px-2 py-0.5 text-xs font-medium", klein: "px-1.5 text-[10px]" } as const;

/** Een JAS-klasse die alleen informeert (in de passages, de inventaris, de graaf): de pil van `StatusLabel` in de kleur
 *  van de klasse (`jasStyle`). Klikbaar is hij alleen op de reviewkaart, en daar is hij een knop met ▾. */
export function KlasseLabel({ klasse, klein = false, children, className = "", ...rest }: {
  klasse: string;
  klein?: boolean;
  children?: React.ReactNode;
  className?: string;
} & Attrs) {
  return (
    <span className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full border ${LABEL_MAAT[klein ? "klein" : "gewoon"]} ${jasStyle(klasse)} ${className}`}
      {...rest}>
      {children ?? klasseLabel(klasse)}
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
