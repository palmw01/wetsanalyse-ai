"use client";

import Link from "next/link";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, ObjectRij, ObjectRijen, Teller, Tellers } from "@/components/ui/Pagina";
import { ProjectKop } from "@/components/werkgebieden/ProjectKop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { STAND_LABEL, STAND_TOON, STAND_UITLEG, dekkingZin, splits } from "@/lib/deelvragen";
import type { GesprekSamenvatting } from "@/lib/types";
import { useDeelvragenDekking } from "@/lib/useDeelvragenDekking";
import { artefactKaarten, artefactPad, deelvraagPad, projectPad } from "@/lib/werkgebiedPaden";

/** Het overzicht van een werkgebied (mock-up v4, `overview`): tellers, en daaronder twee kolommen. Links de
 *  analyseopdracht – de analysevraag centraal, aanleiding, context en doel bij elkaar – en de deelvragen met
 *  hun stand; rechts de laatste gesprekken en de artefacten. Lange lijsten staan op hun eigen tab. */
export function OverzichtTab() {
  const { wg, stand } = useWerkgebied();
  const { actief, voorgesteld } = splits(wg.deelvragen);
  const dekking = useDeelvragenDekking(wg.id, wg.revisie, actief.length);
  const standVan = new Map((dekking?.deelvragen ?? []).map((d) => [d.id, d.stand]));
  const kaarten = artefactKaarten(wg, stand);
  const annotaties = kaarten.find((k) => k.soort === "annotaties")!;
  const wv = stand.werkvoorraad;
  const klaar = wv?.eenheden.filter((e) => ["afgerond", "beoordeeld", "zonder_markeringen"].includes(e.stand.status)).length;
  const begrippen = stand.begrippen?.filter((b) => b.status !== "vervangen").length;

  return (
    <div data-werkgebied-overzicht>
      <ProjectKop tab="overzicht" />
      <Tellers>
        <Teller getal={stand.gesprekken?.length} label="Gesprekken" href={projectPad(wg.id, "gesprekken")} />
        <Teller getal={wg.bronnen.length} label="Bronnen" href={projectPad(wg.id, "bronnen")} />
        <Teller getal={wv ? `${klaar}/${wv.eenheden.length}` : undefined} label="Bepalingen beoordeeld"
          href={artefactPad(wg.id, "annotaties")} />
        <Teller getal={begrippen} label="Begrippen" href={artefactPad(wg.id, "begrippen")} />
      </Tellers>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 space-y-4">
          <Kaart titel="Analyseopdracht" meer={{ href: artefactPad(wg.id, "dossier"), label: "Dossier" }} data-kaart="analyseopdracht">
            <p className="mb-3 rounded-md border-l-4 border-lint bg-lint/5 px-3 py-2.5 text-[0.95rem] font-medium leading-relaxed text-ink"
              data-analysevraag>
              {wg.analysevraag.trim() || <span className="font-normal text-muted">Nog geen analysevraag.</span>}
            </p>
            <dl className="divide-y divide-line text-sm">
              {([["aanleiding", "Aanleiding"], ["context", "Context"], ["doel", "Doel"]] as const).map(([veld, label]) => (
                <div key={veld} className="grid gap-0.5 py-2 sm:grid-cols-[7rem_1fr] sm:gap-3" data-dossier-veld={veld}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="min-w-0 whitespace-pre-line text-ink">
                    {(wg[veld] ?? "").trim() || <span className="text-muted">Nog niet ingevuld.</span>}
                  </dd>
                </div>
              ))}
            </dl>
          </Kaart>

          <Kaart titel="Deelvragen" telling={actief.length} toelichting={dekkingZin(dekking) || undefined}
            meer={{ href: artefactPad(wg.id, "dossier"), label: "Beheren" }} data-kaart="deelvragen">
            <ObjectRijen label="Deelvragen" leeg="Nog geen deelvragen. Lex stelt ze voor in het gesprek, of voeg ze toe in het dossier.">
              {actief.map((d, i) => {
                const s = standVan.get(d.id);
                return (
                  <ObjectRij key={d.id} href={deelvraagPad(wg.id, d.id)} voor={`${i + 1}.`} titel={d.vraag}
                    data-deelvraag-rij={d.id}
                    sub={`${d.bronnen.length} ${d.bronnen.length === 1 ? "bron" : "bronnen"} · ${d.begrippen.length} ${d.begrippen.length === 1 ? "begrip" : "begrippen"}`}
                    status={s && <StatusLabel toon={STAND_TOON[s]} uitleg={STAND_UITLEG[s]}>{STAND_LABEL[s]}</StatusLabel>} />
                );
              })}
            </ObjectRijen>
            {voorgesteld.length > 0 && (
              <Link href={artefactPad(wg.id, "dossier")} className="focus-ring mt-2 inline-block rounded text-xs font-medium text-aandacht-geel-tekst hover:underline">
                {voorgesteld.length} {voorgesteld.length === 1 ? "voorstel" : "voorstellen"} van Lex om te beoordelen
              </Link>
            )}
          </Kaart>
        </div>

        <div className="min-w-0 space-y-4">
          <Kaart titel="Gesprekken" telling={stand.gesprekken?.length} meer={{ href: projectPad(wg.id, "gesprekken") }}
            toelichting="Deze gesprekken staan ook onder dit werkgebied in de linkernavigatie." data-kaart="gesprekken">
            <GesprekRijen gesprekken={stand.gesprekken?.slice(0, 3) ?? null} />
            <Link href={`/workbench?werkgebied=${encodeURIComponent(wg.id)}`}
              className="focus-ring mt-2 inline-block rounded text-xs font-medium text-lint hover:underline">
              Nieuw gesprek in dit werkgebied
            </Link>
          </Kaart>

          <Kaart titel="Artefacten" meer={{ href: projectPad(wg.id, "artefacten") }} data-kaart="artefacten">
            <ObjectRijen label="Artefacten">
              {kaarten.map((k) => (
                <ObjectRij key={k.soort} href={artefactPad(wg.id, k.soort)} titel={k.titel} sub={k.versie || undefined}
                  status={k.status && <StatusLabel toon={k.status.toon}>{k.status.tekst}</StatusLabel>} />
              ))}
            </ObjectRijen>
          </Kaart>

          <Melding type="uitleg" compact>
            Annotaties en begrippen zijn zelfstandige, gedeelde objecten. Wie een gesprek verwijdert, houdt ze.
            {!annotaties.status && wg.bronnen.length > 0 && !wv && " De stand van de annotaties wordt nog geladen."}
          </Melding>
        </div>
      </div>
    </div>
  );
}

export function gesprekSub(g: GesprekSamenvatting): string {
  const d = g.updated ? new Date(g.updated) : null;
  const wanneer = d && !Number.isNaN(d.getTime())
    ? d.toLocaleDateString("nl-NL", { day: "numeric", month: "short" }) : "";
  return [wanneer, `${g.aantal_berichten} berichten`].filter(Boolean).join(" · ");
}

export function GesprekRijen({ gesprekken }: { gesprekken: GesprekSamenvatting[] | null }) {
  if (gesprekken === null) return <p className="text-sm text-muted">Laden…</p>;
  return (
    <ObjectRijen label="Gesprekken" leeg="Nog geen gesprekken in dit werkgebied.">
      {gesprekken.map((g) => (
        <ObjectRij key={g.id} href={`/workbench?gesprek=${encodeURIComponent(g.id)}`} titel={g.titel || "Nieuw gesprek"}
          sub={gesprekSub(g)} data-gesprek={g.id} />
      ))}
    </ObjectRijen>
  );
}
