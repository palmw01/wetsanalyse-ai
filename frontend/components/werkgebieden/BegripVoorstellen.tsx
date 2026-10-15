"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import {
  beantwoordVraag, besluitGroep, foutTekst, haalActieveBegrippenRun, haalGroepen, haalLaatsteBegrippenRun,
  koppelGroep, neemGroepenOver, startBegrippenRun, stopRun, volgRun,
} from "@/lib/api";
import {
  AANDACHT_LABEL, BESLUIT_LABEL, HYPOTHESE_LABEL, enigeDefinitie, groepenVanVraag, isBeslisbaar, overnameVoor,
  passageTekst, sorteerGroepen, voortgangsregel,
} from "@/lib/begripVoorstellen";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Betekenisgroep, BegrippenRun, GroepenAntwoord } from "@/lib/types";

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 coarse:min-h-[44px]";
const INGEKLAPT = "wa_voorstellen_ingeklapt";

const telling = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

const datum = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** De strook "Voorstellen van Lex" op de tab Begrippen (spoor D, levering 3a).
 *
 *  Lex draait de deterministische begrippenketen (ADR-004) op de passages van het werkgebied en stelt
 *  groepen voor: formuleringen die mogelijk één begrip aanduiden. De jurist beslist per groep:
 *  overnemen (ook splitsen of combineren), koppelen aan een bestaand begrip, afwijzen of parkeren.
 *  Een voorstel is geen begrip, en geen besluit wijzigt een annotatie. */
export function BegripVoorstellen({ id, onBegrip, onGewijzigd }: {
  id: string;
  /** Een overgenomen of gekoppeld begrip openen in de werkplek. */
  onBegrip: (begripId: string) => void;
  /** De begrippenlijst ernaast is veranderd (een overname maakt een begrip). */
  onGewijzigd: () => void;
}) {
  const [ingeklapt, setIngeklapt] = useState(false);
  const [data, setData] = useState<GroepenAntwoord | null>(null);
  const [laatste, setLaatste] = useState<BegrippenRun | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [voortgang, setVoortgang] = useState<string[]>([]);
  const [agentRun, setAgentRun] = useState<string | null>(null);
  const [gekozen, setGekozen] = useState<Set<string>>(new Set());     // groepen om te combineren
  const [combiNaam, setCombiNaam] = useState("");
  const kijker = useRef<AbortController | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setIngeklapt(localStorage.getItem(INGEKLAPT) === "1"); } catch { /* geen opslag */ }
  }, []);

  const laad = useCallback(async () => {
    try {
      const [g, l] = await Promise.all([haalGroepen(id), haalLaatsteBegrippenRun(id)]);
      setData(g);
      setLaatste(l);
    } catch (e) {
      setFout(foutTekst(e, "De voorstellen konden niet worden geladen."));
    }
  }, [id]);

  /** Meekijken met een lopende run; daarna opnieuw laden. Een `error` van Lex wordt een melding. */
  const volg = useCallback(async (runId: string) => {
    kijker.current?.abort();
    const ctl = new AbortController();
    kijker.current = ctl;
    setAgentRun(runId);
    setVoortgang([]);
    try {
      await volgRun(runId, { onStatus: (m) => setVoortgang((v) => [...v, voortgangsregel(m)]) }, 0, ctl.signal);
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      setFout(foutTekst(e, "Lex kon de voorstellen niet maken."));
    }
    if (ctl.signal.aborted) return;
    setAgentRun(null);
    await laad();
    onGewijzigd();
  }, [laad, onGewijzigd]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
    // Loopt er al een run voor dit werkgebied (een ander tabblad, of herladen), dan haken we aan.
    void haalActieveBegrippenRun(id).then((r) => {
      if (r && r !== "onbekend") void volg(r.run_id);
    });
    return () => kijker.current?.abort();
  }, [id, laad, volg]);

  async function start() {
    setFout(null);
    setMelding(null);
    try {
      const { agent_run_id } = await startBegrippenRun(id);
      if (agent_run_id) await volg(agent_run_id);
      else {
        await laad();
        setMelding("De voorstellen gelden al voor de huidige stand van het werkgebied; er viel niets nieuws te rekenen.");
      }
    } catch (e) {
      setFout(foutTekst(e, "Lex kon niet beginnen."));
    }
  }

  /** Een besluit uitvoeren; een fout (al besloten, al primair) verschijnt bij de strook. */
  async function besluit(actie: () => Promise<unknown>, na?: (uit: unknown) => void) {
    setFout(null);
    setMelding(null);
    try {
      const uit = await actie();
      await laad();
      onGewijzigd();
      na?.(uit);
      return true;
    } catch (e) {
      setFout(foutTekst(e));
      return false;
    }
  }

  function wisselIngeklapt() {
    setIngeklapt((v) => {
      try { localStorage.setItem(INGEKLAPT, v ? "0" : "1"); } catch { /* alleen deze sessie */ }
      return !v;
    });
  }

  const groepen = sorteerGroepen(data?.groepen ?? []);
  const open = groepen.filter(isBeslisbaar);
  const combi = groepen.filter((g) => gekozen.has(g.id));
  const run = laatste ?? data?.run ?? null;
  const vragen = data?.run?.uitkomst?.vragen ?? [];
  const relaties = data?.run?.uitkomst?.relaties ?? [];

  return (
    <section className="rounded-button border border-line bg-paper" aria-labelledby="voorstellen-kop">
      <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={wisselIngeklapt} aria-expanded={!ingeklapt}
          className="focus-ring flex items-center gap-1.5 rounded text-left">
          <ChevronOmlaag className={`transition-transform ${ingeklapt ? "-rotate-90" : ""}`} />
          <span id="voorstellen-kop" className="font-display text-sm font-semibold text-lint">Voorstellen van Lex</span>
          {open.length > 0 && <span className="text-xs text-muted">· {open.length} open</span>}
        </button>
        {agentRun ? (
          <Button size="sm" variant="secondary" className="w-full sm:w-auto" onClick={() => void stopRun(agentRun)}>
            Stoppen
          </Button>
        ) : (
          <Button size="sm" className="w-full sm:w-auto" onClick={() => void start()}>
            {run ? "Opnieuw voorstellen" : "Stel begrippen voor"}
          </Button>
        )}
      </div>

      {!ingeklapt && (
        <div className="space-y-4 border-t border-line px-4 py-3">
          {agentRun && (
            <ol className="space-y-0.5 text-xs text-muted" aria-live="polite" aria-label="Voortgang van Lex">
              {voortgang.length === 0 ? <li>Lex begint…</li> : voortgang.map((v, i) => <li key={i}>{v}</li>)}
            </ol>
          )}
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {melding && <Melding type="uitleg" compact>{melding}</Melding>}

          {run && !agentRun && (
            <div className="space-y-1 text-xs text-muted">
              <p>
                Laatste voorstel {datum(run.gewijzigd)} · {run.aantal_formuleringen} passages ·{" "}
                {telling(data?.groepen.length ?? 0, "groep", "groepen")} · {telling(vragen.length, "vraag", "vragen")}
                {run.status === "mislukt" && <span className="text-aandacht-geel-tekst"> · mislukt: {run.reden || "onbekend"}</span>}
              </p>
              {laatste?.verouderd && (
                <p className="text-aandacht-geel-tekst">
                  Gebaseerd op een oudere stand van het werkgebied (er kwamen passages of bronnen bij). Stel opnieuw voor om ze mee te nemen.
                </p>
              )}
              {run.overgeslagen.length > 0 && (
                <details>
                  <summary className="focus-ring cursor-pointer rounded">
                    {run.overgeslagen.length === 1 ? "1 passage" : `${run.overgeslagen.length} passages`} niet meegenomen
                  </summary>
                  <ul className="mt-1 space-y-0.5 pl-4">
                    {run.overgeslagen.map((o) => <li key={o.element_id}>“{o.tekst}” – {o.reden}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}

          {!run && !agentRun && data && (
            <p className="text-sm text-muted">
              Lex zoekt in de passages van dit werkgebied naar formuleringen die één begrip aanduiden – op grond van wat de wet zelf vastlegt
              (definities, “bedoeld in”). Een voorstel is een vraag aan jou, geen begrip.
            </p>
          )}

          {combi.length >= 2 && (
            <form
              className="flex flex-col gap-2 rounded-kaart border border-lint p-2 sm:flex-row sm:items-center"
              onSubmit={(e) => {
                e.preventDefault();
                const leden = new Set(combi.flatMap((g) => g.leden.map((l) => l.element_id)));
                void besluit(() => neemGroepenOver(id, overnameVoor(combi, leden, combiNaam || combi[0].voorstel.naam, true)),
                  (b) => { setGekozen(new Set()); setCombiNaam(""); onBegrip((b as { id: string }).id); });
              }}
            >
              <span className="text-sm text-ink">{combi.length} groepen samen als één begrip:</span>
              <Input value={combiNaam} onChange={(e) => setCombiNaam(e.target.value)} placeholder={combi[0].voorstel.naam}
                aria-label="Naam van het gecombineerde begrip" className="sm:w-56" />
              <Button type="submit" size="sm">Samen als één begrip</Button>
              <button type="button" className="focus-ring rounded text-xs text-muted underline" onClick={() => setGekozen(new Set())}>
                Annuleren
              </button>
            </form>
          )}

          {groepen.length > 0 && (
            <ul className="grid gap-3 lg:grid-cols-2" aria-label="Voorgestelde groepen">
              {groepen.map((g) => (
                <VoorstelKaart
                  key={g.id}
                  groep={g}
                  gekozen={gekozen.has(g.id)}
                  onKies={(aan) => setGekozen((s) => { const n = new Set(s); if (aan) n.add(g.id); else n.delete(g.id); return n; })}
                  onOvernemen={(naam, leden, metDef) => besluit(() => neemGroepenOver(id, overnameVoor([g], leden, naam, metDef)),
                    (b) => onBegrip((b as { id: string }).id))}
                  onKoppelen={(begripId) => besluit(() => koppelGroep(id, g.id, begripId), () => onBegrip(begripId))}
                  onBesluit={(soort, reden) => besluit(() => besluitGroep(id, g.id, soort, reden))}
                  onBegrip={onBegrip}
                />
              ))}
            </ul>
          )}

          {vragen.length > 0 && data?.run && (
            <section aria-labelledby="vragen-kop" className="space-y-2">
              <h3 id="vragen-kop" className="text-sm font-semibold text-lint">Twijfelvragen</h3>
              <ul className="space-y-2">
                {vragen.map((v) => {
                  const antwoord = data.run!.vragen_besluiten[v.kandidaat_id];
                  const vraagZin = `Horen ${passageTekst(v.van, data.passages, groepen)} en ${passageTekst(v.naar, data.passages, groepen)} bij hetzelfde begrip?`;
                  return (
                    <li key={v.kandidaat_id} className="rounded-kaart border border-line px-3 py-2 text-sm">
                      <p className="text-ink">{vraagZin}</p>
                      {v.uitleg.map((u) => <p key={u} className="text-xs text-muted">{u}</p>)}
                      {antwoord ? (
                        <p className="mt-1 text-xs text-muted">Beantwoord: {antwoord.antwoord} · {antwoord.door}</p>
                      ) : (
                        <div className="mt-1 flex gap-1.5">
                          {(["samen", "apart"] as const).map((a) => (
                            <button key={a} type="button" className={`${KNOP} border-line text-lint hover:bg-surface`}
                              aria-label={`${a === "samen" ? "Samen" : "Apart"}: ${vraagZin}`}
                              onClick={() => void besluit(() => beantwoordVraag(id, data.run!.id, v.kandidaat_id, a), () => {
                                if (a === "samen") setGekozen((s) => new Set([...s, ...groepenVanVraag(v, groepen)]));
                              })}>
                              {a === "samen" ? "Samen" : "Apart"}
                            </button>
                          ))}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {relaties.length > 0 && data && (
            <details className="text-sm">
              <summary className="focus-ring cursor-pointer rounded text-sm font-semibold text-lint">
                Relaties ({relaties.length}) – ter informatie
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-ink">
                {relaties.map((r) => (
                  <li key={r.kandidaat_id}>
                    {passageTekst(r.van, data.passages, groepen)} {HYPOTHESE_LABEL[r.hypothese] ?? r.hypothese}{" "}
                    {passageTekst(r.naar, data.passages, groepen)}
                    {r.aandacht === "geel" && <span className="text-aandacht-geel-tekst"> · {AANDACHT_LABEL.geel}</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

function VoorstelKaart({ groep: g, gekozen, onKies, onOvernemen, onKoppelen, onBesluit, onBegrip }: {
  groep: Betekenisgroep;
  gekozen: boolean;
  onKies: (aan: boolean) => void;
  onOvernemen: (naam: string, leden: Set<string>, metDefinitie: boolean) => Promise<boolean>;
  onKoppelen: (begripId: string) => Promise<boolean>;
  onBesluit: (soort: "afwijzen" | "parkeren" | "heropenen", reden?: string) => Promise<boolean>;
  onBegrip: (begripId: string) => void;
}) {
  const [leden, setLeden] = useState<Set<string>>(() => new Set(g.leden.map((l) => l.element_id)));
  const [naam, setNaam] = useState(g.voorstel.naam);
  const definitie = enigeDefinitie([g]);
  const [metDef, setMetDef] = useState(!!definitie);
  const [modus, setModus] = useState<null | "overnemen" | "afwijzen" | "parkeren">(null);
  const [reden, setReden] = useState("");
  const beslisbaar = isBeslisbaar(g);
  const naamVoorLabel = `groep “${g.voorstel.naam}”`;

  return (
    <li className={`rounded-kaart border bg-paper px-3 py-2 ${gekozen ? "border-lint" : "border-line"} ${beslisbaar ? "" : "opacity-75"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-display text-sm font-semibold text-lint">{g.voorstel.naam}</p>
          <p className="text-[11px] text-muted">
            <span className={g.aandacht === "geel" ? "text-aandacht-geel-tekst" : ""}>{AANDACHT_LABEL[g.aandacht]}</span>
            {" · "}{g.leden.length} passages
            {!beslisbaar || g.besluit === "geparkeerd" ? ` · ${BESLUIT_LABEL[g.besluit]}` : ""}
          </p>
        </div>
        {beslisbaar && (
          <label className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted">
            <input type="checkbox" checked={gekozen} onChange={(e) => onKies(e.target.checked)}
              aria-label={`Kies ${naamVoorLabel} om te combineren`} className="focus-ring accent-lint" />
            combineren
          </label>
        )}
      </div>

      {definitie && (
        <p className="mt-1 text-xs text-ink">
          <span className="text-muted">Brondefinitie ({definitie.vindplaats}): </span>“{definitie.tekst}”
        </p>
      )}

      <ul className="mt-2 space-y-1" aria-label={`Passages van ${naamVoorLabel}`}>
        {g.leden.map((l) => (
          <li key={l.element_id} className="flex items-start gap-2 text-sm">
            {beslisbaar && (
              <input type="checkbox" checked={leden.has(l.element_id)} className="focus-ring mt-1 accent-lint"
                aria-label={`Neem “${l.tekst}” mee`}
                onChange={(e) => setLeden((s) => { const n = new Set(s); if (e.target.checked) n.add(l.element_id); else n.delete(l.element_id); return n; })} />
            )}
            <span className="min-w-0">
              <span className={`mr-1 inline-flex rounded-full border px-1.5 text-[10px] ${jasStyle(l.jas_klasse)}`}>{klasseLabel(l.jas_klasse)}</span>
              <span className="text-ink">“{l.tekst}”</span>{" "}
              <span className="text-xs text-muted">{l.vindplaats}</span>
              {l.review_status === "voorgesteld" && <span className="text-xs text-aandacht-geel-tekst"> · annotatie nog niet beoordeeld</span>}
            </span>
          </li>
        ))}
      </ul>

      {g.uitleg.length > 0 && <ul className="mt-1 space-y-0.5 text-xs text-muted">{g.uitleg.map((u) => <li key={u}>{u}</li>)}</ul>}
      {g.conflicten.length > 0 && (
        <p className="mt-1 text-xs text-aandacht-geel-tekst">
          Er is ook bewijs dat ze níét hetzelfde betekenen ({g.conflicten.length}); beoordeel de passages zelf.
        </p>
      )}

      {g.lijkt_op.length > 0 && beslisbaar && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">
          Lijkt op:
          {g.lijkt_op.map((b) => (
            <button key={b.begrip_id} type="button" className={`${KNOP} border-line text-lint hover:bg-surface`}
              aria-label={`Koppel ${naamVoorLabel} aan het begrip ${b.naam}`} onClick={() => void onKoppelen(b.begrip_id)}>
              Koppelen aan {b.naam}
            </button>
          ))}
        </div>
      )}

      {beslisbaar ? (
        modus === "overnemen" ? (
          <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); void onOvernemen(naam, leden, metDef).then((ok) => ok && setModus(null)); }}>
            <Input value={naam} onChange={(e) => setNaam(e.target.value)} aria-label={`Naam van het begrip uit ${naamVoorLabel}`} maxLength={200} />
            {definitie && (
              <label className="flex items-center gap-1.5 text-xs text-ink">
                <input type="checkbox" checked={metDef} onChange={(e) => setMetDef(e.target.checked)} className="focus-ring accent-lint" />
                Neem de brondefinitie letterlijk over
              </label>
            )}
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="submit" size="sm" disabled={!naam.trim() || leden.size === 0}>
                Overnemen{leden.size < g.leden.length ? ` (${leden.size} van ${g.leden.length})` : ""}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={() => setModus(null)}>Annuleren</Button>
            </div>
          </form>
        ) : modus ? (
          <form className="mt-2 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); void onBesluit(modus, reden).then((ok) => ok && setModus(null)); }}>
            <Input value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Reden" aria-label={`Reden om ${naamVoorLabel} ${modus === "afwijzen" ? "af te wijzen" : "te parkeren"}`} />
            <Button type="submit" size="sm" variant="secondary">{modus === "afwijzen" ? "Afwijzen" : "Parkeren"}</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setModus(null)}>Annuleren</Button>
          </form>
        ) : (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button type="button" className={`${KNOP} border-lint text-lint hover:bg-surface`} aria-label={`Neem ${naamVoorLabel} over als begrip`} onClick={() => setModus("overnemen")}>
              Overnemen als begrip
            </button>
            <button type="button" className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`} aria-label={`Wijs ${naamVoorLabel} af`} onClick={() => setModus("afwijzen")}>
              Afwijzen
            </button>
            {g.besluit === "open" && (
              <button type="button" className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`} aria-label={`Parkeer ${naamVoorLabel}`} onClick={() => setModus("parkeren")}>
                Parkeren
              </button>
            )}
            {g.besluit === "geparkeerd" && (
              <button type="button" className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`} aria-label={`Heropen ${naamVoorLabel}`} onClick={() => void onBesluit("heropenen")}>
                Heropenen
              </button>
            )}
          </div>
        )
      ) : (
        <p className="mt-2 text-xs text-muted">
          {g.begrip_id ? (
            <>
              {BESLUIT_LABEL[g.besluit]}:{" "}
              <button type="button" className="focus-ring rounded text-lint underline" onClick={() => onBegrip(g.begrip_id!)}>begrip openen</button>
            </>
          ) : (
            <>
              {BESLUIT_LABEL[g.besluit]}{g.reden ? `: ${g.reden}` : ""} ·{" "}
              <button type="button" className="focus-ring rounded text-lint underline" aria-label={`Heropen ${naamVoorLabel}`} onClick={() => void onBesluit("heropenen")}>
                heropenen
              </button>
            </>
          )}
        </p>
      )}
    </li>
  );
}
