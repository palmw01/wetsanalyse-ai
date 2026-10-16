"use client";

import { useCallback, useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { BegripKaart, type LexBijKaart } from "@/components/werkgebieden/BegripKaart";
import { BegripLex } from "@/components/werkgebieden/BegripLex";
import { BegripPassages } from "@/components/werkgebieden/BegripPassages";
import { BegripRelaties } from "@/components/werkgebieden/BegripRelaties";
import {
  foutTekst, haalBegrip, haalHerbeoordelingen, haalKaartVoorstellen, neemKaartVoorstelOver, verwijderBegrip,
  wijsKaartVoorstelAf,
} from "@/lib/api";
import { geraaktPerKoppeling } from "@/lib/herbeoordeling";
import { verouderdUit, type Verouderd } from "@/lib/begripLex";
import type { Begrip, BegripSamenvatting, Herbeoordelingen, KaartVoorstellenAntwoord } from "@/lib/types";
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
export function BegripWerk({ id, begripId, primair, andere = [], onGewijzigd, onOnbewaard, onWeg, onNaarBegrip }: {
  id: string;
  begripId: string;
  primair: Record<string, { begrip_id: string; naam: string }>;
  /** De andere begrippen van het werkgebied: om mee te vergelijken (*Verklaar het betekenisverschil*). */
  andere?: readonly BegripSamenvatting[];
  /** Na elke geslaagde mutatie: de lijst ververst haar tellingen en aandachtspunten. */
  onGewijzigd: () => void;
  onOnbewaard: (onbewaard: boolean) => void;
  onWeg: () => Promise<void>;
  /** Na *Nieuwe betekenis* of *Combineren* (fase F2): open het begrip dat het werk draagt. */
  onNaarBegrip?: (begripId: string) => void;
}) {
  const [begrip, setBegrip] = useState<Begrip | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  // Op een smal scherm één van de twee; vanaf xl naast elkaar.
  const [kant, setKant] = useState<"begrip" | "bronnen">("begrip");
  // Lex naast de kaart (fase E): de voorstellen per veld, en welke er verouderd bleek bij overnemen.
  const [lex, setLex] = useState<KaartVoorstellenAntwoord | null>(null);
  const [verouderd, setVerouderd] = useState<Verouderd | null>(null);
  const [onbewaard, setOnbewaard] = useState(false);
  // Herbeoordelen (fase F1): welke dragende passages veranderden. Vraagt de bronboom, dus los van het
  // begrip geladen; faalt stil – de passages staan er dan zoals de api ze zonder graaf ziet.
  const [herbeoordeling, setHerbeoordeling] = useState<Herbeoordelingen | null>(null);
  const meldOnbewaard = useCallback((o: boolean) => {
    setOnbewaard(o);
    onOnbewaard(o);
  }, [onOnbewaard]);

  const laadLex = useCallback(async () => {
    try {
      setLex(await haalKaartVoorstellen(id, begripId));
    } catch {
      // Faalt stil: zonder voorstellen werkt de kaart gewoon; de strook zegt dan niets over eerdere runs.
    }
  }, [id, begripId]);

  // Opnieuw bij elke revisie: een eigen wijziging kan een open voorstel verouderd maken, en de kaart
  // hoort dat te zeggen vóórdat iemand op *Overnemen* klikt.
  const revisie = begrip?.revisie;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laadLex();
  }, [laadLex, revisie]);

  // Ook bij elke revisie: na herkoppelen of bevestigen hoort de passage uit de herbeoordeling te gaan.
  useEffect(() => {
    let levend = true;
    haalHerbeoordelingen(id, begripId)
      .then((h) => levend && setHerbeoordeling(h))
      .catch(() => levend && setHerbeoordeling(null));
    return () => { levend = false; };
  }, [id, begripId, revisie]);

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

  async function verwijder() {
    if (!begrip) return;
    setFout(null);
    setMelding(null);
    try {
      await verwijderBegrip(id, begrip.id, begrip.revisie);
      await onWeg();
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({
          type: "waarschuwing",
          tekst: "Iemand anders wijzigde dit begrip net. Bekijk de nieuwe stand voordat je het verwijdert.",
        });
      } else {
        setFout(foutTekst(e, "Verwijderen is niet gelukt."));
      }
    }
  }

  const bijKaart: LexBijKaart = {
    voorstellen: lex?.voorstellen ?? [],
    verouderd,
    overnemen: async (v, extra) => {
      const gelukt = await muteer((r) => neemKaartVoorstelOver(id, begripId, v.id, r, extra), {
        gelukt: "Overgenomen van Lex; dat is een nieuwe revisie.",
        opFout: (e) => {
          const oud = verouderdUit(e, v.id);
          if (!oud) return false;
          setVerouderd(oud);
          return true;
        },
      });
      if (gelukt) setVerouderd(null);
      await laadLex();
      return gelukt;
    },
    afwijzen: async (v, reden) => {
      try {
        setLex(await wijsKaartVoorstelAf(id, begripId, v.id, reden));
        return true;
      } catch (e) {
        setFout(foutTekst(e, "Afwijzen is niet gelukt."));
        return false;
      }
    },
  };

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
        <div className={`space-y-4 ${kant === "begrip" ? "" : "hidden xl:block"}`}>
          {begrip.status !== "vervangen" && (
            <BegripLex id={id} begrip={begrip} andere={andere} onbewaard={onbewaard} data={lex} onVernieuw={laadLex} />
          )}
          <BegripKaart
            id={id}
            begrip={begrip}
            muteer={muteer}
            onOnbewaard={meldOnbewaard}
            onVerwijder={verwijder}
            lex={bijKaart}
          />
          <BegripRelaties id={id} begrip={begrip} andere={andere} onGewijzigd={() => { void laad(); onGewijzigd(); }}
            onNaarBegrip={onNaarBegrip} />
        </div>
        <div className={kant === "bronnen" ? "" : "hidden xl:block"}>
          <BegripPassages id={id} begrip={begrip} primair={primair} muteer={muteer}
            geraakt={geraaktPerKoppeling(herbeoordeling, begrip.id)} />
        </div>
      </div>
    </div>
  );
}
