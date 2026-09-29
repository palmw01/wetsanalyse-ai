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
  type GraafKnoop, type RelatieGroep, type Samenhang,
} from "@/lib/samenhang";
import type { CameraStand, GraafCameraBediening } from "./GraafCanvas";

// three.js en de renderer laden pas als de graaf echt in beeld komt.
const Canvas = dynamic(() => import("./GraafCanvas").then((m) => m.GraafCanvas), {
  ssr: false, loading: () => <div className="flex h-full items-center justify-center text-sm text-muted" role="status">3D-graaf laden…</div>,
});
const KNOP = "focus-ring inline-flex min-h-9 items-center justify-center gap-1.5 rounded-button border border-line bg-paper px-2.5 py-1.5 text-xs text-lint transition-colors hover:border-lint/40 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50 coarse:min-h-11";
const GROEPEN: [RelatieGroep, string][] = [["structuur", "Bronstructuur"], ["verwijzingen", "Verwijzingen"], ["annotaties", "Annotaties"]];

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
  const [delen, setDelen] = useState<Samenhang[]>();
  const [fout, setFout] = useState("");
  const [laadtUit, setLaadtUit] = useState("");
  const [selectie, setSelectie] = useState(doel.bron_iri);
  const [uitgebreid, setUitgebreid] = useState<string[]>([doel.bron_iri]);
  const [filters, setFilters] = useState<Record<RelatieGroep, boolean>>({ structuur: true, verwijzingen: true, annotaties: true });
  const [lijst, setLijst] = useState(false);
  const [zoek, setZoek] = useState("");
  const camera = useRef<CameraStand | null>(null);
  const laad = useCallback(async () => {
    setFout("");
    try {
      const eerste = await haalSamenhang(doel);
      // Een lid opent het hele artikel; alleen het gevraagde lid is uitgeklapt. Het artikel zelf
      // uitklappen toont alle inkomende verwijzingen tegelijk – dat is een keuze, geen begin.
      setDelen([eerste]);
    } catch (e) { setFout(foutTekst(e, "De samenhang is niet geladen.")); }
  }, [doel]);
  useEffect(() => {
    // Externe request initialiseren; dezelfde actie dient ook de retryknop.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (actief) void laad();
  }, [laad, actief]);
  return { delen, setDelen, fout, setFout, laadtUit, setLaadtUit, selectie, setSelectie, uitgebreid, setUitgebreid,
    filters, setFilters, lijst, setLijst, zoek, setZoek, camera, laad };
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
  const { delen, setDelen, fout, setFout, laadtUit, setLaadtUit, selectie, setSelectie, uitgebreid, setUitgebreid,
    filters, setFilters, lijst, setLijst, zoek, setZoek, camera, laad } = stand;
  const bediening = useRef<GraafCameraBediening | null>(null);

  const alles = useMemo(() => delen ? bouwGraaf(delen) : { nodes: [], links: [] }, [delen]);
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

  function kies(id: string) {
    setSelectie(id);
    onKiesElement(alles.nodes.find((n) => n.id === id)?.element_id || undefined);
  }

  async function toonVerbindingen() {
    if (!geselecteerd) return;
    setUitgebreid((ids) => [...new Set([...ids, geselecteerd.id])]);
    if (!uitklapbaar(geselecteerd) || delen?.some((d) => d.artikel_iri === geselecteerd.id)) return;
    setLaadtUit(geselecteerd.id);
    try {
      const nieuw = await haalSamenhang({ bron_iri: geselecteerd.id });
      setDelen((oud) => oud && !oud.some((d) => d.artikel_iri === nieuw.artikel_iri) ? [...oud, nieuw] : oud);
      setUitgebreid((ids) => [...new Set([...ids, nieuw.artikel_iri])]);
    } catch (e) { setFout(foutTekst(e, "Deze bepaling kon niet worden bijgeladen.")); }
    finally { setLaadtUit(""); }
  }

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
          <span className="ml-auto rounded-full border border-line bg-paper px-2 py-1 text-[10px] font-semibold tracking-wide text-muted">3D</span>
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
            {!geselecteerd.rand && geselecteerd.soort !== "klasse" && <button className={KNOP} onClick={() => onOpenTekst(geselecteerd)}>Open brontekst</button>}
            {onVraag && geselecteerd.soort !== "klasse" && <button className={KNOP} onClick={() => onVraag(geselecteerd)}>Vraag Lex hierover</button>}
            <button className={KNOP} onClick={() => void toonVerbindingen()} disabled={!!laadtUit || (!extraAantal && !(uitklapbaar(geselecteerd) && !delen.some((d) => d.artikel_iri === geselecteerd.id)))}
              title={!extraAantal ? "Alle verbindingen van deze knoop zijn zichtbaar" : undefined}>
              {laadtUit === geselecteerd.id ? "Laden…" : uitklapbaar(geselecteerd) ? "Artikel bijladen" : `Toon verbindingen${extraAantal > 0 ? ` (+${extraAantal})` : ""}`}
            </button>
            <button className={KNOP} onClick={() => bediening.current?.focus(geselecteerd)}>Focus</button>
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
        </div> : <p className="p-5 text-sm text-muted">Selecteer een zichtbare knoop om de bron, markering of klasse te bekijken.</p>}
      </div>
    </div>
    <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 border-t border-line px-4 py-2 text-[10px] text-muted">
      <span className="inline-flex items-center gap-1"><Bol className="text-lint" /> Bron</span>
      <span className="inline-flex items-center gap-1"><Bol className="text-muted" /> Markering in JAS-kleur</span>
      <span className="inline-flex items-center gap-1"><Ruit /> JAS-klasse</span>
      <span className="inline-flex items-center gap-1"><Cirkel /> Buiten dit artikel</span>
      <button onClick={() => { setUitgebreid(alles.nodes.map((n) => n.id)); setFilters({ structuur: true, verwijzingen: true, annotaties: true }); }} className="focus-ring ml-auto rounded text-lint underline underline-offset-2">Alles tonen</button>
    </div>
  </div>;
}
