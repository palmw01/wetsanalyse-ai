"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Bestandenlijst } from "@/components/ui/Bestandenlijst";
import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button, knopKlasse } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Plus, Potlood } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { MeerMenu, MenuKnop, MenuVerwijder } from "@/components/ui/MeerMenu";
import { Melding } from "@/components/ui/Melding";
import { Kaart } from "@/components/ui/Pagina";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { Markdown } from "@/components/werkplek/Markdown";
import { foutTekst, haalConcept, isApiError, slaConceptOp, toetsConcept } from "@/lib/api";
import { leesOpslag, schrijfOpslag } from "@/lib/opslag";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import {
  bestandsvolgorde, leesWerk, omvang, padFout, splitsFrontmatter, werkSleutel, wijzigingZin, wijzigingen,
  type Bestanden, type Bevinding, type WerkplaatsOnderdeel, type WerkplaatsStand, type WerkplaatsVersie,
} from "@/lib/werkplaats";

/** Hoe lang na de laatste toetsaanslag de controle draait en het werk in de browser wordt bewaard. */
const WACHT_MS = 600;

type Controle = { stand: "bewaard" | "bezig" | "klaar" | "mislukt"; geldig: boolean; bevindingen: Bevinding[] };

/** De bestanden van een concept: lezen, en voor de eigenaar bewerken (ADR-016 §B7, stap B2-2).
 *
 *  - Links de bestanden en wat de controle vond, rechts het gekozen bestand; op een telefoon onder elkaar.
 *  - Bewerken gaat in een gewoon tekstvak. Na een korte pauze toetst de api de hele stand (poort 1, zonder op te
 *    slaan); een antwoord op een oudere stand telt niet.
 *  - *Opslaan* maakt een volgende versie. Versies groeien alleen aan: ook een versie die de controle niet haalt, wordt
 *    bewaard. Is er intussen een nieuwere versie, dan blijft de tekst staan en kiest de gebruiker.
 *  - Niet-opgeslagen werk staat in de browser tot het is opgeslagen of verworpen, en weggaan vraagt eerst.
 *  - Geen sneltoetsen met een letter; niets hier start Lex. */
export function ConceptEditor({ o, versie, grenzen, bewerkbaar, onOpgeslagen, zij, klaargezet, onVerworpen, draait }: {
  o: WerkplaatsOnderdeel;
  versie: WerkplaatsVersie;
  grenzen: WerkplaatsStand["grenzen"];
  /** De eigenaar, op een concept dat niet is ingetrokken. Anders alleen lezen. */
  bewerkbaar: boolean;
  /** Er is een nieuwe versie: laad het concept opnieuw. */
  onOpgeslagen: () => void;
  /** Onder de bestanden en de controle: de versies. */
  zij?: React.ReactNode;
  /** De bestanden van een eerdere versie, teruggezet als wijziging op deze (*Zet terug als concept*). */
  klaargezet?: { bestanden: Bestanden; van: number | "draait" } | null;
  onVerworpen?: () => void;
  /** Het concept loopt achter: de hash van wat er nu draait. Opslaan met het vinkje maakt dat de nieuwe basis. */
  draait?: { hash: string } | null;
}) {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const bewaard = useMemo<Bestanden>(() => versie.bestanden ?? {}, [versie]);
  const sleutel = werkSleutel(o.id, versie.nummer);

  const [werk, setWerk] = useState<Bestanden>(klaargezet && bewerkbaar ? klaargezet.bestanden : bewaard);
  const [hersteld, setHersteld] = useState(false);
  const [controle, setControle] = useState<Controle>({ stand: "bewaard", geldig: versie.geldig, bevindingen: versie.bevindingen });
  const [lezen, setLezen] = useState(false);
  const [toelichting, setToelichting] = useState("");
  // "Ik heb verwerkt wat er nu draait": wie opnieuw begon vanaf wat er draait, heeft dat per definitie.
  const [verwerkt, setVerwerkt] = useState(klaargezet?.van === "draait");
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [nieuwer, setNieuwer] = useState<WerkplaatsVersie | null>(null);
  const [afgerond, setAfgerond] = useState(false);
  const [formulier, setFormulier] = useState<null | { soort: "nieuw" | "hernoem"; pad: string }>(null);

  // Niet-opgeslagen werk van een vorig bezoek staat er weer (na het mounten: de server kent geen opslag).
  useEffect(() => {
    // Wat net is teruggezet, gaat voor werk van een vorig bezoek.
    if (!bewerkbaar || klaargezet) return;
    const oud = leesOpslag(sleutel, leesWerk);
    if (oud && wijzigingen(bewaard, oud).aantal > 0) { setWerk(oud); setHersteld(true); }
  }, [sleutel, bewaard, bewerkbaar, klaargezet]);

  const w = useMemo(() => wijzigingen(bewaard, werk), [bewaard, werk]);
  // Na het opslaan is dit de editor van een versie die er niet meer toe doet: de nieuwe versie krijgt een nieuwe editor.
  const gewijzigd = bewerkbaar && !afgerond && w.aantal > 0;
  const looptAchter = bewerkbaar && !afgerond && !!draait;
  const paden = useMemo(() => bestandsvolgorde(Object.keys(werk)), [werk]);
  const gevraagd = zoekParams.get("bestand") ?? "";
  const gekozen = paden.includes(gevraagd) ? gevraagd : paden[0] ?? "";
  const maat = useMemo(() => omvang(werk, grenzen), [werk, grenzen]);

  // De controle live, en het werk in de browser: allebei na een korte pauze, en alleen als er iets gewijzigd is.
  const ronde = useRef(0);
  useEffect(() => {
    const mijn = ++ronde.current;
    if (!gewijzigd) {
      schrijfOpslag(sleutel, undefined);
      setControle({ stand: "bewaard", geldig: versie.geldig, bevindingen: versie.bevindingen });
      return;
    }
    const afbreken = new AbortController();
    const t = setTimeout(async () => {
      schrijfOpslag(sleutel, werk);
      setControle((c) => ({ ...c, stand: "bezig" }));
      try {
        const uit = await toetsConcept({ soort: o.soort, naam: o.naam, bestanden: werk }, afbreken.signal);
        // Een antwoord op een stand die intussen weer veranderde, telt niet.
        if (mijn === ronde.current) setControle({ stand: "klaar", geldig: uit.geldig, bevindingen: uit.bevindingen });
      } catch (e) {
        if (mijn !== ronde.current || afbreken.signal.aborted) return;
        // Wat de api nooit bewaart (een ongeldig pad, te groot) komt als 422 met de bevindingen terug.
        const bevindingen = isApiError(e) && Array.isArray(e.data?.bevindingen) ? (e.data.bevindingen as Bevinding[]) : [];
        setControle({ stand: bevindingen.length ? "klaar" : "mislukt", geldig: false, bevindingen });
      }
    }, WACHT_MS);
    return () => { clearTimeout(t); afbreken.abort(); };
  }, [werk, gewijzigd, sleutel, o.soort, o.naam, versie]);

  // Weggaan met niet-opgeslagen werk vraagt eerst: herladen en sluiten via de browser, een link via de bewaker.
  // Sluit of herlaadt de browser toch, dan staat het werk van dit moment in de browser (de pauze wacht daar niet op).
  const laatste = useRef(werk);
  useEffect(() => { laatste.current = werk; }, [werk]);
  useEffect(() => {
    if (!gewijzigd) return;
    const waarschuw = (e: BeforeUnloadEvent) => e.preventDefault();
    const bewaar = () => schrijfOpslag(sleutel, laatste.current);
    window.addEventListener("beforeunload", waarschuw);
    window.addEventListener("pagehide", bewaar);
    return () => { window.removeEventListener("beforeunload", waarschuw); window.removeEventListener("pagehide", bewaar); };
  }, [gewijzigd, sleutel]);
  const bewaker = useOnbewaardBewaker(gewijzigd);
  // Wie na de vraag toch weggaat, gooit zijn wijzigingen weg: zo zegt de melding het, dus ook uit de browser.
  const tochWeg = () => { setAfgerond(true); schrijfOpslag(sleutel, undefined); bewaker.toch(); };

  const kies = useCallback((p: string) => {
    const qs = new URLSearchParams(zoekParams.toString());
    qs.set("bestand", p);
    // `replace`: een ander bestand is geen stap in de geschiedenis.
    router.replace(`${pad}?${qs}`, { scroll: false });
  }, [router, pad, zoekParams]);

  function verwerp() {
    setWerk(bewaard); setHersteld(false); setNieuwer(null); setFout(null); setToelichting(""); setVerwerkt(false);
    onVerworpen?.();
  }

  async function slaOp(naVersie: number) {
    setBezig(true); setFout(null);
    try {
      await slaConceptOp(o.id, { bestanden: werk, na_versie: naVersie, toelichting: toelichting.trim(),
        ...(draait && verwerkt ? { basis_hash: draait.hash } : {}) });
      schrijfOpslag(sleutel, undefined);
      setAfgerond(true); setNieuwer(null); setHersteld(false); setToelichting("");
      onOpgeslagen();
    } catch (e) {
      // Een 409 kan betekenen dat er intussen een nieuwere versie is (een ander venster). Dat lezen we na bij de api,
      // niet uit de tekst van de fout: de tekst in het vak blijft staan en de gebruiker kiest.
      if (isApiError(e) && e.status === 409) {
        const nu = await haalConcept(o.id).catch(() => null);
        if (nu?.laatste && nu.laatste.nummer > naVersie && nu.stand !== "ingetrokken") { setNieuwer(nu.laatste); return; }
      }
      const bevindingen = isApiError(e) && Array.isArray(e.data?.bevindingen) ? (e.data.bevindingen as Bevinding[]) : [];
      setFout([foutTekst(e, "De versie kon niet worden opgeslagen."), ...bevindingen.map((b) => b.melding)].join(" "));
    } finally {
      setBezig(false);
    }
  }

  function voerFormulierUit(e: React.FormEvent) {
    e.preventDefault();
    if (!formulier) return;
    const anders = formulier.soort === "hernoem" ? paden.filter((p) => p !== gekozen) : paden;
    if (!formulier.pad || padFout(formulier.pad, anders)) return;
    if (formulier.soort === "hernoem") {
      if (formulier.pad !== gekozen) setWerk(({ [gekozen]: inhoud, ...rest }) => ({ ...rest, [formulier.pad]: inhoud }));
    } else setWerk((b) => ({ ...b, [formulier.pad]: "" }));
    kies(formulier.pad);
    setFormulier(null);
  }

  const perBestand = (p: string) => controle.bevindingen.filter((b) => b.bestand === p);
  const algemeen = controle.bevindingen.filter((b) => !paden.includes(b.bestand));
  const formulierFout = formulier ? padFout(formulier.pad, formulier.soort === "hernoem" ? paden.filter((p) => p !== gekozen) : paden) : "";
  const isMarkdown = gekozen.endsWith(".md");
  const tekst = werk[gekozen] ?? "";
  const tekens = [...tekst].length;

  return (
    <div data-concept-versie={versie.nummer} data-gewijzigd={gewijzigd ? "ja" : "nee"}>
      {bewaker.wachtend && (
        <OnbewaardMelding className="mb-4" waar="In dit concept" handeling={bewaker.wachtend.handeling}
          onBlijf={bewaker.blijf} onToch={tochWeg} />
      )}
      {hersteld && gewijzigd && (
        <div className="mb-4" data-melding="hersteld">
          <Melding type="uitleg">Je niet-opgeslagen wijzigingen van de vorige keer staan er weer. Sla ze op, of verwerp ze onderaan.</Melding>
        </div>
      )}
      {klaargezet && gewijzigd && !hersteld && (
        <div className="mb-4" data-melding="teruggezet">
          <Melding type="uitleg">
            {klaargezet.van === "draait" ? "De bestanden die nu draaien staan" : `De bestanden van versie ${klaargezet.van} staan`} klaar
            als wijziging op versie {versie.nummer}. Er is nog niets veranderd: opslaan maakt er versie {versie.nummer + 1} van,
            verwerpen laat versie {versie.nummer} staan.
            {klaargezet.van === "draait" && ` Wat jij veranderde zit hier niet in; het blijft bewaard in versie ${versie.nummer} en eerder.`}
          </Melding>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <Kaart titel="Bestanden" telling={paden.length} data-blok="bestanden"
            acties={bewerkbaar && !formulier ? (
              <Button variant="secondary" size="xs" onClick={() => setFormulier({ soort: "nieuw", pad: "" })} data-actie="bestand-nieuw">
                <Plus className="h-3 w-3" />Bestand</Button>) : undefined}>
            {formulier && (
              <form onSubmit={voerFormulierUit} className="mb-3" data-bestand-formulier={formulier.soort}>
                <Field label={formulier.soort === "nieuw" ? "Pad van het nieuwe bestand" : `Nieuwe naam voor ${gekozen}`} error={formulierFout || undefined}>
                  <Input value={formulier.pad} onChange={(e) => setFormulier({ ...formulier, pad: e.target.value.trim() })} autoFocus
                    autoComplete="off" spellCheck={false} placeholder="references/uitleg.md" aria-invalid={!!formulierFout} className="font-mono text-xs" />
                </Field>
                <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                  <Button type="submit" size="sm" disabled={!formulier.pad || !!formulierFout} data-actie="bestand-bevestigen">
                    {formulier.soort === "nieuw" ? "Toevoegen" : "Hernoemen"}</Button>
                  <Button type="button" variant="secondary" size="sm" onClick={() => setFormulier(null)}>Annuleren</Button>
                </div>
              </form>
            )}
            <Bestandenlijst paden={paden} gekozen={gekozen} onKies={kies} label="Bestanden van dit concept"
              stand={(p) => (w.gewijzigd.includes(p) ? "gewijzigd" : w.toegevoegd.includes(p) ? "nieuw" : "")}
              bij={(p) => {
                const n = perBestand(p).length;
                const anders = w.gewijzigd.includes(p) ? "gewijzigd" : w.toegevoegd.includes(p) ? "nieuw" : "";
                return (<>
                  {anders && <StatusLabel toon="lint" uitleg={anders === "nieuw" ? "Nieuw, nog niet opgeslagen" : "Gewijzigd, nog niet opgeslagen"}>{anders}</StatusLabel>}
                  {n > 0 && <StatusLabel toon="geel" uitleg={n === 1 ? "1 bevinding in dit bestand" : `${n} bevindingen in dit bestand`}>{n}</StatusLabel>}
                </>);
              }} />
            {w.verwijderd.length > 0 && (
              <p className="mt-3 text-xs text-muted [overflow-wrap:anywhere]" data-bestanden-verwijderd>
                Verwijderd, nog niet opgeslagen: <span className="font-mono">{w.verwijderd.join(", ")}</span>
              </p>
            )}
          </Kaart>
          <Kaart titel="Controle" telling={controle.bevindingen.length} data-blok="controle" data-controle={controle.stand}
            toelichting={controle.stand === "mislukt" ? "De controle kon nu niet draaien. Opslaan kan wel; dan toetst de api de versie."
              : controle.stand === "bezig" ? "Wordt gecontroleerd…"
              : `${gewijzigd ? "Wat er nu staat" : "Deze versie"} ${controle.geldig ? "haalt de controle." : "haalt de controle niet."}${
                !controle.geldig && !gewijzigd ? " Ze is bewaard, maar kan zo niet verder." : ""}`}>
            {!o.image_bekend && o.soort === "skill" && (
              <p className="mb-2 text-xs text-muted">Lex heeft nog niet gemeld wat er draait. De controle tegen de andere skills kon daarom nog niet.</p>
            )}
            {controle.bevindingen.length > 0 && (
              <ul aria-label="Bevindingen van de controle" className="space-y-2 text-sm">
                {[...algemeen, ...paden.flatMap(perBestand)].map((b, i) => (
                  <li key={i} data-bevinding={b.code} className="[overflow-wrap:anywhere]">
                    {b.bestand && (paden.includes(b.bestand)
                      ? <button type="button" onClick={() => kies(b.bestand)} className="focus-ring block rounded font-mono text-xs text-lint hover:underline">{b.bestand}</button>
                      : <span className="block font-mono text-xs text-muted">{b.bestand}</span>)}
                    {b.melding}
                  </li>
                ))}
              </ul>
            )}
          </Kaart>
          {zij}
        </div>

        <Kaart data-blok="inhoud" titel={<span className="font-mono text-sm [overflow-wrap:anywhere]">{gekozen || "Geen bestanden"}</span>}
          acties={gekozen ? (
            <span className="flex items-center gap-1.5">
              {isMarkdown && (
                <Button variant="secondary" size="xs" aria-pressed={lezen} onClick={() => setLezen((l) => !l)} data-actie="lezen">
                  {lezen ? "Bewerken" : "Lezen"}</Button>
              )}
              {bewerkbaar && (
                <MeerMenu label={`Meer bij ${gekozen}`}>
                  {(sluit) => (<>
                    <MenuKnop icoon={<Potlood />} onClick={() => { sluit(); setFormulier({ soort: "hernoem", pad: gekozen }); }}>Hernoemen</MenuKnop>
                    <MenuVerwijder ariaLabel={`${gekozen} verwijderen`} titel="Het bestand gaat pas echt weg als je opslaat."
                      onBevestig={() => { sluit(); setWerk(({ [gekozen]: _weg, ...rest }) => rest); }} />
                  </>)}
                </MeerMenu>
              )}
            </span>) : undefined}>
          {!gekozen ? <p className="text-sm text-muted">Dit concept heeft geen bestanden.</p>
            : (lezen && isMarkdown) || !bewerkbaar ? <Leesweergave pad={gekozen} tekst={tekst} opgemaakt={lezen && isMarkdown} />
            : (
              <>
                <AutoTextarea value={tekst} onChange={(e) => setWerk((b) => ({ ...b, [gekozen]: e.target.value }))} rows={12}
                  aria-label={`Inhoud van ${gekozen}`} spellCheck={false} data-bestand-inhoud={gekozen}
                  className="font-mono text-xs leading-relaxed [overflow-wrap:anywhere]" />
                <p className="mt-2 text-xs tabular-nums text-muted" data-omvang>
                  {tekens.toLocaleString("nl-NL")}{grenzen.tekens_per_bestand > 0 && ` van ${grenzen.tekens_per_bestand.toLocaleString("nl-NL")}`} tekens in dit bestand
                  {" · "}{maat.tekens.toLocaleString("nl-NL")}{grenzen.tekens > 0 && ` van ${grenzen.tekens.toLocaleString("nl-NL")}`} in de versie
                </p>
              </>
            )}
        </Kaart>
      </div>

      {(gewijzigd || looptAchter) && (
        <div className="sticky bottom-0 z-10 -mx-1 mt-4 rounded-kaart border border-line bg-paper p-3 shadow-kaart" data-opslaan>
          {looptAchter && !nieuwer && (
            <label className="mb-3 flex items-start gap-2 text-sm text-ink" data-verwerkt>
              <input type="checkbox" checked={verwerkt} onChange={(e) => setVerwerkt(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--lint))]" />
              <span>Ik heb verwerkt wat er nu draait. Na het opslaan bouwt dit concept voort op de versie die nu draait, en
                loopt het niet meer achter.</span>
            </label>
          )}
          {nieuwer ? (
            <div data-conflict={nieuwer.nummer}>
              <Melding type="waarschuwing" titel={`Er is intussen versie ${nieuwer.nummer} opgeslagen`}>
                Je tekst staat hier nog; er is niets weggegooid. Sla je op, dan wordt jouw tekst versie {nieuwer.nummer + 1} en
                blijft versie {nieuwer.nummer} bewaard bij de versies. Verwerp je, dan zie je versie {nieuwer.nummer} en ben je je eigen
                wijzigingen kwijt.
              </Melding>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Button size="sm" onClick={() => slaOp(nieuwer.nummer)} disabled={bezig} data-actie="toch-opslaan">
                  {bezig ? "Bezig…" : `Opslaan als versie ${nieuwer.nummer + 1}`}</Button>
                <BevestigKnop bevestigTekst="Wijzigingen verwerpen?" className={`${knopKlasse("secondary", "sm")} w-full sm:w-auto`}
                  onBevestig={() => { schrijfOpslag(sleutel, undefined); setAfgerond(true); verwerp(); onOpgeslagen(); }}>Mijn wijzigingen verwerpen</BevestigKnop>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="min-w-0 flex-1">
                <Field label="Toelichting bij deze versie" hint={wijzigingZin(w) || "geen wijziging in de bestanden"}>
                  <Input value={toelichting} onChange={(e) => setToelichting(e.target.value)} maxLength={500} autoComplete="off"
                    placeholder="Wat heb je veranderd? (mag leeg)" />
                </Field>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button size="sm" onClick={() => slaOp(versie.nummer)} data-actie="opslaan"
                  disabled={bezig || maat.teVeel.length > 0 || !(gewijzigd || (looptAchter && verwerkt))}>
                  {bezig ? "Bezig…" : `Opslaan als versie ${versie.nummer + 1}`}</Button>
                <BevestigKnop bevestigTekst="Verwerpen?" onBevestig={verwerp} className={`${knopKlasse("secondary", "sm")} w-full sm:w-auto`}
                  ariaLabel="Wijzigingen verwerpen">Verwerpen</BevestigKnop>
              </div>
            </div>
          )}
          {maat.teVeel.length > 0 && <Melding type="waarschuwing" compact className="mt-2">{maat.teVeel.join(" ")}</Melding>}
          {fout && <Melding type="fout" compact className="mt-2">{fout}</Melding>}
          {!controle.geldig && controle.stand === "klaar" && !nieuwer && (
            <p className="mt-2 text-xs text-muted">Wat er nu staat haalt de controle niet. Opslaan kan: de versie wordt bewaard, maar kan zo niet verder.</p>
          )}
        </div>
      )}
    </div>
  );
}

/** Een bestand om te lezen: zoals het is, of een Markdown-bestand opgemaakt met zijn frontmatter erboven. */
function Leesweergave({ pad, tekst, opgemaakt }: { pad: string; tekst: string; opgemaakt: boolean }) {
  const PRE = "max-w-full whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink [overflow-wrap:anywhere]";
  if (!opgemaakt) return <pre data-bestand-inhoud={pad} className={PRE}>{tekst}</pre>;
  const { frontmatter, rest } = splitsFrontmatter(tekst);
  return (
    <div data-bestand-gelezen={pad} className="min-w-0 [overflow-wrap:anywhere]">
      {frontmatter && <pre className={`${PRE} mb-3 rounded-knop bg-surface p-2 text-muted`}>{frontmatter}</pre>}
      <Markdown tekst={rest} links="vrij" />
    </div>
  );
}
