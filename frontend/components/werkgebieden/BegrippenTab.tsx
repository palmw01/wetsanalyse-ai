"use client";

import { useCallback, useEffect, useState } from "react";

import { Button, LinkButton } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BegripWerk } from "@/components/werkgebieden/BegripWerk";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { exporteerBegrippen, foutTekst, haalHerbeoordelingen, lijstBegrippen, maakBegrip } from "@/lib/api";
import { geraakteBegrippen, herbeoordelingZin, strookKop } from "@/lib/herbeoordeling";
import type { BegrippenLijst, Herbeoordelingen } from "@/lib/types";

const EXPORT_FORMATEN = [
  { formaat: "csv" as const, label: "CSV", uitleg: "één rij per passage, met vindplaats en bron" },
  { formaat: "json" as const, label: "JSON", uitleg: "alle begrippen met hun koppelingen en bewijsstand" },
];

/** De begrippen van het werkgebied: links de lijst, daarnaast het gekozen begrip (kaart en
 *  passages). Begrippen zijn analyse-uitkomsten, geen wettelijke definities.
 *
 *  Het gekozen begrip staat in de URL (via `onKies`). Wie wisselt terwijl de kaart wijzigingen draagt
 *  die nog niet bewaard zijn, krijgt eerst de vraag of dat de bedoeling is – zonder systeemvenster. */
export function BegrippenTab({ id, gekozen, onKies, onbewaard, onOnbewaard }: {
  id: string;
  gekozen?: string;
  onKies: (begripId: string | undefined) => void;
  /** Draagt de kaart niet-bewaarde wijzigingen? Staat in `WerkgebiedClient`, dat ook een tabwissel
   *  ermee bewaakt. */
  onbewaard: boolean;
  onOnbewaard: (onbewaard: boolean) => void;
}) {
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  // Herbeoordelen (fase F1): begrippen waarvan een dragende passage veranderde. Vraagt de bronboom en
  // is dus trager dan de lijst; faalt stil, de lijst staat er dan gewoon.
  const [herbeoordeling, setHerbeoordeling] = useState<Herbeoordelingen | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [nieuweNaam, setNieuweNaam] = useState("");
  const [bezig, setBezig] = useState(false);
  // Met niet-bewaarde wijzigingen wacht een wissel van begrip op bevestiging.
  const [wachtendeKeuze, setWachtendeKeuze] = useState<string | null | undefined>(undefined);

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

  function kies(begripId: string | undefined) {
    if (begripId === gekozen) return;
    if (onbewaard) {
      setWachtendeKeuze(begripId ?? null);
      return;
    }
    onKies(begripId);
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
      {wachtendeKeuze !== undefined && (
        <OnbewaardMelding
          onBlijf={() => setWachtendeKeuze(undefined)}
          onToch={() => {
            const doel = wachtendeKeuze ?? undefined;
            setWachtendeKeuze(undefined);
            onOnbewaard(false);
            onKies(doel);
          }}
        />
      )}

      {/* De werkplek in de context van dit werkgebied: daar vraag je Lex om begrippen, en de
          voorstellen openen als artefact naast het gesprek. */}
      <div className="flex justify-end">
        <LinkButton href={`/workbench?werkgebied=${encodeURIComponent(id)}`} variant="secondary" size="sm"
          className="w-full sm:w-auto">
          Bespreek met Lex
        </LinkButton>
      </div>

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
                  onClick={() => kies(b.begrip_id)}
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
              onDownload={(f) => exporteerBegrippen(id, f as "csv" | "json")}
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
            <ul className="space-y-1.5" aria-label="Begrippen in dit werkgebied">
              {lijst.begrippen.filter((b) => b.status !== "vervangen").map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => kies(b.id)}
                    aria-current={b.id === gekozen ? "true" : undefined}
                    className={`focus-ring w-full rounded-kaart border px-3 py-2 text-left transition-colors coarse:min-h-[44px] ${
                      b.id === gekozen ? "border-lint bg-lint/5" : "border-line bg-paper hover:bg-surface"
                    }`}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-sm font-medium text-lint">{b.inhoud.naam}</span>
                      <span className={`shrink-0 text-[11px] ${b.status === "geaccordeerd" ? "text-ink" : "text-muted"}`}>
                        {b.status === "geaccordeerd" ? "geaccordeerd" : "concept"}
                      </span>
                    </span>
                    <span className="block text-xs text-muted">
                      {b.aantal_koppelingen === 1 ? "1 passage" : `${b.aantal_koppelingen} passages`}
                    </span>
                    {geraakt.has(b.id) ? (
                      <span className="mt-0.5 block text-xs text-aandacht-geel-tekst">
                        Herbeoordelen: {herbeoordelingZin(geraakt.get(b.id)!.passages, geraakt.get(b.id)!.relaties)}
                      </span>
                    ) : b.aandachtspunten[0] && (
                      <span className="mt-0.5 block text-xs text-aandacht-geel-tekst">{b.aandachtspunten[0]}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
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
              <BegripWerk
                key={gekozen}
                id={id}
                begripId={gekozen!}
                primair={lijst?.primair ?? {}}
                andere={lijst?.begrippen ?? []}
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
