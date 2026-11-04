"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Kruis, PijlRechts } from "@/components/ui/Icoon";
import { haalBronselectie } from "@/lib/api";
import { BRONSELECTIE_GEWIJZIGD, paneelTelling } from "@/lib/bronselectie";
import { klaarActie, typActie, type IntakeActie, type Vraagkaart } from "@/lib/vraagkaart";

/** Het compacte kaartje van de bronselectie (`weergave: paneel`, 3 nov 2026): het gesprek blijft rustig, zoals een
 *  artefact bij Claude. Het noemt hoeveel er ligt – live, want je beslist in het paneel – en verwijst ernaar:
 *  *Bronnen beoordelen* opent het paneel, *+ Bepaling toevoegen* het venster, *Klaar* gaat verder. Een bepaling
 *  typen blijft kunnen ("artikel 25 lid 2 Invorderingswet 1990"): Lex voegt haar toe en het kaartje blijft. */
export function BronselectieKaart({ kaart, uitgeschakeld, onActie, onSluit, onBeoordelen, onToevoegen }: {
  kaart: Vraagkaart;
  uitgeschakeld: boolean;
  onActie: (actie: IntakeActie) => void;
  onSluit: () => void;
  onBeoordelen?: () => void;
  onToevoegen?: () => void;
}) {
  const werkgebiedId = kaart.intake_id.slice(3);
  const [telling, setTelling] = useState(kaart.telling ?? { kandidaten: 0, opgenomen: 0 });
  const [eigen, setEigen] = useState("");
  useEffect(() => {
    let levend = true;
    const laad = () => haalBronselectie(werkgebiedId)
      .then((o) => {
        const d = o.deelvragen.find((x) => x.id === kaart.deelvraag_id);
        if (levend && d) setTelling(paneelTelling(d, kaart.stap));
      }).catch(() => {});
    void laad();
    const bij = (e: Event) => { if ((e as CustomEvent).detail === werkgebiedId) void laad(); };
    window.addEventListener(BRONSELECTIE_GEWIJZIGD, bij);
    return () => { levend = false; window.removeEventListener(BRONSELECTIE_GEWIJZIGD, bij); };
  }, [werkgebiedId, kaart.deelvraag_id, kaart.stap]);

  const kern = kaart.stap === "bs_bepalingen";
  const typ = typActie(kaart, eigen);
  return (
    <section aria-label="Bronselectie van Lex" data-vraagdock={kaart.stap} data-bronselectie-kaart={kaart.deelvraag_id}
      className="relative w-full rounded-[24px] border border-line bg-white px-5 pb-4 pt-3 shadow-kaart">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm tabular-nums text-muted">{kaart.nr} van {kaart.totaal}</p>
          <h2 className="mt-0.5 font-display text-lg font-semibold leading-snug text-ink">{kaart.vraag}</h2>
        </div>
        <button type="button" aria-label="Vraag sluiten" onClick={onSluit}
          className="focus-ring inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line bg-white text-ink shadow-zacht hover:bg-surface coarse:h-11 coarse:w-11">
          <Kruis className="text-base" />
        </button>
      </div>
      <div className="mt-3 rounded-kaart border border-line bg-surface/60 px-4 py-3" data-telling>
        <p className="text-sm font-medium text-ink">
          {kern ? "Kernbepalingen" : "Wat eraan hangt"} · {telling.kandidaten} {telling.kandidaten === 1 ? "kandidaatbron" : "kandidaatbronnen"}
          {telling.opgenomen > 0 && <span className="font-normal text-muted"> · {telling.opgenomen} opgenomen</span>}
        </p>
        <p className="mt-0.5 text-xs text-muted">
          Lees de tekst en neem op of sluit uit in het paneel. {kern ? "Klaar? Dan zoek ik wat eraan hangt." : "Wat je opneemt, komt erbij als contextbron."}
        </p>
      </div>
      {/* Opbouw zoals het VraagDock: de nevenacties naast elkaar en even breed, dan de eigen bepaling, en onderaan
          rechts de hoofdknop. Niet in één rij met flex-wrap: dan viel *Klaar* bij deze breedte los op een eigen regel. */}
      {(onBeoordelen || onToevoegen) && (
        <div className={`mt-3 grid gap-2 ${onBeoordelen && onToevoegen ? "sm:grid-cols-2" : ""}`} data-nevenacties>
          {onBeoordelen && (
            <Button variant="secondary" size="sm" onClick={onBeoordelen} className="w-full">
              Bronnen beoordelen <PijlRechts className="ml-1" />
            </Button>
          )}
          {onToevoegen && (
            <Button variant="secondary" size="sm" onClick={onToevoegen} disabled={uitgeschakeld} className="w-full">
              + Bepaling toevoegen
            </Button>
          )}
        </div>
      )}
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (typ && !uitgeschakeld) { onActie(typ); setEigen(""); } }}>
        <input value={eigen} onChange={(e) => setEigen(e.target.value)} disabled={uitgeschakeld}
          aria-label="Een bepaling typen" placeholder="Of typ een bepaling, bijv. ‘artikel 9 lid 2 Iw 1990’"
          className="focus-ring min-h-[36px] min-w-0 flex-1 rounded-field border border-line bg-paper px-3 text-sm placeholder:text-faint" />
        {typ && <Button type="submit" variant="ghost" size="sm">Voeg toe</Button>}
      </form>
      <div className="mt-3 flex sm:justify-end">
        <Button onClick={() => onActie(klaarActie(kaart))} disabled={uitgeschakeld} className="w-full px-5 sm:w-auto" data-klaar>
          {kern ? "Klaar met de kernbepalingen" : "Klaar, afronden"} <PijlRechts />
        </Button>
      </div>
    </section>
  );
}
