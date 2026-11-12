"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { Select } from "@/components/ui/Field";
import { Regel, Regels, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Meter } from "@/components/ui/Meter";
import { haalContextBoom } from "@/lib/api";
import {
  adviezen, beginKoud, beginTekst, boomVerbruik, contextRegel, grootste, hoofdagent, kindRijen, kort, legenda, lijn,
  procent, profielTekst, raster, rolLabel, signaal, totaalVerbruik, verloop,
  type Beurt, type ContextAgent, type ContextBoom, type Contextopbouw, type KindRij,
} from "@/lib/contextweergave";

/** De contextweergave (plan contextweergave, ADR-015): wat `/context` in Claude Code laat zien, voor Lex. Eén component
 *  met twee ingangen: de **contextmeter** bij het invoerveld en het **paneel** naast het gesprek (`ContextPaneel`, soort
 *  `contextopbouw`). Het rekenwerk staat in `lib/contextweergave.ts`, het register van de categorieën in
 *  `lib/contextdelen.ts`.
 *
 *  Een weergave, geen artefact: je besluit hier niets, en er staat geen knop die Lex start. */

/** De beurten met een meting van het gesprek dat openstaat; de werkplek vult het (uit de berichten en uit het
 *  `meting`-event van een lopende beurt). Zonder (de rondleiding, buiten de werkplek) is er niets te tonen. */
export const ContextopbouwContext = createContext<{ gesprekId: string | null; beurten: Beurt[] } | null>(null);

/** Hoe breed het lijntje van het verloop is getekend; het schaalt mee met het paneel. */
const VERLOOP = { breedte: 240, hoogte: 40 };

// ── De meter bij het invoerveld ──────────────────────────────────────────────────────────────────────────────────────

/** De contextmeter: de omvang van het laatste verzoek en het deel van het venster dat het vult. Een stip (met tekst voor
 *  een schermlezer) zodra er iets speelt: de historie is ingekort, er vielen beurten weg, of de beurt begon koud. Een
 *  klik opent het paneel; de tooltip noemt de drie grootste delen en het verbruik van de beurt. */
export function ContextMeter({ beurten, heeftBeurten, onOpen }: {
  beurten: Beurt[];
  /** Er staan al beurten in het gesprek: zonder meting zegt de meter dan "nog niet gemeten". */
  heeftBeurten: boolean;
  onOpen: () => void;
}) {
  const laatste = beurten.at(-1)?.contextopbouw;
  const vorige = beurten.at(-2)?.contextopbouw;
  const agent = hoofdagent(laatste);
  if (!laatste && !heeftBeurten) return null;
  const letOp = laatste ? signaal(laatste, vorige) : undefined;
  const regels = !laatste ? ["De context van dit gesprek is nog niet gemeten."]
    : !agent ? [`Verbruik van de laatste beurt: ${kort(totaalVerbruik(laatste.som))}.`]
    : [
      `Context van de laatste beurt: ${kort(agent.laatste.totaal)}, ${procent(agent.laatste.totaal, agent.venster)} van het venster.`,
      `Grootste delen: ${grootste(agent).map((r) => `${r.deel.label} ${kort(r.omvang)}`).join(" · ")}.`,
      `Verbruik van deze beurt: ${kort(totaalVerbruik(laatste.som))}.`,
      ...(letOp ? [letOp.tekst] : []),
    ];
  const tekst = !laatste ? "nog niet gemeten" : agent ? contextRegel(agent) : kort(totaalVerbruik(laatste.som));
  return (
    <button type="button" data-contextmeter data-signaal={letOp?.id} onClick={onOpen} title={regels.join("\n")}
      aria-label={`Context: ${regels.join(" ")} Open de contextweergave.`}
      className="focus-ring inline-flex shrink-0 items-center gap-1.5 rounded-knop-xs px-1.5 py-1 text-xs text-muted hover:text-ink coarse:min-h-11">
      {agent && <Meter percentage={(agent.laatste.totaal / Math.max(agent.venster, 1)) * 100} label="Context van het venster"
        toon="verbruik" dun className="w-10" />}
      <span className="whitespace-nowrap tabular-nums">{tekst}</span>
      {letOp && <span aria-hidden="true" data-contextsignaal className="h-1.5 w-1.5 rounded-full bg-waarschuwing" />}
    </button>
  );
}

// ── Het paneel ───────────────────────────────────────────────────────────────────────────────────────────────────────

/** De inhoud van het paneel *Context van deze beurt*: de beurtkiezer, per agent de context, het verbruik, de boom, het
 *  verloop, de adviezen en de details per aanroep. */
export function ContextopbouwInhoud() {
  const stand = useContext(ContextopbouwContext);
  const beurten = useMemo(() => stand?.beurten ?? [], [stand]);
  const gesprekId = stand?.gesprekId ?? null;
  // Standaard de laatste beurt; een gekozen beurt blijft staan tot hij er niet meer is.
  const [gekozen, setGekozen] = useState<string | null>(null);
  const index = gekozen === null ? beurten.length - 1 : Math.max(beurten.findIndex((b) => b.run_id === gekozen), -1);
  const plek = index === -1 ? beurten.length - 1 : index;
  const beurt = beurten[plek];
  const boom = useBoom(gesprekId, beurten.length);

  const bekend = beurten.map((b) => b.run_id);
  if (!beurt) {
    // Geen gemeten beurt in dit gesprek zelf. Een regie gebruikt geen model, maar haar deelgesprekken wel: die staan er dan.
    const los = kindRijen(boom.boom, "", true, bekend);
    return <>
      <p data-context-leeg className="text-sm text-muted">
        In dit gesprek is nog geen beurt gemeten. Een beurt zonder model (een overzicht uit de kennisgraaf, een vaste
        handeling, het verdelen van werk over deelgesprekken) heeft geen context, en een bericht van vóór de meting ook niet.
      </p>
      {(los.length > 0 || boom.fout) && <Boom kinderen={los} fout={boom.fout} />}
    </>;
  }
  const c = beurt.contextopbouw;
  const vorige = beurten[plek - 1]?.contextopbouw;
  const kinderen = kindRijen(boom.boom, c.run_id, plek === beurten.length - 1, bekend);
  const punten = verloop(beurten);
  return <>
    {beurten.length > 1 && (
      <label className="block text-sm">
        <span className="mb-1 block text-xs text-muted">Beurt</span>
        <Select data-context-beurtkiezer value={beurt.run_id} aria-label="Kies een beurt"
          onChange={(e) => setGekozen(e.target.value === beurten.at(-1)?.run_id ? null : e.target.value)}>
          {beurten.map((b, i) => (
            <option key={b.run_id || i} value={b.run_id}>
              {i === beurten.length - 1 ? `Beurt ${i + 1} (de laatste)` : `Beurt ${i + 1}`}
            </option>
          ))}
        </Select>
      </label>
    )}
    <Beurtkaart c={c} vorige={vorige} />
    {(kinderen.length > 0 || boom.fout) && <Boom c={c} kinderen={kinderen} fout={boom.fout} />}
    {punten.length > 1 && <Verloop punten={punten} plek={plek} />}
  </>;
}

/** De boom bij het lezen: de contextopbouw van de deelgesprekken. Faalt het ophalen, dan zegt het paneel dat; de eigen
 *  context staat er dan nog. */
function useBoom(gesprekId: string | null, versie: number): { boom?: ContextBoom; fout: boolean } {
  const [uit, setUit] = useState<{ boom?: ContextBoom; fout: boolean }>({ fout: false });
  useEffect(() => {
    if (!gesprekId) return;
    let levend = true;
    haalContextBoom(gesprekId).then((boom) => levend && setUit({ boom, fout: false }))
      .catch(() => levend && setUit((s) => ({ ...s, fout: true })));
    return () => { levend = false; };
  }, [gesprekId, versie]);
  return uit;
}

/** Eén beurt: per agent met een toollus de context, dan het verbruik, de adviezen en de details. Dezelfde kaart voor de
 *  eigen beurt en voor een deelgesprek. */
function Beurtkaart({ c, vorige, kind = false }: { c: Contextopbouw; vorige?: Contextopbouw; kind?: boolean }) {
  const tips = kind ? [] : adviezen(c, vorige);
  return <>
    {c.agenten.length
      ? c.agenten.map((a) => <AgentContext key={a.rol} agent={a} meer={c.agenten.length > 1} />)
      : <Sectie titel="Context" niveau={3}>
          <p className="text-sm text-muted">Deze beurt had geen agent die in rondes werkt, dus er is geen context die groeit.
            Wat de beurt kostte, staat hieronder.</p>
        </Sectie>}
    <VerbruikBlok c={c} />
    {tips.length > 0 && (
      <Sectie titel="Wat je kunt doen" niveau={3} data-context-adviezen>
        <ul className="space-y-1.5 text-sm text-ink">
          {tips.map((t) => <li key={t.id} data-advies={t.id}>{t.tekst}</li>)}
        </ul>
      </Sectie>
    )}
    <Details c={c} />
  </>;
}

function AgentContext({ agent, meer }: { agent: ContextAgent; meer: boolean }) {
  const regels = legenda(agent);
  const vakjes = raster(agent);
  const beschrijving = `Samenstelling van het verzoek: ${regels.map((r) => `${r.deel.label} ${r.aandeel}`).join(", ")}.`;
  return (
    <Sectie titel={meer ? `Context · ${rolLabel(agent.rol)}` : "Context"} niveau={3} data-context-agent={agent.rol}
      toelichting="Het laatste verzoek van deze beurt. Lex bouwt de context bij elke beurt opnieuw op.">
      {profielTekst(agent) && <p data-context-profiel className="break-words text-xs text-muted">Profiel: {profielTekst(agent)}</p>}
      <p data-context-regel className="text-sm text-ink">
        <span className="font-semibold tabular-nums">{kort(agent.laatste.totaal)}</span>
        {agent.venster > 0 && <> · {procent(agent.laatste.totaal, agent.venster)} van het venster ({kort(agent.venster)})</>}
      </p>
      <div role="img" aria-label={beschrijving} data-context-raster
        className="grid grid-cols-[repeat(20,minmax(0,1fr))] gap-0.5">
        {vakjes.map((d, i) => <span key={i} data-vakje={d.id} className={`aspect-square rounded-[2px] ${d.kleur}`} />)}
      </div>
      <ul data-context-legenda className="divide-y divide-line text-sm">
        {regels.map((r) => (
          <li key={r.deel.id} data-categorie={r.deel.id} title={r.deel.uitleg} className="flex items-baseline gap-2 py-1.5">
            <span aria-hidden="true" className={`h-2.5 w-2.5 shrink-0 translate-y-px rounded-[2px] ${r.deel.kleur}`} />
            <span className="min-w-0 flex-1 text-ink">
              {r.deel.label}
              {r.grens !== undefined && <span className="block text-xs text-muted">grens ≈ {kort(r.grens)}; daarboven kort Lex oudere beurten in</span>}
            </span>
            <span className="shrink-0 tabular-nums text-muted">≈ {kort(r.omvang)}</span>
            <span className="w-14 shrink-0 text-right tabular-nums text-muted">{r.aandeel}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        Het totaal is exact. De verdeling over de delen is een schatting (≈)
        {agent.laatste.voorvoegsel.exact
          ? <>; het vaste deel (instructies, methode en tools) is samen exact {kort(agent.laatste.voorvoegsel.omvang)}.</>
          : "."}
      </p>
      <p data-context-begin={beginKoud(agent) ? "koud" : "warm"} className="text-sm text-ink">{beginTekst(agent)}</p>
    </Sectie>
  );
}

function VerbruikBlok({ c }: { c: Contextopbouw }) {
  const totaal = totaalVerbruik(c.som);
  return (
    <Sectie titel="Verbruik van deze beurt" niveau={3} data-context-verbruik
      toelichting="Alles wat het model in de hele beurt las en schreef, over alle rondes. Dit telt voor je budget.">
      <Regels>
        <Regel naam="Totaal"><span data-verbruik-totaal className="font-semibold tabular-nums">{kort(totaal)}</span></Regel>
        <Regel naam="Uit de cache gelezen"><Getal n={c.som.cache_lees} van={totaal} /></Regel>
        <Regel naam="Naar de cache geschreven"><Getal n={c.som.cache_schrijf} van={totaal} /></Regel>
        <Regel naam="Nieuw gelezen"><Getal n={c.som.invoer} van={totaal} /></Regel>
        <Regel naam="Geschreven door Lex"><Getal n={c.som.uitvoer} van={totaal} /></Regel>
      </Regels>
      {c.verbruik.length > 1 && (
        <ul data-verbruik-rollen className="divide-y divide-line text-sm">
          {c.verbruik.map((v) => (
            <li key={v.rol} className="flex items-baseline gap-2 py-1.5">
              <span className="min-w-0 flex-1 text-ink">{rolLabel(v.rol)}
                <span className="block text-xs text-muted">{v.aanroepen === 1 ? "1 aanroep" : `${v.aanroepen} aanroepen`}</span></span>
              <span className="shrink-0 tabular-nums text-muted">{kort(totaalVerbruik(v))}</span>
            </li>
          ))}
        </ul>
      )}
    </Sectie>
  );
}

function Getal({ n, van }: { n: number; van: number }) {
  return <span className="tabular-nums">{kort(n)} <span className="text-muted">· {procent(n, van)}</span></span>;
}

/** De deelgesprekken van deze beurt: per kind een rij die dezelfde kaart opent, en het verbruik van de boom. */
function Boom({ c, kinderen, fout }: { c?: Contextopbouw; kinderen: KindRij[]; fout: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const som = boomVerbruik(c, kinderen);
  return (
    <Sectie titel="Deelgesprekken" niveau={3} data-context-boom
      toelichting="Elk deelgesprek heeft een eigen context. Zijn verbruik telt mee in je budget.">
      {fout && <Melding type="waarschuwing" compact>De deelgesprekken konden niet worden geladen.</Melding>}
      {kinderen.length > 0 && <>
        <ul className="divide-y divide-line">
          {kinderen.map((k) => (
            <li key={k.gesprek_id} data-context-kind={k.gesprek_id}>
              <button type="button" aria-expanded={open === k.gesprek_id} disabled={!k.gemeten}
                onClick={() => setOpen(open === k.gesprek_id ? null : k.gesprek_id)}
                className="focus-ring flex w-full items-baseline gap-2 rounded-md px-1 py-2 text-left hover:bg-surface disabled:hover:bg-transparent coarse:min-h-11">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{k.titel || "Deelgesprek"}</span>
                  <span className="block text-xs text-muted">
                    {k.gemeten
                      ? <>{k.context && profielTekst(k.context) ? `${profielTekst(k.context)} · ` : ""}
                          {k.context ? `context ${contextRegel(k.context)} · ` : ""}
                          {k.beurten.length > 1 ? `${k.beurten.length} beurten · ` : ""}verbruik {kort(k.verbruik)}</>
                      : "loopt nog, of niet gemeten"}
                  </span>
                </span>
                {!k.gemeten && <StatusLabel toon="neutraal">niet gemeten</StatusLabel>}
              </button>
              {open === k.gesprek_id && k.beurten.map((b, i) => (
                // Elke beurt van het kind: de rij telt ze samen, dus de kaart toont ze allemaal.
                <div key={b.run_id || i} data-kind-beurt className="space-y-4 border-l border-line py-2 pl-3">
                  {k.beurten.length > 1 && <p className="text-xs font-semibold text-muted">Beurt {i + 1} van {k.beurten.length}</p>}
                  <Beurtkaart c={b.contextopbouw} kind />
                </div>
              ))}
            </li>
          ))}
        </ul>
        <p data-boom-totaal className="text-sm text-ink">
          {c ? "Deze beurt met haar deelgesprekken" : "De deelgesprekken samen"}: <span className="font-semibold tabular-nums">{som.volledig ? "" : "minstens "}{kort(som.totaal)}</span>.
          {!som.volledig && " Niet elk deelgesprek is gemeten, dus het totaal is onvolledig."}
        </p>
      </>}
    </Sectie>
  );
}

/** Het verloop over het gesprek: per beurt de omvang van de context en het verbruik, als twee lijntjes. */
function Verloop({ punten, plek }: { punten: { context: number; verbruik: number }[]; plek: number }) {
  const { breedte, hoogte } = VERLOOP;
  const context = punten.map((p) => p.context), verbruik = punten.map((p) => p.verbruik);
  const beschrijving = `Verloop over ${punten.length} beurten. Context: van ${kort(context[0])} naar ${kort(context.at(-1) ?? 0)}. `
    + `Verbruik per beurt: van ${kort(verbruik[0])} naar ${kort(verbruik.at(-1) ?? 0)}.`;
  const x = punten.length > 1 ? (plek * breedte) / (punten.length - 1) : 0;
  return (
    <Sectie titel="Verloop in dit gesprek" niveau={3} data-context-verloop>
      <svg viewBox={`0 -2 ${breedte} ${hoogte + 4}`} role="img" aria-label={beschrijving} preserveAspectRatio="none"
        className="h-12 w-full overflow-visible">
        <line x1={x} x2={x} y1={0} y2={hoogte} className="stroke-line" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        <polyline points={lijn(verbruik, breedte, hoogte)} fill="none" className="stroke-muted" strokeWidth={1.5}
          strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
        <polyline points={lijn(context, breedte, hoogte)} fill="none" className="stroke-lint" strokeWidth={1.5}
          vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="text-xs text-muted">
        Doorgetrokken: de context per beurt (nu {kort(context[plek])}). Gestippeld: het verbruik per beurt (nu {kort(verbruik[plek])}).
        Elk lijntje heeft zijn eigen schaal.
      </p>
    </Sectie>
  );
}

/** Het detail per modelaanroep, ingeklapt: cache, uitvoer, duur en de vingerafdrukken van het vaste deel. */
function Details({ c }: { c: Contextopbouw }) {
  if (!c.aanroepen.length) return null;
  return (
    <details data-context-details className="text-sm">
      <summary className="focus-ring cursor-pointer rounded-md py-1 text-muted hover:text-ink">
        Details per aanroep ({c.aanroepen.length})
      </summary>
      <ol className="mt-2 divide-y divide-line">
        {c.aanroepen.map((a, i) => (
          <li key={i} className="py-1.5">
            <span className="block text-ink">{i + 1}. {rolLabel(a.rol)} · <span className="tabular-nums">{kort(a.totaal)}</span></span>
            <span className="block text-xs tabular-nums text-muted">
              cache gelezen {kort(a.cache_lees)} · geschreven {kort(a.cache_schrijf)} · nieuw {kort(a.invoer)} · uitvoer {kort(a.uitvoer)}
              {a.ms > 0 && <> · {(a.ms / 1000).toLocaleString("nl-NL", { maximumFractionDigits: 1 })} s</>}
            </span>
            {(a.tools_hash || a.system_hash) && (
              <span className="block break-all font-mono text-xs text-faint">
                tools {a.tools_hash || "–"} · instructies {a.system_hash || "–"}
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-muted">
        De twee codes zijn vingerafdrukken van de tools en de instructies. Verschillen ze van de vorige beurt, dan is het
        vaste deel opnieuw geschreven.
      </p>
    </details>
  );
}
