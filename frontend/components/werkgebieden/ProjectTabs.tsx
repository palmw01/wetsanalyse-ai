"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { KLIK_KAART, Kaart } from "@/components/ui/Pagina";
import { GesprekRijen } from "@/components/werkgebieden/OverzichtTab";
import { ProjectKop } from "@/components/werkgebieden/ProjectKop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { knopKlasse } from "@/components/ui/Button";
import { FilterChip } from "@/components/ui/FilterChip";
import { ARTEFACT_LABEL, ARTEFACT_SOORTEN, artefactKaarten, artefactPad, type ArtefactSoort } from "@/lib/werkgebiedPaden";

/** De gesprekken van dit werkgebied (mock-up v4, `projectChats`). Een klik opent de gewone werkplek; er is
 *  geen tweede chatvenster op deze pagina. Gesprekken zijn per gebruiker: je ziet je eigen. */
export function GesprekkenTab() {
  const { wg, stand } = useWerkgebied();
  return (
    <div data-werkgebied-gesprekken>
      <ProjectKop tab="gesprekken" />
      <Kaart titel="Gesprekken binnen dit werkgebied" telling={stand.gesprekken?.length}
        toelichting="Klik op een gesprek om het in de werkplek te openen. Je ziet je eigen gesprekken; die van collega's zijn van hen."
        acties={
          <Link href={`/workbench?werkgebied=${encodeURIComponent(wg.id)}`}
            className={knopKlasse("primary", "sm")}>
            Nieuw gesprek
          </Link>
        }>
        <GesprekRijen gesprekken={stand.gesprekken} />
      </Kaart>
    </div>
  );
}

/** De analyseproducten van dit werkgebied (mock-up v4, `projectArtifacts`): zelfstandige objecten, geen
 *  chatberichten. Elk opent op een eigen pagina. */
export function ArtefactenTab() {
  const { wg, stand } = useWerkgebied();
  const [filter, setFilter] = useState<"alle" | ArtefactSoort>("alle");
  const kaarten = artefactKaarten(wg, stand).filter((k) => filter === "alle" || k.soort === filter);
  return (
    <div data-werkgebied-artefacten>
      <ProjectKop tab="artefacten" />
      <p className="mb-3 text-sm text-muted">Zelfstandig opgeslagen analyseproducten. Wie een gesprek verwijdert, houdt ze.</p>
      <div className="mb-4 flex flex-wrap gap-1.5" role="group" aria-label="Soort artefact">
        {(["alle", ...ARTEFACT_SOORTEN] as const).map((s) => (
          <FilterChip key={s} gekozen={filter === s} onKies={() => setFilter(s)}>
            {s === "alle" ? "Alles" : ARTEFACT_LABEL[s]}
          </FilterChip>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {kaarten.map((k) => (
          <Link key={k.soort} href={artefactPad(wg.id, k.soort)} data-artefact-kaart={k.soort}
            className={`${KLIK_KAART} group flex min-h-[11rem] flex-col p-5`}>
            {/* De icoontegel van het artefactkaartje in het gesprek (spoor K, de mock-up). */}
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-lint/10 text-lint" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 3h8l5 5v13H6z" /><path d="M14 3v5h5" /><path d="M9 13h7M9 17h7" />
              </svg>
            </span>
            <span className="mt-3 text-[11px] font-medium uppercase tracking-wide text-faint">{ARTEFACT_LABEL[k.soort]}</span>
            <span className="mt-0.5 font-display text-sm font-semibold text-ink group-hover:text-lint">{k.titel}</span>
            <span className="mt-1 flex-1 text-xs leading-relaxed text-muted">{k.omschrijving}</span>
            <span className="mt-3 flex items-center justify-between gap-2">
              <span className="text-xs text-muted">{k.versie}</span>
              {k.status && <StatusLabel toon={k.status.toon}>{k.status.tekst}</StatusLabel>}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
