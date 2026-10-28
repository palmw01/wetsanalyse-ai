"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Archief, Mapje, Opstellen, Prullenbak } from "@/components/ui/Icoon";
import { MENU_RIJ } from "@/components/ui/Menu";
import { lijstWerkgebieden } from "@/lib/api";
import type { WerkgebiedSamenvatting } from "@/lib/types";

/** Wat je met één gesprek kunt doen. Bewust drie verschillende handelingen (spoor G1, op verzoek van
 *  de gebruiker): **archiveren** haalt het uit de navigatie en is terug te halen, **verplaatsen**
 *  hangt het onder een ander werkgebied of maakt het los, en **verwijderen** is definitief. Dat
 *  laatste vraagt een expliciete bevestiging die eerst archiveren aanbiedt – het gesprek is een
 *  verslag, en annotaties, begrippen en werkgebieden blijven altijd bestaan.
 *
 *  Eén inhoud, twee schillen: onder een rij in de sidebar (inline, want de lijst scrolt) en in de
 *  kop van het gesprek (een popover). */
export interface GesprekActiesProps {
  werkgebiedId?: string;
  gearchiveerd?: boolean;
  onHernoem?: () => void;
  onArchiveer: (gearchiveerd: boolean) => void;
  onVerplaats: (werkgebiedId: string) => void;
  onVerwijder: () => void;
  /** Na elke gekozen handeling (de schil klapt dicht). */
  onKlaar?: () => void;
}

type Stap = "menu" | "verplaats" | "verwijder";

const RIJ = MENU_RIJ;

export function GesprekActies({
  werkgebiedId = "", gearchiveerd = false, onHernoem, onArchiveer, onVerplaats, onVerwijder, onKlaar,
}: GesprekActiesProps) {
  const [stap, setStap] = useState<Stap>("menu");
  const klaar = (doe: () => void) => () => {
    doe();
    onKlaar?.();
  };

  if (stap === "verplaats") {
    return <Verplaats huidig={werkgebiedId} onKies={(id) => { onVerplaats(id); onKlaar?.(); }} onTerug={() => setStap("menu")} />;
  }

  if (stap === "verwijder") {
    return (
      <div className="flex flex-col gap-2 p-2.5" data-gesprek-verwijderen>
        <p className="text-sm font-medium text-ink">Gesprek definitief verwijderen?</p>
        <p className="text-xs leading-relaxed text-muted">
          Het gesprek en het geheugen van Lex erover gaan weg; dat is niet terug te halen. Annotaties,
          begrippen en werkgebieden blijven bestaan.
          {!gearchiveerd && " Wil je het alleen uit beeld hebben, archiveer het dan."}
        </p>
        {/* Altijd onder elkaar (spoor I4): de sidebar is smal, en naast elkaar viel *Definitief verwijderen*
            er vanaf `sm:` buiten. */}
        <div className="flex flex-col gap-1.5">
          {!gearchiveerd && (
            <Button size="sm" variant="secondary" className="w-full" onClick={klaar(() => onArchiveer(true))}>
              Archiveren
            </Button>
          )}
          <Button size="sm" variant="danger" className="w-full" onClick={klaar(onVerwijder)}>
            Definitief verwijderen
          </Button>
          <Button size="sm" variant="ghost" className="w-full" onClick={() => setStap("menu")}>
            Annuleren
          </Button>
        </div>
      </div>
    );
  }

  return (
    <ul className="flex flex-col p-1" role="menu">
      {onHernoem && (
        <li role="none">
          <button type="button" role="menuitem" className={RIJ} onClick={klaar(onHernoem)}>
            <Opstellen className="text-muted" /> Hernoemen
          </button>
        </li>
      )}
      <li role="none">
        <button type="button" role="menuitem" className={RIJ} onClick={() => setStap("verplaats")}>
          <Mapje className="text-muted" /> {werkgebiedId ? "Naar ander werkgebied…" : "Toevoegen aan werkgebied…"}
        </button>
      </li>
      {werkgebiedId && (
        <li role="none">
          <button type="button" role="menuitem" className={RIJ} onClick={klaar(() => onVerplaats(""))}>
            <Mapje className="text-muted" /> Naar recente gesprekken
          </button>
        </li>
      )}
      <li role="none">
        <button type="button" role="menuitem" className={RIJ} onClick={klaar(() => onArchiveer(!gearchiveerd))}>
          <Archief className="text-muted" /> {gearchiveerd ? "Herstellen uit archief" : "Archiveren"}
        </button>
      </li>
      <li role="none">
        <button type="button" role="menuitem" className={`${RIJ} text-fout`} onClick={() => setStap("verwijder")}>
          <Prullenbak /> Verwijderen…
        </button>
      </li>
    </ul>
  );
}

/** De werkgebieden om naartoe te verplaatsen; pas geladen als je erom vraagt. */
function Verplaats({ huidig, onKies, onTerug }: { huidig: string; onKies: (id: string) => void; onTerug: () => void }) {
  const [lijst, setLijst] = useState<WerkgebiedSamenvatting[] | null>(null);
  const [fout, setFout] = useState(false);
  useEffect(() => {
    let actief = true;
    lijstWerkgebieden()
      .then((l) => actief && setLijst(l.filter((w) => w.id !== huidig)))
      .catch(() => actief && setFout(true));
    return () => {
      actief = false;
    };
  }, [huidig]);

  return (
    <div className="flex flex-col p-1" data-gesprek-verplaatsen>
      <p className="px-2.5 pb-1 pt-1.5 text-xs font-medium text-muted">Naar welk werkgebied?</p>
      {fout && <p className="px-2.5 py-1.5 text-xs text-fout">De werkgebieden zijn niet geladen.</p>}
      {!fout && lijst === null && <p className="px-2.5 py-1.5 text-xs text-muted">Laden…</p>}
      {lijst?.length === 0 && <p className="px-2.5 py-1.5 text-xs text-muted">Geen ander werkgebied.</p>}
      <ul className="max-h-60 overflow-y-auto">
        {lijst?.map((w) => (
          <li key={w.id}>
            <button type="button" className={RIJ} onClick={() => onKies(w.id)}>
              <Mapje className="text-muted" /> <span className="truncate">{w.naam}</span>
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className={`${RIJ} text-muted`} onClick={onTerug}>
        Terug
      </button>
    </div>
  );
}
