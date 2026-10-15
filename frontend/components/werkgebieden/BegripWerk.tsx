"use client";

import { useCallback, useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { BegripKaart } from "@/components/werkgebieden/BegripKaart";
import { BegripPassages } from "@/components/werkgebieden/BegripPassages";
import { foutTekst, haalBegrip, isApiError } from "@/lib/api";
import type { Begrip } from "@/lib/types";
import { isRevisieConflict } from "@/lib/werkgebied";

export interface BegripMutatieOpties {
  gelukt?: string;
  /** Een fout die bij een formulier hoort: `true` als die hem al toont. */
  opFout?: (e: unknown) => boolean;
}
export type BegripMutatie = (actie: (revisie: number) => Promise<Begrip>, opties?: BegripMutatieOpties) => Promise<boolean>;

/** Eén begrip: de kaart en de passages. Alle mutaties lopen via `muteer`, met de revisie in beeld.
 *  Wijzigde iemand anders het begrip intussen (412), dan komt de nieuwe stand in beeld en zegt de
 *  pagina dat; de handeling wordt niet stil herhaald. Een fout met een leesbare melding van de api
 *  (`al_primair`, `poort`, `element_buiten_werkgebied`) verschijnt zoals de api hem formuleert. */
export function BegripWerk({ id, begripId, primair, onGewijzigd, onOnbewaard, onWeg }: {
  id: string;
  begripId: string;
  primair: Record<string, { begrip_id: string; naam: string }>;
  /** Na elke geslaagde mutatie: de lijst ververst haar tellingen en aandachtspunten. */
  onGewijzigd: () => void;
  onOnbewaard: (onbewaard: boolean) => void;
  onWeg: () => Promise<void>;
}) {
  const [begrip, setBegrip] = useState<Begrip | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  // Op een smal scherm één van de twee; vanaf xl naast elkaar.
  const [kant, setKant] = useState<"begrip" | "bronnen">("begrip");

  const laad = useCallback(async () => {
    try {
      setBegrip(await haalBegrip(id, begripId));
    } catch (e) {
      setFout(foutTekst(e, "Het begrip kon niet worden geladen."));
    }
  }, [id, begripId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  const muteer: BegripMutatie = useCallback(
    async (actie, { gelukt, opFout } = {}) => {
      if (!begrip) return false;
      setFout(null);
      setMelding(null);
      try {
        setBegrip(await actie(begrip.revisie));
        if (gelukt) setMelding({ type: "bevestiging", tekst: gelukt });
        onGewijzigd();
        return true;
      } catch (e) {
        if (isRevisieConflict(e)) {
          await laad();
          setMelding({
            type: "waarschuwing",
            tekst: "Iemand anders wijzigde dit begrip net. De nieuwste stand staat nu in beeld; kijk of je wijziging nog nodig is.",
          });
        } else if (!opFout?.(e)) {
          setFout(foutTekst(e));
        }
        return false;
      }
    },
    [begrip, laad, onGewijzigd],
  );

  if (!begrip)
    return fout ? (
      <Melding type="fout">{fout}</Melding>
    ) : (
      <div className="space-y-3">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-40 w-full" />
      </div>
    );

  const n = begrip.koppelingen.length;
  return (
    <div className="space-y-4">
      {fout && <Melding type="fout">{fout}</Melding>}
      {melding && (
        <Melding type={melding.type} compact>
          {melding.tekst}
        </Melding>
      )}
      <div role="group" aria-label="Weergave" className="flex gap-1.5 xl:hidden">
        {(["begrip", "bronnen"] as const).map((k) => (
          <button
            key={k}
            type="button"
            aria-pressed={kant === k}
            onClick={() => setKant(k)}
            className={`focus-ring min-h-[24px] rounded-full border px-2.5 py-0.5 text-[0.7rem] transition coarse:min-h-[44px] ${
              kant === k ? "border-lint bg-lint text-paper" : "border-line text-muted hover:border-lint hover:text-ink"
            }`}
          >
            {k === "begrip" ? "Begrip" : `Bronnen (${n})`}
          </button>
        ))}
      </div>
      <div className="gap-5 xl:grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className={kant === "begrip" ? "" : "hidden xl:block"}>
          <BegripKaart
            id={id}
            begrip={begrip}
            muteer={muteer}
            onOnbewaard={onOnbewaard}
            onWeg={onWeg}
            onVerwijderFout={(e) => setFout(isApiError(e) ? foutTekst(e) : "Verwijderen is niet gelukt.")}
          />
        </div>
        <div className={kant === "bronnen" ? "" : "hidden xl:block"}>
          <BegripPassages id={id} begrip={begrip} primair={primair} muteer={muteer} />
        </div>
      </div>
    </div>
  );
}
