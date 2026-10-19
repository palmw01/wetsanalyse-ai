"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { BegripReview } from "@/components/werkgebieden/BegripReview";
import { MeedenkBevestiging } from "@/components/werkgebieden/MeedenkBevestiging";
import {
  foutTekst, haalActieveBegrippenRun, haalGroepen, haalLaatsteBegrippenRun, haalVerdieping, startBegrippenRun, stopRun,
  volgRun,
} from "@/lib/api";
import { hypotheseZin } from "@/lib/begripRelaties";
import {
  AANDACHT_LABEL, meedenkOmvang, openVragen, passageTekst, reviewVoortgang, voortgangsregel,
} from "@/lib/begripVoorstellen";
import type { BegrippenRun, GroepenAntwoord, VerdiepingWerkvoorraad } from "@/lib/types";

const INGEKLAPT = "wa_voorstellen_ingeklapt";

const telling = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

const datum = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** De strook "Voorstellen van Lex" op de tab Begrippen (spoor D, levering 3a) en in het artefactpaneel.
 *
 *  Lex draait de deterministische begrippenketen (ADR-004) op de passages van het werkgebied en stelt
 *  groepen voor: formuleringen die mogelijk één begrip aanduiden. De strook draagt het starten, de
 *  voortgang, het aanbod om mee te denken (fase C) en de relaties; het beoordelen zelf is de
 *  reviewlijst `BegripReview` (fase D). Een voorstel is geen begrip, en geen besluit wijzigt een
 *  annotatie. */
export function BegripVoorstellen({ id, runId, onBegrip, onGewijzigd, inklapbaar = true, onMeedenken }: {
  id: string;
  /** De ronde waar een artefact in het gesprek naar wijst. De voorstellen zijn altijd die van de
   *  laatste ronde – daar wordt verder beoordeeld –, maar is dat een andere, dan zegt de strook dat. */
  runId?: string;
  /** Na de bevestiging om mee te denken (fase C). Zonder: de werkplek opent in dit werkgebied met een
   *  vers gesprek en start daar (`/workbench?werkgebied=<id>&meedenk=<n>`), zoals annoteren in fase B. */
  onMeedenken?: (aantal: number) => void;
  /** Op de tab Begrippen een strook die je kunt inklappen; in het artefactpaneel is hij de hele
   *  inhoud en staat hij altijd open. */
  inklapbaar?: boolean;
  /** Een overgenomen of gekoppeld begrip openen in de werkplek. */
  onBegrip: (begripId: string) => void;
  /** De begrippenlijst ernaast is veranderd (een overname maakt een begrip). */
  onGewijzigd: () => void;
}) {
  const [ingeklaptBewaard, setIngeklapt] = useState(false);
  const ingeklapt = inklapbaar && ingeklaptBewaard;
  const [data, setData] = useState<GroepenAntwoord | null>(null);
  const [laatste, setLaatste] = useState<BegrippenRun | null>(null);
  const router = useRouter();
  // Wat Lex nog kan verdiepen (fase C). Lukt dat niet, dan geen aanbod: de voorstellen staan er wel.
  const [verdieping, setVerdieping] = useState<VerdiepingWerkvoorraad | null>(null);
  const [meedenkOpen, setMeedenkOpen] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [voortgang, setVoortgang] = useState<string[]>([]);
  const [agentRun, setAgentRun] = useState<string | null>(null);
  const kijker = useRef<AbortController | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setIngeklapt(localStorage.getItem(INGEKLAPT) === "1"); } catch { /* geen opslag */ }
  }, []);

  const laad = useCallback(async (): Promise<GroepenAntwoord | null> => {
    try {
      const [g, l, v] = await Promise.all([haalGroepen(id), haalLaatsteBegrippenRun(id),
        haalVerdieping(id).catch(() => null)]);
      setData(g);
      setLaatste(l);
      setVerdieping(v && Array.isArray(v.vragen) && Array.isArray(v.batches) ? v : null);
      return g;
    } catch (e) {
      setFout(foutTekst(e, "De voorstellen konden niet worden geladen."));
      return null;
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

  function wisselIngeklapt() {
    setIngeklapt((v) => {
      try { localStorage.setItem(INGEKLAPT, v ? "0" : "1"); } catch { /* alleen deze sessie */ }
      return !v;
    });
  }

  const review = reviewVoortgang(data);
  const teGaan = review.totaal - review.beslist;
  const run = laatste ?? data?.run ?? null;
  const vragen = openVragen(data);
  const kanMeedenken = !!verdieping && !verdieping.verdiept && verdieping.aantal > 0 && !agentRun;
  const relaties = data?.run?.uitkomst?.relaties ?? [];

  return (
    <section data-begripvoorstellen className="rounded-button border border-line bg-paper" aria-labelledby="voorstellen-kop">
      <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        {inklapbaar ? (
          <button type="button" onClick={wisselIngeklapt} aria-expanded={!ingeklapt}
            className="focus-ring flex items-center gap-1.5 rounded text-left">
            <ChevronOmlaag className={`transition-transform ${ingeklapt ? "-rotate-90" : ""}`} />
            <span id="voorstellen-kop" className="font-display text-sm font-semibold text-lint">Voorstellen van Lex</span>
            {teGaan > 0 && <span className="text-xs text-muted">· {teGaan} te beoordelen</span>}
          </button>
        ) : (
          <p className="flex items-center gap-1.5">
            <span id="voorstellen-kop" className="font-display text-sm font-semibold text-lint">Voorstellen van Lex</span>
            {teGaan > 0 && <span className="text-xs text-muted">· {teGaan} te beoordelen</span>}
          </p>
        )}
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
          {runId && laatste && laatste.id !== runId && !agentRun && (
            <Melding type="uitleg" compact>
              Dit gesprek wijst naar een eerdere ronde van Lex. Hieronder staan de voorstellen van de laatste
              ronde ({datum(laatste.gewijzigd)}): daar beoordeel je verder.
            </Melding>
          )}

          {run && !agentRun && (
            <div className="space-y-1 text-xs text-muted">
              <p>
                Laatste voorstel {datum(run.gewijzigd)} · {run.aantal_formuleringen} passages ·{" "}
                {telling(data?.groepen.length ?? 0, "groep", "groepen")} · {telling(vragen.length, "vraag", "vragen")}
                {run.status === "mislukt" && <span className="text-aandacht-geel-tekst"> · mislukt: {run.reden || "onbekend"}</span>}
              </p>
              {data?.verdieping && (
                <p>Lex dacht mee{data.verdieping.op ? ` op ${datum(data.verdieping.op)}` : ""}: advies bij de twijfelvragen en
                  een kaart per groep. Een definitie die Lex formuleerde, staat geel.</p>
              )}
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

          {kanMeedenken && verdieping && (
            <div className="flex flex-col gap-2 rounded-kaart border border-line bg-surface/40 p-3 sm:flex-row sm:items-center sm:justify-between"
              data-meedenk-aanbod={verdieping.aantal}>
              <p className="text-sm text-ink">
                Lex kan meedenken over {meedenkOmvang({ vragen: verdieping.vragen.length, kaarten: verdieping.kaarten.length })}:
                advies bij twijfel, en een definitie uit de bron of door Lex geformuleerd. Dat kost tokens.
              </p>
              <Button size="sm" className="w-full shrink-0 sm:w-auto" onClick={() => setMeedenkOpen(true)}>
                Laat Lex meedenken ({verdieping.aantal})
              </Button>
            </div>
          )}
          {meedenkOpen && verdieping && (
            <MeedenkBevestiging werkvoorraad={verdieping} onSluit={() => setMeedenkOpen(false)}
              onBevestig={(aantal) => {
                setMeedenkOpen(false);
                if (onMeedenken) onMeedenken(aantal);
                else router.push(`/workbench?werkgebied=${encodeURIComponent(id)}&meedenk=${aantal}`);
              }} />
          )}

          {!run && !agentRun && data && (
            <p className="text-sm text-muted">
              Lex zoekt in de passages van dit werkgebied naar formuleringen die één begrip aanduiden – op grond van wat de wet zelf vastlegt
              (definities, “bedoeld in”). Een voorstel is een vraag aan jou, geen begrip.
            </p>
          )}

          {data && data.run && (data.groepen.length > 0 || vragen.length > 0) && (
            <BegripReview id={id} data={data} onHerlaad={laad} onBegrip={onBegrip} onGewijzigd={onGewijzigd} />
          )}

          {relaties.length > 0 && data && (
            <details className="text-sm">
              <summary className="focus-ring cursor-pointer rounded text-sm font-semibold text-lint">
                Relaties ({relaties.length}) – ter informatie
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-ink">
                {relaties.map((r) => (
                  <li key={r.kandidaat_id}>
                    {hypotheseZin(r.hypothese, passageTekst(r.van, data.passages, data.groepen),
                      passageTekst(r.naar, data.passages, data.groepen)).join(" ")}
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
