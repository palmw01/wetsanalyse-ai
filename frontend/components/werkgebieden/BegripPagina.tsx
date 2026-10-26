"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { PaginaKop, Stip } from "@/components/ui/Pagina";
import { BegripWerk } from "@/components/werkgebieden/BegripWerk";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { foutTekst, haalWerkgebied, lijstBegrippen } from "@/lib/api";
import type { BegrippenLijst, Werkgebied } from "@/lib/types";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { artefactPad, begripPad } from "@/lib/werkgebiedPaden";

const STATUS: Record<string, { tekst: string; toon: "groen" | "neutraal" }> = {
  geaccordeerd: { tekst: "Geaccordeerd", toon: "groen" },
  concept: { tekst: "Concept", toon: "neutraal" },
  vervangen: { tekst: "Vervangen", toon: "neutraal" },
};

/** Eén begrip op een eigen pagina (spoor G3, mock-up v4 `conceptPage`): de volledige begripskaart met
 *  betekenis, bronpassages, relaties, beoordeling en historie – zonder zijpaneel. Het begrip hoort bij het
 *  begrippenkader van één werkgebied; dat staat in het kruimelpad. Een geformuleerd analysebegrip is geen
 *  wettelijke definitie: de kaart zegt waar de definitie vandaan komt. */
export function BegripPagina({ werkgebiedId, begripId }: { werkgebiedId: string; begripId: string }) {
  const router = useRouter();
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const vraagRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (bewaker.wachtend) vraagRef.current?.scrollIntoView({ block: "nearest" });
  }, [bewaker.wachtend]);

  const laadLijst = useCallback(async () => {
    try {
      setLijst(await lijstBegrippen(werkgebiedId));
    } catch (e) {
      setFout(foutTekst(e, "De begrippen konden niet worden geladen."));
    }
  }, [werkgebiedId]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laadLijst();
    haalWerkgebied(werkgebiedId).then(setWg).catch(() => {});
  }, [laadLijst, werkgebiedId]);

  const begrip = lijst?.begrippen.find((b) => b.id === begripId);
  const naam = begrip?.inhoud.naam || "Begrip";
  const status = begrip ? STATUS[begrip.status] : undefined;
  const kader = artefactPad(werkgebiedId, "begrippen");

  return (
    <WerkgebiedSchil titel={naam} onFout={setFout} breed bewaak={bewaker.bewaak}>
      <div data-begrip-pagina={begripId}>
        <PaginaKop
          kruimels={[{ label: "Begrippen", href: "/begrippen" }, { label: wg?.naam ?? "Werkgebied", href: kader }, { label: naam }]}
          titel={naam}
          sub="Begrippenkaart: betekenis, bronpassages, relaties en beoordeling."
          meta={<>
            {status && <StatusLabel toon={status.toon}>{status.tekst}</StatusLabel>}
            {wg && <><Stip /><span>Begrippenkader {wg.naam}</span></>}
            <Stip /><span>Een analysebegrip, geen wettelijke definitie</span>
          </>}
          acties={begrip && (
            <VraagLexKnop primair onderwerp={{ soort: "begrip", werkgebied_id: werkgebiedId, id: begripId, label: naam }}
              naam={`Bespreek ${naam} met Lex`} />
          )}
        />
        {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
        {bewaker.wachtend && (
          <div ref={vraagRef}>
            <OnbewaardMelding className="mb-4" handeling="verlaten" onBlijf={bewaker.blijf}
              onToch={() => { setOnbewaard(false); bewaker.toch(); }} />
          </div>
        )}
        {lijst && (
          <BegripWerk
            key={begripId}
            id={werkgebiedId}
            begripId={begripId}
            primair={lijst.primair ?? {}}
            andere={lijst.begrippen}
            onGewijzigd={() => void laadLijst()}
            onOnbewaard={setOnbewaard}
            onNaarBegrip={(b) => router.push(begripPad(werkgebiedId, b))}
            // Na verwijderen (dat doet de kaart zelf): terug naar het begrippenkader.
            onWeg={async () => {
              setOnbewaard(false);
              router.push(kader);
            }}
          />
        )}
      </div>
    </WerkgebiedSchil>
  );
}
