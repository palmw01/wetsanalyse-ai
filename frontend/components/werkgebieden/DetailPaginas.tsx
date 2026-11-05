"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { BewerkKnop } from "@/components/ui/Bewerkbaar";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Kaart, ObjectRij, ObjectRijen, PaginaKop, SplitDetail, Stip, TabLinks, type Kruimel } from "@/components/ui/Pagina";
import { BegrippenTab } from "@/components/werkgebieden/BegrippenTab";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { DeelvraagPaneel } from "@/components/werkgebieden/DeelvraagPaneel";
import { Deelvragen } from "@/components/werkgebieden/Deelvragen";
import { ElementenTab } from "@/components/werkgebieden/ElementenTab";
import { HistorieTab } from "@/components/werkgebieden/HistorieTab";
import { GegevensFormulier, ProjectKop, datum } from "@/components/werkgebieden/ProjectKop";
import { SamenhangTab } from "@/components/werkgebieden/SamenhangTab";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { wijzigWerkgebied } from "@/lib/api";
import type { BegripWeergave } from "@/lib/begrippen";
import { splits } from "@/lib/deelvragen";
import type { Werkgebied } from "@/lib/types";
import { DOSSIER_VELDEN, ROL_LABEL, STATUS_LABEL, datumNl } from "@/lib/werkgebied";
import { themaLabel } from "@/lib/tooiThemas";
import { metLeesbareBronnen } from "@/lib/bronKandidaten";
import {
  ARTEFACT_LABEL, artefactKaarten, artefactPad, begripPad, deelvraagPad, projectPad, type ArtefactSoort,
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
  const { wg, muteer, zetOnbewaard } = useWerkgebied();
  // *Gegevens bewerken* in de projectkop komt hier met `?bewerk=1`: het formulier staat dan meteen open.
  const zoek = useSearchParams();
  const router = useRouter();
  const [bewerken, setBewerken] = useState(() => zoek.get("bewerk") === "1");
  // Elk gegeven bewerk je op de plek waar het staat: het dossier op de kaart *Analyseopdracht*, peildatum en status
  // op de kaart *Versie*. Eén tegelijk.
  const [versieBewerken, setVersieBewerken] = useState(false);
  const bewaar = (sluit: () => void) => async (w: Parameters<React.ComponentProps<typeof GegevensFormulier>["onBewaar"]>[0]) => {
    if (await muteer((r) => wijzigWerkgebied(wg.id, { ...w, verwachte_revisie: r }), { gelukt: "Opgeslagen." })) sluit();
  };
  useEffect(() => {
    if (zoek.get("bewerk") === "1") router.replace(artefactPad(wg.id, "dossier"), { scroll: false });
  }, [zoek, router, wg.id]);
  return (
    <SplitDetail
      hoofd={<>
        <Kaart titel="Analyseopdracht" acties={!bewerken && !versieBewerken
          && <BewerkKnop wat="Analyseopdracht" onClick={() => setBewerken(true)} />}>
          {bewerken ? (
            <GegevensFormulier wg={wg} onSluit={() => setBewerken(false)} onOnbewaard={zetOnbewaard}
              onBewaar={bewaar(() => setBewerken(false))} />
          ) : (
          <Regels className="text-sm" data-dossier>
            <Regel naam="Naam" data-dossier-veld="naam">{wg.naam}</Regel>
            {DOSSIER_VELDEN.map(({ veld, label }) => (
              <Regel key={veld} naam={label} data-dossier-veld={veld}>
                {(wg[veld] ?? "").trim()
                  ? <span className="whitespace-pre-line">{metLeesbareBronnen(wg[veld] ?? "")}</span>
                  : <span className="text-muted">{`Nog geen ${label.toLowerCase()}. Lex vult het aan in het gesprek.`}</span>}
              </Regel>
            ))}
            <Regel naam="Thema" data-dossier-veld="thema">
              {wg.thema ? (wg.thema_label || themaLabel(wg.thema) || wg.thema) : <span className="text-muted">Nog geen thema.</span>}
            </Regel>
            {/* Het zoekbereik pas je aan via Lex (*Vul de regelingen aan*): zoeken in de graaf hoort bij het gesprek. */}
            <Regel naam="Regelingen" data-dossier-veld="regelingen">
              {(wg.regelingen ?? []).length
                ? (wg.regelingen ?? []).map((r) => r.label || r.bwb_id).join("; ")
                : <span className="text-muted">Nog geen regelingen. Lex vult ze aan in het gesprek.</span>}
            </Regel>
          </Regels>
          )}
        </Kaart>
        {/* `Deelvragen` draagt zijn eigen kop, telling en de voorstellen van Lex. */}
        <Kaart><Deelvragen wg={wg} muteer={muteer} /></Kaart>
      </>}
      zij={<>
        <Kaart titel="Versie" acties={!versieBewerken && !bewerken
          && <BewerkKnop wat="Peildatum en status" onClick={() => setVersieBewerken(true)} />}>
          {versieBewerken ? (
            <GegevensFormulier wg={wg} deel="versie" onSluit={() => setVersieBewerken(false)} onOnbewaard={zetOnbewaard}
              onBewaar={bewaar(() => setVersieBewerken(false))} />
          ) : (
          <Regels className="text-sm" data-versie>
            <Regel naam="Revisie">{wg.revisie}</Regel>
            <Regel naam="Status">{STATUS_LABEL[wg.status]}</Regel>
            <Regel naam="Peildatum">{wg.peildatum ? datumNl(wg.peildatum) : <span className="text-muted">de aanmaakdatum</span>}</Regel>
            <Regel naam="Gewijzigd">{datum(wg.gewijzigd)}</Regel>
          </Regels>
          )}
        </Kaart>
        <Relaties soort="dossier" />
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
        <SamenhangTab wg={wg} muteer={muteer} onKiesBegrip={(b) => router.push(begripPad(wg.id, b))} />
      ) : (
        // Lezen gebeurt hier, naast de lijst; de kaart (passages, relaties, accorderen) is de pagina van het
        // begrip (spoor G3).
        <BegrippenTab id={wg.id} gekozen={begrip} onbewaard={onbewaard} onOnbewaard={zetOnbewaard} weergave="lezen"
          onKies={(b, w) => (b && w === "kaart" ? router.push(begripPad(wg.id, b)) : naar(b, "lezen"))}
          onWeergave={(w) => (begrip && w === "kaart" ? router.push(begripPad(wg.id, begrip)) : naar(begrip, "lezen"))} />
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
        sub="De deelvraag, haar bronnen en wat Lex erbij voorstelt."
        acties={d && (
          <VraagLexKnop primair onderwerp={{ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag }}
            naam={`Bespreek deze deelvraag met Lex`} />
        )}
      />
      {/* Het idioom van de mock-up (spoor L): links de deelvraag met haar bronnen en de voorstellen van Lex, rechts
          waar ze bij hoort – het werkgebied en de andere deelvragen. */}
      <SplitDetail
        hoofd={(
          <DeelvraagPaneel key={deelvraagId} werkgebiedId={wg.id} deelvraagId={deelvraagId} opPagina
            onGewijzigd={() => void laad()}
            onKies={(o) => router.push(`${projectPad(wg.id)}/deelvragen/${encodeURIComponent(o.id)}`)} />
        )}
        zij={<>
          <Kaart titel="Analysevraag" meer={{ href: projectPad(wg.id), label: "Werkgebied" }}>
            <p className="text-sm text-ink">{wg.analysevraag.trim() || <span className="text-muted">Nog geen analysevraag.</span>}</p>
          </Kaart>
          {actief.length > 1 && (
            <Kaart titel="Andere deelvragen" telling={actief.length - 1}>
              <ObjectRijen label="Andere deelvragen">
                {actief.map((x, i) => x.id === deelvraagId ? null : (
                  <ObjectRij key={x.id} href={deelvraagPad(wg.id, x.id)} voor={`${i + 1}.`} titel={x.vraag}
                    sub={x.bronnen.length === 1 ? "1 bron" : `${x.bronnen.length} bronnen`} />
                ))}
              </ObjectRijen>
            </Kaart>
          )}
        </>}
      />
    </div>
  );
}

export function HistoriePagina() {
  const { wg } = useWerkgebied();
  return (
    <div data-historie-pagina>
      <ProjectKop tab="historie" />
      <Kaart titel="Historie"
        toelichting="Wie wat deed in dit werkgebied: bronnen, deelvragen, begrippen en besluiten, nieuwste eerst.">
        <HistorieTab key={wg.revisie} id={wg.id} bronnen={wg.bronnen} />
      </Kaart>
    </div>
  );
}

/** De bepalingen die Lex vond (fase A), om rond te kijken; kiezen gaat per deelvraag, in de bronselectie. */
export function BronVoorstellenPagina() {
  const { wg } = useWerkgebied();
  const labels = useMemo(() => new Map(wg.bronnen.map((b) => [b.bron_iri, b.label || b.bron_iri])), [wg.bronnen]);
  return (
    <div data-bronvoorstellen-pagina>
      <PaginaKop
        kruimels={[...basisKruimels(wg), { label: "Bronnen", href: projectPad(wg.id, "bronnen") }, { label: "Voorstellen van Lex" }]}
        titel="Bepalingen voorgesteld door Lex"
        sub="Wat Lex vond bij de laatste zoekopdracht, met het bewijs. Kiezen doe je per deelvraag, in de bronselectie."
        acties={bespreek(wg)} />
      <Kaart><BronKandidaten id={wg.id} labels={labels} /></Kaart>
      <p className="mt-3 text-xs text-muted">
        {ROL_LABEL.analyseren}: telt mee in de werkvoorraad · {ROL_LABEL.context}: ondersteunt de analyse.
      </p>
    </div>
  );
}
