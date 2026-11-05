"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Field";
import { Lijst, LijstRij } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { foutTekst, gebruikGeneriek, zoekBegrippen } from "@/lib/api";
import { kort, type BegripOverzichtRij } from "@/lib/begrippenOverzicht";
import type { BegripSamenvatting } from "@/lib/types";
import { begripPad } from "@/lib/werkgebiedPaden";

/** Een generiek begrip in dit werkgebied gebruiken (ADR-006): zonder kopie, de passages koppel je daarna hier. Dit zoekt in
 *  de begrippen van het platform, niet in de graaf, en hoort dus op het artefact. */
export function GeneriekGebruiken({ id, gebruikt, onSluit }: {
  id: string;
  /** Wat dit werkgebied al heeft: dat staat er niet nog eens bij. */
  gebruikt: readonly BegripSamenvatting[];
  onSluit: () => void;
}) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [rijen, setRijen] = useState<BegripOverzichtRij[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);

  useEffect(() => {
    let levend = true;
    const t = setTimeout(() => {
      zoekBegrippen(new URLSearchParams({ kader: "generiek", status: "geaccordeerd", ...(term.trim() ? { q: term.trim() } : {}) }))
        .then((u) => levend && setRijen(u.resultaten))
        .catch((e) => levend && setFout(foutTekst(e, "De generieke begrippen konden niet worden geladen.")));
    }, 200);
    return () => { levend = false; clearTimeout(t); };
  }, [term]);

  const al = new Set(gebruikt.map((b) => b.id));
  const getoond = (rijen ?? []).filter((b) => !al.has(b.id));

  async function kies(begripId: string) {
    setBezig(true);
    setFout(null);
    try {
      await gebruikGeneriek(id, begripId);
      router.push(begripPad(id, begripId));
    } catch (e) {
      setFout(foutTekst(e, "Het begrip kon niet worden gebruikt."));
      setBezig(false);
    }
  }

  return (
    <Dialog label="Generiek begrip gebruiken" variant="compact" onSluit={onSluit}>
      <div className="flex min-h-0 flex-1 flex-col" data-generiek-gebruiken>
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <p className="text-xs text-muted">Generiek begrip gebruiken</p>
          <h2 className="font-display text-base font-semibold text-lint">Eén definitie, jouw passages</h2>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          <Input type="search" value={term} onChange={(e) => setTerm(e.target.value)} autoFocus
            aria-label="Zoeken in de generieke begrippen" placeholder="Zoek op naam, term of definitie" />
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {rijen === null && !fout ? <p className="text-xs text-muted">Laden…</p>
            : getoond.length === 0 ? <p className="text-sm text-muted">Geen generiek begrip gevonden.</p> : (
              <Lijst label="Generieke begrippen">
                {getoond.map((b) => (
                  <LijstRij key={b.id} titel={b.naam} meta={b.definitie ? kort(b.definitie, 140) : "Nog geen definitie."}
                    status={<Button size="xs" variant="secondary" disabled={bezig} aria-label={`Gebruik ${b.naam}`}
                      onClick={() => void kies(b.id)}>Gebruiken</Button>} />
                ))}
              </Lijst>
            )}
        </div>
      </div>
    </Dialog>
  );
}
