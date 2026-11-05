"use client";

import { useState } from "react";

import { BewerkKnop } from "@/components/ui/Bewerkbaar";
import { Button, IcoonKnop } from "@/components/ui/Button";
import { FilterChip } from "@/components/ui/FilterChip";
import { Kruis } from "@/components/ui/Icoon";
import { Lijst, LijstRij, Sectie, StatusLabel, type StatusToon } from "@/components/ui/Lijst";
import { MeerMenu, MenuKnop, MenuVerwijder } from "@/components/ui/MeerMenu";
import { Suggestie } from "@/components/ui/Suggestie";
import { WerkgebiedKaart } from "@/components/werkgebieden/WerkgebiedKaart";
import type { WerkgebiedSamenvatting } from "@/lib/types";

/** De levende stijlgids van Lex (5 nov 2026, besluit gebruiker na het stijlblad): de echte componenten naast elkaar, in
 *  elke stand. Hier kijk je of iets klopt, en een nieuwe knop of een nieuw label toets je hieraan. De regel: **een pil is
 *  een label, een afgeronde rechthoek is een knop.** Alleen voor beheerders, in het instellingenvenster. Toont alleen
 *  echte componenten: een voorbeeld dat hier nagebouwd is, loopt achter op de app. */

const TONEN: { toon: StatusToon; voorbeelden: string[] }[] = [
  { toon: "groen", voorbeelden: ["Geaccordeerd", "Bevestigd door review"] },
  { toon: "geel", voorbeelden: ["Keuze voor jou", "Opnieuw bekijken"] },
  { toon: "rood", voorbeelden: ["Waarschijnlijk fout"] },
  { toon: "neutraal", voorbeelden: ["In voorbereiding", "Nog niet gestart"] },
  { toon: "lint", voorbeelden: ["Deelvraag"] },
];

const VOORBEELD_WG: WerkgebiedSamenvatting = {
  id: "stijl-voorbeeld", naam: "Rekeningafspraak", analysevraag: "Wanneer mag de ontvanger een betaling rechtstreeks aan een derde overmaken?",
  afbakening: "", peildatum: null, status: "in_voorbereiding", revisie: 1, aangemaakt_door: "voorbeeld",
  aangemaakt: "2026-11-04T09:00:00Z", gewijzigd: "2026-11-04T09:00:00Z", gearchiveerd: null, aantal_bronnen: 4,
};

const niets = () => {};

export function StijlPanel() {
  const [filter, setFilter] = useState("alle");
  return (
    <div className="space-y-8" data-stijlgids>
      <section className="space-y-2">
        <h2 className="font-display text-lg font-semibold text-lint">Labels en knoppen</h2>
        <p className="max-w-prose text-sm text-muted">
          Eén regel voor heel Lex: <strong className="text-ink">een pil is een label, een afgeronde rechthoek is een knop.</strong>{" "}
          Een label zegt iets en doet niets: geen hover, geen handje. Een knop doet iets en heeft altijd de vorm van{" "}
          <em>Nieuw gesprek</em>. Alles hieronder is het echte component uit de app.
        </p>
      </section>

      <Sectie titel="Labels" toelichting="StatusLabel – kleur draagt een oordeel; grijs is neutraal, lintblauw zegt waar iets over gaat.">
        <div className="flex flex-wrap gap-2" data-stijl="labels">
          {TONEN.flatMap(({ toon, voorbeelden }) => voorbeelden.map((v) => <StatusLabel key={v} toon={toon}>{v}</StatusLabel>))}
        </div>
      </Sectie>

      <Sectie titel="Knoppen" toelichting="Button – drie maten, vier varianten. md voor de hoofdactie van een scherm, sm in een kop of formulier, xs in een rij.">
        <div className="space-y-4" data-stijl="knoppen">
          {(["md", "sm", "xs"] as const).map((maat) => (
            <div key={maat} className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-faint">{maat}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Button size={maat} variant="primary">Opslaan</Button>
                <Button size={maat} variant="secondary">Nieuw gesprek</Button>
                <Button size={maat} variant="ghost">Annuleren</Button>
                <Button size={maat} variant="danger">Verwijderen</Button>
                <Button size={maat} variant="secondary" disabled>Uit</Button>
              </div>
            </div>
          ))}
        </div>
      </Sectie>

      <Sectie titel="In een rij" toelichting="BewerkKnop, IcoonKnop en het menu ⋯ (MeerMenu): dezelfde kleine rechthoek, even hoog als het label ernaast.">
        <Lijst label="Voorbeeld van een rij">
          <LijstRij voor="1." titel="Wat is een rekeningafspraak?" meta="Voorgesteld door Lex · nog geen bronnen"
            status={<span className="flex items-center gap-1.5">
              <StatusLabel>Nog niet gestart</StatusLabel>
              <BewerkKnop wat="Voorbeeld" onClick={niets} />
              <MeerMenu label="Acties: voorbeeld">
                {(sluit) => (<>
                  <MenuKnop onClick={sluit}>Bronnen koppelen</MenuKnop>
                  <MenuVerwijder onBevestig={sluit} />
                </>)}
              </MeerMenu>
            </span>} />
        </Lijst>
        <div className="mt-3 flex items-center gap-2">
          <IcoonKnop size="xs" aria-label="Sluiten (xs)"><Kruis /></IcoonKnop>
          <IcoonKnop size="sm" aria-label="Sluiten (sm)"><Kruis /></IcoonKnop>
          <span className="text-xs text-muted">IcoonKnop xs en sm</span>
        </div>
      </Sectie>

      <Sectie titel="Kiezen" toelichting="FilterChip – een keuze is iets wat je aanklikt, dus een kleine rechthoek; gekozen is lintblauw gevuld.">
        <div className="flex flex-wrap gap-2" data-stijl="filters">
          {[["alle", "Alle (6)"], ["voorbereiding", "In voorbereiding (3)"], ["actief", "Actief (2)"], ["afgerond", "Afgerond (1)"]].map(([k, l]) => (
            <FilterChip key={k} gekozen={filter === k} onKies={() => setFilter(k)}>{l}</FilterChip>
          ))}
        </div>
      </Sectie>

      <Sectie titel="Suggesties" toelichting="Suggestie – de vorm van de voorbeeldvragen in de lege werkplek; klein boven het invoerveld.">
        <div className="space-y-3" data-stijl="suggesties">
          <div className="flex flex-wrap gap-2"><Suggestie>Wat betekent het begrip &apos;belastingschuldige&apos;?</Suggestie></div>
          <div className="flex flex-wrap gap-1.5">
            <Suggestie klein>Stel deelvragen voor</Suggestie>
            <Suggestie klein>Bepaal de bronnen per deelvraag</Suggestie>
            <Suggestie klein>Annoteer wat nog niet geannoteerd is</Suggestie>
          </div>
        </div>
      </Sectie>

      <Sectie titel="In de app" toelichting="WerkgebiedKaart, het eerste voorbeeld van de gebruiker: het statuslabel naast de knoppen.">
        <div className="max-w-sm" data-stijl="werkgebiedkaart">
          <WerkgebiedKaart wg={VOORBEELD_WG} onVerwijder={async () => {}} />
        </div>
      </Sectie>

      <Sectie titel="Rond" toelichting="Alleen de verstuurknop van het invoerveld is rond: de hoofdactie van het gesprek. Een JAS-klasse die je kunt wijzigen (de reviewkaart) is een rechthoek in haar kleur met ▾; een klasse die alleen informeert is een label (KlasseLabel)." />
    </div>
  );
}
