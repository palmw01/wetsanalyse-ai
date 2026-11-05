"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { PaginaKop, Stip } from "@/components/ui/Pagina";
import { BEGRIP_STATUS_TOON, BegripInhoud, BegripMenu } from "@/components/werkgebieden/BegripInhoud";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { haalWerkgebied } from "@/lib/api";
import { begripAlsMarkdown } from "@/lib/artefactMarkdown";
import { definitieAard } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL } from "@/lib/begrippenOverzicht";
import type { Werkgebied } from "@/lib/types";
import { useBegrip } from "@/lib/useBegrip";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { artefactPad, begripPad } from "@/lib/werkgebiedPaden";

/** Eén begrip op een eigen pagina (spoor G3, mock-up v4 `conceptPage`; de inhoud sinds spoor N `BegripInhoud`). Het
 *  begrip hoort bij het begrippenkader van één werkgebied; dat staat in het kruimelpad. */
export function BegripPagina({ werkgebiedId, begripId }: { werkgebiedId: string; begripId: string }) {
  const router = useRouter();
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const vraagRef = useRef<HTMLDivElement>(null);
  const kader = artefactPad(werkgebiedId, "begrippen");
  const stand = useBegrip({
    context: { soort: "werkgebied", werkgebiedId }, begripId,
    // Na verwijderen: terug naar het begrippenkader.
    onVerwijderd: () => { setOnbewaard(false); router.push(kader); },
  });

  useEffect(() => {
    if (bewaker.wachtend) vraagRef.current?.scrollIntoView({ block: "nearest" });
  }, [bewaker.wachtend]);
  useEffect(() => {
    haalWerkgebied(werkgebiedId).then(setWg).catch(() => {});
  }, [werkgebiedId]);

  const begrip = stand.begrip;
  const naam = begrip?.inhoud.naam || "Begrip";

  return (
    <WerkgebiedSchil titel={naam} onFout={setFout} breed bewaak={bewaker.bewaak}>
      <div data-begrip-pagina={begripId}>
        <PaginaKop
          kruimels={[{ label: "Begrippen", href: "/begrippen" }, { label: wg?.naam ?? "Werkgebied", href: kader }, { label: naam }]}
          titel={naam}
          sub="Betekenis, voorbeelden, passages, relaties en beoordeling."
          meta={<>
            {begrip && <StatusLabel toon={BEGRIP_STATUS_TOON[begrip.status]}>{BEGRIP_STATUS_LABEL[begrip.status]}</StatusLabel>}
            {wg && <><Stip /><span>Begrippenkader {wg.naam}</span></>}
            {begrip && (() => {
              // Brondefinitie of analysebegrip: een geformuleerd begrip is geen wettelijke definitie (spoor G5).
              const aard = definitieAard(begrip.inhoud);
              return <><Stip /><span data-definitie-aard={aard.soort} title={aard.uitleg}>{aard.titel}</span></>;
            })()}
            {begrip && <><Stip /><span>revisie {begrip.revisie}</span></>}
          </>}
          acties={begrip && <>
            <ExportKnop onFout={setFout} titel={naam} formaten={[]} markdown={() => begripAlsMarkdown(begrip)} />
            <VraagLexKnop primair onderwerp={{ soort: "begrip", werkgebied_id: werkgebiedId, id: begripId, label: naam }}
              naam={`Bespreek ${naam} met Lex`} />
            <BegripMenu stand={stand} onNaarBegrip={(b) => router.push(begripPad(werkgebiedId, b))} />
          </>}
        />
        {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
        {bewaker.wachtend && (
          <div ref={vraagRef}>
            <OnbewaardMelding waar="Op de begrippagina" className="mb-4" handeling="verlaten" onBlijf={bewaker.blijf}
              onToch={() => { setOnbewaard(false); bewaker.toch(); }} />
          </div>
        )}
        <BegripInhoud stand={stand} weergave="pagina" onOnbewaard={setOnbewaard}
          onNaarBegrip={(b) => router.push(begripPad(werkgebiedId, b))} />
      </div>
    </WerkgebiedSchil>
  );
}
