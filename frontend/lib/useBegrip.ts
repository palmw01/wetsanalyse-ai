"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  accordeerBegrip, accordeerGeneriek, foutTekst, haalBegrip, haalBegripRevisies, haalConformiteit, haalGeneriekBegrip,
  haalGeneriekConformiteit, haalGeneriekRevisies, haalHerbeoordelingen, haalKaartVoorstellen, heropenBegrip, heropenGeneriek,
  lijstBegrippen, neemKaartVoorstelOver, verwijderBegrip, verwijderGeneriek, wijsKaartVoorstelAf, wijzigBegrip, wijzigGeneriek,
} from "@/lib/api";
import { verouderdUit, type Verouderd } from "@/lib/kaartVoorstel";
import type {
  Begrip, BegripInhoud, BegripRelatie, BegrippenLijst, Herbeoordelingen, KaartVoorstel, KaartVoorstellenAntwoord, RelatiesAntwoord,
} from "@/lib/types";
import { metSpoor } from "@/lib/uiSpoor";
import { verwijderdUit, type Verwijderd } from "@/lib/verwijderen";
import { isRevisieConflict } from "@/lib/werkgebied";

export interface BegripMutatieOpties {
  gelukt?: string;
  /** Een fout die bij een formulier hoort: `true` als die hem al toont. */
  opFout?: (e: unknown) => boolean;
}
export type BegripMutatie = (actie: (revisie: number) => Promise<Begrip>, opties?: BegripMutatieOpties) => Promise<boolean>;

/** Vanuit waar je naar een begrip kijkt (ADR-006): in een werkgebied, of op de eigen pagina van een generiek begrip. */
export type BegripContext = { soort: "werkgebied"; werkgebiedId: string } | { soort: "generiek" };

/** Een oude versie (de versiekiezer): het begrip en zijn relaties zoals ze toen waren. */
export interface BegripOpname { begrip: Begrip; relaties?: RelatiesAntwoord | null }

/** Eén begrip, zoals de pagina en het paneel het delen. Alle mutaties lopen via `muteer`, met de revisie in beeld.
 *  Wijzigde iemand anders het begrip intussen (412), dan komt de nieuwe stand in beeld en zegt de melding dat; de
 *  handeling wordt niet stil herhaald. Een fout met een leesbare melding van de api (`al_primair`, `poort`,
 *  `element_buiten_werkgebied`) verschijnt zoals de api hem formuleert. Met `opname` wordt niets opgehaald. */
export function useBegrip({ context, begripId, opname, onGewijzigd, onVerwijderd }: {
  context: BegripContext;
  begripId: string;
  opname?: BegripOpname;
  /** Na elke geslaagde mutatie: de lijst eromheen ververst haar tellingen. */
  onGewijzigd?: () => void;
  /** Het begrip is verwijderd; zonder blijft de verwijderd-stand in beeld. */
  onVerwijderd?: () => void | Promise<void>;
}) {
  const id = context.soort === "werkgebied" ? context.werkgebiedId : "";
  const generiek = context.soort === "generiek";
  const alleenLezen = !!opname;
  // Dezelfde handelingen, op de route die bij de plek hoort.
  const api = useMemo(() => generiek ? {
    wijzig: (r: number, inhoud: BegripInhoud) => wijzigGeneriek(begripId, r, inhoud),
    accordeer: (r: number) => accordeerGeneriek(begripId, r),
    heropen: (r: number) => heropenGeneriek(begripId, r),
    revisies: () => haalGeneriekRevisies(begripId),
    conformiteit: () => haalGeneriekConformiteit(),
  } : {
    wijzig: (r: number, inhoud: BegripInhoud) => wijzigBegrip(id, begripId, r, inhoud),
    accordeer: (r: number) => accordeerBegrip(id, begripId, r),
    heropen: (r: number) => heropenBegrip(id, begripId, r),
    revisies: () => haalBegripRevisies(id, begripId),
    conformiteit: () => haalConformiteit(id),
  }, [generiek, id, begripId]);
  const [relatiesGeneriek, setRelatiesGeneriek] = useState<BegripRelatie[]>([]);
  const [begrip, setBegrip] = useState<Begrip | null>(opname?.begrip ?? null);
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  const [verwijderd, setVerwijderd] = useState<Verwijderd | null>(null);
  const [lex, setLex] = useState<KaartVoorstellenAntwoord | null>(null);
  const [verouderd, setVerouderd] = useState<Verouderd | null>(null);
  const [herbeoordeling, setHerbeoordeling] = useState<Herbeoordelingen | null>(null);

  const laad = useCallback(async () => {
    try {
      if (generiek) {
        const g = await haalGeneriekBegrip(begripId);
        setBegrip(g.begrip);
        setRelatiesGeneriek(g.relaties);
      } else setBegrip(await haalBegrip(id, begripId));
      setFout(null);
    } catch (e) {
      // Een verwijderd begrip is een toestand, geen fout – zoals een verwijderde annotatie.
      const v = verwijderdUit(e);
      if (v) {
        setVerwijderd(v);
        setBegrip(null);
      } else setFout(foutTekst(e, "Het begrip kon niet worden geladen."));
    }
  }, [generiek, id, begripId]);

  // De lijst draagt de primaire duidingen en de andere begrippen; faalt stil, het begrip staat er dan gewoon.
  const laadLijst = useCallback(async () => {
    if (generiek) return;
    try { setLijst(await lijstBegrippen(id)); } catch { setLijst(null); }
  }, [generiek, id]);

  useEffect(() => {
    if (alleenLezen) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
    void laadLijst();
  }, [laad, laadLijst, alleenLezen]);

  // Per revisie: een eigen wijziging kan een open voorstel verouderd maken, en na herkoppelen of bevestigen hoort de
  // passage uit de herbeoordeling te gaan. Beide vragen meer dan het begrip en falen stil.
  const revisie = begrip?.revisie;
  const laadLex = useCallback(async () => {
    if (generiek) return;
    try { setLex(await haalKaartVoorstellen(id, begripId)); } catch { /* zonder voorstellen werkt de rest gewoon */ }
  }, [generiek, id, begripId]);
  const [gezien, setGezien] = useState(0);
  /** Na *Klopt nog*: de melding hoort weg te gaan, ook al blijft de revisie gelijk. */
  const herbeoordeel = useCallback(() => setGezien((n) => n + 1), []);
  useEffect(() => {
    if (alleenLezen || generiek) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laadLex();
    let levend = true;
    haalHerbeoordelingen(id, begripId)
      .then((h) => levend && setHerbeoordeling(h))
      .catch(() => levend && setHerbeoordeling(null));
    return () => { levend = false; };
  }, [generiek, id, begripId, revisie, gezien, alleenLezen, laadLex]);

  const muteer: BegripMutatie = useCallback(async (actie, { gelukt, opFout } = {}) => {
    if (!begrip) return false;
    setMelding(null);
    try {
      setBegrip(await actie(begrip.revisie));
      if (gelukt) setMelding({ type: "bevestiging", tekst: gelukt });
      void laadLijst();
      onGewijzigd?.();
      return true;
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit begrip net. De nieuwste stand staat nu in beeld; kijk of je wijziging nog nodig is." });
      } else if (!opFout?.(e)) {
        setMelding({ type: "waarschuwing", tekst: foutTekst(e) });
      }
      return false;
    }
  }, [begrip, laad, laadLijst, onGewijzigd]);

  /** Echt wissen, zoals een annotatie (`lib/verwijderen.ts`). Een vervangen begrip gaat niet weg (409: verwijder de
   *  opvolger); een 412 laadt de nieuwe stand. */
  async function verwijder() {
    if (!begrip) return;
    setMelding(null);
    try {
      await metSpoor("begrip_verwijderen", () => generiek ? verwijderGeneriek(begripId, begrip.revisie)
        : verwijderBegrip(id, begripId, begrip.revisie));
      await laad();                          // de api zegt nu wanneer en door wie
      await onVerwijderd?.();
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit begrip net. Bekijk de nieuwe stand voordat je het verwijdert." });
      } else setMelding({ type: "waarschuwing", tekst: foutTekst(e, "Het begrip is niet verwijderd.") });
    }
  }

  async function overnemen(v: KaartVoorstel, extra: Parameters<typeof neemKaartVoorstelOver>[4]) {
    const gelukt = await muteer((r) => neemKaartVoorstelOver(id, begripId, v.id, r, extra), {
      gelukt: "Overgenomen van Lex; dat is een nieuwe revisie.",
      opFout: (e) => {
        const oud = verouderdUit(e, v.id);
        if (oud) setVerouderd(oud);
        return !!oud;
      },
    });
    if (gelukt) setVerouderd(null);
    await laadLex();
    return gelukt;
  }

  async function afwijzen(v: KaartVoorstel, reden: string) {
    try {
      setLex(await wijsKaartVoorstelAf(id, begripId, v.id, reden));
      return true;
    } catch (e) {
      setMelding({ type: "waarschuwing", tekst: foutTekst(e, "Afwijzen is niet gelukt.") });
      return false;
    }
  }

  return { context, id, generiek, begripId, begrip, lijst, fout, melding, verwijderd, verouderd, herbeoordeling, alleenLezen,
    relatiesOpname: opname?.relaties ?? null, relatiesGeneriek, voorstellen: lex?.voorstellen ?? [], api, laad, herbeoordeel,
    muteer, verwijder, overnemen, afwijzen };
}

export type BegripStand = ReturnType<typeof useBegrip>;
