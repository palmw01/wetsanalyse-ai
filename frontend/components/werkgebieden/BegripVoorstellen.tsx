"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Groep, GroepRij, ObjectRij, ObjectRijen } from "@/components/ui/Pagina";
import { VraagRegel } from "@/components/werkgebieden/BegripTerm";
import { StatusLabel } from "@/components/ui/Lijst";
import { akkoordGroep, beantwoordVraag, foutTekst, haalGroepen, haalLaatsteBegrippenRun } from "@/lib/api";
import { hypotheseZin } from "@/lib/begripRelaties";
import { losseVragen, termenVan, termOmvang } from "@/lib/begripTermen";
import { AANDACHT_LABEL, BESLUIT_LABEL, openVragen, passageTekst, samenAkkoord } from "@/lib/begripVoorstellen";
import type { BegrippenRun, GroepenAntwoord } from "@/lib/types";
import { begripPad, termPad } from "@/lib/werkgebiedPaden";

const telling = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

const datum = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** De voorstellen van Lex (spoor D, levering 3a), op de pagina van het kader en in het artefactpaneel.
 *
 *  Lex draait de deterministische begrippenketen (ADR-004) op de passages van het werkgebied en stelt
 *  groepen voor: formuleringen die mogelijk één begrip aanduiden. Starten en meedenken vraag je Lex in
 *  het gesprek (*Stel begrippen voor*, *Denk mee over de begrippen*; F3e): dit toont de laatste
 *  ronde, de voorstellen **per term** (spoor H4: de keten maakt één groep per term per bepaling, dus
 *  "tijdvak" stond er zeven keer) en de relaties. Beoordelen gebeurt op de pagina van een term
 *  (`BegripTermPagina`). Een voorstel is geen begrip, en geen besluit wijzigt een annotatie. */
export function BegripVoorstellen({ id, runId, kop = "Voorstellen van Lex", sub, boven, opname }: {
  id: string;
  /** De ronde waar een artefact in het gesprek naar wijst. De voorstellen zijn altijd die van de
   *  laatste ronde – daar wordt verder beoordeeld –, maar is dat een andere, dan zegt de strook dat. */
  runId?: string;
  /** De kop van de rijen; op de pagina van het kader staan ze onder *Te doen*. */
  kop?: string;
  sub?: React.ReactNode;
  /** Rijen boven de termen: wat er verder te doen is (de begrippen om te herbeoordelen). */
  boven?: React.ReactNode[];
  /** Een oude versie (de versiekiezer): de voorstellen zoals ze toen waren. Alleen lezen: niets ophalen en geen besluiten;
   *  de rijen naar de termpagina tonen de stand van nu, en dat staat erbij. De aanroeper remount per versie (`key`). */
  opname?: GroepenAntwoord;
}) {
  const [data, setData] = useState<GroepenAntwoord | null>(opname ?? null);
  const [laatste, setLaatste] = useState<BegrippenRun | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const router = useRouter();

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
    if (opname) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad, opname]);

  const termen = termenVan(data);
  const open = termen.filter((t) => t.open.length > 0);
  const besloten = termen.filter((t) => t.open.length === 0);
  const los = losseVragen(data, termen);

  async function voer(actie: () => Promise<unknown>) {
    setBezig(true);
    setFout(null);
    try { await actie(); await laad(); } catch (e) { setFout(foutTekst(e)); } finally { setBezig(false); }
  }
  const run = laatste ?? data?.run ?? null;
  const vragen = openVragen(data);
  const relaties = data?.run?.uitkomst?.relaties ?? [];

  return (
    <section data-begripvoorstellen aria-label={kop} className="space-y-3">
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {opname && (
            <p className="text-xs text-muted" data-alleen-lezen>Een term openen toont de stand van nu; daar beoordeel je verder.</p>
          )}
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

          {(boven?.length || open.length > 0) ? (
            <Groep kop={kop} telling={(boven?.length ?? 0) + open.length} sub={sub} label="Voorstellen van Lex per term">
              {boven}
              {open.map((t) => (
                <GroepRij key={t.sleutel} href={termPad(id, t.sleutel)} data-term={t.sleutel} titel={t.naam}
                  sub={<>
                    {termOmvang(t)} · {telling(t.passages, "passage", "passages")}
                    {t.vragenBuiten.length > 0 && ` · ${telling(t.vragenBuiten.length, "vraag", "vragen")} naar een andere term`}
                  </>}
                  status={<>
                    <StatusLabel toon="lint">Voorstel van Lex</StatusLabel>
                    {t.lijktOp.length > 0 && <StatusLabel>lijkt op {t.lijktOp[0].naam}{t.lijktOp[0].generiek ? " (generiek)" : ""}</StatusLabel>}
                    {t.open.some((g) => g.aandacht === "geel") && <StatusLabel toon="geel">{AANDACHT_LABEL.geel}</StatusLabel>}
                  </>} />
              ))}
            </Groep>
          ) : null}
          {data?.run && open.length === 0 && termen.length > 0 && (
            <p className="text-sm text-muted">Alle voorstellen van deze ronde zijn beoordeeld.</p>
          )}
          {data?.run && los.length > 0 && !opname && (
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
    </section>
  );
}
