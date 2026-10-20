"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BegripWerk } from "@/components/werkgebieden/BegripWerk";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { foutTekst, haalDeelvragenDekking, haalWerkgebied, lijstBegrippen } from "@/lib/api";
import { werkgebiedLabel, type WerkgebiedArtefact } from "@/lib/artefact";
import { STAND_KLASSE, STAND_LABEL, STAND_UITLEG, dekkingZin, isDeelvragenDekking, splits } from "@/lib/deelvragen";
import type { BegrippenLijst, DeelvragenDekking, Werkgebied } from "@/lib/types";
import { DOSSIER_VELDEN, STATUS_LABEL } from "@/lib/werkgebied";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";

const TAB: Record<WerkgebiedArtefact["soort"], string> = { begrippen: "begrippen", bronnen: "bronnen", werkgebied: "" };

/** Een artefact van een werkgebied in de werkplek, in dezelfde schil als een annotatie (een kolom naast
 *  de chat vanaf 1280px, anders een sheet):
 *
 *  - **begrippen** – de voorstellen van Lex (`BegripVoorstellen`), dezelfde inhoud als op de tab
 *    Begrippen. Een overgenomen begrip opent in het werkgebied: daar staan de kaart en de passages.
 *  - **bronnen** – de bepalingen die Lex vond (`BronKandidaten`), dezelfde inhoud als op de tab Bronnen.
 *  - **één begrip** (`begrip_id`, een kaartactie vanuit het gesprek, fase F4) – de kaart met Lex ernaast
 *    (`BegripWerk`), dezelfde als op de tab Begrippen; de voorstellen staan onder hun veld.
 *  - **werkgebied** – het werkgebied dat Lex met de analist samenstelde (activiteit 1): naam,
 *    analysevraag, afbakening en bronnen, en de weg naar de pagina van het werkgebied.
 *
 *  Eén inhoud, twee schillen. Net als op de tab vraagt het paneel eerst bevestiging als de kaart
 *  niet-bewaarde wijzigingen draagt: bij sluiten (kruisje, Escape, achtergrond) en bij een link weg. */
export function WerkgebiedArtefactPaneel({ doel, variant = "side", onSluit, onMeedenken }: {
  doel: WerkgebiedArtefact;
  variant?: DialogVariant;
  onSluit: () => void;
  /** Lex laten meedenken (fase C) in het gesprek dat hier open staat; zonder deze haak navigeert de
   *  strook naar een vers gesprek, en dat start niet in een werkplek die al open is. */
  onMeedenken?: (werkgebiedId: string, aantal: number) => void;
}) {
  const router = useRouter();
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const sluit = () => bewaker.bewaak(onSluit, "sluiten");
  const naarWerkgebied = `/werkgebieden/${encodeURIComponent(doel.werkgebied_id)}` +
    (TAB[doel.soort] ? `?tab=${TAB[doel.soort]}` : "") +
    (doel.begrip_id ? `&begrip=${encodeURIComponent(doel.begrip_id)}` : "");
  const soort = werkgebiedLabel(doel);
  const titel = doel.titel || soort;
  return (
    <Dialog label={`${soort}: ${titel}`} variant={variant} onSluit={sluit}>
      <div data-artefact data-artefact-soort={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-start gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{doel.soort === "werkgebied" ? "Samengesteld met Lex" : `${soort} van Lex`}</p>
            <h2 className="truncate font-display text-base font-semibold text-lint">{titel}</h2>
            <Link href={naarWerkgebied} className="focus-ring text-xs font-medium text-lint underline-offset-2 hover:underline">
              Open het werkgebied
            </Link>
          </div>
          <button
            type="button"
            onClick={sluit}
            aria-label="Sluiten"
            className="focus-ring -mr-1 shrink-0 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink"
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {bewaker.wachtend && (
            <OnbewaardMelding
              className="mb-4"
              handeling={bewaker.wachtend.handeling}
              onBlijf={bewaker.blijf}
              onToch={() => {
                setOnbewaard(false);
                bewaker.toch();
              }}
            />
          )}
          {doel.soort === "werkgebied" ? (
            <WerkgebiedInhoud id={doel.werkgebied_id} naarWerkgebied={naarWerkgebied} />
          ) : doel.begrip_id ? (
            <EenBegrip werkgebiedId={doel.werkgebied_id} begripId={doel.begrip_id} onSluit={onSluit}
              onOnbewaard={setOnbewaard}
              onNaarBegrip={(b) => router.push(`/werkgebieden/${encodeURIComponent(doel.werkgebied_id)}?tab=begrippen&begrip=${encodeURIComponent(b)}`)} />
          ) : doel.soort === "begrippen" ? (
            <BegripVoorstellen
              id={doel.werkgebied_id}
              runId={doel.run_id}
              inklapbaar={false}
              onMeedenken={onMeedenken ? (aantal) => onMeedenken(doel.werkgebied_id, aantal) : undefined}
              onBegrip={(b) => router.push(`${naarWerkgebied}&begrip=${encodeURIComponent(b)}`)}
              // Er staat hier geen begrippenlijst naast die ververst moet worden.
              onGewijzigd={() => {}}
            />
          ) : (
            // Opnemen wijzigt het werkgebied; hier staat geen selectie naast die ververst moet worden.
            <BronKandidaten id={doel.werkgebied_id} onGewijzigd={() => {}} />
          )}
        </div>
      </div>
    </Dialog>
  );
}

/** Het werkgebied zelf: wat er met Lex is samengesteld, zoals het nu bij de api staat – het dossier
 *  (startactiviteit a, analysevraag, praktijkvoorbeeld, afbakening), de deelvragen met hun dekking en
 *  de bronnen. */
function WerkgebiedInhoud({ id, naarWerkgebied }: { id: string; naarWerkgebied: string }) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [dekking, setDekking] = useState<DeelvragenDekking | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [poging, setPoging] = useState(0);
  useEffect(() => {
    let levend = true;
    haalWerkgebied(id).then((w) => { if (levend) setWg(w); }).catch((e) => { if (levend) setFout(foutTekst(e)); });
    // De dekking is een hint: faalt ze, dan staan de deelvragen er zonder stand.
    haalDeelvragenDekking(id).then((d) => { if (levend && isDeelvragenDekking(d)) setDekking(d); }).catch(() => {});
    return () => { levend = false; };
  }, [id, poging]);
  if (fout) {
    return (
      <Melding type="fout" titel="Het werkgebied kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => { setFout(null); setPoging((p) => p + 1); }}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!wg) return <SkeletonCard regels={4} />;
  const analyse = wg.bronnen.filter((b) => b.rol === "analyseren");
  const deelvragen = splits(wg.deelvragen).actief;
  return (
    <div data-werkgebied-inhoud className="space-y-5 text-sm text-ink">
      <p className="text-xs text-muted">{STATUS_LABEL[wg.status]} · revisie {wg.revisie}</p>
      {DOSSIER_VELDEN.map(({ veld, label }) => (
        <section key={veld} data-dossier-veld={veld}>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{label}</h3>
          {(wg[veld] ?? "").trim()
            ? <p className="whitespace-pre-line">{wg[veld]}</p>
            : <p className="text-muted">{`Nog geen ${label.toLowerCase()}.`}</p>}
        </section>
      ))}
      <section data-deelvragen>
        <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
          Deelvragen ({deelvragen.length}){dekkingZin(dekking) && ` · ${dekkingZin(dekking)}`}
        </h3>
        {deelvragen.length ? (
          <ol className="space-y-1">
            {deelvragen.map((d, i) => {
              const stand = dekking?.deelvragen.find((x) => x.id === d.id)?.stand;
              return (
                <li key={d.id} className="flex items-start gap-2 rounded-lg border border-line px-3 py-1.5">
                  <span className="tabular-nums text-muted">{i + 1}.</span>
                  <span className="min-w-0 flex-1">{d.vraag}</span>
                  {stand && (
                    <span title={STAND_UITLEG[stand]}
                      className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${STAND_KLASSE[stand]}`}>
                      {STAND_LABEL[stand]}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="text-muted">Geen deelvragen. Je kunt ze toevoegen op de tab Bronnen, of Lex laten voorstellen.</p>
        )}
      </section>
      <section>
        <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Bronnen ({analyse.length})</h3>
        {analyse.length ? (
          <ul className="space-y-1">
            {analyse.map((b) => <li key={b.id} className="rounded-lg border border-line px-3 py-1.5">{b.label || b.bron_iri}</li>)}
          </ul>
        ) : (
          <p className="text-muted">Nog geen bronnen. Voeg ze toe op de tab Bronnen, of laat Lex bepalingen zoeken.</p>
        )}
      </section>
      <Link href={naarWerkgebied}
        className="focus-ring inline-flex w-full items-center justify-center rounded-button bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 sm:w-auto">
        Open het werkgebied
      </Link>
    </div>
  );
}

/** Eén begrip in het paneel: de kaart zoals op de tab Begrippen. De lijst van het werkgebied levert de
 *  primaire duidingen en de andere begrippen (om mee te vergelijken); faalt die, dan werkt de kaart
 *  zonder. */
function EenBegrip({ werkgebiedId, begripId, onSluit, onOnbewaard, onNaarBegrip }: {
  werkgebiedId: string;
  begripId: string;
  onSluit: () => void;
  onOnbewaard: (onbewaard: boolean) => void;
  onNaarBegrip: (begripId: string) => void;
}) {
  const [lijst, setLijst] = useState<BegrippenLijst | null>(null);
  useEffect(() => {
    let levend = true;
    lijstBegrippen(werkgebiedId).then((l) => { if (levend) setLijst(l); }).catch(() => {});
    return () => { levend = false; };
  }, [werkgebiedId]);
  return (
    <BegripWerk
      id={werkgebiedId}
      begripId={begripId}
      primair={lijst?.primair ?? {}}
      andere={(lijst?.begrippen ?? []).filter((b) => b.id !== begripId)}
      onGewijzigd={() => {}}
      onOnbewaard={onOnbewaard}
      // Verwijderd: er valt hier niets meer te tonen.
      onWeg={async () => onSluit()}
      onNaarBegrip={onNaarBegrip}
    />
  );
}
