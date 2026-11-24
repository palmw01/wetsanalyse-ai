"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { GraafBeeld } from "@/components/graaf/GraafBeeld";
import {
  MAAT, RAND_CENTRAAL, knoopKleuren, knoopSleutel, lijnNaam, pijlpunt, type DiagramData, type DiagramKnoop,
  type DiagramLijn,
} from "@/lib/diagram2c";

/** Wat in beeld is, in de eenheden van de tekening (de `viewBox`). */
interface Beeld { x: number; y: number; b: number; h: number }

/** Het 2c-diagram rond één centrale formulering (Handleiding §3.4c), getekend uit wat de api uitrekende: hetzelfde
 *  plaatje als in het werkgebiedrapport, maar met knopen en lijnen die je kunt kiezen. Kleur draagt nooit alleen: elke
 *  knoop noemt zijn klasse, elke lijn haar relatie; een voorstel is gestippeld, een impliciete partij ook (haar rand).
 *
 *  De bediening is die van de graaf (melding gebruiker 24 nov 2026): het muiswiel zoomt rond de cursor, slepen verschuift,
 *  en rechtsonder staan dezelfde knoppen (`GraafBeeld`: *Alles in beeld*, inzoomen, uitzoomen). Geen scrollbalken: het
 *  venster heeft de verhouding van de tekening en zoomen verandert alleen wat erin te zien is. Een klik zonder slepen
 *  kiest nog steeds een knoop of lijn. Zonder `onKiesKnoop` en `onKiesLijn` is het een plaatje. */
export function Diagram2c({ data, gekozenKnoop, gekozenLijn, onKiesKnoop, onKiesLijn, label }: {
  data: DiagramData;
  /** `knoopSleutel` van de gekozen knoop. */
  gekozenKnoop?: string;
  /** `relatie_id` van de gekozen lijn. */
  gekozenLijn?: string;
  onKiesKnoop?: (knoop: DiagramKnoop) => void;
  onKiesLijn?: (lijn: DiagramLijn) => void;
  label: string;
}) {
  const { diagram, plaatsing, lijnen } = data;
  const rand = 3;
  const kiesbaar = !!(onKiesKnoop || onKiesLijn);
  const alles: Beeld = { x: -rand, y: -rand, b: plaatsing.breedte + 2 * rand, h: plaatsing.hoogte + 2 * rand };
  const [beeld, setBeeld] = useState<Beeld>(alles);
  const sleutel = `${alles.b}x${alles.h}`;
  // Een nieuwe tekening (na een besluit) begint weer met alles in beeld.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setBeeld({ x: -rand, y: -rand, b: plaatsing.breedte + 2 * rand, h: plaatsing.hoogte + 2 * rand }), [sleutel]); // eslint-disable-line react-hooks/exhaustive-deps
  const svg = useRef<SVGSVGElement>(null);
  const sleep = useRef<{ x: number; y: number; beeld: Beeld; schaal: number; bewogen: boolean } | null>(null);
  const [sleept, setSleept] = useState(false);

  /** Pixels per eenheid van de tekening, zoals ze nu in beeld is (de viewBox staat op `meet`). */
  const schaal = useCallback(() => {
    const r = svg.current?.getBoundingClientRect();
    return r ? Math.min(r.width / beeld.b, r.height / beeld.h) : 1;
  }, [beeld]);

  /** Zoom met `factor` (< 1: inzoomen) rond een punt in de tekening; hoogstens 6× in, niet verder uit dan alles. */
  const zoom = useCallback((factor: number, rond?: { x: number; y: number }) => {
    setBeeld((v) => {
      const b = Math.min(alles.b * 1.2, Math.max(alles.b / 6, v.b * factor));
      const f = b / v.b;
      const c = rond ?? { x: v.x + v.b / 2, y: v.y + v.h / 2 };
      return { x: c.x - (c.x - v.x) * f, y: c.y - (c.y - v.y) * f, b, h: v.h * f };
    });
  }, [alles.b]);

  // Het muiswiel zoomt rond de cursor. Een eigen luisteraar, niet `onWheel`: React registreert die passief, en dan scrolt
  // de pagina mee.
  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const wiel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const s = Math.min(r.width / beeld.b, r.height / beeld.h);
      // De tekening staat gecentreerd in het venster (`xMidYMid meet`).
      const ox = (r.width - beeld.b * s) / 2, oy = (r.height - beeld.h * s) / 2;
      const punt = { x: beeld.x + (e.clientX - r.left - ox) / s, y: beeld.y + (e.clientY - r.top - oy) / s };
      zoom(Math.exp(e.deltaY * 0.0015), punt);
    };
    el.addEventListener("wheel", wiel, { passive: false });
    return () => el.removeEventListener("wheel", wiel);
  }, [beeld, zoom]);

  return (
    <div className="relative" data-diagram-zoom={(alles.b / beeld.b).toFixed(2)}>
    <svg ref={svg} role={kiesbaar ? "group" : "img"} aria-label={label} data-diagram-2c={diagram.centraal}
      viewBox={`${beeld.x} ${beeld.y} ${beeld.b} ${beeld.h}`} preserveAspectRatio="xMidYMid meet"
      className={`block w-full select-none touch-none ${sleept ? "cursor-grabbing" : "cursor-grab"}`}
      // Het venster heeft de verhouding van de hele tekening, en wordt nooit hoger dan 60% van het scherm.
      style={{ fontFamily: "inherit", aspectRatio: `${alles.b} / ${alles.h}`, maxHeight: "60vh", minHeight: "8rem" }}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        sleep.current = { x: e.clientX, y: e.clientY, beeld, schaal: schaal(), bewogen: false };
      }}
      onPointerMove={(e) => {
        const s = sleep.current;
        if (!s) return;
        const dx = e.clientX - s.x, dy = e.clientY - s.y;
        if (!s.bewogen && Math.abs(dx) + Math.abs(dy) < 4) return;
        if (!s.bewogen) { s.bewogen = true; setSleept(true); svg.current?.setPointerCapture?.(e.pointerId); }
        setBeeld({ ...s.beeld, x: s.beeld.x - dx / s.schaal, y: s.beeld.y - dy / s.schaal });
      }}
      onPointerUp={(e) => {
        if (sleep.current?.bewogen) svg.current?.releasePointerCapture?.(e.pointerId);
        else sleep.current = null;
        setSleept(false);
      }}
      // Na echt slepen is de klik die volgt geen keuze.
      onClickCapture={(e) => {
        if (sleep.current?.bewogen) { e.stopPropagation(); e.preventDefault(); }
        sleep.current = null;
      }}>
      {lijnen.map((l) => {
        const gekozen = !!gekozenLijn && l.relatie_id === gekozenLijn;
        const voorstel = l.lifecycle === "voorgesteld";
        const kleur = gekozen ? RAND_CENTRAAL : "rgb(var(--muted))";
        const naam = lijnNaam(l, diagram.knopen);
        return (
          <g key={`${l.relatie_id}-${l.van}-${l.naar}-${l.code}`} data-diagram-lijn={l.relatie_id}
            {...(onKiesLijn && l.relatie_id ? {
              role: "button", tabIndex: 0, "aria-label": `Relatie: ${naam}`, "aria-pressed": gekozen,
              onClick: () => onKiesLijn(l),
              onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onKiesLijn(l); } },
              className: "cursor-pointer outline-none [&:focus-visible>rect.label]:stroke-lint",
            } : {})}>
            <title>{naam}{voorstel ? " (voorstel)" : ""}</title>
            {/* Een brede, onzichtbare lijn: anders is een lijn van 0,7 nauwelijks aan te klikken. */}
            {onKiesLijn && <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="transparent" strokeWidth={8} />}
            <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke={kleur} strokeWidth={gekozen ? 1.6 : 0.7}
              strokeDasharray={voorstel ? "3 2" : undefined} />
            <polygon points={pijlpunt(l)} fill={kleur} />
            <rect className="label" x={l.lx - l.lb / 2} y={l.ly - l.lh / 2} width={l.lb} height={l.lh} rx={1}
              fill="rgb(var(--paper))" stroke={gekozen ? RAND_CENTRAAL : "none"} strokeWidth={0.6} />
            {l.label.map((r, i) => (
              <text key={i} x={l.lx} y={l.ly - l.lh / 2 + MAAT.labelRegel * (i + 1) - 1.2} textAnchor="middle"
                fontSize={MAAT.label} fontStyle="italic" fill="rgb(var(--muted))">{r}</text>
            ))}
          </g>
        );
      })}
      {plaatsing.knopen.map((g) => {
        const k = g.knoop;
        const sleutel = knoopSleutel(k);
        const centraal = k.soort === "element" && k.id === diagram.centraal;
        const gekozen = sleutel === gekozenKnoop;
        const { vlak, rand: randkleur } = knoopKleuren(k.klasse);
        const naam = `${g.kop}: ${k.tekst}`;
        return (
          <g key={sleutel} data-diagram-knoop={sleutel}
            {...(onKiesKnoop ? {
              role: "button", tabIndex: 0, "aria-label": naam, "aria-pressed": gekozen,
              onClick: () => onKiesKnoop(k),
              onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onKiesKnoop(k); } },
              className: "cursor-pointer outline-none [&:focus-visible>rect.vak]:stroke-lint",
            } : {})}>
            <title>{naam}</title>
            <rect className="vak" x={g.x} y={g.y} width={g.b} height={g.h} rx={2} fill="rgb(var(--paper))"
              stroke={gekozen || centraal ? RAND_CENTRAAL : randkleur} strokeWidth={gekozen ? 2.4 : centraal ? 1.6 : 0.8}
              strokeDasharray={k.soort === "impliciet" ? "2 2" : undefined} />
            <rect x={g.x + 0.4} y={g.y + 0.4} width={g.b - 0.8} height={MAAT.kop - 0.4} fill={vlak} />
            <text x={g.x + 4} y={g.y + MAAT.kop - 3} fontSize={MAAT.kopTekst} fontWeight={600} fill="#1a1a1a"
              textLength={tekstbreedte(g.kop, MAAT.kopTekst, 600) > g.b - 8 ? g.b - 8 : undefined} lengthAdjust="spacingAndGlyphs">
              {g.kop}
            </text>
            {g.regels.map((r, i) => (
              <text key={i} x={g.x + 4} y={g.y + MAAT.kop + MAAT.marge + (i + 1) * MAAT.regel - 2}
                fontSize={MAAT.tekst} fill="rgb(var(--ink))"
                textLength={tekstbreedte(r, MAAT.tekst) > g.b - 8 ? g.b - 8 : undefined} lengthAdjust="spacingAndGlyphs">
                {r}
              </text>
            ))}
          </g>
        );
      })}
    </svg>
      {/* Dezelfde knoppen als de graaf, rechtsonder in het venster. */}
      <div className="pointer-events-none absolute bottom-2 right-2 flex">
        <GraafBeeld onPasIn={() => setBeeld(alles)} onZoom={(f) => zoom(f)} />
      </div>
    </div>
  );
}

let meetDoek: CanvasRenderingContext2D | null | undefined;

/** De breedte van een regel in de eenheden van de tekening (de lettergrootte is in dezelfde eenheden), gemeten met de
 *  letter van de pagina. Alleen om een regel die niet past iets in te persen, zoals de PDF hem iets kleiner zet; nooit
 *  afkappen: de tekst is letterlijk. Zonder canvas (de server, een test) een ruime schatting. */
function tekstbreedte(tekst: string, grootte: number, gewicht = 400): number {
  if (meetDoek === undefined) {
    meetDoek = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d");
  }
  if (!meetDoek) return tekst.length * grootte * 0.5;
  meetDoek.font = `${gewicht} 100px ${getComputedStyle(document.body).fontFamily}`;
  return (meetDoek.measureText(tekst).width / 100) * grootte;
}
