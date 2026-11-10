"use client";

// Het overzicht van een onderwerp, naast het gesprek: per regeling de delen met al hun bepalingen, wat
// het onderwerp verder noemt, de wettelijke definitie en het redactionele trefwoord. In het gesprek staat
// alleen de samenvatting met een kaartje: een lange lijst hoort naast de tekst, net als de bronselectie.
//
// De inhoud komt uit de graaf (graph-qa `agent/overzicht.py`), niet uit de tekst van het model, en reist
// mee in het bericht: elk nummer staat er zoals de graaf het heeft, nooit als bereik, en dezelfde vraag
// geeft hetzelfde paneel. De rekenkern staat in `lib/overzicht.ts`.

import { useState } from "react";

import { Vindplaats } from "@/components/antwoord/Vindplaats";
import { useOpenBron } from "@/components/werkplek/ContextPaneel";
import { Button } from "@/components/ui/Button";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { bepalingNaam, deelKop, telling, zoekverantwoording } from "@/lib/overzicht";
import type { Overzicht, OverzichtBepaling, OverzichtDeel, OverzichtRegeling } from "@/lib/types";
import { bronHref } from "@/lib/url";

/** De regeling zelf, als link naar wetten.overheid.nl: een hele regeling opent niet als tab (een bepaling wel). */
function RegelingLink({ label, iri, jci }: { label: string; iri: string; jci?: string }) {
  // Bij voorkeur de jci (die kent wetten.overheid.nl), anders de graaf-IRI; `bronHref` weigert al het
  // andere, en dan is het platte tekst.
  const href = bronHref(jci || iri);
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-lint underline underline-offset-2 [overflow-wrap:anywhere]">{label}</a>
  ) : <span>{label}</span>;
}

/** De bepalingen van een deel als rij namen. Een klik opent de bepaling als tab in hetzelfde paneel (het bronvenster,
 *  PR 4): met 35 artikelen in een hoofdstuk zou een rij per artikel het paneel vullen, en een uitklap eronder is een
 *  tweede weergave van dezelfde tekst. */
function Bepalingen({ bepalingen, naam, regeling }: {
  bepalingen: OverzichtBepaling[]; naam?: (b: OverzichtBepaling) => string; regeling?: string;
}) {
  const opener = useOpenBron();
  return (
    <div className="px-4 pb-3">
      <ul className="flex flex-wrap gap-x-3 gap-y-1">
        {bepalingen.map((b) => {
          const tekst = naam ? naam(b) : bepalingNaam(b);
          return (
            <li key={b.iri}>
              {opener ? (
                <button type="button" data-overzicht-bepaling={b.iri}
                  onClick={() => opener({ soort: "bron", bron_iri: b.iri, titel: regeling ? `${tekst} – ${regeling}` : tekst })}
                  className="focus-ring min-h-[24px] rounded text-left text-sm text-lint underline underline-offset-2 [overflow-wrap:anywhere] coarse:min-h-[44px]">
                  {tekst}
                </button>
              ) : <Vindplaats vindplaats={{ iri: b.iri, label: tekst, jci: "", regeling: regeling ?? "" }} kort />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function DeelRij({ deel, regeling }: { deel: OverzichtDeel; regeling: string }) {
  const [open, setOpen] = useState(false);
  const kop = deelKop(deel);
  return (
    <GroepRij titel={kop} data-overzicht-deel={deel.iri}
      sub={`${deel.bepalingen.length} bepaling${deel.bepalingen.length === 1 ? "" : "en"}${deel.subdelen.length ? ` · waarin ${deel.subdelen.map((s) => s.label).join(", ")}` : ""}`}
      uitklap={{ open, onWissel: () => setOpen((o) => !o), label: kop }}
      onder={open ? <Bepalingen bepalingen={deel.bepalingen} regeling={regeling} /> : undefined} />
  );
}

function OokGenoemdRij({ regeling }: { regeling: OverzichtRegeling }) {
  // Heeft de regeling geen deel over het onderwerp, dan is dit alles wat je van haar ziet: open.
  const [open, setOpen] = useState(regeling.delen.length === 0);
  const titel = `Noemt het onderwerp ook (${regeling.ook_genoemd.length})`;
  const plaats = (b: OverzichtRegeling["ook_genoemd"][number]) => `${bepalingNaam(b)}${b.in_deel ? ` · in ${b.in_deel.label}` : ""}`;
  return (
    <GroepRij titel={titel} uitklap={{ open, onWissel: () => setOpen((o) => !o), label: titel }}
      onder={open ? <Bepalingen bepalingen={regeling.ook_genoemd} regeling={regeling.citeertitel} naam={(b) => plaats(b as OverzichtRegeling["ook_genoemd"][number])} /> : undefined} />
  );
}

export function OverzichtPaneel({ overzicht, onMaakWerkgebied }: { overzicht: Overzicht; onMaakWerkgebied?: (o: Overzicht) => void }) {
  const t = telling(overzicht);
  return (
    <div data-testid="overzicht" className="space-y-5 text-sm text-ink">
      <p className="text-xs text-muted">
        {t.regelingen} regeling{t.regelingen === 1 ? "" : "en"} · {t.delen} {t.delen === 1 ? "deel" : "delen"} met
        {" "}{t.bepalingen} bepaling{t.bepalingen === 1 ? "" : "en"}
        {t.ookGenoemd > 0 && <> · {t.ookGenoemd} die het onderwerp verder noemen</>}
      </p>

      {overzicht.definities.length > 0 && (
        <section>
          <h3 className="mb-1 font-display text-sm font-semibold text-lint">Wettelijke definitie</h3>
          <ul className="space-y-1">
            {overzicht.definities.map((d) => (
              <li key={d.iri}>„{d.begrip}” – {d.citeertitel}, <Vindplaats vindplaats={{ iri: d.iri, label: d.vindplaats || d.label || "vindplaats", jci: d.jci ?? "", regeling: "" }} kort /></li>
            ))}
          </ul>
        </section>
      )}

      {overzicht.regelingen.length === 0 && <p className="text-muted">De graaf bevat geen deel of bepaling over dit onderwerp.</p>}

      {overzicht.regelingen.map((r) => (
        <Groep key={r.bwb_id} label={r.citeertitel} kop={<RegelingLink label={r.citeertitel} iri={`urn:bwb:${r.bwb_id}`} />}
          telling={r.delen.length ? `${r.delen.length} ${r.delen.length === 1 ? "deel" : "delen"}` : undefined}>
          {r.delen.map((d) => <DeelRij regeling={r.citeertitel} key={d.iri} deel={d} />)}
          {r.ook_genoemd.length > 0 && <OokGenoemdRij key="ook" regeling={r} />}
        </Groep>
      ))}

      <footer className="space-y-0.5 text-xs text-muted">
        {overzicht.trefwoorden.map((tw) => (
          <p key={tw.trefwoord}>Trefwoord „{tw.trefwoord}” (redactioneel) bij: {tw.regelingen.map((x) => x.citeertitel).join(", ")}</p>
        ))}
        <p>{zoekverantwoording(overzicht)}</p>
        {!overzicht.volledig && <p>Dit overzicht raakte zijn bovengrens; er kan meer over het onderwerp zijn.</p>}
      </footer>

      {onMaakWerkgebied && overzicht.regelingen.length > 0 && (
        <Button variant="secondary" size="sm" className="w-full sm:w-auto" onClick={() => onMaakWerkgebied(overzicht)}>Maak hier een werkgebied van</Button>
      )}
    </div>
  );
}
