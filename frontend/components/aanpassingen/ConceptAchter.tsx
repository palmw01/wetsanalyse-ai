"use client";

import { useState } from "react";

import { Bestandenlijst } from "@/components/ui/Bestandenlijst";
import { Button, LinkButton } from "@/components/ui/Button";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart } from "@/components/ui/Pagina";
import { Tekstverschil } from "@/components/ui/Tekstverschil";
import { datumTijd } from "@/lib/datum";
import {
  bestandsvolgorde, conceptPad, wijzigingZin, wijzigingen, type Bestanden, type ImageOnderdeel, type WerkplaatsOnderdeel,
  type WerkplaatsVersie,
} from "@/lib/werkplaats";

type Kant = "intussen" | "mijn";

/** Een concept dat achterloopt (ADR-016 §B7, stap B2-4): er draait intussen een andere versie dan waar het op
 *  voortbouwt. De pagina toont de twee verschillen naast elkaar te kiezen: wat er intussen veranderde (de basis tegen
 *  wat er draait) en wat de gebruiker veranderde (de basis tegen zijn laatste versie).
 *
 *  **Er wordt niets automatisch samengevoegd.** De gebruiker verwerkt het zelf in zijn concept, of begint opnieuw vanaf
 *  wat er draait. Bij allebei staat vooraf wat er met zijn eigen wijzigingen gebeurt, en er verandert niets tot hij
 *  opslaat. Kent de pagina de basis niet meer, dan is er één vergelijking: wat er draait tegen het concept. */
export function LooptAchter({ o, laatste, basis, draait, bestand, onKiesBestand, onOpnieuw, zij }: {
  o: WerkplaatsOnderdeel;
  laatste: WerkplaatsVersie;
  /** De versie waarop het concept voortbouwt, met haar bestanden; `null` als ze er niet (meer) bij staat. */
  basis: WerkplaatsVersie | null;
  draait: ImageOnderdeel;
  bestand: string;
  onKiesBestand: (pad: string) => void;
  /** Alleen voor de eigenaar: de bestanden die draaien klaarzetten als wijziging. */
  onOpnieuw?: () => void;
  zij: React.ReactNode;
}) {
  const [kant, setKant] = useState<Kant>("intussen");
  const mijn: Bestanden = laatste.bestanden ?? {};
  const van: Bestanden = basis?.bestanden ?? draait.bestanden;
  const naar: Bestanden = !basis ? mijn : kant === "intussen" ? draait.bestanden : mijn;
  const w = wijzigingen(van, naar);
  const paden = bestandsvolgorde([...Object.keys(naar), ...w.verwijderd]);
  const anders = [...w.gewijzigd, ...w.toegevoegd, ...w.verwijderd];
  const gekozen = paden.includes(bestand) ? bestand : anders[0] || paden[0] || "";
  const stand = (p: string) => (w.gewijzigd.includes(p) ? "gewijzigd" : w.toegevoegd.includes(p) ? "nieuw" : w.verwijderd.includes(p) ? "verwijderd" : "");
  const wat = !basis ? "Wat er draait tegen je concept" : kant === "intussen" ? "Wat er intussen veranderde" : "Wat jij veranderde";
  const tussen = !basis ? `wat er draait en versie ${laatste.nummer}`
    : kant === "intussen" ? `versie ${basis.nummer} en wat er draait` : `versie ${basis.nummer} en versie ${laatste.nummer}`;

  return (
    <div data-loopt-achter data-kant={basis ? kant : "draait"}>
      <div className="mb-4" data-melding="achter-uitleg">
        <Melding type="uitleg" titel="Dit concept bouwt voort op een oudere versie">
          {basis ? `Je concept bouwt voort op versie ${basis.nummer}. ` : ""}
          Intussen draait er een andere versie{draait.gemeld_op ? ` (gemeld ${datumTijd(draait.gemeld_op)})` : ""}. Hieronder staat
          {basis ? " wat er intussen veranderde en wat jij veranderde" : " het verschil tussen wat er draait en je concept"}.
          {" "}Er wordt niets automatisch samengevoegd.
        </Melding>
      </div>
      {basis && (
        <div role="group" aria-label="Welk verschil" className="mb-4 flex flex-col gap-2 sm:flex-row">
          <Button variant={kant === "intussen" ? "primary" : "secondary"} size="sm" aria-pressed={kant === "intussen"}
            onClick={() => setKant("intussen")} data-kant-keuze="intussen">Wat er intussen veranderde</Button>
          <Button variant={kant === "mijn" ? "primary" : "secondary"} size="sm" aria-pressed={kant === "mijn"}
            onClick={() => setKant("mijn")} data-kant-keuze="mijn">Wat jij veranderde</Button>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <Kaart titel={wat} telling={w.aantal} toelichting={w.aantal ? wijzigingZin(w) : "Geen verschil."} data-blok="bestanden">
            <Bestandenlijst paden={paden} gekozen={gekozen} onKies={onKiesBestand} label={`${wat}: bestanden`} stand={stand}
              bij={(p) => stand(p) && <StatusLabel toon={stand(p) === "verwijderd" ? "neutraal" : "lint"}>{stand(p)}</StatusLabel>} />
          </Kaart>
          {zij}
        </div>
        <Kaart data-blok="inhoud" titel={<span className="font-mono text-sm [overflow-wrap:anywhere]">{gekozen || "Geen bestanden"}</span>}>
          {gekozen ? <Tekstverschil oud={van[gekozen] ?? ""} nieuw={naar[gekozen] ?? ""} label={`Verschil in ${gekozen} tussen ${tussen}`} />
            : <p className="text-sm text-muted">Geen bestanden.</p>}
        </Kaart>
      </div>
      <div className="mt-4 rounded-kaart border border-line bg-paper p-3 shadow-zacht" data-achter-keuze>
        <p className="text-sm font-medium text-ink">Hoe wil je verder?</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
          <li><span className="font-medium">Verder met mijn concept.</span> Je verwerkt zelf wat er intussen veranderde. Vink bij
            het opslaan aan dat je dat hebt gedaan; daarna loopt je concept niet meer achter. Je eigen wijzigingen blijven staan.</li>
          {onOpnieuw && (
            <li><span className="font-medium">Begin opnieuw vanaf wat er draait.</span> De bestanden die nu draaien staan dan klaar
              als wijziging. Wat jij veranderde zit daar niet in; het blijft bewaard in versie {laatste.nummer} en eerder, en is
              daar terug te zetten.</li>
          )}
        </ul>
        <p className="mt-2 text-xs text-muted">In beide gevallen verandert er niets tot je opslaat.</p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <LinkButton href={conceptPad(o.id)} variant="secondary" size="sm" className="w-full sm:w-auto">Verder met mijn concept</LinkButton>
          {onOpnieuw && (
            <Button variant="secondary" size="sm" className="w-full sm:w-auto" onClick={onOpnieuw} data-actie="opnieuw-vanaf-draait">
              Begin opnieuw vanaf wat er draait</Button>
          )}
        </div>
      </div>
    </div>
  );
}
