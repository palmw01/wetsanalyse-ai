"use client";

// Eén beurt in de thread van de werkplek.
//
// Dit stond als één grote `items.map` in `WerkplekClient`. Tijdens het streamen rendert dat
// component elk frame opnieuw, en daarmee élke beurt in het gesprek – ook de tachtig die al lang
// klaar zijn. Als eigen `memo`-component rendert alleen de rij waarvan iets veranderde: de beurt
// die binnenstroomt. Dat werkt alleen als de props stabiel zijn, dus de handelingen komen binnen als
// één `acties`-object dat `WerkplekClient` één keer maakt (zie `useThreadActies` daar), en per rij
// alleen het eigen document en de eigen vlaggen – niet de hele `docs`-map.

import Link from "next/link";
import { memo, useEffect, useMemo, useState } from "react";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import { ChevronOmlaag, Cirkel, Waarschuwing } from "@/components/ui/Icoon";
import { HergebruikMelding } from "@/components/werkplek/HergebruikMelding";
import { KeuzeKaart } from "@/components/werkplek/KeuzeKaart";
import { Markdown, StreamendeTekst } from "@/components/werkplek/Markdown";
import { OverzichtBlok } from "@/components/werkplek/OverzichtBlok";
import { ReeksBlok } from "@/components/werkplek/ReeksBlok";
import { ToolSpoor } from "@/components/werkplek/ToolSpoor";
import {
  annotatieTitel, doelVanKandidaat, doelVoorOpnieuw, kandidaatLabel, kandidaatPrompt,
} from "@/lib/annotatie";
import type { NodeDoel } from "@/lib/annotatieNode";
import { doelenVanKandidaten, reeksPrompt } from "@/lib/reeks";
import { normaliseerBronnen, samenhangDoelen, samenhangKnopTekst } from "@/lib/bronnen";
import { overzichtAlsMarkdown, overzichtDoelen, overzichtKnopTekst } from "@/lib/overzicht";
import { beurtSamenvatting, laatsteRun } from "@/lib/waarom";
import type { ThreadItem } from "@/lib/threadItem";
import type {
  AgentDoelInvoer, AgentGrounding, AgentKandidaat, AnnotatieDocument, Bron,
} from "@/lib/types";

/** Wat een rij kan laten gebeuren. Eén stabiel object per venster, zodat `memo` iets oplevert. */
export interface ThreadActies {
  verstuur: (vast?: string, doel?: AgentDoelInvoer, hergebruik?: "opnieuw", doelen?: AgentDoelInvoer[]) => void;
  openArtefact: (slug: string, doel?: NodeDoel) => void;
  /** De 3D-samenhang van een bron onder een antwoord; `extra` zijn de andere genoemde artikelen. */
  openSamenhang: (doel: NodeDoel, extra?: NodeDoel[]) => void;
  /** Eén lid uit een reeksblok openen, met bladeren door de rest van de reeks. */
  openReeksLid: (runId: string, doel: NodeDoel) => void;
  stop: () => void;
}

interface Props {
  item: ThreadItem;
  /** Is dit de beurt die nu binnenstroomt? Die krijgt platte tekst tot hij klaar is. */
  streamt: boolean;
  /** Er loopt een beurt (ergens in dit gesprek). */
  bezig: boolean;
  geblokkeerd: boolean;
  demo: boolean;
  samenhangAan: boolean;
  /** Een reeksblok: loopt déze reeks nu? */
  loopt: boolean;
  /** Een annotatiekaart: het document erachter, als het geladen is. */
  doc?: AnnotatieDocument;
  /** Een annotatiekaart: het document bestaat niet meer. */
  verwijderd: boolean;
  acties: ThreadActies;
}

export const ThreadRij = memo(function ThreadRij({
  item, streamt, bezig, geblokkeerd, demo, samenhangAan, loopt, doc, verwijderd, acties,
}: Props) {
  return item.type === "user" ? (
    <div className="flex animate-rise flex-col items-end gap-1">
      {item.over && (
        <span className="max-w-[85%] truncate rounded-full bg-surface px-2.5 py-0.5 text-[0.7rem] text-muted">
          bij {item.over}
        </span>
      )}
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-bubbel bg-lint/10 px-4 py-2.5 text-sm text-ink">
        {item.tekst}
      </div>
      {item.nietVerstuurd && (
        <span className="max-w-[85%] text-right text-[0.7rem] text-muted">
          Niet verstuurd: er liep al een vraag in dit gesprek. Je vraag staat weer in het invoerveld.
        </span>
      )}
    </div>
  ) : item.type === "antwoord" ? (
    <div className="group flex animate-rise gap-3">
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">Lex</p>
        {item.denk && <DenkProces tekst={item.denk} actief={bezig && !item.tekst} />}
        <ToolSpoor events={item.tool_executions} />
        {item.tekst ? (
          streamt ? (
            <StreamendeTekst tekst={item.tekst} />
          ) : (
            // De afgekeurde citaten worden in de tekst zelf aangewezen; het blok eronder
            // blijft staan voor wat níét in de weergave terug te vinden was.
            <Markdown tekst={item.tekst} nietLetterlijk={item.grounding?.niet_letterlijk} bronnen={item.bronnen}
              onOpenSamenhang={samenhangAan && !demo ? acties.openSamenhang : undefined} />
          )
        ) : item.denk || item.overzicht ? null : (
          <Punten />
        )}
        {/* Het overzicht uit de graaf staat los van de tekst: dezelfde vraag, hetzelfde blok. */}
        {item.overzicht && <OverzichtBlok overzicht={item.overzicht} />}
        {item.bronnen && item.bronnen.length > 0 && <Bronnen bronnen={item.bronnen} />}
        {samenhangAan && !demo && (item.overzicht || !!item.bronnen?.length) && (() => {
          // Met een overzicht: de delen daarvan, in zijn eigen volgorde – los van hoe Lex formuleerde.
          // Anders: de artikelen die het antwoord noemt, in tekstvolgorde (`samenhangDoelen`).
          const keuze = item.overzicht ? overzichtDoelen(item.overzicht) : samenhangDoelen(item.tekst ?? "", item.bronnen ?? []);
          const tekst = item.overzicht ? overzichtKnopTekst(keuze, item.overzicht) : samenhangKnopTekst(keuze);
          const [doel, ...extra] = keuze.doelen;
          return doel && <button type="button"
            onClick={() => acties.openSamenhang(doel, extra)}
            className="focus-ring mt-3 flex items-center gap-2 rounded-lg border border-lint/20 bg-lint/[0.03] px-3 py-2 text-left text-xs font-medium text-lint transition-colors hover:bg-lint/10">
            <GraafIcoon />{tekst} in 3D
          </button>;
        })()}
        {item.tekst && item.grounding && <Brongetrouwheid grounding={item.grounding} />}
        {item.tekst && <KopieerKnop tekst={item.overzicht ? `${item.tekst}\n\n${overzichtAlsMarkdown(item.overzicht)}` : item.tekst} />}
      </div>
    </div>
  ) : item.type === "kandidaten" ? (
    <div className="group flex animate-rise gap-3">
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">Lex</p>
        {item.tekst && <Markdown tekst={item.tekst} />}
        {item.keuze ? (
          <KeuzeKaart
            kandidaten={item.kandidaten}
            keuze={item.keuze}
            uitgeschakeld={bezig || geblokkeerd || demo}
            onKies={(ks) => ks.length === 1
              ? acties.verstuur(kandidaatPrompt(ks[0]), doelVanKandidaat(ks[0]))
              : acties.verstuur(reeksPrompt(item.keuze?.ouder ?? "", ks), undefined, undefined, doelenVanKandidaten(ks))}
          />
        ) : (
          <KandidatenKeuze
            kandidaten={item.kandidaten}
            uitgeschakeld={bezig || geblokkeerd}
            onKies={(k) => acties.verstuur(kandidaatPrompt(k), doelVanKandidaat(k))}
          />
        )}
      </div>
    </div>
  ) : item.type === "reeks" ? (
    <div className="group flex animate-rise gap-3">
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">Lex</p>
        {item.tekst && <Markdown tekst={item.tekst} />}
        <ReeksBlok
          reeks={item.reeks}
          loopt={loopt}
          onStop={acties.stop}
          onOpen={(o) => {
            if (o.annotatie_doel) acties.openReeksLid(item.reeks.runId, o.annotatie_doel);
          }}
          spoor={(o, actief) => (
            <>
              {o.denk && <DenkProces tekst={o.denk} actief={actief} label="Zo is dit tot stand gekomen" />}
              <ToolSpoor events={o.tool_executions} />
            </>
          )}
        />
      </div>
    </div>
  ) : (
    // Een annotatie is ook een beurt van Lex: zijn naam, wat hij erover zegt (hoogstens vier zinnen,
    // door graph-qa uit de data opgebouwd), de kaart naar het artefact, en onderaan hoe het tot stand kwam.
    <div className="group flex animate-rise gap-3">
      <LexAvatar />
      <div className="min-w-0 flex-1 text-sm text-ink">
        <p className="mb-1 text-xs font-medium text-muted">Lex</p>
        {item.tekst && <div className="mb-3" data-testid="annotatie-samenvatting"><Markdown tekst={item.tekst} /></div>}
        <AnnotatieChip
          doc={doc}
          titel={item.titel}
          aantal={doc?.elementen.filter((e) => !e.verouderd).length}
          verwijderd={verwijderd}
          onOpen={() => acties.openArtefact(item.slug, item.annotatie_doel)}
        />
        {(() => {
          // De meting van de laatste ronde: wat er uitkwam, wat zonder zinsontleding ging en hoe lang
          // het duurde. Uit het document, want de meting reist mee op elk element (`geproduceerd_door`).
          const samenvatting = !verwijderd && doc ? beurtSamenvatting(laatsteRun(doc.elementen)?.instellingen?.meting) : "";
          return samenvatting && <p className="mt-1 px-1 text-xs text-muted" data-testid="beurtsamenvatting">Laatste ronde van Lex: {samenvatting}</p>;
        })()}
        {(() => {
          // Alleen op een gedeelde laag: een oud per-gebruiker-document kan niet worden
          // aangevuld, en een verwijderde annotatie al helemaal niet.
          const opnieuwDoel = item.annotatie_doel ? {
            bwbId: item.annotatie_doel.bwb_id || "", bron_iri: item.annotatie_doel.bron_iri,
          } : doc?.laag_sleutel && !verwijderd
            ? doelVoorOpnieuw(item.doel, doc) : undefined;
          if (!item.hergebruik && !opnieuwDoel) return null;
          return (
            <HergebruikMelding
              hergebruik={item.hergebruik}
              uitgeschakeld={bezig || geblokkeerd || demo}
              onOpnieuw={opnieuwDoel ? () => acties.verstuur(
                `Annoteer ${item.annotatie_doel?.label || (doc ? annotatieTitel(doc) : "deze bepaling")} opnieuw`, opnieuwDoel, "opnieuw",
              ) : undefined}
            />
          );
        })()}
        {item.denk && <div className="mt-3"><DenkProces tekst={item.denk} actief={false} label="Zo is dit tot stand gekomen" /></div>}
        <ToolSpoor events={item.tool_executions} />
      </div>
    </div>
  );
});

/** Compacte kaart in de chatstroom die naar het annotatie-artefact leidt (opent het slide-in paneel). */
function AnnotatieChip({
  doc,
  titel,
  aantal,
  verwijderd = false,
  onOpen,
}: {
  doc?: AnnotatieDocument;
  /** Het label uit het bericht zelf (`annotatie_titel`); de terugval als `doc` er niet (meer) is. */
  titel?: string;
  aantal?: number;
  verwijderd?: boolean;
  onOpen: () => void;
}) {
  const label = doc
    ? `${doc.werkgebied || doc.bwbId} – art. ${doc.artikel}${doc.lid ? ` lid ${doc.lid}` : ""}`
    : titel || "Annotatie";

  // Een verwijderde annotatie is geen kapotte knop maar een grafsteen: het gesprek blijft leesbaar
  // (daarom de bewaarde titel), maar er valt niets meer te openen – dus ook geen knop die dat
  // suggereert. Wat er nog wél te doen valt is doorlopen naar het overzicht.
  if (verwijderd) {
    return (
      <div className="flex w-full items-center gap-3 rounded-kaart border border-dashed border-line bg-surface px-4 py-3 text-left">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-line/40 text-faint" aria-hidden>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
          </svg>
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-muted line-through decoration-faint">
            {label}
          </span>
          <span className="block text-xs text-muted">Deze annotatie is verwijderd</span>
        </span>
        <Link
          href="/annotaties"
          className="focus-ring inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface-2 coarse:min-h-[44px]"
        >
          Alle annotaties
        </Link>
      </div>
    );
  }

  return (
    <button
      type="button"
      data-tour="chip"
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-kaart border border-line bg-surface px-4 py-3 text-left shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-lint/10 text-lint" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
          <path d="M14 2v6h6M9 13l2 2 4-4" />
        </svg>
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-ink">{label}</span>
        <span className="block text-xs text-muted">
          JAS-annotatie{typeof aantal === "number" ? ` · ${aantal} elementen` : ""} · review openen
        </span>
      </span>
      <span className="shrink-0 text-muted" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m9 18 6-6-6-6" />
        </svg>
      </span>
    </button>
  );
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
          <button
            type="button"
            disabled={uitgeschakeld}
            onClick={() => onKies(k)}
            className="flex w-full items-center gap-3 rounded-kaart border border-line bg-surface px-4 py-3 text-left shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-ink">{kandidaatLabel(k)}</span>
              {k.fragment && <span className="mt-0.5 block line-clamp-2 text-xs text-muted">{k.fragment}</span>}
            </span>
            <span className="shrink-0 text-muted" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function Punten() {
  return (
    <span className="inline-flex gap-1" aria-label="Bezig">
      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted" />
      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted" />
      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted" />
    </span>
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
  const [gekopieerd, setGekopieerd] = useState(false);
  const [mislukt, setMislukt] = useState(false);
  // De "Gekopieerd"-melding weer weghalen, en de timer opruimen als het bericht ondertussen
  // verdwijnt (bv. bij het wisselen van gesprek).
  useEffect(() => {
    if (!gekopieerd) return;
    const id = window.setTimeout(() => setGekopieerd(false), 1500);
    return () => window.clearTimeout(id);
  }, [gekopieerd]);

  async function kopieer() {
    try {
      await navigator.clipboard.writeText(tekst);
      setGekopieerd(true);
      setMislukt(false);
    } catch {
      // Het klembord is niet overal beschikbaar (onbeveiligde origin, geweigerde toestemming). Een
      // klik waar niets van gebeurt leest als een kapotte knop – zeg dus dat het niet lukte.
      setMislukt(true);
    }
  }
  return (
    <button
      type="button"
      onClick={kopieer}
      aria-label="Antwoord kopiëren"
      className="mt-2 inline-flex items-center gap-1.5 rounded px-1.5 py-1 text-xs text-muted transition-opacity hover:text-lint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100 coarse:opacity-100"
    >
      {mislukt ? (
        <span className="text-fout">Kopiëren lukte niet</span>
      ) : gekopieerd ? (
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

// Inklapbaar "Denkproces"-blok (Claude-stijl): streamt live terwijl de agent werkt (`actief`) en klapt
// automatisch dicht zodra het antwoord er is. De gebruiker kan het handmatig weer openen.
function DenkProces({
  tekst,
  actief,
  label = "Denkproces",
}: {
  tekst: string;
  actief: boolean;
  /** Bij een annotatie is dit geen "denkproces" maar het spoor van het samenspel tussen de agents. */
  label?: string;
}) {
  const [keuze, setKeuze] = useState<boolean | null>(null);
  const open = keuze ?? actief;

  return (
    <div data-tour="denkproces" className="mb-2">
      <button
        type="button"
        onClick={() => setKeuze(!open)}
        className="inline-flex items-center gap-1.5 rounded-full px-1 text-xs text-muted transition-colors hover:text-ink"
        aria-expanded={open}
      >
        {actief && <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent-soft" aria-hidden />}
        <span>{actief ? "Denkt na…" : label}</span>
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
  if (grounding.niveau === "gegrond") return null;
  const onbepaald = grounding.niveau === "onbepaald";
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
                <span key={item.sleutel}>{i > 0 && ", "}{link(item)}</span>
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
