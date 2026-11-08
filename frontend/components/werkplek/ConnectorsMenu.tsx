"use client";

import { knopKlasse } from "@/components/ui/Button";
import { ChevronOmlaag, Vinkje } from "@/components/ui/Icoon";
import { MenuKeuze, MenuKnop, MenuLijst } from "@/components/ui/MeerMenu";
import { MENU_PANEEL } from "@/components/ui/Menu";
import { Popover } from "@/components/ui/Popover";
import { MENU_RIJ } from "@/components/ui/Menu";
import { herkomstVan, menuNaam, menuRegel, actieveConnectors, schakelbaar, type ConnectorStand } from "@/lib/connectorsMenu";

const HERKOMST = {
  gesprek: "Eigen keuze voor dit gesprek.",
  werkgebied: "De standaard van dit werkgebied.",
  standaard: "Alles wat de beheerder aanzette.",
} as const;

/** *Bronnen en tools* boven het invoerveld (ADR-013): welke bronnen buiten de wettekst Lex in dit gesprek mag
 *  raadplegen. Zonder connector die de beheerder aanzette, is er geen menu: dan is er alleen wetgeving. */
export function ConnectorsMenu({ stand, onWissel, onAlsStandaard, onTerugNaarStandaard, onOpen }: {
  stand: ConnectorStand;
  onWissel: (naam: string) => void;
  /** Bij het openen: de werkplek haalt de stand opnieuw op als er een beschikbaarheid onbekend is. */
  onOpen?: () => void;
  /** Alleen in een werkgebied: deze stand wordt de standaard voor de gesprekken daarin. */
  onAlsStandaard?: () => void;
  onTerugNaarStandaard?: () => void;
}) {
  if (stand.beschikbaar.length === 0) return null;
  const aan = actieveConnectors(stand);
  const herkomst = herkomstVan(stand);
  return (
    <Popover ariaLabel="Bronnen en tools" positie="left-0 bottom-full mb-1" className={`w-72 ${MENU_PANEEL}`}
      trigger={(open, toggle) => (
        <button type="button" onClick={() => { if (!open) onOpen?.(); toggle(); }} aria-expanded={open} aria-haspopup="menu" aria-label={menuNaam(stand)}
          data-connectors-menu className={`${knopKlasse("ghost", "sm")} max-w-full gap-1.5 text-xs`}>
          {menuRegel(stand).map((d, i) => (
            <span key={d.label} className={`inline-flex items-center gap-1 ${d.aan ? "text-ink" : "text-muted"}`}
              data-bron={d.label} data-aan={d.aan ? "" : undefined}>
              {i > 0 && <span aria-hidden className="text-muted">·</span>}
              {d.label}
              {d.aan ? <Vinkje className="text-lint" />
                : <span aria-hidden className="text-muted">{d.onbekend ? "onbekend" : "uit"}</span>}
            </span>
          ))}
          <ChevronOmlaag className="text-muted" />
        </button>
      )}>
      {(sluit) => (
        <div>
          <p className="px-2 pb-1 pt-1.5 text-xs text-muted">
            Wetgeving staat altijd aan. Een bron is geen wettekst: Lex citeert eruit met de eigen vindplaats.
          </p>
          <MenuLijst>
            {stand.beschikbaar.map((c) => schakelbaar(c) ? (
              <MenuKeuze key={c.naam} gekozen={aan.includes(c.naam)} onClick={() => onWissel(c.naam)}>{c.label}</MenuKeuze>
            ) : (
              // Een schakelaar die niets doet, is erger dan geen (review ADR-013, punt 2): graph-qa was niet te lezen.
              <li key={c.naam} role="none" data-connector-onbekend={c.naam}>
                <span role="menuitem" aria-disabled="true" className={`${MENU_RIJ} cursor-default text-muted hover:bg-transparent`}>
                  {c.label} · beschikbaarheid nu onbekend
                </span>
              </li>
            ))}
            {onAlsStandaard && (
              <MenuKnop onClick={() => { onAlsStandaard(); sluit(); }}>Maak dit de standaard van het werkgebied</MenuKnop>
            )}
            {herkomst === "gesprek" && onTerugNaarStandaard && (
              <MenuKnop onClick={() => { onTerugNaarStandaard(); sluit(); }}>Terug naar de standaard</MenuKnop>
            )}
          </MenuLijst>
          <p className="px-2 pb-1.5 pt-1 text-xs text-muted" data-connectors-herkomst={herkomst}>{HERKOMST[herkomst]}</p>
        </div>
      )}
    </Popover>
  );
}
