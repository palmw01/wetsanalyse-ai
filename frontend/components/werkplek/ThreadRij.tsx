"use client";

// Eén beurt in de thread van de werkplek.
//
// Dit stond als één grote `items.map` in `WerkplekClient`. Tijdens het streamen rendert dat
// component elk frame opnieuw, en daarmee élke beurt in het gesprek – ook de tachtig die al lang
// klaar zijn. Als eigen `memo`-component rendert alleen de rij waarvan iets veranderde: de beurt
// die binnenstroomt. Dat werkt alleen als de props stabiel zijn, dus de handelingen komen binnen als
// één `acties`-object dat `WerkplekClient` één keer maakt (zie `useThreadActies` daar), en per rij
// alleen het eigen document en de eigen vlaggen – niet de hele `docs`-map.

import { memo, useMemo, useState } from "react";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import { Antwoord } from "@/components/antwoord/Antwoord";
import { BepalingChips } from "@/components/antwoord/BepalingChip";
import { BerichtSamenhangContext, type BerichtSamenhang } from "@/components/werkplek/ContextPaneel";
import { Vindplaats } from "@/components/antwoord/Vindplaats";
import { alleenNietGetoetst } from "@/lib/antwoord";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { ChevronOmlaag, Cirkel, Waarschuwing } from "@/components/ui/Icoon";
import { HergebruikMelding } from "@/components/werkplek/HergebruikMelding";
import { Denkt } from "@/components/ui/Denkt";
import { Melding } from "@/components/ui/Melding";
import { PaneelChip, chipSub } from "@/components/ui/PaneelChip";
import { KeuzeKaart } from "@/components/werkplek/KeuzeKaart";
import { Markdown, StreamendeTekst } from "@/components/werkplek/Markdown";
import { ReeksBlok } from "@/components/werkplek/ReeksBlok";
import { DelegatieBlok } from "@/components/werkplek/DelegatieBlok";
import { VragenKaart } from "@/components/werkplek/VragenKaart";
import {
  doelVanKandidaat, kandidaatLabel, kandidaatPrompt,
} from "@/lib/annotatie";
import type { NodeDoel } from "@/lib/annotatieNode";
import { ARTEFACT_SOORT_LABEL, artefactKop, isTeOpenen, type Artefact } from "@/lib/artefact";
import { doelenVanKandidaten, reeksPrompt } from "@/lib/reeks";
import { kaartenVan, normaliseerBronnen, zonderKaarten } from "@/lib/bronnen";
import { overzichtAlsMarkdown, telling } from "@/lib/overzicht";
import { beurtSamenvatting } from "@/lib/waarom";
import { KOPIEER_MISLUKT, KOPIEER_MISLUKT_KORT, useKopieer } from "@/lib/kopieer";
import type { ThreadItem } from "@/lib/threadItem";
import { ANNOTEER_PROMPT, PLAFOND, bepalingen, deelgesprekken, regiePrompt, type BevestigingKeuze } from "@/lib/werkgebiedAnnoteren";
import { MEEDENK_PROMPT } from "@/lib/begripVoorstellen";
import type { VragenGroep } from "@/lib/vraagkaart";
import type {
  AgentGrounding, AgentKandidaat, Bron, Overzicht,
  BeurtUitkomst,
} from "@/lib/types";

/** Een werkgebiedopdracht die Lex pas na akkoord start: het werkgebied annoteren (fase B, de default)
 *  of meedenken over de begripsvoorstellen (fase C). `bevestigd` = het aantal dat de analist zag. */
export type { WerkgebiedAnnoteren } from "@/lib/beurtVerzoek";
import type { BeurtVerzoek } from "@/lib/beurtVerzoek";

/** Wat een rij kan laten gebeuren. Eén stabiel object per venster, zodat `memo` iets oplevert. */
export interface ThreadActies {
  /** Een nieuwe beurt (`lib/beurtVerzoek.ts`): alleen wat erin staat gaat mee. */
  verstuur: (verzoek: BeurtVerzoek) => void;
  openArtefact: (slug: string, doel?: NodeDoel) => void;
  /** Een artefact dat geen annotatie is (begripsvoorstellen) in het artefactpaneel openen. */
  openArtefactVan: (artefact: Artefact) => void;
  /** De samenhang van een bron onder een antwoord in de graaf; `extra` zijn de andere genoemde
   *  artikelen, of de andere delen van een overzicht. `graaf`: met welk bereik hij opent en wat de
   *  nadruk krijgt (een overzicht: de hele kennisgraaf, met alles uit het overzicht). */
  /** Eén lid uit een reeksblok openen, met bladeren door de rest van de reeks. */
  openReeksLid: (runId: string, doel: NodeDoel) => void;
  stop: () => void;
  /** *Annuleren* bij een voorstel van Lex: niets starten, en dat vastleggen in het gesprek. */
  annuleer: () => void;
  /** Het overzicht van een antwoord naast het gesprek openen. */
  openOverzicht: (overzicht: Overzicht) => void;
  /** "Een vraag stellen ›": de weggeklikte vraag onderaan weer openen (activiteit 1). */
  openVraag: () => void;
  /** Een ander gesprek openen: het deelgesprek van een subagent of regie. */
  openGesprek: (id: string) => void;
}

interface Props {
  item: ThreadItem;
  /** Is dit de beurt die nu binnenstroomt? Die krijgt platte tekst tot hij klaar is. */
  streamt: boolean;
  /** Er loopt een beurt (ergens in dit gesprek). */
  bezig: boolean;
  geblokkeerd: boolean;
  demo: boolean;
  /** Een reeksblok: loopt déze reeks nu? */
  loopt: boolean;
  /** Het eerste item van een reeks vragen (activiteit 1): de Vragen-kaart die het draagt. */
  vragen?: VragenGroep;
  /** Een voorstel van Lex met een bevestiging: al beantwoord (gestart of geannuleerd)? Dan geen knoppen. */
  keuze?: BevestigingKeuze;
  /** Het gesprek van deze thread: de stand van zijn delegaties staat bij de api per gesprek. */
  gesprekId?: string | null;
  acties: ThreadActies;
}

export const ThreadRij = memo(function ThreadRij({
  item, streamt, bezig, geblokkeerd, demo, loopt, vragen, keuze, gesprekId, acties,
}: Props) {
  // De kaarten onder een antwoord (ontdubbelen PR 2): per bepaling één, en de samenhang van het bericht voor elke ingang
  // erin (kaart, vindplaats, citatie). De bronnenlijst laat weg wat een kaart heeft.
  const kaarten = useMemo(() => (item.type === "antwoord" ? kaartenVan(item) : null), [item]);
  const bericht = useMemo<BerichtSamenhang | null>(() => (kaarten?.doelen.length
    ? { doelen: kaarten.doelen, graaf: { keten: true } } : null), [kaarten]);
  const restBronnen = useMemo(() => (item.type === "antwoord" && item.bronnen
    ? zonderKaarten(item.bronnen, kaarten?.bepalingen ?? []) : []), [item, kaarten]);
  if (vragen) {
    // Het samenstellen van een werkgebied: wat Lex bij de eerste vraag zei, en de vragen met je antwoorden.
    return (
      <LexRij>
          {vragen.tekst && <div className="mb-2"><Markdown tekst={vragen.tekst} /></div>}
          {/* De vraag van een subagent (ADR-016 §A4): wat de subagents deden, boven de vraag. */}
          {(item.type === "antwoord" || item.type === "artefact") && item.delegatie && !demo && (
            <div className="mb-2"><DelegatieBlok weergave={item.delegatie} gesprekId={gesprekId} loopt={streamt}
              onOpenGesprek={acties.openGesprek} /></div>
          )}
          <VragenKaart groep={vragen} onOpen={acties.openVraag} />
      </LexRij>
    );
  }
  return item.type === "user" && item.doorgegeven ? (
    // Wat de code in een deelgesprek doorgaf (B5): geen bubbel van de jurist, maar een blok van Lex met wat het is.
    <div className="flex animate-rise gap-3" data-doorgegeven={item.doorgegeven}>
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">
          Lex · {item.doorgegeven === "opdracht" ? "Opdracht aan de subagent" : "Antwoorden van de jurist, doorgegeven"}
        </p>
        <div className="whitespace-pre-wrap break-words rounded-kaart border border-line bg-surface px-4 py-2.5 text-sm text-ink">
          {item.tekst}
        </div>
      </div>
    </div>
  ) : item.type === "user" ? (
    <div className="flex animate-rise flex-col items-end gap-1">
      {item.over && (
        <span className="max-w-[85%] truncate rounded-full bg-surface px-2.5 py-0.5 text-2xs text-muted">
          bij {item.over}
        </span>
      )}
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-bubbel bg-lint/10 px-4 py-2.5 text-sm text-ink">
        {item.tekst}
      </div>
      {item.nietVerstuurd && (
        <span className="max-w-[85%] text-right text-2xs text-muted">
          Niet verstuurd: er liep al een vraag in dit gesprek. Je vraag staat weer in het invoerveld.
        </span>
      )}
    </div>
  ) : item.type === "antwoord" ? (
    <BerichtSamenhangContext.Provider value={bericht}>
    <LexRij denk={item.denk} denkt={bezig && !item.tekst}>
        {item.delegatie && !demo && (
          <DelegatieBlok weergave={item.delegatie} gesprekId={gesprekId} loopt={streamt} onOpenGesprek={acties.openGesprek} />
        )}
        {item.antwoord ? (
          <Antwoord antwoord={item.antwoord} bronnen={item.bronnen} nietLetterlijk={item.grounding?.niet_letterlijk} />
        ) : item.tekst ? (
          streamt ? (
            <StreamendeTekst tekst={item.tekst} />
          ) : (
            // De afgekeurde citaten worden in de tekst zelf aangewezen; het blok eronder
            // blijft staan voor wat níét in de weergave terug te vinden was.
            <Markdown tekst={item.tekst} nietLetterlijk={item.grounding?.niet_letterlijk} bronnen={item.bronnen} />
          )
        ) : item.denk || item.overzicht || !streamt ? null : (
          <Denkt />
        )}
        {/* Wat het antwoord aanwijst, naast het gesprek te openen met wat de graaf er verder over weet (ADR-008). */}
        {!demo && kaarten && <BepalingChips bepalingen={kaarten.bepalingen} />}
        <BeurtUitkomstBlok uitkomst={item.uitkomst} />
        {/* Het overzicht uit de graaf staat naast het gesprek: hier de samenvatting en een kaartje. */}
        {item.overzicht && item.overzicht.regelingen.length > 0 && !demo && (
          <div className="mt-3"><OverzichtKaartje overzicht={item.overzicht} onOpen={() => acties.openOverzicht(item.overzicht!)} /></div>
        )}
        {/* Bij een overzicht linkt het paneel elke vindplaats: een bronnenlijst van 40–90 regels ernaast
            zegt niets nieuws. De bronnen blijven in het bericht (herkomst, eval). */}
        {!item.overzicht && !item.antwoord?.doelen.length && restBronnen.length > 0 && <Bronnen bronnen={restBronnen} />}
        {item.bevestiging && !demo && (
          <BevestigingBlok bevestiging={item.bevestiging} keuze={keuze} bezig={bezig} geblokkeerd={geblokkeerd} acties={acties} />
        )}
        {/* Een antwoord met alleen afgeleide duiding of tekst van de code (een leemte) heeft niets van het model te controleren. */}
        {item.tekst && item.grounding && !(item.grounding.niveau === "onbepaald" && alleenNietGetoetst(item.antwoord)) && <Brongetrouwheid grounding={item.grounding} />}
        {item.tekst && <KopieerKnop tekst={item.overzicht ? `${item.tekst}\n\n${overzichtAlsMarkdown(item.overzicht)}` : item.tekst} />}
    </LexRij>
    </BerichtSamenhangContext.Provider>
  ) : item.type === "kandidaten" ? (
    <LexRij>
        {item.tekst && <Markdown tekst={item.tekst} />}
        {item.keuze ? (
          <KeuzeKaart
            kandidaten={item.kandidaten}
            keuze={item.keuze}
            uitgeschakeld={bezig || geblokkeerd || demo}
            onKies={(ks) => ks.length === 1
              ? acties.verstuur({ prompt: kandidaatPrompt(ks[0]), doel: doelVanKandidaat(ks[0]) })
              : acties.verstuur({ prompt: reeksPrompt(item.keuze?.ouder ?? "", ks), doelen: doelenVanKandidaten(ks) })}
          />
        ) : (
          <KandidatenKeuze
            kandidaten={item.kandidaten}
            uitgeschakeld={bezig || geblokkeerd}
            onKies={(k) => acties.verstuur({ prompt: kandidaatPrompt(k), doel: doelVanKandidaat(k) })}
          />
        )}
    </LexRij>
  ) : item.type === "reeks" ? (
    <LexRij>
        <BeurtUitkomstBlok uitkomst={item.uitkomst} />
        <ReeksBlok
          reeks={item.reeks}
          loopt={loopt}
          onStop={acties.stop}
          onOpen={(o) => {
            if (o.annotatie_doel) acties.openReeksLid(item.reeks.runId, o.annotatie_doel);
          }}
          spoor={(o, actief) => o.denk && <DenkProces tekst={o.denk} actief={actief} />}
        />
        {/* De samenvatting van een werkgebied-run komt ná de bepalingen. */}
        {item.tekst && <div className="mt-3"><Markdown tekst={item.tekst} /></div>}
    </LexRij>
  ) : item.type === "artefact" ? (
    // Een ander artefact (begripsvoorstellen): dezelfde vorm als een annotatie – naam, wat Lex erover
    // zegt en de chip naar het paneel; het denkproces bovenaan, zoals bij elke beurt.
    <LexRij denk={item.denk}>
        {item.tekst && <div className="mb-3"><Markdown tekst={item.tekst} /></div>}
        <ArtefactChip artefact={item.artefact} onOpen={() => acties.openArtefactVan(item.artefact)} />
        {item.delegatie && !demo && (
          <DelegatieBlok weergave={item.delegatie} gesprekId={gesprekId} loopt={streamt} onOpenGesprek={acties.openGesprek} />
        )}
        {/* De bundel van een regie draagt de knop voor de volgende fase (graph-qa #1521). */}
        {item.bevestiging && !demo && (
          <BevestigingBlok bevestiging={item.bevestiging} keuze={keuze} bezig={bezig} geblokkeerd={geblokkeerd} acties={acties} />
        )}
    </LexRij>
  ) : (
    // Een annotatie is ook een beurt van Lex: zijn naam, wat hij erover zegt (hoogstens vier zinnen,
    // door graph-qa uit de data opgebouwd) en de kaart naar het artefact. Het denkproces staat bovenaan, net als bij
    // een antwoord: één plek en één label voor elke beurt (besluit gebruiker 15 nov 2026).
    <LexRij denk={item.denk}>
        {item.tekst && <div className="mb-3" data-testid="annotatie-samenvatting"><Markdown tekst={item.tekst} /></div>}
        <AnnotatieChip
          titel={item.titel}
          onOpen={() => acties.openArtefact(item.slug, item.annotatie_doel)}
        />
        {(() => {
          // De meting van deze ronde: wat er uitkwam, wat zonder zinsontleding ging en hoe lang het
          // duurde. Uit het bericht zelf.
          const samenvatting = beurtSamenvatting(item.meting);
          return samenvatting && <p className="mt-1 px-1 text-xs text-muted" data-testid="beurtsamenvatting">Laatste ronde van Lex: {samenvatting}</p>;
        })()}
        {(() => {
          // Alleen op een gedeelde laag, dus met een bronnode.
          const opnieuwDoel = item.annotatie_doel ? {
            bwbId: item.annotatie_doel.bwb_id || "", bron_iri: item.annotatie_doel.bron_iri,
          } : undefined;
          if (!item.hergebruik && !opnieuwDoel) return null;
          return (
            <HergebruikMelding
              hergebruik={item.hergebruik}
              uitgeschakeld={bezig || geblokkeerd || demo}
              onOpnieuw={opnieuwDoel ? () => acties.verstuur({
                prompt: `Annoteer ${item.annotatie_doel?.label || "deze bepaling"} opnieuw`,
                doel: opnieuwDoel, hergebruik: "opnieuw",
              }) : undefined}
            />
          );
        })()}
    </LexRij>
  );
}, zelfdeRij);

/** De `memo`-vergelijking: alles op identiteit, behalve de Vragen-kaart – die wordt elke render opnieuw
 *  gegroepeerd (`groepeerVragen`) en telt als gelijk zolang de inhoud gelijk is. */
function zelfdeRij(a: Props, b: Props): boolean {
  const sleutels = Object.keys(b) as (keyof Props)[];
  if (Object.keys(a).length !== sleutels.length) return false;
  return sleutels.every((k) => k === "vragen" ? JSON.stringify(a.vragen) === JSON.stringify(b.vragen) : a[k] === b[k]);
}

/** Het kaartje van een overzicht, in de vorm van de artefactchip: de inhoud staat naast het gesprek. */
function OverzichtKaartje({ overzicht, onOpen }: { overzicht: Overzicht; onOpen: () => void }) {
  const t = telling(overzicht);
  const n = t.bepalingen + t.ookGenoemd;
  return (
    <PaneelChip titel={`Overzicht: ${overzicht.gevraagd}`} icoon={<GraafIcoon />} onClick={onOpen} data-testid="overzicht-kaartje"
      sub={`${t.regelingen === 1 ? "1 regeling" : `${t.regelingen} regelingen`} · ${n === 1 ? "1 bepaling" : `${n} bepalingen`}`} />
  );
}

const ARTEFACTICOON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="6" cy="6" r="3" /><circle cx="18" cy="18" r="3" /><circle cx="18" cy="6" r="3" />
    <path d="M9 6h6M18 9v6M8.2 8.2l7.6 7.6" />
  </svg>
);

const ANNOTATIEICOON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
    <path d="M14 2v6h6M9 13l2 2 4-4" />
  </svg>
);

/** De chip van een artefact dat geen annotatie is. Afleidingsregels zijn gereserveerd: de kaart staat
 *  er, maar opent nog niets – en zegt dat, in plaats van een knop die niets doet. */
function ArtefactChip({ artefact, onOpen }: { artefact: Artefact; onOpen: () => void }) {
  const { soort, titel } = artefactKop(artefact);
  if (!isTeOpenen(artefact)) {
    return <PaneelChip titel={titel} data-artefact-soort={artefact.soort}
      sub={`${soort ? `${soort} · nog niet te openen` : "Nog niet te openen"} in de werkplek`} />;
  }
  return <PaneelChip titel={titel} icoon={ARTEFACTICOON} onClick={onOpen} data-artefact-soort={artefact.soort}
    sub={chipSub(soort, artefact.soort === "werkgebied" ? "bekijken" : "beoordelen")} />;
}

/** Compacte kaart in de chatstroom die naar het annotatie-artefact leidt (opent het slide-in paneel). */
function AnnotatieChip({ titel, onOpen }: {
  /** Het label uit het bericht zelf (de titel van het artefact). */
  titel?: string;
  onOpen: () => void;
}) {
  return <PaneelChip titel={titel || "Annotatie"} icoon={ANNOTATIEICOON} onClick={onOpen} data-tour="chip"
    sub={chipSub(ARTEFACT_SOORT_LABEL.annotatie, "beoordelen")} />;
}

/** De keuzelijst bij een onderwerp-vraag: welke bepaling gaat de werkvoorraad in?
 *
 *  Eén klik = één annotatie-opdracht. Bewust géén multi-select met "annoteer alle vijf": elke
 *  annotatie is een eigen document met een eigen review, en vijf tegelijk starten maakt de
 *  reviewlast onzichtbaar op het moment dat je hem aangaat.
 */
function KandidatenKeuze({
  kandidaten,
  uitgeschakeld,
  onKies,
}: {
  kandidaten: AgentKandidaat[];
  /** Er loopt al een beurt, of het tokenbudget is op. De keuzes blijven zichtbaar – wat de agent
   *  voorstelde hoort leesbaar te blijven – maar zijn dan niet aan te klikken. */
  uitgeschakeld: boolean;
  onKies: (k: AgentKandidaat) => void;
}) {
  return (
    <ul className="mt-2 flex flex-col gap-2">
      {kandidaten.map((k) => (
        <li key={`${k.bwbId}|${k.artikel}|${k.lid ?? ""}`}>
          <PaneelChip titel={kandidaatLabel(k)} sub={k.fragment || undefined} subRegels={2}
            uitgeschakeld={uitgeschakeld} onClick={() => onKies(k)} />
        </li>
      ))}
    </ul>
  );
}

/** Een voorstel dat Lex niet zonder akkoord start: de knop die het start en *Annuleren*, of wat er gekozen is. Eén blok voor
 *  een gewoon antwoord en een artefact (de bundel van een regie met de knop voor de volgende fase). */
function BevestigingBlok({ bevestiging, keuze, bezig, geblokkeerd, acties }: {
  bevestiging: import("@/lib/types").Bevestiging;
  keuze?: BevestigingKeuze;
  bezig: boolean;
  geblokkeerd: boolean;
  acties: ThreadActies;
}) {
  if (bevestiging.aantal <= 0) return null;
  return (
    <>
      {/* Lex begint niet zonder akkoord: het voorstel noemt aantal en kosten, de knop start. */}
      {keuze && (
        <p className="mt-3 text-xs text-muted" data-bevestiging-keuze={keuze}>
          {keuze === "geannuleerd" ? "Geannuleerd: Lex is niet begonnen." : "Gestart."}
        </p>
      )}
      {!keuze && (
        <ButtonRow align="start" className="mt-3">
        {bevestiging.soort === "regie" && bevestiging.plan_id && bevestiging.opdracht ? (
          <Button size="sm" className="w-full sm:w-auto" disabled={bezig || geblokkeerd}
            data-bevestiging={bevestiging.aantal}
            onClick={() => acties.verstuur({ prompt: regiePrompt(bevestiging.opdracht!), regie:
              { werkgebiedId: bevestiging.werkgebied_id, opdracht: bevestiging.opdracht!,
                planId: bevestiging.plan_id! } })}>
            Start de regie ({deelgesprekken(bevestiging.aantal)})
          </Button>
        ) : bevestiging.soort === "begrippen_verdiepen" ? (
          <Button size="sm" className="w-full sm:w-auto" disabled={bezig || geblokkeerd}
            data-bevestiging={bevestiging.aantal}
            onClick={() => acties.verstuur({ prompt: MEEDENK_PROMPT, annoteren:
              { werkgebiedId: bevestiging.werkgebied_id, bevestigd: bevestiging.aantal,
                modus: "begrippen_verdiepen",
                ...(bevestiging.werkvoorraad_id ? { werkvoorraadId: bevestiging.werkvoorraad_id } : {}) } })}>
            Laat Lex meedenken ({bevestiging.aantal})
          </Button>
        ) : (
          <Button size="sm" className="w-full sm:w-auto" disabled={bezig || geblokkeerd}
            data-bevestiging={bevestiging.aantal}
            onClick={() => acties.verstuur({ prompt: ANNOTEER_PROMPT, annoteren:
              { werkgebiedId: bevestiging.werkgebied_id, bevestigd: bevestiging.aantal,
                ...(bevestiging.bereik ? { bereik: bevestiging.bereik } : {}),
                ...(bevestiging.deelvraag_id ? { deelvraagId: bevestiging.deelvraag_id } : {}) } })}>
            Laat Lex annoteren ({bepalingen(Math.min(bevestiging.aantal, PLAFOND))})
          </Button>
        )}
          <Button size="sm" variant="secondary" className="w-full sm:w-auto" disabled={bezig}
            onClick={() => acties.annuleer()}>
            Annuleren
          </Button>
        </ButtonRow>
      )}
    </>
  );
}

/** Klein avatar links van een antwoord van Lex (zelfde icoonstijl als de AnnotatieChip).
 *  Bewust een machine-icoon en geen monogram of gezicht: Lex heeft een naam om over te kunnen
 *  praten, niet om als collega te lezen – zijn voorstellen zijn voorstellen. */
function LexAvatar() {
  return (
    <span
      className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-lint/10 text-lint"
      aria-hidden
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 8V4H8" />
        <rect width="16" height="12" x="4" y="8" rx="2" />
        <path d="M2 14h2M20 14h2M15 13v2M9 13v2" />
      </svg>
    </span>
  );
}

/** Kopieert de letterlijke antwoordtekst; toont kort "Gekopieerd". Subtiel, hover-onthullend op desktop. */
function KopieerKnop({ tekst }: { tekst: string }) {
  const { stand, kopieer } = useKopieer();
  return (
    <button
      type="button"
      onClick={() => void kopieer(tekst)}
      aria-label="Antwoord kopiëren"
      className="mt-2 inline-flex items-center gap-1.5 rounded px-1.5 py-1 text-xs text-muted transition-opacity hover:text-lint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100 coarse:opacity-100"
    >
      {stand === "mislukt" ? (
        <span className="text-fout" title={KOPIEER_MISLUKT}>{KOPIEER_MISLUKT_KORT}</span>
      ) : stand === "gekopieerd" ? (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M20 6 9 17l-5-5" />
          </svg>
          Gekopieerd
        </>
      ) : (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <rect width="14" height="14" x="8" y="8" rx="2" />
            <path d="M4 16V4a2 2 0 0 1 2-2h10" />
          </svg>
          Kopiëren
        </>
      )}
    </button>
  );
}

/** Een beurt van Lex: avatar, naam en, als er een spoor is, het denkproces bovenaan. Elke soort rij van Lex gebruikt
 *  dit, zodat het denkproces overal op dezelfde plek en met hetzelfde label staat (besluit gebruiker 15 nov 2026). */
function LexRij({ denk, denkt = false, children }: { denk?: string; denkt?: boolean; children: React.ReactNode }) {
  return (
    <div className="group flex animate-rise gap-3">
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">Lex</p>
        {denk && <DenkProces tekst={denk} actief={denkt} />}
        {children}
      </div>
    </div>
  );
}

// Inklapbaar "Denkproces"-blok (Claude-stijl): streamt live terwijl de agent werkt (`actief`) en klapt
// automatisch dicht zodra het antwoord er is. De gebruiker kan het handmatig weer openen.
function DenkProces({
  tekst,
  actief,
}: {
  tekst: string;
  actief: boolean;
}) {
  const [keuze, setKeuze] = useState<boolean | null>(null);
  const open = keuze ?? actief;

  return (
    <div data-tour="denkproces" className="mb-2">
      <button
        type="button"
        onClick={() => setKeuze(!open)}
        className="inline-flex items-center gap-1.5 rounded-knop-xs px-1 text-xs text-muted transition-colors hover:text-ink"
        aria-expanded={open}
      >
        {actief && <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-soft motion-safe:animate-pulse" aria-hidden />}
        <span>{actief ? "Denkt na…" : "Denkproces"}</span>
        {/* De chevron wijst naar rechts (ingeklapt) en draait omlaag bij openen. */}
        <ChevronOmlaag className={`-rotate-90 transition-transform ${open ? "rotate-0" : ""}`} />
      </button>
      {open && (
        <div className="mt-1.5 whitespace-pre-wrap rounded-kaart border border-line bg-surface px-3 py-2 text-xs leading-relaxed text-muted [overflow-wrap:anywhere]">
          {tekst}
        </div>
      )}
    </div>
  );
}

// Inklapbare bronnenlijst – standaard dicht met een teller, want de lijst kan lang zijn.
/** Wat de brongetrouwheidstoets van dit antwoord vond – alleen als er iets te melden is.
 *
 *  Bij een schoon resultaat zwijgt dit blok: de bronnenlijst eronder is dan het signaal, en een
 *  groen vinkje bij elk antwoord leert mensen er overheen te kijken. De twee gevallen die er wél
 *  toe doen:
 *
 *  - **onbepaald** – het antwoord noemde geen vindplaats en geen citaat, dus er viel niets te
 *    controleren. Dat is nadrukkelijk niet hetzelfde als "gecontroleerd en juist"; in één bool
 *    vallen die twee samen, en dan laat de UI ze allebei weg.
 *  - **ongegrond** – er staat een verwijzing in die niet uit de graaf kwam, of een citaat dat niet
 *    letterlijk in de opgehaalde tekst staat. Dat is precies waar een jurist op afgaat. */
function Brongetrouwheid({ grounding }: { grounding: AgentGrounding }) {
  if (grounding.niveau === "gegrond" && !grounding.afgekapt) return null;
  const onbevestigd = grounding.onbevestigd ?? [];
  const onbepaald = grounding.niveau === "onbepaald" && !grounding.afgekapt && !onbevestigd.length;
  return (
    <div
      data-tour="grounding"
      className={`mt-2 flex items-start gap-2 rounded-kaart border px-3 py-2 text-xs ${
        onbepaald
          ? "border-line bg-surface text-muted"
          : "border-aandacht-geel-rand bg-aandacht-geel-bg text-aandacht-geel-tekst"
      }`}
    >
      <span className="mt-0.5">{onbepaald ? <Cirkel /> : <Waarschuwing />}</span>
      <span className="min-w-0">
        {onbepaald ? (
          "Dit antwoord noemt geen vindplaats of letterlijk citaat, dus er valt niets te controleren tegen de graaf."
        ) : (
          <>
            {grounding.afgekapt && (
              <span className="block" data-afgekapt>
                Dit antwoord is afgekapt: het is langer dan Lex in één keer kan schrijven. Stel een gerichtere vraag voor de rest.
              </span>
            )}
            {onbevestigd.length > 0 && (
              <span className="block break-words" data-onbevestigd>
                Niet teruggevonden in wat Lex ophaalde: {onbevestigd.join(" · ")}. Controleer dit zelf.
              </span>
            )}
            {grounding.unsupported.length > 0 && (
              <span className="block break-words">
                Niet uit de graaf: {grounding.unsupported.join(", ")}
              </span>
            )}
            {grounding.niet_letterlijk.length > 0 && (
              <span className="block break-words">
                {grounding.niet_letterlijk.length === 1 ? "Dit citaat staat" : "Deze citaten staan"} niet
                letterlijk in de opgehaalde tekst: {grounding.niet_letterlijk.map((c) => `“${c}”`).join(" · ")}
              </span>
            )}
          </>
        )}
      </span>
    </div>
  );
}

/** Een mislukte beurt: dezelfde melding live en na herladen. Gestopt zegt de tekst zelf (`_(gestopt)_`). */
function BeurtUitkomstBlok({ uitkomst }: { uitkomst?: BeurtUitkomst }) {
  if (uitkomst?.status !== "mislukt") return null;
  return (
    <div className="mt-2" data-beurt-uitkomst="mislukt">
      <Melding type="fout" compact>{uitkomst.melding || "Er ging iets mis."}</Melding>
    </div>
  );
}

function Bronnen({ bronnen }: { bronnen: Bron[] }) {
  const [open, setOpen] = useState(false);
  // Eén bepaling is één bron, gegroepeerd per regeling (`lib/bronnen.ts`) – ook voor oudere
  // berichten, waarin dezelfde bepaling nog als graaf-IRI én als jci kon staan.
  const lijst = useMemo(() => normaliseerBronnen(bronnen), [bronnen]);
  const link = (item: { label: string; href?: string }) => item.href ? (
    <a href={item.href} target="_blank" rel="noopener noreferrer"
      className="text-lint underline underline-offset-2 [overflow-wrap:anywhere]">{item.label}</a>
  ) : item.label;
  return (
    <div data-tour="bronnen" className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-ink"
        aria-expanded={open}
      >
        <span className="font-medium">Bronnen ({lijst.aantal})</span>
        {/* De chevron wijst naar rechts (ingeklapt) en draait omlaag bij openen. */}
        <ChevronOmlaag className={`-rotate-90 transition-transform ${open ? "rotate-0" : ""}`} />
      </button>
      {open && (
        <ul className="mt-1.5 space-y-1 break-words rounded-kaart border border-line bg-surface px-3 py-2 text-xs text-muted [overflow-wrap:anywhere]">
          {lijst.groepen.map((g) => (
            <li key={g.bwb_id}>
              <span className="font-medium text-ink">{link({ label: g.naam, href: g.href })}</span>
              {g.items.length > 0 && <>{" – "}{g.items.map((item, i) => (
                // Een bepaling opent als tab naast het gesprek (het bronvenster, PR 4); met Ctrl/⌘ de bron zelf.
                <span key={item.sleutel}>{i > 0 && ", "}{item.sleutel.startsWith("urn:bwb:") && item.soort !== "regeling"
                  ? <Vindplaats vindplaats={{ iri: item.sleutel, label: item.label, jci: "", regeling: g.naam }} kort />
                  : link(item)}</span>
              ))}</>}
            </li>
          ))}
          {lijst.overig.length > 0 && (
            <li>{lijst.overig.map((item, i) => <span key={item.sleutel}>{i > 0 && ", "}{link(item)}</span>)}</li>
          )}
        </ul>
      )}
    </div>
  );
}
