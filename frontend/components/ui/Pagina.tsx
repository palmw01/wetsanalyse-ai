import Link from "next/link";

import { ChevronOmlaag } from "@/components/ui/Icoon";

/** De bouwstenen van een objectpagina (spoor G2, naar de mock-up v4). Eén idioom op elke pagina:
 *
 *  - `PaginaKop` – kruimelpad, titel, één zin ondertitel, een meta-regel (status · context) en hoogstens
 *    twee knoppen;
 *  - `TabLinks` – de tabs van een project als échte links: elke tab heeft een eigen URL, Terug werkt;
 *  - `Kaart` – een witte kaart met een kop en eventueel *Alles bekijken*;
 *  - `SplitDetail` – links de inhoud, rechts de relaties en de voortgang;
 *  - `ObjectRij` – een compacte rij (titel, subregel, status, chevron) die naar een detailpagina gaat.
 *    Geen knoppen per rij en geen IRI's in beeld: wat je met het object doet, staat op zijn pagina;
 *  - `Groep` + `GroepRij` – een groep rijen in één kader met een kop erboven (`groupbox` + `itemrow` van de
 *    mock-up): de bronnen per deelvraag, de bepalingen per regeling (spoor K);
 *  - `Teller` – een getal met een label, als link naar waar het over gaat. */

export interface Kruimel {
  label: string;
  href?: string;
}

export function Kruimelpad({ items }: { items: Kruimel[] }) {
  return (
    <nav aria-label="Kruimelpad" className="mb-2 flex min-w-0 flex-wrap items-center gap-1 text-xs text-muted">
      {items.map((k, i) => (
        <span key={`${k.label}-${i}`} className="flex min-w-0 items-center gap-1">
          {i > 0 && <ChevronOmlaag className="-rotate-90 text-faint" />}
          {k.href && i < items.length - 1 ? (
            <Link href={k.href} className="focus-ring truncate rounded hover:text-ink hover:underline">{k.label}</Link>
          ) : (
            <span aria-current={i === items.length - 1 ? "page" : undefined} className="truncate">{k.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

export function PaginaKop({ kruimels, titel, sub, meta, acties }: {
  kruimels: Kruimel[];
  titel: React.ReactNode;
  sub?: React.ReactNode;
  meta?: React.ReactNode;
  acties?: React.ReactNode;
}) {
  return (
    <header className="mb-5" data-paginakop>
      <Kruimelpad items={kruimels} />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-xl font-semibold text-lint [overflow-wrap:anywhere]">{titel}</h1>
          {sub && <p className="mt-1 max-w-3xl text-sm text-muted">{sub}</p>}
          {meta && <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">{meta}</div>}
        </div>
        {acties && <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">{acties}</div>}
      </div>
    </header>
  );
}

/** Een punt tussen twee meta-gegevens. */
export function Stip() {
  return <span aria-hidden className="text-faint">·</span>;
}

export function TabLinks({ label, tabs, actief }: {
  label: string;
  tabs: { key: string; label: string; href: string; telling?: number }[];
  actief: string;
}) {
  return (
    // Een rij die op een smal scherm niet past scrolt, in plaats van tabs af te kappen.
    <nav aria-label={label} className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => {
        const gekozen = t.key === actief;
        return (
          <Link key={t.key} href={t.href} aria-current={gekozen ? "page" : undefined} data-tab={t.key}
            // De teller hoort bij de naam, met haakjes: anders leest een schermlezer "Bronnen2".
            aria-label={t.telling !== undefined ? `${t.label} (${t.telling})` : undefined}
            className={`focus-ring -mb-px inline-flex min-h-[44px] shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              gekozen ? "border-lint text-lint" : "border-transparent text-muted hover:text-lint"
            }`}>
            {t.label}
            {t.telling !== undefined && (
              <span className="rounded-full bg-surface px-1.5 text-xs tabular-nums text-muted">{t.telling}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

export function Kaart({ titel, telling, toelichting, meer, acties, children, className = "", ...rest }: {
  titel?: React.ReactNode;
  telling?: React.ReactNode;
  toelichting?: React.ReactNode;
  /** *Alles bekijken* rechts in de kop. */
  meer?: { href: string; label?: string };
  acties?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
} & Omit<React.HTMLAttributes<HTMLElement>, "title">) {
  return (
    <section className={`rounded-kaart border border-line bg-paper p-4 shadow-zacht sm:p-5 ${className}`} {...rest}>
      {(titel || meer || acties) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {titel && (
              <h2 className="font-display text-sm font-semibold text-ink">
                {titel}
                {telling !== undefined && <span className="ml-1.5 font-normal tabular-nums text-muted">{telling}</span>}
              </h2>
            )}
            {toelichting && <p className="mt-0.5 text-xs text-muted">{toelichting}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {acties}
            {meer && (
              <Link href={meer.href} className="focus-ring rounded text-xs font-medium text-lint hover:underline">
                {meer.label ?? "Alles bekijken"}
              </Link>
            )}
          </div>
        </div>
      )}
      {children}
    </section>
  );
}

export function SplitDetail({ hoofd, zij }: { hoofd: React.ReactNode; zij: React.ReactNode }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="min-w-0 space-y-4">{hoofd}</div>
      <aside className="min-w-0 space-y-4">{zij}</aside>
    </div>
  );
}

export function ObjectRijen({ label, children, leeg }: { label: string; children: React.ReactNode; leeg?: React.ReactNode }) {
  const kinderen = Array.isArray(children) ? children.filter(Boolean) : children;
  if (leeg && Array.isArray(kinderen) && kinderen.length === 0) return <p className="text-sm text-muted">{leeg}</p>;
  return <ul aria-label={label} className="-mx-2 divide-y divide-line">{kinderen}</ul>;
}

export function ObjectRij({ href, titel, sub, status, voor, ...rest }: {
  href: string;
  titel: React.ReactNode;
  sub?: React.ReactNode;
  status?: React.ReactNode;
  voor?: React.ReactNode;
} & Omit<React.LiHTMLAttributes<HTMLLIElement>, "title">) {
  return (
    <li {...rest}>
      <Link href={href}
        className="focus-ring group flex min-h-[44px] items-center gap-3 rounded-md px-2 py-2.5 transition-colors hover:bg-surface">
        {voor !== undefined && <span className="shrink-0 text-sm tabular-nums text-muted">{voor}</span>}
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink [overflow-wrap:anywhere] group-hover:text-lint">{titel}</span>
          {sub && <span className="mt-0.5 block text-xs text-muted [overflow-wrap:anywhere]">{sub}</span>}
        </span>
        {status && <span className="flex shrink-0 flex-wrap justify-end gap-1.5">{status}</span>}
        <ChevronOmlaag className="shrink-0 -rotate-90 text-faint group-hover:text-lint" />
      </Link>
    </li>
  );
}

/** Een groep rijen in één kader (spoor K, de `groupbox` van de mock-up): een kop met telling en status, en
 *  daaronder de rijen met een scheidingslijn – rustiger dan losse kaartjes, en geen boom. */
export function Groep({ kop, sub, telling, status, label, children, leeg, ...rest }: {
  kop: React.ReactNode;
  sub?: React.ReactNode;
  telling?: React.ReactNode;
  status?: React.ReactNode;
  /** De toegankelijke naam van de lijst. */
  label: string;
  children?: React.ReactNode;
  /** Wat er staat als de groep geen rijen heeft. */
  leeg?: React.ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, "title">) {
  const kinderen = Array.isArray(children) ? children.flat().filter(Boolean) : children ? [children] : [];
  return (
    <section {...rest}>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2.5 gap-y-1 border-b border-line pb-2">
        <h3 className="min-w-0 font-display text-sm font-semibold text-lint [overflow-wrap:anywhere]">{kop}</h3>
        {telling !== undefined && <span className="text-xs tabular-nums text-muted">{telling}</span>}
        {status && <span className="ml-auto flex shrink-0 items-center gap-1.5">{status}</span>}
        {sub && <p className="w-full text-xs text-muted">{sub}</p>}
      </div>
      {kinderen.length ? (
        <ul aria-label={label} className="divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper shadow-zacht">
          {kinderen}
        </ul>
      ) : leeg ? <p className="text-sm text-muted">{leeg}</p> : null}
    </section>
  );
}

/** Eén rij in een `Groep` (de `itemrow` van de mock-up): titel, subregel, status en een chevron naar de pagina
 *  van het object. `eind` staat buiten de link (een menu ⋯), `onder` eronder (dat menu, uitgeklapt). */
export function GroepRij({ href, titel, sub, status, eind, onder, ...rest }: {
  href: string;
  titel: React.ReactNode;
  sub?: React.ReactNode;
  status?: React.ReactNode;
  eind?: React.ReactNode;
  onder?: React.ReactNode;
} & Omit<React.LiHTMLAttributes<HTMLLIElement>, "title">) {
  return (
    <li {...rest}>
      <div className="flex items-center gap-2 pr-2 transition-colors hover:bg-surface">
        <Link href={href} className="focus-ring group flex min-h-[48px] min-w-0 flex-1 items-center gap-3 rounded-md py-3 pl-4">
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-lint [overflow-wrap:anywhere] group-hover:underline">{titel}</span>
            {sub && <span className="mt-0.5 block text-xs leading-relaxed text-muted [overflow-wrap:anywhere]">{sub}</span>}
          </span>
          {status && <span className="flex shrink-0 flex-wrap justify-end gap-1.5">{status}</span>}
          <ChevronOmlaag className="shrink-0 -rotate-90 text-faint group-hover:text-lint" />
        </Link>
        {eind}
      </div>
      {onder}
    </li>
  );
}

export function Tellers({ children }: { children: React.ReactNode }) {
  return <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>;
}

export function Teller({ getal, label, href }: { getal: React.ReactNode; label: string; href: string }) {
  return (
    <Link href={href} data-teller={label}
      className="focus-ring flex flex-col rounded-kaart border border-line bg-paper px-4 py-3 shadow-zacht transition-colors hover:border-lint">
      <span className="font-display text-2xl font-semibold tabular-nums text-lint">{getal ?? "–"}</span>
      <span className="text-xs text-muted">{label}</span>
    </Link>
  );
}
