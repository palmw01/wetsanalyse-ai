"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { ObjectRij, ObjectRijen } from "@/components/ui/Pagina";
import { VraagRegel } from "@/components/werkgebieden/BegripTerm";
import { StatusLabel } from "@/components/ui/Lijst";
import { akkoordGroep, beantwoordVraag, foutTekst, haalGroepen, haalLaatsteBegrippenRun } from "@/lib/api";
import { hypotheseZin } from "@/lib/begripRelaties";
import { losseVragen, termenVan, termOmvang } from "@/lib/begripTermen";
import { AANDACHT_LABEL, BESLUIT_LABEL, openVragen, passageTekst, samenAkkoord } from "@/lib/begripVoorstellen";
import type { BegrippenRun, GroepenAntwoord } from "@/lib/types";
import { begripPad, termPad } from "@/lib/werkgebiedPaden";

const INGEKLAPT = "wa_voorstellen_ingeklapt";

const telling = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

const datum = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** De strook "Voorstellen van Lex" op de tab Begrippen (spoor D, levering 3a) en in het artefactpaneel.
 *
 *  Lex draait de deterministische begrippenketen (ADR-004) op de passages van het werkgebied en stelt
 *  groepen voor: formuleringen die mogelijk één begrip aanduiden. Starten en meedenken vraag je Lex in
 *  het gesprek (*Stel begrippen voor*, *Denk mee over de begrippen*; F3e): de strook toont de laatste
 *  ronde, de voorstellen **per term** (spoor H4: de keten maakt één groep per term per bepaling, dus
 *  "tijdvak" stond er zeven keer) en de relaties. Beoordelen gebeurt op de pagina van een term
 *  (`BegripTermPagina`). Een voorstel is geen begrip, en geen besluit wijzigt een annotatie. */
export function BegripVoorstellen({ id, runId, inklapbaar = true }: {
  id: string;
  /** De ronde waar een artefact in het gesprek naar wijst. De voorstellen zijn altijd die van de
   *  laatste ronde – daar wordt verder beoordeeld –, maar is dat een andere, dan zegt de strook dat. */
  runId?: string;
  /** Op de tab Begrippen een strook die je kunt inklappen; in het artefactpaneel is hij de hele
   *  inhoud en staat hij altijd open. */
  inklapbaar?: boolean;
}) {
  const [ingeklaptBewaard, setIngeklapt] = useState(false);
  const ingeklapt = inklapbaar && ingeklaptBewaard;
  const [data, setData] = useState<GroepenAntwoord | null>(null);
  const [laatste, setLaatste] = useState<BegrippenRun | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const router = useRouter();

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

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  function wisselIngeklapt() {
    setIngeklapt((v) => {
      try { localStorage.setItem(INGEKLAPT, v ? "0" : "1"); } catch { /* alleen deze sessie */ }
      return !v;
    });
  }

  const termen = termenVan(data);
  const open = termen.filter((t) => t.open.length > 0);
  const besloten = termen.filter((t) => t.open.length === 0);
  const los = losseVragen(data, termen);

  async function voer(actie: () => Promise<unknown>) {
    setBezig(true);
    setFout(null);
    try { await actie(); await laad(); } catch (e) { setFout(foutTekst(e)); } finally { setBezig(false); }
  }
  const teGaan = open.length;
  const run = laatste ?? data?.run ?? null;
  const vragen = openVragen(data);
  const relaties = data?.run?.uitkomst?.relaties ?? [];

  return (
    <section data-begripvoorstellen className="rounded-button border border-line bg-paper" aria-labelledby="voorstellen-kop">
      <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        {inklapbaar ? (
          <button type="button" onClick={wisselIngeklapt} aria-expanded={!ingeklapt}
            className="focus-ring flex items-center gap-1.5 rounded text-left">
            <ChevronOmlaag className={`transition-transform ${ingeklapt ? "-rotate-90" : ""}`} />
            <span id="voorstellen-kop" className="font-display text-sm font-semibold text-lint">Voorstellen van Lex</span>
            {teGaan > 0 && <span className="text-xs text-muted">· {telling(teGaan, "term", "termen")} te beoordelen</span>}
          </button>
        ) : (
          <p className="flex items-center gap-1.5">
            <span id="voorstellen-kop" className="font-display text-sm font-semibold text-lint">Voorstellen van Lex</span>
            {teGaan > 0 && <span className="text-xs text-muted">· {telling(teGaan, "term", "termen")} te beoordelen</span>}
          </p>
        )}
      </div>

      {!ingeklapt && (
        <div className="space-y-4 border-t border-line px-4 py-3">
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {runId && laatste && laatste.id !== runId && (
            <Melding type="uitleg" compact>
              Dit gesprek wijst naar een eerdere ronde van Lex. Hieronder staan de voorstellen van de laatste
              ronde ({datum(laatste.gewijzigd)}): daar beoordeel je verder.
            </Melding>
          )}

          {run && (
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
                  Gebaseerd op een oudere stand van het werkgebied (er kwamen passages of bronnen bij). Vraag Lex opnieuw om voorstellen om ze mee te nemen.
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

          {!run && data && (
            <p className="text-sm text-muted">
              Vraag Lex in het gesprek om begrippen voor te stellen. Hij zoekt in de passages van dit werkgebied naar formuleringen die
              één begrip aanduiden – op grond van wat de wet zelf vastlegt (definities, “bedoeld in”). Een voorstel is een vraag aan
              jou, geen begrip.
            </p>
          )}

          {data?.run && open.length > 0 && (
            <ObjectRijen label="Voorstellen van Lex per term">
              {open.map((t) => (
                <ObjectRij key={t.sleutel} href={termPad(id, t.sleutel)} data-term={t.sleutel} titel={t.naam}
                  sub={<>
                    {termOmvang(t)} · {telling(t.passages, "passage", "passages")}
                    {t.vragenBuiten.length > 0 && ` · ${telling(t.vragenBuiten.length, "vraag", "vragen")} naar een andere term`}
                  </>}
                  status={<>
                    {t.lijktOp.length > 0 && <StatusLabel>lijkt op {t.lijktOp[0].naam}</StatusLabel>}
                    {t.open.some((g) => g.aandacht === "geel") && <StatusLabel toon="geel">{AANDACHT_LABEL.geel}</StatusLabel>}
                  </>} />
              ))}
            </ObjectRijen>
          )}
          {data?.run && open.length === 0 && termen.length > 0 && (
            <p className="text-sm text-muted">Alle voorstellen van deze ronde zijn beoordeeld.</p>
          )}
          {data?.run && los.length > 0 && (
            <details className="text-sm">
              <summary className="focus-ring cursor-pointer rounded text-sm font-semibold text-lint">Losse twijfelvragen ({los.length})</summary>
              <ul className="divide-y divide-line" aria-label="Losse twijfelvragen">
                {los.map((v) => (
                  <VraagRegel key={v.kandidaat_id} vraag={v} data={data} bezig={bezig}
                    onApart={() => void voer(() => beantwoordVraag(id, data.run!.id, v.kandidaat_id, "apart"))}
                    onSamen={(naam) => void voer(async () => {
                      const uit = await akkoordGroep(id, samenAkkoord(v, data.groepen, data.passages, naam));
                      router.push(begripPad(id, uit.begrip.id));
                    })} />
                ))}
              </ul>
            </details>
          )}
          {besloten.length > 0 && (
            <details className="text-sm">
              <summary className="focus-ring cursor-pointer rounded text-sm font-semibold text-lint">Beoordeelde termen ({besloten.length})</summary>
              <ObjectRijen label="Beoordeelde termen">
                {besloten.map((t) => (
                  <ObjectRij key={t.sleutel} href={termPad(id, t.sleutel)} titel={t.naam}
                    sub={[...new Set(t.besloten.map((g) => BESLUIT_LABEL[g.besluit]))].join(", ")} />
                ))}
              </ObjectRijen>
            </details>
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
