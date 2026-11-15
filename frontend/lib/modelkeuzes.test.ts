import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { STANDAARD, gebruiktDoor, keuzesVoor, modelTekst, parseOverzicht, parseStand, sleutelVanProfiel } from "./modelkeuzes";

const BRONMODEL = join(__dirname, "..", "..", "packages", "bronmodel", "bronmodel", "modelkeuzes.py");
const sleutel = (s: string, soort: "agent" | "stap" = "agent") => ({ sleutel: s, soort, label: s, groep: "g", beschrijving: "b" });

describe("de sleutels volgen het bronmodel", () => {
  it("een agentprofiel heet agent:<naam>, net als in bronmodel.modelkeuzes", () => {
    expect(readFileSync(BRONMODEL, "utf8")).toContain('Modelkeuze(f"agent:{naam}"');
    expect(sleutelVanProfiel("agentprofiel/definitie")).toBe("agent:definitie");
  });
});

describe("parseStand", () => {
  it("laat een rij die niet klopt weg, en zonder sleutels is er geen stand", () => {
    const s = parseStand({ standaard: { profiel: "p", model: "claude-x", bron: "standaard" },
      keuzes: { "agent:a": { profiel: "p", model: "claude-x", bron: "keuze" }, "agent:b": { profiel: 3 } },
      sleutels: [sleutel("agent:a"), { sleutel: "x" }] });
    expect(Object.keys(s!.keuzes)).toEqual(["agent:a"]);
    expect(s!.sleutels.map((x) => x.sleutel)).toEqual(["agent:a"]);
    expect(parseStand({ keuzes: {} })).toBeNull();
  });
});

describe("modelTekst", () => {
  it("zegt of het een keuze of de standaard is, en zonder model het model van de omgeving", () => {
    expect(modelTekst({ profiel: "snel", model: "claude-haiku", bron: "keuze" })).toBe("snel (claude-haiku)");
    expect(modelTekst({ profiel: "std", model: "claude-sonnet", bron: "standaard" })).toBe("standaard (claude-sonnet)");
    expect(modelTekst(undefined)).toBe("het model van de omgeving");
  });
});

describe("het beheer", () => {
  const o = parseOverzicht({ standaard: "std", standaard_model: "claude-sonnet", standaard_niet_bruikbaar: "",
    keuzes: [{ ...sleutel("agent:definitie"), label: "Definitie", profiel: "snel" }, { ...sleutel("stap:intake", "stap"), label: "Werkgebied samenstellen", profiel: null }],
    profielen: { snel: { niet_bruikbaar: "", gebruikt_door: ["agent:definitie"] },
      ander: { niet_bruikbaar: "Het profiel heeft een ander endpoint dan de straat.", gebruikt_door: [] } } })!;

  it("Standaard eerst (met het model), dan de profielen op naam; een onbruikbaar profiel staat uit met de reden", () => {
    const k = keuzesVoor(o);
    expect(k[0]).toMatchObject({ waarde: STANDAARD, label: "Standaard (claude-sonnet)", uit: false });
    expect(k.slice(1).map((x) => x.waarde)).toEqual(["ander", "snel"]);
    expect(k[1]).toMatchObject({ uit: true, reden: "Het profiel heeft een ander endpoint dan de straat." });
  });

  it("vult ontbrekende velden aan en noemt waar een profiel gekozen is bij label", () => {
    expect(o.keuzes[0]).toMatchObject({ waarschuwing: "", niet_bruikbaar: "", door: "" });
    expect(gebruiktDoor(o, "snel")).toEqual(["Definitie"]);
    expect(gebruiktDoor(o, "onbekend")).toEqual([]);
  });
});
