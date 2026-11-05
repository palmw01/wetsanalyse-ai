"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BewerkVoet, useBewerken } from "@/components/ui/Bewerkbaar";
import { Button } from "@/components/ui/Button";
import { FilterChip } from "@/components/ui/FilterChip";
import { Input } from "@/components/ui/Field";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { BEGRIP_STATUS_TOON } from "@/components/werkgebieden/BegripInhoud";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { GeneriekGebruiken } from "@/components/werkgebieden/GeneriekGebruiken";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { exporteerBegrippen, foutTekst, haalHerbeoordelingen, lijstBegrippen, maakBegrip } from "@/lib/api";
import { EXPORT_FORMATEN, filterBegrippen, type BegripStatusFilter } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL, BEGRIP_STATUSSEN, kort } from "@/lib/begrippenOverzicht";
import { geraakteBegrippen, herbeoordelingZin, strookKop } from "@/lib/herbeoordeling";
import type { BegripSamenvatting, BegrippenLijst, Herbeoordelingen } from "@/lib/types";
import { begripPad } from "@/lib/werkgebiedPaden";

/** Het begrippenkader van een werkgebied, in de vorm van de tab Bronnen (spoor N): eerst *Te doen* – de termen die Lex
 *  voorstelt en de begrippen om te herbeoordelen –, dan de begrippen als rijen. Een rij opent de pagina van het begrip,
 *  daar lees en besluit je. Begrippen zijn analyse-uitkomsten, geen wettelijke definities. */
export function BegrippenKader({ id }: { id: string }) {
  const router = useRouter();
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  // Herbeoordelen (fase F1) vraagt de bronboom en is dus trager dan de lijst; faalt stil, de lijst staat er gewoon.
  const [herbeoordeling, setHerbeoordeling] = useState<Herbeoordelingen | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [zoek, setZoek] = useState("");
  const [status, setStatus] = useState<BegripStatusFilter>("alle");
  const [gebruiken, setGebruiken] = useState(false);

  const laad = useCallback(async () => {
    void haalHerbeoordelingen(id).then(setHerbeoordeling, () => setHerbeoordeling(null));
    try {
      setLijst(await lijstBegrippen(id));
    } catch (e) {
      setFout(foutTekst(e, "De begrippen konden niet worden geladen."));
    }
  }, [id]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const nieuw = useBewerken({
    begin: "",
    opslaan: async (naam) => {
      const b = await maakBegrip(id, { inhoud: { naam: naam.trim() } });
      router.push(begripPad(id, b.id));
    },
  });

  const geraakt = geraakteBegrippen(herbeoordeling);
  const begrippen = useMemo(() => lijst?.begrippen ?? [], [lijst]);
  const getoond = useMemo(() => filterBegrippen(begrippen, { term: zoek, status }), [begrippen, zoek, status]);
  const teDoen = [...(herbeoordeling?.begrippen ?? []).map((b) => (
    <GroepRij key={b.begrip_id} href={begripPad(id, b.begrip_id)} data-herbeoordelen={b.begrip_id} titel={b.naam}
      sub={herbeoordelingZin(b.koppelingen.length, b.relaties?.length ?? 0)}
      status={<StatusLabel toon="geel">Herbeoordelen</StatusLabel>} />
  )), ...(herbeoordeling?.generiek ?? []).map((g) => (
    <GroepRij key={`generiek-${g.begrip_id}`} href={begripPad(id, g.begrip_id)} data-herbeoordelen={g.begrip_id} titel={g.naam}
      sub={g.opvolger ? `Vervangen door ${g.opvolger.naam}` : "Het generieke begrip veranderde"}
      status={<StatusLabel toon="geel">Herbeoordelen</StatusLabel>} />
  ))];

  return (
    <div className="space-y-5" data-begrippen-kader>
      {fout && <Melding type="fout">{fout}</Melding>}

      <BegripVoorstellen id={id} kop="Te doen" boven={teDoen}
        sub={herbeoordeling?.begrippen.length ? <>
          {strookKop(herbeoordeling)}
          {!herbeoordeling.volledig && " Niet elke bron kon worden opgehaald; wat daar veranderde staat er niet bij."}
        </> : undefined} />

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <input type="search" value={zoek} onChange={(e) => setZoek(e.target.value)} placeholder="Zoek op naam, term of definitie"
          aria-label="Begrippen doorzoeken"
          className="focus-ring min-h-[36px] w-full rounded-field border border-line bg-paper px-3 text-sm sm:max-w-xs" />
        <div className="flex flex-wrap gap-1" role="group" aria-label="Status">
          {(["alle", ...BEGRIP_STATUSSEN] as const).map((s) => (
            <FilterChip key={s} gekozen={status === s} onKies={() => setStatus(s)}>
              {s === "alle" ? "Alle" : BEGRIP_STATUS_LABEL[s]}
            </FilterChip>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:ml-auto sm:flex-row sm:items-center">
          {begrippen.length > 0 && (
            <ExportKnop formaten={EXPORT_FORMATEN} onFout={setFout}
              onDownload={(f) => exporteerBegrippen(id, f as (typeof EXPORT_FORMATEN)[number]["formaat"])} />
          )}
          <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setGebruiken(true)}>Generiek begrip gebruiken</Button>
          {!nieuw.open && <Button size="sm" variant="secondary" className="w-full sm:w-auto" onClick={nieuw.start}>Nieuw begrip</Button>}
        </div>
      </div>

      {nieuw.open && (
        <div role="group" aria-label="Nieuw begrip">
          <Input autoFocus value={nieuw.concept} onChange={(e) => nieuw.zet(e.target.value)} onKeyDown={nieuw.toetsen(true)}
            placeholder="Naam van het nieuwe begrip" aria-label="Naam van het nieuwe begrip" maxLength={200} />
          <BewerkVoet onAnnuleer={nieuw.annuleer} onOpslaan={() => void nieuw.slaOp()} bezig={nieuw.bezig}
            gewijzigd={!!nieuw.concept.trim()} opslaanTekst="Aanmaken" fout={nieuw.fout} />
        </div>
      )}

      {lijst === null ? (
        !fout && <div className="space-y-2"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
      ) : (
        <Groep kop="Begrippen" telling={getoond.length} label="Begrippen in dit werkgebied"
          leeg={begrippen.length
            ? "Geen begrippen bij deze keuze."
            : "Nog geen begrippen. Maak er hier een, of kies in de annotaties de passages waaruit een begrip ontstaat."}>
          {getoond.map((b) => <BegripRij key={b.id} id={id} begrip={b}
            aandacht={geraakt.has(b.id)
              ? `Herbeoordelen: ${herbeoordelingZin(geraakt.get(b.id)!.passages, geraakt.get(b.id)!.relaties)}`
              : b.aandachtspunten[0]} />)}
        </Groep>
      )}
      {gebruiken && <GeneriekGebruiken id={id} gebruikt={begrippen} onSluit={() => setGebruiken(false)} />}
    </div>
  );
}

function BegripRij({ id, begrip: b, aandacht }: { id: string; begrip: BegripSamenvatting; aandacht?: string }) {
  return (
    <GroepRij href={begripPad(id, b.id)} data-begrip-rij={b.id}
      titel={<span className={b.status === "vervangen" ? "line-through" : ""}>{b.inhoud.naam}</span>}
      status={<>
        {b.kader === "generiek" && <StatusLabel toon="lint">Generiek</StatusLabel>}
        <StatusLabel toon={BEGRIP_STATUS_TOON[b.status]}>{BEGRIP_STATUS_LABEL[b.status]}</StatusLabel>
      </>}
      sub={<>
        {b.aantal_koppelingen === 1 ? "1 passage" : `${b.aantal_koppelingen} passages`}
        {b.inhoud.definitie && ` · ${kort(b.inhoud.definitie)}`}
        {b.vervangen_door && ` · vervangen door ${b.vervangen_door.naam}`}
        {aandacht && <span className="mt-0.5 block text-aandacht-geel-tekst">{aandacht}</span>}
      </>} />
  );
}
