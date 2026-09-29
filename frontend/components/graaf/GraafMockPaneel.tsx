"use client";

import dynamic from "next/dynamic";
import { Component, useMemo, useRef, useState, type ReactNode } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ArtefactInhoud, type ArtefactInhoudProps } from "@/components/werkplek/ArtefactInhoud";
import { jasStyle } from "@/lib/jas";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { ARTIKEL, LID1, LID2, SOORT_LABEL, bouwVoorbeeldGraaf, zichtbareGraaf, type GraafKnoop, type RelatieGroep } from "@/lib/graafMock";
import type { CameraStand, GraafCameraBediening } from "./GraafCanvas";

const Canvas = dynamic(() => import("./GraafCanvas").then((m) => m.GraafCanvas), {
  ssr: false, loading: () => <div className="flex h-full items-center justify-center text-sm text-muted" role="status">3D-graaf laden…</div>,
});
const KNOP = "focus-ring inline-flex min-h-9 items-center justify-center gap-1.5 rounded-button border border-line bg-paper px-2.5 py-1.5 text-xs text-lint transition-colors hover:border-lint/40 hover:bg-surface coarse:min-h-11";

export function GraafIcoon({ className = "h-4 w-4" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
    <path d="m6 7 12 2M6 7l5 12m7-10-7 10" /><circle cx="6" cy="7" r="3" fill="currentColor" stroke="none" />
    <circle cx="18" cy="9" r="3" fill="currentColor" stroke="none" /><circle cx="11" cy="19" r="3" fill="currentColor" stroke="none" />
  </svg>;
}

class CanvasGrens extends Component<{ children: ReactNode }, { fout: boolean }> {
  state = { fout: false };
  static getDerivedStateFromError() { return { fout: true }; }
  render() {
    return this.state.fout ? <p role="status" className="p-6 text-sm text-muted">3D kon niet worden geladen. De knopenlijst en brontekst blijven beschikbaar. Herlaad de pagina om opnieuw te proberen.</p> : this.props.children;
  }
}

type Props = Omit<ArtefactInhoudProps, "onSluiten"> & {
  breed: boolean; onSluit: () => void; tab: "tekst" | "graaf";
  onTab: (tab: "tekst" | "graaf") => void;
  onVraagOverBron: (node: GraafKnoop) => void;
};

export function GraafMockPaneel({ breed, onSluit, tab, onTab, onVraagOverBron, ...annotatie }: Props) {
  const [graafGeopend, setGraafGeopend] = useState(tab === "graaf");
  if (tab === "graaf" && !graafGeopend) setGraafGeopend(true);
  const [groot, setGroot] = useState(false);
  const [selectie, setSelectie] = useState(ARTIKEL);
  const [uitgebreid, setUitgebreid] = useState<string[]>([LID1]);
  const [filters, setFilters] = useState<Record<RelatieGroep, boolean>>({ structuur: true, verwijzingen: true, annotaties: true });
  const [lijst, setLijst] = useState(false);
  const [zoek, setZoek] = useState("");
  const camera = useRef<CameraStand | null>(null);
  const bediening = useRef<GraafCameraBediening | null>(null);
  const alles = useMemo(() => bouwVoorbeeldGraaf(annotatie.doc), [annotatie.doc]);
  const gekozenId = annotatie.actiefId ?? selectie;
  // Een in de tekst gekozen markering is meteen zichtbaar in de graaf, inclusief zijn klasse.
  const data = useMemo(() => zichtbareGraaf(alles, annotatie.actiefId ? [...uitgebreid, annotatie.actiefId] : uitgebreid, filters), [alles, uitgebreid, filters, annotatie.actiefId]);
  const geselecteerd = data.nodes.find((n) => n.id === gekozenId);
  const element = annotatie.doc.elementen.find((e) => e.id === geselecteerd?.elementId);
  const relaties = data.links.filter((l) => l.source === gekozenId || l.target === gekozenId);
  const zichtbareLijst = data.nodes.filter((n) => `${n.label} ${n.klasse || ""}`.toLocaleLowerCase("nl").includes(zoek.toLocaleLowerCase("nl")));

  function kies(id: string) {
    setSelectie(id);
    annotatie.onKies(alles.nodes.find((n) => n.id === id)?.elementId);
  }
  function uitklappen() {
    if (!geselecteerd) return;
    setUitgebreid((ids) => [...new Set([...ids, gekozenId])]);
  }
  function openTekst() {
    if (!geselecteerd) return;
    onTab("tekst");
    if (geselecteerd.soort === "klasse") {
      annotatie.onKies(annotatie.doc.elementen.find((e) => e.klasse === geselecteerd.klasse && e.lifecycle !== "rejected")?.id);
    } else annotatie.onKies(geselecteerd.elementId);
    // De gedeelde tekstcomponent scrollt zelf naar geselecteerde markeringen.
    if (geselecteerd.lid && !geselecteerd.elementId) {
      requestAnimationFrame(() => document.querySelector(`[data-artefact] [data-lid="${geselecteerd.lid}"]`)?.scrollIntoView({ block: "center" }));
    }
  }
  const extraAantal = geselecteerd ? new Set(alles.links.filter((e) => filters[e.groep] && (e.source === gekozenId || e.target === gekozenId))
    .map((e) => e.source === gekozenId ? e.target : e.source).filter((id) => !data.nodes.some((n) => n.id === id))).size : 0;

  return <Dialog label="Samenhang · 3D-graaf" variant={groot ? "fullscreen" : breed ? "kolom" : "side"}
    onSluit={onSluit} onEscape={() => { if (groot) setGroot(false); else if (lijst) setLijst(false); else if (tab === "graaf") onSluit(); }}>
    <div className="flex min-h-0 flex-1 flex-col" data-testid="graaf-paneel" data-vergroot={groot}>
      <div className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-2.5">
        <div className="flex rounded-lg bg-surface p-1" role="group" aria-label="Weergave kiezen">
          {(["tekst", "graaf"] as const).map((waarde) => <button key={waarde} type="button"
            aria-pressed={tab === waarde} onClick={() => onTab(waarde)}
            className={`focus-ring flex min-h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium ${tab === waarde ? "bg-paper text-lint shadow-zacht" : "text-muted hover:text-lint"}`}>
            {waarde === "graaf" && <GraafIcoon />}{waarde === "tekst" ? "Tekst" : "3D-graaf"}
          </button>)}
        </div>
        <div className="flex-1" />
        <button className="focus-ring rounded-lg p-2 text-muted hover:bg-surface" onClick={() => setGroot((v) => !v)} aria-label={groot ? "Verkleinen" : "Vergroten"} title={groot ? "Terug naar zijpaneel" : "Graaf vergroten"}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d={groot ? "M9 3v6H3m18 6h-6v6M3 9l6-6m6 18 6-6" : "M8 3H3v5m13 13h5v-5M3 3l6 6m6 6 6 6"} /></svg>
        </button>
        <button className="focus-ring rounded-lg p-2 text-muted hover:bg-surface" onClick={onSluit} aria-label="Paneel sluiten"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </div>
      <div className={tab === "tekst" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
        {tab === "tekst" && <ArtefactInhoud {...annotatie} onSluiten={onSluit} />}
      </div>
      <div className={tab === "graaf" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
        <div className="shrink-0 border-b border-line px-5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-faint">Bronnen &amp; annotaties</p>
          <h2 className="mt-0.5 text-base font-semibold text-lint">Samenhang van artikel 9</h2>
          <p className="mt-1 text-xs text-muted">Invorderingswet 1990 <span className="px-1.5 text-faint">·</span> {data.nodes.length} knopen <span className="px-1.5 text-faint">·</span> {data.links.length} relaties</p>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
            {([['structuur', 'Bronstructuur'], ['verwijzingen', 'Verwijzingen'], ['annotaties', 'Annotaties']] as const).map(([key, label]) => <label key={key} className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
              <input type="checkbox" checked={filters[key]} onChange={() => setFilters((f) => ({ ...f, [key]: !f[key] }))} className="h-3.5 w-3.5 accent-[#154273]" />{label}
            </label>)}
          </div>
        </div>
        <div className={`flex min-h-0 flex-1 ${groot ? "flex-col md:flex-row" : "flex-col"}`}>
          <div className="relative flex min-h-[245px] min-w-0 flex-1 flex-col bg-[#f7f9fc]">
            <div className="flex shrink-0 items-center gap-2 px-3 pt-3">
              <button className={KNOP} onClick={() => bediening.current?.pasIn()}>Alles in beeld</button>
              <button className={`${KNOP} ${lijst ? "border-lint/50 bg-lint/5" : ""}`} aria-expanded={lijst} onClick={() => setLijst((v) => !v)}>Knopenlijst</button>
              <span className="ml-auto rounded-full border border-line bg-paper px-2 py-1 text-[10px] font-semibold tracking-wide text-muted">3D</span>
            </div>
            <div className="relative min-h-0 flex-1">
              {graafGeopend && <CanvasGrens><Canvas data={data} selectie={gekozenId} onSelecteer={kies} camera={camera} bediening={bediening} zichtbaar={tab === "graaf"} /></CanvasGrens>}
              {lijst && <div className="absolute inset-y-2 left-3 z-10 flex w-[min(270px,calc(100%-24px))] flex-col rounded-kaart border border-line bg-paper/95 shadow-kaart">
                <div className="border-b border-line p-2"><input aria-label="Knopen zoeken" placeholder="Zoek bron, fragment of klasse…" value={zoek} onChange={(e) => setZoek(e.target.value)} className="focus-ring w-full rounded-field border border-line bg-paper px-2 py-2 text-xs" /></div>
                <div className="min-h-0 overflow-y-auto p-1" role="group" aria-label="Knopen in de graaf">
                  {zichtbareLijst.map((node) => <button key={node.id} data-knoop-id={node.id} aria-pressed={gekozenId === node.id} onClick={() => kies(node.id)} className={`focus-ring flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-xs ${gekozenId === node.id ? "bg-lint/10 text-lint" : "text-ink hover:bg-surface"}`}>
                    <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: node.kleur }} /><span className="min-w-0"><span className="block">{node.label}</span><span className="text-[10px] text-faint">{SOORT_LABEL[node.soort]}</span></span>
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
                <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-faint"><span className="h-2 w-2 rounded-full" style={{ background: geselecteerd.kleur }} />{SOORT_LABEL[geselecteerd.soort]}{element && <span className="ml-auto normal-case tracking-normal">{LIFECYCLE_LABEL[element.lifecycle] || element.lifecycle}</span>}</div>
                <h3 className="text-sm font-semibold leading-relaxed">{geselecteerd.label}</h3>
              </div>
              {element && <span className={`inline-block rounded border px-2 py-0.5 text-[11px] ${jasStyle(element.klasse)}`}>{element.klasse}</span>}
              {geselecteerd.tekst && <p className="border-l-2 border-lint/20 pl-3 text-xs leading-relaxed text-muted">{geselecteerd.tekst}</p>}
              {element?.toelichting && <p className="text-xs leading-relaxed text-muted">{element.toelichting}</p>}
              {element?.alternatieven?.map((alt) => <p key={alt.klasse} className="rounded-lg bg-surface p-2 text-xs text-muted"><strong>Andere lezing: {alt.klasse}.</strong> {alt.motivatie}</p>)}
              <div className="flex flex-wrap gap-2">
                <button className={KNOP} onClick={openTekst}>Open brontekst</button>
                <button className={KNOP} onClick={() => { setGroot(false); onVraagOverBron(geselecteerd); }}>Vraag Lex hierover</button>
                <button className={KNOP} onClick={uitklappen} disabled={!extraAantal} title={!extraAantal ? "Alle verbindingen van deze knoop zijn zichtbaar" : undefined}>Toon verbindingen{extraAantal > 0 ? ` (+${extraAantal})` : ""}</button>
                <button className={KNOP} onClick={() => bediening.current?.focus(geselecteerd)}>Focus</button>
              </div>
              {relaties.length > 0 && <div className="border-t border-line pt-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">Verbonden met</p>
                {relaties.map((rel) => {
                  const uitgaand = rel.source === gekozenId;
                  const ander = data.nodes.find((n) => n.id === (uitgaand ? rel.target : rel.source));
                  if (!ander) return null;
                  return <button key={rel.id} onClick={() => kies(ander.id)} className="focus-ring flex w-full items-baseline gap-2 rounded py-1 text-left text-xs hover:bg-surface">
                    <span className="shrink-0 text-faint">{uitgaand ? "→" : "←"} {rel.label}</span><span className="truncate text-lint">{ander.label}</span>
                  </button>;
                })}
              </div>}
              <p className="text-[10px] leading-relaxed text-faint">Verbindingen tonen structuur en verwijzingen. Annotaties zijn voorstellen in deze voorbeeldscène.</p>
            </div> : <p className="p-5 text-sm text-muted">Selecteer een zichtbare knoop om de bron, markering of klasse te bekijken.</p>}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 border-t border-line px-4 py-2 text-[10px] text-muted">
          <span>● <span className="text-lint">Bron</span></span><span>● Markering in JAS-kleur</span><span>◆ JAS-klasse</span>
          <button onClick={() => { setUitgebreid([LID1, LID2, ...alles.nodes.filter((n) => n.soort === "markering").map((n) => n.id)]); setFilters({ structuur: true, verwijzingen: true, annotaties: true }); }} className="focus-ring ml-auto rounded text-lint underline underline-offset-2">Hele voorbeeld tonen</button>
        </div>
      </div>
    </div>
  </Dialog>;
}
