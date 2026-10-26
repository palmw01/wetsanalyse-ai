"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { BegripPaneel } from "@/components/werkgebieden/BegripPaneel";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { DeelvraagPaneel } from "@/components/werkgebieden/DeelvraagPaneel";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSamenvatting } from "@/components/werkgebieden/WerkgebiedSamenvatting";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { foutTekst, haalWerkgebied, verwijderWerkgebied } from "@/lib/api";
import { metSpoor } from "@/lib/uiSpoor";
import { verwijderdUit, verwijderdZin, type Verwijderd } from "@/lib/verwijderen";
import { isRevisieConflict } from "@/lib/werkgebied";
import { werkgebiedLabel, type WerkgebiedArtefact } from "@/lib/artefact";
import type { Werkgebied } from "@/lib/types";
import { STATUS_LABEL } from "@/lib/werkgebied";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { artefactPad, begripPad, deelvraagPad, projectPad, voorstellenPad } from "@/lib/werkgebiedPaden";

/** Waar *Open volledige pagina* heen gaat: de pagina van wat het paneel toont (spoor G2). */
function paginaVan(doel: WerkgebiedArtefact): string {
  const id = doel.werkgebied_id;
  switch (doel.soort) {
    case "begrippen": return artefactPad(id, "begrippen");
    case "begrip": return doel.begrip_id ? begripPad(id, doel.begrip_id) : artefactPad(id, "begrippen");
    case "bronnen": return voorstellenPad(id);
    case "deelvraag": return doel.deelvraag_id ? deelvraagPad(id, doel.deelvraag_id) : projectPad(id);
    default: return projectPad(id);
  }
}
const KOP: Record<WerkgebiedArtefact["soort"], string> = {
  begrippen: "Begripsvoorstellen van Lex", bronnen: "Gevonden bepalingen van Lex", werkgebied: "Samengesteld met Lex",
  deelvraag: "Deelvraag", begrip: "Begrip",
};

/** Een artefact van een werkgebied in de werkplek, in dezelfde schil als een annotatie (een kolom naast
 *  de chat vanaf 1280px, anders een sheet):
 *
 *  - **begrippen** – de voorstellen van Lex (`BegripVoorstellen`), dezelfde inhoud als op de tab
 *    Begrippen. Een overgenomen begrip opent in het werkgebied: daar staan de kaart en de passages.
 *  - **bronnen** – de bepalingen die Lex vond (`BronKandidaten`), dezelfde inhoud als op de tab Bronnen.
 *  - **begrip** (F3d) – één begrip om te beoordelen (`BegripPaneel`): een leesweergave, de open voorstellen
 *    van Lex per veld en een kleine bewerking; de begripskaart zelf staat in het werkgebied.
 *  - **deelvraag** (F3d) – één deelvraag (`DeelvraagPaneel`): stand, de voorstellen die haar vervangen,
 *    bronnen en de kandidaten die Lex erbij vond.
 *  - **werkgebied** – het werkgebied dat Lex met de analist samenstelde (activiteit 1): de
 *    `WerkgebiedSamenvatting` (dezelfde als bovenaan de pagina) en de weg naar die pagina.
 *
 *  Eén schakelaar op de soort; geen Lex-knoppen in de inhoud – wel *Vraag Lex* in de kop, die het object
 *  als onderwerp boven het invoerveld zet.
 *
 *  Eén inhoud, twee schillen. Net als op de tab vraagt het paneel eerst bevestiging als de kaart
 *  niet-bewaarde wijzigingen draagt: bij sluiten (kruisje, Escape, achtergrond) en bij een link weg. */
export function WerkgebiedArtefactPaneel({ doel, variant = "side", onSluit, onWissel, onVerwijderd }: {
  doel: WerkgebiedArtefact;
  variant?: DialogVariant;
  onSluit: () => void;
  /** Het werkgebied is vanuit dit paneel verwijderd: de werkplek verlaat het dan, als ze erin stond. */
  onVerwijderd?: (werkgebiedId: string) => void;
  /** Een ander artefact in hetzelfde paneel (de opvolger van een vervangen deelvraag of begrip). */
  onWissel?: (doel: WerkgebiedArtefact) => void;
}) {
  const router = useRouter();
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const sluit = () => bewaker.bewaak(onSluit, "sluiten");
  const naarWerkgebied = paginaVan(doel);
  const soort = werkgebiedLabel(doel);
  const titel = doel.titel || soort;
  return (
    <Dialog label={`${soort}: ${titel}`} variant={variant} onSluit={sluit}>
      <div data-artefact data-artefact-soort={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-start gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{KOP[doel.soort]}</p>
            <h2 className="truncate font-display text-base font-semibold text-lint">{titel}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              <Link href={naarWerkgebied} className="focus-ring text-xs font-medium text-lint underline-offset-2 hover:underline">
                Open volledige pagina
              </Link>
              {doel.soort === "werkgebied" && (
                <VraagLexKnop onderwerp={{ soort: "werkgebied", werkgebied_id: doel.werkgebied_id, id: "", label: doel.titel ?? "" }} />
              )}
              {doel.soort === "deelvraag" && doel.deelvraag_id && (
                <VraagLexKnop onderwerp={{ soort: "deelvraag", werkgebied_id: doel.werkgebied_id, id: doel.deelvraag_id, label: doel.titel }} />
              )}
              {doel.soort === "begrip" && doel.begrip_id && (
                <VraagLexKnop onderwerp={{ soort: "begrip", werkgebied_id: doel.werkgebied_id, id: doel.begrip_id, label: doel.titel }} />
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={sluit}
            aria-label="Sluiten"
            className="focus-ring -mr-1 shrink-0 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink"
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {bewaker.wachtend && (
            <OnbewaardMelding
              className="mb-4"
              handeling={bewaker.wachtend.handeling}
              onBlijf={bewaker.blijf}
              onToch={() => {
                setOnbewaard(false);
                bewaker.toch();
              }}
            />
          )}
          {doel.soort === "werkgebied" ? (
            <WerkgebiedInhoud id={doel.werkgebied_id} naarWerkgebied={naarWerkgebied}
              onVerwijderd={() => onVerwijderd?.(doel.werkgebied_id)} />
          ) : doel.soort === "begrip" && doel.begrip_id ? (
            <BegripPaneel werkgebiedId={doel.werkgebied_id} begripId={doel.begrip_id} onOnbewaard={setOnbewaard}
              onNaarBegrip={(b) => onWissel
                ? onWissel({ soort: "begrip", werkgebied_id: doel.werkgebied_id, run_id: "", begrip_id: b, titel: "" })
                : router.push(begripPad(doel.werkgebied_id, b))} />
          ) : doel.soort === "deelvraag" && doel.deelvraag_id ? (
            <DeelvraagPaneel werkgebiedId={doel.werkgebied_id} deelvraagId={doel.deelvraag_id}
              onKies={onWissel ? (d) => onWissel({ soort: "deelvraag", werkgebied_id: doel.werkgebied_id, run_id: "",
                deelvraag_id: d.id, titel: d.vraag }) : undefined} />
          ) : doel.soort === "begrippen" ? (
            <BegripVoorstellen
              id={doel.werkgebied_id}
              runId={doel.run_id}
              inklapbaar={false}
              onBegrip={(b) => router.push(begripPad(doel.werkgebied_id, b))}
              // Er staat hier geen begrippenlijst naast die ververst moet worden.
              onGewijzigd={() => {}}
            />
          ) : (
            // Opnemen wijzigt het werkgebied; hier staat geen selectie naast die ververst moet worden.
            <BronKandidaten id={doel.werkgebied_id} onGewijzigd={() => {}} />
          )}
        </div>
      </div>
    </Dialog>
  );
}

/** Het werkgebied zelf: wat er met Lex is samengesteld, zoals het nu bij de api staat – dezelfde
 *  samenvatting als bovenaan de werkgebiedpagina. */
function WerkgebiedInhoud({ id, naarWerkgebied, onVerwijderd }: {
  id: string;
  naarWerkgebied: string;
  onVerwijderd: () => void;
}) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [verwijderd, setVerwijderd] = useState<Verwijderd | null>(null);
  const [poging, setPoging] = useState(0);
  useEffect(() => {
    let levend = true;
    haalWerkgebied(id).then((w) => { if (levend) setWg(w); }).catch((e) => {
      if (!levend) return;
      // Een verwijderd werkgebied is een toestand, geen fout – zoals een verwijderde annotatie.
      const v = verwijderdUit(e);
      if (v) setVerwijderd(v);
      else setFout(foutTekst(e));
    });
    return () => { levend = false; };
  }, [id, poging]);

  async function verwijder() {
    if (!wg) return;
    setMelding(null);
    try {
      await metSpoor("werkgebied_verwijderen", () => verwijderWerkgebied(id, wg.revisie));
      setWg(null);
      setPoging((p) => p + 1);              // de api zegt nu wanneer en door wie
      onVerwijderd();
    } catch (e) {
      if (isRevisieConflict(e)) {
        setPoging((p) => p + 1);
        setMelding("Iemand anders wijzigde dit werkgebied net. Bekijk de nieuwe stand voordat je het verwijdert.");
      } else setMelding(foutTekst(e, "Het werkgebied is niet verwijderd."));
    }
  }

  if (verwijderd) {
    return <Melding type="uitleg"><span data-verwijderd>{verwijderdZin(verwijderd)}</span></Melding>;
  }
  if (fout) {
    return (
      <Melding type="fout" titel="Het werkgebied kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => { setFout(null); setPoging((p) => p + 1); }}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!wg) return <SkeletonCard regels={4} />;
  return (
    <div data-werkgebied-inhoud className="space-y-4 text-sm text-ink">
      <div className="flex items-center gap-2">
        <p className="text-xs text-muted">{STATUS_LABEL[wg.status]} · revisie {wg.revisie}</p>
        <VerwijderKnop soort="werkgebied" onBevestig={verwijder} className="ml-auto" />
      </div>
      {melding && <Melding type="waarschuwing" compact>{melding}</Melding>}
      <WerkgebiedSamenvatting wg={wg} vraagLex />
      <Link href={naarWerkgebied}
        className="focus-ring inline-flex w-full items-center justify-center rounded-button bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 sm:w-auto">
        Open het werkgebied
      </Link>
    </div>
  );
}
