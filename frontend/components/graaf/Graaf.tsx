"use client";

import dynamic from "next/dynamic";
import { Component, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Melding } from "@/components/ui/Melding";
import { Meter } from "@/components/ui/Meter";
import type { NodeDoel, NodeWeergave } from "@/lib/annotatieNode";
import { hoofdactie as bepaalHoofdactie, knopenInWeergave, paneelDoel, relatieGroepen, telling, tellingTekst } from "@/lib/graaf/bediening";
import { ankerVan, bouwModel, type KnoopData } from "@/lib/graaf/model";
import { focusVan, lagenVoor, weergaveContext } from "@/lib/graaf/weergave";
import { clusterOmschrijving, isDeelCluster } from "@/lib/samenhang";
import { GraafBeeld } from "./GraafBeeld";
import { GraafHint } from "./GraafHint";
import { GraafInspector } from "./GraafInspector";
import { GraafLagen } from "./GraafLagen";
import { GraafZoek } from "./GraafZoek";
import { ChevronOmlaag, Terug } from "@/components/ui/Icoon";
import { eigenKleur } from "@/lib/graaf/stijl";
import type { GraafKoppeling } from "./koppeling";
import type { Bereik, GraafOpties, GraafStand } from "./useGraafStand";
import { useKnoopDetail, useKnoopInfo, useMarkeringElement } from "./useKnoopDetail";

// sigma en WebGL laden pas als de graaf echt in beeld komt.
const Tekenaar = dynamic(() => import("./GraafTekenaar").then((m) => m.GraafTekenaar), { ssr: false });

const GEEN_WEBGL = "Deze browser kan de graaf niet tekenen. Zoeken, lagen en de details blijven beschikbaar.";
/** Midden in het canvas, in dezelfde kaartvorm als de laadbalk: de bediening erboven blijft vrij. */
function CanvasMelding({ children, rol = "status" }: { children: ReactNode; rol?: "status" | "alert" }) {
  return <div className="absolute inset-0 flex items-center justify-center p-6">
    <p role={rol} className="max-w-xs rounded-kaart border border-line bg-paper/95 p-4 text-sm text-muted shadow-kaart">{children}</p>
  </div>;
}
class TekenGrens extends Component<{ children: ReactNode }, { fout: boolean }> {
  state = { fout: false };
  static getDerivedStateFromError() { return { fout: true }; }
  render() { return this.state.fout ? <CanvasMelding>{GEEN_WEBGL}</CanvasMelding> : this.props.children; }
}

const LEEG = bouwModel([]);
const ZIJBALK = "wa_graaf_zijbalk";

/** De samenhang als graaf: bronstructuur, letterlijke verwijzingen en de actuele markeringen met hun
 *  JAS-klasse, getekend met sigma.js. De graaf vult het vlak; de bediening zweeft erover zoals bij een
 *  kaart: zoeken linksboven, lagen en legenda linksonder, beeld rechtsonder. Wat een knoop is, staat
 *  in de inspector, met één hoofdactie. Leeft als tab naast de tekst in het annotatiepaneel; de gekozen
 *  markering is in beide tabs dezelfde.
 *
 *  Het selectiemodel staat in `lib/graaf/weergave.ts`: lagen bepalen wat zichtbaar is, een keuze
 *  bepaalt alleen de nadruk. */
/** De benamingen rond de doelen van de graaf: de bereikschakelaar, de weg terug, de focus en de kop
 *  in de inspector. */
export interface GraafContext {
  /** "Dit antwoord" – bereikschakelaar en inspectorkop. */
  naam: string;
  /** "Antwoord" – de schakelaar op een smal scherm. */
  kort: string;
  /** "het antwoord" – "Terug naar …". */
  terug: string;
  /** "wat het antwoord noemt" – "Nadruk op …". */
  focus: string;
}
export const ANTWOORD: GraafContext = { naam: "Dit antwoord", kort: "Antwoord", terug: "het antwoord", focus: "wat het antwoord noemt" };

export function Graaf({ stand, zichtbaar, groot, actiefElementId, weergave, dekking, koppelingRef, onKiesElement, onOpenTekst, onWisselArtikel, onVraag,
  benaming = ANTWOORD, bijKnoop }: {
  stand: GraafStand; zichtbaar: boolean; groot: boolean;
  actiefElementId?: string;
  /** De weergave in het paneel: daaruit haalt de inspector tekst, markeringen en hun spoor zonder
   *  extra verzoek. */
  weergave?: NodeWeergave;
  /** Per bron-IRI de zinsdelen zonder detectortreffer, uit het paneel (alleen de geopende bepaling). */
  dekking?: Record<string, string[]>;
  /** Waar de graaf zijn handelingen neerzet voor het overzichtsblok (`koppeling.ts`), zolang hij in
   *  beeld is. */
  koppelingRef?: RefObject<GraafKoppeling | null>;
  onKiesElement: (elementId?: string) => void;
  /** *Bekijk in de tekst*. Bij een markering staat `anker` op de bronknoop waar zij op ligt. */
  onOpenTekst: (knoop: KnoopData, anker?: string) => void;
  /** Een knoop uit een ander geladen artikel: het paneel opent op dat artikel, met het bereik van nu
   *  en – als die actueel is – de kennisgraaf die al geladen is. Zonder deze haak is elke knoop "Toon
   *  in tekst". */
  onWisselArtikel?: (doel: NodeDoel, graaf: GraafOpties) => void;
  onVraag?: (knoop: KnoopData) => void;
  /** Hoe de graaf zijn doelen noemt: standaard het antwoord, op de werkgebiedpagina het werkgebied. */
  benaming?: GraafContext;
  /** Een extra handeling bij de gekozen knoop, naast de hoofdactie – bv. opnemen in een werkgebied. */
  bijKnoop?: (knoop: KnoopData & { id: string }) => ReactNode;
}) {
  const { bronnen, getekend, laadfase, fout, melding, selectie, setSelectie, wachtendeKeuze, setWachtendeKeuze,
    lagen, setLagen, markering, setMarkering, lagenOpen, setLagenOpen, aangeraakt, setAangeraakt, camera, bediening,
    laadErbij, laadtBij, bereik, setBereik, focusIds } = stand;
  const [geenWebgl, setGeenWebgl] = useState(false);
  const bedekking = useRef<HTMLDivElement>(null);
  // De zijbalk (inspector naast de vergrote graaf) in te klappen tot een strook; per kijker onthouden.
  // Opslag kan ontbreken (privévenster): dan gewoon uitgeklapt.
  const [zijbalkIn, setZijbalkIn] = useState(false);
  useEffect(() => {
    // Pas na de eerste render lezen: de server kent geen localStorage.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setZijbalkIn(localStorage.getItem(ZIJBALK) === "in"); } catch { /* geen opslag */ }
  }, []);
  function wisselZijbalk() {
    setZijbalkIn((v) => {
      try { localStorage.setItem(ZIJBALK, v ? "uit" : "in"); } catch { /* geen opslag: alleen deze sessie */ }
      return !v;
    });
  }
  const [aangewezen, setAangewezen] = useState<string | null>(null);
  // De markering die de graaf zelf koos (en aan het paneel doorgaf): een keuze uit de tekst is een
  // andere, en die moet in beeld komen.
  const eigenKeuze = useRef<string | undefined>(undefined);
  const model = getekend?.model ?? LEEG;
  const ongedekt = useMemo(() => new Set(Object.keys(dekking ?? {})), [dekking]);

  // De gekozen markering van het paneel gaat voor; anders de eigen keuze, zolang die nog bestaat (na
  // een annotatiewijziging kan een markering weg zijn).
  const actieveKnoop = actiefElementId ? `element:${actiefElementId}` : null;
  const gekozen = actieveKnoop && model.hasNode(actieveKnoop) ? actieveKnoop : selectie && model.hasNode(selectie) ? selectie : null;
  // Wat het antwoord noemt heeft de nadruk, in beide bereiken: dat is het begin, en waar een
  // achtergrondklik of Escape naar terugkeert. Beslaat de focus het hele model (een heel artikel), dan
  // is er niets te dimmen.
  const focus = useMemo(() => {
    if (!getekend) return null;
    const f = focusVan(model, focusIds);
    return f.bereik.size && f.bereik.size < model.order ? f : null;
  }, [getekend, model, focusIds]);
  const context = useMemo(() => weergaveContext(model, { lagen, markering, selectie: gekozen, focus, ongedekt, aangewezen }),
    [model, lagen, markering, gekozen, focus, ongedekt, aangewezen]);
  // Een nieuwe kaart in beeld: op de keuze als die er is, anders op wat het antwoord noemt. De tekenaar
  // doet er alleen iets mee als de sleutel (het bereik) verandert.
  const inpassen = useMemo(() => getekend && {
    sleutel: getekend.bereik,
    ids: gekozen && getekend.model.hasNode(gekozen) ? [gekozen] : focus ? [...focus.bereik] : [],
  }, [getekend, gekozen, focus]);
  const wisselBereik = (nieuw: Bereik) => { setAangeraakt(true); setBereik(nieuw); };
  const groepen = useMemo(() => (gekozen ? relatieGroepen(model, gekozen) : []), [model, gekozen]);
  const tel = useMemo(() => telling(model), [model]);
  const hoofd = bronnen?.[0];
  // De knopen die het paneel als tekst kan tonen: wat in zijn weergave staat (vaak één lid), niet het
  // hele artikel dat de graaf laadt. Al het andere opent in het paneel in plaats van naar een tekst te
  // springen die het niet bevat.
  const inPaneel = useMemo(() => (onWisselArtikel && weergave ? knopenInWeergave(model, weergave) : undefined),
    [model, weergave, onWisselArtikel]);
  const gekozenData = gekozen ? model.getNodeAttributes(gekozen) : undefined;
  const heeftBegrippen = useMemo(() => model.someNode((_, a) => a.soort === "begrip"), [model]);
  const actie = gekozen && gekozenData ? bepaalHoofdactie(gekozenData, gekozen, inPaneel) : null;
  // De tekst voor de inspector: van de gekozen bepaling, of bij een markering van haar anker. Alleen
  // bepalingen: de tekst van een heel hoofdstuk of een regeling past niet in een inspector.
  const tekstBron = !gekozen || !gekozenData ? null : gekozenData.soort === "markering" ? ankerVan(model, gekozen) ?? null
    : ["artikel", "lid", "onderdeel"].includes(gekozenData.soort) ? gekozen : null;
  const detail = useKnoopDetail(tekstBron, weergave, stand.detailCache, stand.detailVersie);
  // Wat de kennisgraaf over een bronknoop weet; een markering of klasse staat niet in de BWB-graaf,
  // een niet-geïmporteerde bepaling evenmin.
  const info = useKnoopInfo(gekozen && gekozenData && !["markering", "klasse", "extern", "begrip"].includes(gekozenData.soort) ? gekozen : null,
    stand.infoCache);
  const bekendeElementen = useMemo(() => [...(weergave?.elementen ?? []), ...(detail && typeof detail === "object" ? detail.elementen : [])],
    [weergave, detail]);
  // Zolang de tekst van het anker laadt, wachten: het element zit er meestal in.
  const element = useMarkeringElement(gekozenData?.soort === "markering" ? gekozenData.element_id || undefined : undefined, bekendeElementen,
    detail === "laden");

  /** Kiezen, of met `null` de keuze opheffen. Via zoeken of de inspector vliegt de camera mee; in de
   *  graaf zelf niet – daar staat de knoop al onder je muis. Een knoop die een laag verbergt, zet die
   *  laag aan (`lagenVoor`). */
  function kies(id: string | null, vlieg = true) {
    // Een id dat niet op de kaart staat (een element uit de tekst dat de graaf niet kent) kiest niets:
    // anders is er een onzichtbare keuze en doet de eerste Escape schijnbaar niets.
    if (id && !model.hasNode(id)) return;
    setAangeraakt(true);
    const elementId = id ? model.getNodeAttribute(id, "element_id") || undefined : undefined;
    eigenKeuze.current = elementId;
    setSelectie(id);
    onKiesElement(elementId);
    if (!id) return;
    const nodig = lagenVoor(model, id, lagen, markering);
    if (nodig.lagen !== lagen) setLagen(nodig.lagen);
    if (nodig.markering !== markering) setMarkering(nodig.markering);
    if (vlieg) requestAnimationFrame(() => bediening.current?.focus(id));
  }
  // Het overzichtsblok wijst aan en kiest via de werkplek (`koppeling.ts`). Een knoop die alleen in de
  // kennisgraaf staat, haalt die erbij: de keuze blijft staan en komt in beeld zodra hij er is.
  useEffect(() => {
    if (!koppelingRef || !zichtbaar) return;
    koppelingRef.current = {
      wijs: (id) => setAangewezen(id),
      kies: (id) => {
        setAangewezen(null);
        if (model.hasNode(id)) { kies(id); return true; }
        // Niet op deze kaart: de hele kennisgraaf erbij halen, en de keuze laten wachten tot hij er
        // is (hieronder). Staat die al open en kent hij de knoop ook niet, dan is het gewoon een link.
        if (bereik === "kennisgraaf") return false;
        setAangeraakt(true);
        setWachtendeKeuze(id);
        setBereik("kennisgraaf");
        return true;
      },
    };
    return () => { koppelingRef.current = null; };
  });

  // Een wachtende keuze wordt een gewone keuze zodra de kaart van dit bereik er is – met de lagen die
  // hij nodig heeft en de melding aan het paneel. Kent die kaart hem niet, dan vervalt hij.
  const opBereik = getekend?.bereik === bereik;
  useEffect(() => {
    if (!wachtendeKeuze || !opBereik) return;
    setWachtendeKeuze(null);
    kies(wachtendeKeuze);
    // `kies` leest de stand van deze render; alleen de komst van de kaart telt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wachtendeKeuze, opBereik, getekend]);

  // Een keuze die niet meer op de kaart staat (de markering is verworpen of verwijderd, of de keuze
  // kwam uit een bereik dat meer bevat) vervalt: anders is er een onzichtbare keuze en doet de eerste
  // Escape schijnbaar niets.
  useEffect(() => {
    if (selectie && opBereik && getekend && !getekend.model.hasNode(selectie)) setSelectie(null);
  }, [selectie, opBereik, getekend, setSelectie]);

  // Een markering die in de Tekst-tab gekozen is, staat in de graaf misschien buiten beeld: erheen
  // vliegen zodra de graaf zichtbaar is. Niet bij een keuze uit de graaf zelf.
  const getekendModel = getekend?.model;
  useEffect(() => {
    if (!zichtbaar || !actiefElementId || actiefElementId === eigenKeuze.current) return;
    const id = `element:${actiefElementId}`;
    if (!getekendModel?.hasNode(id)) return;
    eigenKeuze.current = actiefElementId;
    requestAnimationFrame(() => bediening.current?.focus(id));
  }, [zichtbaar, actiefElementId, getekendModel, bediening]);

  /** Terug naar het begin: geen keuze, en wat het antwoord noemt in beeld. */
  function naarAntwoord() {
    kies(null);
    requestAnimationFrame(() => bediening.current?.toon(focus ? [...focus.bereik] : []));
  }

  function doeHoofdactie() {
    if (!gekozen || !gekozenData) return;
    if (actie === "tekst") onOpenTekst(gekozenData, gekozenData.soort === "markering" ? ankerVan(model, gekozen) : undefined);
    else if (actie === "laden") void laadErbij(gekozen);
    else if (actie === "wissel") {
      // Een markering opent het paneel op haar anker (het lid), niet op het hele artikel.
      const anker = gekozenData.soort === "markering" ? ankerVan(model, gekozen) : undefined;
      const d = anker ? paneelDoel(anker, model.getNodeAttributes(anker)) : paneelDoel(gekozen, gekozenData);
      if (d) onWisselArtikel?.(d, { bereik, kennisgraaf: stand.kennisgraafActueel });
    }
  }

  if (!bronnen && fout) return <div className="p-5">
    <Melding type="fout" titel="Niet geladen">{fout.tekst}{" "}
      <button type="button" onClick={fout.herstel} className="underline">Opnieuw proberen</button></Melding>
  </div>;

  const titel = bereik === "kennisgraaf" ? "de hele kennisgraaf" : bronnen && bronnen.length > 1 ? clusterOmschrijving(bronnen)
    : (hoofd && model.hasNode(hoofd.artikel_iri) ? model.getNodeAttribute(hoofd.artikel_iri, "naam") : hoofd?.doel.label) ?? "de bepaling";
  const hoofdNaam = hoofd && model.hasNode(hoofd.artikel_iri) ? model.getNodeAttribute(hoofd.artikel_iri, "naam") : "het eerste artikel";
  return <div className="flex min-h-0 flex-1 flex-col" data-testid="samenhang-graaf" data-vergroot={groot}
    data-gereed={!!getekend && opBereik} data-bereik={bereik} data-zijbalk={groot && zijbalkIn ? "in" : "uit"} data-selectie={gekozen ?? ""} data-aangewezen={aangewezen ?? ""}>
    <div className="shrink-0 border-b border-line px-5 py-2.5">
      <h2 className="text-sm font-semibold text-lint">
        {bereik === "kennisgraaf" ? "De hele kennisgraaf" : `Samenhang van ${titel}`}
        {getekend && <span className="ml-2 text-xs font-normal text-muted" data-testid="graaf-telling">{tellingTekst(tel)}</span>}
      </h2>
      {focus && opBereik && <p className="mt-1 text-xs text-muted" data-testid="graaf-focus">Nadruk op {benaming.focus}{" "}
        ({focus.doelen.size === 1 ? "1 deel of bepaling" : `${focus.doelen.size} delen en bepalingen`}<span className="hidden sm:inline">, met wat eronder valt en waarnaar het verwijst</span>)<span className="hidden sm:inline">; de rest staat gedimd op de kaart</span>.</p>}
      {hoofd && !hoofd.verwijzingen_beschikbaar && <p className="mt-1 text-xs text-muted">Verwijzingen zijn nu niet beschikbaar; je ziet de bronstructuur en de annotaties.</p>}
      {bronnen?.some((d) => d.afgekapt) && <p className="mt-1 text-xs text-muted">Er zijn meer verwijzingen dan getoond; de eerste 200 per richting staan in beeld.</p>}
      {weergave && bronnen && bronnen.length > 1 && bereik === "antwoord" && <p className="mt-1 text-xs text-muted">De tekst en de annotatie in het paneel gaan over {hoofdNaam}; een knoop uit een ander artikel opent dat artikel in het paneel.{bronnen.some(isDeelCluster) ? " Een hoofdstuk of afdeling staat er met zijn artikelen; open een artikel voor leden, annotaties en verwijzingen." : ""}</p>}
      {stand.nietGeladen > 0 && <p className="mt-1 text-xs text-muted">{stand.nietGeladen === 1 ? "1 deel is" : `${stand.nietGeladen} delen zijn`} niet geladen.</p>}
      {melding && <p role="alert" className="mt-1 text-xs text-fout" data-testid="graaf-melding">{melding}</p>}
    </div>
    <div className={`flex min-h-0 flex-1 ${groot ? "flex-col md:flex-row" : "flex-col"}`}>
      <div className="relative min-h-[260px] min-w-0 flex-1 bg-[#f7f9fc]">
        {geenWebgl ? <CanvasMelding>{GEEN_WEBGL}</CanvasMelding>
          : getekend && <TekenGrens><Tekenaar model={getekend.model} posities={getekend.posities} context={context} zichtbaar={zichtbaar}
            inpassen={inpassen ?? undefined} cameraRef={camera} bedieningRef={bediening} bedekking={bedekking} onKies={(id) => kies(id, false)} onFout={() => setGeenWebgl(true)} /></TekenGrens>}
        {/* Bij een wissel van bereik blijft de vorige kaart zichtbaar onder de laadbalk. */}
        {!opBereik && !fout && <Laadbalk fase={laadfase} kennisgraaf={bereik === "kennisgraaf"} over={!!getekend} />}
        {/* Wat het tekenen in dit bereik tegenhoudt, midden op het canvas, met de weg terug. */}
        {fout && <CanvasMelding rol="alert"><span data-testid="graaf-fout">{fout.tekst}</span>{" "}
          <button type="button" onClick={fout.herstel} className="focus-ring rounded text-lint underline">Opnieuw proberen</button></CanvasMelding>}
        {/* Bediening zweeft over het canvas; de lege ruimte ertussen laat klikken door naar de graaf. */}
        {getekend && <div ref={bedekking} className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
          <div className="flex flex-col items-start gap-2">
          <div className="flex w-full items-start justify-between gap-2">
            <GraafZoek model={model} verborgen={context.verborgen} gekozen={gekozen} onKies={(id) => kies(id)} />
            <div role="group" aria-label="Wat de graaf toont" className="pointer-events-auto flex shrink-0 rounded-full border border-line bg-paper/95 p-0.5 shadow-kaart">
              {/* Mobiel kort, zodat het zoekveld ernaast leesbaar blijft; de volle naam staat in het label. */}
              {(["antwoord", "kennisgraaf"] as const).map((b) => <button key={b} type="button" aria-pressed={bereik === b}
                aria-label={b === "antwoord" ? benaming.naam : "Hele kennisgraaf"}
                onClick={() => wisselBereik(b)}
                className={`focus-ring min-h-8 rounded-full px-3 text-xs coarse:min-h-11 ${bereik === b ? "bg-lint text-paper" : "text-muted hover:text-lint"}`}>
                <span className="sm:hidden">{b === "antwoord" ? benaming.kort : "Alles"}</span>
                <span className="hidden sm:inline">{b === "antwoord" ? benaming.naam : "Hele kennisgraaf"}</span></button>)}
            </div>
          </div>
          {/* Zolang er een keuze is: de weg terug naar het begin, onder het zoekveld. */}
          {gekozen && focus && <button type="button" onClick={naarAntwoord} data-testid="graaf-terug"
            className="focus-ring pointer-events-auto flex min-h-8 shrink-0 items-center gap-1.5 rounded-full border border-line bg-paper/95 px-3 text-xs text-lint shadow-kaart hover:bg-surface coarse:min-h-11">
            <Terug />Terug naar {benaming.terug}</button>}
          </div>
          <div className="flex items-end justify-between gap-2">
            <GraafLagen lagen={lagen} open={lagenOpen} onOpen={setLagenOpen}
              onWissel={(l) => setLagen((oud) => ({ ...oud, [l]: !oud[l] }))}
              dekking={ongedekt.size > 0} begrippen={heeftBegrippen} markering={{ waarde: markering, onKies: setMarkering }} />
            <GraafHint klaar={aangeraakt} terug={benaming.terug} />
            <GraafBeeld onPasIn={() => bediening.current?.pasIn()} onZoom={(f) => bediening.current?.zoom(f)}
              onNaarAntwoord={focus ? naarAntwoord : undefined} terug={benaming.terug} />
          </div>
        </div>}
      </div>
      {/* De inspector heeft één scrollvak (de details erin); deze schil geeft alleen de hoogte door. Een
          tweede scrollvak eromheen slikte het muiswiel: met `overscroll-behavior: contain` op elke
          scroller gaf het binnenste, dat niets te scrollen had, het wiel niet door. */}
      <div data-testid="graaf-zijbalk" className={`relative flex shrink-0 flex-col border-t border-line bg-paper ${!groot ? "max-h-[45%]"
        : `max-h-[40dvh] md:max-h-none md:border-l md:border-t-0 ${zijbalkIn ? "md:w-10" : "md:w-[22rem] lg:w-[26rem] xl:w-[28rem]"}`}`}>
        {/* Breed: de zijbalk is in te klappen tot een strook, met een greep op zijn linkerrand. */}
        {groot && <button type="button" onClick={wisselZijbalk} aria-expanded={!zijbalkIn}
          aria-label={zijbalkIn ? "Zijbalk uitklappen" : "Zijbalk inklappen"} title={zijbalkIn ? "Zijbalk uitklappen" : "Zijbalk inklappen"}
          className="focus-ring absolute -left-3 top-1/2 z-10 hidden h-12 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-paper text-muted shadow-kaart hover:text-lint md:flex">
          <ChevronOmlaag className={zijbalkIn ? "rotate-90" : "-rotate-90"} /></button>}
        {groot && zijbalkIn && gekozenData && <div className="hidden flex-col items-center pt-4 md:flex">
          <span className="h-3 w-3 rounded-full border border-black/10" style={{ background: eigenKleur(gekozenData) }}
            title={`Gekozen: ${gekozenData.naam}`} data-testid="graaf-zijbalk-keuze" />
        </div>}
        <div className={`flex min-h-0 flex-1 flex-col ${groot && zijbalkIn ? "md:hidden" : ""}`}>
        <GraafInspector key={gekozen ?? ""} model={model} id={gekozen} smal={!groot}
          detail={detail} info={info} element={element} doelen={focus ? [...focus.doelen] : hoofd ? [hoofd.doel.bron_iri] : []}
          ongedekt={lagen.dekking && gekozen ? dekking?.[gekozen] : undefined}
          hoofdactie={actie} laadt={!!gekozen && laadtBij === gekozen}
          groepen={groepen} telling={tel}
          onCentreer={() => gekozen && bediening.current?.focus(gekozen)}
          onSluit={() => kies(null)}
          onHoofdactie={doeHoofdactie}
          onVraag={onVraag && gekozenData && gekozenData.soort !== "klasse" && gekozenData.soort !== "begrip" ? () => onVraag(gekozenData) : undefined}
          doelenKop={benaming.naam} extra={bijKnoop && gekozen && gekozenData ? bijKnoop({ ...gekozenData, id: gekozen }) : undefined}
          onKies={(id) => kies(id)} />
        </div>
      </div>
    </div>
  </div>;
}

/** Zolang er niets te tekenen is: wat er gebeurt en hoe ver het is. Verschijnt pas na een kort moment,
 *  zodat een layout uit de cache geen flits van een balk geeft. */
function Laadbalk({ fase, kennisgraaf, over }: { fase: GraafStand["laadfase"]; kennisgraaf: boolean; over: boolean }) {
  const procent = fase.fase === "layout" ? Math.round(fase.fractie * 100) : null;
  const tekst = fase.fase === "ophalen" ? (kennisgraaf ? "Hele kennisgraaf ophalen…" : "Graaf ophalen…")
    : fase.fase === "layout" ? `Layout berekenen – ${procent} %` : "Tekenen…";
  return <div className={`absolute inset-0 flex items-center justify-center p-6 ${over ? "bg-[#f7f9fc]/70" : ""}`} data-testid="graaf-laadbalk">
    <div className="w-full max-w-xs animate-verschijn space-y-2 rounded-kaart border border-line bg-paper/95 p-4 shadow-kaart">
      <p className="text-xs text-muted" aria-hidden="true">{tekst}</p>
      <Meter percentage={procent} label={tekst} />
    </div>
  </div>;
}
