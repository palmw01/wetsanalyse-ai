"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { PaginaKop, Stip } from "@/components/ui/Pagina";
import { BEGRIP_STATUS_TOON, BegripInhoud, BegripMenu } from "@/components/werkgebieden/BegripInhoud";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { begripAlsMarkdown } from "@/lib/artefactMarkdown";
import { definitieAard } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL } from "@/lib/begrippenOverzicht";
import { useBegrip } from "@/lib/useBegrip";
import { artefactPad, begripPad, projectPad } from "@/lib/werkgebiedPaden";

/** Eén begrip op een eigen pagina binnen zijn werkgebied (spoor G3, mock-up v4 `conceptPage`; de inhoud sinds spoor N
 *  `BegripInhoud`). De project-laag draagt het werkgebied en de bewaker van niet-bewaarde wijzigingen. */
export function BegripPagina({ begripId }: { begripId: string }) {
  const router = useRouter();
  const { wg, zetBreed, zetOnbewaard } = useWerkgebied();
  const [fout, setFout] = useState<string | null>(null);
  const kader = artefactPad(wg.id, "begrippen");
  const stand = useBegrip({
    context: { soort: "werkgebied", werkgebiedId: wg.id }, begripId,
    // Na verwijderen: terug naar het begrippenkader.
    onVerwijderd: () => { zetOnbewaard(false); router.push(kader); },
  });
  useEffect(() => {
    zetBreed(true);
    return () => zetBreed(false);
  }, [zetBreed]);

  const begrip = stand.begrip;
  const naam = begrip?.inhoud.naam || "Begrip";
  const naarBegrip = (b: string) => router.push(begripPad(wg.id, b));

  return (
    <div data-begrip-pagina={begripId}>
      <PaginaKop
        kruimels={[
          { label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) },
          { label: "Artefacten", href: projectPad(wg.id, "artefacten") }, { label: "Begrippenkader", href: kader }, { label: naam },
        ]}
        titel={naam}
        sub="Betekenis, voorbeelden, passages, relaties en beoordeling."
        meta={begrip && <>
          <StatusLabel toon={BEGRIP_STATUS_TOON[begrip.status]}>{BEGRIP_STATUS_LABEL[begrip.status]}</StatusLabel>
          <Stip /><span>Begrippenkader {wg.naam}</span>
          {(() => {
            // Brondefinitie of analysebegrip: een geformuleerd begrip is geen wettelijke definitie (spoor G5).
            const aard = definitieAard(begrip.inhoud);
            return <><Stip /><span data-definitie-aard={aard.soort} title={aard.uitleg}>{aard.titel}</span></>;
          })()}
          <Stip /><span>revisie {begrip.revisie}</span>
        </>}
        acties={begrip && <>
          <ExportKnop onFout={setFout} titel={naam} formaten={[]} markdown={() => begripAlsMarkdown(begrip)} />
          <VraagLexKnop primair onderwerp={{ soort: "begrip", werkgebied_id: wg.id, id: begripId, label: naam }}
            naam={`Bespreek ${naam} met Lex`} />
          <BegripMenu stand={stand} onNaarBegrip={naarBegrip} />
        </>}
      />
      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
      <BegripInhoud stand={stand} weergave="pagina" onOnbewaard={zetOnbewaard} onNaarBegrip={naarBegrip} />
    </div>
  );
}
