"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { knopKlasse } from "@/components/ui/Button";
import { ChevronOmlaag, Vinkje, Waarschuwing } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { MenuKeuze, MenuKnop, MenuLijst } from "@/components/ui/MeerMenu";
import { MENU_PANEEL } from "@/components/ui/Menu";
import { Popover } from "@/components/ui/Popover";
import { MENU_RIJ } from "@/components/ui/Menu";
import { herkomstVan, menuKort, menuMelding, menuNaam, menuRegel, actieveConnectors, schakelbaar, STAND_WOORD, toonMenu, type ConnectorStand } from "@/lib/connectorsMenu";

const HERKOMST = {
  gesprek: "Je koos dit voor dit gesprek.",
  werkgebied: "Zoals ingesteld voor dit werkgebied.",
  standaard: "Standaard: alle beschikbare bronnen staan aan.",
} as const;

/** De reden achter een connector zonder schakelaar. */
const REDEN = {
  onbekend: "nu niet te controleren",
  niet_aangeboden: "hier niet beschikbaar",
} as const;

/** *Bronnen en tools* boven het invoerveld (ADR-013): welke bronnen buiten de wettekst Lex in dit gesprek mag
 *  raadplegen. Zonder connector die de beheerder aanzette, is er geen menu: dan is er alleen wetgeving. Het menu
 *  verdwijnt nooit stil: lukt het ophalen niet, of biedt de omgeving een aangezette bron niet aan, dan zegt het dat. */
export function ConnectorsMenu({ stand, onWissel, onAlsStandaard, onTerugNaarStandaard, onOpen, onOpnieuw }: {
  stand: ConnectorStand;
  onWissel: (naam: string) => void;
  /** Bij het openen: de werkplek haalt de stand opnieuw op als er een beschikbaarheid onbekend is. */
  onOpen?: () => void;
  /** Alleen in een werkgebied: deze stand wordt de standaard voor de gesprekken daarin. */
  onAlsStandaard?: () => void;
  onTerugNaarStandaard?: () => void;
  /** *Opnieuw proberen* in de melding: de stand opnieuw ophalen. */
  onOpnieuw?: () => void;
}) {
  const volRef = useRef<HTMLSpanElement>(null);
  const kort = useTePast(volRef);
  if (!toonMenu(stand)) return null;
  const aan = actieveConnectors(stand);
  const samenvatting = menuKort(stand);
  const herkomst = herkomstVan(stand);
  const melding = menuMelding(stand);
  return (
    <Popover ariaLabel="Bronnen en tools" positie="left-0 bottom-full mb-1" className={`w-72 ${MENU_PANEEL}`}
      trigger={(open, toggle) => (
        <button type="button" onClick={() => { if (!open) onOpen?.(); toggle(); }} aria-expanded={open} aria-haspopup="menu" aria-label={menuNaam(stand)}
          data-connectors-menu data-kort={kort ? "" : undefined} data-laden={stand.controleert ? "controleert" : stand.laden === "mislukt" ? "mislukt" : undefined}
          aria-busy={stand.controleert || undefined}
          className={`${knopKlasse("ghost", "sm")} relative max-w-full gap-1.5 text-xs ${kort ? "overflow-hidden" : ""}`}>
          {stand.laden === "mislukt" && !stand.controleert && <Waarschuwing className="text-aandacht-geel-tekst" />}
          {kort && (
            <span className="inline-flex items-center gap-1.5 text-ink" data-connectors-kort>
              {samenvatting.tekst}
              {samenvatting.aandacht && <StatusLabel toon="geel" klein aria-hidden>{STAND_WOORD[samenvatting.aandacht]}</StatusLabel>}
            </span>
          )}
          {/* De volle regel staat er altijd: zo meet de knop of hij past. Past hij niet, dan is hij onzichtbaar en buiten de flow. */}
          <span ref={volRef} aria-hidden={kort || undefined}
            className={kort ? "pointer-events-none invisible absolute left-0 top-0 inline-flex items-center gap-1.5" : "inline-flex items-center gap-1.5"}>
          {menuRegel(stand).map((d, i) => (
            <span key={d.label} className={`inline-flex items-center gap-1 ${d.stand === "aan" ? "text-ink" : "text-muted"}`}
              data-bron={d.label} data-aan={d.stand === "aan" ? "" : undefined} data-stand={d.stand}>
              {i > 0 && <span aria-hidden className="text-muted">·</span>}
              {d.label}
              {d.stand === "aan" ? <Vinkje className="text-lint" />
                // Laden is geen oordeel: geen kleur en geen woord, alleen een gedempt label tot de stand er is.
                : d.stand === "laden" ? null
                : d.stand === "uit" ? <span aria-hidden className="text-muted">{STAND_WOORD.uit}</span>
                : <StatusLabel toon="geel" klein aria-hidden>{STAND_WOORD[d.stand]}</StatusLabel>}
            </span>
          ))}
          </span>
          <ChevronOmlaag className="text-muted" />
        </button>
      )}>
      {(sluit) => (
        <div>
          {melding && (
            <Melding type="waarschuwing" compact className="mx-1 mt-1" >
              <p data-connectors-melding>{melding}</p>
            </Melding>
          )}
          <p className="px-2 pb-1 pt-1.5 text-xs text-muted">
            Wetgeving staat altijd aan. Andere bronnen zijn geen wettekst. Lex citeert eruit met hun eigen vindplaats.
          </p>
          <MenuLijst>
            {stand.beschikbaar.map((c) => schakelbaar(c) ? (
              <MenuKeuze key={c.naam} gekozen={aan.includes(c.naam)} onClick={() => onWissel(c.naam)}>{c.label}</MenuKeuze>
            ) : (
              // Een schakelaar die niets doet, is erger dan geen (review ADR-013, punt 2).
              <li key={c.naam} role="none" data-connector-onbekend={c.beschikbaarheid === "onbekend" ? c.naam : undefined}
                data-connector-niet-aangeboden={c.beschikbaarheid === "niet_aangeboden" ? c.naam : undefined}>
                <span role="menuitem" aria-disabled="true" className={`${MENU_RIJ} cursor-default text-muted hover:bg-transparent`}>
                  {c.label} · {c.beschikbaarheid === "niet_aangeboden" ? REDEN.niet_aangeboden
                    : stand.controleert ? STAND_WOORD.laden : REDEN.onbekend}
                </span>
              </li>
            ))}
            {melding && onOpnieuw && (
              <MenuKnop onClick={() => onOpnieuw()}>Opnieuw proberen</MenuKnop>
            )}
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

/** Wat de knop naast de regel nodig heeft: de opvulling, de chevron en de tussenruimte. */
const KNOP_EXTRA_PX = 48;

/** Of de volle regel niet past in de ruimte die de werkplek het menu geeft (`[data-connectors-ruimte]`, anders de
 *  ouder). Gemeten, niet op een breakpoint: naast een open zijpaneel is de kolom op een breed scherm ook smal. */
function useTePast(volRef: React.RefObject<HTMLSpanElement | null>): boolean {
  const [kort, setKort] = useState(false);
  useLayoutEffect(() => {
    const vol = volRef.current;
    const ruimte = vol?.closest<HTMLElement>("[data-connectors-ruimte]") ?? vol?.parentElement?.parentElement;
    if (!vol || !ruimte || typeof ResizeObserver === "undefined") return;
    const meet = () => setKort(vol.scrollWidth + KNOP_EXTRA_PX > ruimte.clientWidth);
    meet();
    const waarnemer = new ResizeObserver(meet);
    waarnemer.observe(ruimte);
    waarnemer.observe(vol);
    return () => waarnemer.disconnect();
  });
  return kort;
}
