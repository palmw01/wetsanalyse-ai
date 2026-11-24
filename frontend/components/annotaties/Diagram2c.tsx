"use client";

import {
  MAAT, RAND_CENTRAAL, knoopKleuren, knoopSleutel, lijnNaam, pijlpunt, type DiagramData, type DiagramKnoop,
  type DiagramLijn,
} from "@/lib/diagram2c";

/** Het 2c-diagram rond één centrale formulering (Handleiding §3.4c), getekend uit wat de api uitrekende: hetzelfde
 *  plaatje als in het werkgebiedrapport, maar met knopen en lijnen die je kunt kiezen. Kleur draagt nooit alleen: elke
 *  knoop noemt zijn klasse, elke lijn haar relatie; een voorstel is gestippeld, een impliciete partij ook (haar rand).
 *
 *  Zonder `onKiesKnoop` en `onKiesLijn` is het een plaatje. De tekening schaalt mee met de breedte (`viewBox`). */
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
  return (
    <svg role={kiesbaar ? "group" : "img"} aria-label={label} data-diagram-2c={diagram.centraal}
      viewBox={`${-rand} ${-rand} ${plaatsing.breedte + 2 * rand} ${plaatsing.hoogte + 2 * rand}`}
      className="h-auto w-full select-none"
      // Nooit kleiner dan leesbaar: een eenheid is minstens 1,1 px (de tekst dan ~8 px). Is er minder ruimte, dan scrolt de
      // kaart eromheen in de breedte.
      style={{ fontFamily: "inherit", minWidth: `${Math.round((plaatsing.breedte + 2 * rand) * 1.1)}px` }}>
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
