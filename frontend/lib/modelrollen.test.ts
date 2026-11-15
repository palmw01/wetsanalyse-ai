import { describe, expect, it } from "vitest";
import { groepeerModelrollen, keuzesVoorRol, STANDAARD_WAARDE } from "./modelrollen";
import type { Modelrol, ModelrollenOverzicht } from "./types";

const rol = (naam: string, groep: string, profiel: string | null = null): Modelrol => ({
  naam, label: naam, groep, beschrijving: "", waarschuwing: "", profiel, model: "", niet_bruikbaar: "", door: "",
  bijgewerkt: "",
});

const stand = (rollen: Modelrol[]): ModelrollenOverzicht => ({
  standaard: "sonnet", standaard_model: "claude-sonnet-4-6", standaard_niet_bruikbaar: "", rollen,
  profielen: { sonnet: "", licht: "", elders: "Het profiel heeft een ander endpoint dan de straat." },
});

describe("model per rol", () => {
  it("groepeert in de volgorde van de api", () => {
    const g = groepeerModelrollen([rol("a", "Gesprek"), rol("b", "Annoteren"), rol("c", "Gesprek")]);
    expect(g.map(([n, r]) => [n, r.map((x) => x.naam)])).toEqual([["Gesprek", ["a", "c"]], ["Annoteren", ["b"]]]);
  });

  it("zet de standaard voorop en schakelt een onbruikbaar profiel uit", () => {
    const r = rol("supervisor", "Gesprek");
    const k = keuzesVoorRol(stand([r]), r);
    expect(k[0]).toEqual({ waarde: STANDAARD_WAARDE, label: "Standaard (sonnet)", uit: false });
    expect(k.find((x) => x.waarde === "elders")?.uit).toBe(true);
    expect(k.find((x) => x.waarde === "licht")?.uit).toBe(false);
  });

  it("houdt een gekozen profiel kiesbaar, ook als het onbruikbaar werd of verdween", () => {
    const onbruikbaar = rol("ophaal", "Annoteren", "elders");
    expect(keuzesVoorRol(stand([onbruikbaar]), onbruikbaar).find((x) => x.waarde === "elders")?.uit).toBe(false);
    const weg = rol("ophaal", "Annoteren", "verdwenen");
    expect(keuzesVoorRol(stand([weg]), weg).at(-1)).toEqual({ waarde: "verdwenen", label: "verdwenen (bestaat niet meer)", uit: false });
  });
});
