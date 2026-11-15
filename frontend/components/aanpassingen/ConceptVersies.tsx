"use client";

import Link from "next/link";
import { useState } from "react";

import { Bestandenlijst } from "@/components/ui/Bestandenlijst";
import { Button, LinkButton } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart } from "@/components/ui/Pagina";
import { Tekstverschil } from "@/components/ui/Tekstverschil";
import { datumTijd } from "@/lib/datum";
import {
  bestandsvolgorde, conceptPad, versiePad, wijzigingZin, wijzigingen, type Bestanden, type WerkplaatsOnderdeel, type WerkplaatsVersie,
} from "@/lib/werkplaats";

/** Hoeveel versies de kaart meteen toont; de rest klapt uit. */
const EERST = 8;

/** De versies van een concept, de nieuwste boven (ADR-016 §B7, stap B2-3): wie, wanneer, de toelichting, of de versie de
 *  controle haalt en welke er draait. Een klik opent die versie om te lezen en te vergelijken; de laatste versie opent
 *  de pagina zoals ze is. Versies groeien alleen aan: hier wordt niets gewijzigd. */
export function VersiesKaart({ o, gekozen }: { o: WerkplaatsOnderdeel; gekozen: number | null }) {
  const [alles, setAlles] = useState(false);
  const lijst = [...(o.versielijst ?? [])].sort((a, b) => b.nummer - a.nummer);
  const laatste = lijst[0]?.nummer ?? 0;
  const getoond = alles ? lijst : lijst.slice(0, EERST);
  return (
    <Kaart titel="Versies" telling={lijst.length} data-blok="versies"
      acties={lijst.length > 1 && gekozen === null
        ? <Link href={versiePad(o.id, laatste)} className="focus-ring rounded text-xs font-medium text-lint hover:underline" data-actie="vergelijk-laatste">Vergelijk</Link>
        : undefined}>
      <ul aria-label="Versies van dit concept" className="-mx-1 space-y-0.5">
        {getoond.map((v) => {
          const hier = gekozen === v.nummer || (gekozen === null && v.nummer === laatste);
          return (
            <li key={v.nummer}>
              <Link href={v.nummer === laatste ? conceptPad(o.id) : versiePad(o.id, v.nummer)} aria-current={hier ? "true" : undefined}
                data-versie={v.nummer}
                className="focus-ring block rounded-knop px-2 py-1.5 text-sm text-ink transition-colors hover:bg-surface aria-[current=true]:bg-lint/[0.06]">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="font-medium text-lint">Versie {v.nummer}</span>
                  {v.actief && <StatusLabel toon="groen" uitleg="Dit is de versie die Lex gebruikt.">draait nu</StatusLabel>}
                  {!v.geldig && <StatusLabel toon="geel" uitleg="Deze versie haalt de controle niet.">
                    {v.bevindingen.length === 1 ? "1 bevinding" : `${v.bevindingen.length} bevindingen`}</StatusLabel>}
                </span>
                <span className="block text-xs text-muted [overflow-wrap:anywhere]">{datumTijd(v.gemaakt)} · {v.door}</span>
                {v.toelichting && <span className="block text-xs text-ink [overflow-wrap:anywhere]">{v.toelichting}</span>}
              </Link>
            </li>
          );
        })}
      </ul>
      {lijst.length > EERST && !alles && (
        <Button variant="secondary" size="xs" className="mt-2" onClick={() => setAlles(true)} data-actie="versies-alle">
          Toon alle {lijst.length} versies</Button>
      )}
    </Kaart>
  );
}

/** Eén versie om te lezen en te vergelijken met een andere. Alleen lezen: een oude versie wijzigt nooit. *Zet terug
 *  als concept* neemt haar bestanden over als wijziging op de laatste versie; pas opslaan maakt daar een nieuwe versie van. */
export function VersieWeergave({ o, versie, met, andere, bestand, onKiesBestand, onKiesMet, onTerugzetten, zij }: {
  o: WerkplaatsOnderdeel;
  versie: WerkplaatsVersie;
  /** De versie waarmee vergeleken wordt, met haar bestanden; `null` zonder vergelijking (of nog aan het laden). */
  met: WerkplaatsVersie | null;
  /** De nummers waaruit te kiezen is om mee te vergelijken. */
  andere: number[];
  bestand: string;
  onKiesBestand: (pad: string) => void;
  onKiesMet: (nummer: number | null) => void;
  /** Alleen voor de eigenaar, op een concept dat niet is ingetrokken, en niet op de laatste versie. */
  onTerugzetten?: () => void;
  zij: React.ReactNode;
}) {
  const [inhoud, setInhoud] = useState(false);
  const nu: Bestanden = versie.bestanden ?? {};
  const toen: Bestanden | null = met?.bestanden ?? null;
  const w = toen ? wijzigingen(toen, nu) : null;
  // Wat sinds de andere versie verdween, staat ook in de lijst: anders is een verwijderd bestand niet te zien.
  const paden = bestandsvolgorde([...Object.keys(nu), ...(w?.verwijderd ?? [])]);
  const gekozen = paden.includes(bestand) ? bestand : (w && [...w.gewijzigd, ...w.toegevoegd, ...w.verwijderd][0]) || paden[0] || "";
  const stand = (p: string) => (!w ? "" : w.gewijzigd.includes(p) ? "gewijzigd" : w.toegevoegd.includes(p) ? "nieuw" : w.verwijderd.includes(p) ? "verwijderd" : "");
  const laatste = o.laatste?.nummer ?? versie.nummer;
  const PRE = "max-w-full whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink [overflow-wrap:anywhere]";

  return (
    <div data-versie-weergave={versie.nummer} data-vergeleken-met={met?.nummer ?? ""}>
      <div className="mb-4" data-melding="oude-versie">
        <Melding type="uitleg">
          Je bekijkt versie {versie.nummer} van {datumTijd(versie.gemaakt)}, door {versie.door}.
          {versie.nummer === laatste ? " Dit is de laatste versie." : " Een eerdere versie is alleen te lezen."}
          {w && ` Vergeleken met versie ${met?.nummer}: ${w.aantal ? wijzigingZin(w) : "geen verschil"}.`}
        </Melding>
      </div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="sm:w-56">
          <Field label="Vergelijk met">
            <Select value={met ? String(met.nummer) : ""} onChange={(e) => onKiesMet(e.target.value ? Number(e.target.value) : null)}
              data-vergelijk-met>
              <option value="">niets</option>
              {andere.map((n) => <option key={n} value={n}>versie {n}</option>)}
            </Select>
          </Field>
        </div>
        <LinkButton href={conceptPad(o.id)} variant="secondary" size="sm" className="w-full sm:w-auto">
          {versie.nummer === laatste ? "Terug naar het concept" : "Ga naar de laatste versie"}</LinkButton>
        {onTerugzetten && (
          <Button variant="secondary" size="sm" className="w-full sm:w-auto" onClick={onTerugzetten} data-actie="terugzetten"
            title={`De bestanden van versie ${versie.nummer} komen als wijziging op versie ${laatste} te staan. Er verandert niets tot je opslaat.`}>
            Zet terug als concept</Button>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <Kaart titel="Bestanden" telling={Object.keys(nu).length} data-blok="bestanden">
            <Bestandenlijst paden={paden} gekozen={gekozen} onKies={onKiesBestand} label={`Bestanden van versie ${versie.nummer}`} stand={stand}
              bij={(p) => stand(p) && (
                <StatusLabel toon={stand(p) === "verwijderd" ? "neutraal" : "lint"}
                  uitleg={`${stand(p) === "nieuw" ? "Nieuw" : stand(p) === "verwijderd" ? "Verwijderd" : "Gewijzigd"} sinds versie ${met?.nummer}`}>{stand(p)}</StatusLabel>)} />
          </Kaart>
          {zij}
        </div>
        <Kaart data-blok="inhoud" titel={<span className="font-mono text-sm [overflow-wrap:anywhere]">{gekozen || "Geen bestanden"}</span>}
          acties={toen && gekozen && stand(gekozen) !== "verwijderd" ? (
            <Button variant="secondary" size="xs" aria-pressed={inhoud} onClick={() => setInhoud((x) => !x)} data-actie="verschil-of-inhoud">
              {inhoud ? "Verschil" : "Inhoud"}</Button>) : undefined}>
          {!gekozen ? <p className="text-sm text-muted">Deze versie heeft geen bestanden.</p>
            : toen && (!inhoud || stand(gekozen) === "verwijderd") ? (
              <Tekstverschil oud={toen[gekozen] ?? ""} nieuw={nu[gekozen] ?? ""}
                label={`Verschil in ${gekozen} tussen versie ${met?.nummer} en versie ${versie.nummer}`} />
            ) : <pre data-bestand-inhoud={gekozen} className={PRE}>{nu[gekozen]}</pre>}
        </Kaart>
      </div>
    </div>
  );
}
