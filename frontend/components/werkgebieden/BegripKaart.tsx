"use client";

import { useEffect, useState } from "react";

import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import type { BegripMutatie } from "@/components/werkgebieden/BegripWerk";
import { KaartVoorstelKaart } from "@/components/werkgebieden/KaartVoorstel";
import {
  accordeerBegrip, foutTekst, haalBegripRevisies, haalConformiteit, heropenBegrip, wijzigBegrip,
} from "@/lib/api";
import { conformZin, veldVanPad, type Conformiteit } from "@/lib/begripGraaf";
import {
  HERKOMST_LABEL, OORDEEL_LABEL, inhoudGewijzigd, naarRijen, regels, revisieZin, uitRegels, uitRijen,
  volledigeInhoud,
} from "@/lib/begrippen";
import { definitieDoor, openPerVeld, type Verouderd } from "@/lib/kaartVoorstel";
import { BEGRIPSTYPE_LABEL } from "@/lib/begripVoorstellen";
import { JAS_KLASSEN } from "@/lib/jas";
import type {
  Begrip, BegripInhoud, BegripRevisie, Begripstype, DefinitieHerkomst, KaartVeld, KaartVoorstel, Voorbeeld,
  VoorbeeldOordeel,
} from "@/lib/types";

/** Wat Lex naast de kaart heeft staan (fase E), en hoe de kaart erover besluit. `BegripWerk` draagt het. */
export interface LexBijKaart {
  voorstellen: readonly KaartVoorstel[];
  verouderd: Verouderd | null;
  overnemen: (v: KaartVoorstel, extra: { aanpassing?: string; oordeel?: VoorbeeldOordeel; nu_gezien?: string }) => Promise<boolean>;
  afwijzen: (v: KaartVoorstel, reden: string) => Promise<boolean>;
}

const KNOP_KLEIN =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]";

const tijd = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Wat het formulier bewerkt. Lijsten staan als tekst (één per regel) en eigenschappen als rijen,
 *  omdat ze zo te bewerken zijn; `naarInhoud` maakt er weer de vorm van de api van. */
interface Concept {
  inhoud: BegripInhoud;
  termen: string;
  vragen: string;
  rijen: [string, string][];
}

function uitBegrip(i: BegripInhoud): Concept {
  const v = volledigeInhoud(i);
  return { inhoud: v, termen: regels(v.alternatieve_termen), vragen: regels(v.open_vragen), rijen: naarRijen(v.eigenschappen) };
}

function naarInhoud(c: Concept): BegripInhoud {
  return { ...c.inhoud, alternatieve_termen: uitRegels(c.termen), open_vragen: uitRegels(c.vragen), eigenschappen: uitRijen(c.rijen) };
}

/** De begripskaart: één formulier met *Opslaan* (geen autosave – elke bewaring is een revisie).
 *  Definitie, de herkomst ervan en de uitleg staan apart, want een begripsdefinitie is iets anders
 *  dan de letterlijke brondefinitie of de toelichting op een interpretatie. */
export function BegripKaart({ id, begrip, muteer, onOnbewaard, onVerwijder, lex }: {
  id: string;
  begrip: Begrip;
  muteer: BegripMutatie;
  onOnbewaard: (onbewaard: boolean) => void;
  /** Verwijderen, met de revisie in beeld; `BegripWerk` handelt een conflict af. */
  onVerwijder: () => Promise<void>;
  lex?: LexBijKaart;
}) {
  const [concept, setConcept] = useState<Concept>(() => uitBegrip(begrip.inhoud));
  // De serverstand waarop het concept rust. Verandert de inhoud op de server (iemand anders sloeg op),
  // dan nemen we hem over als er niets onbewaard is, en zeggen we het anders.
  const [basis, setBasis] = useState<BegripInhoud>(begrip.inhoud);
  const [conflict, setConflict] = useState(false);
  const [bezig, setBezig] = useState(false);

  const inhoud = naarInhoud(concept);
  const onbewaard = inhoudGewijzigd(begrip.inhoud, inhoud);
  if (inhoudGewijzigd(basis, begrip.inhoud)) {
    setBasis(begrip.inhoud);
    if (!inhoudGewijzigd(basis, inhoud)) setConcept(uitBegrip(begrip.inhoud));     // niets onbewaard
    else if (onbewaard) setConflict(true);                                         // anders dan beide
  }

  useEffect(() => {
    onOnbewaard(onbewaard);
  }, [onbewaard, onOnbewaard]);
  useEffect(() => () => onOnbewaard(false), [onOnbewaard]);
  // Herladen of het venster sluiten: dat kan de pagina niet zelf tegenhouden, de browser wel.
  useEffect(() => {
    if (!onbewaard) return;
    const waarschuw = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", waarschuw);
    return () => window.removeEventListener("beforeunload", waarschuw);
  }, [onbewaard]);

  const zet = <K extends keyof BegripInhoud>(veld: K, waarde: BegripInhoud[K]) =>
    setConcept((c) => ({ ...c, inhoud: { ...c.inhoud, [veld]: waarde } }));

  async function bewaar(e: React.FormEvent) {
    e.preventDefault();
    if (!onbewaard || bezig || !inhoud.naam.trim()) return;
    setBezig(true);
    if (await muteer((r) => wijzigBegrip(id, begrip.id, r, inhoud), { gelukt: "Opgeslagen." })) setConflict(false);
    setBezig(false);
  }

  const voorbeelden = concept.inhoud.voorbeelden;
  const perVeld = openPerVeld(lex?.voorstellen ?? []);
  const vanLex = (veld: KaartVeld) => lex && perVeld[veld].length > 0 && (
    <div className="space-y-2" aria-label={`Voorstellen van Lex bij ${veld}`}>
      {perVeld[veld].map((v) => (
        <KaartVoorstelKaart key={v.id} v={v} onbewaard={onbewaard} geaccordeerd={begrip.status === "geaccordeerd"}
          verouderd={lex.verouderd?.voorstelId === v.id ? lex.verouderd : null}
          onOvernemen={(extra) => lex.overnemen(v, extra)} onAfwijzen={(reden) => lex.afwijzen(v, reden)} />
      ))}
    </div>
  );
  const door = definitieDoor(begrip.inhoud);
  const zetVoorbeeld = (i: number, v: Partial<Voorbeeld>) =>
    zet("voorbeelden", voorbeelden.map((x, j) => (j === i ? { ...x, ...v } : x)));

  return (
    <article className="space-y-5 rounded-button border border-line bg-paper p-4" aria-label={`Begrip ${begrip.inhoud.naam}`}>
      <header className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h3 className="font-display text-base font-semibold text-lint">{begrip.inhoud.naam}</h3>
        <p className="text-xs text-muted">
          {begrip.status === "geaccordeerd" ? "Geaccordeerd" : "Concept"} · revisie {begrip.revisie}
        </p>
      </header>

      {conflict && (
        <Melding type="waarschuwing" compact>
          <p>
            Iemand anders sloeg intussen een nieuwe versie van dit begrip op. Jouw wijzigingen staan nog in
            het formulier; opslaan overschrijft de nieuwe versie.
          </p>
          <button
            type="button"
            className="mt-1 underline"
            onClick={() => {
              setConcept(uitBegrip(begrip.inhoud));
              setConflict(false);
            }}
          >
            Nieuwe versie overnemen
          </button>
        </Melding>
      )}

      <form onSubmit={bewaar} className="space-y-4">
        <Field label="Naam" required>
          <Input value={concept.inhoud.naam} onChange={(e) => zet("naam", e.target.value)} maxLength={200} required />
        </Field>
        <Field label="Alternatieve termen" hint="één per regel">
          <Textarea value={concept.termen} onChange={(e) => setConcept((c) => ({ ...c, termen: e.target.value }))} rows={2} />
        </Field>
        <Field label="Context" hint="waarbinnen deze betekenis geldt">
          <Textarea value={concept.inhoud.context} onChange={(e) => zet("context", e.target.value)} rows={2} maxLength={4000} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="JAS-duiding">
            <Select value={concept.inhoud.jas_klasse} onChange={(e) => zet("jas_klasse", e.target.value)}>
              <option value="">Geen</option>
              {JAS_KLASSEN.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </Select>
          </Field>
          <Field label="Begripstype" hint="werkindeling, geen JAS-klasse">
            <Select value={concept.inhoud.begripstype ?? ""} onChange={(e) => zet("begripstype", e.target.value as Begripstype | "")}>
              <option value="">Nog niet ingedeeld</option>
              {(Object.keys(BEGRIPSTYPE_LABEL) as Begripstype[]).map((t) => (
                <option key={t} value={t}>{BEGRIPSTYPE_LABEL[t]}</option>
              ))}
            </Select>
          </Field>
          <Field label="Geldigheid">
            <Input value={concept.inhoud.geldigheid} onChange={(e) => zet("geldigheid", e.target.value)} maxLength={1000} />
          </Field>
        </div>

        <Field label="Definitie" hint={door || undefined}>
          <Textarea value={concept.inhoud.definitie} onChange={(e) => zet("definitie", e.target.value)} rows={3} maxLength={8000} />
        </Field>
        {vanLex("definitie")}
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-ink">Herkomst van de definitie</legend>
          <div className="flex flex-col gap-1.5 sm:flex-row sm:gap-4">
            {(Object.keys(HERKOMST_LABEL) as DefinitieHerkomst[]).map((h) => (
              <label key={h} className="inline-flex items-center gap-1.5 text-sm text-ink">
                <input
                  type="radio"
                  name={`herkomst-${begrip.id}`}
                  checked={concept.inhoud.definitie_herkomst === h}
                  onChange={() => zet("definitie_herkomst", h)}
                  className="focus-ring accent-lint"
                />
                {HERKOMST_LABEL[h]}
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Uitleg" hint="toelichting op de interpretatie">
          <Textarea value={concept.inhoud.uitleg} onChange={(e) => zet("uitleg", e.target.value)} rows={2} maxLength={8000} />
        </Field>
        {vanLex("uitleg")}
        <Field label="Onderbouwing">
          <Textarea value={concept.inhoud.onderbouwing} onChange={(e) => zet("onderbouwing", e.target.value)} rows={2} maxLength={8000} />
        </Field>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-ink">Voorbeelden</legend>
          <p className="text-xs text-muted">Ook grensgevallen en tegenvoorbeelden: ze toetsen de afbakening.</p>
          {voorbeelden.map((v, i) => (
            <div key={i} className="space-y-2 rounded-kaart border border-line p-2">
              <Textarea value={v.tekst} onChange={(e) => zetVoorbeeld(i, { tekst: e.target.value })} rows={2} aria-label={`Voorbeeld ${i + 1}`} />
              <div className="flex flex-col gap-2 sm:flex-row">
                <Select value={v.oordeel} onChange={(e) => zetVoorbeeld(i, { oordeel: e.target.value as VoorbeeldOordeel })} aria-label={`Oordeel bij voorbeeld ${i + 1}`} className="sm:w-48">
                  {(Object.keys(OORDEEL_LABEL) as VoorbeeldOordeel[]).map((o) => (
                    <option key={o} value={o}>{OORDEEL_LABEL[o]}</option>
                  ))}
                </Select>
                <Input value={v.toelichting} onChange={(e) => zetVoorbeeld(i, { toelichting: e.target.value })} placeholder="Toelichting" aria-label={`Toelichting bij voorbeeld ${i + 1}`} />
                <button type="button" className={KNOP_KLEIN} onClick={() => zet("voorbeelden", voorbeelden.filter((_, j) => j !== i))}>
                  Weghalen
                </button>
              </div>
            </div>
          ))}
          <button type="button" className={KNOP_KLEIN} onClick={() => zet("voorbeelden", [...voorbeelden, { tekst: "", oordeel: "wel", toelichting: "" }])}>
            Voorbeeld toevoegen
          </button>
          {vanLex("voorbeelden")}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-ink">Eigenschappen</legend>
          {concept.rijen.map(([k, v], i) => (
            <div key={i} className="flex flex-col gap-2 sm:flex-row">
              <Input value={k} onChange={(e) => setConcept((c) => ({ ...c, rijen: c.rijen.map((r, j) => (j === i ? [e.target.value, r[1]] : r)) }))} placeholder="Eigenschap" aria-label={`Eigenschap ${i + 1}`} className="sm:w-48" />
              <Input value={v} onChange={(e) => setConcept((c) => ({ ...c, rijen: c.rijen.map((r, j) => (j === i ? [r[0], e.target.value] : r)) }))} placeholder="Waarde" aria-label={`Waarde van eigenschap ${i + 1}`} />
              <button type="button" className={KNOP_KLEIN} onClick={() => setConcept((c) => ({ ...c, rijen: c.rijen.filter((_, j) => j !== i) }))}>
                Weghalen
              </button>
            </div>
          ))}
          <button type="button" className={KNOP_KLEIN} onClick={() => setConcept((c) => ({ ...c, rijen: [...c.rijen, ["", ""]] }))}>
            Eigenschap toevoegen
          </button>
        </fieldset>

        <Field label="Open vragen" hint="één per regel">
          <Textarea value={concept.vragen} onChange={(e) => setConcept((c) => ({ ...c, vragen: e.target.value }))} rows={2} />
        </Field>
        {vanLex("open_vragen")}

        <ButtonRow align="start">
          <Button type="submit" disabled={!onbewaard || bezig || !inhoud.naam.trim()}>
            {bezig ? "Bezig…" : "Opslaan"}
          </Button>
          {onbewaard && (
            <Button type="button" variant="secondary" onClick={() => { setConcept(uitBegrip(begrip.inhoud)); setConflict(false); }}>
              Wijzigingen weggooien
            </Button>
          )}
        </ButtonRow>
      </form>

      <Accorderen id={id} begrip={begrip} onbewaard={onbewaard} muteer={muteer} />
      <Historie id={id} begrip={begrip} />

      <div className="border-t border-line pt-3">
        <VerwijderKnop soort="begrip" onBevestig={onVerwijder} />
      </div>
    </article>
  );
}

/** Accorderen en heropenen. De poort rekent de server; hier staan zijn redenen letterlijk. */
function Accorderen({ id, begrip, onbewaard, muteer }: {
  id: string;
  begrip: Begrip;
  onbewaard: boolean;
  muteer: BegripMutatie;
}) {
  const [bezig, setBezig] = useState(false);
  async function doe(actie: (r: number) => Promise<Begrip>, gelukt: string) {
    setBezig(true);
    await muteer(actie, { gelukt });
    setBezig(false);
  }

  if (begrip.status === "geaccordeerd")
    return (
      <section className="space-y-2 rounded-kaart bg-surface p-3" aria-label="Status">
        <p className="text-sm text-ink">
          Geaccordeerd door {begrip.geaccordeerd_door}
          {begrip.geaccordeerd_op && ` op ${tijd(begrip.geaccordeerd_op)}`}.
        </p>
        {begrip.aandachtspunten.map((a) => (
          <p key={a} className="text-xs text-aandacht-geel-tekst">{a}</p>
        ))}
        <NlSbbStand id={id} begrip={begrip} />
        <Button size="sm" variant="secondary" disabled={bezig} onClick={() => void doe((r) => heropenBegrip(id, begrip.id, r), "Heropend.")}>
          Heropenen
        </Button>
      </section>
    );

  const { mag, redenen } = begrip.accorderen;
  return (
    <section className="space-y-2 rounded-kaart bg-surface p-3" aria-label="Accorderen">
      {onbewaard ? (
        <p className="text-xs text-muted">Sla eerst je wijzigingen op; de poort kijkt naar wat bewaard is.</p>
      ) : !mag ? (
        <div>
          <p className="text-xs font-medium text-ink">Nog nodig om te accorderen:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-ink" aria-label="Nog nodig om te accorderen">
            {redenen.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-ink">Alles is er: naam, definitie, context en beoordeelde, actuele passages.</p>
      )}
      <NlSbbStand id={id} begrip={begrip} />
      <Button size="sm" disabled={!mag || onbewaard || bezig} onClick={() => void doe((r) => accordeerBegrip(id, begrip.id, r), "Geaccordeerd.")}>
        Accorderen
      </Button>
    </section>
  );
}

/** Is het begrip NL-SBB-conform (fase F3)? Diagnostisch: het houdt accorderen niet tegen, en een
 *  conforme kaart is daarmee nog niet juridisch juist. Opnieuw gevraagd bij elke revisie; faalt stil. */
function NlSbbStand({ id, begrip }: { id: string; begrip: Begrip }) {
  const [c, setC] = useState<Conformiteit | null>(null);
  useEffect(() => {
    let levend = true;
    haalConformiteit(id).then((x) => levend && setC(x)).catch(() => levend && setC(null));
    return () => { levend = false; };
  }, [id, begrip.id, begrip.revisie]);
  const stand = c?.begrippen[begrip.id];
  const zin = c ? conformZin(stand, c.nl_sbb_versie) : null;
  if (!zin || !stand) return null;
  const meldingen = stand.meldingen;
  return (
    <div className="text-xs" data-testid="nl-sbb-stand">
      <p className={stand.conform ? "text-muted" : "text-aandacht-geel-tekst"}>{zin}</p>
      {meldingen.length > 0 && (
        <details className="mt-1">
          <summary className="focus-ring cursor-pointer text-[11px] text-muted">Meldingen ({meldingen.length})</summary>
          <ul className="mt-1 space-y-0.5 pl-4 text-[11px] text-muted">
            {meldingen.map((m, i) => (
              <li key={i}>
                {m.laag === "nl_sbb" ? "NL-SBB" : "Platform"} · {m.ernst} · {veldVanPad(m.pad) || "begrip"}{m.melding ? `: ${m.melding}` : ""}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-[10px] text-faint">Een diagnose, geen blokkade: conform zegt iets over de vorm, niet over de juridische juistheid.</p>
        </details>
      )}
    </div>
  );
}

/** Per revisie wie wat deed, met de oude inhoud bewaard in de api. Pas geladen bij openklappen, en
 *  opnieuw bij een nieuwe revisie. */
function Historie({ id, begrip }: { id: string; begrip: Begrip }) {
  const [open, setOpen] = useState(false);
  const [revisies, setRevisies] = useState<BegripRevisie[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let levend = true;
    haalBegripRevisies(id, begrip.id)
      .then((r) => levend && setRevisies(r))
      .catch((e) => levend && setFout(foutTekst(e, "De historie kon niet worden geladen.")));
    return () => { levend = false; };
  }, [open, id, begrip.id, begrip.revisie]);

  return (
    // Zelfde vorm als de historie van een annotatie (`RevisieHistorie`).
    <details className="group rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded text-xs font-medium text-muted">
        <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />
        Historie <span className="font-normal text-faint">({begrip.revisie} {begrip.revisie === 1 ? "revisie" : "revisies"})</span>
      </summary>
      {fout ? (
        <p className="mt-2 text-xs text-aandacht-rood-tekst">{fout}</p>
      ) : !revisies ? (
        <p className="mt-2 text-xs text-muted">Laden…</p>
      ) : (
        <ol className="mt-2 space-y-1.5" aria-label="Historie van het begrip">
          {revisies.map((r) => (
            <li key={r.revisie} className="flex flex-col gap-0.5 border-b border-line pb-1.5 sm:flex-row sm:gap-3">
              <span className="shrink-0 text-xs text-muted sm:w-40">{tijd(r.tijdstip)}</span>
              <span className="text-ink">
                {revisieZin(r)} <span className="text-xs text-muted">· {r.actor} · revisie {r.revisie}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}
