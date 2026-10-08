"use client";

import dynamic from "next/dynamic";
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { foutTekst } from "@/lib/api";
import { haalElement, type NodeDoel, type NodeElement } from "@/lib/annotatieNode";
import {
  bouwGraaf, haalSamenhang, hoofdactie as bepaalHoofdactie, relatieGroepen, samenvatting, uitklapbaar, zichtbareGraaf,
  type GraafData, type GraafKnoop, type MarkeringFilter, type RelatieGroep, type Samenhang,
  clusterOmschrijving, isDeelCluster,
} from "@/lib/samenhang";
import type { CameraStand, GraafCameraBediening } from "./GraafCanvas";
import { GraafBeeld } from "./GraafBeeld";
import { GraafHint } from "./GraafHint";
import { GraafInspector } from "./GraafInspector";
import { GraafLagen } from "./GraafLagen";
import { GraafZoek } from "./GraafZoek";

// three.js en de renderer laden pas als de graaf echt in beeld komt.
const Canvas = dynamic(() => import("./GraafCanvas").then((m) => m.GraafCanvas), {
  ssr: false, loading: () => <div className="flex h-full items-center justify-center text-sm text-muted" role="status">3D-graaf laden…</div>,
});
class CanvasGrens extends Component<{ children: ReactNode }, { fout: boolean }> {
  state = { fout: false };
  static getDerivedStateFromError() { return { fout: true }; }
  render() {
    return this.state.fout ? <p role="status" className="p-6 text-sm text-muted">3D kon niet worden geladen. Zoeken, lagen en de details blijven beschikbaar. Herlaad de pagina om opnieuw te proberen.</p> : this.props.children;
  }
}

/** De toestand van de graaf. Leeft in het paneel (búiten de `Dialog`): vergroten wisselt de
 *  dialoogvorm en remount daarmee de inhoud, en zonder dit waren bijgeladen artikelen, uitklappingen,
 *  selectie en camera dan weg. `actief` laadt pas als de tab voor het eerst opengaat. */
export function useSamenhangStand(doel: NodeDoel, actief: boolean, extra: NodeDoel[] = []) {
  // Een nieuwe array met dezelfde doelen mag niet opnieuw laden: vergelijk op de bron-IRI's.
  const extraSleutel = extra.map((d) => d.bron_iri).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const extraDoelen = useMemo(() => extra, [extraSleutel]);
  const [nietGeladen, setNietGeladen] = useState(0);
  // Delen en graaf samen: elke nieuwe stand wordt gerekend met de posities van de vorige, zodat een
  // annotatiewijziging of bijgeladen artikel de bestaande kaart niet verschuift.
  const [geladen, setGeladen] = useState<{ delen: Samenhang[]; graaf: GraafData }>();
  const [fout, setFout] = useState("");
  const [laadtUit, setLaadtUit] = useState("");
  const [selectie, setSelectie] = useState(doel.bron_iri);
  const [uitgebreid, setUitgebreid] = useState<string[]>([doel.bron_iri]);
  const [filters, setFilters] = useState<Record<RelatieGroep, boolean>>({ structuur: true, verwijzingen: true, annotaties: true });
  // De stand van vóór "Alles tonen", zodat "Minder tonen" precies daarheen terugkeert.
  const [voorAlles, setVoorAlles] = useState<{ uitgebreid: string[]; filters: Record<RelatieGroep, boolean> } | null>(null);
  // De gekozen knoop die je zelf inklapte, terwijl zijn selectie hem anders zou uitklappen.
  const [ingeklapt, setIngeklapt] = useState("");
  const [lagenOpen, setLagenOpen] = useState(false);
  // De dekkingslaag verbergt niets, hij markeert alleen; daarom los van `filters` en van Omgeving/Alles.
  const [toonDekking, setToonDekking] = useState(true);
  const [markeringFilter, setMarkeringFilter] = useState<MarkeringFilter>("alle");
  const [aangeraakt, setAangeraakt] = useState(false);
  const camera = useRef<CameraStand | null>(null);
  const zetDelen = useCallback((maak: (oud: Samenhang[]) => Samenhang[]) => setGeladen((oud) => {
    const delen = maak(oud?.delen ?? []);
    return { delen, graaf: bouwGraaf(delen, oud?.graaf) };
  }), []);
  const laad = useCallback(async () => {
    setFout("");
    try {
      // Het doel van het paneel eerst; de andere artikelen uit het antwoord (`extra`) tegelijk, elk
      // als eigen cluster. Eén artikel dat niet laadt is een melding, geen fout voor het geheel.
      const [eerste, ...rest] = await Promise.allSettled([doel, ...extraDoelen].map((d) => haalSamenhang(d)));
      if (eerste.status === "rejected") throw eerste.reason;
      const delen = [eerste.value];
      for (const r of rest) {
        if (r.status === "fulfilled" && !delen.some((d) => d.artikel_iri === r.value.artikel_iri)) delen.push(r.value);
      }
      setNietGeladen(rest.filter((r) => r.status === "rejected").length);
      // Een lid opent het hele artikel; alleen het gevraagde lid is uitgeklapt. Het artikel zelf
      // uitklappen toont alle inkomende verwijzingen tegelijk – dat is een keuze, geen begin. De
      // extra artikelen staan uitgeklapt, zoals een bijgeladen artikel.
      zetDelen(() => delen);
      if (delen.length > 1) setUitgebreid([doel.bron_iri, ...delen.slice(1).map((d) => d.artikel_iri)]);
    } catch (e) { setFout(foutTekst(e, "De samenhang is niet geladen.")); }
  }, [doel, extraDoelen, zetDelen]);
  useEffect(() => {
    // Externe request initialiseren; dezelfde actie dient ook de retryknop.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (actief) void laad();
  }, [laad, actief]);

  /** Na een annotatiewijziging: elk geladen deel opnieuw ophalen. Uitklappingen, filters, selectie
   *  en camera blijven; een weggehaalde geselecteerde markering valt terug op het geopende doel. */
  const ververs = useCallback(async () => {
    const delen = geladen?.delen;
    if (!delen?.length) return;
    try {
      const nieuw = await Promise.all(delen.map((d) => haalSamenhang({ bron_iri: d.doel.bron_iri })));
      // Per artikel vervangen, niet de hele lijst: een artikel dat intussen werd geopend blijft staan.
      zetDelen((oud) => oud.map((d) => nieuw.find((n) => n.artikel_iri === d.artikel_iri) ?? d));
      const ids = new Set(nieuw.flatMap((d) => d.knopen.map((k) => k.id)));
      setSelectie((huidig) => (huidig && !ids.has(huidig) ? doel.bron_iri : huidig));
    } catch (e) { setFout(foutTekst(e, "De graaf is niet bijgewerkt; herlaad om de laatste stand te zien.")); }
  }, [geladen, zetDelen, doel.bron_iri]);

  /** Weergave *Omgeving* ⇄ *Alles*. Terug naar Omgeving herstelt precies de stand van daarvoor. */
  const zetWeergave = useCallback((weergave: "omgeving" | "alles", allesIds: string[]) => {
    if (weergave === "omgeving") {
      if (!voorAlles) return;
      setUitgebreid(voorAlles.uitgebreid);
      setFilters(voorAlles.filters);
      setVoorAlles(null);
      return;
    }
    if (voorAlles) return;
    setVoorAlles({ uitgebreid, filters });
    setUitgebreid(allesIds);
    setFilters({ structuur: true, verwijzingen: true, annotaties: true });
  }, [voorAlles, uitgebreid, filters]);
  /** Een verborgen knoop zichtbaar maken (gekozen via zoeken of de inspector). Ook in de bewaarde
   *  omgeving, zodat terugschakelen hem niet meteen weer verbergt. */
  const toon = useCallback((id: string) => {
    setUitgebreid((ids) => ids.includes(id) ? ids : [...ids, id]);
    setVoorAlles((v) => v && !v.uitgebreid.includes(id) ? { ...v, uitgebreid: [...v.uitgebreid, id] } : v);
  }, []);

  return { delen: geladen?.delen, alles: geladen?.graaf, nietGeladen, zetDelen, ververs, fout, setFout, laadtUit, setLaadtUit,
    selectie, setSelectie, uitgebreid, setUitgebreid, filters, setFilters, voorAlles, setVoorAlles, zetWeergave, toon,
    ingeklapt, setIngeklapt, lagenOpen, setLagenOpen, aangeraakt, setAangeraakt, camera, laad, toonDekking, setToonDekking, markeringFilter, setMarkeringFilter };
}
export type SamenhangStand = ReturnType<typeof useSamenhangStand>;

/** De samenhang van de geopende bepaling als 3D-graaf: bronstructuur, letterlijke verwijzingen
 *  (één stap) en de actuele markeringen met hun JAS-klasse. De graaf vult het vlak; bediening zweeft
 *  erover zoals bij een kaart: zoeken en weergave boven, lagen en beeld onder. Wat een knoop is,
 *  staat in de inspector, met één hoofdactie. Leeft als tab naast de tekst in het annotatiepaneel;
 *  de gekozen markering is in beide tabs dezelfde. */
export function SamenhangGraaf({ stand, zichtbaar, groot, actiefElementId, elementen, dekking, onKiesElement, onOpenTekst, onWisselArtikel, onVraag }: {
  stand: SamenhangStand; zichtbaar: boolean; groot: boolean;
  actiefElementId?: string;
  /** De elementen van de weergave in het paneel: daaruit haalt de inspector het spoor van een markering. */
  elementen?: NodeElement[];
  /** Per bron-IRI de zinsdelen zonder detectortreffer, uit het paneel (alleen de geopende bepaling). */
  dekking?: Record<string, string[]>;
  onKiesElement: (elementId?: string) => void;
  onOpenTekst: (knoop: GraafKnoop) => void;
  /** Een knoop uit een ander geladen artikel: het paneel opent op dat artikel. Zonder deze haak is
   *  elke knoop "Toon in tekst", zoals voorheen. */
  onWisselArtikel?: (knoop: GraafKnoop) => void;
  onVraag?: (knoop: GraafKnoop) => void;
}) {
  const { delen, zetDelen, fout, setFout, laadtUit, setLaadtUit, selectie, setSelectie, uitgebreid, setUitgebreid,
    filters, setFilters, voorAlles, zetWeergave, toon, ingeklapt, setIngeklapt, lagenOpen, setLagenOpen, aangeraakt, setAangeraakt,
    camera, laad, toonDekking, setToonDekking, markeringFilter, setMarkeringFilter } = stand;
  const aandacht = useMemo(() => new Set(toonDekking ? Object.keys(dekking ?? {}) : []), [dekking, toonDekking]);
  const heeftDekking = Object.keys(dekking ?? {}).length > 0;
  const bediening = useRef<GraafCameraBediening | null>(null);

  const alles = useMemo(() => stand.alles ?? { nodes: [], links: [] }, [stand.alles]);
  const actieveKnoop = actiefElementId ? `element:${actiefElementId}` : undefined;
  const gekozenId = actieveKnoop && alles.nodes.some((n) => n.id === actieveKnoop) ? actieveKnoop : selectie;
  // De omgeving is wat je zelf uitklapte. Daarbovenop klapt de gekozen knoop uit zolang hij gekozen
  // is, als hij in de omgeving verborgen was (via zoeken of een tijdelijk getoonde buur). Kies je
  // iets anders, dan verdwijnt dat weer – anders bleef elke ooit gekozen knoop voorgoed in beeld.
  const omgeving = useMemo(() => zichtbareGraaf(alles, uitgebreid, filters, markeringFilter), [alles, uitgebreid, filters, markeringFilter]);
  // De inspector kijkt naar de héle graaf: ook een verborgen buur staat erin en is te kiezen.
  const geselecteerd = alles.nodes.find((n) => n.id === gekozenId);
  const tijdelijk = useMemo(() => {
    const k = alles.nodes.find((n) => n.id === gekozenId);
    return k && k.id !== ingeklapt && !uitgebreid.includes(k.id)
      && !omgeving.nodes.some((n) => n.id === k.id) ? k.id : "";
  }, [alles, gekozenId, ingeklapt, uitgebreid, omgeving]);
  const data = useMemo(() => tijdelijk ? zichtbareGraaf(alles, [...uitgebreid, tijdelijk], filters, markeringFilter) : omgeving,
    [alles, uitgebreid, filters, markeringFilter, tijdelijk, omgeving]);
  const groepen = useMemo(() => gekozenId ? relatieGroepen(alles, gekozenId) : [], [alles, gekozenId]);
  const verborgenBuren = (id: string) => new Set(alles.links.filter((e) => filters[e.groep] && (e.source === id || e.target === id))
    .map((e) => e.source === id ? e.target : e.source).filter((b) => !data.nodes.some((n) => n.id === b))).size;
  const hoofd = delen?.[0];
  const geopend = delen?.map((d) => d.artikel_iri) ?? [];
  // De knopen die het paneel als tekst kan tonen: die van het eigen artikel, niet de bijgeladen.
  const inPaneel = useMemo(() => onWisselArtikel && hoofd ? new Set(hoofd.knopen.filter((k) => !k.rand).map((k) => k.id)) : undefined,
    [hoofd, onWisselArtikel]);

  /** Kiezen: zichtbaar maken als hij verborgen was, selecteren en de camera laten vliegen. Een lege
   *  id – klik op de achtergrond – heft de selectie en daarmee het dimmen op. */
  function kies(id: string) {
    setSelectie(id);
    setIngeklapt("");
    onKiesElement(alles.nodes.find((n) => n.id === id)?.element_id || undefined);
    const knoop = id ? alles.nodes.find((n) => n.id === id) : undefined;
    if (!knoop) return;
    setAangeraakt(true);
    requestAnimationFrame(() => bediening.current?.focus(knoop));
  }

  /** Een randknoop buiten het artikel als eigen artikel openen (bijladen). */
  async function openArtikel(knoop: GraafKnoop) {
    if (!uitklapbaar(knoop) || geopend.includes(knoop.id)) return;
    toon(knoop.id);
    setLaadtUit(knoop.id);
    try {
      const nieuw = await haalSamenhang({ bron_iri: knoop.id });
      zetDelen((oud) => oud.some((d) => d.artikel_iri === nieuw.artikel_iri) ? oud : [...oud, nieuw]);
      toon(nieuw.artikel_iri);
    } catch (e) { setFout(foutTekst(e, "Deze bepaling kon niet worden bijgeladen.")); }
    finally { setLaadtUit(""); }
  }
  /** Verbindingen van een knoop tonen of weer verbergen. Een alleen door de selectie uitgeklapte
   *  knoop klap je in voor zolang hij gekozen is. */
  function wisselVerbindingen(id: string) {
    if (id === tijdelijk) { setIngeklapt(id); return; }
    if (id === ingeklapt) { setIngeklapt(""); return; }
    setUitgebreid((ids) => ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]);
  }
  /** Dubbelklik in de graaf: een randknoop openen, anders verbindingen tonen of verbergen. */
  function dubbelklik(id: string) {
    const knoop = alles.nodes.find((n) => n.id === id);
    if (!knoop) return;
    setAangeraakt(true);
    if (bepaalHoofdactie(knoop, geopend) === "openen") void openArtikel(knoop);
    // Wat de selectie tijdelijk uitklapte, zet dubbelklikken vast in de omgeving.
    else if (id === tijdelijk) toon(id);
    else wisselVerbindingen(id);
  }
  function doeHoofdactie(knoop: GraafKnoop) {
    const actie = bepaalHoofdactie(knoop, geopend, inPaneel);
    if (actie === "tekst") onOpenTekst(knoop);
    else if (actie === "openen") void openArtikel(knoop);
    else if (actie === "wissel") onWisselArtikel?.(knoop);
  }

  if (!delen) return <div className="space-y-3 p-5">
    {fout ? <Melding type="fout" titel="Niet geladen">{fout}{" "}
      <button type="button" onClick={() => void laad()} className="underline">Opnieuw proberen</button></Melding>
      : <><Skeleton className="h-4 w-64" /><Skeleton className="h-48 w-full" /><Skeleton className="h-4 w-40" /></>}
  </div>;

  const weergave = voorAlles ? "alles" : "omgeving";
  return <div className="flex min-h-0 flex-1 flex-col" data-testid="samenhang-graaf" data-vergroot={groot}>
    <div className="shrink-0 border-b border-line px-5 py-2.5">
      <h2 className="text-sm font-semibold text-lint">
        Samenhang van {delen.length > 1 ? clusterOmschrijving(delen)
          : alles.nodes.find((n) => n.id === hoofd?.artikel_iri)?.label ?? "de bepaling"}
        <span className="ml-2 text-xs font-normal text-muted">{data.nodes.length} knopen · {data.links.length} relaties</span>
      </h2>
      {hoofd && !hoofd.verwijzingen_beschikbaar && <p className="mt-1 text-xs text-muted">Verwijzingen zijn nu niet beschikbaar; je ziet de bronstructuur en de annotaties.</p>}
      {delen.some((d) => d.afgekapt) && <p className="mt-1 text-xs text-muted">Er zijn meer verwijzingen dan getoond; de eerste 200 per richting staan in beeld.</p>}
      {delen.length > 1 && <p className="mt-1 text-xs text-muted">De tekst en de annotatie in het paneel gaan over {alles.nodes.find((n) => n.id === hoofd?.artikel_iri)?.label ?? "het eerste artikel"}; een knoop uit een ander artikel opent dat artikel in het paneel.{delen.some(isDeelCluster) ? " Een hoofdstuk of afdeling staat er met zijn artikelen; open een artikel voor leden, annotaties en verwijzingen." : ""}</p>}
      {stand.nietGeladen > 0 && <p className="mt-1 text-xs text-muted">{stand.nietGeladen === 1 ? "1 artikel is" : `${stand.nietGeladen} artikelen zijn`} niet geladen.</p>}
      {fout && <p role="alert" className="mt-1 text-xs text-fout">{fout}</p>}
    </div>
    <div className={`flex min-h-0 flex-1 ${groot ? "flex-col md:flex-row" : "flex-col"}`}>
      <div className="relative min-h-[260px] min-w-0 flex-1 bg-[#f7f9fc]">
        <CanvasGrens><Canvas data={data} selectie={gekozenId} onSelecteer={kies} onDubbelklik={dubbelklik}
          onInteractie={() => setAangeraakt(true)} camera={camera} bediening={bediening} zichtbaar={zichtbaar}
          aandacht={aandacht} /></CanvasGrens>
        {/* Bediening zweeft over het canvas; de lege ruimte ertussen laat klikken door naar de graaf. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
          <div className="flex items-start justify-between gap-2">
            <GraafZoek graaf={alles} zichtbaar={data.nodes} gekozen={gekozenId} onKies={kies} />
            <div role="group" aria-label="Weergave" className="pointer-events-auto flex shrink-0 rounded-full border border-line bg-paper/95 p-0.5 shadow-kaart">
              {(["omgeving", "alles"] as const).map((w) => <button key={w} type="button" aria-pressed={weergave === w}
                onClick={() => zetWeergave(w, alles.nodes.map((n) => n.id))}
                className={`focus-ring min-h-8 rounded-full px-3 text-xs coarse:min-h-11 ${weergave === w ? "bg-lint text-paper" : "text-muted hover:text-lint"}`}>
                {w === "omgeving" ? "Omgeving" : "Alles"}</button>)}
            </div>
          </div>
          <div className="flex items-end justify-between gap-2">
            <GraafLagen filters={filters} open={lagenOpen} onOpen={setLagenOpen}
              onWissel={(g: RelatieGroep) => setFilters((f) => ({ ...f, [g]: !f[g] }))}
              dekking={heeftDekking ? { aan: toonDekking, onWissel: () => setToonDekking((v) => !v) } : undefined}
              markering={filters.annotaties ? { waarde: markeringFilter, onKies: setMarkeringFilter } : undefined} />
            <GraafHint klaar={aangeraakt} />
            <GraafBeeld onPasIn={() => bediening.current?.pasIn()} onZoom={(f) => bediening.current?.zoom(f)} />
          </div>
        </div>
      </div>
      <div className={`shrink-0 border-t border-line bg-paper ${groot ? "max-h-[40dvh] overflow-y-auto md:max-h-none md:w-80 md:border-l md:border-t-0" : "flex max-h-[45%] flex-col"}`}>
        <GraafInspector knoop={geselecteerd} smal={!groot}
          element={geselecteerd?.element_id ? elementen?.find((e) => e.id === geselecteerd.element_id) : undefined}
          laadElement={geselecteerd?.element_id ? () => haalElement(geselecteerd.element_id) : undefined}
          ongedekt={toonDekking && geselecteerd ? dekking?.[geselecteerd.id] : undefined}
          hoofdactie={geselecteerd ? bepaalHoofdactie(geselecteerd, geopend, inPaneel) : null}
          uitgeklapt={!!geselecteerd && (uitgebreid.includes(geselecteerd.id) || tijdelijk === geselecteerd.id)}
          verborgenBuren={geselecteerd ? verborgenBuren(geselecteerd.id) : 0}
          laadt={!!geselecteerd && laadtUit === geselecteerd.id}
          groepen={groepen} samenvatting={samenvatting(alles)}
          onCentreer={() => geselecteerd && bediening.current?.focus(geselecteerd)}
          onSluit={() => kies("")}
          onHoofdactie={() => geselecteerd && doeHoofdactie(geselecteerd)}
          onVraag={onVraag && geselecteerd && geselecteerd.soort !== "klasse" ? () => onVraag(geselecteerd) : undefined}
          onVerbindingen={() => geselecteerd && wisselVerbindingen(geselecteerd.id)}
          onKies={kies} />
      </div>
    </div>
  </div>;
}
