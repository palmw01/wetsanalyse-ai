"use client";

import Link from "next/link";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { icoonKnopKlasse } from "@/components/ui/Button";
import { Meer, Prullenbak, Vinkje } from "@/components/ui/Icoon";
import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";
import { Popover } from "@/components/ui/Popover";

/** Het ene ⋯-menu van Lex (5 nov 2026, besluit gebruiker: overal gelijk). Bij een werkgebied, een deelvraag, een bron,
 *  een gesprek in de kop en in de zijbalk: dezelfde knop, hetzelfde paneel, dezelfde regels.
 *
 *  - **De knop** (`MeerKnop`) is een icoonknop (`icoonKnopKlasse`): een vierkantje met de vorm van *Bewerken* ernaast,
 *    `xs` in een rij (24px), `sm` in een kop naast knoppen van 32px.
 *  - **Het paneel** is `MENU_PANEEL`, de regels zijn `MENU_RIJ` met een icoon ervoor (`MenuKnop`); een keuze die meteen
 *    geldt (een rol) is een `MenuKeuze` met een vinkje bij wat nu geldt.
 *  - **Verwijderen staat onderaan, rood, met een prullenbak** (`MenuVerwijder`), en vraagt een tweede klik op dezelfde
 *    plek (*Verwijderen?*). Geen losse knop in het menu: dan ziet hetzelfde menu er per plek anders uit.
 *  - Wat niet in het ⋯-menu hoort: *Bewerken* (bij het blok zelf, `BewerkKnop`) en de hoofdknoppen van een kop. */

type Maat = "xs" | "sm";

export function MeerKnop({ label, open, onClick, maat = "xs", className = "" }: {
  /** De toegankelijke naam: waarvan dit het menu is ("Acties: Wie is belastingschuldige?"). */
  label: string;
  open: boolean;
  onClick: () => void;
  maat?: Maat;
  className?: string;
}) {
  return (
    <button type="button" onClick={onClick} aria-expanded={open} aria-haspopup="menu" aria-label={label} title="Meer"
      data-meer-knop className={`${icoonKnopKlasse(maat)} ${className}`}>
      <Meer />
    </button>
  );
}

/** Knop plus paneel. `children` krijgt `sluit`, zodat een regel het menu dichtdoet. */
export function MeerMenu({ label, maat = "xs", breedte = "w-56", children }: {
  label: string;
  maat?: Maat;
  breedte?: string;
  children: (sluit: () => void) => React.ReactNode;
}) {
  return (
    <Popover ariaLabel={label} className={`${breedte} ${MENU_PANEEL}`}
      trigger={(open, toggle) => <MeerKnop label={label} open={open} onClick={toggle} maat={maat} />}>
      {(sluit) => <MenuLijst>{children(sluit)}</MenuLijst>}
    </Popover>
  );
}

/** De lijst in het paneel; ook voor een menu dat inline onder een rij openklapt (de zijbalk scrolt). */
export function MenuLijst({ children }: { children: React.ReactNode }) {
  return <ul role="menu" className="flex flex-col" data-meer-menu>{children}</ul>;
}

/** Een handeling. `gevaar`: een verwijderen dat eerst een eigen bevestiging toont (een gesprek: archiveren of
 *  definitief) – rood en onderaan, zoals `MenuVerwijder`. */
export function MenuKnop({ icoon, onClick, children, ariaLabel, gevaar = false }: {
  icoon?: React.ReactNode;
  onClick: () => void;
  children: React.ReactNode;
  ariaLabel?: string;
  gevaar?: boolean;
}) {
  return (
    <li role="none" className={gevaar ? ONDERAAN : undefined}>
      <button type="button" role="menuitem" className={`${MENU_RIJ} ${gevaar ? "text-fout" : ""}`} onClick={onClick}
        aria-label={ariaLabel}>
        <Icoonplek kleur={gevaar ? "text-fout" : undefined}>{icoon}</Icoonplek>{children}
      </button>
    </li>
  );
}

/** Een regel die naar een pagina gaat: een echte link, zodat de bewaker van niet-bewaarde wijzigingen hem ziet. */
export function MenuLink({ icoon, href, children, ariaLabel }: {
  icoon?: React.ReactNode;
  href: string;
  children: React.ReactNode;
  ariaLabel?: string;
}) {
  return (
    <li role="none">
      <Link role="menuitem" href={href} className={MENU_RIJ} aria-label={ariaLabel}>
        <Icoonplek>{icoon}</Icoonplek>{children}
      </Link>
    </li>
  );
}

const ONDERAAN = "mt-1 border-t border-line pt-1";

/** Een keuze die meteen geldt, met een vinkje bij wat nu geldt (een rol). */
export function MenuKeuze({ gekozen, onClick, children }: { gekozen: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <li role="none">
      <button type="button" role="menuitemradio" aria-checked={gekozen} className={MENU_RIJ} onClick={onClick}>
        <Icoonplek kleur="text-lint">{gekozen && <Vinkje />}</Icoonplek>{children}
      </button>
    </li>
  );
}

/** Verwijderen: onderaan, rood, tweede klik bevestigt. `titel` zegt wat er weggaat en wat blijft. */
export function MenuVerwijder({ onBevestig, ariaLabel, titel, vraag = "Verwijderen?", children = "Verwijderen" }: {
  onBevestig: () => void | Promise<void>;
  ariaLabel?: string;
  titel?: string;
  /** De vraag bij de eerste klik, als het niet *Verwijderen?* is (bv. *Losmaken?*). */
  vraag?: string;
  children?: React.ReactNode;
}) {
  return (
    <li role="none" className={ONDERAAN}>
      <BevestigKnop role="menuitem" bevestigTekst={vraag} ariaLabel={ariaLabel} titel={titel} onBevestig={onBevestig}
        className={`${MENU_RIJ} text-fout`} bevestigClassName="bg-fout/10 font-medium">
        <Icoonplek kleur="text-fout"><Prullenbak /></Icoonplek>{children}
      </BevestigKnop>
    </li>
  );
}

/** Een vaste plek voor het icoon, zodat de tekst van elke regel op dezelfde lijn begint. */
function Icoonplek({ children, kleur = "text-muted" }: { children?: React.ReactNode; kleur?: string }) {
  return <span aria-hidden className={`inline-flex w-4 shrink-0 justify-center ${kleur}`}>{children}</span>;
}
