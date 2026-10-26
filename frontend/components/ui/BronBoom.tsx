"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import { bladerenVan, type Blad, type BoomKnoop } from "@/lib/bronPlaats";

/** Bepalingen als boom (spoor H): regeling › hoofdstuk/afdeling › artikel › lid, elk niveau in te klappen,
 *  met per kop het aantal. Het blad tekent de aanroeper (`renderBlad`). Met `vinkjes` heeft elk blad een
 *  vinkje en elke kop een vinkje met drie standen: een heel artikel, hoofdstuk of regeling in één klik.
 *
 *  De boom kent de bepalingen niet: dezelfde component voor de voorstellen van Lex, de bronnen van een
 *  deelvraag en het koppelen. De groepering rekent `bouwBoom` (`lib/bronPlaats.ts`). */
export interface BronBoomProps<T> {
  boom: readonly BoomKnoop<T>[];
  label: string;
  renderBlad: (blad: Blad<T>) => ReactNode;
  /** Gekozen = de `sleutel` van een blad (standaard de bron-IRI). */
  vinkjes?: {
    gekozen: ReadonlySet<string>;
    onZet: (iris: string[], aan: boolean) => void;
    /** De toegankelijke naam van het vinkje van een blad. */
    naam: (blad: Blad<T>) => string;
  };
  /** Extra attributen op het blad (`data-*`, `aria-current`). */
  bladAttrs?: (blad: Blad<T>) => Record<string, string | number | boolean | undefined>;
}

export function BronBoom<T>({ boom, label, renderBlad, vinkjes, bladAttrs }: BronBoomProps<T>) {
  const [dicht, setDicht] = useState<ReadonlySet<string>>(new Set());
  const wissel = (k: string) => setDicht((d) => {
    const n = new Set(d);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });
  return (
    <ul aria-label={label} className="space-y-3" data-bronboom>
      {boom.map((r) => <Knoop key={r.sleutel} knoop={r} diepte={0} dicht={dicht} wissel={wissel}
        renderBlad={renderBlad} vinkjes={vinkjes} bladAttrs={bladAttrs} />)}
    </ul>
  );
}

function Knoop<T>({ knoop, diepte, dicht, wissel, renderBlad, vinkjes, bladAttrs }: {
  knoop: BoomKnoop<T>;
  diepte: number;
  dicht: ReadonlySet<string>;
  wissel: (k: string) => void;
} & Pick<BronBoomProps<T>, "renderBlad" | "vinkjes" | "bladAttrs">) {
  const open = !dicht.has(knoop.sleutel);
  const alle = bladerenVan(knoop);
  const aantal = alle.length;
  const kop = knoop.soort === "regeling" ? "text-sm font-semibold text-ink"
    : knoop.soort === "deel" ? "text-xs font-semibold uppercase tracking-wide text-muted"
    : "text-sm font-medium text-ink";
  return (
    <li data-boom-knoop={knoop.soort} data-boom-sleutel={knoop.sleutel}>
      <div className="flex min-h-[32px] items-center gap-2">
        {vinkjes && <KopVinkje iris={alle.map((b) => b.sleutel)} vinkjes={vinkjes} naam={knoop.label} />}
        <button type="button" onClick={() => wissel(knoop.sleutel)} aria-expanded={open}
          className={`focus-ring flex min-w-0 flex-1 items-center gap-1.5 rounded text-left ${kop}`}>
          <ChevronOmlaag className={`shrink-0 text-faint transition-transform ${open ? "" : "-rotate-90"}`} />
          <span className="truncate">{knoop.label}</span>
          <span className="shrink-0 text-xs font-normal normal-case tracking-normal text-faint">{aantal}</span>
        </button>
      </div>
      {open && (
        <ul className={`mt-1 space-y-1 ${diepte < 3 ? "ml-2 border-l border-line pl-3" : ""}`}>
          {knoop.bladeren.map((b) => (
            <li key={b.sleutel} className="flex items-start gap-2" data-boom-blad={b.bron_iri} {...(bladAttrs?.(b) ?? {})}>
              {vinkjes && (
                <input type="checkbox" checked={vinkjes.gekozen.has(b.sleutel)} aria-label={vinkjes.naam(b)}
                  onChange={(e) => vinkjes.onZet([b.sleutel], e.target.checked)}
                  className="focus-ring mt-1.5 shrink-0 accent-lint" />
              )}
              <div className="min-w-0 flex-1">{renderBlad(b)}</div>
            </li>
          ))}
          {knoop.kinderen.map((k) => <Knoop key={k.sleutel} knoop={k} diepte={diepte + 1} dicht={dicht} wissel={wissel}
            renderBlad={renderBlad} vinkjes={vinkjes} bladAttrs={bladAttrs} />)}
        </ul>
      )}
    </li>
  );
}

/** Het vinkje van een kop: aan als alles eronder gekozen is, half als een deel. */
function KopVinkje({ iris, vinkjes, naam }: {
  iris: string[];
  vinkjes: { gekozen: ReadonlySet<string>; onZet: (iris: string[], aan: boolean) => void };
  naam: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const aan = iris.filter((i) => vinkjes.gekozen.has(i)).length;
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = aan > 0 && aan < iris.length;
  }, [aan, iris.length]);
  return (
    <input ref={ref} type="checkbox" checked={aan > 0 && aan === iris.length} aria-label={`Alles in ${naam}`}
      onChange={(e) => vinkjes.onZet(iris, e.target.checked)} className="focus-ring shrink-0 accent-lint" />
  );
}
