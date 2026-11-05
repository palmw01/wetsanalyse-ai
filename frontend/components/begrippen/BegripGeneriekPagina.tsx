"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { PaginaKop, Stip } from "@/components/ui/Pagina";
import { BEGRIP_STATUS_TOON, BegripInhoud, BegripMenu } from "@/components/werkgebieden/BegripInhoud";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { begripAlsMarkdown } from "@/lib/artefactMarkdown";
import { definitieAard } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL } from "@/lib/begrippenOverzicht";
import { useBegrip } from "@/lib/useBegrip";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { generiekPad } from "@/lib/werkgebiedPaden";

/** De eigen pagina van een generiek begrip (ADR-006): hier wijzig en accordeer je de inhoud, voor elk werkgebied dat het
 *  gebruikt. De passages staan per werkgebied en worden daar beheerd. */
export function BegripGeneriekPagina({ begripId }: { begripId: string }) {
  const router = useRouter();
  const [fout, setFout] = useState<string | null>(null);
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const stand = useBegrip({
    context: { soort: "generiek" }, begripId,
    onVerwijderd: () => { setOnbewaard(false); router.push("/begrippen"); },
  });
  const begrip = stand.begrip;
  const naam = begrip?.inhoud.naam || "Begrip";
  const n = begrip?.gebruik?.length ?? 0;
  const naarBegrip = (b: string) => router.push(generiekPad(b));

  return (
    <WerkgebiedSchil titel={naam} onFout={setFout} breed bewaak={bewaker.bewaak}>
      <div data-begrip-pagina={begripId} data-generiek>
        <PaginaKop
          kruimels={[{ label: "Begrippen", href: "/begrippen" }, { label: "Generiek", href: "/begrippen?kader=generiek" }, { label: naam }]}
          titel={naam}
          sub="Eén definitie voor elk werkgebied dat dit begrip gebruikt."
          meta={begrip && <>
            <StatusLabel toon="lint">Generiek</StatusLabel>
            <StatusLabel toon={BEGRIP_STATUS_TOON[begrip.status]}>{BEGRIP_STATUS_LABEL[begrip.status]}</StatusLabel>
            <Stip /><span>{n === 1 ? "Gebruikt in 1 werkgebied" : `Gebruikt in ${n} werkgebieden`}</span>
            <Stip /><span title={definitieAard(begrip.inhoud).uitleg}>{definitieAard(begrip.inhoud).titel}</span>
            <Stip /><span>revisie {begrip.revisie}</span>
          </>}
          acties={begrip && <>
            <ExportKnop onFout={setFout} titel={naam} formaten={[]} markdown={() => begripAlsMarkdown(begrip)} />
            <BegripMenu stand={stand} onNaarBegrip={naarBegrip} />
          </>}
        />
        {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
        {bewaker.wachtend && (
          <OnbewaardMelding waar="Op de begrippagina" className="mb-4" handeling="verlaten" onBlijf={bewaker.blijf}
            onToch={() => { setOnbewaard(false); bewaker.toch(); }} />
        )}
        <BegripInhoud stand={stand} weergave="pagina" onOnbewaard={setOnbewaard} onNaarBegrip={naarBegrip} />
      </div>
    </WerkgebiedSchil>
  );
}
