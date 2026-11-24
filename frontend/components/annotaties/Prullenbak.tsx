"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Dialog } from "@/components/ui/Dialog";
import { LaadRegel } from "@/components/ui/LaadStand";
import { KlasseLabel } from "@/components/ui/Lijst";
import { Melding, MeldingActie } from "@/components/ui/Melding";
import { foutTekst } from "@/lib/api";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import {
  impactZinnen, inhoudZin, verwijderdOp, type PrullenbakInhoud, type PrullenbakItem, type VerwijderImpact,
} from "@/lib/annotatiePrullenbak";
import { aantal } from "@/lib/aantal";
import { datumKort } from "@/lib/datum";
import type { NodeElement } from "@/lib/annotatieNode";
import type { Lifecycle } from "@/lib/types";

/** De bevestiging vóór het verwijderen van een annotatie, op elke plek waar dat kan (het menu ⋯ van het paneel, de kaart
 *  in het overzicht): wat er naar de prullenbak gaat, welke begrippen en afleidingsregels ernaar verwijzen, en hoe lang je
 *  het kunt terugzetten. Kan de telling niet laden, dan zegt het venster dat, en kun je toch verwijderen: het is niet
 *  definitief. */
export function VerwijderBevestiging({ bepaling, haalImpact, onVerwijder, onSluit }: {
  /** De bepaling, als regel boven de titel ("Artikel 9, lid 1"). */
  bepaling?: string;
  haalImpact?: () => Promise<VerwijderImpact>;
  onVerwijder: () => Promise<void>;
  onSluit: () => void;
}) {
  const [impact, setImpact] = useState<VerwijderImpact | null>(null);
  const [laadFout, setLaadFout] = useState("");
  const [fout, setFout] = useState("");
  const [bezig, setBezig] = useState(false);

  // Eén keer tellen bij het openen: de aanroeper geeft vaak een nieuwe functie per render.
  const haal = useRef(haalImpact);
  useEffect(() => {
    if (!haal.current) return;
    let actueel = true;
    haal.current().then((i) => { if (actueel) setImpact(i); },
      (e) => { if (actueel) setLaadFout(foutTekst(e, "De telling is niet geladen.")); });
    return () => { actueel = false; };
  }, []);

  async function verwijder() {
    setFout("");
    setBezig(true);
    try {
      await onVerwijder();
      onSluit();
    } catch (e) {
      setFout(foutTekst(e, "De annotatie is niet verwijderd."));
      setBezig(false);
    }
  }

  const zinnen = impact && impactZinnen(impact);
  return (
    <Dialog label="Annotatie verwijderen" variant="compact" onSluit={onSluit}
      kop={{ titel: "Annotatie verwijderen?", soort: bepaling, sluitLabel: "Niet verwijderen" }}>
      <div className="flex min-h-0 flex-col gap-3 overflow-y-auto p-6 text-sm" data-verwijder-bevestiging>
        {zinnen ? <>
          <p className="text-ink" data-verwijder-verlies>{zinnen.verlies}</p>
          {zinnen.verwijzers && <Melding type="waarschuwing" compact data-verwijder-verwijzers>{zinnen.verwijzers}</Melding>}
          <p className="text-muted">{zinnen.terug}</p>
        </> : haalImpact && !laadFout ? <LaadRegel>Tellen wat er verloren gaat…</LaadRegel> : (
          <p className="text-muted">
            {laadFout ? `Wat er verloren gaat, is niet te tellen (${laadFout}). ` : ""}
            De annotatie gaat met al haar markeringen en beoordelingen naar de prullenbak; je kunt haar terugzetten zolang
            er geen nieuwe annotatie op deze bepaling staat.
          </p>
        )}
        {fout && <Melding type="fout" compact>{fout}</Melding>}
        <ButtonRow>
          <Button variant="danger" onClick={() => void verwijder()} disabled={bezig} data-verwijder-bevestig>
            {bezig ? "Bezig…" : "Verwijderen"}
          </Button>
          <Button variant="ghost" onClick={onSluit} disabled={bezig}>Annuleren</Button>
        </ButtonRow>
      </div>
    </Dialog>
  );
}

/** Wat er van deze bepaling in de prullenbak ligt, in het annotatiepaneel. Zonder nieuwe annotatie: "verwijderd op …"
 *  met *Terugzetten*. Met een nieuwe annotatie: wat er nu ligt, en *Vergelijken*. Zonder item (definitief, of van vóór
 *  de prullenbak) alleen dat de annotatie verwijderd is. */
export function PrullenbakBlok({ prullenbak, verwijderd, elementenNu, haalItem, onTerugzetten }: {
  prullenbak?: PrullenbakItem | null;
  verwijderd?: { op: string; door?: string } | null;
  elementenNu: NodeElement[];
  haalItem?: (id: string) => Promise<PrullenbakInhoud>;
  onTerugzetten?: (id: string) => Promise<void>;
}) {
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState("");
  const [vergelijk, setVergelijk] = useState(false);
  const p = prullenbak;

  async function zetTerug(id: string) {
    if (!onTerugzetten || bezig) return;
    setFout("");
    setBezig(true);
    try {
      await onTerugzetten(id);
    } catch (e) {
      setFout(foutTekst(e, "De annotatie is niet teruggezet."));
    } finally {
      setBezig(false);
    }
  }

  if (p && p.terugzetbaar) {
    return (
      <>
        <Melding type="uitleg" compact data-prullenbak="terugzetbaar">
          Deze annotatie is {verwijderdOp(p.op, p.door)}. Ze ligt in de prullenbak tot {datumKort(p.bewaard_tot)}:
          {" "}{inhoudZin(p)}.{" "}
          {onTerugzetten && (bezig ? <span className="font-medium">Bezig met terugzetten…</span>
            : <MeldingActie onClick={() => void zetTerug(p.id)} data-terugzetten>Terugzetten</MeldingActie>)}
          {" "}Of vraag Lex om de bepaling opnieuw te annoteren, of markeer zelf.
        </Melding>
        {fout && <Melding type="fout" compact>{fout}</Melding>}
      </>
    );
  }
  if (p) {
    return (
      <>
        <Melding type="uitleg" compact data-prullenbak="bezet">
          Er ligt een eerder verwijderde annotatie van deze bepaling in de prullenbak ({verwijderdOp(p.op, p.door)};
          {" "}{inhoudZin(p)}). Nu staat hier een nieuwe annotatie met {aantal(elementenNu.length, "markering", "markeringen")};
          terugzetten kan pas als die is verwijderd, want één bepaling heeft één annotatie.{" "}
          {haalItem && <MeldingActie onClick={() => setVergelijk(true)} data-vergelijken>Vergelijken</MeldingActie>}
        </Melding>
        {vergelijk && haalItem && (
          <Vergelijking id={p.id} haalItem={haalItem} nu={elementenNu} onSluit={() => setVergelijk(false)} />
        )}
      </>
    );
  }
  if (verwijderd) {
    return (
      <Melding type="uitleg" compact data-prullenbak="definitief">
        Deze annotatie is {verwijderdOp(verwijderd.op, verwijderd.door)} en staat niet meer in de prullenbak; terugzetten
        kan niet. Vraag Lex om de bepaling opnieuw te annoteren, of markeer zelf.
      </Melding>
    );
  }
  return null;
}

type Rij = { id: string; klasse: string; tekst: string; lifecycle: string };
const sleutel = (r: Rij) => `${r.klasse}|${r.tekst}`;

/** Toen naast nu: de markeringen in de prullenbak en die van de annotatie van nu, met wat in beide staat. */
function Vergelijking({ id, haalItem, nu, onSluit }: {
  id: string; haalItem: (id: string) => Promise<PrullenbakInhoud>; nu: NodeElement[]; onSluit: () => void;
}) {
  const [toen, setToen] = useState<PrullenbakInhoud | null>(null);
  const [fout, setFout] = useState("");
  useEffect(() => {
    let actueel = true;
    haalItem(id).then((x) => { if (actueel) setToen(x); },
      (e) => { if (actueel) setFout(foutTekst(e, "De annotatie in de prullenbak is niet geladen.")); });
    return () => { actueel = false; };
  }, [haalItem, id]);
  const rijenToen = (toen?.elementen ?? []).filter((e) => !e.verouderd);
  const rijenNu = nu.filter((e) => !e.verouderd);
  const inNu = new Set(rijenNu.map(sleutel));
  const inToen = new Set(rijenToen.map(sleutel));
  const beide = rijenToen.filter((r) => inNu.has(sleutel(r))).length;
  return (
    <Dialog label="Annotaties vergelijken" variant="compact" onSluit={onSluit}
      kop={{ titel: "Toen en nu", uitleg: toen ? `Verwijderd op ${datumKort(toen.op)} door ${toen.door}` : undefined,
        sluitLabel: "Vergelijking sluiten" }}>
      <div className="flex min-h-0 flex-col gap-3 overflow-y-auto p-6 text-sm" data-vergelijking>
        {fout ? <Melding type="fout" compact>{fout}</Melding> : !toen ? <LaadRegel /> : <>
          <p className="text-muted" data-vergelijking-telling>
            {beide} in beide, {rijenToen.length - beide} alleen in de prullenbak, {rijenNu.filter((r) => !inToen.has(sleutel(r))).length} alleen nu.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Kolom titel="In de prullenbak" rijen={rijenToen} ander={inNu} />
            <Kolom titel="Nu" rijen={rijenNu} ander={inToen} />
          </div>
        </>}
      </div>
    </Dialog>
  );
}

function Kolom({ titel, rijen, ander }: { titel: string; rijen: Rij[]; ander: Set<string> }) {
  return (
    <section className="min-w-0">
      <h3 className="text-xs font-medium text-muted">{titel} ({rijen.length})</h3>
      <ul className="mt-2 divide-y divide-line">
        {rijen.map((r) => (
          <li key={r.id} className="py-2" data-in-beide={ander.has(sleutel(r)) ? "ja" : "nee"}>
            <KlasseLabel klasse={r.klasse} klein />
            <q className="mt-1 block text-ink [overflow-wrap:anywhere]">{r.tekst}</q>
            <span className="block text-xs text-muted">
              {LIFECYCLE_LABEL[r.lifecycle as Lifecycle] ?? r.lifecycle}{ander.has(sleutel(r)) ? "" : " · alleen hier"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
