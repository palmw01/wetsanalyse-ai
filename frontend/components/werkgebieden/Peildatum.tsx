"use client";

import { useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { haalToestanden } from "@/lib/api";
import type { Toestanden } from "@/lib/types";
import { datumNl, peildatumZin, toestandMeldingen } from "@/lib/werkgebied";

/** De peildatum boven de bronnen (tab Bronnen, deelvraagpagina, paneel naast het gesprek), met per regeling
 *  sinds wanneer de tekst in de kennisgraaf geldt. De graaf heeft per regeling alleen de nieuwste toestand:
 *  geldt die pas ná de peildatum, dan zegt een gele melding dat de tekst kan afwijken. Faalt stil. */
export function PeildatumRegel({ werkgebiedId, revisie = 0 }: { werkgebiedId: string; revisie?: number }) {
  const [t, setT] = useState<Toestanden | null>(null);
  useEffect(() => {
    let levend = true;
    haalToestanden(werkgebiedId).then((x) => { if (levend) setT(x); });
    return () => { levend = false; };
  }, [werkgebiedId, revisie]);
  if (!t) return null;
  const meldingen = toestandMeldingen(t);
  const geldig = t.regelingen.filter((r) => r.geldig_vanaf);
  return (
    <div data-peildatum={t.peildatum} className="space-y-2">
      <p className="text-xs text-muted">
        <span className="font-medium text-ink">{peildatumZin(t.peildatum, t.peildatum_standaard)}</span>
        {geldig.length > 0 && (
          <>
            {" · tekst geldig vanaf "}
            {geldig.map((r, i) => (
              <span key={r.bwb_id}>{i > 0 && ", "}{datumNl(r.geldig_vanaf)} ({r.citeertitel})</span>
            ))}
          </>
        )}
      </p>
      {meldingen.length > 0 && (
        <Melding type="waarschuwing" compact>
          <span data-peildatum-melding>{meldingen.join(" ")}</span>
        </Melding>
      )}
    </div>
  );
}
