import { readFileSync } from "node:fs";
import { globSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  hervatIndex, indexVan, LEGE_STAND, moetStarten, RONDLEIDING_VERSIE, STAPPEN, vraagtArtefact,
  zichtbareStappen,
} from "./rondleiding";
import {
  DEMO_SLUG, demoBron, maakDemoDocument, maakDemoScene, pasDemoBeslissingToe,
  voegDemoElementToe, wisDemoElement, zetDemoStatus,
} from "./rondleidingDemo";
import { vindPositie } from "./selectie";
import { BESLIST_LIFECYCLES } from "./annotatie";

describe("de stappenlijst", () => {
  it("heeft unieke ids", () => {
    const ids = STAPPEN.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("loopt van oriëntatie naar afronding zonder terug te springen", () => {
    const orde = ["orientatie", "opdracht", "beoordelen", "afronding"];
    const posities = STAPPEN.map((s) => orde.indexOf(s.fase));
    expect(posities).toEqual([...posities].sort((a, b) => a - b));
  });

  it("opent het artefact pas nadat de stap erover is gegaan", () => {
    const eersteMetArtefact = STAPPEN.findIndex((s) => s.artefactOpen);
    // De stap die het artefact laat openen ("chip") staat er direct vóór en heeft hem zelf nog niet
    // nodig — anders wijst de rondleiding naar een paneel dat nog dicht is.
    expect(STAPPEN[eersteMetArtefact - 1].anker).toBe("chip");
    expect(STAPPEN[eersteMetArtefact - 1].artefactOpen).toBeUndefined();
  });

  it("laat elke stap iets aanwijzen", () => {
    for (const s of STAPPEN) expect(s.anker.length).toBeGreaterThan(0);
  });

  it("filtert beheerdersstappen weg voor een analist", () => {
    expect(zichtbareStappen(false).every((s) => !s.alleenBeheerder)).toBe(true);
    expect(zichtbareStappen(true).length).toBeGreaterThanOrEqual(zichtbareStappen(false).length);
  });

  it("weet welke stap het artefact nodig heeft", () => {
    const i = STAPPEN.findIndex((s) => s.artefactOpen);
    expect(vraagtArtefact(STAPPEN, i)).toBe(true);
    expect(vraagtArtefact(STAPPEN, 0)).toBe(false);
  });
});

describe("hervatten", () => {
  it("pakt de bewaarde stap op", () => {
    expect(hervatIndex(STAPPEN, STAPPEN[4].id)).toBe(4);
  });

  it("begint opnieuw als de bewaarde stap niet meer bestaat", () => {
    expect(hervatIndex(STAPPEN, "een-stap-die-weg-is")).toBe(0);
    expect(hervatIndex(STAPPEN, undefined)).toBe(0);
  });

  it("kent geen stap zonder id", () => {
    expect(indexVan(STAPPEN, undefined)).toBe(-1);
  });
});

describe("moetStarten", () => {
  it("start bij een lege stand", () => {
    expect(moetStarten(LEGE_STAND)).toBe(true);
  });

  it("start niet meer na afronden", () => {
    expect(moetStarten({ versie: RONDLEIDING_VERSIE, gezien: true })).toBe(false);
  });

  it("biedt zich opnieuw aan na een nieuwe versie", () => {
    expect(moetStarten({ versie: RONDLEIDING_VERSIE - 1, gezien: true })).toBe(true);
  });
});

describe("de voorbeeldscène", () => {
  it("markeert uitsluitend fragmenten die letterlijk in de wettekst staan", () => {
    const doc = maakDemoDocument();
    const bron = demoBron();
    const bezet: { start: number; eind: number }[] = [];
    for (const el of doc.elementen) {
      expect(el.anker, `${el.klasse} — "${el.tekst}"`).not.toBeNull();
      // Zelfde terugvindweg als het documentpaneel: staat de markering niet, dan zweeft hij.
      const pos = vindPositie(bron, el.tekst, el.anker, bezet);
      expect(pos, `${el.klasse} — "${el.tekst}"`).toBeGreaterThanOrEqual(0);
      bezet.push({ start: pos, eind: pos + el.tekst.length });
    }
  });

  it("laat de markeringen niet overlappen", () => {
    const bereiken = maakDemoDocument()
      .elementen.map((el) => el.anker!)
      .sort((a, b) => a.start - b.start);
    for (let i = 1; i < bereiken.length; i++) {
      expect(bereiken[i].start).toBeGreaterThanOrEqual(bereiken[i - 1].eind);
    }
  });

  it("begint met alles nog te beoordelen", () => {
    const doc = maakDemoDocument();
    expect(doc.elementen.length).toBeGreaterThan(5);
    expect(doc.elementen.every((el) => !BESLIST_LIFECYCLES.includes(el.lifecycle))).toBe(true);
  });

  it("toont alle drie de aandachtniveaus", () => {
    const niveaus = new Set(maakDemoDocument().elementen.map((el) => el.aandacht));
    expect(niveaus).toEqual(new Set(["groen", "geel", "rood"]));
  });

  it("levert een thread met een annotatie die naar het voorbeelddocument wijst", () => {
    const scene = maakDemoScene();
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip).toBeDefined();
    expect(chip!.type === "annotatie" && chip!.slug).toBe(DEMO_SLUG);
    expect(scene.docs[DEMO_SLUG]).toBeDefined();
    expect(scene.infos[DEMO_SLUG]).toBeDefined();
  });

  it("draagt overal het voorbeeld-label", () => {
    const scene = maakDemoScene();
    expect(scene.docs[DEMO_SLUG].citeertitel).toContain("VOORBEELD");
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip!.type === "annotatie" && chip!.titel).toContain("VOORBEELD");
  });

  it("bouwt elke keer een schone lei", () => {
    const eerste = maakDemoDocument();
    const beslist = pasDemoBeslissingToe(eerste, eerste.elementen[0].id, { type: "approve", comment: "" });
    expect(beslist.elementen[0].lifecycle).toBe("human_approved");
    // Het origineel blijft ongemoeid, en een volgende start begint weer bij nul.
    expect(eerste.elementen[0].lifecycle).toBe("critic_checked");
    expect(maakDemoDocument().elementen[0].lifecycle).toBe("critic_checked");
  });
});

describe("de demo-mutaties", () => {
  it("verwerpt een voorstel zonder het te wissen", () => {
    const doc = maakDemoDocument();
    const na = pasDemoBeslissingToe(doc, doc.elementen[1].id, {
      type: "reject", comment: "", review_reason: "verkeerde_klasse",
    });
    expect(na.elementen).toHaveLength(doc.elementen.length);
    expect(na.elementen[1].lifecycle).toBe("rejected");
  });

  it("neemt een klassewijziging over", () => {
    const doc = maakDemoDocument();
    const na = pasDemoBeslissingToe(doc, doc.elementen[0].id, {
      type: "edit", comment: "", wijziging: { klasse: "Rechtssubject" },
    });
    expect(na.elementen[0].klasse).toBe("Rechtssubject");
    expect(na.elementen[0].lifecycle).toBe("edited");
    expect(na.elementen[0].gewijzigd_door).toBe("mens");
  });

  it("zet een eigen markering er meteen goedgekeurd bij en wist hem weer", () => {
    const doc = maakDemoDocument();
    const bron = demoBron();
    const { doc: bij, id } = voegDemoElementToe(doc, {
      klasse: "Rechtsobject", tekst: "het aanslagbiljet", lid: "1", toelichting: "",
      anker: { lid: "1", start: 0, eind: 16, voor: "", na: "", bron_hash: "" },
    });
    expect(bron.length).toBeGreaterThan(0);
    expect(bij.elementen).toHaveLength(doc.elementen.length + 1);
    expect(bij.elementen.at(-1)!.lifecycle).toBe("human_approved");
    expect(bij.elementen.at(-1)!.herkomst).toBe("mens");
    expect(wisDemoElement(bij, id).elementen).toHaveLength(doc.elementen.length);
  });

  it("rondt af en heropent", () => {
    const doc = maakDemoDocument();
    expect(zetDemoStatus(doc, "geaccordeerd").status).toBe("geaccordeerd");
    expect(zetDemoStatus(zetDemoStatus(doc, "geaccordeerd"), "in_review").status).toBe("in_review");
  });
});

describe("de ankers bestaan echt", () => {
  // Een stap die naar een `data-tour` wijst dat niemand meer zet, valt stil terug op een
  // gecentreerde kaart: de rondleiding breekt niet, maar wijst ook niets meer aan — en dat merk je
  // pas als je hem zelf doorloopt. Vandaar deze koppeling aan de bron.
  const bron = readFileSync(new URL("./rondleiding.test.ts", import.meta.url).pathname, "utf-8");
  const componenten = globSync("components/**/*.tsx").map((p) => readFileSync(p, "utf-8")).join("\n");

  /** Staat dit anker ergens in de componenten? Twee vormen tellen mee: het letterlijke attribuut,
   *  en de expressievorm (`data-tour={eerste ? "review-kaart" : undefined}`) die de reviewlijst
   *  gebruikt om alleen de bovenste kaart te markeren. */
  const gezet = (sleutel: string) =>
    componenten.includes(`data-tour="${sleutel}"`) ||
    (componenten.includes("data-tour={") && componenten.includes(`"${sleutel}"`));

  it("vindt elk anker terug in een component", () => {
    expect(bron.length).toBeGreaterThan(0);
    for (const stap of STAPPEN) {
      expect(gezet(stap.anker), `anker "${stap.anker}" (stap ${stap.id})`).toBe(true);
      if (stap.ankerSmal) expect(gezet(stap.ankerSmal), `anker "${stap.ankerSmal}"`).toBe(true);
    }
  });

  it("valt niet voor een anker dat nergens staat", () => {
    expect(gezet("dit-anker-bestaat-niet")).toBe(false);
  });
});
