"use client";

import dynamic from "next/dynamic";
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ChevronOmlaag, Cirkel, Ruit } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { foutTekst } from "@/lib/api";
import { jasStyle } from "@/lib/jas";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import type { NodeDoel } from "@/lib/annotatieNode";
import type { Lifecycle } from "@/lib/types";
import {
  SOORT_LABEL, bouwGraaf, haalSamenhang, uitklapbaar, zichtbareGraaf,
  type GraafData, type GraafKnoop, type RelatieGroep, type Samenhang,
} from "@/lib/samenhang";
import type { CameraStand, GraafCameraBediening } from "./GraafCanvas";

// three.js en de renderer laden pas als de graaf echt in beeld komt.
const Canvas = dynamic(() => import("./GraafCanvas").then((m) => m.GraafCanvas), {
  ssr: false, loading: () => <div className="flex h-full items-center justify-center text-sm text-muted" role="status">3D-graaf laden…</div>,
});
const KNOP = "focus-ring inline-flex min-h-9 items-center justify-center gap-1.5 rounded-button border border-line bg-paper px-2.5 py-1.5 text-xs text-lint transition-colors hover:border-lint/40 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50 coarse:min-h-11";
const GROEPEN: [RelatieGroep, string][] = [["structuur", "Bronstructuur"], ["verwijzingen", "Verwijzingen"], ["annotaties", "Annotaties"]];

/** Een lijnstuk in de legenda, in dezelfde kleur en dikte als de verbinding in de graaf. */
function Streep({ className }: { className: string }) {
  return <span aria-hidden="true" className={`inline-block w-5 shrink-0 rounded-full ${className}`} />;
}

/** Een gevulde stip in de kleur van de tekst (legenda). */
function Bol({ className = "" }: { className?: string }) {
  return <svg className={`h-[1em] w-[1em] ${className}`} viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="5" fill="currentColor" /></svg>;
}

class CanvasGrens extends Component<{ children: ReactNode }, { fout: boolean }> {
  state = { fout: false };
  static getDerivedStateFromError() { return { fout: true }; }
  render() {
    return this.state.fout ? <p role="status" className="p-6 text-sm text-muted">3D kon niet worden geladen. De knopenlijst en brontekst blijven beschikbaar. Herlaad de pagina om opnieuw te proberen.</p> : this.props.children;
  }
}

/** De toestand van de graaf. Leeft in het paneel (búiten de `Dialog`): vergroten wisselt de
 *  dialoogvorm en remount daarmee de inhoud, en zonder dit waren bijgeladen artikelen, uitklappingen,
 *  selectie en camera dan weg. `actief` laadt pas als de tab voor het eerst opengaat. */
export function useSamenhangStand(doel: NodeDoel, actief: boolean) {
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
  const [lijst, setLijst] = useState(false);
  const [legenda, setLegenda] = useState(false);
  const [zoek, setZoek] = useState("");
  const camera = useRef<CameraStand | null>(null);
  const zetDelen = useCallback((maak: (oud: Samenhang[]) => Samenhang[]) => setGeladen((oud) => {
    const delen = maak(oud?.delen ?? []);
    return { delen, graaf: bouwGraaf(delen, oud?.graaf) };
  }), []);
  const laad = useCallback(async () => {
    setFout("");
    try {
      const eerste = await haalSamenhang(doel);
      // Een lid opent het hele artikel; alleen het gevraagde lid is uitgeklapt. Het artikel zelf
      // uitklappen toont alle inkomende verwijzingen tegelijk – dat is een keuze, geen begin.
      zetDelen(() => [eerste]);
    } catch (e) { setFout(foutTekst(e, "De samenhang is niet geladen.")); }
  }, [doel, zetDelen]);
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
      zetDelen(() => nieuw);
      const ids = new Set(nieuw.flatMap((d) => d.knopen.map((k) => k.id)));
      setSelectie((huidig) => (huidig && !ids.has(huidig) ? doel.bron_iri : huidig));
    } catch (e) { setFout(foutTekst(e, "De graaf is niet bijgewerkt; herlaad om de laatste stand te zien.")); }
  }, [geladen, zetDelen, doel.bron_iri]);

  /** Alles tonen en weer terug naar de stand van daarvoor. */
  const wisselAlles = useCallback((allesIds: string[]) => {
    if (voorAlles) {
      setUitgebreid(voorAlles.uitgebreid);
      setFilters(voorAlles.filters);
      setVoorAlles(null);
      return;
    }
    setVoorAlles({ uitgebreid, filters });
    setUitgebreid(allesIds);
    setFilters({ structuur: true, verwijzingen: true, annotaties: true });
  }, [voorAlles, uitgebreid, filters]);

  return { delen: geladen?.delen, alles: geladen?.graaf, zetDelen, ververs, fout, setFout, laadtUit, setLaadtUit,
    selectie, setSelectie, uitgebreid, setUitgebreid, filters, setFilters, voorAlles, setVoorAlles, wisselAlles,
    lijst, setLijst, legenda, setLegenda, zoek, setZoek, camera, laad };
}
export type SamenhangStand = ReturnType<typeof useSamenhangStand>;

/** De samenhang van de geopende bepaling als 3D-graaf: bronstructuur, letterlijke verwijzingen
 *  (één stap) en de actuele markeringen met hun JAS-klasse. Leeft als tab naast de tekst in het
 *  annotatiepaneel; de gekozen markering is in beide tabs dezelfde. */
export function SamenhangGraaf({ stand, zichtbaar, groot, actiefElementId, onKiesElement, onOpenTekst, onVraag }: {
  stand: SamenhangStand; zichtbaar: boolean; groot: boolean;
  actiefElementId?: string;
  onKiesElement: (elementId?: string) => void;
  onOpenTekst: (knoop: GraafKnoop) => void;
  onVraag?: (knoop: GraafKnoop) => void;
}) {
  const { delen, zetDelen, fout, setFout, laadtUit, setLaadtUit, selectie, setSelectie, uitgebreid, setUitgebreid,
    filters, setFilters, voorAlles, setVoorAlles, wisselAlles, lijst, setLijst, legenda, setLegenda, zoek, setZoek,
    camera, laad } = stand;
  const bediening = useRef<GraafCameraBediening | null>(null);

  const alles = useMemo(() => stand.alles ?? { nodes: [], links: [] }, [stand.alles]);
  const actieveKnoop = actiefElementId ? `element:${actiefElementId}` : undefined;
  const gekozenId = actieveKnoop && alles.nodes.some((n) => n.id === actieveKnoop) ? actieveKnoop : selectie;
  // Een in de tekst gekozen markering is meteen zichtbaar in de graaf, met haar klasse.
  const data = useMemo(() => zichtbareGraaf(alles, actieveKnoop ? [...uitgebreid, actieveKnoop] : uitgebreid, filters),
    [alles, uitgebreid, filters, actieveKnoop]);
  const geselecteerd = data.nodes.find((n) => n.id === gekozenId);
  const relaties = data.links.filter((l) => l.source === gekozenId || l.target === gekozenId);
  const zichtbareLijst = data.nodes.filter((n) => `${n.label} ${n.klasse}`.toLocaleLowerCase("nl").includes(zoek.toLocaleLowerCase("nl")));
  const extraAantal = geselecteerd ? new Set(alles.links.filter((e) => filters[e.groep] && (e.source === gekozenId || e.target === gekozenId))
    .map((e) => e.source === gekozenId ? e.target : e.source).filter((id) => !data.nodes.some((n) => n.id === id))).size : 0;
  const hoofd = delen?.[0];

  /** Kiezen laat de camera naar de knoop vliegen (zoals de CGM-viewer); een lege id – klik op de
   *  achtergrond – heft de selectie en daarmee het dimmen op. */
  function kies(id: string) {
    setSelectie(id);
    onKiesElement(alles.nodes.find((n) => n.id === id)?.element_id || undefined);
    const knoop = id ? alles.nodes.find((n) => n.id === id) : undefined;
    if (knoop) requestAnimationFrame(() => bediening.current?.focus(knoop));
  }

  /** Een randknoop buiten het artikel als eigen artikel bijladen. */
  async function bijladen() {
    if (!geselecteerd || !uitklapbaar(geselecteerd)) return;
    setUitgebreid((ids) => [...new Set([...ids, geselecteerd.id])]);
    setLaadtUit(geselecteerd.id);
    try {
      const nieuw = await haalSamenhang({ bron_iri: geselecteerd.id });
      zetDelen((oud) => oud.some((d) => d.artikel_iri === nieuw.artikel_iri) ? oud : [...oud, nieuw]);
      setUitgebreid((ids) => [...new Set([...ids, nieuw.artikel_iri])]);
      // "Minder tonen" mag een net bijgeladen artikel niet verbergen.
      setVoorAlles((v) => v && { ...v, uitgebreid: [...new Set([...v.uitgebreid, geselecteerd.id, nieuw.artikel_iri])] });
    } catch (e) { setFout(foutTekst(e, "Deze bepaling kon niet worden bijgeladen.")); }
    finally { setLaadtUit(""); }
  }
  /** Verbindingen van de gekozen knoop tonen, of weer verbergen als hij uitgeklapt is. */
  function wisselVerbindingen() {
    if (!geselecteerd) return;
    setUitgebreid((ids) => ids.includes(geselecteerd.id) ? ids.filter((i) => i !== geselecteerd.id) : [...ids, geselecteerd.id]);
  }
  const uitgeklapt = !!geselecteerd && uitgebreid.includes(geselecteerd.id);
  const bijlaadbaar = !!geselecteerd && uitklapbaar(geselecteerd) && !delen?.some((d) => d.artikel_iri === geselecteerd.id);

  if (!delen) return <div className="space-y-3 p-5">
    {fout ? <Melding type="fout" titel="Niet geladen">{fout}{" "}
      <button type="button" onClick={() => void laad()} className="underline">Opnieuw proberen</button></Melding>
      : <><Skeleton className="h-4 w-64" /><Skeleton className="h-48 w-full" /><Skeleton className="h-4 w-40" /></>}
  </div>;

  return <div className="flex min-h-0 flex-1 flex-col" data-testid="samenhang-graaf" data-vergroot={groot}>
    <div className="shrink-0 border-b border-line px-5 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-faint">Bronnen &amp; annotaties</p>
      <h2 className="mt-0.5 text-base font-semibold text-lint">Samenhang van {alles.nodes.find((n) => n.id === hoofd?.artikel_iri)?.label ?? "de bepaling"}</h2>
      <p className="mt-1 text-xs text-muted">{data.nodes.length} knopen <span className="px-1.5 text-faint">·</span> {data.links.length} relaties</p>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
        {GROEPEN.map(([key, label]) => <label key={key} className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
          <input type="checkbox" checked={filters[key]} onChange={() => setFilters((f) => ({ ...f, [key]: !f[key] }))} className="h-3.5 w-3.5 accent-lint" />{label}
        </label>)}
      </div>
      {hoofd && !hoofd.verwijzingen_beschikbaar && <p className="mt-2 text-xs text-muted">Verwijzingen zijn nu niet beschikbaar; je ziet de bronstructuur en de annotaties.</p>}
      {delen.some((d) => d.afgekapt) && <p className="mt-2 text-xs text-muted">Er zijn meer verwijzingen dan getoond; de eerste 200 per richting staan in beeld.</p>}
      {fout && <p role="alert" className="mt-2 text-xs text-fout">{fout}</p>}
    </div>
    <div className={`flex min-h-0 flex-1 ${groot ? "flex-col md:flex-row" : "flex-col"}`}>
      <div className="relative flex min-h-[245px] min-w-0 flex-1 flex-col bg-[#f7f9fc]">
        <div className="flex shrink-0 items-center gap-2 px-3 pt-3">
          <button className={KNOP} onClick={() => bediening.current?.pasIn()}>Alles in beeld</button>
          <button className={`${KNOP} ${lijst ? "border-lint/50 bg-lint/5" : ""}`} aria-expanded={lijst} onClick={() => setLijst((v) => !v)}>Knopenlijst</button>
          <button className={`${KNOP} ${legenda ? "border-lint/50 bg-lint/5" : ""}`} aria-expanded={legenda} onClick={() => setLegenda((v) => !v)}>Legenda</button>
          <button className={`${KNOP} ${voorAlles ? "border-lint/50 bg-lint/5" : ""}`} aria-pressed={!!voorAlles}
            onClick={() => wisselAlles(alles.nodes.map((n) => n.id))}>{voorAlles ? "Minder tonen" : "Alles tonen"}</button>
        </div>
        <div className="relative min-h-0 flex-1">
          <CanvasGrens><Canvas data={data} selectie={gekozenId} onSelecteer={kies} camera={camera} bediening={bediening} zichtbaar={zichtbaar} /></CanvasGrens>
          {lijst && <div className="absolute inset-y-2 left-3 z-10 flex w-[min(270px,calc(100%-24px))] flex-col rounded-kaart border border-line bg-paper/95 shadow-kaart">
            <div className="border-b border-line p-2"><input aria-label="Knopen zoeken" placeholder="Zoek bron, fragment of klasse…" value={zoek} onChange={(e) => setZoek(e.target.value)} className="focus-ring w-full rounded-field border border-line bg-paper px-2 py-2 text-xs" /></div>
            <div className="min-h-0 overflow-y-auto p-1" role="group" aria-label="Knopen in de graaf">
              {zichtbareLijst.map((node) => <button key={node.id} data-knoop-id={node.id} aria-pressed={gekozenId === node.id} onClick={() => kies(node.id)} className={`focus-ring flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-xs ${gekozenId === node.id ? "bg-lint/10 text-lint" : "text-ink hover:bg-surface"}`}>
                <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: node.kleur }} /><span className="min-w-0"><span className="block">{node.label}</span><span className="text-[10px] text-faint">{SOORT_LABEL[node.soort]}{node.rand ? " · buiten dit artikel" : ""}</span></span>
              </button>)}
              {!zichtbareLijst.length && <p className="p-3 text-xs text-muted">Geen knopen gevonden.</p>}
            </div>
          </div>}
          {legenda && <div role="group" aria-label="Legenda" className="absolute bottom-2 right-3 z-10 w-56 rounded-kaart border border-line bg-paper/95 p-3 text-xs text-muted shadow-kaart">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-faint">Knopen</p>
            <p className="flex items-center gap-2"><Bol className="text-lint" /> Bron (regeling, artikel, lid)</p>
            <p className="flex items-center gap-2"><Bol className="text-muted" /> Markering, in JAS-kleur</p>
            <p className="flex items-center gap-2"><Ruit /> JAS-klasse</p>
            <p className="flex items-center gap-2"><Cirkel /> Buiten dit artikel</p>
            <p className="mb-1.5 mt-2.5 text-[10px] font-semibold uppercase tracking-wider text-faint">Verbindingen</p>
            <p className="flex items-center gap-2"><Streep className="h-[3px] bg-[#8aa1b6]" /> bevat</p>
            <p className="flex items-center gap-2"><Streep className="h-[2px] bg-[#6b4e91]" /> verwijst naar</p>
            <p className="flex items-center gap-2"><Streep className="h-px bg-[#9fb3c5]" /> markeert / heeft klasse</p>
            <p className="mt-2 text-[10px] text-faint">Hover toont de naam; afstand en positie hebben geen juridische betekenis.</p>
          </div>}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-line/60 px-4 py-2 text-[10px] text-muted">
          <span>Slepen: draaien · scrollen: zoomen</span><span>Klik op een knoop om te verkennen</span>
        </div>
      </div>
      <div className={`shrink-0 overflow-y-auto border-t border-line bg-paper ${groot ? "max-h-[30dvh] md:max-h-none md:w-80 md:border-l md:border-t-0" : "max-h-[30dvh] sm:max-h-[36vh]"}`} data-testid="graaf-detail">
        {geselecteerd ? <div className="space-y-3 p-4">
          <div>
            <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-faint"><span className="h-2 w-2 rounded-full" style={{ background: geselecteerd.kleur }} />{SOORT_LABEL[geselecteerd.soort]}{geselecteerd.rand && geselecteerd.soort !== "extern" ? " · buiten dit artikel" : ""}{geselecteerd.lifecycle && <span className="ml-auto normal-case tracking-normal">{LIFECYCLE_LABEL[geselecteerd.lifecycle as Lifecycle] || geselecteerd.lifecycle}</span>}</div>
            <h3 className="text-sm font-semibold leading-relaxed">{geselecteerd.label}</h3>
          </div>
          {geselecteerd.soort === "markering" && <span className={`inline-block rounded border px-2 py-0.5 text-[11px] ${jasStyle(geselecteerd.klasse)}`}>{geselecteerd.klasse}</span>}
          {geselecteerd.tekst && geselecteerd.soort !== "markering" && <p className="border-l-2 border-lint/20 pl-3 text-xs leading-relaxed text-muted">{geselecteerd.tekst}</p>}
          <div className="flex flex-wrap gap-2">
            {/* Alleen knoppen die voor deze knoop iets doen; niets staat grijs in beeld. */}
            <button className={KNOP} onClick={() => bediening.current?.focus(geselecteerd)} title="Camera naar deze knoop">Focus</button>
            {uitgeklapt
              ? <button className={KNOP} onClick={wisselVerbindingen}>Verberg verbindingen</button>
              : extraAantal > 0 && <button className={KNOP} onClick={wisselVerbindingen}>Toon verbindingen (+{extraAantal})</button>}
            {bijlaadbaar && <button className={KNOP} onClick={() => void bijladen()} disabled={!!laadtUit}>
              {laadtUit === geselecteerd.id ? "Laden…" : "Artikel bijladen"}</button>}
            {!geselecteerd.rand && geselecteerd.soort !== "klasse" && <button className={KNOP} onClick={() => onOpenTekst(geselecteerd)}>Open brontekst</button>}
            {onVraag && geselecteerd.soort !== "klasse" && <button className={KNOP} onClick={() => onVraag(geselecteerd)}>Vraag Lex hierover</button>}
          </div>
          {geselecteerd.soort === "extern" && <p className="text-xs text-muted">Deze bepaling staat niet in de kennisgraaf; alleen de verwijzing ernaar is bekend.</p>}
          {relaties.length > 0 && <div className="border-t border-line pt-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">Verbonden met</p>
            {relaties.map((rel) => {
              const uitgaand = rel.source === gekozenId;
              const ander = data.nodes.find((n) => n.id === (uitgaand ? rel.target : rel.source));
              if (!ander) return null;
              return <button key={rel.id} onClick={() => kies(ander.id)} className="focus-ring flex w-full items-baseline gap-2 rounded py-1 text-left text-xs hover:bg-surface">
                <span className="inline-flex shrink-0 items-center gap-1 text-faint"><ChevronOmlaag className={uitgaand ? "-rotate-90" : "rotate-90"} /> {rel.label}</span><span className="truncate text-lint">{ander.label}</span>
                {rel.anker_tekst && <span className="truncate text-faint">({rel.anker_tekst})</span>}
              </button>;
            })}
          </div>}
          <p className="text-[10px] leading-relaxed text-faint">Verbindingen tonen bronstructuur, verwijzingen uit de tekst en annotaties. Afstand en positie hebben geen juridische betekenis.</p>
        </div> : <p className="p-5 text-sm text-muted">Selecteer een knoop in de graaf of de knopenlijst om de bron, markering of klasse te bekijken.</p>}
      </div>
    </div>
  </div>;
}
