"use client";

import dynamic from "next/dynamic";
import { Component, useEffect, useMemo, useState, type ReactNode, type RefObject } from "react";
import { Melding } from "@/components/ui/Melding";
import { Meter } from "@/components/ui/Meter";
import { haalElement, type NodeDoel, type NodeElement } from "@/lib/annotatieNode";
import { hoofdactie as bepaalHoofdactie, paneelDoel, relatieGroepen, telling, tellingTekst } from "@/lib/graaf/bediening";
import { bouwModel, type KnoopData } from "@/lib/graaf/model";
import { focusVan, lagenVoor, weergaveContext } from "@/lib/graaf/weergave";
import { clusterOmschrijving, isDeelCluster } from "@/lib/samenhang";
import { GraafBeeld } from "./GraafBeeld";
import { GraafHint } from "./GraafHint";
import { GraafInspector } from "./GraafInspector";
import { GraafLagen } from "./GraafLagen";
import { GraafZoek } from "./GraafZoek";
import type { GraafKoppeling } from "./koppeling";
import type { Bereik, GraafStand } from "./useGraafStand";

// sigma en WebGL laden pas als de graaf echt in beeld komt.
const Tekenaar = dynamic(() => import("./GraafTekenaar").then((m) => m.GraafTekenaar), { ssr: false });

const GEEN_WEBGL = "Deze browser kan de graaf niet tekenen. Zoeken, lagen en de details blijven beschikbaar.";
/** Midden in het canvas, in dezelfde kaartvorm als de laadbalk: de bediening erboven blijft vrij. */
function CanvasMelding({ children }: { children: ReactNode }) {
  return <div className="absolute inset-0 flex items-center justify-center p-6">
    <p role="status" className="max-w-xs rounded-kaart border border-line bg-paper/95 p-4 text-sm text-muted shadow-kaart">{children}</p>
  </div>;
}
class TekenGrens extends Component<{ children: ReactNode }, { fout: boolean }> {
  state = { fout: false };
  static getDerivedStateFromError() { return { fout: true }; }
  render() { return this.state.fout ? <CanvasMelding>{GEEN_WEBGL}</CanvasMelding> : this.props.children; }
}

const LEEG = bouwModel([]);

/** De samenhang als graaf: bronstructuur, letterlijke verwijzingen en de actuele markeringen met hun
 *  JAS-klasse, getekend met sigma.js. De graaf vult het vlak; de bediening zweeft erover zoals bij een
 *  kaart: zoeken linksboven, lagen en legenda linksonder, beeld rechtsonder. Wat een knoop is, staat
 *  in de inspector, met één hoofdactie. Leeft als tab naast de tekst in het annotatiepaneel; de gekozen
 *  markering is in beide tabs dezelfde.
 *
 *  Het selectiemodel staat in `lib/graaf/weergave.ts`: lagen bepalen wat zichtbaar is, een keuze
 *  bepaalt alleen de nadruk. */
export function Graaf({ stand, zichtbaar, groot, actiefElementId, elementen, dekking, koppelingRef, onKiesElement, onOpenTekst, onWisselArtikel, onVraag }: {
  stand: GraafStand; zichtbaar: boolean; groot: boolean;
  actiefElementId?: string;
  /** De elementen van de weergave in het paneel: daaruit haalt de inspector het spoor van een markering. */
  elementen?: NodeElement[];
  /** Per bron-IRI de zinsdelen zonder detectortreffer, uit het paneel (alleen de geopende bepaling). */
  dekking?: Record<string, string[]>;
  /** Waar de graaf zijn handelingen neerzet voor het overzichtsblok (`koppeling.ts`), zolang hij in
   *  beeld is. */
  koppelingRef?: RefObject<GraafKoppeling | null>;
  onKiesElement: (elementId?: string) => void;
  onOpenTekst: (knoop: KnoopData) => void;
  /** Een knoop uit een ander geladen artikel: het paneel opent op dat artikel. Zonder deze haak is
   *  elke knoop "Toon in tekst". */
  onWisselArtikel?: (doel: NodeDoel) => void;
  onVraag?: (knoop: KnoopData) => void;
}) {
  const { bronnen, getekend, laadfase, fout, laad, selectie, setSelectie, lagen, setLagen, markering, setMarkering,
    lagenOpen, setLagenOpen, aangeraakt, setAangeraakt, camera, bediening, laadErbij, laadtBij,
    bereik, setBereik, focusIds, laadKennisgraaf } = stand;
  const [geenWebgl, setGeenWebgl] = useState(false);
  const [aangewezen, setAangewezen] = useState<string | null>(null);
  const model = getekend?.model ?? LEEG;
  const ongedekt = useMemo(() => new Set(Object.keys(dekking ?? {})), [dekking]);

  // De gekozen markering van het paneel gaat voor; anders de eigen keuze, zolang die nog bestaat (na
  // een annotatiewijziging kan een markering weg zijn).
  const actieveKnoop = actiefElementId ? `element:${actiefElementId}` : null;
  const gekozen = actieveKnoop && model.hasNode(actieveKnoop) ? actieveKnoop : selectie && model.hasNode(selectie) ? selectie : null;
  // In de hele kennisgraaf krijgt wat het antwoord noemt de nadruk; in "dit antwoord" ís alles dat al.
  const focus = useMemo(() => (getekend?.bereik === "kennisgraaf" ? focusVan(model, focusIds) : null), [getekend, model, focusIds]);
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
  // De knopen die het paneel als tekst kan tonen: die van het eigen artikel, niet de bijgeladen.
  const inPaneel = useMemo(() => (onWisselArtikel && hoofd ? new Set(hoofd.knopen.filter((k) => !k.rand).map((k) => k.id)) : undefined),
    [hoofd, onWisselArtikel]);
  const gekozenData = gekozen ? model.getNodeAttributes(gekozen) : undefined;
  const actie = gekozen && gekozenData ? bepaalHoofdactie(gekozenData, gekozen, inPaneel) : null;

  /** Kiezen, of met `null` de keuze opheffen. Via zoeken of de inspector vliegt de camera mee; in de
   *  graaf zelf niet – daar staat de knoop al onder je muis. Een knoop die een laag verbergt, zet die
   *  laag aan (`lagenVoor`). */
  function kies(id: string | null, vlieg = true) {
    setAangeraakt(true);
    setSelectie(id);
    onKiesElement(id && model.hasNode(id) ? model.getNodeAttribute(id, "element_id") || undefined : undefined);
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
        if (model.hasNode(id)) kies(id);
        else { setSelectie(id); setBereik("kennisgraaf"); }
        return true;
      },
    };
    return () => { koppelingRef.current = null; };
  });

  function doeHoofdactie() {
    if (!gekozen || !gekozenData) return;
    if (actie === "tekst") onOpenTekst(gekozenData);
    else if (actie === "laden") void laadErbij(gekozen);
    else if (actie === "wissel") { const d = paneelDoel(gekozen, gekozenData); if (d) onWisselArtikel?.(d); }
  }

  const opBereik = getekend?.bereik === bereik;
  if (!bronnen && fout) return <div className="p-5">
    <Melding type="fout" titel="Niet geladen">{fout}{" "}
      <button type="button" onClick={() => void laad()} className="underline">Opnieuw proberen</button></Melding>
  </div>;

  const titel = bereik === "kennisgraaf" ? "de hele kennisgraaf" : bronnen && bronnen.length > 1 ? clusterOmschrijving(bronnen)
    : (hoofd && model.hasNode(hoofd.artikel_iri) ? model.getNodeAttribute(hoofd.artikel_iri, "naam") : hoofd?.doel.label) ?? "de bepaling";
  const hoofdNaam = hoofd && model.hasNode(hoofd.artikel_iri) ? model.getNodeAttribute(hoofd.artikel_iri, "naam") : "het eerste artikel";
  return <div className="flex min-h-0 flex-1 flex-col" data-testid="samenhang-graaf" data-vergroot={groot}
    data-gereed={!!getekend && opBereik} data-bereik={bereik} data-selectie={gekozen ?? ""} data-aangewezen={aangewezen ?? ""}>
    <div className="shrink-0 border-b border-line px-5 py-2.5">
      <h2 className="text-sm font-semibold text-lint">
        {bereik === "kennisgraaf" ? "De hele kennisgraaf" : `Samenhang van ${titel}`}
        {getekend && <span className="ml-2 text-xs font-normal text-muted" data-testid="graaf-telling">{tellingTekst(tel)}</span>}
      </h2>
      {focus && opBereik && <p className="mt-1 text-xs text-muted" data-testid="graaf-focus">Nadruk op wat het antwoord noemt
        ({focus.doelen.size === 1 ? "1 deel of bepaling" : `${focus.doelen.size} delen en bepalingen`}, met wat eronder valt); de rest staat gedimd op de kaart.</p>}
      {hoofd && !hoofd.verwijzingen_beschikbaar && <p className="mt-1 text-xs text-muted">Verwijzingen zijn nu niet beschikbaar; je ziet de bronstructuur en de annotaties.</p>}
      {bronnen?.some((d) => d.afgekapt) && <p className="mt-1 text-xs text-muted">Er zijn meer verwijzingen dan getoond; de eerste 200 per richting staan in beeld.</p>}
      {bronnen && bronnen.length > 1 && bereik === "antwoord" && <p className="mt-1 text-xs text-muted">De tekst en de annotatie in het paneel gaan over {hoofdNaam}; een knoop uit een ander artikel opent dat artikel in het paneel.{bronnen.some(isDeelCluster) ? " Een hoofdstuk of afdeling staat er met zijn artikelen; open een artikel voor leden, annotaties en verwijzingen." : ""}</p>}
      {stand.nietGeladen > 0 && <p className="mt-1 text-xs text-muted">{stand.nietGeladen === 1 ? "1 deel is" : `${stand.nietGeladen} delen zijn`} niet geladen.</p>}
      {fout && bronnen && <p role="alert" className="mt-1 text-xs text-fout">{fout}{" "}
        {bereik === "kennisgraaf" && !stand.kennisgraaf && <button type="button" onClick={() => void laadKennisgraaf()} className="underline">Opnieuw proberen</button>}</p>}
    </div>
    <div className={`flex min-h-0 flex-1 ${groot ? "flex-col md:flex-row" : "flex-col"}`}>
      <div className="relative min-h-[260px] min-w-0 flex-1 bg-[#f7f9fc]">
        {geenWebgl ? <CanvasMelding>{GEEN_WEBGL}</CanvasMelding>
          : getekend && <TekenGrens><Tekenaar model={getekend.model} posities={getekend.posities} context={context} zichtbaar={zichtbaar}
            inpassen={inpassen ?? undefined} cameraRef={camera} bedieningRef={bediening} onKies={(id) => kies(id, false)} onFout={() => setGeenWebgl(true)} /></TekenGrens>}
        {/* Bij een wissel van bereik blijft de vorige kaart zichtbaar onder de laadbalk. */}
        {!opBereik && !fout && <Laadbalk fase={laadfase} kennisgraaf={bereik === "kennisgraaf"} over={!!getekend} />}
        {/* Bediening zweeft over het canvas; de lege ruimte ertussen laat klikken door naar de graaf. */}
        {getekend && <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
          <div className="flex items-start justify-between gap-2">
            <GraafZoek model={model} verborgen={context.verborgen} gekozen={gekozen} onKies={(id) => kies(id)} />
            <div role="group" aria-label="Wat de graaf toont" className="pointer-events-auto flex shrink-0 rounded-full border border-line bg-paper/95 p-0.5 shadow-kaart">
              {(["antwoord", "kennisgraaf"] as const).map((b) => <button key={b} type="button" aria-pressed={bereik === b}
                onClick={() => wisselBereik(b)}
                className={`focus-ring min-h-8 rounded-full px-3 text-xs coarse:min-h-11 ${bereik === b ? "bg-lint text-paper" : "text-muted hover:text-lint"}`}>
                {b === "antwoord" ? "Dit antwoord" : "Hele kennisgraaf"}</button>)}
            </div>
          </div>
          <div className="flex items-end justify-between gap-2">
            <GraafLagen lagen={lagen} open={lagenOpen} onOpen={setLagenOpen}
              onWissel={(l) => setLagen((oud) => ({ ...oud, [l]: !oud[l] }))}
              dekking={ongedekt.size > 0} markering={{ waarde: markering, onKies: setMarkering }} />
            <GraafHint klaar={aangeraakt} />
            <GraafBeeld onPasIn={() => bediening.current?.pasIn()} onZoom={(f) => bediening.current?.zoom(f)} />
          </div>
        </div>}
      </div>
      <div className={`shrink-0 border-t border-line bg-paper ${groot ? "max-h-[40dvh] overflow-y-auto md:max-h-none md:w-80 md:border-l md:border-t-0" : "flex max-h-[45%] flex-col"}`}>
        <GraafInspector model={model} id={gekozen} smal={!groot}
          element={gekozenData?.element_id ? elementen?.find((e) => e.id === gekozenData.element_id) : undefined}
          laadElement={gekozenData?.element_id ? () => haalElement(gekozenData.element_id) : undefined}
          ongedekt={lagen.dekking && gekozen ? dekking?.[gekozen] : undefined}
          hoofdactie={actie} laadt={!!gekozen && laadtBij === gekozen}
          groepen={groepen} telling={tel}
          onCentreer={() => gekozen && bediening.current?.focus(gekozen)}
          onSluit={() => kies(null)}
          onHoofdactie={doeHoofdactie}
          onVraag={onVraag && gekozenData && gekozenData.soort !== "klasse" ? () => onVraag(gekozenData) : undefined}
          onKies={(id) => kies(id)} />
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
