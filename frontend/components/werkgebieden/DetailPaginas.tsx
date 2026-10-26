"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Kaart, PaginaKop, SplitDetail, Stip, TabLinks, type Kruimel } from "@/components/ui/Pagina";
import { BegrippenTab } from "@/components/werkgebieden/BegrippenTab";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { DeelvraagPaneel } from "@/components/werkgebieden/DeelvraagPaneel";
import { Deelvragen } from "@/components/werkgebieden/Deelvragen";
import { ElementenTab } from "@/components/werkgebieden/ElementenTab";
import { HistorieTab } from "@/components/werkgebieden/HistorieTab";
import { GegevensDialoog, datum } from "@/components/werkgebieden/ProjectKop";
import { SamenhangTab } from "@/components/werkgebieden/SamenhangTab";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { wijzigWerkgebied } from "@/lib/api";
import type { BegripWeergave } from "@/lib/begrippen";
import { splits } from "@/lib/deelvragen";
import type { Werkgebied } from "@/lib/types";
import { BEREIK_LABEL, DOSSIER_VELDEN, ROL_LABEL, STATUS_LABEL, annotatieHref } from "@/lib/werkgebied";
import {
  ARTEFACT_LABEL, artefactKaarten, artefactPad, projectPad, voorstellenPad, type ArtefactSoort,
} from "@/lib/werkgebiedPaden";

function basisKruimels(wg: Werkgebied): Kruimel[] {
  return [{ label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) }];
}

const bespreek = (wg: Werkgebied) => (
  <VraagLexKnop primair onderwerp={{ soort: "werkgebied", werkgebied_id: wg.id, id: "", label: wg.naam }}
    naam={`Bespreek ${wg.naam} met Lex`} />
);

/** Eén artefact op een eigen pagina (mock-up v4, `artifactPage`): het product, met rechts waar het op
 *  rust en hoe ver het is. De inhoud is het bestaande zelfstandige object – geen kopie. */
export function ArtefactPagina({ soort, begrip, weergave, deel }: {
  soort: ArtefactSoort;
  begrip?: string;
  weergave: BegripWeergave;
  deel: "lijst" | "samenhang";
}) {
  const { wg, stand, zetBreed } = useWerkgebied();
  const kaart = artefactKaarten(wg, stand).find((k) => k.soort === soort)!;
  const breed = soort === "begrippen" || soort === "annotaties";
  useEffect(() => {
    zetBreed(breed);
    return () => zetBreed(false);
  }, [breed, zetBreed]);

  return (
    <div data-artefact-pagina={soort}>
      <PaginaKop
        kruimels={[...basisKruimels(wg), { label: "Artefacten", href: projectPad(wg.id, "artefacten") }, { label: ARTEFACT_LABEL[soort] }]}
        titel={kaart.titel}
        sub={kaart.omschrijving}
        meta={<>
          {kaart.status && <StatusLabel toon={kaart.status.toon}>{kaart.status.tekst}</StatusLabel>}
          {kaart.versie && <><Stip /><span>{kaart.versie}</span></>}
          <Stip /><span>Zelfstandig analyseproduct</span>
        </>}
        acties={bespreek(wg)}
      />
      {soort === "dossier" && <Dossier />}
      {soort === "bronselectie" && <Bronselectie />}
      {soort === "annotaties" && <Annotaties />}
      {soort === "begrippen" && <Begrippenkader begrip={begrip} weergave={weergave} deel={deel} />}
    </div>
  );
}

function Relaties({ soort }: { soort: ArtefactSoort }) {
  const { wg } = useWerkgebied();
  const andere = (["dossier", "bronselectie", "annotaties", "begrippen"] as const).filter((s) => s !== soort);
  return (
    <Kaart titel="Samenhang">
      <ul className="space-y-1">
        {andere.map((s) => (
          <li key={s}>
            <Link href={artefactPad(wg.id, s)} className="focus-ring block rounded-md px-2 py-1.5 text-sm text-lint hover:bg-surface">
              {ARTEFACT_LABEL[s]}
            </Link>
          </li>
        ))}
      </ul>
    </Kaart>
  );
}

function Dossier() {
  const { wg, muteer } = useWerkgebied();
  const [bewerken, setBewerken] = useState(false);
  return (
    <SplitDetail
      hoofd={<>
        <Kaart titel="Analyseopdracht" acties={<Button size="sm" variant="secondary" onClick={() => setBewerken(true)}>Bewerken</Button>}>
          <Regels className="text-sm" data-dossier>
            {DOSSIER_VELDEN.map(({ veld, label }) => (
              <Regel key={veld} naam={label} data-dossier-veld={veld}>
                {(wg[veld] ?? "").trim()
                  ? <span className="whitespace-pre-line">{wg[veld]}</span>
                  : <span className="text-muted">{`Nog geen ${label.toLowerCase()}. Lex vult het aan in het gesprek.`}</span>}
              </Regel>
            ))}
          </Regels>
        </Kaart>
        {/* `Deelvragen` draagt zijn eigen kop, telling en de voorstellen van Lex. */}
        <Kaart><Deelvragen wg={wg} muteer={muteer} /></Kaart>
        {bewerken && (
          <GegevensDialoog wg={wg} onSluit={() => setBewerken(false)}
            onBewaar={async (w) => {
              if (await muteer((r) => wijzigWerkgebied(wg.id, { ...w, verwachte_revisie: r }), { gelukt: "Opgeslagen." })) setBewerken(false);
            }} />
        )}
      </>}
      zij={<>
        <Kaart titel="Versie">
          <Regels className="text-sm">
            <Regel naam="Revisie">{wg.revisie}</Regel>
            <Regel naam="Status">{STATUS_LABEL[wg.status]}</Regel>
            <Regel naam="Gewijzigd">{datum(wg.gewijzigd)}</Regel>
          </Regels>
        </Kaart>
        <Relaties soort="dossier" />
      </>}
    />
  );
}

function Bronselectie() {
  const { wg, stand } = useWerkgebied();
  const open = stand.kandidaten?.filter((k) => k.status === "voorgesteld").length ?? 0;
  return (
    <SplitDetail
      hoofd={<>
        {wg.afbakening.trim() && (
          <Kaart titel="Afbakening"><p className="whitespace-pre-line text-sm text-ink">{wg.afbakening}</p></Kaart>
        )}
        {(["analyseren", "context"] as const).map((rol) => {
          const lijst = wg.bronnen.filter((b) => b.rol === rol);
          return (
            <Kaart key={rol} titel={rol === "analyseren" ? "Om te analyseren" : "Context"} telling={lijst.length}>
              {lijst.length === 0 ? <p className="text-sm text-muted">Geen.</p> : (
                <ul className="divide-y divide-line">
                  {lijst.map((b) => (
                    <li key={b.id} className="py-2.5 text-sm">
                      <Link href={annotatieHref(b.bron_iri)} className="focus-ring rounded font-medium text-lint hover:underline">
                        {b.label || b.bron_iri}
                      </Link>
                      <p className="text-xs text-muted">{BEREIK_LABEL[b.bereik]} · opgenomen door {b.toegevoegd_door}</p>
                      {b.reden && <p className="mt-1 whitespace-pre-line text-ink">{b.reden}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Kaart>
          );
        })}
      </>}
      zij={<>
        <Kaart titel="Beheren">
          <p className="text-sm text-muted">Opnemen, de rol wijzigen of weghalen doe je in het register.</p>
          <Link href={projectPad(wg.id, "bronnen")} className="focus-ring mt-2 inline-block rounded text-sm font-medium text-lint hover:underline">
            Naar de bronnen
          </Link>
          {open > 0 && (
            <Link href={voorstellenPad(wg.id)} className="focus-ring mt-1 block rounded text-sm font-medium text-aandacht-geel-tekst hover:underline">
              {open} {open === 1 ? "voorstel" : "voorstellen"} van Lex
            </Link>
          )}
        </Kaart>
        <Relaties soort="bronselectie" />
      </>}
    />
  );
}

function Annotaties() {
  const { wg } = useWerkgebied();
  const router = useRouter();
  return (
    // Opnieuw ophalen bij elke nieuwe revisie: een andere selectie is een andere inventaris.
    <Kaart>
      <ElementenTab key={wg.revisie} id={wg.id}
        onNaarBegrip={(b) => router.push(artefactPad(wg.id, "begrippen", { begrip: b }))} />
    </Kaart>
  );
}

function Begrippenkader({ begrip, weergave, deel }: { begrip?: string; weergave: BegripWeergave; deel: "lijst" | "samenhang" }) {
  const { wg, muteer, onbewaard, zetOnbewaard } = useWerkgebied();
  const router = useRouter();
  // Begrip en weergave staan in de URL; `replace`, want een begripwissel is geen stap in de geschiedenis.
  const naar = (b: string | undefined, w: BegripWeergave = weergave) =>
    router.replace(artefactPad(wg.id, "begrippen", { begrip: b, weergave: w }), { scroll: false });
  return (
    <>
      <TabLinks label="Begrippenkader" actief={deel} tabs={[
        { key: "lijst", label: "Begrippen", href: artefactPad(wg.id, "begrippen") },
        { key: "samenhang", label: "Samenhang", href: artefactPad(wg.id, "begrippen", { deel: "samenhang" }) },
      ]} />
      {deel === "samenhang" ? (
        <SamenhangTab wg={wg} muteer={muteer} onKiesBegrip={(b) => router.push(artefactPad(wg.id, "begrippen", { begrip: b, weergave: "kaart" }))} />
      ) : (
        <BegrippenTab id={wg.id} gekozen={begrip} onbewaard={onbewaard} onOnbewaard={zetOnbewaard} weergave={weergave}
          onKies={(b, w) => naar(b, w ?? weergave)} onWeergave={(w) => naar(begrip, w)} />
      )}
    </>
  );
}

/** Eén deelvraag op een eigen pagina (mock-up v4, `questionPage`): de vraag, haar stand, de voorstellen van
 *  Lex die haar vervangen, haar bronnen en begrippen, en wat Lex erbij vond – dezelfde inhoud als het paneel
 *  naast het gesprek. */
export function DeelvraagPagina({ deelvraagId }: { deelvraagId: string }) {
  const { wg, laad } = useWerkgebied();
  const router = useRouter();
  const { actief } = splits(wg.deelvragen);
  const nr = actief.findIndex((d) => d.id === deelvraagId);
  const d = wg.deelvragen?.find((x) => x.id === deelvraagId);
  return (
    <div data-deelvraag-pagina={deelvraagId}>
      <PaginaKop
        kruimels={[...basisKruimels(wg), { label: nr >= 0 ? `Deelvraag ${nr + 1}` : "Deelvraag" }]}
        titel={d?.vraag ?? "Deelvraag"}
        sub="De vraag, haar bronnen en begrippen, en wat Lex erbij vond."
        acties={d && (
          <VraagLexKnop primair onderwerp={{ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag }}
            naam={`Bespreek deze deelvraag met Lex`} />
        )}
      />
      <Kaart>
        <DeelvraagPaneel key={deelvraagId} werkgebiedId={wg.id} deelvraagId={deelvraagId} onGewijzigd={() => void laad()}
          onKies={(o) => router.push(`${projectPad(wg.id)}/deelvragen/${encodeURIComponent(o.id)}`)} />
      </Kaart>
    </div>
  );
}

export function HistoriePagina() {
  const { wg } = useWerkgebied();
  return (
    <div data-historie-pagina>
      <PaginaKop kruimels={[...basisKruimels(wg), { label: "Historie" }]} titel={`Historie van ${wg.naam}`}
        sub="Wie wat deed in dit werkgebied: bronnen, deelvragen, begrippen en besluiten, nieuwste eerst." />
      <Kaart><HistorieTab key={wg.revisie} id={wg.id} bronnen={wg.bronnen} /></Kaart>
    </div>
  );
}

/** De bepalingen die Lex voorstelde (fase A), om te beoordelen: opnemen, later of uitsluiten. */
export function BronVoorstellenPagina() {
  const { wg, laad } = useWerkgebied();
  const labels = useMemo(() => new Map(wg.bronnen.map((b) => [b.bron_iri, b.label || b.bron_iri])), [wg.bronnen]);
  return (
    <div data-bronvoorstellen-pagina>
      <PaginaKop
        kruimels={[...basisKruimels(wg), { label: "Bronnen", href: projectPad(wg.id, "bronnen") }, { label: "Voorstellen van Lex" }]}
        titel="Bepalingen voorgesteld door Lex"
        sub="Wat Lex vond toen je hem in het gesprek liet zoeken. Opnemen maakt een bronselectie met de rol die je kiest."
        acties={bespreek(wg)} />
      <Kaart><BronKandidaten id={wg.id} labels={labels} onGewijzigd={() => void laad()} /></Kaart>
      <p className="mt-3 text-xs text-muted">
        {ROL_LABEL.analyseren}: telt mee in de werkvoorraad · {ROL_LABEL.context}: ondersteunt de analyse.
      </p>
    </div>
  );
}
