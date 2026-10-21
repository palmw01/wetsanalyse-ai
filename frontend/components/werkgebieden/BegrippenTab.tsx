"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Lijst, LijstRij } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { BegripPaneel } from "@/components/werkgebieden/BegripPaneel";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BegripWerk } from "@/components/werkgebieden/BegripWerk";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { exporteerBegrippen, foutTekst, haalHerbeoordelingen, lijstBegrippen, maakBegrip } from "@/lib/api";
import type { BegripWeergave } from "@/lib/begrippen";
import { geraakteBegrippen, herbeoordelingZin, strookKop } from "@/lib/herbeoordeling";
import type { BegripSamenvatting, BegrippenLijst, Herbeoordelingen } from "@/lib/types";

const EXPORT_FORMATEN = [
  { formaat: "csv" as const, label: "CSV", uitleg: "één rij per passage, met vindplaats en bron" },
  { formaat: "json" as const, label: "JSON", uitleg: "alle begrippen met hun koppelingen en bewijsstand" },
  { formaat: "ttl" as const, label: "Turtle (NL-SBB)", uitleg: "de geaccordeerde begrippen als begrippenkader, met conformiteit per begrip" },
  { formaat: "ttl-alle" as const, label: "Turtle, alle begrippen", uitleg: "ook concepten en vervangen begrippen, met hun status" },
];

/** De begrippen van het werkgebied: links de lijst, daarnaast het gekozen begrip. Begrippen zijn
 *  analyse-uitkomsten, geen wettelijke definities.
 *
 *  Het gekozen begrip opent om te lezen (`BegripPaneel`, F3e: de leesweergave met de voorstellen van Lex
 *  per veld); *Begripskaart* wisselt naar de kaart met passages, relaties en accorderen (`BegripWerk`).
 *  Er staat er steeds één, en de keuze blijft staan bij een wissel van begrip: wie op de kaart werkt en
 *  een opvolger maakt, landt op diens kaart. Lex vraag je in het gesprek, via *Vraag Lex* bij elk begrip.
 *
 *  Het gekozen begrip staat in de URL (via `onKies`). Wie wisselt terwijl de kaart wijzigingen draagt
 *  die nog niet bewaard zijn, krijgt eerst de vraag of dat de bedoeling is – zonder systeemvenster. */
export function BegrippenTab({ id, gekozen, onKies, onbewaard, onOnbewaard, weergave, onWeergave }: {
  id: string;
  gekozen?: string;
  onKies: (begripId: string | undefined, weergave?: BegripWeergave) => void;
  /** Draagt de kaart niet-bewaarde wijzigingen? Staat in `WerkgebiedClient`, dat ook een tabwissel
   *  ermee bewaakt. */
  onbewaard: boolean;
  onOnbewaard: (onbewaard: boolean) => void;
  /** Lezen of de kaart; staat in `WerkgebiedClient` (en in de URL), zodat hij een wissel van begrip overleeft. */
  weergave: BegripWeergave;
  onWeergave: (w: BegripWeergave) => void;
}) {
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  // Herbeoordelen (fase F1): begrippen waarvan een dragende passage veranderde. Vraagt de bronboom en
  // is dus trager dan de lijst; faalt stil, de lijst staat er dan gewoon.
  const [herbeoordeling, setHerbeoordeling] = useState<Herbeoordelingen | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [nieuweNaam, setNieuweNaam] = useState("");
  const [bezig, setBezig] = useState(false);
  // Met niet-bewaarde wijzigingen wacht een wissel van begrip op bevestiging.
  const [wachtendeKeuze, setWachtendeKeuze] = useState<{ id?: string; weergave?: BegripWeergave } | null>(null);

  const laadLijst = useCallback(async () => {
    void haalHerbeoordelingen(id).then(setHerbeoordeling, () => setHerbeoordeling(null));
    try {
      setLijst(await lijstBegrippen(id));
    } catch (e) {
      setFout(foutTekst(e, "De begrippen konden niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laadLijst();
  }, [laadLijst]);

  function kies(begripId: string | undefined, w?: BegripWeergave) {
    if (begripId === gekozen && (!w || w === weergave)) return;
    if (onbewaard) {
      setWachtendeKeuze({ id: begripId, weergave: w });
      return;
    }
    onKies(begripId, w);
  }

  async function maak(e: React.FormEvent) {
    e.preventDefault();
    if (!nieuweNaam.trim() || bezig) return;
    setBezig(true);
    setFout(null);
    try {
      const b = await maakBegrip(id, { inhoud: { naam: nieuweNaam.trim() } });
      setNieuweNaam("");
      await laadLijst();
      onKies(b.id);
    } catch (err) {
      setFout(foutTekst(err, "Het begrip kon niet worden aangemaakt."));
    } finally {
      setBezig(false);
    }
  }

  const gekozenBestaat = !!gekozen && !!lijst?.begrippen.some((b) => b.id === gekozen);
  const geraakt = geraakteBegrippen(herbeoordeling);

  return (
    <div className="space-y-4">
      {fout && <Melding type="fout">{fout}</Melding>}
      {wachtendeKeuze && (
        <OnbewaardMelding
          onBlijf={() => setWachtendeKeuze(null)}
          onToch={() => {
            const doel = wachtendeKeuze;
            setWachtendeKeuze(null);
            onOnbewaard(false);
            onKies(doel.id, doel.weergave);
          }}
        />
      )}

      <BegripVoorstellen
        id={id}
        onGewijzigd={laadLijst}
        onBegrip={(b) => {
          // Na een overname staat het nieuwe begrip er pas na het verversen van de lijst.
          void laadLijst().then(() => kies(b));
        }}
      />

      {herbeoordeling && herbeoordeling.begrippen.length > 0 && (
        <section aria-label="Herbeoordelen" className="rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-3 py-2">
          <p className="text-sm font-medium text-aandacht-geel-tekst">{strookKop(herbeoordeling)}</p>
          <p className="mt-0.5 text-xs text-ink">
            De wettekst of de annotatie onder een dragende passage veranderde. De oude bewijsstand blijft; jij
            beslist of het begrip nog klopt, herkoppelt of de passage losmaakt.
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Begrippen om te herbeoordelen">
            {herbeoordeling.begrippen.map((b) => (
              <li key={b.begrip_id}>
                <button
                  type="button"
                  onClick={() => kies(b.begrip_id, "kaart")}
                  aria-current={b.begrip_id === gekozen ? "true" : undefined}
                  className="focus-ring inline-flex min-h-[24px] items-center rounded-full border border-aandacht-geel-rand bg-paper px-2.5 py-0.5 text-[11px] font-medium text-ink hover:bg-surface coarse:min-h-[44px]"
                >
                  {b.naam} · {herbeoordelingZin(b.koppelingen.length, b.relaties?.length ?? 0)}
                </button>
              </li>
            ))}
          </ul>
          {!herbeoordeling.volledig && (
            <p className="mt-1.5 text-xs text-muted">
              Niet elke bron kon worden opgehaald; wat daar veranderde staat er niet bij.
            </p>
          )}
        </section>
      )}

      <div className="gap-5 lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
        {/* Op een smal scherm de lijst óf het begrip; vanaf lg naast elkaar. */}
        <aside className={`space-y-3 ${gekozenBestaat ? "hidden lg:block" : ""}`} aria-label="Begrippen">
          <form onSubmit={maak} className="flex flex-col gap-2">
            <Input
              value={nieuweNaam}
              onChange={(e) => setNieuweNaam(e.target.value)}
              placeholder="Naam van een nieuw begrip"
              aria-label="Naam van een nieuw begrip"
              maxLength={200}
            />
            <Button type="submit" size="sm" disabled={bezig || !nieuweNaam.trim()}>
              Nieuw begrip
            </Button>
          </form>
          {lijst && lijst.begrippen.length > 0 && (
            <ExportKnop
              formaten={EXPORT_FORMATEN}
              onFout={setFout}
              onDownload={(f) => exporteerBegrippen(id, f as (typeof EXPORT_FORMATEN)[number]["formaat"])}
            />
          )}
          {lijst === null ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : lijst.begrippen.length === 0 ? (
            <p className="text-sm text-muted">
              Nog geen begrippen. Maak er hier een, of kies op de tab Elementen de passages waaruit een
              begrip ontstaat.
            </p>
          ) : (
            <>
            <Lijst label="Begrippen in dit werkgebied">
              {lijst.begrippen.filter((b) => b.status !== "vervangen").map((b) => (
                <BegripRij key={b.id} id={id} begrip={b} gekozen={b.id === gekozen} onKies={() => kies(b.id)}
                  aandacht={geraakt.has(b.id)
                    ? `Herbeoordelen: ${herbeoordelingZin(geraakt.get(b.id)!.passages, geraakt.get(b.id)!.relaties)}`
                    : b.aandachtspunten[0]} />
              ))}
            </Lijst>
            {lijst.begrippen.some((b) => b.status === "vervangen") && (
              <details className="text-xs text-muted">
                <summary className="focus-ring cursor-pointer rounded">
                  Vervangen ({lijst.begrippen.filter((b) => b.status === "vervangen").length})
                </summary>
                <ul className="mt-1.5 space-y-1" aria-label="Vervangen begrippen">
                  {lijst.begrippen.filter((b) => b.status === "vervangen").map((b) => (
                    <li key={b.id}>
                      <button type="button" onClick={() => kies(b.id)} aria-current={b.id === gekozen ? "true" : undefined}
                        className="focus-ring w-full rounded px-2 py-1 text-left hover:bg-surface coarse:min-h-[44px]">
                        <span className="line-through">{b.inhoud.naam}</span>
                        {b.vervangen_door && <span className="block">vervangen door {b.vervangen_door.naam}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            </>
          )}
        </aside>

        <div className="min-w-0">
          {gekozen && lijst && !gekozenBestaat ? (
            <Melding type="uitleg">Dit begrip bestaat niet (meer) in dit werkgebied.</Melding>
          ) : gekozenBestaat ? (
            <>
              <button
                type="button"
                onClick={() => kies(undefined)}
                className="focus-ring mb-3 inline-flex items-center gap-1 rounded text-xs text-muted hover:text-ink lg:hidden"
              >
                <ChevronOmlaag className="rotate-90" /> Alle begrippen
              </button>
              <GekozenBegrip
                key={gekozen}
                id={id}
                begripId={gekozen!}
                lijst={lijst!}
                weergave={weergave}
                onWeergave={onWeergave}
                onGewijzigd={laadLijst}
                onOnbewaard={onOnbewaard}
                onNaarBegrip={(b) => {
                  onOnbewaard(false);
                  void laadLijst().then(() => onKies(b));
                }}
                onWeg={async () => {
                  onOnbewaard(false);
                  await laadLijst();
                  onKies(undefined);
                }}
              />
            </>
          ) : (
            lijst && lijst.begrippen.length > 0 && (
              <p className="hidden text-sm text-muted lg:block">Kies links een begrip.</p>
            )
          )}
        </div>
      </div>
    </div>
  );
}

/** Eén begrip in de lijst: de naam kiest het, *Vraag Lex* zet het als onderwerp in het gesprek. */
function BegripRij({ id, begrip: b, gekozen, aandacht, onKies }: {
  id: string;
  begrip: BegripSamenvatting;
  gekozen: boolean;
  /** Geel onder de rij: wat herbeoordeeld moet, of het eerste aandachtspunt. */
  aandacht?: string;
  onKies: () => void;
}) {
  return (
    <LijstRij actief={gekozen} data-begrip-rij={b.id}
      titel={
        <button type="button" onClick={onKies} aria-current={gekozen ? "true" : undefined}
          className="focus-ring rounded text-left font-medium text-lint hover:underline coarse:min-h-[44px]">
          {b.inhoud.naam}
        </button>
      }
      status={<span className={`text-[11px] ${b.status === "geaccordeerd" ? "text-ink" : "text-muted"}`}>
        {b.status === "geaccordeerd" ? "geaccordeerd" : "concept"}
      </span>}
      meta={<>
        {b.aantal_koppelingen === 1 ? "1 passage" : `${b.aantal_koppelingen} passages`}
        {aandacht && <span className="mt-0.5 block text-aandacht-geel-tekst">{aandacht}</span>}
      </>}
      acties={<VraagLexKnop onderwerp={{ soort: "begrip", werkgebied_id: id, id: b.id, label: b.inhoud.naam }}
        className="justify-center" />}
    />
  );
}

/** Het gekozen begrip: lezen (`BegripPaneel`) of de kaart (`BegripWerk`). Een wissel met niet-bewaarde
 *  wijzigingen vraagt eerst bevestiging, net als een wissel van begrip. */
function GekozenBegrip({ id, begripId, lijst, weergave, onWeergave, onGewijzigd, onOnbewaard, onNaarBegrip, onWeg }: {
  id: string;
  begripId: string;
  lijst: BegrippenLijst;
  weergave: BegripWeergave;
  onWeergave: (w: BegripWeergave) => void;
  onGewijzigd: () => void;
  onOnbewaard: (onbewaard: boolean) => void;
  onNaarBegrip: (begripId: string) => void;
  onWeg: () => Promise<void>;
}) {
  const [onbewaard, setOnbewaard] = useState(false);
  const [wachtend, setWachtend] = useState(false);
  const meld = useCallback((o: boolean) => {
    setOnbewaard(o);
    onOnbewaard(o);
  }, [onOnbewaard]);

  function wissel() {
    const naar = weergave === "lezen" ? "kaart" : "lezen";
    if (onbewaard) return setWachtend(true);
    onWeergave(naar);
    if (naar === "lezen") onGewijzigd();
  }

  return (
    <div className="space-y-3" data-begrip-weergave={weergave}>
      <div className="flex justify-end">
        <Button size="sm" variant="secondary" className="w-full sm:w-auto" onClick={wissel}>
          {weergave === "lezen" ? "Begripskaart" : "Terug naar het begrip"}
        </Button>
      </div>
      {wachtend && (
        <OnbewaardMelding
          onBlijf={() => setWachtend(false)}
          onToch={() => {
            setWachtend(false);
            meld(false);
            onWeergave(weergave === "lezen" ? "kaart" : "lezen");
          }}
        />
      )}
      {weergave === "lezen" ? (
        <BegripPaneel werkgebiedId={id} begripId={begripId} onOnbewaard={meld} onNaarBegrip={onNaarBegrip} />
      ) : (
        <BegripWerk
          id={id}
          begripId={begripId}
          primair={lijst.primair ?? {}}
          andere={lijst.begrippen}
          onGewijzigd={onGewijzigd}
          onOnbewaard={meld}
          onNaarBegrip={onNaarBegrip}
          onWeg={onWeg}
        />
      )}
    </div>
  );
}
