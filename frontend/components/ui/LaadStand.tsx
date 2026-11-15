import type { ReactNode } from "react";

import { Melding, MeldingActie } from "./Melding";
import { Skeleton, SkeletonCard } from "./Skeleton";

/** Hoe een object eruitziet zolang het laadt: een kaart (een paneel, een tab), drie regels (een paneel met wettekst) of
 *  een lijst rijen (de gesprekkenlijst). */
export type LaadSkelet = "kaart" | "tekst" | "rijen";

function Skelet({ vorm }: { vorm: LaadSkelet }) {
  if (vorm === "kaart") return <SkeletonCard regels={4} />;
  if (vorm === "rijen") {
    return (
      <div className="flex flex-col gap-1" aria-hidden>
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
      </div>
    );
  }
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton className="h-4 w-64 max-w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-4 w-40" />
    </div>
  );
}

/** Een object laden (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §2): zolang
 *  het laadt een skelet, bij een fout een melding "{wat} kon niet worden geladen." met *Opnieuw proberen*, en na een
 *  verwijdering de zin die dat zegt. Elk paneel, elke tab en de gesprekkenlijst gebruiken dit; `app/laadStand.test.ts`
 *  bewaakt dat er geen eigen foutmelding met *Opnieuw proberen* naast komt.
 *
 *  `wat` is het onderwerp met lidwoord en hoofdletter ("Het begrip", "De graaf"). */
export function LaadStand({ wat, fout, onOpnieuw, verwijderd, skelet = "kaart", compact = false }: {
  wat: string;
  fout?: string | null;
  onOpnieuw?: () => void;
  /** De zin dat het object verwijderd is (`verwijderdZin`); gaat vóór de fout. */
  verwijderd?: ReactNode;
  skelet?: LaadSkelet;
  /** Klein, voor een smalle plek (de zijbalk). */
  compact?: boolean;
}) {
  if (verwijderd) return <Melding type="uitleg" compact={compact}><span data-verwijderd>{verwijderd}</span></Melding>;
  if (fout) {
    const titel = `${wat} kon niet worden geladen.`;
    // De foutzin van de aanroeper is vaak dezelfde zin als terugval (`foutTekst(e, titel)`); niet twee keer zeggen.
    const reden = fout === titel ? null : fout;
    return (
      <Melding type="fout" compact={compact} titel={compact ? undefined : titel} data-laadfout>
        {compact ? <>{titel}{reden && <>{" "}{reden}</>}</> : reden}
        {onOpnieuw && <>{" "}<MeldingActie onClick={onOpnieuw}>Opnieuw proberen</MeldingActie></>}
      </Melding>
    );
  }
  return <div aria-busy="true"><Skelet vorm={skelet} /></div>;
}

/** De regel zolang iets kleins laadt (een uitklap, een lijstje in een menu): één woord, één kleur. */
export function LaadRegel({ children = "Laden…", klein = false }: { children?: ReactNode; klein?: boolean }) {
  return <p className={`${klein ? "text-xs" : "text-sm"} text-muted`} role="status">{children}</p>;
}
