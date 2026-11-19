"use client";

import { useEffect } from "react";

import { Stip, PaginaKop } from "@/components/ui/Pagina";
import { RegelInhoud, RegelStatus } from "@/components/werkgebieden/RegelInhoud";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { downloadTekst, lijstOpenPunten } from "@/lib/api";
import { puntenAlsMarkdown } from "@/lib/openPunten";
import { bestandsnaam } from "@/lib/artefactMarkdown";
import { regelAlsMarkdown } from "@/lib/regels";
import { useRegel, useRegelKeten } from "@/lib/useRegel";
import { artefactPad, projectPad } from "@/lib/werkgebiedPaden";

/** Eén afleidingsregel op een eigen pagina binnen zijn werkgebied (ADR-018), in de vorm van `BegripPagina`. De
 *  project-laag draagt het werkgebied; de keten geeft *Volgt op* en *Leidt tot*. */
export function RegelPagina({ regelId }: { regelId: string }) {
  const { wg, zetBreed } = useWerkgebied();
  const stand = useRegel({ werkgebiedId: wg.id, regelId });
  const { keten } = useRegelKeten(wg.id);
  useEffect(() => {
    zetBreed(true);
    return () => zetBreed(false);
  }, [zetBreed]);

  const regel = stand.regel;
  const naam = regel?.naam || "Afleidingsregel";
  return (
    <div data-regel-pagina={regelId}>
      <PaginaKop
        kruimels={[
          { label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) },
          { label: "Artefacten", href: projectPad(wg.id, "artefacten") },
          { label: "Afleidingsregels", href: artefactPad(wg.id, "regels") }, { label: naam },
        ]}
        titel={naam}
        sub={regel ? `Leidt ${regel.uitvoer || "de uitvoer"} af, met grondslag, gevallen en voorbeelden.` : undefined}
        meta={regel && <><RegelStatus regel={regel} /><Stip /><span>Afleidingsregels {wg.naam}</span></>}
        acties={regel && (
          <ExportKnop titel={naam} onFout={() => undefined}
            formaten={[{ formaat: "json", label: "JSON", uitleg: "de regel, machineleesbaar" }]}
            markdown={async () => regelAlsMarkdown(regel)
              + puntenAlsMarkdown(await lijstOpenPunten(wg.id, { soort: "regel", id: regel.id }).catch(() => []))}
            onDownload={async () => downloadTekst(JSON.stringify(regel, null, 2), bestandsnaam(naam, "json"), "application/json")} />
        )}
      />
      <RegelInhoud stand={stand} weergave="pagina" keten={keten} />
    </div>
  );
}
