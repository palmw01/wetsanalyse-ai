import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Structuurcontrole op de tokenbudget-blokkade in de werkplek.
 *
 *  Vitest draait hier node-only en rendert geen componenten, dus `disabled` op een knop is niet te
 *  meten. Wat wél te bewaken is, is de regel die deze hele klasse fouten sluit — en die is precies
 *  ontstaan uit een fout: de eerste versie schermde alleen de verzendknop af, waarna je via de
 *  voorbeeldvragen, de kandidatenlijst en het beginscherm alsnog een beurt kon starten. Per knop
 *  testen zou diezelfde fout herhalen; de guard in `verstuur()` is het enige dat álle paden dekt,
 *  ook die er later bij komen.
 */
const BRON = readFileSync(join(__dirname, "WerkplekClient.tsx"), "utf8");

/** De body van `verstuur()`, tot aan de volgende top-level functie. */
function verstuurBody(): string {
  const start = BRON.indexOf("async function verstuur(");
  expect(start, "verstuur() niet gevonden – is hij hernoemd?").toBeGreaterThan(-1);
  const rest = BRON.slice(start);
  const eind = rest.indexOf("\n  function ", 1);
  return eind > 0 ? rest.slice(0, eind) : rest;
}

describe("tokenbudget-blokkade", () => {
  it("verstuur() weigert een beurt zodra het budget op is", () => {
    // Zonder deze guard is elke knop een eigen achterdeur.
    expect(verstuurBody()).toMatch(/if\s*\(geblokkeerd\)\s*return;/);
  });

  it("de guard staat vóór het aanmaken van een gesprek", () => {
    // Anders ontstaat er bij een geweigerde vraag alsnog een leeg gesprek in de sidebar.
    const body = verstuurBody();
    expect(body.indexOf("if (geblokkeerd) return;")).toBeLessThan(body.indexOf("maakGesprek("));
  });

  it("leidt `geblokkeerd` af uit de serverstand, niet uit een eigen berekening", () => {
    // De api bepaalt of iemand geblokkeerd is; zou de browser zelf rekenen, dan kan de invoer
    // dichtgaan op een ander moment dan waarop de server weigert.
    expect(BRON).toMatch(/const geblokkeerd = Boolean\(verbruik\?\.actief && verbruik\.geblokkeerd\)/);
  });

  it("schakelt de knoppen uit die anders om de invoerbalk heen gaan", () => {
    // De zichtbare helft: de knoppen blijven staan, maar reageren niet. Dat is een aanvulling op de
    // guard hierboven, geen vervanging ervan.
    const knoppen = BRON.match(/disabled=\{geblokkeerd\}/g) ?? [];
    expect(knoppen.length).toBeGreaterThanOrEqual(2);
    expect(BRON).toContain("uitgeschakeld={bezig || geblokkeerd}");
  });
});
